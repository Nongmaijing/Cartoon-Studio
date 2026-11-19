import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { DashboardData, Job, Project, QueueState, WorkflowEntry } from "../types";
import { Gallery } from "../components/Gallery";
import { JobTable } from "../components/JobTable";
import { QueuePanel } from "../components/QueuePanel";
import { Alert, EmptyState, PageHeader, ProgressBar, StatCard } from "../components/Ui";

interface FormState {
  projectId: string;
  workflowId: string;
  prompt: string;
  negative: string;
  width: number;
  height: number;
  steps: number;
  cfg: number;
  seed: number;
  sampler: string;
  scheduler: string;
  length: number;
  fps: number;
}

const DEFAULT_PROMPT =
  "A cheerful cartoon fox in a red scarf standing in a sunny forest clearing, western 2D TV cartoon style, clean bold outlines, flat colors, expressive eyes, storybook lighting";

const IMAGE_DEFAULTS = { width: 512, height: 512, steps: 20, cfg: 7, sampler: "euler", scheduler: "normal" };
const SDXL_IMAGE_DEFAULTS = { width: 1024, height: 1024, steps: 28, cfg: 6, sampler: "dpmpp_2m", scheduler: "karras" };
function imageDefaults(workflow?: WorkflowEntry) {
  return workflow?.engine === "sdxl" ? SDXL_IMAGE_DEFAULTS : IMAGE_DEFAULTS;
}
const VIDEO_DEFAULTS = {
  width: 1280,
  height: 704,
  steps: 20,
  cfg: 5,
  sampler: "uni_pc",
  scheduler: "simple",
  length: 121,
  fps: 24,
};

function gb(bytes?: number) {
  return bytes ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : "—";
}

