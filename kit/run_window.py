#!/usr/bin/env python3
"""Driver of a pump-window run of the skeleton (the kit of handout 0OEyt; numerics as run_full.py of Secs. 29-32 of report 0JOalb).
The work directory is made by window_setup.py: hp3.wls, this file, pumps.txt (lines "j P"), plan.txt (lines "prefix nt withWeights j"
in the order to run, an optional 5th field giving that job's precision), params.txt (GA, GS, PREC, MEMMIN), nproc (number of kernels, re-read every minute).  One hp3.wls front-end per
job, nproc at a time, a job is launched only if MemAvailable > MEMMIN GB.  Only jobs started in THIS directory are counted or killed,
so several runs (and other people's) can share a machine.
An optional file shinshu (a ceiling of kernels, or max: every thread of the machine; read every minute like nproc) lets the run take
the threads that stay idle: one kernel more after 10 minutes in which at least that many threads were free of any other work, back
toward nproc (never below) as soon as other work has taken them for 2 minutes.  A kernel above nproc runs the shortest job waiting,
so that the retreat is quick (a lower count stops new launches; no job is killed).  The current count is in shinshu.now.
  python3 run_window.py              run the plan to the end (rerun to resume: files present are skipped, jobs in flight adopted)
  python3 run_window.py --progress   one line: ASCII bar of the kernel time done, files per order, kernels, memory, end estimate
  python3 run_window.py --kill       stop now: the driver, its front-ends and their kernels (a file STOP only stops new launches)
  python3 run_window.py --uchikiri   end as soon as possible without loss: no new pump, only the jobs that complete the pumps started
                                     (one with a job done or in flight), and say when the run will end; --dry only says it
  python3 run_window.py --chushi     stop now, but a job within 10 minutes of completion (--soon MIN) is first offered to wait for:
                                     abort it too [n]ow, or [a]fter it completes; --now or --wait answers ahead, --dry only says it
  python3 run_window.py ... --dir D  the run of directory D rather than this file's own (for --progress and the --dry runs)
A file atend holds a command run at the end of the run (Ten-Go's uchikiri: push the last results)."""
import heapq, os, re, shlex, signal, subprocess, sys, time
WORK = os.path.realpath(sys.argv[sys.argv.index("--dir") + 1]) if "--dir" in sys.argv else os.path.dirname(os.path.realpath(__file__)); os.chdir(WORK)
if "--dir" in sys.argv and not {"--progress", "--dry"} & set(sys.argv): sys.exit("--dir only reads: with --progress or --dry")   # never stop another run by mistake
P = dict(l.split("=", 1) for l in open("params.txt").read().split() if "=" in l)
GA, GS, PREC, MEMMIN = P["GA"], P["GS"], P["PREC"], float(P["MEMMIN"])
T = {"150w": 1118, "150w80": 1409, "200e": 760, "250e": 1580, "300e": 2685, "400e": 11076}   # seconds per job, azag at home on ~30 kernels
# (Ten-Go's reference): for the bar, and, scaled to this run's own speed, to choose the job of a kernel above nproc
def tcost(o): return T.get(o, 600 * (int(re.match(r"\d+", o)[0]) / 150) ** 3)
pumps = dict(l.split() for l in open("pumps.txt") if l.strip())
plan = [l.split() for l in open("plan.txt") if l.strip() and not l.startswith("#")]


def ours():   # wolframscript front-ends running hp3.wls in this directory: pid -> (prefix, j)
    out = {}
    for line in subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True).stdout.splitlines():
        tok = line.split()
        if "hp3.wls" in tok and "wolframscript" in " ".join(tok[1:3]):
            try:
                if os.readlink(f"/proc/{tok[0]}/cwd") != WORK: continue
            except OSError: continue
            k = tok.index("hp3.wls"); out[int(tok[0])] = (tok[k + 5], tok[k + 7].split(":")[0])
    return out


