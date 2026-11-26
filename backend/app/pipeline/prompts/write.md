Write a structured product detail page draft using ONLY the verified claims provided.

Rules:
- Every overview paragraph, feature, and specification row MUST cite one or more claim_ids from the ledger.
- Do not introduce facts that are not in the verified claims list.
- Follow the style excerpt for tone; rules enforcement is handled separately by code.
- Title: brand + model/size + category + useful verified specs; keep under the title character limit.
- Include site_benefits only from the allowed list when relevant.
- List gaps_addressed using the exact gap strings you covered from the ledger gaps.
- UK English. No competitor names. No URLs.

Return JSON only matching the PdpDraft schema.
