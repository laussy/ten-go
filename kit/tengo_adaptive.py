"""The rule of Ten-Go's adaptive campaigns (in the pool as kit/tengo_adaptive.py), that of code/adaptwin.py (Sec. 33 of report 0JOalb),
applied at each claim: the pumps whose 250e and 300e files are in the pool (in the machine's cache of the campaign's results) and those
still to come decide which pumps are added.  Pumps on the lattice x_J = X0 + J H0/2^LEV; certificate D (a 250e line is kept if 300e
reproduces it within EPS); the gap of Sec. 14 between consecutive pumps, a line being a source only if reproduced to SRC and its
continuation, the nearest eigenvalue at the other pump, certified too; an interval is split while gap/DELTA or width/HMAX exceeds 1,
worst first, down to the lattice step, in four rather than two when fewer intervals are open than a third of the kernels.
Needs numpy and scipy, as adaptwin.py does."""
import json, os
from fractions import Fraction
import numpy as np
from scipy.spatial import cKDTree


def loadfile(f):   # as converged.loadfile: a header "# x na", then rows gamma omega [Lp Kp]
    with open(f) as fh: head = fh.readline().split()
    d = np.loadtxt(f, comments="#", ndmin=2)
    return dict(x=float(Fraction(head[1])), gamma=d[:, 0], omega=d[:, 1], D=d[:, 0] + 1j * d[:, 1])


def cert(lo, hi, eps):   # as converged.certify for one pump: each 250e eigenvalue, its distance to the nearest 300e one, ok within eps
    r = dict(lo); r["dist"] = cKDTree(np.c_[hi["D"].real, hi["D"].imag]).query(np.c_[lo["D"].real, lo["D"].imag])[0]; r["ok"] = r["dist"] < eps
    return r


def gap(a, b, src, wmax):   # as adaptwin.gap
    g = 0.0
    for s, t in ((a, b), (b, a)):
        m = (s["dist"] < src) & (np.abs(s["omega"]) <= wmax)
        if m.any(): m[m] = t["ok"][cKDTree(np.c_[t["D"].real, t["D"].imag]).query(np.c_[s["D"][m].real, s["D"][m].imag])[1]]
        sr = np.abs(s["omega"][m]); tg = np.abs(t["omega"][t["ok"]])
        if len(sr) and len(tg): g = max(g, np.abs(sr[:, None] - tg[None, :]).min(axis=1).max())
    return g


def grow(rule, prefix, cache, known, waiting, kern):
    """the Js to add, worst interval first, and the number of intervals open: known, the Js whose 250e and 300e files are in cache;
    waiting, the Js of the campaign still to come (an interval with such an end waits).  The gaps are kept in cache/gaps.json, since
    two pumps done never change"""
    step = Fraction(rule["h0"]) / 2 ** rule["lev"]; delta, hmax = rule["delta"], rule["hmax"]
    gf = os.path.join(cache, "gaps.json"); G = json.load(open(gf)) if os.path.exists(gf) else {}; C = {}
    def c(J):
        if J not in C: C[J] = cert(loadfile(os.path.join(cache, f"{prefix}_nt250e_{J}.dat")), loadfile(os.path.join(cache, f"{prefix}_nt300e_{J}.dat")), rule["eps"])
        return C[J]
    Js = sorted(set(known) | set(waiting)); iv = []
    for J1, J2 in zip(Js, Js[1:]):
        if J1 in waiting or J2 in waiting or J2 - J1 < 2: continue
        k = f"{J1},{J2}"
        if k not in G: G[k] = gap(c(J1), c(J2), rule["src"], rule["wmax"])
        r = max(G[k] / delta, float((J2 - J1) * step) / hmax)
        if r > 1: iv.append((r, J1, J2, G[k]))
    with open(gf, "w") as f: json.dump(G, f)
    iv.sort(reverse=True); four = 3 * len(iv) < kern; new = []
    for r, J1, J2, g in iv:
        for J in ([J1 + (J2 - J1) * k // 4 for k in (1, 2, 3)] if four and J2 - J1 >= 4 and g > delta else [(J1 + J2) // 2]):
            if J not in new and J not in known and J not in waiting: new.append(J)
    return new, len(iv)
