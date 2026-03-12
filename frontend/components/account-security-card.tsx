"use client";

import { FormEvent, useState } from "react";

import { SectionCard } from "@/components/section-card";
import { readErrorMessage } from "@/lib/utils";


export function AccountSecurityCard() {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsPending(true);

    const formData = new FormData(event.currentTarget);
    const currentPassword = String(formData.get("current_password") ?? "");
    const newPassword = String(formData.get("new_password") ?? "");
    const confirmPassword = String(formData.get("confirm_password") ?? "");

    if (newPassword.length < 12) {
      setError("새 비밀번호는 12자 이상이어야 합니다.");
      setIsPending(false);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("새 비밀번호 확인이 일치하지 않습니다.");
      setIsPending(false);
      return;
    }

    if (currentPassword === newPassword) {
      setError("새 비밀번호는 현재 비밀번호와 달라야 합니다.");
      setIsPending(false);
      return;
    }

    const response = await fetch("/api/proxy/auth/change-password", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });

    if (!response.ok) {
      setError(await readErrorMessage(response));
      setIsPending(false);
      return;
    }

    const data = (await response.json()) as { message: string };
    setMessage(data.message);
    setIsPending(false);
    event.currentTarget.reset();
  }

  return (
    <SectionCard
      title="관리자 비밀번호 변경"
      description="현재 비밀번호를 확인한 뒤 새 비밀번호로 교체합니다. 운영 서버에서는 주기적으로 교체하는 편이 안전합니다."
    >
      <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit} noValidate>
        <label className="field">
          <span className="label">현재 비밀번호</span>
          <input
            className="input"
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
          />
        </label>

        <div className="hidden md:block" />

        <label className="field">
          <span className="label">새 비밀번호</span>
          <input
            className="input"
            name="new_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
          />
        </label>

        <label className="field">
          <span className="label">새 비밀번호 확인</span>
          <input
            className="input"
            name="confirm_password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
          />
        </label>

        <p className="text-sm leading-6 text-muted md:col-span-2">새 비밀번호는 12자 이상이어야 합니다.</p>

        {error ? (
          <p className="rounded-xl border border-danger/20 bg-dangerSoft px-4 py-3 text-sm text-danger md:col-span-2">
            {error}
          </p>
        ) : null}

        {message ? (
          <p className="rounded-xl border border-ok/20 bg-okSoft px-4 py-3 text-sm text-ok md:col-span-2">{message}</p>
        ) : null}

        <div className="md:col-span-2 flex justify-end">
          <button className="button-primary" type="submit" disabled={isPending}>
            {isPending ? "변경 중..." : "비밀번호 변경"}
          </button>
        </div>
      </form>
    </SectionCard>
  );
}