export default function Dashboard() {
  const { selectedId, selectProject } = useProject();
  const [data, setData] = useState<DashboardData | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowEntry[]>([]);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [setupLoading, setSetupLoading] = useState(true);
  const [form, setForm] = useState<FormState>({
    projectId: "",
    workflowId: "",
    prompt: DEFAULT_PROMPT,
    negative: "",
    seed: -1,
    ...IMAGE_DEFAULTS,
    length: 121,
    fps: 24,
  });

  const refresh = useCallback(async () => {
    try {
      const [result, queueResult] = await Promise.all([api.dashboard(), api.queue().catch(() => null)]);
      setData(result);
      if (queueResult) setQueue(queueResult);
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    Promise.all([api.projects(), api.workflows()])
      .then(([projectList, workflowList]) => {
        setProjects(projectList);
        setWorkflows(workflowList);
        const preferred =
          workflowList.find((item) => item.runnable && item.id === "sdxl_txt2img") ||
          workflowList.find((item) => item.runnable && item.id === "sd15_txt2img") ||
          workflowList.find((item) => item.runnable && item.kind === "image") ||
          workflowList.find((item) => item.runnable);
        setForm((current) => ({
          ...current,
          projectId: current.projectId || projectList[0]?.id || "",
          workflowId: current.workflowId || preferred?.id || "",
          ...(current.workflowId ? {} : imageDefaults(preferred)),
        }));
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)))
      .finally(() => setSetupLoading(false));
  }, []);

  useEffect(() => {
    if (selectedId) {
      setForm((current) => (current.projectId === selectedId ? current : { ...current, projectId: selectedId }));
    }
  }, [selectedId]);

  const selectedWorkflow = useMemo(
    () => workflows.find((item) => item.id === form.workflowId),
    [workflows, form.workflowId]
  );
  const isVideo = selectedWorkflow?.kind === "video";

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  const chooseWorkflow = (workflowId: string) => {
    const workflow = workflows.find((item) => item.id === workflowId);
    const defaults = workflow?.kind === "video" ? VIDEO_DEFAULTS : imageDefaults(workflow);
    setForm((current) => ({ ...current, workflowId, ...defaults }));
  };

  const submit = async () => {
    if (!form.projectId) {
      setError("Create a project first, then generate.");
      return;
    }
    if (!form.workflowId) {
      setError("No runnable workflow is available.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload: Record<string, unknown> = {
        project_id: form.projectId,
        workflow_id: form.workflowId,
        prompt: form.prompt,
        negative_prompt: form.negative || undefined,
        width: Number(form.width),
        height: Number(form.height),
        steps: Number(form.steps),
        cfg: Number(form.cfg),
        seed: Number(form.seed),
        sampler: form.sampler,
        scheduler: form.scheduler,
      };
      if (isVideo) {
        payload.length = Number(form.length);
        payload.fps = Number(form.fps);
      }
      const job = await api.generate(payload);
      setNotice(`Job ${job.id.slice(0, 8)} queued with ${job.workflow_name}.`);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (job: Job) => {
    try {
      await api.cancelJob(job.id);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const counts = data?.counts;
  const system = data?.system;
  const comfy = data?.comfyui;

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Create a project, describe a shot, and generate cartoon frames or clips with your local ComfyUI models."
        actions={
          <button className="btn ghost" onClick={refresh}>
            Refresh
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <div className="stat-grid">
        <StatCard label="Active projects" value={data ? counts?.projects ?? 0 : "—"} />
        <StatCard label="Characters" value={data ? counts?.characters ?? 0 : "—"} />
        <StatCard label="Backgrounds" value={data ? counts?.backgrounds ?? 0 : "—"} />
        <StatCard label="Scenes" value={data ? counts?.scenes ?? 0 : "—"} />
        <StatCard label="Completed episodes" value={data ? counts?.episodes ?? 0 : "—"} />
        <StatCard label="Outputs" value={data ? counts?.assets ?? 0 : "—"} />
      </div>

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>ComfyUI Connection</h2>
              <div className="panel-sub">{comfy?.server_url || "http://127.0.0.1:8188"}</div>
            </div>
            <span className="conn-pill">
              <span className={`dot ${comfy ? (comfy.connected ? "ok" : "bad") : "warn"}`} />
              {comfy ? (comfy.connected ? "Connected" : "Offline") : "Checking…"}
            </span>
          </div>
          {!comfy ? (
            <div className="empty">Checking ComfyUI…</div>
          ) : comfy.connected ? (
            <div className="kv">
              <span className="k">Version</span>
              <span className="v">{comfy.version}</span>
              <span className="k">Device</span>
              <span className="v">{comfy.devices?.[0]?.name || "—"}</span>
              <span className="k">VRAM</span>
              <span className="v">
                {comfy.devices?.[0]
                  ? `${(comfy.devices[0].vram_free / 1024 ** 3).toFixed(1)} GB free of ${(
                      comfy.devices[0].vram_total / 1024 ** 3
                    ).toFixed(1)} GB`
                  : "—"}
              </span>
              <span className="k">System RAM</span>
              <span className="v">{gb(comfy.ram_total)}</span>
            </div>
          ) : (
            <Alert kind="warn">
              {comfy?.error || "ComfyUI is not reachable. Start ComfyUI Desktop, then refresh."}
            </Alert>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>System</h2>
              <div className="panel-sub">Live host usage</div>
            </div>
          </div>
          <div className="stack">
            <div>
              <div className="meter-row">
                <span>RAM</span>
                <strong>
                  {system ? `${system.ram_used_gb} / ${system.ram_total_gb} GB` : "—"}
                </strong>
              </div>
              <ProgressBar value={system?.ram_percent ?? 0} />
            </div>
            <div>
              <div className="meter-row">
                <span>GPU utilization</span>
                <strong>{system?.gpu ? `${system.gpu.utilization_percent}%` : "—"}</strong>
              </div>
              <ProgressBar value={system?.gpu?.utilization_percent ?? 0} />
            </div>
            <div>
              <div className="meter-row">
                <span>VRAM</span>
                <strong>
                  {system?.gpu
                    ? `${system.gpu.vram_used_mb.toFixed(0)} / ${system.gpu.vram_total_mb.toFixed(0)} MB`
                    : "—"}
                </strong>
              </div>
              <ProgressBar
                value={
                  system?.gpu ? (100 * system.gpu.vram_used_mb) / Math.max(1, system.gpu.vram_total_mb) : 0
                }
              />
            </div>
            <div className="row between small muted">
              <span>CPU {system?.cpu_percent ?? 0}%</span>
              <span>{system?.gpu ? `${system.gpu.name} · ${system.gpu.temperature_c}°C` : "No NVIDIA GPU data"}</span>
            </div>
          </div>
        </section>
      </div>

      <div className="grid dash">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Quick Generate</h2>
              <div className="panel-sub">Local ComfyUI keyframes or Wan 2.2 clips</div>
            </div>
          </div>
          {setupLoading ? (
            <div className="empty">Loading project and workflows…</div>
          ) : projects.length === 0 ? (
            <EmptyState>
              You need a project before generating. <Link className="link" to="/projects">Create your first project</Link>.
            </EmptyState>
          ) : (
            <div className="stack">
              <div className="form-grid">
                <div className="field">
                  <label>Project</label>
                  <select
                    value={form.projectId}
                    onChange={(event) => {
                      set("projectId", event.target.value);
                      selectProject(event.target.value);
                    }}
                  >
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Workflow</label>
                  <select value={form.workflowId} onChange={(event) => chooseWorkflow(event.target.value)}>
                    {workflows.map((workflow) => (
                      <option key={workflow.id} value={workflow.id} disabled={!workflow.runnable}>
                        {workflow.name}
                        {workflow.runnable ? "" : " (unavailable)"}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field span-2">
                  <label>Prompt</label>
                  <textarea value={form.prompt} onChange={(event) => set("prompt", event.target.value)} />
                </div>
                <div className="field span-2">
                  <label>Negative prompt</label>
                  <input
                    value={form.negative}
                    placeholder="Leave blank to use the configured default"
                    onChange={(event) => set("negative", event.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Width</label>
                  <select value={form.width} onChange={(event) => set("width", Number(event.target.value))}>
                    {[512, 640, 768, 832, 1024, 1280].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Height</label>
                  <select value={form.height} onChange={(event) => set("height", Number(event.target.value))}>
                    {[512, 640, 704, 768, 832, 1024].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Steps</label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={form.steps}
                    onChange={(event) => set("steps", Number(event.target.value))}
                  />
                </div>
                <div className="field">
                  <label>CFG</label>
                  <input
                    type="number"
                    step={0.5}
                    value={form.cfg}
                    onChange={(event) => set("cfg", Number(event.target.value))}
                  />
                </div>
                <div className="field">
                  <label>Seed (-1 = random)</label>
                  <input
                    type="number"
                    value={form.seed}
                    onChange={(event) => set("seed", Number(event.target.value))}
                  />
                </div>
                <div className="field">
                  <label>Sampler</label>
                  <input value={form.sampler} onChange={(event) => set("sampler", event.target.value)} />
                </div>
                <div className="field">
                  <label>Scheduler</label>
                  <input value={form.scheduler} onChange={(event) => set("scheduler", event.target.value)} />
                </div>
                {isVideo && (
                  <>
                    <div className="field">
                      <label>Frames (4n+1)</label>
                      <input
                        type="number"
                        value={form.length}
                        onChange={(event) => set("length", Number(event.target.value))}
                      />
                    </div>
                    <div className="field">
                      <label>FPS</label>
                      <input
                        type="number"
                        value={form.fps}
                        onChange={(event) => set("fps", Number(event.target.value))}
                      />
                    </div>
                  </>
                )}
              </div>
              {isVideo && (
                <Alert kind="warn">
                  Video generation on 6 GB VRAM can take 20+ minutes per clip. Frames must satisfy 4n+1 (121, 161…).
                </Alert>
              )}
              <div className="row between">
                <span className="tiny muted">
                  {selectedWorkflow?.runnable === false
                    ? "This workflow is missing models or nodes."
                    : "Runs on the local ComfyUI server."}
                </span>
                <button className="btn primary" onClick={submit} disabled={busy}>
                  {busy ? "Submitting…" : isVideo ? "Generate video" : "Generate image"}
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Job Queue</h2>
              <div className="panel-sub">One GPU job at a time</div>
            </div>
            {queue && (
              <span className="chip">
                {queue.counts.running} running · {queue.counts.queued} queued
              </span>
            )}
          </div>
          <QueuePanel queue={queue} onCancel={cancel} idleText="Queue idle. Submit a prompt to start generating." />
        </section>
      </div>

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Recent Jobs</h2>
            <div className="panel-sub">Latest generation activity</div>
          </div>
          <Link className="btn sm ghost" to="/workflows">
            Workflows
          </Link>
        </div>
        <JobTable jobs={data?.recent_jobs ?? []} onCancel={cancel} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Recent Outputs</h2>
            <div className="panel-sub">Saved under CartoonStudio\outputs</div>
          </div>
        </div>
        <Gallery assets={data?.recent_assets ?? []} />
      </section>
    </>
  );
}
