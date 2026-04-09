# Python

## Style & Naming

Follow PEP 8. Use `ruff` to enforce it automatically.

| Thing       | Convention          | Example                |
|-------------|---------------------|------------------------|
| Variable    | `snake_case`        | `user_count`           |
| Function    | `snake_case`        | `get_active_users()`   |
| Class       | `PascalCase`        | `UserAccount`          |
| Constant    | `UPPER_SNAKE_CASE`  | `MAX_RETRIES`          |
| Module      | `short_lowercase`   | `utils.py`             |
| Package     | `shortlowercase`    | `mypackage/`           |
| Exception   | `PascalCase + Error`| `InvalidTokenError`    |

Import ordering: standard library, blank line, third-party, blank line, local. Use `isort` or `ruff` to enforce.

```python
import os
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel

from myapp.config import Settings
from myapp.models import User
```

## Idioms

Write Python, not Java-in-Python.

**Iteration: don't index into sequences**

```python
# No
for i in range(len(users)):
    print(users[i].name)

# Yes
for user in users:
    print(user.name)

# Need the index too? enumerate.
for i, user in enumerate(users):
    print(i, user.name)
```

**Comprehensions over map/filter**

```python
# No
squares = list(map(lambda x: x ** 2, range(10)))
evens = list(filter(lambda x: x % 2 == 0, numbers))

# Yes
squares = [x ** 2 for x in range(10)]
evens = [x for x in numbers if x % 2 == 0]
```

**Context managers for resource cleanup**

```python
# No
f = open("data.csv")
try:
    content = f.read()
finally:
    f.close()

# Yes
with open("data.csv") as f:
    content = f.read()
```

**Unpacking and walrus operator**

```python
# Swap without temp
a, b = b, a

# Unpack in loops
for name, score in zip(names, scores):
    print(f"{name}: {score}")

# Walrus operator (3.8+) -- assign and test
if (n := len(items)) > 10:
    print(f"Too many items: {n}")
```

## Error Handling

Python favors EAFP (Easier to Ask Forgiveness than Permission). Try the operation, catch the specific failure. Use LBYL only when the check is cheap and failure is common (e.g., `dict.get()`).

**Never use bare `except:`**. It swallows `KeyboardInterrupt`, `SystemExit`, and `MemoryError`. Catch the narrowest exception you can handle.

```python
# BAD -- bare except hides everything
try:
    process(data)
except:
    pass

# BAD -- too broad
try:
    value = config["timeout"]
except Exception:
    value = 30

# GOOD -- specific exception
try:
    value = config["timeout"]
except KeyError:
    value = 30
```

**Custom exceptions and chaining**

```python
class ServiceError(Exception):
    """Base exception for this service."""

class NotFoundError(ServiceError):
    def __init__(self, resource: str, resource_id: str):
        self.resource = resource
        self.resource_id = resource_id
        super().__init__(f"{resource} {resource_id!r} not found")

class UpstreamError(ServiceError):
    """Wraps errors from external APIs."""

# Preserve the original traceback with `from`
try:
    resp = httpx.get(url)
    resp.raise_for_status()
except httpx.HTTPStatusError as exc:
    raise UpstreamError(f"API call failed: {exc.response.status_code}") from exc
```

## Project Structure

Use the `src` layout. It prevents accidentally importing your source tree instead of the installed package.

```
myproject/
    src/
        myproject/
            __init__.py
            config.py
            models.py
            services/
                __init__.py
                users.py
            cli.py
    tests/
        __init__.py
        conftest.py
        test_models.py
        test_services/
            __init__.py
            test_users.py
    pyproject.toml
    README.md
    .gitignore
```

Minimal `pyproject.toml`:

```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 99
target-version = "py311"
```

## Testing

Use `pytest`. Name test files `test_*.py`, test functions `test_*`. Put shared fixtures in `conftest.py`.

