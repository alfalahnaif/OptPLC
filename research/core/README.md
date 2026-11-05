# nuXmv witness extraction (research only)

`nuxmv_witness.py` parses textual LTL verdicts and counterexamples without an LLM or changes to the OptPLC application workflow. `extract_witnesses.py` handles one log; `extract_pilot_witnesses.py` handles only manifest-designated canonical ELCON G3 runs. The October pilot text files remain the source of record.

## Run

From the repository root, with the G3 results available at `research/elcon2027/results`:

```powershell
python -m research.core.extract_pilot_witnesses --manifest research/elcon2027/witness_manifest.json --results-root research/elcon2027/results --output-root research/elcon2027/witnesses
python -m pytest research/tests -q
```

For a single log, provide two JSON objects: a map from each exact nuXmv specification text to its property ID, and a map from each trace variable to `input`, `output`, or `state`:

```powershell
python -m research.core.extract_witnesses raw.txt --case-id E27-I01 --mutant-id I-M4 --property-map properties.json --roles roles.json --output witness.json
```

Whitespace runs in specification keys are collapsed, but formulas are otherwise matched literally. Unknown property IDs and variable roles cause errors. The ELCON mappings are in `research/elcon2027/witness_config.json` and correspond to the named `LTLSPEC` declarations in the pilot SMV models.

## Canonical experiment manifest

`research/elcon2027/witness_manifest.json` is the experiment inventory. Its `schema_version` is `1`, and each `runs` entry supplies `case_id`, `mutant_id` (`reference` for a reference run), `log_path` relative to `--results-root`, `property_set` (a key in `witness_config.json`), a Boolean `canonical`, and an optional `expected_source_sha256`. The pilot manifest pins the byte hash of every listed log.

The batch tool parses only `canonical: true` entries. It rejects duplicate log paths, duplicate canonical `(case_id, mutant_id)` pairs, missing canonical files, mismatched canonical source hashes, and incomplete property sets. It never chooses a substitute by searching the directory. Manifest entries with `canonical: false` may share an identity with a canonical entry; their raw logs remain historical evidence and are excluded from extraction and metrics. In the pilot manifest, 21 entries are canonical (3 references and 18 mutants). The two older `E27-M01_G3_M-M1.txt` and `E27-M01_G3_M-M3.txt` entries are historical. Their hashes are recorded in the manifest but the batch tool does not read or verify non-canonical files.

The generated `canonical_index.json` has one `verdicts` row per canonical property verdict, with case, mutant, property set, property ID, status, source path and hash, and witness JSON path. The separate `run_summary.json` has one row per canonical run and these distinct totals: `number_of_runs`, `number_of_properties_checked`, `number_of_runs_with_violation`, `number_of_property_violations`, and `number_of_unique_mutants_with_violation`. A property is counted as checked only when its status is `SATISFIED` or `VIOLATED`; references are excluded from the unique-mutant count. Both files carry the manifest byte hash. These index and summary files define the canonical dataset; directory contents do not.

## JSON schema

Each output file is an array with one witness record per property verdict. A record has `case_id`, `mutant_id`, `property_id`, `specification`, `verification_status` (`SATISFIED`, `VIOLATED`, `ERROR`, or `UNKNOWN`), `tool`, `tool_version`, `source_output_path`, `source_encoding`, `source_sha256`, `raw_source`, `steps`, and `transitions`.

`raw_source` is the complete decoded log, including original line endings. `source_sha256` hashes the original file bytes, including its BOM. The pilot logs use UTF-16 with a BOM; the loader also accepts UTF-8 with or without a BOM. In the canonical corpus, `source_output_path` is relative to the manifest's results root.

Each step has a zero-based `index`, original `nuxmv_state` label, `inputs`, `outputs`, `state`, `changed_variables`, `observed_variables`, `carried_variables`, and `loop_start`. `inputs`/`outputs`/`state` contain the full known valuation at that step. `observed_variables` names assignments printed at that step; `carried_variables` names values carried from an earlier state because nuXmv omitted unchanged assignments. `changed_variables` names variables whose value differs from the preceding step; it is empty for the first step. Boolean `TRUE`/`FALSE` become JSON booleans. Other values stay as original strings, including numbers and enum literals.

`transitions` records consecutive step edges and, where nuXmv marks a loop, the edge from the last step back to `loop_start`. A satisfied property has empty `steps` and `transitions`. An explicit error or unknown verdict has no fabricated trace. A run-level error requires the caller to provide a `__run__` property ID.

## Supported and unsupported output

The parser supports nuXmv's textual `Trace Type: Counterexample`, `-> State: n.m <-`, sparse assignments, and one lasso loop marker. It requires all variables later mentioned to appear in the initial state. It fails explicitly on malformed assignments, new variables after the initial state, duplicate or missing verdicts, unexpected trace lines, and unknown roles or property IDs.

It does not parse XML traces, separate `-> Input:` blocks, multiple loops in one trace, or partial initial valuations. It does not interpret non-Boolean values or infer signals absent from the log. It does not implement distinguishing traces or intent refinement.

The next research stage can consume the generated JSON records directly and use `steps`, `transitions`, and `source_sha256` to replay or compare candidate behavior against the original evidence.
