// Number and date formatting shared by tiles, charts and tables.

const DASH = "—";

function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function currencySymbol(currency?: string | null): string {
  if (!currency) return "";
  try {
    const part = new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      currencyDisplay: "narrowSymbol",
    })
      .formatToParts(0)
      .find((p) => p.type === "currency");
    return part?.value ?? `${currency} `;
  } catch {
    return `${currency} `;
  }
}

/** Compact money: 5.56e12 -> "$5.56T", -1.2e9 -> "-$1.20B". */
export function fmtMoney(v: unknown, currency?: string | null, digits = 2): string {
  if (!isNum(v)) return DASH;
  const sym = currencySymbol(currency);
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  for (const [limit, suffix] of [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ] as const) {
    if (abs >= limit) return `${sign}${sym}${(abs / limit).toFixed(digits)}${suffix}`;
  }
  return `${sign}${sym}${abs.toFixed(digits)}`;
}

/** A share price: always two decimals, thousands-separated. */
export function fmtPrice(v: unknown, currency?: string | null): string {
  if (!isNum(v)) return DASH;
  return `${currencySymbol(currency)}${v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** A fraction as a percentage: 0.254 -> "25.4%". */
export function fmtPct(v: unknown, digits = 1): string {
  if (!isNum(v)) return DASH;
  return `${(v * 100).toFixed(digits)}%`;
}

/** A signed percentage from a fraction: 0.254 -> "+25.4%". */
export function fmtSignedPct(v: unknown, digits = 1): string {
  if (!isNum(v)) return DASH;
  return `${v > 0 ? "+" : ""}${(v * 100).toFixed(digits)}%`;
}

export function fmtMult(v: unknown, digits = 1): string {
  if (!isNum(v)) return DASH;
  return `${v.toFixed(digits)}x`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Parse "YYYY-MM-DD" without timezone drift. */
function parts(iso: string): [number, number, number] | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

/** "2026-07-31" -> "Jul 31, 2026". */
export function fmtDate(iso?: string | null): string {
  const p = iso ? parts(iso) : null;
  return p ? `${MONTHS[p[1] - 1]} ${p[2]}, ${p[0]}` : (iso ?? DASH);
}

/** How long ago an ISO timestamp was: "just now", "12 min ago", "3 h ago". */
export function fmtAgo(iso: string, now = Date.now()): string {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(minutes)) return "";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`;
}

/** "2026-07-31" -> "Jul ’26" (period-end label for a quarter). */
export function fmtMonthYear(iso: string): string {
  const p = parts(iso);
  return p ? `${MONTHS[p[1] - 1]} ’${String(p[0]).slice(2)}` : iso;
}

export function monthOf(iso: string): string {
  const p = parts(iso);
  return p ? MONTHS[p[1] - 1] : "";
}

export function yearOf(iso: string): string {
  return parts(iso)?.[0].toString() ?? iso;
}

/** Round axis ticks covering [min, max], about `count` of them. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (!(max > min)) return [min];
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let t = Math.ceil(min / step) * step; t <= max + step * 1e-9; t += step) {
    ticks.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  }
  return ticks;
}
