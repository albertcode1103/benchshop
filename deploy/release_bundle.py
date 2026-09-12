"""Build a private, verified release bundle. Never replaces a running database.

Run with --check first. Packaging requires a clean Git tree, a quiescent source,
and all referenced static pictures tracked as real files (not LFS pointers).
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
from urllib.parse import unquote

from PIL import Image, UnidentifiedImageError
from reportlab.pdfbase.ttfonts import TTFError, TTFont

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico'}
RASTER_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
REQUIRED_RELEASE_ASSETS = {
    'tb/site/BOTEN.png',
    'assets/fonts/harmonyos-sans/HarmonyOS_Sans.ttf',
    'assets/fonts/harmonyos-sans/HarmonyOS_Sans_Italic.ttf',
    'assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf',
    'assets/fonts/harmonyos-sans/LICENSE.txt',
}
PRIVATE_PARTS = {'.git', '.venv', '.venv312', 'tmp', 'data', 'backups', 'migration-backups', 'uploads', '__pycache__', 'output', 'outputs'}
CSS_URL_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def validate_raster_image(path):
    """Raise ValueError when a release image is unreadable before packaging."""
    if path.suffix.lower() not in RASTER_IMAGE_EXTENSIONS:
        return
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
        raise ValueError('Unreadable static asset: {} ({})'.format(path, error)) from error


def validate_font(path):
    """Raise ValueError unless a bundled TrueType font can actually be parsed."""
    try:
        TTFont('_release_validation_font_', str(path), validate=1)
    except (OSError, ValueError, KeyError, IndexError, TypeError, TTFError) as error:
        raise ValueError('Unreadable required font: {} ({})'.format(path, error)) from error


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


def validate_path_case(root, relative):
    """Reject paths that only resolve on a case-insensitive developer filesystem."""
    current = root
    for part in Path(relative).parts:
        if not current.is_dir():
            return
        names = {entry.name for entry in current.iterdir()}
        if part not in names and any(name.casefold() == part.casefold() for name in names):
            raise ValueError('Path casing mismatch: ' + relative)
        current = current / part


def validate_css_urls(root, tracked, blockers):
    """Check local CSS resources before a case-sensitive target deployment."""
    for relative in sorted(path for path in tracked if path.endswith('.css')):
        stylesheet = safe_path(root, relative)
        if not stylesheet.is_file():
            continue
        for _, raw_url in CSS_URL_PATTERN.findall(stylesheet.read_text(encoding='utf-8')):
            value = unquote(raw_url.split('?', 1)[0].split('#', 1)[0].strip())
            if not value or value.startswith(('data:', 'http:', 'https:', '//', '#', 'var(')):
                continue
            candidate = Path(os.path.normpath(str(stylesheet.parent / value)))
            try:
                target_relative = candidate.relative_to(root).as_posix()
            except ValueError:
                blockers.append('Unsafe CSS resource path: {} -> {}'.format(relative, raw_url))
                continue
            try:
                validate_path_case(root, target_relative)
            except ValueError as error:
                blockers.append(str(error))
                continue
            resolved = candidate.resolve()
            if not resolved.is_file():
                blockers.append('Missing CSS resource: {} -> {}'.format(relative, raw_url))


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
    for relative in sorted(REQUIRED_RELEASE_ASSETS):
        if relative not in tracked:
            blockers.append('Untracked required release asset: ' + relative)
            continue
        try:
            path = safe_path(root, relative)
            validate_path_case(root, relative)
            if not path.is_file():
                blockers.append('Missing required release asset: ' + relative)
            elif relative.endswith('.ttf'):
                validate_font(path)
            elif path.suffix.lower() in RASTER_IMAGE_EXTENSIONS:
                validate_raster_image(path)
        except ValueError as error:
            blockers.append(str(error))
    if (root / 'alembic.ini').is_file():
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'backend/migrations'))
        if {version} != set(ScriptDirectory.from_config(config).get_heads()):
            blockers.append('Database migration does not match release code')
    files = {}
    validate_css_urls(root, tracked, blockers)
    for relative in sorted(tracked):
        p = Path(relative)
        if set(p.parts) & PRIVATE_PARTS or p.suffix.lower() in {'.db','.sqlite','.sqlite3','.xls','.xlsx','.psd','.zip','.pdf'} or (p.name.startswith('.env') and p.name != '.env.example'):
            continue
        path = safe_path(root, relative)
        try:
            validate_path_case(root, relative)
        except ValueError as error:
            blockers.append(str(error))
            continue
        if not path.is_file():
            blockers.append('Missing tracked file: ' + relative)
            continue
        try:
            validate_raster_image(path)
        except ValueError as error:
            blockers.append(str(error))
        with path.open('rb') as stream:
            if stream.read(80).startswith(b'version https://git-lfs.github.com/spec/v1'):
                blockers.append('Missing LFS entity: ' + relative)
        files['code/' + relative] = path
    for ref in sorted(refs | {'tb/site/BOTEN.png'}):
        if ref.startswith('api/v1/media/'):
            relative = ref[len('api/v1/media/'):]
            candidate = safe_path(uploads, relative)
            if not candidate.is_file(): blockers.append('Missing upload: ' + ref)
            else:
                try: validate_raster_image(candidate)
                except ValueError as error: blockers.append(str(error))
        elif ref.startswith('uploads/'):
            blockers.append('Unsupported legacy upload path; explicit mapping required: ' + ref)
        else:
            candidate = safe_path(root, ref)
            if ref not in tracked: blockers.append('Untracked referenced static asset: ' + ref)
            try:
                validate_path_case(root, ref)
            except ValueError as error:
                blockers.append(str(error))
                continue
            if not candidate.is_file(): blockers.append('Missing static asset: ' + ref)
            else:
                try: validate_raster_image(candidate)
                except ValueError as error: blockers.append(str(error))
    # Keep all uploads: historical JSON may contain paths not represented in live rows.
    if uploads.is_dir():
        for path in sorted(uploads.rglob('*')):
            if path.is_file():
                relative = path.relative_to(uploads).as_posix()
                try:
                    validate_raster_image(path)
                except ValueError as error:
                    blockers.append(str(error))
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
    for name, expected in hashes.items():
        if digest(files[name]) != expected:
            raise ValueError('Source changed while archiving: ' + name)
    report.update(files=hashes, archive_sha256=digest(archive))
    verify_archive(archive, report)
    (output / 'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def verify_archive(archive, manifest):
    """Verify a received release archive against its separately transferred manifest.

    This deliberately reads and hashes every member before any receiver extracts
    it, so a partial or corrupted transfer cannot be mistaken for a valid bundle.
    """
    archive = Path(archive)
    expected_files = dict(manifest.get('files') or {})
    expected_archive_hash = str(manifest.get('archive_sha256') or '')
    if not expected_archive_hash or digest(archive) != expected_archive_hash:
        raise ValueError('Release archive checksum does not match manifest')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)) or set(names) != set(expected_files):
            raise ValueError('Release archive file list does not match manifest')
        for member in members:
            if not member.isfile() or member.issym() or member.islnk():
                raise ValueError('Unsafe release archive member: ' + member.name)
            stream = tar.extractfile(member)
            if stream is None:
                raise ValueError('Unreadable release archive member: ' + member.name)
            actual = hashlib.sha256(stream.read()).hexdigest()
            if actual != expected_files[member.name]:
                raise ValueError('Release archive member checksum does not match manifest: ' + member.name)
    return True


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
