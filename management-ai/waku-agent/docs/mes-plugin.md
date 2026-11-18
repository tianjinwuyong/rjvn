# MES plugin boundary

Waku can optionally retrieve MES context through two read-only tools:

- `mes_list_work_orders`
- `mes_list_active_boms`

Enable them by setting `MES_API_BASE_URL` in `.env` (for example,
`http://127.0.0.1:5178/api`). `MES_API_TOKEN` is optional and is sent as a
Bearer token when present.

The adapter intentionally has no create/update/delete methods. Work-order
creation, material binding, registration, and loading remain governed by the
MES/PDA screens and their audit trail. This is the practical part of the
plugin-oriented design: tools can be added or removed without changing the
agent loop, while high-impact writes stay behind explicit business workflows.
