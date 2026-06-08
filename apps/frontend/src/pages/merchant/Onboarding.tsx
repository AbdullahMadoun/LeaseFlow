import { Navigate } from "react-router-dom";

/**
 * Onboarding is deprecated — new signups drop straight into /merchant/dashboard.
 * First-time merchant-profile creation is now inlined on the wizard's first use
 * (see NewLoan.tsx), and users can polish business details anytime in Profile.
 *
 * Kept as a redirect so inbound links / Supabase Auth email-confirm URLs that
 * point here don't 404.
 */
export function MerchantOnboarding() {
  return <Navigate to="/merchant/dashboard" replace />;
}
