# Executed checks and their scope

`clean-comparison.json` records two completed 44-step campaigns on the same 27
Python files, 51 test methods per campaign, comparison of 44 regenerated result
JSON files, 25 CSV files, 1,409 cases, and the 50-page manuscript rebuild. Only the
listed timing/memory fields are excluded; preparation CPU is explicitly included
in that list. The complete raw second-run accounting is in
`clean-reproduction.json`, with `clean-scaling-samples.csv` and regenerated clean
paper inputs. `clean-unit-tests.txt` is the actual clean test log. The author run
was resumed after two interrupted outer batches; completed-step CPU totals do
not cover their partial executions. The clean campaign ran continuously.

`obstruction-format-before.txt` is an actual isolated pre-repair probe of the
selection-problem header. The new unit tests check explicit format rejection and
that an unexpected RuntimeError still propagates. `reference-consistency.json`
checks 38 distinct used keys and reading-scope records; it is not a network or
whole-paper audit. `pdf-inspection.json` records the final 50-page inspection.
The main experiment records and logs are under ../results/.
