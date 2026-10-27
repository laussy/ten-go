"""Ten-Go's sea chart (海図, kaizu): `ten-go --kaizu [PORT]` serves on this machine alone (http://127.0.0.1:1945/) the page kaizu.html,
which draws a campaign as a BitTorrent client draws a file: each pump a piece as wide as its estimated time on the reference machine,
done (in the colour of the machine), held by an allocation (paler; the pumps of this machine's jobs running filled as far as they have
gone), free, or past the deadline of its allocation; in the order of the campaign (its parts in their order, each in the global order)
or in the order of g.  A drag over the map, or a part of the list, is given a priority, high, normal, low or skip (never claimed): a rule
of prio/<c>.json in the pool, the last rule that matches a pump deciding, pushed like a claim; the next claim of each machine is drawn as
the claim would take it (an adaptive part's new pumps aside: the rule makes them only at the claim).  The clone is fetched every
minute; a watch of the machine fetches it too, and the two share the clone's lock."""
import http.server, json, os, re, secrets, threading, time, urllib.parse
from fractions import Fraction

LOCK = threading.Lock()   # one thread at a time in tengo: its lock of the clone is re-entrant within a process, not between threads
LAST = dict(fetched=0.0, lost=None)


def running(W):
    """the hp3.wls front-ends running in W: [(order, pump id, seconds since it started)]"""
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
        if j: out.append((m[1], int(j[1]), up - int(st.rsplit(")", 1)[1].split()[19]) / tick))   # field 22 of stat: the start, in ticks
    return out


def watches():   # the pids of the watches running on this machine
    out = []
    for d in os.listdir("/proc"):
        try: cmd = open(f"/proc/{d}/cmdline").read().split("\0") if d.isdigit() else []
        except OSError: continue
        if any(x.endswith(("tengo.py", "ten-go")) for x in cmd[1:2]) and "watch" in cmd[2:]: out.append(int(d))
    return out


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
    prog = {}   # this machine's pumps held: the part of their cost done here (files done, jobs running by their time so far)
    Sme, _ = T.cost(cm, A, me); O = {p[0]: p[2] for p in cm["pumps"]}
    for a in A:
        W = T.workdir(a)
        if a["machine"] != me or a["status"] != "open" or not os.path.isdir(W): continue
        run = {(o, j): t for o, j, t in running(W)}
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
        rest = sum(Km[p] for a in op for p in a["pumps"] if p not in done); kern = mj["kernels"]   # the watch keeps the drivers to it
        take, tot, _ = T.choose(c, cm, A, m, mj["kernels"], hours, cm["pumps"], busy)
        machines.append(dict(name=m, kernels=mj["kernels"], factor=mj.get("factor", 1.0), about=mj.get("about", ""), here=m == me,
                             speed=sum(K.values()) / max(sum(Km.values()), 1), done=sum(len(a["done"]) for a in A if a["machine"] == m),
                             kh=sum(float(e["kh"]) for e in T.ledger() if e["task"] == c and e["machine"] == m),
                             open=[dict(id=a["id"], n=len(a["pumps"]), done=len(a["done"]), kernels=a["kernels"], hours=a["hours"], created=a["created"],
                                        deadline=a["deadline"], updated=a.get("updated"), shinshu=a.get("shinshu"), shugeki=a.get("shugeki"),
                                        rest=sum(Km[p] for p in a["pumps"] if p not in done)) for a in op],
                             rest=rest, end=now + rest / kern if op else None, watch=watches() if m == me else None,
                             next=dict(pumps=take, cost=tot, hours=hours, kernels=mj["kernels"])))
    head = T.git("log", "-1", "--format=%h%x09%ct%x09%s", check=False).stdout.strip().split("\t")
    count = [sum(1 for p in pumps if p[10] == k) for k in range(len(rules))]
    return dict(version=T.VERSION, machine=me, now=now, campaigns=T.campaigns(), campaign=c, about=cm.get("about", ""), ref=ref,
                ref_kernels=T.machine(ref)["kernels"], head=head, fetched=LAST["fetched"], lost=LAST["lost"],
                parts=[dict(prefix=q["prefix"], kind=q.get("kind", "grid"), base=q["base"], about=q.get("about", "")) for q in Q],
                pumps=pumps, rules=[dict(r, decides=count[k]) for k, r in enumerate(rules)], levels=list(T.LEVELS), machines=machines)


