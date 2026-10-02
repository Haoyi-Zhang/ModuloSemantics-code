#!/usr/bin/env python3
"""Run bounded, serial, self-contained scientific reproduction chunks."""
from __future__ import annotations
import argparse,json,os,resource,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FAMILIES=('guarded-division','fault-prefix','memory-token','recurrence-one',
          'recurrence-three','complementary','two-predicates','identity-boundary')
STEPS=['tests','pilot',*FAMILIES,'mutations','resources','generated',
       'certificate-oracle','dominance','reconcile']

def command(step):
    py=sys.executable
    if step=='tests':return [py,'-m','unittest','discover','-s','tests','-v']
    if step=='certificate-oracle':return [py,'-m','semantic_certificates.certificate_oracle']
    if step=='dominance':return [py,'-m','semantic_certificates.dominance']
    if step=='reconcile':return [py,'verify_results.py']
    suffix=['family','--name',step] if step in FAMILIES else [step]
    outfile='family-'+step if step in FAMILIES else step
    return [py,'-m','semantic_certificates.experiments',*suffix,
            '--output','results/'+outfile+'.json']

def save(obj):
    path=ROOT/'results/reproduction.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');tmp.replace(path)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--step',choices=STEPS)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--max-steps',type=int)
    args=ap.parse_args()
    if args.step and args.resume:ap.error('--step and --resume are mutually exclusive')
    if args.max_steps is not None and args.max_steps<1:ap.error('--max-steps must be positive')
    selected=[args.step] if args.step else STEPS
    report={'requested_steps':selected,'completed_steps':[], 'all_steps_passed':False,
            'child_cpu_seconds':0.,'wall_seconds':0.,'maximum_concurrent_children':1}
    if args.resume:
        path=ROOT/'results/reproduction.json'
        if not path.exists():ap.error('No prior reproduction progress to resume')
        report=json.loads(path.read_text())
        if report['requested_steps']!=STEPS:ap.error('Only an all-step run can be resumed')
        completed=report['completed_steps']
        if any(r['returncode'] for r in completed):ap.error('Failed step: start a fresh run after repair')
        if [r['step'] for r in completed]!=STEPS[:len(completed)]:ap.error('Non-prefix progress cannot be resumed')
        selected=STEPS[len(completed):]
    if args.max_steps is not None:selected=selected[:args.max_steps]
    prior_wall=report['wall_seconds']
    start=time.perf_counter()
    (ROOT/'results').mkdir(exist_ok=True)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',OMP_NUM_THREADS='1',
             OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for step in selected:
        before=resource.getrusage(resource.RUSAGE_CHILDREN)
        t=time.perf_counter(); timed_out=False
        try:
            cmd=command(step)
            proc=subprocess.run([cmd[0],'run_bounded.py',*cmd[1:]],cwd=ROOT,env=env,text=True,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=80)
            code,output=proc.returncode,proc.stdout
        except subprocess.TimeoutExpired as ex:
            code=-1;timed_out=True
            output=ex.stdout or b''
            if isinstance(output,bytes):output=output.decode(errors='replace')
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu=(after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime)
        entry={'step':step,'returncode':code,'wall_seconds':time.perf_counter()-t,
               'child_cpu_seconds':cpu,'timed_out':timed_out}
        if step=='tests':(ROOT/'results/unit-tests.txt').write_text(output)
        report['completed_steps'].append(entry)
        report['child_cpu_seconds']+=cpu;report['wall_seconds']=prior_wall+time.perf_counter()-start
        report['child_peak_rss_kib_so_far']=max(report.get('child_peak_rss_kib_so_far',0),after.ru_maxrss)
        save(report)
        print(json.dumps(entry),flush=True)
        if code:
            print(output[-8000:],file=sys.stderr)
            return 1
    report['all_steps_passed']=([r['step'] for r in report['completed_steps']]==STEPS)
    report['selected_batch_passed']=True
    report['wall_seconds']=prior_wall+time.perf_counter()-start
    save(report)
    return 0

if __name__=='__main__':sys.exit(main())
