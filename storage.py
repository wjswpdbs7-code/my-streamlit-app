"""Workspace persistence. SQLite locally, PostgreSQL via DATABASE_URL in Cloud."""
import sqlite3, json, uuid, base64, hashlib
from pathlib import Path
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, url='', root='.able_data', workspace='default'):
        self.remote=bool(url); self.workspace=workspace
        if url:
            import psycopg
            self.db=psycopg.connect(url, autocommit=True, connect_timeout=10)
        else:
            Path(root).mkdir(parents=True,exist_ok=True)
            self.db=sqlite3.connect(str(Path(root)/'able.sqlite3'),timeout=15)
            self.db.execute('PRAGMA journal_mode=WAL')
        self.run('CREATE TABLE IF NOT EXISTS able_items (workspace TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(workspace,kind,id))')
        self.run('CREATE TABLE IF NOT EXISTS able_blobs (workspace TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(workspace,id))')
    def run(self,sql,args=()):
        c=self.db.execute(sql.replace('?', '%s') if self.remote else sql,args)
        if not self.remote:self.db.commit()
        return c
    def put(self,kind,item):
        item=dict(item);item.setdefault('id',uuid.uuid4().hex)
        self.run('INSERT INTO able_items(workspace,kind,id,payload,updated) VALUES(?,?,?,?,?) ON CONFLICT(workspace,kind,id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(self.workspace,kind,item['id'],json.dumps(item,ensure_ascii=False),now()))
        return item
    def get(self,kind,id):
        row=self.run('SELECT payload FROM able_items WHERE workspace=? AND kind=? AND id=?',(self.workspace,kind,id)).fetchone()
        return json.loads(row[0]) if row else None
    def list(self,kind):
        return [json.loads(x[0]) for x in self.run('SELECT payload FROM able_items WHERE workspace=? AND kind=? ORDER BY updated',(self.workspace,kind)).fetchall()]
    def delete(self,kind,id):self.run('DELETE FROM able_items WHERE workspace=? AND kind=? AND id=?',(self.workspace,kind,id))
    def asset(self,name,data,origin='upload',conversation=''):
        id=hashlib.sha256(data).hexdigest()
        self.run('INSERT INTO able_blobs(workspace,id,data) VALUES(?,?,?) ON CONFLICT(workspace,id) DO NOTHING',(self.workspace,id,base64.b64encode(data).decode()))
        old=self.get('assets',id)
        return old or self.put('assets',{'id':id,'name':Path(name).name,'size':len(data),'origin':origin,'conversation':conversation,'created':now(),'text':'','indexed':False})
    def bytes(self,id):
        row=self.run('SELECT data FROM able_blobs WHERE workspace=? AND id=?',(self.workspace,id)).fetchone()
        if not row:raise FileNotFoundError('저장된 파일을 찾을 수 없습니다.')
        return base64.b64decode(row[0])
    def claim(self,id,kind):
        c=self.run('INSERT INTO able_items(workspace,kind,id,payload,updated) VALUES(?,?,?,?,?) ON CONFLICT(workspace,kind,id) DO NOTHING',(self.workspace,'operations',id,json.dumps({'id':id,'kind':kind,'state':'처리 중 또는 결과 확인 필요'},ensure_ascii=False),now()))
        return c.rowcount==1
    def finish(self,id,kind,state):self.put('operations',{'id':id,'kind':kind,'state':state})
    def close(self):self.db.close()
