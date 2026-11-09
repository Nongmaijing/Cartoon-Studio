import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Character, CharacterSheetStatus, Job, MediaItem } from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";

type Kind = "reference" | "expression" | "pose";

const LABEL_OPTIONS: Record<Kind, string[]> = {
  reference: ["front", "side", "back", "three quarter"],
  expression: ["happy", "sad", "angry", "surprised", "scared", "excited", "neutral"],
  pose: ["standing", "sitting", "running", "jumping", "waving", "walking"],
};

const SIZE_PRESETS = [
  { label: "Full body HD · 768×1152", width: 768, height: 1152 },
  { label: "Portrait · 640×640", width: 640, height: 640 },
  { label: "Wide · 768×512", width: 768, height: 512 },
  { label: "Square HD · 768×768", width: 768, height: 768 },
  { label: "Fast · 512×768", width: 512, height: 768 },
];

const KIND_LABEL: Record<Kind, string> = {
  reference: "Reference view",
  expression: "Expression",
  pose: "Pose",
};

interface ProfileState {
  name: string;
  description: string;
  style: string;
  clothing: string;
  appearance: string;
}

const EMPTY_PROFILE: ProfileState = {
  name: "",
  description: "",
  style: "",
  clothing: "",
  appearance: "",
};

function isActive(job: Job | null): boolean {
  return !!job && (job.status === "queued" || job.status === "running");
}

