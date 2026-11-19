import { NavLink } from "react-router-dom";
import { useProject } from "../ProjectContext";
import { Icon, type IconName } from "./Icons";

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  phase?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: "dashboard" },
  { to: "/projects", label: "Projects", icon: "projects" },
  { to: "/characters", label: "Characters", icon: "characters" },
  { to: "/backgrounds", label: "Backgrounds", icon: "backgrounds" },
  { to: "/scenes", label: "Scenes", icon: "scenes" },
  { to: "/animation", label: "Animation", icon: "animation" },
  { to: "/director", label: "AI Director", icon: "director" },
  { to: "/models", label: "Model Studio", icon: "models" },
  { to: "/voice", label: "Voice & Dialogue", icon: "voice" },
  { to: "/episode", label: "Episode Editor", icon: "episode" },
  { to: "/workflows", label: "Workflows", icon: "workflows" },
  { to: "/settings", label: "Settings", icon: "settings" },
];

export function Sidebar({ connected }: { connected: boolean | null }) {
  const { projects, selectedId, selectProject, loading } = useProject();
  const state = connected === null ? "warn" : connected ? "ok" : "bad";
  const text = connected === null ? "Checking ComfyUI" : connected ? "ComfyUI online" : "ComfyUI offline";
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">CS</div>
        <div className="brand-text">
          <div className="brand-name">Cartoon Studio</div>
          <div className="brand-sub">Local 2D production</div>
        </div>
      </div>

      <div className="project-switch">
        <label htmlFor="active-project">Active project</label>
        <select
          id="active-project"
          value={selectedId}
          onChange={(event) => selectProject(event.target.value)}
          disabled={loading}
        >
          {projects.length === 0 && <option value="">No projects yet</option>}
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      <nav className="nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            title={item.label}
          >
            <Icon name={item.icon} />
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="conn-pill" title={text}>
          <span className={`dot ${state}`} />
          <span className="conn-text">{text}</span>
        </div>
        <div className="meta">
          v0.7.0
          <br />
          Local-first production
          <br />
          ComfyUI + optional AI
        </div>
      </div>
    </aside>
  );
}
