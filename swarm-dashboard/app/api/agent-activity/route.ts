import { NextResponse } from "next/server";
import { buildActivityByAgent, ingestStatsFeedToHistory, readStatsPayload } from "@/lib/agent-activity";

export async function GET() {
  const stats = await readStatsPayload();
  const history = await ingestStatsFeedToHistory(stats);
  const activity = buildActivityByAgent(stats, history);

  return NextResponse.json({
    ok: true,
    activity,
    jobsHistoryCount: history.jobs.length,
  });
}
