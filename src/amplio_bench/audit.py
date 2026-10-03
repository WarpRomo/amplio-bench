from pathlib import Path
import json,re
ERROR_PATTERNS={'provider_429':re.compile(r'429 Too Many|rate limit',re.I),'retry_exhausted':re.compile(r'openai request failed after',re.I),'runtime_error':re.compile(r'\bRuntimeError\b'),'crashed':re.compile(r'\bcrashed\b',re.I),'error_log':re.compile(r'level=ERROR')}
def verifier_rounds(run):
    out=set(); pat=re.compile(r'(?:^|/)steps/round-(\d+)/verifier/reward\.txt$')
    for p in Path(run).rglob('reward.txt'):
        m=pat.search(p.as_posix())
        if m: out.add(int(m.group(1)))
    return sorted(out)
def check_harbor_verifier_isolation(root):
    p=Path(root)/'src/harbor/trial/multi_step.py'
    if not p.exists(): return {'status':'FAIL','reason':f'missing {p}'}
    s=p.read_text(errors='replace'); start=s.find('def _prepare_step')
    if start<0: start=s.find('async def _prepare_step')
    if start<0: return {'status':'FAIL','reason':'_prepare_step not found'}
    nexts=[x for x in (s.find('\n    async def ',start+1),s.find('\n    def ',start+1)) if x>=0]; end=min(nexts) if nexts else min(len(s),start+8000)
    ok='_reset_shared_step_verifier_dirs' in s[start:end]
    return {'status':'PASS' if ok else 'FAIL','prepare_step_calls_helper':ok,'source':str(p)}
def audit_run(run_dir,expected_rounds=None,harbor_root=None):
    run=Path(run_dir); found=verifier_rounds(run); exp=list(range(1,expected_rounds+1)) if expected_rounds else None
    checks={'rounds':{'found':found,'expected':exp,'pass':bool(found) if exp is None else found==exp}}
    rc=run/'harbor_rc.txt'; checks['harbor_exit_code']={'value':None,'pass':None}
    if rc.exists(): value=int(rc.read_text().strip()); checks['harbor_exit_code']={'value':value,'pass':value==0}
    hits={}; log=run/'run.log'
    if log.exists():
        text=log.read_text(errors='replace')
        for name,pat in ERROR_PATTERNS.items():
            x=pat.findall(text)
            if x: hits[name]=[str(v) for v in x[:10]]
    checks['known_runtime_errors']={'hits':hits,'pass':not hits}
    pf=run/'audit/daytona-postflight.txt'; checks['sandbox_cleanup']={'pass':None}
    if pf.exists(): checks['sandbox_cleanup']={'pass':'COUNT_AFTER_CLEANUP = 0' in pf.read_text(errors='replace')}
    if harbor_root: checks['verifier_isolation']=check_harbor_verifier_isolation(harbor_root)
    gates=[]
    for v in checks.values():
        if isinstance(v,dict) and v.get('pass') is not None: gates.append(bool(v['pass']))
        elif isinstance(v,dict) and v.get('status') in {'PASS','FAIL'}: gates.append(v['status']=='PASS')
    return {'run_dir':str(run),'checks':checks,'validation_status':'PASS' if gates and all(gates) else 'FAIL'}
def write_audit(r,out): Path(out).write_text(json.dumps(r,indent=2)+'\n')
