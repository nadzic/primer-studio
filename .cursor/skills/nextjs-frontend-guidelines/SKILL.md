---
name: nextjs-frontend-guidelines
description: Applies project-specific Next.js frontend best practices for App Router, client/server boundaries, environment variables, typing, and build safety. Use when implementing, refactoring, or reviewing code under app/frontend or when the user mentions Next.js pages, components, routing, or frontend build errors.
---

# Next.js Frontend Guidelines

## Scope

Use this skill for work in `app/frontend` (Next.js 16 + React 19 + TypeScript).

## First step before coding

This project explicitly requires checking current Next.js docs before substantial changes:
- Read relevant docs in `app/frontend/node_modules/next/dist/docs/`.
- Treat deprecation warnings as required follow-up tasks, not optional cleanup.

## Project defaults

- Prefer App Router patterns (`src/app/**`).
- Keep components server-first; add `"use client"` only when needed for hooks/events/browser APIs.
- Keep pages thin; move API calls and transforms into reusable utilities.
- Use strict TypeScript types and avoid implicit `any`.

## Client/server boundary rules

- Do not call browser-only SDKs in server code.
- Do not instantiate browser clients at module top-level if env can be missing during build.
- Initialize sensitive clients lazily in event handlers or guarded code paths.
- If env is required, fail with explicit, actionable errors.

## Environment variable rules

- Public browser variables must use `NEXT_PUBLIC_` prefix.
- Build-time variables used in Docker builds must be passed as `--build-arg`.
- Runtime-only secrets must not be exposed to client bundles.
- Keep fallback behavior deterministic (no silent empty strings).

## API/data access conventions

- Centralize frontend API access in library modules (for example under `src/lib`).
- Ensure request helpers return typed responses.
- Surface non-OK HTTP responses with useful error text.
- Keep auth/session token fetching isolated and reusable.

## Quality checks before finishing

Run these in `app/frontend`:

```bash
npm run lint
npm run typecheck
npm run build
npm run test
```

If only one check can be run quickly, prioritize `npm run build` because it catches route-level and env-related failures.

## Common anti-patterns to avoid

- Eager SDK initialization in component render path that can crash prerender/build.
- Moving secrets into `NEXT_PUBLIC_*` just to make builds pass.
- Mixing multiple package managers/lockfiles during dependency updates.
- Returning untyped `unknown` payloads from request helpers without narrowing.
