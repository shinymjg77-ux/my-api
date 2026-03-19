"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { readErrorMessage } from "@/lib/utils";


export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsPending(true);

    try {
      const formData = new FormData(event.currentTarget);
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          username: String(formData.get("username") ?? ""),
          password: String(formData.get("password") ?? ""),
        }),
        credentials: "same-origin",
      });

      if (!response.ok) {
        setError(await readErrorMessage(response));
        return;
      }

      const nextPath = searchParams.get("next");
      const safeNext =
        nextPath && nextPath.startsWith("/") && !nextPath.startsWith("//")
          ? nextPath
          : "/dashboard";
      router.push(safeNext);
      router.refresh();
    } catch {
      setError("서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요.");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="w-full max-w-md space-y-8">
      <div className="space-y-3">
        <div className="inline-flex rounded-full border border-line bg-panel px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted">
          Admin Access
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-bold tracking-tight text-ink">관리자 로그인</h2>
          <p className="text-sm leading-6 text-muted">
            FastAPI 백엔드 세션 쿠키를 그대로 사용합니다. 로그인 후 관리자 페이지로 즉시 이동합니다.
          </p>
        </div>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <label className="field">
          <span className="label">사용자명</span>
          <input className="input" name="username" placeholder="admin" autoComplete="username" required />
        </label>

        <label className="field">
          <span className="label">비밀번호</span>
          <input
            className="input"
            name="password"
            placeholder="비밀번호"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>

        {error ? (
          <p role="alert" className="rounded-xl border border-danger/20 bg-dangerSoft px-4 py-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <button className="button-primary w-full" type="submit" disabled={isPending}>
          {isPending ? "로그인 중..." : "로그인"}
        </button>
      </form>

      <div className="rounded-2xl border border-line bg-panel p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">운영 메모</p>
        <p className="mt-2 text-sm leading-6 text-muted">
          서버 배포 환경에서는 관리자 계정을 별도로 관리하고, 초기 부트스트랩 비밀번호는 즉시 교체하는 편이 안전합니다.
        </p>
      </div>
    </div>
  );
}
