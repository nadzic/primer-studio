"use client";

export function AppHeader() {
  return (
    <header className="relative z-10 flex items-center justify-between px-6 py-6 md:px-10">
      <div className="flex items-center gap-2 text-sm font-semibold tracking-[0.2em] text-zinc-300">
        <span className="text-base text-white">V</span>
        <span>VERITAKE</span>
      </div>
      <p className="text-xs text-zinc-500">Research mode</p>
    </header>
  );
}
