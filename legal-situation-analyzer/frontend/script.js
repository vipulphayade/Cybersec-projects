const form = document.getElementById("analyze-form");
const descriptionField = document.getElementById("description");
const submitButton = document.getElementById("submit-button");
const statusText = document.getElementById("status-text");
const resultContainer = document.getElementById("result");
const followupPanel = document.getElementById("followup-panel");
const followupForm = document.getElementById("followup-form");
const followupField = document.getElementById("followup-question");
const followupButton = document.getElementById("followup-button");
const followupStatus = document.getElementById("followup-status");
const followupResult = document.getElementById("followup-result");

let lastContext = null;

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const renderList = (items) => {
  if (!items || items.length === 0) {
    return "<li>No specific details available.</li>";
  }

  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
};

const renderConditions = (items) => {
  if (!items || items.length === 0) {
    return "<p class=\"empty-note\">No special condition details were found for this result.</p>";
  }

  return items
    .map(
      (item) => `
        <article class="condition-card">
          <h4>${escapeHtml(item.requirement)}</h4>
          <p>${escapeHtml(item.plain_explanation)}</p>
        </article>
      `
    )
    .join("");
};

const renderRelatedRules = (items) => {
  if (!items || items.length === 0) {
    return "<p class=\"empty-note\">No closely linked supporting rules were found.</p>";
  }

  return items
    .map(
      (item) => `
        <article class="related-rule">
          <strong>${escapeHtml(item.section)}${item.subsection ? `(${escapeHtml(item.subsection)})` : ""}</strong>
          <p>${escapeHtml(item.title)}</p>
        </article>
      `
    )
    .join("");
};

const renderCollapsibleSection = (title, content, sectionClass = "") => `
  <article class="${["card", "result-block", "accordion", sectionClass].filter(Boolean).join(" ")}">
    <button type="button" class="accordion-header" aria-expanded="false">
      <span>${escapeHtml(title)}</span>
      <span class="accordion-icon" aria-hidden="true">+</span>
    </button>
    <div class="accordion-content">
      ${content}
    </div>
  </article>
`;

const initializeCollapsibles = (scope) => {
  const toggles = scope.querySelectorAll(".accordion-header");
  toggles.forEach((toggle) => {
    const accordion = toggle.parentElement;
    const icon = toggle.querySelector(".accordion-icon");
    if (!accordion) {
      return;
    }

    toggle.addEventListener("click", () => {
      const isOpen = accordion.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(isOpen));
      if (icon) {
        icon.textContent = isOpen ? "-" : "+";
      }
    });
  });
};

const resetFollowup = () => {
  if (followupField) {
    followupField.value = "";
  }

  if (followupResult) {
    followupResult.innerHTML = "";
    followupResult.classList.add("hidden");
  }

  if (followupStatus) {
    followupStatus.textContent = "";
  }

  if (followupPanel) {
    followupPanel.classList.add("hidden");
  }
};

