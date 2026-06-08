const s = StreamFlow.loadState();
const setupResult = document.getElementById("setupResult");
const ffResult = document.getElementById("ffResult");

function setupPlan() {
  if (!s.payoutDone) {
    setupResult.classList.remove("hidden");
    setupResult.innerHTML = "Complete vendor payout first.";
    return;
  }

  const mode = document.getElementById("mode").value;
  const tenor = Math.max(1, Number(document.getElementById("tenor").value));
  const capture = Number(document.getElementById("capture").value) / 100;

  s.repaymentMode = mode;
  s.tenor = tenor;
  s.dailyStream = 0;
  s.monthlyPlan = 0;

  const estimatedDailySales = 45000 / 30;

  if (mode === "sales") {
    s.dailyStream = Math.round(estimatedDailySales * capture);
  } else if (mode === "fixed") {
    s.monthlyPlan = Math.round(s.approved / tenor);
  } else {
    s.monthlyPlan = Math.round((s.approved * 0.55) / tenor);
    s.dailyStream = Math.round(estimatedDailySales * Math.min(capture, 0.1));
  }

  StreamFlow.pushTimeline(s, `Repayment configured: mode=${mode}, daily=${s.dailyStream}, monthly=${s.monthlyPlan}.`);
  StreamFlow.saveState(s);

  setupResult.classList.remove("hidden");
  setupResult.innerHTML = `<b>Repayment Stream Active</b><br>Mode: ${mode}<br>Daily: ${StreamFlow.fmt(s.dailyStream)} SAR<br>Monthly: ${StreamFlow.fmt(s.monthlyPlan)} SAR<br>Month-end shortfall rule: collect remaining due.`;
}

document.getElementById("setup").addEventListener("click", setupPlan);

document.getElementById("ff").addEventListener("click", () => {
  if (s.approved <= 0) return;

  const collected = (s.dailyStream * 30) + s.monthlyPlan;
  const before = s.outstanding;
  s.outstanding = Math.max(0, s.outstanding - collected);
  const delta = before - s.outstanding;
  s.repaid += delta;

  StreamFlow.pushTimeline(s, `Fast-forward 30 days: ${StreamFlow.fmt(delta)} SAR collected.`);
  StreamFlow.saveState(s);

  ffResult.classList.remove("hidden");
  ffResult.innerHTML = `<b>30-Day Simulation Done</b><br>Collected: ${StreamFlow.fmt(delta)} SAR<br>Remaining Outstanding: ${StreamFlow.fmt(s.outstanding)} SAR`;
});
