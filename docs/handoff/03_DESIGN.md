# 03 — Design System

Stitch delivered a complete neo-brutalist design system in `handoff/design/`.
This file is the digest; for the long-form design rationale read
`handoff/design/leaseflow_mono_brutalist_1/DESIGN.md`. For layout and state
specs read `../leaseflow/docs/FRONTEND_SPEC.md`.

## Aesthetic north star

**"Architectural Ledger"** — editorial, brutalist, intentionally tactile.
Think: a luxury boutique's inventory ledger rendered digitally. Warm bone
background to keep the geometry from feeling clinical.

## Critical rules (non-negotiable)

1. **0px border radius everywhere.** No rounded corners anywhere. This is the signature.
2. **3px solid black borders** on cards, buttons, inputs, panels.
3. **Hard offset shadows, no blur.** `box-shadow: Npx Npx 0 #000` where N ∈ {3, 4, 6, 8}.
4. **Hover = translate + shadow grow.**
   `hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0 #000 }`
5. **All-light theme.** Even admin screens. No dark mode. No theme toggle.
6. **Monospace for data** — JetBrains Mono for labels, numbers, status chips.
   **Display for hero** — Space Grotesk for big headlines. **Inter for body.**

## Color palette (exact tokens — Tailwind `theme.extend.colors`)

```ts
// tailwind.config.ts
colors: {
  // Surfaces
  "surface":                   "#F9F9F7",   // bone background
  "surface-container-lowest":  "#FFFFFF",   // input fields
  "surface-container-low":     "#F4F4F2",   // subtle cards
  "surface-container":         "#EDEDEB",   // nested panels
  "surface-container-high":    "#E8E8E6",   // sidebars, utility panels
  "surface-variant":           "#E2E3E1",

  // Text
  "on-surface":                "#1A1C1B",   // primary text (charcoal)
  "on-surface-variant":        "#4E4632",
  "on-primary":                "#FFFFFF",

  // Brand
  "primary":                   "#000000",   // heaviest structural elements
  "primary-fixed-dim":         "#F3C000",   // yellow accent (brand highlight)
  "secondary":                 "#525F74",   // blue-collar luxury accent
  "tertiary":                  "#2F3C50",

  // Semantic
  "success":                   "#16A34A",
  "warning":                   "#D97706",
  "error":                     "#DC2626",
  "error-container":           "#FFDAD6",
}
```

## Typography

```html
<!-- index.html or layout -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800;900&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
```

```ts
// tailwind.config.ts
fontFamily: {
  "sans":    ["Inter",           "system-ui", "sans-serif"],
  "display": ["Space Grotesk",   "sans-serif"],
  "mono":    ["JetBrains Mono",  "ui-monospace", "monospace"],
}
```

**Usage rules:**
- `font-display` — hero headings (48-96px): page titles, hero numbers, empty-state statements.
- `font-sans` — body copy (14-17px): paragraphs, labels, form text, nav items.
- `font-mono` — metadata (11-13px, `tracking-widest uppercase`): status chips,
  labels above sections, SAR amounts, timestamps, IDs.

## The "brutalist offset" utility

Put this in your Tailwind config as a reusable plugin or utility class:

```css
/* src/styles/brutalist.css */
.offset-shadow-sm { box-shadow: 3px 3px 0 #000000; }
.offset-shadow   { box-shadow: 4px 4px 0 #000000; }
.offset-shadow-md { box-shadow: 6px 6px 0 #000000; }
.offset-shadow-lg { box-shadow: 8px 8px 0 #000000; }

.hover-lift {
  transition: transform 120ms, box-shadow 120ms;
}
.hover-lift:hover {
  transform: translate(-2px, -2px);
  box-shadow: 6px 6px 0 #000000;
}
```

## Component patterns (from Stitch's HTML)

### Primary button
```html
<button class="
  bg-black text-white font-mono text-sm font-bold uppercase tracking-wider
  px-6 py-3
  border-[3px] border-black
  offset-shadow-sm hover-lift
">
  Apply now
</button>
```

### Input field
```html
<label class="block">
  <span class="absolute -top-3 left-3 bg-surface px-2 font-mono text-xs uppercase tracking-widest text-on-surface">Email</span>
  <input
    class="w-full
      bg-white text-on-surface font-sans text-base
      border-[3px] border-black
      px-4 py-3
      focus:outline-none focus:bg-surface-container-low"
  />
</label>
```

**Notice the label trick**: labels sit ON the top border, breaking the frame —
"architectural notation" style. Required for all inputs.

