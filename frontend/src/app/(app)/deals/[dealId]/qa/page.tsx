"use client";

import { useParams } from "next/navigation";
import { QAChat } from "@/components/qa/qa-chat";

export default function QAPage() {
  const params = useParams<{ dealId: string }>();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Deal Q&A</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Ask questions about this deal. Answers are grounded in meeting
          transcripts and uploaded documents with citations.
        </p>
      </div>
      <QAChat dealId={params.dealId} />
    </div>
  );
}
