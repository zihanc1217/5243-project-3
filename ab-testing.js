(function () {
  const EXPERIMENT_KEY = "homepage_hero_v1";
  const STORAGE_KEY = `ab_variant_${EXPERIMENT_KEY}`;
  const VALID_VARIANTS = ["control", "value-first"];
  const EVENTS = [];

  const VARIANT_CONTENT = {
    control: {
      heroTitle: "Plan smarter. Launch faster.",
      heroSubtitle:
        "Fluxboard helps product and marketing teams coordinate work, remove blockers, and ship confident launches.",
      heroPrimaryCta: "Start free trial",
      heroSecondaryCta: "See customer stories",
      heroProof: "Trusted by 2,000+ teams to coordinate product launches.",
      benefitsTitle: "Why teams choose Fluxboard",
      benefit1Title: "Single source of truth",
      benefit1Body:
        "Bring planning docs, deadlines, and owners into one shared workflow.",
      benefit2Title: "Automated launch checklists",
      benefit2Body:
        "Standardize quality checks so launches are predictable and repeatable.",
      benefit3Title: "Clear stakeholder updates",
      benefit3Body:
        "Share status and risks instantly through lightweight weekly snapshots.",
      testimonialTitle: "How customers describe the impact",
      testimonialQuote:
        '"Fluxboard helped us reduce launch prep chaos dramatically. Everyone knows what to do and when to do it."',
      testimonialCitation:
        "Priya Rao, Director of Product Operations at Northbay Tech",
      signupTitle: "Get early access to our latest release",
      signupSubtitle:
        "Join our waitlist and we will send you onboarding details and launch templates.",
      signupButton: "Join waitlist",
      signupSuccess:
        "Thanks! You are on the waitlist. We will follow up shortly.",
      signupError: "Please enter a valid email address.",
      ctaIntent: "trial",
    },
    "value-first": {
      heroTitle: "Recover hours every launch cycle.",
      heroSubtitle:
        "High-performing teams use Fluxboard to reduce launch prep time, automate handoffs, and avoid last-minute chaos.",
      heroPrimaryCta: "See a 2-minute demo",
      heroSecondaryCta: "Review launch metrics",
      heroProof: "Teams report 34% faster launch preparation in the first month.",
      benefitsTitle: "What changes after adopting Fluxboard",
      benefit1Title: "Stop status-chasing in Slack",
      benefit1Body:
        "Shared timelines and owners make dependencies visible without constant check-ins.",
      benefit2Title: "Reduce launch delays",
      benefit2Body:
        "Reusable launch templates keep critical quality checks from getting skipped.",
      benefit3Title: "Prove impact quickly",
      benefit3Body:
        "Track blocker trends and prep velocity to show measurable operational gains.",
      testimonialTitle: "Results teams share after switching",
      testimonialQuote:
        '"Within two sprints, our launch prep process became predictable and significantly less stressful."',
      testimonialCitation:
        "Jordan Kim, Head of Growth Operations at Meridian Labs",
      signupTitle: "Get the launch operations playbook",
      signupSubtitle:
        "Join the waitlist and receive onboarding plus a proven launch checklist template.",
      signupButton: "Get early access",
      signupSuccess:
        "You are in. We will send your playbook and onboarding details soon.",
      signupError: "Please provide a valid work email.",
      ctaIntent: "demo",
    },
  };

  function parseVariantFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const override = params.get("ab_variant");
    return VALID_VARIANTS.includes(override) ? override : null;
  }

  function getStoredVariant() {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      return VALID_VARIANTS.includes(saved) ? saved : null;
    } catch (error) {
      return null;
    }
  }

  function chooseRandomVariant() {
    return Math.random() < 0.5 ? "control" : "value-first";
  }

  function persistVariant(variant) {
    try {
      window.localStorage.setItem(STORAGE_KEY, variant);
    } catch (error) {
      // Ignore storage errors so experiment assignment still works.
    }
  }

  function getOrAssignVariant() {
    const override = parseVariantFromUrl();
    if (override) {
      persistVariant(override);
      return override;
    }

    const stored = getStoredVariant();
    if (stored) {
      return stored;
    }

    const assigned = chooseRandomVariant();
    persistVariant(assigned);
    return assigned;
  }

  function trackEvent(eventName, properties = {}) {
    const payload = {
      event: eventName,
      experiment_key: EXPERIMENT_KEY,
      variant: state.variant,
      timestamp: new Date().toISOString(),
      ...properties,
    };

    EVENTS.push(payload);
    console.log("[ab-test]", payload);

    if (Array.isArray(window.dataLayer)) {
      window.dataLayer.push(payload);
    }

    if (window.analytics && typeof window.analytics.track === "function") {
      window.analytics.track(eventName, payload);
    }
  }

  function applyVariantToPage(variant) {
    const root = document.documentElement;
    root.setAttribute("data-ab-variant", variant);

    const copySet = VARIANT_CONTENT[variant] || VARIANT_CONTENT.control;
    const copyNodes = document.querySelectorAll("[data-copy-key]");
    copyNodes.forEach((node) => {
      const key = node.getAttribute("data-copy-key");
      if (!key || !(key in copySet)) {
        return;
      }
      node.textContent = copySet[key];
    });

    const variantTag = document.getElementById("variantTag");
    if (variantTag) {
      variantTag.textContent = `Current variant: ${variant}`;
    }
  }

  function getContentForCurrentVariant() {
    return VARIANT_CONTENT[state.variant] || VARIANT_CONTENT.control;
  }

  function initSignupForm() {
    const form = document.getElementById("signupForm");
    if (!form) {
      return;
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const input = document.getElementById("emailInput");
      const message = document.getElementById("formMessage");
      if (!input || !message) {
        return;
      }

      const emailValue = input.value.trim();
      const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue);
      const variantCopy = getContentForCurrentVariant();

      if (!validEmail) {
        message.textContent = variantCopy.signupError;
        message.className = "message message-error";
        trackEvent("signup_validation_failed", { reason: "invalid_email" });
        return;
      }

      message.textContent = variantCopy.signupSuccess;
      message.className = "message message-success";

      trackEvent("signup_submitted", {
        email_domain: emailValue.split("@")[1] || null,
      });
      form.reset();
    });
  }

  function initTrackedClicks() {
    const trackedNodes = document.querySelectorAll("[data-track]");
    trackedNodes.forEach((node) => {
      node.addEventListener("click", function () {
        trackEvent(node.getAttribute("data-track"), {
          text: node.textContent ? node.textContent.trim() : null,
          tag: node.tagName.toLowerCase(),
        });
      });
    });
  }

  function initExperiment() {
    state.variant = getOrAssignVariant();
    applyVariantToPage(state.variant);

    trackEvent("experiment_exposure", {
      path: window.location.pathname,
      referrer: document.referrer || null,
    });
  }

  function setVariant(variant) {
    if (!VALID_VARIANTS.includes(variant)) {
      throw new Error(
        `Invalid variant "${variant}". Expected one of: ${VALID_VARIANTS.join(", ")}`
      );
    }

    persistVariant(variant);
    state.variant = variant;
    applyVariantToPage(variant);
    trackEvent("variant_manually_set", { source: "console" });
  }

  function clearVariant() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      // Ignore storage errors
    }
  }

  const state = {
    variant: "control",
  };

  window.abTesting = {
    getVariant: () => state.variant,
    setVariant,
    clearVariant,
    trackEvent,
    getEvents: () => [...EVENTS],
    getExperimentKey: () => EXPERIMENT_KEY,
    getValidVariants: () => [...VALID_VARIANTS],
  };

  document.addEventListener("DOMContentLoaded", function () {
    initExperiment();
    initTrackedClicks();
    initSignupForm();
  });
})();
