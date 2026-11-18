# Adjacent projects adopted for Ruijing

This decision keeps the production path small and auditable:

| Project | Decision | Use in this system |
| --- | --- | --- |
| Needle 2 | Optional spike | Evaluate as a future offline PDA classifier for scan feedback; never make a loading decision without MES. |
| ToolJet | Prototype only | Use for disposable admin mockups; production MES/WMS pages remain in the existing web app. |
| RustDesk | Operations only | Use a self-hosted, access-controlled relay for support; never embed it in station agents. |
| PartMode | Research only | Investigate BOM/part visualization; MES remains the BOM source of truth. |
| attention-span | UX guidance | Keep Waku responses short, with an explicit status, next action, and blocking reason. |
| DeepSeek Harness/Cordis | Architecture reference | Borrow plugin boundaries; do not replace Waku while those APIs are still unstable. |

## Safe integration order

1. Waku local Qwen remains the orchestration model.
2. The read-only MES plugin supplies work orders and active BOMs.
3. PDA actions continue to be validated and committed by MES.
4. Needle is tested only against recorded, non-production scan fixtures.
5. Any new tool must be read-only by default and explicitly registered in the
   Waku registry.

This prevents a small edge model, visual builder, or remote-support tool from
bypassing the MES binding/loading audit trail.
