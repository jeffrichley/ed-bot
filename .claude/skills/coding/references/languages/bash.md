# Bash

## Style & Naming

Use `#!/usr/bin/env bash` for portability. Two-space indentation, no tabs. Max 80 characters per line.

| Thing              | Convention         | Example                  |
|--------------------|--------------------|--------------------------|
| Variable           | `lower_snake_case` | `file_count`             |
| Function           | `lower_snake_case` | `parse_config()`         |
| Constant           | `UPPER_SNAKE_CASE` | `readonly MAX_RETRIES=3` |
| Exported/env var   | `UPPER_SNAKE_CASE` | `export DATA_DIR="/opt"` |
| Executable script  | `lower-kebab`      | `run-backup`             |
| Library file       | `lower_snake.sh`   | `string_utils.sh`        |

Every script starts with a shebang and a header comment:

```bash
#!/usr/bin/env bash
# run-backup -- Sync local data to S3 and prune old snapshots.
# Usage: run-backup [--dry-run] <bucket-name>

set -euo pipefail
```

Declare variables with `local` inside functions. Separate declaration from command substitution to preserve exit codes:

```bash
process_file() {
  local filename="$1"
  local content
  content=$(cat "$filename")  # exit code captured correctly
}
```

## Idioms

Write modern Bash, not Bourne shell.

**Test expressions: `[[ ]]` over `[ ]`**

```bash
# Non-idiomatic
if [ -n "$var" ] && [ "$var" != "none" ]; then

# Idiomatic -- [[ ]] supports && natively, no word-splitting risk
if [[ -n "$var" && "$var" != "none" ]]; then
```

**Command substitution: `$()` over backticks**

```bash
# Non-idiomatic -- backticks can't nest cleanly
dir=`dirname \`readlink -f "$0"\``

# Idiomatic -- $() nests naturally
dir=$(dirname "$(readlink -f "$0")")
```

**Parameter expansion over external commands**

```bash
# Non-idiomatic -- spawns a subprocess for simple string ops
ext=$(echo "$file" | sed 's/.*\.//')
base=$(echo "$file" | sed 's/\.[^.]*$//')

# Idiomatic -- pure bash, no fork
ext="${file##*.}"
base="${file%.*}"
```

Other idioms to internalize:

- `set -euo pipefail` at the top of every script.
- Here strings (`<<< "$var"`) over `echo "$var" | cmd`.
- Process substitution (`< <(cmd)`) to avoid subshell variable loss in loops.
- `printf '%s\n' "$msg"` over `echo "$msg"` when output must be predictable.
- `"${array[@]}"` for safe array expansion (always quoted).

## Error Handling

Start every script with strict mode. Use `trap` for cleanup. Send errors to stderr.

```bash
#!/usr/bin/env bash
set -euo pipefail

WORK_DIR=""

cleanup() {
  local exit_code=$?
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    rm -rf "$WORK_DIR"
  fi
  exit "$exit_code"
}
trap cleanup EXIT

die() {
  printf '%s\n' "$1" >&2
  exit "${2:-1}"
}

main() {
  WORK_DIR=$(mktemp -d) || die "Failed to create temp directory"

  local input="${1:?Usage: process-data <input-file>}"
  [[ -f "$input" ]] || die "File not found: $input"

  cp "$input" "$WORK_DIR/data.csv" || die "Copy failed"
  process "$WORK_DIR/data.csv"
}

main "$@"
```

Key rules:

- `trap cleanup EXIT` fires on normal exit, errors, and signals. Always use it.
- Check return codes explicitly for commands where failure is expected: `if ! grep -q pattern file; then ...`.
- Use `|| die "msg"` for one-liner guards.
- Beware: `set -e` does not trigger inside `if` conditions, `&&`/`||` chains, or command substitutions in assignments like `local x=$(false)`. Test those paths manually.

## Project Structure

```
myproject/
    bin/
        run-backup            # executable entry points (no .sh extension)
        migrate-db
    lib/
        logging.sh            # sourced libraries (.sh extension)
        config.sh
        db_utils.sh
    conf/
        defaults.conf         # key=value config files
    tests/
        test_logging.bats     # bats-core test files
        test_db_utils.bats
        fixtures/
            sample.csv
    Makefile                  # install, test, lint targets
    README.md
