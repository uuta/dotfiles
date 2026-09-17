---
name: neo-frontend-design
description: "Design web interfaces with a requested dark, neon, terminal, or cyberpunk aesthetic."
---

This skill guides creation of dark command-center / cyberpunk dashboard interfaces inspired by the OJPP Portal (https://ojpp-portal-web.vercel.app/). Every output must feel like a mission-critical control panel — dense with data, alive with neon glow, and grounded in terminal aesthetics.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Principles

Before coding, commit to the **Dark Command Center** aesthetic:
- **Mood**: Military ops room meets cyberpunk HUD. Information-dense, high-contrast, zero fluff.
- **Hierarchy**: Data values dominate. Labels recede into gray. Color is functional, not decorative — each module owns a single neon accent.
- **Atmosphere**: The background is alive (generative art, glitch textures, pixel-sort gradients) but never competes with content.

## Typography

- **Labels & Headers**: All-caps, wide `letter-spacing` (0.2em+), monospace or condensed sans-serif. Use fonts like `JetBrains Mono`, `IBM Plex Mono`, `Space Mono`, `Fira Code`, or condensed families like `Barlow Condensed`, `Oswald`.
- **Metric Values**: Oversized (3rem–6rem), bold weight, colored in the module's neon accent. These are the visual anchors of every card.
- **Body Text**: Small (0.75rem–0.875rem), gray (#888–#aaa), monospace. Reads like terminal output.
- **Section Dividers**: Use `// SECTION_NAME` comment-style labels in uppercase gray monospace.

```css
/* Example token scale */
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
--font-condensed: 'Barlow Condensed', 'Oswald', sans-serif;
--text-label: 0.75rem;
--text-body: 0.875rem;
--text-metric: 3.5rem;
--letter-spacing-wide: 0.2em;
```

## Color System

- **Background**: Near-black base `#0a0a0f` to `#0d0d14`. Never pure black.
- **Surface**: Dark cards at `#111118` to `#16161e` with subtle `1px` borders in `rgba(255,255,255,0.06)`.
- **Labels**: Gray `#666` to `#999`.
- **Values**: White `#e8e8e8` to `#ffffff`.
- **Per-Module Neon Accents** (each module gets ONE):

```css
--neon-orange: #ff6b35;
--neon-green: #00ff88;
--neon-cyan: #00d4ff;
--neon-magenta: #ff00aa;
--neon-yellow: #ffd700;
--neon-blue: #4488ff;
--neon-red: #ff3355;
--neon-purple: #aa44ff;
```

- **Glow Effect**: Apply matching `text-shadow` or `box-shadow` with the accent color at low opacity for neon glow:

```css
.metric-value {
  color: var(--neon-cyan);
  text-shadow: 0 0 20px rgba(0, 212, 255, 0.5), 0 0 40px rgba(0, 212, 255, 0.2);
}
```

## Layout

Follow the OJPP Portal structure as a reference pattern:

1. **Hero Section**: Full-width, generative art background. Large title in condensed all-caps. Subtitle in small gray monospace.
2. **Status Bar**: Horizontal strip with inline key-value pairs, LIVE indicators (pulsing green dot), and real-time timestamps.
3. **Module Card Grid**: CSS Grid (2–3 columns on desktop, 1 on mobile). Each card has:
   - Top: `// MODULE_NAME` label in gray
   - Center: Giant neon metric value
   - Bottom: Secondary stats, progress bars, or mini-charts
4. **Terminal Section**: Black background, monospace text, simulated command prompts (`$`), syntax-highlighted code blocks. Wrap in a window chrome with macOS traffic-light dots (red/yellow/green circles).
5. **Footer**: Minimal, gray monospace, version numbers or status codes.

```css
/* Grid example */
.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.5rem;
  padding: 2rem;
}
```

## Components

### Module Card
```css
.module-card {
  background: #111118;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 1.5rem;
  position: relative;
  overflow: hidden;
}
.module-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--module-accent);
  box-shadow: 0 0 10px var(--module-accent);
}
```

### Terminal Window
- macOS-style title bar with three dots: `#ff5f57` (close), `#ffbd2e` (minimize), `#28c840` (maximize)
- Black `#0a0a0a` body with monospace text
- Command prefix `$` in accent color, output in gray/white

### Progress Bar
```css
.progress-bar {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--module-accent);
  box-shadow: 0 0 8px var(--module-accent);
  transition: width 1s ease;
}
```

### LIVE Indicator
```css
.live-dot {
  width: 8px; height: 8px;
  background: #00ff88;
  border-radius: 50%;
  animation: pulse 2s infinite;
  box-shadow: 0 0 6px #00ff88;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}
```

### Status Badge
- Small pill-shaped badges with neon border and transparent background
- Text matches border color
- Examples: `ACTIVE`, `SYNCING`, `OFFLINE`

## Motion & Effects

- **Neon Glow**: `text-shadow` and `box-shadow` using accent colors. Animate glow intensity on hover.
- **Glitch Effect**: Occasional `clip-path` or `transform: translate` jitter on hero text. Keep subtle — 2–3 second intervals, small displacement.
- **Progress Animation**: Bars fill with eased transitions. Add shimmer overlay moving left-to-right.
- **Staggered Reveal**: Cards appear with `animation-delay` increments (50–100ms each) using `opacity` and `translateY`.
- **Scanline Overlay** (optional): Faint horizontal lines via repeating-linear-gradient over the entire page for CRT effect.

```css
/* Glitch keyframes */
@keyframes glitch {
  0%, 95%, 100% { transform: translate(0); }
  96% { transform: translate(-2px, 1px); }
  97% { transform: translate(2px, -1px); }
  98% { transform: translate(-1px, -1px); }
  99% { transform: translate(1px, 1px); }
}

/* Staggered card entry */
.module-card {
  animation: fadeInUp 0.6s ease both;
}
.module-card:nth-child(1) { animation-delay: 0s; }
.module-card:nth-child(2) { animation-delay: 0.1s; }
.module-card:nth-child(3) { animation-delay: 0.2s; }

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
```

## Background Treatment

The background should feel alive but not distract:
- **Option A**: CSS generative gradient mesh with animated hue shifts (dark purples, deep blues, near-black)
- **Option B**: Canvas-based particle field or noise texture
- **Option C**: Static pixel-sort / databend image at very low opacity (0.1–0.2)
- Always overlay a semi-transparent dark layer to ensure content readability

```css
body {
  background-color: #0a0a0f;
  background-image:
    radial-gradient(ellipse at 20% 50%, rgba(100, 0, 255, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, rgba(0, 100, 255, 0.06) 0%, transparent 50%);
}
```

## Anti-Patterns (NEVER do these)

- Light backgrounds or white themes
- Rounded, bubbly, "friendly" UI elements
- Pastel colors or soft gradients
- Generic sans-serif fonts (Inter, Roboto, Arial)
- Even color distribution — one module, one accent
- Decorative illustrations or icons that break the data-dense aesthetic
- Empty space without purpose — this is a command center, not a landing page

## Reference

- OJPP Portal: https://ojpp-portal-web.vercel.app/
- Aesthetic keywords: dark command center, cyberpunk dashboard, neon HUD, terminal UI, data-dense, mission-critical

Remember: Every pixel should feel like it belongs on a screen in a dimly lit operations room. Dense data, neon accents, monospace precision. No fluff, no decoration — only signal.