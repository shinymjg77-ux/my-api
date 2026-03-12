"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime } from "@/lib/format";
import type { HttpMethod, ManagedApi, ManagedApiInput } from "@/lib/types";
import { readErrorMessage } from "@/lib/utils";


interface ApiManagerProps {
  initialItems: ManagedApi[];
}


const emptyForm: ManagedApiInput = {
  name: "",
  url: "",
  method: "GET",
  description: "",
  is_active: true,
};


function buildEditState(items: ManagedApi[]) {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      {
        name: item.name,
        url: item.url,
        method: item.method,
        description: item.description ?? "",
        is_active: item.is_active,
      } satisfies ManagedApiInput,
    ]),
  ) as Record<number, ManagedApiInput>;
}


export function ApiManager({ initialItems }: ApiManagerProps) {
  const router = useRouter();
  const [createForm, setCreateForm] = useState<ManagedApiInput>(emptyForm);
  const [editForms, setEditForms] = useState<Record<number, ManagedApiInput>>(() => buildEditState(initialItems));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [pendingKey, setPendingKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setEditForms(buildEditState(initialItems));
    setEditingId(null);
  }, [initialItems]);

  async function submitRequest(url: string, init: RequestInit) {
    setError("");
    const response = await fetch(url, {
      ...init,
      credentials: "same-origin",
      headers: {
        "content-type": "application/json",
        ...(init.headers ?? {}),
      },
    });

    if (!response.ok) {
      setError(await readErrorMessage(response));
      return false;
    }

    router.refresh();
    return true;
  }

  async function handleCreate() {
    setPendingKey("create");
    const ok = await submitRequest("/api/proxy/apis", {
      method: "POST",
      body: JSON.stringify(createForm),
    });
    if (ok) {
      setCreateForm(emptyForm);
    }
    setPendingKey("");
  }

  async function handleUpdate(apiId: number) {
    setPendingKey(`update-${apiId}`);
    const ok = await submitRequest(`/api/proxy/apis/${apiId}`, {
      method: "PUT",
      body: JSON.stringify(editForms[apiId]),
    });
    if (ok) {
      setEditingId(null);
    }
    setPendingKey("");
  }

  async function handleDelete(apiId: number) {
    if (!window.confirm("이 API 항목을 삭제하시겠습니까?")) {
      return;
    }

    setPendingKey(`delete-${apiId}`);
    await submitRequest(`/api/proxy/apis/${apiId}`, {
      method: "DELETE",
    });
    setPendingKey("");
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      <SectionCard title="새 API 등록" description="실제로 호출하거나 추적할 API 엔드포인트를 등록합니다.">
        <div className="space-y-4">
          <label className="field">
            <span className="label">이름</span>
            <input
              className="input"
              value={createForm.name}
              onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Billing API"
            />
          </label>

          <label className="field">
            <span className="label">URL</span>
            <input
              className="input"
              value={createForm.url}
              onChange={(event) => setCreateForm((current) => ({ ...current, url: event.target.value }))}
              placeholder="https://api.example.com/v1/health"
            />
          </label>

          <label className="field">
            <span className="label">HTTP 메서드</span>
            <select
              className="select"
              value={createForm.method}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, method: event.target.value as HttpMethod }))
              }
            >
              {["GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                <option key={method} value={method}>
                  {method}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">설명</span>
            <textarea
              className="textarea"
              value={createForm.description}
              onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="운영 시 어떤 목적으로 사용하는 API인지 기록합니다."
            />
          </label>

          <label className="flex items-center gap-3 rounded-xl border border-line bg-panelStrong px-4 py-3 text-sm text-ink">
            <input
              checked={createForm.is_active}
              type="checkbox"
              onChange={(event) => setCreateForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            등록 직후 활성 상태로 둡니다
          </label>

          {error ? <p className="rounded-xl border border-danger/20 bg-dangerSoft px-4 py-3 text-sm text-danger">{error}</p> : null}

          <button className="button-primary w-full" type="button" onClick={handleCreate} disabled={pendingKey === "create"}>
            {pendingKey === "create" ? "저장 중..." : "API 저장"}
          </button>
        </div>
      </SectionCard>

      <SectionCard
        title="등록된 API"
        description={`${initialItems.length}개의 API 엔드포인트를 관리 중입니다.`}
      >
        {initialItems.length === 0 ? (
          <EmptyState title="등록된 API가 없습니다." description="왼쪽 입력 폼에서 첫 번째 API 항목을 추가해 운영 목록을 시작하세요." />
        ) : (
          <div className="space-y-4">
            {initialItems.map((item) => {
              const form = editForms[item.id];
              const isEditing = editingId === item.id;

              return (
                <article key={item.id} className="rounded-2xl border border-line bg-panelStrong p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-ink">{item.name}</h3>
                        <StatusBadge tone={item.is_active ? "success" : "muted"}>
                          {item.is_active ? "Active" : "Disabled"}
                        </StatusBadge>
                        <StatusBadge>{item.method}</StatusBadge>
                      </div>
                      <p className="break-all font-mono text-sm text-muted">{item.url}</p>
                      <p className="text-sm leading-6 text-muted">{item.description || "설명 없음"}</p>
                      <div className="grid gap-2 text-xs text-muted sm:grid-cols-2">
                        <span>생성: {formatDateTime(item.created_at)}</span>
                        <span>수정: {formatDateTime(item.updated_at)}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button className="button-secondary" type="button" onClick={() => setEditingId(isEditing ? null : item.id)}>
                        {isEditing ? "편집 닫기" : "편집"}
                      </button>
                      <button
                        className="button-danger"
                        type="button"
                        onClick={() => handleDelete(item.id)}
                        disabled={pendingKey === `delete-${item.id}`}
                      >
                        {pendingKey === `delete-${item.id}` ? "삭제 중..." : "삭제"}
                      </button>
                    </div>
                  </div>

                  {isEditing ? (
                    <div className="mt-5 grid gap-4 border-t border-line pt-5 md:grid-cols-2">
                      <label className="field">
                        <span className="label">이름</span>
                        <input
                          className="input"
                          value={form.name}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], name: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span className="label">HTTP 메서드</span>
                        <select
                          className="select"
                          value={form.method}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], method: event.target.value as HttpMethod },
                            }))
                          }
                        >
                          {["GET", "POST", "PUT", "PATCH", "DELETE"].map((method) => (
                            <option key={method} value={method}>
                              {method}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="field md:col-span-2">
                        <span className="label">URL</span>
                        <input
                          className="input"
                          value={form.url}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], url: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field md:col-span-2">
                        <span className="label">설명</span>
                        <textarea
                          className="textarea"
                          value={form.description}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], description: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="flex items-center gap-3 rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink md:col-span-2">
                        <input
                          checked={form.is_active}
                          type="checkbox"
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], is_active: event.target.checked },
                            }))
                          }
                        />
                        이 API를 활성 상태로 유지합니다
                      </label>

                      <div className="md:col-span-2 flex justify-end">
                        <button
                          className="button-primary"
                          type="button"
                          onClick={() => handleUpdate(item.id)}
                          disabled={pendingKey === `update-${item.id}`}
                        >
                          {pendingKey === `update-${item.id}` ? "저장 중..." : "변경 저장"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
