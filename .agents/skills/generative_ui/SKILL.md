---
name: generative_ui
description: How to render rich interactive HTML widgets inline in the chat or as standalone artifacts. Use this skill when you want to show the user diagrams, data visualizations, interactive controls, educational walkthroughs, or any rich visual content beyond plain text and markdown.
metadata:
  icon: dashboard
---

# Generative UI Skill

This skill provides guidelines and patterns for rendering rich interactive HTML widgets inline in the chat or as standalone artifacts within JARVIS.

## Core Rules for Generative UI
1. **Self-Contained & Responsive:** Every component must be fully responsive and function seamlessly on both desktop HUDs and mobile screens.
2. **Tailwind CSS & Design Tokens:** Use clean design tokens, high-contrast dark themes (`--bg-dark: #07090e`, `--panel-bg: rgba(14, 20, 33, 0.75)`, `--cyan: #00e5ff`, `--emerald: #00e676`), and clear typographic hierarchy.
3. **Interactive Controls:** Include interactive tabs, search-as-you-type inputs with millisecond debounce, real-time stat counters, and modal dialogs.
4. **Theme Adaptation:** Respect dark/light themes cleanly using CSS variables and translucency (backdrop blur).
5. **Security & Sandboxing:** Zero remote scripts or CDNs without integrity; avoid unsanitized `innerHTML` with user inputs.

## Component Patterns
- **Local Search HUD:** Search bar with live latency badge (<5ms hot cache, 1-20ms FTS5, 20-50ms vector), search mode switcher (Hybrid, Keyword, Semantic, Research), and result cards with highlighted snippets.
- **Career-Ops Pipeline Board:** Kanban/Funnel visualization with fit score badges, ATS resume preview, STAR interview cards, and salary comparison bar charts.
- **System Telemetry Gauges:** Real-time CPU, RAM, disk, and process indicators with pulsing status rings.

