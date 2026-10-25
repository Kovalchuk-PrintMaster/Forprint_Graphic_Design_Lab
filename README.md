# ForPrint Graphic Design Lab — independent F1 pilot

Autonomous R&D laboratory; not a production-ready Prepress Hub service.
Owner determines lab priorities and accepts lab demonstrations.
No Blueprint approval is needed for isolated synthetic lab experiments;
production integration requires its own separate review.

## Active functional goal
Run F1 on Illustrator, return native editable AI + PDF + PNG,
open and edit text in AI, save and reopen, record visual acceptance.
Legacy W2 helpers are imported unchanged to preserve previously tested behavior.
Host Registry, multi-host abstraction, web admin, and additional apps come later.

## Constraints
Synthetic-only inputs. No automatic retries, remote writes, customer dispatch,
or Windows execution during this bootstrap. Do not run old one-use task IDs.
The prior Prepress Hub GC16–GC18 working tree is untouched.

Run `make f1-source-check PYTHON=/path/to/python` and
`make f1-test PYTHON=/path/to/python`.
See `coordination/lab/f1_import_manifest_v0_1.json` for evidence.
