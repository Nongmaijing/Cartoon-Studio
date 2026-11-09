import type { ReactNode } from "react";
import { PageHeader } from "./Ui";
import { Icon, type IconName } from "./Icons";

export function Placeholder({
  title,
  icon,
  phase,
  summary,
  features,
  children,
}: {
  title: string;
  icon: IconName;
  phase: string;
  summary: string;
  features: string[];
  children?: ReactNode;
}) {
  return (
    <>
      <PageHeader
        title={title}
        subtitle="This module is part of the Cartoon Studio production pipeline. Phase 1 focuses on the shell, ComfyUI connection, workflows and image generation."
      />
      <div className="phase-hero">
        <div className="phase-icon">
          <Icon name={icon} size={24} />
        </div>
        <div>
          <span className="phase-badge">Phase {phase}</span>
          <p className="page-sub" style={{ marginTop: 10 }}>
            {summary}
          </p>
          <ul className="feature-list">
            {features.map((feature) => (
              <li key={feature}>{feature}</li>
            ))}
          </ul>
        </div>
      </div>
      {children}
    </>
  );
}
