# Kotlin

## Style & Naming

- **Classes/objects**: `PascalCase` -- `UserRepository`, `HttpClient`
- **Functions/properties**: `camelCase` -- `fetchUser`, `isValid`
- **Constants** (`const val`, top-level `val`): `UPPER_SNAKE` -- `MAX_RETRIES`, `DEFAULT_TIMEOUT`
- **Packages**: all lowercase, no underscores -- `org.example.myproject`
- **Files**: match the primary class name (`UserRepository.kt`), or descriptive PascalCase for multi-declaration files (`StringExtensions.kt`)
- **Acronyms**: two letters both caps (`IOStream`), longer capitalize first only (`HttpClient`, `XmlParser`)
- **Backing properties**: underscore prefix for private mutable state

```kotlin
const val MAX_CONNECTIONS = 10

class UserRepository(private val api: UserApi) {
    private val _users = mutableListOf<User>()
    val users: List<User> get() = _users

    fun fetchActiveUsers(): List<User> = api.getUsers().filter { it.isActive }
}
```

## Idioms

Use data classes, not hand-rolled POJOs. Use `when` as an expression. Prefer `val` over `var`. Use scope functions for configuration and null handling.

**Non-idiomatic vs idiomatic -- null handling:**

```kotlin
// Non-idiomatic
fun getDisplayName(user: User?): String {
    if (user != null) {
        if (user.nickname != null) {
            return user.nickname
        }
        return user.fullName
    }
    return "Anonymous"
}

// Idiomatic
fun getDisplayName(user: User?): String =
    user?.nickname ?: user?.fullName ?: "Anonymous"
```

**Non-idiomatic vs idiomatic -- object configuration:**

```kotlin
// Non-idiomatic
val config = ServerConfig()
config.host = "localhost"
config.port = 8080
config.ssl = true

// Idiomatic
val config = ServerConfig().apply {
    host = "localhost"
    port = 8080
    ssl = true
}
```

**Non-idiomatic vs idiomatic -- type checking:**

```kotlin
// Non-idiomatic
fun describe(shape: Shape): String {
    if (shape is Circle) return "Circle r=${shape.radius}"
    else if (shape is Rectangle) return "Rect ${shape.w}x${shape.h}"
    else return "Unknown"
}

// Idiomatic
fun describe(shape: Shape): String = when (shape) {
    is Circle -> "Circle r=${shape.radius}"
    is Rectangle -> "Rect ${shape.w}x${shape.h}"
    else -> "Unknown"
}
```

**Scope function cheat sheet:**
- `let` -- transform nullable or scoped value: `user?.let { save(it) }`
- `run` -- compute something in object context: `service.run { fetchAll() }`
- `apply` -- configure and return the object: `Widget().apply { color = RED }`
- `also` -- side effects, return the object: `list.also { println(it.size) }`
- `with` -- multiple calls on the same object: `with(canvas) { drawLine(); drawCircle() }`

## Error Handling

All Kotlin exceptions are unchecked. Use `require` for argument validation, `check` for state validation, and `runCatching`/`Result` for functional error chains.

```kotlin
class UserService(private val repo: UserRepository) {

    fun activateUser(userId: String): Result<User> {
        require(userId.isNotBlank()) { "userId must not be blank" }

        return runCatching { repo.findById(userId) }
            .onFailure { e -> logger.error("Lookup failed for $userId", e) }
            .map { user ->
                check(!user.isBanned) { "Cannot activate banned user ${user.id}" }
                user.copy(active = true)
            }
            .onSuccess { repo.save(it) }
    }
}

// Calling code
service.activateUser(id)
    .onSuccess { println("Activated: ${it.name}") }
    .onFailure { println("Failed: ${it.message}") }

// Or extract value with fallback
val user = service.activateUser(id).getOrElse { defaultUser }
```

Custom exceptions when you need domain-specific types:

```kotlin
class EntityNotFoundException(val id: String) : RuntimeException("Entity not found: $id")
class ValidationException(val field: String, message: String) : IllegalArgumentException(message)
```

## Project Structure

```
my-project/
  build.gradle.kts
  settings.gradle.kts
  src/
    main/
      kotlin/
        com/example/myproject/
          model/
            User.kt
          repository/
            UserRepository.kt
          service/
            UserService.kt
      resources/
        application.conf
    test/
      kotlin/
        com/example/myproject/
          service/
            UserServiceTest.kt
      resources/
        test-data.json
```

Package directories mirror the package declaration. `build.gradle.kts` uses the Kotlin DSL. Multi-module projects use `settings.gradle.kts` to declare included modules.

## Testing

JUnit 5 with MockK for mocking and Kotest matchers for assertions. Use backtick names for readability.

