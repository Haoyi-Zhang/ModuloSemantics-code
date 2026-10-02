"""Apply resource limits in a fresh process, then execute the requested Python step.

Avoid Python work in subprocess preexec_fn; no external program is invoked.
"""
import os,resource,sys
if hasattr(os,'sched_getaffinity'):
    allowed=os.sched_getaffinity(0)
    if allowed:os.sched_setaffinity(0,{min(allowed)})
resource.setrlimit(resource.RLIMIT_AS,(int(3.5*1024**3),)*2)
resource.setrlimit(resource.RLIMIT_CPU,(40,44))
os.execv(sys.executable,[sys.executable,*sys.argv[1:]])
