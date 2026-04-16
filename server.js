const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const express = require("express");
const cookieParser = require("cookie-parser");

const app = express();
const PORT = process.env.PORT || 3000;

const DATA_DIR = path.join(__dirname, "data");
const DATA_FILE = path.join(DATA_DIR, "ab-data.json");
const VISITOR_COOKIE = "ab_visitor_id";
const VARIANT_COOKIE = "ab_variant";
const COOKIE_MAX_AGE_MS = 1000 * 60 * 60 * 24 * 30;

const VARIANTS = {
  A: {
    name: "Variant A",
    headline: "Improve your workflow with one focused dashboard.",
    subheadline: "Track key metrics in one place and move from idea to action faster.",
    ctaText: "Start your free setup",
    badgeText: "Classic Layout"
  },
  B: {
    name: "Variant B",
    headline: "Get results faster with a guided analytics experience.",
    subheadline: "Visual prompts and a brighter call-to-action help teams get started quickly.",
    ctaText: "Get started in 60 seconds",
    badgeText: "Guided Layout"
  }
};

function ensureStoreFile() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }

  if (!fs.existsSync(DATA_FILE)) {
    const initialStore = {
      visitors: {},
      events: []
    };
    fs.writeFileSync(DATA_FILE, JSON.stringify(initialStore, null, 2));
  }
}

function readStore() {
  ensureStoreFile();
  try {
    const raw = fs.readFileSync(DATA_FILE, "utf8");
    const parsed = JSON.parse(raw);
    if (!parsed.visitors || !parsed.events) {
      throw new Error("Unexpected data structure.");
    }
    return parsed;
  } catch (error) {
    const fallback = { visitors: {}, events: [] };
    fs.writeFileSync(DATA_FILE, JSON.stringify(fallback, null, 2));
    return fallback;
  }
}

function writeStore(store) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(store, null, 2));
}

function randomVariant() {
  return Math.random() < 0.5 ? "A" : "B";
}

function toVariant(candidate) {
  if (typeof candidate !== "string") {
    return null;
  }

  const key = candidate.trim().toUpperCase();
  return VARIANTS[key] ? key : null;
}

function getOrCreateVisitorId(req, res) {
  const existing = req.cookies[VISITOR_COOKIE];
  if (existing) {
    return existing;
  }

  const visitorId = crypto.randomUUID();
  res.cookie(VISITOR_COOKIE, visitorId, {
    maxAge: COOKIE_MAX_AGE_MS,
    sameSite: "lax",
    httpOnly: false
  });
  return visitorId;
}

function ensureVisitorAssignment(store, visitorId, preferredVariant) {
  const existing = store.visitors[visitorId];
  const variantFromPreference = toVariant(preferredVariant);

  if (variantFromPreference && (!existing || existing.variant !== variantFromPreference)) {
    store.visitors[visitorId] = {
      variant: variantFromPreference,
      assignedAt: new Date().toISOString()
    };
    return { variant: variantFromPreference, assignmentCreated: true, source: "forced" };
  }

  if (existing && toVariant(existing.variant)) {
    return { variant: existing.variant, assignmentCreated: false, source: "stored" };
  }

  const variant = variantFromPreference || randomVariant();
  store.visitors[visitorId] = {
    variant,
    assignedAt: new Date().toISOString()
  };

  return {
    variant,
    assignmentCreated: true,
    source: variantFromPreference ? "cookie" : "random"
  };
}

function recordEvent(store, { visitorId, variant, type, metadata }) {
  store.events.push({
    id: crypto.randomUUID(),
    visitorId,
    variant,
    type,
    metadata: metadata || {},
    timestamp: new Date().toISOString()
  });
}

function erf(x) {
  const sign = x < 0 ? -1 : 1;
  const absX = Math.abs(x);
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const t = 1 / (1 + p * absX);
  const y =
    1 -
    (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX));
  return sign * y;
}

function normalCdf(value) {
  return (1 + erf(value / Math.sqrt(2))) / 2;
}

function twoProportionZTest(successA, totalA, successB, totalB) {
  if (totalA === 0 || totalB === 0) {
    return null;
  }

  const p1 = successA / totalA;
  const p2 = successB / totalB;
  const pooled = (successA + successB) / (totalA + totalB);
  const standardError = Math.sqrt(pooled * (1 - pooled) * ((1 / totalA) + (1 / totalB)));

  if (standardError === 0) {
    return null;
  }

  const zScore = (p2 - p1) / standardError;
  const pValue = 2 * (1 - normalCdf(Math.abs(zScore)));

  return {
    zScore,
    pValue
  };
}