def tree(pid):   # pid and all its descendants
    kids = subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True).stdout.split()
    return [pid] + [q for k in kids for q in tree(int(k))]


def order(pre): return pre.split("_nt")[-1]
def hm(x): m = round(x / 60); return f"{m} min" if m < 60 else f"{m // 60} h" + (f" {m % 60:02d}" if m % 60 else "")   # 3 min, 2 h 20, 6 h


def few(xs):   # 17 min, 2 h 20, 6 h; or, past four, the first three ... the last (n jobs)
    t = [hm(x[4]) for x in xs]; return ", ".join(t) if len(t) <= 4 else f"{', '.join(t[:3])} ... {t[-1]} ({len(t)} jobs)"


def driving():   # is the driver of this directory running
    try: os.kill(int(open("driver.pid").read()), 0); return True
    except (OSError, ValueError): return False


def inflight():
    """the jobs running here, [(pid, prefix, j, seconds since they started, seconds still expected)], the expected from this run's own
    job times per order (its log), else T; and that cost per order"""
    took = {}
    for l in (open("run.log") if os.path.exists("run.log") else []):
        m = re.search(r" done (\S+) j=\S+ P=\S+ in (\d+) s", l)
        if m and "NO FILE" not in l: took.setdefault(order(m[1]), []).append(int(m[2]))
    per = lambda o: sum(took[o]) / len(took[o]) if took.get(o) else tcost(o)
    hz = os.sysconf("SC_CLK_TCK"); boot = next(int(l.split()[1]) for l in open("/proc/stat") if l.startswith("btime")); now = time.time(); out = []
    for pid, (pre, j) in ours().items():
        try: el = now - boot - int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[19]) / hz   # since the job started
        except OSError: continue
        out.append((pid, pre, j, el, max(per(order(pre)) - el, 60)))
    return out, per


def kill(pids):   # these front-ends and all their descendants (wolframscript ignores SIGTERM and leaves its kernel behind)
    for q in [q for pid in pids for q in tree(pid)]:
        try: os.kill(q, signal.SIGKILL)
        except OSError: pass


def killall():   # the driver, its front-ends and their kernels; the number of jobs killed
    open("STOP", "w").write("killed\n")
    if os.path.exists("driver.pid"):
        try: os.kill(int(open("driver.pid").read()), signal.SIGKILL)
        except OSError: pass
    fe = ours(); kill(fe)
    for k in range(10):   # a kernel can outlive its front-end for a moment: any WolframKernel still working in this directory
        time.sleep(1); left = [int(l.split()[0]) for l in subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True).stdout.splitlines()
                               if "WolframKernel" in l and os.path.realpath(f"/proc/{l.split()[0]}/cwd") == WORK]
        for q in left:
            try: os.kill(q, signal.SIGKILL)
            except OSError: pass
        if not left: break
    return len(fe)


if "--progress" in sys.argv:
    tot = done_t = 0; parts = []
    for o in dict.fromkeys(order(f[0]) for f in plan):
        pre = next(f[0] for f in plan if order(f[0]) == o); n_all = sum(order(f[0]) == o for f in plan)
        n = sum(os.path.exists(f"{f[0]}_{f[3]}.dat") for f in plan if order(f[0]) == o)
        t = T[o] if o in T else 600 * (int(o[:-1]) / 150) ** 3; tot += n_all * t; done_t += n * t; parts.append(f"{o} {n}/{n_all}")
    pct = 100 * done_t / tot; b = int(pct * 40 / 100); ep = open("launch-epoch").read().split() if os.path.exists("launch-epoch") else []
    el = time.time() - int(ep[0]) if ep else 0; seed = float(ep[1]) if len(ep) > 1 else 0   # kernel time already on disk at launch (copied files)
    new = (done_t - seed) / (tot - seed) if tot > seed else 1   # the end estimate uses only the work done since the launch
    eta = time.strftime("%a %H:%M", time.localtime(time.time() + el * (1 - new) / new)) if 0 < new < 1 else "-"
    mem = next(int(l.split()[1]) / 1e6 for l in open("/proc/meminfo") if l.startswith("MemAvailable"))
    print(f"{time.strftime('%H:%M')} [{'#' * b}{'.' * (40 - b)}] {pct:.0f} % of the kernel time; {', '.join(parts)}; "
          f"running {len(ours())}/{open('nproc').read().strip()}"
          + (f" (uchikiri since {time.strftime('%H:%M', time.localtime(os.path.getmtime('UCHIKIRI')))})" if os.path.exists("UCHIKIRI") else "")
          + (f" (shinshu: {open('shinshu.now').read().strip()} now, up to {open('shinshu').read().strip() or 'max'})" if os.path.exists("shinshu") and os.path.exists("shinshu.now") else "")
          + f"; {mem:.0f} GB free; end about {eta}")
    sys.exit()
