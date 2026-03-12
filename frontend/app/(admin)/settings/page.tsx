import { AccountSecurityCard } from "@/components/account-security-card";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";


export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="보안 및 운영 설정"
        description="관리자 계정 보안과 서버 운영 자동화 상태를 확인하는 화면입니다."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <AccountSecurityCard />

        <SectionCard title="운영 자동화 메모" description="서버 측 자동화 항목 요약입니다.">
          <div className="space-y-4 text-sm leading-6 text-muted">
            <p>SQLite 백업은 `cron`으로 매일 실행되고, 생성된 `.gz` 파일은 원격 스토리지 업로드를 시도할 수 있습니다.</p>
            <p>백업/업데이트 로그는 `/var/log/my-api/*.log`로 모아두고 `logrotate`로 압축 순환합니다.</p>
            <p>장애 알림은 `/etc/my-api/ops.env`에 웹훅을 넣으면 활성화됩니다. 현재는 자격증명/웹훅 입력 전까지는 비활성 상태여도 안전하게 동작합니다.</p>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
