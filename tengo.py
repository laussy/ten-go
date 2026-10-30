#!/usr/bin/env python3
"""Operation Ten-Go v1.33 (lw page [[Ten-Go]]): several machines share one pool of pump jobs through a GitHub repository (public,
github.com/laussy/ten-go), and no pump is ever computed twice.  A machine asks for a BUDGET, not for pumps: `ten-go --honkai --jikan 10` takes, in one
go, the free pumps of the campaign in its global (van der Corput) order as long as their jobs, run on this machine the longest
first, end within the ten hours (a single pump if the budget is very small).  The claim is a
commit pushed to the repository; a push refused because another machine pushed first is redone from the new state, so that no pump
can be in two allocations.  An allocation has a deadline (its start + 1.5 budget + 2 h, the budget at least its longest job): the pumps it has not done by then go back to
the pool.  The jobs are run by run_window.py (kit/), one work directory per allocation.

Repository (the clone is Ten-Go's alone: every command starts by resetting it to origin/main):
  campaigns/<c>.json   params, file prefix, reference seconds per order, pumps [id, P, orders] in the global order
  machines/<m>.json    kernels, speed factor against the reference
  allocs/<c>/<id>.json one allocation: machine, budget, deadline, pumps, done, measured job times, results, status
  results/<c>/<id>-<n>.tgz   the .dat files of the pumps done, one archive per push
  ledger.tsv           the kernel-hours (kh) spent, per task: one line per allocation (brought up to date by --tassei) or per run log
                       imported (any run of run_window.py, in Ten-Go or not), or booked by hand
  prio/<c>.json        the priorities of the pumps of campaign c, set in --kaizu: rules, the last that matches a pump deciding
The command is `ten-go`, a link to this file on the PATH (ln -s CLONE/tengo.py ~/bin/ten-go).  Local: ~/.config/tengo.json {"machine", "repo", "work"} (written by `ten-go --kido`; env TENGO_CONF names another file).

--until TAG, an AF tag (read back by ~/bin/AF, lw page [[AF]]) or 'YYYY-MM-DD HH:MM', is the time of a claim or a watch: --honkai
takes the hours from now until then in place of --jikan.  Given both --jikan and --until, --honkai only prints itself again, its
--jikan set to those hours and --until dropped, with the kernel-hours (kh) they make as a comment.

The time given (--jikan, --until) is a plan, not an end: an allocation runs its pumps the longest first (within a priority, each one's
jobs the longest first) so that its time is met, the smallest last; past its time it goes on, but as a sortie, in prevision of an
imminent uchikiri: the pumps started are completed first, then those not started run the cheapest first, whole.  A watch past its
--until goes on likewise, with sorties (claims as --shugeki: the cheapest pumps first), from half an hour before, until the campaign
is complete or an uchikiri by hand.  --kikan (帰還, the return to base) ends at the time instead: an allocation (--honkai --kikan) then
ends without loss (its driver makes its own uchikiri: the pumps started complete, the others go back to the pool), and a watch (watch
--until TAG --kikan) claims nothing in the last half hour, its allocations ending without loss at TAG.

--shinshu [N] (--honkai, launch, watch) lets the allocation take the threads that stay idle, from its kernels up to N (no N: every
thread of the machine), and give them back as soon as other work wants them: the driver looks every minute (kit/run_window.py), one
kernel more after 10 minutes of threads free of any other work, back toward the allocation's kernels after 2 minutes of activity; a
kernel above them runs the shortest job waiting, so that the retreat is quick.  The budget is unchanged: shinshu only ends it sooner.

--gensoku N (減速) lowers this machine to N kernels for Ten-Go, its allocations together, from now until --zensoku (with --jikan H, for
H hours): a job that ends is not replaced while N or more run (none is killed), the claims are made for N kernels, and no idle thread
is borrowed (shinshu).  --zensoku [H] (全速) gives the kernels back one at a time over H hours (1; 0: at once), as the end of a
--gensoku --jikan does over an hour.  It is this machine's own (gensoku.json in its work directory, no commit), kept by its watch, and
said by --senkyo and its kaizu; when it is set, it says when the open allocations will end, and which would miss their deadline.

ten-go --uchikiri ends this machine's allocations as soon as possible without loss: each driver launches
no new pump and completes those started (a job done or in flight), and says when it will end, and what a STOP or a kill would waste
instead; the pumps not started go back to the pool at once, a watch of the machine claims nothing more, and the driver pushes the last
results when it ends.  With --dry, it only says when.
ten-go --chushi [MIN] stops them now (there is no other stop), but a job within MIN minutes of completion (10) is first offered to wait
for: "One job is 3 min from completion; the next are 17 min, 2 h 20, 6 h away, so those are aborted. Abort this one too [n]ow, or
[a]fter it completes?"  --now or --wait answers ahead (without a terminal, one of them is needed), --dry only asks.  The pumps not
complete go back to the pool at once, and those the jobs waited for complete are pushed when they end.

--shugeki (with --honkai or watch) is a sortie, for a machine that may be stopped any moment: it claims the cheapest pumps first
(their cost on this machine, the global order among equals) and its driver runs them whole, one after the other (no shortest job
taken ahead for a kernel above the allocation's), so that an uchikiri ends within a job or two and a chushi wastes little.

--sensen SPEC.json declares a campaign from a spec file (see declare): a grid, whose pumps already computed in the runs it names are
left out, or an adaptive campaign, whose pumps grow at each claim by the rule of adaptwin.py (kit/tengo_adaptive.py) applied to the results
in the pool, seeded with the pumps of the runs it names (they go to the pool as the results of an allocation "seed").  Short claims
suit an adaptive campaign: it is refined only when a claim is made.  A campaign in parts (kind parts) joins several, each with its own
file prefix and kind, its pumps numbered from its own base; a claim takes from the parts in their order (an adaptive part first, say,
the next parts filling what it cannot).  watch without --until runs until the campaign is complete.  --zoen SPEC.json (増援,
reinforcements) adds the parts of SPEC to the campaign it names, while it runs: new pump numbers (nothing claimed changes), the same
parameters, at the end or before the part "before" (an index); the watches take them up at their next claim.  --kaiso SPEC.json (改装,
a refit) changes the orders of the pumps of a part that no allocation holds (open, past its deadline or not) and none has done, by
the map of SPEC ({"name": campaign, "part": prefix, "orders": {"300e": "300e80", ...}}): to a higher precision, say, while it runs;
the pumps held or done keep theirs.  --dry only says what would change.

--kaizu [PORT] (海図, the sea chart) serves on this machine alone a page (http://127.0.0.1:1945/; kit/tengo_kaizu.py, kaizu.html) that
draws the campaign as the pieces of a torrent, each pump as wide as its estimated time: done, held (paler; what this machine is
computing in a sharp shade of its colour, as far as it has gone), free; in the order of the campaign or of g, with its parts, the
priorities, the machines and the next claim each would make, the dates with their AF tags (~/bin/AF).  A drag over the pieces, the
pieces picked by a click (hpT #1951, #1949, #1947...), or a part of the list, is given a priority, now, high, normal, low or skip
(never claimed): a rule of prio/<c>.json, pushed like a claim.  The pieces picked can also be named, a sub-campaign of the campaign:
a rule with a name, listed with the parts, whose priority is raised or lowered there (it then decides again, as the last rule).  A
claim takes the free pumps now first, then high, normal, low, each in the order of the campaign (--shugeki: the cheapest first); the
watches take normal, low and skip up at their next claim (what is claimed already runs on), and now and high at once (press): a watch
claims the pumps of that level alone, and its allocations still launching pumps of a lower level end without loss (an uchikiri: the
pumps started complete, the others go back to the pool).  The pumps of high then take the kernels as that uchikiri frees them; those
of now take them at once, the jobs of the other allocations being paused (SIGSTOP to the job, its kernel waiting in memory where it
stands: nothing is lost, as many as the memory holds) and resumed, the nearest to completion first, as the kernels come back, their
paused time left out of the job times (paused.tsv); their deadlines are pushed back by the span of the claim of now.  An uchikiri or a
chushi by hand resumes the jobs paused first.  A kaizu already on the port is stopped first (it ends the push it may be in), and its
pages reload into the new one.

A kh is one kernel for one hour: the jobs' own times summed, a failed job's included (an adopted job's time, unknown, is not).  The
ledger keeps what each task cost: `ten-go kh` shows the totals per task and machine, `ten-go kh TASK` the lines of a task.

Usage: ten-go --kido MACHINE --repo CLONE --work DIR | --senkyo [--sakusen C] | --honkai --jikan H|--until TAG [--sakusen C] [--ki N] [--go] [--shinshu [N]] [--shugeki] [--kikan]
       | --tassei [--alloc ID] | --uchikiri [--dry] [--alloc ID] | --chushi [MIN] [--now|--wait|--dry] [--alloc ID] | launch [--alloc ID] [--shinshu [N]] | watch [--until TAG [--kikan]] [--jikan 10] [--sakusen C] [--shinshu [N]] [--shugeki]
       | --shushu [DIR] [--sakusen C] (unpack every result into DIR) | --sensen NAME|SPEC.json (declare a campaign) | --zoen SPEC.json (add parts to one) | --kaiso SPEC.json [--dry] (refit a part)
       | --kaizu [PORT] [--sakusen C] (the sea chart, a page on this machine) | --gensoku N [--jikan H] (fewer kernels) | --zensoku [H] (all back)
       | kh [TASK] | kh import DIR [TASK] [--machine M] [--note TEXT] | kh add TASK KH [--machine M] [--note TEXT]"""
import argparse, fcntl, glob, heapq, json, os, random, re, shlex, shutil, signal, subprocess, sys, tarfile, time
from contextlib import contextmanager
from fractions import Fraction
VERSION = "1.33"   # 1.1: claim --go (was --launch) starts the driver; 1.2: the command is ten-go (a link to this file); 1.3: --until TAG; 1.4: kh, the ledger; 1.5: --shinshu; 1.6: --uchikiri; 1.7: --chushi; 1.8: claim is --honkai, release is gone (--chushi); 1.9: --kernels is --ki; 1.10: --campaign (-c) is --sakusen; 1.11: init is --kido, --hours is --jikan; 1.12: status is --senkyo, done --tassei; 1.13: fetch is --shushu; 1.14: --shugeki; 1.15: mkcampaign is --sensen; 1.16: spec files, adaptive campaigns; 1.17: campaigns in parts, watch to completion; 1.18: launch without the sleep inhibitor where refused (ssh); 1.19: --zoen; 1.20: --zoen brings reference times for new orders; 1.21: a deadline past the longest job, the watch goes on in a new version; 1.22: an allocation whose jobs have all started is not still launching; 1.23: the watch outlives a failed git (the network gone); 1.24: --kaiso; 1.25: the clone locked (a watch and a command by hand lost each other's commits); 1.26: --kaizu, the sea chart, and the priorities it sets (prio/<c>.json); 1.27: the kaizu's logo, the blocks run in their machine's colour (azag reddish, yzao purplish), the dates with their AF tags; 1.28: the kaizu's logo small (200 px under the pointer), what is being computed in a sharp shade of its machine's colour (no more red and purple); 1.29: --kaizu stops a kaizu already on its port, and the pages of the old one reload into the new; 1.30: --gensoku N, --zensoku [H] (the watch kept all the kernels of machines/<m>.json: a lower nproc set by hand was undone within a minute); 1.31: the kaizu's pieces picked by a click, its sub-campaigns (pumps picked, named), the level now, and now and high claimed at once by the watches (high: their allocations end without loss, these take the kernels as they free; now: the jobs of the others paused meanwhile); 1.32: a job paused only for a claim of now waiting for kernels (a machine one job over its kernels, as a fresh claim makes it, paused the newest job for a minute); 1.33: the time a plan, not an end (an allocation runs the longest pumps first and, past its time, the rest as a sortie; a watch past its --until goes on with sorties), --kikan to end at the time, and a claim filled up to its time by that order (no longer the longest job kept back)
CONF = os.environ.get("TENGO_CONF", os.path.expanduser("~/.config/tengo.json"))   # another file for a test identity
C = {}


