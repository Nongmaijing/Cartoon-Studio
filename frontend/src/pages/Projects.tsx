import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../ProjectContext";
import type { Project } from "../types";
import { Alert, EmptyState, PageHeader } from "../components/Ui";

export default function Projects() {
  const navigate = useNavigate();
  const { selectedId, selectProject, refreshProjects } = useProject();
  const [projects, setProjects] = useState<Project[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      setProjects(await api.projects(includeArchived));
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, [includeArchived]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject(name.trim(), description.trim());
      setName("");
      setDescription("");
      setNotice(`Created project "${project.name}".`);
      await refresh();
      await refreshProjects();
      selectProject(project.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const rename = async (project: Project) => {
    if (!editName.trim()) return;
    try {
      await api.updateProject(project.id, { name: editName.trim() });
      setEditing(null);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const duplicate = async (project: Project) => {
    try {
      const copy = await api.duplicateProject(project.id);
      setNotice(`Duplicated as "${copy.name}".`);
      await refresh();
      await refreshProjects();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  const archive = async (project: Project) => {
    try {
      await api.archiveProject(project.id);
      setNotice(`Archived "${project.name}".`);
      await refresh();
      await refreshProjects();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  };

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle="A project keeps its characters, backgrounds, scenes, workflows and generated media together."
        actions={
          <label className="row small muted" style={{ gap: 8 }}>
            <input
              type="checkbox"
              style={{ width: 15, height: 15 }}
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            Show archived
          </label>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-head">
          <div>
            <h2>New Project</h2>
            <div className="panel-sub">Project files are stored separately from ComfyUI.</div>
          </div>
        </div>
        <div className="form-grid">
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="My cartoon episode" />
          </div>
          <div className="field">
            <label>Description</label>
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Optional"
            />
          </div>
        </div>
        <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
          <button className="btn primary" onClick={create} disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create project"}
          </button>
        </div>
      </section>

      {projects.length === 0 ? (
        <EmptyState>No projects yet. Create one above to start producing.</EmptyState>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))" }}>
          {projects.map((project) => (
            <section className="panel" key={project.id}>
              <div className="panel-head">
                <div style={{ minWidth: 0 }}>
                  {editing === project.id ? (
                    <div className="row">
                      <input value={editName} onChange={(event) => setEditName(event.target.value)} />
                      <button className="btn sm primary" onClick={() => rename(project)}>
                        Save
                      </button>
                    </div>
                  ) : (
                    <h2 style={{ fontSize: 15 }}>{project.name}</h2>
                  )}
                  <div className="panel-sub">{project.description || "No description"}</div>
                </div>
                <div className="btn-row">
                  {project.id === selectedId && <span className="badge completed">Active</span>}
                  {project.archived === 1 && <span className="badge cancelled">Archived</span>}
                </div>
              </div>

              <div className="kv" style={{ marginBottom: 14 }}>
                <span className="k">Characters</span>
                <span className="v">{project.character_count}</span>
                <span className="k">Backgrounds</span>
                <span className="v">{project.background_count}</span>
                <span className="k">Scenes</span>
                <span className="v">{project.scene_count}</span>
                <span className="k">Jobs</span>
                <span className="v">{project.job_count}</span>
                <span className="k">Outputs</span>
                <span className="v">{project.asset_count}</span>
                <span className="k">Created</span>
                <span className="v">{new Date(project.created_at).toLocaleString()}</span>
              </div>

              <div className="btn-row">
                {project.archived === 0 && (
                  <button
                    className="btn sm primary"
                    onClick={() => {
                      selectProject(project.id);
                      navigate("/");
                    }}
                  >
                    {project.id === selectedId ? "Open" : "Set active"}
                  </button>
                )}
                <button
                  className="btn sm"
                  onClick={() => {
                    setEditing(project.id);
                    setEditName(project.name);
                  }}
                >
                  Rename
                </button>
                <button className="btn sm" onClick={() => duplicate(project)}>
                  Duplicate
                </button>
                {project.archived === 0 && (
                  <button className="btn sm ghost" onClick={() => archive(project)}>
                    Archive
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
