const s = StreamFlow.loadState();

const scoreResult = document.getElementById("scoreResult");
const offerResult = document.getElementById("offerResult");
const acceptStatus = document.getElementById("acceptStatus");

function approvalFactor(score) {
  if (score >= 80) return 1;
  if (score >= 70) return 0.85;
  if (score >= 60) return 0.7;
  if (score >= 50) return 0.55;
  if (score >= 40) return 0.4;
  return 0.25;
}

document.getElementById("score").addEventListener("click", () => {
  if (!s.extracted) {
    scoreResult.classList.remove("hidden");
    scoreResult.innerHTML = "Complete onboarding and AI extraction first.";
    return;
  }

  const avgSales = Number(document.getElementById("avgSales").value);
  const vol = Number(document.getElementById("volatility").value);
  const conn = document.getElementById("connectionType").value;

  s.riskScore = Math.min(90, Math.max(35, Math.round((avgSales / 1000) - vol * 0.5 + 45)));
  s.dailyCapacity = Math.round((avgSales / 30) * 0.22);

  StreamFlow.pushTimeline(s, `Financials connected via ${conn}; risk score computed: ${s.riskScore}.`);
  StreamFlow.saveState(s);

  scoreResult.classList.remove("hidden");
  scoreResult.innerHTML = `<b>Risk Engine Output</b><br>Score: ${s.riskScore}/100<br>Daily Repayment Capacity: ${StreamFlow.fmt(s.dailyCapacity)} SAR/day`;
});

document.getElementById("generate").addEventListener("click", () => {
  const requested = Number(document.getElementById("requested").value);
  const invoiceAmount = Number(document.getElementById("invoiceAmount").value);

  if (s.riskScore === 0 || requested <= 0 || invoiceAmount <= 0) {
    offerResult.classList.remove("hidden");
    offerResult.innerHTML = "Run risk scoring and enter valid values first.";
    return;
  }

  s.requested = requested;
  s.invoiceAmount = invoiceAmount;

  const byScore = requested * approvalFactor(s.riskScore);
  const byCapacity = s.dailyCapacity * 30;
  s.approved = Math.max(1000, Math.floor(Math.min(byScore, byCapacity, requested)));
  s.outstanding = s.approved;

  const gap = Math.max(0, invoiceAmount - s.approved);
  document.getElementById("topup").value = gap;

  StreamFlow.pushTimeline(s, `Instant offer generated: approved ${StreamFlow.fmt(s.approved)} SAR from requested ${StreamFlow.fmt(requested)} SAR.`);
  StreamFlow.saveState(s);

  offerResult.classList.remove("hidden");
  offerResult.innerHTML = `<b>Counter-Offer</b><br>Requested: ${StreamFlow.fmt(requested)} SAR<br>Approved: ${StreamFlow.fmt(s.approved)} SAR<br>Invoice Gap: ${StreamFlow.fmt(gap)} SAR`;
});

document.getElementById("accept").addEventListener("click", () => {
  if (s.approved <= 0) {
    acceptStatus.classList.remove("hidden");
    acceptStatus.textContent = "Generate offer first.";
    return;
  }
  s.topup = Math.max(0, Number(document.getElementById("topup").value));
  StreamFlow.pushTimeline(s, `Merchant accepted counter-offer with top-up ${StreamFlow.fmt(s.topup)} SAR.`);
  StreamFlow.saveState(s);
  acceptStatus.classList.remove("hidden");
  acceptStatus.textContent = `Accepted. Top-up confirmed: ${StreamFlow.fmt(s.topup)} SAR.`;
});
