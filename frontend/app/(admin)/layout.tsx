import type { ReactNode } from "react";

import { AdminShell } from "@/components/admin-shell";
import { requireAdmin } from "@/lib/server-api";


export default async function AdminLayout({ children }: { children: ReactNode }) {
  const admin = await requireAdmin();
  return <AdminShell admin={admin}>{children}</AdminShell>;
}
