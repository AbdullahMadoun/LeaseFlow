import { Navigate, Route, Routes } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import UserDashboardPage from "./pages/UserDashboardPage";
import BusinessProfilePage from "./pages/BusinessProfilePage";
import NewRequestPage from "./pages/NewRequestPage";
import RequestReviewPage from "./pages/RequestReviewPage";
import RequestHistoryPage from "./pages/RequestHistoryPage";
import RequestDetailPage from "./pages/RequestDetailPage";
import PaymentPlanPage from "./pages/PaymentPlanPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminRequestsPage from "./pages/AdminRequestsPage";
import AdminReviewPage from "./pages/AdminReviewPage";
import NotFoundPage from "./pages/NotFoundPage";
import { useAuth } from "./context/AuthContext";

function ProtectedRoute({ children, allow }) {
  const { isAuthenticated, currentUser } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (allow && !allow.includes(currentUser.role)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route path="/dashboard" element={<ProtectedRoute allow={["customer"]}><UserDashboardPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute allow={["customer"]}><BusinessProfilePage /></ProtectedRoute>} />
      <Route path="/request/new" element={<ProtectedRoute allow={["customer"]}><NewRequestPage /></ProtectedRoute>} />
      <Route path="/request/invoice" element={<Navigate to="/request/new" replace />} />
      <Route path="/request/plan" element={<Navigate to="/request/new" replace />} />
      <Route path="/request/review" element={<ProtectedRoute allow={["customer"]}><RequestReviewPage /></ProtectedRoute>} />
      <Route path="/requests" element={<ProtectedRoute allow={["customer"]}><RequestHistoryPage /></ProtectedRoute>} />
      <Route path="/requests/:id" element={<ProtectedRoute allow={["customer"]}><RequestDetailPage /></ProtectedRoute>} />
      <Route path="/payment-plan/:id" element={<ProtectedRoute allow={["customer"]}><PaymentPlanPage /></ProtectedRoute>} />

      <Route path="/admin/dashboard" element={<ProtectedRoute allow={["admin"]}><AdminDashboardPage /></ProtectedRoute>} />
      <Route path="/admin/requests" element={<ProtectedRoute allow={["admin"]}><AdminRequestsPage /></ProtectedRoute>} />
      <Route path="/admin/review/:id" element={<ProtectedRoute allow={["admin"]}><AdminReviewPage /></ProtectedRoute>} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
