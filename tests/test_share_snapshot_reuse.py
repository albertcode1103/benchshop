import os
from pathlib import Path
import subprocess
import sys


def test_snapshot_reuse_and_quota(tmp_path):
    script = '''
from concurrent.futures import ThreadPoolExecutor
from backend.database_upgrade import upgrade_database
from backend.database import get_connection
from backend import commerce_repository as repo
from backend.account_errors import AccountError
upgrade_database()
with get_connection() as db:
    for user in ('qa','other'):
        db.execute("INSERT INTO users(id,email,role) VALUES(?,?, 'customer')", (user,user+'@example.test'))
quantity = 1
def load(kind, ident, user):
    return dict(item_type=kind,source_id=ident,quantity=quantity,display_name='Fixture',product_model='',payload={lang:{'source_id':ident,'code':'TOOL','name':'Fixture'} for lang in ('zh','en')})
repo._load_share_item = load
repo._canonical_cart_order = lambda item: 0
refs = [{'item_type':'tool','id':'old-row'}]
original = repo.create_commerce_share(refs,'qa',note='Original')
refs = [{'item_type':'tool','id':'new-row'}]
def create(n): return repo.create_commerce_share(refs,'qa','en','Changed',f'unique-request-{n}',True)
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(create,range(4)))
assert all(r['code']==original['code'] and r['note']=='Original' and r['reused'] for r in results)
with get_connection() as db:
    assert db.execute('SELECT COUNT(*) FROM commerce_shares').fetchone()[0]==1
assert repo.create_commerce_share(refs,'other',reuse_existing=True)['code'] != original['code']
for n in range(2,11):
    quantity=n
    repo.create_commerce_share(refs,'qa',reuse_existing=True)
quantity=1
assert create(99)['code']==original['code'] # quota full still allows reuse
quantity=11
try:
    create(100)
    raise AssertionError('Quota bypass')
except AccountError as error:
    assert error.code=='SHARE_QUOTA_EXCEEDED'
quantity=1
with get_connection() as db:
    db.execute('UPDATE commerce_shares SET active=0 WHERE id=?',(original['id'],))
replacement=create(101)
assert replacement['code']!=original['code']
with get_connection() as db:
    db.execute("UPDATE commerce_shares SET expires_at='2000-01-01' WHERE id=?",(replacement['id'],))
assert create(102)['code'] != replacement['code']
quantity=1
refs=[{'item_type':'device_config','id':'new-device-row'}]
import json
from backend.admin_catalog_repository import create_product
create_product({'id':'fixture-model','name':'Fixture'})
with get_connection() as db:
    db.execute("INSERT INTO saved_configs(id,user_id,name,product_id,snapshot_json) VALUES('fixture-config','qa','Fixture','fixture-model','{}')")
    db.execute("INSERT INTO config_shares(id,config_id,code,created_by,expires_at,item_count,note) VALUES('legacy','fixture-config','999999','qa','2099-01-01',1,'Legacy note')")
    db.execute("INSERT INTO config_share_items(id,share_id,sort_order,display_name,snapshot_json) VALUES('legacy-item','legacy',0,'Fixture',?)", (json.dumps(load('device_config','old-device-row','qa')['payload']),))
legacy=create(103)
assert legacy['code']=='999999' and legacy['note']=='Legacy note' and legacy['document_version']==1
quantity=50
refs=[{'item_type':'tool','id':'fresh-tool'}]
def fresh(n): return repo.create_commerce_share(refs,'other',idempotency_key=f'fresh-request-{n}',reuse_existing=True)
with ThreadPoolExecutor(max_workers=4) as pool:
    assert len({r['code'] for r in pool.map(fresh,range(4))}) == 1
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', script], cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, BOTEN_DATABASE_PATH=str(tmp_path / 'reuse.db')), capture_output=True, text=True, encoding='utf8', timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
