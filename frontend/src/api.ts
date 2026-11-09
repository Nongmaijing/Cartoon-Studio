import type {
  AIConversation,
  AIToolDefinition,
  AIToolExecution,
  AppConfig,
  Asset,
  Background,
  Character,
  ComfyTest,
  DashboardData,
  DialogueLine,
  DiscoveryInfo,
  EnginesResponse,
  Episode,
  EpisodeTimeline,
  Job,
  MediaItem,
  ModelLists,
  ChatGPTTunnelStatus,
  ProductionOverview,
  ProductionRun,
  Project,
  ProviderStatusResponse,
  QueueState,
  Scene,
  SceneReference,
  SettingsPayload,
  ValidateResult,
  VoiceAssignment,
  VoiceEnginesResponse,
  WorkflowDetail,
  WorkflowEntry,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      // keep the status text
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  dashboard: () => request<DashboardData>("/dashboard"),

  projects: (includeArchived = false) =>
    request<Project[]>(`/projects?include_archived=${includeArchived}`),
  createProject: (name: string, description = "") =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  updateProject: (id: string, data: { name?: string; description?: string; archived?: boolean }) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  archiveProject: (id: string) =>
    request<Project>(`/projects/${id}/archive`, { method: "POST" }),
  duplicateProject: (id: string) =>
    request<Project>(`/projects/${id}/duplicate`, { method: "POST" }),

  workflows: () => request<WorkflowEntry[]>("/workflows"),
  workflow: (id: string) => request<WorkflowDetail>(`/workflows/${id}`),
  validateWorkflow: (id: string) =>
    request<ValidateResult>(`/workflows/${id}/validate`, { method: "POST" }),
  importWorkflow: (payload: { name: string; api: Record<string, unknown>; mapping?: Record<string, unknown> }) =>
    request<WorkflowEntry>("/workflows/import", { method: "POST", body: JSON.stringify(payload) }),
  exportWorkflowUrl: (id: string) => `${BASE}/workflows/${id}/export`,

  generate: (payload: Record<string, unknown>) =>
    request<Job>("/generate", { method: "POST", body: JSON.stringify(payload) }),
  jobs: (limit = 50) => request<Job[]>(`/jobs?limit=${limit}`),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  queue: () => request<QueueState>("/jobs/queue"),
  cancelJob: (id: string) => request<{ job_id: string; status: string }>(`/jobs/${id}/cancel`, { method: "POST" }),

  assets: (limit = 50, projectId?: string, kind?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (projectId) params.set("project_id", projectId);
    if (kind) params.set("kind", kind);
    return request<Asset[]>(`/assets?${params.toString()}`);
  },
  upscaleAsset: (
    assetId: string,
    payload?: {
      workflow_id?: string;
      owner_type?: "character" | "scene" | "background";
      owner_id?: string;
      role?: string;
      label?: string;
    }
  ) =>
    request<{ job: Job; asset_id: string; mode: string; input_image: string }>(
      `/assets/${assetId}/upscale`,
      { method: "POST", body: JSON.stringify(payload || {}) }
    ),

  characters: (projectId?: string) =>
    request<Character[]>(`/characters${projectId ? `?project_id=${projectId}` : ""}`),
  createCharacter: (payload: {
    project_id: string;
    name: string;
    description?: string;
    style?: string;
    clothing?: string;
    appearance?: string;
  }) => request<Character>("/characters", { method: "POST", body: JSON.stringify(payload) }),
  updateCharacter: (
    id: string,
    payload: Partial<Pick<Character, "name" | "description" | "style" | "clothing" | "appearance">>
  ) => request<Character>(`/characters/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  characterMedia: (id: string) => request<MediaItem[]>(`/characters/${id}/media`),
  characterJobs: (id: string) => request<Job[]>(`/characters/${id}/jobs`),
  setCharacterCanonical: (id: string, assetId: string) =>
    request<Character>(`/characters/${id}/canonical`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId }),
    }),
  clearCharacterCanonical: (id: string) =>
    request<Character>(`/characters/${id}/canonical`, { method: "DELETE" }),
  updateCharacterVoice: (id: string, payload: VoiceAssignment) =>
    request<Character>(`/characters/${id}/voice`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  generateCharacter: (
    id: string,
    payload: {
      kind: "reference" | "expression" | "pose";
      label?: string;
      prompt?: string;
      negative_prompt?: string;
      width?: number;
      height?: number;
      steps?: number;
      cfg?: number;
      seed?: number;
      workflow_id?: string;
      reference_asset_id?: string;
      reference_mode?: "identity" | "pose";
      denoise?: number;
      control_strength?: number;
    }
  ) =>
    request<{
      job: Job;
      character_id: string;
      prompt: string;
      mode: string;
      input_image?: string | null;
      reference_asset_id?: string | null;
      fallback?: boolean;
    }>(`/characters/${id}/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  attachCharacterMedia: (id: string, payload: { asset_id: string; role: string; label?: string }) =>
    request<{ character_id: string }>(`/characters/${id}/media`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  backgrounds: (projectId?: string) =>
    request<Background[]>(`/backgrounds${projectId ? `?project_id=${projectId}` : ""}`),
  createBackground: (payload: {
    project_id: string;
    name: string;
    description?: string;
    aspect_ratio?: string;
    width?: number;
    height?: number;
  }) => request<Background>("/backgrounds", { method: "POST", body: JSON.stringify(payload) }),
  updateBackground: (
    id: string,
    payload: Partial<Pick<Background, "name" | "description" | "aspect_ratio" | "width" | "height">>
  ) => request<Background>(`/backgrounds/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  backgroundMedia: (id: string) => request<MediaItem[]>(`/backgrounds/${id}/media`),
  backgroundJobs: (id: string) => request<Job[]>(`/backgrounds/${id}/jobs`),
  generateBackground: (
    id: string,
    payload: {
      prompt?: string;
      negative_prompt?: string;
      width?: number;
      height?: number;
      steps?: number;
      cfg?: number;
      seed?: number;
    }
  ) =>
    request<{ job: Job; background_id: string; prompt: string }>(`/backgrounds/${id}/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  attachBackgroundMedia: (id: string, payload: { asset_id: string; role?: string; label?: string }) =>
    request<{ background_id: string }>(`/backgrounds/${id}/media`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  scenes: (projectId?: string) =>
    request<Scene[]>(`/scenes${projectId ? `?project_id=${projectId}` : ""}`),
  createScene: (payload: {
    project_id: string;
    name: string;
    description?: string;
    dialogue?: string;
    action?: string;
    camera?: string;
    duration?: number;
    background_id?: string | null;
    character_ids?: string[];
    settings?: Record<string, unknown>;
  }) => request<Scene>("/scenes", { method: "POST", body: JSON.stringify(payload) }),
  scene: (id: string) => request<Scene>(`/scenes/${id}`),
  updateScene: (
    id: string,
    payload: {
      name?: string;
      description?: string;
      dialogue?: string;
      action?: string;
      camera?: string;
      duration?: number;
      background_id?: string | null;
      character_ids?: string[];
      settings?: Record<string, unknown>;
    }
  ) => request<Scene>(`/scenes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  sceneMedia: (id: string, role?: string) =>
    request<MediaItem[]>(`/scenes/${id}/media${role ? `?role=${role}` : ""}`),
  sceneReferences: (id: string) => request<SceneReference[]>(`/scenes/${id}/references`),
  sceneJobs: (id: string) => request<Job[]>(`/scenes/${id}/jobs`),
  generateScene: (
    id: string,
    payload: {
      kind: "keyframe" | "video";
      workflow_id?: string;
      prompt?: string;
      negative_prompt?: string;
      width?: number;
      height?: number;
      steps?: number;
      cfg?: number;
      seed?: number;
      length?: number;
      fps?: number;
      start_image?: string;
      reference_asset_id?: string;
      reference_mode?: "identity" | "pose";
      denoise?: number;
      control_strength?: number;
    }
  ) =>
    request<{
      job: Job;
      prompt: string;
      kind: string;
      width?: number;
      height?: number;
      input_image?: string | null;
      mode?: string;
      reference_asset_id?: string | null;
      fallback?: boolean;
    }>(`/scenes/${id}/generate`, { method: "POST", body: JSON.stringify(payload) }),
  addSceneCast: (id: string, characterId: string, role = "main") =>
    request<Scene>(`/scenes/${id}/cast`, {
      method: "POST",
      body: JSON.stringify({ character_id: characterId, role }),
    }),
  removeSceneCast: (id: string, characterId: string) =>
    request<Scene>(`/scenes/${id}/cast/${characterId}`, { method: "DELETE" }),
  attachSceneMedia: (id: string, payload: { asset_id: string; role: "keyframe" | "video" | "other"; label?: string }) =>
    request<{ scene_id: string }>(`/scenes/${id}/media`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  animationGenerate: (payload: {
    project_id: string;
    workflow_id?: string;
    prompt: string;
    negative_prompt?: string;
    width?: number;
    height?: number;
    steps?: number;
    cfg?: number;
    seed?: number;
    length?: number;
    fps?: number;
    sampler?: string;
    scheduler?: string;
    start_image?: string;
    scene_id?: string;
  }) =>
    request<{ job: Job; mode: string; input_image?: string | null }>("/animation/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  animationJobs: (projectId?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (projectId) params.set("project_id", projectId);
    return request<Job[]>(`/animation/jobs?${params.toString()}`);
  },
  engines: () => request<EnginesResponse>("/animation/engines"),

  voiceEngines: (refresh = false) =>
    request<VoiceEnginesResponse>(`/voice/engines${refresh ? "?refresh=true" : ""}`),
  previewVoice: async (payload: {
    text: string;
    engine?: string;
    voice?: string;
    rate?: number;
    pitch?: number;
    volume?: number;
    emotion?: string;
  }): Promise<Blob> => {
    const response = await fetch(BASE + "/voice/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        // keep the status text
      }
      throw new Error(detail);
    }
    return response.blob();
  },

  sceneDialogue: (sceneId: string) => request<DialogueLine[]>(`/scenes/${sceneId}/dialogue`),
  createDialogueLine: (
    sceneId: string,
    payload: {
      character_id?: string | null;
      text: string;
      emotion?: string;
      voice_engine?: string;
      voice_name?: string;
      rate?: number;
      pitch?: number;
      volume?: number;
      start_ms?: number;
    }
  ) =>
    request<DialogueLine>(`/scenes/${sceneId}/dialogue`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateDialogueLine: (
    lineId: string,
    payload: Partial<{
      character_id: string | null;
      text: string;
      emotion: string;
      voice_engine: string;
      voice_name: string;
      rate: number;
      pitch: number;
      volume: number;
      start_ms: number;
      order_index: number;
    }>
  ) =>
    request<DialogueLine>(`/dialogue/${lineId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteDialogueLine: (lineId: string) =>
    request<{ deleted: boolean; line_id: string }>(`/dialogue/${lineId}`, { method: "DELETE" }),
  generateDialogueLine: (lineId: string) =>
    request<DialogueLine>(`/dialogue/${lineId}/generate`, { method: "POST" }),
  generateSceneDialogue: (sceneId: string) =>
    request<{ lines: DialogueLine[]; generated: number; errors: { line_id: string; error: string }[] }>(
      `/scenes/${sceneId}/dialogue/generate`,
      { method: "POST" }
    ),
  importSceneDialogue: (sceneId: string, replace = false) =>
    request<DialogueLine[]>(`/scenes/${sceneId}/dialogue/import`, {
      method: "POST",
      body: JSON.stringify({ replace }),
    }),

  episodes: (projectId?: string) =>
    request<Episode[]>(`/episodes${projectId ? `?project_id=${projectId}` : ""}`),
  createEpisode: (payload: { project_id: string; name: string; description?: string }) =>
    request<Episode>("/episodes", { method: "POST", body: JSON.stringify(payload) }),
  episode: (id: string) => request<Episode>(`/episodes/${id}`),
  updateEpisode: (id: string, payload: { name?: string; description?: string }) =>
    request<Episode>(`/episodes/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteEpisode: (id: string) =>
    request<{ deleted: boolean; episode_id: string }>(`/episodes/${id}`, { method: "DELETE" }),
  saveEpisodeTimeline: (id: string, timeline: EpisodeTimeline) =>
    request<Episode>(`/episodes/${id}/timeline`, {
      method: "PUT",
      body: JSON.stringify(timeline),
    }),
  exportEpisode: (id: string, timeline?: EpisodeTimeline) =>
    request<Episode>(`/episodes/${id}/export`, {
      method: "POST",
      body: JSON.stringify(timeline ? { timeline } : {}),
    }),
  cancelEpisodeExport: (id: string) =>
    request<{ episode_id: string; status: string }>(`/episodes/${id}/cancel`, { method: "POST" }),

  settings: () => request<SettingsPayload>("/settings"),
  saveSettings: (config: Partial<AppConfig>) =>
    request<SettingsPayload>("/settings", { method: "PUT", body: JSON.stringify(config) }),

  aiHealth: () => request<{ status: string; openai: Record<string, any>; model: string | null }>("/v1/ai/health"),
  aiTools: () =>
    request<{ count: number; tools: AIToolDefinition[] }>("/v1/ai/tools"),
  aiConversations: (projectId?: string) =>
    request<AIConversation[]>(`/v1/ai/conversations${projectId ? `?project_id=${projectId}` : ""}`),
  createAIConversation: (payload: {
    project_id?: string | null;
    episode_id?: string | null;
    title?: string;
    model?: string;
  }) =>
    request<AIConversation>("/v1/ai/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  aiConversation: (id: string) => request<AIConversation>(`/v1/ai/conversations/${id}`),
  sendAIMessage: (id: string, payload: { message: string; project_id?: string | null; episode_id?: string | null }) =>
    request<{
      conversation_id: string;
      message: string;
      tool_executions: Array<Record<string, any>>;
      response_id: string | null;
      confirmation_required: boolean;
    }>(`/v1/ai/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  aiToolExecutions: (conversationId?: string) =>
    request<AIToolExecution[]>(
      `/v1/ai/tool-executions${conversationId ? `?conversation_id=${conversationId}` : ""}`
    ),
  providerStatus: () => request<ProviderStatusResponse>("/v1/providers/status"),
  productionOverview: (projectId?: string) =>
    request<ProductionOverview>(`/v1/production/overview${projectId ? `?project_id=${projectId}` : ""}`),
  productionStatus: (runId: string) => request<ProductionRun>(`/v1/production/status/${runId}`),
  startProduction: (payload: {
    project_id: string;
    episode_id: string;
    plan?: Record<string, any>;
    confirm: boolean;
    idempotency_key?: string;
  }) =>
    request<ProductionRun>("/v1/production/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  pauseProduction: (runId: string) =>
    request<ProductionRun>(`/v1/production/pause/${runId}`, { method: "POST" }),
  resumeProduction: (runId: string) =>
    request<ProductionRun>(`/v1/production/resume/${runId}`, { method: "POST" }),
  cancelProduction: (runId: string) =>
    request<ProductionRun>(`/v1/production/cancel/${runId}`, { method: "POST" }),
  reviewScene: (sceneId: string) =>
    request<Record<string, any>>(`/v1/production/scenes/${sceneId}/review`, { method: "POST" }),
  approveScene: (sceneId: string, notes = "") =>
    request<Record<string, any>>(`/v1/production/scenes/${sceneId}/approve`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),
  rejectScene: (sceneId: string, notes = "") =>
    request<Record<string, any>>(`/v1/production/scenes/${sceneId}/reject`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    }),
  mcpStatus: () => request<Record<string, any>>("/v1/mcp/status"),
  chatgptTunnelStatus: () => request<ChatGPTTunnelStatus>("/v1/mcp/tunnel/status"),
  startChatGPTTunnel: (payload: { confirm: boolean; ttl_minutes: number }) =>
    request<ChatGPTTunnelStatus>("/v1/mcp/tunnel/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  stopChatGPTTunnel: () =>
    request<ChatGPTTunnelStatus>("/v1/mcp/tunnel/stop", { method: "POST" }),

  comfyTest: () => request<ComfyTest>("/comfy/test"),
  discovery: () => request<DiscoveryInfo>("/comfy/discovery"),
  models: () => request<ModelLists>("/comfy/models"),
};
