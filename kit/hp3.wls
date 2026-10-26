(* High-precision spectral structure of the dissipative JC model (cavity emission).
   Usage: wolframscript -file hp2.wls nt ga gs prec outprefix withWeights "i1:P1,i2:P2,..." [scan]
   scan = "Ps" (default): the list gives P_sigma values; scan = "ga": the list gives gamma_a values (then arg ga is ignored, Ps = gs-arg?? no:)
   For scan = "ga": args are  nt Ps gs prec outprefix withWeights list  (Ps in place of ga).
   One file per value: outprefix_<i>.dat, header "# x= na=", rows: gamma_p omega_p [Lp Kp]. *)
args = Rest[$ScriptCommandLine];
nt = ToExpression[args[[1]]]; par1 = ToExpression[args[[2]]]; gs = ToExpression[args[[3]]];
prec = ToExpression[args[[4]]]; out = args[[5]]; withW = ToExpression[args[[6]]];
list = (StringSplit[#, ":"] & /@ StringSplit[args[[7]], ","]);
scan = If[Length[args] >= 8, args[[8]], "Ps"];
trunc = If[Length[args] >= 9, args[[9]], "manifold"];
g = 1; Pa = 0;
states = If[trunc == "photon", Flatten[Table[{n, i}, {n, 0, nt}, {i, 0, 1}], 1], Flatten[Table[If[n + i <= nt, {n, i}, Nothing], {n, 0, nt}, {i, 0, 1}], 1]];
d = Length[states]; pos = Association[Thread[states -> Range[d]]];
a = SparseArray[Flatten[Table[If[st[[1]] >= 1, {pos[{st[[1]] - 1, st[[2]]}], pos[st]} -> Sqrt[st[[1]]], Nothing], {st, states}]], {d, d}];
s = SparseArray[Flatten[Table[If[st[[2]] == 1, {pos[{st[[1]], 0}], pos[st]} -> 1, Nothing], {st, states}]], {d, d}];
Id = IdentityMatrix[d, SparseArray];
H = g (Transpose[a].s + a.Transpose[s]);
lind[c_] := Module[{cdc = Transpose[c].c}, 1/2 (2 KroneckerProduct[c, c] - KroneckerProduct[cdc, Id] - KroneckerProduct[Id, Transpose[cdc]])];
Lham = -I (KroneckerProduct[H, Id] - KroneckerProduct[Id, Transpose[H]]);
La = lind[a]; Ls = lind[s]; LPs = lind[Transpose[s]];
Nex = Total /@ states;
idx1 = Flatten[Table[If[Nex[[k]] - Nex[[l]] == 1, (k - 1) d + l, Nothing], {k, d}, {l, d}]];
idx0 = Flatten[Table[If[Nex[[k]] == Nex[[l]], (k - 1) d + l, Nothing], {k, d}, {l, d}]];
kl1 = Table[{Quotient[j - 1, d] + 1, Mod[j - 1, d] + 1}, {j, idx1}];
kl0 = Table[{Quotient[j - 1, d] + 1, Mod[j - 1, d] + 1}, {j, idx0}];
ph = Table[I^(states[[kl[[1]], 1]] - states[[kl[[2]], 1]]), {kl, kl1}];
avec = Table[a[[kl1[[j, 2]], kl1[[j, 1]]]]/ph[[j]], {j, Length[kl1]}];
trrow = Table[If[kl[[1]] == kl[[2]], 1, 0], {kl, kl0}];
nvec = Table[If[kl[[1]] == kl[[2]], states[[kl[[1]], 1]], 0], {kl, kl0}];
Do[
  i = item[[1]]; x = Rationalize[ToExpression[item[[2]]], 0];
  If[scan == "Ps", ga = par1; Ps = x, Ps = par1; ga = x];
  L = Lham + ga La + gs Ls + Ps LPs;
  L1 = Normal[L[[idx1, idx1]]];
  L1r = DiagonalMatrix[ph].L1.DiagonalMatrix[1/ph];
  L1n = N[L1r, prec];
  imax = Max[Abs[Im[L1n]]];
  If[imax > 10^(-prec/2), Print["WARNING: not real, max Im = ", imax]];
  L1n = Re[L1n];
  t0 = AbsoluteTime[];
  If[withW == 1,
    L0 = N[Normal[L[[idx0, idx0]]], prec];
    rhs = Join[ConstantArray[0, Length[idx0]], {1}];
    rho0 = LeastSquares[Join[L0, {trrow}], rhs];
    na = Re[nvec.rho0];
    rho = SparseArray[Thread[kl0 -> rho0], {d, d}];
    chi = (rho.Transpose[a]);
    chi0 = Table[chi[[kl1[[j, 1]], kl1[[j, 2]]]] ph[[j]], {j, Length[kl1]}];
    {vals, vecs} = Eigensystem[L1n];
    V = Transpose[vecs];
    c = LinearSolve[V, chi0];
    trc = avec.V;
    w = c trc/na;
    Dp = -vals;
    Export[out <> "_" <> i <> ".dat", Join[{{"#", x, na}}, Transpose[{Re[Dp], Im[Dp], Re[w], Im[w]}]], "Table"];
    Print[i, " x=", N[x], " nt=", nt, " na=", na, " sumL=", Total[Re[w]], " t=", AbsoluteTime[] - t0],
    vals = Eigenvalues[L1n];
    Dp = -vals;
    Export[out <> "_" <> i <> ".dat", Join[{{"#", x, -1}}, Transpose[{Re[Dp], Im[Dp]}]], "Table"];
    Print[i, " x=", N[x], " nt=", nt, " t=", AbsoluteTime[] - t0]
  ], {item, list}];
