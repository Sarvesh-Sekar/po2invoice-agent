-- Canonical FIELD_DEFINITIONS seed (header fields).
-- Idempotent: each row is inserted only if its field_name is not present.

-- 1. po_number
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'po_number', 'The unique purchase order identifier, found near the header block using labels like PO No, PO Number, Order No, Purchase Order, or #.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'po_number');

-- 2. customer
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'customer', 'The primary buyer or customer name, usually located in the top-left header section. Falls back to the GST registration owner name if absent.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'customer');

-- 3. gst_no
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'gst_no', 'The 15-character Goods and Services Tax Identification Number, identified by labels like GSTIN, GST No, or GST IN.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'gst_no');

-- 4. po_date
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'po_date', 'The date the purchase order was issued, identified by labels like Date, PO Date, or Order Date. Formatted as YYYY-MM-DD.', 'date', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'po_date');

-- 5. currency
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'currency', 'The currency used in the document, identified by symbols (Rs, $, EUR, SGD) or ISO codes. Defaults to INR if unspecified.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'currency');

-- 6. ship_to
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'ship_to', 'The complete delivery destination block, typically labeled as Ship To, Deliver To, or Consignee.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'ship_to');

-- 7. address_1
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'address_1', 'The first street address line extracted from the ship-to destination block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'address_1');

-- 8. address_2
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'address_2', 'The second street address line, representing the area, locality, or landmarks from the ship-to block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'address_2');

-- 9. city
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'city', 'The city or municipality extracted from the ship-to destination block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'city');

-- 10. state
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'state', 'The state, province, or region extracted from the ship-to destination block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'state');

-- 11. country
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'country', 'The country name or code extracted from the ship-to destination block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'country');

-- 12. zip
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'zip', 'The 4-10 digit postal or zip code extracted from the ship-to destination block.', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'zip');

-- 13. total_amount
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'total_amount', 'The final numeric billing amount, preferred from labels like Grand Total, Total, Amount Payable, or Net Total.', 'number', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'total_amount');

-- 14. product_name
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'product_name', 'Product name on a line item', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'product_name');

-- 15. sku
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'sku', 'Product SKU on a line item', 'string', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'sku');

-- 16. quantity
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'quantity', 'Ordered quantity on a line item', 'number', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'quantity');

-- 17. unit_price
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'unit_price', 'Unit price on a line item', 'number', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'unit_price');

-- 18. total_price
INSERT INTO field_definitions (field_id, field_name, field_description, field_type, created_at, modified_at)
SELECT GEN_RANDOM_UUID(), 'total_price', 'Line-item total price', 'number', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM field_definitions WHERE field_name = 'total_price');