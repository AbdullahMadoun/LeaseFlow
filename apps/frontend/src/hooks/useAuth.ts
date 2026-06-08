import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase, type Profile, type UserRole } from "../lib/supabase";

type AuthState = {
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
};

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({
    session: null,
    profile: null,
    loading: true,
  });

  useEffect(() => {
    let cancelled = false;

    const loadProfile = async (session: Session | null) => {
      if (!session) {
        if (!cancelled) setState({ session: null, profile: null, loading: false });
        return;
      }
      // Hold loading=true while we fetch the profile. Without this there is a
      // brief window on login/signup where {session: new, profile: null,
      // loading: false} leaks to the consumer and RequireRole flashes
      // "Profile not found" before the profile row is readable.
      if (!cancelled) setState((s) => ({ ...s, session, loading: true }));

      // The `handle_new_user` trigger fires synchronously, but in rare cases
      // (replication lag on fresh signup) the row isn't visible to the client
      // on first try. Retry a couple of times with backoff before giving up.
      const fetchProfile = async () =>
        await supabase
          .from("profiles")
          .select("id, role, display_name, created_at")
          .eq("id", session.user.id)
          .maybeSingle();
      let { data } = await fetchProfile();
      for (let i = 0; !data && i < 2; i++) {
        await new Promise((r) => setTimeout(r, 600 * (i + 1)));
        if (cancelled) return;
        ({ data } = await fetchProfile());
      }
      if (!cancelled) {
        setState({
          session,
          profile: (data as Profile | null) ?? null,
          loading: false,
        });
      }
    };

    supabase.auth.getSession().then(({ data }) => loadProfile(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      loadProfile(session);
    });

    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, []);

  return state;
}

export function homePathFor(role: UserRole | null | undefined): string {
  if (role === "admin") return "/admin";
  if (role === "merchant") return "/merchant/dashboard";
  return "/";
}
