# LLM Integrations

The LLM functions send Qlik text values to a server-configured backend and return generated text. Azure OpenAI and Foundry are the defaults for existing installations.

## Environment

Azure OpenAI functions require:

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=
AZURE_OPENAI_RESPONSES_BASE_URL=
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

| SSE backend setting | Values | Additional configuration |
| --- | --- | --- |
| `QLIK_LLM_RESPONSES_BACKEND` | `azure_openai`, `openai`, `codex_cli`, `gemini`, `ollama` | Selects the backend for `LLM_Response` and `LLM_Response_Bulk`. |
| `QLIK_LLM_CHAT_BACKEND` | `azure_openai`, `openai` | Selects the backend for `LLM_Chat`, `LLM_Chat_Bulk`, and OpenAI document extraction. |
| `QLIK_LLM_CLAUDE_BACKEND` | `foundry`, `anthropic`, `claude_cli` | Selects the backend for `LLM_Claude_Chat` and its bulk variant. Local document extraction uses a Claude API backend. |

Direct OpenAI uses `OPENAI_API_KEY` and `OPENAI_MODEL`. Direct Anthropic uses `ANTHROPIC_API_KEY` and defaults to the Claude 5.5 family. Set `ANTHROPIC_HAIKU_MODEL`, `ANTHROPIC_SONNET_MODEL` or `ANTHROPIC_OPUS_MODEL` to pin explicit models. For Foundry, set the `AZURE_CLAUDE_*` variables to your deployed names. On a named Foundry deployment where the model rejects sampling parameters, set `QLIK_LLM_CLAUDE_SAMPLING=false`.

Gemini uses `GEMINI_API_KEY` and `GEMINI_MODEL` with Google's stateless `generateContent` API. Ollama uses `OLLAMA_MODEL` and defaults to `OLLAMA_BASE_URL=http://127.0.0.1:11434`. Both accept plain text or `json_schema_b64` for structured output on models that support it.

## Functions

| Function | Qlik use | Parameters | Output |
| --- | --- | --- | --- |
| `LLM_Chat` | Chart expression | prompt, kwargs | text response |
| `LLM_Chat_Bulk` | Load script | key, prompt, kwargs | key, prompt, response |
| `LLM_Claude_Chat` | Chart expression | prompt, kwargs | text response |
| `LLM_Claude_Chat_Bulk` | Load script | key, prompt, kwargs | key, prompt, response |
| `LLM_Response` | Chart expression | prompt, kwargs | Configured backend text or JSON |
| `LLM_Response_Bulk` | Load script | key, prompt, kwargs | key, prompt, response |

## Azure OpenAI Examples

Chart expression:

```qlik
<AAI>.LLM_Chat(
  'Classify this customer comment as Positive, Neutral, or Negative: ' & Comment,
  'system_prompt=Return one label only.,temperature=0,max_tokens=20'
)
```

Load script:

```qlik
PromptInput:
Load
  CustomerID,
  Prompt,
  'system_prompt=Summarize in one sentence.,temperature=0.2,max_tokens=80' as Args
Resident SourceTable;

LLMResponses:
Extension <AAI>.LLM_Chat_Bulk(PromptInput{CustomerID, Prompt, Args});
```

## Responses API

Use `LLM_Response` for the current Azure/OpenAI Responses API, stateful continuation, and strict structured output:

```qlik
<AAI>.LLM_Response(
  'Summarize the current account risk',
  'system_prompt=You are a risk analyst,max_tokens=300,store=false'
)
```

For strict JSON, encode the JSON Schema as base64url and pass it as `json_schema_b64`. Encoding avoids collisions with the comma-delimited SSE kwargs format. The REST façade accepts the schema as a normal JSON object.

Responses-specific kwargs are `previous_response_id`, `store`, `json_schema_name`, and `json_schema_b64`. Temperature is omitted unless explicitly supplied, which keeps reasoning-model deployments compatible.

