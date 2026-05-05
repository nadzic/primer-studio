"use client";

import { WorkspaceTab } from "@/components/home/workspace-types";

type TabsBarProps = {
  tabs: WorkspaceTab[];
  activeTabId: string;
  onSelect: (tabId: string) => void;
  onClose: (tabId: string) => void;
  onCreateNew?: () => void;
};

export function TabsBar({ tabs, activeTabId, onSelect, onClose, onCreateNew }: TabsBarProps) {
  return (
    <div className="hide-scrollbar mb-4 overflow-x-auto">
      <div className="flex min-w-max items-center gap-2">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          const isClosable = tab.kind === "report";
          return (
            <div
              key={tab.id}
              className={`group inline-flex h-8 items-center gap-2 rounded-full border px-3 text-sm transition ${
                isActive
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(tab.id)}
                className="inline-flex h-8 items-center gap-2"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    tab.kind === "launchpad"
                      ? isActive
                        ? "bg-emerald-300"
                        : "bg-emerald-400"
                      : isActive
                        ? "bg-zinc-200"
                        : "bg-zinc-300"
                  }`}
                />
                <span className="max-w-44 truncate">{tab.title}</span>
              </button>
              {isClosable && (
                <button
                  type="button"
                  onClick={() => onClose(tab.id)}
                  className={`inline-flex h-6 w-6 items-center justify-center rounded-full transition ${
                    isActive
                      ? "text-white/80 hover:bg-white/10 hover:text-white"
                      : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
                  }`}
                  aria-label={`Close ${tab.title}`}
                  title="Close tab"
                >
                  <svg
                    aria-hidden
                    viewBox="0 0 24 24"
                    className="h-4 w-4 fill-none stroke-current"
                    strokeWidth="2.2"
                  >
                    <path d="M6 6 18 18" />
                    <path d="M18 6 6 18" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
        <button
          type="button"
          onClick={onCreateNew}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-zinc-200 bg-white text-zinc-600 transition hover:border-zinc-300 hover:bg-zinc-50 hover:text-zinc-900"
          title="New research tab"
          aria-label="New research tab"
        >
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            className="h-4 w-4 fill-none stroke-current"
            strokeWidth="2.2"
          >
            <path d="M12 5v14" />
            <path d="M5 12h14" />
          </svg>
        </button>
      </div>
    </div>
  );
}

