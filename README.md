# A/B Test Website (Project 3)

This repository contains a complete website for running a simple A/B test experiment.
It includes:

- a landing page with two variants (A and B),
- random user assignment with sticky cookies,
- event tracking for page views, CTA clicks, section views, and signup submissions,
- a dashboard to monitor experiment metrics and statistical significance,
- and an API to reset experiment data for repeated trials.

## Features

### 1) Experiment assignment

- Users are randomly assigned to variant `A` or `B` on first visit.
- Assignment persists using cookies so users keep the same variant.
- You can force assignment via URL for demonstration:
  - `http://localhost:3000/?variant=A`
  - `http://localhost:3000/?variant=B`

### 2) Landing page behavior

- Each variant has different copy and CTA styling.
- Events are recorded via API:
  - `page_view`
  - `cta_click`
  - `section_view`
  - `signup_submit`

### 3) Dashboard and analysis

Open `http://localhost:3000/dashboard.html` to view:

- total visitors and total events,
- per-variant counts (visitors, page views, CTA clicks, signups),
- conversion rates,
- two-proportion z-test output (z-score, p-value, significance at alpha=0.05).

### 4) Data storage

Experiment data is stored locally in:

`data/ab-data.json`

This file is created automatically at runtime.

## Run locally

### Prerequisites

- Node.js 18+ (or any modern Node with `crypto.randomUUID`)
- npm

### Install dependencies

```bash
npm install
```

### Start server

```bash
npm start
```

Then open:

- Landing page: `http://localhost:3000/`
- Dashboard: `http://localhost:3000/dashboard.html`

## API overview

### `GET /api/assignment`

Returns visitor assignment and variant config.

Optional query parameter:

- `variant=A|B` forces assignment.

### `POST /api/event`

Records a user event.

Example body:

```json
{
  "type": "cta_click",
  "metadata": { "placement": "hero_primary" }
}
```

Allowed event types: `page_view`, `cta_click`, `signup_submit`, `section_view`.

### `GET /api/results`

Returns aggregated metrics and statistical significance summary.

### `POST /api/reset`

Clears all stored visitor and event data.

## Notes for Project 3 report

This app gives your team a full experiment platform. For your final report, you can:

1. Define a hypothesis (for example: "Variant B increases signup rate").
2. Collect data by sharing the app link.
3. Export or inspect `data/ab-data.json`.
4. Use `/api/results` and additional analysis scripts (Python/R) for deeper statistical checks.
