// Detect First frontend configuration.
// This is the only file that needs editing to connect the UI to the Python backend.
window.DETECT_FIRST_CONFIG = {
  // Origin of the Python backend. "" means the same origin that serves this page.
  // Example for a separately running server: "http://localhost:5000"
  apiBase: "",

  // Endpoint that wraps the existing classifier. See README.md for the contract.
  scanEndpoint: "/api/scan",

  // Live API only. A failed scan shows a connection error, never a sample verdict.
  mode: "live",

  // How long to wait for the backend before giving up, in milliseconds.
  timeoutMs: 4000
};
