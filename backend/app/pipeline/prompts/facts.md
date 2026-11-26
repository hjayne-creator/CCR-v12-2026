Extract a verified fact ledger from the supplied source texts.

Rules:
- Every claim MUST include at least one evidence object with a verbatim excerpt copied from a source.
- Prefer specifications, features, package contents, warranty, and safety facts.
- Mark status VERIFIED only when the excerpt is literally present in the cited source.
- List competitive content gaps (facts competitors mention that the subject page lacks) in gaps[].
- Do not invent numbers, certifications, or capabilities.
- Use claim_id values like C001, C002, …

Return JSON only.
