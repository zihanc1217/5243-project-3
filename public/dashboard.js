const totalVisitorsElement = document.getElementById("totalVisitors");
const totalEventsElement = document.getElementById("totalEvents");
const variantTableBody = document.getElementById("variantTableBody");
const significanceTextElement = document.getElementById("significanceText");
const refreshButton = document.getElementById("refreshButton");
const resetButton = document.getElementById("resetButton");

function formatPercent(value) {
  if (typeof value !== "number") {
    return "0.00%";
  }
  return `${value.toFixed(2)}%`;
}

function formatNumber(value, fractionDigits = 4) {
  if (typeof value !== "number") {
    return "N/A";
  }
  return value.toFixed(fractionDigits);
}

function renderVariantRows(variants) {
  const rows = Object.values(variants)
    .sort((a, b) => a.variant.localeCompare(b.variant))
    .map((variantData) => {
      return `
        <tr>
          <td>${variantData.name} (${variantData.variant})</td>
          <td>${variantData.visitors}</td>
          <td>${variantData.pageViews}</td>
          <td>${variantData.ctaClicks}</td>
          <td>${variantData.signups}</td>
          <td>${formatPercent(variantData.ctaRate)}</td>
          <td>${formatPercent(variantData.signupRate)}</td>
        </tr>
      `;
    })
    .join("");

  variantTableBody.innerHTML = rows;
}

function renderSignificance(significance) {
  if (!significance) {
    significanceTextElement.textContent =
      "Not enough visitor data in both variants to compute significance.";
    return;
  }

  const verdict = significance.isSignificantAtFivePercent
    ? "Difference is significant at alpha = 0.05."
    : "Difference is not significant at alpha = 0.05.";

  significanceTextElement.textContent = `${significance.metric}: z=${formatNumber(
    significance.zScore,
    3
  )}, p=${formatNumber(significance.pValue, 5)}. ${verdict}`;
}

async function fetchResults() {
  const response = await fetch("/api/results");
  if (!response.ok) {
    throw new Error("Unable to load results.");
  }
  return response.json();
}

async function refreshDashboard() {
  const results = await fetchResults();
  totalVisitorsElement.textContent = results.totals.visitors;
  totalEventsElement.textContent = results.totals.events;
  renderVariantRows(results.variants);
  renderSignificance(results.significance);
}

refreshButton.addEventListener("click", () => {
  void refreshDashboard();
});

resetButton.addEventListener("click", async () => {
  const shouldReset = window.confirm(
    "Reset all experiment data? This clears visitors and event history."
  );
  if (!shouldReset) {
    return;
  }

  const response = await fetch("/api/reset", {
    method: "POST"
  });

  if (!response.ok) {
    window.alert("Failed to reset data.");
    return;
  }

  await refreshDashboard();
});

refreshDashboard().catch(() => {
  significanceTextElement.textContent = "Failed to load dashboard data.";
});
