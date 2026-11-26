Write a structured product detail page draft using ONLY the verified claims provided.

Rules:
- Every overview paragraph, feature, and specification row MUST cite one or more claim_ids from the ledger.
- Do not introduce facts that are not in the verified claims list.
- Follow the style excerpt for tone; rules enforcement is handled separately by code.
- Title: brand + model/size + category + useful verified specs; keep under the title character limit.
- Include site_benefits only from the allowed list when relevant.
- List gaps_addressed using the exact gap strings you covered from the ledger gaps.
- UK English. No outbound URLs.
- Competitor / alternative names may appear ONLY as comparison.table column headers — never in overview, features, FAQs, or site_benefits.
- Do NOT include a customer-facing Sources section. Supporting claim_ids are internal only.

## FAQs (faqs field)

Always include **3 to 6** FAQs (inclusive).

- Derive questions from research inputs in the user payload:
  - `research_gaps` (competitive content gaps)
  - `research_question_seeds` (question-like lines found on subject/competitor pages)
  - verified claims (especially warranty, safety, compatibility, use_case, package_contents, specs)
- Each FAQ must have a clear question and a factual answer supported by verified claim_ids.
- Prefer buyer-decision questions (fit, capacity, clearance, safety, what’s included, warranty, use cases).
- Do not invent specifications. If research raises a question you cannot answer from verified claims, skip it.
- Questions must be distinct (no near-duplicates).
- No competitor/alternative names in FAQ text.
- No URLs or inline citations in FAQ text.

## How it compares (comparison field)

Include `comparison` ONLY when the user payload says `comparison_eligible` is true
(at least min_alternatives **suitable** alternatives that share overlapping verified specs with the subject).
Allowed for both Brand and Reseller identity.

When eligible:
- Build a concise table comparing the subject with the provided `alternatives` (already filtered for suitability).
- `columns`: use **brand + model** short labels.
  - First column: `subject_column_label`
  - Then each alternative's `label` (not the full marketing title)
- Compare only attributes that are material to the purchase decision AND verified for **every** column product.
- Prefer dimensions listed in `overlap_keys` / comparison_rules.attribute_examples when values exist for all products.
- Identify configuration differences plainly; do not normalize or infer missing values.
- **Do not leave empty cells.** If a value is missing for any product, omit that entire row.
- Prefer fewer complete rows over more incomplete ones. If no complete rows are possible, set `comparison` to null.
- Use neutral, factual wording. This is a selection aid, not a promotional comparison.
- No inline citations or URLs in cells; put supporting claim_ids on comparison.claim_ids.
- Optional `choose_if`: one short factual "Choose this if…" line per column (same order as columns).

When NOT eligible (`comparison_eligible` is false):
- Set `comparison` to null. Do not invent alternatives.

Return JSON only matching the PdpDraft schema.