def die(msg): sys.exit(f"ten-go: {msg}")
def R(*p): return os.path.join(C["repo"], *p)
def stamp(t): return time.strftime("%a %d %b %H:%M", time.localtime(t))
def hm(x): m = round(x / 60); return f"{m} min" if m < 60 else f"{m // 60} h" + (f" {m % 60:02d}" if m % 60 else "")   # 3 min, 2 h 20, 6 h


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
    """the command line as typed, its --jikan set to h and --until dropped (an option as is or with =; no abbreviations)"""
    out, args = ["ten-go"], iter(sys.argv[1:])
    for x in args:
        k = x.split("=", 1)[0]
        if k == "--jikan": out += ["--jikan", f"{h:g}"]
        elif k == "--until": pass
        else: out.append(x); continue
        if "=" not in x: next(args, None)
    return " ".join(map(shlex.quote, out))


def git(*a, check=True):
    r = subprocess.run(["git", "-C", C["repo"], *a], capture_output=True, text=True)
    if check and r.returncode: die(f"git {' '.join(a)} failed:\n{r.stderr.strip()}")
    return r


HOLD = [0, None]
@contextmanager
def clone():
    """the clone to this process alone, re-entrant: a watch and a command run by hand share it, and the reset of one between the
    commit and the push of the other lost that commit (the push then said up to date and the command reported it done)"""
    if not HOLD[0]: HOLD[1] = open(os.path.join(C["repo"], ".git", "tengo.lock"), "w"); fcntl.flock(HOLD[1], fcntl.LOCK_EX)
    HOLD[0] += 1
    try: yield
    finally:
        HOLD[0] -= 1
        if not HOLD[0]: HOLD[1].close()


def sync():
    with clone(): git("fetch", "-q", "origin"); git("reset", "-q", "--hard", "origin/main")


def transact(change, msg):
    """apply `change` to the fresh state of the repository (it returns what it did, or None when there is nothing to do) and push; a
    refused push (another machine pushed first) is redone from the new state, so that a claim is recomputed from what is still free"""
    for attempt in range(10):
        with clone():
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
def dec(x):   # an exact pump as a decimal, exact on these lattices (else a/b, which hp3.wls reads as well)
    x = Fraction(x)
    for n in range(31):
        if (x * 10 ** n).denominator == 1:
            d = str(abs(x.numerator * 10 ** n // x.denominator)).rjust(n + 1, "0"); return ("-" if x < 0 else "") + (d[:-n] + "." + d[-n:] if n else d)
    return f"{x.numerator}/{x.denominator}"
def upto(v): return "every thread" if v == "max" else f"{v} kernels"
def ceiling(v, kern):   # --shinshu: None, max (every thread of the machine), or a number of kernels above kern
    if v in (None, "max"): return v
    try: n = int(v)
    except ValueError: die(f"--shinshu {v}: a number of kernels, or nothing for every thread of the machine")
    return n if n > kern else die(f"--shinshu {n}: not above the {kern} kernels of the allocation")
def parts(cm):   # the parts of a campaign, each {kind, prefix, base[, rule]}; a campaign of one kind is its own single part
    return cm.get("parts") or [dict(kind=cm.get("kind", "grid"), prefix=cm["prefix"], base=0, rule=cm.get("rule"))]
def part(cm, pid): return max((q for q in parts(cm) if pid >= q["base"]), key=lambda q: q["base"])
def pre(cm, pid): return part(cm, pid)["prefix"]   # the file prefix of a pump
def tilde(p): h = os.path.expanduser("~"); return "~" + p[len(h):] if p.startswith(h + "/") else p


LEDGER = ["task", "machine", "source", "jobs", "failed", "kh", "first", "last", "note"]   # first and last job done


def ledger(): return [dict(zip(LEDGER, l.rstrip("\n").split("\t"))) for l in open(R("ledger.tsv")).readlines()[1:]] if os.path.exists(R("ledger.tsv")) else []


def save_ledger(L):
    with open(R("ledger.tsv"), "w") as f:
        f.write("\t".join(LEDGER) + "\n")   # a header GitHub shows as a table
        for e in sorted(L, key=lambda e: (e["first"], e["source"])): f.write("\t".join(str(e[k]) for k in LEDGER) + "\n")


def logspent(W):
    """jobs, failed jobs and kernel-seconds of the jobs a run.log of run_window.py reports done (the time they were paused left out),
    and when the first and the last of them ended (the times of their files: the log has no dates)"""
    n = bad = sec = 0; f = os.path.join(W, "run.log"); T = []; PZ = pauses(W)
    for l in (open(f) if os.path.exists(f) else []):
        m = re.search(r" done (\S+) j=(\d+) P=\S+ in (\d+) s", l)
        if not m: continue
        n += 1; sec += max(int(m[3]) - round(PZ.get((m[1], m[2]), 0)), 0); bad += "NO FILE" in l; d = os.path.join(W, f"{m[1]}_{m[2]}.dat")
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
    die(f"say which campaign with --sakusen ({', '.join(cs)})")


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


LEVELS = ("now", "high", "normal", "low", "skip")   # the priorities set in --kaizu, in the order the claims take them (skip: never)
PRESS = ("now", "high")   # the levels a watch claims for at once, ending its allocations without loss (now: pausing their jobs too)


def prio(c): f = R("prio", c + ".json"); return json.load(open(f))["rules"] if os.path.exists(f) else []


def matcher(cm, r):   # does the rule r ({level, and part, g: [lo, hi] or pumps: [ids]; a sub-campaign: a name}) hold for the pump p ([id, P, orders])
    ids = set(r.get("pumps", [])); lo, hi = (Fraction(r["g"][0]), Fraction(r["g"][1])) if "g" in r else (None, None)
    return lambda p: ("part" not in r or pre(cm, p[0]) == r["part"]) and ("pumps" not in r or p[0] in ids) and (lo is None or lo <= Fraction(p[1]) <= hi)


def level(c, cm):
    """the priority of a pump by the rules of prio/<c>.json, the last that matches deciding: p -> (level, index of the rule; normal,
    None when none does)"""
    M = [(r["level"], matcher(cm, r)) for r in prio(c)]
    def f(p):
        for k in range(len(M) - 1, -1, -1):
            if M[k][1](p): return M[k][0], k
        return "normal", None
    return f


def sequence(take, O, S, K1, L, shugeki=False):
    """the order the driver runs the pumps `take` in (their orders O, seconds per order S, cost K1, priority L): by priority, the
    longest pump first within one (shugeki: as taken, the cheapest first), each pump's jobs the longest first (shugeki: as listed)"""
    if shugeki: return [(p, list(O[p])) for p in take]
    return [(p, sorted(O[p], key=lambda o: -S[o])) for p in sorted(take, key=lambda p: (L[p], -K1[p]))]


def span(seq, S, kern):   # the end of the jobs of seq (from sequence) launched in that order on kern kernels, each as one frees (seconds)
    free = [0.0] * max(kern, 1)
    for _, orders in seq:
        for o in orders: heapq.heapreplace(free, free[0] + S[o])
    return max(free)


def choose(c, cm, A, m, kern, hours, pumps, busy, shugeki=False, only=None):
    """the pumps a claim of `hours` on `kern` kernels of machine m takes from `pumps`: those not busy, by their priority (now, high,
    normal, low; skip never; only: those of that level alone), within one priority in their order (shugeki: the cheapest first), as
    long as the jobs taken, run the longest first (sequence), end within the hours (a single pump if it is longer); returns them, their
    cost (kernel-seconds) and their longest job"""
    S, K1 = cost(cm, A, m); lv = level(c, cm); L = {p[0]: LEVELS.index(lv(p)[0]) for p in pumps}; O = {p[0]: p[2] for p in pumps}
    order = sorted(pumps, key=lambda x: K1[x[0]]) if shugeki else pumps   # shugeki: the cheapest first
    take, tot, hold = [], 0.0, 0   # their cost in kernel-seconds, their longest job
    ok = (lambda k: k == LEVELS.index(only)) if only else (lambda k: k < LEVELS.index("skip"))
    for pid, P, orders in sorted((p for p in order if ok(L[p[0]])), key=lambda p: L[p[0]]):   # stable: the order within a priority kept
        if pid in busy: continue
        h = max(hold, *(S[o] for o in orders))   # within kern (hours - h) kernel-hours, any order of launch ends in time: no need to look
        if take and tot + K1[pid] > kern * (hours * 3600 - h) and span(sequence(take + [pid], O, S, K1, L, shugeki), S, kern) > hours * 3600: break
        take.append(pid); tot += K1[pid]; hold = h
    return take, tot, hold


# ----------------------------------------------------------------------------------------------------------------- the work directory
def setup(a):
    cm = campaign(a["campaign"]); W = workdir(a); os.makedirs(W, exist_ok=True)
    for f in ("hp3.wls", "run_window.py"): shutil.copy(R("kit", f), W)
    P = {pid: (Pv, orders) for pid, Pv, orders in cm["pumps"]}
    open(os.path.join(W, "pumps.txt"), "w").write("".join(f"{pid} {P[pid][0]}\n" for pid in a["pumps"]))
    open(os.path.join(W, "params.txt"), "w").write("".join(f"{k}={v}\n" for k, v in cm["params"].items()))
    open(os.path.join(W, "nproc"), "w").write(f"{a['kernels']}\n")
    if a.get("shinshu"): open(os.path.join(W, "shinshu"), "w").write(f"{a['shinshu']}\n")   # read by the driver every minute
    if a.get("shugeki"): open(os.path.join(W, "shugeki"), "w").write("whole pumps, in the plan's order\n")
    open(os.path.join(W, "jikan"), "w").write(f"{int(a['created'] + a['hours'] * 3600)}\n")   # its time: past it, the pumps left the cheapest first
    if a.get("kikan"): open(os.path.join(W, "kikan"), "w").write(f"{a['kikan']}\n"); atend(a, W)   # then it ends without loss (--kikan)
    S, K1 = cost(cm, allocs(a["campaign"]), a["machine"]); lv = level(a["campaign"], cm); L = {p[0]: LEVELS.index(lv(p)[0]) for p in cm["pumps"]}
    with open(os.path.join(W, "plan.txt"), "w") as f:
        f.write(f"# prefix nt withWeights j [prec]   (Ten-Go allocation {a['id']} of {a['campaign']}: {len(a['pumps'])} pumps, "
                + ("the cheapest first, a sortie)\n" if a.get("shugeki") else "the longest first within a priority, each one's jobs the longest first)\n"))
        for pid, orders in sequence(a["pumps"], {p: P[p][1] for p in a["pumps"]}, S, K1, L, a.get("shugeki")):
            for o in orders:
                nt, w, prec = parse(o); f.write(f"{pre(cm, pid)}_nt{o} {nt} {w} {pid}" + (f" {prec}" if prec else "") + "\n")
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


def jobs(W):
    """the jobs running in W: {pid of the front-end: (prefix, pump, paused)}, paused: stopped by a watch (SIGSTOP) for the kaizu's
    pumps of level now"""
    out = {}
    for pid in ours(W)[1]:
        try: cmd = open(f"/proc/{pid}/cmdline").read().split("\0"); st = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        except OSError: continue
        k = cmd.index("hp3.wls")
        if len(cmd) > k + 7: out[pid] = (cmd[k + 5], cmd[k + 7].split(":")[0], st[0] == "T")
    return out


def kids():   # {pid: its children}, from one look at /proc
    out = {}
    for d in filter(str.isdigit, os.listdir("/proc")):
        try: out.setdefault(int(open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()[1]), []).append(int(d))
        except (OSError, IndexError, ValueError): pass
    return out


def tree(pid, K=None):   # pid and all its descendants, parents first (a job: its front-end wolframscript, a sh, the WolframKernel)
    K = K or kids(); out, todo = [], [pid]
    while todo: q = todo.pop(0); out.append(q); todo += K.get(q, [])
    return out


def elapsed(pid):   # seconds since the process started
    try: return float(open("/proc/uptime").read().split()[0]) - int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[19]) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError): return 0.0


