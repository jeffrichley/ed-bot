# SQL

## Style & Naming

Lowercase for keywords. Lowercase `snake_case` for everything else. Enforce with [SQLFluff](https://sqlfluff.com/).

| Thing       | Convention          | Example                |
|-------------|---------------------|------------------------|
| Table       | `snake_case`        | `user_account`         |
| Column      | `snake_case`        | `created_at`           |
| Primary key | `<table>_id`        | `order_id`             |
| Foreign key | `<referenced>_id`   | `user_id`              |
| Index       | `ix_<table>_<cols>` | `ix_order_user_id`     |
| Constraint  | `<type>_<table>_<detail>` | `uq_user_email`  |
| Boolean     | `is_` / `has_`      | `is_active`            |

No prefixes like `tbl_` or `vw_`. Singular table names. Always use explicit `as` for aliases. Avoid single-letter aliases in joins. Trailing commas.

```sql
select
    o.order_id,
    o.created_at,
    u.full_name as customer_name,
    sum(li.quantity * li.unit_price) as order_total
from order as o
inner join user_account as u on u.user_id = o.user_id
inner join line_item as li on li.order_id = o.order_id
where o.created_at >= '2025-01-01'
group by 1, 2, 3
order by o.created_at desc;
```

Four-space indentation. One column per line in `select`. `and`/`or` at the start of the line. Keep lines under 100 characters.

## Idioms

Write modern SQL. CTEs over subqueries. Explicit joins over implicit. Window functions over self-joins.

**CTEs over nested subqueries**

```sql
-- No: nested subquery
select * from (
    select user_id, count(*) as order_count
    from order group by user_id
) as sub where sub.order_count > 5;

-- Yes: CTE reads top-to-bottom
with user_orders as (
    select user_id, count(*) as order_count
    from order
    group by 1
)
select * from user_orders where order_count > 5;
```

**EXISTS over IN for correlated checks**

```sql
-- No: IN with subquery (breaks when subquery returns NULLs)
select * from user_account where user_id in (select user_id from order);

-- Yes: EXISTS is explicit and NULL-safe
select * from user_account as u
where exists (select 1 from order as o where o.user_id = u.user_id);
```

**Window functions over self-joins**

```sql
-- No: self-join with correlated subquery to get previous row
select curr.*, prev.amount as prev_amount
from payment as curr
left join payment as prev
    on prev.user_id = curr.user_id
    and prev.created_at = (
        select max(created_at) from payment
        where user_id = curr.user_id and created_at < curr.created_at
    );

-- Yes: lag window function
select *, lag(amount) over (partition by user_id order by created_at) as prev_amount
from payment;
```

Other patterns to prefer: `coalesce(x, 0)` over `case when x is null`, `inner join` over bare `join`, `union all` over `union` unless you need dedup, `group by 1, 2` over repeating column names.

## Error Handling

Name your constraints. Wrap multi-statement changes in transactions. Use `savepoint` for partial rollback.

```sql
-- Named constraints make errors debuggable
create table user_account (
    user_id   bigint generated always as identity primary key,
    email     text not null constraint uq_user_email unique,
    full_name text not null,
    balance   numeric(12,2) not null default 0
        constraint ck_user_balance_nonneg check (balance >= 0),
    created_at timestamptz not null default now()
);

-- Transaction with savepoint for partial rollback
begin;
    insert into user_account (email, full_name) values ('ada@example.com', 'Ada Lovelace');
    savepoint before_transfer;
    update user_account set balance = balance - 100 where email = 'ada@example.com';
    update user_account set balance = balance + 100 where email = 'bob@example.com';
    -- check row count in app code; if 0: rollback to savepoint before_transfer;
commit;

-- Upsert: insert or update on conflict
insert into user_setting (user_id, setting_key, setting_value)
values (42, 'theme', 'dark')
on conflict (user_id, setting_key)
do update set setting_value = excluded.setting_value;
```

Defensive patterns: use `on conflict` for upserts, `where exists` before updates, and always check affected row counts in application code.

## Project Structure

```
db/
    migrations/
        0001_create_user_account.sql
        0002_create_order.sql
        0003_add_order_status_index.sql
    seeds/
        reference_data.sql
        dev_fixtures.sql
    schema/
        tables/
            user_account.sql
            order.sql
            line_item.sql
        views/
            order_summary.sql
        functions/
            calculate_total.sql
    tests/
        test_user_constraints.sql
        test_order_totals.sql
```

Migrations are numbered sequentially and represent one atomic schema change each. Never edit a migration after it has been applied. The `schema/` directory holds the current canonical DDL for reference. `seeds/` holds repeatable data loads.

## Testing

Use [pgTAP](https://pgtap.org/) for PostgreSQL. Tests are functions that return TAP-formatted output.

```sql
begin;
select plan(3);

select lives_ok(
    $$ insert into user_account (email, full_name) values ('test@example.com', 'Test User') $$,
    'Can insert a new user'
);
select throws_ok(
    $$ insert into user_account (email, full_name) values ('test@example.com', 'Dupe') $$,
    '23505', null, 'Duplicate email is rejected'  -- 23505 = unique_violation
);
select throws_ok(
    $$ update user_account set balance = -1 where email = 'test@example.com' $$,
    '23514', null, 'Negative balance is rejected'  -- 23514 = check_violation
);

select * from finish();
rollback;
```

For dbt projects, use `schema.yml` tests (`unique`, `not_null`, `accepted_values`, `relationships`) and custom `select` tests that return rows when something is wrong (zero rows = pass).

## Common Gotchas

**1. NULL comparisons with `=` instead of `IS`**. `where status = null` returns zero rows, always. Use `where status is null`. Same trap with `not in`: if the subquery returns any NULL, the entire expression evaluates to UNKNOWN. Use `not exists` instead.

**2. Implicit type coercion kills index usage**. `where phone_number = 5551234` when `phone_number` is `text` forces a cast on every row, skipping the index. Match your types: `where phone_number = '5551234'`.

**3. GROUP BY with non-aggregated columns**. MySQL silently picks arbitrary values for columns missing from `group by`. Postgres rejects it outright. Always list every non-aggregated column.

**4. DELETE or UPDATE without WHERE**. `delete from user_account;` wipes the table. No confirmation, no undo. Always write the `where` clause first, test it as a `select`, then convert to `delete`.

**5. Missing indexes on foreign keys**. PostgreSQL does not auto-index FK columns. Every FK used in joins or `on delete cascade` needs an explicit index, or you get sequential scans on large tables.

## Best Practices

- **One CTE, one job.** Each CTE should do one logical transformation. Name it after what it produces, not what it does (`active_users`, not `filter_users`).
- **Qualify every column in multi-table queries.** `o.created_at`, never bare `created_at`. Avoids ambiguity when schemas change.
- **Use `timestamptz`, never `timestamp`.** Store everything in UTC. Let the application layer handle display timezones.
- **Default to `text` over `varchar(n)`.** In PostgreSQL, `varchar(n)` adds a constraint check with no storage benefit. Use `text` with a check constraint if you need a max length.
- **Add `not null` unless you have a reason not to.** Every nullable column is a source of three-valued logic bugs. Make columns non-null by default and use `coalesce` at the query level when needed.
- **Put `created_at` and `updated_at` on every table.** Use database defaults (`default now()`) and triggers for `updated_at`. You will always wish you had them.
- **Use `bigint` for primary keys.** `int` maxes out at 2.1 billion. `bigint` costs 4 extra bytes per row and removes a future migration nightmare.
- **Write `select` before `delete`.** Before any destructive statement, run it as a `select` first to verify the affected rows. Wrap destructive operations in a transaction with manual `commit`.
- **Index foreign keys explicitly.** PostgreSQL does not auto-index FK columns. Missing FK indexes cause slow cascading deletes and join performance issues.
- **Avoid `select *` in production code.** Spell out columns. Schema changes break `select *` silently at runtime instead of loudly at deploy time.
