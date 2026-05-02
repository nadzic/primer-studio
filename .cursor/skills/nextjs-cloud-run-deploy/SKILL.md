---
name: nextjs-cloud-run-deploy
description: Guides reliable Next.js Docker and Cloud Run deployments with Artifact Registry, build args, runtime env, and failure triage. Use when the user mentions Cloud Run, GitHub Actions deploy failures, docker push/build issues, or production rollout checks for the frontend.
---

# Next.js Cloud Run Deploy

## Scope

Use this skill when debugging or implementing frontend deploy flow:
- Docker build in CI,
- push to Artifact Registry,
- deploy to Cloud Run.

## Known project deployment shape

- Frontend image is built from `app/frontend/Dockerfile`.
- Build requires public env values:
  - `NEXT_PUBLIC_API_URL`
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Workflow file is `.github/workflows/ci.yml`.

## Deployment checklist

1. Verify GitHub variables exist and are non-empty:
   - `GCP_PROJECT_ID`, `GCP_REGION`, `GAR_REPOSITORY`
   - `CLOUD_RUN_FRONTEND_SERVICE`
   - all required `NEXT_PUBLIC_*` vars
2. Ensure Artifact Registry repo exists in the same region as image hostname.
3. Ensure CI service account has at least:
   - `roles/artifactregistry.writer`
   - `roles/run.admin`
   - `roles/iam.serviceAccountUser`
4. Confirm Docker auth target matches region host:
   - `${REGION}-docker.pkg.dev`
5. Confirm Docker build passes all required `--build-arg` values.

## Fast triage by error message

- `Repository ... not found`:
  - repo name mismatch or wrong region/project.
- `process.env.<NEXT_PUBLIC_...> is required` during `next build`:
  - missing build arg / missing GitHub variable.
- `Permission denied` on push:
  - missing Artifact Registry IAM role.
- Deploy step skipped after build failure:
  - always fix upstream build/push step first.

## Safe verification commands

```bash
gh variable list
gcloud artifacts repositories list --project "$PROJECT_ID" --format="table(name,format,location)"
```

For local frontend validation before triggering CI:

```bash
cd app/frontend
npm run build
```

## Post-deploy smoke checks

- Open frontend Cloud Run URL and verify initial page loads.
- Verify login path renders without runtime crash.
- Verify frontend can call API endpoint configured by `NEXT_PUBLIC_API_URL`.
