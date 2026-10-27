#!/usr/bin/env python3
"""Operation Ten-Go v1.6 (lw page [[Ten-Go]]): several machines share one pool of pump jobs through a GitHub repository (public,
github.com/laussy/ten-go), and no pump is ever computed twice.  A machine asks for a BUDGET, not for pumps: `ten-go claim --hours 10` takes, in one
go, the free pumps of the campaign in its global (van der Corput) order until their cost on this machine fills the ten hours, the
longest job kept back so that the last jobs launched still end in time (a single pump if the budget is very small).  The claim is a
commit pushed to the repository; a push refused because another machine pushed first is redone from the new state, so that no pump
can be in two allocations.  An allocation has a deadline (its start + 1.5 budget + 2 h): the pumps it has not done by then go back to
the pool.  The jobs are run by run_window.py (kit/), one work directory per allocation.

Repository (the clone is Ten-Go's alone: every command starts by resetting it to origin/main):
  campaigns/<c>.json   params, file prefix, reference seconds per order, pumps [id, P, orders] in the global order
  machines/<m>.json    kernels, speed factor against the reference
  allocs/<c>/<id>.json one allocation: machine, budget, deadline, pumps, done, measured job times, results, status
  results/<c>/<id>-<n>.tgz   the .dat files of the pumps done, one archive per push
  ledger.tsv           the kernel-hours (kh) spent, per task: one line per allocation (brought up to date by done) or per run log
                       imported (any run of run_window.py, in Ten-Go or not), or booked by hand
The command is `ten-go`, a link to this file on the PATH (ln -s CLONE/tengo.py ~/bin/ten-go).  Local: ~/.config/tengo.json {"machine", "repo", "work"} (written by `ten-go init`; env TENGO_CONF names another file).

--until TAG, an AF tag (read back by ~/bin/AF, lw page [[AF]]) or 'YYYY-MM-DD HH:MM', ends a claim or a watch at that moment: claim
takes the hours from now until then in place of --hours.  Given both --hours and --until, claim only prints itself again, its --hours
set to those hours and --until dropped, with the kernel-hours (kh) they make as a comment.

--shinshu [N] (claim, launch, watch) lets the allocation take the threads that stay idle, from its kernels up to N (no N: every
thread of the machine), and give them back as soon as other work wants them: the driver looks every minute (kit/run_window.py), one
kernel more after 10 minutes of threads free of any other work, back toward the allocation's kernels after 2 minutes of activity; a
kernel above them runs the shortest job waiting, so that the retreat is quick.  The budget is unchanged: shinshu only ends it sooner.

release --uchikiri (or ten-go --uchikiri) ends this machine's allocations as soon as possible without loss: each driver launches
no new pump and completes those started (a job done or in flight), and says when it will end, and what a STOP or a kill would waste
instead; the pumps not started go back to the pool at once, a watch of the machine claims nothing more, and the driver pushes the last
results when it ends.  With --dry, it only says when.

A kh is one kernel for one hour: the jobs' own times summed, a failed job's included (an adopted job's time, unknown, is not).  The
ledger keeps what each task cost: `ten-go kh` shows the totals per task and machine, `ten-go kh TASK` the lines of a task.

Usage: ten-go init MACHINE --repo CLONE --work DIR | status [-c C] | claim --hours H|--until TAG [-c C] [--kernels N] [--go] [--shinshu [N]]
       | done [--alloc ID] | release [--alloc ID] [--uchikiri [--dry]] | launch [--alloc ID] [--shinshu [N]] | watch --until TAG [--hours 10] [-c C] [--shinshu [N]]
       | fetch [-c C] [DIR] (unpack every result into DIR) | mkcampaign NAME
       | kh [TASK] | kh import DIR [TASK] [--machine M] [--note TEXT] | kh add TASK KH [--machine M] [--note TEXT]"""
import argparse, glob, json, os, random, re, shlex, shutil, subprocess, sys, tarfile, time
VERSION = "1.6"   # 1.1: claim --go (was --launch) starts the driver; 1.2: the command is ten-go (a link to this file); 1.3: --until TAG; 1.4: kh, the ledger; 1.5: --shinshu; 1.6: --uchikiri
CONF = os.environ.get("TENGO_CONF", os.path.expanduser("~/.config/tengo.json"))   # another file for a test identity
C = {}


def die(msg): sys.exit(f"ten-go: {msg}")
def R(*p): return os.path.join(C["repo"], *p)
def stamp(t): return time.strftime("%a %d %b %H:%M", time.localtime(t))


