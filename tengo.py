#!/usr/bin/env python3
"""Operation Ten-Go v1.0 (lw page [[Operation Ten-Go]]): several machines share one pool of pump jobs through a private GitHub
repository, and no pump is ever computed twice.  A machine asks for a BUDGET, not for pumps: `tengo claim --hours 10` takes, in one
go, the free pumps of the campaign in its global (van der Corput) order until their cost on this machine fills the ten hours, the
longest job kept back so that the last jobs launched still end in time (a single pump if the budget is very small).  The claim is a
commit pushed to the repository; a push refused because another machine pushed first is redone from the new state, so that no pump
can be in two allocations.  An allocation has a deadline (its start + 1.5 budget + 2 h): the pumps it has not done by then go back to
the pool.  The jobs are run by run_window.py (kit/), one work directory per allocation.

Repository (the clone is tengo's alone: every command starts by resetting it to origin/main):
  campaigns/<c>.json   params, file prefix, reference seconds per order, pumps [id, P, orders] in the global order
  machines/<m>.json    kernels, speed factor against the reference
  allocs/<c>/<id>.json one allocation: machine, budget, deadline, pumps, done, measured job times, results, status
  results/<c>/<id>-<n>.tgz   the .dat files of the pumps done, one archive per push
Local: ~/.config/tengo.json {"machine", "repo", "work"} (written by `tengo init`; env TENGO_CONF names another file).

Usage: tengo init MACHINE --repo CLONE --work DIR | status [-c C] | claim --hours H [-c C] [--kernels N] [--launch]
       | done [--alloc ID] | release [--alloc ID] | launch [--alloc ID] | watch --until 'YYYY-MM-DD HH:MM' [--hours 10] [-c C]
       | fetch [-c C] [DIR] (unpack every result into DIR) | mkcampaign NAME"""
import argparse, glob, json, os, random, re, shutil, subprocess, sys, tarfile, time
VERSION = "1.0"
CONF = os.environ.get("TENGO_CONF", os.path.expanduser("~/.config/tengo.json"))   # another file for a test identity
C = {}


def die(msg): sys.exit(f"tengo: {msg}")
def R(*p): return os.path.join(C["repo"], *p)
def stamp(t): return time.strftime("%a %d %b %H:%M", time.localtime(t))


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
        print("tengo: push refused (another machine pushed first), redoing from the new state", file=sys.stderr)
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


def launch(a, quiet=False):
    W = workdir(a)
    if not os.path.isdir(W): setup(a)
    if ours(W)[0]: return quiet or print(f"tengo: the driver of {a['id']} is already running")
    if os.path.exists(os.path.join(W, "STOP")): die(f"{W}/STOP exists (released or stopped by hand): remove it to run again")
    for f in glob.glob(os.path.join(W, "*.dat")):
        if os.path.getsize(f) < 1000: os.remove(f)   # the leftover of a killed job
    cmd = (["systemd-inhibit", "--what=sleep:idle", f"--why=Ten-Go {a['id']}"] if shutil.which("systemd-inhibit") else []) + ["python3", "run_window.py"]
    subprocess.Popen(cmd, cwd=W, stdin=subprocess.DEVNULL, stdout=open(os.path.join(W, "run.log"), "a"), stderr=subprocess.STDOUT, start_new_session=True)
    print(f"tengo: launched {a['id']} in {W} on {a['kernels']} kernels")


