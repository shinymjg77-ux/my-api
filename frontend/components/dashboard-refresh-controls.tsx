"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { formatDateTime } from "@/lib/format";


interface DashboardRefreshControlsProps {
  generatedAt: string;
}


export function DashboardRefreshControls({ generatedAt }: DashboardRefreshControlsProps) {
  const router = useRouter();
  const [isMounted, setIsMounted] = useState(false);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setIsMounted(true);

    const timer = window.setInterval(() => {
      startTransition(() => {
        router.refresh();
      });
    }, 20_000);

    return () => {
      window.clearInterval(timer);
    };
  }, [router, startTransition]);

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted">
        Last Update {isMounted ? formatDateTime(generatedAt) : "-"}
      </p>
      <button
        className="button-secondary"
        type="button"
        onClick={() =>
          startTransition(() => {
            router.refresh();
          })
        }
        disabled={isPending}
      >
        {isPending ? "갱신 중..." : "새로고침"}
      </button>
    </div>
  );
}
