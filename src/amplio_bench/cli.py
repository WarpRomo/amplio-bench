import argparse,json
from pathlib import Path
from .case_metrics import analyze_run,write_analysis
from .audit import audit_run,write_audit
from .provenance import build_manifest,write_manifest
from .secrets import scan_tree
from .runner import run_evocode
def repoarg(v):
    if '=' not in v:raise argparse.ArgumentTypeError('NAME=PATH required')
    n,p=v.split('=',1);return n,Path(p)
def main():
    p=argparse.ArgumentParser(prog='amplio-bench');s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('analyze-evocode');q.add_argument('--run-dir',type=Path,required=True);q.add_argument('--out-dir',type=Path,required=True)
    q=s.add_parser('audit-run');q.add_argument('--run-dir',type=Path,required=True);q.add_argument('--expected-rounds',type=int);q.add_argument('--harbor-root',type=Path);q.add_argument('--out',type=Path,required=True)
    q=s.add_parser('manifest');q.add_argument('--task-dir',type=Path,required=True);q.add_argument('--adapter',type=Path,required=True);q.add_argument('--repo',action='append',default=[],type=repoarg);q.add_argument('--out',type=Path,required=True)
    q=s.add_parser('secret-scan');q.add_argument('path',type=Path)
    q=s.add_parser('run-evocode');q.add_argument('--config',type=Path,required=True);q.add_argument('--task',type=Path,required=True);q.add_argument('--out',type=Path,required=True);q.add_argument('--model',required=True);q.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if a.cmd=='analyze-evocode':r=analyze_run(a.run_dir);write_analysis(r,a.out_dir);print(json.dumps(r,indent=2))
    elif a.cmd=='audit-run':r=audit_run(a.run_dir,a.expected_rounds,a.harbor_root);write_audit(r,a.out);print(json.dumps(r,indent=2));raise SystemExit(0 if r['validation_status']=='PASS' else 1)
    elif a.cmd=='manifest':r=build_manifest(a.task_dir,a.adapter,dict(a.repo));write_manifest(r,a.out);print(json.dumps(r,indent=2))
    elif a.cmd=='secret-scan':h=scan_tree(a.path);print('SECRET_SCAN=PASS' if not h else json.dumps(h,indent=2));raise SystemExit(0 if not h else 1)
    elif a.cmd=='run-evocode':raise SystemExit(run_evocode(a.config,a.task,a.out,a.model,a.dry_run))
if __name__=='__main__':main()
