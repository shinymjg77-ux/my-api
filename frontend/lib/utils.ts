export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}


export async function readErrorMessage(response: Response) {
  try {
    const data = await response.json();
    if (typeof data === "object" && data !== null) {
      if ("detail" in data && typeof data.detail === "string") {
        return data.detail;
      }
      if ("detail" in data && Array.isArray(data.detail)) {
        const messages = data.detail
          .map((item: unknown) => {
            if (typeof item !== "object" || item === null) {
              return null;
            }
            if ("msg" in item && typeof item.msg === "string") {
              return item.msg;
            }
            return null;
          })
          .filter((value: string | null): value is string => Boolean(value));

        if (messages.length > 0) {
          return messages.join(", ");
        }
      }
      if ("message" in data && typeof data.message === "string") {
        return data.message;
      }
    }
  } catch {}

  try {
    const text = await response.text();
    if (text) {
      return text;
    }
  } catch {}

  return `Request failed with status ${response.status}`;
}


export function toQueryString(params: Record<string, string | number | boolean | null | undefined>) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }
  return searchParams.toString();
}
