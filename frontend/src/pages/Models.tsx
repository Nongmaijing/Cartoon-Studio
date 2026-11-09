import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type {
  Asset,
  ModelCatalog,
  ModelConfig,
  ModelFileEntry,
  ModelLists,
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

export default function Models() {
  const { selectedId } = useProject();
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowEntry[]>([]);
  const [modelLists, setModelLists] = useState<ModelLists | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [queueState, setQueueState] = useState<QueueState | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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

  const save = async () => {
    if (!config) return;
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
              <span className="k">Workflow</span>
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
                  <label className="tiny">
                    <input type="checkbox" checked={config.low_vram} onChange={(event) => setModel("low_vram", event.target.checked)} /> Low-VRAM mode
                  </label>
                  <label className="tiny">
                    <input type="checkbox" checked={config.tiled_vae} onChange={(event) => setModel("tiled_vae", event.target.checked)} /> Tiled VAE decode
                  </label>
                  <label className="tiny">
                    CPU offload
                    <select value={config.cpu_offload} onChange={(event) => setModel("cpu_offload", event.target.value)}>
                      <option value="auto">Auto</option>
                      <option value="lowvram">--lowvram</option>
                      <option value="novram">--novram</option>
                    </select>
                  </label>
                  <label className="tiny">
                    Attention
                    <select value={config.attention} onChange={(event) => setModel("attention", event.target.value)}>
                      <option value="default">Default</option>
                      <option value="pytorch">PyTorch cross-attention</option>
                      <option value="split">Split cross-attention</option>
                    </select>
                  </label>
                  <label className="tiny">
                    Batch size
                    <input type="number" min={1} max={1} value={1} readOnly style={{ width: 54 }} />
                  </label>
                </div>
                <div className="tiny muted">
                  Low-VRAM mode and attention are ComfyUI launch flags; they are reported and recommended here but not changed automatically. Tiled VAE is applied by the SDXL workflow templates. Precision is determined by the checkpoint and ComfyUI; no separate precision switch is forced.
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
                <div className="panel-sub">No download button. Review license, size and VRAM, then install manually if appropriate.</div>
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
                        <span className={`chip ${item.installed ? "exp" : ""}`}>
                          {item.installed ? `installed: ${item.installed_file}` : "not installed"}
                        </span>
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
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {catalog?.note && <div className="tiny muted" style={{ marginTop: 12 }}>{catalog.note}</div>}
    </>
  );
}
