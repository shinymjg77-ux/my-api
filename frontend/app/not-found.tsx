import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="panel-strong w-full max-w-md p-8 text-center">
        <h1 className="text-2xl font-bold text-ink">페이지를 찾을 수 없습니다</h1>
        <p className="mt-3 text-sm text-muted">요청하신 페이지가 존재하지 않습니다.</p>
        <Link href="/dashboard" className="button-primary mt-6 inline-flex">
          대시보드로 이동
        </Link>
      </div>
    </main>
  );
}