def moment(s):
    """the time of --until: an AF tag, read back by ~/bin/AF (not a copy of its decoder here), or 'YYYY-MM-DD HH:MM'"""
    if re.fullmatch(r"[0-9A-Za-z]{5,6}", s):
        try: r = subprocess.run([shutil.which("AF") or os.path.expanduser("~/bin/AF"), "-b", s], capture_output=True, text=True)
        except FileNotFoundError: die(f"--until {s}: reading an AF tag needs ~/bin/AF")
        if r.returncode: die(f"--until {s}: {r.stderr.strip()}")
        return int(r.stdout.split("\t")[0])
    try: return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))
    except ValueError: die(f"--until {s}: neither an AF tag nor 'YYYY-MM-DD HH:MM'")


def hours_until(s):
    t = moment(s); h = int((t - time.time()) / 36) / 100   # floored to 0.01 h
    if h <= 0: die(f"--until {s}: {stamp(t)} is past")
    return h, t


def restated(h):
    """the command line as typed, its --hours set to h and --until dropped (the options as argparse takes them, abbreviated or with =)"""
    out, args = ["ten-go"], iter(sys.argv[1:])
    for x in args:
        k = x.split("=", 1)[0]
        if len(k) > 3 and "--hours".startswith(k): out += ["--hours", f"{h:g}"]
        elif len(k) > 2 and "--until".startswith(k): pass
        else: out.append(x); continue
        if "=" not in x: next(args, None)
    return " ".join(map(shlex.quote, out))


def git(*a, check=True):
    r = subprocess.run(["git", "-C", C["repo"], *a], capture_output=True, text=True)
    if check and r.returncode: die(f"git {' '.join(a)} failed:\n{r.stderr.strip()}")
    return r


def sync(): git("fetch", "-q", "origin"); git("reset", "-q", "--hard", "origin/main")


def transact(change, msg):
    """apply `change` to the fresh state of the repository (it returns what it did, or None when there is nothing to do) and push; a
    refused push (another machine pushed first) is redone from the new state, so that a claim is recomputed from what is still free"""
    for attempt in range(10):
        sync(); out = change()
        if out is None: return None
        git("add", "-A"); git("commit", "-q", "-m", msg(out))
        if git("push", "-q", "origin", "HEAD:main", check=False).returncode == 0: return out
        print("ten-go: push refused (another machine pushed first), redoing from the new state", file=sys.stderr)
        time.sleep(random.uniform(2, 10))
    die("could not push after 10 attempts")


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: json.dump(obj, f, indent=1); f.write("\n")


def campaigns(): return sorted(os.path.basename(f)[:-5] for f in glob.glob(R("campaigns", "*.json")))
def campaign(c): return json.load(open(R("campaigns", c + ".json")))
def allocs(c): return [json.load(open(f)) for f in sorted(glob.glob(R("allocs", c, "*.json")))]
def machine(m): return json.load(open(R("machines", m + ".json")))
def workdir(a): return os.path.join(C["work"], a["campaign"], a["id"])
def parse(o): m = re.fullmatch(r"(\d+)([we])(\d*)", o); return int(m[1]), int(m[2] == "w"), m[3]   # "150w80": n_t 150, weights, 80 digits
def kh(s): return f"{s / 3600:.1f}"
def upto(v): return "every thread" if v == "max" else f"{v} kernels"
def ceiling(v, kern):   # --shinshu: None, max (every thread of the machine), or a number of kernels above kern
    if v in (None, "max"): return v
    try: n = int(v)
    except ValueError: die(f"--shinshu {v}: a number of kernels, or nothing for every thread of the machine")
    return n if n > kern else die(f"--shinshu {n}: not above the {kern} kernels of the allocation")
def tilde(p): h = os.path.expanduser("~"); return "~" + p[len(h):] if p.startswith(h + "/") else p


LEDGER = ["task", "machine", "source", "jobs", "failed", "kh", "first", "last", "note"]   # first and last job done


def ledger(): return [dict(zip(LEDGER, l.rstrip("\n").split("\t"))) for l in open(R("ledger.tsv")).readlines()[1:]] if os.path.exists(R("ledger.tsv")) else []


def save_ledger(L):
    with open(R("ledger.tsv"), "w") as f:
        f.write("\t".join(LEDGER) + "\n")   # a header GitHub shows as a table
        for e in sorted(L, key=lambda e: (e["first"], e["source"])): f.write("\t".join(str(e[k]) for k in LEDGER) + "\n")


