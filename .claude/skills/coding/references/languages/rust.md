# Rust

## Style & Naming

| Item              | Convention             | Example                |
|-------------------|------------------------|------------------------|
| Types, Traits     | `UpperCamelCase`       | `HttpRequest`, `Clone` |
| Enum variants     | `UpperCamelCase`       | `Color::DarkRed`       |
| Functions/Methods | `snake_case`           | `fetch_users()`        |
| Local variables   | `snake_case`           | `user_count`           |
| Constants/Statics | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES`          |
| Modules/Crates    | `snake_case`           | `http_client`          |
| Type parameters   | Short `UpperCamelCase` | `T`, `E`, `Req`        |
| Lifetimes         | Short lowercase        | `'a`, `'de`            |
| Macros            | `snake_case!`          | `vec!`, `println!`     |

Acronyms count as one word in `UpperCamelCase`: `Uuid`, not `UUID`. `Stdin`, not `StdIn`.
No `-rs` or `-rust` in crate names. No `get_` prefix on getters. No `use-` or `with-` in feature names.

```rust
use std::collections::HashMap;

pub struct HttpClient {
    base_url: String,
    max_retries: u32,
}

impl HttpClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self { base_url: base_url.into(), max_retries: 3 }
    }

    pub fn base_url(&self) -> &str { &self.base_url }  // no get_ prefix
}
```

## Idioms

**Prefer iterators over manual loops:**

```rust
// Non-idiomatic
let mut names = Vec::new();
for user in &users {
    if user.active {
        names.push(user.name.clone());
    }
}

// Idiomatic
let names: Vec<_> = users.iter()
    .filter(|u| u.active)
    .map(|u| u.name.clone())
    .collect();
```

**Use `?` instead of manual matching:**

```rust
// Non-idiomatic
fn read_config(path: &str) -> Result<Config, Error> {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(e) => return Err(e.into()),
    };
    let config = match serde_json::from_str(&content) {
        Ok(c) => c,
        Err(e) => return Err(e.into()),
    };
    Ok(config)
}

// Idiomatic
fn read_config(path: &str) -> Result<Config, Error> {
    let content = std::fs::read_to_string(path)?;
    let config = serde_json::from_str(&content)?;
    Ok(config)
}
```

**Use `From`/`Into` conversions and Option combinators:**

```rust
// Non-idiomatic
let port = match config.port {
    Some(p) => p,
    None => 8080,
};

// Idiomatic
let port = config.port.unwrap_or(8080);
let addr = config.host.map(|h| format!("{}:{}", h, port));
```

Other patterns to use: builder pattern for complex construction, newtype pattern
(`struct UserId(u64)`) for type safety, `impl From<X> for Y` over manual conversion methods,
`if let` / `let else` over single-arm `match`.

## Error Handling

Use `thiserror` in libraries (callers need to match errors). Use `anyhow` in applications
(you just want context and backtraces). Many projects use both.

```rust
// Library error type with thiserror
use thiserror::Error;

#[derive(Debug, Error)]
pub enum StorageError {
    #[error("record not found: {id}")]
    NotFound { id: String },

