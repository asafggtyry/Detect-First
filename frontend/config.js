// Detect First frontend configuration.
// This is the only file that needs editing to connect the UI to the Python backend.
window.DETECT_FIRST_CONFIG = {
  // Origin of the Python backend. "" means the same origin that serves this page.
  // Example for a separately running server: "http://localhost:5000"
  apiBase: "",

  // Endpoint that wraps the existing classifier. See README.md for the contract.
  scanEndpoint: "/api/scan",

  // "auto": call the backend; if it is unreachable, show labelled sample results.
  // "live": call the backend only; failures show a "couldn't scan" state.
  // "demo": never call the backend; always show labelled sample results.
  mode: "auto",

  // How long to wait for the backend before giving up, in milliseconds.
  timeoutMs: 4000
};
