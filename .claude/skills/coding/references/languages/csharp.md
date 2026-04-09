# C#

## Style & Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Public type, method, property | PascalCase | `OrderService`, `GetTotal()` |
| Private field | `_camelCase` | `_connectionString` |
| Local variable, parameter | camelCase | `itemCount`, `userId` |
| Constant (local or field) | PascalCase | `MaxRetries` |
| Interface | `I` prefix + PascalCase | `IOrderRepository` |
| Static private field | `s_camelCase` | `s_instance` |
| File-scoped namespace | One per file | `namespace MyApp.Orders;` |

Usings go outside the namespace, `System.*` first, then alphabetical. Use file-scoped namespaces unless you need multiple namespaces in one file. Always specify visibility modifiers explicitly; visibility comes before other modifiers (`public static` not `static public`).

```csharp
using System;
using System.Collections.Generic;
using Microsoft.Extensions.Logging;

namespace MyApp.Orders;

public class OrderService
{
    private readonly ILogger<OrderService> _logger;
    private readonly IOrderRepository _repository;
    private static readonly TimeSpan s_defaultTimeout = TimeSpan.FromSeconds(30);

    public OrderService(ILogger<OrderService> logger, IOrderRepository repository)
    {
        _logger = logger;
        _repository = repository;
    }

    public async Task<Order?> GetByIdAsync(int id) =>
        await _repository.FindAsync(id);
}
```

## Idioms

**Records instead of boilerplate DTOs:**

```csharp
// Non-idiomatic: manual equality, ToString, etc.
public class Point
{
    public double X { get; init; }
    public double Y { get; init; }
    // ... Equals, GetHashCode, ToString ...
}

// Idiomatic: record does it all.
public record Point(double X, double Y);
```

**Pattern matching instead of type-checking chains:**

```csharp
// Non-idiomatic
if (shape is Circle)
    return ((Circle)shape).Radius * Math.PI * 2;
else if (shape is Rectangle)
    return (((Rectangle)shape).Width + ((Rectangle)shape).Height) * 2;

// Idiomatic: switch expression with pattern matching.
double perimeter = shape switch
{
    Circle c    => c.Radius * Math.PI * 2,
    Rectangle r => (r.Width + r.Height) * 2,
    _           => throw new ArgumentException($"Unknown shape: {shape.GetType().Name}")
};
```

**Collection expressions and LINQ instead of manual loops:**

```csharp
// Non-idiomatic
var ids = new List<int>();
foreach (var order in orders)
    if (order.IsActive)
        ids.Add(order.Id);

// Idiomatic: LINQ + collection expressions.
int[] ids = [.. orders.Where(o => o.IsActive).Select(o => o.Id)];
```

Other patterns to prefer: nullable reference types (enable `<Nullable>enable</Nullable>` always), `init`-only properties for immutable data, raw string literals for multi-line strings, primary constructors for DI in simple classes, `required` properties to force initialization without constructors.

## Error Handling

Throw exceptions for truly exceptional situations. Use the TryParse / Try-pattern for expected failures. Never catch `Exception` without a filter. Always use `using` for disposables.

```csharp
// Custom exception with inner exception.
public class OrderNotFoundException : Exception
{
    public int OrderId { get; }

    public OrderNotFoundException(int orderId)
        : base($"Order {orderId} not found.")
    {
        OrderId = orderId;
    }

    public OrderNotFoundException(int orderId, Exception inner)
        : base($"Order {orderId} not found.", inner)
    {
        OrderId = orderId;
    }
}

// Try-pattern for expected failures.
public static bool TryParseOrderId(string input, out int orderId)
{
    orderId = 0;
    if (string.IsNullOrWhiteSpace(input)) return false;
    return int.TryParse(input, out orderId) && orderId > 0;
}

// Using declaration for disposable resources (no braces needed).
public async Task<string> ReadConfigAsync(string path)
{
    using var stream = File.OpenRead(path);
    using var reader = new StreamReader(stream);
    return await reader.ReadToEndAsync();
}

// Exception filter: only catch transient failures.
try
{
    await httpClient.PostAsync(url, content);
}
catch (HttpRequestException ex) when (ex.StatusCode is >= (HttpStatusCode)500)
{
    _logger.LogWarning(ex, "Transient server error, will retry");
    throw;
}
```

## Project Structure

