import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type {
  AIConversation,
  AIDirectorModel,
  AIMessage,
  ChatGPTTunnelStatus,
  Episode,
  ProductionOverview,
  ProductionRun,
  ProviderInfo,
  Scene,
} from "../types";
import { Alert, EmptyState, PageHeader, ProgressBar, StatusBadge } from "../components/Ui";

interface LiveTool {
  name: string;
  result: Record<string, unknown>;
}

function isActiveRun(run: ProductionRun | null): boolean {
  return !!run && ["running", "paused"].includes(run.status);
}

function toolSummary(result: Record<string, unknown>): string {
  if (result.error) return `error: ${String(result.error)}`;
  if (result.confirmation_required) return "confirmation required";
  if (result.job_id) return `job ${String(result.job_id)}`;
  if (result.run_id) return `run ${String(result.run_id)}`;
  if (result.scene_id) return `scene ${String(result.scene_id)}`;
  if (result.episode_id) return `episode ${String(result.episode_id)}`;
  return result.ok === false ? "failed" : "completed";
}

export default function Director() {
  const { selectedId, projects } = useProject();
  const [conversations, setConversations] = useState<AIConversation[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [toolExecutions, setToolExecutions] = useState<Array<Record<string, any>>>([]);
  const [liveTools, setLiveTools] = useState<LiveTool[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [confirmationRequired, setConfirmationRequired] = useState(false);

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState("");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [overview, setOverview] = useState<ProductionOverview | null>(null);
  const [run, setRun] = useState<ProductionRun | null>(null);
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [aiModel, setAiModel] = useState<string | null>(null);
  const [localLlm, setLocalLlm] = useState<string | null>(null);
  const [directorModels, setDirectorModels] = useState<AIDirectorModel[]>([]);
  const [directorModel, setDirectorModel] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tunnel, setTunnel] = useState<ChatGPTTunnelStatus | null>(null);
  const [tunnelBusy, setTunnelBusy] = useState(false);
  const [tunnelError, setTunnelError] = useState("");
  const [tunnelTtl, setTunnelTtl] = useState(30);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  const selectedProject = projects.find((project) => project.id === selectedId) || null;
  const selectedEpisode = episodes.find((episode) => episode.id === selectedEpisodeId) || null;
  const providers: ProviderInfo[] = overview?.providers?.providers || [];

  const scrollMessages = useCallback(() => {
    window.setTimeout(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }, 50);
  }, []);

  const loadTunnel = useCallback(async () => {
    try {
      setTunnel(await api.chatgptTunnelStatus());
      setTunnelError("");
    } catch (exc) {
      setTunnelError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  const loadOverview = useCallback(async () => {
    if (!selectedId) return;
    try {
      const data = await api.productionOverview(selectedId);
      setOverview(data);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  const loadScenes = useCallback(async () => {
    if (!selectedId) {
      setScenes([]);
      return;
    }
    try {
      setScenes(await api.scenes(selectedId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId]);

  const loadProjectData = useCallback(async () => {
    if (!selectedId) {
      setEpisodes([]);
      setScenes([]);
      setConversations([]);
      setConversationId("");
      setOverview(null);
      return;
    }
    try {
      const [episodeList, conversationList, health, modelList] = await Promise.all([
        api.episodes(selectedId),
        api.aiConversations(selectedId),
        api.aiHealth(),
        api.aiModels(),
      ]);
      setEpisodes(episodeList);
      setConversations(conversationList);
      setAiConfigured(health.openai.configured);
      setAiModel(health.model);
      setLocalLlm(health.llm?.ollama?.available ? String(health.llm.ollama.default_model || "ollama") : null);
      setDirectorModels(modelList.models);
      setDirectorModel((current) => {
        if (current) return current;
        const stored = window.localStorage.getItem("directorModel") || "";
        if (modelList.models.some((item) => item.id === stored)) return stored;
        if (modelList.default) return modelList.default;
        return modelList.models.find((item) => item.tools)?.id || "";
      });
      setSelectedEpisodeId((current) =>
        current && episodeList.some((episode) => episode.id === current) ? current : episodeList[0]?.id || ""
      );
      setConversationId((current) =>
        current && conversationList.some((conversation) => conversation.id === current)
          ? current
          : conversationList[0]?.id || ""
      );
      await Promise.all([loadOverview(), loadScenes()]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [selectedId, loadOverview, loadScenes]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  useEffect(() => {
    loadTunnel();
    const timer = window.setInterval(loadTunnel, 5000);
    return () => window.clearInterval(timer);
  }, [loadTunnel]);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setToolExecutions([]);
      return;
    }
    api
      .aiConversation(conversationId)
      .then((conversation) => {
        setMessages(conversation.messages || []);
        setToolExecutions(conversation.tool_executions || []);
        scrollMessages();
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, [conversationId, scrollMessages]);

  useEffect(() => {
    if (!run || !isActiveRun(run)) return;
    const runId = run.run_id;
    const timer = window.setInterval(async () => {
      try {
        const current = await api.productionStatus(runId);
        setRun(current);
        if (["completed", "failed", "cancelled"].includes(current.status)) {
          window.clearInterval(timer);
          await Promise.all([loadOverview(), loadScenes()]);
          if (current.status === "completed") setNotice("Production run completed.");
          if (current.status === "failed") setError(current.error || "Production run failed.");
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc));
        window.clearInterval(timer);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run?.run_id, run?.status, loadOverview, loadScenes]);

  useEffect(() => {
    scrollMessages();
  }, [messages, liveTools, scrollMessages]);

  const ensureConversation = async (): Promise<string> => {
    if (conversationId) return conversationId;
    const created = await api.createAIConversation({
      project_id: selectedId,
      episode_id: selectedEpisodeId || null,
      title: selectedProject ? `Director — ${selectedProject.name}` : "Director chat",
    });
    setConversations((current) => [created, ...current]);
    setConversationId(created.id);
    return created.id;
  };

  const refreshAiStatus = async () => {
    try {
      const health = await api.aiHealth();
      setAiConfigured(health.openai.configured);
      setAiModel(health.model);
      setLocalLlm(health.llm?.ollama?.available ? String(health.llm.ollama.default_model || "ollama") : null);
      setNotice(health.openai.configured ? "OpenAI connection is configured." : "OpenAI is not configured for Director chat.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || sending || !selectedId) return;
    setError("");
    setNotice("");
    setSending(true);
    setStatusText("Connecting to the Director…");
    setLiveTools([]);
    setConfirmationRequired(false);
    const localUser: AIMessage = {
      id: `local-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, localUser]);
    setInput("");
    try {
      const id = await ensureConversation();
      const selectedDirectorModel = directorModels.find((item) => item.id === directorModel);
      const response = await fetch(`/api/v1/ai/conversations/${id}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          project_id: selectedId,
          episode_id: selectedEpisodeId || null,
          provider: selectedDirectorModel?.provider || null,
          model: selectedDirectorModel?.model || null,
        }),
      });
      if (!response.ok || !response.body) {
        let detail = `${response.status} ${response.statusText}`;
        try {
          const body = await response.json();
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
        } catch {
          // keep status text
        }
        throw new Error(detail);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finished = false;
      while (!finished) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          let event = "message";
          let data = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          let payload: Record<string, any> = {};
          try {
            payload = data ? JSON.parse(data) : {};
          } catch {
            payload = { message: data };
          }
          if (event === "status") {
            setStatusText(String(payload.message || "Working…"));
          } else if (event === "tool_execution") {
            setLiveTools((current) => [
              ...current,
              { name: String(payload.name || "tool"), result: (payload.result || {}) as Record<string, unknown> },
            ]);
            setStatusText(`Executed ${String(payload.name || "tool")}`);
          } else if (event === "assistant_message") {
            const assistant: AIMessage = {
              id: `local-assistant-${Date.now()}`,
              conversation_id: id,
              role: "assistant",
              content: String(payload.message || ""),
              created_at: new Date().toISOString(),
            };
            setMessages((current) => [...current, assistant]);
            setConfirmationRequired(Boolean(payload.confirmation_required));
            setStatusText("");
          } else if (event === "error") {
            setError(String(payload.error || "The Director encountered an error."));
            setStatusText("");
          } else if (event === "done") {
            finished = true;
            setStatusText("");
          }
          boundary = buffer.indexOf("\n\n");
        }
      }
      const conversation = await api.aiConversation(id);
      setMessages(conversation.messages || []);
      setToolExecutions(conversation.tool_executions || []);
      await Promise.all([loadOverview(), loadScenes()]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSending(false);
      setStatusText("");
      scrollMessages();
    }
  };

  const createConversation = async () => {
    if (!selectedId) return;
    try {
      const created = await api.createAIConversation({
        project_id: selectedId,
        episode_id: selectedEpisodeId || null,
        title: selectedProject ? `Director — ${selectedProject.name}` : "Director chat",
      });
      setConversations((current) => [created, ...current]);
      setConversationId(created.id);
      setNotice("New Director conversation created.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const connectChatGPT = async () => {
    if (
      !window.confirm(
        "Start a public Cloudflare tunnel with MCP authentication disabled?\n\n" +
          "Anyone with the connector URL can control this Cartoon Studio instance. " +
          (tunnelTtl === 0
            ? "The tunnel will stay active until you click Disconnect & secure, or until the backend/cloudflared stops."
            : `The tunnel and no-auth mode stop automatically after ${tunnelTtl} minutes.`)
      )
    ) {
      return;
    }
    setTunnelBusy(true);
    setTunnelError("");
    setNotice("Starting the ChatGPT tunnel. This can take 20–40 seconds…");
    try {
      const status = await api.startChatGPTTunnel({ confirm: true, ttl_minutes: tunnelTtl });
      setTunnel(status);
      setNotice("ChatGPT tunnel is live. Copy the connector URL into ChatGPT.");
    } catch (exc) {
      setTunnelError(exc instanceof Error ? exc.message : String(exc));
      setNotice("");
    } finally {
      setTunnelBusy(false);
    }
  };

  const disconnectChatGPT = async () => {
    setTunnelBusy(true);
    setTunnelError("");
    setNotice("Stopping the tunnel and restoring bearer authentication…");
    try {
      const status = await api.stopChatGPTTunnel();
      setTunnel(status);
      setNotice("Tunnel stopped. MCP bearer authentication is restored.");
    } catch (exc) {
      setTunnelError(exc instanceof Error ? exc.message : String(exc));
      setNotice("");
    } finally {
      setTunnelBusy(false);
    }
  };

  const copyConnectorUrl = async () => {
    if (!tunnel?.connector_url) return;
    try {
      await navigator.clipboard.writeText(tunnel.connector_url);
      setNotice("Connector URL copied. Paste it into ChatGPT.");
    } catch {
      setTunnelError("Could not copy automatically. Select and copy the URL manually.");
    }
  };

  const startProduction = async () => {
    if (!selectedId || !selectedEpisodeId) {
      setError("Select an episode before starting production.");
      return;
    }
    if (scenes.length === 0) {
      setError("Create at least one scene before starting production.");
      return;
    }
    if (!window.confirm("Start the automated production run for this episode? This can queue image, audio and render jobs.")) {
      return;
    }
    setError("");
    setNotice("");
    try {
      const started = await api.startProduction({
        project_id: selectedId,
        episode_id: selectedEpisodeId,
        plan: {
          scenes: scenes.map((scene) => ({
            scene_id: scene.id,
            motion: "zoom_in",
            transition: "fade",
          })),
          assemble: true,
        },
        confirm: true,
        idempotency_key: `production-${selectedEpisodeId}-${Date.now()}`,
      });
      setRun(started);
      setNotice("Production queued. Monitor the task list on the right.");
      await loadOverview();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const controlRun = async (action: "pause" | "resume" | "cancel") => {
    if (!run) return;
    try {
      const updated =
        action === "pause"
          ? await api.pauseProduction(run.run_id)
          : action === "resume"
          ? await api.resumeProduction(run.run_id)
          : await api.cancelProduction(run.run_id);
      setRun(updated);
      setNotice(`Production ${action === "cancel" ? "cancel requested" : action + "d"}.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const reviewScene = async (sceneId: string) => {
    try {
      const report = await api.reviewScene(sceneId);
      setNotice(`Scene review: ${report.status}. ${report.summary || ""}`);
      await loadScenes();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const approveScene = async (sceneId: string) => {
    try {
      await api.approveScene(sceneId);
      setNotice("Scene approved.");
      await Promise.all([loadScenes(), loadOverview()]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const rejectScene = async (sceneId: string) => {
    try {
      await api.rejectScene(sceneId, "Rejected from AI Director.");
      setNotice("Scene rejected.");
      await Promise.all([loadScenes(), loadOverview()]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  if (!selectedId) {
    return (
      <>
        <PageHeader title="AI Director" subtitle="Plan, execute and monitor cartoon production with an AI director." />
        <EmptyState>
          No project selected. <Link className="link" to="/projects">Create or open a project</Link> to start
          directing.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="AI Director"
        subtitle="Bring your own OpenAI key for the in-app director, or control the same production through ChatGPT/MCP."
        actions={
          <>
            <button className="btn ghost" onClick={refreshAiStatus}>
              Refresh AI status
            </button>
            <button className="btn primary" onClick={createConversation}>
              New conversation
            </button>
          </>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}
      {aiConfigured === false && (
        <div style={{ marginBottom: 14 }}>
          <Alert kind="warn">
            OpenAI is not configured for Director chat. Set <span className="mono">OPENAI_API_KEY</span> and{" "}
            <span className="mono">OPENAI_MODEL</span> in <span className="mono">D:\bro\CartoonStudio\.env</span>,
            then restart the backend.{" "}
            {localLlm
              ? `Local Ollama (${localLlm}) is available for story/script generation through tools.`
              : "The MCP and production tools remain available without OpenAI."}
          </Alert>
        </div>
      )}

      <section className={`panel chatgpt-connect${tunnel?.active ? " live" : ""}`}>
        <div className="panel-head">
          <div>
            <h2>ChatGPT Connection</h2>
            <div className="panel-sub">
              One-click temporary MCP tunnel. Auto-secures after the selected session length.
            </div>
          </div>
          <span className={`chip ${tunnel?.active ? "exp" : ""}`}>
            {tunnel?.active ? "Tunnel live" : "Off"}
          </span>
        </div>

        {tunnelError && (
          <div style={{ marginBottom: 10 }}>
            <Alert kind="error">{tunnelError}</Alert>
          </div>
        )}

        {!tunnel?.active ? (
          <div className="chatgpt-connect-body">
            <p className="tiny muted">
              Starts a Cloudflare quick tunnel to port 8020 and temporarily switches MCP to no-auth
              mode. Anyone with the connector URL can control production. The tunnel and no-auth
              mode stop automatically after 30 minutes.
            </p>
            <div className="row">
              <label className="tiny muted" htmlFor="chatgpt-ttl">
                Keep connected
              </label>
              <select
                id="chatgpt-ttl"
                value={tunnelTtl}
                onChange={(event) => setTunnelTtl(Number(event.target.value))}
                disabled={tunnelBusy}
              >
                <option value={30}>30 minutes</option>
                <option value={60}>1 hour</option>
                <option value={120}>2 hours</option>
                <option value={240}>4 hours</option>
                <option value={480}>8 hours</option>
                <option value={0}>Never auto-stop</option>
              </select>
              <button
                className="btn primary"
                onClick={connectChatGPT}
                disabled={tunnelBusy || tunnel?.cloudflared_available === false}
              >
                {tunnelBusy ? "Starting tunnel…" : "Connect ChatGPT"}
              </button>
              <button className="btn ghost" onClick={loadTunnel} disabled={tunnelBusy}>
                Refresh
              </button>
              {tunnel?.cloudflared_available === false && (
                <span className="tiny" style={{ color: "var(--danger)" }}>
                  cloudflared not found
                </span>
              )}
            </div>
            <div className="tiny muted">
              Requires ChatGPT Business/Enterprise/Edu with custom MCP connectors enabled.
            </div>
          </div>
        ) : (
          <div className="chatgpt-connect-body">
            <Alert kind="warn">
              No-auth mode is live. Anyone with this URL can control production.{" "}
              {tunnel.ttl_minutes === 0
                ? "No auto-stop is set; click Disconnect & secure when finished."
                : `The tunnel stops automatically in ${Math.max(
                    0,
                    Math.ceil((tunnel.remaining_seconds ?? 0) / 60)
                  )} min.`}
            </Alert>
            {tunnel.public_reachable === false && (
              <Alert kind="warn">
                The public URL is not reachable yet. Wait a few seconds, then click Refresh status
                before adding the connector.
              </Alert>
            )}
            <div className="chatgpt-url-row">
              <code>{tunnel.connector_url}</code>
              <button className="btn sm" onClick={copyConnectorUrl}>
                Copy URL
              </button>
            </div>
            <ol className="chatgpt-steps">
              <li>
                Open{" "}
                <a className="link" href="https://chatgpt.com/plugins" target="_blank" rel="noreferrer">
                  ChatGPT Plugins
                </a>
                .
              </li>
              <li>Add a custom MCP server / connector.</li>
              <li>Paste the connector URL above.</li>
              <li>
                Choose <strong>No authentication</strong>.
              </li>
              <li>Create it, scan tools, and enable the connector.</li>
            </ol>
            <div className="tiny muted">
              This is a temporary quick tunnel. If it expires or the backend restarts, the URL
              changes. Click Connect ChatGPT again and update the connector URL in ChatGPT.
            </div>
            <div className="row">
              <button className="btn" onClick={disconnectChatGPT} disabled={tunnelBusy}>
                {tunnelBusy ? "Securing…" : "Disconnect & secure"}
              </button>
              <button className="btn ghost" onClick={loadTunnel} disabled={tunnelBusy}>
                Refresh status
              </button>
            </div>
          </div>
        )}
      </section>

      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Director Chat</h2>
              <div className="panel-sub">
                {selectedProject?.name} · {selectedEpisode?.name || "No episode selected"} ·{" "}
                {directorModels.find((item) => item.id === directorModel)?.label ||
                  (aiConfigured ? `model ${aiModel || "configured"}` : localLlm ? `local LLM ${localLlm}` : "No model configured")}
              </div>
            </div>
            {sending && <StatusBadge status="running" />}
          </div>

          <div className="ai-conversation-bar">
            <select
              value={conversationId}
              onChange={(event) => {
                const next = event.target.value;
                setConversationId(next);
                const conversation = conversations.find((item) => item.id === next);
                if (conversation?.model && directorModels.some((item) => item.id === conversation.model)) {
                  setDirectorModel(conversation.model);
                  window.localStorage.setItem("directorModel", conversation.model);
                }
              }}
            >
              <option value="">New conversation</option>
              {conversations.map((conversation) => (
                <option key={conversation.id} value={conversation.id}>
                  {conversation.title || conversation.id}
                </option>
              ))}
            </select>
            <select
              value={directorModel}
              onChange={(event) => {
                setDirectorModel(event.target.value);
                window.localStorage.setItem("directorModel", event.target.value);
              }}
              title="Director model"
            >
              <option value="">Default model</option>
              {directorModels.map((model) => (
                <option key={model.id} value={model.id} disabled={!model.tools}>
                  {model.label}
                  {model.tools ? "" : " (no tool calling)"}
                </option>
              ))}
            </select>
          </div>

          <div className="ai-messages" ref={messagesRef}>
            {messages.length === 0 && !sending && (
              <div className="media-empty">
                Ask the Director to plan a story, create characters, build a storyboard, start production or review
                scenes. Expensive actions require confirmation.
              </div>
            )}
            {messages.map((message) => (
              <div key={message.id} className={`ai-bubble ${message.role}`}>
                <div className="ai-role">{message.role === "user" ? "You" : "AI Director"}</div>
                <div style={{ whiteSpace: "pre-wrap" }}>{message.content}</div>
                {message.tool_calls && message.tool_calls.length > 0 && (
                  <details className="ai-tool-details">
                    <summary>{message.tool_calls.length} tool execution(s)</summary>
                    {message.tool_calls.map((tool, index) => (
                      <div className="ai-tool" key={index}>
                        <strong>{String(tool.name || "tool")}</strong>
                        <span>{toolSummary((tool.result || {}) as Record<string, unknown>)}</span>
                      </div>
                    ))}
                  </details>
                )}
              </div>
            ))}
            {liveTools.map((tool, index) => (
              <div className="ai-tool" key={`live-${index}`}>
                <strong>{tool.name}</strong>
                <span>{toolSummary(tool.result)}</span>
              </div>
            ))}
            {statusText && <div className="ai-status">{statusText}</div>}
          </div>

          {toolExecutions.length > 0 && (
            <details className="ai-tool-details" style={{ marginTop: 8 }}>
              <summary>{toolExecutions.length} recorded tool execution(s)</summary>
              {toolExecutions.slice(-20).map((execution) => (
                <div className="ai-tool" key={String(execution.id)}>
                  <strong>{String(execution.tool_name || "tool")}</strong>
                  <span>{String(execution.status || "")}</span>
                </div>
              ))}
            </details>
          )}

          {confirmationRequired && (
            <Alert kind="warn">
              The Director is waiting for confirmation of an expensive or destructive action. Reply with your explicit
              approval.
            </Alert>
          )}

          <div className="ai-composer">
            <textarea
              value={input}
              placeholder='e.g. "Plan a 60-second story about a shy rabbit who finds a lost star."'
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
            />
            <button className="btn primary" onClick={send} disabled={sending || !input.trim()}>
              {sending ? "Working…" : "Send"}
            </button>
          </div>
          <div className="tiny muted" style={{ marginTop: 6 }}>
            The Director executes real backend tools. It never reports a generation as complete until the backend job
            reports completed.
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Production Control</h2>
              <div className="panel-sub">Same production system used by ChatGPT/MCP.</div>
            </div>
            {run && <StatusBadge status={run.status} />}
          </div>

          <div className="field" style={{ marginBottom: 10 }}>
            <label>Episode</label>
            <select value={selectedEpisodeId} onChange={(event) => setSelectedEpisodeId(event.target.value)}>
              <option value="">No episode</option>
              {episodes.map((episode) => (
                <option key={episode.id} value={episode.id}>
                  {episode.name} · {episode.status}
                </option>
              ))}
            </select>
          </div>

          <div className="row" style={{ marginBottom: 12 }}>
            <button className="btn primary sm" onClick={startProduction} disabled={!selectedEpisodeId || scenes.length === 0}>
              Start production
            </button>
            {run && (
              <>
                {run.status === "running" && (
                  <button className="btn sm" onClick={() => controlRun("pause")}>Pause</button>
                )}
                {run.status === "paused" && (
                  <button className="btn sm" onClick={() => controlRun("resume")}>Resume</button>
                )}
                {isActiveRun(run) && (
                  <button className="btn sm" onClick={() => controlRun("cancel")}>Cancel</button>
                )}
              </>
            )}
          </div>

          <div className="stat-grid ai-stats">
            <div className="stat"><div className="stat-value">{overview?.scenes.total ?? 0}</div><div className="stat-label">Scenes</div></div>
            <div className="stat"><div className="stat-value">{overview?.scenes.completed ?? 0}</div><div className="stat-label">Ready</div></div>
            <div className="stat"><div className="stat-value">{overview?.scenes.pending ?? 0}</div><div className="stat-label">Pending</div></div>
            <div className="stat"><div className="stat-value">{overview?.scenes.failed ?? 0}</div><div className="stat-label">Failed</div></div>
            <div className="stat"><div className="stat-value">{overview?.production_runs.running ?? 0}</div><div className="stat-label">Runs</div></div>
            <div className="stat"><div className="stat-value">{overview?.production_runs.completed ?? 0}</div><div className="stat-label">Done</div></div>
          </div>

          {run && (
            <div className="stack" style={{ marginTop: 12 }}>
              <div className="meter-row">
                <span>{run.state} · {run.current_stage || "—"}</span>
                <strong>{Math.round(run.progress)}%</strong>
              </div>
              <ProgressBar value={run.progress} />
              {run.error && <Alert kind="error">{run.error}</Alert>}
              <div className="ai-task-list">
                {run.tasks.map((task) => (
                  <div className="ai-task" key={task.id}>
                    <div className="row between">
                      <strong>{task.stage}</strong>
                      <span className={`chip ${task.status === "completed" ? "exp" : task.status === "failed" ? "pose" : ""}`}>
                        {task.status}
                      </span>
                    </div>
                    <div className="tiny muted">
                      {task.scene_id ? `scene ${task.scene_id}` : "episode"} · attempts {task.attempts}
                      {task.job_id ? ` · job ${task.job_id}` : ""}
                    </div>
                    {task.error && <div className="tiny" style={{ color: "var(--danger)" }}>{task.error}</div>}
                  </div>
                ))}
              </div>
              {run.log && <pre className="prompt-preview" style={{ maxHeight: 160, overflow: "auto" }}>{run.log}</pre>}
            </div>
          )}

          <div className="section-title" style={{ marginTop: 14 }}>Providers</div>
          <div className="ai-provider-list">
            {providers.map((provider) => (
              <div className="ai-provider" key={`${provider.type}-${provider.name}`}>
                <div className="row between">
                  <strong>{provider.name} · {provider.type}</strong>
                  <span className={`chip ${provider.available ? "exp" : ""}`}>
                    {provider.available ? "ready" : "unavailable"}
                  </span>
                </div>
                <div className="tiny muted">{provider.notes}</div>
              </div>
            ))}
            {providers.length === 0 && <div className="tiny muted">Provider status unavailable.</div>}
          </div>

          <div className="tiny muted" style={{ marginTop: 10 }}>
            ComfyUI: {overview?.providers?.comfyui_connected ? "connected" : "offline"} ·{" "}
            {overview?.providers?.defaults ? Object.entries(overview.providers.defaults).map(([key, value]) => `${key}=${value}`).join(" · ") : ""}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Scene Review</h2>
            <div className="panel-sub">Approve, reject, or run deterministic quality checks. Approvals persist across both interfaces.</div>
          </div>
          <button className="btn sm ghost" onClick={loadScenes}>Refresh</button>
        </div>
        {scenes.length === 0 ? (
          <div className="media-empty">No scenes yet. Create scenes or use the Director to generate a storyboard.</div>
        ) : (
          <div className="stack">
            {scenes.map((scene) => (
              <div className="ai-scene-row" key={scene.id}>
                <div className="row between">
                  <div>
                    <strong>{scene.name}</strong>
                    <div className="tiny muted">
                      {scene.background?.name || "No background"} · {scene.cast.length} cast ·{" "}
                      {scene.keyframe_count} keyframe(s) · {scene.dialogue_count} dialogue line(s) ·{" "}
                      quality {(scene.quality || {}).status || "not reviewed"}
                    </div>
                  </div>
                  <div className="row">
                    <span className={`chip ${scene.approval_status === "approved" ? "exp" : scene.approval_status === "rejected" ? "pose" : ""}`}>
                      {scene.approval_status || "draft"}
                    </span>
                    <button className="btn sm" onClick={() => reviewScene(scene.id)}>Review</button>
                    <button className="btn sm" onClick={() => approveScene(scene.id)}>Approve</button>
                    <button className="btn sm" onClick={() => rejectScene(scene.id)}>Reject</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
