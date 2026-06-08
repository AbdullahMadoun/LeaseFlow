const s = StreamFlow.loadState();

document.getElementById("kApproved").textContent = StreamFlow.fmt(s.approved);
document.getElementById("kOutstanding").textContent = StreamFlow.fmt(s.outstanding);
document.getElementById("kDaily").textContent = StreamFlow.fmt(s.dailyStream);
document.getElementById("kMonthly").textContent = StreamFlow.fmt(s.monthlyPlan);
document.getElementById("kPool").textContent = StreamFlow.fmt(s.investorPool);

document.getElementById("resetDemo").addEventListener("click", () => {
  const fresh = StreamFlow.resetState();
  StreamFlow.saveState(fresh);
  location.reload();
});
