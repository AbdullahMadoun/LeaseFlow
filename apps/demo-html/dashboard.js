const s = StreamFlow.loadState();

function set(id, v) {
  document.getElementById(id).textContent = StreamFlow.fmt(v);
}

set("kApproved", s.approved);
set("kOutstanding", s.outstanding);
set("kDaily", s.dailyStream);
set("kMonthly", s.monthlyPlan);
set("kPool", s.investorPool);

const progress = s.approved > 0 ? Math.min(100, (s.repaid / s.approved) * 100) : 0;
document.getElementById("progressText").textContent = `Repayment Progress: ${progress.toFixed(1)}%`;
document.getElementById("bar").style.width = `${progress}%`;

const ul = document.getElementById("timeline");
if (s.timeline.length === 0) {
  const li = document.createElement("li");
  li.textContent = "No events yet. Start from Onboarding page.";
  ul.appendChild(li);
} else {
  s.timeline.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
}