def paused(W):   # the jobs of W paused now: {pid: {t: since, pre: prefix, j: pump}} (paused.json)
    try: return json.load(open(os.path.join(W, "paused.json")))
    except (OSError, ValueError): return {}


def pauses(W):   # {(prefix, pump): seconds paused} of the jobs of W, the pauses ended (paused.tsv) and those going on
    out = {}; now = time.time()
    try:
        for l in open(os.path.join(W, "paused.tsv")):
            x = l.split()
            if len(x) == 3: out[x[0], x[1]] = out.get((x[0], x[1]), 0) + float(x[2])
    except OSError: pass
    for v in paused(W).values(): out[v["pre"], v["j"]] = out.get((v["pre"], v["j"]), 0) + now - v["t"]
    return out


def freeze(W, pids, why):
    """pause these jobs of W (their front-ends' pids): SIGSTOP to the front-end, its sh and its kernel, parents first; nothing is
    lost, the kernel waits in memory where it stands"""
    P = paused(W); J = jobs(W); now = time.time(); n = 0
    for pid in pids:
        if pid not in J or J[pid][2]: continue
        for q in tree(pid):
            try: os.kill(q, signal.SIGSTOP)
            except OSError: pass
        P[str(pid)] = dict(t=now, pre=J[pid][0], j=J[pid][1]); n += 1
        open(os.path.join(W, "run.log"), "a").write(f"{time.strftime('%H:%M:%S')} paused {J[pid][0]} j={J[pid][1]} ({why})\n")
    save(os.path.join(W, "paused.json"), P); return n


def thaw(W, pids=None):
    """resume the jobs of W paused (pids None: all of them, and any stopped otherwise), children first; the length of each pause goes
    to paused.tsv, so that the job's time leaves it out; how many"""
    P = paused(W); now = time.time(); n = 0; J = jobs(W)
    todo = [int(k) for k in P] if pids is None else [p for p in pids if str(p) in P]
    if pids is None: todo += [p for p, v in J.items() if v[2] and str(p) not in P]
    for pid in todo:
        for q in reversed(tree(pid)):
            try: os.kill(q, signal.SIGCONT)
            except OSError: pass
        v = P.pop(str(pid), None)
        if v:
            open(os.path.join(W, "paused.tsv"), "a").write(f"{v['pre']}\t{v['j']}\t{now - v['t']:.0f}\n")
            open(os.path.join(W, "run.log"), "a").write(f"{time.strftime('%H:%M:%S')} resumed {v['pre']} j={v['j']} after {hm(now - v['t'])}\n")
        n += 1
    for k in [k for k in P if int(k) not in J]:   # a job paused that is gone (killed): its pause ends with it
        v = P.pop(k); open(os.path.join(W, "paused.tsv"), "a").write(f"{v['pre']}\t{v['j']}\t{now - v['t']:.0f}\n")
    if os.path.exists(os.path.join(W, "paused.json")): save(os.path.join(W, "paused.json"), P)
    return n


def inhibitor(a):
    """systemd-inhibit, to keep the machine awake while the driver runs: sleep and idle where the session may block them, idle alone
    where sleep needs an interactive authentication (an ssh session), else nothing"""
    if not shutil.which("systemd-inhibit"): return []
    for what in ("sleep:idle", "idle"):
        if subprocess.run(["systemd-inhibit", f"--what={what}", "--why=Ten-Go test", "true"], capture_output=True).returncode == 0:
            return ["systemd-inhibit", f"--what={what}", f"--why=Ten-Go {a['id']}"]
    return []


def launch(a, quiet=False, shinshu=None):
    W = workdir(a)
    if not os.path.isdir(W): setup(a)
    if shinshu: open(os.path.join(W, "shinshu"), "w").write(f"{ceiling(shinshu, a['kernels'])}\n")
    if ours(W)[0]: return quiet or print(f"ten-go: the driver of {a['id']} is already running")
    if os.path.exists(os.path.join(W, "STOP")): die(f"{W}/STOP exists (released or stopped by hand): remove it to run again")
    for f in glob.glob(os.path.join(W, "*.dat")):
        if os.path.getsize(f) < 1000: os.remove(f)   # the leftover of a killed job
    cmd = inhibitor(a) + ["python3", "run_window.py"]
    subprocess.Popen(cmd, cwd=W, stdin=subprocess.DEVNULL, stdout=open(os.path.join(W, "run.log"), "a"), stderr=subprocess.STDOUT, start_new_session=True)
    sh = open(os.path.join(W, "shinshu")).read().strip() if os.path.exists(os.path.join(W, "shinshu")) else ""
    print(f"ten-go: launched {a['id']} in {W} on {a['kernels']} kernels" + (f", shinshu up to {upto(sh)}" if sh else ""))


# ----------------------------------------------------------------------------------------------------------------------- commands
def cmd_claim(c, hours, kernels=None, do_launch=False, shinshu=None, shugeki=False, quiet=False, only=None, kikan=None):
    m = C["machine"]; kern = kernels or kernels_now(); c = pick(c); sh = ceiling(shinshu, kern)
    def change():
        cm = campaign(c); A = allocs(c); now = time.time(); busy = held(A, now); pumps, grew = cm["pumps"], None
        if any(q["kind"] == "adaptive" for q in parts(cm)) and not only: pumps, grew = grown(c, cm, A, busy, kern)   # the rule, now: new pumps appended
        take, tot, hold = choose(c, cm, A, m, kern, hours, pumps, busy, shugeki, only)
        if not take: return None
        aid = base = f"{m}-{time.strftime('%Y%m%d-%H%M%S')}"; k = 1
        while os.path.exists(R("allocs", c, aid + ".json")): k += 1; aid = f"{base}-{k}"   # two claims in the same second
        a = dict(id=aid, campaign=c, machine=m, kernels=kern, hours=hours, created=int(now), deadline=int(now + 1.5 * max(hours * 3600, hold) + 7200),   # a job longer than the claim keeps it
                 cost_kernel_h=round(tot / 3600, 1), pumps=take, done=[], times={}, results=[], status="open", tengo=VERSION, shinshu=sh, shugeki=shugeki)
        if only: a["prio"] = only   # a claim of the kaizu's now or high pumps alone, made at once by a watch
        if kikan: a["kikan"] = int(kikan if kikan is not True else now + hours * 3600)   # it ends without loss then (--kikan: its time, or the watch's)
        if grew: a["grown"], a["open"] = grew; save(R("campaigns", c + ".json"), cm)   # the new pumps, in the claim's commit
        save(R("allocs", c, aid + ".json"), a); return a
    a = transact(change, lambda a: f"honkai {a['id']}: {len(a['pumps'])} {a.get('prio', '')} pumps of {c}, {a['hours']:g} h on {a['kernels']} kernels".replace("  ", " "))
    if a is None: return None if quiet else print(f"ten-go: nothing free in {c}")
    W = setup(a); P = {pid: Pv for pid, Pv, _ in campaign(c)["pumps"]}; xs = sorted(float(Fraction(P[p])) for p in a["pumps"])
    print(f"ten-go: claimed {a['id']}: {len(a['pumps'])} pumps of {c} ({xs[0]:g}-{xs[-1]:g} g, {f"{a['grown']} new by the rule, {a['open']} intervals to split now" if "grown" in a else f"the {only} pumps of the kaizu" if only else 'the cheapest first, a sortie' if shugeki else 'by the priorities of the kaizu' if prio(c) else 'spread in the global order'}), "
          f"{a['cost_kernel_h']} kh for {hours:g} h on {kern} kernels; deadline {stamp(a['deadline'])}; work directory {W}"
          + (f"; shinshu up to {upto(sh)}" if sh else "") + (f"; it ends without loss at {stamp(a['kikan'])} (kikan)" if a.get("kikan") else ""))
    if do_launch: launch(a)
    return a


def complete(a, cm):
    W = workdir(a); O = {pid: orders for pid, _, orders in cm["pumps"]}
    ok = lambda f: os.path.exists(f) and os.path.getsize(f) > 1000
    return [p for p in a["pumps"] if all(ok(os.path.join(W, f"{pre(cm, p)}_nt{o}_{p}.dat")) for o in O[p])]


def jobtimes(W, prefix, pids):   # the times of the jobs done, without the time they were paused
    out = {}; PZ = pauses(W)
    if os.path.exists(os.path.join(W, "run.log")):
        for l in open(os.path.join(W, "run.log")):
            m = re.search(rf"done {re.escape(prefix)}_nt(\w+) j=(\d+) P=\S+ in (\d+) s", l)
            if m and int(m[2]) in pids and "NO FILE" not in l: out.setdefault(m[1], []).append(max(int(m[3]) - round(PZ.get((f"{prefix}_nt{m[1]}", m[2]), 0)), 0))
    return out


def cmd_done(aid=None, final=None):
    """push the pumps finished since the last push (their files as one archive), their job times, and the status of the allocation (the
    pumps of one ended at its time by its driver, not started, given back first: kikan without a watch)"""
    for a in mine(aid): back(a)
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
                            for o in O[p]: n = f"{pre(cm, p)}_nt{o}_{p}.dat"; t.add(os.path.join(W, n), arcname=n)
                    a["results"].append(rel); a["done"] += new
                    for px in {pre(cm, p) for p in new}:
                        for o, v in jobtimes(W, px, {p for p in new if pre(cm, p) == px}).items(): a["times"].setdefault(o, []).extend(v)
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


def ending(): open(os.path.join(C["work"], "ENDING"), "w").write(f"{int(time.time())}\n")   # a watch of this machine claims no more
def knows(W, opt): return opt in open(os.path.join(W, "run_window.py")).read()   # an older driver would take it for a plain run


