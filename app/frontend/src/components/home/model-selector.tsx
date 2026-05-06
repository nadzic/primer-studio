"use client";

import { ChangeEvent } from "react";

import { MODEL_OPTIONS } from "@/components/home/model-options";

type ModelSelectorProps = {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  className?: string;
};

export function ModelSelector({
  value,
  onChange,
  disabled = false,
  className,
}: ModelSelectorProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    onChange(event.target.value);
  }

  return (
    <label className={className}>
      <span className="sr-only">Model</span>
      <span className="relative block w-full max-w-[220px]">
        <select
          value={value}
          onChange={handleChange}
          disabled={disabled}
          className="h-9 w-full appearance-none rounded-full border border-zinc-200 bg-white py-0 pl-3 pr-9 text-xs font-medium text-zinc-700 shadow-sm outline-none transition hover:border-zinc-300 focus:border-zinc-400 disabled:cursor-not-allowed disabled:opacity-60"
          aria-label="Select model"
        >
          {MODEL_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-zinc-500">
          <svg
            aria-hidden
            viewBox="0 0 20 20"
            className="h-4 w-4 fill-none stroke-current"
            strokeWidth="2"
          >
            <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </span>
    </label>
  );
}
