import os
from pathlib import Path
import subprocess
import sys

def test_progress_precedence_and_pagination(tmp_path):
    script = '''
from backend.database_upgrade import upgrade_database
from backend.database import get_connection
from backend.inquiry_repository import list_staff_inquiries
upgrade_database()
with get_connection() as db:
    db.execute("INSERT INTO users(id,email,role) VALUES('qa','qa@example.test','admin')")
    db.execute("INSERT INTO users(id,email,role) VALUES('qa2','qa2@example.test','sales')")
    for name,state in [('new','new'),('draft','quoted'),('sent','quoted'),('archived','quoted'),('closed','closed'),('cancelled','cancelled')]:
        db.execute("INSERT INTO customer_inquiries(id,inquiry_number,created_by,source_type,status,item_count,idempotency_key) VALUES(?,?,'qa','cart',?,1,?)",(name,name,state,name))
    for name,states in [('draft',['draft']),('sent',['draft','sent']),('archived',['archived']),('closed',['sent']),('cancelled',['draft'])]:
        for i,state in enumerate(states):
            db.execute("INSERT INTO commerce_quotes(id,user_id,items_json,source_type,source_document_id,lifecycle_status) VALUES(?,?,'[]','inquiry',?,?)",(name+str(i),'qa2' if i else 'qa',name,state))
expected={'new':'new','draft':'pending','sent':'sent','archived':'archived','closed':'closed','cancelled':'cancelled'}
for ident,status in expected.items():
    result=list_staff_inquiries('qa','admin',1,1,status='business_'+status)
    assert result['total']==1 and result['items'][0]['id']==ident and result['items'][0]['business_status']==status, result
    assert list_staff_inquiries('qa','admin',2,1,status='business_'+status)['items']==[]
'''
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", script], cwd=Path(__file__).resolve().parents[1], env=dict(os.environ, BOTEN_DATABASE_PATH=str(tmp_path / "progress.db")), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
