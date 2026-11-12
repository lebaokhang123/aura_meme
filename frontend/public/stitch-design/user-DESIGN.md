---
name: Cyber-Clean Neon Community
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
  on-surface-variant: '#cac4d0'
  inverse-surface: '#e3e1ed'
  inverse-on-surface: '#2f3039'
  outline: '#948f9a'
  outline-variant: '#49454f'
  surface-tint: '#d0bcff'
  primary: '#e9ddff'
  on-primary: '#37265e'
  primary-container: '#d0bcff'
  on-primary-container: '#594983'
  inverse-primary: '#665590'
  secondary: '#d0bcff'
  on-secondary: '#3c0091'
  secondary-container: '#5424af'
  on-secondary-container: '#c1a7ff'
  tertiary: '#acedff'
  on-tertiary: '#003640'
  tertiary-container: '#4cd7f6'
  on-tertiary-container: '#005b6b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#210f48'
  on-primary-fixed-variant: '#4d3d76'
  secondary-fixed: '#e9ddff'
  secondary-fixed-dim: '#d0bcff'
  on-secondary-fixed: '#23005c'
  on-secondary-fixed-variant: '#5424af'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#12131b'
  on-background: '#e3e1ed'
  surface-variant: '#33343d'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '800'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
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
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
  mono-counter:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  mono-tag:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system expresses a nocturnal, razor-sharp digital culture hub tailored for Vietnamese youth, digital natives, and internet subcultures. Blending modern forum dynamics with the sleek, high-efficiency ergonomics of contemporary chat tools, the aesthetic embraces a **Cyber-Clean** direction—restrained dark-mode surfaces energized by targeted violet luminescence and electric cyan highlights.

### Emotional Tone
- **Electric yet Focused:** Captures late-night internet camaraderie without sensory overload or visual fatigue.
- **Mysterious & Polished:** Depth is established through deep obsidian layers rather than stark black voids, accented with subtle neon diffusions.
- **Culturally Attuned:** Built from the ground up for Vietnamese typography, ensuring stacked diacritics sit cleanly alongside English community idioms.

### Stylistic Directives
- **Subtle Luminescence:** Active states, selected feeds, and upvote counters leverage atmospheric outer glows (`0 0 16px rgba(160, 120, 255, 0.25)`) instead of flat solid fills.
- **Clean Precision:** All containers feature micro-borders (1px) with controlled contrast to frame media assets and user comments sharply.
- **Content Hierarchy:** Media is the primary hero. The UI recedes gracefully into the background until engaged by hover or interaction.

## Colors

The palette relies on a carefully stepped dark tonal foundation, punctuated by atmospheric purples and electric cyan accents.

### Tonal Foundations
- **Base Canvas (`#12131B`):** The primary canvas background color for all root-level viewports.
- **Lowest Surface (`#0D0E15`):** Reserved for backdrop canvas wells, recessed code blocks, and behind-media embeds.
- **Card Surface (`#1A1B23`):** Default card background for feed posts, interactive list items, and flyout menus.
- **Elevated Surface (`#1E1F27`):** Elevated modals, popovers, dropdown tooltips, and floating controls.

### Structural Lines & Dividers
- **Default Border (`#292932`):** Primary 1px structural separator across sidebars, feed dividers, and default input boundaries.
- **Highlight Border (`#33343D`):** Elevated container outlines, active card boundaries, and hover borders.

### Typographic Contrast
- **Primary Text (`#E3E1ED`):** High-clarity off-white for headers, post titles, and high-priority reads.
- **Secondary Text (`#CBC3D7`):** Softened lavender-tinted gray for body paragraphs, sub-metadata, and timestamps.
- **Tertiary / Muted (`#7A788A`):** For disabled items, placeholder copy, and low-priority tags.

