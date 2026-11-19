import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Background, Job, MediaItem } from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";
import { AutoGrowTextarea } from "../components/AutoGrowTextarea";

const ASPECTS = [
  { ratio: "16:9", width: 1024, height: 576, label: "16:9 ? 1024?576 (SD 1.5)" },
  { ratio: "16:9", width: 1216, height: 832, label: "16:9 ? 1216?832 (SDXL)" },
  { ratio: "4:3", width: 896, height: 672, label: "4:3 ? 896?672" },
  { ratio: "1:1", width: 768, height: 768, label: "1:1 ? 768?768" },
  { ratio: "9:16", width: 576, height: 1024, label: "9:16 ? 576?1024" },
];

interface BackgroundProfile {
  name: string;
  description: string;
  aspect_ratio: string;
}

function isActive(job: Job | null): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

export default function Backgrounds() {
  const { selectedId, projects } = useProject();
  const [backgrounds, setBackgrounds] = useState<Background[]>([]);
  const [selectedBgId, setSelectedBgId] = useState("");
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [newProfile, setNewProfile] = useState<BackgroundProfile>({
    name: "",
    description: "",
    aspect_ratio: "16:9",
  });
  const [newAspect, setNewAspect] = useState(0);

  const [profile, setProfile] = useState<BackgroundProfile>({
    name: "",
    description: "",
    aspect_ratio: "16:9",
  });
  const [savingProfile, setSavingProfile] = useState(false);

  const [sizeIndex, setSizeIndex] = useState(0);
  const [steps, setSteps] = useState(28);
  const [seed, setSeed] = useState(-1);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");

  const [attachId, setAttachId] = useState("");
  const [attachLabel, setAttachLabel] = useState("");

  const selected = useMemo(
    () => backgrounds.find((background) => background.id === selectedBgId) || null,
    [backgrounds, selectedBgId]
  );

  const refreshBackgrounds = useCallback(async () => {
    if (!selectedId) {
      setBackgrounds([]);
      setSelectedBgId("");
      return;
    }
    try {
      const list = await api.backgrounds(selectedId);
      setBackgrounds(list);
      setSelectedBgId((current) =>
        current && list.some((background) => background.id === current) ? current : list[0]?.id || ""
      );
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  const loadMedia = useCallback(async (backgroundId: string) => {
    if (!backgroundId) {
      setMedia([]);
      return;
    }
    try {
      setMedia(await api.backgroundMedia(backgroundId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    refreshBackgrounds();
  }, [refreshBackgrounds]);

  useEffect(() => {
    loadMedia(selectedBgId);
    setActiveJob(null);
    setLastPrompt("");
    if (!selectedBgId) {
      setProfile({ name: "", description: "", aspect_ratio: "16:9" });
      return;
    }
    api
      .backgroundJobs(selectedBgId)
      .then((jobs) => {
        const running = jobs.find((job) => job.status === "queued" || job.status === "running");
        if (running) setActiveJob(running);
      })
      .catch(() => undefined);
  }, [selectedBgId, loadMedia]);

  useEffect(() => {
    if (!selected) {
      setProfile({ name: "", description: "", aspect_ratio: "16:9" });
      return;
    }
    setProfile({
      name: selected.name,
      description: selected.description,
      aspect_ratio: selected.aspect_ratio,
    });
  }, [selected?.id, selected?.created_at]);

  useEffect(() => {
    if (!activeJob || !isActive(activeJob)) return;
    const jobId = activeJob.id;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.job(jobId);
        setActiveJob(job);
        if (["completed", "failed", "cancelled", "interrupted"].includes(job.status)) {
          window.clearInterval(timer);
          await refreshBackgrounds();
          await loadMedia(selectedBgId);
          if (job.status === "completed") {
            setNotice("Background generated and attached.");
            setError("");
          } else if (job.status === "failed") {
            setError(job.error || "Generation failed.");
          }
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
        window.clearInterval(timer);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeJob?.id, activeJob?.status, refreshBackgrounds, loadMedia, selectedBgId]);

  const createBackground = async () => {
    if (!selectedId || !newProfile.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const aspect = ASPECTS[newAspect];
      const created = await api.createBackground({
        project_id: selectedId,
        name: newProfile.name.trim(),
        description: newProfile.description.trim(),
        aspect_ratio: aspect.ratio,
        width: aspect.width,
        height: aspect.height,
      });
      setNewProfile({ name: "", description: "", aspect_ratio: aspect.ratio });
      setShowCreate(false);
      await refreshBackgrounds();
      setSelectedBgId(created.id);
      setNotice(`Created background "${created.name}".`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const saveProfile = async () => {
    if (!selected) return;
    setSavingProfile(true);
    setError("");
    try {
      const aspect = ASPECTS.find((item) => item.ratio === profile.aspect_ratio) || ASPECTS[0];
      await api.updateBackground(selected.id, {
        name: profile.name.trim(),
        description: profile.description.trim(),
        aspect_ratio: profile.aspect_ratio,
        width: aspect.width,
        height: aspect.height,
      });
      await refreshBackgrounds();
      setNotice("Background details saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSavingProfile(false);
    }
  };

  const generate = async () => {
    if (!selected) return;
    setError("");
    setNotice("");
    const size = ASPECTS[sizeIndex];
    try {
      const result = await api.generateBackground(selected.id, {
        prompt: extraPrompt.trim() || undefined,
        width: size.width,
        height: size.height,
        steps,
        cfg: 6.5,
        seed,
      });
      setActiveJob(result.job);
      setLastPrompt(result.prompt);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const attachExisting = async () => {
    if (!selected || !attachId.trim()) return;
    setError("");
    try {
      await api.attachBackgroundMedia(selected.id, {
        asset_id: attachId.trim(),
        role: "background",
        label: attachLabel.trim(),
      });
      setAttachId("");
      setAttachLabel("");
      await refreshBackgrounds();
      await loadMedia(selected.id);
      setNotice("Existing asset attached.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const upscaleMedia = async (assetId: string) => {
    if (!selected) return;
    setError("");
    setNotice("");
    try {
      const result = await api.upscaleAsset(assetId, {
        owner_type: "background",
        owner_id: selected.id,
        role: "background",
        label: "upscaled",
      });
      setActiveJob(result.job);
      setNotice("4× upscale queued. The new image will appear under Generated Views when complete.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Backgrounds" subtitle="Generate reusable cartoon environments." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          building backgrounds.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Backgrounds"
        subtitle="Generate reusable cartoon environments — interiors, streets, schools, parks, shops and landscapes."
        actions={
          <button className="btn primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Close" : "New background"}
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>New Background</h2>
              <div className="panel-sub">Saved into {projects.find((project) => project.id === selectedId)?.name}</div>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Name</label>
              <input
                value={newProfile.name}
                placeholder="Forest clearing"
                onChange={(event) => setNewProfile({ ...newProfile, name: event.target.value })}
              />
            </div>
            <div className="field">
              <label>Aspect ratio</label>
              <select value={newAspect} onChange={(event) => setNewAspect(Number(event.target.value))}>
                {ASPECTS.map((aspect, index) => (
                  <option key={aspect.ratio} value={index}>
                    {aspect.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field span-2">
              <label>Description</label>
              <AutoGrowTextarea
                minRows={4}
                maxHeight={320}
                value={newProfile.description}
                placeholder="A sunny forest clearing with tall pine trees, mossy rocks and wildflowers."
                onChange={(event) => setNewProfile({ ...newProfile, description: event.target.value })}
              />
            </div>
          </div>
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={createBackground} disabled={busy || !newProfile.name.trim()}>
              {busy ? "Creating…" : "Create background"}
            </button>
          </div>
        </section>
      )}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Library</h2>
            <div className="panel-sub">{backgrounds.length} background(s) in this project</div>
          </div>
        </div>
        {backgrounds.length === 0 ? (
          <EmptyState>No backgrounds yet. Use “New background” to add the first location.</EmptyState>
        ) : (
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {backgrounds.map((background) => (
              <button
                key={background.id}
                className={`character-item${background.id === selectedBgId ? " active" : ""}`}
                style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
                onClick={() => setSelectedBgId(background.id)}
              >
                <div style={{ width: "100%", aspectRatio: "16 / 9", borderRadius: 8, overflow: "hidden", background: "#0a0e15" }}>
                  {background.cover_url ? (
                    <img
                      src={background.cover_url}
                      alt={background.name}
                      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                    />
                  ) : (
                    <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--muted-2)", fontSize: 11 }}>
                      No image yet
                    </div>
                  )}
                </div>
                <div className="character-meta" style={{ width: "100%" }}>
                  <strong>{background.name}</strong>
                  <span>{background.description || "No description"}</span>
                  <div className="chip-row">
                    <span className="chip">{background.aspect_ratio}</span>
                    <span className="chip">{background.width}×{background.height}</span>
                    <span className="chip ref">{background.image_count} image(s)</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {selected && (
        <>
          <div className="split">
            <section className="panel">
              <div className="detail-head">
                <div>
                  <h2>{selected.name}</h2>
                  <div className="panel-sub mono">{selected.id}</div>
                </div>
                <button className="btn sm primary" onClick={saveProfile} disabled={savingProfile || !profile.name.trim()}>
                  {savingProfile ? "Saving…" : "Save details"}
                </button>
              </div>
              <div className="form-grid">
                <div className="field">
                  <label>Name</label>
                  <input value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} />
                </div>
                <div className="field">
                  <label>Aspect ratio</label>
                  <select
                    value={profile.aspect_ratio}
                    onChange={(event) => setProfile({ ...profile, aspect_ratio: event.target.value })}
                  >
                    {ASPECTS.map((aspect) => (
                      <option key={aspect.ratio} value={aspect.ratio}>
                        {aspect.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field span-2">
                  <label>Description</label>
                  <AutoGrowTextarea
                    minRows={5}
                    maxHeight={420}
                    value={profile.description}
                    placeholder="Describe the location: time of day, weather, architecture, palette, props."
                    onChange={(event) => setProfile({ ...profile, description: event.target.value })}
                  />
                </div>
              </div>
              {media[0] && <img className="bg-preview" style={{ marginTop: 12 }} src={media[0].url} alt={selected.name} />}
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Generate</h2>
                  <div className="panel-sub">Local ComfyUI model · no characters in the prompt</div>
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
                  {activeJob.status === "failed" && (
                    <div className="tiny" style={{ color: "var(--danger)" }}>{activeJob.error}</div>
                  )}
                </div>
              )}

              <div className="form-grid">
                <div className="field">
                  <label>Resolution</label>
                  <select value={sizeIndex} onChange={(event) => setSizeIndex(Number(event.target.value))}>
                    {ASPECTS.map((aspect, index) => (
                      <option key={aspect.ratio} value={index}>
                        {aspect.label}
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
                  <label>Seed (-1 = random)</label>
                  <input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} />
                </div>
                <div className="field">
                  <label>Extra prompt</label>
                  <input
                    value={extraPrompt}
                    placeholder="optional, e.g. sunset lighting"
                    onChange={(event) => setExtraPrompt(event.target.value)}
                  />
                </div>
              </div>

              <div className="row between" style={{ marginTop: 12 }}>
                <span className="tiny muted">{ASPECTS[sizeIndex].label}</span>
                <button className="btn primary" onClick={generate} disabled={isActive(activeJob)}>
                  {isActive(activeJob) ? "Generating…" : "Generate background"}
                </button>
              </div>

              {lastPrompt && (
                <>
                  <div className="section-title" style={{ marginTop: 14 }}>Last prompt</div>
                  <div className="prompt-preview">{lastPrompt}</div>
                </>
              )}
            </section>
          </div>

          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h2>Generated Views</h2>
                <div className="panel-sub">{media.length} saved image(s)</div>
              </div>
            </div>
            {media.length === 0 ? (
              <div className="media-empty">No images yet. Generate one above, or attach an existing asset below.</div>
            ) : (
              <div className="media-grid">
                {media.map((item) => (
                  <div key={item.link_id} className="media-card landscape">
                    <a href={item.url} target="_blank" rel="noreferrer">
                      <img src={item.url} alt={item.label || item.filename} loading="lazy" />
                    </a>
                    <div className="media-cap">
                      <span className="wrap">{item.label || item.role}</span>
                      <span>{item.filename.split(".").pop()}</span>
                    </div>
                    <div className="media-actions">
                      <button
                        className="btn sm"
                        onClick={() => upscaleMedia(item.id)}
                        disabled={isActive(activeJob)}
                        title="Upscale 4× with 4x-UltraSharp"
                      >
                        Upscale 4×
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Attach Existing Asset</h2>
                <div className="panel-sub">Link any generated image in this project to the background</div>
              </div>
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Asset ID</label>
                <input value={attachId} placeholder="e.g. 62548225a719" onChange={(event) => setAttachId(event.target.value)} />
              </div>
              <div className="field">
                <label>Label</label>
                <input value={attachLabel} placeholder="day, night…" onChange={(event) => setAttachLabel(event.target.value)} />
              </div>
              <div className="field">
                <label>&nbsp;</label>
                <button className="btn" onClick={attachExisting} disabled={!attachId.trim()}>
                  Attach asset
                </button>
              </div>
            </div>
          </section>
        </>
      )}
    </>
  );
}