### Card
```html
<article class="
  bg-white
  border-[3px] border-black
  offset-shadow-md
  p-6
  hover-lift
">
  <h3 class="font-display text-2xl font-bold">Title</h3>
  <p class="font-sans text-sm text-on-surface-variant">Body</p>
</article>
```

### Status chip
```html
<span class="inline-flex items-center gap-2
  font-mono text-xs font-bold uppercase tracking-widest
  px-3 py-1
  border-[3px] border-black">
  <span class="w-2 h-2 bg-success animate-pulse"></span>
  Approved
</span>
```

### Section label (editorial micro-header)
```html
<div class="flex items-center gap-4 mb-8 font-mono text-xs uppercase tracking-widest text-on-surface-variant">
  <span>01 — Your Application</span>
  <span class="flex-1 h-0.5 bg-on-surface-variant"></span>
</div>
```

### Big number card (hero-scale amounts)
```html
<article class="bg-surface-container-low border-[3px] border-black offset-shadow-md p-8">
  <span class="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
    Next Payment Due
  </span>
  <p class="font-display text-6xl font-bold text-on-surface mt-2">
    SAR 4,791.67
  </p>
  <p class="font-mono text-xs text-on-surface-variant mt-1">
    In 14 days · installment 1 of 12
  </p>
</article>
```

## What's in `handoff/design/`

Stitch delivered **18 static HTML files**, one per screen. For each screen
there's a `code.html` (the Tailwind HTML) and a `screen.png` (the visual
mockup). Copy the Tailwind classes and structure — you're porting, not
re-inventing.

| Folder | Screen | Corresponds to |
|---|---|---|
| `landing_page/` | Public landing | `/` |
| `login/` | Login form | `/login` |
| `signup/` | Sign-up form | `/signup` |
| `onboarding/` | First-time merchant setup | `/merchant/onboarding` |
| `merchant_dashboard/` | Merchant home | `/merchant/dashboard` |
| `apply_step_1/` | Loan wizard step 1 (amount + item) | `/merchant/new-loan` (step 1) |
| `apply_step_2/` | Loan wizard step 2 (docs + classifier) | `/merchant/new-loan` (step 2) |
| `apply_step_3/` | Loan wizard step 3 (review + submit) | `/merchant/new-loan` (step 3) |
| `loan_analyzing_clean/` | Pipeline running | `/merchant/loans/:id` (analyzing) |
| `loan_decided/` | Decision arrived | `/merchant/loans/:id` (done) |
| `payments/` | Installments + Pay-now | `/merchant/payments` |
| `profile/` | Merchant profile | `/merchant/profile` |
| `admin_dashboard_light/` | Admin loan feed | `/admin` |
| `admin_loan_detail_light/` | Admin loan detail (4 tabs) | `/admin/loans/:id` |
| `admin_risk_light/` | Risk snapshot page | `/admin/risk` |
| `admin_segments_light/` | Segment catalog | `/admin/segments` |
| `leaseflow_mono_brutalist_1/` | Design system reference | — (read `DESIGN.md`) |
| `leaseflow_mono_brutalist_2/` | Design system reference | — (read `DESIGN.md`) |

**Open a screen PNG to see the target visual. Open `code.html` to get the
Tailwind structure. Port to React components incrementally.**

## What to port, what to re-invent

- **Port directly**: layout structure, Tailwind class composition, color usage,
  spacing, typography choices, icon placement. The visuals are locked.
- **Re-invent**: data binding, state logic, forms/validation, routing,
  realtime subscriptions, keyboard accessibility, loading/error states.
  Stitch's HTML has placeholder copy and fake data — replace with live data.

## Icons

Stitch's HTML uses `Material Symbols Outlined`. Continue using it — it's
already in the fonts link above. For React, use inline `<span class="material-symbols-outlined">name</span>` or install `@marella/material-symbols` if you want tree-shaking.

## Responsive strategy

- **Merchant**: mobile-first. Design at 375px, scale up to 1024px. Everything
  works on phone. Admin never touches merchant routes.
- **Admin**: desktop-first. Design at 1440px minimum width. Admin is an
  operator tool — don't waste time making it tiny-mobile friendly.

## Accessibility minimums

- All interactive elements keyboard-reachable (tab order matches visual order).
- Focus ring visible — `focus:outline-[3px] focus:outline-offset-2 focus:outline-primary-fixed-dim`.
- `prefers-reduced-motion` — disable the pulse animation on status dots.
- Color contrast: the black/bone combo passes WCAG AAA (21:1). The yellow
  accent on bone passes AA for non-text. Don't put body text on yellow.
- `aria-live="polite"` on the analyzing-state progress card.
- Form errors: use `aria-invalid` + a visible red line + an error message tied
  via `aria-describedby`.
