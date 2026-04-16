# Experiment-Ready Website Starter

This repository now contains a lightweight website scaffold designed so we can
run A/B tests on it later without restructuring everything.

## What is included

- A landing page (`index.html`)
- Styling (`styles.css`)
- Client-side experiment framework (`ab-testing.js`)
  - 50/50 variant assignment
  - Local persistence via `localStorage`
  - Query parameter override (`?ab_variant=control` or `?ab_variant=value-first`)
  - Exposure and interaction tracking hooks

## Run locally

Use any static server. Example with Python:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## A/B testing controls

- Current assigned variant:
  - `window.abTesting.getVariant()`
- All tracked events for current page view:
  - `window.abTesting.getEvents()`
- Force a variant manually in the browser:
  - `window.abTesting.setVariant("control")`
  - `window.abTesting.setVariant("value-first")`
- Clear stored assignment:
  - `window.abTesting.clearVariant()`

## Tracking integration

`ab-testing.js` will:

- log each event to the console
- push to `window.dataLayer` (if available)
- call `window.analytics.track(...)` (if available)

That makes it easy to plug into analytics tools later with minimal changes.
