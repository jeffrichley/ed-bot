# PHP

## Style & Naming

Follow PSR-12. Use `php-cs-fixer` or `phpcs` to enforce it automatically.

| Thing       | Convention          | Example                |
|-------------|---------------------|------------------------|
| Variable    | `$camelCase`        | `$userCount`           |
| Function    | `camelCase`         | `getActiveUsers()`     |
| Class       | `PascalCase`        | `UserAccount`          |
| Interface   | `PascalCase`        | `Cacheable`            |
| Constant    | `UPPER_SNAKE_CASE`  | `MAX_RETRIES`          |
| Enum        | `PascalCase`        | `Status::Active`       |
| File        | match class name    | `UserAccount.php`      |
| Namespace   | `PascalCase`        | `App\Services`         |

Namespace and use ordering: `use` after `namespace`, one blank line between. Group: PHP core, third-party, project-local. Alphabetize within groups.

```php
<?php
declare(strict_types=1);
namespace App\Services;

use DateTimeImmutable;
use GuzzleHttp\ClientInterface;
use App\Models\User;
```

PSR-4 autoloading: namespace `App\Services` maps to `src/Services/`. One class per file. No closing `?>` tag.

## Idioms

Write modern PHP 8.x, not PHP 5 with a new version number.

**Constructor promotion + readonly: kill the boilerplate**

```php
// No: manual property assignment
class UserService {
    private UserRepository $repo;
    private LoggerInterface $logger;
    public function __construct(UserRepository $repo, LoggerInterface $logger) {
        $this->repo = $repo;
        $this->logger = $logger;
    }
}

// Yes: constructor promotion with readonly
class UserService {
    public function __construct(
        private readonly UserRepository $repo,
        private readonly LoggerInterface $logger,
    ) {}
}
```

**Enums + match: replace string constants and switch**

```php
// No: stringly-typed with switch
function getStatusColor(string $status): string {
    switch ($status) {
        case 'pending': return 'yellow';
        case 'active':  return 'green';
        default:        return 'black';
    }
}

// Yes: backed enum with match
enum Status: string {
    case Pending = 'pending';
    case Active  = 'active';

    public function color(): string {
        return match ($this) {
            self::Pending => 'yellow',
            self::Active  => 'green',
        };
    }
}
```

**Arrow functions + first-class callables + named arguments**

```php
// No
$users = array_filter($users, function ($u) { return $u->isActive(); });
$result = array_map(function ($n) { return strtoupper($n); }, $names);

// Yes
$users = array_filter($users, fn(User $u) => $u->isActive());
$result = array_map(strtoupper(...), $names);
$user = new User(name: 'Ada Lovelace', email: 'ada@example.com', role: Role::Admin);
```

## Error Handling

Use exceptions, not return codes. Catch the narrowest type. Always declare `strict_types`.

```php
class ServiceException extends \RuntimeException {}

class NotFoundException extends ServiceException {
    public function __construct(
        public readonly string $resource,
        public readonly string|int $resourceId,
    ) {
        parent::__construct("{$resource} '{$resourceId}' not found");
    }
}
```

```php
public function fetchOrder(int $id): Order {
    try {
        $response = $this->client->get("/orders/{$id}");
        return Order::fromArray($response->json());
    } catch (ClientException $e) {
        if ($e->getCode() === 404) {
            throw new NotFoundException('Order', $id);
        }
        throw new UpstreamException("Order API failed: {$e->getMessage()}", previous: $e);
    } finally {
        $this->logger->info('Order fetch attempted', ['id' => $id]);
    }
}
```

Convert legacy warnings to exceptions:

```php
set_error_handler(function (int $severity, string $msg, string $file, int $line): never {
    throw new \ErrorException($msg, 0, $severity, $file, $line);
});
```

## Project Structure

Standard Composer project with PSR-4 autoloading.

```
myproject/
    src/
        Models/          User.php, Order.php
        Services/        UserService.php
        Repositories/    UserRepository.php
        Exceptions/      ServiceException.php, NotFoundException.php
    tests/
        Unit/            Services/UserServiceTest.php
        Integration/     Repositories/UserRepositoryTest.php
    public/              index.php
    composer.json
    phpunit.xml
    phpstan.neon
```

