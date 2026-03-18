"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { SectionCard } from "@/components/section-card";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime } from "@/lib/format";
import type { HttpMethod, ManagedApi, ManagedApiInput } from "@/lib/types";
import { cn, readErrorMessage } from "@/lib/utils";


interface ApiManagerProps {
  initialItems: ManagedApi[];
}

interface ApiTreeNode {
  name: string;
  path: string;
  children: ApiTreeNode[];
  items: ManagedApi[];
}

interface ApiTreeBuilderNode {
  name: string;
  path: string;
  children: Map<string, ApiTreeBuilderNode>;
  items: ManagedApi[];
}


function buildEditState(items: ManagedApi[]) {
  return Object.fromEntries(
    items.map((item) => [
      item.id,
      {
        name: item.name,
        group_path: item.group_path ?? "",
        url: item.url,
        method: item.method,
        description: item.description ?? "",
        is_active: item.is_active,
      } satisfies ManagedApiInput,
    ]),
  ) as Record<number, ManagedApiInput>;
}


function buildApiTree(items: ManagedApi[]) {
  const root = new Map<string, ApiTreeBuilderNode>();
  const ungrouped: ManagedApi[] = [];

  for (const item of items) {
    const segments = (item.group_path ?? "")
      .split("/")
      .map((segment) => segment.trim())
      .filter(Boolean);

    if (segments.length === 0) {
      ungrouped.push(item);
      continue;
    }

    let cursor = root;
    let currentPath = "";
    let currentNode: ApiTreeBuilderNode | null = null;

    for (const segment of segments) {
      currentPath = currentPath ? `${currentPath}/${segment}` : segment;
      let nextNode = cursor.get(segment);
      if (!nextNode) {
        nextNode = {
          name: segment,
          path: currentPath,
          children: new Map(),
          items: [],
        };
        cursor.set(segment, nextNode);
      }
      currentNode = nextNode;
      cursor = nextNode.children;
    }

    currentNode?.items.push(item);
  }

  function materialize(nodes: Map<string, ApiTreeBuilderNode>): ApiTreeNode[] {
    return Array.from(nodes.values())
      .map((node) => ({
        name: node.name,
        path: node.path,
        items: [...node.items].sort((left, right) => left.name.localeCompare(right.name)),
        children: materialize(node.children),
      }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }

  return {
    ungrouped: [...ungrouped].sort((left, right) => left.name.localeCompare(right.name)),
    grouped: materialize(root),
  };
}


function collectGroupPaths(nodes: ApiTreeNode[]) {
  const paths = new Set<string>();

  function visit(items: ApiTreeNode[]) {
    for (const item of items) {
      paths.add(item.path);
      visit(item.children);
    }
  }

  visit(nodes);
  return paths;
}


function firstAvailableApiId(items: ManagedApi[]) {
  return items[0]?.id ?? null;
}


export function ApiManager({ initialItems }: ApiManagerProps) {
  const router = useRouter();
  const [editForms, setEditForms] = useState<Record<number, ManagedApiInput>>(() => buildEditState(initialItems));
  const [selectedId, setSelectedId] = useState<number | null>(() => firstAvailableApiId(initialItems));
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => new Set());
  const [pendingKey, setPendingKey] = useState("");
  const [error, setError] = useState("");

  const tree = useMemo(() => buildApiTree(initialItems), [initialItems]);
  const selectedItem = useMemo(
    () => initialItems.find((item) => item.id === selectedId) ?? null,
    [initialItems, selectedId],
  );

  useEffect(() => {
    setEditForms(buildEditState(initialItems));

    setSelectedId((current) => {
      if (current && initialItems.some((item) => item.id === current)) {
        return current;
      }
      return firstAvailableApiId(initialItems);
    });

    const availablePaths = collectGroupPaths(tree.grouped);
    setExpandedPaths((current) => {
      const next = new Set<string>();
      for (const path of current) {
        if (availablePaths.has(path)) {
          next.add(path);
        }
      }
      return next;
    });
  }, [initialItems, tree.grouped]);

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

  async function handleUpdate() {
    if (!selectedItem) {
      return;
    }

    setPendingKey(`update-${selectedItem.id}`);
    await submitRequest(`/api/proxy/apis/${selectedItem.id}`, {
      method: "PUT",
      body: JSON.stringify(editForms[selectedItem.id]),
    });
    setPendingKey("");
  }

  async function handleDelete() {
    if (!selectedItem) {
      return;
    }
    if (!window.confirm("이 API 항목을 삭제하시겠습니까?")) {
      return;
    }

    setPendingKey(`delete-${selectedItem.id}`);
    const ok = await submitRequest(`/api/proxy/apis/${selectedItem.id}`, {
      method: "DELETE",
    });
    if (ok) {
      setSelectedId(null);
    }
    setPendingKey("");
  }

  function toggleGroup(path: string) {
    setExpandedPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  function renderApiRow(item: ManagedApi, depth: number) {
    const isSelected = item.id === selectedId;

    return (
      <button
        key={item.id}
        type="button"
        onClick={() => setSelectedId(item.id)}
        className={cn(
          "flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition",
          "hover:border-accent/40 hover:bg-panelStrong",
          isSelected ? "border-accent bg-panelStrong shadow-sm" : "border-transparent bg-transparent",
        )}
        style={{ paddingLeft: 12 + depth * 18 }}
      >
        <span className="w-2 shrink-0 text-muted">-</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">{item.name}</span>
          <span className="block truncate font-mono text-[11px] text-muted">{item.url}</span>
        </span>
        <StatusBadge>{item.method}</StatusBadge>
      </button>
    );
  }

  function renderGroupNode(node: ApiTreeNode, depth: number): ReactNode {
    const isExpanded = expandedPaths.has(node.path);

    return (
      <div key={node.path} className="space-y-1">
        <button
          type="button"
          onClick={() => toggleGroup(node.path)}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-ink hover:bg-panelStrong"
          style={{ paddingLeft: 12 + depth * 18 }}
        >
          <span className="w-3 shrink-0 text-xs text-muted">{isExpanded ? "-" : "+"}</span>
          <span className="truncate">{node.name}</span>
          <span className="ml-auto text-[11px] uppercase tracking-[0.18em] text-muted">Folder</span>
        </button>

        {isExpanded ? (
          <div className="space-y-1">
            {node.items.map((item) => renderApiRow(item, depth + 1))}
            {node.children.map((child) => renderGroupNode(child, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  }

  const selectedForm = selectedItem ? editForms[selectedItem.id] : null;

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
      <SectionCard
        title="API 계층"
        description={`${initialItems.length}개의 API 엔드포인트를 폴더 구조로 탐색합니다.`}
      >
        {initialItems.length === 0 ? (
          <EmptyState
            title="표시할 API가 없습니다."
            description="현재 필터 조건에 맞는 API가 없습니다."
          />
        ) : (
          <div className="space-y-1">
            {tree.ungrouped.length > 0 ? (
              <div className="space-y-1">
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-ink"
                >
                  <span className="w-3 shrink-0 text-xs text-muted">-</span>
                  <span>Ungrouped</span>
                  <span className="ml-auto text-[11px] uppercase tracking-[0.18em] text-muted">Folder</span>
                </button>
                {tree.ungrouped.map((item) => renderApiRow(item, 1))}
              </div>
            ) : null}

            {tree.grouped.map((node) => renderGroupNode(node, 0))}
          </div>
        )}
      </SectionCard>

      <SectionCard
        title="API 상세"
        description="선택한 API의 메타데이터를 확인하고 바로 수정합니다."
        action={
          selectedItem ? (
            <div className="flex items-center gap-2">
              <StatusBadge tone={selectedItem.is_active ? "success" : "muted"}>
                {selectedItem.is_active ? "Active" : "Disabled"}
              </StatusBadge>
              <StatusBadge>{selectedItem.method}</StatusBadge>
            </div>
          ) : null
        }
      >
        {!selectedItem || !selectedForm ? (
          <EmptyState
            title="API를 선택하세요."
            description="왼쪽 계층 트리에서 API를 선택하면 상세 정보와 편집 폼이 열립니다."
          />
        ) : (
          <div className="space-y-5">
            {error ? (
              <p className="rounded-xl border border-danger/20 bg-dangerSoft px-4 py-3 text-sm text-danger">
                {error}
              </p>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field">
                <span className="label">이름</span>
                <input
                  className="input"
                  value={selectedForm.name}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [selectedItem.id]: { ...current[selectedItem.id], name: event.target.value },
                    }))
                  }
                />
              </label>

              <label className="field">
                <span className="label">그룹 경로</span>
                <input
                  className="input"
                  value={selectedForm.group_path}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [selectedItem.id]: { ...current[selectedItem.id], group_path: event.target.value },
                    }))
                  }
                />
              </label>

              <label className="field">
                <span className="label">HTTP 메서드</span>
                <select
                  className="select"
                  value={selectedForm.method}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [selectedItem.id]: {
                        ...current[selectedItem.id],
                        method: event.target.value as HttpMethod,
                      },
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

              <div className="field">
                <span className="label">활성 상태</span>
                <label className="flex items-center gap-3 rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink">
                  <input
                    checked={selectedForm.is_active}
                    type="checkbox"
                    onChange={(event) =>
                      setEditForms((current) => ({
                        ...current,
                        [selectedItem.id]: {
                          ...current[selectedItem.id],
                          is_active: event.target.checked,
                        },
                      }))
                    }
                  />
                  이 API를 활성 상태로 유지합니다
                </label>
              </div>

              <label className="field md:col-span-2">
                <span className="label">URL</span>
                <input
                  className="input font-mono"
                  value={selectedForm.url}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [selectedItem.id]: { ...current[selectedItem.id], url: event.target.value },
                    }))
                  }
                />
              </label>

              <label className="field md:col-span-2">
                <span className="label">설명</span>
                <textarea
                  className="textarea min-h-28"
                  value={selectedForm.description}
                  onChange={(event) =>
                    setEditForms((current) => ({
                      ...current,
                      [selectedItem.id]: { ...current[selectedItem.id], description: event.target.value },
                    }))
                  }
                />
              </label>
            </div>

            <div className="grid gap-3 rounded-2xl border border-line bg-panel px-4 py-4 md:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Created</p>
                <p className="mt-1 text-sm text-ink">{formatDateTime(selectedItem.created_at)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">Updated</p>
                <p className="mt-1 text-sm text-ink">{formatDateTime(selectedItem.updated_at)}</p>
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-3 border-t border-line pt-5">
              <button
                className="button-danger"
                type="button"
                onClick={handleDelete}
                disabled={pendingKey === `delete-${selectedItem.id}`}
              >
                {pendingKey === `delete-${selectedItem.id}` ? "삭제 중..." : "삭제"}
              </button>
              <button
                className="button-primary"
                type="button"
                onClick={handleUpdate}
                disabled={pendingKey === `update-${selectedItem.id}`}
              >
                {pendingKey === `update-${selectedItem.id}` ? "저장 중..." : "변경 저장"}
              </button>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
