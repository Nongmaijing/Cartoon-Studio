import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type {
  Asset,
  DialogueLine,
  Episode,
  EpisodeAudio,
  EpisodeSegment,
  EpisodeSettings,
  EpisodeTimeline,
  MediaItem,
  Scene,
  ShotPlan,
} from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";
import { AutoGrowTextarea } from "../components/AutoGrowTextarea";

const SIZE_PRESETS = [
  { label: "1280×720 · 720p", width: 1280, height: 720 },
  { label: "960×540 · 540p", width: 960, height: 540 },
  { label: "1920×1080 · 1080p", width: 1920, height: 1080 },
];

const EMPTY_SETTINGS: EpisodeSettings = {
  width: 1280,
  height: 720,
  fps: 24,
  subtitles: "soft",
  background_music_asset_id: null,
  background_music_volume: 0.35,
  fade_duration_ms: 350,
};

function cloneTimeline(value: EpisodeTimeline | undefined): EpisodeTimeline {
  if (!value) {
    return { segments: [], audio: [], settings: { ...EMPTY_SETTINGS } };
  }
  return {
    segments: value.segments.map((segment) => ({ ...segment })),
    audio: value.audio.map((item) => ({ ...item })),
    settings: { ...EMPTY_SETTINGS, ...(value.settings || {}) },
  };
}

function totalMs(timeline: EpisodeTimeline): number {
  return timeline.segments.reduce((total, segment) => total + Math.max(0, segment.duration_ms), 0);
}

function kindForAsset(asset: Asset): "video" | "image" {
  if (asset.kind === "video" || asset.mime?.startsWith("video/")) return "video";
  const filename = asset.filename.toLowerCase();
  return /\.(mp4|webm|mov|mkv|gif)$/.test(filename) ? "video" : "image";
}

function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}

