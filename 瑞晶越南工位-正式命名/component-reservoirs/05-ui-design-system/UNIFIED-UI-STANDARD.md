# Ruijing Unified Factory UI Standard

Status: mandatory for station Agents, MES pages, PDA and Android applications.

## 1. Unified interaction

### Primary workflow

1. Scanner input is the default production input.
2. A valid scan advances exactly one defined workflow step.
3. Manual entry requires an explicit permission and is visually identified.
4. A destructive or exceptional action requires reason + authorized operator + confirmation.
5. Every action returns one result: success, blocked, attention, offline queued, or failed.

### Keyboard and focus

| Action | Standard |
|---|---|
| Scanner focus | Persistent on the active scan field; restored after non-blocking feedback |
| `Enter` | Submit the active scan/form once |
| `Esc` | Close a non-critical dialog/drawer; never dismiss an active safety block |
| `F1` | Context help |
| `F2` | Authorized manual entry |
| `F8` | Diagnostics |
| `Ctrl+L` | Language selection |
| Overview/full screen | User command has priority over automatic camera or close-view motion |

### Feedback timing

- PASS: immediate stable confirmation; no celebratory animation.
- New NG/alarm: one brief visual/audio cue per immutable event ID, then persistent non-flashing state.
- Historical NG/alarm: visible and silent.
- MES offline: persistent amber state; production decision actions follow explicit offline policy.
- Unauthorized: explain required role and keep current scan/work context.
- Processing: disable duplicate submission without hiding current data.

## 2. Unified fonts

### Font families

- UI text: `Microsoft YaHei UI`, `Noto Sans`, `Arial`, sans-serif.
- SN, QR, WO, IP, timestamps and measurements: `Consolas`, `Noto Sans Mono`, monospace.
- Vietnamese diacritics must render in the chosen fallback; no bitmap text.

### Type scale

| Token | Size | Weight | Use |
|---|---:|---:|---|
| `font.display` | 32 px | 700 | PASS/NG and critical result |
| `font.title` | 20 px | 700 | Page/station title |
| `font.section` | 16 px | 700 | Panel heading |
| `font.body` | 14 px | 400 | Main labels and values |
| `font.action` | 14 px | 700 | Buttons |
| `font.caption` | 12 px | 400 | Secondary context and health strip |
| `font.code` | 16–24 px | 600 | Scanned SN/WO/QR depending on available width |

Rules: no page-local font sizes; translations may wrap only at defined label boundaries; important codes use middle ellipsis plus full-value tooltip/detail.

## 3. Unified colors

| Token | Hex | Meaning |
|---|---|---|
| `surface.canvas` | `#08131D` | Application background |
| `surface.panel` | `#101D27` | Primary panel |
| `surface.raised` | `#192833` | Input/raised control |
| `border.default` | `#2C414F` | Structural boundary |
| `text.primary` | `#F2F6F8` | Primary content |
| `text.secondary` | `#9EB0BC` | Supporting content |
| `state.active` | `#18C6D9` | Current focus, scan step or connected activity |
| `state.pass` | `#22D887` | PASS only |
| `state.attention` | `#F2B84B` | Warning, offline, pending human action |
| `state.ng` | `#F05252` | New/active NG, safety block or destructive action |
| `state.info` | `#4C8DFF` | Neutral information and configuration |
| `state.disabled` | `#536572` | Unavailable action |

Rules: color never carries meaning alone; every state also has text/icon. No decorative gradients, glass effects, rainbow dashboards or station-specific status colors.

## 4. Unified layouts

### Whole-page visual balance

- Visual weight follows production importance: live result and next required action dominate; scanner and MES context support it; history stays secondary.
- Use asymmetrical balance intentionally: the 22/56/22 desktop grid is a default weight system, not three equal cards.
- Avoid dead zones, crowded corners, isolated buttons, oversized empty panels and dense text on only one side.
- Align panel tops, action baselines and recurring labels across the full page.
- The alarm banner and health strip provide stable horizontal anchors so the page does not jump when state changes.
- Expanded content replaces or overlays a reserved region; it must not push critical scanner/result controls off-screen.

