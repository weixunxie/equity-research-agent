import { fmtMoney, fmtMult, fmtPct, fmtSignedPct } from "@/lib/format";
import type { Financials, Peer } from "@/lib/types";

const COLUMNS: { key: keyof Peer; label: string; fmt: (v: number | null) => string }[] = [
  { key: "market_cap", label: "Market cap", fmt: (v) => fmtMoney(v, null, 2) },
  { key: "trailing_pe", label: "P/E", fmt: (v) => fmtMult(v) },
  { key: "forward_pe", label: "Fwd P/E", fmt: (v) => fmtMult(v) },
  { key: "ev_to_ebitda", label: "EV/EBITDA", fmt: (v) => fmtMult(v) },
  { key: "price_to_sales", label: "P/S", fmt: (v) => fmtMult(v) },
  { key: "gross_margin", label: "Gross margin", fmt: (v) => fmtPct(v) },
  { key: "operating_margin", label: "Op. margin", fmt: (v) => fmtPct(v) },
  { key: "revenue_yoy", label: "Rev. growth", fmt: (v) => fmtSignedPct(v) },
];

function subjectRow(company: string, f: Financials): Peer {
  return {
    ticker: f.ticker ?? "",
    name: company,
    market_cap: f.valuation?.market_cap ?? null,
    trailing_pe: f.valuation?.trailing_pe ?? null,
    forward_pe: f.valuation?.forward_pe ?? null,
    ev_to_ebitda: f.valuation?.ev_to_ebitda ?? null,
    price_to_sales: f.valuation?.price_to_sales ?? null,
    gross_margin: f.profitability?.gross_margin ?? null,
    operating_margin: f.profitability?.operating_margin ?? null,
    revenue_yoy: f.growth?.revenue_yoy ?? null,
  };
}

export default function PeersTable({
  company,
  financials,
  peers,
  basis,
}: {
  company: string;
  financials: Financials;
  peers: Peer[];
  basis?: string | null;
}) {
  if (peers.length === 0) {
    return <p className="text-sm text-muted">No comparable companies were found for this ticker.</p>;
  }
  const rows = [subjectRow(company, financials), ...peers];

  return (
    <div>
      <div className="-mx-6 overflow-x-auto px-6">
        <table className="num w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-axis text-xs text-muted">
              <th scope="col" className="py-2 pr-4 text-left font-medium">Company</th>
              {COLUMNS.map((c) => (
                <th key={c.key} scope="col" className="px-2 py-2 text-right font-medium last:pr-0">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.ticker} className={`border-b border-grid last:border-0 ${i === 0 ? "bg-accent-wash" : ""}`}>
                <th scope="row" className={`py-2.5 pr-4 text-left font-normal ${i === 0 ? "pl-2" : ""}`}>
                  <span className="font-semibold text-ink">{row.ticker}</span>
                  <span className="ml-2 text-ink2">{row.name}</span>
                </th>
                {COLUMNS.map((c) => (
                  <td
                    key={c.key}
                    className={`px-2 py-2.5 text-right last:pr-0 ${i === 0 ? "font-semibold text-ink last:pr-2" : "text-ink2"}`}
                  >
                    {c.fmt(row[c.key] as number | null)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {basis ? <p className="mt-3 text-xs text-muted">{basis}</p> : null}
    </div>
  );
}