```kotlin
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class UserServiceTest {

    private val repo: UserRepository = mockk()
    private val service = UserService(repo)

    @BeforeEach
    fun reset() = clearAllMocks()

    @Test
    fun `activateUser returns active user when found`() {
        val user = User(id = "u1", name = "Ada", active = false, isBanned = false)
        every { repo.findById("u1") } returns user
        every { repo.save(any()) } just runs

        val result = service.activateUser("u1")

        result.isSuccess shouldBe true
        result.getOrThrow().active shouldBe true
        verify { repo.save(match { it.active && it.id == "u1" }) }
    }

    @Test
    fun `activateUser fails for blank userId`() {
        shouldThrow<IllegalArgumentException> {
            service.activateUser("")
        }.message shouldContain "must not be blank"
    }

    @Nested
    inner class EdgeCases {
        @Test
        fun `activateUser fails when user is banned`() {
            val banned = User(id = "u2", name = "Eve", active = false, isBanned = true)
            every { repo.findById("u2") } returns banned

            val result = service.activateUser("u2")

            result.isFailure shouldBe true
            result.exceptionOrNull() shouldBe instanceOf<IllegalStateException>()
        }
    }
}
```

Use test helper factories with default arguments instead of complex builders:

```kotlin
fun createUser(
    id: String = "test-id",
    name: String = "Test User",
    active: Boolean = false,
    isBanned: Boolean = false,
) = User(id = id, name = name, active = active, isBanned = isBanned)
```

## Common Gotchas

**1. Platform types from Java interop.** Java methods return platform types (`String!`) that bypass null safety. Always declare an explicit Kotlin type when storing Java return values.

```kotlin
// Dangerous -- name is String! (platform type), could be null at runtime
val name = javaApi.getName()

// Safe -- compiler enforces null checks
val name: String = javaApi.getName()       // throws immediately if null
val name: String? = javaApi.getName()      // forces you to handle null
```

**2. `data class copy()` with mutable properties.** `copy()` is shallow. Mutable properties inside a data class are shared between the original and the copy.

```kotlin
data class Config(val tags: MutableList<String>)
val a = Config(mutableListOf("v1"))
val b = a.copy()
b.tags.add("v2")
println(a.tags)  // [v1, v2] -- both mutated! Use immutable collections.
```

**3. Coroutine cancellation swallowed by catch-all.** Catching `Exception` or `Throwable` inside a coroutine swallows `CancellationException`, creating zombie coroutines.

```kotlin
// Broken -- swallows cancellation
try { riskyWork() } catch (e: Exception) { log(e) }

// Correct -- rethrow cancellation
try { riskyWork() } catch (e: Exception) {
    coroutineContext.ensureActive()
    log(e)
}
```

**4. `lateinit` on primitives or nullables.** `lateinit` only works with `var` of non-null, non-primitive types. Use `by lazy` for `val` initialization, and `Delegates.notNull<Int>()` for primitives.

**5. SAM conversion ambiguity.** When a Kotlin function takes multiple SAM interfaces, lambda syntax can get confusing. Name your lambdas or use explicit `object :` syntax for clarity.

```kotlin
// Unclear which lambda is which
executor.schedule({ doWork() }, { handleError() })

// Clear
executor.schedule(
    action = Runnable { doWork() },
    errorHandler = ErrorHandler { handleError() },
)
```

## Best Practices

- **Prefer immutable data.** Use `val`, immutable collections (`List`, `Map`), and `data class` with `val` properties. Mutability is opt-in, not the default.
- **Use sealed classes for restricted hierarchies.** Model finite state (API results, UI states, navigation events) with `sealed class` or `sealed interface` so `when` is exhaustive without `else`.
- **Use `require`/`check` at boundaries.** Validate inputs with `require` (throws `IllegalArgumentException`) and state with `check` (throws `IllegalStateException`) at public function entry points.
- **Prefer expression bodies for short functions.** `fun isAdult(age: Int): Boolean = age >= 18` is clearer than a block body with `return`.
- **Use `sequence` for lazy pipelines.** When chaining `filter`/`map`/`take` on large collections, `asSequence()` avoids intermediate list allocations.
- **Scope functions should clarify, not obscure.** If nesting more than two scope functions, extract a named function instead. Readability beats conciseness.
- **Explicit return types on public API.** Let the compiler infer types inside function bodies, but always declare return types on public/protected members.
- **Prefer `listOf`/`mapOf`/`setOf` over constructor calls.** `listOf("a", "b")` instead of `ArrayList<String>().apply { add("a"); add("b") }`.
- **Use structured concurrency.** Launch coroutines in a defined scope (`viewModelScope`, `coroutineScope`). Never use `GlobalScope` in production code.
- **Use trailing commas.** They make diffs cleaner and reordering painless.
