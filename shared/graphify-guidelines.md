# Graphify

Use the installed Graphify skill only when the user invokes `$graphify` or
explicitly asks for a broad architectural knowledge graph spanning code,
documentation, papers, images, or diagrams.

When `graphify-out/graph.json` already exists and Graphify is in scope, prefer
focused `graphify query`, `graphify path`, or `graphify explain` calls over
reading the complete report or scanning the complete corpus.

Keep CodeGraph as the default for precise source-code navigation, symbols,
callers, callees, dependencies, and implementation impact. Use Graphify for
broader cross-source architecture and exploration. Do not run both for the same
question unless the first tool lacks sufficient evidence.

Do not initialize, rebuild, watch, or refresh a Graphify graph without the
user's request. Graphify is on demand, not an always-on replacement for ordinary
repository tools or CodeGraph.
