# Ten-Go

The pool of jobs shared by my machines (azag, yzao) for a long-running task [e.g., computing the one-atom-laser skeleton, cf. 0JOalb].

A machine asks for a **budget**, not for tasks: `ten-go --honkai --jikan 10` takes, in one go, the free task of the ongoing "campaign" in its
global (van der Corput) order as long as their jobs, run on that machine the longest first, end within the ten hours. The claim is a commit;
a push refused because another machine pushed first is redone from the new state, so that no pump is ever in two allocations. An
allocation has a deadline (start + 1.5 budget + 2 h, the budget at least its longest job), after which its tasks not done are free
again.

## Commands

The command is `ten-go`, a link to the clone's `tengo.py` on the PATH: `ln -s CLONE/tengo.py ~/bin/ten-go`.

    ten-go --kido MACHINE --repo CLONE --work DIR # once per machine: ~/.config/tengo.json
    ten-go --senkyo                               # what is done, held (by whom, until when) and free
    ten-go --honkai --jikan 10 [--ki N] [--go] [--shinshu [N]] [--shugeki] [--kikan]   # claim an allocation (and launch it)
    ten-go --honkai --until TAG [--ki N] [--go]   # the hours from now until the AF tag TAG (or 'YYYY-MM-DD HH:MM')
    ten-go --honkai --jikan 10 --until TAG ...    # only prints the same command, its --jikan set to the hours until TAG
    ten-go --tassei                               # push the pumps finished (results/*.tgz) and the job times
    ten-go --uchikiri [--dry] [--nohoju]          # end as soon as possible WITHOUT LOSS (the kernels freed filled meanwhile); says when
    ten-go --gensoku N [--jikan H]                # this machine down to N kernels, until --zensoku (or for H hours)
    ten-go --zensoku [H]                          # all its kernels back, one at a time over H hours (1; 0: at once)
    ten-go --chushi [MIN] [--now|--wait|--dry]    # stop NOW (the only stop), but first offer to wait for jobs within MIN (10) min
    ten-go launch [--shinshu [N]]                 # (re)start the driver of this machine's open allocation
    ten-go watch [--until TAG] [--jikan 10]       # unattended (without --until: until the campaign is complete): claim, launch, push every 30 min, restart
                                                  # (a new version pushed to the pool takes the watch over at its next sync)
    ten-go watch --until TAG --kikan              # ends at TAG (without --kikan, it goes on past TAG with sorties)
    ten-go --shushu DIR                           # unpack every result into DIR
    ten-go --kaiso SPEC.json [--dry]              # refit a part: new orders for its pumps not held or done (e.g. 300e -> 300e80)
    ten-go --kaizu [PORT]                         # the sea chart: the campaign as pieces, and its priorities (http://127.0.0.1:1945/)
    ten-go kh [TASK]                              # kernel-hours (kh) spent, per task and machine (ledger.tsv)
    ten-go kh import DIR [TASK] [--note TEXT]     # book (or bring up to date) any run of run_window.py, in Ten-Go or not
    ten-go kh add TASK KH [--note TEXT]           # book by hand a run without a log

