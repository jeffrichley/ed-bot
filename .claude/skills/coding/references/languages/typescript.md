# TypeScript

## Style & Naming

| Kind | Convention | Example |
|------|-----------|---------|
| Variables, functions, methods | `camelCase` | `getUserName`, `isReady` |
| Types, interfaces, classes, enums | `PascalCase` | `UserProfile`, `HttpClient` |
| Global constants, enum values | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `API_BASE_URL` |
| Files | `kebab-case.ts` | `user-profile.ts`, `http-client.ts` |
| Type parameters | Single uppercase letter or short PascalCase | `T`, `TResult` |

**Imports:** Named imports only. No default exports. Group: stdlib/node, external, internal, relative.

**`type` vs `interface`:** Use `interface` for object shapes (extendable, better error messages). Use `type` for unions, intersections, mapped types, and anything that is not a plain object shape.

```typescript
// interface for object shapes
interface User {
  id: string;
  name: string;
  email: string;
}

// type for unions and computed types
type Result<T> = { ok: true; value: T } | { ok: false; error: AppError };
type UserKeys = keyof User;
```

## Idioms

### Discriminated unions over class hierarchies

```typescript
// Non-idiomatic: instanceof checks, brittle
class NetworkError { constructor(public status: number) {} }
class TimeoutError { constructor(public ms: number) {} }
function handle(e: NetworkError | TimeoutError) {
  if (e instanceof NetworkError) { /* ... */ }
}

// Idiomatic: discriminated union with exhaustive switch
type AppError =
  | { kind: "network"; status: number }
  | { kind: "timeout"; ms: number }
  | { kind: "validation"; fields: string[] };

function handle(e: AppError): string {
  switch (e.kind) {
    case "network":    return `HTTP ${e.status}`;
    case "timeout":    return `Timed out after ${e.ms}ms`;
    case "validation": return `Bad fields: ${e.fields.join(", ")}`;
  }
}
```

### `satisfies` over type annotations for constants

```typescript
// Non-idiomatic: annotation widens the type, loses literal keys
const routes: Record<string, string> = { home: "/", about: "/about" };
routes.home;   // string -- but TS won't error on routes.bogus

// Idiomatic: satisfies validates AND preserves literal types
const routes = {
  home: "/",
  about: "/about",
} satisfies Record<string, string>;
routes.home;   // "/" (literal)
routes.bogus;  // compile error
```

### `const` assertions for literal tuples and objects

```typescript
// Non-idiomatic: widened to string[]
const statuses = ["idle", "loading", "error"];

// Idiomatic: readonly tuple of literal types
const statuses = ["idle", "loading", "error"] as const;
type Status = (typeof statuses)[number]; // "idle" | "loading" | "error"
```

## Error Handling

Use the Result pattern with discriminated unions. Throw only for truly exceptional situations (programmer errors). Return typed errors for expected failures.

```typescript
// Define error types as a discriminated union
type FetchError =
  | { kind: "network"; message: string }
  | { kind: "not_found" }
  | { kind: "parse"; raw: string };

type Result<T, E = FetchError> =
  | { ok: true; value: T }
  | { ok: false; error: E };

async function fetchUser(id: string): Promise<Result<User>> {
  const res = await fetch(`/api/users/${id}`).catch(
    (e): Result<never> => ({ ok: false, error: { kind: "network", message: String(e) } })
  );
  if (!("ok" in res)) return res; // propagate network error

  if (res.status === 404) return { ok: false, error: { kind: "not_found" } };

  const body = await res.text();
  try {
    return { ok: true, value: JSON.parse(body) as User };
  } catch {
    return { ok: false, error: { kind: "parse", raw: body } };
  }
}

// Exhaustive handling -- compiler catches missing cases
function describeError(e: FetchError): string {
  switch (e.kind) {
    case "network":   return `Network: ${e.message}`;
    case "not_found": return "User not found";
    case "parse":     return `Bad JSON: ${e.raw.slice(0, 50)}`;
    default: {
      const _exhaustive: never = e;
      throw new Error(`Unhandled error: ${JSON.stringify(_exhaustive)}`);
    }
  }
}

// Assertion functions for preconditions
function assertDefined<T>(val: T | undefined, msg: string): asserts val is T {
  if (val === undefined) throw new Error(msg);
}
```

