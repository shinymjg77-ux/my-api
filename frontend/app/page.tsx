import { redirect } from "next/navigation";

import { getCurrentAdmin } from "@/lib/server-api";


export default async function HomePage() {
  const admin = await getCurrentAdmin();
  redirect(admin ? "/dashboard" : "/login");
}