```

Entry points in `bin/` source libraries relative to their own location:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/logging.sh"
source "${SCRIPT_DIR}/../lib/config.sh"
```

## Testing

Use [bats-core](https://github.com/bats-core/bats-core). Name test files `test_*.bats`. Each `@test` block runs in its own subshell with `set -e` enabled, so any failing command fails the test.

```bash
#!/usr/bin/env bats

setup() {
  SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  source "${SCRIPT_DIR}/../lib/string_utils.sh"
  TEST_DIR=$(mktemp -d)
}

teardown() {
  rm -rf "$TEST_DIR"
}

@test "trim removes leading and trailing whitespace" {
  result=$(trim "  hello world  ")
  [[ "$result" == "hello world" ]]
}

@test "parse_config reads key-value pairs" {
  echo 'timeout=30' > "$TEST_DIR/test.conf"
  echo 'retries=5' >> "$TEST_DIR/test.conf"

  run parse_config "$TEST_DIR/test.conf" "timeout"
  [[ "$status" -eq 0 ]]
  [[ "$output" == "30" ]]
}

@test "parse_config fails on missing file" {
  run parse_config "/nonexistent/file" "key"
  [[ "$status" -ne 0 ]]
}
```

Run with: `bats tests/` or `bats --tap tests/` for CI-friendly TAP output.

## Common Gotchas

**1. Unquoted variables undergo word splitting and globbing**

```bash
file="my report.txt"
rm $file       # BUG: removes "my" and "report.txt" separately
rm "$file"     # Correct: removes "my report.txt"

files="*.log"
echo $files    # BUG: glob expands to matching filenames
echo "$files"  # Correct: prints literal "*.log"
```

**2. Pipes create subshells, killing variable scope**

```bash
count=0
cat file.txt | while read -r line; do
  ((count++))
done
echo "$count"  # BUG: prints 0 -- the while loop ran in a subshell

# Fix: use process substitution or redirect
count=0
while read -r line; do
  ((count++))
done < <(cat file.txt)
echo "$count"  # Correct: prints actual line count
```

**3. `local` masks return codes**

```bash
my_func() {
  local result=$(might_fail)  # BUG: exit code of might_fail is lost
  echo "$result"
}

my_func() {
  local result
  result=$(might_fail)        # Correct: set -e can now catch failure
  echo "$result"
}
```

**4. `[[ $a > $b ]]` does string comparison, not numeric**

```bash
[[ 9 > 10 ]]  && echo "yes"  # Prints "yes" -- string "9" > string "10"
(( 9 > 10 ))  && echo "yes"  # Correct: no output -- arithmetic comparison
```

**5. Iterating filenames with `ls` breaks on spaces and special characters**

```bash
# BUG: breaks on spaces, newlines, globs
for f in $(ls *.csv); do process "$f"; done

# Correct: use a glob directly
for f in ./*.csv; do
  [[ -e "$f" ]] || continue   # handle no-match case
  process "$f"
done
```

## Best Practices

- **Always quote `"$variables"` and `"$(command substitutions)"`.** The unquoted form is almost never what you want.
- **Use `shellcheck` on every script.** Run it in CI. Fix every warning. It catches real bugs.
- **Use arrays for lists, not space-delimited strings.** `files=("a.txt" "b c.txt")` then `"${files[@]}"` handles spaces correctly.
- **Use `main "$@"` pattern.** Define a `main` function, call it at the bottom. This prevents partial-execution if the script is truncated during download.
- **Use `readonly` for constants.** `readonly DB_HOST="localhost"` prevents accidental reassignment.
- **Prefer `printf` over `echo`.** `echo` behavior varies across platforms (`-n`, `-e` flags). `printf` is portable and predictable.
- **Use `[[ -f "$file" ]]` before operating on files.** Never assume a glob matched or a file exists.
- **Redirect errors to stderr.** `echo "Error: ..." >&2`. Never mix error messages with stdout data.
- **If your script exceeds 200 lines, reconsider.** Bash is glue. For complex logic, use Python or Go and call it from a thin shell wrapper.