export default function EpisodeEditor() {
  const { selectedId, projects } = useProject();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState("");
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [timeline, setTimeline] = useState<EpisodeTimeline>(cloneTimeline(undefined));
  const [dirty, setDirty] = useState(false);
  const [shotPlan, setShotPlan] = useState<ShotPlan | null>(null);
  const [shotPlanBusy, setShotPlanBusy] = useState(false);
  const [scriptState, setScriptState] = useState<{
    has_script: boolean;
    script_approved: boolean;
    latest_revision_number: number;
    current_sha256: string;
    storyboard_stale: boolean;
  } | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [newEpisode, setNewEpisode] = useState({ name: "", description: "" });

  const [segmentSceneId, setSegmentSceneId] = useState("");
  const [segmentAssets, setSegmentAssets] = useState<MediaItem[]>([]);
  const [segmentAssetId, setSegmentAssetId] = useState("");
  const [segmentDuration, setSegmentDuration] = useState(4);
  const [segmentTransition, setSegmentTransition] = useState<"cut" | "fade">("cut");
  const [segmentMotion, setSegmentMotion] = useState<"none" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right">("zoom_in");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);

  const assetMap = useMemo(() => {
    const map = new Map<string, Asset>();
    assets.forEach((asset) => map.set(asset.id, asset));
    return map;
  }, [assets]);
  const audioAssets = useMemo(() => assets.filter((asset) => asset.kind === "audio"), [assets]);
  const segmentScene = useMemo(
    () => scenes.find((scene) => scene.id === segmentSceneId) || null,
    [scenes, segmentSceneId]
  );

  const refreshEpisodes = useCallback(async (selectId?: string) => {
    if (!selectedId) {
      setEpisodes([]);
      setSelectedEpisodeId("");
      return;
    }
    try {
      const list = await api.episodes(selectedId);
      setEpisodes(list);
      setSelectedEpisodeId((current) => {
        const wanted = selectId || current;
        return wanted && list.some((item) => item.id === wanted) ? wanted : list[0]?.id || "";
      });
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  useEffect(() => {
    refreshEpisodes();
  }, [refreshEpisodes]);

  useEffect(() => {
    if (!selectedId) {
      setScenes([]);
      setAssets([]);
      return;
    }
    Promise.all([api.scenes(selectedId), api.assets(200, selectedId)])
      .then(([sceneList, assetList]) => {
        setScenes(sceneList);
        setAssets(assetList);
        setSegmentSceneId((current) =>
          current && sceneList.some((scene) => scene.id === current) ? current : sceneList[0]?.id || ""
        );
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedEpisodeId) {
      setEpisode(null);
      setTimeline(cloneTimeline(undefined));
      setDirty(false);
      setShotPlan(null);
      setScriptState(null);
      return;
    }
    let alive = true;
    api
      .episode(selectedEpisodeId)
      .then((value) => {
        if (!alive) return;
        setEpisode(value);
        setTimeline(cloneTimeline(value.timeline));
        setDirty(false);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
    api
      .getShotPlan(selectedEpisodeId)
      .then((plan) => {
        if (alive) setShotPlan(plan);
      })
      .catch(() => {
        if (alive) setShotPlan(null);
      });
    api
      .scriptState(selectedEpisodeId)
      .then((state) => {
        if (alive) setScriptState(state);
      })
      .catch(() => {
        if (alive) setScriptState(null);
      });
    return () => {
      alive = false;
    };
  }, [selectedEpisodeId]);

  useEffect(() => {
    if (!episode || !["queued", "exporting"].includes(episode.status)) return;
    const id = episode.id;
    const timer = window.setInterval(async () => {
      try {
        const value = await api.episode(id);
        setEpisode(value);
        if (["completed", "failed", "cancelled", "interrupted"].includes(value.status)) {
          window.clearInterval(timer);
          setExporting(false);
          if (value.status === "completed") {
            setNotice("Episode exported successfully.");
            setError("");
          } else if (value.status === "failed") {
            setError(value.error || "Episode export failed.");
          }
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
        window.clearInterval(timer);
        setExporting(false);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [episode?.id, episode?.status]);

  useEffect(() => {
    if (!segmentSceneId) {
      setSegmentAssets([]);
      setSegmentAssetId("");
      return;
    }
    api
      .sceneMedia(segmentSceneId)
      .then((media) => {
        const visual = media.filter((item) => item.role === "keyframe" || item.role === "video");
        setSegmentAssets(visual);
        setSegmentAssetId((current) =>
          current && visual.some((item) => item.id === current) ? current : visual[0]?.id || ""
        );
        const scene = scenes.find((item) => item.id === segmentSceneId);
        setSegmentDuration(scene?.duration || 4);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, [segmentSceneId, scenes]);

  const markDirty = (next: EpisodeTimeline) => {
    setTimeline(next);
    setDirty(true);
  };

  const createEpisode = async () => {
    if (!selectedId || !newEpisode.name.trim()) return;
    setError("");
    try {
      const created = await api.createEpisode({
        project_id: selectedId,
        name: newEpisode.name.trim(),
        description: newEpisode.description.trim(),
      });
      setNewEpisode({ name: "", description: "" });
      setShowCreate(false);
      await refreshEpisodes(created.id);
      setSelectedEpisodeId(created.id);
      setNotice(`Created episode "${created.name}".`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const saveTimeline = async () => {
    if (!episode) return null;
    setSaving(true);
    setError("");
    try {
      const saved = await api.saveEpisodeTimeline(episode.id, timeline);
      setEpisode(saved);
      setDirty(false);
      await refreshEpisodes(episode.id);
      setNotice("Timeline saved.");
      return saved;
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const addSegment = async () => {
    if (!segmentAssetId || !segmentSceneId) return;
    const media = segmentAssets.find((item) => item.id === segmentAssetId);
    const scene = scenes.find((item) => item.id === segmentSceneId);
    const duration = Math.max(0.1, segmentDuration) * 1000;
    const start = totalMs(timeline);
    const segment: EpisodeSegment = {
      id: `seg_${Date.now().toString(36)}`,
      scene_id: segmentSceneId,
      asset_id: segmentAssetId,
      kind: media ? kindForAsset(media) : "video",
      duration_ms: Math.round(duration),
      trim_start_ms: 0,
      transition: segmentTransition,
      motion: segmentMotion,
      label: `${scene?.name || "Scene"} · ${media?.label || media?.filename || segmentAssetId}`,
    };
    const nextAudio = [...timeline.audio];
    try {
      const lines: DialogueLine[] = await api.sceneDialogue(segmentSceneId);
      let cursor = start;
      for (const line of lines) {
        if (!line.audio_asset_id) continue;
        const lineStart = line.start_ms > 0 ? start + line.start_ms : cursor;
        const exists = nextAudio.some(
          (item) => item.asset_id === line.audio_asset_id && Math.abs(item.start_ms - lineStart) < 50
        );
        if (!exists) {
          nextAudio.push({
            id: `aud_${Date.now().toString(36)}_${nextAudio.length}`,
            asset_id: line.audio_asset_id,
            start_ms: Math.max(0, Math.round(lineStart)),
            volume: 1,
            loop: false,
            label: `${line.character_name || "Narrator"} · ${line.text.slice(0, 42)}`,
            kind: "dialogue",
          });
        }
        cursor = Math.max(cursor, lineStart + (line.duration_ms || 1500) + 150);
      }
    } catch {
      // Dialogue audio is optional; adding the scene segment still works.
    }
    markDirty({
      ...timeline,
      segments: [...timeline.segments, segment],
      audio: nextAudio,
    });
    setNotice(`Added scene segment with ${nextAudio.length - timeline.audio.length} dialogue track(s).`);
  };

  const updateSegment = (index: number, patch: Partial<EpisodeSegment>) => {
    const segments = timeline.segments.map((segment, i) => (i === index ? { ...segment, ...patch } : segment));
    markDirty({ ...timeline, segments });
  };

  const moveSegment = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= timeline.segments.length) return;
    const segments = [...timeline.segments];
    [segments[index], segments[target]] = [segments[target], segments[index]];
    markDirty({ ...timeline, segments });
  };

  const removeSegment = (index: number) => {
    markDirty({ ...timeline, segments: timeline.segments.filter((_, i) => i !== index) });
  };

  const addAudio = () => {
    const first = audioAssets[0];
    if (!first) {
      setError("No audio assets in this project yet. Generate dialogue in Voice & Dialogue first.");
      return;
    }
    const item: EpisodeAudio = {
      id: `aud_${Date.now().toString(36)}`,
      asset_id: first.id,
      start_ms: 0,
      volume: 1,
      loop: false,
      label: first.filename,
      kind: "other",
    };
    markDirty({ ...timeline, audio: [...timeline.audio, item] });
  };

  const updateAudio = (index: number, patch: Partial<EpisodeAudio>) => {
    const audio = timeline.audio.map((item, i) => (i === index ? { ...item, ...patch } : item));
    markDirty({ ...timeline, audio });
  };

  const removeAudio = (index: number) => {
    markDirty({ ...timeline, audio: timeline.audio.filter((_, i) => i !== index) });
  };

  const updateSettings = (patch: Partial<EpisodeSettings>) => {
    markDirty({ ...timeline, settings: { ...timeline.settings, ...patch } });
  };

  const buildPlan = async () => {
    if (!episode) return;
    setShotPlanBusy(true);
    setError("");
    setNotice("");
    try {
      const plan = await api.buildShotPlan(episode.id);
      setShotPlan(plan);
      setNotice(
        `Shot plan built: ${plan.shot_count} shots, about ${plan.estimate.total_gpu_minutes} GPU minutes on the 6 GB profile. No jobs were started.`
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setShotPlanBusy(false);
    }
  };

  const approveScript = async () => {
    if (!episode || !scriptState?.has_script) return;
    if (!window.confirm("Approve the current script for production?")) return;
    setError("");
    try {
      await api.approveScript(episode.id);
      setScriptState(await api.scriptState(episode.id));
      setNotice("Script approved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const exportEpisode = async () => {
    if (!episode) return;
    setError("");
    setNotice("");
    setExporting(true);
    try {
      const saved = await api.saveEpisodeTimeline(episode.id, timeline);
      setEpisode(saved);
      setDirty(false);
      const queued = await api.exportEpisode(episode.id);
      setEpisode(queued);
      setNotice("Export queued. FFmpeg runs in the background; the current GPU queue is untouched.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setExporting(false);
    }
  };

  const cancelExport = async () => {
    if (!episode) return;
    try {
      await api.cancelEpisodeExport(episode.id);
      setEpisode(await api.episode(episode.id));
      setExporting(false);
      setNotice("Export cancellation requested.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const removeEpisode = async () => {
    if (!episode) return;
    if (!window.confirm("Delete this episode? Exported files stay on disk as assets.")) return;
    try {
      await api.deleteEpisode(episode.id);
      setEpisode(null);
      setSelectedEpisodeId("");
      await refreshEpisodes();
      setNotice("Episode deleted.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const timelineTotal = totalMs(timeline);

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Episode Editor" subtitle="Arrange finished scenes, mix audio and export an MP4." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          editing an episode.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Episode Editor"
        subtitle="Arrange finished scenes, mix dialogue/music and export a 1080p MP4 (720p/540p optional). Timeline edits never regenerate scenes."
        actions={
          <button className="btn primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Close" : "New episode"}
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      {episode && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>Shot Plan</h2>
              <div className="panel-sub">
                Shot-level production plan and resource estimate. Building a plan does not start generation.
              </div>
            </div>
            <button className="btn primary sm" onClick={buildPlan} disabled={shotPlanBusy}>
              {shotPlanBusy ? "Planning…" : shotPlan ? "Rebuild plan" : "Build shot plan"}
            </button>
          </div>
          {shotPlan ? (
            <>
              <div className="stat-grid ai-stats" style={{ marginBottom: 12 }}>
                <div className="stat"><div className="stat-value">{shotPlan.shot_count}</div><div className="stat-label">Shots</div></div>
                <div className="stat"><div className="stat-value">{shotPlan.estimate.total_gpu_minutes}</div><div className="stat-label">GPU minutes</div></div>
                <div className="stat"><div className="stat-value">{shotPlan.estimate.image_seconds}</div><div className="stat-label">Image sec</div></div>
                <div className="stat"><div className="stat-value">{shotPlan.estimate.animation_seconds}</div><div className="stat-label">Video sec</div></div>
                <div className="stat"><div className="stat-value">{shotPlan.estimate.dialogue_lines}</div><div className="stat-label">Dialogue</div></div>
                <div className="stat"><div className="stat-value">{shotPlan.estimate.missing_keyframes}</div><div className="stat-label">Missing keys</div></div>
              </div>
              <div style={{ overflow: "auto", maxHeight: 360 }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Shot</th>
                      <th>Scene</th>
                      <th>Duration</th>
                      <th>Characters</th>
                      <th>Dialogue</th>
                      <th>Keyframe</th>
                      <th>Animation</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shotPlan.shots.map((shot) => (
                      <tr key={String(shot.id)}>
                        <td className="mono">{String(shot.label || shot.shot_number)}</td>
                        <td>{String(shot.scene_number)}</td>
                        <td>{String(shot.duration_seconds)}s</td>
                        <td>{(shot.characters || []).map((character: any) => character.name).join(", ") || "—"}</td>
                        <td>{shot.audio_requirements?.dialogue_count ?? 0}</td>
                        <td>{shot.generation_instructions?.needs_keyframe ? "needed" : "ready"}</td>
                        <td>{shot.generation_instructions?.needs_animation ? "planned" : "ready"}</td>
                        <td><span className="chip">{String(shot.status || "planned")}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="tiny muted" style={{ marginTop: 8 }}>{shotPlan.estimate.note}</div>
            </>
          ) : (
            <div className="tiny muted">
              No shot plan yet. Build one to estimate GPU time and shot-level work before starting production.
            </div>
          )}
        </section>
      )}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>New Episode</h2>
              <div className="panel-sub">Saved into {projects.find((project) => project.id === selectedId)?.name}</div>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Name</label>
              <input
                value={newEpisode.name}
                placeholder="Episode 1 · The Glowing Mushroom"
                onChange={(event) => setNewEpisode({ ...newEpisode, name: event.target.value })}
              />
            </div>
            <div className="field span-2">
              <label>Description</label>
              <AutoGrowTextarea
                minRows={3}
                maxHeight={260}
                value={newEpisode.description}
                placeholder="Milo discovers a strange light in the forest."
                onChange={(event) => setNewEpisode({ ...newEpisode, description: event.target.value })}
              />
            </div>
          </div>
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={createEpisode} disabled={!newEpisode.name.trim()}>
              Create episode
            </button>
          </div>
        </section>
      )}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Episodes</h2>
            <div className="panel-sub">{episodes.length} episode(s) in this project</div>
          </div>
        </div>
        {episodes.length === 0 ? (
          <EmptyState>No episodes yet. Use “New episode” to start a timeline.</EmptyState>
        ) : (
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", marginBottom: 0 }}>
            {episodes.map((item) => (
              <button
                key={item.id}
                className={`character-item${item.id === selectedEpisodeId ? " active" : ""}`}
                style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
                onClick={() => setSelectedEpisodeId(item.id)}
              >
                <div className="scene-thumb">
                  {item.output_url ? <video src={item.output_url} muted preload="metadata" /> : <span>No export yet</span>}
                </div>
                <div className="character-meta" style={{ width: "100%" }}>
                  <strong>{item.name}</strong>
                  <span>{item.description || "No description"}</span>
                  <div className="chip-row">
                    <span className="chip">{item.segment_count} scene(s)</span>
                    <span className="chip ref">{formatSeconds(item.duration_ms)}</span>
                    <span className={`chip ${item.status === "completed" ? "exp" : ""}`}>{item.status}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {episode && (
        <>
          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="detail-head">
              <div>
                <h2>{episode.name}</h2>
                <div className="panel-sub mono">{episode.id} · {formatSeconds(timelineTotal)} timeline</div>
              </div>
              <div className="row">
                {dirty && <span className="chip" style={{ borderColor: "var(--warn)" }}>Unsaved changes</span>}
                <StatusBadge status={episode.status} />
                <button className="btn sm" onClick={saveTimeline} disabled={saving || !dirty}>
                  {saving ? "Saving…" : "Save timeline"}
                </button>
                <button className="btn sm ghost" onClick={removeEpisode}>
                  Delete
                </button>
              </div>
            </div>

            <div className="timeline-bar">
              {timeline.segments.length === 0 ? (
                <div className="tiny muted" style={{ padding: "10px 12px" }}>Timeline is empty. Add a scene segment below.</div>
              ) : (
                timeline.segments.map((segment, index) => {
                  const asset = assetMap.get(segment.asset_id);
                  return (
                    <div
                      key={segment.id || index}
                      className={`timeline-segment${index % 2 ? " alt" : ""}`}
                      style={{ width: `${(segment.duration_ms / Math.max(1, timelineTotal)) * 100}%` }}
                      title={segment.label}
                    >
                      <span>{index + 1}</span>
                      <small>{formatSeconds(segment.duration_ms)}</small>
                      {asset?.kind === "video" ? <em>VIDEO</em> : null}
                    </div>
                  );
                })
              )}
            </div>

            <div className="row between" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
              <div className="row">
                <span className="chip">
                  Script:{" "}
                  {scriptState
                    ? scriptState.has_script
                      ? scriptState.latest_revision_number > 0
                        ? `rev ${scriptState.latest_revision_number} · ${scriptState.script_approved ? "approved" : "not approved"}`
                        : "installed · no validated revision"
                      : "not installed"
                    : "loading…"}
                </span>
                {scriptState?.storyboard_stale && <span className="chip pose">storyboard stale</span>}
                {scriptState?.has_script && (
                  <span className="tiny muted mono">{scriptState.current_sha256.slice(0, 12)}</span>
                )}
              </div>
              <button
                className="btn sm"
                onClick={approveScript}
                disabled={!scriptState?.has_script || scriptState.script_approved || scriptState.latest_revision_number === 0}
                title={
                  scriptState?.latest_revision_number === 0
                    ? "Install a validated script revision first"
                    : undefined
                }
              >
                {scriptState?.script_approved ? "Script approved" : "Approve script"}
              </button>
            </div>

            <div className="row between" style={{ marginTop: 12 }}>
              <div className="row">
                <span className="chip">{timeline.segments.length} scene(s)</span>
                <span className="chip ref">{timeline.audio.length} audio track(s)</span>
                <span className="chip">{formatSeconds(timelineTotal)}</span>
              </div>
              <div className="row">
                {["queued", "exporting"].includes(episode.status) ? (
                  <button className="btn" onClick={cancelExport}>Cancel export</button>
                ) : (
                  <button
                    className="btn primary"
                    onClick={exportEpisode}
                    disabled={exporting || timeline.segments.length === 0}
                  >
                    {exporting ? "Exporting…" : "Export MP4"}
                  </button>
                )}
              </div>
            </div>

            {["queued", "exporting"].includes(episode.status) && (
              <div className="stack" style={{ marginTop: 12 }}>
                <div className="meter-row">
                  <span>Rendering episode</span>
                  <strong>{Math.round(episode.progress)}%</strong>
                </div>
                <ProgressBar value={episode.progress} />
              </div>
            )}
            {episode.error && (
              <div style={{ marginTop: 12 }}>
                <Alert kind="error">{episode.error}</Alert>
              </div>
            )}
            {episode.log && (
              <>
                <div className="section-title" style={{ marginTop: 14 }}>Export log</div>
                <pre className="prompt-preview" style={{ whiteSpace: "pre-wrap", maxHeight: 220, overflow: "auto" }}>
                  {episode.log}
                </pre>
              </>
            )}
            {episode.output_url && (
              <>
                <div className="section-title" style={{ marginTop: 14 }}>Exported MP4</div>
                <video
                  controls
                  src={`${episode.output_url}?t=${encodeURIComponent(episode.updated_at)}`}
                  style={{ width: "100%", borderRadius: 10, background: "#000" }}
                />
                <div className="row between" style={{ marginTop: 8 }}>
                  <span className="tiny muted">
                    {episode.settings.width}×{episode.settings.height} · {episode.settings.fps} fps ·{" "}
                    {formatSeconds(episode.duration_ms)}
                  </span>
                  <div className="row">
                    <a
                      className="btn sm"
                      href={episode.output_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open MP4
                    </a>
                    <a className="btn sm" href={`${episode.output_url}?download=1`}>
                      Download MP4
                    </a>
                    {episode.subtitle_url && (
                      <a className="btn sm" href={episode.subtitle_url} download>
                        Download SRT
                      </a>
                    )}
                  </div>
                </div>
              </>
            )}
          </section>

          <div className="split">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Add Scene Segment</h2>
                  <div className="panel-sub">Uses existing keyframes and clips; nothing is regenerated.</div>
                </div>
              </div>
              {scenes.length === 0 ? (
                <div className="media-empty">
                  No scenes in this project. <Link className="link" to="/scenes">Create a scene</Link> first.
                </div>
              ) : (
                <>
                  <div className="form-grid">
                    <div className="field">
                      <label>Scene</label>
                      <select value={segmentSceneId} onChange={(event) => setSegmentSceneId(event.target.value)}>
                        {scenes.map((scene) => (
                          <option key={scene.id} value={scene.id}>{scene.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label>Visual</label>
                      <select value={segmentAssetId} onChange={(event) => setSegmentAssetId(event.target.value)}>
                        {segmentAssets.length === 0 && <option value="">No keyframes or clips</option>}
                        {segmentAssets.map((asset) => (
                          <option key={asset.id} value={asset.id}>
                            {asset.role} · {asset.label || asset.filename}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label>Duration (seconds)</label>
                      <input
                        type="number"
                        min={0.1}
                        step={0.1}
                        value={segmentDuration}
                        onChange={(event) => setSegmentDuration(Number(event.target.value))}
                      />
                    </div>
                    <div className="field">
                      <label>Transition into segment</label>
                      <select
                        value={segmentTransition}
                        onChange={(event) => setSegmentTransition(event.target.value as "cut" | "fade")}
                      >
                        <option value="cut">Cut</option>
                        <option value="fade">Fade through black</option>
                      </select>
                    </div>
                    <div className="field">
                      <label>Camera motion (images)</label>
                      <select
                        value={segmentMotion}
                        onChange={(event) =>
                          setSegmentMotion(
                            event.target.value as "none" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right"
                          )
                        }
                      >
                        <option value="none">None</option>
                        <option value="zoom_in">Zoom in</option>
                        <option value="zoom_out">Zoom out</option>
                        <option value="pan_left">Pan left</option>
                        <option value="pan_right">Pan right</option>
                      </select>
                    </div>
                  </div>
                  <div className="row between" style={{ marginTop: 12 }}>
                    <span className="tiny muted">
                      {segmentScene ? `Scene duration ${segmentScene.duration}s` : "Choose a scene"}
                    </span>
                    <button className="btn primary" onClick={addSegment} disabled={!segmentAssetId}>
                      Add segment + dialogue audio
                    </button>
                  </div>
                </>
              )}
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Export Settings</h2>
                  <div className="panel-sub">FFmpeg writes a new MP4; previous exports are kept.</div>
                </div>
              </div>
              <div className="form-grid">
                <div className="field span-2">
                  <label>Resolution</label>
                  <select
                    value={SIZE_PRESETS.findIndex(
                      (preset) => preset.width === timeline.settings.width && preset.height === timeline.settings.height
                    )}
                    onChange={(event) => {
                      const preset = SIZE_PRESETS[Number(event.target.value)];
                      if (preset) updateSettings({ width: preset.width, height: preset.height });
                    }}
                  >
                    {SIZE_PRESETS.map((preset, index) => (
                      <option key={preset.label} value={index}>{preset.label}</option>
                    ))}
                    {SIZE_PRESETS.every(
                      (preset) => preset.width !== timeline.settings.width || preset.height !== timeline.settings.height
                    ) && (
                      <option value={-1}>
                        {timeline.settings.width}×{timeline.settings.height} · custom
                      </option>
                    )}
                  </select>
                </div>
                <div className="field">
                  <label>FPS</label>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    step={1}
                    value={timeline.settings.fps}
                    onChange={(event) => updateSettings({ fps: Number(event.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Fade duration (ms)</label>
                  <input
                    type="number"
                    min={0}
                    max={2000}
                    step={50}
                    value={timeline.settings.fade_duration_ms}
                    onChange={(event) => updateSettings({ fade_duration_ms: Number(event.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>Subtitles</label>
                  <select
                    value={timeline.settings.subtitles}
                    onChange={(event) => updateSettings({ subtitles: event.target.value as "soft" | "none" })}
                  >
                    <option value="soft">Embed soft track from dialogue</option>
                    <option value="none">No subtitles</option>
                  </select>
                </div>
                <div className="field">
                  <label>Background music</label>
                  <select
                    value={timeline.settings.background_music_asset_id || ""}
                    onChange={(event) =>
                      updateSettings({ background_music_asset_id: event.target.value || null })
                    }
                  >
                    <option value="">None</option>
                    {audioAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>{asset.filename}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Music volume ({timeline.settings.background_music_volume.toFixed(2)})</label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={timeline.settings.background_music_volume}
                    onChange={(event) =>
                      updateSettings({ background_music_volume: Number(event.target.value) })
                    }
                  />
                </div>
              </div>
            </section>
          </div>

          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h2>Scene Segments</h2>
                <div className="panel-sub">Order, duration, trim and transition are timeline-only edits.</div>
              </div>
            </div>
            {timeline.segments.length === 0 ? (
              <div className="media-empty">No segments yet. Add one above.</div>
            ) : (
              <div className="stack">
                {timeline.segments.map((segment, index) => {
                  const asset = assetMap.get(segment.asset_id);
                  return (
                    <div className="dialogue-line" key={segment.id || index}>
                      <div className="dialogue-head">
                        <span className="dialogue-index">{index + 1}</span>
                        <div className="dialogue-who">
                          <strong>{segment.label}</strong>
                          <span className="tiny muted">
                            {segment.kind} · {asset?.filename || segment.asset_id}
                          </span>
                        </div>
                        <div className="row">
                          <button className="btn sm" onClick={() => moveSegment(index, -1)} disabled={index === 0}>↑</button>
                          <button
                            className="btn sm"
                            onClick={() => moveSegment(index, 1)}
                            disabled={index === timeline.segments.length - 1}
                          >
                            ↓
                          </button>
                          <button className="btn sm" onClick={() => removeSegment(index)}>Remove</button>
                        </div>
                      </div>
                      <div className="form-grid">
                        <div className="field">
                          <label>Duration (seconds)</label>
                          <input
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={segment.duration_ms / 1000}
                            onChange={(event) =>
                              updateSegment(index, { duration_ms: Math.round(Number(event.target.value) * 1000) })
                            }
                          />
                        </div>
                        <div className="field">
                          <label>Trim start (seconds)</label>
                          <input
                            type="number"
                            min={0}
                            step={0.1}
                            value={segment.trim_start_ms / 1000}
                            onChange={(event) =>
                              updateSegment(index, { trim_start_ms: Math.round(Number(event.target.value) * 1000) })
                            }
                          />
                        </div>
                        <div className="field">
                          <label>Transition</label>
                          <select
                            value={segment.transition}
                            onChange={(event) =>
                              updateSegment(index, { transition: event.target.value as "cut" | "fade" })
                            }
                          >
                            <option value="cut">Cut</option>
                            <option value="fade">Fade through black</option>
                          </select>
                        </div>
                        <div className="field">
                          <label>Camera motion</label>
                          <select
                            value={segment.motion || "none"}
                            onChange={(event) =>
                              updateSegment(index, {
                                motion: event.target.value as
                                  | "none"
                                  | "zoom_in"
                                  | "zoom_out"
                                  | "pan_left"
                                  | "pan_right",
                              })
                            }
                          >
                            <option value="none">None</option>
                            <option value="zoom_in">Zoom in</option>
                            <option value="zoom_out">Zoom out</option>
                            <option value="pan_left">Pan left</option>
                            <option value="pan_right">Pan right</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Audio Tracks</h2>
                <div className="panel-sub">Dialogue, music and effects are mixed at their start offsets.</div>
              </div>
              <button className="btn sm" onClick={addAudio}>Add audio track</button>
            </div>
            {timeline.audio.length === 0 ? (
              <div className="media-empty">No audio tracks. Adding a scene segment copies its dialogue audio automatically.</div>
            ) : (
              <div className="stack">
                {timeline.audio.map((item, index) => (
                  <div className="dialogue-line" key={item.id || index}>
                    <div className="form-grid">
                      <div className="field span-2">
                        <label>Audio asset</label>
                        <select
                          value={item.asset_id}
                          onChange={(event) => {
                            const asset = assetMap.get(event.target.value);
                            updateAudio(index, {
                              asset_id: event.target.value,
                              label: asset?.filename || item.label,
                            });
                          }}
                        >
                          {audioAssets.map((asset) => (
                            <option key={asset.id} value={asset.id}>{asset.filename}</option>
                          ))}
                          {!audioAssets.some((asset) => asset.id === item.asset_id) && (
                            <option value={item.asset_id}>{item.label || item.asset_id}</option>
                          )}
                        </select>
                      </div>
                      <div className="field">
                        <label>Start (seconds)</label>
                        <input
                          type="number"
                          min={0}
                          step={0.1}
                          value={item.start_ms / 1000}
                          onChange={(event) =>
                            updateAudio(index, { start_ms: Math.round(Number(event.target.value) * 1000) })
                          }
                        />
                      </div>
                      <div className="field">
                        <label>Volume ({item.volume.toFixed(2)})</label>
                        <input
                          type="range"
                          min={0}
                          max={1.5}
                          step={0.05}
                          value={item.volume}
                          onChange={(event) => updateAudio(index, { volume: Number(event.target.value) })}
                        />
                      </div>
                      <div className="field">
                        <label>Loop</label>
                        <select
                          value={item.loop ? "yes" : "no"}
                          onChange={(event) => updateAudio(index, { loop: event.target.value === "yes" })}
                        >
                          <option value="no">Play once</option>
                          <option value="yes">Loop to episode end</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>&nbsp;</label>
                        <button className="btn sm" onClick={() => removeAudio(index)}>Remove</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
