const s = StreamFlow.loadState();
const payResult = document.getElementById("payResult");

document.getElementById("pay").addEventListener("click", () => {
  if (s.approved <= 0) {
    payResult.classList.remove("hidden");
    payResult.innerHTML = "No approved offer found. Complete Risk & Offer page first.";
    return;
  }

  const supplier = document.getElementById("supplier").value.trim();
  const iban = document.getElementById("iban").value.trim();

  s.payoutDone = true;
  StreamFlow.pushTimeline(s, `Vendor payout executed to ${supplier} via Stream simulation.`);
  StreamFlow.saveState(s);

  payResult.classList.remove("hidden");
  payResult.innerHTML = `<b>Vendor Payment Completed</b><br>Supplier: ${supplier}<br>Financed Amount: ${StreamFlow.fmt(s.approved)} SAR<br>Merchant Top-up: ${StreamFlow.fmt(s.topup)} SAR<br>Destination IBAN: ${iban}`;
});
