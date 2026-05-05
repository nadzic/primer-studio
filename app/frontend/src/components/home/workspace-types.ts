import { ResearchResponse } from "@/components/home/types";

export type FollowupMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
};

export type WorkspaceTab =
  | {
      id: string;
      kind: "launchpad";
      title: "Launchpad";
    }
  | {
      id: string;
      kind: "report";
      title: string;
      runId: string;
    };

export type ResearchRunStatus = "running" | "completed" | "failed";

export type ResearchRun = {
  id: string;
  query: string;
  createdAt: number;
  finishedAt?: number;
  status: ResearchRunStatus;
  response?: ResearchResponse;
  formattedReport?: string;
  errorMessage?: string;
  followup: FollowupMessage[];
};

