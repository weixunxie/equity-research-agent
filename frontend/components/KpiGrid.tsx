import { fmtMoney, fmtMult, fmtPct, fmtSignedPct } from "@/lib/format";
import type { Financials } from "@/lib/types";

interface Tile {
  label: string;
  value: string;
  note?: string;
}

function tiles(f: Financials): Tile[] {
  const v = f.valuation ?? {};
  const p = f.profitability ?? {};
  const g = f.growth ?? {};
  const b = f.balance ?? {};
  return [
    {
      label: "Market cap",
      value: fmtMoney(v.market_cap, f.currency),
      note: `EV ${fmtMoney(v.enterprise_value, f.currency)}`,
    },
    {
      label: "P/E (trailing)",
      value: fmtMult(v.trailing_pe),
      note: `Forward ${fmtMult(v.forward_pe)}`,
    },
    {
      label: "EV / EBITDA",
      value: fmtMult(v.ev_to_ebitda),
      note: `P/S ${fmtMult(v.price_to_sales)}`,
    },
    {
      label: "Revenue growth",
      value: fmtSignedPct(g.revenue_yoy),
      note: `Earnings ${fmtSignedPct(g.earnings_yoy)} · YoY`,
    },
    {
      label: "Gross margin",
      value: fmtPct(p.gross_margin),
      note: `Net ${fmtPct(p.net_margin)}`,
    },
    {
      label: "Operating margin",
      value: fmtPct(p.operating_margin),
      note: `ROE ${fmtPct(p.return_on_equity)}`,
    },
    {
      label: "Free cash flow",
      value: fmtMoney(b.free_cash_flow, f.currency),
      note: "Trailing 12 months",
    },
    {
      label: "Debt / equity",
      value: fmtMult(b.debt_to_equity, 2),
      note: `Cash ${fmtMoney(b.total_cash, f.currency, 1)} · Debt ${fmtMoney(b.total_debt, f.currency, 1)}`,
    },
  ];
}

export default function KpiGrid({ financials }: { financials: Financials }) {
  return (
    <dl className="card grid grid-cols-2 gap-px overflow-hidden bg-grid lg:grid-cols-4">
      {tiles(financials).map((t) => (
        <div key={t.label} className="bg-surface px-5 py-4">
          <dt className="text-xs text-muted">{t.label}</dt>
          <dd className="mt-1 text-2xl font-semibold tracking-tight text-ink">{t.value}</dd>
          {t.note ? <dd className="num mt-0.5 text-xs text-ink2">{t.note}</dd> : null}
        </div>
      ))}
    </dl>
  );
}
