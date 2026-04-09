# Go

## Style & Naming

- **Exported** names are `PascalCase`. **Unexported** names are `camelCase`. No underscores, no `ALL_CAPS` constants.
- **Acronyms** keep consistent case: `ServeHTTP`, `appID`, `xmlHTTPRequest`. Never `ServeHttp` or `appId`.
- **Variables**: short names near declaration (`i`, `r`, `c`), longer names further from declaration.
- **Receivers**: one or two letters matching the type (`c` for `Client`). Never `self`, `this`, or `me`. Stay consistent across all methods.
- **Packages**: lowercase, single-word, no underscores. Avoid `util`, `common`, `helpers`. The package name is part of the identifier: `bytes.Buffer`, not `bytes.BytesBuffer`.
- **Files**: `snake_case.go`. Test files end with `_test.go`.
- **Imports**: stdlib first, blank line, then third-party. Use `goimports` to automate.

```go
import (
    "context"
    "fmt"
    "net/http"

    "github.com/your-org/your-lib/internal/auth"
    "go.uber.org/zap"
)

type HTTPClient struct {           // exported, acronym stays uppercase
    baseURL    string              // unexported field
    maxRetries int
}

func (c *HTTPClient) Do(ctx context.Context, req *http.Request) (*http.Response, error) {
    // receiver is 'c', not 'client', 'self', or 'this'
}
```

## Idioms

**Error check -- guard clause, not else:**

```go
// Non-idiomatic
result, err := doThing()
if err == nil {
    // long happy path indented
} else {
    return err
}

// Idiomatic
result, err := doThing()
if err != nil {
    return fmt.Errorf("do thing: %w", err)
}
// happy path at left margin
```

**Comma-ok -- test presence, don't assume:**

```go
// Non-idiomatic
val := myMap[key]  // silent zero value if missing

// Idiomatic
val, ok := myMap[key]
if !ok {
    return fmt.Errorf("key %q not found", key)
}
```

**Interface satisfaction -- accept interfaces, return structs:**

```go
// Non-idiomatic: concrete dependency
func Process(db *PostgresDB) error { ... }

// Idiomatic: accept the behavior you need
func Process(store io.Reader) error { ... }
```

Other patterns to internalize: `defer` for cleanup immediately after acquiring a resource, goroutine+channel over shared memory with mutexes, embedding for composition over inheritance, table-driven tests for every function with multiple cases.

## Error Handling

Use `%w` when callers need to inspect the error chain. Use `%v` at system boundaries to create a clean break. Error strings are lowercase, no trailing punctuation.

```go
// Sentinel errors -- package-level, checked with errors.Is
var ErrNotFound = errors.New("not found")
var ErrConflict = errors.New("conflict")

// Custom error type -- checked with errors.As
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s %s", e.Field, e.Message)
}

// Wrapping with context
func GetUser(id string) (*User, error) {
    row, err := db.QueryRow(ctx, query, id)
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, fmt.Errorf("get user %s: %w", id, ErrNotFound)
        }
        return nil, fmt.Errorf("get user %s: %w", id, err)
    }

    var u User
    if err := row.Scan(&u.Name, &u.Email); err != nil {
        return nil, fmt.Errorf("scan user %s: %w", id, err)
    }
    return &u, nil
}

// Caller site
user, err := GetUser("abc")
if errors.Is(err, ErrNotFound) {
    http.Error(w, "not found", 404)
    return
}
var ve *ValidationError
if errors.As(err, &ve) {
    http.Error(w, ve.Message, 422)
    return
}
```

## Project Structure

Skip `pkg/` unless you are building a public library. Most projects only need `cmd/` and `internal/`.

```
myservice/
  cmd/
    myservice/
      main.go           # wiring only: config, DI, start server
  internal/
    server/
      server.go         # HTTP handler setup
      routes.go
    storage/
      postgres.go       # implements a storage interface
    domain/
      user.go           # core types and business logic
      user_test.go
  go.mod
  go.sum
  Makefile
  README.md
```

- `cmd/` holds one `main.go` per binary. Keep it thin: parse config, wire dependencies, call `Run()`.
- `internal/` is compiler-enforced privacy. Other modules cannot import it.
- Group by domain or responsibility, not by layer. `internal/user/` over `internal/models/` + `internal/handlers/` + `internal/repositories/`.

## Testing

Use the `testing` package. Table-driven tests with subtests are the default pattern.

```go
func TestParseSize(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int64
        wantErr bool
    }{
        {name: "bytes", input: "100B", want: 100},
        {name: "kilobytes", input: "2KB", want: 2048},
        {name: "empty", input: "", wantErr: true},
        {name: "invalid", input: "abc", wantErr: true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseSize(tt.input)
            if tt.wantErr {
                if err == nil {
                    t.Fatalf("ParseSize(%q) expected error, got %d", tt.input, got)
                }
                return
            }
            if err != nil {
                t.Fatalf("ParseSize(%q) unexpected error: %v", tt.input, err)
            }
            if got != tt.want {
                t.Errorf("ParseSize(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

- `t.Helper()` in test helpers so failures report the caller's line.
- `t.Fatalf` when you can't continue. `t.Errorf` to collect multiple failures.
- `t.Cleanup(func())` over manual teardown.
- Avoid assertion libraries. The stdlib `testing` package plus `if got != want` is clear and sufficient.
- Put test helpers in `_test.go` files or a `testutil` internal package.

## Common Gotchas

**Nil interface vs nil pointer.** An interface holding a nil pointer is not nil. This trips up error checks.

```go
func maybeError() error {
    var err *MyError = nil
    return err  // returns non-nil interface containing nil pointer!
}
// maybeError() != nil is TRUE. Return plain nil instead.
```

**Goroutine leaks.** Every goroutine you start must have a clear exit path. Use `context.Context` for cancellation.

```go
// Leak: this goroutine blocks forever if nobody reads ch
go func() { ch <- result }()

// Fix: select with context
go func() {
    select {
    case ch <- result:
    case <-ctx.Done():
    }
}()
```

**Slice append aliasing.** Appending to a slice from a sub-slice can mutate the original backing array.

```go
a := []int{1, 2, 3, 4}
b := a[:2]          // b = [1 2], shares backing array
b = append(b, 99)   // a is now [1 2 99 4] -- surprise!
```

**Zero values are real.** An uninitialized `bool` is `false`, `int` is `0`, `string` is `""`, pointer is `nil`, map is `nil` (reads OK, writes panic). Design types so zero values are useful.

**Deferred closure captures.** `defer` evaluates the function arguments immediately, but a closure captures variables by reference.

```go
for _, f := range files {
    defer f.Close()  // all defers run at function return, not loop iteration
}
// Use an anonymous function or close inside the loop body instead.
```

## Best Practices

- Accept `context.Context` as the first parameter. Never store it in a struct.
- Return `error` as the last return value. Check every error. If you truly want to discard one, assign to `_` with a comment explaining why.
- Keep interfaces small. One to three methods. Define interfaces where they are consumed, not where they are implemented.
- Use `defer` for cleanup immediately after acquisition: open/close, lock/unlock, start/stop.
- Prefer synchronous APIs. Let callers add concurrency. Don't spawn goroutines inside library functions unless documented.
- Use `errors.Is` and `errors.As` for error inspection, never string matching.
- Run `gofmt` (or `goimports`) on every save. Non-negotiable.
- Write table-driven tests by default. Use subtests with `t.Run` for clear failure output.
- Avoid `init()` functions. They make testing hard and execution order unclear. Wire dependencies explicitly in `main`.
- Do not use `panic` for normal error handling. Reserve it for truly unrecoverable programmer errors.
