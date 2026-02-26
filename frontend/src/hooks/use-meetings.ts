import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  Meeting,
  MeetingUploadInitiate,
  MeetingUploadConfirm,
  MeetingUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";

const MEETINGS_KEY = "meetings";

export function useMeetings(dealId: string | undefined) {
  return useQuery({
    queryKey: [MEETINGS_KEY, dealId],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Meeting>>(
        `/deals/${dealId}/meetings`
      );
      return data;
    },
    enabled: !!dealId,
  });
}

export function useMeeting(
  dealId: string | undefined,
  meetingId: string | undefined
) {
  return useQuery({
    queryKey: [MEETINGS_KEY, dealId, meetingId],
    queryFn: async () => {
      const { data } = await apiClient.get<Meeting>(
        `/deals/${dealId}/meetings/${meetingId}`
      );
      return data;
    },
    enabled: !!dealId && !!meetingId,
  });
}

export function useInitiateMeetingUpload() {
  return useMutation({
    mutationFn: async (payload: MeetingUploadInitiate) => {
      const { data } = await apiClient.post<MeetingUploadInitiateResponse>(
        `/deals/${payload.deal_id}/meetings/upload/initiate`,
        payload
      );
      return data;
    },
  });
}

export function useConfirmMeetingUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MeetingUploadConfirm) => {
      const { data } = await apiClient.post<Meeting>(
        `/meetings/${payload.meeting_id}/upload/confirm`,
        payload
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY] });
    },
  });
}
