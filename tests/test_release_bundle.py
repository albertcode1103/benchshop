import json
import sqlite3
import subprocess
import tarfile
import pytest
from deploy.release_bundle import build, inspect, safe_path


@pytest.fixture
def release_source(tmp_path):
    root = tmp_path / 'repo'; root.mkdir()
    (root / 'tb/site').mkdir(parents=True)
    (root / 'tb/site/BOTEN.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    (root / 'index.html').write_text('<html>fixture</html>')
    subprocess.run(['git','init',str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'add','index.html','tb/site/BOTEN.png'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.com','commit','-m','fixture'],check=True,capture_output=True)
    database = tmp_path / 'source.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE alembic_version(version_num TEXT)')
        db.execute("INSERT INTO alembic_version VALUES ('test')")
        db.execute('CREATE TABLE records(snapshot TEXT)')
        db.execute('INSERT INTO records VALUES (?)',(json.dumps({'image':'/tb/site/BOTEN.png'}),))
    uploads = tmp_path / 'uploads'; uploads.mkdir()
    (uploads / 'historical.png').write_bytes(b'historical image')
    return root,database,uploads


def test_private_bundle_contains_verified_snapshot_and_uploads(release_source,tmp_path):
    root,database,uploads=release_source
    output=tmp_path/'release'
    report=build(root,database,uploads,output)
    assert not report['blockers']
    with tarfile.open(output/'release.tar.gz') as tar:
        assert set(tar.getnames()) == {'code/index.html','code/tb/site/BOTEN.png','data/boten.db','data/uploads/catalog/historical.png'}
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


def test_missing_upload_blocks_snapshot_release(release_source):
    root,database,uploads=release_source
    with sqlite3.connect(database) as db:
        db.execute('INSERT INTO records VALUES (?)',(json.dumps({'image':'/api/v1/media/missing.png'}),))
    report,_=inspect(root,database,uploads)
    assert any('Missing upload' in item for item in report['blockers'])


@pytest.mark.parametrize('relative',['../secret','/absolute','C:/private','tb/../../private','tb\\private'])
def test_release_paths_cannot_escape(tmp_path,relative):
    with pytest.raises(ValueError): safe_path(tmp_path,relative)
