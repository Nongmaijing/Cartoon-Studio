import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type {
  Asset,
  FastModeStatus,
  ModelCatalog,
  ModelConfig,
  ModelDownload,
  ModelFileEntry,
  ModelLists,
  ModelRecommendation,
  ProductionRegistry,
  QueueState,
  WorkflowEntry,
} from "../types";
import { Alert, EmptyState, PageHeader } from "../components/Ui";

const PRESET_KEYS = [
  "sdxl_character",
  "sdxl_portrait",
  "sdxl_background",
  "sdxl_scene",
  "sd15_character",
  "sd15_background",
  "sd15_scene",
];

const WORKFLOW_KEYS: Array<{ key: string; label: string }> = [
  { key: "character_txt2img", label: "Character text-to-image" },
  { key: "character_img2img", label: "Character reference / img2img" },
  { key: "expression", label: "Expression sheet" },
  { key: "pose", label: "Pose sheet" },
  { key: "background", label: "Background" },
  { key: "scene", label: "Scene / keyframe" },
];

function formatSize(entry: ModelFileEntry): string {
  if (!entry.size_gb) return "—";
  return `${entry.size_gb.toFixed(2)} GB`;
}

function archLabel(value: string): string {
  if (value === "sdxl") return "SDXL";
  if (value === "sd15") return "SD 1.5";
  if (value === "wan") return "Wan";
  if (value === "flux") return "FLUX";
  return "Unknown";
}

function statusChip(status: string): string {
  if (status === "ready") return "exp";
  if (status === "partial") return "ref";
  return "pose";
}

function formatBytes(value: number): string {
  if (!value) return "0 MB";
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
  return `${(value / 1024 ** 2).toFixed(0)} MB`;
}