const renderResult = (payload) => {
  const confidence = Number.isFinite(Number(payload.confidence))
    ? Math.max(0, Math.min(1, Number(payload.confidence)))
    : 0;
  const confidencePercent = Math.round(confidence * 100);

  lastContext = payload;
  followupPanel.classList.remove("hidden");
  resultContainer.className = "";
  resultContainer.innerHTML = `
    <div class="result-grid">
      <article class="card result-block accent rule-card">
        <span class="result-label">Relevant bye-law</span>
        <h3>Section ${escapeHtml(payload.section || "Not identified")}${payload.subsection ? `(${escapeHtml(payload.subsection)})` : ""}</h3>
        <div class="summary-meta">
          <div>
            <span class="result-label">Rule title</span>
            <p>${escapeHtml(payload.title || "Not identified")}</p>
          </div>
          <div class="confidence-box">
            <span class="result-label">Confidence score</span>
            <div class="confidence-copy">
              <span>Confidence</span>
              <strong>${escapeHtml(confidencePercent)}%</strong>
            </div>
            <div class="confidence-track" aria-hidden="true">
              <span class="confidence-fill" style="width: ${confidencePercent}%;"></span>
            </div>
          </div>
        </div>
      </article>
      <article class="card result-block explanation-card">
        <span class="result-label">Simple explanation</span>
        <p>${escapeHtml(payload.explanation)}</p>
      </article>
      <article class="card result-block example-card">
        <span class="result-label">Example scenario</span>
        <p>${escapeHtml(payload.example)}</p>
      </article>
      <article class="card result-block conditions-card">
        <span class="result-label">Conditions required</span>
        <div class="condition-grid">${renderConditions(payload.conditions_required)}</div>
      </article>
      ${renderCollapsibleSection(
        "Supporting Bye-law Text",
        `<span class="result-label">Supporting bye-law text</span><p>${escapeHtml(payload.citation)}</p>`
      )}
      ${renderCollapsibleSection(
        "Arguments",
        `<span class="result-label">Possible challenge arguments</span><ul>${renderList(payload.possible_challenges)}</ul>`
      )}
      ${renderCollapsibleSection(
        "Related Statutes",
        `<span class="result-label">Related statutes</span><ul>${renderList(payload.related_statutes)}</ul>`
      )}
      ${renderCollapsibleSection(
        "Related Rules",
        `<span class="result-label">Related rules</span><div class="related-rule-grid">${renderRelatedRules(payload.related_rules)}</div>`
      )}
      <article class="card result-block disclaimer">
        <span class="result-label">Important disclaimer</span>
        <p>${escapeHtml(payload.disclaimer)}</p>
      </article>
    </div>
  `;
  initializeCollapsibles(resultContainer);
};

const renderError = (message) => {
  resultContainer.className = "";
  resultContainer.innerHTML = `
    <div class="result-grid">
      <article class="card result-block error">
        <span class="result-label">Request issue</span>
        <p>${escapeHtml(message)}</p>
      </article>
    </div>
  `;
};

const renderFollowup = (payload) => {
  followupResult.classList.remove("hidden");
  followupResult.innerHTML = `
    <article class="result-block">
      <span class="result-label">Follow-up answer</span>
      <p>${escapeHtml(payload.answer)}</p>
    </article>
    <article class="result-block">
      <span class="result-label">Supporting text</span>
      <p>${escapeHtml(payload.citation)}</p>
    </article>
  `;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const description = descriptionField.value.trim();
  if (description.length < 10) {
    renderError("Please provide a little more detail so the system can understand the situation.");
    return;
  }

  submitButton.disabled = true;
  statusText.textContent = "Analyzing...";
  resetFollowup();

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ description }),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      const message = errorPayload?.detail || "The analyzer could not process the request.";
      throw new Error(message);
    }

    const payload = await response.json();
    renderResult(payload);
    statusText.textContent = "Analysis completed.";
  } catch (error) {
    renderError(error.message || "Unexpected error while contacting the API.");
    statusText.textContent = "Analysis failed.";
    followupPanel.classList.add("hidden");
    lastContext = null;
  } finally {
    submitButton.disabled = false;
  }
});

followupForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = followupField.value.trim();
  if (!lastContext) {
    followupStatus.textContent = "Analyze a situation first.";
    return;
  }

  if (question.length < 2) {
    followupStatus.textContent = "Please enter a short follow-up question.";
    return;
  }

  followupButton.disabled = true;
  followupStatus.textContent = "Getting answer...";

  try {
    const response = await fetch("/api/followup", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        context: lastContext,
      }),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      const message = errorPayload?.detail || "The follow-up request could not be processed.";
      throw new Error(message);
    }

    const payload = await response.json();
    renderFollowup(payload);
    followupStatus.textContent = "Follow-up answered.";
  } catch (error) {
    followupResult.classList.remove("hidden");
    followupResult.innerHTML = `
      <article class="result-block error">
        <span class="result-label">Follow-up issue</span>
        <p>${escapeHtml(error.message || "Unexpected follow-up error.")}</p>
      </article>
    `;
    followupStatus.textContent = "Follow-up failed.";
  } finally {
    followupButton.disabled = false;
  }
});