```python
# tests/conftest.py
import pytest
from myproject.models import User

@pytest.fixture
def sample_user():
    return User(name="Ada Lovelace", email="ada@example.com")

@pytest.fixture
def db(tmp_path):
    """Yield a temporary database, clean up after."""
    db_path = tmp_path / "test.db"
    conn = create_connection(db_path)
    yield conn
    conn.close()
```

```python
# tests/test_models.py
import pytest
from myproject.models import User, ValidationError

def test_user_full_name(sample_user):
    assert sample_user.full_name == "Ada Lovelace"

def test_user_rejects_empty_email():
    with pytest.raises(ValidationError, match="email"):
        User(name="Test", email="")

@pytest.mark.parametrize("email,valid", [
    ("user@example.com", True),
    ("user@", False),
    ("", False),
    ("a@b.co", True),
])
def test_email_validation(email, valid):
    if valid:
        User(name="Test", email=email)  # should not raise
    else:
        with pytest.raises(ValidationError):
            User(name="Test", email=email)
```

Run with: `pytest -x -q` (stop on first failure, quiet output).

## Common Gotchas

**1. Mutable default arguments are shared across calls**

```python
# BUG: every call shares the same list
def add_item(item, items=[]):
    items.append(item)
    return items

add_item("a")  # ["a"]
add_item("b")  # ["a", "b"] -- not ["b"]

# FIX: use None sentinel
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

**2. Late binding closures capture variables by reference**

```python
# BUG: all functions return 8 (the final value of i)
funcs = [lambda x: x * i for i in range(5)]
[f(2) for f in funcs]  # [8, 8, 8, 8, 8]

# FIX: bind early with default argument
funcs = [lambda x, i=i: x * i for i in range(5)]
[f(2) for f in funcs]  # [0, 2, 4, 6, 8]
```

**3. `is` vs `==`**

```python
a = [1, 2, 3]
b = [1, 2, 3]
a == b   # True  -- same value
a is b   # False -- different objects

# `is` checks identity (same object in memory). Use it ONLY for None/True/False.
if x is None: ...    # correct
if x == None: ...    # wrong
```

**4. Catching exceptions too broadly silences real bugs**

```python
# You think you're handling missing keys, but you're also
# silencing TypeErrors, AttributeErrors, and anything else.
try:
    do_everything()
except Exception:
    pass  # "it works on my machine"
```

**5. String concatenation in loops is O(n^2)**

```python
# Slow: creates a new string every iteration
result = ""
for word in words:
    result += word + " "

# Fast: join is O(n)
result = " ".join(words)
```

## Best Practices

- **Type hints everywhere.** Use them on function signatures, dataclass fields, and module-level variables. Run `mypy --strict` or `pyright` in CI.
- **Use `pathlib.Path` instead of `os.path`.** It reads better, chains naturally, and is cross-platform: `Path("data") / "output" / "results.csv"`.
- **f-strings for formatting.** Not `%`, not `.format()`. Use `f"{value!r}"` for debug representations.
- **Dataclasses or Pydantic for data containers.** Stop writing classes with manual `__init__`, `__repr__`, and `__eq__`. Use `@dataclass` for internal data, Pydantic `BaseModel` for validated external input.
- **`from __future__ import annotations` at the top of every module.** Enables postponed evaluation of type hints, avoids forward-reference issues, and becomes the default in future Python versions.
- **Never mutate a collection while iterating over it.** Copy first (`for item in list(items):`) or build a new collection.
- **Use `logging` instead of `print` for anything that ships.** Configure it once at the entry point, use `logger = logging.getLogger(__name__)` in every module.
- **Prefer `enum.Enum` over string constants.** Typos in strings are silent bugs. Typos in enum members are `AttributeError`.
- **Pin dependencies in `pyproject.toml` with lower bounds, lock with `uv lock` or `pip-compile`.** Loose pins in dev, locked files in CI and production.
