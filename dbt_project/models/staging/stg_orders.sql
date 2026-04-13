SELECT
    order_id,
    created_at::TIMESTAMP   AS created_at,
    website_session_id,
    user_id,
    primary_product_id,
    items_purchased,
    price_usd::NUMERIC(10,2)    AS price_usd,
    cogs_usd::NUMERIC(10,2)     AS cogs_usd
FROM {{ source('raw', 'orders') }}
WHERE order_id IS NOT NULL
