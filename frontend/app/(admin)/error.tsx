"use client";

export default function AdminError({ error, reset }: { error: Error; reset: () => void }) {
  const detail =
    process.env.NODE_ENV !== "production" && error.message
      ? error.message
      : "페이지를 다시 불러오거나 잠시 후 다시 시도해주세요.";

  return (
    <div className="panel-strong p-8 text-center">
      <h2 className="text-xl font-bold text-ink">페이지 로드 중 오류 발생</h2>
      <p className="mt-3 text-sm text-muted">{detail}</p>
      <button onClick={reset} className="button-primary mt-6">
        다시 시도
      </button>
    </div>
  );
}
