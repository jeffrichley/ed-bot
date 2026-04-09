# C / C++

## Style & Naming

Follow [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html) conventions:

| Element       | Convention          | Example                    |
|---------------|---------------------|----------------------------|
| Files         | `snake_case.cc/.h`  | `order_parser.cc`          |
| Types/Classes | `PascalCase`        | `OrderParser`              |
| Functions     | `PascalCase`        | `ParseOrder()`             |
| Variables     | `snake_case`        | `order_count`              |
| Members       | `snake_case_`       | `order_count_`             |
| Constants     | `kCamelCase`        | `kMaxRetries`              |
| Macros        | `UPPER_SNAKE`       | `LOG_FATAL`                |
| Enumerators   | `kCamelCase`        | `kSuccess`, `kNotFound`    |

**Include ordering** -- related header first, then blanks between groups:

```cpp
#include "project/server/connection.h"  // 1. related header

#include <sys/types.h>                  // 2. C system headers
#include <unistd.h>

#include <string>                       // 3. C++ standard library
#include <vector>

#include "absl/strings/str_cat.h"       // 4. other libraries
#include "project/base/logging.h"       // 5. project headers
```

## Idioms

### Raw pointer ownership -> `std::unique_ptr`

```cpp
// BAD: who deletes this?
Connection* conn = new Connection(addr);
Process(conn);
delete conn;  // easy to forget, exception-unsafe

// GOOD: ownership is explicit, cleanup is automatic
auto conn = std::make_unique<Connection>(addr);
Process(conn.get());
// deleted when conn goes out of scope
```

### Manual resource cleanup -> RAII wrapper

```cpp
// BAD: leak if DoWork() throws
FILE* f = fopen("data.bin", "rb");
DoWork(f);
fclose(f);

// GOOD: RAII via ifstream -- closed on scope exit no matter what
std::ifstream f("data.bin", std::ios::binary);
DoWork(f);
```

### Index loops -> range-based for + structured bindings

```cpp
// BAD: index math, easy off-by-one
for (size_t i = 0; i < scores.size(); ++i) {
    std::cout << scores[i].first << ": " << scores[i].second << "\n";
}

// GOOD: structured bindings (C++17)
for (const auto& [name, score] : scores) {
    std::cout << name << ": " << score << "\n";
}
```

### Other patterns to prefer

- `std::optional<T>` over sentinel values (`-1`, `nullptr`).
- `constexpr` over `#define` for compile-time constants.
- `auto` for complex iterator/template types, explicit types for readability.
- Move semantics (`std::move`) when transferring ownership -- never use the source after.

## Error Handling

Use `std::expected<T, E>` (C++23) for functions that can fail. It returns either a value or a typed error, without the overhead or control-flow surprises of exceptions.

```cpp
#include <expected>
#include <fstream>
#include <string>
#include <system_error>

enum class ParseError {
    kFileNotFound,
    kMalformedInput,
    kOutOfRange,
};

std::expected<Config, ParseError> LoadConfig(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        return std::unexpected(ParseError::kFileNotFound);
    }

    auto data = ReadAll(file);  // RAII: file closes on return
    if (!IsValid(data)) {
        return std::unexpected(ParseError::kMalformedInput);
    }

    return Config{.data = std::move(data)};
}

// Caller
void Run() {
    auto result = LoadConfig("app.toml");
    if (!result) {
        LOG(ERROR) << "Config failed: " << static_cast<int>(result.error());
        return;
    }
    UseConfig(result.value());
}
```

**When to use what:**

- `std::expected` -- recoverable failures (file I/O, parsing, network).
- Exceptions -- truly exceptional, unrecoverable errors (out of memory, invariant violation).
- `noexcept` -- mark functions that must not throw (move constructors, destructors, swap).

## Project Structure

```
myproject/
  CMakeLists.txt              # root: project name, C++ standard, add_subdirectory()
  cmake/
    FindSomeLib.cmake         # custom find modules
  include/
    myproject/
      core.h                  # public headers, mirrors src/ layout
      parser.h
  src/
    CMakeLists.txt            # add_library(myproject_lib ...)
    core.cc
    parser.cc
  apps/
    CMakeLists.txt            # add_executable(myproject_app ...)
    main.cc
  tests/
    CMakeLists.txt            # link gtest, add_test()
    core_test.cc
    parser_test.cc
  third_party/                # vendored deps or git submodules
```

