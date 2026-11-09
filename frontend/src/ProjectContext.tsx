import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { Project } from "./types";

const STORAGE_KEY = "cartoon-studio.selected-project";

interface ProjectContextValue {
  projects: Project[];
  selectedId: string;
  selected: Project | null;
  loading: boolean;
  error: string;
  selectProject: (id: string) => void;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string>(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) || "";
    } catch {
      return "";
    }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshProjects = useCallback(async () => {
    try {
      const list = await api.projects();
      setProjects(list);
      setError("");
      setSelectedId((current) => {
        if (current && list.some((project) => project.id === current)) return current;
        return list[0]?.id || "";
      });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    try {
      if (selectedId) window.localStorage.setItem(STORAGE_KEY, selectedId);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // localStorage can be unavailable in hardened browsers; selection still works in memory.
    }
  }, [selectedId]);

  const value = useMemo<ProjectContextValue>(() => {
    const selected = projects.find((project) => project.id === selectedId) || null;
    return {
      projects,
      selectedId,
      selected,
      loading,
      error,
      selectProject: setSelectedId,
      refreshProjects,
    };
  }, [projects, selectedId, loading, error, refreshProjects]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) throw new Error("useProject must be used inside ProjectProvider.");
  return context;
}
