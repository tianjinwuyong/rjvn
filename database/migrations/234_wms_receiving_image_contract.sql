-- Supplier quality evidence is linked to the received material lot, not to a
-- free-standing URL. The object itself lives in managed storage; this table
-- stores immutable metadata for audit and retention.
CREATE TABLE IF NOT EXISTS wms_receiving_image_evidence (
  id BIGSERIAL PRIMARY KEY,
  material_lot_id BIGINT NOT NULL REFERENCES material_lots(id) ON DELETE RESTRICT,
  storage_key VARCHAR(512) NOT NULL,
  file_name VARCHAR(240) NOT NULL,
  mime_type VARCHAR(64) NOT NULL CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),
  size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
  checksum VARCHAR(128) NOT NULL,
  captured_by VARCHAR(120) NOT NULL,
  notes TEXT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (material_lot_id, checksum)
);
CREATE INDEX IF NOT EXISTS idx_wms_receiving_image_lot
  ON wms_receiving_image_evidence(material_lot_id, captured_at DESC);
