import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";

export default function RunList() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.runs()
        .then((r) => { if (alive) setRuns(r); })
        .catch((e) => { if (alive) setError(String(e)); });
    load();
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div>
      <h1>Runs</h1>
      <p className="lede">Lean rules-driven PDP pipeline for SGS Engineering.</p>
      <p><Link to="/new" className="btn">New run</Link></p>
      {error && <p className="error">{error}</p>}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>URL</th>
              <th>Stage</th>
              <th>Cost</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 && (
              <tr><td colSpan={6} className="muted">No runs yet.</td></tr>
            )}
            {runs.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/runs/${r.id}`}>#{r.id}</Link></td>
                <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                <td className="mono" style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
                  <Link to={`/runs/${r.id}`} title={r.url}>{r.url}</Link>
                </td>
                <td>{r.current_stage}/6</td>
                <td className="mono">${r.cost_usd.toFixed(4)}</td>
                <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
