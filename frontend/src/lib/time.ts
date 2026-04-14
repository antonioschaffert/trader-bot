/**
 * Format an ISO timestamp string to Eastern Time.
 */
const ET_OPTIONS: Intl.DateTimeFormatOptions = {
  timeZone: "America/New_York",
};

const etTimeFormatter = new Intl.DateTimeFormat("en-US", {
  ...ET_OPTIONS,
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
});

const etDateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  ...ET_OPTIONS,
  month: "numeric",
  day: "numeric",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
});

export function formatTimeET(iso: string | null | undefined): string {
  if (!iso) return "--:--:--";
  return etTimeFormatter.format(new Date(iso)) + " ET";
}

export function formatDateTimeET(iso: string | null | undefined): string {
  if (!iso) return "";
  return etDateTimeFormatter.format(new Date(iso)) + " ET";
}
