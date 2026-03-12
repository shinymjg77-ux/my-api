"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime, formatLatency } from "@/lib/format";
import type { DBType, DbConnection, DbConnectionInput, DbConnectionTestResponse } from "@/lib/types";
import { readErrorMessage } from "@/lib/utils";


interface DbConnectionManagerProps {
  initialItems: DbConnection[];
}


const emptyForm: DbConnectionInput = {
  name: "",
  db_type: "postgresql",
  host: "",
  port: "",
  db_name: "",
  username: "",
  password: "",
  description: "",
  is_active: true,
};


function buildEditState(items: DbConnection[]) {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      {
        name: item.name,
        db_type: item.db_type,
        host: item.host ?? "",
        port: item.port ? String(item.port) : "",
        db_name: item.db_name ?? "",
        username: item.username ?? "",
        password: "",
        description: item.description ?? "",
        is_active: item.is_active,
      } satisfies DbConnectionInput,
    ]),
  ) as Record<number, DbConnectionInput>;
}


function toCreatePayload(form: DbConnectionInput) {
  return {
    name: form.name,
    db_type: form.db_type,
    host: form.host || null,
    port: form.port ? Number(form.port) : null,
    db_name: form.db_name || null,
    username: form.username || null,
    password: form.password || null,
    description: form.description || null,
    is_active: form.is_active,
  };
}


function toUpdatePayload(form: DbConnectionInput) {
  return {
    name: form.name,
    db_type: form.db_type,
    host: form.host || null,
    port: form.port ? Number(form.port) : null,
    db_name: form.db_name || null,
    username: form.username || null,
    ...(form.password ? { password: form.password } : {}),
    description: form.description || null,
    is_active: form.is_active,
  };
}


