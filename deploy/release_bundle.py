"""Build a private, verified release bundle. Never replaces a running database.

Run with --check first. Packaging requires a clean Git tree, a quiescent source,
and all referenced static pictures tracked as real files (not LFS pointers).
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile
from urllib.parse import unquote

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico'}
PRIVATE_PARTS = {'.git', '.venv', '.venv312', 'tmp', 'data', 'backups', 'migration-backups', 'uploads', '__pycache__', 'output', 'outputs'}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def safe_path(root, relative):
    if '\\' in relative or ':' in relative or relative.startswith('/'):
        raise ValueError('Unsafe release path: ' + relative)
    parts = Path(relative).parts
    if not parts or '..' in parts:
        raise ValueError('Unsafe release path: ' + relative)
    path = root.joinpath(relative)
    if not path.resolve().is_relative_to(root.resolve()) or any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)):
        raise ValueError('Symlink or escaping release path: ' + relative)
    return path


def database_info(database):
    refs, counts = set(), {}
    def visit(value):
        if isinstance(value, dict):
            for part in value.values(): visit(part)
        elif isinstance(value, (list, tuple)):
            for part in value: visit(part)
        elif isinstance(value, str):
            if value.startswith(('tb/', '/tb/', 'assets/', '/assets/', '/api/v1/media/', 'uploads/', '/uploads/')):
                reference = unquote(value.lstrip('/'))
                if Path(reference).suffix.lower() in IMAGE_EXTENSIONS:
                    refs.add(reference)
            elif value.startswith(('{', '[')):
                try: nested = json.loads(value)
                except ValueError: return
                visit(nested)
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database integrity/foreign-key check failed')
        version = db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            cursor = db.execute('SELECT * FROM "' + table.replace('"','""') + '"')
            counts[table] = 0
            for row in cursor:
                counts[table] += 1
                visit(row)
    return version, counts, refs


def inspect(root, database, uploads):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args]).decode('utf-8')
    tracked = set(git('ls-files', '-z').split('\0')) - {''}
    blockers = []
    if git('status', '--porcelain', '--untracked-files=normal').strip():
        blockers.append('Git worktree is not clean; review and commit release files first')
    version, counts, refs = database_info(database)
    if (root / 'alembic.ini').is_file():
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'backend/migrations'))
        if {version} != set(ScriptDirectory.from_config(config).get_heads()):
            blockers.append('Database migration does not match release code')
    files = {}
    for relative in sorted(tracked):
        p = Path(relative)
        if set(p.parts) & PRIVATE_PARTS or p.suffix.lower() in {'.db','.sqlite','.sqlite3','.xls','.xlsx','.psd','.zip','.pdf'} or (p.name.startswith('.env') and p.name != '.env.example'):
            continue
        path = safe_path(root, relative)
        if not path.is_file():
            blockers.append('Missing tracked file: ' + relative)
            continue
        with path.open('rb') as stream:
            if stream.read(80).startswith(b'version https://git-lfs.github.com/spec/v1'):
                blockers.append('Missing LFS entity: ' + relative)
        files['code/' + relative] = path
    for ref in sorted(refs | {'tb/site/BOTEN.png'}):
        if ref.startswith('api/v1/media/'):
            relative = ref[len('api/v1/media/'):]
            candidate = safe_path(uploads, relative)
            if not candidate.is_file(): blockers.append('Missing upload: ' + ref)
        elif ref.startswith('uploads/'):
            blockers.append('Unsupported legacy upload path; explicit mapping required: ' + ref)
        else:
            candidate = safe_path(root, ref)
            if ref not in tracked: blockers.append('Untracked referenced static asset: ' + ref)
            if not candidate.is_file(): blockers.append('Missing static asset: ' + ref)
    # Keep all uploads: historical JSON may contain paths not represented in live rows.
    if uploads.is_dir():
        for path in sorted(uploads.rglob('*')):
            if path.is_file():
                relative = path.relative_to(uploads).as_posix()
                files['data/uploads/catalog/' + relative] = safe_path(uploads, relative)
    return {'commit':git('rev-parse','HEAD').strip(), 'migration':version, 'table_counts':counts,
            'image_reference_count':len(refs), 'blockers':blockers}, files


def build(root, database, uploads, output):
    if output.exists(): raise ValueError('Output exists; refusing overwrite')
    if any(output.resolve().is_relative_to(root / part) for part in ('admin','account','assets','tb','css','js')):
        raise ValueError('Release database must not be stored in a public asset directory')
    report, files = inspect(root, database, uploads)
    if report['blockers']: raise ValueError('\n'.join(report['blockers']))
    output.mkdir(parents=True)
    snapshot = output / 'boten.db'
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(snapshot)) as target:
        source.backup(target)
    version, counts, snapshot_refs = database_info(snapshot)
    if version != report['migration'] or counts != report['table_counts']:
        raise ValueError('Source changed while packaging; stop source editing and retry in a new directory')
    _, _, current_refs = database_info(database)
    if snapshot_refs != current_refs:
        raise ValueError('Image references changed while packaging; retry after stopping source editing')
    for ref in snapshot_refs:
        name = 'data/uploads/catalog/' + ref[len('api/v1/media/'):] if ref.startswith('api/v1/media/') else 'code/' + ref
        if name not in files:
            raise ValueError('Snapshot image absent from release: ' + ref)
    files['data/boten.db'] = snapshot
    hashes = {name:digest(path) for name,path in files.items()}
    archive = output / 'release.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name,path in sorted(files.items()): tar.add(path, arcname=name, recursive=False)
    with tarfile.open(archive, 'r:gz') as tar:
        for name,expected in hashes.items():
            with tar.extractfile(name) as stream:
                if hashlib.sha256(stream.read()).hexdigest() != expected: raise ValueError('Source changed while archiving: ' + name)
    report.update(files=hashes, archive_sha256=digest(archive))
    (output / 'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--uploads', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check:
        report, _ = inspect(root,args.database,args.uploads)
    elif args.output:
        report = build(root,args.database,args.uploads,args.output)
    else:
        parser.error('Choose --check or --output')
    print(json.dumps({k:v for k,v in report.items() if k != 'files'},ensure_ascii=False,indent=2))
    return 1 if report.get('blockers') else 0


if __name__ == '__main__':
    raise SystemExit(main())