## Shared Codex CLI pilot

1. Install a Codex CLI with `--ephemeral`, `--ignore-user-config` and `--output-schema` support. On Windows, set `QLIK_LLM_CODEX_BIN` to the absolute path of the native `codex.exe` if the service account cannot find it on its `PATH`.
2. Run `codex login` as the OS identity that runs the SSE service. If setting `QLIK_LLM_CODEX_HOME`, use the same absolute directory as `CODEX_HOME` during login, and restrict directory access to the service identity. Run `codex login status` in that profile.
3. Set `QLIK_LLM_RESPONSES_BACKEND=codex_cli` in the service configuration and restart it. `QLIK_LLM_CODEX_MODEL` can select a model available under the logged-in account. The CLI chooses its default model when the variable is omitted.
4. Test with one chart call and one short reload. The server-side login and quota are shared by all callers of this SSE instance. Validate access and billing for the selected account before using the pilot on a shared production connection.

```qlik
<AAI>.LLM_Response('Return the word READY.', 'max_tokens=50')
```

The backend starts one fresh CLI process per row. Defaults are one concurrent process, eight rows per SSE call and 90 seconds per process. The environment variables `QLIK_LLM_CLI_CONCURRENCY`, `QLIK_LLM_CLI_MAX_ROWS` and `QLIK_LLM_CLI_TIMEOUT_SECONDS` configure those limits. Codex reuses the profile's SQLite state. Set `QLIK_LLM_CODEX_STATE_DIR` to an absolute, private directory to put that state on the service volume, and allow time for the initial backfill if the login profile has existing sessions. The CLI treats `max_tokens` as a prompt hint. `temperature` and continuation requests return row errors. Use `json_schema_b64` for strict JSON. `store=false` is supported and CLI debug logging is disabled. Leave the REST façade configured for its API backend.

An authorized Claude CLI pilot uses `QLIK_LLM_CLAUDE_BACKEND=claude_cli`, the native `claude` executable, and `claude auth login` under the service identity. `QLIK_LLM_CLAUDE_CONFIG_DIR` maps to `CLAUDE_CONFIG_DIR`, and `QLIK_LLM_CLAUDE_BIN` can specify the executable. The shared CLI limits apply here as well. Confirm Anthropic approval before offering subscription usage through this integration.

## Claude Examples

```qlik
<AAI>.LLM_Claude_Chat(
  'Explain the likely business driver behind this movement: ' & TrendText,
  'model=sonnet,system_prompt=You are a concise analytics assistant.,temperature=0.2,max_tokens=300'
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
| `temperature` | Provider default for Responses/Claude | Available on models that support sampling controls |
| `max_tokens` | `2048` | API output-token limit or CLI prompt hint |
| `model` | `sonnet` for Claude | Claude only |
| `debug` | `false` | Writes request and response logs |

## Agent Notes

- Prefer bulk functions in load scripts for repeatable enrichment; avoid chart expressions that call an LLM on every interaction unless the row count is tiny.
- Keep prompts deterministic for classification and data extraction by using `temperature=0`.
- Never send secrets, personal data, or customer-confidential text unless the deployment has been approved for that data class.
- Use short, schema-like prompts when Qlik needs predictable downstream parsing.


### SDK refresh compatibility

The frozen runtime uses OpenAI 3.41 and Anthropic 2.3. Azure Chat Completions
and the separate Azure Responses `/openai/v1/` client retain their configured
deployments and API versions. Claude Foundry requests explicitly retain
`anthropic-version: 2023-06-01`, the [documented Microsoft Foundry contract](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/claude-models).
Anthropic 2 defaults to a newer API and removes the `temperature` Python keyword;
the adapter sends the existing temperature through `extra_body` for that pinned
Foundry contract. This keeps existing Qlik temperature arguments and defaults.
Claude output joins text blocks and skips thinking blocks. Updating the SDK does
not change deployment names, provision models or make paid acceptance calls.
