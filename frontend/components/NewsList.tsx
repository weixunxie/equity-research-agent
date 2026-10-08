import { fmtDate } from "@/lib/format";
import type { NewsItem, Sentiment } from "@/lib/types";

export default function NewsList({
  news,
  sentiment,
}: {
  news: NewsItem[];
  sentiment: Sentiment | null;
}) {
  return (
    <div>
      {sentiment ? <p className="text-sm leading-relaxed text-ink2">{sentiment.summary}</p> : null}
      {news.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No recent news was retrieved.</p>
      ) : (
        <ul className={`divide-y divide-grid ${sentiment ? "mt-3 border-t border-grid" : ""}`}>
          {news.map((item) => (
            <li key={item.url} className="py-3 last:pb-0">
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-ink hover:text-accent hover:underline"
              >
                {item.title}
              </a>
              <div className="mt-0.5 text-xs text-muted">
                {[item.source, item.published_date ? fmtDate(item.published_date) : null]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
              {item.snippet ? (
                <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink2">{item.snippet}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
