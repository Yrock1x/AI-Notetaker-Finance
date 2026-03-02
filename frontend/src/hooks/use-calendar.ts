import { useDeals } from "./use-deals";
import { useMeetings } from "./use-meetings";
import type { Meeting } from "@/types";

export interface CalendarMeeting extends Meeting {
  deal_name: string;
  deal_id: string;
}

export function useCalendarMeetings() {
  const { data: dealsData } = useDeals();
  const deals = dealsData?.items || [];

  // Fetch meetings for each deal
  // Use individual useMeetings hooks for first 3 deals
  const deal0 = deals[0]?.id;
  const deal1 = deals[1]?.id;
  const deal2 = deals[2]?.id;

  const { data: meetings0 } = useMeetings(deal0);
  const { data: meetings1 } = useMeetings(deal1);
  const { data: meetings2 } = useMeetings(deal2);

  const allMeetings: CalendarMeeting[] = [];

  if (meetings0?.items) {
    meetings0.items.forEach((m) =>
      allMeetings.push({
        ...m,
        deal_name: deals[0]?.name || "",
        deal_id: deals[0]?.id || "",
      })
    );
  }
  if (meetings1?.items) {
    meetings1.items.forEach((m) =>
      allMeetings.push({
        ...m,
        deal_name: deals[1]?.name || "",
        deal_id: deals[1]?.id || "",
      })
    );
  }
  if (meetings2?.items) {
    meetings2.items.forEach((m) =>
      allMeetings.push({
        ...m,
        deal_name: deals[2]?.name || "",
        deal_id: deals[2]?.id || "",
      })
    );
  }

  return { meetings: allMeetings, isLoading: !dealsData };
}
