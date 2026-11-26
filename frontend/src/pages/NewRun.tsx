import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

type ProviderCatalog = Record<
  string,
  Array<{ id: string; label: string; input_per_mtok: number; output_per_mtok: number }>
>;

const DEFAULT_URL =
  "https://www.sgs-engineering.com/sgs-3-ton-low-profile-trolley-jack";

export default function NewRun() {
  const nav = useNavigate();
  const [providers, setProviders] = useState<ProviderCatalog>({});
  const [url, setUrl] = useState(DEFAULT_URL);
  const [writerProvider, setWriterProvider] = useState("anthropic");
  const [writerModel, setWriterModel] = useState("claude-sonnet-5-5");
  const [qaProvider, setQaProvider] = useState("openai");
  const [qaModel, setQaModel] = useState("gpt-6.1-terra");
  const [extractProvider, setExtractProvider] = useState("openai");
  const [extractModel, setExtractModel] = useState("gpt-6-luna");
  const [useFixtures, setUseFixtures] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.models().then((m) => setProviders(m.providers)).catch((e) => setError(String(e)));
  }, []);

  const writerModels = useMemo(() => providers[writerProvider] || [], [providers, writerProvider]);
  const qaModels = useMemo(() => providers[qaProvider] || [], [providers, qaProvider]);
  const extractModels = useMemo(() => providers[extractProvider] || [], [providers, extractProvider]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await api.createRun({
        url,
        client_slug: "sgs-engineering",
        writer: { provider: writerProvider, model: writerModel },
        qa: { provider: qaProvider, model: qaModel },
        extract: { provider: extractProvider, model: extractModel },
        use_fixtures: useFixtures,
      });
      nav(`/runs/${run.id}`);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  function priceNote(provider: string, model: string) {
    const m = (providers[provider] || []).find((x) => x.id === model);
    if (!m) return null;
    return (
      <div className="muted mono" style={{ marginTop: 4 }}>
        ${m.input_per_mtok.toFixed(2)} / ${m.output_per_mtok.toFixed(2)} per 1M tokens
      </div>
    );
  }

  return (
    <div>
      <h1>New run</h1>
      <p className="lede">
        SGS Engineering only. Code owns scrape, validation, and release; models handle research, facts, and writing.
      </p>
      <form className="panel" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="url">Subject PDP URL</label>
          <input id="url" value={url} onChange={(e) => setUrl(e.target.value)} required />
        </div>

        <div className="row">
          <div className="field">
            <label>Writer provider</label>
            <select
              value={writerProvider}
              onChange={(e) => {
                setWriterProvider(e.target.value);
                const first = providers[e.target.value]?.[0]?.id;
                if (first) setWriterModel(first);
              }}
            >
              {Object.keys(providers).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Writer model</label>
            <select value={writerModel} onChange={(e) => setWriterModel(e.target.value)}>
              {writerModels.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            {priceNote(writerProvider, writerModel)}
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>QA provider</label>
            <select
              value={qaProvider}
              onChange={(e) => {
                setQaProvider(e.target.value);
                const first = providers[e.target.value]?.[0]?.id;
                if (first) setQaModel(first);
              }}
            >
              {Object.keys(providers).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>QA model</label>
            <select value={qaModel} onChange={(e) => setQaModel(e.target.value)}>
              {qaModels.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            {priceNote(qaProvider, qaModel)}
          </div>
        </div>

        <div className="row">
          <div className="field">
            <label>Extract / research provider</label>
            <select
              value={extractProvider}
              onChange={(e) => {
                setExtractProvider(e.target.value);
                const first = providers[e.target.value]?.[0]?.id;
                if (first) setExtractModel(first);
              }}
            >
              {Object.keys(providers).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Extract model</label>
            <select value={extractModel} onChange={(e) => setExtractModel(e.target.value)}>
              {extractModels.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            {priceNote(extractProvider, extractModel)}
          </div>
        </div>

        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={useFixtures}
              onChange={(e) => setUseFixtures(e.target.checked)}
              style={{ width: "auto", marginRight: 8 }}
            />
            Use offline fixtures (no live Firecrawl/search)
          </label>
        </div>

        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Starting…" : "Start run"}</button>
      </form>
    </div>
  );
}
