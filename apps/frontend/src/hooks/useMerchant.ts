import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "./useAuth";

export type Merchant = {
  id: string;
  user_id: string;
  business_name: string;
  cr_number: string | null;
  google_maps_url: string | null;
  phone: string | null;
  created_at: string;
};

export function useMerchant(): { merchant: Merchant | null; loading: boolean; reload: () => void } {
  const { session } = useAuth();
  const [merchant, setMerchant] = useState<Merchant | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!session) {
      setMerchant(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      const { data } = await supabase
        .from("merchants")
        .select("*")
        .eq("user_id", session.user.id)
        .maybeSingle();
      if (!cancelled) {
        setMerchant((data as Merchant | null) ?? null);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session, tick]);

  return { merchant, loading, reload: () => setTick((t) => t + 1) };
}
