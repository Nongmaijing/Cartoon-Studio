import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Background, Character, Job, MediaItem, Scene, SceneReference, WorkflowEntry } from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";
import { AutoGrowTextarea } from "../components/AutoGrowTextarea";
import { JobTable } from "../components/JobTable";
import { QueuePanel, elapsedSeconds, etaSeconds, formatDuration } from "../components/QueuePanel";

const IMAGE_SIZES = [
  { label: "512×288 · fast", width: 512, height: 288 },
  { label: "768×432 · balanced", width: 768, height: 432 },
  { label: "1024×576 · detailed", width: 1024, height: 576 },
  { label: "1216×832 · SDXL", width: 1216, height: 832 },
];

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

interface SceneForm {
  name: string;
  description: string;
  dialogue: string;
  action: string;
  camera: string;
  duration: number;
}

const EMPTY_FORM: SceneForm = {
  name: "",
  description: "",
  dialogue: "",
  action: "",
  camera: "",
  duration: 5,
};

function isActive(job: Job | null): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

function nearestSizeIndex(sizes: { width: number; height: number }[], width?: number, height?: number): number {
  if (!width || !height) return 0;
  const exact = sizes.findIndex((size) => size.width === width && size.height === height);
  if (exact >= 0) return exact;
  let best = 0;
  let bestScore = Number.POSITIVE_INFINITY;
  sizes.forEach((size, index) => {
    const score = Math.abs(size.width - width) + Math.abs(size.height - height);
    if (score < bestScore) {
      bestScore = score;
      best = index;
    }
  });
  return best;
}

