import { proxyToBackend } from "@/lib/server-api";


export async function GET(request: Request) {
  return proxyToBackend(request, "/auth/me");
}
