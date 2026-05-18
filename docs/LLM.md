# LLM Integrations

The LLM functions send Qlik text values to configured Azure-hosted models and return generated text. Use them for controlled enrichment, classification, summarization, explanations, and scripted batch generation.

## Environment

Azure OpenAI functions require:

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=
```

Azure AI Foundry Claude functions require:

```env
AZURE_FOUNDRY_API_KEY=
AZURE_FOUNDRY_API_VERSION=
AZURE_FOUNDRY_CLAUDE_API_ENDPOINT=
AZURE_CLAUDE_HAIKU=
AZURE_CLAUDE_OPUS=
AZURE_CLAUDE_SONNET=
```

## Functions

| Function | Qlik use | Parameters | Output |
| --- | --- | --- | --- |
| `LLM_Chat` | Chart expression | prompt, kwargs | text response |
| `LLM_Chat_Bulk` | Load script | key, prompt, kwargs | key, prompt, response |
| `LLM_Claude_Chat` | Chart expression | prompt, kwargs | text response |
| `LLM_Claude_Chat_Bulk` | Load script | key, prompt, kwargs | key, prompt, response |

## Azure OpenAI Examples

Chart expression:

```qlik
<AAI>.LLM_Chat(
  'Classify this customer comment as Positive, Neutral, or Negative: ' & Comment,
  'system_prompt=Return one label only.|temperature=0|max_tokens=20'
)
```

Load script:

```qlik
PromptInput:
Load
  CustomerID,
  Prompt,
  'system_prompt=Summarize in one sentence.|temperature=0.2|max_tokens=80' as Args
Resident SourceTable;

LLMResponses:
Extension <AAI>.LLM_Chat_Bulk(PromptInput{CustomerID, Prompt, Args});
```

## Claude Examples

```qlik
<AAI>.LLM_Claude_Chat(
  'Explain the likely business driver behind this movement: ' & TrendText,
  'model=sonnet|system_prompt=You are a concise analytics assistant.|temperature=0.2|max_tokens=300'
)
```

Claude model aliases:

| Alias | Environment variable |
| --- | --- |
| `haiku` | `AZURE_CLAUDE_HAIKU` |
| `sonnet` | `AZURE_CLAUDE_SONNET` |
| `opus` | `AZURE_CLAUDE_OPUS` |

A full model name may be passed with `model=<name>` when an alias is not enough.

## Keyword Arguments

| Argument | Default | Notes |
| --- | --- | --- |
| `system_prompt` | none | System/developer instruction for the model |
| `temperature` | `0.7` | Lower values are more deterministic |
| `max_tokens` | `2048` | Maximum response tokens |
| `model` | `sonnet` for Claude | Claude only |
| `debug` | `false` | Writes request and response logs |

## Agent Notes

- Prefer bulk functions in load scripts for repeatable enrichment; avoid chart expressions that call an LLM on every interaction unless the row count is tiny.
- Keep prompts deterministic for classification and data extraction by using `temperature=0`.
- Never send secrets, personal data, or customer-confidential text unless the deployment has been approved for that data class.
- Use short, schema-like prompts when Qlik needs predictable downstream parsing.
