import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, homePathFor } from "../hooks/useAuth";
import type { UserRole } from "../lib/supabase";

type Props = {
  role: UserRole;
  children: ReactNode;
};

export function RequireRole({ role, children }: Props) {
  const { session, profile, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="font-mono text-xs uppercase tracking-widest text-on-surface-variant">
          Loading&hellip;
        </div>
      </div>
    );
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!profile) {
    // Authenticated but profile row missing — surface a quiet retry path.
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="font-mono text-xs uppercase tracking-widest text-error">
          Profile not found. Contact support.
        </div>
      </div>
    );
  }

  if (profile.role !== role) {
    return <Navigate to={homePathFor(profile.role)} replace />;
  }

  return <>{children}</>;
}
