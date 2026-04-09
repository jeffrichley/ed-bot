# Java

## Style & Naming

Follow the [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html). Use `google-java-format` to enforce it automatically.

| Thing        | Convention         | Example                  |
|--------------|--------------------|--------------------------|
| Class        | `PascalCase`       | `UserAccount`            |
| Interface    | `PascalCase`       | `Readable`               |
| Method       | `camelCase`        | `getActiveUsers()`       |
| Variable     | `camelCase`        | `userCount`              |
| Constant     | `UPPER_SNAKE_CASE` | `MAX_RETRIES`            |
| Package      | `lowercase`        | `com.example.deepspace`  |
| Type Param   | Single capital / `ClassT` | `E`, `RequestT`   |
| Enum Value   | `UPPER_SNAKE_CASE` | `ORDER_PENDING`          |

One public top-level class per file. File name matches the class name. Import ordering: static imports (one block), blank line, non-static imports (one block). ASCII sort within each block. No wildcard imports.

```java
import static java.util.Objects.requireNonNull;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import com.example.myapp.model.User;
import com.example.myapp.service.UserService;
```

## Idioms

Write modern Java, not Java 8-in-Java 21.

**Records over hand-rolled value classes**

```java
// Non-idiomatic: 40+ lines of boilerplate
public class Point {
    private final int x;
    private final int y;
    public Point(int x, int y) { this.x = x; this.y = y; }
    public int getX() { return x; }
    public int getY() { return y; }
    // plus equals, hashCode, toString...
}

// Idiomatic: one line, immutable, equals/hashCode/toString generated
public record Point(int x, int y) {}
```

**Pattern matching over instanceof + cast**

```java
// Non-idiomatic
if (shape instanceof Circle) {
    Circle c = (Circle) shape;
    return Math.PI * c.radius() * c.radius();
}

// Idiomatic: bind and test in one step
if (shape instanceof Circle c) {
    return Math.PI * c.radius() * c.radius();
}
```

**Sealed classes + switch expressions for exhaustive handling**

```java
public sealed interface Shape permits Circle, Rectangle, Triangle {}
public record Circle(double radius) implements Shape {}
public record Rectangle(double width, double height) implements Shape {}
public record Triangle(double base, double height) implements Shape {}

double area(Shape shape) {
    return switch (shape) {
        case Circle c    -> Math.PI * c.radius() * c.radius();
        case Rectangle r -> r.width() * r.height();
        case Triangle t  -> 0.5 * t.base() * t.height();
    }; // compiler enforces exhaustiveness -- no default needed
}
```

**Other modern features worth using:**
- `var` for local variables when the type is obvious: `var users = List.of("Ada", "Grace");`
- Text blocks for multi-line strings: `"""\n    SELECT *\n    FROM users\n    """`
- `Optional` as a return type, never as a field or parameter.
- Streams for transforms, not for everything. A for-loop is fine when it's clearer.

## Error Handling

**Checked vs unchecked:** Use checked exceptions (`extends Exception`) for recoverable conditions the caller must handle (I/O failures, validation). Use unchecked exceptions (`extends RuntimeException`) for programming errors (null arguments, illegal state). When in doubt, prefer unchecked.

**Custom exceptions with chaining:**

```java
public class ServiceException extends RuntimeException {
    public ServiceException(String message) { super(message); }
    public ServiceException(String message, Throwable cause) { super(message, cause); }
}

public class UserNotFoundException extends ServiceException {
    private final String userId;

    public UserNotFoundException(String userId) {
        super("User not found: " + userId);
        this.userId = userId;
    }

    public String getUserId() { return userId; }
}
```

**Try-with-resources for every `AutoCloseable`:**

```java
// Resources are closed automatically, even on exception
public List<String> readLines(Path path) throws IOException {
    try (var reader = Files.newBufferedReader(path);
         var lines = reader.lines()) {
        return lines.filter(line -> !line.isBlank()).toList();
    }
}
```

Never catch `Exception` or `Throwable` unless you are at a top-level boundary (main method, HTTP handler). Catch the narrowest type you can handle.

## Project Structure

Standard Maven/Gradle layout. Do not invent your own.

