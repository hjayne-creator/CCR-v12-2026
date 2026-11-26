# Prompt
I've written extensive prompts with very specific instructions for DynEcom clients. What I find is that none of the platforms I've tested (Gemini, Claude, ChatGPT) consistently follow every instruction. Give me a list of strategies I can deploy to expect consistent execution and results.

## Answer (GPT)
The problem you're experiencing is fundamental to how large language models work. LLMs interpret instructions rather than execute them like traditional software. Even the best models can overlook instructions, misinterpret requirements, prioritize competing objectives, or produce different results when given identical prompts.

The problem becomes particularly pronounced with DynEcom because you're combining extensive core prompts, client-specific style guides, competitive research, factual accuracy requirements, SEO, GEO, CRO, and very specific output formatting requirements.

I would change the objective from getting AI to consistently follow instructions to building a system that ensures the final output complies with those instructions.

That distinction is important, particularly when you're generating thousands of product pages without individual human review.

## 1\. Strategies to improve consistent execution

I've ranked these roughly in order of their potential impact on DynEcom's business.

| # | Strategy | Expected impact | Implementation effort |
| --- | --- | --- | --- |
| 1 | Move deterministic instructions from prompts into code | Very high | Medium |
| 2 | Implement independent quality control | Very high | Medium |
| 3 | Break prompts into smaller, specialized tasks | Very high | Medium |
| 4 | Convert style guides into machine-readable rules | Very high | Medium |
| 5 | Separate factual research from content creation | Very high | Medium |
| 6 | Enforce structured outputs | High | Low |
| 7 | Establish a hierarchy of instructions | High | Low |
| 8 | Automatically correct failed instructions | High | Medium |
| 9 | Build a regression testing library | High | Medium |
| 10 | Eliminate conflicting and ambiguous instructions | High | Low |
| 11 | Provide examples of correct and incorrect outputs | High | Low |
| 12 | Use different models for different tasks | Medium–High | Medium |
| 13 | Standardize model versions and settings | Medium | Low |
| 14 | Maintain model-specific prompt variations | Medium | Medium |
| 15 | Consider fine-tuning models | Medium | High |

## 2\. Detailed recommendations

### 1\. Move deterministic instructions from prompts into code

Never ask AI to perform a task that traditional software can perform with certainty.

I suspect a considerable percentage of DynEcom's current instructions could be executed or validated programmatically.

| Instruction | Recommended execution |
| --- | --- |
| Count words | Code |
| Calculate target word count | Code |
| Convert metric to U.S. customary units | Code |
| Enforce character limits | Code |
| Remove non-ASCII characters | Code |
| Arrange CSV columns | Code |
| Verify required fields | Code |
| Generate standard HTML formatting | Code |
| Detect prohibited words | Code |
| Generate schema markup from validated attributes | Code |
| Verify an exact manufacturer part number match | Code where structured identifiers are available |
| Write compelling product descriptions | AI |
| Identify meaningful competitive content gaps | AI |
| Explain product benefits | AI |
| Assess whether a claim is supported by source material | AI + code |

This should simultaneously improve consistency, reduce token consumption and lower your cost per PDP.

### 2\. Implement independent quality control

Don't rely on the AI that wrote the content to determine whether it followed its own instructions.

Create a separate quality control process that receives the completed content, relevant source data and a numbered set of requirements.

Require an individual result for every instruction.

## Sample DynEcom compliance report

Rejected

Illustrative automated PDP quality controlRules evaluated# 10

Passed# 7

Failed# 3

ACC-001

Exact manufacturer part number

PASS

ACC-002

No unsupported product claims

FAIL

ACC-003

Original verified facts retained

PASS

STY-001

Correct units of measure

PASS

STY-002

Client terminology

PASS

STY-003

Prohibited marketing language

PASS

SEO-001

Meta title character limit

FAIL

SEO-002

Required product attributes

PASS

GEO-001

Verified competitive content gaps addressed

FAIL

FMT-001

Required output structure

PASS

Disposition: Return failed fields for targeted correction.

The key is to make the AI demonstrate compliance with evidence rather than simply ask it whether it followed the instructions.

### 3\. Break prompts into smaller, specialized tasks

The more instructions you give an AI simultaneously, the more opportunities there are for failure. Research such as FollowBench has specifically examined the difficulty LLMs experience when accumulating multiple instruction constraints.

ACL Anthology

+1

Rather than providing your entire core prompt and style guide throughout the process, give each AI call only the instructions relevant to its specific assignment.

| Task | Instructions provided |
| --- | --- |
| Product identification | Product matching rules |
| Content extraction | Extraction and source verification rules |
| Competitive analysis | Competitor selection and gap analysis rules |
| Factual reconciliation | Source hierarchy and conflict resolution rules |
| Content writing | Client editorial and content requirements |
| SEO optimization | SEO-specific requirements |
| Quality control | Applicable compliance rules |

Let your platform control the sequence of execution rather than allowing AI to decide which steps to perform and when.

### 4\. Convert style guides into machine-readable rules

I would continue maintaining human-readable client style guides but convert them into structured rules that your platform can execute.

For example, instead of:

