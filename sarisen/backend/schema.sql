create extension if not exists pgcrypto;


-- 1. STORES  (one row per sari-sari store)
create table if not exists stores (
    id          uuid        primary key default gen_random_uuid(),
    name        text        not null check (length(trim(name)) > 0),
    owner_name  text,
    language    text        not null default 'en'
                            check (language in ('en', 'tl', 'ceb')),
    created_at  timestamptz not null default now()
);


-- 2. USERS  (store owners / login accounts)
--    Separate from stores so one store can later have several accounts.
create table if not exists users (
    id            uuid        primary key default gen_random_uuid(),
    store_id      uuid        not null references stores(id) on delete cascade,
    email         text        not null,
    password_hash text        not null,
    created_at    timestamptz not null default now()
);

-- Email uniqueness is case-insensitive (Ana@x.com == ana@x.com).
create unique index if not exists uq_users_email_lower
    on users (lower(email));


-- 3. PRODUCTS  (master data — one row per item, never duplicated)
create table if not exists products (
    id             uuid          primary key default gen_random_uuid(),
    store_id       uuid          not null references stores(id) on delete cascade,
    name           text          not null check (length(trim(name)) > 0),
    category       text          not null default 'General',
    cost_price     numeric(10,2) not null default 0 check (cost_price >= 0),
    sell_price     numeric(10,2) not null default 0 check (sell_price >= 0),
    stock          integer       not null default 0 check (stock >= 0),
    lead_time_days integer       not null default 3 check (lead_time_days >= 0),
    is_active      boolean       not null default true,
    created_at     timestamptz   not null default now()
);


-- 4. SALES  (transaction table — the fact table of the system)
--    unit_price is a deliberate snapshot of the price at the moment of
--    sale. It must NOT be read from products later, otherwise historical
--    revenue would change whenever a price is edited.
create table if not exists sales (
    id         bigserial     primary key,
    store_id   uuid          not null references stores(id) on delete cascade,
    product_id uuid          not null references products(id) on delete cascade,
    quantity   integer       not null check (quantity > 0),
    unit_price numeric(10,2) not null default 0 check (unit_price >= 0),
    sold_at    date          not null default current_date,
    created_at timestamptz   not null default now()
);


-- 5. ALERTS  (anomaly findings produced by IsolationForest)
create table if not exists alerts (
    id          bigserial   primary key,
    store_id    uuid        not null references stores(id) on delete cascade,
    product_id  uuid        references products(id) on delete cascade,
    alert_date  date        not null,
    severity    text        not null default 'medium'
                            check (severity in ('low', 'medium', 'high')),
    message     text        not null,
    is_verified boolean     not null default false,
    created_at  timestamptz not null default now(),

    -- Stops the same anomaly being inserted twice on every re-scan.
    constraint uq_alerts_finding unique (product_id, alert_date, message)
);


--  INDEXES — chosen to match the actual query patterns

-- Products are listed per store; partial index keeps it small.
create index if not exists idx_products_store_active
    on products (store_id)
    where is_active;

-- Dashboard: "sales for this store in the last N days"
create index if not exists idx_sales_store_date
    on sales (store_id, sold_at desc);

-- Forecasting: "sales of this product over time"
create index if not exists idx_sales_product_date
    on sales (product_id, sold_at desc);

-- Alerts page: unverified alerts per store, newest first
create index if not exists idx_alerts_store_recent
    on alerts (store_id, is_verified, alert_date desc);



-- VIEW — daily quantity per product (feeds the ML feature builder)
create or replace view v_daily_sales as
select
    s.store_id,
    s.product_id,
    s.sold_at,
    sum(s.quantity)::int           as quantity,
    sum(s.quantity * s.unit_price) as revenue
from sales s
group by s.store_id, s.product_id, s.sold_at;