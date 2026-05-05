"use client";

export function AppHeader() {
  return (
    <header className="fixed inset-x-0 top-0 z-40 border-b border-zinc-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6 md:px-8">
        <div className="flex items-center gap-2 text-sm font-semibold tracking-[0.18em] text-zinc-900">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-200 text-xs font-bold text-emerald-900">
            P
          </span>
          <span>PRIMER STUDIO</span>
        </div>
        <p className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs text-zinc-600">
          Agentic research prototype
        </p>
      </div>
    </header>
  );
}