### Accents & Signatures
- **Primary Lavender (`#D0BCFF`):** Dominant interactive color, primary actions, and key brand anchors.
- **Stronger Violet (`#A078FF`):** Focused states, active tabs, trending metrics, and interactive glows.
- **Cyan Accent (`#4CD7F6`):** Highlights, badges, live stream indicators, and secondary focus alerts.
- **Electric Blue (`#4D8EFF`):** Links, upvoted states, and verified community markers.

## Typography

The type system balances expressive modern headings with high-legibility body copy tuned explicitly for complex Vietnamese diacritics (e.g., ể, ộ, ẵ, ự).

### Font Roles
- **Headlines (`Plus Jakarta Sans`):** Modern geometric posture with open apertures, lending an energetic yet polished edge to post headings, channel names, and banners.
- **Body (`Inter`):** Systematic neutral baseline designed to ensure dense comment threads and fast-paced feeds remain readable across all density levels without tone clashes.
- **Counters & Code (`JetBrains Mono`):** Applied to vote totals, engagement metrics, system timestamps, user handles, and cryptographic tags (`Bảo Khố`) to reinforce the cyber feel.

### Diacritic Accommodations
- Line heights on body styles are locked to a minimum of `1.5x` (`22px` on `14px` body) to guarantee no clipping occurs on double-stacked tone marks in Vietnamese script.
- Uppercase transformations are avoided on long titles to prevent accented vowels from colliding with adjacent layout boundaries.

## Layout & Spacing

The layout is built around a multi-column spatial distribution anchored to an **8px base grid system**.

### Desktop Architecture (Viewport ≥ 1280px)
- **Top Bar:** Fixed `64px` height spanning the viewport. Houses the primary brand identifier, a centered search field (`w: 440px`), notification pulses, and the user profile tray.
- **Left Navigation Rail:** `240px` static width. Houses community hubs, primary feeds (*Trang chủ*, *Khám phá*, *Xếp hạng*), and vault collections (*Bảo Khố*).
- **Center Meme Feed:** Fixed max-width `660px` centered canvas. Primary interaction column housing content upload triggers, sorting bars, and stacked meme cards.
- **Right Context Rail:** `275px` static width. Houses community rules, leaderboard widgets, trending hashtags, and platform metadata (*Giới thiệu*, *Liên hệ*).

### Responsive Adaptation
- **Tablet (768px – 1279px):** The right context rail folds into a collapsible sheet or floating icon trigger. The left navigation contracts to an icon-only strip (`72px`). Center feed expands dynamically to consume remaining space up to `720px`.
- **Mobile (< 768px):** Single-column layout. The left navigation translates into a bottom tab bar (`56px` height) featuring core routes (*Trang chủ*, *Khám phá*, *Đăng tải*, *Bảo Khố*, *Cá nhân*). Post cards span edge-to-edge with `12px` lateral padding.

## Elevation & Depth

Visual hierarchy is constructed through tonal layering augmented by atmospheric neon bloom rather than traditional muddy drop shadows.

### Surface Tiers
- **Tier 0 (Deep Ground - `#0D0E15`):** Canvas bedrock, media letterboxing, and code containers.
- **Tier 1 (Base Viewport - `#12131B`):** Global page wrapper and un-carded layout margins.
- **Tier 2 (Default Container - `#1A1B23`):** Post cards, sidebar panels, modal bodies. Defined by a crisp `1px solid #292932` edge.
- **Tier 3 (Floating Elements - `#1E1F27`):** Dropdown menus, tooltips, popovers, and sticky sub-navigation bars. Outlined by `1px solid #33343D`.

### Neon Glow & Atmosphere
- **Active Violet Bloom:** High-engagement nodes (e.g., active filter chips, current route tabs, and upvoted states) emit a diffused violet aura: `box-shadow: 0 0 16px rgba(160, 120, 255, 0.18)`.
- **Cyan Pulse:** Reserved for real-time notifications, newly minted badges, and trending alerts: `box-shadow: 0 0 12px rgba(76, 215, 246, 0.22)`.
- **Card Hover Elevation:** On desktop hover, cards subtly elevate by swapping border color to `#33343D` and applying an ultra-soft bottom shadow: `box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5)`.

