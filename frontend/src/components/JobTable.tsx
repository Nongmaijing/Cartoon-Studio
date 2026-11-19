import type { Job } from "../types";
import { ProgressBar, StatusBadge } from "./Ui";

function shortId(id: string) {
  return id.slice(0, 8);
}

function when(iso?: string | null) {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function elapsed(job: Job) {
  if (!job.started_at) return "—";
  const start = new Date(job.started_at).getTime();
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function JobTable({
  jobs,
  onCancel,
}: {
  jobs: Job[];
  onCancel?: (job: Job) => void;
}) {
  if (!jobs.length) {
    return <div className="empty">No generation jobs yet.</div>;
  }
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <thead>
          <tr>
            <th>Job</th>
            <th>Workflow</th>
            <th>Status</th>
            <th style={{ minWidth: 150 }}>Progress</th>
            <th>Elapsed</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const output = job.outputs?.[0];
            return (
              <tr key={job.id}>
                <td className="mono">{shortId(job.id)}</td>
                <td>
                  <div>{job.workflow_name || job.workflow_id}</div>
                  <div className="tiny muted">
                    {job.params?.positive_prompt ? String(job.params.positive_prompt).slice(0, 60) : ""}
                  </div>
                </td>
                <td>
                  <StatusBadge status={job.status} />
                  {job.error && (
                    <div className="tiny" style={{ color: "var(--danger)", marginTop: 4, maxWidth: 260 }}>
                      {job.error.slice(0, 140)}
                    </div>
                  )}
                </td>
                <td>
                  <ProgressBar value={job.status === "completed" ? 100 : job.progress} />
                  <div className="tiny muted" style={{ marginTop: 4 }}>
                    {job.status === "completed" ? "100%" : `${Math.round(job.progress)}%`}
                    {job.node ? ` · node ${job.node}` : ""}
                  </div>
                </td>
                <td className="muted">{elapsed(job)}</td>
                <td className="muted">{when(job.created_at)}</td>
                <td>
                  <div className="row" style={{ gap: 6 }}>
                    {output?.url && (
                      <a className="btn sm" href={output.url} target="_blank" rel="noreferrer">
                        Open output
                      </a>
                    )}
                    {(job.status === "running" || job.status === "queued") && onCancel && (
                      <button className="btn sm danger" onClick={() => onCancel(job)}>
                        Cancel
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
