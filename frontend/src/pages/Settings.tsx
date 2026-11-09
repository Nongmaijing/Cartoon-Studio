import { useEffect, useState } from "react";
import { api } from "../api";
import type { AppConfig, ComfyTest, DiscoveryInfo, ModelLists, SettingsPayload } from "../types";
import { Alert, PageHeader } from "../components/Ui";

function update(section: keyof AppConfig, key: string, value: unknown) {
  return (current: AppConfig | null): AppConfig | null => {
    if (!current) return current;
    return {
      ...current,
      [section]: { ...(current[section] as Record<string, unknown>), [key]: value },
    } as AppConfig;
  };
}

export default function Settings() {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [comfy, setComfy] = useState<ComfyTest | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryInfo | null>(null);
  const [models, setModels] = useState<ModelLists | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = async () => {
    try {
      const result = await api.settings();
      setPayload(result);
      setConfig(result.config);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      setComfy(await api.comfyTest());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setTesting(false);
    }
  };

  const discover = async () => {
    try {
      setDiscovery(await api.discovery());
      await load();
      setNotice("Discovery refreshed from the running ComfyUI process.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const loadModels = async () => {
    try {
      setModels(await api.models());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  useEffect(() => {
    load();
    test();
    discover();
    loadModels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!config) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const result = await api.saveSettings(config);
      setPayload(result);
      setConfig(result.config);
      setNotice("Settings saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  };

  if (!config) {
    return (
      <>
        <PageHeader title="Settings" subtitle="ComfyUI connection, storage and generation defaults." />
        {error ? <Alert kind="error">{error}</Alert> : <div className="empty">Loading settings…</div>}
      </>
    );
  }

  const set = (section: keyof AppConfig, key: string, value: unknown) => {
    setConfig(update(section, key, value));
  };

  const pathRow = (label: string, key: keyof AppConfig["paths"]) => (
    <div className="field" key={key}>
      <label>
        {label}{" "}
        {payload?.paths_exist?.[key] === false && <span style={{ color: "var(--danger)" }}>· missing</span>}
      </label>
      <input value={config.paths[key]} onChange={(event) => set("paths", key, event.target.value)} />
    </div>
  );

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="The app writes only to its own config. ComfyUI configuration and models are never modified automatically."
        actions={
          <>
            <button className="btn ghost" onClick={test} disabled={testing}>
              {testing ? "Testing…" : "Test connection"}
            </button>
            <button className="btn ghost" onClick={discover}>
              Auto-discover
            </button>
            <button className="btn primary" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save settings"}
            </button>
          </>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>ComfyUI Connection</h2>
              <div className="panel-sub">Existing server used as the generation engine</div>
            </div>
            <span className="conn-pill">
              <span className={`dot ${comfy?.connected ? "ok" : "bad"}`} />
              {comfy?.connected ? "Connected" : "Offline"}
            </span>
          </div>

          <div className="stack">
            <div className="field">
              <label>Server URL</label>
              <input
                value={config.comfyui.server_url}
                onChange={(event) => set("comfyui", "server_url", event.target.value)}
              />
            </div>
            <div className="field">
              <label>ComfyUI installation path</label>
              <input
                value={config.comfyui.install_path}
                placeholder="Auto-discovered from the running process"
                onChange={(event) => set("comfyui", "install_path", event.target.value)}
              />
            </div>
            <div className="field">
              <label>Request timeout (seconds)</label>
              <input
                type="number"
                value={config.comfyui.request_timeout_seconds}
                onChange={(event) => set("comfyui", "request_timeout_seconds", Number(event.target.value))}
              />
            </div>

            {comfy && (
              <div className="kv">
                <span className="k">Status</span>
                <span className="v">{comfy.connected ? "Connected" : comfy.error || "Offline"}</span>
                <span className="k">Version</span>
                <span className="v">{comfy.version || "—"}</span>
                <span className="k">Device</span>
                <span className="v">{comfy.device || "—"}</span>
                <span className="k">Queue</span>
                <span className="v">
                  {comfy.queue_running ?? "—"} running · {comfy.queue_pending ?? "—"} pending
                </span>
                <span className="k">Nodes installed</span>
                <span className="v">{comfy.node_count ?? "—"}</span>
                <span className="k">PyTorch</span>
                <span className="v">{comfy.pytorch || "—"}</span>
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Discovery</h2>
              <div className="panel-sub">Read from the live ComfyUI process and model-path YAML</div>
            </div>
          </div>
          {discovery ? (
            <div className="kv">
              <span className="k">Process PID</span>
              <span className="v">{discovery.process_pid ?? "—"}</span>
              <span className="k">Install path</span>
              <span className="v wrap">{discovery.install_path || "—"}</span>
              <span className="k">Output dir</span>
              <span className="v wrap">{discovery.output_dir || "—"}</span>
              <span className="k">Input dir</span>
              <span className="v wrap">{discovery.input_dir || "—"}</span>
              <span className="k">Model YAML</span>
              <span className="v wrap">{discovery.extra_model_paths || "—"}</span>
              <span className="k">Model dirs</span>
              <span className="v wrap">{(discovery.model_dirs || []).join(" · ") || "—"}</span>
              <span className="k">User workflows</span>
              <span className="v wrap">{discovery.user_workflows_dir || "—"}</span>
              <span className="k">Source</span>
              <span className="v">{discovery.discovered_from_process ? "running process" : "config / fallback"}</span>
            </div>
          ) : (
            <div className="empty">Discovery has not run yet.</div>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Storage</h2>
            <div className="panel-sub">All app data stays under D:\bro\CartoonStudio</div>
          </div>
        </div>
        <div className="form-grid">
          {pathRow("Workflow directory", "workflow_dir")}
          {pathRow("Output directory", "output_dir")}
          {pathRow("Assets directory", "assets_dir")}
          {pathRow("Projects directory", "projects_dir")}
          {pathRow("Logs directory", "logs_dir")}
          {pathRow("Data directory", "data_dir")}
          <div className="field span-2">
            <label>Model directories (one per line)</label>
            <textarea
              value={(config.comfyui.models_dirs || []).join("\n")}
              onChange={(event) =>
                set(
                  "comfyui",
                  "models_dirs",
                  event.target.value
                    .split(/\r?\n/)
                    .map((line) => line.trim())
                    .filter(Boolean)
                )
              }
            />
          </div>
          <div className="field">
            <label>FFmpeg path (blank = use PATH)</label>
            <input
              value={config.ffmpeg.path}
              placeholder={payload?.ffmpeg_detected || "ffmpeg.exe"}
              onChange={(event) => set("ffmpeg", "path", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Detected FFmpeg</label>
            <input value={payload?.ffmpeg_detected || "not found"} readOnly />
          </div>
        </div>
      </section>

      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Generation Defaults</h2>
              <div className="panel-sub">Used when the UI leaves a field blank</div>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Default workflow</label>
              <input
                value={config.generation.default_workflow}
                onChange={(event) => set("generation", "default_workflow", event.target.value)}
              />
            </div>
            <div className="field">
              <label>Timeout (seconds)</label>
              <input
                type="number"
                value={config.generation.timeout_seconds}
                onChange={(event) => set("generation", "timeout_seconds", Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Width</label>
              <input
                type="number"
                value={config.generation.width}
                onChange={(event) => set("generation", "width", Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Height</label>
              <input
                type="number"
                value={config.generation.height}
                onChange={(event) => set("generation", "height", Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Steps</label>
              <input
                type="number"
                value={config.generation.steps}
                onChange={(event) => set("generation", "steps", Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>CFG</label>
              <input
                type="number"
                step={0.5}
                value={config.generation.cfg}
                onChange={(event) => set("generation", "cfg", Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>Sampler</label>
              <input
                value={config.generation.sampler}
                onChange={(event) => set("generation", "sampler", event.target.value)}
              />
            </div>
            <div className="field">
              <label>Scheduler</label>
              <input
                value={config.generation.scheduler}
                onChange={(event) => set("generation", "scheduler", event.target.value)}
              />
            </div>
            <div className="field span-2">
              <label>Default negative prompt</label>
              <textarea
                value={config.generation.negative_prompt}
                onChange={(event) => set("generation", "negative_prompt", event.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Available Models</h2>
              <div className="panel-sub">Reported by ComfyUI /object_info</div>
            </div>
            <button className="btn sm ghost" onClick={loadModels}>
              Refresh
            </button>
          </div>
          {models ? (
            <div className="stack">
              {(
                [
                  ["Checkpoints", models.checkpoints],
                  ["Diffusion models", models.diffusion_models],
                  ["Text encoders", models.text_encoders],
                  ["VAEs", models.vaes],
                ] as [string, string[]][]
              ).map(([label, list]) => (
                <div key={label}>
                  <div className="section-title">{label}</div>
                  <div className="btn-row">
                    {list.length ? (
                      list.map((item) => (
                        <span key={item} className="badge queued" style={{ textTransform: "none", letterSpacing: 0 }}>
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="small muted">None</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty">Model list unavailable. Check the ComfyUI connection.</div>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Voice / TTS</h2>
            <div className="panel-sub">
              Windows SAPI is discovered automatically. Piper, Coqui TTS and eSpeak NG are detected from PATH or these paths.
            </div>
          </div>
        </div>
        <div className="form-grid">
          <div className="field">
            <label>Default engine</label>
            <input
              value={config.tts.default_engine}
              placeholder="sapi"
              onChange={(event) => set("tts", "default_engine", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Default voice (blank = first available)</label>
            <input
              value={config.tts.default_voice}
              placeholder="Microsoft Zira Desktop"
              onChange={(event) => set("tts", "default_voice", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Piper executable</label>
            <input
              value={config.tts.piper_path}
              placeholder="piper.exe or full path"
              onChange={(event) => set("tts", "piper_path", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Piper voice model folder</label>
            <input
              value={config.tts.piper_model_dir}
              placeholder="folder containing .onnx voice models"
              onChange={(event) => set("tts", "piper_model_dir", event.target.value)}
            />
          </div>
          <div className="field">
            <label>Speech timeout (seconds)</label>
            <input
              type="number"
              value={config.tts.timeout_seconds}
              onChange={(event) => set("tts", "timeout_seconds", Number(event.target.value))}
            />
          </div>
        </div>
      </section>
    </>
  );
}