## Shapes

The interface balances soft curved corners with geometric structure, communicating modern approachability without losing its cybernetic edge.

### Radius Conventions
- **Base Components (`rounded-md`, 8px / 0.5rem):** Standard buttons, input search fields, drop-down menus, and tooltips.
- **Medium Structural Elements (`rounded-lg`, 16px / 1rem):** Secondary containers, image embed wrappers, and sub-panels.
- **Primary Cards (`rounded-xl`, 24px / 1.5rem):** Primary feed cards, modal windows, and hero promo banners.
- **Pill Badges (`rounded-full`):** Category tags, counter chips, avatar frames, and live engagement indicators.

## Components

### Buttons
- **Primary Action:** Solid background with lavender tint (`#D0BCFF`), text in deep obsidian (`#0D0E15`), `Plus Jakarta Sans` font weight 600. On hover, shifts to `#A078FF` with an electric glow (`0 0 16px rgba(160, 120, 255, 0.4)`).
- **Secondary Action:** Transparent fill, `1px solid #33343D`, text in `#E3E1ED`. On hover, background shifts to `#1E1F27` and border shifts to `#D0BCFF`.
- **Ghost / Icon Button:** Transparent background, text `#CBC3D7`. On hover, background shifts to `rgba(208, 188, 255, 0.08)` and text turns to `#E3E1ED`.

### Cards (Meme Feed Cards)
- **Container:** Background `#1A1B23`, border `1px solid #292932`, border radius `20px` (`rounded-xl`), padding `16px`.
- **Header:** Author avatar (`36px` circle), username in `#E3E1ED` (font weight 600), post timestamp in `JetBrains Mono` (`#CBC3D7`, 12px), action overflow icon on right.
- **Media Frame:** Contained within `rounded-lg` (16px), background `#0D0E15` to ensure non-standard aspect ratios maintain contrast.
- **Engagement Bar:** Horizontal pill cluster containing vertical vote controls, comment triggers, share actions, and the *Bảo Khố* bookmarking switch.

### Vote Stepper / Counters
- **Vote Pillar:** Pill-shaped container (`rounded-full`) with background `#1E1F27`, border `1px solid #292932`.
- **Upvote Active:** Icon transitions to `#A078FF`, count text set in `JetBrains Mono` `#D0BCFF`, subtle ambient glow.
- **Downvote Active:** Icon and count transition to muted electric blue (`#4D8EFF`).

### Search Field (Header 64px)
- **Container:** Centered in top bar, height `40px`, max width `440px`, background `#1A1B23`, border `1px solid #292932`, border radius `8px`.
- **Typography:** Placeholder text `#7A788A` ("Tìm kiếm meme, cộng đồng, thẻ..."), active text `#E3E1ED`.
- **Focus State:** Border transitions to `#A078FF` with cyan accent highlight: `box-shadow: 0 0 0 1px #A078FF, 0 0 12px rgba(76, 215, 246, 0.2)`.

### Chips & Filter Tabs
- **Filter Chip:** Height `32px`, pill-shaped (`rounded-full`), background `#1A1B23`, border `1px solid #292932`, text `#CBC3D7`.
- **Selected State:** Background `rgba(160, 120, 255, 0.12)`, border `1px solid #A078FF`, text `#D0BCFF`, accompanied by a small active dot indicator.

### Input Fields & Comment Areas
- **Comment Input:** Multi-line text field, background `#12131B`, border `1px solid #292932`, border radius `12px`, padding `12px 16px`. Focus state shifts border to `#A078FF`.

### Vietnamese Localization Patterns
- **Standard Navigation Strings:** *Trang chủ* (Home), *Khám phá* (Explore), *Xếp hạng* (Leaderboard), *Bảo Khố* (Vault/Saved), *Đăng tải* (Upload/Post), *Giới thiệu* (About), *Liên hệ* (Contact).
- **Metric Formatting:** Metrics display compact notations compatible with local formats (e.g., `12,4k lượt thích`, `852 bình luận`).