The time given (`--jikan`, `--until`) is a plan, not an end. An allocation runs its pumps the longest first (within a priority; each
one's jobs the longest first too), so that its time is met with the smallest last, and a claim takes as many as end within the time
in that order. Past its time the allocation goes on, but as a sortie, in prevision of an imminent uchikiri: the pumps started are
completed first, then those not started run the cheapest first, whole. A watch past its `--until` goes on likewise with sorties
(claims as `--shugeki`: the cheapest pumps first), from half an hour before, until the campaign is complete or an uchikiri by hand.
`--kikan` (帰還, the return to base) ends at the time instead: `--honkai --kikan` makes an allocation that its driver ends without
loss at its time (its own uchikiri), and `watch --until TAG --kikan` claims nothing in the last half hour, its allocations ending
without loss at TAG. Outside Ten-Go, files `jikan` and `kikan` (an epoch) in a run's directory do the same.

`--shinshu [N]` lets an allocation take the threads that stay idle, from its kernels up to N (no N: every thread), and give them
back when other work wants them: the driver looks every minute, adds a kernel after 10 minutes of free threads, comes back toward
the allocation's kernels after 2 minutes of other activity, and runs the shortest jobs waiting on the kernels above them, so that
the retreat is quick (no job is killed). Outside Ten-Go, a file `shinshu` (a number, or `max`) in a run's directory does the same.

`--gensoku N` (減速) lowers this machine to N kernels for Ten-Go, its allocations together, from now until `--zensoku` (with
`--jikan H`, for H hours): a job that ends is not replaced while N or more run (none is killed), the claims are made for N kernels,
and no idle thread is borrowed. `--zensoku [H]` (全速) gives the kernels back one at a time over H hours (1; 0: at once), as the end
of a `--gensoku --jikan` does over an hour. It is the machine's own (`gensoku.json` in its work directory, no commit), kept by its
watch and said by `--senkyo` and its kaizu; when it is set, it says when the open allocations will end, and which would miss their
deadline. The watch otherwise keeps every kernel of `machines/<m>.json` busy: an `nproc` lowered by hand is undone within a minute.

`--uchikiri` ends the allocations of the machine without loss: each driver launches no new pump and completes those started (a job
done or in flight), and says when it will end and what a STOP or a kill would waste instead; the pumps not started go back to the
pool at once, a watch claims nothing more, and the driver pushes the last results when it ends. `--dry` only says when. Outside
Ten-Go: `python3 run_window.py --uchikiri [--dry]` in the run's directory.
The kernels that free before that end are not left idle (**hoju**, 補充, since 1.34): the allocation keeps those of its small pumps
not started that, whole, end before the pumps started even at a slow time (90 % of the job times measured on the machine), and the
driver launches each as kernels free if it still ends in time then, else gives it back to the pool at once. `--nohoju` gives back
every pump not started, as before; the uchikiri a watch makes for the kaizu's high or now has no hoju (those take the kernels).

`--chushi` stops now, but a job within 10 minutes of completion is first offered to wait for: "One job is 3 min from completion;
the next are 17 min, 2 h 20, 6 h away, so those are aborted. Abort this one too [n]ow, or [a]fter it completes?" `--now` or `--wait`
answers ahead (needed without a terminal), `--dry` only asks. Outside Ten-Go: `python3 run_window.py --chushi [--soon MIN]`.

`--shugeki` (with `--honkai` or `watch`) is a sortie, for a machine that may be stopped any moment: the cheapest pumps first, run
whole one after the other, so that an uchikiri ends within a job or two and a chushi wastes little.

`--kaizu` (海図, the sea chart) serves on this machine alone (http://127.0.0.1:1945/, or `--kaizu PORT`) a page that draws the campaign
as a BitTorrent client draws a file: each pump a piece as wide as its estimated time on azag, done (in its machine's colour), held
(paler; what this machine is computing in a sharp shade of its colour, as far as it has gone), free, or past its allocation's
deadline; in the order of the campaign or of g, with the parts, the machines (allocations, end, watch) and the next claim each would
make, the dates with their Anno Fabri tags (`~/bin/AF`). A drag over the pieces, the pieces picked by a click (hpT #1951, #1949,
#1947...), or a part in the list, is given a priority, **now**, **high**, **normal**, **low** or **skip** (never claimed): a rule of
`prio/<c>.json`, pushed like a claim, the last rule that matches a pump deciding. The pieces picked can also be named, a
**sub-campaign** of the campaign, listed under the parts, whose priority is raised or lowered there. A claim takes the free pumps now
first, then high, normal, low, each in the order of the campaign (`--shugeki`: the cheapest first). The watches take normal, low and
skip up at their next claim, and what is claimed already runs on; **now** and **high** they take at once: a watch claims the pumps of
that level alone, and its allocations still launching pumps of a lower level end without loss (an uchikiri: the pumps started
complete, the others go back to the pool). The pumps of high then take the kernels as that uchikiri frees them; those of now take them
at once, the jobs of the other allocations being paused (SIGSTOP: the kernel waits in memory where it stands, nothing is lost; as many
as the memory holds) and resumed, the nearest to completion first, as the kernels come back, their paused time left out of the job
times; their deadlines are pushed back by the span of the claim of now. An uchikiri or a chushi by hand resumes the paused jobs first.
A kaizu already on the port is stopped first (it ends the push it may be in), and the pages open on it reload into the new one. Any
machine with a clone can run its own.

A campaign is declared once, by `ten-go --sensen SPEC.json`: a **grid** (lattices, orders by range of P, ranges left out, and the runs
already computed, whose pumps are left out, read from each file's header) or an **adaptive** campaign (the rule of the adaptive
driver, `kit/tengo_adaptive.py`, applied at each claim to the results in the pool, so that its pumps grow as the results come; it
starts from the runs it names, whose files enter the pool as the results of an allocation `seed`). Short claims suit an adaptive
campaign, refined only when a claim is made.
A campaign in **parts** joins several (each its own kind and file prefix); a claim takes from the parts in their order. The
first, `uijin` (`specs/uijin.json`): the 4 pumps of the adaptive run left half done, a probe of the lines that jump at
5.2085 g below the lattice step (and once at 80 digits), a study of the working precision (`hpR`, `hpS`: 40 to 320 digits), then the boiling window at 0.08 g, and the close grid at
0.004 g as a filler, added later by `ten-go --zoen SPEC.json`, and refitted to 80 digits by `ten-go --kaiso SPEC.json` once the
study showed 40 digits wrong for some lines with gamma >= 6.5 g (its pumps done at 40 digits redone at 80 at the end). Parts may
also be explicit lists. `watch` without `--until`
runs until the campaign is complete.

The clone belongs to Ten-Go: every command resets it to `origin/main` first.

## Layout

- `campaigns/<c>.json`: parameters, file prefix, reference seconds per order, pumps `[id, P, orders]` in the global order (an
  adaptive campaign: its rule too, and pumps that grow at each claim)
- `machines/<m>.json`: kernels and speed factor (the costs are then refined from the measured jobs)
- `allocs/<c>/<id>.json`: one allocation (machine, budget, deadline, pumps, done, job times, results, status)
- `ledger.tsv`: the kernel-hours spent, one line per allocation (kept up to date by `--tassei`), per run log imported, or booked by
  hand. A kh is one kernel for one hour: the jobs' own times summed, a failed job's included.
- `results/<c>/<id>-<n>.tgz`: the `.dat` files of the pumps done, one archive per push
- `prio/<c>.json`: the priorities set in `--kaizu`, rules (a part, a span of g, or pumps picked, these maybe named: a sub-campaign; a
  level), the last that matches deciding
- `kit/`: `hp3.wls` and `run_window.py`, copied into each allocation's work directory; `tengo_adaptive.py`, the rule of the adaptive
  campaigns (needs numpy and scipy); `tengo_kaizu.py` and `kaizu.html`, the sea chart, with
  `ten-go-logo-0PQTC-200px.png`, the logo (Ten-go-logo-0PQTC.png) at 200 px