> All dimensions must be expressed in U.S. customary units. Fractions should be converted to decimals. Do not include metric dimensions.

Create a configuration like this:

json

```json
{
  "rule_id": "STY-014",
  "description": "Dimension formatting",
  "unit_system": "US_CUSTOMARY",
  "number_format": "DECIMAL",
  "allow_metric": false,
  "priority": "MANDATORY",
  "validation_method": "CODE",
  "on_failure": "AUTO_CORRECT"
}
```

Every instruction should have a unique ID, scope, priority, validation method and action to take upon failure.

This would allow you to build a universal DynEcom processing engine with different configurations for Jameco, Wabash, Design Public, SGS Engineering and future clients.

It would also make changes to a client's style guide much easier to test and deploy.

### 5\. Separate factual research from content creation

Create an intermediate, verified product fact repository before allowing AI to write anything.

Client PDP

Existing content

External sources

Manufacturer and competitors

Extract and reconcile facts

Exact product matching, quotations and source URLs

Verified product fact repository

Approved facts, source references and unresolved conflicts

AI content writer

Uses approved facts and client-specific editorial rules

The writing AI should not be allowed to independently introduce new factual information.

Each fact should have a unique identifier, source URL, supporting quotation, product identifier and verification status. Ideally, generated factual claims should reference those identifiers internally.

For DynEcom, this is one of the most important strategies for reducing hallucinations, unsupported claims and unintended changes to existing product information.

### 6\. Enforce structured outputs

All three major platforms offer API-level structured output capabilities for supported models.