# ----------------------------------------------------------------------------------------------------------------------- commands
def cmd_claim(c, hours, kernels=None, do_launch=False):
    m = C["machine"]; kern = kernels or machine(m)["kernels"]; c = pick(c)
    def change():
        cm = campaign(c); A = allocs(c); now = time.time(); busy = held(A, now); S, K1 = cost(cm, A, m)
        budget = kern * max(hours * 3600 - max(S.values()), 0)   # kernel-seconds, the longest job kept back
        take, tot = [], 0.0
        for pid, P, orders in cm["pumps"]:
            if pid in busy: continue
            if take and tot + K1[pid] > budget: break
            take.append(pid); tot += K1[pid]
        if not take: return None
        aid = f"{m}-{time.strftime('%Y%m%d-%H%M%S')}"
        a = dict(id=aid, campaign=c, machine=m, kernels=kern, hours=hours, created=int(now), deadline=int(now + 1.5 * hours * 3600 + 7200),
                 cost_kernel_h=round(tot / 3600, 1), pumps=take, done=[], times={}, results=[], status="open", tengo=VERSION)
        save(R("allocs", c, aid + ".json"), a); return a
    a = transact(change, lambda a: f"claim {a['id']}: {len(a['pumps'])} pumps of {c}, {a['hours']:g} h on {a['kernels']} kernels")
    if a is None: return print(f"tengo: nothing free in {c}")
    W = setup(a); P = {pid: Pv for pid, Pv, _ in campaign(c)["pumps"]}; xs = sorted(float(P[p]) for p in a["pumps"])
    print(f"tengo: claimed {a['id']}: {len(a['pumps'])} pumps of {c} ({xs[0]:g}-{xs[-1]:g} g, spread in the global order), "
          f"{a['cost_kernel_h']} kernel-h for {hours:g} h on {kern} kernels; deadline {stamp(a['deadline'])}; work directory {W}")
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
        out = []
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
                if new or st != a["status"]:
                    a["status"] = st; a["updated"] = int(time.time()); save(R("allocs", c, a["id"] + ".json"), a)
                    out.append(f"{a['id']}: +{len(new)} pumps ({len(a['done'])}/{len(a['pumps'])} done), {st}")
        return out or None
    out = transact(change, lambda o: "done: " + "; ".join(o))
    print("tengo: " + ("; ".join(out) if out else "nothing new to push"))


