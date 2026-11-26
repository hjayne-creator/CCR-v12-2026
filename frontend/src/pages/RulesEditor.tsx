import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, ClientRulesPack, RuleDef, RulesMeta } from "../api";

const EMPTY_RULE = (): RuleDef => ({
  rule_id: "",
  description: "",
  priority: "MANDATORY",
  scope: ["qc"],
  validation_method: "CODE",
  on_failure: "FAIL",
  params: {},
});

export default function RulesEditor() {
  const [slug, setSlug] = useState("sgs-engineering");
  const [clients, setClients] = useState<Array<{ slug: string; name: string }>>([]);
  const [pack, setPack] = useState<ClientRulesPack | null>(null);
  const [styleExcerpt, setStyleExcerpt] = useState("");
  const [meta, setMeta] = useState<RulesMeta | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [rawMode, setRawMode] = useState(false);
  const [rawJson, setRawJson] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load(nextSlug = slug) {
    setError(null);
    setMessage(null);
    try {
      const data = await api.getRules(nextSlug);
      setPack(data.pack);
      setStyleExcerpt(data.style_excerpt || "");
      setMeta(data.meta);
      setRawJson(JSON.stringify(data.pack, null, 2));
      if (!expanded && data.pack.rules[0]) setExpanded(data.pack.rules[0].rule_id);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    let alive = true;
    api.clients()
      .then((c) => { if (alive) setClients(c.map((x) => ({ slug: x.slug, name: x.name }))); })
      .catch(() => undefined);
    api.getRules("sgs-engineering")
      .then((data) => {
        if (!alive) return;
        setPack(data.pack);
        setStyleExcerpt(data.style_excerpt || "");
        setMeta(data.meta);
        setRawJson(JSON.stringify(data.pack, null, 2));
        if (data.pack.rules[0]) setExpanded(data.pack.rules[0].rule_id);
      })
      .catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, []);

  const prefixHint = useMemo(() => {
    if (!meta || !expanded) return null;
    const prefix = expanded.split("-")[0];
    return meta.prefix_legend[prefix] || null;
  }, [meta, expanded]);

  function updateRule(index: number, patch: Partial<RuleDef>) {
    if (!pack) return;
    const rules = pack.rules.map((r, i) => (i === index ? { ...r, ...patch } : r));
    setPack({ ...pack, rules });
  }

  function toggleScope(index: number, scope: string) {
    if (!pack) return;
    const rule = pack.rules[index];
    const has = rule.scope.includes(scope);
    const scopeNext = has ? rule.scope.filter((s) => s !== scope) : [...rule.scope, scope];
    updateRule(index, { scope: scopeNext });
  }

  function updateParamsJson(index: number, text: string) {
    try {
      const parsed = text.trim() ? JSON.parse(text) : {};
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("params must be a JSON object");
      }
      updateRule(index, { params: parsed });
      setError(null);
    } catch (e) {
      setError(`Params JSON for rule #${index + 1}: ${String(e)}`);
    }
  }

  function addRule() {
    if (!pack) return;
    const rule = EMPTY_RULE();
    rule.rule_id = `NEW-${String(pack.rules.length + 1).padStart(3, "0")}`;
    setPack({ ...pack, rules: [...pack.rules, rule] });
    setExpanded(rule.rule_id);
  }

  function removeRule(index: number) {
    if (!pack) return;
    const removed = pack.rules[index]?.rule_id;
    const rules = pack.rules.filter((_, i) => i !== index);
    setPack({ ...pack, rules });
    if (expanded === removed) setExpanded(rules[0]?.rule_id || null);
  }

  async function onSaveRules(e: FormEvent) {
    e.preventDefault();
    if (!pack && !rawMode) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      let body: ClientRulesPack;
      if (rawMode) {
        body = JSON.parse(rawJson) as ClientRulesPack;
      } else {
        body = pack!;
      }
      const saved = await api.saveRules(slug, body);
      setPack(saved.pack);
      setRawJson(JSON.stringify(saved.pack, null, 2));
      setMessage(`Saved rules v${saved.pack.version} (${saved.pack.rules.length} rules). New runs will use this pack.`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSaveStyle(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await api.saveStyleExcerpt(slug, styleExcerpt);
      setStyleExcerpt(saved.style_excerpt);
      setMessage("Saved style excerpt.");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Rules</h1>
      <p className="lede">
        Edit machine-readable client rules. Changes write to disk and apply to new runs immediately.
      </p>

      <div className="panel">
        <div className="row">
          <div className="field">
            <label htmlFor="client">Client</label>
            <select
              id="client"
              value={slug}
              onChange={(e) => {
                const next = e.target.value;
                setSlug(next);
                load(next);
              }}
            >
              {(clients.length ? clients : [{ slug: "sgs-engineering", name: "SGS Engineering" }]).map((c) => (
                <option key={c.slug} value={c.slug}>{c.name} ({c.slug})</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Editor mode</label>
            <div style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 42 }}>
              <button type="button" className={!rawMode ? "" : "secondary"} onClick={() => setRawMode(false)}>Form</button>
              <button
                type="button"
                className={rawMode ? "" : "secondary"}
                onClick={() => {
                  if (pack) setRawJson(JSON.stringify(pack, null, 2));
                  setRawMode(true);
                }}
              >
                Raw JSON
              </button>
            </div>
          </div>
        </div>
        {meta && (
          <p className="muted" style={{ margin: 0 }}>
            Prefixes: {Object.entries(meta.prefix_legend).map(([k, v]) => (
              <span key={k} style={{ marginRight: 12 }}><span className="mono">{k}</span> {v.split("—")[0].trim()}</span>
            ))}
          </p>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {message && <p className="muted">{message}</p>}

      {!pack && !error && <p className="muted">Loading…</p>}

      {pack && !rawMode && (
        <form className="panel" onSubmit={onSaveRules}>
          <div className="row">
            <div className="field">
              <label>Version</label>
              <input value={pack.version} onChange={(e) => setPack({ ...pack, version: e.target.value })} />
            </div>
            <div className="field">
              <label>Client slug (locked to path)</label>
              <input value={pack.client_slug} readOnly />
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Rules ({pack.rules.length})</h2>
            <button type="button" className="secondary" onClick={addRule}>Add rule</button>
          </div>

          {pack.rules.map((rule, index) => {
            const open = expanded === rule.rule_id || expanded === `idx-${index}`;
            return (
              <div key={`${rule.rule_id}-${index}`} className="rule-card">
                <button
                  type="button"
                  className="rule-card-head"
                  onClick={() => setExpanded(open ? null : (rule.rule_id || `idx-${index}`))}
                >
                  <span className="mono">{rule.rule_id || "(new)"}</span>
                  <span className={`badge ${rule.priority === "MANDATORY" ? "fail" : "flag"}`}>{rule.priority}</span>
                  <span className="muted" style={{ flex: 1, textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {rule.description}
                  </span>
                  <span className="muted">{open ? "▾" : "▸"}</span>
                </button>
                {open && (
                  <div className="rule-card-body">
                    {prefixHint && expanded === rule.rule_id && (
                      <p className="muted" style={{ marginTop: 0 }}>{prefixHint}</p>
                    )}
                    <div className="row">
                      <div className="field">
                        <label>Rule ID</label>
                        <input
                          className="mono"
                          value={rule.rule_id}
                          onChange={(e) => {
                            updateRule(index, { rule_id: e.target.value });
                            setExpanded(e.target.value || `idx-${index}`);
                          }}
                          required
                        />
                      </div>
                      <div className="field">
                        <label>Priority</label>
                        <select
                          value={rule.priority}
                          onChange={(e) => updateRule(index, { priority: e.target.value as RuleDef["priority"] })}
                        >
                          {(meta?.priority_options || ["MANDATORY", "PREFERRED"]).map((p) => (
                            <option key={p} value={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="field">
                      <label>Description</label>
                      <textarea
                        rows={2}
                        value={rule.description}
                        onChange={(e) => updateRule(index, { description: e.target.value })}
                        required
                      />
                    </div>
                    <div className="row">
                      <div className="field">
                        <label>Validation</label>
                        <select
                          value={rule.validation_method}
                          onChange={(e) => updateRule(index, { validation_method: e.target.value as RuleDef["validation_method"] })}
                        >
                          {(meta?.validation_options || ["CODE", "LLM", "HYBRID"]).map((p) => (
                            <option key={p} value={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label>On failure</label>
                        <select
                          value={rule.on_failure}
                          onChange={(e) => updateRule(index, { on_failure: e.target.value as RuleDef["on_failure"] })}
                        >
                          {(meta?.on_failure_options || ["FAIL", "FLAG", "AUTO_CORRECT", "TARGETED_REPAIR"]).map((p) => (
                            <option key={p} value={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="field">
                      <label>Scope</label>
                      <div className="scope-grid">
                        {(meta?.scope_options || []).map((s) => (
                          <label key={s} className="scope-chip">
                            <input
                              type="checkbox"
                              checked={rule.scope.includes(s)}
                              onChange={() => toggleScope(index, s)}
                            />
                            {s}
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="field">
                      <label>Params (JSON object)</label>
                      <textarea
                        className="mono"
                        rows={5}
                        defaultValue={JSON.stringify(rule.params || {}, null, 2)}
                        key={`params-${rule.rule_id}-${index}`}
                        onBlur={(e) => updateParamsJson(index, e.target.value)}
                      />
                    </div>
                    <button type="button" className="secondary" onClick={() => removeRule(index)}>Remove rule</button>
                  </div>
                )}
              </div>
            );
          })}

          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save rules"}</button>
            <button type="button" className="secondary" onClick={() => load(slug)} disabled={busy}>Reload</button>
          </div>
        </form>
      )}

      {rawMode && (
        <form className="panel" onSubmit={onSaveRules}>
          <label>Raw rules.json</label>
          <textarea
            className="mono"
            rows={24}
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
            style={{ marginTop: 8 }}
          />
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save raw JSON"}</button>
            <button type="button" className="secondary" onClick={() => load(slug)} disabled={busy}>Reload</button>
          </div>
        </form>
      )}

      <form className="panel" onSubmit={onSaveStyle}>
        <h2 style={{ marginTop: 0 }}>Style excerpt</h2>
        <p className="muted">Tone guidance for the writer only — not enforced like rules.json.</p>
        <textarea rows={10} value={styleExcerpt} onChange={(e) => setStyleExcerpt(e.target.value)} />
        <div style={{ marginTop: 12 }}>
          <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save style excerpt"}</button>
        </div>
      </form>
    </div>
  );
}