def logspent(W):
    """jobs, failed jobs and kernel-seconds of the jobs a run.log of run_window.py reports done, and when the first and the last of
    them ended (the times of their files: the log has no dates)"""
    n = bad = sec = 0; f = os.path.join(W, "run.log"); T = []
    for l in (open(f) if os.path.exists(f) else []):
        m = re.search(r" done (\S+) j=(\d+) P=\S+ in (\d+) s", l)
        if not m: continue
        n += 1; sec += int(m[3]); bad += "NO FILE" in l; d = os.path.join(W, f"{m[1]}_{m[2]}.dat")
        if os.path.exists(d): T.append(os.path.getmtime(d))
    T = T or [os.path.getmtime(f)] if n else [0]
    return n, bad, sec, min(T), max(T)


def book(L, task, m, source, spent, note=""):
    """bring the line of `source` up to `spent` (from logspent); True when it changed"""
    n, bad, sec, t0, t1 = spent; d = lambda t: time.strftime("%Y-%m-%d %H:%M", time.localtime(t)); e = next((e for e in L if e["source"] == source), None)
    if e is None and n: L.append(dict(task=task, machine=m, source=source, jobs=n, failed=bad, kh=f"{sec / 3600:.2f}", first=d(t0), last=d(t1), note=note))
    elif e and (str(n), f"{sec / 3600:.2f}") != (e["jobs"], e["kh"]): e.update(jobs=n, failed=bad, kh=f"{sec / 3600:.2f}", last=d(t1))
    else: return False
    return True


def pick(c):
    cs = campaigns()
    if c: return c if c in cs else die(f"no campaign {c} (there are: {', '.join(cs)})")
    if len(cs) == 1: return cs[0]
    die(f"say which campaign with -c ({', '.join(cs)})")


def held(A, now):
    """the pumps out of the pool: those done, and all those of an open allocation before its deadline"""
    out = set()
    for a in A:
        out |= set(a["done"])
        if a["status"] == "open" and now < a["deadline"]: out |= set(a["pumps"])
    return out