def cmd_release(aid=None):
    sync()
    mine = [a for c in campaigns() for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open" and (not aid or a["id"] == aid)]
    if not mine: return print("tengo: no open allocation of this machine")
    for a in mine:
        W = workdir(a)
        if os.path.isdir(W) and any(ours(W)): subprocess.run(["python3", "run_window.py", "--kill"], cwd=W)   # its own jobs only
        elif os.path.isdir(W): open(os.path.join(W, "STOP"), "w").write("released\n")
    for a in mine: cmd_done(a["id"], final="released")


def cmd_status(c=None):
    sync(); now = time.time()
    for c in ([pick(c)] if c else campaigns()):
        cm = campaign(c); A = allocs(c); N = len(cm["pumps"])
        done = set().union(*(set(a["done"]) for a in A)) if A else set(); hold = held(A, now) - done
        _, K1 = cost(cm, A, "azag" if os.path.exists(R("machines", "azag.json")) else C["machine"])
        left = sum(K1[p] for p, _, _ in cm["pumps"] if p not in done) / 3600; b = int(40 * len(done) / N)
        print(f"{c}: [{'#' * b}{'.' * (40 - b)}] {len(done)}/{N} pumps done, {len(hold)} held, {N - len(done) - len(hold)} free; "
              f"{left:.0f} kernel-h left at the reference speed")
        for m in sorted({a["machine"] for a in A}):
            op = [a for a in A if a["machine"] == m and a["status"] == "open"]
            S, Km = cost(cm, A, m); rest = sum(Km[p] for a in op for p in a["pumps"] if p not in set(a["done"]))
            kern = max([a["kernels"] for a in op] or [machine(m)["kernels"]])
            print(f"  {m}: {sum(len(a['done']) for a in A if a['machine'] == m)} pumps done in all; "
                  + (f"holds {sum(len(a['pumps']) - len(a['done']) for a in op)}, {rest / 3600:.0f} kernel-h, end about {stamp(now + rest / kern)}" if op else "holds nothing"))
        for a in sorted(A, key=lambda a: a["created"])[-12:]:
            late = a["status"] == "open" and now > a["deadline"]
            print(f"    {a['id']:24s} {len(a['done']):4d}/{len(a['pumps']):<4d} {a['status']:9s} {a['hours']:g} h x {a['kernels']}, deadline {stamp(a['deadline'])}"
                  + ("  PASSED: its pumps not done are free again" if late else ""))


def tail_state(W):
    """jobs still waiting in the driver of W (from its log) and front-ends running"""
    wait = None
    if os.path.exists(os.path.join(W, "run.log")):
        for l in open(os.path.join(W, "run.log")):
            m = re.search(r"(\d+) jobs to run|(\d+) waiting", l)
            if m: wait = int(m[1] or m[2])
    return wait, len(ours(W)[1])


def cmd_watch(until, hours, c):
    """the unattended loop: claim and launch an allocation while time remains before `until`, push the pumps done every 30 min,
    restart a dead driver (3 times per allocation at most), and claim the next allocation as soon as the current one has launched all
    its jobs, its tail then lending its kernels to the new one (the nproc of the new driver = kernels - jobs of the tail)"""
    end = time.mktime(time.strptime(until, "%Y-%m-%d %H:%M")); restarts = {}; last = 0; c = pick(c)
    print(f"tengo watch until {stamp(end)} ({C['machine']}, {c})", flush=True)
    while True:
        now = time.time()
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
            a = cmd_claim(c, min(hours, (end - now) / 3600), kern)
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
    print(f"tengo: {n} files of {c} in {dest}")


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
    ap = argparse.ArgumentParser(description="Operation Ten-Go: a shared pool of pump jobs in a git repository")
    ap.add_argument("cmd"); ap.add_argument("arg", nargs="?"); ap.add_argument("-c", "--campaign")
    ap.add_argument("--hours", type=float); ap.add_argument("--kernels", type=int); ap.add_argument("--launch", action="store_true")
    ap.add_argument("--alloc"); ap.add_argument("--until"); ap.add_argument("--repo"); ap.add_argument("--work")
    a = ap.parse_args()
    if a.cmd in ("-v", "version"): return print(f"tengo {VERSION}")
    if a.cmd == "init":
        if not (a.arg and a.repo and a.work): die("tengo init MACHINE --repo CLONE --work DIR")
        save(CONF, dict(machine=a.arg, repo=os.path.abspath(os.path.expanduser(a.repo)), work=os.path.abspath(os.path.expanduser(a.work))))
        return print(f"tengo: {CONF} written ({a.arg})")
    try: C.update(json.load(open(CONF)))
    except FileNotFoundError: die(f"no {CONF}: run `tengo init MACHINE --repo CLONE --work DIR` first")
    if a.cmd == "status": cmd_status(a.campaign)
    elif a.cmd == "claim":
        if not a.hours: die("claim --hours H")
        cmd_claim(a.campaign, a.hours, a.kernels, a.launch)
    elif a.cmd == "done": cmd_done(a.alloc)
    elif a.cmd == "release": cmd_release(a.alloc)
    elif a.cmd == "launch":
        sync(); op = [x for c in campaigns() for x in allocs(c) if x["machine"] == C["machine"] and x["status"] == "open" and (not a.alloc or x["id"] == a.alloc)]
        for x in op: launch(x)
        if not op: print("tengo: no open allocation of this machine")
    elif a.cmd == "watch":
        if not a.until: die("watch --until 'YYYY-MM-DD HH:MM'")
        cmd_watch(a.until, a.hours or 10, a.campaign)
    elif a.cmd == "fetch": cmd_fetch(a.campaign, a.arg or ".")
    elif a.cmd == "mkcampaign":
        if a.arg not in CAMPAIGNS: die(f"known campaigns: {', '.join(CAMPAIGNS)}")
        cm = CAMPAIGNS[a.arg](); transact(lambda: save(R("campaigns", a.arg + ".json"), cm) or a.arg, lambda o: f"campaign {o}: {len(cm['pumps'])} pumps")
        print(f"tengo: campaign {a.arg}, {len(cm['pumps'])} pumps")
    else: die(f"unknown command {a.cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
