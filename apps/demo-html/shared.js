const KEY = "streamflow_demo_state_v1";

const defaults = {
  verified: false,
  extracted: false,
  riskScore: 0,
  dailyCapacity: 0,
  requested: 20000,
  invoiceAmount: 18000,
  approved: 0,
  topup: 0,
  payoutDone: false,
  repaymentMode: "sales",
  dailyStream: 0,
  monthlyPlan: 0,
  tenor: 3,
  outstanding: 0,
  repaid: 0,
  investorPool: 0,
  timeline: []
};

function loadState() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...defaults };
    return { ...defaults, ...JSON.parse(raw) };
  } catch {
    return { ...defaults };
  }
}

function saveState(state) {
  localStorage.setItem(KEY, JSON.stringify(state));
}

function fmt(n) {
  return Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function pushTimeline(state, text) {
  const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  state.timeline.unshift(`[${now}] ${text}`);
  state.timeline = state.timeline.slice(0, 30);
}

function resetState() {
  localStorage.removeItem(KEY);
  return { ...defaults };
}

window.StreamFlow = { loadState, saveState, fmt, pushTimeline, resetState, defaults };
