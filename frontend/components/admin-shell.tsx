"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/logout-button";
import type { Admin } from "@/lib/types";
import { cn } from "@/lib/utils";


interface AdminShellProps {
  admin: Admin;
  children: ReactNode;
}


const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/runtime", label: "Runtime" },
  { href: "/apis", label: "APIs" },
  { href: "/db-connections", label: "DB Connections" },
  { href: "/logs", label: "Logs" },
  { href: "/settings", label: "Settings" },
];


export function AdminShell({ admin, children }: AdminShellProps) {
  const pathname = usePathname();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const currentSection = navItems.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));

  return (
    <div className="min-h-screen px-4 py-4 sm:px-5 sm:py-5 lg:px-6">
      <div className="mx-auto grid max-w-[1680px] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside
          className={cn(
            "panel fixed inset-y-4 left-4 z-40 hidden w-[280px] flex-col overflow-hidden lg:sticky lg:top-6 lg:flex lg:h-[calc(100vh-3rem)] lg:w-auto",
            isMenuOpen && "flex",
          )}
        >
          <div className="border-b border-line px-6 py-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Personal API Admin</p>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-ink">Operations</h1>
            <p className="mt-2 text-sm leading-6 text-muted">혼자 운영하는 API와 DB 상태를 매일 확인하는 관리자 셸입니다.</p>
          </div>

          <nav aria-label="주요 탐색" className="flex-1 space-y-2 px-4 py-5">
            {navItems.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center rounded-xl px-4 py-3 text-sm font-semibold transition",
                    isActive ? "bg-ink text-white" : "text-ink hover:bg-panelStrong",
                  )}
                  onClick={() => setIsMenuOpen(false)}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="border-t border-line px-4 py-5">
            <div className="rounded-2xl border border-line bg-panelStrong px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Signed In</p>
              <p className="mt-3 text-base font-semibold text-ink">{admin.username}</p>
              <p className="mt-1 text-sm text-muted">{admin.is_active ? "활성 관리자" : "비활성 관리자"}</p>
              <div className="mt-4">
                <LogoutButton />
              </div>
            </div>
          </div>
        </aside>

        <div className="space-y-4">
          <header className="panel flex items-center justify-between px-5 py-4 lg:hidden">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Personal API Admin</p>
              <h2 className="mt-1 text-lg font-semibold text-ink">{currentSection?.label ?? "Operations"}</h2>
            </div>
            <button
              className="button-secondary"
              type="button"
              aria-expanded={isMenuOpen}
              onClick={() => setIsMenuOpen((value) => !value)}
            >
              {isMenuOpen ? "메뉴 닫기" : "메뉴"}
            </button>
          </header>

          <header className="panel hidden items-center justify-between px-6 py-5 lg:flex">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Quiet Operations Console</p>
              <p className="mt-2 text-lg font-semibold text-ink">{currentSection?.label ?? "Overview"}</p>
            </div>
            <div className="rounded-full border border-line bg-panelStrong px-4 py-2 text-sm text-muted">
              Environment: development
            </div>
          </header>

          <main className="space-y-6">{children}</main>
        </div>
      </div>

      {isMenuOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-ink/30 lg:hidden"
          aria-label="Close menu overlay"
          onClick={() => setIsMenuOpen(false)}
        />
      ) : null}
    </div>
  );
}
