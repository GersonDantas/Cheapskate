# CodeGraph

When a repository root contains `.codegraph/`, use CodeGraph before broad text
or file searches for architecture, symbol relationships, callers, callees, and
impact analysis. Prefer `codegraph_explore` when available; otherwise use
`codegraph explore "<question>"`.

If `.codegraph/` is absent, use ordinary repository tools and do not initialize
an index without the user's request.
