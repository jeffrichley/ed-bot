# Language Reference Template

Use this template when writing a new `references/languages/<lang>.md` file. Every section is required. Keep each section focused and opinionated — this is how we write code, not an encyclopedia.

---

## Required Sections

### 1. `# <Language Name>`

Top-level heading. Just the language name.

### 2. `## Style & Naming`

The conventions that make code look like it belongs in this language. Cover:
- Naming conventions (variables, functions, classes, constants, files/modules)
- Casing rules (snake_case, camelCase, PascalCase, etc.)
- File and directory naming
- Import/module organization and ordering

Show a short example of well-named code in this language.

### 3. `## Idioms`

The patterns that distinguish fluent code from "translated from another language" code. Cover:
- The idiomatic way to do common operations (iteration, string building, null/nil handling, etc.)
- Language-specific constructs that should be preferred over generic alternatives
- What "Pythonic" / "Rustic" / "idiomatic Go" / etc. actually means in practice

Show 2-3 before/after examples: non-idiomatic vs idiomatic.

### 4. `## Error Handling`

How this language expects you to handle errors. Cover:
- The standard error mechanism (exceptions, Result types, error returns, etc.)
- When to use which error strategy
- How to create custom errors/exceptions
- What NOT to do (swallowing errors, bare except, panic for control flow, etc.)

Show a complete example of proper error handling in this language.

### 5. `## Project Structure`

The standard way to organize a project in this language. Cover:
- Canonical directory layout
- Entry points
- How modules/packages work
- Where tests go

Show the directory tree for a well-structured small project.

### 6. `## Testing`

How to write tests in this language. Cover:
- The standard test framework and how to run tests
- Test file naming and organization
- The idiomatic test pattern (arrange/act/assert, table-driven, etc.)
- Mocking/stubbing approach

Show a complete test example.

### 7. `## Common Gotchas`

The mistakes that bite everyone, especially when coming from another language. Cover:
- 3-5 specific pitfalls with short explanations
- Footguns in the standard library
- Performance traps
- Mutability / concurrency surprises

### 8. `## Best Practices`

Bulleted list of opinionated rules for writing good code in this language. These should be language-specific, not general principles (those live in SKILL.md). Keep to 6-10 bullets.

---

## Guidelines

- **Be opinionated.** This is how we write code, not a survey of options.
- **Show, don't tell.** Every section should have at least one code example.
- **Keep it scannable.** An agent should be able to find what it needs in seconds.
- **No overlap with SKILL.md.** Don't repeat general practices like SRP, YAGNI, DRY. Those apply everywhere. This file covers what's specific to the language.
- **No overlap with library references.** If a framework has its own file in `references/libraries/`, don't cover it here. The language file covers the standard library and core language only.
- **Target length: 100-200 lines.** Enough to be useful, short enough to be read in full.
