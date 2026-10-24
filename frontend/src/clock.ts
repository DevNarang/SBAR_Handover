export const IST_TZ = "Asia/Kolkata";

const IST_CLOCK: Intl.DateTimeFormatOptions = {
  timeZone: IST_TZ,
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
};

export function formatIst(value: string | Date | null | undefined): string {
  if (!value) return "—";
  let d: Date;
  if (value instanceof Date) {
    d = value;
  } else if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(value.trim())) {
    d = new Date(value.replace(" ", "T") + "+05:30");
  } else {
    d = new Date(value);
  }
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", IST_CLOCK);
}

export function nowIstIso(): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: IST_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const g = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${g("year")}-${g("month")}-${g("day")}T${g("hour")}:${g("minute")}:${g("second")}`;
}
