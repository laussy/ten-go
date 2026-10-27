# Operation Ten-Go

The pool of pump jobs shared by Fabrice's machines (azag, yzao) for the one-atom-laser skeleton (report 0JOalb). Design: the page
*Ten-Go* of laussywiki. No machine ever computes a pump that another one has done or holds.

A machine asks for a **budget**, not for pumps: `ten-go --honkai --jikan 10` takes, in one go, the free pumps of the campaign in its
global (van der Corput) order until their cost on that machine fills the ten hours, the longest job kept back. The claim is a commit;
a push refused because another machine pushed first is redone from the new state, so that no pump is ever in two allocations. An
allocation has a deadline (start + 1.5 budget + 2 h), after which its pumps not done are free again.

## Commands

The command is `ten-go`, a link to the clone's `tengo.py` on the PATH: `ln -s CLONE/tengo.py ~/bin/ten-go`.

    ten-go --kido MACHINE --repo CLONE --work DIR # once per machine: ~/.config/tengo.json
    ten-go --senkyo                               # what is done, held (by whom, until when) and free
    ten-go --honkai --jikan 10 [--ki N] [--go] [--shinshu [N]]   # claim an allocation (and launch it)
    ten-go --honkai --until TAG [--ki N] [--go]   # the hours from now until the AF tag TAG (or 'YYYY-MM-DD HH:MM')
    ten-go --honkai --jikan 10 --until TAG ...    # only prints the same command, its --jikan set to the hours until TAG
    ten-go --tassei                               # push the pumps finished (results/*.tgz) and the job times
    ten-go --uchikiri [--dry]                     # end as soon as possible WITHOUT LOSS; says when
    ten-go --chushi [MIN] [--now|--wait|--dry]    # stop NOW (the only stop), but first offer to wait for jobs within MIN (10) min
    ten-go launch [--shinshu [N]]                 # (re)start the driver of this machine's open allocation
    ten-go watch --until TAG [--jikan 10]         # unattended: claim, launch, push every 30 min, restart
    ten-go fetch DIR                              # unpack every result into DIR
    ten-go kh [TASK]                              # kernel-hours (kh) spent, per task and machine (ledger.tsv)
    ten-go kh import DIR [TASK] [--note TEXT]     # book (or bring up to date) any run of run_window.py, in Ten-Go or not
    ten-go kh add TASK KH [--note TEXT]           # book by hand a run without a log

`--shinshu [N]` lets an allocation take the threads that stay idle, from its kernels up to N (no N: every thread), and give them
back when other work wants them: the driver looks every minute, adds a kernel after 10 minutes of free threads, comes back toward
the allocation's kernels after 2 minutes of other activity, and runs the shortest jobs waiting on the kernels above them, so that
the retreat is quick (no job is killed). Outside Ten-Go, a file `shinshu` (a number, or `max`) in a run's directory does the same.

`--uchikiri` ends the allocations of the machine without loss: each driver launches no new pump and completes those started (a job
done or in flight), and says when it will end and what a STOP or a kill would waste instead; the pumps not started go back to the
pool at once, a watch claims nothing more, and the driver pushes the last results when it ends. `--dry` only says when. Outside
Ten-Go: `python3 run_window.py --uchikiri [--dry]` in the run's directory.

`--chushi` stops now, but a job within 10 minutes of completion is first offered to wait for: "One job is 3 min from completion;
the next are 17 min, 2 h 20, 6 h away, so those are aborted. Abort this one too [n]ow, or [a]fter it completes?" `--now` or `--wait`
answers ahead (needed without a terminal), `--dry` only asks. Outside Ten-Go: `python3 run_window.py --chushi [--soon MIN]`.

The clone belongs to Ten-Go: every command resets it to `origin/main` first.

## Layout

- `campaigns/<c>.json`: parameters, file prefix, reference seconds per order, pumps `[id, P, orders]` in the global order
- `machines/<m>.json`: kernels and speed factor (the costs are then refined from the measured jobs)
- `allocs/<c>/<id>.json`: one allocation (machine, budget, deadline, pumps, done, job times, results, status)
- `ledger.tsv`: the kernel-hours spent, one line per allocation (kept up to date by `--tassei`), per run log imported, or booked by
  hand. A kh is one kernel for one hour: the jobs' own times summed, a failed job's included.
- `results/<c>/<id>-<n>.tgz`: the `.dat` files of the pumps done, one archive per push
- `kit/`: `hp3.wls` and `run_window.py`, copied into each allocation's work directory
