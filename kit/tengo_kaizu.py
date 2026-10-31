"""Ten-Go's sea chart (海図, kaizu): `ten-go --kaizu [PORT]` serves on this machine alone (http://127.0.0.1:1945/) the page kaizu.html,
which draws a campaign as a BitTorrent client draws a file: each pump a piece as wide as its estimated time on the reference machine,
done (in the colour of the machine), held by an allocation (paler; what this machine is computing in a sharp shade of its colour, as
far as it has gone), free, or past the deadline of its allocation; in the order of the campaign (its parts in their order, each in the
global order) or in the order of g.  A drag over the map, the pieces picked by a click, or a part of the list, is given a priority,
now, high, normal, low or skip (never claimed): a rule of prio/<c>.json in the pool, the last rule that matches a pump deciding, pushed
like a claim; the pieces picked can be named, a sub-campaign of the campaign, listed with the parts, its priority raised or lowered
there (the watches claim now and high at once: see press in tengo.py); the next claim of each machine is drawn as the claim would take
it (an adaptive part's new pumps aside: the rule makes them only at the claim).  A kaizu
already on the port is stopped first, and its pages reload into the new one.  Its button tassei pushes at once the pumps this machine
has done (ten-go --tassei), which a watch does within the minute a pump completes (1.38).  The dates have their Anno Fabri tags (~/bin/AF; none
where it is not), the page Ten-Go's logo (lw [[Ten-Go]], File:Ten-go-logo-0PQTC.png, small, at 200 px under the pointer).  The clone is
fetched every minute; a watch of the machine fetches it too, and the two share the clone's lock."""
import contextlib, errno, functools, http.server, io, json, os, re, secrets, shutil, signal, subprocess, threading, time, urllib.parse
from fractions import Fraction

LOCK = threading.Lock()   # one thread at a time in tengo: its lock of the clone is re-entrant within a process, not between threads
LAST = dict(fetched=0.0, lost=None)
AFX = shutil.which("AF") or shutil.which("af") or os.path.expanduser("~/bin/AF")


