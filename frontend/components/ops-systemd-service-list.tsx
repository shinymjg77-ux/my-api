import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import type { OpsServiceStatus } from "@/lib/types";


interface OpsSystemdServiceListProps {
  services: OpsServiceStatus[];
}


export function OpsSystemdServiceList({ services }: OpsSystemdServiceListProps) {
  if (services.length === 0) {
    return <EmptyState title="추적 중인 systemd 서비스가 없습니다." description="OPS_SYSTEMD_UNITS 설정을 확인하세요." />;
  }

  return (
    <div className="space-y-3">
      {services.map((service) => (
        <div key={service.name} className="rounded-2xl border border-line bg-panelStrong p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-ink">{service.name}</p>
                <StatusBadge tone={service.is_healthy ? "success" : "danger"}>
                  {service.is_healthy ? "healthy" : "degraded"}
                </StatusBadge>
              </div>
              <p className="text-sm leading-6 text-muted">{service.description || "설명 없음"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone={service.active_state === "active" ? "success" : "danger"}>
                {service.active_state}
              </StatusBadge>
              <StatusBadge tone="muted">{service.sub_state}</StatusBadge>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