    #[error("connection failed")]
    Connection(#[from] std::io::Error),

    #[error("deserialization failed")]
    Deserialize(#[from] serde_json::Error),
}

// Application code with anyhow
use anyhow::{Context, Result};

fn load_user(id: &str) -> Result<User> {
    let path = format!("data/users/{id}.json");
    let content = std::fs::read_to_string(&path)
        .with_context(|| format!("failed to read user file: {path}"))?;
    let user: User = serde_json::from_str(&content)
        .context("failed to parse user JSON")?;
    Ok(user)
}
```

**When to panic:** Only in truly unrecoverable states, setup/initialization code that
cannot proceed, or when an invariant violation means a bug exists. Never panic in library code
on bad input. Use `expect("reason")` over bare `unwrap()`.

## Project Structure

```
my-project/
  Cargo.toml
  src/
    main.rs          # binary entry point, thin — delegates to lib
    lib.rs           # library root, pub mod declarations
    config.rs        # module file
    db/
      mod.rs         # submodule root
      connection.rs
      queries.rs
  tests/
    integration_test.rs   # integration tests (no #[cfg(test)] needed)
  benches/
    benchmark.rs
  examples/
    basic_usage.rs
```

For workspaces with multiple crates:

```
my-workspace/
  Cargo.toml           # [workspace] members = ["crates/*"]
  crates/
    core/              # shared library
      Cargo.toml
      src/lib.rs
    cli/               # binary that depends on core
      Cargo.toml
      src/main.rs
    server/
      Cargo.toml
      src/main.rs
```

Keep `main.rs` thin. Parse args, set up logging, call into `lib.rs`. This makes your
logic testable without running the binary.

## Testing

```rust
// src/math.rs — unit tests live in the same file
pub fn factorial(n: u64) -> u64 {
    (1..=n).product()
}

/// Computes the nth fibonacci number.
///
/// ```
/// use my_crate::math::fibonacci;
/// assert_eq!(fibonacci(10), 55);
/// ```
pub fn fibonacci(n: u64) -> u64 {
    let (mut a, mut b) = (0, 1);
    for _ in 0..n {
        (a, b) = (b, a + b);
    }
    a
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn factorial_base_cases() {
        assert_eq!(factorial(0), 1);
        assert_eq!(factorial(1), 1);
    }

    #[test]
    fn factorial_known_values() {
        assert_eq!(factorial(5), 120);
        assert_eq!(factorial(10), 3_628_800);
    }

    #[test]
    #[should_panic(expected = "overflow")]
    fn factorial_overflow() {
        factorial(u64::MAX);
    }
}
```

```rust
// tests/integration_test.rs — no #[cfg(test)] needed, cargo handles it
use my_crate::math::factorial;

#[test]
fn factorial_works_through_public_api() {
    assert_eq!(factorial(6), 720);
}
```

Run with `cargo test`. Use `cargo test -- --nocapture` to see println output.
Doc tests (in `///` comments) run automatically and keep examples honest.

## Common Gotchas

**1. Moving a value then trying to use it.** The borrow checker enforces single ownership.
Once you pass a `String` to a function that takes ownership, you cannot use it again.
Clone explicitly if you need both copies, or pass `&str` instead.

**2. `String` vs `&str` confusion.** Accept `&str` in function parameters (or `impl AsRef<str>`).
Return `String` when the function owns the data. Don't `.to_string()` everything out of laziness.

**3. Clone guilt.** Beginners `.clone()` to silence the borrow checker. This works but hides
design problems. If you're cloning in a loop, rethink your data ownership. Cloning is fine
when it's intentional and the data is small.

**4. Lifetime elision hides complexity.** When a function returns a reference, the compiler
infers lifetimes from the inputs. If you have multiple reference parameters and a reference
return, you must annotate. The rules: each param gets its own lifetime, if exactly one input
lifetime exists it applies to all outputs, `&self`'s lifetime applies to method outputs.

**5. Async ecosystem fragmentation.** `tokio` and `async-std` are not interchangeable runtimes.
Pick one (usually tokio) and stick with it. Mixing runtimes causes subtle panics.
Mark your `main` with `#[tokio::main]` and don't think about it again.

## Best Practices

- **Run `cargo clippy` on every commit.** Treat warnings as errors in CI: `cargo clippy -- -D warnings`. The pedantic lint group is worth enabling for libraries.
- **Use `cargo fmt` with no exceptions.** Do not argue about style. Let rustfmt win.
- **Make illegal states unrepresentable.** Use enums over booleans, newtypes over raw primitives, and the type system to enforce invariants at compile time.
- **Implement `Debug` on every public type.** Use `#[derive(Debug)]` by default. Also derive `Clone`, `PartialEq`, `Eq`, `Hash` when it makes sense. Eagerly implement standard traits.
- **Accept borrowed data, return owned data.** Functions taking `&str`, `&[T]`, `&Path` are more flexible than those requiring `String`, `Vec<T>`, `PathBuf`.
- **Prefer `expect("reason")` over `unwrap()`.** When you hit a bug, the message tells you why the assumption was violated.
- **Use `#[must_use]` on functions with important return values.** The compiler warns callers who ignore the result.
- **Keep `unsafe` blocks minimal and documented.** Justify every `unsafe` with a `// SAFETY:` comment explaining why the invariants hold. Wrap unsafe code in safe abstractions.
- **Pin dependencies in `Cargo.lock` for binaries.** Libraries should specify semver ranges; applications should commit `Cargo.lock` for reproducible builds.
- **Write `From` impls instead of custom conversion methods.** This integrates with `?` and the rest of the ecosystem. Use `#[from]` in thiserror to generate them.