Minimal `composer.json`:

```json
{
    "require": { "php": ">=8.2" },
    "require-dev": {
        "phpunit/phpunit": "^11.0",
        "phpstan/phpstan": "^2.0"
    },
    "autoload": { "psr-4": { "App\\": "src/" } },
    "autoload-dev": { "psr-4": { "Tests\\": "tests/" } }
}
```

## Testing

Use PHPUnit. Name test classes `*Test.php`, methods `test_description_of_behavior`. Data providers for parameterized tests. `createMock()` for dependencies.

```php
class UserServiceTest extends TestCase
{
    #[Test]
    public function test_find_returns_user_when_exists(): void {
        $repo = $this->createMock(UserRepository::class);
        $repo->method('findById')->with(42)->willReturn(new User(id: 42, name: 'Ada'));

        $service = new UserService(repo: $repo);
        $this->assertSame('Ada', $service->find(42)->name);
    }

    #[Test]
    public function test_find_throws_when_not_found(): void {
        $repo = $this->createMock(UserRepository::class);
        $repo->method('findById')->willReturn(null);

        $this->expectException(NotFoundException::class);
        (new UserService(repo: $repo))->find(999);
    }

    #[Test]
    #[DataProvider('emailProvider')]
    public function test_email_validation(string $email, bool $valid): void {
        if (!$valid) {
            $this->expectException(\InvalidArgumentException::class);
        }
        new User(id: 1, name: 'Test', email: $email);
        $this->assertTrue($valid);
    }

    public static function emailProvider(): iterable {
        yield 'valid email'    => ['user@example.com', true];
        yield 'missing domain' => ['user@', false];
        yield 'empty string'   => ['', false];
    }
}
```

Run with: `./vendor/bin/phpunit --testdox --colors`

## Common Gotchas

**1. Loose comparison (`==`) is a minefield**

```php
0 == 'foobar'         // true -- string coerces to 0
'0e1234' == '0e5678'  // true -- both are float 0
// Fix: always use === and pass strict: true to in_array(), array_search(), etc.
```

**2. Array keys silently coerce**

```php
$a = [];
$a[true] = 'a';  // key becomes 1
$a[null] = 'b';  // key becomes ''
$a[1.7]  = 'c';  // key becomes 1, overwrites 'a'
count($a); // 2, not 3
```

**3. `empty()` is almost never what you want**

```php
empty('0')  // true -- the string "0" is considered empty
// Be explicit: if ($value !== '' && $value !== null) { ... }
```

**4. Arrays copy on pass, objects pass by reference**

```php
function addItem(array $cart): array {
    $cart[] = 'item';
    return $cart;  // caller's $cart is unchanged -- arrays are copied
}
// Objects are passed by handle -- mutations affect the original
```

**5. `DateTime` mutates, `DateTimeImmutable` doesn't**

```php
$date = new DateTime('2025-01-01');
$date->modify('+1 day');  // $date is now Jan 2 -- mutated in place

$date = new DateTimeImmutable('2025-01-01');
$next = $date->modify('+1 day');  // $date is still Jan 1 -- safe
```

## Best Practices

- **`declare(strict_types=1)` in every file.** Without it, PHP silently coerces `"123abc"` to `123` for an `int` parameter.
- **Type everything.** Parameters, return types, properties. Union types (`int|string`), `never` for throws, `void` for no return.
- **Prefer `readonly` properties and classes.** Immutability by default. DTOs should be `readonly class`.
- **Use enums instead of class constants for finite sets.** `Status::Active` is type-safe and exhaustive in `match`.
- **Inject dependencies, don't create them.** Pass `LoggerInterface`, not `new Logger()`.
- **Use `DateTimeImmutable` over `DateTime`.** Always.
- **`match` over `switch`.** Strict comparison, returns a value, throws on unhandled cases.
- **Run PHPStan at level 8+ in CI.** Catches nulls, wrong types, and dead code before runtime.
- **Composer autoloading only.** No `require`/`include` for your own classes. If you're writing `require_once`, something is wrong.
