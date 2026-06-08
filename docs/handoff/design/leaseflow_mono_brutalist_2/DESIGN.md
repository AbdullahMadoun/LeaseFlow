# Design System Specification: The Architectural Ledger

## 1. Overview & Creative North Star
This design system rejects the "softness" of modern SaaS templates in favor of **The Architectural Ledger**. It is a visual philosophy that treats financial leasing not as a vague cloud service, but as a rigid, high-stakes infrastructure. 

By merging the raw honesty of Neo-brutalism with the precision of technical documentation, we create an interface that feels authoritative, unyielding, and bespoke. We break the grid through intentional asymmetry—offsetting containers and utilizing "terminal-style" floating panels—to ensure the UI feels like a custom-built tool rather than a generic dashboard.

### The North Star: "Precision Brutalism"
Every element must feel physically constructed. If a component exists, it must have weight (3px borders) and a shadow (hard offsets). We do not use transparency to hide; we use high-contrast layering to expose the hierarchy.

---

## 2. Colors & Tonal Depth
The palette is divided into two distinct environments: the **Merchant Theme** (High-Contrast Editorial) and the **Admin Theme** (Deep Terminal).

### The "No-Softness" Rule
Unlike traditional systems that use 1px hairlines, this system prohibits thin, delicate borders. Boundaries are defined by a **3px hard stroke (`var(--border)`)**. 

### Surface Hierarchy & Nesting
Depth is achieved through the **Stacking Principle**. Instead of using blurs to show elevation, we use background shifts and hard-offset shadows.
*   **Base Layer:** `surface` (#FBFBF9 or #0F0F0F).
*   **The Nested Container:** When placing a card inside a section, use `surface-container-low`. 
*   **The Interactive Layer:** Primary actions sit on the `primary` (#FDC800) container, always framed by the 3px border to prevent the color from "bleeding" into the workspace.

### Signature Textures
While the system is brutalist, we inject "soul" through high-end digital textures:
*   **Terminal Glass:** For live-updating panels, use a semi-transparent version of the surface color with a `backdrop-filter: blur(10px)`. This is the *only* place blur is permitted, signifying a "live" or "volatile" data stream.
*   **The Shadow Scale:** Use no-blur offsets to indicate "lift."
    *   *Level 1 (Default):* 3px x 3px
    *   *Level 2 (Hover):* 4px x 4px
    *   *Level 3 (Modals):* 8px x 8px

---

## 3. Typography: The Editorial Contrast
We use a dual-typeface system to separate human-centric content from machine-precise data.

*   **Body & Narrative:** **'Inter'**. Used for all descriptive text, emails, and long-form content. It provides the readability necessary for complex leasing terms.
*   **Data & Meta:** **'JetBrains Mono'**. Used for all numbers, labels, chips, and micro-copy. This font signals "System Output" and reinforces the "Ledger" aesthetic.

### Typographic Hierarchy
*   **Display (Inter, Bold):** Massive, tight-leading headlines for hero sections.
*   **Micro-Labels (Mono, All-Caps):** Used for section headers, accompanied by a **divider trail** (a 3px horizontal line that extends to the edge of the container).
*   **Numerical Data (Mono):** All financial figures must use tabular figures (monospaced) to ensure columns align perfectly in tables.

---

## 4. Elevation & Depth: The Hard Offset
We do not use light and shadow; we use **geometry and displacement.**

*   **The Layering Principle:** To lift an object, we do not increase a blur radius. We increase the distance of the `3px solid` shadow. 
*   **The Ghost Border:** For secondary elements that require containment without visual clutter, use the `outline-variant` at 20% opacity. This is the only exception to the 3px rule.
*   **The Terminal Window:** Live panels must feature a "header bar" in the Secondary color (#432DD7 / #7B6BF6) with three 8px square "window controls" on the left, mimicking a terminal emulator.

---

## 5. Components

### Buttons: The Tactile Block
*   **Primary:** Background #FDC800, 3px Black Border, 4px Hard Offset Shadow. On click, the shadow disappears (`transform: translate(4px, 4px)`), mimicking a physical depress.
*   **Secondary:** Background #432DD7 (Merchant) / #7B6BF6 (Admin), Text #FFFFFF.
*   **Shape:** 0px border-radius. Absolute square corners.

### Terminal Live-Panels
Used for real-time lease flow monitoring. These panels use 'JetBrains Mono' and a subtle scanline pattern (1px repeating linear gradient) to differentiate from static forms.

### Input Fields & Controls
*   **Text Inputs:** 3px border, 0px radius. The label is a Mono All-Caps micro-label floating above the top-left corner.
*   **Checkboxes/Radios:** Large 24px squares. Checked state uses a solid #FDC800 fill with a heavy black "X" or "Square" glyph.
*   **Chips:** 'JetBrains Mono' text. Backgrounds are strictly `surface-container-high`. No rounded ends; they must be rectangular blocks.

### The "Ledger" List
Forbid the use of standard divider lines between list items. Instead:
1.  Use a 16px vertical gap.
2.  Use alternating background tints (Surface vs Surface-Container-Low).
3.  Each list item is its own "Block" with a 3px border on the bottom only, creating a heavy-weighted stacked look.

---

## 6. Do's and Don'ts

### Do
*   **DO** use the 8-point spacing scale for everything. If an element is off by 2px, it breaks the "Architectural" feel.
*   **DO** use intentional asymmetry. For example, a right-hand sidebar should be 3px taller or shorter than the main content area to create visual tension.
*   **DO** ensure all numbers are in 'JetBrains Mono'. Financial clarity is the soul of this system.

### Don't
*   **DON'T** use border-radius. Ever. Even a 2px radius destroys the brutalist integrity.
*   **DON'T** use soft drop shadows. If a shadow doesn't have a hard edge, it doesn't belong.
*   **DON'T** use 1px lines to separate content. Use a 3px border or a change in surface color.
*   **DON'T** center-align editorial headers. Keep them left-aligned and anchored to the "Architectural" grid.

---

## 7. Interaction Patterns
*   **Hover States:** When hovering over any interactive card or button, the hard-offset shadow should grow from 4px to 6px, and the element should move -2px on both axes to simulate "lifting" toward the user.
*   **Loading States:** Use a "Block Progress" bar—a series of 3px-bordered squares that fill solid #FDC800 one by one, rather than a spinning circle.