## Project Structure

```
my-project/
  src/
    index.ts              # entry point
    types.ts              # shared type definitions
    utils/
      validation.ts
    services/
      user-service.ts
    __tests__/
      user-service.test.ts
  dist/                   # compiled output (gitignored)
  tsconfig.json
  package.json
  vitest.config.ts
```

Minimal strict `tsconfig.json`:

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "exactOptionalPropertyTypes": true,
    "noUncheckedIndexedAccess": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

Key flags: `strict` (non-negotiable), `noUncheckedIndexedAccess` (catches undefined from indexed access), `exactOptionalPropertyTypes` (distinguishes `undefined` from missing).

## Testing

Use Vitest. Colocate tests in `__tests__/` or as `*.test.ts` next to source files.

```typescript
import { describe, it, expect, vi } from "vitest";
import { fetchUser } from "../services/user-service";
import type { User } from "../types";

// Type-safe mock
const mockFetch = vi.fn<typeof globalThis.fetch>();
vi.stubGlobal("fetch", mockFetch);

describe("fetchUser", () => {
  it("returns user on success", async () => {
    const user: User = { id: "1", name: "Ada", email: "ada@test.com" };
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(user), { status: 200 })
    );

    const result = await fetchUser("1");
    expect(result).toEqual({ ok: true, value: user });
  });

  it("returns not_found on 404", async () => {
    mockFetch.mockResolvedValueOnce(new Response("", { status: 404 }));

    const result = await fetchUser("999");
    expect(result).toEqual({ ok: false, error: { kind: "not_found" } });
  });
});
```

**Type testing** with `vitest`'s `expectTypeOf`:

```typescript
import { expectTypeOf } from "vitest";
import type { Result } from "../types";

it("Result discriminates correctly", () => {
  expectTypeOf<Result<string>>().toMatchTypeOf<
    { ok: true; value: string } | { ok: false; error: FetchError }
  >();
});
```

**Mocking typed dependencies:** Use `vi.mocked()` to preserve types on mocked modules. Never cast mocks to `any`.

## Common Gotchas

**1. `any` silently disables type checking on everything it touches.**
It propagates: `const x: any = ...; const y = x.foo;` -- `y` is also `any`. Use `unknown` and narrow instead.

**2. Structural typing means extra properties pass silently.**
```typescript
interface Point { x: number; y: number }
const p: Point = { x: 1, y: 2, z: 3 }; // error: literal check
const obj = { x: 1, y: 2, z: 3 };
const q: Point = obj; // no error: structural match
```

**3. Enums have footguns.**
Numeric enums allow reverse mapping and accept any number at runtime. Prefer string enums or plain union types: `type Dir = "up" | "down"`.

**4. Type assertions (`as`) bypass safety, type narrowing does not.**
```typescript
// Dangerous: compiles, crashes at runtime
const n = ("hello" as unknown) as number;

// Safe: narrowing with runtime check
function isNumber(v: unknown): v is number {
  return typeof v === "number";
}
```

**5. Optional properties vs `undefined` properties are different with `exactOptionalPropertyTypes`.**
```typescript
interface A { x?: string }     // x may be missing
interface B { x: string | undefined } // x must be present, can be undefined
```

## Best Practices

- Enable `strict`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes` in every project. Start strict, never loosen.
- Prefer `unknown` over `any`. If you must use `any`, add a `// eslint-disable-next-line` with a reason.
- Use discriminated unions for state machines, error types, and polymorphic data. Avoid class hierarchies for data.
- Let TypeScript infer return types for private/internal functions. Annotate return types explicitly on exported public APIs.
- Use `satisfies` for config objects and constants where you want validation without type widening.
- Avoid `enum`. Use `as const` objects or string union types for sets of known values.
- Never use `!` (non-null assertion) in production code. Narrow the type properly or refactor.
- Use branded types for domain identifiers: `type UserId = string & { __brand: "UserId" }`.
- Keep type definitions close to the code that uses them. Only put truly shared types in a `types.ts` file.
- Prefer `readonly` arrays and properties by default. Mutate only when performance requires it.