def atend(a, W):   # the driver of a pushes its last results when it ends
    open(os.path.join(W, "atend"), "w").write(shlex.join(["env", f"TENGO_CONF={CONF}", sys.executable, os.path.realpath(__file__), "--tassei", "--alloc", a["id"]]) + "\n")


def shrink(a, kept, why):
    """give back to the pool at once the pumps of allocation a not in kept (those its driver no longer completes); how many"""
    def change():
        x = json.load(open(R("allocs", a["campaign"], a["id"] + ".json")))
        back = [p for p in x["pumps"] if str(p) not in kept and p not in x["done"]]
        if x["status"] != "open" or not back: return None
        x["pumps"] = [p for p in x["pumps"] if p not in back]; x[why] = int(time.time()); save(R("allocs", a["campaign"], a["id"] + ".json"), x)
        return len(back)
    return transact(change, lambda n: f"{why} {a['id']}: {n} pumps back to the pool") or 0


def back(a):
    """allocation a ended by its driver at its time (kikan: an uchikiri of its own, the pumps it completes in uchikiri.kept), the pool
    not told yet: its pumps not started go back at once; how many"""
    f = os.path.join(workdir(a), "uchikiri.kept")
    if a.get("uchikiri") or not os.path.exists(f): return 0
    kept = set(open(f).read().split())
    return shrink(a, kept, "uchikiri") if any(str(p) not in kept and p not in a["done"] for p in a["pumps"]) else 0


