# Operation Ten-Go

The pool of pump jobs shared by Fabrice's machines (azag, yzao) for the one-atom-laser skeleton (report 0JOalb). Design: the page
*Ten-Go* of laussywiki. No machine ever computes a pump that another one has done or holds.

A machine asks for a **budget**, not for pumps: `ten-go claim --hours 10` takes, in one go, the free pumps of the campaign in its
global (van der Corput) order until their cost on that machine fills the ten hours, the longest job kept back. The claim is a commit;
a push refused because another machine pushed first is redone from the new state, so that no pump is ever in two allocations. An
allocation has a deadline (start + 1.5 budget + 2 h), after which its pumps not done are free again.

## Commands

The command is `ten-go`, a link to the clone's `tengo.py` on the PATH: `ln -s CLONE/tengo.py ~/bin/ten-go`.

    ten-go init MACHINE --repo CLONE --work DIR   # once per machine: ~/.config/tengo.json
    ten-go status                                 # what is done, held (by whom, until when) and free
    ten-go claim --hours 10 [--kernels N] [--go]
    ten-go claim --until TAG [--kernels N] [--go]   # the hours from now until the AF tag TAG (or 'YYYY-MM-DD HH:MM')
    ten-go claim --hours 10 --until TAG ...       # only prints the same command, its --hours set to the hours until TAG
    ten-go done                                   # push the pumps finished (results/*.tgz) and the job times
    ten-go release                                # stop this machine's jobs, push what is done, free the rest
    ten-go launch                                 # (re)start the driver of this machine's open allocation
    ten-go watch --until TAG [--hours 10]         # unattended: claim, launch, push every 30 min, restart
    ten-go fetch DIR                              # unpack every result into DIR

The clone belongs to Ten-Go: every command resets it to `origin/main` first.

## Layout

- `campaigns/<c>.json`: parameters, file prefix, reference seconds per order, pumps `[id, P, orders]` in the global order
- `machines/<m>.json`: kernels and speed factor (the costs are then refined from the measured jobs)
- `allocs/<c>/<id>.json`: one allocation (machine, budget, deadline, pumps, done, job times, results, status)
- `results/<c>/<id>-<n>.tgz`: the `.dat` files of the pumps done, one archive per push
- `kit/`: `hp3.wls` and `run_window.py`, copied into each allocation's work directory
