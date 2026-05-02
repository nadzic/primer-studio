import crypto from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

type ElevenLabsTranscription = {
  text?: unknown;
  transcript?: unknown;
};

export const runtime = "nodejs";

const GUEST_COOKIE_NAME = "veritake_guest_id";
const GUEST_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
const DEFAULT_COOKIE_SECRET = "dev-change-me";
const DEFAULT_TRANSCRIBE_DAILY_LIMIT = 2;
const ELEVENLABS_TRANSCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text";
const ELEVENLABS_MODEL_ID = "scribe_v1";
const ELEVENLABS_LANGUAGE_CODE = "sl";

const fallbackDailyCounter = new Map<string, number>();

type RateLimitDecision = {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetAt: string | null;
};

function setGuestCookie(response: NextResponse, cookieValue: string): void {
  response.cookies.set({
    name: GUEST_COOKIE_NAME,
    value: cookieValue,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: GUEST_COOKIE_MAX_AGE_SECONDS,
    path: "/",
  });
}

function getEnv(...names: string[]): string {
  for (const name of names) {
    const value = process.env[name];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return "";
}

function getCookieSecret(): string {
  return getEnv("RATE_LIMIT_COOKIE_SECRET", "COOKIE_SIGNING_SECRET") || DEFAULT_COOKIE_SECRET;
}

function signGuestId(guestId: string): string {
  return crypto.createHmac("sha256", getCookieSecret()).update(guestId).digest("hex").slice(0, 24);
}

function verifySignedGuestId(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  const [guestId, providedSig] = value.split(".", 2);
  if (!guestId || !providedSig) {
    return null;
  }
  const expected = signGuestId(guestId);
  if (providedSig.length !== expected.length) {
    return null;
  }
  return crypto.timingSafeEqual(Buffer.from(providedSig), Buffer.from(expected)) ? guestId : null;
}

function dailyLimit(): number {
  const raw = process.env.RATE_LIMIT_ANON_DAILY ?? `${DEFAULT_TRANSCRIBE_DAILY_LIMIT}`;
  const parsed = Number.parseInt(raw, 10);
  return Number.isNaN(parsed) || parsed <= 0 ? DEFAULT_TRANSCRIBE_DAILY_LIMIT : parsed;
}

function getUtcWindowStart(): string {
  return new Date().toISOString().slice(0, 10);
}

function buildFallbackDecision(guestId: string, limit: number): RateLimitDecision {
  const counterKey = `${getUtcWindowStart()}:${guestId}`;
  const currentCount = fallbackDailyCounter.get(counterKey) ?? 0;
  const nextCount = currentCount + 1;
  fallbackDailyCounter.set(counterKey, nextCount);

  const allowed = nextCount <= limit;
  return {
    allowed,
    limit,
    remaining: Math.max(limit - nextCount, 0),
    resetAt: null,
  };
}

async function checkTranscribeRateLimit(request: NextRequest): Promise<{
  decision: RateLimitDecision;
  cookieValueToSet: string | null;
}> {
  const rawCookie = request.cookies.get(GUEST_COOKIE_NAME)?.value;
  const verifiedGuestId = verifySignedGuestId(rawCookie);

  const guestId = verifiedGuestId ?? crypto.randomUUID().replaceAll("-", "");
  const cookieValueToSet = verifiedGuestId ? null : `${guestId}.${signGuestId(guestId)}`;
  const decision = buildFallbackDecision(guestId, dailyLimit());

  return { decision, cookieValueToSet };
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      {
        error: "Missing ElevenLabs API key. Set ELEVENLABS_API_KEY in frontend environment.",
      },
      { status: 500 },
    );
  }

  const { decision, cookieValueToSet } = await checkTranscribeRateLimit(request);
  if (!decision.allowed) {
    const limited = NextResponse.json(
      {
        detail: {
          code: "rate_limit_exceeded",
          message: "You've reached free limit for voice transcription.",
          limit: decision.limit,
          remaining: decision.remaining,
          reset_at: decision.resetAt,
        },
      },
      { status: 429 },
    );
    if (cookieValueToSet) {
      setGuestCookie(limited, cookieValueToSet);
    }
    return limited;
  }

  const inputForm = await request.formData();
  const audio = inputForm.get("audio");
  if (!(audio instanceof File)) {
    return NextResponse.json({ error: "audio file is required" }, { status: 400 });
  }

  const elevenForm = new FormData();
  elevenForm.append("file", audio, audio.name || "dictation.webm");
  elevenForm.append("model_id", ELEVENLABS_MODEL_ID);
  elevenForm.append("language_code", ELEVENLABS_LANGUAGE_CODE);

  const elevenResponse = await fetch(ELEVENLABS_TRANSCRIBE_URL, {
    method: "POST",
    headers: {
      "xi-api-key": apiKey,
    },
    body: elevenForm,
  });

  if (!elevenResponse.ok) {
    const errorText = await elevenResponse.text();
    return NextResponse.json(
      { error: `ElevenLabs transcription failed: ${errorText}` },
      { status: elevenResponse.status },
    );
  }

  const data = (await elevenResponse.json()) as ElevenLabsTranscription;
  const text =
    typeof data.text === "string"
      ? data.text
      : typeof data.transcript === "string"
        ? data.transcript
        : "";

  const success = NextResponse.json({ text: text.trim() });
  if (cookieValueToSet) {
    setGuestCookie(success, cookieValueToSet);
  }
  return success;
}
