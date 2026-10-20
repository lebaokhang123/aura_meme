---
name: Aura Neon Dark
colors:
  surface: '#12131b'
  surface-dim: '#12131b'
  surface-bright: '#383842'
  surface-container-lowest: '#0d0e15'
  surface-container-low: '#1a1b23'
  surface-container: '#1e1f27'
  surface-container-high: '#292932'
  surface-container-highest: '#33343d'
  on-surface: '#e3e1ed'
  on-surface-variant: '#cbc3d7'
  inverse-surface: '#e3e1ed'
  inverse-on-surface: '#2f3039'
  outline: '#958ea0'
  outline-variant: '#494454'
  surface-tint: '#d0bcff'
  primary: '#d0bcff'
  on-primary: '#3c0091'
  primary-container: '#a078ff'
  on-primary-container: '#340080'
  inverse-primary: '#6d3bd7'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#adc6ff'
  on-tertiary: '#002e6a'
  tertiary-container: '#4d8eff'
  on-tertiary-container: '#00285d'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#23005c'
  on-primary-fixed-variant: '#5516be'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#d8e2ff'
  tertiary-fixed-dim: '#adc6ff'
  on-tertiary-fixed: '#001a42'
  on-tertiary-fixed-variant: '#004395'
  background: '#12131b'
  on-background: '#e3e1ed'
  surface-variant: '#33343d'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '800'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system channels an immersive, high-engagement community space inspired by late-night Discord culture, Reddit-style content hierarchies, and vibrant Web3/gaming HUD interfaces. The design combines structured utility with playful gamification, utilizing dense information layouts, luminous accents, and tactile feedback.

### Key Personality Attributes
- **Electric & Focused:** Deep obsidian-tinted backgrounds minimize eye fatigue while electric violet and cyan highlights instantly pull the eye to critical user actions, memes, and community activity.
- **Gamified & Celebratory:** User progression, status tiers, Aura scores, and streak systems are celebrated through micro-glows, badges, and gradient ribbons without cluttering editorial legibility.
- **Modular & Scannable:** Tightly grouped component cards, clean borders, and disciplined spacing allow vast streams of media and text discussions to coexist seamlessly.

### Aesthetic Movement
**Dark Neon Minimalism with Glassmorphic HUD Undertones.** Surfaces rely on deep multi-layered ink tones (`#0D0E12`, `#13141C`, `#1A1C26`), subtle 1px structural outlines (`#262938`), and localized illumination (diffused neon blooms on hover and active states) rather than heavy drop shadows.

## Colors

The palette establishes an ultra-dark canvas with distinct depth layers and hyper-saturated gamification accents.

### Color Tiers
- **Surface Canvas (`#0D0E12`):** Primary background base layer for global views and viewport boundaries.
- **Surface Layer 1 (`#13141C`):** Component card containers, sidebars, and navigation rails.
- **Surface Layer 2 (`#1A1C26`):** Elevated modals, dropdown menus, popovers, and nested response blocks.
- **Surface Border (`#262938`):** Strict 1px boundary layer separating nested modules without high visual weight.
- **Surface Border Focus (`#373C52`):** Interactive borders on hover and active inputs.

### Brand & Accent Highlights
- **Primary Violet (`#8B5CF6`):** Primary CTAs, active tab indicators, level milestones, and Aura status.
- **Secondary Cyan (`#06B6D4`):** Secondary actions, upvote interactions, media tags, and live community presence.
- **Tertiary Blue (`#3B82F6`):** Informational links, secondary badges, and media metadata.

### Gamification & State Badges
- **Aura Emerald (`#10B981`):** Positive reputation, completed quests, active online status, and verified creators.
- **Aura Amber (`#F59E0B`):** Streaks, rare meme drops, high Aura rank, and token balances.
- **Nitro Gradient:** Linear gradient from `rgba(139, 92, 246, 1)` to `rgba(6, 182, 212, 1)` used exclusively for high-tier rank frames, active XP progress fills, and premium callouts.

## Typography

The typographic hierarchy pairs **Plus Jakarta Sans** for expressive, modern headings with **Inter** for compact, highly legible body copy and interface labels.

### Rules of Usage
- **Display Headings (`Plus Jakarta Sans`):** Use bold and extra-bold weights (`700`, `800`) with tight letter spacing for page titles, community headers, and meme post headlines.
- **Body & Threading (`Inter`):** Utilize regular (`400`) and medium (`500`) weights for threaded discussions, comment lists, and user metadata to maintain high scanning comfort.
- **Counters & Badges:** Use `label-sm` with uppercase transformation and a subtle tracking bump (`letterSpacing: 0.04em`) for XP amounts, rank tags, and upvote tallies.

## Layout & Spacing

The layout is built on a responsive 3-column architecture optimized for media-rich dashboards and community feeds:

- **Desktop (1200px+):** 
  - Left navigation & community server rail: 260px fixed width.
  - Center feed / main post viewport: 1fr flexible grid (max-width 740px).
  - Right gamification & leaderboard rail: 320px fixed width.
  - Gutters: `gutter-lg` (`1.5rem`).
- **Tablet (768px - 1199px):**
  - Left navigation collapses into an icon dock (72px).
  - Main feed expands across remaining canvas with the leaderboard collapsible or placed below.
  - Gutters: `gutter` (`1rem`).
- **Mobile (< 768px):**
  - Single-column flow with a fixed bottom navigation bar (56px height).
  - Margins set to `margin` (`1rem`) to maximize media viewing width.

### Rhythm & Alignment
- Post cards and input widgets adhere strictly to a 4px/8px micro-grid.
- Feed items use `space-md` (`0.75rem`) vertical spacing between list entities to create dense, continuous scanning like Discord text channels and modern social media boards.

## Elevation & Depth

Visual hierarchy does not use diffuse white light shadows. Instead, depth is established through tonal layering, crisp 1px borders, and colored backglows.

### Layer Stack
1. **Base Surface (Z-0):** `#0D0E12`.
2. **Card & Panel Layer (Z-1):** `#13141C` with `border: 1px solid #262938`.
3. **Floating & Hover Layer (Z-2):** `#1A1C26` with `border: 1px solid #373C52` and an ambient glow (`box-shadow: 0 4px 20px -2px rgba(139, 92, 246, 0.12)`).
4. **Overlay / Dialog Layer (Z-3):** `#13141C` with 80% opacity, `backdrop-filter: blur(12px)`, and `border: 1px solid rgba(139, 92, 246, 0.3)`.

### Glow Accents
- Interactive highlights utilize a subtle inner rim light (`box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.06)`).
- Gamified alerts and Nitro components use localized radial glows (`0 0 16px rgba(139, 92, 246, 0.25)`).

## Shapes

The design language balances friendly, contemporary curvature with structural precision.

- **Standard Cards & Modals:** `rounded-xl` (`1rem` / 16px) for feed posts, user profile cards, and leaderboard panels.
- **Large Panels & Hero Banners:** `rounded-2xl` (`1.5rem` / 24px) for featured community hubs and banner modules.
- **Badges, Pills & Avatars:** Fully circular/pill (`9999px`) for Aura points, online status dots, tags, and category chips.
- **Buttons & Form Controls:** `rounded-lg` (`0.5rem` / 8px) to retain functional, click-targeted sharpness.

## Components

### Buttons
- **Primary:** Violet fill (`#8B5CF6`) with white text (`#FFFFFF`), `font-weight: 600`, 8px padding inline, hover state transitioning to `#7C3AED` with `box-shadow: 0 0 12px rgba(139, 92, 246, 0.4)`.
- **Secondary:** Surface `#1A1C26` background, 1px border `#262938`, text `#E2E8F0`. On hover, border tint switches to `#06B6D4` with text `#38BDF8`.
- **Nitro / Aura Boost:** Gradient `linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%)`, text white, elevated scale transition (`scale: 1.02`).

### Post Cards (Meme / Blog)
- Outer container: `#13141C` background, 1px `#262938` border, `rounded-xl` (16px), `padding: 1.25rem`.
- Left-rail or bottom-docked vote widget: Stacked upvote/counter/downvote cluster styled with rounded pill shape, active upvote toggling `#06B6D4` icon and text color.
- Media viewport: Fully responsive `rounded-lg` wrapper with `#090A0D` matte letterbox for non-standard aspect meme uploads.

### Gamification Elements
- **XP Progress Bar:** Height 6px, track background `#1A1C26` with `rounded-full`. Indicator fill uses gradient `#8B5CF6` to `#06B6D4` with a right-edge highlight pip.
- **Aura Badges:** `inline-flex` items with `height: 24px`, pill-shaped, `padding: 0 8px`, containing an SVG badge icon, small count (`label-sm`), and background tinting based on status:
  - High Rank / Streak: Amber tint (`rgba(245, 158, 11, 0.12)` text `#F59E0B`).
  - Community Mod / Verified: Emerald tint (`rgba(16, 185, 129, 0.12)` text `#10B981`).
  - Nitro Aura: Violet tint (`rgba(139, 92, 246, 0.15)` text `#C4B5FD`).

### Form Inputs
- Background `#0D0E12`, border 1px solid `#262938`, text color `#F1F5F9`, placeholder `#64748B`.
- Focused state: Border transitions to `#8B5CF6` with a ring glow `0 0 0 2px rgba(139, 92, 246, 0.2)`.

### Tags & Filter Chips
- Capsule-shaped pills (`border-radius: 9999px`), surface `#1A1C26`, text `#94A3B8`, border 1px solid `#262938`. Active state gains `#8B5CF6` border and soft glow with violet text.