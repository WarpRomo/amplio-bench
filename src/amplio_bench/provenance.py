from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def tree_hash(root):
    root=Path(root); h=hashlib.sha256(); entries={}
    for p in sorted(x for x in root.rglob('*') if x.is_file()):
        rel=p.relative_to(root).as_posix(); fh=sha256_file(p); entries[rel]=fh; h.update(rel.encode()+b'\0'+fh.encode()+b'\n')
    return h.hexdigest(),entries

def git_sha(path): return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
def build_manifest(task_dir,adapter,repos):
    th,files=tree_hash(task_dir)
    return {'created_utc':datetime.now(timezone.utc).isoformat(),'task_dir':str(task_dir),'task_tree_sha256':th,'task_file_count':len(files),'task_file_hashes':files,'adapter':str(adapter),'adapter_sha256':sha256_file(adapter),'repos':{n:git_sha(p) for n,p in repos.items()}}
def write_manifest(m,out): Path(out).write_text(json.dumps(m,indent=2)+'\n')