```
myproject/
    src/
        main/
            java/
                com/example/myproject/
                    Application.java
                    model/
                        User.java
                        Order.java
                    service/
                        UserService.java
                    repository/
                        UserRepository.java
            resources/
                application.properties
        test/
            java/
                com/example/myproject/
                    service/
                        UserServiceTest.java
                    repository/
                        UserRepositoryTest.java
            resources/
                test-data.json
    build.gradle.kts          (or pom.xml)
    settings.gradle.kts
    .gitignore
```

Test classes mirror the package structure of the code they test. Test class name = class under test + `Test`.

## Testing

Use JUnit 5 with AssertJ for assertions. Use Mockito for test doubles.

```java
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock UserRepository repository;
    @InjectMocks UserService service;

    @Test
    void findUser_returnsUser_whenExists() {
        var expected = new User("alice", "alice@example.com");
        when(repository.findById("alice")).thenReturn(Optional.of(expected));

        var result = service.findUser("alice");

        assertThat(result).isEqualTo(expected);
    }

    @Test
    void findUser_throwsNotFound_whenMissing() {
        when(repository.findById("ghost")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.findUser("ghost"))
            .isInstanceOf(UserNotFoundException.class)
            .hasMessageContaining("ghost");
    }

    @ParameterizedTest
    @CsvSource({
        "alice@example.com, true",
        "bob@,              false",
        "'',                false",
        "a@b.co,            true"
    })
    void validateEmail(String email, boolean expected) {
        assertThat(User.isValidEmail(email)).isEqualTo(expected);
    }
}
```

Test method naming: `methodUnderTest_expectedBehavior_condition`. No `test` prefix (JUnit 5 does not need it).

## Common Gotchas

**1. Broken equals/hashCode contract**

If you override `equals()`, you must override `hashCode()`. Objects that are `equals()` must produce the same hash code. Break this and `HashMap`/`HashSet` silently lose your data. Use records (which generate both) or your IDE's generator.

**2. `==` on wrapper types compares identity, not value**

```java
Integer a = 200;
Integer b = 200;
a == b;      // false -- different objects (outside -128..127 cache)
a.equals(b); // true  -- always use .equals() for objects
```

**3. Null references everywhere**

Java has no null safety in the type system. Defend at boundaries: validate inputs with `Objects.requireNonNull()`, return `Optional` instead of null, use `@Nullable`/`@NonNull` annotations and let your IDE warn you.

**4. ConcurrentModificationException**

Modifying a collection while iterating over it throws. Use `Iterator.remove()`, `removeIf()`, or build a new collection.

```java
// Crashes at runtime
for (var item : items) {
    if (item.isExpired()) items.remove(item);
}

// Correct
items.removeIf(Item::isExpired);
```

**5. Mutable date/time objects (legacy API)**

`java.util.Date` and `Calendar` are mutable. A getter returning a `Date` field lets callers corrupt your object's state. Use `java.time` instead (`LocalDate`, `Instant`, `ZonedDateTime`). They are immutable and thread-safe.

## Best Practices

- **Use records for DTOs, value objects, and anything that is just data.** They are immutable, have correct `equals`/`hashCode`, and eliminate boilerplate.
- **Prefer `List.of()`, `Set.of()`, `Map.of()` for immutable collections.** Unmodifiable by default, modifiable by choice. Never return a mutable collection from a public method.
- **Use `Optional` as a return type only.** Never as a method parameter, field, or collection element. Call `orElseThrow()` or `orElse()` at the boundary.
- **Favor composition over inheritance.** Extend a class only when there is a genuine "is-a" relationship. Use interfaces and delegation for everything else.
- **Close resources with try-with-resources.** Never rely on `finally` blocks for cleanup. If a class holds a resource, implement `AutoCloseable`.
- **Use `java.time` for all date/time work.** `Date`, `Calendar`, and `SimpleDateFormat` are broken by design. Do not use them in new code.
- **Make classes and methods `final` unless designed for extension.** Unintended subclassing causes fragile base class problems.
- **Use `sealed` to model closed hierarchies.** State machines, AST nodes, API responses with a fixed set of variants. The compiler enforces exhaustive handling.
- **Run `NullAway` or `ErrorProne` in CI.** Catch null dereferences and common bugs at compile time, not in production.
