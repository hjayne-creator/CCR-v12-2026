export type ModelChoice = { provider: string; model: string };

export type RunSummary = {
  id: number;
  url: string;
  status: string;
  current_stage: number;
  identity_class?: string | null;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  released: boolean;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type RuleDef = {
  rule_id: string;
  description: string;
  priority: "MANDATORY" | "PREFERRED";
  scope: string[];
  validation_method: "CODE" | "LLM" | "HYBRID";
  on_failure: "AUTO_CORRECT" | "TARGETED_REPAIR" | "FLAG" | "FAIL";
  params: Record<string, unknown>;
};

export type ClientRulesPack = {
  client_slug: string;
  version: string;
  hierarchy: string[];
  rules: RuleDef[];
};

export type RulesMeta = {
  scope_options: string[];
  priority_options: string[];
  validation_options: string[];
  on_failure_options: string[];
  prefix_legend: Record<string, string>;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  models: () => req<{ providers: Record<string, Array<{ id: string; label: string; input_per_mtok: number; output_per_mtok: number }>> }>("/api/models"),
  clients: () => req<Array<{ id: number; slug: string; name: string; domain: string; rules_version: string }>>("/api/clients"),
  runs: () => req<RunSummary[]>("/api/runs"),
  createRun: (body: {
    url: string;
    client_slug?: string;
    writer?: ModelChoice;
    qa?: ModelChoice;
    extract?: ModelChoice;
    use_fixtures?: boolean;
  }) => req<RunSummary>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  getRun: (id: number) => req<Record<string, unknown>>(`/api/runs/${id}`),
  getRules: (slug: string) =>
    req<{ pack: ClientRulesPack; style_excerpt: string; meta: RulesMeta }>(`/api/clients/${slug}/rules`),
  saveRules: (slug: string, pack: ClientRulesPack) =>
    req<{ pack: ClientRulesPack; style_excerpt: string; saved: boolean }>(`/api/clients/${slug}/rules`, {
      method: "PUT",
      body: JSON.stringify(pack),
    }),
  saveStyleExcerpt: (slug: string, text: string) =>
    req<{ style_excerpt: string; saved: boolean }>(`/api/clients/${slug}/style-excerpt`, {
      method: "PUT",
      body: JSON.stringify({ text }),
    }),
};
