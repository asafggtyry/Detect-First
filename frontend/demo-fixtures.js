// Sample scan responses used ONLY when the Python classifier is not reachable
// (mode "demo", or mode "auto" with no backend). They are hand-written stand-ins
// in the same shape the backend returns, and the UI labels them as sample
// results. They are not model predictions. Keyed by exact message text.
window.DETECT_FIRST_DEMO_FIXTURES = {
  "Hi, we met yesterday.": {
    is_scam: false,
    reasons: []
  },

  "Hello! We are hiring students for remote work. Deposit $60 in the next 24 hours to secure your position and start earning up to $300 per day. Reply now for onboarding details.": {
    is_scam: true,
    reasons: [
      { category: "unsolicited_job_offer", evidence: "“We are hiring students” — from a number you have never contacted" },
      { category: "unrealistic_earnings", evidence: "“earning up to $300 per day”" },
      { category: "vague_job_details", evidence: "Only “remote work” — no role, duties or hours" },
      { category: "urgency_pressure", evidence: "“in the next 24 hours”, “Reply now”" },
      { category: "unverified_employer", evidence: "No company or recruiter name given" }
    ]
  }
};
