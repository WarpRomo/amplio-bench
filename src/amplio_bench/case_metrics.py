from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import csv, json, re
PASS_STATUSES={"success","pass"}
ROUND_RE=re.compile(r"(?:^|/)steps/round-(\d+)/verifier/test-stdout\.txt$")
FIELD_RE=re.compile(r"\b([A-Za-z0-9_-]+)=([^\s]+)")
@dataclass(frozen=True)
class Case:
    case_id:str; status:str; origin:str|None=None; requirement:str|None=None; case_type:str|None=None
    @property
    def passed(self): return self.status in PASS_STATUSES
@dataclass
class RoundMetrics:
    round:int; reward:float; cases_total:int; cases_success:int; cases_fail:int; success_rate:float
    stable_success:int|None=None; regressions:int|None=None; recoveries:int|None=None; stable_fail:int|None=None
    new_cases:int|None=None; new_success:int|None=None; new_fail:int|None=None; new_success_rate:float|None=None

def parse_case_line(line):
    if not line.startswith('CASE_RESULT '): return None
    f=dict(FIELD_RE.findall(line))
    if not f.get('case_id') or not f.get('status'): return None
    return Case(f['case_id'],f['status'],f.get('origin_step'),f.get('requirement_ref'),f.get('case_type'))

def parse_verifier_stdout(path):
    out={}
    for line in path.read_text(errors='replace').splitlines():
        c=parse_case_line(line)
        if c: out[c.case_id]=c
    return out

def discover_round_files(run_dir):
    found=defaultdict(list)
    for p in Path(run_dir).rglob('test-stdout.txt'):
        m=ROUND_RE.search(p.as_posix())
        if m: found[int(m.group(1))].append(p)
    bad={r:ps for r,ps in found.items() if len(ps)!=1}
    if bad: raise ValueError('expected exactly one verifier stdout per round: '+', '.join(f'r{r}={len(ps)}' for r,ps in sorted(bad.items())))
    return {r:ps[0] for r,ps in found.items()}

def analyze_run(run_dir):
    files=discover_round_files(Path(run_dir))
    if not files: raise ValueError('no EvoCode verifier rounds found')
    nums=sorted(files)
    if nums != list(range(nums[0],nums[-1]+1)): raise ValueError(f'non-contiguous rounds: {nums}')
    prev=None; by_round={}; rows=[]
    for n in nums:
        stdout=files[n]; cases=parse_verifier_stdout(stdout); reward=float((stdout.parent/'reward.txt').read_text().strip())
        success=sum(c.passed for c in cases.values()); total=len(cases); row=RoundMetrics(n,reward,total,success,total-success,success/total if total else 0.0)
        if prev is not None:
            common=set(prev)&set(cases); new=set(cases)-set(prev)
            row.stable_success=sum(prev[c].passed and cases[c].passed for c in common)
            row.regressions=sum(prev[c].passed and not cases[c].passed for c in common)
            row.recoveries=sum(not prev[c].passed and cases[c].passed for c in common)
            row.stable_fail=sum(not prev[c].passed and not cases[c].passed for c in common)
            row.new_cases=len(new); row.new_success=sum(cases[c].passed for c in new); row.new_fail=len(new)-row.new_success
            row.new_success_rate=row.new_success/len(new) if new else None
        rows.append(row); by_round[n]=cases; prev=cases
    req=defaultdict(Counter)
    for c in by_round[nums[-1]].values(): req[c.requirement or '?']['success' if c.passed else 'fail']+=1
    final=[]
    for name,count in sorted(req.items()):
        total=count['success']+count['fail']; final.append({'requirement':name,'success':count['success'],'fail':count['fail'],'total':total,'success_rate':count['success']/total if total else 0.0})
    return {'rounds':[asdict(x) for x in rows],'final_round_requirements':final}

def write_analysis(result,out_dir):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['round','reward','cases_success','cases_total','cases_fail','success_rate','stable_success','regressions','recoveries','stable_fail','new_cases','new_success','new_fail','new_success_rate']
    with (out/'round_metrics.csv').open('w',newline='') as f:
        x=csv.DictWriter(f,fieldnames=fields); x.writeheader(); [x.writerow({k:r.get(k) for k in fields}) for r in result['rounds']]
    fields2=['requirement','success','fail','total','success_rate']
    with (out/'final_requirements.csv').open('w',newline='') as f:
        x=csv.DictWriter(f,fieldnames=fields2); x.writeheader(); x.writerows(result['final_round_requirements'])
    lines=['# Run summary','','| Round | Passing | Rate | New solved | Regressions | Recoveries |','|---:|---:|---:|---:|---:|---:|']
    for i,r in enumerate(result['rounds']):
        if i==0: new=reg=rec='—'
        else: new=f"{r['new_success']}/{r['new_cases']}"; reg=str(r['regressions']); rec=str(r['recoveries'])
        lines.append(f"| {r['round']} | {r['cases_success']}/{r['cases_total']} | {100*r['success_rate']:.1f}% | {new} | {reg} | {rec} |")
    (out/'summary.md').write_text('\n'.join(lines)+'\n')
