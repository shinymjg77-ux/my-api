import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { getCurrentAdmin } from "@/lib/server-api";


export default async function LoginPage() {
  const admin = await getCurrentAdmin();

  if (admin) {
    redirect("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="panel hidden flex-col justify-between p-10 lg:flex">
          <div className="space-y-6">
            <span className="inline-flex rounded-full border border-accent/20 bg-accentSoft px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
              Personal Operations Console
            </span>
            <div className="space-y-4">
              <h1 className="max-w-lg text-4xl font-bold leading-tight text-ink">
                혼자 운영하는 API와 DB 상태를 한 화면에서 관리하는 관리자 콘솔
              </h1>
              <p className="max-w-xl text-base leading-7 text-muted">
                로그인 후 API 엔드포인트, 데이터베이스 연결, 최근 에러 로그를 바로 확인할 수 있습니다.
                과한 장식 대신 운영 판단에 필요한 정보 밀도를 우선했습니다.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="panel-strong p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Visibility</p>
              <p className="mt-3 text-lg font-semibold text-ink">Dashboard</p>
              <p className="mt-2 text-sm text-muted">최근 성공/실패 흐름과 주의 로그를 즉시 파악합니다.</p>
            </div>
            <div className="panel-strong p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Control</p>
              <p className="mt-3 text-lg font-semibold text-ink">API & DB</p>
              <p className="mt-2 text-sm text-muted">등록, 수정, 상태 전환, 연결 테스트를 한 곳에서 처리합니다.</p>
            </div>
            <div className="panel-strong p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Audit</p>
              <p className="mt-3 text-lg font-semibold text-ink">Logs</p>
              <p className="mt-2 text-sm text-muted">최근 실패와 인증 이벤트를 빠르게 검색하고 추적합니다.</p>
            </div>
          </div>
        </section>

        <section className="panel-strong flex items-center justify-center p-6 sm:p-10">
          <LoginForm />
        </section>
      </div>
    </main>
  );
}
