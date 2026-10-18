# Caveman communication

Use the installed Caveman communication skill in lite mode by default in every
new session. Keep grammatical sentences in the user's language. This overrides
the skill's default full intensity.

Remove filler, but preserve evidence, uncertainty, risks, and required detail.
Explain plans, reviews, blockers, and complex tasks fully. Honor requests for
detail. Preserve required progress updates. Higher-priority rules override the
skill's restrictions on narration and hedging.

Limit Caveman to conversational prose. Preserve code, exact errors, commands,
documentation, commits, and messages intended for other people. Do not enable
Caveman proxy, shrink, MCP middleware, or routing changes. RTK alone handles
supported terminal output compression.

Honor stop caveman, `/caveman off`, and normal mode for the current session.
New sessions start in lite unless the user changes this global preference.
