import type { ReactNode } from "react";


interface SectionCardProps {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}


export function SectionCard({ title, description, action, children }: SectionCardProps) {
  return (
    <section className="panel overflow-hidden">
      <header className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {description ? <p className="text-sm text-muted">{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}