export function DbConnectionManager({ initialItems }: DbConnectionManagerProps) {
  const router = useRouter();
  const [createForm, setCreateForm] = useState<DbConnectionInput>(emptyForm);
  const [editForms, setEditForms] = useState<Record<number, DbConnectionInput>>(() => buildEditState(initialItems));
  const [editingId, setEditingId] = useState<number | null>(null);
  const [pendingKey, setPendingKey] = useState("");
  const [error, setError] = useState("");
  const [testMessage, setTestMessage] = useState("");

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
    const ok = await submitRequest("/api/proxy/db-connections", {
      method: "POST",
      body: JSON.stringify(toCreatePayload(createForm)),
    });
    if (ok) {
      setCreateForm(emptyForm);
      setTestMessage("");
    }
    setPendingKey("");
  }

  async function handleUpdate(connectionId: number) {
    setPendingKey(`update-${connectionId}`);
    const ok = await submitRequest(`/api/proxy/db-connections/${connectionId}`, {
      method: "PUT",
      body: JSON.stringify(toUpdatePayload(editForms[connectionId])),
    });
    if (ok) {
      setEditingId(null);
    }
    setPendingKey("");
  }

  async function handleDelete(connectionId: number) {
    if (!window.confirm("이 DB 연결을 삭제하시겠습니까?")) {
      return;
    }

    setPendingKey(`delete-${connectionId}`);
    await submitRequest(`/api/proxy/db-connections/${connectionId}`, {
      method: "DELETE",
    });
    setPendingKey("");
  }

  async function handleAdhocTest() {
    setPendingKey("adhoc-test");
    setError("");
    setTestMessage("");

    const response = await fetch("/api/proxy/db-connections/test", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(toCreatePayload(createForm)),
    });

    if (!response.ok) {
      setError(await readErrorMessage(response));
      setPendingKey("");
      return;
    }

    const data = (await response.json()) as DbConnectionTestResponse;
    setTestMessage(`${data.success ? "성공" : "실패"} · ${data.message}${data.latency_ms ? ` · ${formatLatency(data.latency_ms)}` : ""}`);
    setPendingKey("");
  }

  async function handleSavedTest(connectionId: number) {
    setPendingKey(`test-${connectionId}`);
    setError("");

    const response = await fetch(`/api/proxy/db-connections/${connectionId}/test`, {
      method: "POST",
      credentials: "same-origin",
    });

    if (!response.ok) {
      setError(await readErrorMessage(response));
      setPendingKey("");
      return;
    }

    router.refresh();
    setPendingKey("");
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
      <SectionCard title="새 DB 연결 등록" description="저장 전 테스트와 저장 후 재테스트 모두 지원합니다.">
        <div className="grid gap-4">
          <label className="field">
            <span className="label">연결 이름</span>
            <input
              className="input"
              value={createForm.name}
              onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Primary Postgres"
            />
          </label>

          <label className="field">
            <span className="label">DB 종류</span>
            <select
              className="select"
              value={createForm.db_type}
              onChange={(event) => setCreateForm((current) => ({ ...current, db_type: event.target.value as DBType }))}
            >
              <option value="postgresql">PostgreSQL</option>
              <option value="sqlite">SQLite</option>
            </select>
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="field">
              <span className="label">호스트</span>
              <input
                className="input"
                value={createForm.host}
                onChange={(event) => setCreateForm((current) => ({ ...current, host: event.target.value }))}
                placeholder="127.0.0.1"
              />
            </label>

            <label className="field">
              <span className="label">포트</span>
              <input
                className="input"
                value={createForm.port}
                onChange={(event) => setCreateForm((current) => ({ ...current, port: event.target.value }))}
                placeholder="5432"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="field">
              <span className="label">DB 이름</span>
              <input
                className="input"
                value={createForm.db_name}
                onChange={(event) => setCreateForm((current) => ({ ...current, db_name: event.target.value }))}
                placeholder="app"
              />
            </label>

            <label className="field">
              <span className="label">사용자명</span>
              <input
                className="input"
                value={createForm.username}
                onChange={(event) => setCreateForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="postgres"
              />
            </label>
          </div>

          <label className="field">
            <span className="label">비밀번호</span>
            <input
              className="input"
              type="password"
              value={createForm.password}
              onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))}
              placeholder="저장 시 암호화됩니다"
            />
          </label>

          <label className="field">
            <span className="label">설명</span>
            <textarea
              className="textarea"
              value={createForm.description}
              onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="연결 용도나 운영 메모를 기록합니다."
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
          {testMessage ? <p className="rounded-xl border border-ok/20 bg-okSoft px-4 py-3 text-sm text-ok">{testMessage}</p> : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <button className="button-secondary" type="button" onClick={handleAdhocTest} disabled={pendingKey === "adhoc-test"}>
              {pendingKey === "adhoc-test" ? "테스트 중..." : "입력값으로 테스트"}
            </button>
            <button className="button-primary" type="button" onClick={handleCreate} disabled={pendingKey === "create"}>
              {pendingKey === "create" ? "저장 중..." : "DB 연결 저장"}
            </button>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="등록된 DB 연결" description={`${initialItems.length}개의 연결 구성을 보관 중입니다.`}>
        {initialItems.length === 0 ? (
          <EmptyState title="등록된 DB 연결이 없습니다." description="좌측에서 연결 정보를 입력하고 테스트한 뒤 저장하세요." />
        ) : (
          <div className="space-y-4">
            {initialItems.map((item) => {
              const form = editForms[item.id];
              const isEditing = editingId === item.id;
              const testTone =
                item.last_test_status === "success" ? "success" : item.last_test_status === "failed" ? "danger" : "muted";

              return (
                <article key={item.id} className="rounded-2xl border border-line bg-panelStrong p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-ink">{item.name}</h3>
                        <StatusBadge tone={item.is_active ? "success" : "muted"}>
                          {item.is_active ? "Active" : "Disabled"}
                        </StatusBadge>
                        <StatusBadge>{item.db_type}</StatusBadge>
                        <StatusBadge tone={testTone}>{item.last_test_status ?? "untested"}</StatusBadge>
                      </div>

                      <div className="grid gap-2 text-sm text-muted sm:grid-cols-2">
                        <span>Host: {item.host || "-"}</span>
                        <span>Port: {item.port ?? "-"}</span>
                        <span>DB: {item.db_name || "-"}</span>
                        <span>User: {item.username || "-"}</span>
                        <span>Password: {item.has_password ? item.password_masked : "-"}</span>
                        <span>최근 테스트: {formatDateTime(item.last_tested_at)}</span>
                      </div>

                      <p className="text-sm leading-6 text-muted">{item.description || "설명 없음"}</p>
                      {item.last_test_message ? <p className="text-xs leading-6 text-muted">{item.last_test_message}</p> : null}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        className="button-secondary"
                        type="button"
                        onClick={() => handleSavedTest(item.id)}
                        disabled={pendingKey === `test-${item.id}`}
                      >
                        {pendingKey === `test-${item.id}` ? "테스트 중..." : "재테스트"}
                      </button>
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
                        <span className="label">연결 이름</span>
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
                        <span className="label">DB 종류</span>
                        <select
                          className="select"
                          value={form.db_type}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], db_type: event.target.value as DBType },
                            }))
                          }
                        >
                          <option value="postgresql">PostgreSQL</option>
                          <option value="sqlite">SQLite</option>
                        </select>
                      </label>

                      <label className="field">
                        <span className="label">호스트</span>
                        <input
                          className="input"
                          value={form.host}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], host: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span className="label">포트</span>
                        <input
                          className="input"
                          value={form.port}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], port: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span className="label">DB 이름</span>
                        <input
                          className="input"
                          value={form.db_name}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], db_name: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field">
                        <span className="label">사용자명</span>
                        <input
                          className="input"
                          value={form.username}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], username: event.target.value },
                            }))
                          }
                        />
                      </label>

                      <label className="field md:col-span-2">
                        <span className="label">비밀번호</span>
                        <input
                          className="input"
                          type="password"
                          value={form.password}
                          onChange={(event) =>
                            setEditForms((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], password: event.target.value },
                            }))
                          }
                          placeholder="비워두면 기존 저장된 비밀번호를 유지합니다."
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
                        이 DB 연결을 활성 상태로 유지합니다
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
