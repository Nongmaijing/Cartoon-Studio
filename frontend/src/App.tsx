import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { Sidebar } from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import Workflows from "./pages/Workflows";
import Settings from "./pages/Settings";
import Characters from "./pages/Characters";
import Backgrounds from "./pages/Backgrounds";
import Scenes from "./pages/Scenes";
import Animation from "./pages/Animation";
import Director from "./pages/Director";
import Voice from "./pages/Voice";
import Episode from "./pages/Episode";

export default function App() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const result = await api.comfyTest();
        if (alive) setConnected(result.connected);
      } catch {
        if (alive) setConnected(false);
      }
    };
    check();
    const timer = window.setInterval(check, 20000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="app">
      <Sidebar connected={connected} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/characters" element={<Characters />} />
          <Route path="/backgrounds" element={<Backgrounds />} />
          <Route path="/scenes" element={<Scenes />} />
          <Route path="/animation" element={<Animation />} />
          <Route path="/director" element={<Director />} />
          <Route path="/voice" element={<Voice />} />
          <Route path="/episode" element={<Episode />} />
          <Route path="/workflows" element={<Workflows />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
