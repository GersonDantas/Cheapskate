# Cheapskate

Cheapskate is a reproducible configuration and evaluation toolkit for reducing
avoidable context in Codex and Claude Code. It combines concise shared
instructions with clearly separated integrations for terminal output and code
navigation.

Cheapskate is currently an implementation candidate. It does not yet claim a
percentage reduction in total tokens or provider billing. Those claims require
the controlled, versioned evaluation described below.

<p align="center">
  <a href="https://ko-fi.com/gerson_dantas" target="_blank" rel="noopener noreferrer">
    <img src="https://github.com/GersonDantas/img/blob/b81c0ba4adb694a7a65a91f64f7a1670d4d5c101/qrcode.png" alt="Buy Me a Coffee" height="200">
  </a>
</p>

<p align="center">Enjoying Cheapskate? Support the project with a coffee ☕</p>

## Current scope

- Shared working and coding instructions.
- RTK terminal-output policy.
- Caveman lite conversational policy without proxy or middleware compression.
- CodeGraph routing for repositories that already contain an index.
- Explicit, on-demand Graphify routing for broad cross-source exploration.
- Generated adapters for Codex, Claude Code, and generic hosts.
- Public synthetic evaluation cases and private real-prompt collection.
- A reproducible baseline for before-and-after comparisons.

The macOS installer and dependency manifest support diagnosis, installation,
audit, update, rollback, and removal. Plugin packaging and an independent
installation validation remain scheduled before publication.

## macOS installation

Requires Python 3.11+. Preview the plan, then apply it:

```sh
python3 scripts/cheapskate.py install --dry-run
python3 scripts/cheapskate.py install
python3 scripts/cheapskate.py check
```

The complete profile installs missing dependencies with pinned hashes, migrates
recognized RTK hooks, and registers CodeGraph MCP. Existing instructions and
unrelated configuration are preserved. Use `--instructions-only` for the
instruction profile and `--with-team` for the optional Personal Agent Team.

See [installation and recovery](docs/installation.md) for prerequisites,
confirmation, version handling, runtime limitations, audit, and rollback.

## Repository layout

```text
shared/                 Portable source of behavioral instructions
codex/                  Generated Codex bundle and host-specific rules
claude/                 Generated Claude imports and host-specific rules
generic/                Generated bundle for hosts without imports
scripts/                Generation and evaluation commands
evals/baseline/         Public immutable comparison baseline
evals/synthetic.jsonl   Public evaluation cases
evals/local/            Private ignored prompts and run artifacts
docs/                   Architecture and decision records
```

## Generate adapters

Edit files in `shared/`, `codex/rtk-guidelines.md`, or
`claude/host-guidelines.md`, then run:

```sh
sh scripts/sync-instructions.sh
```

Commit the generated adapters with their sources. CI will later verify that they
remain synchronized.

## Preview the evaluation suite

The default command performs no provider calls:

```sh
python3 scripts/eval-suite.py
```

Run a selected public case only after reviewing the reported provider-call
count:

```sh
python3 scripts/eval-suite.py \
  --ids direct-answer \
  --hosts codex,claude \
  --run --max-calls 4 --timeout 75
```

The suite keeps model, effort, tools, and sandbox equal within each before/after
pair. It alternates execution order across pairs. Use the raw usage returned by
each host; keep RTK output estimates separate from provider token usage.

Runs retain per-arm metadata, raw events and partial failures in the private
output directory. A client failure does not prevent reporting the other client.
The default cap is eight planned client inference executions; client-internal
provider retries are outside this cap. See the
[benchmark protocol](docs/benchmark-protocol.md) for interpretation, quality
review and the distinction between text evaluation and full-tool scenarios.

The default evaluation settings are `gpt-6-sol` with medium effort for Codex and
the Claude Code `sonnet` alias with medium effort. Override them with
`CODEX_EVAL_MODEL`, `CODEX_EVAL_EFFORT`, `CLAUDE_EVAL_MODEL`, and
`CLAUDE_EVAL_EFFORT`. Reports intended for comparison or review must record an
exact resolved model rather than relying only on a moving alias.

## Private real prompts

Create a local preview from recent completed sessions:

```sh
python3 scripts/collect-real-prompts.py
```

The collector does not call a model. It redacts common secret and identifier
patterns, flags named references for human review, limits prompt length, and
writes mode `0600` files under ignored `evals/local/`.

Review every generated item and select five to ten IDs. A real-prompt run also
requires the exact digest of the reviewed file:

```sh
python3 scripts/eval-suite.py \
  --source real \
  --ids codex-01,claude-01 \
  --approve-sha REVIEWED_SHA256 \
  --run
```

Changing the preview changes the digest and invalidates approval.

## Interpreting results

Compare more than response length:

- input, cached input, reasoning, and output tokens when exposed by the host;
- correct task completion;
- formatting and language requirements;
- unsupported claims and scope expansion;
- duration, failures, and repeated work;
- graph creation or synchronization cost when graph tools are evaluated.

Run every synthetic case once. Repeat divergences, failures, and critical cases
three times. Subjective quality requires blind human review. Do not add RTK,
Caveman, CodeGraph, or Graphify percentages together.

## Design boundaries

- RTK handles supported terminal output. Caveman handles conversational prose.
- CodeGraph is the default for precise code relationships only when indexed.
- Graphify is explicit and on demand for broad cross-source knowledge graphs.
- Cheapskate does not initialize graph indexes without the user's request.
- Personal Agent Team is optional and owns its own models, workflows, triggers,
  permissions, contracts, and limits.
- Credentials, sessions, caches, histories, private prompts, and local indexes
  never belong in this repository.

See [architecture](docs/architecture.md) and
[decision record](docs/decisions.md) for the rationale.

## Project status

The repository is moving from the historical `0.0.1` instruction set toward a
macOS-first release candidate. The installer has isolated tests; independent
installation, runtime hook validation, benchmarks, and publication remain.
