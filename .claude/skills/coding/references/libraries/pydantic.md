# Pydantic

## Model Definition

Define models by subclassing `BaseModel` with type-annotated fields:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str
    email: str
    age: int = Field(gt=0, le=150, description="User age in years")
    bio: str | None = None
```

### Configuration

Use `model_config` with `ConfigDict` instead of inner `class Config`:

```python
from pydantic import BaseModel, ConfigDict

class StrictUser(BaseModel):
    model_config = ConfigDict(
        strict=True,           # no type coercion
        frozen=True,           # immutable after creation
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    name: str
    email: str
```

## Field Constraints with Annotated

Prefer `Annotated` with constraints over `Field()` where possible — these compile into Rust-level validation and are faster than Python validators:

```python
from typing import Annotated
from pydantic import BaseModel
from annotated_types import Gt, MinLen

class Product(BaseModel):
    name: Annotated[str, MinLen(1)]
    price: Annotated[float, Gt(0)]
    tags: Annotated[list[str], MinLen(1)]
```

Common constraints: `Gt`, `Ge`, `Lt`, `Le`, `MinLen`, `MaxLen`, `Predicate`.

## Validators

### Field Validators

Validate individual fields. Always use `@classmethod`:

```python
from pydantic import BaseModel, field_validator

class Signup(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password", mode="before")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
```

Modes: `before` (raw input), `after` (default, post-coercion), `wrap` (around standard validation), `plain` (replaces standard validation).

### Model Validators

Validate across multiple fields:

```python
from typing import Self
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def end_after_start(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
```

Use `mode="before"` for raw dict input, `mode="after"` when you need typed fields.

## Serialization

```python
user = User(name="Alice", email="alice@example.com", age=30)

# To dict
user.model_dump()
user.model_dump(exclude_none=True)
user.model_dump(include={"name", "email"})

# To JSON string
user.model_dump_json()
user.model_dump_json(indent=2)
```

### Computed Fields

Derived values included in serialization output:

```python
from pydantic import BaseModel, computed_field

class Box(BaseModel):
    width: float
    height: float
    depth: float

    @computed_field
    @property
    def volume(self) -> float:
        return self.width * self.height * self.depth

Box(width=1, height=2, depth=3).model_dump()
# {'width': 1.0, 'height': 2.0, 'depth': 3.0, 'volume': 6.0}
```

## Parsing / Validation

```python
# From dict
user = User.model_validate({"name": "Alice", "email": "a@b.com", "age": 30})

# From JSON string
user = User.model_validate_json('{"name": "Alice", "email": "a@b.com", "age": 30}')

# Strict mode per-call
user = User.model_validate(data, strict=True)
```

## TypeAdapter

Validate types that aren't BaseModel subclasses:

```python
from pydantic import TypeAdapter

IntList = TypeAdapter(list[int])
result = IntList.validate_python(["1", "2", "3"])  # [1, 2, 3]
result = IntList.validate_json('[1, 2, 3]')

# Generate JSON schema for any type
schema = IntList.json_schema()
```

Create TypeAdapter instances once and reuse — don't create them in loops.

## JSON Schema

```python
# From model
schema = User.model_json_schema()

# From TypeAdapter
schema = TypeAdapter(list[int]).json_schema()
```

## Best Practices

- **Prefer `Annotated` constraints over `@field_validator`** for simple checks (gt, min_length, etc.). Annotated constraints run in Rust and are significantly faster.
- **Use `@field_validator` only for logic that can't be expressed declaratively** — normalization, cross-referencing external data, complex string parsing.
- **Use `model_config = ConfigDict(frozen=True)`** for immutable value objects. This prevents mutation bugs and makes models hashable.
- **Use `model_validate_json()` for JSON input** instead of `json.loads()` + `model_validate()`. The single-step path is faster because it skips the intermediate Python dict.
- **Don't create TypeAdapter in hot loops.** Instantiate once at module level and reuse.
- **Use `mode="before"` validators sparingly.** They receive raw untyped input and bypass Pydantic's coercion. Prefer `mode="after"` (the default) unless you need to transform input before type checking.
- **Use `exclude_none=True` on `model_dump()`** when serializing for APIs — don't send null fields the consumer didn't ask for.
- **Use `Literal` and discriminated unions** for polymorphic models instead of isinstance checks.
- **Set `strict=True` at the model level** when type coercion is dangerous (e.g., financial data). Lax mode silently converts `"42"` to `42`.
- **Never use v1 methods.** `parse_obj`, `parse_raw`, `.json()`, `.dict()` are all deprecated. Use `model_validate`, `model_validate_json`, `model_dump_json`, `model_dump`.
