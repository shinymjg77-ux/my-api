import { proxyToBackend } from "@/lib/server-api";


function resolvePath(params: { path: string[] }) {
  return `/${params.path.join("/")}`;
}


export async function GET(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyToBackend(request, resolvePath(await params));
}


export async function POST(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyToBackend(request, resolvePath(await params));
}


export async function PUT(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyToBackend(request, resolvePath(await params));
}


export async function PATCH(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyToBackend(request, resolvePath(await params));
}


export async function DELETE(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return proxyToBackend(request, resolvePath(await params));
}
