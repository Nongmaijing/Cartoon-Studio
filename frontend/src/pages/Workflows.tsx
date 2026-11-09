import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ValidateResult, WorkflowDetail, WorkflowEntry } from "../types";
import { Alert, EmptyState, PageHeader, StatusBadge } from "../components/Ui";

export default function Workflows() {
  const [workflows, setWorkflows] = useState<WorkflowEntry[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [validation, setValidation] = useState<{ id: string; result: ValidateResult } | null>(null);
  const [busyId, setBusyId] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setWorkflows(await api.workflows());
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const view = async (workflow: WorkflowEntry) => {
    setBusyId(workflow.id);
    try {
      setDetail(await api.workflow(workflow.id));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusyId("");
    }
  };

  const validate = async (workflow: WorkflowEntry) => {
    setBusyId(workflow.id);
    setError("");
    try {
      const result = await api.validateWorkflow(workflow.id);
      setValidation({ id: workflow.id, result });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusyId("");
    }
  };

  const importFile = async (file: File) => {
    setError("");
    setNotice("");
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as Record<string, unknown>;
      const apiGraph = (parsed.api as Record<string, unknown>) || parsed;
      const mapping = (parsed.mapping as Record<string, unknown>) || undefined;
      const name = (parsed.name as string) || file.name.replace(/\.json$/i, "");
      const entry = await api.importWorkflow({ name, api: apiGraph, mapping });
      setNotice(`Imported "${entry.name}".`);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <>
      <PageHeader
        title="Workflows"
        subtitle="ComfyUI API workflows are preserved as JSON. A mapping sidecar connects simple UI fields to the actual node inputs."
        actions={
          <>
            <button className="btn ghost" onClick={refresh}>
              Refresh
            </button>
            <button className="btn primary" onClick={() => fileRef.current?.click()}>
              Import workflow
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) importFile(file);
              }}
            />
          </>
        }
      />

      {error && <div style={{ marginBottom: 14 }}><Alert kind="error">{error}</Alert></div>}
      {notice && <div style={{ marginBottom: 14 }}><Alert kind="ok">{notice}</Alert></div>}

      <Alert kind="info">
        Import accepts a ComfyUI <strong>API-format</strong> graph. If no mapping is supplied, roles are inferred
        from node classes and links. UI-format workflows from ComfyUI are listed read-only and must be exported as
        API format before they can run here.
      </Alert>

      <div style={{ height: 16 }} />

      {workflows.length === 0 ? (
        <EmptyState>No workflows discovered in CartoonStudio\workflows.</EmptyState>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))" }}>
          {workflows.map((workflow) => (
            <section className="panel" key={workflow.id}>
              <div className="panel-head">
                <div style={{ minWidth: 0 }}>
                  <h2 style={{ fontSize: 15 }}>{workflow.name}</h2>
                  <div className="panel-sub mono wrap">{workflow.id}</div>
                </div>
                <StatusBadge status={workflow.runnable ? "completed" : workflow.format === "ui" ? "interrupted" : "failed"} />
              </div>

              <div className="kv" style={{ marginBottom: 12 }}>
                <span className="k">Engine</span>
                <span className="v">{workflow.engine}</span>
                <span className="k">Kind</span>
                <span className="v">{workflow.kind}</span>
                <span className="k">Format</span>
                <span className="v">{workflow.format}</span>
                <span className="k">Source</span>
                <span className="v">{workflow.source}</span>
                <span className="k">Roles</span>
                <span className="v">{workflow.roles.length}</span>
              </div>

              {workflow.model_status && workflow.model_status.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div className="section-title">Models</div>
                  <div className="stack" style={{ gap: 6 }}>
                    {workflow.model_status.map((model) => (
                      <div key={model.role} className="row between small">
                        <span className="muted">{model.label}</span>
                        <span style={{ color: model.available ? "var(--success)" : "var(--danger)" }} className="wrap">
                          {model.value || "not set"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {workflow.errors.length > 0 && (
                <div className="alert warn small" style={{ marginBottom: 12 }}>
                  {workflow.errors.join(" ")}
                </div>
              )}

              <div className="btn-row">
                <button className="btn sm" onClick={() => view(workflow)} disabled={busyId === workflow.id}>
                  View JSON
                </button>
                {workflow.format === "api" && (
                  <button className="btn sm" onClick={() => validate(workflow)} disabled={busyId === workflow.id}>
                    Validate
                  </button>
                )}
                {workflow.source === "studio" && (
                  <a className="btn sm ghost" href={api.exportWorkflowUrl(workflow.id)}>
                    Export
                  </a>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="panel-head">
              <div>
                <h2>{detail.entry.name}</h2>
                <div className="panel-sub mono">{detail.entry.path}</div>
              </div>
              <button className="btn sm ghost" onClick={() => setDetail(null)}>
                Close
              </button>
            </div>
            <div className="section-title">Mapping roles</div>
            <pre className="code">{JSON.stringify(detail.mapping, null, 2)}</pre>
            <div className="section-title" style={{ marginTop: 14 }}>API workflow</div>
            <pre className="code">{JSON.stringify(detail.api, null, 2)}</pre>
          </div>
        </div>
      )}

      {validation && (
        <div className="modal-backdrop" onClick={() => setValidation(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="panel-head">
              <div>
                <h2>Validation · {validation.id}</h2>
                <div className="panel-sub">
                  {validation.result.valid ? "All mapped inputs exist in ComfyUI." : "Some mapped inputs are invalid."}
                </div>
              </div>
              <button className="btn sm ghost" onClick={() => setValidation(null)}>
                Close
              </button>
            </div>
            {validation.result.valid ? (
              <Alert kind="ok">Workflow is runnable.</Alert>
            ) : (
              <Alert kind="error">{validation.result.errors.join(" ")}</Alert>
            )}
            <div style={{ height: 12 }} />
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Node</th>
                  <th>Input</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {validation.result.checks.map((check) => (
                  <tr key={check.role}>
                    <td>{check.label}</td>
                    <td className="mono">{check.node}</td>
                    <td className="mono">{check.input}</td>
                    <td style={{ color: check.ok ? "var(--success)" : "var(--danger)" }}>
                      {check.ok ? "OK" : check.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
