import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { ActivityLogListResponse, Admin, DashboardSummary, DbConnection, ManagedApi, OpsDashboard, RuntimeLogs } from "@/lib/types";
import { readErrorMessage } from "@/lib/utils";


const BACKEND_BASE_URL = process.env.BACKEND_BASE_URL ?? "http://127.0.0.1:8000";
const BACKEND_API_PREFIX = process.env.BACKEND_API_PREFIX ?? "/api/v1";


type QueryValue = string | number | boolean | null | undefined;

interface ServerFetchOptions extends Omit<RequestInit, "cache"> {
  query?: Record<string, QueryValue>;
}


function normalizePath(path: string) {
  const withLeadingSlash = path.startsWith("/") ? path : `/${path}`;
  return `${BACKEND_API_PREFIX}${withLeadingSlash}`;
}


function buildBackendUrl(path: string, query?: Record<string, QueryValue>) {
  const url = new URL(normalizePath(path), BACKEND_BASE_URL);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
  }

  return url;
}


async function copyBackendResponse(response: Response) {
  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  const setCookie = response.headers.get("set-cookie");

  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (setCookie) {
    headers.set("set-cookie", setCookie);
  }

  return new Response(await response.arrayBuffer(), {
    status: response.status,
    headers,
  });
}


export async function proxyToBackend(request: Request, path: string) {
  const sourceUrl = new URL(request.url);
  const targetUrl = buildBackendUrl(path);
  targetUrl.search = sourceUrl.search;

  const headers = new Headers();
  const cookieHeader = request.headers.get("cookie");
  const contentType = request.headers.get("content-type");

  headers.set("accept", "application/json");
  if (cookieHeader) {
    headers.set("cookie", cookieHeader);
  }
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
  });

  return copyBackendResponse(response);
}


export async function serverFetch(path: string, options: ServerFetchOptions = {}) {
  const { query, headers: initHeaders, ...rest } = options;
  const cookieStore = await cookies();
  const headers = new Headers(initHeaders);
  const cookieHeader = cookieStore.toString();

  headers.set("accept", "application/json");
  if (cookieHeader) {
    headers.set("cookie", cookieHeader);
  }
  if (rest.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  return fetch(buildBackendUrl(path, query), {
    ...rest,
    headers,
    cache: "no-store",
  });
}


async function readJsonOrRedirect<T>(response: Response): Promise<T> {
  if (response.status === 401 || response.status === 403) {
    redirect("/login");
  }
  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
  return (await response.json()) as T;
}


export async function getCurrentAdmin() {
  const response = await serverFetch("/auth/me");
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as Admin;
}


export async function requireAdmin() {
  const admin = await getCurrentAdmin();
  if (!admin) {
    redirect("/login");
  }
  return admin;
}


export async function getDashboardSummary() {
  const response = await serverFetch("/dashboard/summary");
  return readJsonOrRedirect<DashboardSummary>(response);
}


export async function getOpsDashboard() {
  const response = await serverFetch("/dashboard/overview");
  return readJsonOrRedirect<OpsDashboard>(response);
}


export async function getRuntimeLogs() {
  const response = await serverFetch("/dashboard/runtime-logs");
  return readJsonOrRedirect<RuntimeLogs>(response);
}


export async function getManagedApis(query?: Record<string, QueryValue>) {
  const response = await serverFetch("/apis", { query });
  return readJsonOrRedirect<ManagedApi[]>(response);
}


export async function getDbConnections(query?: Record<string, QueryValue>) {
  const response = await serverFetch("/db-connections", { query });
  return readJsonOrRedirect<DbConnection[]>(response);
}


export async function getLogs(query?: Record<string, QueryValue>) {
  const response = await serverFetch("/logs", { query });
  return readJsonOrRedirect<ActivityLogListResponse>(response);
}
