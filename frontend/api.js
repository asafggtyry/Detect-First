// Detect First API adapter.
//
// Every request to the Python backend, and every assumption about its JSON,
// lives in this file. app.js only sees the normalized objects returned here.
//
// Endpoint and response handling follows docs/API.md and docs/DYNAMIC_API.md.
window.DetectFirstApi = (function () {
  "use strict";

  var CONFIG = Object.assign({
    apiBase: "",
    timeoutMs: 4000
  }, window.DETECT_FIRST_CONFIG || {});
  var ENDPOINTS = {
    scan: "/api/scan",
    analyze: "/api/analyze",
    history: "/api/demo/history",
    receive: "/api/demo/receive",
    reset: "/api/demo/reset",
    decide: "/api/demo/conversations/",
    evaluationStart: "/api/evaluation/start",
    evaluationNext: "/api/evaluation/next",
    evaluationArbitrary: "/api/evaluation/arbitrary"
  };

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

  // IDs match the backend scenario_label values; random omits scenario_label.
  var SCENARIOS = [
    { id: "random", label: "Random", short: "random message" },
    { id: "family_friend", label: "Family or friend (saved contact)", short: "family or friend" },
    { id: "normal_stranger", label: "Unknown sender, everyday message", short: "unknown sender" },
    { id: "potential_fraudulent_recruiter", label: "Unknown sender, recruiter-style offer", short: "recruiter-style" }
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

  // Send a same-origin request and return parsed JSON. Controllers allow cancellation.
  function request(method, path, body, controller) {
    controller = controller || new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () { timedOut = true; controller.abort(); }, CONFIG.timeoutMs);
    var options = { method: method, credentials: "same-origin", signal: controller.signal };
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

  function post(path, body, controller) { return request("POST", path, body, controller); }
  function get(path, controller) { return request("GET", path, undefined, controller); }

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

  // Resolve one backend-supplied Python-code-point span to the corresponding
  // UTF-16 range, rejecting stale or mismatched excerpts.
  function locate(candidate, text, convert) {
    if (!Number.isInteger(candidate.start) || !Number.isInteger(candidate.end) ||
        typeof candidate.excerpt !== "string" || !candidate.excerpt ||
        candidate.source !== "evidence_rule") return null;
    var start = convert(candidate.start);
    var end = convert(candidate.end);
    if (start < 0 || end <= start || end > text.length ||
        text.slice(start, end) !== candidate.excerpt) return null;
    return [start, end];
  }

  // Only structured rule spans are highlights; model labels and reason text
  // are intentionally not treated as explanations.
  function collectSpans(raw, text) {
    if (typeof text !== "string" || !text) return [];
    var candidates = Array.isArray(raw.evidence_spans) ? raw.evidence_spans : [];

    var convert = offsetConverter(text);
    var spans = [];
    candidates.forEach(function (candidate) {
      if (!candidate || typeof candidate !== "object" ||
          typeof candidate.category !== "string" ||
          typeof candidate.explanation !== "string" || !candidate.explanation.trim()) return;
      var range = locate(candidate, text, convert);
      if (!range || !text.slice(range[0], range[1]).trim()) return;
      var category = normalizeCategory(candidate.category);
      spans.push({
        start: range[0],
        end: range[1],
        phrase: text.slice(range[0], range[1]),
        key: category.key,
        label: category.label,
        explanation: candidate.explanation
      });
    });

    // Highlights cannot nest: retain the longest span at a shared start, then
    // discard later overlaps in a stable category/excerpt order.
    spans.sort(function (a, b) {
      return a.start - b.start || b.end - a.end || a.key.localeCompare(b.key);
    });
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
      spans: collectSpans(raw, text),
      modelFlagged: raw.model_flagged,
      evidenceFlagged: raw.evidence_flagged,
      warningSource: raw.warning_source,
      scanned: raw.scanned,
      skippedReason: raw.skipped_reason
    };
  }

  // ---------- server-backed dynamic conversation shapes ----------

  function normalizeConversation(raw) {
    if (!raw || typeof raw !== "object" || typeof raw.id !== "string" || !raw.id ||
        typeof raw.sender_name !== "string" || !raw.sender_name.trim() ||
        typeof raw.sender !== "string" || typeof raw.saved_contact !== "boolean" ||
        !Array.isArray(raw.messages) || raw.messages.length === 0 ||
        SCENARIOS.slice(1).every(function (scenario) { return scenario.id !== raw.scenario_label; })) {
      throw invalid("Invalid conversation response");
    }

    var messages = raw.messages.map(function (message) {
      if (!message || typeof message.text !== "string" || !message.text ||
          ["incoming", "outgoing"].indexOf(message.direction) === -1) {
        throw invalid("Invalid conversation message");
      }
      return {
        dir: message.direction === "incoming" ? "in" : "out",
        text: message.text,
        time: firstString(message.time),
        synthetic: message.synthetic === true
      };
    });
    var firstIncoming = messages.filter(function (message) { return message.dir === "in"; })[0];
    if (!firstIncoming) throw invalid("Conversation has no incoming message");
    var analysis = raw.analysis && firstIncoming && !raw.saved_contact
      ? normalizeResult(raw.analysis, firstIncoming.text) : null;
    if (!raw.saved_contact && !analysis) throw invalid("Missing conversation analysis");
    if (raw.saved_contact && raw.analysis && raw.analysis.scanned !== false) {
      throw invalid("Saved contact must not be scanned");
    }
    if (raw.decision !== null && raw.decision !== undefined &&
        ["blocked", "accepted"].indexOf(raw.decision) === -1) {
      throw invalid("Invalid conversation decision");
    }

    return {
      id: raw.id,
      name: raw.sender_name,
      sender: raw.sender,
      saved: raw.saved_contact,
      scenarioLabel: raw.scenario_label,
      messages: messages,
      analysis: analysis,
      decision: raw.decision || null,
      serverBacked: true
    };
  }

  function normalizeIncoming(raw) {
    if (!raw || typeof raw !== "object" || !raw.conversation) {
      throw invalid("Invalid receive response");
    }
    return {
      conversation: normalizeConversation(raw.conversation),
      simulationFixtureCheck: raw.simulation_fixture_check || null
    };
  }

  function normalizeHistory(raw) {
    if (!raw || !Array.isArray(raw.conversations) ||
        !raw.decisions || typeof raw.decisions !== "object" || Array.isArray(raw.decisions)) {
      throw invalid("Invalid conversation history");
    }
    var decisions = {};
    Object.keys(raw.decisions).forEach(function (id) {
      var decision = raw.decisions[id];
      if (typeof id === "string" && ["blocked", "accepted"].indexOf(decision) !== -1) {
        decisions[id] = decision;
      }
    });
    return {
      conversations: raw.conversations.map(normalizeConversation),
      decisions: decisions,
      simulationFixtureCheck: raw.simulation_fixture_check || null
    };
  }

  function receiveMessage(scenarioId) {
    var body = scenarioId && scenarioId !== "random" ? { scenario_label: scenarioId } : {};
    return post(ENDPOINTS.receive, body).then(normalizeIncoming);
  }

  // Blind-evaluation responses are shown as returned, so reject anything incomplete
  // rather than render a partly made-up result.
  function checkEvaluation(raw) {
    function bit(value) { return value === 0 || value === 1; }
    var ok = raw && typeof raw === "object" &&
      Number.isInteger(raw.sample_index) && Number.isInteger(raw.total_samples) &&
      raw.total_samples > 0 && raw.sample_index >= 0 && raw.sample_index <= raw.total_samples &&
      raw.metrics && typeof raw.metrics === "object";
    if (ok && typeof raw.text !== "undefined") {
      ok = typeof raw.text === "string" && raw.text.length > 0 && raw.sample_index > 0 &&
        bit(raw.model_prediction) && bit(raw.evidence_prediction) &&
        bit(raw.combined_prediction) && bit(raw.reference_label) &&
        ["model", "evidence_rules", "combined_warning"].every(function (key) {
          var metric = raw.metrics[key];
          return metric && ["examples", "true_positives", "true_negatives", "false_positives", "false_negatives"]
            .every(function (field) { return Number.isInteger(metric[field]) && metric[field] >= 0; });
        });
    }
    if (!ok) throw invalid("Invalid evaluation response");
    return raw;
  }

  // ---------- public ----------

  return {
    SCENARIOS: SCENARIOS,
    describeError: describeError,

    // First-contact scan of a chat's first incoming message.
    scan: function (chat, text) {
      return post(ENDPOINTS.scan, {
        message: text,
        sender: chat.name,
        is_saved_contact: chat.saved,
        is_first_message: true
      }).then(function (raw) { return normalizeResult(raw, text); });
    },

    // Stateless one-off analysis for the Test Message screen.
    analyze: function (text, controller) {
      return post(ENDPOINTS.analyze, { message: text }, controller)
        .then(function (raw) { return normalizeResult(raw, text); });
    },

    reset: function () {
      return post(ENDPOINTS.reset).then(function (data) {
        if (!data || data.reset !== true) throw invalid("Invalid reset response");
      });
    },

    history: function () {
      return get(ENDPOINTS.history).then(normalizeHistory);
    },

    decide: function (conversationId, decision) {
      if (["block", "accept"].indexOf(decision) === -1) {
        return Promise.reject(invalid("Invalid decision"));
      }
      return post(ENDPOINTS.decide + encodeURIComponent(conversationId) + "/decision", {
        decision: decision
      }).then(function (raw) {
        if (!raw || !raw.conversation || typeof raw.conversation.id !== "string" ||
            raw.conversation.decision !== (decision === "block" ? "blocked" : "accepted")) {
          throw invalid("Invalid decision response");
        }
        return raw.conversation;
      });
    },

    receiveMessage: receiveMessage,
    startEvaluation: function (seed) {
      return post(ENDPOINTS.evaluationStart, seed === undefined ? {} : { seed: seed }).then(checkEvaluation);
    },
    nextEvaluation: function () { return post(ENDPOINTS.evaluationNext, {}).then(checkEvaluation); },
    analyzeArbitrary: function (text) {
      return post(ENDPOINTS.evaluationArbitrary, { message: text });
    }
  };
})();
