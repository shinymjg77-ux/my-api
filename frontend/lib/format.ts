const dateTimeFormatter = new Intl.DateTimeFormat("ko-KR", {
  dateStyle: "medium",
  timeStyle: "short",
});

const compactNumberFormatter = new Intl.NumberFormat("ko-KR");


export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return dateTimeFormatter.format(new Date(value));
}


export function formatCount(value: number) {
  return compactNumberFormatter.format(value);
}


export function formatLatency(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${compactNumberFormatter.format(value)} ms`;
}


export function formatStatusCode(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return compactNumberFormatter.format(value);
}
