# Design System Specification: Mono-Brutalist Editorial

## 1. Overview & Creative North Star: "The Architectural Ledger"
This design system rejects the "softness" of modern SaaS in favor of a high-impact, editorial aesthetic. Our Creative North Star is **The Architectural Ledger**: a digital environment that feels as structured and permanent as a physical blueprint, yet as refined as a luxury boutique’s inventory list.

By combining a warm, bone-toned palette with aggressive, unapologetic geometry (zero radius, 3px borders), we move beyond the generic "flat" UI. We are creating a space that prioritizes clarity, authority, and intentional friction. This is not a "quiet" interface; it is a declarative one.

---

## 2. Color & Tonal Architecture
The palette is rooted in a single, unified Light Theme. The warmth of the bone surface prevents the brutalist geometry from feeling clinical, creating a "premium utilitarian" vibe.

### Core Palette
- **Surface (Primary Background):** `#F9F9F7` — The "Bone" canvas.
- **On-Surface (Primary Text):** `#1A1C1B` — High-contrast charcoal for maximum legibility.
- **Primary:** `#000000` — Used for the heaviest architectural elements (borders, primary buttons).
- **Secondary / Tertiary:** `#525F74` & `#2F3C50` — Used for professional, "blue-collar luxury" accents.

### The "Hard Border" Mandate
Unlike traditional systems that use shadows for depth, this system uses **Structural Ink**.
- **Rule:** Sectioning is never achieved through 1px subtle lines. It is achieved through **3px solid borders** (`primary` or `outline`) or distinct background shifts.
- **Surface Nesting:** To create hierarchy without clutter, use the `surface-container` tiers. A `surface-container-high` (`#E8E8E6`) area should be used for sidebars or utility panels to "ground" them against the main `#F9F9F7` stage.

### Signature Texture: The Brutalist Offset
Main CTAs and high-level containers should use a **Hard Offset Shadow**. This is not a blur, but a secondary 3px border offset by 4px or 8px, creating a "stacked card" effect that feels tactile and mechanical.

---

## 3. Typography: Editorial Authority
We pair the technical precision of **Inter** with the avant-garde, geometric personality of **Space Grotesk**.

- **Display & Headlines (Space Grotesk):** These are our "Statement" layers. Use `display-lg` (3.5rem) for dashboard hero numbers or empty states to lean into the brutalist aesthetic. The tight tracking and sharp angles of Space Grotesk mirror our 0px radius rule.
- **Body & Titles (Inter):** Inter handles the "Work" layers. At `body-md` (0.875rem), it provides the utilitarian clarity needed for complex merchant data and administrative ledgers.
- **Labeling (Space Grotesk):** All metadata and labels (`label-md`) must be in Space Grotesk to maintain a "technical blueprint" feel even at small scales.

---

## 4. Elevation & Depth: Geometric Stacking
Traditional elevation (Z-axis) is replaced by **Physical Stacking**.

- **The Layering Principle:** Depth is expressed through the **3px border**. If an element is "above" another (like a modal or a dropdown), it does not use a soft blur. It uses a 3px border and a solid, non-blurred offset shadow in `#000000` at 100% opacity.
- **0px Radius Rule:** This is non-negotiable. Every button, input, card, and modal must have a `0px` border radius. The sharpness is our signature.
- **Intentional Asymmetry:** Break the grid. When using cards, allow the offset shadows to bleed into the gutters. This creates a sense of "organized chaos" that feels custom-designed rather than template-generated.

---

## 5. Components

### Buttons
- **Primary:** `#000000` background, `#D6E3FD` text. 3px border. On hover, the button shifts its position by 2px to "meet" its offset shadow.
- **Secondary:** `#F9F9F7` background, `#000000` text, 3px solid border.
- **Tertiary:** No background, 3px border only.

### Input Fields
- **Default State:** `#FFFFFF` background, 3px solid `#000000` border, 0px radius.
- **Focus State:** Background shifts to `surface-container-low` (`#F4F4F2`) with a secondary 2px inner border.
- **Labels:** Always sitting on the top-left border line, breaking the frame—mimicking architectural notations.

### Cards & Lists
- **Cards:** No dividers allowed. Content is grouped by high-contrast headers and 3px borders.
- **Lists:** Instead of 1px dividers, use a `surface-container-highest` (`#E2E3E1`) background on hover to "highlight" the row. 
- **The "Ledger" Table:** Tables should use 3px vertical lines to separate core data pillars, emphasizing the "Mono-Brutalist" grid.

### Chips & Tags
- Rectangular, 2px border, Space Grotesk `label-sm`. These should feel like physical "stamps" on a document.

---

## 6. Do’s and Don’ts

### Do:
- **Do** use massive scale differences between headlines and body text.
- **Do** allow elements to feel "heavy." Thick borders are your friend.
- **Do** use the Bone (`#F9F9F7`) and Charcoal (`#1C293C`) contrast to create a premium, paper-like feel.
- **Do** keep every corner perfectly square (0px).

### Don’t:
- **Don’t** use soft drop shadows. If it’s not a hard-edged offset, it doesn’t belong.
- **Don’t** use 1px lines. They look "weak" in this system. Minimum border width is 2px; 3px is preferred.
- **Don’t** use "Light Mode" and "Dark Mode." This system is a singular, high-contrast Light experience for all users (Admin and Merchant).
- **Don’t** use rounded corners for any reason—not even for checkboxes or avatars. Use squares.

---

## 7. Signature Interaction: "The Press"
Interaction should feel mechanical. When a user clicks a button or card, it should not "glow." It should physically move 2px down and 2px right—mechanically "closing" the gap of its offset shadow, simulating a physical press.