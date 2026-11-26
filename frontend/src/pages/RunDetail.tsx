import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Stage = {
  stage: number;
  name: string;
  status: string;
  gate?: string;
  error?: string;
  duration_ms?: number;
};

type RuleResult = {
  rule_id: string;
  description: string;
  status: string;
  evidence: string;
  auto_fixed?: boolean;
};

type Draft = {
  title: string;
  overview: Array<{ text: string; claim_ids: string[] }>;
  features: Array<{ feature: string; benefit: string; claim_ids: string[] }>;
  specifications: Array<{ attribute: string; value: string; claim_ids: string[] }>;
  faqs: Array<{ question: string; answer: string; claim_ids: string[] }>;
  site_benefits: Array<{ text: string; claim_ids: string[] }>;
  gaps_addressed?: string[];
  word_count?: number;
};

export default function RunDetail() {
  const { id } = useParams();
  const runId = Number(id);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    const load = () =>
      api.getRun(runId)
        .then((d) => { if (alive) setData(d); })
        .catch((e) => { if (alive) setError(String(e)); });
    load();
    const t = setInterval(load, 2500);
    return () => { alive = false; clearInterval(t); };
  }, [runId]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  const run = data.run as {
    id: number; url: string; status: string; current_stage: number;
    identity_class?: string; cost_usd: number; input_tokens: number; output_tokens: number;
    released: boolean; error?: string;
  };
  const stages = (data.stages as Stage[]) || [];
  const compliance = data.compliance as {
    disposition: string; passed: number; failed: number; flagged: number;
    rules_evaluated: number; results: RuleResult[]; notes?: string[];
  } | null;
  const draft = data.draft as Draft | null;
  const ledger = data.fact_ledger as { claims?: Array<{ claim_id: string; statement: string; status: string; claim_type: string }>; gaps?: string[]; verified_count?: number } | null;
  const usage = (data.usage as Array<{ role: string; provider: string; model: string; cost_usd: number; input_tokens: number; output_tokens: number }>) || [];

  function downloadJson() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `ccr-run-${run.id}.json`;
    a.click();
  }

  function downloadMarkdown() {
    if (!draft) return;
    const lines = [
      `# ${draft.title}`,
      "",
      "## Overview",
      ...(draft.overview || []).map((b) => b.text),
      "",
      "## Features",
      ...(draft.features || []).map((f) => `- **${f.feature}** — ${f.benefit}`),
      "",
      "## Specifications",
      ...(draft.specifications || []).map((s) => `- ${s.attribute}: ${s.value}`),
      "",
      "## FAQs",
      ...(draft.faqs || []).map((q) => `### ${q.question}\n${q.answer}`),
      "",
      "## Site benefits",
      ...(draft.site_benefits || []).map((b) => `- ${b.text}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `ccr-run-${run.id}.md`;
    a.click();
  }

  return (
    <div>
      <p className="muted"><Link to="/">← Runs</Link></p>
      <h1>Run #{run.id}</h1>
      <p className="lede mono">{run.url}</p>

      <div className="panel">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <span className={`badge ${run.status}`}>{run.status}</span>
          {run.identity_class && <span className="badge">{run.identity_class}</span>}
          {run.released && <span className="badge released">released</span>}
          <span className="mono muted">${run.cost_usd.toFixed(4)} · {run.input_tokens + run.output_tokens} tokens</span>
        </div>
        {run.error && <p className="error" style={{ marginTop: 12 }}>{run.error}</p>}
        <div className="timeline">
          {stages.map((s) => (
            <div key={s.stage} className={`step-pill ${s.status}`}>
              {s.stage}. {s.name} · {s.status}
              {s.duration_ms != null ? ` · ${s.duration_ms}ms` : ""}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          <button type="button" className="secondary" onClick={downloadJson}>Download JSON</button>
          <button type="button" className="secondary" onClick={downloadMarkdown} disabled={!draft}>Download Markdown</button>
        </div>
      </div>

      {compliance && (
        <div className="panel">
          <h2>Compliance report</h2>
          <p>
            Disposition: <span className={`badge ${compliance.disposition.toLowerCase()}`}>{compliance.disposition}</span>
            {" "}· {compliance.passed} passed / {compliance.failed} failed / {compliance.flagged} flagged
            {" "}of {compliance.rules_evaluated}
          </p>
          <table>
            <thead>
              <tr><th>Rule</th><th>Status</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {compliance.results.map((r) => (
                <tr key={r.rule_id}>
                  <td>
                    <div className="mono">{r.rule_id}</div>
                    <div className="muted" style={{ fontSize: "0.85rem" }}>{r.description}</div>
                  </td>
                  <td><span className={`badge ${r.status.toLowerCase()}`}>{r.status}{r.auto_fixed ? " · auto" : ""}</span></td>
                  <td>{r.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {draft && (
        <div className="panel">
          <h2>Draft {draft.word_count ? `· ${draft.word_count} words` : ""}</h2>
          <h3 style={{ marginTop: 0 }}>{draft.title}</h3>
          <div className="draft-block">
            <h3>Overview</h3>
            {(draft.overview || []).map((b, i) => (
              <div key={i}>
                <p>{b.text}</p>
                <div className="claim-ids">{(b.claim_ids || []).join(", ")}</div>
              </div>
            ))}
          </div>
          <div className="draft-block">
            <h3>Features</h3>
            <ul>
              {(draft.features || []).map((f, i) => (
                <li key={i}><strong>{f.feature}</strong> — {f.benefit}
                  <div className="claim-ids">{(f.claim_ids || []).join(", ")}</div>
                </li>
              ))}
            </ul>
          </div>
          <div className="draft-block">
            <h3>Specifications</h3>
            <table>
              <tbody>
                {(draft.specifications || []).map((s, i) => (
                  <tr key={i}>
                    <td>{s.attribute}</td>
                    <td>{s.value}<div className="claim-ids">{(s.claim_ids || []).join(", ")}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {ledger && (
        <div className="panel">
          <h2>Fact ledger · {ledger.verified_count ?? (ledger.claims || []).filter((c) => c.status === "VERIFIED").length} verified</h2>
          <table>
            <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Statement</th></tr></thead>
            <tbody>
              {(ledger.claims || []).map((c) => (
                <tr key={c.claim_id}>
                  <td className="mono">{c.claim_id}</td>
                  <td>{c.claim_type}</td>
                  <td><span className={`badge ${c.status === "VERIFIED" ? "pass" : "fail"}`}>{c.status}</span></td>
                  <td>{c.statement}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(ledger.gaps || []).length > 0 && (
            <>
              <h3>Gaps</h3>
              <ul>{ledger.gaps!.map((g) => <li key={g}>{g}</li>)}</ul>
            </>
          )}
        </div>
      )}

      <div className="panel">
        <h2>LLM usage</h2>
        <table>
          <thead><tr><th>Role</th><th>Provider</th><th>Model</th><th>Tokens</th><th>Cost</th></tr></thead>
          <tbody>
            {usage.length === 0 && <tr><td colSpan={5} className="muted">No LLM calls yet.</td></tr>}
            {usage.map((u, i) => (
              <tr key={i}>
                <td>{u.role}</td>
                <td>{u.provider}</td>
                <td className="mono">{u.model}</td>
                <td className="mono">{u.input_tokens} / {u.output_tokens}</td>
                <td className="mono">${u.cost_usd.toFixed(5)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>FAQ</h2>
        <div className="draft-block">
          <h3>What do rule ID prefixes mean?</h3>
          <table>
            <thead>
              <tr><th>Prefix</th><th>Meaning</th><th>Covers</th></tr>
            </thead>
            <tbody>
              <tr><td className="mono">ACC</td><td>Accuracy</td><td>Product identity, supported claims, evidence excerpts, trusted sources</td></tr>
              <tr><td className="mono">STY</td><td>Style</td><td>UK spelling, banned marketing language, no links / competitor names</td></tr>
              <tr><td className="mono">SEO</td><td>SEO</td><td>Title length, word count, title structure</td></tr>
              <tr><td className="mono">FMT</td><td>Format</td><td>Required output structure (title, overview, features, specs)</td></tr>
              <tr><td className="mono">GEO</td><td>Gap / GEO coverage</td><td>Competitive content gaps addressed</td></tr>
              <tr><td className="mono">CLT</td><td>Client</td><td>Client-specific policy (e.g. allowed SGS site benefits)</td></tr>
            </tbody>
          </table>
          <p className="muted" style={{ marginTop: 8 }}>
            Example: <span className="mono">ACC-003</span> is accuracy rule #3. Prefixes are DynEcom conventions for the compliance report.
          </p>
        </div>
        <div className="draft-block">
          <h3>What do PASS / FAIL / FLAG / SKIP mean?</h3>
          <ul>
            <li><strong>PASS</strong> — rule satisfied (sometimes after auto-correct)</li>
            <li><strong>FAIL</strong> — checked rule not met</li>
            <li><strong>FLAG</strong> — preferred rule not fully met; hold for review</li>
            <li><strong>SKIP</strong> — rule not applicable to this run</li>
          </ul>
        </div>
        <div className="draft-block">
          <h3>When is copy released?</h3>
          <p>
            Only when disposition is <span className="badge released">RELEASE</span> (no mandatory failures).
            {" "}<span className="badge hold">HOLD</span> means preferred issues remain (for example GEO-001).
            {" "}<span className="badge reject">REJECT</span> means mandatory rules failed.
          </p>
        </div>
        <div className="draft-block">
          <h3>What are claim IDs under the draft?</h3>
          <p className="muted" style={{ margin: 0 }}>
            Each draft block should cite verified fact-ledger IDs (e.g. <span className="mono">C001</span>).
            That ties copy back to source excerpts checked by <span className="mono">ACC-002</span> / <span className="mono">ACC-003</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