def mine(aid): return [a for c in campaigns() for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open" and (not aid or a["id"] == aid)]


def uchikiri(a, dry=False):
    """end allocation a as soon as possible without loss (run_window.py --uchikiri, which says when): its pumps not started go back to
    the pool at once, and the driver pushes the last results when it ends (its file atend); what happened, in words"""
    W = workdir(a)
    if not (os.path.isdir(W) and ours(W)[0]): return f"{a['id']}: no driver running (`ten-go --chushi` gives its pumps back)"
    if not knows(W, "--uchikiri"): return f"{a['id']}: its driver predates uchikiri (`ten-go --chushi` stops it)"
    if not dry: atend(a, W)
    r = subprocess.run(["python3", "run_window.py", "--uchikiri"] + (["--dry"] if dry else []), cwd=W, capture_output=True, text=True)
    say = (r.stdout + r.stderr).strip()
    if dry or r.returncode: return f"{a['id']}: {say}"
    n = shrink(a, set(open(os.path.join(W, "uchikiri.kept")).read().split()), "uchikiri")   # the pumps started, as the driver saw them
    return f"{a['id']}: {n} pumps back to the pool at once; {say}; the driver pushes the last results when it ends"


def cmd_uchikiri(aid=None, dry=False):
    """end this machine's open allocations as soon as possible without loss (uchikiri), its watch claiming no more; the jobs a watch
    paused for the kaizu's pumps of level now resume first"""
    sync(); M = mine(aid)
    if not M: return print("ten-go: no open allocation of this machine")
    if not dry: ending()
    for a in M:
        if not dry and os.path.isdir(workdir(a)) and (n := thaw(workdir(a))): print(f"ten-go: {a['id']}: {n} jobs paused resumed")
        print(f"ten-go: {uchikiri(a, dry)}")


def cmd_chushi(aid=None, soon=10, how=None):
    """stop this machine's open allocations now (run_window.py --chushi), a job within `soon` minutes of completion being first offered
    to wait for (how: now, wait or dry answers ahead); the pumps not complete go back to the pool at once, and those the jobs waited for
    complete are pushed when they end"""
    sync(); M = mine(aid)
    if not M: return print("ten-go: no open allocation of this machine")
    if how != "dry": ending()
    for a in M:
        W = workdir(a); run = os.path.isdir(W) and any(ours(W))
        if run and how != "dry" and (n := thaw(W)): print(f"ten-go: {a['id']}: {n} jobs paused resumed (a job paused would never end)")
        print(f"ten-go: {a['id']}:", flush=True)
        if run and not knows(W, "--chushi"):   # an older driver: stopped at once, without the warning
            if how == "dry": print("its driver predates chushi: it would be stopped at once"); continue
            subprocess.run(["python3", "run_window.py", "--kill"], cwd=W); cmd_done(a["id"], final="released"); continue
        if how == "dry":
            if run: subprocess.run(["python3", "run_window.py", "--chushi", "--soon", f"{soon:g}", "--dry"], cwd=W)
            else: print("no job running")
            continue
        if run and subprocess.run(["python3", "run_window.py", "--chushi", "--soon", f"{soon:g}"] + ([f"--{how}"] if how else []), cwd=W).returncode: continue
        if os.path.isdir(W) and ours(W)[0]:   # its driver waits for the jobs about to complete
            atend(a, W); n = shrink(a, set(open(os.path.join(W, "chushi.kept")).read().split()), "chushi")
            print(f"ten-go: {a['id']}: {n} pumps back to the pool at once; the driver pushes the last results when its jobs end")
        else: cmd_done(a["id"], final="released")


def cmd_status(c=None):
    sync(); now = time.time()
    for c in ([pick(c)] if c else campaigns()):
        cm = campaign(c); A = allocs(c); N = len(cm["pumps"])
        done = set().union(*(set(a["done"]) for a in A)) if A else set(); hold = held(A, now) - done
        _, K1 = cost(cm, A, "azag" if os.path.exists(R("machines", "azag.json")) else C["machine"])
        left = sum(K1[p] for p, _, _ in cm["pumps"] if p not in done) / 3600; b = int(40 * len(done) / N)
        print(f"{c}: [{'#' * b}{'.' * (40 - b)}] {len(done)}/{N} pumps done, {len(hold)} held, {N - len(done) - len(hold)} free; "
              f"{left:.0f} kh left at the reference speed; {sum(float(e['kh']) for e in ledger() if e['task'] == c):.1f} kh spent")
        if prio(c):
            lv = level(c, cm); out = held(A, now); n = {L: sum(lv(p)[0] == L for p in cm["pumps"] if p[0] not in out) for L in LEVELS}
            subs = [r["name"] for r in prio(c) if r.get("name")]
            print(f"  priorities (--kaizu, prio/{c}.json): {len(prio(c))} rules" + (f" ({len(subs)} sub-campaigns: {', '.join(subs)})" if subs else "")
                  + f"; of the free pumps {n['now']} now, {n['high']} high, {n['normal']} normal, {n['low']} low, {n['skip']} skipped")
        for m in sorted({a["machine"] for a in A}):
            if m == "seed": print(f"  seed: {sum(len(a['done']) for a in A if a['machine'] == m)} pumps from the runs before Ten-Go"); continue
            op = [a for a in A if a["machine"] == m and a["status"] == "open"]
            S, Km = cost(cm, A, m); rest = sum(Km[p] for a in op for p in a["pumps"] if p not in set(a["done"]))
            kern = max([a["kernels"] for a in op] or [machine(m)["kernels"]])
            print(f"  {m}: {sum(len(a['done']) for a in A if a['machine'] == m)} pumps done in all, "
                  f"{sum(float(e['kh']) for e in ledger() if e['task'] == c and e['machine'] == m):.1f} kh; "
                  + (f"holds {sum(len(a['pumps']) - len(a['done']) for a in op)}, {rest / 3600:.0f} kh, end about {stamp(now + rest / kern)}" if op else "holds nothing"))
        for a in sorted(A, key=lambda a: a["created"])[-12:]:
            late = a["status"] == "open" and now > a["deadline"]
            print(f"    {a['id']:24s} {len(a['done']):4d}/{len(a['pumps']):<4d} {a['status']:9s} {a['hours']:g} h x {a['kernels']}"
                  + (f" (shinshu up to {upto(a['shinshu'])})" if a.get("shinshu") else "") + (" (shugeki)" if a.get("shugeki") else "") + f", deadline {stamp(a['deadline'])}" + (f", kikan {stamp(a['kikan'])}" if a.get("kikan") else "")
                  + (f", uchikiri {stamp(a['uchikiri'])}" if a.get("uchikiri") else "") + (f", the kaizu's {a['prio']}" if a.get("prio") else "")
                  + (f", delayed {hm(a['delayed'])} by now" if a.get("delayed") else "")
                  + (f", {n} jobs paused" if a["machine"] == C["machine"] and a["status"] == "open" and os.path.isdir(workdir(a)) and (n := sum(v[2] for v in jobs(workdir(a)).values())) else "")
                  + ("  PASSED: its pumps not done are free again" if late else ""))
    if said_gensoku(): print(f"{C['machine']} (this machine): {said_gensoku()}")


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


def planleft(W):   # the jobs of the plan of W without their file (those running among them), the pumps an uchikiri dropped left out
    plan = [l.split() for l in open(os.path.join(W, "plan.txt")) if l.strip() and not l.startswith("#")]
    if os.path.exists(os.path.join(W, "uchikiri.kept")): kept = set(open(os.path.join(W, "uchikiri.kept")).read().split()); plan = [f for f in plan if f[3] in kept]
    return sum(1 for f in plan if not (os.path.exists(x := os.path.join(W, f"{f[0]}_{f[3]}.dat")) and os.path.getsize(x) > 1000))


def tail_state(W):
    """jobs still waiting in the driver of W and front-ends running: the driver's log says how many wait only when a job ends (so that
    a claim of one long job would look as if launching until it is done), the plan less the files done and the jobs running counts a
    failed job as waiting (and, after an uchikiri, the pumps it dropped are left out of the plan); the smaller of the two"""
    wait = None; run = len(ours(W)[1])
    if os.path.exists(os.path.join(W, "run.log")):
        for l in open(os.path.join(W, "run.log")):
            m = re.search(r"(\d+) jobs to run|(\d+) waiting", l)
            if m: wait = int(m[1] or m[2])
    if wait and os.path.exists(os.path.join(W, "plan.txt")): wait = min(wait, max(planleft(W) - run, 0))
    return wait, run


# ------------------------------------------------------------------------------------------------------- gensoku (減速), zensoku (全速)
def gensoku():   # this machine's lowering of its kernels (--gensoku, --zensoku): its file in the work directory, or None
    try: return json.load(open(os.path.join(C["work"], "gensoku.json")))
    except (OSError, ValueError): return None


def kernels_now(now=None):
    """the kernels this machine gives Ten-Go now, its allocations together: those of machines/<m>.json, fewer under a --gensoku, held
    until its end (--zensoku, or its --jikan), then one more at a time until all are back at the end of its ramp"""
    full = machine(C["machine"])["kernels"]; g = gensoku(); now = now or time.time()
    if not g: return full
    k = min(g["kernels"], full)
    if g["until"] is not None and now >= g["until"]: k += int((full - k) * min(1.0, (now - g["until"]) / g["ramp"])) if g["ramp"] else full - k
    return k


def said_gensoku(now=None):   # the --gensoku of this machine in words ("" without one)
    g = gensoku(); now = now or time.time()
    if not g: return ""
    full = machine(C["machine"])["kernels"]; k = kernels_now(now)
    if g["until"] is None: return f"gensoku: {k} of its {full} kernels, held until --zensoku"
    if now < g["until"]: return f"gensoku: {k} of its {full} kernels until {stamp(g['until'])}, then back to {full} over {g['ramp'] / 3600:g} h"
    return f"zensoku: {k} of its {full} kernels, all back by {stamp(g['until'] + g['ramp'])}"


def rank(a, W):   # who gets the kernels first: an allocation of the kaizu's now, then those ending without loss (uchikiri), then the others
    return 0 if a.get("prio") == "now" else 1 if os.path.exists(os.path.join(W, "UCHIKIRI")) else 2


def memroom(cm):
    """how many jobs more the memory holds above MEMMIN (and 2 GB): the largest job running now (its kernel and front-end) as the
    measure, 1 GB without one"""
    avail = next(int(l.split()[1]) / 1e6 for l in open("/proc/meminfo") if l.startswith("MemAvailable"))
    def rss(p):
        try: return int(open(f"/proc/{p}/statm").read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e9
        except (OSError, IndexError, ValueError): return 0.0
    K = kids(); big = 0.0
    for a in ours_open():
        W = workdir(a)
        for pid in (jobs(W) if os.path.isdir(W) else {}): big = max(big, sum(rss(q) for q in tree(pid, K)))
    return max(int((avail - float(cm["params"].get("MEMMIN", 8)) - 2) / (big or 1.0)), 0)


def apportion(op, pause=True):
    """the kernels of this machine among its open allocations op.  As a rule, those still launching jobs take what the jobs running in
    the others leave of kernels_now() (when there are several, or under a --gensoku even alone).  An allocation of the kaizu's now, or
    one of high next to others, or jobs paused, share them by rank instead (now, then the uchikiri, then the others, the older first):
    each takes what its jobs need of what the ranks before it leave, the newest still launching the rest; the jobs of a lower rank
    above their share are paused (SIGSTOP; pause False: not) for an allocation of now still launching, as many as the memory holds, and
    resume, the nearest to completion first, as kernels come back to their share.  A --gensoku, or a sharing by rank, keeps the drivers
    from borrowing idle threads (their file shinshu set to 0, given back after)"""
    with clone():
        g = gensoku(); kern = kernels_now(); T = []
        for a in op:
            W = workdir(a); wait, run = tail_state(W) if os.path.isdir(W) else (None, 0); J = jobs(W) if os.path.isdir(W) else {}
            fz = [p for p, v in J.items() if v[2]]
            if wait is None and os.path.exists(os.path.join(W, "plan.txt")): wait = max(planleft(W) - run, 0)   # its driver has said nothing yet
            T.append(dict(a=a, W=W, wait=wait or 0, run=run, J=J, fz=fz, act=run - len(fz), rank=rank(a, W)))
        ranked = any(x["fz"] for x in T) or (len(T) > 1 and (any(x["a"].get("prio") for x in T) or sum(1 for x in T if x["wait"]) > 1))
        if not ranked:
            busy = sum(x["run"] for x in T if not x["wait"])
            for x in T:
                if x["wait"] and (len(op) > 1 or g): open(os.path.join(x["W"], "nproc"), "w").write(f"{max(kern - busy, 0 if g else 1)}\n")
        else:
            order = sorted(T, key=lambda x: (x["rank"], bool(x["wait"]), x["a"]["created"])); rem = kern
            for x in order: x["allot"] = min(x["run"] + x["wait"], rem); rem -= x["allot"]
            fresh = [x for x in order if x["wait"]]
            if fresh: fresh[-1]["allot"] += rem   # the newest still launching: what is left
            S = {c: cost(campaign(c), allocs(c), C["machine"])[0] for c in {x["a"]["campaign"] for x in T}}   # seconds per order here
            left = lambda x, pid: S[x["a"]["campaign"]].get(x["J"][pid][0].split("_nt")[-1], 3600) - (elapsed(pid) - pauses(x["W"]).get(x["J"][pid][:2], 0))
            want = sum(min(x["wait"], x["allot"] - x["act"]) for x in order if x["rank"] == 0 and x["wait"] and x["allot"] > x["act"])
            need = want - max(kern - sum(x["act"] for x in T), 0)   # a machine over its kernels already (a fresh claim gets one at least) pauses nothing for it
            if pause and want > 0 and need > 0:   # for now: the jobs of the lowest ranks above their share, the furthest from completion first
                need = min(need, memroom(campaign(order[0]["a"]["campaign"]))); now_ids = ", ".join(x["a"]["id"] for x in order if x["rank"] == 0)
                for x in reversed(order):
                    if need <= 0: break
                    if x["rank"] == 0 or x["act"] <= x["allot"]: continue
                    live = sorted((p for p, v in x["J"].items() if not v[2]), key=lambda p: -left(x, p))[:min(need, x["act"] - x["allot"])]
                    n = freeze(x["W"], live, f"for the now pumps of {now_ids}"); x["act"] -= n; need -= n; x["fz"] += live
            free = kern - sum(x["act"] for x in T)
            for x in order:   # now: no more than the kernels free once paused (the memory may have held fewer pauses, or none under an uchikiri)
                if x["rank"] == 0 and x["wait"]: x["allot"] = min(x["allot"], x["act"] + max(free, 0)); free -= max(x["allot"] - x["act"], 0)
            for x in order:   # resume within the share, the nearest to completion first
                if not x["fz"] or free <= 0 or x["act"] >= x["allot"]: continue
                back = sorted(x["fz"], key=lambda p: left(x, p))[:min(len(x["fz"]), x["allot"] - x["act"], free)]
                n = thaw(x["W"], back); x["act"] += n; free -= n
            for x in T:
                if x["wait"]: open(os.path.join(x["W"], "nproc"), "w").write(f"{max(x['allot'], 0)}\n")
        for x in T:
            W = x["W"]; f, kept = os.path.join(W, "shinshu"), os.path.join(W, "shinshu.gensoku")
            if os.path.exists(f):
                s = open(f).read().strip()
                if (g or ranked) and s != "0": open(kept, "w").write(s + "\n"); open(f, "w").write("0\n")
                elif not (g or ranked) and s == "0" and os.path.exists(kept): os.replace(kept, f)


def settle(op, pause=True):   # apportion; a --gensoku whose kernels are all back then ends (True)
    apportion(op, pause); g = gensoku()
    if g and g["until"] is not None and kernels_now() >= machine(C["machine"])["kernels"]:
        os.remove(os.path.join(C["work"], "gensoku.json")); apportion(op, pause); return True
    return False


def started(W):   # the pumps under way or done in W (as strings): a job done or in flight, as the driver's uchikiri sees them
    have = {os.path.basename(f).rsplit("_", 1)[1][:-4] for f in glob.glob(os.path.join(W, "*.dat")) if os.path.getsize(f) > 1000}
    return have | {v[1] for v in jobs(W).values()}


def unstarted(a):   # the pumps of allocation a (of this machine) not started
    W = workdir(a); s = started(W) if os.path.isdir(W) else set()
    return [p for p in a["pumps"] if str(p) not in s and p not in a["done"]]


def delay(c, ids, by, why):   # push back the deadlines of these allocations by `by` seconds (they wait for a claim of now)
    def change():
        out = []
        for aid in ids:
            f = R("allocs", c, aid + ".json"); x = json.load(open(f))
            if x["status"] != "open": continue
            x["deadline"] = int(x["deadline"] + by); x["delayed"] = x.get("delayed", 0) + int(by); save(f, x); out.append(aid)
        return out or None
    return transact(change, lambda o: f"{why}: the deadlines of {', '.join(o)} pushed back by {hm(by)}") or []


def press(c, op, kern, hours, shugeki=False, kikan=None):
    """the kaizu's pumps of level now or high (PRESS) are claimed at once, the pumps of the best level alone, by a watch whose
    allocations are not already launching pumps of that level (or above); when the claim is made, the allocations of this machine
    still launching pumps of a lower level end without loss (an uchikiri: the pumps started complete, the others go back to the pool).
    The pumps of high then take the kernels as the uchikiri frees them; those of now take them at once (apportion pauses the jobs of
    the others, whose deadlines are pushed back by the span of the claim).  Pumps of that level held by an allocation of this machine
    that has not started them: that allocation ends (uchikiri) first, and they are claimed at the next look.  What it did, or None"""
    cm = campaign(c); A = allocs(c); now = time.time(); lv = level(c, cm); out = held(A, now)
    un = {a["id"]: unstarted(a) for a in op}; mine_un = {p for v in un.values() for p in v}
    L = {}
    for p in cm["pumps"]:
        x = lv(p)[0]
        if x in PRESS and (p[0] not in out or p[0] in mine_un): L.setdefault(x, set()).add(p[0])
    best = next((x for x in PRESS if L.get(x)), None)
    if not best: return None
    k = LEVELS.index(best); lev = {p[0]: LEVELS.index(lv(p)[0]) for p in cm["pumps"]}
    if any(un[a["id"]] and max(lev[p] for p in un[a["id"]]) <= k for a in op): return None   # one of ours is on pumps of that level already
    lower = [a for a in op if any(lev[p] > k for p in un[a["id"]]) and not os.path.exists(os.path.join(workdir(a), "UCHIKIRI"))]
    said = []
    if L[best] - mine_un:   # free: claimed now, then the others end
        a = cmd_claim(c, hours, kern, shugeki=shugeki, quiet=True, only=best, kikan=kikan)
        if not a: return None   # another machine was first
        said.append(f"{a['id']}: {len(a['pumps'])} pumps of {best} claimed at once")
        if best == "now":
            late = [x["id"] for x in op if set(x["pumps"]) - set(x["done"])]
            if late: delay(c, late, a["deadline"] - a["created"], f"now {a['id']}"); said.append(f"the deadlines of {', '.join(late)} pushed back by {hm(a['deadline'] - a['created'])}")
            for x in [a] + [x for x in op if os.path.isdir(workdir(x)) and tail_state(workdir(x))[0] != 0]:   # no launch before apportion shares the kernels out, the others paused
                open(os.path.join(workdir(x), "nproc"), "w").write("0\n")
        for x in lower: said.append("uchikiri " + uchikiri(x))
        launch(a, quiet=True)
    else:   # held, not started, by ours: those allocations end first
        for x in [x for x in op if set(un[x["id"]]) & L[best] and not os.path.exists(os.path.join(workdir(x), "UCHIKIRI"))]: said.append(f"uchikiri for the {best} pumps it holds: " + uchikiri(x))
    return "; ".join(said) or None


def ours_open(): return [a for c in campaigns() for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open"]


def cmd_gensoku(n, hours=None):
    """--gensoku N [--jikan H]: this machine gives Ten-Go N kernels at most from now, its allocations together, until --zensoku (or for
    H hours, then back one at a time over an hour); says when its open allocations end then, and which would miss their deadline"""
    with clone():
        m = C["machine"]; full = machine(m)["kernels"]; now = time.time()
        if not 1 <= n <= full: die(f"--gensoku {n}: from 1 to the {full} kernels of {m} (machines/{m}.json); --uchikiri ends its allocations without loss")
        if hours is not None and hours <= 0: die("--gensoku N --jikan H: H hours, more than 0")
        save(os.path.join(C["work"], "gensoku.json"), dict(kernels=n, set=int(now), until=int(now + hours * 3600) if hours else None, ramp=3600))
        op = ours_open(); apportion(op)
        print(f"ten-go: {m}: {said_gensoku()}; a job that ends is not replaced while {n} or more run (none is killed), the claims are for {n}")
        rest = sum(sum(cost(campaign(a["campaign"]), allocs(a["campaign"]), m)[1][p] for p in a["pumps"] if p not in set(a["done"])) for a in op)
        if op:
            t = now + rest / n; late = [a for a in op if a["deadline"] < t]
            print(f"  its open allocations, {rest / 3600:.1f} kh left: done about {stamp(t)} at {n} kernels" + ("" if late else ", within their deadlines"))
            for a in late: print(f"  {a['id']}: " + (f"past its deadline already ({stamp(a['deadline'])}): its pumps not done are free again" if a["deadline"] < now else
                                 f"its deadline {stamp(a['deadline'])} comes first: the pumps it has not done by then go back to the pool (--uchikiri ends it without loss)"))


def cmd_zensoku(hours=1.0):
    """--zensoku [H]: the end of a --gensoku, the kernels given back one at a time over H hours (1; 0: at once)"""
    with clone():
        m = C["machine"]; full = machine(m)["kernels"]; g = gensoku(); now = time.time()
        if not g: return print(f"ten-go: {m} has no --gensoku: all its {full} kernels are Ten-Go's")
        k = kernels_now(now); save(os.path.join(C["work"], "gensoku.json"), dict(g, kernels=k, until=int(now), ramp=int(max(hours, 0) * 3600)))
        if settle(ours_open()): return print(f"ten-go: {m}: all its {full} kernels are Ten-Go's again")
        print(f"ten-go: {m}: {said_gensoku()}, one more every {round(hours * 60 / (full - k), 1):g} min")


LAST = 1800   # the last half hour of a watch's time: no claim then (kikan), or sorties from then on


def cmd_watch(until, hours, c, shinshu=None, shugeki=False, kikan=False):
    """the unattended loop: claim and launch an allocation while time remains before `until`, then go on with sorties (the cheapest
    pumps first, whole), until the campaign is complete (nothing free and no allocation open anywhere) or an uchikiri or a chushi by
    hand (kikan: end at `until`, what runs then ending without loss; no `until`: until the campaign is complete), push the pumps done every 30 min,
    restart a dead driver (3 times per allocation at most), and claim the next allocation as soon as the current one has launched all
    its jobs, its tail then lending its kernels to the new one (the nproc of the new driver = kernels - jobs of the tail); a new
    version pushed to the pool takes the watch over at its next sync; a git that fails (the network gone) is tried again every minute"""
    end = moment(until) if until else float("inf"); restarts = {}; last = 0; c = pick(c); flag = os.path.join(C["work"], "ENDING"); said = 0; lost = None; kprev = None
    halt = kikan; late = False   # halt: no claim past `end` (kikan, or an uchikiri by hand); late: past it, going on with sorties
    t0 = float(os.environ.get("TENGO_WATCH_T0", time.time()))   # the start of the first watch: an uchikiri before a new version still counts
    print(f"ten-go watch until {stamp(end) if until else 'the campaign is complete'} ({C['machine']}, {c})"
          + ("" if not until else ", ending then without loss (kikan)" if kikan else ", then on with the cheapest pumps first, whole, until the campaign is complete"), flush=True)
    while True:
        try:
            now = time.time()
            if not (halt and end <= now) and os.path.exists(flag) and os.path.getmtime(flag) > t0:
                end, halt = min(end, now), True; print(f"{time.strftime('%H:%M:%S')} uchikiri or chushi: no more claims, the watch ends with its drivers", flush=True)
            if end - now <= LAST and not halt and not late:   # its time near or past: the next claims are sorties, so that an uchikiri ends soon
                late = True; print(f"{time.strftime('%H:%M:%S')} {'its time is up' if now >= end else f'its time is up at {stamp(end)}'}: on with sorties, "
                                   "the cheapest pumps first, whole (an uchikiri ends within a job or two)", flush=True)
            open_claims = end - now > LAST or late and not halt; sortie = shugeki or late; hrs = hours if late else min(hours, (end - now) / 3600)
            if now - last > 1800: cmd_done(); last = now
            sync(); op = [a for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open"]
            if newer(): os.environ["TENGO_WATCH_T0"] = str(t0); os.execv(sys.executable, [sys.executable, os.path.realpath(__file__)] + sys.argv[1:])
            for a in op:
                W = workdir(a); log = open(os.path.join(W, "run.log")).read() if os.path.exists(os.path.join(W, "run.log")) else ""
                if not ours(W)[0] and "ALLDONE" not in log.split("tengo-launch")[-1] and not os.path.exists(os.path.join(W, "STOP")):
                    if restarts.get(a["id"], 0) >= 3:   # it does not start: its pumps back to the pool, not held until the deadline
                        print(f"{time.strftime('%H:%M:%S')} driver of {a['id']} down after 3 starts: released", flush=True)
                        open(os.path.join(W, "STOP"), "w").write("released by the watch\n"); cmd_done(a["id"], final="released"); continue
                    restarts[a["id"]] = restarts.get(a["id"], 0) + 1; print(f"{time.strftime('%H:%M:%S')} driver of {a['id']} not running: start {restarts[a['id']]}", flush=True)
                    open(os.path.join(W, "run.log"), "a").write(f"{time.strftime('%H:%M:%S')} tengo-launch (watch)\n"); launch(a, quiet=True)
            for a in op:   # an allocation ended at its time by its driver (kikan): its pumps not started back to the pool at once
                if (n := back(a)): print(f"{time.strftime('%H:%M:%S')} kikan {a['id']}: {n} pumps back to the pool", flush=True)
            pressed = open_claims and press(c, op, kernels_now(), hrs, sortie, kikan and end)   # the kaizu's now and high, at once
            if pressed:
                print(f"{time.strftime('%H:%M:%S')} {pressed}", flush=True); op = [a for a in allocs(c) if a["machine"] == C["machine"] and a["status"] == "open"]
            tails = [(a, *tail_state(workdir(a))) for a in op]
            fresh = [a for a, wait, run in tails if wait]           # an allocation still launching jobs
            down = [a for a in op if not ours(workdir(a))[0] and not os.path.exists(os.path.join(workdir(a), "STOP"))
                    and "ALLDONE" not in (open(os.path.join(workdir(a), "run.log")).read() if os.path.exists(os.path.join(workdir(a), "run.log")) else "")]
            if not fresh and not down and not pressed and open_claims:   # no new claim while one of ours has its driver down
                busy = sum(run for _, _, run in tails); kern = kernels_now()   # fewer under a --gensoku
                a = cmd_claim(c, hrs, kern, shinshu=shinshu, shugeki=sortie, quiet=True, kikan=kikan and end)
                if a:
                    open(os.path.join(workdir(a), "nproc"), "w").write(f"{max(kern - busy, 0 if gensoku() else 1)}\n"); launch(a); op = op + [a]   # shared out below with the others
                elif not op:
                    held_by = sorted({x["machine"] for x in allocs(c) if x["status"] == "open"})
                    if not held_by:
                        cm = campaign(c); lv = level(c, cm); out = held(allocs(c), now); sk = sum(lv(p)[0] == "skip" for p in cm["pumps"] if p[0] not in out)
                        cmd_done(); print(f"{time.strftime('%H:%M:%S')} {c} is complete: nothing free" + (f" but the {sk} pumps skipped (--kaizu)" if sk else "") + ", no allocation open; watch ends", flush=True); return
                    if now - said > 1800: said = now; print(f"{time.strftime('%H:%M:%S')} nothing free in {c} for now, waiting on {', '.join(held_by)}", flush=True)
            if settle(op, pause=not (halt and end <= now)): print(f"{time.strftime('%H:%M:%S')} zensoku: all the {kernels_now()} kernels of {C['machine']} are Ten-Go's again", flush=True)
            if (k := kernels_now()) != kprev and gensoku(): print(f"{time.strftime('%H:%M:%S')} {said_gensoku()}", flush=True)
            kprev = k                                               # above: the newest allocation takes the kernels the tails free
            if halt and now > end and not any(run for _, _, run in tails):
                for a in op: os.path.isdir(workdir(a)) and thaw(workdir(a))   # none should be left paused
                cmd_done(); print(f"{time.strftime('%H:%M:%S')} watch ends", flush=True); return
            if lost: print(f"{time.strftime('%H:%M:%S')} the watch works again", flush=True); lost = None
        except (SystemExit, Exception) as e:   # a git that fails (the network gone), or a file half written: said once, tried again in a minute
            what = str(e) if isinstance(e, SystemExit) else f"{type(e).__name__}: {e}"
            if what != lost: lost = what; print(f"{time.strftime('%H:%M:%S')} {what}\n  (the watch tries again every minute)", flush=True)
        time.sleep(60)


def newer():
    """the pool's tengo.py is a version other than the one running, and it starts: the watch goes on in it"""
    f = os.path.realpath(__file__); m = re.search(r'^VERSION = "([^"]+)"', open(f).read(), re.M)
    if not m or m[1] in (VERSION, *newer.bad): return False
    try: ok = subprocess.run([sys.executable, f, "version"], capture_output=True, text=True, timeout=120).stdout.strip() == f"ten-go {m[1]}"
    except subprocess.TimeoutExpired: ok = False
    print(f"{time.strftime('%H:%M:%S')} the pool brings ten-go {m[1]}: " + ("the watch goes on in it" if ok else "it does not start, the watch stays in " + VERSION), flush=True)
    if not ok: newer.bad.add(m[1])   # said once
    return ok
newer.bad = set()


def cmd_fetch(c, dest):
    sync(); c = pick(c); os.makedirs(dest, exist_ok=True); n = 0
    for f in sorted(glob.glob(R("results", c, "*.tgz"))):
        with tarfile.open(f) as t: t.extractall(dest, filter="data"); n += len(t.getnames())
    print(f"ten-go: {n} files of {c} in {dest}")


# ------------------------------------------------------------------------------------------------------------------------ campaigns
REF = {"150w": 1118, "150w80": 1409, "200e": 760, "250e": 1580, "300e": 2685, "300e80": 3400, "400e": 11076}   # seconds per job, azag at home, 30 kernels


def computed(sources):
    """{exact pump: set of orders} of the .dat files of these runs (directories or .tgz archives), the pump read from each file's
    header, its exact x, whatever the run's numbering; a file under 1000 bytes is a kill's leftover"""
    out = {}
    def add(name, size, first):
        m = re.search(r"_nt(\d+[we]\d*)_\d+\.dat$", name)
        if m and size > 1000: out.setdefault(Fraction(first.split()[1]), set()).add(m[1])
    for src in sources:
        if os.path.isdir(src):
            for f in glob.glob(os.path.join(src, "*.dat")): add(f, os.path.getsize(f), open(f).readline())
        else:
            with tarfile.open(src) as t:
                for x in t:
                    if x.isfile() and x.name.endswith(".dat"): add(x.name, x.size, t.extractfile(x).readline().decode())
    return out


def declare(path, sp=None, here=None):
    """a campaign from a spec file (JSON; its relative paths from the file's directory):
      {"name", "about", "prefix", "params": {GA, GS, PREC, MEMMIN}, "ref": {order: seconds} (default REF), and either
       "kind": "grid", "grid": [[from, to, step], ...], "orders": [[lo, hi, [orders]], ...] (for P in [lo, hi), hi may be "inf"),
         "except": [[lo, hi], ...], "have": [runs]: a pump whose orders are all in these runs (directories or .tgz archives) is left out;
       or "kind": "adaptive", "rule": {x0, x1, h0, lev, delta, hmax, wmax, eps, src, orders}, "seed": [run directories]: the pumps of
         these runs (files <prefix>_nt<order>_<J>.dat on the rule's lattice) are its first pumps, those complete done (their files go
         to the pool as the results of an allocation "seed"), the others to be completed;
       or "kind": "list", "pumps": [[id, P, orders] or [P, orders], ...]: these pumps, as given;
       or "kind": "parts", "parts": [part, ...]: each part a grid, list or adaptive spec with its own prefix (an adaptive part with a
         seed first), its pumps numbered from k 10^7, a claim taking from the parts in their order}
    returns the campaign and the seed (None, or the seed allocation with the files of its archives); sp and here give the spec and its
    directory directly (for --zoen)"""
    if sp is None: sp = json.load(open(path)); here = os.path.dirname(os.path.abspath(path))
    at = lambda f: os.path.join(here, os.path.expanduser(f))
    if not re.fullmatch(r"[\w.-]+", sp.get("name", "")): die(f"{path}: a name of letters, digits, . - _")
    def build(q, base):   # one part: its pumps (numbered from base), the pumps done of its seed and their files, the pumps left out
        if q.get("kind", "grid") == "grid":
            pts = set()
            for a, b, st in q["grid"]:
                a, b, st = Fraction(str(a)), Fraction(str(b)), Fraction(str(st)); pts |= {a + i * st for i in range(int((b - a) / st) + 1)}
            pts = {P for P in pts if not any(Fraction(str(lo)) <= P <= Fraction(str(hi)) for lo, hi in q.get("except", []))}
            def orders(P):
                for lo, hi, o in q["orders"]:
                    if Fraction(str(lo)) <= P and (hi == "inf" or P < Fraction(str(hi))): return o
                die(f"{path}: no orders for P = {dec(P)}")
            have = computed([at(f) for f in q.get("have", [])])
            keep = sorted(P for P in pts if not set(orders(P)) <= have.get(P, set()))
            return [[base + i, dec(keep[i]), orders(keep[i])] for i in vdc(len(keep))], [], [], len(pts) - len(keep)
        if q["kind"] == "list":   # explicit pumps, [id, P, orders] (the id within the part, < 10^7) or [P, orders] (numbered in order)
            out = []
            for i, e in enumerate(q["pumps"]):
                pid, P, o = e if len(e) == 3 else (i, *e)
                if not 0 <= pid < 10 ** 7: die(f"{path}: a pump id within 0..10^7 ({pid})")
                out.append([base + pid, dec(Fraction(str(P))), list(o)])
            return out, [], [], 0
        if q["kind"] != "adaptive": die(f"{path}: kind grid, list, adaptive or parts")
        if q.get("seed") and base: die(f"{path}: an adaptive part with a seed comes first (its files keep their numbers)")
        r = q["rule"]; x0 = Fraction(str(r["x0"])); step = Fraction(str(r["h0"])) / 2 ** r["lev"]; have, files = {}, []
        jmax = int((Fraction(str(r["x1"])) - x0) / step)   # only the seed's pumps in the window [x0, x1]
        for d in q.get("seed", []):
            for f in sorted(glob.glob(os.path.join(at(d), f"{q['prefix']}_nt*_*.dat"))):
                m = re.search(rf"{re.escape(q['prefix'])}_nt(\d+[we]\d*)_(\d+)\.dat$", f)
                if not m or os.path.getsize(f) <= 1000 or not 0 <= int(m[2]) <= jmax: continue
                if Fraction(open(f).readline().split()[1]) != x0 + int(m[2]) * step: die(f"{f}: not on the rule's lattice")
                have.setdefault(int(m[2]), set()).add(m[1]); files.append(f)
        full = sorted(J for J, o in have.items() if set(r["orders"]) <= o)
        return ([[base + J, dec(x0 + J * step), list(r["orders"]) if J in full else [o for o in r["orders"] if o not in have[J]]] for J in sorted(have)],
                [base + J for J in full], files, 0)
    kind = sp.get("kind", "grid"); qs = sp["parts"] if kind == "parts" else [sp]
    cm = dict(name=sp["name"], prefix=qs[0]["prefix"], about=sp.get("about", ""), params=sp["params"], ref=sp.get("ref", REF), kind=kind, pumps=[])
    full, files, out, P = [], [], 0, []
    for k, q in enumerate(qs):
        base = k * 10 ** 7   # the pumps of part k are numbered from k 10^7
        pumps, f1, f2, lo = build(q, base); cm["pumps"] += pumps; full += f1; files += f2; out += lo
        P.append(dict(kind=q.get("kind", "grid"), prefix=q["prefix"], base=base, about=q.get("about", ""), pumps=len(pumps), left_out=lo,
                      **({"rule": q["rule"]} if q.get("kind") == "adaptive" else {})))
    if kind == "parts":
        cm["parts"] = P
        if len({q["prefix"] for q in P}) < len(P): die(f"{path}: each part its own prefix")
    elif kind == "adaptive": cm["rule"] = sp["rule"]
    if out: cm["left_out"] = out
    seed = (dict(id="seed", campaign=cm["name"], machine="seed", kernels=0, hours=0, created=int(time.time()), deadline=int(time.time()),
                 cost_kernel_h=0, pumps=full, done=full, times={}, results=[], status="finished", tengo=VERSION,
                 about=f"the pumps of {', '.join(d for q in qs for d in q.get('seed', []))} before Ten-Go"), files) if files else None
    for p in cm["pumps"]:
        if not set(p[2]) <= set(cm["ref"]): die(f"{path}: no reference time for the orders {set(p[2]) - set(cm['ref'])}")
    return cm, seed


def reinforce(path):
    """--zoen: the parts of a spec ({"name": campaign, "before": index (default: at the end), "parts": [...]}) added to a campaign in
    parts, each from a new base, the pumps of the campaign kept in the order of its parts; returns the change for transact"""
    sp = json.load(open(path)); here = os.path.dirname(os.path.abspath(path)); name = sp.get("name", "")
    def change():
        if not os.path.exists(R("campaigns", name + ".json")): die(f"--zoen: no campaign {name} in the pool")
        cm = campaign(name)
        if cm.get("kind") != "parts": die(f"--zoen: {name} is not a campaign in parts")
        if sp.get("params", cm["params"]) != cm["params"]: die("--zoen: the parameters differ from the campaign's (one driver runs a claim)")
        ref = dict(cm.get("ref", REF), **sp.get("ref", {}))   # the spec may bring reference times for new orders (300e120, ...)
        add, seed = declare(path, dict(sp, kind="parts", params=cm["params"], ref=ref), here); cm["ref"] = ref
        k0 = max(q["base"] for q in cm["parts"]) // 10 ** 7 + 1   # the new parts' bases, after every existing one
        old = {q["prefix"] for q in cm["parts"]}
        for q in add["parts"]:
            if q["prefix"] in old: die(f"--zoen: the prefix {q['prefix']} is already a part of {name}")
        shift = {q["base"]: (k0 + i) * 10 ** 7 for i, q in enumerate(add["parts"])}
        moved = lambda pid: shift[max(b for b in shift if pid >= b)] + pid - max(b for b in shift if pid >= b)
        for q in add["parts"]: q["base"] = shift[q["base"]]
        newp = [[moved(p[0]), p[1], p[2]] for p in add["pumps"]]
        at = sp.get("before", len(cm["parts"]))
        cm["parts"][at:at] = add["parts"]
        order = {q["base"]: i for i, q in enumerate(cm["parts"])}
        cm["pumps"] = sorted(cm["pumps"] + newp, key=lambda p: order[part(dict(parts=cm["parts"]), p[0])["base"]])   # stable: each part's own order kept
        save(R("campaigns", name + ".json"), cm)
        if seed: die("--zoen: an added part with a seed is not supported yet")
        return (name, len(newp), [q["prefix"] for q in add["parts"]])
    return change


def seeded(cm, seed):   # the seed allocation and its archives (60 MB of files at most each, under GitHub's 100 MB a file)
    a, files = seed; n, part = 0, []
    for f in files + [None]:
        if f and sum(os.path.getsize(x) for x in part) + os.path.getsize(f) < 60e6: part.append(f); continue
        if part:
            n += 1; rel = f"results/{cm['name']}/seed-{n}.tgz"; os.makedirs(R("results", cm["name"]), exist_ok=True)
            with tarfile.open(R(rel), "w:gz") as t:
                for x in part: t.add(x, arcname=os.path.basename(x))
            a["results"].append(rel)
        part = [f] if f else []
    save(R("allocs", cm["name"], "seed.json"), a)


def cache(c):   # this machine's copy of the results of campaign c, each archive unpacked once, for the rule of an adaptive campaign
    D = os.path.join(C["work"], c, "cache"); os.makedirs(D, exist_ok=True); seen = os.path.join(D, ".unpacked")
    done = set(open(seen).read().split()) if os.path.exists(seen) else set()
    for f in sorted(glob.glob(R("results", c, "*.tgz"))):
        if os.path.basename(f) in done: continue
        with tarfile.open(f) as t: t.extractall(D, filter="data")
        open(seen, "a").write(os.path.basename(f) + "\n")
    return D


def grown(c, cm, A, busy, kern):
    """a campaign with an adaptive part, at a claim: the rule of each adaptive part applied to its pumps whose 250e and 300e files are in
    the pool and to those still to come, the new pumps appended to cm; returns the pumps to offer, part after part in their order (in an
    adaptive part those free again first, then the new ones, worst interval first; in a grid part its free pumps in the global order),
    and (number new, intervals to split)"""
    sys.path[:0] = [R("kit"), os.path.dirname(os.path.realpath(__file__))]; import tengo_adaptive as adaptive   # the pool's kit first
    D = cache(c); have = {}
    for f in os.listdir(D):
        x = re.match(r"(.+)_nt(\d+[we]\d*)_(\d+)\.dat$", f)
        if x and os.path.getsize(os.path.join(D, f)) > 1000: have.setdefault((x[1], int(x[3])), set()).add(x[2])
    done = set().union(*(set(a["done"]) for a in A)) if A else set(); offer, added, nopen = [], 0, 0
    for q in parts(cm):
        mine = [p for p in cm["pumps"] if part(cm, p[0]) is q]
        if q["kind"] != "adaptive": offer += [p for p in mine if p[0] not in done and p[0] not in busy]; continue
        r = q["rule"]; b = q["base"]; x0 = Fraction(str(r["x0"])); step = Fraction(str(r["h0"])) / 2 ** r["lev"]
        known = {i - b for (px, i), o in have.items() if px == q["prefix"] and i >= b and {"250e", "300e"} <= o}
        waiting = {p[0] - b for p in mine if p[0] not in done and p[0] - b not in known}
        new, n = adaptive.grow(r, q["prefix"], D, known, waiting, kern, b); added += len(new); nopen += n
        fresh = [[b + J, dec(x0 + J * step), list(r["orders"])] for J in new]; cm["pumps"] += fresh
        offer += [p for p in mine if p[0] not in done and p[0] not in busy] + fresh
    return offer, (added, nopen)


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


def refit(path, dry=False):
    """--kaiso: the orders of the pumps of one part that no allocation holds or has done changed by the map of a spec ({"name":
    campaign, "part": prefix, "orders": {old: new}, "ref": {new: seconds} for an order without a reference time yet, "about": why});
    each refit is noted in the campaign (refits); returns the change for transact"""
    sp = json.load(open(path)); name, prefix, mp = sp.get("name", ""), sp.get("part", ""), sp.get("orders", {})
    if not mp: die("--kaiso: the spec has no orders to change")
    for o in list(mp) + list(mp.values()):
        if not re.fullmatch(r"(\d+)([we])(\d*)", o): die(f"--kaiso: {o} is not an order (like 300e, 150w, 300e80)")
    def change():
        if not os.path.exists(R("campaigns", name + ".json")): die(f"--kaiso: no campaign {name} in the pool")
        cm = campaign(name); A = allocs(name); ref = dict(cm["ref"], **sp.get("ref", {}))
        if prefix not in {q["prefix"] for q in parts(cm)}: die(f"--kaiso: no part {prefix} in {name} ({', '.join(q['prefix'] for q in parts(cm))})")
        missing = sorted({o for o in mp.values() if o not in ref})
        if missing: die(f"--kaiso: no reference time for {', '.join(missing)}: give it in the spec (\"ref\")")
        out = set()   # held: done, or in an open allocation, past its deadline or not (its driver may still finish it with the old orders)
        for a in A: out |= set(a["done"]) | (set(a["pumps"]) if a["status"] == "open" else set())
        mine = [p for p in cm["pumps"] if pre(cm, p[0]) == prefix]; n = 0; kept = sum(p[0] in out for p in mine)
        for p in mine:
            if p[0] in out: continue
            new = [mp.get(o, o) for o in p[2]]
            if new != p[2]: p[2] = new; n += 1
        if dry:
            print(f"ten-go: --kaiso {name} {prefix} (dry): {n} pumps would change ({', '.join(f'{a} -> {b}' for a, b in mp.items())}), {kept} held or done keep their orders")
            return None
        if not n: return None
        cm["ref"] = ref; cm.setdefault("refits", []).append(dict(t=int(time.time()), part=prefix, orders=mp, pumps=n, kept=kept, about=sp.get("about", "")))
        save(R("campaigns", name + ".json"), cm)
        return (name, prefix, n, kept, mp)
    return change


def main():
    ap = argparse.ArgumentParser(prog="ten-go", description="Operation Ten-Go: a shared pool of pump jobs in a git repository", allow_abbrev=False)
    ap.add_argument("cmd", nargs="?"); ap.add_argument("arg", nargs="?"); ap.add_argument("more", nargs="*"); ap.add_argument("--sakusen", dest="campaign")
    ap.add_argument("--jikan", dest="hours", type=float); ap.add_argument("--ki", type=int); ap.add_argument("--go", action="store_true")
    ap.add_argument("--alloc"); ap.add_argument("--until"); ap.add_argument("--repo"); ap.add_argument("--work")
    ap.add_argument("--machine"); ap.add_argument("--note", default=""); ap.add_argument("--shinshu", nargs="?", const="max")
    ap.add_argument("--honkai", action="store_true"); ap.add_argument("--uchikiri", action="store_true"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--chushi", nargs="?", const=10, type=float); ap.add_argument("--now", action="store_true"); ap.add_argument("--wait", action="store_true")
    ap.add_argument("--kido", metavar="MACHINE"); ap.add_argument("--senkyo", action="store_true"); ap.add_argument("--tassei", action="store_true")
    ap.add_argument("--shushu", nargs="?", const=".", metavar="DIR"); ap.add_argument("--shugeki", action="store_true"); ap.add_argument("--kikan", action="store_true")
    ap.add_argument("--sensen", metavar="NAME"); ap.add_argument("--zoen", metavar="SPEC"); ap.add_argument("--kaiso", metavar="SPEC")
    ap.add_argument("--kaizu", nargs="?", const=1945, type=int, metavar="PORT")
    ap.add_argument("--gensoku", type=int, metavar="N"); ap.add_argument("--zensoku", nargs="?", const=1.0, type=float, metavar="H")
    OLD = {"--kernels": "--ki N, the kernels of the allocation", "-c": "--sakusen C, the campaign", "--campaign": "--sakusen C, the campaign",
           "--hours": "--jikan H, the hours", "claim": "--honkai", "release": "--chushi, or --uchikiri", "init": "--kido MACHINE --repo CLONE --work DIR",
           "status": "--senkyo", "done": "--tassei", "fetch": "--shushu [DIR]", "mkcampaign": "--sensen NAME"}
    first = next((x for x in sys.argv[1:] if not x.startswith("-")), None)   # an old command only as the command, an old option anywhere
    for x in sys.argv[1:]:
        if x.split("=")[0] in OLD and (x.startswith("-") or x is first): die(f"no {'option' if x.startswith('-') else 'command'} {x.split('=')[0]} any more: {OLD[x.split('=')[0]]}")
    a = ap.parse_args()
    if a.honkai and a.hours and a.until:
        h = hours_until(a.until)[0]; k = a.ki
        if not k:
            try: C.update(json.load(open(CONF))); k = machine(C["machine"])["kernels"]   # no sync: only this machine's kernels
            except (OSError, KeyError, ValueError): pass
        return print(restated(h) + (f"   # {h:g} h x {k} kernels = {h * k:.1f} kh" if k else ""))
    if a.cmd in ("-v", "version"): return print(f"ten-go {VERSION}")
    opts = [o for o, on in (("--honkai", a.honkai), ("--uchikiri", a.uchikiri), ("--chushi", a.chushi is not None), ("--kido", a.kido is not None), ("--senkyo", a.senkyo), ("--tassei", a.tassei), ("--shushu", a.shushu is not None), ("--sensen", a.sensen is not None), ("--zoen", a.zoen is not None), ("--kaiso", a.kaiso is not None), ("--kaizu", a.kaizu is not None), ("--gensoku", a.gensoku is not None), ("--zensoku", a.zensoku is not None)) if on]
    if len(opts) > 1: die(f"{' and '.join(opts)}: one at a time")
    if opts and a.cmd: die(f"{opts[0]} stands alone, without a command ({a.cmd})")
    if a.now and a.wait: die("--now or --wait, not both")
    if a.kikan and not (a.honkai or a.cmd == "watch"): die("--kikan goes with --honkai or watch")
    if not (opts or a.cmd): die(f"no command\n{__doc__}")
    if a.kido is not None:
        if not (a.kido and a.repo and a.work): die("ten-go --kido MACHINE --repo CLONE --work DIR")
        save(CONF, dict(machine=a.kido, repo=os.path.abspath(os.path.expanduser(a.repo)), work=os.path.abspath(os.path.expanduser(a.work))))
        return print(f"ten-go: {CONF} written ({a.kido})")
    try: C.update(json.load(open(CONF)))
    except FileNotFoundError: die(f"no {CONF}: run `ten-go --kido MACHINE --repo CLONE --work DIR` first")
    if a.uchikiri: cmd_uchikiri(a.alloc, a.dry)
    elif a.chushi is not None: cmd_chushi(a.alloc, a.chushi, "dry" if a.dry else "wait" if a.wait else "now" if a.now else None)
    elif a.senkyo: cmd_status(a.campaign)
    elif a.honkai:
        if a.until: a.hours, t = hours_until(a.until); print(f"ten-go: until {a.until}, {stamp(t)}: {a.hours:g} h from now")
        if not a.hours: die("--honkai --jikan H, or --until TAG")
        cmd_claim(a.campaign, a.hours, a.ki, a.go, a.shinshu, a.shugeki, kikan=a.kikan)
    elif a.tassei: cmd_done(a.alloc)
    elif a.cmd == "launch":
        sync(); op = [x for c in campaigns() for x in allocs(c) if x["machine"] == C["machine"] and x["status"] == "open" and (not a.alloc or x["id"] == a.alloc)]
        for x in op: launch(x, shinshu=a.shinshu)
        if not op: print("ten-go: no open allocation of this machine")
    elif a.cmd == "watch":
        if a.kikan and not a.until: die("watch --kikan ends the watch at its --until TAG: without one, the watch runs until the campaign is complete")
        cmd_watch(a.until, a.hours or 10, a.campaign, a.shinshu, a.shugeki, a.kikan)
    elif a.shushu is not None: cmd_fetch(a.campaign, a.shushu)
    elif a.cmd == "kh": cmd_kh(([a.arg] if a.arg else []) + a.more, a.machine, a.note)
    elif a.zoen is not None:
        r = transact(reinforce(a.zoen), lambda o: f"zoen {o[0]}: +{o[1]} pumps ({', '.join(o[2])})")
        print(f"ten-go: {r[0]}: +{r[1]} pumps, the parts {', '.join(r[2])} added; the watches take them up at their next claim")
    elif a.kaiso is not None:
        r = transact(refit(a.kaiso, a.dry), lambda o: f"kaiso {o[0]}: {o[2]} pumps of {o[1]} refitted ({', '.join(f'{x} -> {y}' for x, y in o[4].items())})")
        if r: print(f"ten-go: {r[0]}: {r[2]} pumps of {r[1]} refitted ({', '.join(f'{x} -> {y}' for x, y in r[4].items())}), {r[3]} held or done keep their orders; the watches take them up at their next claim")
        elif not a.dry: print(f"ten-go: --kaiso: nothing to change")
    elif a.gensoku is not None: cmd_gensoku(a.gensoku, a.hours)
    elif a.zensoku is not None: cmd_zensoku(a.zensoku)
    elif a.kaizu is not None:
        sys.path[:0] = [R("kit"), os.path.dirname(os.path.realpath(__file__))]   # the pool's kit first
        try: import tengo_kaizu
        except ImportError: die("--kaizu needs kit/tengo_kaizu.py and kit/kaizu.html in the pool")
        tengo_kaizu.serve(sys.modules[__name__], a.kaizu, a.campaign and pick(a.campaign))
    elif a.sensen is not None:
        if a.sensen.endswith(".json"): cm, seed = declare(a.sensen)
        elif a.sensen in CAMPAIGNS: cm, seed = dict(CAMPAIGNS[a.sensen](), name=a.sensen), None
        else: die(f"--sensen {a.sensen}: a spec file (.json) or a known campaign ({', '.join(CAMPAIGNS)})")
        name = cm["name"]   # declared once: its pump ids are what the allocations point to, so it is never rewritten
        def change():
            if os.path.exists(R("campaigns", name + ".json")): return None
            save(R("campaigns", name + ".json"), cm)
            if seed: seeded(cm, seed)
            return name
        new = transact(change, lambda o: f"sensen {o}: {len(cm['pumps'])} pumps")
        print(f"ten-go: campaign {name} ({cm.get('kind', 'grid')}), {len(cm['pumps'])} pumps"
              + (f", {cm['left_out']} left out as computed already" if cm.get("left_out") else "")
              + (f", {len(seed[0]['done'])} of them done (the seed, {len(seed[1])} files)" if seed else "")
              + ("" if new else ": already declared in the pool, left as it is"))
    else: die(f"unknown command {a.cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
