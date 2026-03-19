import { readFile } from "node:fs/promises";
import path from "node:path";


type ReleaseMetaPayload = {
  git_sha: string;
  release_id: string;
  built_at: string;
  backend_slot?: string;
  frontend_slot?: string;
};

export type RuntimeVersionPayload = {
  status: "ok" | "degraded";
  git_sha: string | null;
  release_id: string | null;
  built_at: string | null;
  frontend_slot: string | null;
  missing_release_meta: boolean;
  release_meta_error: string | null;
};


function getReleaseMetaPath() {
  return path.resolve(process.cwd(), "..", ".release-meta.json");
}


export async function readRuntimeVersion(): Promise<RuntimeVersionPayload> {
  const payload: RuntimeVersionPayload = {
    status: "ok",
    git_sha: null,
    release_id: null,
    built_at: null,
    frontend_slot: null,
    missing_release_meta: false,
    release_meta_error: null,
  };

  let parsed: unknown;
  try {
    parsed = JSON.parse(await readFile(getReleaseMetaPath(), "utf-8"));
  } catch (error) {
    payload.status = "degraded";
    payload.missing_release_meta = true;
    payload.release_meta_error = error instanceof SyntaxError ? "invalid_json" : "missing";
    return payload;
  }

  if (typeof parsed !== "object" || parsed === null) {
    payload.status = "degraded";
    payload.missing_release_meta = true;
    payload.release_meta_error = "invalid_shape";
    return payload;
  }

  const meta = parsed as Partial<ReleaseMetaPayload>;
  if (!meta.git_sha || !meta.release_id || !meta.built_at) {
    payload.status = "degraded";
    payload.missing_release_meta = true;
    payload.release_meta_error = "invalid_shape";
    return payload;
  }

  payload.git_sha = meta.git_sha;
  payload.release_id = meta.release_id;
  payload.built_at = meta.built_at;
  payload.frontend_slot = meta.frontend_slot ?? null;
  return payload;
}