### Desktop station template — 1366×768 first

```text
┌──────────────── Header: plant · line · station · host/IP · operator ────────────────┐
├──────────────── Reserved alarm/status banner (fixed height) ───────────────────────┤
│ Scanner / input  │ Main production action and live result │ MES context / policy   │
│ 22%              │ 56%                                    │ 22%                    │
├──────────────── Fixed health strip: scanner · equipment · MES · outbox · clock ────┤
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- Base spacing unit: 8 px.
- Page padding: 12 px at 1366×768; 16 px at wider sizes.
- Panel gap: 12 px.
- Minimum interactive height: 44 px; primary production action: 48–56 px.
- Header: 68 px; alarm banner: 48 px; health strip: 54 px.
- Main content must fit without page-level vertical scrolling at 1366×768. Long history belongs in a drawer/detail page.
- Scanner and critical result remain visible when side drawers open.

### MES desktop template

Global navigation + page title/context + filter/action row + primary work surface + optional detail drawer. Tables keep sticky headers and stable column meaning.

### PDA / Android template

Top identity/status + one dominant workflow card + fixed scan/action area + step progress + bottom navigation only when workflows require switching. Minimum touch target: 48 dp.

## 5. Component state contract

Every relevant component implements the same state names:

`idle`, `ready`, `processing`, `success`, `attention`, `new-ng`, `historical-ng`, `offline`, `unauthorized`, `disabled`, `error`, `repair`, `configuration`.

State behavior is owned by this design system; business eligibility is owned by MES.

## 6. Harmonized color and elegant motion

### Color harmony

- Surfaces use one cool-neutral family; semantic colors appear as controlled accents, not large decorative fills.
- A state transition changes border, icon, label and a limited accent area together.
- PASS, attention and NG colors keep the same hue meaning across Station, MES, PDA and Android.
- Text contrast remains readable during every intermediate animation frame.
- Do not interpolate directly from PASS green to NG red across muddy intermediate colors. Transition through the neutral surface, then apply the destination semantic accent.

### Motion tokens

| Token | Duration | Easing | Use |
|---|---:|---|---|
| `motion.instant` | 80 ms | linear | Press/focus acknowledgement |
| `motion.fast` | 140 ms | ease-out | Badge, border and small state change |
| `motion.standard` | 200 ms | ease-out | Panel content and SN-slot insertion |
| `motion.drawer` | 240 ms | ease-out / ease-in | Drawer enter / exit |
| `motion.camera` | 450–700 ms | smooth ease-in-out | 3D camera move; always interruptible |

### Motion rules

- Animate cause and effect: scan accepted → slot fills; MES decision → result state changes; user opens detail → drawer moves.
- Prefer opacity + 4–12 px translation or restrained border/accent transition.
- No decorative looping, pulsing dashboards, bouncing controls, repeated flashing or automatic focus theft.
- New alarm gets one short emphasis; historical alarms never animate.
- Motion never delays scanner readiness or action submission.
- User navigation, overview and emergency actions interrupt current animation immediately.
- Respect reduced-motion settings; replace movement with an instant state change and static emphasis.

## 7. Acceptance gate

A page is not standardized until all four columns pass:

| Gate | Required evidence |
|---|---|
| Interaction | Scanner/keyboard/action/alarm/focus test |
| Font | zh/en/vi screenshots with no missing glyph, clipping or overlap |
| Color | Token audit; no private semantic color literals |
| Layout | Native screenshot at target size; no overlap, clipping or unintended scroll |
| Balance | Full-page review at target size; hierarchy and whitespace remain stable in every state |
| Motion | Timing/easing review, interruption test and reduced-motion verification |

Exceptions require an owner, technical reason, expiry date and replacement plan.