function percentage(numerator, denominator) {
  if (!denominator) {
    return 0;
  }
  return (numerator / denominator) * 100;
}

function summarizeResults(store) {
  const variants = Object.keys(VARIANTS);
  const summaryByVariant = {};

  variants.forEach((variant) => {
    const visitors = Object.values(store.visitors).filter((entry) => entry.variant === variant);
    const events = store.events.filter((event) => event.variant === variant);
    const pageViews = events.filter((event) => event.type === "page_view").length;
    const ctaClicks = events.filter((event) => event.type === "cta_click").length;
    const signups = events.filter((event) => event.type === "signup_submit").length;

    summaryByVariant[variant] = {
      variant,
      name: VARIANTS[variant].name,
      visitors: visitors.length,
      pageViews,
      ctaClicks,
      signups,
      ctaRate: percentage(ctaClicks, visitors.length),
      signupRate: percentage(signups, visitors.length)
    };
  });

  const significance = twoProportionZTest(
    summaryByVariant.A.signups,
    summaryByVariant.A.visitors,
    summaryByVariant.B.signups,
    summaryByVariant.B.visitors
  );

  return {
    variants: summaryByVariant,
    totals: {
      visitors: Object.keys(store.visitors).length,
      events: store.events.length
    },
    significance: significance
      ? {
          metric: "Signup conversion rate",
          zScore: significance.zScore,
          pValue: significance.pValue,
          isSignificantAtFivePercent: significance.pValue < 0.05
        }
      : null
  };
}

app.use(express.json({ limit: "100kb" }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, "public")));

app.get("/api/assignment", (req, res) => {
  const forcedVariant = toVariant(req.query.variant);
  const visitorId = getOrCreateVisitorId(req, res);
  const store = readStore();

  const assignment = ensureVisitorAssignment(
    store,
    visitorId,
    forcedVariant || req.cookies[VARIANT_COOKIE]
  );

  if (assignment.assignmentCreated) {
    recordEvent(store, {
      visitorId,
      variant: assignment.variant,
      type: "assignment",
      metadata: { source: assignment.source }
    });
  }

  writeStore(store);
  res.cookie(VARIANT_COOKIE, assignment.variant, {
    maxAge: COOKIE_MAX_AGE_MS,
    sameSite: "lax",
    httpOnly: false
  });

  res.json({
    visitorId,
    variant: assignment.variant,
    config: VARIANTS[assignment.variant]
  });
});

app.post("/api/event", (req, res) => {
  const { type, metadata } = req.body || {};
  const allowedTypes = new Set(["page_view", "cta_click", "signup_submit", "section_view"]);

  if (!allowedTypes.has(type)) {
    res.status(400).json({
      error: "Invalid event type.",
      allowedTypes: Array.from(allowedTypes)
    });
    return;
  }

  const store = readStore();
  const visitorId = getOrCreateVisitorId(req, res);
  const assignment = ensureVisitorAssignment(store, visitorId, req.cookies[VARIANT_COOKIE]);

  if (assignment.assignmentCreated) {
    recordEvent(store, {
      visitorId,
      variant: assignment.variant,
      type: "assignment",
      metadata: { source: assignment.source }
    });
  }

  recordEvent(store, {
    visitorId,
    variant: assignment.variant,
    type,
    metadata
  });

  writeStore(store);
  res.cookie(VARIANT_COOKIE, assignment.variant, {
    maxAge: COOKIE_MAX_AGE_MS,
    sameSite: "lax",
    httpOnly: false
  });

  res.status(201).json({ ok: true });
});

app.get("/api/results", (_req, res) => {
  const store = readStore();
  res.json(summarizeResults(store));
});

app.post("/api/reset", (_req, res) => {
  const resetStore = {
    visitors: {},
    events: []
  };
  writeStore(resetStore);
  res.json({ ok: true });
});

app.listen(PORT, () => {
  // Keep this log so users immediately see where to open the app.
  console.log(`A/B testing app running on http://localhost:${PORT}`);
});