@functools.lru_cache(maxsize=4096)
def af(t):   # the Anno Fabri tag of the moment t (an epoch), or None: no AF on this machine, or a moment before Anno Fabri
    try: out = subprocess.run([AFX, f"@{t}"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return None
    return out if re.fullmatch(r"[0-9A-Za-z]{5,6}", out) else None


def running(W, T=None):
    """the hp3.wls front-ends running in W: [(order, pump id, seconds it has run, paused)], the time it was paused left out"""
    out = []; up = float(open("/proc/uptime").read().split()[0]); tick = os.sysconf("SC_CLK_TCK")
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            if os.readlink(f"/proc/{d}/cwd") != W: continue
            cmd = open(f"/proc/{d}/cmdline").read().split("\0"); st = open(f"/proc/{d}/stat").read()
        except OSError: continue
        if "hp3.wls" not in cmd or "wolframscript" not in os.path.basename(cmd[0]): continue
        k = cmd.index("hp3.wls")   # hp3.wls nt GA GS prec prefix_ntORDER w j:P ...
        m = re.fullmatch(r".+_nt(\d+[we]\d*)", cmd[k + 5]) if len(cmd) > k + 7 else None; j = m and re.match(r"(\d+):", cmd[k + 7])
        if j:
            f = st.rsplit(")", 1)[1].split(); gap = T.pauses(W).get((cmd[k + 5], j[1]), 0) if T else 0
            out.append((m[1], int(j[1]), up - int(f[19]) / tick - gap, f[0] == "T"))   # field 22 of stat: the start, in ticks; field 3: T, stopped
    return out


def watches():   # the pids of the watches running on this machine
    out = []
    for d in os.listdir("/proc"):
        try: cmd = open(f"/proc/{d}/cmdline").read().split("\0") if d.isdigit() else []
        except OSError: continue
        if any(x.endswith(("tengo.py", "ten-go")) for x in cmd[1:2]) and "watch" in cmd[2:]: out.append(int(d))
    return out


def holder(port):
    """the process of this user that listens on the port, (pid, command line), or None (none, or another user's)"""
    socks = set()
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        try: lines = open(f).read().splitlines()[1:]
        except OSError: continue
        for x in map(str.split, lines):
            if int(x[1].rsplit(":", 1)[1], 16) == port and x[3] == "0A": socks.add(f"socket:[{x[9]}]")   # 0A: listening
    for d in filter(str.isdigit, os.listdir("/proc")):
        try:
            if any(os.readlink(f"/proc/{d}/fd/{n}") in socks for n in os.listdir(f"/proc/{d}/fd")): return int(d), open(f"/proc/{d}/cmdline").read().split("\0")
        except OSError: continue
    return None


def gone(pid):   # the process has ended (a zombie not reaped yet: ended)
    try: return open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0] in "ZX"
    except OSError: return True


def bind(T, port, H):
    """the server on 127.0.0.1:port; a kaizu there already is stopped first (it ends the push it may be in), anything else is left be"""
    try: return http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    except OSError as e:
        if e.errno != errno.EADDRINUSE: T.die(f"--kaizu: port {port}: {e.strerror}")
    h = holder(port)
    if not h or not (any(x.endswith(("tengo.py", "ten-go")) for x in h[1][:2]) and "--kaizu" in h[1]):
        T.die(f"--kaizu: port {port} is taken, " + (f"by pid {h[0]}, not a kaizu" if h else "by another user or program") + " (--kaizu PORT for another)")
    pid = h[0]; t = time.time()
    try: os.kill(pid, signal.SIGTERM)
    except ProcessLookupError: pass
    while not gone(pid) and time.time() - t < 20: time.sleep(0.1)
    if not gone(pid): os.kill(pid, signal.SIGKILL); time.sleep(0.5)
    print(f"ten-go --kaizu: the kaizu that was on port {port} (pid {pid}) is stopped", flush=True)
    for _ in range(50):   # its socket closes as it ends
        try: return http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        except OSError: time.sleep(0.1)
    T.die(f"--kaizu: port {port} still taken after the kaizu on it stopped")


def state(T, c, hours):
    """what the page draws: the campaign c as pieces, its parts, the priorities, the machines and the next claim of each in `hours`"""
    now = time.time(); cm = T.campaign(c); A = T.allocs(c); me = T.C["machine"]; ms = sorted(os.path.basename(f)[:-5] for f in os.listdir(T.R("machines")) if f.endswith(".json"))
    ref = "azag" if "azag" in ms else me   # the widths: the costs on the reference machine, as --senkyo
    _, K = T.cost(cm, A, ref); lv = T.level(c, cm); Q = T.parts(cm); busy = T.held(A, now); rules = T.prio(c)
    done, hold, late = {}, {}, {}
    for a in A:
        for p in a["done"]: done[p] = a
    for a in A:
        if a["status"] != "open": continue
        for p in a["pumps"]:
            if p not in done: (hold if now < a["deadline"] else late).setdefault(p, a)
    prog = {}; nfz = {}   # this machine's pumps held: the part of their cost done here (files done, jobs running by their time so far); its jobs paused
    Sme, _ = T.cost(cm, A, me); O = {p[0]: p[2] for p in cm["pumps"]}
    for a in A:
        W = T.workdir(a)
        if a["machine"] != me or a["status"] != "open" or not os.path.isdir(W): continue
        R_ = running(W, T); run = {(o, j): t for o, j, t, _ in R_}; nfz[a["id"]] = sum(z for *_, z in R_)
        for p in a["pumps"]:
            if p in done: continue
            got = sum(Sme[o] if os.path.exists(f := os.path.join(W, f"{T.pre(cm, p)}_nt{o}_{p}.dat")) and os.path.getsize(f) > 1000
                      else min(run[o, p], 0.97 * Sme[o]) if (o, p) in run else 0 for o in O[p])
            if got: prog[p] = round(got / sum(Sme[o] for o in O[p]), 3)
    def status(p):
        if p in done: return "d", done[p]
        if p in hold: return "h", hold[p]
        if p in late: return "l", late[p]
        return "f", None
    pumps = []
    for p in cm["pumps"]:
        st, a = status(p[0]); L, k = lv(p); part = Q.index(T.part(cm, p[0]))
        pumps.append([p[0], part, p[1], float(Fraction(p[1])), p[2], round(K[p[0]]), st, a and a["machine"], a and a["id"], L, k, prog.get(p[0], 0)])
    machines = []
    for m in ms:
        mj = T.machine(m); S, Km = T.cost(cm, A, m); op = [a for a in A if a["machine"] == m and a["status"] == "open"]
        kern = T.kernels_now() if m == me else mj["kernels"]   # the watch keeps the drivers to it (this machine: fewer under a --gensoku)
        rest = sum(Km[p] for a in op for p in a["pumps"] if p not in done)
        take, tot, _ = T.choose(c, cm, A, m, kern, hours, cm["pumps"], busy)
        machines.append(dict(name=m, kernels=kern, full=mj["kernels"], gensoku=T.said_gensoku() if m == me else "", factor=mj.get("factor", 1.0), about=mj.get("about", ""), here=m == me,
                             speed=sum(K.values()) / max(sum(Km.values()), 1), done=sum(len(a["done"]) for a in A if a["machine"] == m),
                             kh=sum(float(e["kh"]) for e in T.ledger() if e["task"] == c and e["machine"] == m),
                             open=[dict(id=a["id"], n=len(a["pumps"]), done=len(a["done"]), kernels=a["kernels"], hours=a["hours"], created=a["created"],
                                        deadline=a["deadline"], updated=a.get("updated"), shinshu=a.get("shinshu"), shugeki=a.get("shugeki"),
                                        prio=a.get("prio"), uchikiri=a.get("uchikiri") or (m == me and os.path.exists(os.path.join(T.workdir(a), "UCHIKIRI"))),
                                        delayed=a.get("delayed"), paused=nfz.get(a["id"], 0),
                                        rest=sum(Km[p] for p in a["pumps"] if p not in done)) for a in op],
                             rest=rest, end=now + rest / kern if op else None, watch=watches() if m == me else None,
                             next=dict(pumps=take, cost=tot, hours=hours, kernels=kern)))
    head = T.git("log", "-1", "--format=%h%x09%ct%x09%s", check=False).stdout.strip().split("\t")
    count = [sum(1 for p in pumps if p[10] == k) for k in range(len(rules))]
    return dict(version=T.VERSION, machine=me, now=now, campaigns=T.campaigns(), campaign=c, about=cm.get("about", ""), ref=ref,
                ref_kernels=T.machine(ref)["kernels"], head=head, fetched=LAST["fetched"], lost=LAST["lost"],
                parts=[dict(prefix=q["prefix"], kind=q.get("kind", "grid"), base=q["base"], about=q.get("about", "")) for q in Q],
                pumps=pumps, rules=[dict(r, decides=count[k]) for k, r in enumerate(rules)], levels=list(T.LEVELS), machines=machines)


def scope(T, cm, r):   # a rule in words, and the pumps it matches
    hit = T.matcher(cm, r); n = sum(1 for p in cm["pumps"] if hit(p)); w = ", ".join(x for x in (r.get("part"), r.get("g") and f"{r['g'][0]}-{r['g'][1]} g") if x)
    return (f"sub-campaign {r['name']}, " if r.get("name") else "") + (f"{w}: " if w else "") + f"{n} pumps" + (" picked" if "pumps" in r else "")


def change_prio(T, c, op):
    """the change of prio/<c>.json for transact: add a rule (it replaces one of the same scope, or a sub-campaign of the same name: a
    sub-campaign named without pumps keeps its own, at the level given, so that it decides again), drop one (by its time and machine),
    or clear them all"""
    def change():
        cm = T.campaign(c); f = T.R("prio", c + ".json"); rules = T.prio(c)
        if op["op"] == "add":
            r = dict(op["rule"]); key = lambda x: ("name", x["name"]) if x.get("name") else (x.get("part"), x.get("g"), sorted(x.get("pumps", [])) if "pumps" in x else None)
            if "name" in r:   # a sub-campaign: pumps picked, under a name (none given: the AF tag of the moment, else s1, s2...)
                r["name"] = re.sub(r"\s+", " ", str(r["name"])).strip()[:40] or af(int(time.time())) or f"s{1 + sum(1 for x in rules if x.get('name'))}"
                old = next((x for x in rules if x.get("name") == r["name"]), None)
                if "pumps" not in r:
                    if not old: T.die(f"no sub-campaign {r['name']}")
                    r["pumps"] = old["pumps"]
                if {"part", "g"} & set(r): T.die("a sub-campaign is made of pumps picked")
            if r.get("level") not in T.LEVELS: T.die(f"no level {r.get('level')}")
            if not ({"part", "g", "pumps"} & set(r)): T.die("a rule names a part, a span of g or pumps")
            if "part" in r and r["part"] not in {q["prefix"] for q in T.parts(cm)}: T.die(f"no part {r['part']} in {c}")
            if "g" in r: lo, hi = sorted(Fraction(str(x)) for x in r["g"]); r["g"] = [T.dec(lo), T.dec(hi)]
            if "pumps" in r:
                ids = {p[0] for p in cm["pumps"]}; r["pumps"] = sorted({int(x) for x in r["pumps"]})
                if not set(r["pumps"]) <= ids: T.die("pumps that are not in the campaign")
            r = dict(level=r["level"], **{k: r[k] for k in ("name", "part", "g", "pumps") if k in r}, t=int(time.time()), by=T.C["machine"])
            rules = [x for x in rules if key(x) != key(r)] + [r]; what = f"{r['level']} {scope(T, cm, r)}"
        elif op["op"] == "drop":
            keep = [x for x in rules if (x.get("t"), x.get("by")) != (op.get("t"), op.get("by"))]
            if len(keep) == len(rules): return None
            what = "rule " + "; ".join(f"{x['level']} {scope(T, cm, x)}" for x in rules if x not in keep) + " dropped"; rules = keep
        elif op["op"] == "clear":
            if not rules: return None
            what = f"the {len(rules)} rules cleared"; rules = []
        else: T.die(f"no operation {op['op']}")
        T.save(f, dict(campaign=c, rules=rules, about="the priorities set by ten-go --kaizu: the last rule that matches a pump decides (none: normal)"))
        return what
    return change


def serve(T, port, c=None):
    here = os.path.dirname(os.path.abspath(__file__)); token = secrets.token_hex(16); boot = secrets.token_hex(4)   # boot: this run, in /state
    page = open(os.path.join(here, "kaizu.html")).read().replace("%%TOKEN%%", token).replace("%%BOOT%%", boot)
    logo = os.path.join(here, "ten-go-logo-0PQTC-200px.png"); logo = open(logo, "rb").read() if os.path.exists(logo) else None
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}   # another name would be a page of elsewhere reaching this one (DNS rebinding)
    def fetch():
        with LOCK:
            try: T.sync(); LAST.update(fetched=time.time(), lost=None)
            except SystemExit as e: LAST["lost"] = str(e)   # the network gone: the clone as it is, said on the page
    fetch(); c = c or (T.campaigns() or T.die("--kaizu: no campaign in the pool"))[0]
    def loop():
        while True: time.sleep(60); fetch()
    threading.Thread(target=loop, daemon=True).start()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def send(self, code, body, kind="application/json"):
            b = body if isinstance(body, bytes) else body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", kind if isinstance(body, bytes) else kind + "; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            if self.headers.get("Host") not in hosts: return self.send(403, {"error": "this page is served to 127.0.0.1 alone"})
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            if u.path == "/": return self.send(200, page, "text/html")
            if u.path == "/logo.png" and logo: return self.send(200, logo, "image/png")
            if u.path == "/af":   # the tags of the moments asked (?t=EPOCH,EPOCH...): {epoch: tag or null}
                return self.send(200, {t: af(int(t)) for t in q.get("t", [""])[0].split(",")[:200] if t.isdigit()})
            if u.path == "/state":
                with LOCK:
                    try: cc = q.get("c", [c])[0]; return self.send(200, dict(state(T, cc if cc in T.campaigns() else c, float(q.get("h", ["2"])[0])), boot=boot))
                    except (SystemExit, Exception) as e: return self.send(500, {"error": str(e)})
            self.send(404, {"error": "no such page"})
        def do_POST(self):   # the token of the page served here: another page of the browser cannot read it, nor send its header
            if self.headers.get("Host") not in hosts or not secrets.compare_digest(self.headers.get("X-Kaizu", ""), token):
                return self.send(403, {"error": "not from the page of this kaizu"})
            try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError: return self.send(400, {"error": "not JSON"})
            if self.path == "/sync": fetch(); return self.send(200, {"ok": True, "lost": LAST["lost"]})
            if self.path == "/tassei":   # ten-go --tassei here: the pumps this machine has done pushed to the pool now, not at the watch's next push
                with LOCK:
                    try:
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out): T.cmd_done()
                        LAST.update(fetched=time.time(), lost=None)
                        return self.send(200, {"ok": True, "said": out.getvalue().strip().removeprefix("ten-go: ") or "nothing new to push"})
                    except SystemExit as e: return self.send(400, {"error": str(e)})
                    except Exception as e: return self.send(500, {"error": f"{type(e).__name__}: {e}"})
            if self.path != "/prio": return self.send(404, {"error": "no such action"})
            cc = body.get("c", c)
            with LOCK:
                try:
                    if cc not in T.campaigns(): return self.send(400, {"error": f"no campaign {cc}"})
                    out = T.transact(change_prio(T, cc, body), lambda w: f"kaizu {cc}: {w} ({T.C['machine']})")
                    LAST.update(fetched=time.time(), lost=None)
                    return self.send(200, {"ok": True, "said": out or "nothing to change"})
                except SystemExit as e: return self.send(400, {"error": str(e)})
                except Exception as e: return self.send(500, {"error": f"{type(e).__name__}: {e}"})

    srv = bind(T, port, H)
    def end(*a):   # SIGTERM (a new kaizu on the port, or a kill): the call into tengo going on, a push maybe, ends first
        with LOCK: print(f"ten-go --kaizu: stopped (pid {os.getpid()}; a new kaizu on the port, or a kill)", flush=True); os._exit(0)
    signal.signal(signal.SIGTERM, end)
    print(f"ten-go --kaizu: the sea chart of {c} at http://127.0.0.1:{port}/ ({T.C['machine']}; Ctrl-C ends it)"
          + (f"\n  the clone could not be fetched: {LAST['lost']}" if LAST["lost"] else ""), flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print()
