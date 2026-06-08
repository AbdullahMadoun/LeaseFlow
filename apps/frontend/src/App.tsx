import { Routes, Route, Navigate } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { Slides } from "./pages/Slides";
import { MerchantOnboarding } from "./pages/merchant/Onboarding";
import { MerchantDashboard } from "./pages/merchant/Dashboard";
import { MerchantNewLoan } from "./pages/merchant/NewLoan";
import { MerchantLoanDetail } from "./pages/merchant/LoanDetail";
import { MerchantPayments } from "./pages/merchant/Payments";
import { MerchantProfile } from "./pages/merchant/Profile";
import { AdminPipeline } from "./pages/admin/Pipeline";
import { AdminLoanDetail } from "./pages/admin/LoanDetail";
import { AdminRisk } from "./pages/admin/Risk";
import { AdminSegments } from "./pages/admin/Segments";
import { RequireRole } from "./components/RequireRole";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/slides" element={<Slides />} />

      <Route
        path="/merchant/onboarding"
        element={
          <RequireRole role="merchant">
            <MerchantOnboarding />
          </RequireRole>
        }
      />
      <Route
        path="/merchant/dashboard"
        element={
          <RequireRole role="merchant">
            <MerchantDashboard />
          </RequireRole>
        }
      />
      <Route
        path="/merchant/new-loan"
        element={
          <RequireRole role="merchant">
            <MerchantNewLoan />
          </RequireRole>
        }
      />
      <Route
        path="/merchant/loans/:id"
        element={
          <RequireRole role="merchant">
            <MerchantLoanDetail />
          </RequireRole>
        }
      />
      <Route
        path="/merchant/payments"
        element={
          <RequireRole role="merchant">
            <MerchantPayments />
          </RequireRole>
        }
      />
      <Route
        path="/merchant/profile"
        element={
          <RequireRole role="merchant">
            <MerchantProfile />
          </RequireRole>
        }
      />

      <Route
        path="/admin"
        element={
          <RequireRole role="admin">
            <AdminPipeline />
          </RequireRole>
        }
      />
      <Route
        path="/admin/loans/:id"
        element={
          <RequireRole role="admin">
            <AdminLoanDetail />
          </RequireRole>
        }
      />
      <Route
        path="/admin/risk"
        element={
          <RequireRole role="admin">
            <AdminRisk />
          </RequireRole>
        }
      />
      <Route
        path="/admin/segments"
        element={
          <RequireRole role="admin">
            <AdminSegments />
          </RequireRole>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
