"""Check a JSON certificate; optionally compare its two executions on an input."""
import argparse,json,sys
from pathlib import Path
from dataclasses import asdict
from .checker import check
from .reference import run_source
from .target import run_target


def unique_pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate JSON key: '+k)
        result[k]=v
    return result


def read_json(name):
    with Path(name).open('rb') as f:
        data=f.read(4*1024*1024+1)
    if len(data)>4*1024*1024:raise ValueError('Input exceeds the 4 MiB CLI limit')
    return json.loads(data,object_pairs_hook=unique_pairs)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('certificate');ap.add_argument('--input')
    args=ap.parse_args()
    try:
        p=read_json(args.certificate);v=check(p);out=asdict(v)
        if args.input and v.accepted:
            data=read_json(args.input)
            source,target=run_source(p,data),run_target(p,data)
            out['source']=source;out['target']=target
            out['equal']=json.dumps(source,sort_keys=True)==json.dumps(target,sort_keys=True)
        print(json.dumps(out,indent=2,sort_keys=True))
        return 0 if v.accepted and out.get('equal',True) else 2
    except (OSError,ValueError,KeyError,TypeError,IndexError,RecursionError) as ex:
        print(json.dumps({'accepted':False,'error':str(ex)}));return 2

if __name__=='__main__':sys.exit(main())