Root `CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.20)
project(myproject LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_subdirectory(src)
add_subdirectory(apps)
enable_testing()
add_subdirectory(tests)
```

## Testing

Use [GoogleTest](https://google.github.io/googletest/primer.html). `EXPECT_*` continues after failure (prefer this). `ASSERT_*` aborts the test (use when the rest of the test would crash).

```cpp
#include "myproject/parser.h"

#include <gtest/gtest.h>

// Simple test
TEST(ParserTest, ParsesValidInput) {
    auto result = Parse("key=value");
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->key, "key");
    EXPECT_EQ(result->value, "value");
}

// Fixture: shared setup across tests
class ParserFixture : public ::testing::Test {
  protected:
    void SetUp() override {
        parser_ = std::make_unique<Parser>(DefaultConfig());
    }

    std::unique_ptr<Parser> parser_;
};

TEST_F(ParserFixture, RejectsEmptyInput) {
    auto result = parser_->Parse("");
    EXPECT_FALSE(result.has_value());
    EXPECT_EQ(result.error(), ParseError::kMalformedInput);
}

TEST_F(ParserFixture, HandlesMultipleEntries) {
    auto result = parser_->ParseAll("a=1\nb=2\nc=3");
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->size(), 3);
}
```

## Common Gotchas

**1. Dangling references from temporaries**

```cpp
const std::string& name = GetUser().name();  // GetUser() returns by value
// name now dangles -- the temporary User is destroyed
```

Fix: store by value, or keep the parent object alive.

**2. Use-after-move**

```cpp
std::vector<int> data = {1, 2, 3};
auto other = std::move(data);
data.push_back(4);  // UB or empty vector -- don't touch data after move
```

Fix: treat moved-from objects as dead. Re-assign before reuse.

**3. Object slicing**

```cpp
class Base { virtual void DoWork(); };
class Derived : public Base { void DoWork() override; };

void Process(Base b) { b.DoWork(); }  // copies only the Base part!
Derived d;
Process(d);  // Derived::DoWork() is NOT called
```

Fix: pass by reference or pointer (`const Base& b`).

**4. Iterator invalidation**

```cpp
std::vector<int> v = {1, 2, 3};
for (auto it = v.begin(); it != v.end(); ++it) {
    if (*it == 2) v.push_back(4);  // invalidates all iterators
}
```

Fix: collect mutations, apply after the loop. Or use `std::erase_if` (C++20).

**5. Header include order hiding missing includes**

If `a.h` happens to include `<string>` and `b.cc` includes `a.h` before using `std::string`, removing `a.h` later breaks `b.cc`. Always include what you use.

## Best Practices

1. **Prefer value semantics.** Pass small types by value, large types by `const&`. Return by value (NRVO handles it).
2. **Use `std::unique_ptr` by default.** Reach for `shared_ptr` only when you genuinely have shared ownership. If you need a non-owning reference, use a raw pointer or `std::string_view`.
3. **Mark single-argument constructors `explicit`.** Prevents silent implicit conversions that cause confusing bugs.
4. **Use `[[nodiscard]]` on functions that return errors.** The compiler warns if the caller ignores the return value.
5. **Default to `const`.** Variables, member functions, parameters. Mutability is the exception.
6. **Prefer `enum class` over plain `enum`.** Scoped enums prevent implicit int conversions and namespace pollution.
7. **Never use `using namespace std;` in headers.** It pollutes every file that includes your header.
8. **Compile with warnings maxed out.** `-Wall -Wextra -Wpedantic -Werror`. Treat warnings as errors in CI.
9. **Use sanitizers in dev builds.** `-fsanitize=address,undefined` catches memory errors and UB that tests alone miss.
10. **Follow the Rule of Five (or Zero).** If you define any of destructor/copy-ctor/copy-assign/move-ctor/move-assign, define all five. Better yet, use RAII members and define none.
