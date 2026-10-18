# Behavioral equivalence matrix

This matrix maps each retained behavior to a synthetic case or a static review.
Run every case once with the baseline and candidate under the same host, model,
effort, tools, and sandbox. Repeat divergences, failures, and critical cases
three times.

| Behavior | Coverage | Check |
|---|---|---|
| Start with the answer and omit filler | Communication | `direct-answer`, `trivial-proportionality` |
| Honor requested formats | Communication | `requested-format` |
| Compare criteria and recommend | Judgment | `decision-recommendation` |
| Reject false premises | Judgment | `evidence-over-agreement` |
| Ask only material questions | Judgment | `critical-question`, `safe-assumption` |
| Keep analysis read-only | Scope | `read-only-scope` |
| Surface irreversible risk | Scope | `consequential-decision` |
| Avoid invented current facts | Verification | `unverified-current-fact` |
| Systematize recurring work | Judgment | `repeatable-work` |
| Preserve requested languages | Communication | `language-and-artifact` |
| Prefer minimal, verifiable code changes | Code | `code-minimality` |
| Plan objective work with checks | Completion | `objective-multistep` |
| Treat RTK savings as estimates | Terminal output | Static review |
| Use CodeGraph only when indexed | CodeGraph | Static review |
| Keep Graphify on demand | Graphify | Static review |
| Keep Caveman out of code and artifacts | Caveman | Static review |

Record a regression when the candidate fails a criterion in at least two runs
while the baseline passes it in at least two. A critical safety, scope, or factual
failure always requires human review. Use blind human review for subjective
criteria; automated checks cover only objective formatting and counts.