if "--kill" in sys.argv: n = killall(); print(f"killed the driver and {n} jobs; remove the file STOP before running again"); sys.exit()
if "--uchikiri" in sys.argv:
    alive = driving(); dry = "--dry" in sys.argv or not alive
    if not dry and not os.path.exists("UCHIKIRI"):
        if os.path.exists("uchikiri.kept"): os.remove("uchikiri.kept")
        open("UCHIKIRI", "w").write(f"{int(time.time())}\n")
    for k in range(0 if dry else 90):   # the driver answers within one turn of its loop (1 s per launch in it)
        if os.path.exists("uchikiri.kept"): break
        time.sleep(1)
    else:
        if not dry: sys.exit("uchikiri: the driver did not answer (an older run_window.py?); the file UCHIKIRI stays for it")
    fly, per = inflight(); fl = {(pre, j) for _, pre, j, _, _ in fly}; have = lambda f: os.path.exists(f"{f[0]}_{f[3]}.dat")
    kept = set(open("uchikiri.kept").read().split()) if os.path.exists("uchikiri.kept") else {j for _, j in fl} | {f[3] for f in plan if have(f)}
    todo = [f for f in plan if f[3] in kept and not have(f) and (f[0], f[3]) not in fl]
    k = int(open("shinshu.now").read()) if os.path.exists("shinshu") and os.path.exists("shinshu.now") else int(open("nproc").read())
    free = [x[4] for x in fly] + [0.0] * max(0, k - len(fly)); heapq.heapify(free)
    for f in todo: heapq.heappush(free, heapq.heappop(free) + per(order(f[0])))   # launched in the plan's order as kernels free
    end = max(free, default=0)
    under = {f[3] for f in plan if f[3] in kept and not have(f)}; drop = {f[3] for f in plan if not have(f)} - kept
    cut = {f[3] for f in todo}   # the pumps a STOP would leave incomplete: their jobs done, and those in flight, for nothing
    stop = sum(per(order(f[0])) for f in plan if f[3] in cut and have(f)) + sum(per(order(pre)) for pre, j in fl if j in cut)
    lose = sum(x[3] for x in fly) + sum(per(order(f[0])) for f in plan if f[3] in under and have(f))   # in flight, and every pump under way
    print(f"uchikiri{' (dry run: nothing changed)' if dry else ''}{'' if alive else ', no driver running'}: {len(drop)} pumps not started "
          f"{'would be ' if dry else ''}given up; {len(fly)} jobs in flight and {len(todo)} to launch complete the {len(under)} pumps under way, "
          f"on {k} kernels; the run ends about {time.strftime('%a %H:%M', time.localtime(time.time() + end))} (in {hm(end)}) without loss. "
          f"Instead, a STOP now would waste {stop / 3600:.1f} kh ({len(cut)} pumps left incomplete), --kill {lose / 3600:.1f} kh")
    sys.exit()
