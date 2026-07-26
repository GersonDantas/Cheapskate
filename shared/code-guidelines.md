# Code guidelines

Behavioral guidelines to reduce common LLM coding errors. Combine with project-specific instructions as needed.

**Tradeoff:** These guidelines favor caution over speed. For trivial tasks, use judgment.

## 1. Think before you code

**Don't assume. Don't hide the confusion. Superficial compensations.**

Before implementing:
- State your assumptions explicitly. If you're not sure, ask.
- If there are multiple interpretations, present them - don't choose silently.
- If there is a simpler approach, say so. Push back when necessary.
- If something is not clear, stop. Name what is confusing. To ask.

## 2. Simplicity first

**Minimum code that solves the problem. Nothing speculative.**

- There are no resources beyond what was requested.
- No abstractions for single-use code.
- No “flexibility” or “configurability” that was not requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite.

Ask yourself: “Would a senior engineer say this is too complicated?” If so, simplify.

## 3. Surgical Changes

**Only play what you should. Only clean up your own mess.**

When editing existing code:
- Do not "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match the existing style, even if you do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes rendered unused.
- Do not remove pre-existing dead code unless requested.

The Test: Each changed line should directly track the user's request.

## 4. Goal-Oriented Execution

**Define success criteria. Loop until verified.**

Turn tasks into verifiable goals:
- "Add Validation" → "Write tests for invalid inputs and make them pass"
- "Fix the bug" → "Write a test that reproduces it and makes it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, establish a brief plan:
```
1. [Step] → check: [check]
2. [Step] → check: [check]
3. [Step] → check: [check]
```

Strong success criteria allow you to loop independently. Weak criteria (“make it work”) require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes to diffs, fewer rewrites due to excessive complications, and clarifying questions come before implementation rather than after errors.
