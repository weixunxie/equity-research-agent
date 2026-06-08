import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ResearchResponse } from "@/lib/types";

export default function ReportView({ report }: { report: ResearchResponse }) {
  return (
    <article className="report-prose">
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
        {report.report_markdown}
      </ReactMarkdown>
    </article>
  );
}
