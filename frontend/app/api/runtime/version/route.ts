import { readRuntimeVersion } from "@/lib/release-meta";


export const dynamic = "force-dynamic";


export async function GET() {
  return Response.json(await readRuntimeVersion());
}
