import type { ReactNode } from "react";


interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}


export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">{eyebrow}</p>
        ) : null}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-ink">{title}</h1>
          <p className="max-w-3xl text-sm leading-6 text-muted">{description}</p>
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
