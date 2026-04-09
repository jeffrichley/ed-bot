# Swift

## Style & Naming

**Types and protocols** use `UpperCamelCase`. **Everything else** uses `lowerCamelCase`. Acronyms follow case uniformly: `utf8Bytes`, `isRepresentableAsASCII`.

**Clarity at the point of use** is the top priority. No abbreviations unless universally understood (`url`, `id`). Protocols that describe "what something is" use nouns (`Collection`). Capability protocols use `-able`/`-ible`/`-ing` (`Equatable`, `ProgressReporting`).

**Files** named after primary type: `OrderParser.swift`. Extensions: `OrderParser+Codable.swift`. Imports grouped: standard library, third-party, your modules.

```swift
import Foundation
import os

import Alamofire

import MyNetworkingKit

struct OrderParser {
    let dateFormatter: DateFormatter
    var orderCount: Int { orders.count }
    private var orders: [Order] = []
}
```

## Idioms

**Use `guard` for early exits, not nested `if let`.**

```swift
// Bad: nested optionals
func process(data: Data?) {
    if let data = data {
        if let string = String(data: data, encoding: .utf8) { print(string) }
    }
}
// Good: guard for early exit
func process(data: Data?) {
    guard let data, let string = String(data: data, encoding: .utf8) else { return }
    print(string)
}
```

**Prefer value types. Use classes only when you need identity or inheritance.**

```swift
// Non-idiomatic: class for pure data
class Point { var x: Double; var y: Double; init(x: Double, y: Double) { self.x = x; self.y = y } }

// Idiomatic: struct with synthesized memberwise init
struct Point { var x: Double; var y: Double }
```

**Protocol extensions for default behavior, not base classes.**

```swift
protocol Describable { var name: String { get } }
extension Describable { var description: String { "Item: \(name)" } }
```

**Trailing closures** for single-closure args. Multiple closures: label all inside parens.

```swift
let evens = numbers.filter { $0.isMultiple(of: 2) }  // trailing
UIView.animate(withDuration: 0.3, animations: { view.alpha = 1.0 },
               completion: { _ in view.removeFromSuperview() })  // labeled
```

## Error Handling

Define domain errors conforming to `Error`. Use `do`/`try`/`catch` for recoverable failures. Use `Result` at async boundaries.
```swift
enum NetworkError: Error, LocalizedError {
    case invalidURL(String)
    case timeout(seconds: Int)
    case unauthorized

    var errorDescription: String? {
        switch self {
        case .invalidURL(let url): return "Invalid URL: \(url)"
        case .timeout(let s): return "Timed out after \(s)s"
        case .unauthorized: return "Authentication required"
        }
    }
}

func fetchUser(id: Int) throws -> User {
    guard let url = URL(string: "https://api.example.com/users/\(id)") else {
        throw NetworkError.invalidURL("/users/\(id)")
    }
    let (data, _) = try URLSession.shared.data(from: url)
    return try JSONDecoder().decode(User.self, from: data)
}

do {
    let user = try fetchUser(id: 42)
} catch let error as NetworkError {
    print(error.localizedDescription)
} catch {
    print("Unexpected: \(error)")
}
```

Never use `try!` outside of tests. Use `try?` only when you genuinely want to discard the error.

## Project Structure

Canonical SPM layout. Every new project starts here unless Xcode-only.
```
MyPackage/
  Package.swift
  Sources/MyPackage/
    Models/User.swift
    Networking/APIClient.swift
    Networking/APIClient+Auth.swift
    MyPackage.swift
  Tests/MyPackageTests/
    UserTests.swift
    APIClientTests.swift
```

```swift
// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "MyPackage",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [.library(name: "MyPackage", targets: ["MyPackage"])],
    dependencies: [
        .package(url: "https://github.com/apple/swift-log.git", from: "1.5.0"),
    ],
    targets: [
        .target(name: "MyPackage", dependencies: [.product(name: "Logging", package: "swift-log")]),
        .testTarget(name: "MyPackageTests", dependencies: ["MyPackage"]),
    ]
)
```

## Testing

Test classes inherit `XCTestCase`. Name tests `test_<unit>_<scenario>_<expected>`. Use `setUp()` for fixtures, `tearDown()` for cleanup. `try!` and force-unwrap are fine in tests.

```swift
import XCTest
@testable import MyPackage

final class UserTests: XCTestCase {
    private var sut: UserService!

    override func setUp() {
        super.setUp()
        sut = UserService(store: MockUserStore())
    }

    override func tearDown() { sut = nil; super.tearDown() }

    func test_fetchUser_validID_returnsUser() throws {
        let user = try sut.fetch(id: 1)
        XCTAssertEqual(user.name, "Alice")
    }

    func test_fetchUser_invalidID_throwsNotFound() {
        XCTAssertThrowsError(try sut.fetch(id: -1)) { error in
            XCTAssertEqual(error as? UserError, .notFound)
        }
    }
}
```

## Common Gotchas

**1. Retain cycles in closures.** Closures capture `self` strongly by default. Stored closures on `self` create cycles.

```swift
// Leak
onUpdate = { self.refresh() }
// Fix
onUpdate = { [weak self] in self?.refresh() }
```

**2. Force unwrapping crashes at runtime.** Never use `!` outside of tests or `IBOutlet`s. Use `guard let`, `if let`, or `??`.

**3. Value type copying.** Structs copy on assignment. Mutating a copy does not affect the original.

**4. `weak` vs `unowned`.** Use `weak` when the reference can become nil. `unowned` on a deallocated object crashes. Default to `weak`.

**5. Sendable and concurrency.** Swift 6 enforces `Sendable` checking. Non-Sendable types cannot cross actor boundaries. Use `@unchecked Sendable` sparingly.

## Best Practices

- **Prefer `let` over `var`.** Immutability by default. Only use `var` when mutation is required.
- **Default to `private`.** Expose minimum API surface: `private` > `fileprivate` > `internal` > `public`.
- **Conform to `Equatable`/`Hashable`/`Codable` via synthesis.** Only write manual conformances when the compiler gets it wrong.
- **Name mutating/nonmutating pairs correctly.** `sort()` mutates, `sorted()` returns. `formUnion()` mutates, `union()` returns.
- **Use `// MARK:` comments** to organize: lifecycle, public API, private helpers, conformances.
- **Avoid stringly-typed code.** Enums with associated values over raw strings for states and categories.
- **Lean on the type system.** `URL` over `String`, `Measurement<UnitLength>` over `Double`, newtypes for domain IDs.
- **Keep optionals shallow.** If you have `String??`, rethink the data model.
- **Use property wrappers and result builders** when they reduce boilerplate, not to show off.
