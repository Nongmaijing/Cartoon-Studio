import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Asset, Character, EnginesResponse, Job, QueueState, Scene } from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";
import { JobTable } from "../components/JobTable";
import { QueuePanel, elapsedSeconds, etaSeconds, formatDuration } from "../components/QueuePanel";

const VIDEO_SIZES = [
  { label: "832×480 · 480p", width: 832, height: 480 },
  { label: "640×384 · small", width: 640, height: 384 },
  { label: "320×192 · pipeline test", width: 320, height: 192 },
  { label: "1280×704 · 720p", width: 1280, height: 704 },
];

const FRAME_PRESETS = [
  { value: 5, label: "5 frames · pipeline test" },
  { value: 49, label: "49 frames · ~2s" },
  { value: 81, label: "81 frames · ~3.4s" },
  { value: 121, label: "121 frames · ~5s" },
];

const DEFAULT_PROMPT =
  "A cheerful cartoon fox in a red scarf runs through a sunlit forest clearing, leaves swirling behind, western 2D TV cartoon style, clean bold outlines, flat colors";

interface EngineCard {
  key: string;
  title: string;
  info: EnginesResponse[keyof Omit<EnginesResponse, "workflows">];
}

function isActive(job: Job | null): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

function EnginePanel({ card }: { card: EngineCard }) {
  const { info } = card;
  const missing = info.missing_nodes || [];
  return (
    <div className={`engine-card${info.available ? " available" : ""}`}>
      <div className="row between">
        <strong>{card.title}</strong>
        <span className={`chip ${info.available ? "exp" : ""}`}>
          {info.available ? "ready" : "not installed"}
        </span>
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>
        {info.notes}
      </div>
      {card.key === "wan22" && (
        <div className="tiny" style={{ marginTop: 8 }}>
          {Object.entries(info.expected).map(([role, value]) => (
            <div key={role} className="row between" style={{ gap: 8 }}>
              <span className="muted">{role}</span>
              <span className="mono wrap" style={{ textAlign: "right" }}>
                {value}
              </span>
            </div>
          ))}
        </div>
      )}
      {missing.length > 0 && (
        <div className="tiny muted" style={{ marginTop: 8 }}>
          Missing nodes: {missing.slice(0, 6).join(", ")}
          {missing.length > 6 ? ` +${missing.length - 6}` : ""}
        </div>
      )}
    </div>
  );
}

