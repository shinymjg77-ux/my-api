import { proxyToBackend } from "@/lib/server-api";


export async function POST(request: Request) {
  return proxyToBackend(request, "/auth/logout");
}
