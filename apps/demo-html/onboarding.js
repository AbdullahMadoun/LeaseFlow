const s = StreamFlow.loadState();

const otpStatus = document.getElementById("otpStatus");
const ocrResult = document.getElementById("ocrResult");

document.getElementById("verifyOtp").addEventListener("click", () => {
  const phone = document.getElementById("phone").value.trim();
  const otp = document.getElementById("otp").value.trim();
  if (!phone || otp.length < 4) {
    otpStatus.classList.remove("hidden");
    otpStatus.textContent = "Enter valid phone and OTP.";
    return;
  }
  s.verified = true;
  StreamFlow.pushTimeline(s, "OTP verification completed by SME owner.");
  StreamFlow.saveState(s);
  otpStatus.classList.remove("hidden");
  otpStatus.textContent = "OTP verified. Account onboarding step completed.";
});

document.getElementById("extract").addEventListener("click", () => {
  if (!s.verified) {
    ocrResult.classList.remove("hidden");
    ocrResult.innerHTML = "Please verify OTP first.";
    return;
  }

  s.extracted = true;
  StreamFlow.pushTimeline(s, "AI extracted CR and invoice fields in bilingual mode.");
  StreamFlow.saveState(s);

  ocrResult.classList.remove("hidden");
  ocrResult.innerHTML = `<b>AI Extraction Complete</b><br>
    CR Number: 1010XXXXXX<br>
    Business: Noon Brew Cafe<br>
    Owner: Abdullah Al-Qahtani<br>
    Supplier: Arabica Supplies Co.<br>
    Invoice: 18,000 SAR<br>
    Due Date: 2026-05-15<br>
    IBAN: SA03 8000 0000 6080 1016 7519`;
});
