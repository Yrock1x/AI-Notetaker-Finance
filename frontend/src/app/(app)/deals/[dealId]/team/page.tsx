"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  useAddDealMember,
  useDealMembers,
  useRemoveDealMember,
} from "@/hooks/use-deals";
import { LoadingState } from "@/components/shared/loading-state";
import { DEAL_ROLE_LABELS } from "@/lib/constants";
import { DealRole } from "@/types";
import { Users, UserMinus, UserPlus } from "lucide-react";

const ROLE_OPTIONS: DealRole[] = [
  DealRole.VIEWER,
  DealRole.ANALYST,
  DealRole.ADMIN,
  DealRole.LEAD,
];

export default function TeamPage() {
  const params = useParams<{ dealId: string }>();
  const { data: members, isLoading } = useDealMembers(params.dealId);
  const removeMember = useRemoveDealMember();
  const addMember = useAddDealMember();

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<DealRole>(DealRole.ANALYST);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);
    try {
      await addMember.mutateAsync({
        dealId: params.dealId,
        payload: { email: inviteEmail.trim(), role: inviteRole },
      });
      setInviteEmail("");
      setInviteRole(DealRole.ANALYST);
      setInviteOpen(false);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Unable to send invite. Check the email and try again.";
      setInviteError(detail);
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading team..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Team Members</h2>
        <button
          type="button"
          onClick={() => setInviteOpen((o) => !o)}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <UserPlus className="h-4 w-4" />
          Invite member
        </button>
      </div>

      {inviteOpen && (
        <form
          onSubmit={handleInvite}
          className="rounded-lg border bg-white p-4 space-y-3"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_140px_auto]">
            <input
              type="email"
              required
              placeholder="colleague@yourfirm.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="rounded-md border border-[#1A1A1A]/15 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as DealRole)}
              className="rounded-md border border-[#1A1A1A]/15 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {DEAL_ROLE_LABELS[r] ?? r}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={addMember.isPending || !inviteEmail.trim()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {addMember.isPending ? "Sending…" : "Send invite"}
            </button>
          </div>
          {inviteError && (
            <p className="text-sm text-red-600">{inviteError}</p>
          )}
          <p className="text-xs text-muted-foreground">
            If they don&apos;t have an account yet, we&apos;ll create a
            placeholder and link it to their Cognito sign-in on first login.
          </p>
        </form>
      )}

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
                      onClick={() => {
                        if (!confirm("Are you sure you want to remove this team member?")) {
                          return;
                        }
                        removeMember.mutate({
                          dealId: params.dealId,
                          userId: member.user_id,
                        });
                      }}
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
