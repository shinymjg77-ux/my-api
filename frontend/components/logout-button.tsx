"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { readErrorMessage } from "@/lib/utils";


export function LogoutButton() {
  const router = useRouter();
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState("");

  async function handleLogout() {
    setIsPending(true);
    setError("");

    const response = await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });

    if (!response.ok) {
      setError(await readErrorMessage(response));
      setIsPending(false);
      return;
    }

    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button className="button-secondary" type="button" onClick={handleLogout} disabled={isPending}>
        {isPending ? "로그아웃 중..." : "로그아웃"}
      </button>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
