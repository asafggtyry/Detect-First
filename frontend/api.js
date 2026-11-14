// Detect First API adapter.
//
// Every request to the Python backend, and every assumption about its JSON,
// lives in this file. app.js only sees the normalized objects returned here.
//
// /api/scan, /api/analyze and /api/reset follow docs/API.md.
//
// PROVISIONAL: the incoming-message simulation and the evidence-span fields are
// being defined by the backend in docs/DYNAMIC_API.md. Until that exists, the
// request built in receiveMessage() and the field names read in
// normalizeIncoming() and collectSpans() are best guesses. When the contract
// lands, those three functions (and `simulateEndpoint` / `scenarios` in
// config.js) are the only places that need to change.
window.DetectFirstApi = (function () {
  "use strict";

  var CONFIG = Object.assign({
    apiBase: "",
    scanEndpoint: "/api/scan",
    analyzeEndpoint: "/api/analyze",
    resetEndpoint: "/api/reset",
    simulateEndpoint: "/api/simulate",
    scenarios: {},
    timeoutMs: 4000
  }, window.DETECT_FIRST_CONFIG || {});

  // Display labels for evidence-rule categories. Unknown categories are shown as sent.
  var CATEGORIES = {
    unsolicited_job_offer: "First-contact job offer",
    upfront_payment_request: "Upfront payment request",
    unrealistic_earnings: "High daily earnings claim",
    vague_job_details: "Limited role details",
    urgency_pressure: "Urgency / pressure",
    unverified_employer: "Employer not verified by demo"
  };
  var CATEGORY_ALIASES = {
    unsolicited_offer: "unsolicited_job_offer",
    unsolicited: "unsolicited_job_offer",
    vague_details: "vague_job_details",
    urgency: "urgency_pressure",
    pressure: "urgency_pressure",
    unverified_employer_identity: "unverified_employer",
    unverified_identity: "unverified_employer"
  };

  // Presenter scenarios. `value` is what is sent to the backend; override the
  // values with `scenarios` in config.js once the backend names them.
  var SCENARIOS = [
    { id: "random", label: "Random", short: "random message" },
    { id: "saved_contact", label: "Family or friend (saved contact)", short: "family or friend" },
    { id: "unknown_harmless", label: "Unknown sender, everyday message", short: "unknown sender" },
    { id: "recruiter", label: "Unknown sender, recruiter-style offer", short: "recruiter-style" }
  ];

  // ---------- transport ----------

  function ApiError(kind, status, detail) {
    this.name = "ApiError";
    this.kind = kind;       // "network" | "timeout" | "http" | "invalid"
    this.status = status || 0;
    this.detail = detail || "";
    this.message = kind + (status ? " " + status : "") + (detail ? ": " + detail : "");
  }
  ApiError.prototype = Object.create(Error.prototype);

  function invalid(detail) { return new ApiError("invalid", 0, detail); }

  // POST JSON and return parsed JSON. `controller` lets a caller cancel the request.
  function post(path, body, controller) {
    controller = controller || new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () { timedOut = true; controller.abort(); }, CONFIG.timeoutMs);
    var options = { method: "POST", credentials: "same-origin", signal: controller.signal };
    if (body !== undefined) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
    return fetch(CONFIG.apiBase + path, options).then(function (response) {
      if (response.ok) {
        return response.json().catch(function () { throw invalid("Response was not JSON"); });
      }
      return response.json().catch(function () { return null; }).then(function (data) {
        var detail = data && typeof data.error === "string" ? data.error : "";
        throw new ApiError("http", response.status, detail);
      });
    }, function () {
      throw new ApiError(timedOut ? "timeout" : "network");
    }).finally(function () { clearTimeout(timer); });
  }

  // A short sentence for the user. `what` names the action, e.g. "receive a message".
  function describeError(error, what) {
    var kind = error && error.kind;
    if (kind === "timeout") return "Couldn’t " + what + ". The server took too long to respond.";
    if (kind === "network") return "Couldn’t " + what + ". The Detect First server can’t be reached.";
    if (kind === "invalid") return "Couldn’t " + what + ". The server sent a response this app can’t read.";
    if (kind === "http") {
      if (error.status === 404 || error.status === 405) {
        return "Couldn’t " + what + ". This server doesn’t provide that feature yet (HTTP " + error.status + ").";
      }
      return "Couldn’t " + what + ". " + (error.detail || "The server reported an error.") +
        " (HTTP " + error.status + ")";
    }
    return "Couldn’t " + what + ".";
  }

  // ---------- analysis results ----------

  function normalizeCategory(value) {
    var key = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    key = CATEGORY_ALIASES[key] || key;
    return { key: key, label: CATEGORIES[key] || String(value) };
  }

  function firstString() {
    for (var i = 0; i < arguments.length; i++) {
      if (typeof arguments[i] === "string" && arguments[i].trim()) return arguments[i];
    }
    return "";
  }

  // Backend offsets count Unicode code points (Python str indices); JavaScript
  // strings count UTF-16 units. Returns a converter, or the identity for plain text.
  function offsetConverter(text) {
    if (!/[\uD800-\uDBFF]/.test(text)) return function (n) { return n; };
    var starts = [];
    var position = 0;
    Array.from(text).forEach(function (ch) { starts.push(position); position += ch.length; });
    starts.push(position);
    return function (n) { return n >= 0 && n < starts.length ? starts[n] : -1; };
  }

  // Resolve one backend-supplied candidate to a range in `text`, or null when it
  // does not describe real text in this message. Never guesses.
  function locate(candidate, text, convert) {
    var phrase = firstString(candidate.text, candidate.phrase, candidate.snippet, candidate.match);
    var start = candidate.start;
    var end = candidate.end;
    if (Number.isInteger(start) && Number.isInteger(end)) {
      var range = [[convert(start), convert(end)], [start, end]].filter(function (r) {
        return r[0] >= 0 && r[1] > r[0] && r[1] <= text.length &&
          (!phrase || text.slice(r[0], r[1]) === phrase);
      })[0];
      if (range) return range;
      // Offsets and quoted phrase disagree, or offsets fall outside the message.
      if (!phrase) return null;
    }
    if (!phrase) return null;
    var index = text.indexOf(phrase);
    return index === -1 ? null : [index, index + phrase.length];
  }

  // Collect evidence spans from the response. Accepts explicit offsets or a
  // verbatim snippet, either listed at the top level or attached to a reason.
  function collectSpans(raw, reasons, text) {
    if (typeof text !== "string" || !text) return [];
    var byCategory = {};
    reasons.forEach(function (reason) { byCategory[reason.key] = reason; });
    var candidates = [];

    var topLevel = raw.spans || raw.evidence_spans || raw.highlights;
    if (Array.isArray(topLevel)) topLevel.forEach(function (span) {
      if (span && typeof span === "object") candidates.push(span);
    });

    raw.reasons.forEach(function (reason) {
      if (!reason || typeof reason !== "object") return;
      var own = Array.isArray(reason.spans) ? reason.spans : reason.span ? [reason.span] : null;
      if (own) {
        own.forEach(function (span) {
          if (span && typeof span === "object") candidates.push(Object.assign({ category: reason.category }, span));
        });
      } else if (Number.isInteger(reason.start) || typeof reason.snippet === "string") {
        candidates.push({ category: reason.category, start: reason.start, end: reason.end, snippet: reason.snippet });
      }
    });

    var convert = offsetConverter(text);
    var spans = [];
    candidates.forEach(function (candidate) {
      var range = locate(candidate, text, convert);
      if (!range || !text.slice(range[0], range[1]).trim()) return;
      var category = candidate.category ? normalizeCategory(candidate.category) : null;
      var reason = category ? byCategory[category.key] : null;
      spans.push({
        start: range[0],
        end: range[1],
        phrase: text.slice(range[0], range[1]),
        key: category ? category.key : "",
        label: category ? category.label : "Evidence",
        explanation: firstString(candidate.explanation, candidate.reason, candidate.evidence, reason && reason.evidence)
      });
    });

    // Highlights cannot nest: keep the earliest span and drop any that overlap it.
    spans.sort(function (a, b) { return a.start - b.start || b.end - a.end; });
    var lastEnd = 0;
    return spans.filter(function (span) {
      if (span.start < lastEnd) return false;
      lastEnd = span.end;
      return true;
    });
  }

  // Validate a scan/analyze response (docs/API.md) and convert it for the UI.
  // `text` is the analyzed message; spans are only kept if they fit inside it.
  function normalizeResult(raw, text) {
    if (!raw || typeof raw.is_scam !== "boolean" || !Array.isArray(raw.reasons) ||
        typeof raw.scanned !== "boolean" || typeof raw.evidence_flagged !== "boolean" ||
        (raw.scanned ? typeof raw.model_flagged !== "boolean" : raw.model_flagged !== null) ||
        ["none", "model", "evidence", "both"].indexOf(raw.warning_source) === -1) {
      throw invalid("Invalid scan response");
    }
    var seen = {};
    var reasons = [];
    raw.reasons.forEach(function (r) {
      var isObj = r && typeof r === "object";
      var name = isObj ? (r.category || r.id || r.label) : r;
      if (!name) return;
      var cat = normalizeCategory(name);
      if (seen[cat.key]) return;
      seen[cat.key] = true;
      reasons.push({
        key: cat.key,
        label: cat.label,
        evidence: isObj && r.evidence ? String(r.evidence) : "",
        snippet: isObj && typeof r.snippet === "string" ? r.snippet : ""
      });
    });
    return {
      flagged: raw.is_scam,
      reasons: reasons,
      spans: collectSpans(raw, reasons, text),
      modelFlagged: raw.model_flagged,
      evidenceFlagged: raw.evidence_flagged,
      warningSource: raw.warning_source,
      scanned: raw.scanned,
      skippedReason: raw.skipped_reason
    };
  }

  // ---------- incoming-message simulation (provisional contract) ----------

  function normalizeIncoming(raw) {
    if (!raw || typeof raw !== "object") throw invalid("Invalid simulation response");
    var sender = raw.sender && typeof raw.sender === "object" ? raw.sender : {};
    var message = raw.message && typeof raw.message === "object" ? raw.message : {};
    var name = firstString(raw.sender, raw.sender_name, raw.name, sender.name, sender.display_name, sender.number).trim();
    var text = firstString(raw.message, raw.text, message.text, message.body);
    var savedFlag = [raw.is_saved_contact, raw.saved, sender.is_saved_contact, sender.saved]
      .filter(function (value) { return typeof value === "boolean"; })[0];

    if (!name || name.length > 200 || !text.trim() || text.length > 5000 || savedFlag === undefined) {
      throw invalid("Invalid simulation response");
    }

    // The simulation may already include the analysis of its own message.
    // A saved contact is never scanned, so any analysis sent for one is ignored.
    var embedded = raw.analysis || raw.scan || raw.result;
    return {
      name: name,
      saved: savedFlag,
      text: text,
      scenario: firstString(raw.scenario, raw.category),
      analysis: embedded && typeof embedded === "object" && !savedFlag ? normalizeResult(embedded, text) : null
    };
  }

  function receiveMessage(scenarioId) {
    var value = Object.prototype.hasOwnProperty.call(CONFIG.scenarios, scenarioId)
      ? CONFIG.scenarios[scenarioId] : scenarioId;
    return post(CONFIG.simulateEndpoint, { scenario: value }).then(normalizeIncoming);
  }

  // ---------- public ----------

  return {
    SCENARIOS: SCENARIOS,
    describeError: describeError,

    // First-contact scan of a chat's first incoming message.
    scan: function (chat, text) {
      return post(CONFIG.scanEndpoint, {
        message: text,
        sender: chat.name,
        is_saved_contact: chat.saved,
        is_first_message: true
      }).then(function (raw) { return normalizeResult(raw, text); });
    },

    // Stateless one-off analysis for the Test Message screen.
    analyze: function (text, controller) {
      return post(CONFIG.analyzeEndpoint, { message: text }, controller)
        .then(function (raw) { return normalizeResult(raw, text); });
    },

    reset: function () {
      return post(CONFIG.resetEndpoint).then(function (data) {
        if (!data || data.reset !== true) throw invalid("Invalid reset response");
      });
    },

    // Ask the backend simulation for one incoming message.
    receiveMessage: receiveMessage
  };
})();