export default function Characters() {
  const { selectedId, projects } = useProject();
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharId, setSelectedCharId] = useState("");
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newProfile, setNewProfile] = useState<ProfileState>({ ...EMPTY_PROFILE });

  // Selected character editor
  const [profile, setProfile] = useState<ProfileState>({ ...EMPTY_PROFILE });
  const [savingProfile, setSavingProfile] = useState(false);

  // Generation form
  const [kind, setKind] = useState<Kind>("reference");
  const [label, setLabel] = useState("front");
  const [extraPrompt, setExtraPrompt] = useState("");
  const [sizeIndex, setSizeIndex] = useState(0);
  const [steps, setSteps] = useState(28);
  const [seed, setSeed] = useState(-1);
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [sheetBusy, setSheetBusy] = useState(false);
  const [sheetStatus, setSheetStatus] = useState<CharacterSheetStatus | null>(null);
  const [sheetId, setSheetId] = useState("");
  const [charModel, setCharModel] = useState<Record<string, any>>({});
  const [savingCharModel, setSavingCharModel] = useState(false);

  // Attach existing asset
  const [attachId, setAttachId] = useState("");
  const [attachRole, setAttachRole] = useState<Kind>("reference");
  const [attachLabel, setAttachLabel] = useState("");

  // Identity / reference conditioning
  const [referenceAssetId, setReferenceAssetId] = useState("");
  const [referenceMode, setReferenceMode] = useState<"identity" | "pose">("identity");
  const [denoise, setDenoise] = useState(0.55);
  const [controlStrength, setControlStrength] = useState(0.8);
  const [canonicalPick, setCanonicalPick] = useState("");

  const selected = useMemo(
    () => characters.find((character) => character.id === selectedCharId) || null,
    [characters, selectedCharId]
  );
  const sheetReference = referenceAssetId || selected?.canonical_asset_id || "";
  const characterApproved = selected?.approval_status === "approved";

  const refreshCharacters = useCallback(async () => {
    if (!selectedId) {
      setCharacters([]);
      setSelectedCharId("");
      return;
    }
    try {
      const list = await api.characters(selectedId);
      setCharacters(list);
      setSelectedCharId((current) =>
        current && list.some((character) => character.id === current) ? current : list[0]?.id || ""
      );
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  const loadMedia = useCallback(async (characterId: string) => {
    if (!characterId) {
      setMedia([]);
      return;
    }
    try {
      setMedia(await api.characterMedia(characterId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    refreshCharacters();
  }, [refreshCharacters]);

  useEffect(() => {
    loadMedia(selectedCharId);
    setActiveJob(null);
    setLastPrompt("");
    setSheetId("");
    setSheetStatus(null);
    if (!selectedCharId) {
      setProfile({ ...EMPTY_PROFILE });
      return;
    }
    api
      .characterJobs(selectedCharId)
      .then((jobs) => {
        const running = jobs.find((job) => job.status === "queued" || job.status === "running");
        if (running) setActiveJob(running);
      })
      .catch(() => undefined);
  }, [selectedCharId, loadMedia]);

  useEffect(() => {
    if (!selected) {
      setProfile({ ...EMPTY_PROFILE });
      setReferenceAssetId("");
      setCharModel({});
      return;
    }
    setProfile({
      name: selected.name,
      description: selected.description,
      style: selected.style,
      clothing: selected.clothing,
      appearance: selected.appearance,
    });
    setReferenceAssetId(selected.canonical_asset_id || "");
    setReferenceMode("identity");
    api
      .characterModel(selected.id)
      .then((result) => setCharModel(result.model || {}))
      .catch(() => setCharModel({}));
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
          await refreshCharacters();
          await loadMedia(selectedCharId);
          if (job.status === "completed") {
            setNotice("Image generated and attached to the character.");
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
  }, [activeJob?.id, activeJob?.status, refreshCharacters, loadMedia, selectedCharId]);

  useEffect(() => {
    if (!sheetId || !selectedCharId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await api.characterSheet(selectedCharId, sheetId);
        if (cancelled) return;
        setSheetStatus(status);
        if (status.complete || status.failed) {
          await refreshCharacters();
          await loadMedia(selectedCharId);
          if (status.complete) setNotice("Character sheet completed.");
          if (status.failed) setError("One or more sheet jobs failed. Check the job errors below.");
        }
      } catch (exc) {
        if (!cancelled) setError(exc instanceof Error ? exc.message : String(exc));
      }
    };
    poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [sheetId, selectedCharId, refreshCharacters, loadMedia]);

  const chooseKind = (next: Kind) => {
    setKind(next);
    setLabel(LABEL_OPTIONS[next][0]);
  };

  const createCharacter = async () => {
    if (!selectedId) {
      setError("Select or create a project first.");
      return;
    }
    if (!newProfile.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await api.createCharacter({
        project_id: selectedId,
        name: newProfile.name.trim(),
        description: newProfile.description.trim(),
        style: newProfile.style.trim(),
        clothing: newProfile.clothing.trim(),
        appearance: newProfile.appearance.trim(),
      });
      setNewProfile({ ...EMPTY_PROFILE });
      setShowCreate(false);
      await refreshCharacters();
      setSelectedCharId(created.id);
      setNotice(`Created character "${created.name}".`);
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
      await api.updateCharacter(selected.id, {
        name: profile.name.trim(),
        description: profile.description.trim(),
        style: profile.style.trim(),
        clothing: profile.clothing.trim(),
        appearance: profile.appearance.trim(),
      });
      await refreshCharacters();
      setNotice("Character profile saved.");
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
    const size = SIZE_PRESETS[sizeIndex];
    try {
      const result = await api.generateCharacter(selected.id, {
        kind,
        label,
        prompt: extraPrompt.trim() || undefined,
        width: size.width,
        height: size.height,
        steps,
        cfg: 6.5,
        seed,
        reference_asset_id: referenceAssetId || undefined,
        reference_mode: referenceMode,
        denoise,
        control_strength: controlStrength,
      });
      setActiveJob(result.job);
      setLastPrompt(result.prompt);
      if (result.fallback) {
        setNotice("Pose mode requested, but ControlNet is not installed. Falling back to image-to-image with the pose reference.");
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const generateSheet = async (sheetKind: "turnaround" | "expressions" | "poses") => {
    if (!selected) return;
    setError("");
    setNotice("");
    setSheetBusy(true);
    try {
      const result = await api.generateCharacterSheet(selected.id, sheetKind, {
        seed,
        steps,
        cfg: 6.5,
        denoise,
        reference_asset_id: referenceAssetId || selected.canonical_asset_id || undefined,
        allow_unapproved_reference: false,
      });
      setSheetId(result.sheet_id);
      setSheetStatus({
        sheet_id: result.sheet_id,
        character_id: result.character_id,
        kind: result.kind,
        jobs: result.jobs,
        items: result.items.map((item) => ({
          label: item.label,
          job_id: item.job_id,
          status: item.status,
          progress: 0,
          error: null,
          outputs: [],
        })),
        complete: false,
        failed: false,
      });
      setNotice(
        `${sheetKind} sheet queued: ${result.jobs.length} images. The existing single-job queue runs them one at a time.`
      );
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSheetBusy(false);
    }
  };

  const approveSelected = async () => {
    if (!selected) return;
    setError("");
    try {
      await api.approveCharacter(selected.id);
      await refreshCharacters();
      setNotice("Character approved. A version snapshot was saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const saveCharacterModel = async () => {
    if (!selected) return;
    setSavingCharModel(true);
    setError("");
    try {
      await api.updateCharacterModel(selected.id, charModel);
      await refreshCharacters();
      setNotice("Character model overrides saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSavingCharModel(false);
    }
  };

  const setCanonical = async () => {
    if (!selected || !canonicalPick) return;
    setError("");
    try {
      await api.setCharacterCanonical(selected.id, canonicalPick);
      await refreshCharacters();
      setCanonicalPick("");
      setReferenceAssetId(canonicalPick);
      setNotice("Canonical identity image saved.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const clearCanonical = async () => {
    if (!selected) return;
    setError("");
    try {
      await api.clearCharacterCanonical(selected.id);
      await refreshCharacters();
      setReferenceAssetId("");
      setNotice("Canonical identity image cleared.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const attachExisting = async () => {
    if (!selected || !attachId.trim()) return;
    setError("");
    try {
      await api.attachCharacterMedia(selected.id, {
        asset_id: attachId.trim(),
        role: attachRole,
        label: attachLabel.trim(),
      });
      setAttachId("");
      setAttachLabel("");
      await refreshCharacters();
      await loadMedia(selected.id);
      setNotice("Existing asset attached.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const upscaleMedia = async (assetId: string, role: string) => {
    if (!selected) return;
    setError("");
    setNotice("");
    try {
      const result = await api.upscaleAsset(assetId, {
        owner_type: "character",
        owner_id: selected.id,
        role,
        label: "upscaled",
      });
      setActiveJob(result.job);
      setNotice(`4× upscale queued. The new image will appear under ${role === "pose" ? "Poses" : role === "expression" ? "Expressions" : "Reference views"} when complete.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const groups: { key: Kind; title: string; items: MediaItem[] }[] = [
    { key: "reference", title: "Reference views", items: media.filter((item) => item.role === "reference") },
    { key: "expression", title: "Expressions", items: media.filter((item) => item.role === "expression") },
    { key: "pose", title: "Poses", items: media.filter((item) => item.role === "pose") },
  ];
  const referenceMedia = media.filter(
    (item) => (item.role === "reference" || item.role === "pose") && item.id !== selected?.canonical_asset_id
  );

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Characters" subtitle="Create and reuse consistent cartoon characters." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          building characters.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Characters"
        subtitle="Build a reusable identity from a description, then generate reference views, expressions and poses with DreamShaper 8."
        actions={
          <button className="btn primary" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Close" : "New character"}
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      {showCreate && (
        <section className="panel" style={{ marginBottom: 16 }}>
          <div className="panel-head">
            <div>
              <h2>New Character</h2>
              <div className="panel-sub">Saved into {projects.find((project) => project.id === selectedId)?.name}</div>
            </div>
          </div>
          <div className="form-grid">
            <div className="field">
              <label>Name</label>
              <input
                value={newProfile.name}
                placeholder="Milo the fox"
                onChange={(event) => setNewProfile({ ...newProfile, name: event.target.value })}
              />
            </div>
            <div className="field">
              <label>Visual style</label>
              <input
                value={newProfile.style}
                placeholder="rounded shapes, warm palette"
                onChange={(event) => setNewProfile({ ...newProfile, style: event.target.value })}
              />
            </div>
            <div className="field span-2">
              <label>Description</label>
              <textarea
                value={newProfile.description}
                placeholder="A curious young fox who lives at the edge of the forest."
                onChange={(event) => setNewProfile({ ...newProfile, description: event.target.value })}
              />
            </div>
            <div className="field">
              <label>Clothing</label>
              <input
                value={newProfile.clothing}
                placeholder="red scarf, blue satchel"
                onChange={(event) => setNewProfile({ ...newProfile, clothing: event.target.value })}
              />
            </div>
            <div className="field">
              <label>Appearance details</label>
              <input
                value={newProfile.appearance}
                placeholder="orange fur, white muzzle, bushy tail"
                onChange={(event) => setNewProfile({ ...newProfile, appearance: event.target.value })}
              />
            </div>
          </div>
          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button className="btn primary" onClick={createCharacter} disabled={busy || !newProfile.name.trim()}>
              {busy ? "Creating…" : "Create character"}
            </button>
          </div>
        </section>
      )}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Cast</h2>
            <div className="panel-sub">{characters.length} character(s) in this project</div>
          </div>
        </div>
        {characters.length === 0 ? (
          <EmptyState>No characters yet. Use “New character” to create the first one.</EmptyState>
        ) : (
          <div className="character-list">
            {characters.map((character) => (
              <button
                key={character.id}
                className={`character-item${character.id === selectedCharId ? " active" : ""}`}
                onClick={() => setSelectedCharId(character.id)}
              >
                <div className="character-avatar">
                  {character.cover_url ? <img src={character.cover_url} alt={character.name} /> : character.name.slice(0, 2).toUpperCase()}
                </div>
                <div className="character-meta">
                  <strong>{character.name}</strong>
                  <span>{character.description || "No description"}</span>
                  <div className="chip-row">
                    <span className="chip ref">{character.reference_count} ref</span>
                    <span className="chip exp">{character.expression_count} exp</span>
                    <span className="chip pose">{character.pose_count} pose</span>
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
                  {savingProfile ? "Saving…" : "Save profile"}
                </button>
              </div>
              <div className="form-grid">
                <div className="field">
                  <label>Name</label>
                  <input value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} />
                </div>
                <div className="field">
                  <label>Visual style</label>
                  <input value={profile.style} onChange={(event) => setProfile({ ...profile, style: event.target.value })} />
                </div>
                <div className="field span-2">
                  <label>Description</label>
                  <textarea
                    value={profile.description}
                    onChange={(event) => setProfile({ ...profile, description: event.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Clothing</label>
                  <input value={profile.clothing} onChange={(event) => setProfile({ ...profile, clothing: event.target.value })} />
                </div>
                <div className="field">
                  <label>Appearance details</label>
                  <input
                    value={profile.appearance}
                    onChange={(event) => setProfile({ ...profile, appearance: event.target.value })}
                  />
                </div>
              </div>
              <div className="tiny muted" style={{ marginTop: 10 }}>
                Identity text is reused in every generation prompt so the character stays recognisable.
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Generate</h2>
                  <div className="panel-sub">DreamShaper 8 · one job at a time</div>
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

              <div className="section-title">Identity lock</div>
              <div className="row" style={{ alignItems: "flex-start", gap: 12, marginBottom: 14 }}>
                {selected.canonical_url ? (
                  <img
                    className="scene-location"
                    src={selected.canonical_url}
                    alt={`${selected.name} canonical identity`}
                    style={{ width: 104, height: 104, objectFit: "cover" }}
                  />
                ) : (
                  <div className="media-empty" style={{ width: 104, height: 104, margin: 0, display: "grid", placeItems: "center" }}>
                    No canonical
                  </div>
                )}
                <div className="stack" style={{ flex: 1 }}>
                  <select value={canonicalPick} onChange={(event) => setCanonicalPick(event.target.value)}>
                    <option value="">Choose a reference or pose image…</option>
                    {referenceMedia.map((item) => (
                      <option key={item.link_id} value={item.id}>
                        {item.role} · {item.label || item.filename}
                      </option>
                    ))}
                  </select>
                  <div className="row">
                    <button className="btn sm" onClick={setCanonical} disabled={!canonicalPick}>
                      Use as canonical
                    </button>
                    {selected.canonical_asset_id && (
                      <button className="btn sm" onClick={clearCanonical}>
                        Clear canonical
                      </button>
                    )}
                    <button className="btn sm" onClick={approveSelected} disabled={characterApproved}>
                      {characterApproved ? "Approved" : "Approve character"}
                    </button>
                  </div>
                  <div className="tiny muted">
                    The canonical image becomes the default identity reference for consistency generation.
                  </div>
                </div>
              </div>

              <details className="ai-tool-details" style={{ marginBottom: 12 }}>
                <summary>Character model overrides (optional)</summary>
                <div className="form-grid" style={{ marginTop: 10 }}>
                  <div className="field">
                    <label>Architecture</label>
                    <select
                      value={charModel.architecture || ""}
                      onChange={(event) => setCharModel({ ...charModel, architecture: event.target.value })}
                    >
                      <option value="">Use global Model Studio</option>
                      <option value="sdxl">SDXL</option>
                      <option value="sd15">SD 1.5</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Checkpoint filename</label>
                    <input
                      value={charModel.checkpoint || ""}
                      placeholder="exact ComfyUI filename, blank = global"
                      onChange={(event) => setCharModel({ ...charModel, checkpoint: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>VAE filename</label>
                    <input
                      value={charModel.vae || ""}
                      placeholder="blank = checkpoint VAE"
                      onChange={(event) => setCharModel({ ...charModel, vae: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>Character LoRA filename</label>
                    <input
                      value={charModel.lora_name || ""}
                      placeholder="blank = no character LoRA"
                      onChange={(event) => setCharModel({ ...charModel, lora_name: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>LoRA strength</label>
                    <input
                      type="number"
                      step="0.05"
                      min="-2"
                      max="2"
                      value={charModel.lora_strength ?? 0.8}
                      onChange={(event) => setCharModel({ ...charModel, lora_strength: Number(event.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>Reference strength / denoise</label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={charModel.reference_strength ?? charModel.denoise ?? 0.55}
                      onChange={(event) =>
                        setCharModel({ ...charModel, reference_strength: Number(event.target.value), denoise: Number(event.target.value) })
                      }
                    />
                  </div>
                </div>
                <div className="row" style={{ marginTop: 8 }}>
                  <button className="btn sm" onClick={saveCharacterModel} disabled={savingCharModel}>
                    {savingCharModel ? "Saving…" : "Save character model settings"}
                  </button>
                  <span className="tiny muted">These override Model Studio for this character only.</span>
                </div>
              </details>

              <div className="form-grid">
                <div className="field">
                  <label>Type</label>
                  <select value={kind} onChange={(event) => chooseKind(event.target.value as Kind)}>
                    <option value="reference">Reference view</option>
                    <option value="expression">Expression</option>
                    <option value="pose">Pose</option>
                  </select>
                </div>
                <div className="field">
                  <label>{kind === "reference" ? "View" : kind === "expression" ? "Expression" : "Pose"}</label>
                  <select value={label} onChange={(event) => setLabel(event.target.value)}>
                    {LABEL_OPTIONS[kind].map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Size</label>
                  <select value={sizeIndex} onChange={(event) => setSizeIndex(Number(event.target.value))}>
                    {SIZE_PRESETS.map((preset, index) => (
                      <option key={preset.label} value={index}>
                        {preset.label}
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
                    placeholder="optional, e.g. holding a lantern"
                    onChange={(event) => setExtraPrompt(event.target.value)}
                  />
                </div>
                <div className="field">
                  <label>Reference image</label>
                  <select value={referenceAssetId} onChange={(event) => setReferenceAssetId(event.target.value)}>
                    <option value="">None — text-to-image</option>
                    {selected.canonical_asset_id && (
                      <option value={selected.canonical_asset_id}>Canonical identity</option>
                    )}
                    {referenceMedia.map((item) => (
                      <option key={item.link_id} value={item.id}>
                        {item.role} · {item.label || item.filename}
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
              </div>

              {referenceAssetId && (
                <div className="tiny muted" style={{ marginTop: 8 }}>
                  {referenceMode === "pose"
                    ? "Pose mode uses ControlNet when installed; otherwise it falls back to image-to-image with the pose reference."
                    : "Identity mode re-renders the reference at the chosen denoise to keep the character design consistent."}
                </div>
              )}

              <div className="row between" style={{ marginTop: 12 }}>
                <span className="tiny muted">{KIND_LABEL[kind]} · {label}</span>
                <button className="btn primary" onClick={generate} disabled={isActive(activeJob)}>
                  {isActive(activeJob) ? "Generating…" : "Generate image"}
                </button>
              </div>

              <div className="section-title" style={{ marginTop: 14 }}>Sheet generation</div>
              {!characterApproved && (
                <div style={{ marginBottom: 8 }}>
                  <Alert kind="warn">
                    Approve the character before generating expression or pose sheets from the master reference.
                    Turnaround can still bootstrap from text.
                  </Alert>
                </div>
              )}
              <div className="row" style={{ flexWrap: "wrap" }}>
                <button className="btn" onClick={() => generateSheet("turnaround")} disabled={sheetBusy || isActive(activeJob)}>
                  Turnaround · 4 views
                </button>
                <button
                  className="btn"
                  onClick={() => generateSheet("expressions")}
                  disabled={sheetBusy || isActive(activeJob) || !sheetReference || !characterApproved}
                  title={!sheetReference ? "Set a canonical reference first" : !characterApproved ? "Approve the character first" : ""}
                >
                  Expressions · 8
                </button>
                <button
                  className="btn"
                  onClick={() => generateSheet("poses")}
                  disabled={sheetBusy || isActive(activeJob) || !sheetReference || !characterApproved}
                  title={!sheetReference ? "Set a canonical reference first" : !characterApproved ? "Approve the character first" : ""}
                >
                  Poses · 8
                </button>
              </div>
              <div className="tiny muted" style={{ marginTop: 6 }}>
                Queues one job per view/expression/pose. The existing single-worker queue runs them in order.
                Expression and pose sheets require an approved master reference.
              </div>

              {sheetStatus && (
                <div className="stack" style={{ marginTop: 12 }}>
                  {sheetStatus.items.map((item) => (
                    <div className="ai-task" key={item.job_id || item.label}>
                      <div className="row between">
                        <strong>{item.label}</strong>
                        <span className={`chip ${item.status === "completed" ? "exp" : item.status === "failed" ? "pose" : ""}`}>
                          {item.status || "queued"}
                        </span>
                      </div>
                      {item.error && <div className="tiny" style={{ color: "var(--danger)" }}>{item.error}</div>}
                      {item.outputs && item.outputs.length > 0 && (
                        <div className="media-grid" style={{ marginTop: 6 }}>
                          {item.outputs.map((output) => (
                            <div className="media-card" key={String(output.asset_id)}>
                              <a href={String(output.url)} target="_blank" rel="noreferrer">
                                <img src={String(output.url)} alt={String(output.filename)} loading="lazy" />
                              </a>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {lastPrompt && (
                <>
                  <div className="section-title" style={{ marginTop: 14 }}>Last prompt</div>
                  <div className="prompt-preview">{lastPrompt}</div>
                </>
              )}
            </section>
          </div>

          {groups.map((group) => (
            <section className="panel" key={group.key} style={{ marginBottom: 16 }}>
              <div className="panel-head">
                <div>
                  <h2>{group.title}</h2>
                  <div className="panel-sub">{group.items.length} saved</div>
                </div>
              </div>
              {group.items.length === 0 ? (
                <div className="media-empty">
                  No {group.title.toLowerCase()} yet. Generate one above, or attach an existing asset below.
                </div>
              ) : (
                <div className="media-grid">
                  {group.items.map((item) => (
                    <div key={item.link_id} className="media-card">
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
                          onClick={() => upscaleMedia(item.id, item.role)}
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
          ))}

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>Attach Existing Asset</h2>
                <div className="panel-sub">Link any generated image in this project to the character</div>
              </div>
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Asset ID</label>
                <input
                  value={attachId}
                  placeholder="e.g. 62548225a719"
                  onChange={(event) => setAttachId(event.target.value)}
                />
              </div>
              <div className="field">
                <label>Role</label>
                <select value={attachRole} onChange={(event) => setAttachRole(event.target.value as Kind)}>
                  <option value="reference">Reference</option>
                  <option value="expression">Expression</option>
                  <option value="pose">Pose</option>
                </select>
              </div>
              <div className="field">
                <label>Label</label>
                <input value={attachLabel} placeholder="front, happy…" onChange={(event) => setAttachLabel(event.target.value)} />
              </div>
              <div className="field" style={{ justifyContent: "flex-end" }}>
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