export default function Scenes() {
  const { selectedId, projects } = useProject();
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState("");
  const [characters, setCharacters] = useState<Character[]>([]);
  const [backgrounds, setBackgrounds] = useState<Background[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowEntry[]>([]);
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [references, setReferences] = useState<SceneReference[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [queue, setQueue] = useState<Awaited<ReturnType<typeof api.queue>> | null>(null);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [setupLoading, setSetupLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [newForm, setNewForm] = useState<SceneForm>({ ...EMPTY_FORM });
  const [newBackgroundId, setNewBackgroundId] = useState("");

  const [form, setForm] = useState<SceneForm>({ ...EMPTY_FORM });
  const [backgroundId, setBackgroundId] = useState("");
  const [castIds, setCastIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const [kind, setKind] = useState<"keyframe" | "video">("keyframe");
  const [imageWorkflow, setImageWorkflow] = useState("");
  const [videoWorkflow, setVideoWorkflow] = useState("");
  const [imageSizeIndex, setImageSizeIndex] = useState(2);
  const [videoSizeIndex, setVideoSizeIndex] = useState(0);
  const [steps, setSteps] = useState(28);
  const [cfg, setCfg] = useState(6.5);
  const [seed, setSeed] = useState(-1);
  const [videoSteps, setVideoSteps] = useState(20);
  const [videoCfg, setVideoCfg] = useState(5);
  const [videoSeed, setVideoSeed] = useState(-1);
  const [length, setLength] = useState(121);
  const [fps, setFps] = useState(24);
  const [startImage, setStartImage] = useState("");
  const [extraPrompt, setExtraPrompt] = useState("");
  const [referenceAssetId, setReferenceAssetId] = useState("");
  const [referenceMode, setReferenceMode] = useState<"identity" | "pose">("identity");
  const [denoise, setDenoise] = useState(0.55);
  const [controlStrength, setControlStrength] = useState(0.8);

  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");

  const selected = useMemo(
    () => scenes.find((scene) => scene.id === selectedSceneId) || null,
    [scenes, selectedSceneId]
  );

  const imageWorkflows = useMemo(
    () => workflows.filter((workflow) => workflow.format === "api" && workflow.kind === "image"),
    [workflows]
  );
  const videoWorkflows = useMemo(
    () => workflows.filter((workflow) => workflow.format === "api" && workflow.kind === "video"),
    [workflows]
  );

  const keyframes = useMemo(() => media.filter((item) => item.role === "keyframe"), [media]);
  const videos = useMemo(() => media.filter((item) => item.role === "video"), [media]);

  const refreshScenes = useCallback(async () => {
    if (!selectedId) {
      setScenes([]);
      setSelectedSceneId("");
      return;
    }
    try {
      const list = await api.scenes(selectedId);
      setScenes(list);
      setSelectedSceneId((current) =>
        current && list.some((scene) => scene.id === current) ? current : list[0]?.id || ""
      );
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  const loadMedia = useCallback(async (sceneId: string) => {
    if (!sceneId) {
      setMedia([]);
      setReferences([]);
      setJobs([]);
      return;
    }
    try {
      const [mediaList, referenceList, jobList] = await Promise.all([
        api.sceneMedia(sceneId),
        api.sceneReferences(sceneId),
        api.sceneJobs(sceneId),
      ]);
      setMedia(mediaList);
      setReferences(referenceList);
      setJobs(jobList);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    refreshScenes();
  }, [refreshScenes]);

  useEffect(() => {
    if (!selectedId) {
      setCharacters([]);
      setBackgrounds([]);
      setWorkflows([]);
      setSetupLoading(false);
      return;
    }
    setSetupLoading(true);
    Promise.allSettled([
      api.characters(selectedId),
      api.backgrounds(selectedId),
      api.workflows(),
    ])
      .then(([characterResult, backgroundResult, workflowResult]) => {
        const failures: string[] = [];
        if (characterResult.status === "fulfilled") setCharacters(characterResult.value);
        else failures.push(`characters: ${String(characterResult.reason)}`);
        if (backgroundResult.status === "fulfilled") setBackgrounds(backgroundResult.value);
        else failures.push(`backgrounds: ${String(backgroundResult.reason)}`);
        if (workflowResult.status === "fulfilled") setWorkflows(workflowResult.value);
        else failures.push(`workflows: ${String(workflowResult.reason)}`);
        if (failures.length) setError(failures.join(" · "));
      })
      .finally(() => setSetupLoading(false));
  }, [selectedId]);

  const imageWorkflowNeedsReference = (workflow?: WorkflowEntry) =>
    Boolean(workflow?.roles?.includes("input_image"));
  const selectedImageWorkflow = workflows.find((workflow) => workflow.id === imageWorkflow);

  useEffect(() => {
    if (!workflows.length) return;
    const compatible = workflows.filter(
      (workflow) =>
        workflow.format === "api" &&
        workflow.kind === "image" &&
        workflow.runnable !== false &&
        imageWorkflowNeedsReference(workflow) === Boolean(referenceAssetId)
    );
    const current = workflows.find((workflow) => workflow.id === imageWorkflow);
    if (current && imageWorkflowNeedsReference(current) === Boolean(referenceAssetId)) return;
    const preferredIds = referenceAssetId
      ? ["sdxl_img2img", "sdxl_controlnet_pose", "sd15_img2img"]
      : ["sdxl_txt2img", "sd15_txt2img"];
    const preferred = preferredIds
      .map((id) => compatible.find((workflow) => workflow.id === id))
      .find(Boolean);
    setImageWorkflow(preferred?.id || compatible[0]?.id || "");
  }, [workflows, referenceAssetId, imageWorkflow]);

  useEffect(() => {
    if (!workflows.length) return;
    const compatible = workflows.filter(
      (workflow) =>
        workflow.format === "api" &&
        workflow.kind === "video" &&
        workflow.runnable !== false &&
        imageWorkflowNeedsReference(workflow) === Boolean(startImage)
    );
    const current = workflows.find((workflow) => workflow.id === videoWorkflow);
    if (current && imageWorkflowNeedsReference(current) === Boolean(startImage)) return;
    setVideoWorkflow(compatible[0]?.id || "");
  }, [workflows, startImage, videoWorkflow]);

  useEffect(() => {
    loadMedia(selectedSceneId);
    setActiveJob(null);
    setLastPrompt("");
    if (!selectedSceneId) return;
    api
      .sceneJobs(selectedSceneId)
      .then((list) => {
        const running = list.find((job) => job.status === "queued" || job.status === "running");
        if (running) setActiveJob(running);
      })
      .catch(() => undefined);
  }, [selectedSceneId, loadMedia]);

  useEffect(() => {
    if (!selected) {
      setForm({ ...EMPTY_FORM });
      setBackgroundId("");
      setCastIds([]);
      return;
    }
    setForm({
      name: selected.name,
      description: selected.description,
      dialogue: selected.dialogue,
      action: selected.action,
      camera: selected.camera,
      duration: selected.duration,
    });
    setBackgroundId(selected.settings.background_id || selected.background?.id || "");
    setCastIds(selected.cast.map((member) => member.character_id));
    setImageWorkflow(selected.settings.workflow_id || "");
    setVideoWorkflow(selected.settings.video_workflow_id || "");
    setImageSizeIndex(
      selected.settings.width && selected.settings.height
        ? nearestSizeIndex(IMAGE_SIZES, selected.settings.width, selected.settings.height)
        : 2
    );
    setVideoSizeIndex(
      selected.settings.video_width && selected.settings.video_height
        ? nearestSizeIndex(VIDEO_SIZES, selected.settings.video_width, selected.settings.video_height)
        : 0
    );
    setSteps(selected.settings.steps ?? 24);
    setCfg(selected.settings.cfg ?? 7);
    setSeed(selected.settings.seed ?? -1);
    setVideoSteps(selected.settings.video_steps ?? 20);
    setVideoCfg(selected.settings.video_cfg ?? 5);
    setVideoSeed(selected.settings.video_seed ?? -1);
    setLength(selected.settings.length ?? 121);
    setFps(selected.settings.fps ?? 24);
    setStartImage(selected.settings.start_image || "");
    setReferenceAssetId(selected.settings.reference_asset_id || "");
    setReferenceMode(selected.settings.reference_mode || "identity");
    setDenoise(selected.settings.denoise ?? 0.55);
    setControlStrength(selected.settings.control_strength ?? 0.8);
  }, [selected?.id, selected?.updated_at]);

  useEffect(() => {
    if (!activeJob || !isActive(activeJob)) return;
    const jobId = activeJob.id;
    const timer = window.setInterval(async () => {
      try {
        const job = await api.job(jobId);
        setActiveJob(job);
        if (["completed", "failed", "cancelled", "interrupted"].includes(job.status)) {
          window.clearInterval(timer);
          await refreshScenes();
          await loadMedia(selectedSceneId);
          if (job.status === "completed") {
            setNotice("Shot output saved and attached to the scene.");
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
  }, [activeJob?.id, activeJob?.status, refreshScenes, loadMedia, selectedSceneId]);

  useEffect(() => {
    const refreshQueue = () => api.queue().then(setQueue).catch(() => undefined);
    refreshQueue();
    const timer = window.setInterval(refreshQueue, 2000);
    return () => window.clearInterval(timer);
  }, []);

  const createScene = async () => {
    if (!selectedId || !newForm.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await api.createScene({
        project_id: selectedId,
        name: newForm.name.trim(),
        description: newForm.description.trim(),
        dialogue: newForm.dialogue.trim(),
        action: newForm.action.trim(),
        camera: newForm.camera.trim(),
        duration: newForm.duration,
        background_id: newBackgroundId || null,
      });
      setNewForm({ ...EMPTY_FORM });
      setNewBackgroundId("");
      setShowCreate(false);
      await refreshScenes();
      setSelectedSceneId(created.id);
      setNotice(`Created scene "${created.name}".`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const saveScene = async () => {
    if (!selected) return;
    setSaving(true);
    setError("");
    const imageSize = IMAGE_SIZES[imageSizeIndex];
    const videoSize = VIDEO_SIZES[videoSizeIndex];
    try {
      await api.updateScene(selected.id, {
        name: form.name.trim(),
        description: form.description.trim(),
        dialogue: form.dialogue.trim(),
        action: form.action.trim(),
        camera: form.camera.trim(),
        duration: form.duration,
        background_id: backgroundId || null,
        character_ids: castIds,
        settings: {
          workflow_id: imageWorkflow || undefined,
          video_workflow_id: videoWorkflow || undefined,
          width: imageSize.width,
          height: imageSize.height,
          steps,
          cfg,
          seed,
          video_width: videoSize.width,
          video_height: videoSize.height,
          video_steps: videoSteps,
          video_cfg: videoCfg,
          video_seed: videoSeed,
          length,
          fps,
          sampler: "uni_pc",
          scheduler: "simple",
          start_image: startImage,
          reference_asset_id: referenceAssetId || null,
          reference_mode: referenceMode,
          denoise,
          control_strength: controlStrength,
        },
      });
      await refreshScenes();
      setNotice("Scene saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  };

  const approveSelectedScene = async () => {
    if (!selected) return;
    if (!window.confirm(`Approve the saved version of “${selected.name}”? Unsaved edits are not included.`)) return;
    setError("");
    try {
      await api.approveScene(selected.id);
      await refreshScenes();
      setNotice("Scene approved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const rejectSelectedScene = async () => {
    if (!selected) return;
    const notes = window.prompt("Why is this scene being rejected?");
    if (notes === null) return;
    setError("");
    try {
      await api.rejectScene(selected.id, notes);
      await refreshScenes();
      setNotice("Scene rejected.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const toggleCast = async (characterId: string) => {
    if (!selected) return;
    setError("");
    try {
      if (castIds.includes(characterId)) {
        await api.removeSceneCast(selected.id, characterId);
      } else {
        await api.addSceneCast(selected.id, characterId);
      }
      await refreshScenes();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const generate = async () => {
    if (!selected) return;
    setError("");
    setNotice("");
    if (kind === "keyframe") {
      if (!selectedImageWorkflow) {
        setError("No image workflow is selected.");
        return;
      }
      if (imageWorkflowNeedsReference(selectedImageWorkflow) !== Boolean(referenceAssetId)) {
        setError("Choose a reference image for this workflow, or select a text-to-image workflow.");
        return;
      }
    }
    setGenerating(true);
    const imageSize = IMAGE_SIZES[imageSizeIndex];
    const videoSize = VIDEO_SIZES[videoSizeIndex];
    try {
      const result = await api.generateScene(selected.id, {
        kind,
        workflow_id: kind === "keyframe" ? imageWorkflow || undefined : videoWorkflow || undefined,
        prompt: extraPrompt.trim() || undefined,
        width: kind === "keyframe" ? imageSize.width : videoSize.width,
        height: kind === "keyframe" ? imageSize.height : videoSize.height,
        steps: kind === "keyframe" ? steps : videoSteps,
        cfg: kind === "keyframe" ? cfg : videoCfg,
        seed: kind === "keyframe" ? seed : videoSeed,
        length: kind === "video" ? length : undefined,
        fps: kind === "video" ? fps : undefined,
        start_image: kind === "video" ? startImage : undefined,
        reference_asset_id: kind === "keyframe" ? referenceAssetId || undefined : undefined,
        reference_mode: kind === "keyframe" ? referenceMode : undefined,
        denoise: kind === "keyframe" ? denoise : undefined,
        control_strength: kind === "keyframe" ? controlStrength : undefined,
      });
      setActiveJob(result.job);
      setLastPrompt(result.prompt);
      if (result.fallback) {
        setNotice("Pose mode requested, but ControlNet is not installed. Falling back to image-to-image with the pose reference.");
      } else if (result.mode === "ipadapter-identity") {
        setNotice("Identity mode: IP-Adapter conditioned the keyframe on the selected reference.");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setGenerating(false);
    }
  };

  const cancel = async (job: Job) => {
    try {
      await api.cancelJob(job.id);
      setQueue(await api.queue());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const upscaleKeyframe = async (assetId: string) => {
    if (!selected) return;
    setError("");
    setNotice("");
    try {
      const result = await api.upscaleAsset(assetId, {
        owner_type: "scene",
        owner_id: selected.id,
        role: "keyframe",
        label: "upscaled",
      });
      setActiveJob(result.job);
      setNotice("4× upscale queued. The new keyframe will appear when complete.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Scenes" subtitle="Turn characters and backgrounds into producible cartoon shots." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          building scenes.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Scenes"
        subtitle="Combine a background, cast, action, dialogue and camera direction into one shot — then generate a keyframe or animate it."
        actions={
          <button className="btn primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Close" : "New scene"}
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>New Scene</h2>
              <div className="panel-sub">Saved into {projects.find((project) => project.id === selectedId)?.name}</div>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Name</label>
              <input
                value={newForm.name}
                placeholder="Milo crosses the clearing"
                onChange={(event) => setNewForm({ ...newForm, name: event.target.value })}
              />
            </div>
            <div className="field">
              <label>Background</label>
              <select value={newBackgroundId} onChange={(event) => setNewBackgroundId(event.target.value)}>
                <option value="">No background yet</option>
                {backgrounds.map((background) => (
                  <option key={background.id} value={background.id}>
                    {background.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field span-2">
              <label>Description</label>
              <AutoGrowTextarea
                minRows={4}
                maxHeight={320}
                value={newForm.description}
                placeholder="Milo steps out of the trees and spots a glowing mushroom."
                onChange={(event) => setNewForm({ ...newForm, description: event.target.value })}
              />
            </div>
          </div>
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={createScene} disabled={busy || !newForm.name.trim()}>
              {busy ? "Creating…" : "Create scene"}
            </button>
          </div>
        </section>
      )}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Scene Library</h2>
            <div className="panel-sub">{scenes.length} scene(s) in this project</div>
          </div>
        </div>
        {scenes.length === 0 ? (
          <EmptyState>No scenes yet. Use “New scene” to build the first shot.</EmptyState>
        ) : (
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", marginBottom: 0 }}>
            {scenes.map((scene) => (
              <button
                key={scene.id}
                className={`character-item${scene.id === selectedSceneId ? " active" : ""}`}
                style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
                onClick={() => setSelectedSceneId(scene.id)}
              >
                <div className="scene-thumb">
                  {scene.cover_url ? (
                    <img src={scene.cover_url} alt={scene.name} />
                  ) : (
                    <span>No keyframe yet</span>
                  )}
                </div>
                <div className="character-meta" style={{ width: "100%" }}>
                  <strong>{scene.name}</strong>
                  <span>{scene.description || "No description"}</span>
                  <div className="chip-row">
                    <span className="chip">{scene.cast.length} cast</span>
                    <span className="chip ref">{scene.keyframe_count} key</span>
                    <span className="chip exp">{scene.video_count} clip</span>
                    <span className="chip">{scene.dialogue_count} line</span>
                    <span className="chip">{scene.duration}s</span>
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
                <div className="row">
                  <span className={`chip ${selected.approval_status === "approved" ? "exp" : selected.approval_status === "rejected" ? "pose" : ""}`}>
                    {selected.approval_status || "draft"}
                  </span>
                  <button className="btn sm" onClick={approveSelectedScene} disabled={selected.approval_status === "approved"}>
                    Approve
                  </button>
                  <button className="btn sm ghost" onClick={rejectSelectedScene} disabled={selected.approval_status === "rejected"}>
                    Reject
                  </button>
                  <button className="btn sm primary" onClick={saveScene} disabled={saving || !form.name.trim()}>
                    {saving ? "Saving…" : "Save scene"}
                  </button>
                </div>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>Name</label>
                  <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                </div>
                <div className="field">
                  <label>Duration (seconds)</label>
                  <input
                    type="number"
                    min={0.5}
                    max={120}
                    step={0.5}
                    value={form.duration}
                    onChange={(event) => setForm({ ...form, duration: Number(event.target.value) })}
                  />
                </div>
                <div className="field span-2">
                  <label>Description</label>
                  <AutoGrowTextarea
                    minRows={4}
                    maxHeight={320}
                    value={form.description}
                    placeholder="What the audience sees in this shot: setting, mood, key props."
                    onChange={(event) => setForm({ ...form, description: event.target.value })}
                  />
                </div>
                <div className="field span-2">
                  <label>Action</label>
                  <AutoGrowTextarea
                    minRows={3}
                    maxHeight={240}
                    value={form.action}
                    placeholder="Milo crouches, then leaps over the log."
                    onChange={(event) => setForm({ ...form, action: event.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Camera</label>
                  <input
                    value={form.camera}
                    placeholder="slow push in, eye level"
                    onChange={(event) => setForm({ ...form, camera: event.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Background</label>
                  <select value={backgroundId} onChange={(event) => setBackgroundId(event.target.value)}>
                    <option value="">No background</option>
                    {backgrounds.map((background) => (
                      <option key={background.id} value={background.id}>
                        {background.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field span-2">
                  <label>
                    Dialogue script ·{" "}
                    <Link className="link" to="/voice">
                      import and voice it in Voice &amp; Dialogue
                    </Link>
                  </label>
                  <AutoGrowTextarea
                    minRows={3}
                    maxHeight={320}
                    value={form.dialogue}
                    placeholder="Character: “A line of dialogue.”"
                    onChange={(event) => setForm({ ...form, dialogue: event.target.value })}
                  />
                </div>
              </div>

              <div className="section-title" style={{ marginTop: 16 }}>Cast</div>
              {setupLoading ? (
                <div className="media-empty">Loading cast and backgrounds…</div>
              ) : characters.length === 0 ? (
                <div className="media-empty">
                  No characters in this project. <Link className="link" to="/characters">Create a character</Link> first.
                </div>
              ) : (
                <div className="character-list">
                  {characters.map((character) => {
                    const active = castIds.includes(character.id);
                    return (
                      <button
                        key={character.id}
                        className={`character-item${active ? " active" : ""}`}
                        onClick={() => toggleCast(character.id)}
                      >
                        <div className="character-avatar">
                          {character.cover_url ? (
                            <img src={character.cover_url} alt={character.name} />
                          ) : (
                            character.name.slice(0, 2).toUpperCase()
                          )}
                        </div>
                        <div className="character-meta">
                          <strong>{character.name}</strong>
                          <span>{active ? "In this scene" : "Click to add to scene"}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}

              {selected.background && (
                <>
                  <div className="section-title" style={{ marginTop: 16 }}>Location</div>
                  <div className="row" style={{ alignItems: "flex-start", gap: 12 }}>
                    {selected.background.cover_url && (
                      <img className="scene-location" src={selected.background.cover_url} alt={selected.background.name} />
                    )}
                    <div>
                      <strong>{selected.background.name}</strong>
                      <div className="tiny muted" style={{ marginTop: 4 }}>{selected.background.description}</div>
                      <div className="tiny muted" style={{ marginTop: 4 }}>
                        {selected.background.width}×{selected.background.height}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Generate Shot</h2>
                  <div className="panel-sub">Local keyframe model, Wan 2.2 motion</div>
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
                        ? `${formatDuration(elapsedSeconds(activeJob))} elapsed`
                        : activeJob.status}
                    </span>
                    <span>
                      {activeJob.status === "running" && etaSeconds(activeJob) !== null
                        ? `~${formatDuration(etaSeconds(activeJob))} left`
                        : ""}
                    </span>
                  </div>
                  {activeJob.status === "failed" && (
                    <div className="tiny" style={{ color: "var(--danger)" }}>{activeJob.error}</div>
                  )}
                </div>
              )}

              <div className="segmented">
                <button className={kind === "keyframe" ? "active" : ""} onClick={() => setKind("keyframe")}>
                  Keyframe
                </button>
                <button className={kind === "video" ? "active" : ""} onClick={() => setKind("video")}>
                  Animate
                </button>
              </div>

              <div className="form-grid" style={{ marginTop: 12 }}>
                <div className="field">
                  <label>{kind === "keyframe" ? "Image workflow" : "Video workflow"}</label>
                  <select
                    value={kind === "keyframe" ? imageWorkflow : videoWorkflow}
                    onChange={(event) =>
                      kind === "keyframe" ? setImageWorkflow(event.target.value) : setVideoWorkflow(event.target.value)
                    }
                  >
                    {(kind === "keyframe" ? imageWorkflows : videoWorkflows).map((workflow) => (
                      <option
                        key={workflow.id}
                        value={workflow.id}
                        disabled={
                          workflow.runnable === false ||
                          imageWorkflowNeedsReference(workflow) !==
                            Boolean(kind === "keyframe" ? referenceAssetId : startImage)
                        }
                      >
                        {workflow.name}
                        {workflow.runnable === false ? " (unavailable)" : ""}
                        {imageWorkflowNeedsReference(workflow) !==
                        Boolean(kind === "keyframe" ? referenceAssetId : startImage)
                          ? " (needs reference)"
                          : ""}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>{kind === "keyframe" ? "Resolution" : "Video resolution"}</label>
                  <select
                    value={kind === "keyframe" ? imageSizeIndex : videoSizeIndex}
                    onChange={(event) =>
                      kind === "keyframe"
                        ? setImageSizeIndex(Number(event.target.value))
                        : setVideoSizeIndex(Number(event.target.value))
                    }
                  >
                    {(kind === "keyframe" ? IMAGE_SIZES : VIDEO_SIZES).map((size, index) => (
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
                    value={kind === "keyframe" ? steps : videoSteps}
                    onChange={(event) =>
                      kind === "keyframe" ? setSteps(Number(event.target.value)) : setVideoSteps(Number(event.target.value))
                    }
                  />
                </div>
                <div className="field">
                  <label>CFG</label>
                  <input
                    type="number"
                    step={0.5}
                    value={kind === "keyframe" ? cfg : videoCfg}
                    onChange={(event) =>
                      kind === "keyframe" ? setCfg(Number(event.target.value)) : setVideoCfg(Number(event.target.value))
                    }
                  />
                </div>
                <div className="field">
                  <label>Seed (-1 = random)</label>
                  <input
                    type="number"
                    value={kind === "keyframe" ? seed : videoSeed}
                    onChange={(event) =>
                      kind === "keyframe" ? setSeed(Number(event.target.value)) : setVideoSeed(Number(event.target.value))
                    }
                  />
                </div>
                {kind === "video" && (
                  <>
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
                    <div className="field span-2">
                      <label>Start image (image-to-video)</label>
                      <select value={startImage} onChange={(event) => setStartImage(event.target.value)}>
                        <option value="">None — text-to-video</option>
                        {keyframes.map((item) => (
                          <option key={item.link_id} value={item.id}>
                            Keyframe {item.filename}
                          </option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
                <div className="field span-2">
                  <label>Extra prompt (optional)</label>
                  <input
                    value={extraPrompt}
                    placeholder="e.g. leaves blowing in the wind"
                    onChange={(event) => setExtraPrompt(event.target.value)}
                  />
                </div>
                {kind === "keyframe" && (
                  <>
                    <div className="field">
                      <label>Reference image</label>
                      <select value={referenceAssetId} onChange={(event) => setReferenceAssetId(event.target.value)}>
                        <option value="">None — text-to-image</option>
                        {references.map((reference) => (
                          <option key={`${reference.source}-${reference.asset_id}`} value={reference.asset_id}>
                            {reference.character_name} · {reference.role} · {reference.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label>Reference mode</label>
                      <select
                        value={referenceMode}
                        onChange={(event) => setReferenceMode(event.target.value as "identity" | "pose")}
                      >
                        <option value="identity">Identity — keep the design</option>
                        <option value="pose">Pose — match the reference pose</option>
                      </select>
                    </div>
                    {referenceAssetId && (
                      <div className="field">
                        <label>Denoise ({denoise.toFixed(2)})</label>
                        <input
                          type="range"
                          min={0.1}
                          max={1}
                          step={0.05}
                          value={denoise}
                          onChange={(event) => setDenoise(Number(event.target.value))}
                        />
                      </div>
                    )}
                    {referenceAssetId && referenceMode === "pose" && (
                      <div className="field">
                        <label>ControlNet strength ({controlStrength.toFixed(2)})</label>
                        <input
                          type="range"
                          min={0}
                          max={2}
                          step={0.05}
                          value={controlStrength}
                          onChange={(event) => setControlStrength(Number(event.target.value))}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>

              {kind === "keyframe" && referenceAssetId && (
                <div className="tiny muted" style={{ marginTop: 8 }}>
                  {referenceMode === "pose"
                    ? "Pose mode uses ControlNet when installed; otherwise it falls back to image-to-image with the pose reference."
                    : "Identity mode re-renders the reference at the chosen denoise so the cast design stays consistent."}
                </div>
              )}

              {kind === "video" && (
                <Alert kind="warn">
                  Wan 2.2 on 6 GB VRAM is slow: 121 frames at 720p can take 20+ minutes. Use the 5-frame
                  pipeline test first.
                </Alert>
              )}

              <div className="row between" style={{ marginTop: 12 }}>
                <span className="tiny muted">
                  {kind === "keyframe"
                    ? "One keyframe, saved to this scene."
                    : startImage
                    ? "Image-to-video: the keyframe becomes frame one."
                    : "Text-to-video: Wan invents the motion from the prompt."}
                </span>
                <button className="btn primary" onClick={generate} disabled={generating || isActive(activeJob)}>
                  {generating ? "Queuing…" : isActive(activeJob) ? "Generating…" : kind === "keyframe" ? "Generate keyframe" : "Animate shot"}
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

          <div className="split">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Keyframes</h2>
                  <div className="panel-sub">{keyframes.length} saved image(s) · 4× upscale available</div>
                </div>
              </div>
              {keyframes.length === 0 ? (
                <div className="media-empty">No keyframes yet. Generate one above.</div>
              ) : (
                <div className="media-grid">
                  {keyframes.map((item) => (
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
                          onClick={() => upscaleKeyframe(item.id)}
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
                  <h2>Clips</h2>
                  <div className="panel-sub">{videos.length} saved video(s)</div>
                </div>
              </div>
              {videos.length === 0 ? (
                <div className="media-empty">No animated clips yet. Use Animate above.</div>
              ) : (
                <div className="media-grid">
                  {videos.map((item) => (
                    <div key={item.link_id} className="media-card landscape">
                      <video src={item.url} controls muted loop playsInline preload="metadata" />
                      <div className="media-cap">
                        <span className="wrap">{item.label || item.role}</span>
                        <span>{item.filename.split(".").pop()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-head">
              <div>
                <h2>Queue</h2>
                <div className="panel-sub">One GPU job at a time</div>
              </div>
            </div>
            <QueuePanel queue={queue} onCancel={cancel} />
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Scene Jobs</h2>
                <div className="panel-sub">Generation history for this shot</div>
              </div>
            </div>
            <JobTable jobs={jobs} onCancel={cancel} />
          </section>
        </>
      )}
    </>
  );
}
