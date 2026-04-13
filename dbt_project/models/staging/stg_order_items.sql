SELECT
    order_item_id,
    created_at::TIMESTAMP   AS created_at,
    order_id,
    product_id,
    (is_primary_item = 1)    AS is_primary_item,
    price_usd::NUMERIC       AS price_usd,
    cogs_usd::NUMERIC        AS cogs_usd
FROM {{ source('raw', 'order_items') }}
WHERE order_item_id IS NOT NULL
