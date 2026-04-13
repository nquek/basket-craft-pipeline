SELECT
    p.product_name,
    DATE_TRUNC('month', o.created_at)::DATE                AS month,
    SUM(oi.price_usd)                                      AS revenue_usd,
    COUNT(DISTINCT o.order_id)                             AS order_count,
    SUM(oi.price_usd)
        / NULLIF(COUNT(DISTINCT o.order_id), 0)            AS avg_order_value_usd
FROM   {{ ref('stg_order_items') }}  oi
JOIN   {{ ref('stg_orders') }}       o  ON oi.order_id   = o.order_id
JOIN   {{ ref('stg_products') }}     p  ON oi.product_id = p.product_id
GROUP  BY 1, 2
ORDER  BY 2, 1
