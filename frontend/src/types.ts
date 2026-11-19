export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  archived: number;
  character_count: number;
  background_count: number;
  scene_count: number;
  job_count: number;
  asset_count: number;
}

export interface Job {
  id: string;
  project_id: string;
  scene_id?: string | null;
  workflow_id: string;
  workflow_name: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  progress: number;
  node?: string | null;
  prompt_id?: string | null;
  queue_position?: number | null;
  params: Record<string, unknown>;
  outputs: OutputItem[];
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface OutputItem {
  asset_id: string;
  filename: string;
  rel_path: string;
  kind: string;
  mime: string;
  url: string;
  metadata?: Record<string, unknown>;
}

export interface Asset {
  id: string;
  project_id: string;
  job_id: string;
  kind: string;
  filename: string;
  rel_path: string;
  mime: string;
  meta: Record<string, unknown>;
  url: string;
  created_at: string;
}

export interface MediaItem extends Asset {
  link_id: string;
  role: string;
  label: string;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  description: string;
  style: string;
  clothing: string;
  appearance: string;
  canonical_asset_id: string | null;
  canonical_url: string | null;
  canonical_created_at?: string | null;
  canonical_stale?: boolean;
  voice_engine: string;
  voice_name: string;
  voice_rate: number;
  voice_pitch: number;
  voice_volume: number;
  created_at: string;
  updated_at: string;
  reference_count: number;
  expression_count: number;
  pose_count: number;
  cover_asset_id: string | null;
  cover_url: string | null;
  approval_status?: string;
  memory?: Record<string, any>;
  model?: Record<string, any>;
  master_reference?: {
    asset_id: string | null;
    url: string | null;
    approved: boolean;
  };
}

export interface Background {
  id: string;
  project_id: string;
  name: string;
  description: string;
  aspect_ratio: string;
  width: number;
  height: number;
  created_at: string;
  image_count: number;
  cover_asset_id: string | null;
  cover_url: string | null;
}

export interface SceneCastMember {
  id: string;
  character_id: string;
  name: string;
  description: string;
  role: string;
  cover_url: string | null;
}

export interface SceneBackground {
  id: string;
  name: string;
  description: string;
  width: number;
  height: number;
  cover_url: string | null;
}

export interface SceneSettings {
  background_id?: string | null;
  workflow_id?: string;
  video_workflow_id?: string;
  width?: number;
  height?: number;
  steps?: number;
  cfg?: number;
  seed?: number;
  reference_asset_id?: string | null;
  reference_mode?: "identity" | "pose";
  denoise?: number;
  control_strength?: number;
  video_width?: number;
  video_height?: number;
  video_steps?: number;
  video_cfg?: number;
  video_seed?: number;
  length?: number;
  fps?: number;
  sampler?: string;
  scheduler?: string;
  start_image?: string;
}

export interface Scene {
  id: string;
  project_id: string;
  name: string;
  description: string;
  dialogue: string;
  action: string;
  camera: string;
  duration: number;
  settings: SceneSettings;
  background: SceneBackground | null;
  cast: SceneCastMember[];
  keyframe_count: number;
  video_count: number;
  dialogue_count: number;
  dialogue_duration_ms: number;
  approval_status?: "draft" | "approved" | "rejected" | string;
  quality?: Record<string, any>;
  cover_asset_id: string | null;
  cover_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineInfo {
  available: boolean;
  nodes: Record<string, boolean>;
  missing_nodes: string[];
  models: Record<string, string[]>;
  expected: Record<string, string>;
  missing_models?: string[];
  notes: string;
}

export interface VideoWorkflowSummary {
  id: string;
  name: string;
  engine: string;
  valid: boolean;
  errors: string[];
  runnable: boolean;
  missing_nodes: string[];
  models?: ModelStatus[];
}

export interface SceneReference {
  character_id: string | null;
  character_name: string;
  asset_id: string;
  url: string;
  role: string;
  label: string;
  source: "canonical" | "media" | "scene";
}

export interface EnginesResponse {
  wan22: EngineInfo;
  animatediff: EngineInfo;
  ipadapter: EngineInfo;
  controlnet: EngineInfo;
  workflows: VideoWorkflowSummary[];
}

export interface QueueState {
  running: Job | null;
  pending: Job[];
  counts: { running: number; queued: number };
}

export interface ModelStatus {
  role: string;
  label: string;
  value: string;
  available: boolean;
  options: string[];
}

export interface RoleDetail {
  role: string;
  label: string;
  node: string;
  input: string;
  class: string;
}

export interface WorkflowEntry {
  id: string;
  name: string;
  path: string;
  source: "studio" | "comfyui";
  format: "api" | "ui" | "unknown";
  engine: string;
  kind: string;
  description: string;
  roles: string[];
  valid: boolean;
  errors: string[];
  modified_at: string;
  runnable?: boolean;
  model_status?: ModelStatus[];
  roles_detail?: RoleDetail[];
  missing_nodes?: string[];
  comfy_error?: string;
}

export interface WorkflowDetail {
  entry: WorkflowEntry;
  api: Record<string, unknown>;
  mapping: Record<string, unknown>;
}

export interface ValidateResult {
  valid: boolean;
  runnable?: boolean;
  checks: {
    role: string;
    label: string;
    node: string;
    input: string;
    ok: boolean;
    message: string;
  }[];
  models: ModelStatus[];
  missing_nodes?: string[];
  errors: string[];
}

export interface DashboardData {
  counts: {
    projects: number;
    characters: number;
    backgrounds: number;
    scenes: number;
    episodes: number;
    assets: number;
    jobs_completed: number;
  };
  comfyui: {
    connected: boolean;
    server_url: string;
    version?: string;
    error?: string;
    devices?: { name: string; vram_total: number; vram_free: number }[];
    ram_total?: number;
    ram_free?: number;
  };
  system: {
    cpu_percent: number;
    ram_total_gb: number;
    ram_used_gb: number;
    ram_percent: number;
    gpu: {
      name: string;
      utilization_percent: number;
      vram_used_mb: number;
      vram_total_mb: number;
      temperature_c: number;
    } | null;
  };
  current_job: Job | null;
  recent_jobs: Job[];
  recent_assets: Asset[];
}

export interface ModelFileEntry {
  name: string;
  relative_path: string | null;
  path: string | null;
  category: string;
  size_bytes: number | null;
  size_gb: number | null;
  architecture: string;
  confidence: string;
  detection_source: string;
  detection_detail: string;
  metadata: Record<string, any>;
  installed_in_comfy: boolean;
  compatible_engines: string[];
  modified_at: string | null;
}

export interface ModelRecommendation {
  name: string;
  filename_hints: string[];
  category: string;
  source: string;
  architecture: string;
  intended_use: string;
  license: string;
  license_notes: string;
  download_size: string;
  vram: string;
  compatibility: string;
  cartoon_suitability: string;
  reference_conditioning: string;
  installed: boolean;
  installed_file: string | null;
  status: string;
  download: {
    available: boolean;
    provider?: string;
    filename?: string;
    category?: string;
    size_bytes?: number;
    size_gb?: number;
    sha256?: string;
    license?: string;
    token_configured?: boolean;
    token_env?: string | null;
    reason?: string;
  };
}

export interface ModelDownload {
  id: string;
  recommendation: string;
  filename: string;
  category: string;
  status: "queued" | "downloading" | "verifying" | "completed" | "failed" | "cancelled";
  bytes_downloaded: number;
  bytes_total: number;
  percent: number;
  speed_mbps: number;
  path: string;
  error: string | null;
  message: string;
  started_at: number | null;
  finished_at: number | null;
}

export interface ModelConfig {
  default_architecture: string;
  checkpoints: Record<string, string>;
  vae: Record<string, string>;
  lora: { name: string; strength: number; architecture: string };
  workflows: Record<string, string>;
  presets: Record<string, Record<string, any>>;
  low_vram: boolean;
  tiled_vae: boolean;
  cpu_offload: string;
  attention: string;
  batch_size: number;
  max_pixels: number;
}

export interface FastModeStatus {
  enabled: boolean;
  lora: string;
  lora_installed: boolean;
  strength: number;
  steps: number;
  cfg: number;
  sampler: string;
  scheduler: string;
  installed_loras: Record<string, boolean>;
  available_presets: number[];
}

export interface ModelCatalog {
  config: ModelConfig;
  active: Record<string, any>;
  comfyui: Record<string, any>;
  models: Record<string, ModelFileEntry[]>;
  missing: Array<{ kind: string; severity: string; message: string; action: string }>;
  recommendations: ModelRecommendation[];
  model_dirs: string[];
  note: string;
}

export interface SettingsPayload {
  config: AppConfig;
  defaults: AppConfig;
  ffmpeg_detected: string;
  paths_exist: Record<string, boolean>;
}

export interface AppConfig {
  comfyui: {
    server_url: string;
    install_path: string;
    output_dir: string;
    models_dirs: string[];
    auto_discover: boolean;
    request_timeout_seconds: number;
  };
  paths: {
    workflow_dir: string;
    output_dir: string;
    assets_dir: string;
    projects_dir: string;
    logs_dir: string;
    data_dir: string;
  };
  generation: {
    default_workflow: string;
    width: number;
    height: number;
    steps: number;
    cfg: number;
    sampler: string;
    scheduler: string;
    batch_size: number;
    seed: number;
    negative_prompt: string;
    timeout_seconds: number;
    max_concurrent_jobs: number;
  };
  models: ModelConfig;
  ffmpeg: { path: string };
  tts: {
    default_engine: string;
    default_voice: string;
    preview_text: string;
    piper_path: string;
    piper_model_dir: string;
    timeout_seconds: number;
  };
  server: { host: string; port: number };
  ui: { poll_interval_ms: number };
}

export interface ComfyTest {
  connected: boolean;
  server_url: string;
  error?: string;
  version?: string;
  python?: string;
  pytorch?: string;
  os?: string;
  ram_total?: number;
  ram_free?: number;
  device?: string;
  vram_total?: number;
  vram_free?: number;
  queue_running?: number;
  queue_pending?: number;
  node_count?: number;
}

export interface DiscoveryInfo {
  process_pid: number | null;
  argv: string[];
  install_path: string;
  output_dir: string;
  input_dir: string;
  extra_model_paths: string;
  model_dirs: string[];
  model_folder_paths: Record<string, string[]>;
  user_workflows_dir: string;
  server_url: string;
  discovered_from_process: boolean;
}

export interface ModelLists {
  checkpoints: string[];
  diffusion_models: string[];
  text_encoders: string[];
  vaes: string[];
  samplers: string[];
  schedulers: string[];
}

export interface VoiceInfo {
  id: string;
  name: string;
  locale: string;
  gender: string;
  age: string;
  path?: string;
}

export interface VoiceEngine {
  id: string;
  name: string;
  available: boolean;
  executable: string;
  voices: VoiceInfo[];
  free_form: boolean;
  notes: string;
}

export interface VoiceEnginesResponse {
  engines: VoiceEngine[];
  default_engine: string;
  default_voice: string;
  detected_at: string;
}

export interface VoiceAssignment {
  engine: string;
  voice: string;
  rate: number;
  pitch: number;
  volume: number;
}

export interface DialogueLine {
  id: string;
  project_id: string;
  scene_id: string;
  character_id: string | null;
  character_name: string | null;
  character_cover_url: string | null;
  order_index: number;
  text: string;
  emotion: string;
  voice_engine: string;
  voice_name: string;
  rate: number;
  pitch: number;
  volume: number;
  start_ms: number;
  audio_asset_id: string | null;
  audio_url: string | null;
  duration_ms: number;
  duration_seconds: number;
  voice_label: string;
  created_at: string;
  updated_at: string;
}

export interface EpisodeSegment {
  id?: string;
  scene_id: string;
  asset_id: string;
  kind: "video" | "image";
  duration_ms: number;
  trim_start_ms: number;
  transition: "cut" | "fade";
  motion: "none" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right";
  label: string;
  muted?: boolean;
}

export interface EpisodeAudio {
  id?: string;
  asset_id: string;
  start_ms: number;
  volume: number;
  loop: boolean;
  label: string;
  kind: "dialogue" | "music" | "sfx" | "other";
}

export interface EpisodeSettings {
  width: number;
  height: number;
  fps: number;
  subtitles: "soft" | "none";
  background_music_asset_id: string | null;
  background_music_volume: number;
  fade_duration_ms: number;
}

export interface EpisodeTimeline {
  segments: EpisodeSegment[];
  audio: EpisodeAudio[];
  settings: EpisodeSettings;
}

export interface Episode {
  id: string;
  project_id: string;
  name: string;
  description: string;
  status: string;
  progress: number;
  timeline: EpisodeTimeline;
  settings: EpisodeSettings;
  output_url: string | null;
  subtitle_url: string | null;
  output_path: string | null;
  output_asset_id: string | null;
  subtitle_path: string | null;
  duration_ms: number;
  segment_count: number;
  audio_count: number;
  error: string | null;
  log: string | null;
  production_state?: string;
  production?: Record<string, any>;
  script?: Record<string, any>;
  storyboard?: Array<Record<string, any>>;
  approved_at?: string | null;
  approved_by?: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  tool_calls?: Array<Record<string, any>>;
  response_id?: string | null;
  created_at: string;
}

export interface AIDirectorModel {
  id: string;
  provider: "openai" | "ollama";
  model: string;
  label: string;
  available: boolean;
  tools: boolean;
  local: boolean;
  parameter_size?: string;
  quantization?: string;
}

export interface AIToolExecution {  id: string;
  conversation_id: string | null;
  tool_name: string;
  arguments: Record<string, any>;
  result: Record<string, any>;
  status: string;
  error?: string | null;
  actor: string;
  created_at: string;
  finished_at?: string | null;
}

export interface AIConversation {
  id: string;
  project_id: string | null;
  episode_id: string | null;
  title: string;
  model: string;
  last_response_id: string | null;
  context_json: string;
  created_at: string;
  updated_at: string;
  messages?: AIMessage[];
  tool_executions?: AIToolExecution[];
}

export interface AIToolDefinition {
  name: string;
  description: string;
  input_schema: Record<string, any>;
  scope: string;
  confirmation_required: boolean;
}

export interface ProviderInfo {
  name: string;
  type: string;
  capabilities: string[];
  available: boolean;
  input_constraints: Record<string, any>;
  output_constraints: Record<string, any>;
  resource_estimate: Record<string, any>;
  config: Record<string, any>;
  notes: string;
  live_connected?: boolean;
  device?: Record<string, any> | null;
}

export interface ProviderStatusResponse {
  providers: ProviderInfo[];
  comfyui_connected: boolean;
  defaults: Record<string, string>;
  system?: Record<string, any>;
}

export interface ProductionTask {
  id: string;
  run_id: string;
  stage: string;
  scene_id: string | null;
  job_id: string | null;
  status: string;
  attempts: number;
  error: string | null;
  payload: Record<string, any>;
  result: Record<string, any>;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ProductionRun {
  run_id: string;
  project_id: string;
  episode_id: string;
  state: string;
  status: string;
  progress: number;
  current_stage: string | null;
  plan: Record<string, any>;
  error: string | null;
  log: string | null;
  tasks: ProductionTask[];
  started_at: string | null;
  finished_at: string | null;
}

export interface ProductionOverview {
  project_id: string | null;
  scenes: { total: number; completed: number; pending: number; failed: number };
  production_runs: {
    running: number;
    paused: number;
    failed: number;
    completed: number;
    recent: Array<Record<string, any>>;
  };
  providers: ProviderStatusResponse;
}

export interface ChatGPTTunnelStatus {
  active: boolean;
  public_url: string | null;
  connector_url: string | null;
  host: string | null;
  auth_mode: string;
  mcp_running: boolean;
  mcp_auth: string | null;
  expires_at: number | null;
  remaining_seconds: number | null;
  ttl_minutes: number;
  public_reachable: boolean;
  cloudflared_available: boolean;
  warning: string;
  message: string;
}

export interface CharacterSheetJob {
  sheet_id: string;
  character_id: string;
  kind: string;
  reference_asset_id: string | null;
  reference_approved: boolean | null;
  seed: number;
  jobs: Job[];
  items: Array<{ label: string; job_id: string | null; status: string | null }>;
  model: Record<string, any> | null;
}

export interface CharacterSheetStatus {
  sheet_id: string;
  character_id: string;
  kind: string | null;
  jobs: Job[];
  items: Array<{
    label: string | null;
    job_id: string | null;
    status: string | null;
    progress: number | null;
    error: string | null;
    outputs: Array<Record<string, any>>;
  }>;
  complete: boolean;
  failed: boolean;
}

export interface ProductionDepartment {
  id: string;
  name: string;
  status: "ready" | "partial" | "blocked" | string;
  summary: string;
  installed: Array<Record<string, any>>;
  missing: Array<Record<string, any>>;
  recommendations: Array<Record<string, any>>;
}

export interface ProductionRegistry {
  departments: ProductionDepartment[];
  summary: {
    ready: number;
    partial: number;
    blocked: number;
    total: number;
    ready_ids: string[];
    partial_ids: string[];
    blocked_ids: string[];
  };
  resources: Record<string, any>;
  llm: Record<string, any>;
  tts: Array<Record<string, any>>;
  image_catalog: Record<string, any>;
  comfyui_nodes: Record<string, any>;
  comfyui_error: string | null;
  recommendations: Array<Record<string, any>>;
  note: string;
}

export interface ShotPlan {
  version: number;
  generated_at: string;
  episode_id: string;
  project_id: string;
  episode_name: string;
  shot_count: number;
  shots: Array<Record<string, any>>;
  estimate: {
    image_seconds: number;
    animation_seconds: number;
    total_gpu_seconds: number;
    total_gpu_minutes: number;
    dialogue_lines: number;
    missing_keyframes: number;
    missing_animations: number;
    note: string;
  };
}
