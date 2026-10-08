"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportView({
  ticker,
  markdown,
  streaming,
}: {
  ticker: string;
  markdown: string;
  /** True while the Writer is still generating; export is held until it ends. */
  streaming: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access denied; the download button still works.
    }
  }

  if (!markdown) {
    return (
      <div className="card space-y-3 p-8" aria-label="Report in progress">
        <div className="skeleton h-7 w-2/3" />
        {[...Array(6)].map((_, i) => (
          <div key={i} className="skeleton h-4" style={{ width: `${100 - (i % 3) * 8}%` }} />
        ))}
        <p className="pt-2 text-sm text-muted">
          The report is written once the research and analysis steps finish.
        </p>
      </div>
    );
  }

  return (
    <div className="card p-6 sm:p-10 print:border-0 print:p-0">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted" aria-live="polite">
          {streaming ? "Writing the report…" : ""}
        </span>
        <div className="flex gap-2">
          <button type="button" className="btn" onClick={copy} disabled={streaming}>
            {copied ? "Copied" : "Copy Markdown"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={streaming}
            onClick={() => download(`${ticker}-equity-research.md`, markdown)}
          >
            Download .md
          </button>
          <button type="button" className="btn" disabled={streaming} onClick={() => window.print()}>
            Print / PDF
          </button>
        </div>
      </div>

      <article className="report-prose mx-auto max-w-3xl">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Open source/news links in a new tab. `node` is dropped so it isn't
            // spread onto the DOM element.
            a({ node, href, children, ...props }) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                  {children}
                </a>
              );
            },
          }}
        >
          {markdown}
        </ReactMarkdown>
      </article>
    </div>
  );
}
