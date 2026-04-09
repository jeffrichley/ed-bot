# Ruby

## Style & Naming

Follow the [RuboCop community style guide](https://rubystyle.guide/). Use `rubocop` to enforce it automatically.

| Thing       | Convention           | Example                |
|-------------|----------------------|------------------------|
| Variable    | `snake_case`         | `user_count`           |
| Method      | `snake_case`         | `fetch_active_users`   |
| Predicate   | `snake_case?`        | `valid?`, `admin?`     |
| Mutating    | `snake_case!`        | `sort!`, `flatten!`    |
| Class       | `PascalCase`         | `UserAccount`          |
| Module      | `PascalCase`         | `Serializable`         |
| Constant    | `SCREAMING_SNAKE`    | `MAX_RETRIES`          |
| File        | `snake_case.rb`      | `user_account.rb`      |

Bang methods (`!`) only exist when a safe counterpart exists. Predicate methods (`?`) always return a boolean. Don't prefix predicates with `is_` or `has_`.

```ruby
class User
  attr_reader :name, :role

  def admin?
    role == :admin
  end

  def normalize_name!
    @name = name.strip.downcase
  end

  def normalize_name
    name.strip.downcase
  end
end
```

## Idioms

Write Ruby, not Java-in-Ruby. Lean on blocks, Enumerable, and implicit return.

**Use map/select/reject, not manual accumulation**

```ruby
# No
result = []
users.each { |u| result << u.name if u.active? }

# Yes
result = users.select(&:active?).map(&:name)
```

**Guard clauses over nested conditionals**

```ruby
# No
def process(order)
  if order
    if order.valid?
      order.submit
    end
  end
end

# Yes
def process(order)
  return unless order
  return unless order.valid?

  order.submit
end
```

**unless for simple negation, modifier form for one-liners**

```ruby
# No
if !user.suspended?
  user.notify
end

# Yes
user.notify unless user.suspended?
```

**Symbol to_proc and implicit return**

```ruby
# No
names = users.map { |u| u.name }
def full_name
  return "#{first_name} #{last_name}"
end

# Yes
names = users.map(&:name)
def full_name
  "#{first_name} #{last_name}"
end
```

**Memoization with ||=, string interpolation, %w/%i literals**

```ruby
@current_user ||= User.find(session[:user_id])

greeting = "Hello #{user.name}, you have #{count} messages"

STATES  = %w[draft published archived].freeze
ACTIONS = %i[create update destroy].freeze
```

## Error Handling

Inherit custom exceptions from `StandardError`, never from `Exception` (that catches signals and syntax errors). Rescue specific classes, most specific first.

```ruby
module Billing
  class Error < StandardError; end

  class CardDeclinedError < Error
    attr_reader :card_last_four

    def initialize(card_last_four)
      @card_last_four = card_last_four
      super("Card ending in #{card_last_four} was declined")
    end
  end

  class RateLimitError < Error; end
end

class PaymentService
  MAX_RETRIES = 3

  def charge(amount, card)
    retries = 0
    begin
      gateway.charge(amount, card.token)
    rescue Billing::RateLimitError => e
      retries += 1
      retry if retries < MAX_RETRIES
      raise
    rescue Billing::CardDeclinedError => e
      notify_user(e.card_last_four)
      false
    ensure
      log_attempt(amount, card)
    end
  end
end
```

Use the implicit `begin` in methods when the entire body needs rescue:

```ruby
def fetch_data(url)
  HTTP.get(url).parse
rescue HTTP::TimeoutError
  { error: "timed out" }
end
```

## Project Structure

Standard gem/library layout. Use `bundler` for dependency management.

```
myproject/
    lib/
        myproject.rb              # entry point, requires submodules
        myproject/
            version.rb
            client.rb
            models/
                user.rb
    spec/
        spec_helper.rb
        myproject/
            client_spec.rb
            models/
                user_spec.rb
    Gemfile
    myproject.gemspec
    Rakefile
    .rubocop.yml
    .gitignore
```

`lib/myproject.rb` wires everything together:

```ruby
require_relative "myproject/version"
require_relative "myproject/client"
require_relative "myproject/models/user"
```

## Testing

Use RSpec. Structure: `describe` the class, `context` for scenarios, `it` for behaviors. Use `let` for lazy values, `before` for setup.

```ruby
# spec/myproject/client_spec.rb
require "spec_helper"

RSpec.describe Myproject::Client do
  subject(:client) { described_class.new(api_key: "test-key") }

  let(:user_data) { { name: "Ada", email: "ada@example.com" } }

  describe "#create_user" do
    context "when the API responds successfully" do
      before do
        stub_request(:post, "https://api.example.com/users")
          .to_return(status: 201, body: user_data.to_json)
      end

      it "returns a User with the correct name" do
        user = client.create_user(user_data)
        expect(user.name).to eq("Ada")
      end

      it "sends the payload as JSON" do
        client.create_user(user_data)
        expect(WebMock).to have_requested(:post, /users/)
          .with(body: user_data.to_json)
      end
    end

    context "when the API returns 422" do
      before do
        stub_request(:post, "https://api.example.com/users")
          .to_return(status: 422, body: '{"error":"invalid"}')
      end

      it "raises a validation error" do
        expect { client.create_user(user_data) }
          .to raise_error(Myproject::ValidationError, /invalid/)
      end
    end
  end
end
```

Run with: `bundle exec rspec --format documentation`.

## Common Gotchas

**1. `nil` is an object, and it's everywhere**

```ruby
nil.class        # => NilClass
nil.to_a         # => []
nil.to_s         # => ""
nil.to_i         # => 0
nil.respond_to?(:empty?)  # => false -- but NoMethodError if you call it

# Use the safe navigation operator or explicit checks
user&.profile&.avatar_url
```

**2. Strings are mutable by default**

```ruby
greeting = "hello"
greeting << " world"    # mutates the original string
greeting.freeze         # now raises FrozenError on mutation

# Add to the top of every file:
# frozen_string_literal: true
```

**3. `==` vs `equal?` vs `eql?`**

```ruby
a = "hello"
b = "hello"
a == b       # true  -- same value
a.equal?(b)  # false -- different objects (identity check)
a.eql?(b)    # true  -- same value and same type (used by Hash for keys)

# Use == for value comparison. Use equal? only when you need identity.
```

**4. `require` vs `require_relative`**

```ruby
require "json"                    # searches $LOAD_PATH -- for gems/stdlib
require_relative "lib/helpers"    # relative to current file -- for your own code
# Mixing them up causes LoadError or loads the wrong file.
```

**5. Monkey patching bites back**

```ruby
# This is legal but dangerous -- affects ALL strings globally
class String
  def blank?
    strip.empty?
  end
end

# Use refinements instead for scoped behavior
module StringExtensions
  refine String do
    def blank?
      strip.empty?
    end
  end
end
```

## Best Practices

- **Freeze string literals.** Put `# frozen_string_literal: true` at the top of every file. Catches accidental mutation and improves performance.
- **Prefer keyword arguments over positional for 2+ parameters.** `def transfer(from:, to:, amount:)` beats `def transfer(from, to, amount)` for readability at call sites.
- **Use `fetch` on hashes instead of bracket access.** `config.fetch(:timeout)` raises `KeyError` on typos; `config[:tiemout]` silently returns `nil`.
- **Freeze your constants.** `STATES = %w[draft published].freeze` prevents accidental mutation. Without `freeze`, anyone can `STATES << "broken"`.
- **Prefer `each_with_object` over `inject`/`reduce` for building hashes and arrays.** It reads left-to-right and avoids the "forgot to return the accumulator" bug.
- **Use `Struct` or `Data` (Ruby 3.2+) for simple value objects.** Don't write a full class when you just need a named container.
- **Run `rubocop --autocorrect` before every commit.** Let the machine handle formatting debates. Configure `.rubocop.yml` once, then stop arguing.
- **Avoid class variables (`@@var`).** They leak across the entire inheritance hierarchy. Use class instance variables (`@var` inside `self` methods) instead.
- **Prefer `public_send` over `send`.** `send` bypasses method visibility, which hides bugs and breaks encapsulation. Reserve `send` for test helpers only.
