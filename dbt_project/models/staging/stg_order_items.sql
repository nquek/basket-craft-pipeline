SELECT
    order_item_id,
    created_at::TIMESTAMP   AS created_at,
    order_id,
    product_id,
    CASE WHEN is_primary_item = 1 THEN TRUE
         WHEN is_primary_item = 0 THEN FALSE
         ELSE NULL
    END AS is_primary_item,
    price_usd::NUMERIC(10,2)    AS price_usd,
    cogs_usd::NUMERIC(10,2)     AS cogs_usd
FROM {{ source('raw', 'order_items') }}
WHERE order_item_id IS NOT NULL