export default function Animation() {
  const { selectedId, projects } = useProject();
  const [engines, setEngines] = useState<EnginesResponse | null>(null);
  const [engineError, setEngineError] = useState("");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [images, setImages] = useState<Asset[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [queue, setQueue] = useState<QueueState | null>(null);

  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [negative, setNegative] = useState("");
  const [width, setWidth] = useState(832);
  const [height, setHeight] = useState(480);
  const [steps, setSteps] = useState(20);
  const [cfg, setCfg] = useState(5);
  const [seed, setSeed] = useState(-1);
  const [length, setLength] = useState(5);
  const [fps, setFps] = useState(24);
  const [sampler, setSampler] = useState("uni_pc");
  const [scheduler, setScheduler] = useState("simple");
  const [startImage, setStartImage] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [workflowId, setWorkflowId] = useState("");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [mode, setMode] = useState("");

  const videoWorkflows = engines?.workflows ?? [];
  const imageToVideo = useMemo(
    () => videoWorkflows.filter((workflow) => /\bi2v\b|image-to-video/i.test(`${workflow.id} ${workflow.name}`)),
    [videoWorkflows]
  );
  const textToVideo = useMemo(
    () => videoWorkflows.filter((workflow) => /\bt2v\b|text-to-video/i.test(`${workflow.id} ${workflow.name}`)),
    [videoWorkflows]
  );

  const needsStartImage = (workflow?: (typeof videoWorkflows)[number]) =>
    /\bi2v\b|image-to-video/i.test(`${workflow?.id || ""} ${workflow?.name || ""}`);
  const selectedWorkflow = videoWorkflows.find((workflow) => workflow.id === workflowId);
  const workflowCompatible = Boolean(selectedWorkflow) && needsStartImage(selectedWorkflow) === Boolean(startImage);

  useEffect(() => {
    if (!videoWorkflows.length) return;
    if (selectedWorkflow && needsStartImage(selectedWorkflow) === Boolean(startImage)) return;
    const candidate = videoWorkflows.find(
      (workflow) =>
        workflow.valid &&
        workflow.runnable !== false &&
        needsStartImage(workflow) === Boolean(startImage)
    );
    if (candidate) setWorkflowId(candidate.id);
  }, [videoWorkflows, startImage, selectedWorkflow]);

  const loadEngines = useCallback(async () => {
    try {
      const result = await api.engines();
      setEngines(result);
      setEngineError("");
      setWorkflowId((current) => {
        if (current && result.workflows.some((workflow) => workflow.id === current)) return current;
        return (
          result.workflows.find((workflow) => workflow.valid && workflow.runnable)?.id ||
          result.workflows.find((workflow) => workflow.valid)?.id ||
          result.workflows[0]?.id ||
          ""
        );
      });
    } catch (exc) {
      setEngineError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const list = await api.animationJobs(selectedId || undefined, 30);
      setJobs(list);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  useEffect(() => {
    loadEngines();
  }, [loadEngines]);

  useEffect(() => {
    if (!selectedId) {
      setScenes([]);
      setImages([]);
      setCharacters([]);
      setJobs([]);
      return;
    }
    Promise.all([api.scenes(selectedId), api.assets(60, selectedId, "image"), api.characters(selectedId)])
      .then(([sceneList, assetList, characterList]) => {
        setScenes(sceneList);
        setImages(assetList);
        setCharacters(characterList);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
    loadJobs();
  }, [selectedId, loadJobs]);

  useEffect(() => {
    const refreshQueue = () => api.queue().then(setQueue).catch(() => undefined);
    refreshQueue();
    const timer = window.setInterval(refreshQueue, 2000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!activeJob || !isActive(activeJob)) return;
    const jobId = activeJob.id;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.job(jobId);
        setActiveJob(job);
        if (["completed", "failed", "cancelled", "interrupted"].includes(job.status)) {
          window.clearInterval(timer);
          await loadJobs();
          if (job.status === "completed") {
            setNotice("Clip finished and saved to the project outputs.");
            setError("");
          } else if (job.status === "failed") {
            setError(job.error || "Animation failed.");
          }
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
        window.clearInterval(timer);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob?.id, activeJob?.status, loadJobs]);

  const applySize = (index: number) => {
    const size = VIDEO_SIZES[index];
    if (!size) return;
    setWidth(size.width);
    setHeight(size.height);
  };

  const submit = async () => {
    if (!selectedId || !prompt.trim()) return;
    if (!workflowCompatible) {
      setError("Choose a workflow that matches the start-image setting.");
      return;
    }
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const result = await api.animationGenerate({
        project_id: selectedId,
        workflow_id: workflowId || undefined,
        prompt: prompt.trim(),
        negative_prompt: negative.trim() || undefined,
        width,
        height,
        steps,
        cfg,
        seed,
        length,
        fps,
        sampler,
        scheduler,
        start_image: startImage || undefined,
        scene_id: sceneId || undefined,
      });
      setActiveJob(result.job);
      setMode(result.mode);
      setNotice(
        result.input_image
          ? "Image-to-video job queued. The start image was uploaded to ComfyUI."
          : "Text-to-video job queued."
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSubmitting(false);
    }
  };

  const cancel = async (job: Job) => {
    try {
      await api.cancelJob(job.id);
      setQueue(await api.queue());
      await loadJobs();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Animation" subtitle="Animate cartoon frames and shots with local ComfyUI engines." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          animating.
        </EmptyState>
      </>
    );
  }

  const cards: EngineCard[] = engines
    ? [
        { key: "wan22", title: "Wan 2.2 TI2V-5B", info: engines.wan22 },
        { key: "animatediff", title: "AnimateDiff", info: engines.animatediff },
        { key: "ipadapter", title: "IPAdapter", info: engines.ipadapter },
        { key: "controlnet", title: "ControlNet", info: engines.controlnet },
      ]
    : [];

  return (
    <>
      <PageHeader
        title="Animation"
        subtitle="Generate motion clips with Wan 2.2, or inspect optional engines. One GPU-heavy job runs at a time."
        actions={
          <button className="btn" onClick={loadEngines}>
            Re-check engines
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Engine Availability</h2>
            <div className="panel-sub">Detected from the live ComfyUI server — nothing is assumed or downloaded.</div>
          </div>
        </div>
        {engineError && <Alert kind="error">{engineError}</Alert>}
        {!engines && !engineError && <EmptyState>Checking installed engines…</EmptyState>}
        {engines && (
          <div className="engine-grid">
            {cards.map((card) => (
              <EnginePanel key={card.key} card={card} />
            ))}
          </div>
        )}
      </section>

      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>New Clip</h2>
              <div className="panel-sub">Text-to-video invents motion; image-to-video starts from a project image.</div>
            </div>
            {activeJob && <StatusBadge status={activeJob.status} />}
          </div>

          {activeJob && (
            <div className="stack" style={{ marginBottom: 14 }}>
              <div className="meter-row">
                <span className="mono">{activeJob.id.slice(0, 8)}</span>
                <strong>{Math.round(activeJob.progress)}%</strong>
              </div>
              <ProgressBar value={activeJob.status === "completed" ? 100 : activeJob.progress} />
              <div className="row between tiny muted">
                <span>
                  {activeJob.status === "running"
                    ? `${formatDuration(elapsedSeconds(activeJob))} elapsed · node ${activeJob.node || "—"}`
                    : activeJob.status}
                </span>
                <span>
                  {activeJob.status === "running" && etaSeconds(activeJob) !== null
                    ? `~${formatDuration(etaSeconds(activeJob))} left`
                    : mode}
                </span>
              </div>
              {activeJob.status === "failed" && (
                <div className="tiny" style={{ color: "var(--danger)" }}>{activeJob.error}</div>
              )}
            </div>
          )}

          <div className="form-grid">
            <div className="field span-2">
              <label>Prompt</label>
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            </div>
            <div className="field span-2">
              <label>Negative prompt</label>
              <input
                value={negative}
                placeholder="Leave empty to use the built-in video negative prompt"
                onChange={(event) => setNegative(event.target.value)}
              />
            </div>
            <div className="field">
              <label>Workflow</label>
              <select value={workflowId} onChange={(event) => setWorkflowId(event.target.value)}>
                <option value="">Auto (based on start image)</option>
                {videoWorkflows.map((workflow) => (
                  <option
                    key={workflow.id}
                    value={workflow.id}
                    disabled={
                      !workflow.valid ||
                      workflow.runnable === false ||
                      needsStartImage(workflow) !== Boolean(startImage)
                    }
                  >
                    {workflow.name}
                    {needsStartImage(workflow) !== Boolean(startImage)
                      ? startImage
                        ? " (text-to-video)"
                        : " (needs start image)"
                      : ""}
                    {!workflow.valid
                      ? " (invalid)"
                      : workflow.runnable === false
                      ? ` (unavailable${workflow.missing_nodes.length ? `: ${workflow.missing_nodes.join(", ")}` : ""})`
                      : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Resolution</label>
              <select
                value={VIDEO_SIZES.findIndex((size) => size.width === width && size.height === height)}
                onChange={(event) => applySize(Number(event.target.value))}
              >
                {VIDEO_SIZES.map((size, index) => (
                  <option key={size.label} value={index}>
                    {size.label}
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
                value={steps}
                onChange={(event) => setSteps(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>CFG</label>
              <input
                type="number"
                step={0.5}
                value={cfg}
                onChange={(event) => setCfg(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Seed (-1 = random)</label>
              <input
                type="number"
                value={seed}
                onChange={(event) => setSeed(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Frames</label>
              <select value={length} onChange={(event) => setLength(Number(event.target.value))}>
                {FRAME_PRESETS.map((preset) => (
                  <option key={preset.value} value={preset.value}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>FPS</label>
              <input
                type="number"
                min={1}
                max={60}
                value={fps}
                onChange={(event) => setFps(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Sampler</label>
              <input value={sampler} onChange={(event) => setSampler(event.target.value)} />
            </div>
            <div className="field">
              <label>Scheduler</label>
              <input value={scheduler} onChange={(event) => setScheduler(event.target.value)} />
            </div>
            <div className="field span-2">
              <label>Start image (image-to-video)</label>
              <select value={startImage} onChange={(event) => setStartImage(event.target.value)}>
                <option value="">None — text-to-video</option>
                {characters.some((character) => character.canonical_asset_id) && (
                  <optgroup label="Character identity (canonical)">
                    {characters
                      .filter((character) => character.canonical_asset_id)
                      .map((character) => (
                        <option key={character.id} value={character.canonical_asset_id || ""}>
                          {character.name} · identity
                        </option>
                      ))}
                  </optgroup>
                )}
                <optgroup label="Project images">
                  {images.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.filename}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
            <div className="field span-2">
              <label>Attach result to scene (optional)</label>
              <select value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
                <option value="">Keep clip at project level</option>
                {scenes.map((scene) => (
                  <option key={scene.id} value={scene.id}>
                    {scene.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <Alert kind="warn">
            Wan 2.2 on 6 GB VRAM is slow: 121 frames at 720p can take 20+ minutes. Start with the 5-frame
            320×192 pipeline test.
          </Alert>

          <div className="row between" style={{ marginTop: 12 }}>
            <span className="tiny muted">
              {startImage ? "Image-to-video: the chosen image becomes frame one." : "Text-to-video: Wan invents the motion."}
              {!workflowCompatible && " The selected workflow does not match the start-image setting."}
              {imageToVideo.length === 0 && startImage ? " No i2v workflow found." : ""}
              {textToVideo.length === 0 && !startImage ? " No t2v workflow found." : ""}
            </span>
            <button className="btn primary" onClick={submit} disabled={submitting || isActive(activeJob) || !prompt.trim() || !workflowCompatible}>
              {submitting ? "Queuing…" : isActive(activeJob) ? "Generating…" : "Generate clip"}
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Queue</h2>
              <div className="panel-sub">One GPU job at a time</div>
            </div>
            {queue && (
              <span className="chip">
                {queue.counts.running} running · {queue.counts.queued} queued
              </span>
            )}
          </div>
          <QueuePanel queue={queue} onCancel={cancel} idleText="Queue idle. Submit a clip to start animating." />
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Recent Clips</h2>
            <div className="panel-sub">Animation jobs for {projects.find((project) => project.id === selectedId)?.name}</div>
          </div>
        </div>
        <JobTable jobs={jobs} onCancel={cancel} />
      </section>
    </>
  );
}