if "--chushi" in sys.argv:
    soon = 60 * float(sys.argv[sys.argv.index("--soon") + 1]) if "--soon" in sys.argv else 600
    how = "wait" if "--wait" in sys.argv else "now" if "--now" in sys.argv else None
    fly, per = inflight(); fly.sort(key=lambda x: x[4]); near = [x for x in fly if x[4] <= soon]; far = [x for x in fly if x[4] > soon]
    one = len(near) == 1
    if near:
        print(f"{'One job is' if one else f'{len(near)} jobs are'} {few(near)} from completion"
              + (f" ({', '.join(f'{order(x[1])} at P={pumps[x[2]]}' for x in near)})" if len(near) <= 3 else "")
              + (f"; the next {'is' if len(far) == 1 else 'are'} {few(far)} away, so {'it is' if len(far) == 1 else 'those are'} aborted" if far else "") + ".")
    if "--dry" in sys.argv:
        print(f"chushi (dry run: nothing changed): {len(fly)} jobs in flight, {sum(x[3] for x in fly) / 3600:.1f} kh in them; none within {hm(soon)} of completion" if not near
              else f"chushi (dry run: nothing changed): [n]ow would lose {sum(x[3] for x in fly) / 3600:.1f} kh, [a]fter {sum(x[3] for x in far) / 3600:.1f} kh, ending in {hm(near[-1][4])}"); sys.exit()
    if near and not how:
        if not sys.stdin.isatty(): print(f"chushi: nothing done; say --wait (abort the others now, {'this one' if one else 'these'} after completion) or --now (abort all)"); sys.exit(3)
        a = input(f"Abort {'this one' if one else 'these'} too [n]ow, or [a]fter {'it completes' if one else 'they complete'}? (anything else: nothing done) ").strip().lower()[:1]
        how = {"n": "now", "a": "wait"}.get(a)
        if not how: print("chushi: nothing done"); sys.exit(3)
    need = {}   # the jobs not done of each pump
    for f in plan:
        if not os.path.exists(f"{f[0]}_{f[3]}.dat"): need.setdefault(f[3], set()).add(f[0])
    wait = {(x[1], x[2]) for x in near} if how == "wait" else set()
    kept = {f[3] for f in plan if f[3] not in need} | {j for j, s in need.items() if all((pre, j) in wait for pre in s)}
    open("chushi.kept", "w").write(" ".join(sorted(kept)) + "\n")   # the pumps complete at the end (for Ten-Go)
    if wait:
        open("STOP", "w").write("chushi\n"); time.sleep(2); keep = {x[0] for x in near}
        kill([pid for pid in ours() if pid not in keep])   # also a job the driver launched before it saw the STOP
        print(f"chushi: {len(far)} jobs aborted ({sum(x[3] for x in far) / 3600:.1f} kh lost), {len(near)} left to complete; "
              f"the run ends about {time.strftime('%H:%M', time.localtime(time.time() + near[-1][4]))}")
    else: n = killall(); print(f"chushi: the driver and {n} jobs aborted ({sum(x[3] for x in fly) / 3600:.1f} kh lost); remove the file STOP before running again")
    sys.exit()
if os.path.exists("driver.pid"):
    try: os.kill(int(open("driver.pid").read()), 0); sys.exit(f"a driver is already running here (pid {open('driver.pid').read()})")
    except OSError: pass
open("driver.pid", "w").write(str(os.getpid()))


def nproc():
    try: return int(open("nproc").read().strip())
    except Exception: return 4


def memavail():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"): return int(l.split()[1]) / 1e6
    return 99


NCPU = os.cpu_count(); EVERY = float(os.environ.get("SHINSHU_EVERY", 60)); RAISE, LOWER = 10, 2   # looks: one a minute; 10 free, 2 busy


def ceiling():   # the file shinshu: a ceiling of kernels (a number, or max: every thread); 0 without it
    try: s = open("shinshu").read().strip()
    except OSError: return 0
    return NCPU if s in ("", "max") else int(s)


