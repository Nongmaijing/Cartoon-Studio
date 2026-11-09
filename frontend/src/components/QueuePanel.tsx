import type { Job, QueueState } from "../types";
import { EmptyState, ProgressBar, StatusBadge } from "./Ui";

export function elapsedSeconds(job: Job): number | null {
  if (!job.started_at) return null;
  const start = new Date(job.started_at).getTime();
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  return Math.max(0, Math.round((end - start) / 1000));
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export function etaSeconds(job: Job): number | null {
  if (job.status !== "running" || !job.started_at || job.progress < 2) return null;
  const elapsed = elapsedSeconds(job);
  if (elapsed === null) return null;
  const total = elapsed / (job.progress / 100);
  return Math.max(0, Math.round(total - elapsed));
}

function QueueRow({ job, onCancel }: { job: Job; onCancel?: (job: Job) => void }) {
  const running = job.status === "running";
  const elapsed = elapsedSeconds(job);
  const eta = etaSeconds(job);
  return (
    <div className={`queue-row${running ? " running" : ""}`}>
      <div className="queue-main">
        <div className="row between">
          <div className="queue-title">
            <span className="mono">{job.id.slice(0, 8)}</span>
            <span className="queue-workflow">{job.workflow_name || job.workflow_id}</span>
          </div>
          <div className="row">
            {job.status === "queued" && job.queue_position ? (
              <span className="chip">position {job.queue_position}</span>
            ) : null}
            <StatusBadge status={job.status} />
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <ProgressBar value={running ? job.progress : 0} />
        </div>
        <div className="row between tiny muted" style={{ marginTop: 6 }}>
          <span>
            {running
              ? `${Math.round(job.progress)}%${job.node ? ` · node ${job.node}` : ""}`
              : "Waiting for the current GPU job"}
          </span>
          <span>
            {running
              ? `${formatDuration(elapsed)} elapsed${eta !== null ? ` · ~${formatDuration(eta)} left` : ""}`
              : "Queued"}
          </span>
        </div>
        {job.error && (
          <div className="tiny" style={{ color: "var(--danger)", marginTop: 6 }}>
            {job.error.slice(0, 220)}
          </div>
        )}
      </div>
      {onCancel && (job.status === "running" || job.status === "queued") && (
        <button className="btn sm danger" onClick={() => onCancel(job)}>
          Cancel
        </button>
      )}
    </div>
  );
}

export function QueuePanel({
  queue,
  onCancel,
  idleText = "Queue idle. Submit a job to start generating.",
}: {
  queue: QueueState | null;
  onCancel?: (job: Job) => void;
  idleText?: string;
}) {
  if (!queue) return <EmptyState>Loading queue…</EmptyState>;
  if (!queue.running && queue.pending.length === 0) {
    return <EmptyState>{idleText}</EmptyState>;
  }
  return (
    <div className="queue-list">
      {queue.running && <QueueRow job={queue.running} onCancel={onCancel} />}
      {queue.pending.map((job) => (
        <QueueRow key={job.id} job={job} onCancel={onCancel} />
      ))}
    </div>
  );
}
