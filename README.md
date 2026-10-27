# Ten-Go

The pool of jobs shared by my machines (azag, yzao) for a long-running task [e.g., computing the one-atom-laser skeleton, cf. 0JOalb].

A machine asks for a **budget**, not for tasks: `tengo claim --hours 10` takes, in one go, the free task of the ongoing "campaign" in its
global (van der Corput) order until their cost on that machine fills the ten hours, the longest job kept back. The claim is a commit;
a push refused because another machine pushed first is redone from the new state, so that no pump is ever in two allocations. An
allocation has a deadline (start + 1.5 budget + 2 h), after which its tasks not done are free again.

## Commands

    python3 tengo.py init MACHINE --repo CLONE --work DIR   # once per machine: ~/.config/tengo.json
    python3 tengo.py status                                 # what is done, held (by whom, until when) and free
    python3 tengo.py claim --hours 10 [--kernels N] [--launch]
    python3 tengo.py done                                   # push the pumps finished (results/*.tgz) and the job times
    python3 tengo.py release                                # stop this machine's jobs, push what is done, free the rest
    python3 tengo.py launch                                 # (re)start the driver of this machine's open allocation
    python3 tengo.py watch --until 'YYYY-MM-DD HH:MM' [--hours 10]   # unattended: claim, launch, push every 30 min, restart
    python3 tengo.py fetch DIR                              # unpack every result into DIR

The clone belongs to tengo: every command resets it to `origin/main` first.

## Layout

- `campaigns/<c>.json`: parameters, file prefix, reference seconds per order, pumps `[id, P, orders]` in the global order
- `machines/<m>.json`: kernels and speed factor (the costs are then refined from the measured jobs)
- `allocs/<c>/<id>.json`: one allocation (machine, budget, deadline, pumps, done, job times, results, status)
- `results/<c>/<id>-<n>.tgz`: the `.dat` files of the pumps done, one archive per push
- `kit/`: `hp3.wls` and `run_window.py`, copied into each allocation's work directory