def secs(cm, A, m, o):
    """seconds of one job of order o on machine m: the median of its measured jobs in this campaign (5 at least), else the reference
    of the campaign times the machine's factor"""
    t = sorted(x for a in A if a["machine"] == m for x in a.get("times", {}).get(o, []))
    return t[len(t) // 2] if len(t) >= 5 else cm["ref"][o] * machine(m).get("factor", 1.0)


def cost(cm, A, m):
    S = {o: secs(cm, A, m, o) for o in cm["ref"]}
    return S, {pid: sum(S[o] for o in orders) for pid, P, orders in cm["pumps"]}


# ----------------------------------------------------------------------------------------------------------------- the work directory
def setup(a):
    cm = campaign(a["campaign"]); W = workdir(a); os.makedirs(W, exist_ok=True)
    for f in ("hp3.wls", "run_window.py"): shutil.copy(R("kit", f), W)
    P = {pid: (Pv, orders) for pid, Pv, orders in cm["pumps"]}
    open(os.path.join(W, "pumps.txt"), "w").write("".join(f"{pid} {P[pid][0]}\n" for pid in a["pumps"]))
    open(os.path.join(W, "params.txt"), "w").write("".join(f"{k}={v}\n" for k, v in cm["params"].items()))
    open(os.path.join(W, "nproc"), "w").write(f"{a['kernels']}\n")
    if a.get("shinshu"): open(os.path.join(W, "shinshu"), "w").write(f"{a['shinshu']}\n")   # read by the driver every minute
    with open(os.path.join(W, "plan.txt"), "w") as f:
        f.write(f"# prefix nt withWeights j [prec]   (Ten-Go allocation {a['id']} of {a['campaign']}: {len(a['pumps'])} pumps in the global order)\n")
        for pid in a["pumps"]:
            for o in P[pid][1]:
                nt, w, prec = parse(o); f.write(f"{cm['prefix']}_nt{o} {nt} {w} {pid}" + (f" {prec}" if prec else "") + "\n")
    save(os.path.join(W, "alloc.json"), a)
    return W


def ours(W):
    """pids of the driver and of the hp3.wls front-ends running in W"""
    drv, fe = [], []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(d + "/cmdline").read().split("\0")
            if os.readlink(d + "/cwd") != W: continue
        except OSError: continue
        if any(x.endswith("run_window.py") for x in cmd) and "python3" in os.path.basename(cmd[0]): drv.append(int(d[6:]))
        elif "hp3.wls" in cmd and "wolframscript" in os.path.basename(cmd[0]): fe.append(int(d[6:]))
    return drv, fe


def launch(a, quiet=False, shinshu=None):
    W = workdir(a)
    if not os.path.isdir(W): setup(a)
    if shinshu: open(os.path.join(W, "shinshu"), "w").write(f"{ceiling(shinshu, a['kernels'])}\n")
    if ours(W)[0]: return quiet or print(f"ten-go: the driver of {a['id']} is already running")
    if os.path.exists(os.path.join(W, "STOP")): die(f"{W}/STOP exists (released or stopped by hand): remove it to run again")
    for f in glob.glob(os.path.join(W, "*.dat")):
        if os.path.getsize(f) < 1000: os.remove(f)   # the leftover of a killed job
    cmd = (["systemd-inhibit", "--what=sleep:idle", f"--why=Ten-Go {a['id']}"] if shutil.which("systemd-inhibit") else []) + ["python3", "run_window.py"]
    subprocess.Popen(cmd, cwd=W, stdin=subprocess.DEVNULL, stdout=open(os.path.join(W, "run.log"), "a"), stderr=subprocess.STDOUT, start_new_session=True)
    sh = open(os.path.join(W, "shinshu")).read().strip() if os.path.exists(os.path.join(W, "shinshu")) else ""
    print(f"ten-go: launched {a['id']} in {W} on {a['kernels']} kernels" + (f", shinshu up to {upto(sh)}" if sh else ""))


# ----------------------------------------------------------------------------------------------------------------------- commands
def cmd_claim(c, hours, kernels=None, do_launch=False, shinshu=None):
    m = C["machine"]; kern = kernels or machine(m)["kernels"]; c = pick(c); sh = ceiling(shinshu, kern)
    def change():
        cm = campaign(c); A = allocs(c); now = time.time(); busy = held(A, now); S, K1 = cost(cm, A, m)
        budget = kern * max(hours * 3600 - max(S.values()), 0)   # kernel-seconds, the longest job kept back
        take, tot = [], 0.0
        for pid, P, orders in cm["pumps"]:
            if pid in busy: continue
            if take and tot + K1[pid] > budget: break
            take.append(pid); tot += K1[pid]
        if not take: return None
        aid = base = f"{m}-{time.strftime('%Y%m%d-%H%M%S')}"; k = 1
        while os.path.exists(R("allocs", c, aid + ".json")): k += 1; aid = f"{base}-{k}"   # two claims in the same second
        a = dict(id=aid, campaign=c, machine=m, kernels=kern, hours=hours, created=int(now), deadline=int(now + 1.5 * hours * 3600 + 7200),
                 cost_kernel_h=round(tot / 3600, 1), pumps=take, done=[], times={}, results=[], status="open", tengo=VERSION, shinshu=sh)
        save(R("allocs", c, aid + ".json"), a); return a
    a = transact(change, lambda a: f"claim {a['id']}: {len(a['pumps'])} pumps of {c}, {a['hours']:g} h on {a['kernels']} kernels")
    if a is None: return print(f"ten-go: nothing free in {c}")
    W = setup(a); P = {pid: Pv for pid, Pv, _ in campaign(c)["pumps"]}; xs = sorted(float(P[p]) for p in a["pumps"])
    print(f"ten-go: claimed {a['id']}: {len(a['pumps'])} pumps of {c} ({xs[0]:g}-{xs[-1]:g} g, spread in the global order), "
          f"{a['cost_kernel_h']} kh for {hours:g} h on {kern} kernels; deadline {stamp(a['deadline'])}; work directory {W}"
          + (f"; shinshu up to {upto(sh)}" if sh else ""))
    if do_launch: launch(a)
    return a


def complete(a, cm):
    W = workdir(a); O = {pid: orders for pid, _, orders in cm["pumps"]}
    ok = lambda f: os.path.exists(f) and os.path.getsize(f) > 1000
    return [p for p in a["pumps"] if all(ok(os.path.join(W, f"{cm['prefix']}_nt{o}_{p}.dat")) for o in O[p])]


def jobtimes(W, prefix, pids):
    out = {}
    if os.path.exists(os.path.join(W, "run.log")):
        for l in open(os.path.join(W, "run.log")):
            m = re.search(rf"done {re.escape(prefix)}_nt(\w+) j=(\d+) P=\S+ in (\d+) s", l)
            if m and int(m[2]) in pids and "NO FILE" not in l: out.setdefault(m[1], []).append(int(m[3]))
    return out


def cmd_done(aid=None, final=None):
    """push the pumps finished since the last push (their files as one archive), their job times, and the status of the allocation"""
    def change():
        out = []; L = ledger(); booked = False
        for c in campaigns():
            cm = campaign(c); O = {pid: orders for pid, _, orders in cm["pumps"]}
            for a in allocs(c):
                if a["machine"] != C["machine"] or a["status"] != "open" or (aid and a["id"] != aid) or not os.path.isdir(workdir(a)): continue
                W = workdir(a); have = set(a["done"]); new = [p for p in complete(a, cm) if p not in have]
                if new:
                    rel = f"results/{c}/{a['id']}-{len(a['results']) + 1}.tgz"; os.makedirs(R("results", c), exist_ok=True)
                    with tarfile.open(R(rel), "w:gz") as t:
                        for p in new:
                            for o in O[p]: n = f"{cm['prefix']}_nt{o}_{p}.dat"; t.add(os.path.join(W, n), arcname=n)
                    a["results"].append(rel); a["done"] += new
                    for o, v in jobtimes(W, cm["prefix"], set(new)).items(): a["times"].setdefault(o, []).extend(v)
                st = final or ("finished" if set(a["done"]) >= set(a["pumps"]) else "open")
                sp = logspent(W); b = book(L, c, a["machine"], "alloc " + a["id"], sp); booked |= b
                if new or st != a["status"]:
                    a["status"] = st; a["updated"] = int(time.time()); save(R("allocs", c, a["id"] + ".json"), a)
                    out.append(f"{a['id']}: +{len(new)} pumps ({len(a['done'])}/{len(a['pumps'])} done), {st}, {kh(sp[2])} kh spent")
                elif b: out.append(f"{a['id']}: {kh(sp[2])} kh spent")
        if booked: save_ledger(L)
        return out or None
    out = transact(change, lambda o: "done: " + "; ".join(o))
    print("ten-go: " + ("; ".join(out) if out else "nothing new to push"))


def cmd_release(aid=None):
    sync()
    mine = [a for c in campaigns() for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open" and (not aid or a["id"] == aid)]
    if not mine: return print("ten-go: no open allocation of this machine")
    for a in mine:
        W = workdir(a)
        if os.path.isdir(W) and any(ours(W)): subprocess.run(["python3", "run_window.py", "--kill"], cwd=W)   # its own jobs only
        elif os.path.isdir(W): open(os.path.join(W, "STOP"), "w").write("released\n")
    for a in mine: cmd_done(a["id"], final="released")


def cmd_uchikiri(aid=None, dry=False):
    """end this machine's open allocations as soon as possible without loss (run_window.py --uchikiri, which says when); the pumps not
    started go back to the pool at once, and the driver pushes the last results when it ends (its file atend)"""
    sync()
    mine = [a for c in campaigns() for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open" and (not aid or a["id"] == aid)]
    if not mine: return print("ten-go: no open allocation of this machine")
    if not dry: open(os.path.join(C["work"], "UCHIKIRI"), "w").write(f"{int(time.time())}\n")   # a watch of this machine claims no more
    for a in mine:
        W = workdir(a)
        if not (os.path.isdir(W) and ours(W)[0]): print(f"ten-go: {a['id']}: no driver running (`ten-go release` gives its pumps back)"); continue
        if not dry: open(os.path.join(W, "atend"), "w").write(shlex.join(["env", f"TENGO_CONF={CONF}", sys.executable, os.path.realpath(__file__), "done", "--alloc", a["id"]]) + "\n")
        r = subprocess.run(["python3", "run_window.py", "--uchikiri"] + (["--dry"] if dry else []), cwd=W, capture_output=True, text=True)
        say = (r.stdout + r.stderr).strip()
        if dry or r.returncode: print(f"ten-go: {a['id']}: {say}"); continue
        kept = set(open(os.path.join(W, "uchikiri.kept")).read().split())   # the pumps started, as the driver saw them
        def change():
            x = json.load(open(R("allocs", a["campaign"], a["id"] + ".json")))
            back = [p for p in x["pumps"] if str(p) not in kept and p not in x["done"]]
            if x["status"] != "open" or not back: return None
            x["pumps"] = [p for p in x["pumps"] if p not in back]; x["uchikiri"] = int(time.time()); save(R("allocs", a["campaign"], a["id"] + ".json"), x)
            return len(back)
        n = transact(change, lambda n: f"uchikiri {a['id']}: {n} pumps back to the pool")
        print(f"ten-go: {a['id']}: {n or 0} pumps back to the pool at once; {say}; the driver pushes the last results when it ends")


def cmd_status(c=None):
    sync(); now = time.time()
    for c in ([pick(c)] if c else campaigns()):
        cm = campaign(c); A = allocs(c); N = len(cm["pumps"])
        done = set().union(*(set(a["done"]) for a in A)) if A else set(); hold = held(A, now) - done
        _, K1 = cost(cm, A, "azag" if os.path.exists(R("machines", "azag.json")) else C["machine"])
        left = sum(K1[p] for p, _, _ in cm["pumps"] if p not in done) / 3600; b = int(40 * len(done) / N)
        print(f"{c}: [{'#' * b}{'.' * (40 - b)}] {len(done)}/{N} pumps done, {len(hold)} held, {N - len(done) - len(hold)} free; "
              f"{left:.0f} kh left at the reference speed; {sum(float(e['kh']) for e in ledger() if e['task'] == c):.1f} kh spent")
        for m in sorted({a["machine"] for a in A}):
            op = [a for a in A if a["machine"] == m and a["status"] == "open"]
            S, Km = cost(cm, A, m); rest = sum(Km[p] for a in op for p in a["pumps"] if p not in set(a["done"]))
            kern = max([a["kernels"] for a in op] or [machine(m)["kernels"]])
            print(f"  {m}: {sum(len(a['done']) for a in A if a['machine'] == m)} pumps done in all, "
                  f"{sum(float(e['kh']) for e in ledger() if e['task'] == c and e['machine'] == m):.1f} kh; "
                  + (f"holds {sum(len(a['pumps']) - len(a['done']) for a in op)}, {rest / 3600:.0f} kh, end about {stamp(now + rest / kern)}" if op else "holds nothing"))
        for a in sorted(A, key=lambda a: a["created"])[-12:]:
            late = a["status"] == "open" and now > a["deadline"]
            print(f"    {a['id']:24s} {len(a['done']):4d}/{len(a['pumps']):<4d} {a['status']:9s} {a['hours']:g} h x {a['kernels']}"
                  + (f" (shinshu up to {upto(a['shinshu'])})" if a.get("shinshu") else "") + f", deadline {stamp(a['deadline'])}"
                  + (f", uchikiri {stamp(a['uchikiri'])}" if a.get("uchikiri") else "")
                  + ("  PASSED: its pumps not done are free again" if late else ""))


def cmd_kh(args, mach=None, note=""):
    """the ledger: totals per task and machine (kh), the lines of one task (kh TASK), a run log booked (kh import DIR [TASK]: again
    later, its line is brought up to date), or a run without a log booked by hand (kh add TASK KH)"""
    m = mach or C["machine"]
    if args and args[0] == "import":
        if len(args) not in (2, 3): die("kh import DIR [TASK]")
        D = os.path.abspath(os.path.expanduser(args[1])); task = args[2] if len(args) == 3 else os.path.basename(D); sp = logspent(D)
        if not sp[0]: die(f"no job done in {tilde(D)}/run.log")
        def change():
            L = ledger()
            if not book(L, task, m, f"log {m}:{tilde(D)}", sp, note): return None
            save_ledger(L); return True
        r = transact(change, lambda r: f"kh: {task} on {m}, {tilde(D)}: {sp[0]} jobs, {kh(sp[2])} kh")
        print(f"ten-go: {task} on {m}: {sp[0]} jobs ({sp[1]} failed), {kh(sp[2])} kh" + ("" if r else ", already in the ledger"))
    elif args and args[0] == "add":
        if len(args) != 3: die("kh add TASK KH")
        task, now = args[1], time.strftime("%Y-%m-%d %H:%M")
        try: x = float(args[2])
        except ValueError: die(f"kh add {task} {args[2]}: KH is a number of kernel-hours")
        def change():
            L = ledger(); L.append(dict(task=task, machine=m, source=f"by hand {now}", jobs="", failed="", kh=f"{x:.2f}", first=now, last=now, note=note))
            save_ledger(L); return True
        transact(change, lambda r: f"kh: {task} on {m}, {x:g} kh by hand"); print(f"ten-go: {task} on {m}: {x:g} kh booked by hand")
    else:
        sync(); L = ledger()
        if not L: return print("ten-go: the ledger is empty")
        if args:
            E = [e for e in L if e["task"] == args[0]] or die(f"no task {args[0]} in the ledger")
            for e in E: print(f"  {e['machine']:6s} {float(e['kh']):9.1f} kh {e['jobs']:>6s} jobs  {e['first']} to {e['last']}  {e['source']}  {e['note']}")
            return print(f"  {'all':6s} {sum(float(e['kh']) for e in E):9.1f} kh")
        M = sorted({e["machine"] for e in L}); T = sorted({e["task"] for e in L}, key=lambda t: min(e["first"] for e in L if e["task"] == t))
        tot = lambda t=None, mm=None: sum(float(e["kh"]) for e in L if (t is None or e["task"] == t) and (mm is None or e["machine"] == mm))
        w = max(len(t) for t in T + ["task"]); print(f"kernel-hours spent (ledger.tsv, {len(L)} lines)")
        print(f"  {'task':{w}s}" + "".join(f"{mm:>9s}" for mm in M) + f"{'all':>9s}  first job")
        for t in T: print(f"  {t:{w}s}" + "".join(f"{tot(t, mm):9.1f}" if tot(t, mm) else f"{'-':>9s}" for mm in M) + f"{tot(t):9.1f}  {min(e['first'] for e in L if e['task'] == t)[:10]}")
        print(f"  {'all':{w}s}" + "".join(f"{tot(None, mm):9.1f}" for mm in M) + f"{tot():9.1f}")


def tail_state(W):
    """jobs still waiting in the driver of W (from its log) and front-ends running"""
    wait = None
    if os.path.exists(os.path.join(W, "run.log")):
        for l in open(os.path.join(W, "run.log")):
            m = re.search(r"(\d+) jobs to run|(\d+) waiting", l)
            if m: wait = int(m[1] or m[2])
    return wait, len(ours(W)[1])


def cmd_watch(until, hours, c, shinshu=None):
    """the unattended loop: claim and launch an allocation while time remains before `until`, push the pumps done every 30 min,
    restart a dead driver (3 times per allocation at most), and claim the next allocation as soon as the current one has launched all
    its jobs, its tail then lending its kernels to the new one (the nproc of the new driver = kernels - jobs of the tail)"""
    end = moment(until); restarts = {}; last = 0; c = pick(c); t0 = time.time(); flag = os.path.join(C["work"], "UCHIKIRI")
    print(f"ten-go watch until {stamp(end)} ({C['machine']}, {c})", flush=True)
    while True:
        now = time.time()
        if end > now and os.path.exists(flag) and os.path.getmtime(flag) > t0:
            end = now; print(f"{time.strftime('%H:%M:%S')} uchikiri: no more claims, the watch ends with its drivers", flush=True)
        if now - last > 1800: cmd_done(); last = now
        sync(); op = [a for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open"]
        for a in op:
            W = workdir(a); log = open(os.path.join(W, "run.log")).read() if os.path.exists(os.path.join(W, "run.log")) else ""
            if not ours(W)[0] and "ALLDONE" not in log.split("tengo-launch")[-1] and not os.path.exists(os.path.join(W, "STOP")):
                if restarts.get(a["id"], 0) >= 3: continue
                restarts[a["id"]] = restarts.get(a["id"], 0) + 1; print(f"{time.strftime('%H:%M:%S')} driver of {a['id']} not running: start {restarts[a['id']]}", flush=True)
                open(os.path.join(W, "run.log"), "a").write(f"{time.strftime('%H:%M:%S')} tengo-launch (watch)\n"); launch(a, quiet=True)
        tails = [(a, *tail_state(workdir(a))) for a in op]
        fresh = [a for a, wait, run in tails if wait]           # an allocation still launching jobs
        if not fresh and end - now > 1800:
            busy = sum(run for _, _, run in tails); kern = machine(C["machine"])["kernels"]
            a = cmd_claim(c, min(hours, (end - now) / 3600), kern, shinshu=shinshu)
            if a:
                open(os.path.join(workdir(a), "nproc"), "w").write(f"{max(kern - busy, 1)}\n"); launch(a)
        if fresh and len(op) > 1:                               # the newest allocation takes the kernels the tails free
            busy = sum(run for a, wait, run in tails if not wait); kern = machine(C["machine"])["kernels"]
            for a in fresh: open(os.path.join(workdir(a), "nproc"), "w").write(f"{max(kern - busy, 1)}\n")
        if now > end and not any(run for _, _, run in tails): cmd_done(); print(f"{time.strftime('%H:%M:%S')} watch ends", flush=True); return
        time.sleep(60)


def cmd_fetch(c, dest):
    sync(); c = pick(c); os.makedirs(dest, exist_ok=True); n = 0
    for f in sorted(glob.glob(R("results", c, "*.tgz"))):
        with tarfile.open(f) as t: t.extractall(dest, filter="data"); n += len(t.getnames())
    print(f"ten-go: {n} files of {c} in {dest}")


# ------------------------------------------------------------------------------------------------------------------------ campaigns
def vdc(n):
    m = max(1, (n - 1).bit_length()); return [r for r in (int(format(k, f"0{m}b")[::-1], 2) for k in range(2 ** m)) if r < n]


def mk_close004():
    """close 0.15-12.51 g at 0.004 g: P = 0.150 + 0.004 k (thousandths = 2 mod 4, the sublattice of Sec. 31), without the pumps of
    Sec. 31 (k = 0 mod 5), the windows of yzao (0.502-1.498, 9.002-9.598 g) and the span 5-6 g of Sec. 32 (its 0.004 g grid is the
    other sublattice); below 5 g n_t = 150 with weights and 200 (certificate B), above 150, 250 and 300 (D), as in Sec. 31"""
    P = []
    for k in range(3091):
        th = 150 + 4 * k
        if k % 5 == 0 or 502 <= th <= 1498 or 5000 <= th <= 6000 or 9002 <= th <= 9598: continue
        P.append((f"{th // 1000}.{th % 1000:03d}", ["200e", "150w"] if th < 5000 else ["300e", "250e", "150w"]))
    pumps = [[i, P[i][0], P[i][1]] for i in vdc(len(P))]   # id = rank in pump, list = the global (van der Corput) order
    return dict(name="close-0.004", prefix="hpT", about=mk_close004.__doc__.split("\n")[0].strip() + " ...",
                params=dict(GA="1/10", GS="293/780364", PREC="40", MEMMIN="8"),
                ref={"150w": 1118, "200e": 760, "250e": 1580, "300e": 2685}, pumps=pumps)


CAMPAIGNS = {"close-0.004": mk_close004}


def main():
    ap = argparse.ArgumentParser(prog="ten-go", description="Operation Ten-Go: a shared pool of pump jobs in a git repository")
    ap.add_argument("cmd", nargs="?"); ap.add_argument("arg", nargs="?"); ap.add_argument("more", nargs="*"); ap.add_argument("-c", "--campaign")
    ap.add_argument("--hours", type=float); ap.add_argument("--kernels", type=int); ap.add_argument("--go", action="store_true")
    ap.add_argument("--alloc"); ap.add_argument("--until"); ap.add_argument("--repo"); ap.add_argument("--work")
    ap.add_argument("--machine"); ap.add_argument("--note", default=""); ap.add_argument("--shinshu", nargs="?", const="max")
    ap.add_argument("--uchikiri", action="store_true"); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "claim" and a.hours and a.until:
        h = hours_until(a.until)[0]; k = a.kernels
        if not k:
            try: C.update(json.load(open(CONF))); k = machine(C["machine"])["kernels"]   # no sync: only this machine's kernels
            except (OSError, KeyError, ValueError): pass
        return print(restated(h) + (f"   # {h:g} h x {k} kernels = {h * k:.1f} kh" if k else ""))
    if a.cmd in ("-v", "version"): return print(f"ten-go {VERSION}")
    if a.uchikiri and a.cmd not in (None, "release"): die("--uchikiri goes with release, or alone")
    if a.cmd is None and not a.uchikiri: die(f"no command\n{__doc__}")
    if a.cmd == "init":
        if not (a.arg and a.repo and a.work): die("ten-go init MACHINE --repo CLONE --work DIR")
        save(CONF, dict(machine=a.arg, repo=os.path.abspath(os.path.expanduser(a.repo)), work=os.path.abspath(os.path.expanduser(a.work))))
        return print(f"ten-go: {CONF} written ({a.arg})")
    try: C.update(json.load(open(CONF)))
    except FileNotFoundError: die(f"no {CONF}: run `ten-go init MACHINE --repo CLONE --work DIR` first")
    if a.uchikiri: cmd_uchikiri(a.alloc, a.dry)
    elif a.cmd == "status": cmd_status(a.campaign)
    elif a.cmd == "claim":
        if a.until: a.hours, t = hours_until(a.until); print(f"ten-go: until {a.until}, {stamp(t)}: {a.hours:g} h from now")
        if not a.hours: die("claim --hours H, or --until TAG")
        cmd_claim(a.campaign, a.hours, a.kernels, a.go, a.shinshu)
    elif a.cmd == "done": cmd_done(a.alloc)
    elif a.cmd == "release": cmd_release(a.alloc)
    elif a.cmd == "launch":
        sync(); op = [x for c in campaigns() for x in allocs(c) if x["machine"] == C["machine"] and x["status"] == "open" and (not a.alloc or x["id"] == a.alloc)]
        for x in op: launch(x, shinshu=a.shinshu)
        if not op: print("ten-go: no open allocation of this machine")
    elif a.cmd == "watch":
        if not a.until: die("watch --until TAG (an AF tag, or 'YYYY-MM-DD HH:MM')")
        cmd_watch(a.until, a.hours or 10, a.campaign, a.shinshu)
    elif a.cmd == "fetch": cmd_fetch(a.campaign, a.arg or ".")
    elif a.cmd == "kh": cmd_kh(([a.arg] if a.arg else []) + a.more, a.machine, a.note)
    elif a.cmd == "mkcampaign":
        if a.arg not in CAMPAIGNS: die(f"known campaigns: {', '.join(CAMPAIGNS)}")
        cm = CAMPAIGNS[a.arg](); transact(lambda: save(R("campaigns", a.arg + ".json"), cm) or a.arg, lambda o: f"campaign {o}: {len(cm['pumps'])} pumps")
        print(f"ten-go: campaign {a.arg}, {len(cm['pumps'])} pumps")
    else: die(f"unknown command {a.cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
