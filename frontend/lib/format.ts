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


export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`;
}


export function formatBytes(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value < 1024) {
    return `${compactNumberFormatter.format(value)} B`;
  }

  const units = ["KB", "MB", "GB", "TB"];
  let current = value / 1024;
  let index = 0;

  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }

  return `${current.toFixed(current >= 10 ? 0 : 1)} ${units[index]}`;
}


export function formatDuration(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "-";
  }

  const days = Math.floor(value / 86400);
  const hours = Math.floor((value % 86400) / 3600);
  const minutes = Math.floor((value % 3600) / 60);

  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}
