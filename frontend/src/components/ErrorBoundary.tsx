import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Cartoon Studio UI error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, color: "#f4f4f4", background: "#0d1117", minHeight: "100vh" }}>
          <h1 style={{ fontSize: 24, marginBottom: 12 }}>Something went wrong on this page.</h1>
          <p style={{ color: "#b9c0cc", marginBottom: 16 }}>
            The production data is safe. Reload the page, or return to the dashboard.
          </p>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              background: "#151b26",
              padding: 16,
              borderRadius: 8,
              color: "#ffb4a2",
              maxWidth: 900,
            }}
          >
            {this.state.error.message}
          </pre>
          <button className="btn primary" style={{ marginTop: 16 }} onClick={() => window.location.assign("/")}>
            Back to dashboard
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
