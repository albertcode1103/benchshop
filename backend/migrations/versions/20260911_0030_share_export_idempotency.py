"""Persist share creation attempts without rewriting share snapshots."""
from alembic import op

revision = "20260911_0030"
down_revision = "20260911_0029"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE TABLE IF NOT EXISTS share_creation_attempts (user_id TEXT NOT NULL REFERENCES users(id), request_key TEXT NOT NULL, payload TEXT NOT NULL, share_id TEXT NOT NULL REFERENCES commerce_shares(id), PRIMARY KEY(user_id,request_key))")

def downgrade():
    op.drop_table("share_creation_attempts")
