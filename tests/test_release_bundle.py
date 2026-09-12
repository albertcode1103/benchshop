import json
import sqlite3
import subprocess
import tarfile
import base64
import shutil
from io import BytesIO
from pathlib import Path
import pytest
import deploy.release_bundle as release_bundle
from deploy.release_bundle import build, database_info, digest, inspect, safe_path, verify_archive


@pytest.fixture
def release_source(tmp_path):
    root = tmp_path / 'repo'; root.mkdir()
    (root / 'tb/site').mkdir(parents=True)
    (root / 'assets/fonts/harmonyos-sans').mkdir(parents=True)
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==')
    (root / 'tb/site/BOTEN.png').write_bytes(png)
    source_fonts = Path(release_bundle.__file__).resolve().parents[1] / 'assets/fonts/harmonyos-sans'
    for name in ('HarmonyOS_Sans.ttf', 'HarmonyOS_Sans_Italic.ttf', 'HarmonyOS_Sans_SC.ttf', 'LICENSE.txt'):
        source = source_fonts / ('HarmonyOS_Sans.ttf' if name.endswith('.ttf') else name)
        shutil.copyfile(source, root / 'assets/fonts/harmonyos-sans' / name)
    (root / 'index.html').write_text('<html>fixture</html>')
    subprocess.run(['git','init',str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'add','index.html','tb/site/BOTEN.png','assets'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.com','commit','-m','fixture'],check=True,capture_output=True)
    database = tmp_path / 'source.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE alembic_version(version_num TEXT)')
        db.execute("INSERT INTO alembic_version VALUES ('test')")
        db.execute('CREATE TABLE records(snapshot TEXT)')
        db.execute('INSERT INTO records VALUES (?)',(json.dumps({'image':'/tb/site/BOTEN.png'}),))
    uploads = tmp_path / 'uploads'; uploads.mkdir()
    (uploads / 'historical.png').write_bytes(png)
    return root,database,uploads


def test_private_bundle_contains_verified_snapshot_and_uploads(release_source,tmp_path):
    root,database,uploads=release_source
    output=tmp_path/'release'
    report=build(root,database,uploads,output)
    assert not report['blockers']
    with tarfile.open(output/'release.tar.gz') as tar:
        assert set(tar.getnames()) == {
            'code/index.html', 'code/tb/site/BOTEN.png',
            'code/assets/fonts/harmonyos-sans/HarmonyOS_Sans.ttf',
            'code/assets/fonts/harmonyos-sans/HarmonyOS_Sans_Italic.ttf',
            'code/assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf',
            'code/assets/fonts/harmonyos-sans/LICENSE.txt',
            'data/boten.db', 'data/uploads/catalog/historical.png',
        }
    with pytest.raises(ValueError,match='overwrite'): build(root,database,uploads,output)


def test_missing_untracked_images_and_dirty_code_block_publication(release_source,tmp_path):
    root,database,uploads=release_source
    (root/'index.html').write_text('changed')
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO records VALUES ('/tb/missing.png')")
    report,_=inspect(root,database,uploads)
    assert any('not clean' in item for item in report['blockers'])
    assert any('Missing static' in item for item in report['blockers'])
    with pytest.raises(ValueError): build(root,database,uploads,tmp_path/'blocked')
    assert not (tmp_path/'blocked').exists()


def test_lfs_pointer_is_not_a_publishable_image(release_source):
    root,database,uploads=release_source
    (root/'tb/site/BOTEN.png').write_text('version https://git-lfs.github.com/spec/v1\noid sha256:missing\nsize 100\n')
    report,_=inspect(root,database,uploads)
    assert any('Missing LFS entity' in item for item in report['blockers'])


def test_missing_font_or_corrupt_referenced_image_blocks_publication(release_source):
    root,database,uploads=release_source
    (root/'assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf').unlink()
    (root/'tb/site/BOTEN.png').write_bytes(b'not a PNG')
    report,_=inspect(root,database,uploads)
    assert any('Missing required release asset' in item for item in report['blockers'])
    assert any('Unreadable static asset' in item for item in report['blockers'])


def test_nonempty_corrupt_font_and_historical_upload_block_publication(release_source):
    root,database,uploads=release_source
    (root/'assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf').write_bytes(b'not a font')
    (uploads/'historical.png').write_bytes(b'not a PNG')
    report,_=inspect(root,database,uploads)
    assert any('Unreadable required font' in item for item in report['blockers'])
    assert any('historical.png' in item and 'Unreadable static asset' in item for item in report['blockers'])


def test_path_case_mismatch_blocks_publication(release_source):
    root,database,uploads=release_source
    (root/'tb/site/BOTEN.png').rename(root/'tb/site/boten.png')
    report,_=inspect(root,database,uploads)
    assert any('Path casing mismatch: tb/site/BOTEN.png' == item for item in report['blockers'])


def test_missing_or_case_mismatched_css_resource_blocks_publication(release_source):
    root,database,uploads=release_source
    (root/'css').mkdir()
    (root/'css/site.css').write_text("@font-face { src: url('../assets/fonts/harmonyos-sans/harmonyos_sans.ttf'); }\n.icon { background: url('../tb/missing.png'); }")
    subprocess.run(['git','-C',str(root),'add','css/site.css'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.com','commit','-m','css fixture'],check=True,capture_output=True)
    report,_=inspect(root,database,uploads)
    assert any('Path casing mismatch: assets/fonts/harmonyos-sans/harmonyos_sans.ttf' == item for item in report['blockers'])
    assert any('Missing CSS resource: css/site.css -> ../tb/missing.png' == item for item in report['blockers'])


def test_source_change_during_archive_is_rejected(release_source, tmp_path, monkeypatch):
    root,database,uploads=release_source
    original_digest = release_bundle.digest
    calls = {'index': 0}
    def mutate_before_final_recheck(path):
        path = Path(path)
        if path == root / 'index.html':
            calls['index'] += 1
            if calls['index'] == 2:
                path.write_text('changed during archive')
        return original_digest(path)
    monkeypatch.setattr(release_bundle, 'digest', mutate_before_final_recheck)
    with pytest.raises(ValueError, match='Source changed while archiving'):
        build(root, database, uploads, tmp_path / 'release')


def test_receiver_rejects_tampering_before_restore_and_restores_verified_snapshot(release_source, tmp_path):
    root, database, uploads = release_source
    output = tmp_path / 'release'
    report = build(root, database, uploads, output)
    archive = output / 'release.tar.gz'
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    assert verify_archive(archive, manifest)

    tampered = tmp_path / 'tampered.tar.gz'
    with tarfile.open(archive, 'r:gz') as source, tarfile.open(tampered, 'w:gz') as target:
        for member in source.getmembers():
            content = source.extractfile(member).read()
            if member.name == 'data/boten.db':
                content = b'X' * len(content)
            target.addfile(member, BytesIO(content))
    destination = tmp_path / 'restore-before-verify'; destination.mkdir()
    sentinel = destination / 'keep.txt'; sentinel.write_text('original')
    with pytest.raises(ValueError, match='checksum'):
        verify_archive(tampered, manifest)
    assert sentinel.read_text() == 'original'

    restored = tmp_path / 'restored'
    with tarfile.open(archive, 'r:gz') as source:
        for member in source.getmembers():
            target = restored / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.extractfile(member).read())
    version, counts, references = database_info(restored / 'data/boten.db')
    assert version == report['migration']
    assert counts == report['table_counts']
    assert references == {'tb/site/BOTEN.png'}
    assert digest(restored / 'code/tb/site/BOTEN.png') == report['files']['code/tb/site/BOTEN.png']


def test_missing_upload_blocks_snapshot_release(release_source):
    root,database,uploads=release_source
    with sqlite3.connect(database) as db:
        db.execute('INSERT INTO records VALUES (?)',(json.dumps({'image':'/api/v1/media/missing.png'}),))
    report,_=inspect(root,database,uploads)
    assert any('Missing upload' in item for item in report['blockers'])


@pytest.mark.parametrize('relative',['../secret','/absolute','C:/private','tb/../../private','tb\\private'])
def test_release_paths_cannot_escape(tmp_path,relative):
    with pytest.raises(ValueError): safe_path(tmp_path,relative)
