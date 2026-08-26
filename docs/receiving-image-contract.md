# Receiving supplier-quality image contract

Images are evidence of a specific `material_lot`, and must never be stored as
base64/data URLs in `material_lots` or in an inspection JSON blob.

1. The client uploads the binary to managed object storage. Storage must enforce
   `image/jpeg`, `image/png`, or `image/webp`, a 10 MiB limit, malware scanning,
   and a generated opaque key such as `receiving/{lotId}/{uuid}`.
2. The client calls `POST /wms/material-lots/:id/receiving-images` with:

   ```json
   {
     "storageKey": "receiving/123/uuid",
     "fileName": "supplier-label.jpg",
     "mimeType": "image/jpeg",
     "sizeBytes": 284921,
     "checksum": "<64 hex SHA-256>",
     "capturedBy": "user-id",
     "notes": "Outer carton damage"
   }
   ```

The API must verify the lot exists, the key belongs to the receiving-image
namespace, metadata matches the object (including checksum), and the caller
has `wms.execute`. It persists metadata in
`wms_receiving_image_evidence`; `GET /wms/material-lots/:id/receiving-images`
returns signed, short-lived download URLs. Never return a permanent bucket URL
or accept a client-supplied `data:` URL/path. The migration adds a unique
`(material_lot_id, checksum)` guard so offline retries are idempotent.
