const required = (key: string, value: string | undefined): string => {
  if (!value) throw new Error(`Missing required env var: ${key}`);
  return value;
};

export const env = {
  SUPABASE_URL: required("VITE_SUPABASE_URL", import.meta.env.VITE_SUPABASE_URL),
  SUPABASE_ANON_KEY: required("VITE_SUPABASE_ANON_KEY", import.meta.env.VITE_SUPABASE_ANON_KEY),
  VAST_AI_URL: required("VITE_VAST_AI_URL", import.meta.env.VITE_VAST_AI_URL),
  STORAGE_BUCKET: required("VITE_STORAGE_BUCKET", import.meta.env.VITE_STORAGE_BUCKET),
} as const;
