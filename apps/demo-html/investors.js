const s = StreamFlow.loadState();
const result = document.getElementById("result");

document.getElementById("add").addEventListener("click", () => {
  const amount = Number(document.getElementById("amount").value);
  const rate = Number(document.getElementById("rate").value);

  if (amount <= 0) {
    result.classList.remove("hidden");
    result.textContent = "Enter valid deposit amount.";
    return;
  }

  s.investorPool += amount;
  const projected = amount * (rate / 100);

  StreamFlow.pushTimeline(s, `Investor fund added: ${StreamFlow.fmt(amount)} SAR.`);
  StreamFlow.saveState(s);

  result.classList.remove("hidden");
  result.innerHTML = `<b>Investor Capital Added</b><br>Deposit: ${StreamFlow.fmt(amount)} SAR<br>Simulated annual return: ${rate}% (${StreamFlow.fmt(projected)} SAR)<br>Fund Pool: ${StreamFlow.fmt(s.investorPool)} SAR`;
});
