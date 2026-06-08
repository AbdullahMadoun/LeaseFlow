import type { ReactNode } from "react";

type Props = {
  terminal: string;
  label: string;
  children: ReactNode;
};

export function AuthShell({ terminal, label, children }: Props) {
  return (
    <div className="bg-[#FBFBF9] text-on-surface min-h-screen flex items-center justify-center p-6">
      <main className="w-full max-w-md">
        <div className="w-full bg-secondary border-x-[3px] border-t-[3px] border-black flex items-center justify-between px-4 py-2">
          <div className="flex gap-2">
            <div className="w-2.5 h-2.5 bg-black" />
            <div className="w-2.5 h-2.5 bg-black" />
            <div className="w-2.5 h-2.5 bg-black" />
          </div>
          <span className="font-mono text-xs text-white tracking-widest uppercase">{terminal}</span>
          <div className="w-10" />
        </div>
        <div className="bg-surface border-[3px] border-black offset-shadow relative">
          <div className="p-8 relative z-10">
            <div className="flex items-center gap-4 mb-10">
              <h1 className="font-mono text-sm font-bold text-black whitespace-nowrap uppercase">{label}</h1>
              <div className="h-[3px] w-full bg-black" />
            </div>
            {children}
          </div>
        </div>
        <div className="mt-6 flex justify-between items-start opacity-60">
          <div className="font-mono text-[10px] space-y-1">
            <p>SYS_STATUS: READY</p>
            <p>ENCRYPTION: AES-256</p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[10px] font-bold">V 0.1</p>
            <div className="flex gap-1 justify-end mt-1">
              <div className="w-3 h-1 bg-black" />
              <div className="w-6 h-1 bg-primary-container" />
            </div>
          </div>
        </div>
      </main>

      <div className="fixed top-12 left-12 -z-10 opacity-10 hidden lg:block">
        <h2 className="text-[120px] font-black leading-none tracking-tighter uppercase text-black">
          LEASE<br />FLOW
        </h2>
      </div>
    </div>
  );
}
