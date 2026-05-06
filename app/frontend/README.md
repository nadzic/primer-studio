## Primer Studio frontend

Next.js chat UI that calls the FastAPI backend research workflow.

### Run locally

Install deps and start the dev server:

```bash
npm install
npm run dev
```

Create `./.env.local`:

- `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`)
- `ELEVENLABS_API_KEY` (optional; only if using voice transcription)

Open `http://localhost:3000`.
