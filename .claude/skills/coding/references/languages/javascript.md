# JavaScript

## Style & Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Variables, functions | `camelCase` | `userId`, `getUserData()` |
| Classes, constructors | `PascalCase` | `UserProfile`, `EventEmitter` |
| Constants (true constants) | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `API_BASE_URL` |
| Files | lowercase, hyphens | `user-service.js`, `parse-config.js` |
| Booleans | `is`/`has`/`can` prefix | `isActive`, `hasPermission` |

Import ordering: built-in modules, external packages, internal modules, relative imports.
Blank line between each group.

```javascript
import fs from "node:fs";
import path from "node:path";

import express from "express";

import { db } from "#lib/database.js";

import { validate } from "./validate.js";
```

Use `const` by default. Use `let` only when reassignment is needed. Never use `var`.

## Idioms

### Destructuring over index/property access

```javascript
// Non-idiomatic
const name = user.name;
const age = user.age;
const first = items[0];

// Idiomatic
const { name, age } = user;
const [first] = items;

// Rename during destructure
const { name: userName, role = "viewer" } = user;
```

### Optional chaining and nullish coalescing over defensive checks

```javascript
// Non-idiomatic
const tax = product && product.price && product.price.tax;
const score = value !== null && value !== undefined ? value : 100;

// Idiomatic
const tax = product?.price?.tax;
const score = value ?? 100; // only null/undefined, not 0 or ""
```

### Array methods over loops

```javascript
// Non-idiomatic
const results = [];
for (let i = 0; i < users.length; i++) {
  if (users[i].active) {
    results.push(users[i].name);
  }
}

// Idiomatic
const results = users
  .filter((u) => u.active)
  .map((u) => u.name);
```

Other idioms to internalize:
- Template literals over string concatenation: `` `Hello, ${name}` ``
- Spread for shallow copies: `{ ...obj, updated: true }`, `[...arr, newItem]`
- Object shorthand: `{ name, age }` instead of `{ name: name, age: age }`
- `Object.hasOwn(obj, key)` over `obj.hasOwnProperty(key)`
- `for...of` when you actually need a loop (side effects, early return)

## Error Handling

Always catch errors at the boundary where you can do something about them.
Never swallow errors silently.

```javascript
// Custom error with context
class AppError extends Error {
  constructor(message, code, cause) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.cause = cause;
  }
}

// Async function with proper error handling
async function fetchUser(id) {
  let response;
  try {
    response = await fetch(`/api/users/${id}`);
  } catch (err) {
    throw new AppError("Network failure", "NETWORK_ERROR", err);
  }

  if (!response.ok) {
    throw new AppError(
      `User fetch failed: ${response.status}`,
      "API_ERROR"
    );
  }

  return response.json();
}

// Caller handles the error at the appropriate level
try {
  const user = await fetchUser(42);
  renderProfile(user);
} catch (err) {
  if (err.code === "NETWORK_ERROR") {
    showOfflineBanner();
  } else {
    logger.error("Failed to load user", { error: err });
    showErrorPage();
  }
}
```

For Promise-based code, always handle rejections:

```javascript
// Promise.allSettled when you need all results regardless of failures
const results = await Promise.allSettled([fetchA(), fetchB(), fetchC()]);
const failures = results.filter((r) => r.status === "rejected");
```

## Project Structure

```
my-project/
  src/
    index.js            # entry point
    config.js           # env vars, feature flags
    lib/
      database.js       # shared infrastructure
      logger.js
    users/
      user-service.js   # business logic
      user-repo.js      # data access
      user-schema.js    # validation
    orders/
      order-service.js
      order-repo.js
    utils/
      parse-date.js
      retry.js
  tests/
    users/
      user-service.test.js
    orders/
      order-service.test.js
    fixtures/
      users.json
  scripts/
    seed-db.js
    migrate.js
  package.json
  vitest.config.js
```

Group by feature, not by layer. A feature folder contains everything for that domain.
Keep `utils/` small. If a util grows, it becomes its own module in `lib/`.

## Testing

Use Vitest (or Jest). Name test files `*.test.js` next to source or in a mirrored `tests/` tree.
Structure with `describe` for the unit, `it` for the behavior. Follow Arrange-Act-Assert.

```javascript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createOrder } from "../src/orders/order-service.js";
import * as repo from "../src/orders/order-repo.js";

vi.mock("../src/orders/order-repo.js");

describe("createOrder", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("saves order and returns id", async () => {
    // Arrange
    const input = { userId: 1, items: [{ sku: "A1", qty: 2 }] };
    repo.save.mockResolvedValue({ id: 99 });

    // Act
    const result = await createOrder(input);

    // Assert
    expect(repo.save).toHaveBeenCalledWith(
      expect.objectContaining({ userId: 1 })
    );
    expect(result.id).toBe(99);
  });

  it("throws on empty items", async () => {
    await expect(createOrder({ userId: 1, items: [] }))
      .rejects
      .toThrow("Order must have at least one item");
  });
});
```

Test the behavior, not the implementation. One assertion per concept.
Mock at module boundaries (repos, HTTP clients), not internal functions.

## Common Gotchas

**1. `==` coerces types, `===` does not.**
`0 == ""` is `true`. `0 == false` is `true`. Always use `===`.

**2. `this` depends on how a function is called, not where it is defined.**
```javascript
const obj = {
  name: "app",
  greet() { return this.name; },
};
const fn = obj.greet;
fn(); // undefined -- `this` is not obj
```
Fix: use arrow functions for callbacks, or `.bind()` when passing methods.

**3. `var` hoists to function scope; `let`/`const` are block-scoped.**
```javascript
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i)); // 3, 3, 3
}
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i)); // 0, 1, 2
}
```

**4. Floating point math is broken by design.**
`0.1 + 0.2 === 0.3` is `false`. Compare with a tolerance, or use integers
(cents instead of dollars).

**5. `async` functions always return a Promise.**
Forgetting `await` gives you a Promise object, not the value. A missing `await`
inside `try` means the catch block never fires for that rejection.

```javascript
// Bug: error is never caught
try {
  fetchData(); // missing await
} catch (err) {
  // unreachable for async errors
}
```

## Best Practices

- **Prefer `const` everywhere.** Reassignment is the exception, not the rule.
- **Use `node:` prefix for built-in imports.** `import fs from "node:fs"` makes it obvious what is built-in vs. third-party.
- **Fail fast.** Validate inputs at function boundaries and throw early.
- **Use `structuredClone()` for deep copies.** Not `JSON.parse(JSON.stringify(x))`, which drops functions, dates, and `undefined`.
- **Prefer `Map` and `Set` over plain objects** when keys are dynamic or non-string.
- **Use `#private` fields in classes.** Not underscore conventions. True encapsulation.
- **Avoid `forEach` when you need to return, `await`, or break.** Use `for...of`.
- **Keep functions under 30 lines.** If a function needs a comment explaining a section, that section is a new function.
- **Run with `"type": "module"` in package.json.** ESM is the standard. CommonJS is legacy.
