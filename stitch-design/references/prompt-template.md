# Stitch Prompt Template

Write one prompt per screen. Be specific. Stitch does much better with concrete, real copy and clear layout structure than with vague words like "modern" or "clean".

```markdown
<Product> is <what it is> for <who>. Design the <page name> page for <DESKTOP|MOBILE>.

STYLE
Mood: <3 adjectives, e.g. futuristic, confident, premium>.
Palette described in words plus hex, with explicit roles:
- Background: <e.g. deep midnight blue (#0B1030)>
- Primary Accent: <e.g. neon violet (#8B5CF6) for buttons & active states>
- Secondary Accent: <e.g. cyan (#06B6D4) for badges & highlights>
- Surface / Cards: <e.g. glassmorphism / dark slate (#1E293B)>
- Text: <e.g. crisp white (#FFFFFF) for headings, muted gray (#94A3B8) for body>
Typography: <e.g. bold geometric sans headings, readable sans body>.
Shapes: <corner radius, e.g. 12px, soft shadows, borders>.
Imagery: <photos / illustrations / abstract graphics>.

LAYOUT (Top to bottom)
1. <Navigation: brand logo left, menu links, action button "Sign In" / "Get Started">
2. <Hero section: punchy headline, descriptive subtext, primary CTA + secondary link, hero graphic/preview right>
3. <Key Features / Value prop: 3 or 4 cards with icons, bold titles, and 2-sentence descriptions>
4. <Social Proof / Metrics / Pricing / Interactive preview section>
N. <Footer: multi-column links, copyright, theme switcher>

CONTENT
Use this real copy, no lorem ipsum: <explicit headlines, button labels, realistic prices, data points, user names>.

COMPONENTS AND STATES
<Buttons: primary, secondary, hover states; Input fields with placeholder & focus ring; Metric cards with growth tags; Toggle switches>

RULES
Keep the same visual style and design language as <anchor page>. High text contrast (WCAG AA). Avoid: generic stock-photo appearance, empty space without purpose, blurry gradients.
```

## Tips for Best Results
- **Anchor First**: Always generate the home/main landing screen first. It establishes the "Design DNA" (palette, typography, border radius).
- **Style Inheritance**: For subsequent screens (e.g. Settings, Dashboard, Pricing), pass the anchor screen's color hexes and styling rules directly into the prompt with the instruction *"Keep the exact same visual style as the Home page."*
- **Edits**: To modify an existing screen, use the `edit_screens` API call and state clearly what changes and what stays identical.
