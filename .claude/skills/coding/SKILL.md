---
name: coding
description: General coding practices with progressive disclosure of library-specific guidance via reference files
generated: 2026-04-03T00:00:00Z
topics:
  - Coding standards and practices
  - Progressive disclosure of library-specific guidance
---

# Coding Practices

## How This Skill Works

This skill provides general coding practices that apply to all work. Language and library-specific guidance lives in `references/` files. **Read the relevant reference when you detect that language or library in the code.**

### Languages

| Reference | When to read |
|-----------|--------------|
| `references/languages/python.md` | Writing Python code |
| `references/languages/javascript.md` | Writing JavaScript code |
| `references/languages/typescript.md` | Writing TypeScript code |
| `references/languages/go.md` | Writing Go code |
| `references/languages/rust.md` | Writing Rust code |
| `references/languages/java.md` | Writing Java code |
| `references/languages/csharp.md` | Writing C# code |
| `references/languages/cpp.md` | Writing C or C++ code |
| `references/languages/ruby.md` | Writing Ruby code |
| `references/languages/swift.md` | Writing Swift code |
| `references/languages/kotlin.md` | Writing Kotlin code |
| `references/languages/php.md` | Writing PHP code |
| `references/languages/bash.md` | Writing shell scripts |
| `references/languages/sql.md` | Writing SQL queries or schemas |

### Libraries & Frameworks

| Reference | When to read |
|-----------|--------------|
| `references/libraries/discordpy.md` | Code imports `discord` or you're building a Discord bot |
| `references/libraries/pydantic.md` | Code imports `pydantic` or you're defining data models / validation |
| `references/libraries/rich.md` | Code imports `rich` or you're formatting console output |
| `references/libraries/typer.md` | Code imports `typer` or you're building a Python CLI app |

Do not guess at language idioms or library APIs. If a reference file exists for what you're working with, read it first.

## General Practices

- **Single responsibility.** Every module, class, and function should have one reason to change. If you're describing what something does and use the word "and", it probably does too much.
- **Separate interface from logic.** Interface layers (CLI, API routes, UI) are thin wrappers that parse input, call logic, format output, and handle errors. Business logic lives in its own package with zero framework imports. This makes logic testable without framework dependencies.
- **YAGNI (You Aren't Gonna Need It).** Only build what's needed right now. Don't add parameters, config options, or abstractions for hypothetical future use. It's cheaper to add later when you understand the real requirement than to maintain speculative code.
- **DRY, but not prematurely.** Duplication is better than the wrong abstraction. Wait until you see the same pattern three times before extracting. When you do extract, name the abstraction for what it does, not where it came from.
- **Fail fast, fail loud.** Validate inputs at system boundaries (user input, external APIs, file I/O). Raise clear exceptions with context about what went wrong. Don't swallow errors or return None when something is actually broken.
- **Names are documentation.** Variables, functions, and classes should describe what they represent or do. If you need a comment to explain what a name means, the name is wrong. Avoid abbreviations except universally understood ones (e.g., `url`, `id`, `db`).
- **Functions should do one thing at one level of abstraction.** A function that reads a file, parses its contents, validates the data, and writes results is doing four things. Break it apart. Each function should read like a single step.
- **Minimize state and scope.** Declare variables as close to their use as possible. Prefer local over instance, instance over global. The less state that's shared, the fewer bugs you get.
- **Composition over inheritance.** Prefer combining small, focused objects over deep class hierarchies. Inheritance creates tight coupling. Composition lets you swap parts independently.
- **Write tests at the boundary.** Test public interfaces, not implementation details. If you refactor internals and tests break, those tests were too tightly coupled. Tests should verify behavior, not structure.
- **Make dependencies explicit.** Pass what a function needs as arguments. Hidden dependencies on globals, singletons, or environment variables make code hard to test and reason about.
- **Keep I/O at the edges.** Core logic should be pure computation: data in, data out. Push file reads, network calls, and database queries to the outer layer. This makes the core testable and portable.

## Usage Reporting

After completing work using this skill, report the outcome by calling `grimoire_record_usage` with:
- skill: "coding"
- project: "E:\workspaces\school\gt\ed-bot"
- outcome: "success" | "partial" | "failure"
- context: what you were trying to accomplish
- notes: what went well, what didn't, any instructions that were wrong or missing

This feedback improves the skill over time. Always report, even on success.
