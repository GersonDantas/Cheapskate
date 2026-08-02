# Code guidelines

Favor the smallest safe change that produces a verifiable result.

- State material assumptions before implementation. Ask only when unresolved ambiguity could change the solution or risk; otherwise proceed with the safest reasonable interpretation.
- Reuse an existing project pattern, standard library feature, native platform capability, or installed dependency before adding code or dependencies.
- Write the minimum code required. Avoid speculative features, single-use abstractions, unused configurability, and handling for impossible scenarios.
- Touch only lines required by the request, preserve existing user changes, match the local style, and do not refactor or clean adjacent code. Remove only items made obsolete by your change.
- For a reported bug, reproduce the behavior before changing production code when practical. For validation, cover invalid input. For a refactor, establish the relevant behavior before and after.
- Run the narrowest relevant check first, then broaden only when risk justifies it. Non-trivial multi-step work should include a short ordered plan with a check for each step.
- The task is complete when the requested behavior passes its checks and no required step remains. Report exactly what could not be verified.
