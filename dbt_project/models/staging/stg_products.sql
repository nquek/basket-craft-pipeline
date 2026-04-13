SELECT
    product_id,
    created_at::TIMESTAMP   AS created_at,
    product_name,
    description
FROM {{ source('raw', 'products') }}
WHERE product_id IS NOT NULL