```
MyApp/
  MyApp.sln
  Directory.Build.props          # shared MSBuild properties
  Directory.Packages.props       # central package management
  .editorconfig
  global.json                    # SDK version pin
  src/
    MyApp.Domain/
      MyApp.Domain.csproj
      Models/
      Interfaces/
    MyApp.Application/
      MyApp.Application.csproj
      Services/
    MyApp.Infrastructure/
      MyApp.Infrastructure.csproj
      Repositories/
  tests/
    MyApp.Domain.Tests/
      MyApp.Domain.Tests.csproj
    MyApp.Application.Tests/
      MyApp.Application.Tests.csproj
```

One `.csproj` per concern. Test projects mirror the `src/` structure with a `.Tests` suffix. Use `Directory.Build.props` at the root for shared settings (target framework, nullable, implicit usings). Use `Directory.Packages.props` for centralized NuGet version management.

## Testing

Use xUnit with `[Fact]` for single cases and `[Theory]` with `[InlineData]` for parameterized tests. Name tests `MethodName_Scenario_ExpectedResult`. Use Moq for dependency isolation.

```csharp
using Moq;
using Xunit;

namespace MyApp.Application.Tests;

public class OrderServiceTests
{
    private readonly Mock<IOrderRepository> _repoMock = new();
    private readonly Mock<ILogger<OrderService>> _loggerMock = new();
    private readonly OrderService _sut;

    public OrderServiceTests()
    {
        _sut = new OrderService(_loggerMock.Object, _repoMock.Object);
    }

    [Fact]
    public async Task GetByIdAsync_ExistingOrder_ReturnsOrder()
    {
        // Arrange
        var expected = new Order { Id = 42, IsActive = true };
        _repoMock.Setup(r => r.FindAsync(42)).ReturnsAsync(expected);

        // Act
        var result = await _sut.GetByIdAsync(42);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(42, result.Id);
        _repoMock.Verify(r => r.FindAsync(42), Times.Once);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public async Task GetByIdAsync_InvalidId_ReturnsNull(int badId)
    {
        _repoMock.Setup(r => r.FindAsync(badId)).ReturnsAsync((Order?)null);

        var result = await _sut.GetByIdAsync(badId);

        Assert.Null(result);
    }
}
```

## Common Gotchas

**1. `async void` swallows exceptions.** Only use `async void` for event handlers. Everything else returns `Task` or `Task<T>`. An unhandled exception in `async void` crashes the process.

**2. LINQ deferred execution bites twice.** A LINQ query is re-evaluated every time you enumerate it. If the underlying data changes or the query is expensive, materialize with `.ToList()` or `.ToArray()`.

```csharp
var query = users.Where(u => u.IsActive); // not executed yet
users.Add(newUser);
var count = query.Count(); // includes newUser -- surprise
```

**3. Mutable structs are a trap.** Modifying a struct through a property or indexer operates on a copy. The original value is unchanged. Prefer `readonly struct` and treat structs as immutable.

**4. Nullable reference types don't prevent nulls at runtime.** They are compiler warnings only. Code from libraries without nullable annotations, deserialization, and `default` on structs containing reference fields can still produce nulls. Validate at trust boundaries.

**5. Captured loop variables in closures.** Before C# 5, `foreach` reused one variable. That's fixed now, but `for` loops still capture by reference. If you close over `i` in a `for` loop, all closures share the final value.

## Best Practices

- **Enable nullable reference types project-wide.** Add `<Nullable>enable</Nullable>` to your csproj. Fix every warning. This is the single highest-impact quality setting in modern C#.
- **Prefer records for data, classes for behavior.** Records give you value equality, `with` expressions, and deconstruction for free.
- **Use `sealed` on classes that aren't designed for inheritance.** It communicates intent, and the JIT can devirtualize calls on sealed types.
- **Favor `ValueTask<T>` over `Task<T>` on hot paths** that often complete synchronously. Avoids heap allocation for the common case.
- **Use collection expressions** (`[1, 2, 3]`) and the spread operator (`[..existing, newItem]`) instead of manual list building. Works with arrays, lists, spans.
- **Use `readonly` on fields and `readonly struct` on value types** wherever possible. The compiler enforces immutability and can optimize accordingly.
- **Return `IReadOnlyList<T>` or `IEnumerable<T>` from public APIs**, not `List<T>`. Expose the narrowest contract. Internally, use concrete types.
- **Use `string.Equals(a, b, StringComparison.Ordinal)`** (or `OrdinalIgnoreCase`) instead of `==` when comparison semantics matter. The default `==` is ordinal, but being explicit prevents culture bugs.
- **Use `TimeProvider` for testable time.** Injecting `TimeProvider` (added in .NET 8) instead of calling `DateTime.UtcNow` directly makes time-dependent code testable without hacks.
