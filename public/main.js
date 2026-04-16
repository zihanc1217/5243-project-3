const landingElement = document.getElementById("landing");
const badgeElement = document.getElementById("heroBadge");
const headlineElement = document.getElementById("headline");
const subheadlineElement = document.getElementById("subheadline");
const ctaButton = document.getElementById("ctaButton");
const signupForm = document.getElementById("signupForm");
const featureCards = Array.from(document.querySelectorAll(".feature-card"));

function readForcedVariant() {
  const params = new URLSearchParams(window.location.search);
  const candidate = params.get("variant");
  if (!candidate) {
    return null;
  }
  const normalized = candidate.trim().toUpperCase();
  return normalized === "A" || normalized === "B" ? normalized : null;
}

async function sendEvent(type, metadata = {}) {
  try {
    await fetch("/api/event", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ type, metadata })
    });
  } catch (_error) {
    // Best effort analytics: the user experience should not fail on telemetry errors.
  }
}

function applyVariantStyles(variant) {
  if (variant === "B") {
    landingElement.classList.remove("layout-a");
    landingElement.classList.add("layout-b");
  } else {
    landingElement.classList.remove("layout-b");
    landingElement.classList.add("layout-a");
  }
}

function attachCardTracking() {
  featureCards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      const section = card.dataset.section || "unknown";
      void sendEvent("section_view", { section });
    });
  });
}

async function initializeLanding() {
  const forcedVariant = readForcedVariant();
  const assignmentUrl = forcedVariant
    ? `/api/assignment?variant=${encodeURIComponent(forcedVariant)}`
    : "/api/assignment";

  const response = await fetch(assignmentUrl);
  if (!response.ok) {
    throw new Error("Failed to fetch assignment.");
  }

  const assignment = await response.json();
  const config = assignment.config;

  badgeElement.textContent = `${config.badgeText} • ${config.name}`;
  headlineElement.textContent = config.headline;
  subheadlineElement.textContent = config.subheadline;
  ctaButton.textContent = config.ctaText;
  applyVariantStyles(assignment.variant);

  void sendEvent("page_view", {
    path: window.location.pathname,
    variant: assignment.variant
  });

  ctaButton.addEventListener("click", () => {
    void sendEvent("cta_click", { placement: "hero_primary" });
    ctaButton.textContent = "Great! Check the dashboard for the event.";
  });

  signupForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const emailInput = document.getElementById("emailInput");
    void sendEvent("signup_submit", { domain: emailInput.value.split("@")[1] || "unknown" });
    signupForm.reset();
    ctaButton.textContent = "Signup tracked. View dashboard metrics.";
  });

  attachCardTracking();
}

initializeLanding().catch(() => {
  badgeElement.textContent = "Error loading variant";
  headlineElement.textContent = "Could not load experiment configuration.";
  subheadlineElement.textContent = "Please refresh the page and try again.";
  ctaButton.textContent = "Retry";
  ctaButton.addEventListener("click", () => {
    window.location.reload();
  });
});
