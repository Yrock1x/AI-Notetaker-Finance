"use client";

import { useParams } from "next/navigation";
import { useDealMembers, useRemoveDealMember } from "@/hooks/use-deals";
import { LoadingState } from "@/components/shared/loading-state";
import { DEAL_ROLE_LABELS } from "@/lib/constants";
import { Users, UserMinus } from "lucide-react";

export default function TeamPage() {
  const params = useParams<{ dealId: string }>();
  const { data: members, isLoading } = useDealMembers(params.dealId);
  const removeMember = useRemoveDealMember();

  if (isLoading) {
    return <LoadingState message="Loading team..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Team Members</h2>
      </div>

      <div className="rounded-lg border bg-white">
        {!members || members.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <Users className="h-8 w-8 text-muted-foreground/30" />
            <p className="mt-2 text-sm text-muted-foreground">
              No team members found.
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="px-4 py-3 font-medium">Member</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Added</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr
                  key={member.id}
                  className="border-b last:border-0 hover:bg-muted/50"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                        {member.user?.full_name?.charAt(0)?.toUpperCase() ?? "?"}
                      </div>
                      <div>
                        <p className="text-sm font-medium">
                          {member.user?.full_name ?? "Unknown"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {member.user?.email ?? ""}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                      {DEAL_ROLE_LABELS[member.role] ?? member.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {new Date(member.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() =>
                        removeMember.mutate({
                          dealId: params.dealId,
                          userId: member.user_id,
                        })
                      }
                      className="text-muted-foreground hover:text-red-600"
                      title="Remove member"
                    >
                      <UserMinus className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
