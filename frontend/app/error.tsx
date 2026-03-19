"use client";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  const detail =
    process.env.NODE_ENV !== "production" && error.message
      ? error.message
      : "잠시 후 다시 시도해주세요.";

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="panel-strong w-full max-w-md p-8 text-center">
        <h1 className="text-2xl font-bold text-ink">문제가 발생했습니다</h1>
        <p className="mt-3 text-sm text-muted">{detail}</p>
        <button onClick={reset} className="button-primary mt-6">
          다시 시도
        </button>
      </div>
    </main>
  );
}
