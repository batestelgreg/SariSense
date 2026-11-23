-- =====================================================================
--  SariSense - PostgreSQL schema (run inside Supabase SQL Editor)
--  Safe to run more than once.
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 1. Stores
-- ---------------------------------------------------------------------
create table if not exists stores (
    id          uuid primary key default gen_random_uuid(),
    name        text        not null,
    owner_name  text,
    language    text        not null default 'en',   -- en | tl | ceb
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 2. Users (store owners)
-- ---------------------------------------------------------------------
create table if not exists users (
    id            uuid primary key default gen_random_uuid(),
    store_id      uuid not null references stores(id) on delete cascade,
    email         text not null unique,
    password_hash text not null,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 3. Products
-- ---------------------------------------------------------------------
create table if not exists products (
    id             uuid primary key default gen_random_uuid(),
    store_id       uuid not null references stores(id) on delete cascade,
    name           text not null,
    category       text default 'General',
    cost_price     numeric(10,2) not null default 0,
    sell_price     numeric(10,2) not null default 0,
    stock          integer not null default 0 check (stock >= 0),
    lead_time_days integer not null default 3,
    is_active      boolean not null default true,
    created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 4. Sales
-- ---------------------------------------------------------------------
create table if not exists sales (
    id         bigserial primary key,
    store_id   uuid not null references stores(id) on delete cascade,
    product_id uuid not null references products(id) on delete cascade,
    quantity   integer not null check (quantity > 0),
    unit_price numeric(10,2) not null default 0,
    sold_at    date not null default current_date,
    created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 5. Alerts (anomaly findings)
-- ---------------------------------------------------------------------
create table if not exists alerts (
    id          bigserial primary key,
    store_id    uuid not null references stores(id) on delete cascade,
    product_id  uuid references products(id) on delete cascade,
    alert_date  date not null,
    severity    text not null default 'medium',      -- low | medium | high
    message     text not null,
    is_verified boolean not null default false,
    created_at  timestamptz not null default now(),
    constraint alerts_unique unique (product_id, alert_date, message)
);

-- =====================================================================
--  INDEXES  (this is where the performance comes from)
-- =====================================================================
create index if not exists idx_users_email
    on users (lower(email));

create index if not exists idx_products_store
    on products (store_id) where is_active;

create index if not exists idx_sales_store_date
    on sales (store_id, sold_at desc);

create index if not exists idx_sales_product_date
    on sales (product_id, sold_at desc);

create index if not exists idx_alerts_store_recent
    on alerts (store_id, is_verified, created_at desc);

-- =====================================================================
--  Helper view: daily quantity per product (used by the ML layer)
-- =====================================================================
create or replace view v_daily_sales as
select
    s.store_id,
    s.product_id,
    s.sold_at,
    sum(s.quantity)::int              as quantity,
    sum(s.quantity * s.unit_price)    as revenue
from sales s
group by s.store_id, s.product_id, s.sold_at;
