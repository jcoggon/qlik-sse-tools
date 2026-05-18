# Firecrawl Web And Document Functions

The Firecrawl functions let Qlik scrape web pages, parse local documents, search the web, extract structured data, and run Firecrawl Agent tasks. They are intended for controlled data acquisition and enrichment workflows.

## Environment

Remote Firecrawl operations require:

```env
FIRECRAWL_API_KEY=
```

Local file parsing does not require the Firecrawl API key when using supported local file types.

## Functions

| Function | Qlik use | Parameters | Output |
| --- | --- | --- | --- |
| `Firecrawl_Scrape` | Chart expression | source, kwargs | text/markdown/html/json string |
| `Firecrawl_Scrape_Bulk` | Load script | key, source, kwargs | key, source, content |
| `Firecrawl_Extract` | Chart expression | source, prompt, kwargs | JSON/text string |
| `Firecrawl_Extract_Bulk` | Load script | key, source, prompt, kwargs | key, source, prompt, extracted |
| `Firecrawl_Search` | Chart expression | query, kwargs | JSON string |
| `Firecrawl_Search_Bulk` | Load script | key, query, kwargs | key, query, results |
| `Firecrawl_Agent` | Chart expression | source, prompt, kwargs | JSON string |
| `Firecrawl_Agent_Bulk` | Load script | key, source, prompt, kwargs | key, source, prompt, result |

`source` may be an `http://` or `https://` URL. For scrape and extract, it may also be a local file path.

## Local File Parsing

Supported local file types:

| Type | Notes |
| --- | --- |
| PDF | Extracts page text; `pdf_mode` and `pdf_max_pages` can control parsing where supported |
| Excel | Converts workbook sheets to Markdown-style content |
| Word | Extracts paragraphs and tables from `.docx` |
| CSV | Converts rows to a Markdown table |
| Text | Reads plain text directly |

## Scrape Examples

```qlik
<AAI>.Firecrawl_Scrape('https://example.com/pricing', 'format=markdown|only_main_content=true')
```

```qlik
<AAI>.Firecrawl_Scrape('C:\Data\catalogue.pdf', 'format=markdown|pdf_max_pages=20')
```

## Extract Examples

```qlik
<AAI>.Firecrawl_Extract(
  'https://example.com/products',
  'Extract product name, brand, size, price, and currency as JSON.',
  'enable_web_search=false'
)
```

```qlik
<AAI>.Firecrawl_Extract(
  'C:\Data\catalogue.pdf',
  'Extract every tyre product and price as JSON.',
  'llm_provider=openai|schema={"type":"object"}'
)
```

## Search And Agent Examples

```qlik
<AAI>.Firecrawl_Search('commercial tyre suppliers South Africa pricing', 'limit=5|scrape_content=true')
```

```qlik
<AAI>.Firecrawl_Agent(
  'https://example.com',
  'Find product names, sizes, and prices. Return JSON only.',
  'model=spark-1-mini|max_credits=100'
)
```

## Keyword Arguments

| Argument | Applies to | Notes |
| --- | --- | --- |
| `format` | scrape | `markdown`, `html`, or `json` |
| `only_main_content` | scrape | Boolean for remote page scraping |
| `timeout` | scrape/extract/search/agent | Timeout value where supported |
| `pdf_mode` | local PDF / remote PDF | OCR or parser mode where supported |
| `pdf_max_pages` | local PDF | Limit pages parsed |
| `schema` | extract/agent | JSON schema string for structured extraction |
| `enable_web_search` | extract | Allow web search during extraction |
| `llm_provider` | local extract | LLM provider for local extraction |
| `limit` | search | Number of search results |
| `location` | search | Search location hint |
| `tbs` | search | Search time filter |
| `scrape_content` | search | Include scraped page content in search result |
| `model` | agent | Firecrawl Agent model |
| `max_credits` | agent | Credit budget |
| `debug` | all | Writes detailed logs |

## Agent Notes

- Use scrape when the desired output is page or document content.
- Use extract when the desired output is a structured answer from a known source.
- Use search when the source is unknown.
- Use agent when a task needs navigation or multi-step research.
- Prefer bulk functions for scheduled reload workflows.
- Always validate the legal and operational approval for scraping third-party sites.