export default function Models() {
  const { selectedId } = useProject();
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowEntry[]>([]);
  const [modelLists, setModelLists] = useState<ModelLists | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [queueState, setQueueState] = useState<QueueState | null>(null);
  const [registry, setRegistry] = useState<ProductionRegistry | null>(null);
  const [freeing, setFreeing] = useState(false);
  const [visionResult, setVisionResult] = useState<Record<string, any> | null>(null);
  const [visionAsset, setVisionAsset] = useState<string>("");
  const [visionBusy, setVisionBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloads, setDownloads] = useState<ModelDownload[]>([]);
  const [downloadTarget, setDownloadTarget] = useState<ModelRecommendation | null>(null);
  const [licenseAccepted, setLicenseAccepted] = useState(false);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [fastMode, setFastMode] = useState<FastModeStatus | null>(null);
  const [fastBusy, setFastBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const cat = await api.modelCatalog();
      setCatalog(cat);
      setConfig(cat.config);
      const [wfResult, listResult, assetResult] = await Promise.allSettled([
        api.workflows(),
        api.models(),
        api.assets(8, selectedId || undefined, "image"),
      ]);
      if (wfResult.status === "fulfilled") setWorkflows(wfResult.value);
      if (listResult.status === "fulfilled") setModelLists(listResult.value);
      if (assetResult.status === "fulfilled") setAssets(assetResult.value);
      try {
        setQueueState(await api.queue());
      } catch {
        setQueueState(null);
      }
      try {
        setRegistry(await api.productionRegistry());
      } catch {
        setRegistry(null);
      }
      try {
        setFastMode(await api.fastMode());
      } catch {
        setFastMode(null);
      }
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshDownloads = useCallback(async () => {
    try {
      setDownloads(await api.modelDownloads());
    } catch {
      /* the catalog is still usable if download state is unavailable */
    }
  }, []);

  useEffect(() => {
    refreshDownloads();
  }, [refreshDownloads]);

  const activeDownload = downloads.some((item) =>
    ["queued", "downloading", "verifying"].includes(item.status)
  );

  useEffect(() => {
    if (!activeDownload) return;
    let disposed = false;
    const tick = async () => {
      try {
        const list = await api.modelDownloads();
        if (disposed) return;
        setDownloads(list);
        if (!list.some((item) => ["queued", "downloading", "verifying"].includes(item.status))) {
          load();
        }
      } catch {
        /* keep polling; transient network errors should not stop a download */
      }
    };
    const timer = window.setInterval(tick, 2000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [activeDownload, load]);

  const downloadFor = (name: string): ModelDownload | undefined => {
    const matches = downloads.filter((item) => item.recommendation === name);
    return (
      matches.find((item) => ["queued", "downloading", "verifying"].includes(item.status)) ||
      matches[0]
    );
  };

  const beginDownload = (item: ModelRecommendation) => {
    setDownloadTarget(item);
    setLicenseAccepted(false);
    setDownloadError("");
  };

  const submitDownload = async () => {
    if (!downloadTarget || !licenseAccepted) return;
    setDownloadBusy(true);
    setDownloadError("");
    try {
      const state = await api.startModelDownload(downloadTarget.name, licenseAccepted);
      setDownloads((current) => [state, ...current.filter((item) => item.id !== state.id)]);
      setDownloadTarget(null);
    } catch (exc) {
      setDownloadError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setDownloadBusy(false);
    }
  };

  const cancelDownload = async (id: string) => {
    try {
      const state = await api.cancelModelDownload(id);
      setDownloads((current) => current.map((item) => (item.id === state.id ? state : item)));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const checkpoints = catalog?.models.checkpoints || [];
  const vaes = catalog?.models.vae || [];
  const loras = catalog?.models.loras || [];
  const controlnets = catalog?.models.controlnet || [];
  const upscalers = catalog?.models.upscale_models || [];
  const imageWorkflows = useMemo(
    () => workflows.filter((workflow) => workflow.kind === "image" && workflow.format === "api"),
    [workflows]
  );
  const samplers = modelLists?.samplers || ["dpmpp_2m", "euler", "dpmpp_sde", "uni_pc"];
  const schedulers = modelLists?.schedulers || ["karras", "normal", "simple", "sgm_uniform"];
  const gpu = catalog?.comfyui?.gpu || {};
  const flags = catalog?.comfyui?.flags || {};
  const active = catalog?.active || {};

  const setModel = (key: keyof ModelConfig, value: unknown) => {
    setConfig((current) => (current ? { ...current, [key]: value } : current));
  };
  const setCheckpoint = (architecture: string, value: string) => {
    setConfig((current) =>
      current ? { ...current, checkpoints: { ...current.checkpoints, [architecture]: value } } : current
    );
  };
  const setVae = (architecture: string, value: string) => {
    setConfig((current) =>
      current ? { ...current, vae: { ...current.vae, [architecture]: value } } : current
    );
  };
  const setLora = (key: string, value: unknown) => {
    setConfig((current) =>
      current ? { ...current, lora: { ...current.lora, [key]: value } as ModelConfig["lora"] } : current
    );
  };
  const setWorkflow = (key: string, value: string) => {
    setConfig((current) =>
      current ? { ...current, workflows: { ...current.workflows, [key]: value } } : current
    );
  };
  const setPreset = (presetKey: string, field: string, value: unknown) => {
    setConfig((current) => {
      if (!current) return current;
      const presets = { ...current.presets };
      presets[presetKey] = { ...(presets[presetKey] || {}), [field]: value };
      return { ...current, presets };
    });
  };

  const toggleFastMode = async (payload: { enabled?: boolean; steps?: number }) => {
    setFastBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await api.setFastMode(payload);
      setFastMode(next);
      setNotice(
        next.enabled
          ? `Fast mode on · ${next.steps} steps, CFG ${next.cfg}, ${next.sampler}/${next.scheduler}.`
          : "Fast mode off. SDXL renders use the full step count again."
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setFastBusy(false);
    }
  };

  const freeVram = async () => {
    setFreeing(true);
    setError("");
    setNotice("");
    try {
      const result = await api.freeResources();
      if (result.ok) {
        setNotice("ComfyUI models unloaded and VRAM released.");
      } else {
        setError(String(result.error || "Could not free VRAM."));
      }
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setFreeing(false);
    }
  };

  const reviewImage = async (assetId: string) => {
    setVisionBusy(true);
    setVisionResult(null);
    setVisionAsset(assetId);
    setError("");
    try {
      const result = await api.visionReview(assetId);
      setVisionResult(result);
      setNotice("Vision review complete. AI review never auto-approves an asset.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setVisionBusy(false);
    }
  };

  const save = async () => {    if (!config) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const result = await api.saveModelConfig(config);
      setConfig(result.models);
      await load();
      setNotice("Model configuration saved. New generations will use it.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  };

  const compatible = (entry: ModelFileEntry, architecture: string) =>
    entry.architecture === architecture || entry.architecture === "unknown";

  const checkpointOptions = (architecture: string) =>
    checkpoints.filter((entry) => compatible(entry, architecture) && entry.installed_in_comfy);

  const vaeOptions = (architecture: string) =>
    vaes.filter((entry) => compatible(entry, architecture) && entry.installed_in_comfy);

  if (loading && !catalog) {
    return (
      <>
        <PageHeader title="Model Studio" subtitle="Discover installed models and configure SDXL or SD 1.5." />
        <div className="empty">Scanning ComfyUI model directories…</div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Model Studio"
        subtitle="Discover installed checkpoints, choose SDXL or SD 1.5, and configure 6 GB-safe presets. Nothing is downloaded automatically."
        actions={
          <>
            <button className="btn ghost" onClick={freeVram} disabled={freeing}>
              {freeing ? "Freeing…" : "Free VRAM"}
            </button>
            <button className="btn ghost" onClick={load} disabled={loading}>
              {loading ? "Scanning…" : "Refresh catalog"}
            </button>
            <button className="btn primary" onClick={save} disabled={saving || !config}>
              {saving ? "Saving…" : "Save model config"}
            </button>
          </>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      {registry && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>Production Registry</h2>
              <div className="panel-sub">
                Department readiness and candidate models. Read-only; nothing is installed automatically.
              </div>
            </div>
            <div className="row">
              <span className="chip exp">{registry.summary.ready} ready</span>
              <span className="chip ref">{registry.summary.partial} partial</span>
              <span className="chip pose">{registry.summary.blocked} blocked</span>
            </div>
          </div>
          <div className="kv" style={{ marginBottom: 12 }}>
            <span className="k">GPU</span>
            <span className="v">
              {registry.resources?.gpu?.name || "offline"} ·{" "}
              {registry.resources?.gpu?.vram_total_gb
                ? `${registry.resources.gpu.vram_free_gb} GB free of ${registry.resources.gpu.vram_total_gb} GB`
                : "VRAM unavailable"}
            </span>
            <span className="k">System RAM</span>
            <span className="v">
              {registry.resources?.ram?.available_gb} GB available of {registry.resources?.ram?.total_gb} GB
            </span>
            <span className="k">Local LLMs</span>
            <span className="v">
              {(registry.llm?.ollama?.models || []).map((model: Record<string, any>) => model.name).join(", ") || "none"}
            </span>
            <span className="k">Vision models</span>
            <span className="v">
              {(registry.llm?.ollama?.models || [])
                .filter((model: Record<string, any>) => (model.capabilities || []).includes("vision"))
                .map((model: Record<string, any>) => model.name)
                .join(", ") || "none"}
            </span>
            <span className="k">Ready TTS</span>
            <span className="v">
              {registry.tts.filter((engine) => engine.status === "ready").map((engine) => engine.name).join(", ") || "none"}
            </span>
          </div>
          <div className="grid two">
            {registry.departments.map((department) => (
              <div className="ai-provider" key={department.id}>
                <div className="row between">
                  <strong>{department.name}</strong>
                  <span className={`chip ${statusChip(department.status)}`}>{department.status}</span>
                </div>
                <div className="tiny muted">{department.summary}</div>
                <div className="tiny">
                  Installed: {department.installed.length} · Missing/candidates: {department.missing.length}
                </div>
                {department.recommendations.length > 0 && (
                  <details className="ai-tool-details">
                    <summary>{department.recommendations.length} candidate model(s)</summary>
                    {department.recommendations.slice(0, 6).map((rec, index) => (
                      <div className="ai-tool" key={`${department.id}-${index}`}>
                        <div>
                          <strong>{String(rec.name || "candidate")}</strong>
                          <div className="tiny muted">{String(rec.license || "license not recorded")}</div>
                        </div>
                        <span className="tiny">{String(rec.vram || rec.download_size || "")}</span>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            ))}
          </div>
          <div className="tiny muted" style={{ marginTop: 10 }}>{registry.note}</div>
        </section>
      )}

      {catalog && (
        <div className="grid two" style={{ marginBottom: 16 }}>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Active Model</h2>
                <div className="panel-sub">What the next generation will use</div>
              </div>
              <span className={`chip ${active.architecture === "sdxl" ? "exp" : "ref"}`}>
                {archLabel(String(active.architecture || "unknown"))}
              </span>
            </div>
            <div className="kv">
              <span className="k">Architecture</span>
              <span className="v">{archLabel(String(active.architecture || "unknown"))}</span>
              <span className="k">Checkpoint</span>
              <span className="v mono wrap">{active.checkpoint || "not configured"}</span>
              <span className="k">Character workflow</span>
              <span className="v mono">{active.workflow_id || "not resolved"}</span>
              <span className="k">Fallback</span>
              <span className="v">{active.fallback_reason || "none"}</span>
              <span className="k">GPU</span>
              <span className="v">{gpu.name || "ComfyUI offline"}</span>
              <span className="k">VRAM</span>
              <span className="v">
                {gpu.vram_total_gb ? `${gpu.vram_used ? (gpu.vram_used / 1024 ** 3).toFixed(2) : "?"} / ${gpu.vram_total_gb} GB used` : "unavailable"}
              </span>
              <span className="k">Low-VRAM flag</span>
              <span className="v">{flags.lowvram ? "--lowvram" : flags.novram ? "--novram" : flags.normalvram ? "--normalvram" : "not set"}</span>
              <span className="k">Attention</span>
              <span className="v">{flags.pytorch_cross_attention ? "PyTorch cross-attention" : flags.split_cross_attention ? "split cross-attention" : "default"}</span>
              <span className="k">Queue</span>
              <span className="v">
                {queueState?.running ? `1 running (${queueState.running.workflow_name || queueState.running.id})` : "idle"}
                {" · "}
                {queueState?.pending?.length ?? 0} pending
              </span>
              <span className="k">Model dirs</span>
              <span className="v tiny wrap">{(catalog?.model_dirs || []).join(" · ") || "none"}</span>
            </div>
            <div className="tiny muted" style={{ marginTop: 8 }}>
              To add another local model directory, use Settings → Storage → Model directories, then Refresh catalog.
            </div>
            {catalog.missing.length > 0 && (
              <>
                <div className="section-title" style={{ marginTop: 14 }}>Missing / recommended</div>
                <div className="stack">
                  {catalog.missing.map((item, index) => (
                    <div key={`${item.kind}-${index}`} className="ai-provider">
                      <div className="row between">
                        <strong>{item.kind}</strong>
                        <span className={`chip ${item.severity === "blocking" ? "pose" : item.severity === "warning" ? "exp" : ""}`}>
                          {item.severity}
                        </span>
                      </div>
                      <div className="tiny muted">{item.message}</div>
                      <div className="tiny">{item.action}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Model Selection</h2>
                <div className="panel-sub">SDXL is used when configured; otherwise SD 1.5 is the fallback.</div>
              </div>
            </div>
            {config && (
              <div className="stack">
                <div className="form-grid">
                  <div className="field">
                    <label>Default architecture</label>
                    <select value={config.default_architecture} onChange={(event) => setModel("default_architecture", event.target.value)}>
                      <option value="sdxl">SDXL</option>
                      <option value="sd15">SD 1.5</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Default LoRA strength</label>
                    <input
                      type="number"
                      step="0.05"
                      min="-2"
                      max="2"
                      value={config.lora.strength}
                      onChange={(event) => setLora("strength", Number(event.target.value))}
                    />
                  </div>
                  <div className="field">
                    <label>SDXL checkpoint</label>
                    <select value={config.checkpoints.sdxl || ""} onChange={(event) => setCheckpoint("sdxl", event.target.value)}>
                      <option value="">Not selected — SD 1.5 fallback</option>
                      {checkpointOptions("sdxl").map((entry) => (
                        <option key={entry.name} value={entry.name}>
                          {entry.name} ({archLabel(entry.architecture)}, {entry.confidence})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>SD 1.5 checkpoint</label>
                    <select value={config.checkpoints.sd15 || ""} onChange={(event) => setCheckpoint("sd15", event.target.value)}>
                      <option value="">Not selected</option>
                      {checkpointOptions("sd15").map((entry) => (
                        <option key={entry.name} value={entry.name}>
                          {entry.name} ({archLabel(entry.architecture)})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>SDXL VAE</label>
                    <select value={config.vae.sdxl || ""} onChange={(event) => setVae("sdxl", event.target.value)}>
                      <option value="">Use checkpoint VAE</option>
                      {vaeOptions("sdxl").map((entry) => (
                        <option key={entry.name} value={entry.name}>{entry.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>SD 1.5 VAE</label>
                    <select value={config.vae.sd15 || ""} onChange={(event) => setVae("sd15", event.target.value)}>
                      <option value="">Use checkpoint VAE</option>
                      {vaeOptions("sd15").map((entry) => (
                        <option key={entry.name} value={entry.name}>{entry.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>LoRA</label>
                    <select
                      value={config.lora.name || ""}
                      onChange={(event) => {
                        const selected = loras.find((entry) => entry.name === event.target.value);
                        setLora("name", event.target.value);
                        setLora("architecture", selected?.architecture || "");
                      }}
                    >
                      <option value="">No LoRA</option>
                      {loras.map((entry) => (
                        <option key={entry.name} value={entry.name}>
                          {entry.name} ({archLabel(entry.architecture)})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>LoRA architecture</label>
                    <select value={config.lora.architecture || ""} onChange={(event) => setLora("architecture", event.target.value)}>
                      <option value="">Unknown / any</option>
                      <option value="sdxl">SDXL</option>
                      <option value="sd15">SD 1.5</option>
                    </select>
                  </div>
                </div>

                <div className="section-title">SDXL Lightning fast mode</div>
                <div className="row" style={{ flexWrap: "wrap", gap: 14, alignItems: "center" }}>
                  <label className="tiny">
                    <input
                      type="checkbox"
                      checked={Boolean(fastMode?.enabled)}
                      disabled={fastBusy || !fastMode}
                      onChange={(event) => toggleFastMode({ enabled: event.target.checked })}
                    />{" "}
                    Fast mode
                  </label>
                  <label className="tiny">
                    Steps
                    <select
                      value={fastMode?.steps ?? 8}
                      disabled={fastBusy || !fastMode}
                      onChange={(event) =>
                        toggleFastMode({ steps: Number(event.target.value), enabled: fastMode?.enabled ?? false })
                      }
                    >
                      <option value={8}>8 steps</option>
                      <option value={4}>4 steps</option>
                    </select>
                  </label>
                  <span className={`chip ${fastMode?.lora_installed ? "exp" : ""}`}>
                    {fastMode?.lora_installed ? "Lightning LoRA installed" : "Lightning LoRA missing"}
                  </span>
                </div>
                <div className="tiny muted" style={{ marginTop: 6 }}>
                  Renders SDXL image jobs at {fastMode?.steps ?? 8} steps, CFG {fastMode?.cfg ?? 1},{" "}
                  {fastMode?.sampler ?? "euler"}/{fastMode?.scheduler ?? "sgm_uniform"} with{" "}
                  <span className="mono">{fastMode?.lora || "the Lightning LoRA"}</span>. Roughly 3–4× faster on the
                  4050. Skips SD 1.5 jobs and any character that already has its own LoRA. IP-Adapter and ControlNet
                  stack on top unchanged.
                </div>

                <div className="section-title">Workflows</div>
                <div className="form-grid">
                  {WORKFLOW_KEYS.map(({ key, label }) => (
                    <div className="field" key={key}>
                      <label>{label}</label>
                      <select value={config.workflows[key] || ""} onChange={(event) => setWorkflow(key, event.target.value)}>
                        <option value="">Auto / fallback</option>
                        {imageWorkflows.map((workflow) => (
                          <option key={workflow.id} value={workflow.id}>
                            {workflow.name} ({workflow.engine})
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>

                <div className="section-title">6 GB VRAM options</div>
                <div className="row" style={{ flexWrap: "wrap", gap: 14 }}>
                  <label className="tiny" title="ComfyUI launch flag — change it in the launcher">
                    <input type="checkbox" checked={config.low_vram} readOnly disabled /> Low-VRAM mode
                  </label>
                  <label className="tiny" title="Applied by the SDXL workflow templates">
                    <input type="checkbox" checked={config.tiled_vae} readOnly disabled /> Tiled VAE decode
                  </label>
                  <label className="tiny" title="ComfyUI launch flag — change it in the launcher">
                    CPU offload
                    <select value={config.cpu_offload} disabled>
                      <option value="auto">Auto</option>
                      <option value="lowvram">--lowvram</option>
                      <option value="novram">--novram</option>
                    </select>
                  </label>
                  <label className="tiny" title="ComfyUI launch flag — change it in the launcher">
                    Attention
                    <select value={config.attention} disabled>
                      <option value="default">Default</option>
                      <option value="pytorch">PyTorch cross-attention</option>
                      <option value="split">Split cross-attention</option>
                    </select>
                  </label>
                  <label className="tiny">
                    Batch size
                    <input type="number" min={1} max={1} value={1} readOnly disabled style={{ width: 54 }} />
                  </label>
                </div>
                <div className="tiny muted">
                  These are ComfyUI launch-level settings and are read-only here. Low-VRAM and attention must be set in the ComfyUI launcher; tiled VAE is baked into the SDXL workflow templates. Active runtime flag:{" "}
                  <strong>{flags.lowvram ? "low-VRAM" : flags.normalvram ? "normal VRAM" : "reported by ComfyUI"}</strong>.
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {config && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>Resolution & Sampling Presets</h2>
              <div className="panel-sub">Safe starting points for 6 GB VRAM. Advanced users can adjust them.</div>
            </div>
          </div>
          <div style={{ overflow: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Preset</th>
                  <th>Width</th>
                  <th>Height</th>
                  <th>Steps</th>
                  <th>CFG</th>
                  <th>Sampler</th>
                  <th>Scheduler</th>
                </tr>
              </thead>
              <tbody>
                {PRESET_KEYS.map((key) => {
                  const preset = config.presets[key] || {};
                  return (
                    <tr key={key}>
                      <td className="mono">{key}</td>
                      <td><input type="number" value={preset.width ?? ""} onChange={(event) => setPreset(key, "width", Number(event.target.value))} style={{ width: 80 }} /></td>
                      <td><input type="number" value={preset.height ?? ""} onChange={(event) => setPreset(key, "height", Number(event.target.value))} style={{ width: 80 }} /></td>
                      <td><input type="number" value={preset.steps ?? ""} onChange={(event) => setPreset(key, "steps", Number(event.target.value))} style={{ width: 70 }} /></td>
                      <td><input type="number" step="0.1" value={preset.cfg ?? ""} onChange={(event) => setPreset(key, "cfg", Number(event.target.value))} style={{ width: 70 }} /></td>
                      <td>
                        <select value={preset.sampler || "dpmpp_2m"} onChange={(event) => setPreset(key, "sampler", event.target.value)}>
                          {samplers.map((sampler) => <option key={sampler} value={sampler}>{sampler}</option>)}
                        </select>
                      </td>
                      <td>
                        <select value={preset.scheduler || "karras"} onChange={(event) => setPreset(key, "scheduler", event.target.value)}>
                          {schedulers.map((scheduler) => <option key={scheduler} value={scheduler}>{scheduler}</option>)}
                        </select>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {catalog && (
        <>
          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h2>Installed Models</h2>
                <div className="panel-sub">Scanned from ComfyUI model directories and live `/object_info`</div>
              </div>
            </div>
            {[
              ["Checkpoints", checkpoints],
              ["VAEs", vaes],
              ["LoRAs", loras],
              ["ControlNet", controlnets],
              ["Upscalers", upscalers],
            ].map(([title, entries]) => (
              <div key={String(title)} style={{ marginBottom: 16 }}>
                <div className="section-title">{String(title)}</div>
                {(entries as ModelFileEntry[]).length === 0 ? (
                  <div className="tiny muted">None found.</div>
                ) : (
                  <div style={{ overflow: "auto" }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Architecture</th>
                          <th>Confidence</th>
                          <th>Size</th>
                          <th>ComfyUI</th>
                          <th>Compatible</th>
                          <th>Detection</th>
                          <th>Path</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(entries as ModelFileEntry[]).map((entry) => (
                          <tr key={entry.name}>
                            <td className="mono wrap">{entry.name}</td>
                            <td>{archLabel(entry.architecture)}</td>
                            <td>{entry.confidence}</td>
                            <td>{formatSize(entry)}</td>
                            <td>{entry.installed_in_comfy ? "installed" : "not listed"}</td>
                            <td>{entry.compatible_engines?.join(", ") || "unknown"}</td>
                            <td className="tiny muted">{entry.detection_detail}</td>
                            <td className="tiny muted wrap">{entry.path || "ComfyUI path only"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </section>

          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h2>Recommended SDXL Models</h2>
                <div className="panel-sub">
                  Whitelist-only downloads. Review the licence, confirm it, and the file is checksum-verified
                  before install. Files go to the first configured model directory.
                </div>
              </div>
            </div>
            <div style={{ overflow: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Source</th>
                    <th>License</th>
                    <th>Size</th>
                    <th>VRAM</th>
                    <th>Cartoon suitability</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.recommendations.map((item) => (
                    <tr key={item.name}>
                      <td>
                        <strong>{item.name}</strong>
                        <div className="tiny muted">{item.intended_use}</div>
                      </td>
                      <td className="tiny wrap">
                        {item.source.startsWith("http") ? (
                          <a className="link" href={item.source} target="_blank" rel="noreferrer">{item.source}</a>
                        ) : (
                          item.source
                        )}
                      </td>
                      <td className="tiny">{item.license}<div className="muted">{item.license_notes}</div></td>
                      <td className="tiny">{item.download_size}</td>
                      <td className="tiny">{item.vram}</td>
                      <td className="tiny">{item.cartoon_suitability}</td>
                      <td>
                        {item.installed ? (
                          <span className="chip exp">installed: {item.installed_file}</span>
                        ) : (() => {
                          const download = downloadFor(item.name);
                          if (download && ["queued", "downloading", "verifying"].includes(download.status)) {
                            return (
                              <div style={{ minWidth: 160 }}>
                                <div className="tiny">
                                  {download.status} · {download.percent.toFixed(1)}%
                                </div>
                                <div className="progress" style={{ margin: "4px 0" }}>
                                  <span style={{ width: `${Math.min(100, download.percent)}%` }} />
                                </div>
                                <div className="tiny muted">
                                  {formatBytes(download.bytes_downloaded)} / {formatBytes(download.bytes_total)}
                                  {download.speed_mbps > 0 ? ` · ${download.speed_mbps.toFixed(1)} MB/s` : ""}
                                </div>
                                <button
                                  className="btn sm ghost"
                                  style={{ marginTop: 4 }}
                                  onClick={() => cancelDownload(download.id)}
                                >
                                  Cancel
                                </button>
                              </div>
                            );
                          }
                          if (download?.status === "failed") {
                            return (
                              <div>
                                <span className="chip pose">failed</span>
                                <div className="tiny" style={{ color: "var(--danger)", marginTop: 4 }}>
                                  {download.error}
                                </div>
                                <button className="btn sm ghost" style={{ marginTop: 4 }} onClick={() => beginDownload(item)}>
                                  Retry
                                </button>
                              </div>
                            );
                          }
                          if (item.download?.available) {
                            return (
                              <button className="btn sm" onClick={() => beginDownload(item)}>
                                Download
                              </button>
                            );
                          }
                          return (
                            <span className="chip" title={item.download?.reason}>
                              manual only
                            </span>
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Recent Image Outputs</h2>
                <div className="panel-sub">Latest generated assets from the active project</div>
              </div>
            </div>
            {assets.length === 0 ? (
              <EmptyState>No generated images yet.</EmptyState>
            ) : (
              <div className="media-grid">
                {assets.map((asset) => (
                  <div key={asset.id} className="media-card">
                    <a href={`/api/assets/${asset.id}/file`} target="_blank" rel="noreferrer">
                      <img src={`/api/assets/${asset.id}/file`} alt={asset.filename} loading="lazy" />
                    </a>
                    <div className="media-cap">
                      <span className="wrap">{asset.filename}</span>
                      <span>{asset.kind}</span>
                    </div>
                    <div className="media-actions">
                      <button className="btn sm" onClick={() => reviewImage(asset.id)} disabled={visionBusy}>
                        {visionBusy && visionAsset === asset.id ? "Reviewing…" : "Vision review"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {visionResult && (
              <>
                <div className="section-title" style={{ marginTop: 14 }}>Vision review · {visionAsset}</div>
                <pre className="prompt-preview" style={{ maxHeight: 320, overflow: "auto" }}>
                  {JSON.stringify(visionResult, null, 2)}
                </pre>
              </>
            )}
          </section>
        </>
      )}

      {downloadTarget && (
        <div className="modal-backdrop" onClick={() => !downloadBusy && setDownloadTarget(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()} style={{ maxWidth: 640 }}>
            <div className="panel-head">
              <div>
                <h2>Download {downloadTarget.name}</h2>
                <div className="panel-sub">
                  Whitelisted source, licence confirmation required, SHA256 verified after download.
                </div>
              </div>
              <button className="btn sm ghost" onClick={() => setDownloadTarget(null)} disabled={downloadBusy}>
                Close
              </button>
            </div>
            {downloadError && <Alert kind="error">{downloadError}</Alert>}
            <table className="table">
              <tbody>
                <tr>
                  <td className="tiny muted">Source</td>
                  <td className="tiny wrap">
                    {downloadTarget.source.startsWith("http") ? (
                      <a className="link" href={downloadTarget.source} target="_blank" rel="noreferrer">
                        {downloadTarget.source}
                      </a>
                    ) : (
                      downloadTarget.source
                    )}
                  </td>
                </tr>
                <tr>
                  <td className="tiny muted">Licence</td>
                  <td className="tiny">
                    {downloadTarget.download?.license || downloadTarget.license}
                    <div className="muted">{downloadTarget.license_notes}</div>
                  </td>
                </tr>
                <tr>
                  <td className="tiny muted">File</td>
                  <td className="tiny mono">{downloadTarget.download?.filename}</td>
                </tr>
                <tr>
                  <td className="tiny muted">Size</td>
                  <td className="tiny">
                    {downloadTarget.download?.size_gb ? `${downloadTarget.download.size_gb} GB` : downloadTarget.download_size}
                  </td>
                </tr>
                <tr>
                  <td className="tiny muted">Destination</td>
                  <td className="tiny mono wrap">
                    {`${catalog?.model_dirs?.[0] || ""}\\${downloadTarget.download?.category || downloadTarget.category}\\${downloadTarget.download?.filename || ""}`}
                  </td>
                </tr>
                <tr>
                  <td className="tiny muted">SHA256</td>
                  <td className="tiny mono wrap">{downloadTarget.download?.sha256}</td>
                </tr>
              </tbody>
            </table>
            {downloadTarget.download?.token_env && !downloadTarget.download.token_configured && (
              <Alert kind="warn">
                This source may require an account token. If the download is refused, set{" "}
                <span className="mono">{downloadTarget.download.token_env}</span> in the backend environment.
              </Alert>
            )}
            <label className="tiny" style={{ display: "flex", gap: 8, alignItems: "flex-start", margin: "12px 0" }}>
              <input
                type="checkbox"
                checked={licenseAccepted}
                onChange={(event) => setLicenseAccepted(event.target.checked)}
                style={{ marginTop: 2 }}
              />
              <span>
                I have reviewed this model’s licence and usage restrictions, and I accept responsibility
                for using it in production.
              </span>
            </label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn ghost" onClick={() => setDownloadTarget(null)} disabled={downloadBusy}>
                Cancel
              </button>
              <button className="btn" onClick={submitDownload} disabled={!licenseAccepted || downloadBusy}>
                {downloadBusy ? "Starting…" : "Download and verify"}
              </button>
            </div>
          </div>
        </div>
      )}

      {catalog?.note && <div className="tiny muted" style={{ marginTop: 12 }}>{catalog.note}</div>}
    </>
  );
}