- [OpenAI Structured Outputs](<https://developers.openai.com/api/docs/guides/structured-outputs?utm_source=chatgpt.com>)
- [Claude Structured Outputs](<https://platform.claude.com/docs/en/build-with-claude/structured-outputs?utm_source=chatgpt.com>)
- [Gemini Structured Outputs](<https://ai.google.dev/gemini-api/docs/structured-output?utm_source=chatgpt.com>)

Instead of asking the AI to return a CSV, HTML document or loosely formatted response, define the required output using a JSON schema.

Your platform should then transform that structured data into the client's required format.

Structured outputs can enforce fields, data types and structural requirements. They cannot guarantee that the information within those fields is factually accurate or that every editorial requirement has been met.

OpenAI API

+2

### 7\. Establish a hierarchy of instructions

Not every instruction should be treated equally. Your prompts should explicitly establish which rules take precedence when they conflict.

For DynEcom, I would recommend the following hierarchy:

1

Factual accuracy

Never introduce unsupported information.

2

Data integrity

Preserve existing verified information.

3

Mandatory client requirements

Units, terminology and content restrictions.

4

Content completeness

Address verified competitive content gaps.

5

SEO, GEO and CRO

Optimize content for discovery and conversion.

6

Editorial preferences

Tone, sentence structure and writing style.

For example, a word count requirement should never cause the AI to invent additional product information.

Your platform should also identify conflicting rules before sending them to the model.

### 8\. Automatically correct failed instructions

Don't simply identify instruction violations. Build a process to correct them.

If the AI correctly followed 47 of 50 instructions, don't regenerate the entire PDP. Return only the three failed instructions, relevant content and supporting evidence for correction.

Lock the portions that passed quality control, then revalidate the complete output after the corrections.

Establish a maximum number of correction attempts. If the content continues to fail, escalate it to a more capable model or put it in an exception queue.

Anthropic describes a similar evaluator-optimizer architecture in its recommendations for building reliable AI workflows.

Anthropic

+1

### 9\. Build a regression testing library

Create a library of perhaps 50–100 representative PDPs that have been manually reviewed and approved.

These should include products with missing attributes, conflicting specifications, similar part numbers, extensive technical information, limited competitive information and complex client requirements.

Whenever you change a prompt, style guide, model or processing step, run the same products through your platform multiple times and measure the results against your approved data and rules.

Track the following KPIs:

| KPI | Suggested initial target |
| --- | --- |
| Exact product matching accuracy | 100% |
| Mandatory formatting compliance | 100% |
| Unsupported factual claims | 0% |
| Verified factual information retained | 100% |
| Verified competitive gaps addressed | 100% or documented exception |
| First-pass mandatory rule compliance | 95%+ |
| Final mandatory rule compliance | 100% of evaluated rules |
| AI cost per PDP | ≤ $0.10 average |

These are proposed engineering targets, not measured results or guarantees of undetected factual accuracy.

This also gives you a much more objective way to compare Gemini, Claude and ChatGPT. OpenAI recommends evaluation-driven development to measure the effect of prompt and model changes.

OpenAI API

+1

### 10\. Eliminate conflicting and ambiguous instructions

Have your core prompts and client style guides audited specifically for ambiguity, redundancy and contradictions.

| Ambiguous instruction | More precise instruction |
| --- | --- |
| Be concise but comprehensive. | Include all verified product attributes without repeating information unnecessarily. |
| Write compelling marketing copy. | Explain verified benefits without introducing subjective or unsupported claims. |
| Include relevant FAQs. | Include FAQs that address documented customer questions or verified information gaps. |
| Preserve original content. | Preserve all verified factual information, but allow changes to wording. |
| Never infer anything. | Do not introduce any factual claim that cannot be supported by approved source material. |

The goal isn't necessarily shorter prompts. It's fewer opportunities for interpretation.

### 11\. Provide examples of correct and incorrect outputs

AI models often respond better to concrete examples than abstract editorial instructions.

For example, when instructing an AI to avoid unsupported marketing language:

Incorrect

This industry-leading power supply delivers exceptional performance and unparalleled reliability.

Correct

This enclosed power supply delivers 24 VDC output and includes short-circuit protection.

Illustrative example assuming these specifications have been verified.

Build a small library of examples specific to each client's most frequently violated rules. Provide those examples only when relevant to the current task.

### 12\. Use different models for different tasks

I wouldn't try to identify one model that is universally superior for DynEcom.

Instead, identify the best-performing, most economical model for each task.

| Task | Recommended model strategy |
| --- | --- |
| Simple data extraction | Low-cost model |
| Attribute classification | Low-cost model |
| Competitor product selection | Strong reasoning model |
| Technical conflict resolution | Strong reasoning model |
| Content writing | Best tested editorial model |
| Factual quality control | Independently evaluated model |
| Formatting | Traditional code |
| Failed quality control | Targeted correction or premium model escalation |

Using a different model provider for quality control may also help identify errors the original model overlooked, although different models can still make the same mistakes.

### 13\. Standardize model versions and settings

For production execution, use APIs rather than consumer chatbot interfaces.

Pin model versions where supported, standardize reasoning effort and output limits, control the context supplied, and test sampling settings for consistency.

Lower temperature can reduce variability on models that support it, but it does not guarantee identical or more accurate outputs.

Record the model version, prompt version, client style guide version, source data snapshot and execution settings for every PDP. This gives you a record of exactly how each output was produced.

### 14\. Maintain model-specific prompt variations

I would maintain one universal master set of DynEcom requirements but allow different implementations for Gemini, Claude and ChatGPT.

The models have different strengths, weaknesses and sensitivities to prompt structures.

Your requirements should remain identical. The language, arrangement and examples used to communicate those requirements can vary by model.

Use regression testing to determine whether a model-specific variation actually improves compliance before maintaining it.

### 15\. Consider fine-tuning models

Once you've accumulated hundreds or thousands of validated product descriptions, you may have a valuable proprietary training dataset.

Fine-tuning could potentially improve editorial consistency, terminology, content structure and adherence to recurring writing patterns. It may also allow you to accomplish certain tasks using smaller, less expensive models.

However, I would pursue this last. Fine-tuning does not eliminate the need for factual verification, deterministic validation or quality control.

## 3\. My recommended DynEcom architecture

I would move away from a predominantly prompt-driven system toward a rules-driven content production system that uses AI for specific functions.

AI performs interpretation and writing. Traditional software controls execution, validation and release.

## 4\. Why even excellent instruction following isn't enough

Consider a hypothetical PDP with 50 mandatory instructions. Assume each instruction has the same probability of being followed correctly and that failures are independent.

Even very high individual instruction compliance can translate into surprisingly low overall PDP compliance.

### Instruction compliance calculator

Number of instructions## 50

Accuracy per instruction## 99.0%

PDPs following every instruction# 60.5%

PDPs with at least one error# 39.5%

Expected results per 10,000 PDPs6,050 fully compliant

3,950 with errors

Illustrative mathematical model assuming independent failures, not actual measured LLM performance. Adjust the sliders to explore different scenarios.

This illustrates why simply switching to a better model is unlikely to solve your problem.

## 5\. Where I would invest first

Given DynEcom's need to scale to thousands of PDPs while simultaneously reducing AI costs to approximately $0.10 per product, I would prioritize the following investments.

| Priority | Investment | Consistency improvement | Cost reduction potential |
| --- | --- | --- | --- |
| 1 | Programmatic rules and validation engine | Very high | High |
| 2 | Machine-readable client style guides | Very high | High |
| 3 | Specialized, smaller prompts | Very high | High |
| 4 | Verified product fact repository | Very high | Medium |
| 5 | Independent quality control | Very high | May increase cost |
| 6 | Targeted corrections instead of full regeneration | High | High |
| 7 | Automated regression testing | High | Medium |
| 8 | Model selection by task | High | High |

These priorities are based on my understanding of DynEcom's existing architecture and objectives, rather than a fresh line-by-line audit of your latest prompts or source code. The actual cost and compliance improvements would need to be measured.

## 6\. The most important philosophical change

I would establish five fundamental engineering principles for DynEcom:

If code can do it, don't use AI.

If AI does it, independently verify it.

If verification fails, correct only what failed.

If accuracy cannot be established, flag it rather than guess.

If a mandatory requirement hasn't passed validation, don't release the content.

Your extensive prompts and client style guides remain valuable. In fact, they represent a significant piece of DynEcom's intellectual property. I would repurpose much of that intellectual property into a proprietary rules, execution and validation engine.

That would make DynEcom less dependent on any individual AI provider, more adaptable as new models emerge, more cost-efficient and considerably more reliable at scale.