def scope(T, cm, r):   # a rule in words, and the pumps it matches
    hit = T.matcher(cm, r); n = sum(1 for p in cm["pumps"] if hit(p)); w = ", ".join(x for x in (r.get("part"), r.get("g") and f"{r['g'][0]}-{r['g'][1]} g") if x)
    return (f"{w}: " if w else "") + f"{n} pumps" + (" picked" if "pumps" in r else "")


def change_prio(T, c, op):
    """the change of prio/<c>.json for transact: add a rule (it replaces one of the same scope), drop one (by its time and machine), or
    clear them all"""
    def change():
        cm = T.campaign(c); f = T.R("prio", c + ".json"); rules = T.prio(c)
        if op["op"] == "add":
            r = op["rule"]; key = lambda x: (x.get("part"), x.get("g"), sorted(x.get("pumps", [])) if "pumps" in x else None)
            if r.get("level") not in T.LEVELS: T.die(f"no level {r.get('level')}")
            if not ({"part", "g", "pumps"} & set(r)): T.die("a rule names a part, a span of g or pumps")
            if "part" in r and r["part"] not in {q["prefix"] for q in T.parts(cm)}: T.die(f"no part {r['part']} in {c}")
            if "g" in r: lo, hi = sorted(Fraction(str(x)) for x in r["g"]); r["g"] = [T.dec(lo), T.dec(hi)]
            if "pumps" in r:
                ids = {p[0] for p in cm["pumps"]}; r["pumps"] = sorted({int(x) for x in r["pumps"]})
                if not set(r["pumps"]) <= ids: T.die("pumps that are not in the campaign")
            r = dict(level=r["level"], **{k: r[k] for k in ("part", "g", "pumps") if k in r}, t=int(time.time()), by=T.C["machine"])
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
    here = os.path.dirname(os.path.abspath(__file__)); token = secrets.token_hex(16)
    page = open(os.path.join(here, "kaizu.html")).read().replace("%%TOKEN%%", token)
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
            b = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", kind + "; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            if self.headers.get("Host") not in hosts: return self.send(403, {"error": "this page is served to 127.0.0.1 alone"})
            u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
            if u.path == "/": return self.send(200, page, "text/html")
            if u.path == "/state":
                with LOCK:
                    try: cc = q.get("c", [c])[0]; return self.send(200, state(T, cc if cc in T.campaigns() else c, float(q.get("h", ["2"])[0])))
                    except (SystemExit, Exception) as e: return self.send(500, {"error": str(e)})
            self.send(404, {"error": "no such page"})
        def do_POST(self):   # the token of the page served here: another page of the browser cannot read it, nor send its header
            if self.headers.get("Host") not in hosts or not secrets.compare_digest(self.headers.get("X-Kaizu", ""), token):
                return self.send(403, {"error": "not from the page of this kaizu"})
            try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError: return self.send(400, {"error": "not JSON"})
            if self.path == "/sync": fetch(); return self.send(200, {"ok": True, "lost": LAST["lost"]})
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

    try: srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    except OSError as e: T.die(f"--kaizu: port {port}: {e.strerror} (a kaizu running already? --kaizu PORT for another)")
    print(f"ten-go --kaizu: the sea chart of {c} at http://127.0.0.1:{port}/ ({T.C['machine']}; Ctrl-C ends it)"
          + (f"\n  the clone could not be fetched: {LAST['lost']}" if LAST["lost"] else ""), flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print()