def others(roots, prev):
    """threads the machine spent since the last look on anything but this run's jobs (roots: their front-ends, with all their
    descendants), from /proc; prev carries the counters from one look to the next.  SHINSHU_OTHERS names a file of made-up values,
    one per look, for the tests"""
    if "SHINSHU_OTHERS" in os.environ:
        v = open(os.environ["SHINSHU_OTHERS"]).read().split(); prev["n"] = prev.get("n", -1) + 1; return float(v[min(prev["n"], len(v) - 1)])
    kids, ticks = {}, {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: f = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()
            except OSError: continue
            kids.setdefault(int(f[1]), []).append(int(d)); ticks[int(d)] = int(f[11]) + int(f[12])   # by parent; utime + stime
    mine, todo = set(), list(roots)
    while todo: q = todo.pop(); mine.add(q); todo += kids.get(q, [])
    c = list(map(int, open("/proc/stat").readline().split()[1:9])); busy, tot = sum(c) - c[3] - c[4], sum(c)   # all but idle, iowait
    old = dict(prev); prev.clear(); prev.update(busy=busy, tot=tot, ticks={q: ticks[q] for q in mine if q in ticks})
    if "tot" not in old or tot == old["tot"]: return None
    ours = sum(t - old["ticks"].get(q, 0) for q, t in prev["ticks"].items())   # a process born since the last look: all its ticks
    return max(0.0, (busy - old["busy"] - ours) / ((tot - old["tot"]) / NCPU))


def shinshu(limit, base, cap, free, hist):
    """the kernels of the run after one look (free: the threads no other work used): one more when at least that many were free for
    RAISE looks, back toward base as soon as other work has taken them for LOWER looks"""
    hist.append(max(base, min(cap, int(free)))); del hist[:-RAISE]
    if len(hist) >= LOWER and max(hist[-LOWER:]) < limit: return max(hist[-LOWER:])
    if len(hist) == RAISE and min(hist) > limit: return limit + 1
    return limit


def pick(extra):   # the next job: in the plan's order, or for a kernel above nproc the shortest waiting
    if not extra: return 0
    t = tcost
    m = {o: sum(v) / len(v) for o, v in took.items() if len(v) >= 3}   # this run's own times (3 jobs at least), and its speed against T
    f = sum(m[o] / t(o) for o in m) / len(m) if m else 1
    return min(range(len(jobs)), key=lambda i: m.get(order(jobs[i][0]), f * t(order(jobs[i][0]))))


jobs = [(f[0], int(f[1]), int(f[2]), f[3], f[4] if len(f) > 4 else PREC) for f in plan if not os.path.exists(f"{f[0]}_{f[3]}.dat")]   # a 5th field = the precision of that job
foreign = ours(); jobs = [j for j in jobs if (j[0], j[3]) not in foreign.values()]
if not os.path.exists("launch-epoch"):   # the launch time and the kernel time of the files present then (copied pumps), for the end estimate
    seed = sum(T.get(order(f[0]), 600 * (int(order(f[0])[:-1]) / 150) ** 3) for f in plan if os.path.exists(f"{f[0]}_{f[3]}.dat"))
    open("launch-epoch", "w").write(f"{int(time.time())} {seed:.0f}")
print(f"{time.strftime('%H:%M:%S')} {len(jobs)} jobs to run ({len(foreign)} adopted in flight), GA={GA} GS={GS} PREC={PREC}"
      + (f", shinshu up to {ceiling()} kernels" if ceiling() else ""), flush=True)
running = []; t0 = time.time(); done = 0; lastmem = 0; took = {}; limit = nproc(); hist = []; prev = {}; look = 0; uchi = False
while jobs or running or foreign:
    now = time.time(); base, cap = nproc(), ceiling()
    if os.path.exists("UCHIKIRI") and not uchi:   # end without loss: only the jobs of the pumps started (a job done or in flight)
        uchi = True; kept = {j for *_, j in running} | {j for _, j in foreign.values()} | {f[3] for f in plan if os.path.exists(f"{f[0]}_{f[3]}.dat")}
        if os.path.exists("uchikiri.kept"): kept = set(open("uchikiri.kept").read().split())   # a driver restarted after it
        else: open("uchikiri.tmp", "w").write(" ".join(sorted(kept)) + "\n"); os.replace("uchikiri.tmp", "uchikiri.kept")
        n = len(jobs); jobs = [x for x in jobs if x[3] in kept]
        print(f"{time.strftime('%H:%M:%S')} UCHIKIRI: {n - len(jobs)} jobs dropped, {len(jobs)} kept to complete the pumps started", flush=True)
    if not cap: hist.clear(); prev.clear(); limit = base
    elif now - look >= EVERY:
        look = now; o = others([p.pid for p, *_ in running] + list(foreign), prev)
        new = limit if o is None else shinshu(max(base, min(cap, limit)), base, cap, NCPU - o - 0.2, hist)
        if new != limit: print(f"{time.strftime('%H:%M:%S')} shinshu: {limit} -> {new} kernels (other work: {o:.1f} of {NCPU} threads)", flush=True)
        limit = new; open("shinshu.now", "w").write(f"{limit}\n")
    limit = max(base, min(cap, limit)) if cap else base
    if os.path.exists("STOP") and jobs: print(f"{time.strftime('%H:%M:%S')} STOP: {len(jobs)} jobs dropped", flush=True); jobs = []
    for pid in list(foreign):
        if not os.path.exists(f"/proc/{pid}"): pre, j = foreign.pop(pid); done += 1; print(f"{time.strftime('%H:%M:%S')} done (adopted) {pre} j={j}", flush=True)
    while jobs and len(running) + len(foreign) < limit and not os.path.exists("STOP"):
        if memavail() < MEMMIN:
            if now - lastmem > 300: print(f"{time.strftime('%H:%M:%S')} memory low ({memavail():.1f} GB available), holding launches", flush=True); lastmem = now
            break
        pre, nt, w, j, prec = jobs.pop(pick(len(running) + len(foreign) >= base))
        log = open(f"{pre}.log", "a")
        p = subprocess.Popen(["nice", "-n", "10", "wolframscript", "-file", "hp3.wls", str(nt), GA, GS, prec, pre, str(w), f"{j}:{pumps[j]}", "Ps", "manifold"],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        running.append((p, time.time(), pre, j)); time.sleep(1)
    time.sleep(5)
    still = []
    for p, ts, pre, j in running:
        if p.poll() is None: still.append((p, ts, pre, j))
        else:
            done += 1; ok = os.path.exists(f"{pre}_{j}.dat")
            if ok: took.setdefault(order(pre), []).append(time.time() - ts)
            print(f"{time.strftime('%H:%M:%S')} done {pre} j={j} P={pumps[j]} in {time.time()-ts:.0f} s {'' if ok else 'NO FILE'}; "
                  f"{done} done, {len(jobs)} waiting, {len(still)+len(foreign)} running, {(time.time()-t0)/60:.0f} min elapsed, {memavail():.0f} GB free", flush=True)
    running = still
print(f"{time.strftime('%H:%M:%S')} ALLDONE", flush=True)
os.remove("driver.pid")
if os.path.exists("shinshu.now"): os.remove("shinshu.now")
if os.path.exists("atend"):   # a command for the end of the run (Ten-Go's uchikiri: push the last results)
    cmd = open("atend").read().strip(); print(f"{time.strftime('%H:%M:%S')} atend: {cmd}", flush=True)
    r = subprocess.run(shlex.split(cmd), stdin=subprocess.DEVNULL); print(f"{time.strftime('%H:%M:%S')} atend: exit {r.returncode}", flush=True)
    if r.returncode == 0: os.remove("atend")
