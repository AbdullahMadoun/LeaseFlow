import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { MerchantShell } from "../../components/MerchantShell";
import { supabase } from "../../lib/supabase";
import { useAuth } from "../../hooks/useAuth";
import { useMerchant } from "../../hooks/useMerchant";

export function MerchantProfile() {
  const { session, profile } = useAuth();
  const { merchant, reload } = useMerchant();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [crNumber, setCrNumber] = useState("");
  const [phone, setPhone] = useState("");
  const [googleMaps, setGoogleMaps] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDisplayName(profile?.display_name ?? "");
  }, [profile]);

  useEffect(() => {
    if (!merchant) return;
    setBusinessName(merchant.business_name ?? "");
    setCrNumber(merchant.cr_number ?? "");
    setPhone(merchant.phone ?? "");
    setGoogleMaps(merchant.google_maps_url ?? "");
  }, [merchant]);

  const handleSave = async () => {
    if (!session) return;
    const nextBusiness = businessName.trim() || merchant?.business_name || "";
    const nextCr = crNumber.trim() || merchant?.cr_number || "";
    if (!nextBusiness || !nextCr) {
      toast.error("Business name and CR number are required.");
      return;
    }
    setSaving(true);
    try {
      await supabase
        .from("profiles")
        .update({ display_name: displayName || null })
        .eq("id", session.user.id);

      const payload = {
        business_name: nextBusiness,
        cr_number: nextCr,
        phone: phone || null,
        google_maps_url: googleMaps || null,
      };

      if (merchant) {
        const { error } = await supabase.from("merchants").update(payload).eq("id", merchant.id);
        if (error) throw error;
      } else {
        const { error } = await supabase
          .from("merchants")
          .insert({ ...payload, user_id: session.user.id });
        if (error) throw error;
      }
      reload();
      toast.success("Profile saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/", { replace: true });
  };

  return (
    <MerchantShell activeTab="profile">
      <div className="mb-10">
        <div className="font-mono text-xs font-bold uppercase tracking-widest text-on-surface-variant flex items-center gap-3">
          <span className="w-8 h-[3px] bg-black" />
          Profile
        </div>
        <h1 className="mt-4 text-5xl font-black tracking-tighter uppercase">Your details</h1>
      </div>

      {merchant?.cr_number === "PENDING" && (
        <div className="mb-6 bg-primary-container border-[3px] border-black offset-shadow p-4">
          <div className="font-mono text-xs font-black uppercase tracking-widest mb-1">
            ⚠ Finish your business profile
          </div>
          <div className="text-sm text-on-surface-variant">
            We&apos;re using a default CR number so you could apply quickly. Replace it with your
            real Commercial Registration to improve underwriting accuracy.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-6">
          <Panel label="Operator">
            <Field label="Display name">
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full border-[3px] border-black bg-white p-3 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                value={session?.user.email ?? ""}
                disabled
                className="w-full border-[3px] border-black bg-surface-container-low p-3 font-mono text-sm opacity-60"
              />
            </Field>
          </Panel>

          <Panel label="Business">
            <Field label="Business name">
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                className="w-full border-[3px] border-black bg-white p-3 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
              />
            </Field>
            <Field label="CR number">
              <input
                type="text"
                value={crNumber}
                onChange={(e) => setCrNumber(e.target.value)}
                placeholder="1010XXXXXX"
                className="w-full border-[3px] border-black bg-white p-3 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
              />
            </Field>
            <Field label="Phone">
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+966 50 000 0000"
                className="w-full border-[3px] border-black bg-white p-3 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
              />
            </Field>
            <Field label="Google Maps URL">
              <input
                type="url"
                value={googleMaps}
                onChange={(e) => setGoogleMaps(e.target.value)}
                placeholder="https://maps.app.goo.gl/…"
                className="w-full border-[3px] border-black bg-white p-3 font-mono text-sm focus:outline-none focus:bg-surface-container-low"
              />
            </Field>
          </Panel>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-primary-container border-[3px] border-black px-8 py-3 font-mono font-black uppercase text-sm offset-shadow hover-lift disabled:opacity-40"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>

        <div className="lg:col-span-4">
          <div className="bg-white border-[3px] border-black offset-shadow p-6">
            <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-4">
              Session
            </div>
            <div className="text-sm text-on-surface-variant mb-6">
              Signed in as <span className="font-mono text-on-surface">{session?.user.email}</span>
            </div>
            <button
              onClick={handleLogout}
              className="w-full bg-error text-white border-[3px] border-black px-4 py-3 font-mono font-black uppercase text-xs offset-shadow hover-lift"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
    </MerchantShell>
  );
}

function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border-[3px] border-black offset-shadow p-6">
      <div className="font-mono text-[10px] font-bold uppercase tracking-widest mb-4">{label}</div>
      <div className="space-y-5">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block font-mono text-[10px] font-bold uppercase tracking-widest mb-2">
        {label}
      </label>
      {children}
    </div>
  );
}
