import { proxyToBackend } from "@/lib/server-api";


function resolvePath(params: { path: string[] }) {
  const joined = params.path.join("/");
  if (joined.includes("..")) {
    return null;
  }
  return `/${joined}`;
}


async function handle(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = resolvePath(await params);
  if (!path) {
    return Response.json({ detail: "Invalid path" }, { status: 400 });
  }
  return proxyToBackend(request, path);
}


export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
