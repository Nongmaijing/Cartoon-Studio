import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Character, DialogueLine, Scene, VoiceEngine, VoiceEnginesResponse } from "../types";
import { Alert, EmptyState, PageHeader } from "../components/Ui";
import { AutoGrowTextarea } from "../components/AutoGrowTextarea";

const EMOTIONS = [
  "neutral",
  "happy",
  "excited",
  "sad",
  "angry",
  "scared",
  "surprised",
  "calm",
  "whisper",
];

interface VoiceForm {
  engine: string;
  voice: string;
  rate: number;
  pitch: number;
  volume: number;
}

function isEngineAvailable(engines: VoiceEngine[], engineId: string): boolean {
  return engines.some((engine) => engine.id === engineId && engine.available);
}

function engineById(engines: VoiceEngine[], id: string): VoiceEngine | undefined {
  return engines.find((engine) => engine.id === id);
}

function formatSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(2)}s`;
}

function EngineCard({ engine }: { engine: VoiceEngine }) {
  const young = engine.voices.filter((voice) => voice.age === "Young").length;
  return (
    <div className={`engine-card${engine.available ? " available" : ""}`}>
      <div className="row between">
        <strong>{engine.name}</strong>
        <span className={`chip ${engine.available ? "exp" : ""}`}>
          {engine.available ? "ready" : "not installed"}
        </span>
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>{engine.notes}</div>
      {engine.voices.length > 0 && (
        <>
          <div className="tiny muted" style={{ marginTop: 6 }}>
            {engine.voices.length} voices{young ? ` · ${young} young/child` : ""}
          </div>
          <div className="chip-row" style={{ marginTop: 6, maxHeight: 132, overflowY: "auto", paddingRight: 4 }}>
            {engine.voices.map((voice) => (
              <span
                className={`chip${voice.age && voice.age !== "Adult" ? " exp" : ""}`}
                key={voice.id}
                title={[voice.locale, voice.gender, voice.age].filter(Boolean).join(" · ")}
              >
                {voice.name}
              </span>
            ))}
          </div>
        </>
      )}
      {engine.executable && (
        <div className="tiny mono wrap" style={{ marginTop: 8, opacity: 0.7 }}>{engine.executable}</div>
      )}
    </div>
  );
}

interface LineCardProps {
  line: DialogueLine;
  characters: Character[];
  engines: VoiceEngine[];
  busy: boolean;
  onBusy: (lineId: string | null) => void;
  onChanged: (line: DialogueLine) => void;
  onDeleted: (lineId: string) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

function LineCard({ line, characters, engines, busy, onBusy, onChanged, onDeleted, onError, onNotice }: LineCardProps) {
  const [text, setText] = useState(line.text);
  const [emotion, setEmotion] = useState(line.emotion);
  const [characterId, setCharacterId] = useState(line.character_id || "");
  const [engine, setEngine] = useState(line.voice_engine);
  const [voice, setVoice] = useState(line.voice_name);
  const [rate, setRate] = useState(line.rate);
  const [pitch, setPitch] = useState(line.pitch);
  const [volume, setVolume] = useState(line.volume);
  const [showVoice, setShowVoice] = useState(false);

  useEffect(() => {
    setText(line.text);
    setEmotion(line.emotion);
    setCharacterId(line.character_id || "");
    setEngine(line.voice_engine);
    setVoice(line.voice_name);
    setRate(line.rate);
    setPitch(line.pitch);
    setVolume(line.volume);
  }, [line.id, line.updated_at]);

  const selectedEngine = engineById(engines, engine);
  const voices = selectedEngine?.voices || [];

  const payload = () => ({
    text: text.trim(),
    emotion,
    character_id: characterId || null,
    voice_engine: engine,
    voice_name: voice,
    rate,
    pitch,
    volume,
  });

  const save = async () => {
    if (!text.trim()) return;
    onBusy(line.id);
    onError("");
    try {
      const updated = await api.updateDialogueLine(line.id, payload());
      onChanged(updated);
      onNotice("Dialogue line saved.");
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      onBusy(null);
    }
  };

  const generate = async () => {
    if (!text.trim()) return;
    onBusy(line.id);
    onError("");
    onNotice("");
    try {
      await api.updateDialogueLine(line.id, payload());
      const updated = await api.generateDialogueLine(line.id);
      onChanged(updated);
      onNotice(`Voice generated for ${updated.character_name || "Narrator"} (${formatSeconds(updated.duration_ms)}).`);
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      onBusy(null);
    }
  };

  const remove = async () => {
    if (!window.confirm("Delete this dialogue line? The generated audio file stays available as an asset.")) return;
    onBusy(line.id);
    try {
      await api.deleteDialogueLine(line.id);
      onDeleted(line.id);
      onNotice("Dialogue line deleted.");
    } catch (exc) {
      onError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      onBusy(null);
    }
  };

  const applyVoice = (character: Character) => {
    if (!character.voice_engine) return;
    setEngine(character.voice_engine);
    setVoice(character.voice_name);
    setRate(character.voice_rate);
    setPitch(character.voice_pitch);
    setVolume(character.voice_volume);
  };

  const chooseCharacter = (value: string) => {
    setCharacterId(value);
    const character = characters.find((item) => item.id === value);
    if (character) applyVoice(character);
  };

  const useCharacterVoice = () => {
    const character = characters.find((item) => item.id === characterId);
    if (character) applyVoice(character);
  };

  return (
    <div className="dialogue-line">
      <div className="dialogue-head">
        <span className="dialogue-index">{line.order_index + 1}</span>
        <div className="dialogue-who">
          <strong>{line.character_name || "Narrator"}</strong>
          <span className="tiny muted">
            {line.voice_label || "voice not generated"} · {line.audio_url ? formatSeconds(line.duration_ms) : "no audio"}
          </span>
        </div>
        <span className="chip">{emotion}</span>
      </div>

      <AutoGrowTextarea
        minRows={2}
        maxHeight={260}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Dialogue text"
      />

      <div className="form-grid" style={{ marginTop: 8 }}>
        <div className="field">
          <label>Speaker</label>
          <select value={characterId} onChange={(event) => chooseCharacter(event.target.value)}>
            <option value="">Narrator</option>
            {characters.map((character) => (
              <option key={character.id} value={character.id}>
                {character.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Emotion</label>
          <select value={emotion} onChange={(event) => setEmotion(event.target.value)}>
            {EMOTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </div>
      </div>

      <details open={showVoice} onToggle={(event) => setShowVoice((event.target as HTMLDetailsElement).open)}>
        <summary className="tiny muted" style={{ cursor: "pointer", marginTop: 6 }}>
          Voice override
        </summary>
        {characterId && (
          <button className="btn sm" style={{ marginTop: 8 }} onClick={useCharacterVoice}>
            Use character voice
          </button>
        )}
        <div className="form-grid" style={{ marginTop: 8 }}>
          <div className="field">
            <label>Engine</label>
            <select value={engine} onChange={(event) => {
              const next = event.target.value;
              setEngine(next);
              const nextEngine = engineById(engines, next);
              setVoice(nextEngine?.voices[0]?.id || "");
            }}>
              {engines.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}{item.available ? "" : " (unavailable)"}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Voice</label>
            {selectedEngine?.free_form ? (
              <input value={voice} onChange={(event) => setVoice(event.target.value)} placeholder="voice / model name" />
            ) : (
              <select value={voice} onChange={(event) => setVoice(event.target.value)}>
                {voices.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
                {voice && !voices.some((item) => item.id === voice) && (
                  <option value={voice}>{voice}</option>
                )}
              </select>
            )}
          </div>
          <div className="field">
            <label>Rate ({rate})</label>
            <input type="range" min={-10} max={10} step={1} value={rate} onChange={(event) => setRate(Number(event.target.value))} />
          </div>
          <div className="field">
            <label>Pitch ({pitch}%)</label>
            <input type="range" min={-50} max={50} step={1} value={pitch} onChange={(event) => setPitch(Number(event.target.value))} />
          </div>
          <div className="field">
            <label>Volume ({volume})</label>
            <input type="range" min={0} max={100} step={1} value={volume} onChange={(event) => setVolume(Number(event.target.value))} />
          </div>
        </div>
      </details>

      {line.audio_url && (
        <audio controls src={line.audio_url} style={{ width: "100%", marginTop: 8 }} />
      )}

      <div className="row between" style={{ marginTop: 8 }}>
        <button className="btn sm" onClick={remove} disabled={busy}>Delete</button>
        <div className="row">
          <button className="btn sm" onClick={save} disabled={busy || !text.trim()}>Save</button>
          <button className="btn sm primary" onClick={generate} disabled={busy || !text.trim()}>
            {busy ? "Generating…" : line.audio_url ? "Regenerate voice" : "Generate voice"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Voice() {
  const { selectedId, projects } = useProject();
  const [engineData, setEngineData] = useState<VoiceEnginesResponse | null>(null);
  const [engineError, setEngineError] = useState("");
  const [characters, setCharacters] = useState<Character[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [sceneId, setSceneId] = useState("");
  const [lines, setLines] = useState<DialogueLine[]>([]);
  const [selectedCharId, setSelectedCharId] = useState("");
  const [voiceForm, setVoiceForm] = useState<VoiceForm>({ engine: "", voice: "", rate: 0, pitch: 0, volume: 100 });
  const [previewText, setPreviewText] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [savingVoice, setSavingVoice] = useState(false);
  const [newLine, setNewLine] = useState({ character_id: "", text: "", emotion: "neutral" });
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [busyLine, setBusyLine] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const engines = engineData?.engines || [];
  const availableEngines = useMemo(() => engines.filter((engine) => engine.available), [engines]);
  const selectedCharacter = useMemo(
    () => characters.find((character) => character.id === selectedCharId) || null,
    [characters, selectedCharId]
  );
  const selectedScene = useMemo(
    () => scenes.find((scene) => scene.id === sceneId) || null,
    [scenes, sceneId]
  );
  const totalAudioMs = useMemo(
    () => lines.reduce((total, line) => total + (line.audio_asset_id ? line.duration_ms : 0), 0),
    [lines]
  );

  const loadEngines = useCallback(async (refresh = false) => {
    try {
      const result = await api.voiceEngines(refresh);
      setEngineData(result);
      setEngineError("");
      return result;
    } catch (exc) {
      setEngineError(exc instanceof Error ? exc.message : String(exc));
      return null;
    }
  }, []);

  const loadLines = useCallback(async (id: string) => {
    if (!id) {
      setLines([]);
      return;
    }
    try {
      setLines(await api.sceneDialogue(id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setCharacters([]);
      setScenes([]);
      setLines([]);
      setSceneId("");
      setSelectedCharId("");
      return;
    }
    let alive = true;
    loadEngines(false);
    Promise.all([api.characters(selectedId), api.scenes(selectedId)])
      .then(([characterList, sceneList]) => {
        if (!alive) return;
        setCharacters(characterList);
        setScenes(sceneList);
        setSelectedCharId((current) =>
          current && characterList.some((item) => item.id === current) ? current : characterList[0]?.id || ""
        );
        setSceneId((current) =>
          current && sceneList.some((item) => item.id === current) ? current : sceneList[0]?.id || ""
        );
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
    return () => {
      alive = false;
    };
  }, [selectedId, loadEngines]);

  useEffect(() => {
    loadLines(sceneId);
  }, [sceneId, loadLines]);

  useEffect(() => {
    if (!selectedCharacter) return;
    if (!engineData) {
      setVoiceForm({
        engine: selectedCharacter.voice_engine || "",
        voice: selectedCharacter.voice_name || "",
        rate: selectedCharacter.voice_rate,
        pitch: selectedCharacter.voice_pitch,
        volume: selectedCharacter.voice_volume,
      });
      return;
    }
    const list = engineData.engines;
    const engineId =
      selectedCharacter.voice_engine && isEngineAvailable(list, selectedCharacter.voice_engine)
        ? selectedCharacter.voice_engine
        : engineData.default_engine;
    const engine = engineById(list, engineId);
    const voice =
      selectedCharacter.voice_name ||
      (engineId === engineData.default_engine ? engineData.default_voice : "") ||
      engine?.voices[0]?.id ||
      "";
    setVoiceForm({
      engine: engineId,
      voice,
      rate: selectedCharacter.voice_rate,
      pitch: selectedCharacter.voice_pitch,
      volume: selectedCharacter.voice_volume,
    });
  }, [selectedCharacter?.id, selectedCharacter?.updated_at, engineData]);

  useEffect(() => {
    if (!engineData) return;
    setPreviewText((current) => current || "Hello! I am ready for my close-up.");
  }, [engineData]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const activeEngine = engineById(engines, voiceForm.engine);
  const voiceChoices = activeEngine?.voices || [];

  const applyVoicePreset = (preset: "child-us" | "child-uk" | "deep" | "reset") => {
    const kokoro = engineById(engines, "kokoro");
    if (preset === "reset" || !kokoro?.available) {
      setVoiceForm((current) => ({ ...current, rate: 0, pitch: 0 }));
      return;
    }
    if (preset === "deep") {
      setVoiceForm((current) => ({
        ...current,
        engine: "kokoro",
        voice: "am_onyx",
        rate: -1,
        pitch: -18,
      }));
      return;
    }
    setVoiceForm((current) => ({
      ...current,
      engine: "kokoro",
      voice: preset === "child-us" ? "af_sky" : "bf_lily",
      rate: 1,
      pitch: 32,
    }));
  };

  const saveVoice = async () => {
    if (!selectedCharacter) return;
    setSavingVoice(true);
    setError("");
    try {
      await api.updateCharacterVoice(selectedCharacter.id, {
        engine: voiceForm.engine,
        voice: voiceForm.voice,
        rate: voiceForm.rate,
        pitch: voiceForm.pitch,
        volume: voiceForm.volume,
      });
      setCharacters(await api.characters(selectedId));
      setNotice(`Voice saved for ${selectedCharacter.name}.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSavingVoice(false);
    }
  };

  const preview = async () => {
    if (!previewText.trim()) return;
    setPreviewing(true);
    setError("");
    try {
      const blob = await api.previewVoice({
        text: previewText.trim(),
        engine: voiceForm.engine,
        voice: voiceForm.voice,
        rate: voiceForm.rate,
        pitch: voiceForm.pitch,
        volume: voiceForm.volume,
      });
      const url = URL.createObjectURL(blob);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return url;
      });
      const audio = new Audio(url);
      await audio.play().catch(() => undefined);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setPreviewing(false);
    }
  };

  const addLine = async () => {
    if (!sceneId || !newLine.text.trim()) return;
    setAdding(true);
    setError("");
    try {
      const created = await api.createDialogueLine(sceneId, {
        character_id: newLine.character_id || null,
        text: newLine.text.trim(),
        emotion: newLine.emotion,
      });
      setLines((current) => [...current, created]);
      setNewLine({ character_id: "", text: "", emotion: "neutral" });
      setNotice("Dialogue line added.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setAdding(false);
    }
  };

  const importScript = async () => {
    if (!sceneId) return;
    setImporting(true);
    setError("");
    try {
      const imported = await api.importSceneDialogue(sceneId, false);
      setLines(await api.sceneDialogue(sceneId));
      setNotice(`Imported ${imported.length} dialogue line(s) from the scene script.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setImporting(false);
    }
  };

  const generateAll = async () => {
    if (!sceneId) return;
    setGeneratingAll(true);
    setError("");
    setNotice("");
    try {
      const result = await api.generateSceneDialogue(sceneId);
      setLines(result.lines);
      if (result.errors.length) {
        setError(`${result.errors.length} line(s) failed: ${result.errors.map((item) => item.error).join("; ")}`);
        setNotice(`Generated ${result.generated} of ${result.lines.length} line(s).`);
      } else {
        setNotice(`Generated audio for all ${result.generated} dialogue line(s).`);
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setGeneratingAll(false);
    }
  };

  if (!selectedId) {
    return (
      <>
        <PageHeader title="Voice & Dialogue" subtitle="Assign local voices and generate dialogue audio." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          writing dialogue.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Voice & Dialogue"
        subtitle="Write per-scene dialogue, assign character voices and render local audio. Nothing is downloaded automatically."
        actions={
          <button className="btn" onClick={() => loadEngines(true)}>
            Re-check engines
          </button>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>Speech Engines</h2>
            <div className="panel-sub">Detected at runtime from local executables and Windows voices.</div>
          </div>
        </div>
        {engineError && <Alert kind="error">{engineError}</Alert>}
        {!engineData && !engineError && <EmptyState>Checking local speech engines…</EmptyState>}
        {engineData && (
          <div className="engine-grid">
            {engines.map((engine) => (
              <EngineCard key={engine.id} engine={engine} />
            ))}
          </div>
        )}
      </section>

      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Character Voices</h2>
              <div className="panel-sub">Each character keeps one reusable local voice.</div>
            </div>
          </div>

          {characters.length > 0 && characters.some((character) => !character.voice_name) && (
            <div style={{ marginBottom: 12 }}>
              <Alert kind="warn">
                Some characters have no voice assigned. Assign a voice before generating dialogue audio.
              </Alert>
            </div>
          )}

          {characters.length === 0 ? (
            <div className="media-empty">
              No characters in this project. <Link className="link" to="/characters">Create a character</Link> first.
            </div>
          ) : (
            <>
              <div className="character-list" style={{ marginBottom: 14 }}>
                {characters.map((character) => (
                  <button
                    key={character.id}
                    className={`character-item${character.id === selectedCharId ? " active" : ""}`}
                    onClick={() => setSelectedCharId(character.id)}
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
                      <span>{character.voice_name ? `${character.voice_engine} · ${character.voice_name}` : "No voice assigned"}</span>
                    </div>
                  </button>
                ))}
              </div>

              {selectedCharacter && (
                <div className="form-grid">
                  <div className="field">
                    <label>Engine</label>
                    <select
                      value={voiceForm.engine}
                      onChange={(event) => {
                        const next = event.target.value;
                        const nextEngine = engineById(engines, next);
                        setVoiceForm({
                          ...voiceForm,
                          engine: next,
                          voice: nextEngine?.voices[0]?.id || "",
                        });
                      }}
                    >
                      {engines.map((engine) => (
                        <option key={engine.id} value={engine.id} disabled={!engine.available}>
                          {engine.name}{engine.available ? "" : " (unavailable)"}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>Voice</label>
                    {activeEngine?.free_form ? (
                      <input
                        value={voiceForm.voice}
                        onChange={(event) => setVoiceForm({ ...voiceForm, voice: event.target.value })}
                        placeholder="voice / model name"
                      />
                    ) : (
                      <select
                        value={voiceForm.voice}
                        onChange={(event) => setVoiceForm({ ...voiceForm, voice: event.target.value })}
                      >
                        {voiceChoices.map((choice) => (
                          <option key={choice.id} value={choice.id}>
                            {choice.name}{choice.locale ? ` · ${choice.locale}` : ""}{choice.gender ? ` · ${choice.gender}` : ""}
                            {choice.age && choice.age !== "Adult" ? ` · ${choice.age}` : ""}
                          </option>
                        ))}
                        {voiceForm.voice && !voiceChoices.some((choice) => choice.id === voiceForm.voice) && (
                          <option value={voiceForm.voice}>{voiceForm.voice}</option>
                        )}
                      </select>
                    )}
                  </div>
                  <div className="field span-2">
                    <label>Voice presets</label>
                    <div className="row" style={{ flexWrap: "wrap" }}>
                      <button className="btn sm" onClick={() => applyVoicePreset("child-us")}>
                        Child · US
                      </button>
                      <button className="btn sm" onClick={() => applyVoicePreset("child-uk")}>
                        Child · UK
                      </button>
                      <button className="btn sm" onClick={() => applyVoicePreset("deep")}>
                        Deep adult
                      </button>
                      <button className="btn sm ghost" onClick={() => applyVoicePreset("reset")}>
                        Reset pitch
                      </button>
                    </div>
                    <div className="tiny muted">
                      Pitch is applied by resampling, so it raises the formants too — that is what makes a voice read as a child.
                      +32% is about +3.8 semitones.
                    </div>
                  </div>
                  <div className="field">
                    <label>Rate ({voiceForm.rate})</label>
                    <input
                      type="range"
                      min={-10}
                      max={10}
                      step={1}
                      value={voiceForm.rate}
                      onChange={(event) => setVoiceForm({ ...voiceForm, rate: Number(event.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>Pitch ({voiceForm.pitch}%)</label>
                    <input
                      type="range"
                      min={-50}
                      max={50}
                      step={1}
                      value={voiceForm.pitch}
                      onChange={(event) => setVoiceForm({ ...voiceForm, pitch: Number(event.target.value) })}
                    />
                  </div>
                  <div className="field">
                    <label>Volume ({voiceForm.volume})</label>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={voiceForm.volume}
                      onChange={(event) => setVoiceForm({ ...voiceForm, volume: Number(event.target.value) })}
                    />
                  </div>
                  <div className="field span-2">
                    <label>Preview text</label>
                    <input
                      value={previewText}
                      placeholder="Hello! I am ready for my close-up."
                      onChange={(event) => setPreviewText(event.target.value)}
                    />
                  </div>
                </div>
              )}

              <div className="row between" style={{ marginTop: 12 }}>
                <span className="tiny muted">
                  {availableEngines.length === 0
                    ? "No local speech engine is available. Install Piper, Coqui TTS or eSpeak NG, or enable Windows SAPI voices."
                    : `${availableEngines.length} engine(s) ready · audio renders on the local CPU`}
                </span>
                <div className="row">
                  <button className="btn" onClick={preview} disabled={previewing || !previewText.trim() || availableEngines.length === 0}>
                    {previewing ? "Rendering…" : "Preview voice"}
                  </button>
                  <button
                    className="btn primary"
                    onClick={saveVoice}
                    disabled={savingVoice || !selectedCharacter || availableEngines.length === 0}
                  >
                    {savingVoice ? "Saving…" : "Save voice"}
                  </button>
                </div>
              </div>
              {previewUrl && <audio controls src={previewUrl} style={{ width: "100%", marginTop: 10 }} />}
            </>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Scene Dialogue</h2>
              <div className="panel-sub">Dialogue lines are stored per scene and stay editable.</div>
            </div>
          </div>

          {scenes.length === 0 ? (
            <div className="media-empty">
              No scenes in this project. <Link className="link" to="/scenes">Create a scene</Link> first.
            </div>
          ) : (
            <>
              <div className="field" style={{ marginBottom: 10 }}>
                <label>Scene</label>
                <select value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
                  {scenes.map((scene) => (
                    <option key={scene.id} value={scene.id}>{scene.name}</option>
                  ))}
                </select>
              </div>

              <div className="chip-row" style={{ marginBottom: 10 }}>
                <span className="chip">{lines.length} line(s)</span>
                <span className="chip ref">{formatSeconds(totalAudioMs)} audio</span>
                <span className="chip">scene {selectedScene?.duration ?? 0}s</span>
              </div>

              <div className="form-grid">
                <div className="field">
                  <label>New line speaker</label>
                  <select
                    value={newLine.character_id}
                    onChange={(event) => setNewLine({ ...newLine, character_id: event.target.value })}
                  >
                    <option value="">Narrator</option>
                    {characters.map((character) => (
                      <option key={character.id} value={character.id}>{character.name}</option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Emotion</label>
                  <select
                    value={newLine.emotion}
                    onChange={(event) => setNewLine({ ...newLine, emotion: event.target.value })}
                  >
                    {EMOTIONS.map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                </div>
                <div className="field span-2">
                  <label>Line text</label>
                  <AutoGrowTextarea
                    minRows={3}
                    maxHeight={240}
                    value={newLine.text}
                    placeholder="Character: “A line of dialogue.”"
                    onChange={(event) => setNewLine({ ...newLine, text: event.target.value })}
                  />
                </div>
              </div>

              <div className="row between" style={{ marginTop: 10 }}>
                <div className="row">
                  <button className="btn sm" onClick={importScript} disabled={importing}>
                    {importing ? "Importing…" : "Import scene text"}
                  </button>
                  <button
                    className="btn sm"
                    onClick={generateAll}
                    disabled={generatingAll || lines.length === 0 || characters.some((character) => !character.voice_name)}
                    title={
                      characters.some((character) => !character.voice_name)
                        ? "Assign a voice to every character first"
                        : undefined
                    }
                  >
                    {generatingAll ? "Generating…" : "Generate all voices"}
                  </button>
                </div>
                <button className="btn primary" onClick={addLine} disabled={adding || !newLine.text.trim()}>
                  {adding ? "Adding…" : "Add line"}
                </button>
              </div>
              <div className="tiny muted" style={{ marginTop: 6 }}>
                “Import scene text” splits the Scenes page dialogue field into lines. Use “Name: text” to assign a cast member.
              </div>
            </>
          )}
        </section>
      </div>

      {selectedScene && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Dialogue — {selectedScene.name}</h2>
              <div className="panel-sub">Voice generation is synchronous and serialized; existing files are never overwritten.</div>
            </div>
          </div>
          {lines.length === 0 ? (
            <div className="media-empty">No dialogue lines yet. Add one above or import the scene script.</div>
          ) : (
            <div className="stack">
              {lines.map((line) => (
                <LineCard
                  key={line.id}
                  line={line}
                  characters={characters}
                  engines={engines}
                  busy={busyLine === line.id}
                  onBusy={setBusyLine}
                  onChanged={(updated) => setLines((current) => current.map((item) => (item.id === updated.id ? updated : item)))}
                  onDeleted={(lineId) => setLines((current) => current.filter((item) => item.id !== lineId))}
                  onError={setError}
                  onNotice={setNotice}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </>
  );
}
