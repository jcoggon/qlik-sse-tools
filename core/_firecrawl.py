import os
import sys
import json
import time
import warnings
import numpy as np
import pandas as pd

# Suppress warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore")

from firecrawl import Firecrawl

import _utils as utils
import ServerSideExtension_pb2 as SSE

# Add Generated folder to module path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PARENT_DIR, 'generated'))

# Optional local file parsing imports
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    import docx as python_docx
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# LLM providers for local file extraction
_LLM_PROVIDERS = {
    'openai': 'openai',
    'claude': 'claude',
}


class FirecrawlForQlik:
    """
    A class to provide Firecrawl web scraping, document parsing, and structured data
    extraction capabilities for Qlik. Supports remote URLs (via Firecrawl API) and
    local files (PDF, Excel, Word, CSV/TXT parsed locally).
    """

    # Counter used to name log files for instances of the class
    log_no = 0

    def __init__(self, request, context):
        """
        Class initializer.
        :param request: an iterable sequence of RowData
        :param context:
        :Sets up the input data frame and parameters based on the request
        """

        # Set the request and context variables for this object instance
        self.request = request
        self.context = context
        self.logfile = None
        self.debug = False

        # Initialize the Firecrawl client from environment variable
        api_key = os.environ.get("FIRECRAWL_API_KEY")
        if api_key:
            self.client = Firecrawl(api_key=api_key)
        else:
            self.client = None

    def scrape(self, load_script=False):
        """
        Scrape a URL or parse a local file and return the content as markdown/text.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.Firecrawl_Scrape('https://competitor.com/pricing', 'format=markdown')
        :<AAI Connection Name>.Firecrawl_Scrape('https://competitor.com/catalogue.pdf', 'format=markdown,pdf_mode=ocr')
        :<AAI Connection Name>.Firecrawl_Scrape('/data/local_file.pdf', 'format=markdown')
        """

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['key', 'source', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData']
            col_headers = ['source', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each source and get content
        responses = []

        for i in self.request_df.index:
            source = self.request_df.loc[i, 'source']

            try:
                if self._is_url(source):
                    content = self._scrape_url(source)
                else:
                    content = self._parse_local_file(source)
            except Exception as e:
                content = "Error: {}".format(str(e))
                if self.debug:
                    self._print_exception("Scrape failed for: {}".format(source), e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], source, content))
            else:
                responses.append(content)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'source', 'content'])

            # Send the response table description to Qlik
            self._send_table_description("scrape_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    def extract(self, load_script=False):
        """
        Extract structured data from a URL or local file using a natural language prompt.
        Returns the extracted data as a JSON string.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.Firecrawl_Extract('https://competitor.com/tyres', 'Extract all tyre names and prices', 'enable_web_search=true')
        :<AAI Connection Name>.Firecrawl_Extract('/data/catalogue.pdf', 'Extract product names and prices', 'llm_provider=openai')
        """

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData', 'strData']
            col_headers = ['key', 'source', 'prompt', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['source', 'prompt', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each source and extract data
        responses = []

        for i in self.request_df.index:
            source = self.request_df.loc[i, 'source']
            prompt = self.request_df.loc[i, 'prompt']

            try:
                if self._is_url(source):
                    extracted = self._extract_from_url(source, prompt)
                else:
                    extracted = self._extract_from_local(source, prompt)
            except Exception as e:
                extracted = json.dumps({"error": str(e)})
                if self.debug:
                    self._print_exception("Extract failed for: {}".format(source), e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], source, extracted))
            else:
                responses.append(extracted)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'source', 'extracted'])

            # Send the response table description to Qlik
            self._send_table_description("extract_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    def search(self, load_script=False):
        """
        Search the web using Firecrawl and return results.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.Firecrawl_Search('auto truck tyre pricing South Africa', 'limit=5')
        """

        if not self.client:
            raise RuntimeError("Firecrawl API key not configured. Set FIRECRAWL_API_KEY in .env")

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['key', 'query', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData']
            col_headers = ['query', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each query and get results
        responses = []

        for i in self.request_df.index:
            query = self.request_df.loc[i, 'query']

            try:
                result_text = self._search_web(query)
            except Exception as e:
                result_text = "Error: {}".format(str(e))
                if self.debug:
                    self._print_exception("Search failed for: {}".format(query), e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], query, result_text))
            else:
                responses.append(result_text)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'query', 'results'])

            # Send the response table description to Qlik
            self._send_table_description("search_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    def agent(self, load_script=False):
        """
        Run a Firecrawl Agent task to autonomously research and extract data.
        The agent searches, navigates, and gathers data from websites.
        Optionally provide a URL to focus the agent on a specific site.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.Firecrawl_Agent('https://competitor.com', 'Find all tyre product names, brands, sizes, and prices', 'model=spark-2|max_credits=100')
        :<AAI Connection Name>.Firecrawl_Agent('', 'Find truck tyre pricing from South African retailers', 'model=spark-2|max_credits=500')
        """

        if not self.client:
            raise RuntimeError("Firecrawl API key not configured. Set FIRECRAWL_API_KEY in .env")

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData', 'strData']
            col_headers = ['key', 'source', 'prompt', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['source', 'prompt', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each agent task
        responses = []

        for i in self.request_df.index:
            source = self.request_df.loc[i, 'source']
            prompt = self.request_df.loc[i, 'prompt']

            try:
                result = self._run_agent(source, prompt)
            except Exception as e:
                result = json.dumps({"error": str(e)})
                if self.debug:
                    self._print_exception("Agent failed for: {}".format(prompt[:50]), e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], source, result))
            else:
                responses.append(result)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'source', 'result'])

            # Send the response table description to Qlik
            self._send_table_description("agent_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    # =========================================================================
    # Input routing
    # =========================================================================

    @staticmethod
    def _is_url(source):
        """Check if the source is a URL (as opposed to a local file path)."""
        return source.strip().lower().startswith(('http://', 'https://'))

    # =========================================================================
    # Remote scraping via Firecrawl API
    # =========================================================================

    def _scrape_url(self, url):
        """
        Scrape a remote URL using the Firecrawl API.
        Handles webpages, remote PDFs, Excel, and Word documents.
        """

        if not self.client:
            raise RuntimeError("Firecrawl API key not configured. Set FIRECRAWL_API_KEY in .env")

        # Build scrape options
        formats = [self.format] if self.format != 'json' else ['markdown']
        scrape_kwargs = {
            'formats': formats,
        }

        if self.only_main_content is not None:
            scrape_kwargs['only_main_content'] = self.only_main_content

        if self.timeout is not None:
            scrape_kwargs['timeout'] = self.timeout

        # Add PDF parser options if specified
        if self.pdf_mode or self.pdf_max_pages:
            parser = {"type": "pdf"}
            if self.pdf_mode:
                parser["mode"] = self.pdf_mode
            if self.pdf_max_pages:
                parser["maxPages"] = self.pdf_max_pages
            scrape_kwargs['parsers'] = [parser]

        result = self.client.scrape(url, **scrape_kwargs)

        # Extract the content based on the requested format
        if hasattr(result, 'markdown') and self.format == 'markdown':
            return result.markdown or ''
        elif hasattr(result, 'html') and self.format == 'html':
            return result.html or ''
        elif hasattr(result, 'markdown'):
            return result.markdown or ''
        elif isinstance(result, dict):
            return result.get('markdown', result.get('html', json.dumps(result)))
        else:
            return str(result)

    def _extract_from_url(self, url, prompt):
        """
        Extract structured data from a remote URL using Firecrawl.
        Strategy: First try scrape with JSON format (faster, works on single URLs).
        Falls back to the Extract API if scrape doesn't return JSON data.
        """

        if not self.client:
            raise RuntimeError("Firecrawl API key not configured. Set FIRECRAWL_API_KEY in .env")

        # Strategy 1: Scrape with JSON format extraction (best for single URLs)
        scrape_kwargs = {
            'formats': [{'type': 'json', 'prompt': prompt}],
        }

        if self.schema:
            scrape_kwargs['formats'] = [{'type': 'json', 'prompt': prompt, 'schema': self.schema}]

        # Add PDF parser options if specified
        if self.pdf_mode or self.pdf_max_pages:
            parser = {"type": "pdf"}
            if self.pdf_mode:
                parser["mode"] = self.pdf_mode
            if self.pdf_max_pages:
                parser["maxPages"] = self.pdf_max_pages
            scrape_kwargs['parsers'] = [parser]

        try:
            result = self.client.scrape(url, **scrape_kwargs)

            # Check for JSON data in the response
            json_data = None
            if hasattr(result, 'json'):
                json_data = result.json
            elif isinstance(result, dict) and 'json' in result:
                json_data = result['json']

            if json_data and json_data != {} and json_data != []:
                return json.dumps(json_data, ensure_ascii=False, default=str)
        except Exception:
            pass  # Fall through to Extract API

        # Strategy 2: Extract API (async, better for multi-URL or complex extraction)
        extract_kwargs = {
            'urls': [url],
            'prompt': prompt,
        }

        if self.schema:
            extract_kwargs['schema'] = self.schema

        if self.enable_web_search:
            extract_kwargs['enable_web_search'] = True

        result = self.client.extract(**extract_kwargs)

        # Return the extracted data as JSON string
        if hasattr(result, 'data'):
            return json.dumps(result.data, ensure_ascii=False, default=str)
        elif isinstance(result, dict):
            data = result.get('data', result)
            return json.dumps(data, ensure_ascii=False, default=str)
        else:
            return str(result)

    def _search_web(self, query):
        """
        Search the web using the Firecrawl Search API.
        """

        # Build search options (query is positional)
        search_kwargs = {}

        if self.search_limit:
            search_kwargs['limit'] = self.search_limit

        if self.location:
            search_kwargs['location'] = self.location

        if self.tbs:
            search_kwargs['tbs'] = self.tbs

        if self.scrape_content:
            search_kwargs['scrape_options'] = {
                'formats': ['markdown']
            }

        result = self.client.search(query, **search_kwargs)

        # Format results as JSON string
        # The SDK returns objects with .data containing SearchResultWeb objects
        # We need to convert these to plain dicts for JSON serialization
        return json.dumps(self._normalize_result(result), ensure_ascii=False, default=str)

    def _run_agent(self, source, prompt):
        """
        Run a Firecrawl Agent task. The agent autonomously searches, navigates,
        and extracts structured data from websites.
        """

        agent_kwargs = {
            'prompt': prompt,
        }

        # Add URLs if a source was provided
        if source and source.strip():
            # Support multiple URLs separated by semicolons
            urls = [u.strip() for u in source.split(';') if u.strip()]
            if urls:
                agent_kwargs['urls'] = urls

        # Set agent model
        if self.agent_model:
            agent_kwargs['model'] = self.agent_model

        # Set max credits
        if self.max_credits:
            agent_kwargs['max_credits'] = self.max_credits

        # Set schema if provided
        if self.schema:
            agent_kwargs['schema'] = self.schema

        result = self.client.agent(**agent_kwargs)

        # Normalize and return as JSON string
        return json.dumps(self._normalize_result(result), ensure_ascii=False, default=str)

    # =========================================================================
    # Local file parsing
    # =========================================================================

    def _parse_local_file(self, filepath):
        """
        Parse a local file and return its content as markdown.
        Supports PDF, Excel, Word, CSV, and plain text files.
        """

        filepath = filepath.strip()

        if not os.path.isfile(filepath):
            raise FileNotFoundError("File not found: {}".format(filepath))

        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.pdf':
            return self._parse_pdf(filepath)
        elif ext in ('.xlsx', '.xls'):
            return self._parse_excel(filepath)
        elif ext in ('.docx', '.doc', '.odt', '.rtf'):
            return self._parse_docx(filepath)
        elif ext in ('.csv',):
            return self._parse_csv(filepath)
        else:
            return self._parse_text(filepath)

    def _parse_pdf(self, filepath):
        """
        Parse a local PDF file and return content as markdown.
        Uses pdfplumber for text and table extraction.
        """

        if not _HAS_PDFPLUMBER:
            raise RuntimeError(
                "pdfplumber is not installed. Install it with: pip install pdfplumber"
            )

        parts = []

        with pdfplumber.open(filepath) as pdf:
            max_pages = self.pdf_max_pages or len(pdf.pages)

            for i, page in enumerate(pdf.pages[:max_pages]):
                parts.append("## Page {}\n".format(i + 1))

                # Extract tables first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table and len(table) > 0:
                            # Convert table to markdown
                            md_table = self._table_to_markdown(table)
                            parts.append(md_table)
                            parts.append("")

                # Extract text (excluding table areas if possible)
                text = page.extract_text()
                if text:
                    parts.append(text.strip())
                    parts.append("")

        return "\n".join(parts).strip()

    def _parse_excel(self, filepath):
        """
        Parse a local Excel file and return content as markdown.
        Each worksheet is converted to a markdown table.
        """

        if not _HAS_OPENPYXL:
            raise RuntimeError(
                "openpyxl is not installed. Install it with: pip install openpyxl"
            )

        parts = []

        # Read all sheets
        sheets = pd.read_excel(filepath, sheet_name=None, engine='openpyxl')

        for sheet_name, df in sheets.items():
            parts.append("## {}\n".format(sheet_name))

            if not df.empty:
                # Convert DataFrame to markdown table
                header = "| " + " | ".join(str(c) for c in df.columns) + " |"
                separator = "| " + " | ".join("---" for _ in df.columns) + " |"
                rows = []
                for _, row in df.iterrows():
                    rows.append("| " + " | ".join(str(v) for v in row.values) + " |")

                parts.append(header)
                parts.append(separator)
                parts.extend(rows)
            else:
                parts.append("*Empty sheet*")

            parts.append("")

        return "\n".join(parts).strip()

    def _parse_docx(self, filepath):
        """
        Parse a local Word document and return content as markdown.
        Preserves headings, paragraphs, and tables.
        """

        if not _HAS_DOCX:
            raise RuntimeError(
                "python-docx is not installed. Install it with: pip install python-docx"
            )

        doc = python_docx.Document(filepath)
        parts = []

        for element in doc.element.body:
            # Handle paragraphs
            if element.tag.endswith('}p'):
                para = None
                for p in doc.paragraphs:
                    if p._element is element:
                        para = p
                        break

                if para and para.text.strip():
                    # Map Word heading styles to markdown
                    style = para.style.name if para.style else ''
                    if style.startswith('Heading 1'):
                        parts.append("# {}".format(para.text))
                    elif style.startswith('Heading 2'):
                        parts.append("## {}".format(para.text))
                    elif style.startswith('Heading 3'):
                        parts.append("### {}".format(para.text))
                    elif style.startswith('Heading'):
                        level = min(int(style.split()[-1]) if style.split()[-1].isdigit() else 4, 6)
                        parts.append("{} {}".format('#' * level, para.text))
                    else:
                        parts.append(para.text)
                    parts.append("")

            # Handle tables
            elif element.tag.endswith('}tbl'):
                for table in doc.tables:
                    if table._element is element:
                        rows = []
                        for row in table.rows:
                            cells = [cell.text.strip() for cell in row.cells]
                            rows.append(cells)

                        if rows:
                            md_table = self._table_to_markdown(rows)
                            parts.append(md_table)
                            parts.append("")
                        break

        return "\n".join(parts).strip()

    def _parse_csv(self, filepath):
        """
        Parse a local CSV file and return content as a markdown table.
        """

        df = pd.read_csv(filepath)

        if df.empty:
            return "*Empty file*"

        # Convert DataFrame to markdown table
        header = "| " + " | ".join(str(c) for c in df.columns) + " |"
        separator = "| " + " | ".join("---" for _ in df.columns) + " |"
        rows = []
        for _, row in df.iterrows():
            rows.append("| " + " | ".join(str(v) for v in row.values) + " |")

        parts = [header, separator] + rows
        return "\n".join(parts)

    def _parse_text(self, filepath):
        """
        Parse a local text file and return its content.
        """

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()

    @staticmethod
    def _normalize_result(obj):
        """
        Recursively convert Firecrawl SDK response objects (pydantic models, dataclasses)
        into plain Python dicts/lists for JSON serialization.
        """
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: FirecrawlForQlik._normalize_result(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [FirecrawlForQlik._normalize_result(item) for item in obj]
        # Handle pydantic models and other objects with __dict__
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        if hasattr(obj, '__dict__'):
            return {k: FirecrawlForQlik._normalize_result(v) for k, v in obj.__dict__.items()
                    if not k.startswith('_')}
        return str(obj)

    @staticmethod
    def _table_to_markdown(table):
        """
        Convert a list of lists (table rows) to a markdown table string.
        """

        if not table or len(table) == 0:
            return ""

        # Clean cell values
        cleaned = []
        for row in table:
            cleaned.append([str(cell).strip().replace('|', '\\|') if cell else '' for cell in row])

        # Build markdown table
        header = "| " + " | ".join(cleaned[0]) + " |"
        separator = "| " + " | ".join("---" for _ in cleaned[0]) + " |"
        rows = []
        for row in cleaned[1:]:
            # Pad row to match header length if needed
            while len(row) < len(cleaned[0]):
                row.append('')
            rows.append("| " + " | ".join(row[:len(cleaned[0])]) + " |")

        return "\n".join([header, separator] + rows)

    # =========================================================================
    # Local file extraction via LLM
    # =========================================================================

    def _extract_from_local(self, filepath, prompt):
        """
        Extract structured data from a local file by:
        1. Parsing the file to markdown
        2. Sending the content + prompt to an LLM for structured extraction
        """

        # Parse the local file to markdown
        content = self._parse_local_file(filepath)

        if not content or content.strip() == '':
            return json.dumps({"error": "No content extracted from file"})

        # Truncate content if too long for LLM context
        max_content_chars = int(self.kwargs.get('max_content_chars', '50000'))
        if len(content) > max_content_chars:
            content = content[:max_content_chars] + "\n\n[Content truncated...]"

        # Build the LLM prompt
        system_prompt = (
            "You are a data extraction assistant. Extract structured data from the provided "
            "document content based on the user's instructions. Return ONLY valid JSON with "
            "no additional text or explanation."
        )

        user_prompt = (
            "Extract the following from this document:\n\n"
            "{}\n\n"
            "---\n\n"
            "DOCUMENT CONTENT:\n\n{}"
        ).format(prompt, content)

        # Call the appropriate LLM provider
        provider = self.llm_provider.lower()

        if provider == 'claude':
            return self._call_claude_for_extraction(system_prompt, user_prompt)
        else:
            return self._call_openai_for_extraction(system_prompt, user_prompt)

    def _call_openai_for_extraction(self, system_prompt, user_prompt):
        """
        Use Azure OpenAI to extract structured data from content.
        """
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-11-01-preview"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        )
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_completion_tokens=4096,
        )

        return response.choices[0].message.content

    def _call_claude_for_extraction(self, system_prompt, user_prompt):
        """
        Use Azure AI Foundry Claude to extract structured data from content.
        """
        import anthropic

        client = anthropic.Anthropic(
            api_key=os.environ.get("AZURE_FOUNDRY_API_KEY"),
            base_url=os.environ.get("AZURE_FOUNDRY_CLAUDE_API_ENDPOINT"),
        )
        api_version = os.environ.get("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")
        model = os.environ.get("AZURE_CLAUDE_SONNET", "claude-sonnet-4-5")

        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
            max_tokens=4096,
            extra_headers={"api-version": api_version},
        )

        return response.content[0].text

    # =========================================================================
    # Parameter handling
    # =========================================================================

    def _set_params(self, kwargs):
        """
        Set input parameters based on the request.
        """

        # If key word arguments were included in the request, get the parameters and values
        # Normalize pipe delimiter to comma (USAGE.md documents | as the kwargs separator)
        normalized = kwargs.replace('|', ',') if kwargs else kwargs
        self.kwargs = {} if len(normalized) == 0 else utils.get_kwargs(normalized)

        # Set the debug option for generating execution logs
        self.debug = False if 'debug' not in self.kwargs else ('true' == self.kwargs.pop('debug').lower())

        # Additional information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'Firecrawl Log {}.txt'.format(self.log_no))
            self._print_log(1)

        # Scrape parameters
        self.format = self.kwargs.pop('format', 'markdown').lower()
        self.only_main_content = None
        omc = self.kwargs.pop('only_main_content', None)
        if omc is not None:
            self.only_main_content = omc.lower() == 'true'
        self.timeout = None
        timeout_str = self.kwargs.pop('timeout', None)
        if timeout_str is not None:
            self.timeout = int(timeout_str)

        # PDF parsing parameters
        self.pdf_mode = self.kwargs.pop('pdf_mode', None)
        pdf_max = self.kwargs.pop('pdf_max_pages', None)
        self.pdf_max_pages = int(pdf_max) if pdf_max else None

        # Extract parameters
        self.schema = None
        schema_str = self.kwargs.pop('schema', None)
        if schema_str:
            try:
                self.schema = json.loads(schema_str)
            except json.JSONDecodeError:
                pass

        self.enable_web_search = self.kwargs.pop('enable_web_search', 'false').lower() == 'true'
        self.llm_provider = self.kwargs.pop('llm_provider', 'openai').lower()

        # Search parameters
        limit_str = self.kwargs.pop('limit', None)
        self.search_limit = int(limit_str) if limit_str else None
        self.location = self.kwargs.pop('location', None)
        self.tbs = self.kwargs.pop('tbs', None)
        self.scrape_content = self.kwargs.pop('scrape_content', 'false').lower() == 'true'

        # Agent parameters
        self.agent_model = self.kwargs.pop('model', None)
        max_credits_str = self.kwargs.pop('max_credits', None)
        self.max_credits = int(max_credits_str) if max_credits_str else None

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(2)

        # Remove the kwargs column from the request_df
        self.request_df = self.request_df.drop(['kwargs'], axis=1)

    # =========================================================================
    # Table description for load script calls
    # =========================================================================

    def _send_table_description(self, variant):
        """
        Send the table description to Qlik as meta data.
        Used when the SSE is called from the Qlik load script.
        """

        # Set up the table description to send as metadata to Qlik
        self.table = SSE.TableDescription()
        self.table.name = "SSE-Response-Firecrawl"
        self.table.numberOfRows = len(self.response_df)

        # Set up fields for the table
        if variant == "scrape_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="source")
            self.table.fields.add(name="content")
        elif variant == "extract_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="source")
            self.table.fields.add(name="extracted")
        elif variant == "search_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="query")
            self.table.fields.add(name="results")
        elif variant == "agent_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="source")
            self.table.fields.add(name="result")

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(5)

        # Send table description
        table_header = (('qlik-tabledescription-bin', self.table.SerializeToString()),)
        self.context.send_initial_metadata(table_header)

    # =========================================================================
    # Logging
    # =========================================================================

    def _print_log(self, step):
        """
        Output useful information to stdout and the log file if debugging is required.
        :step: Print the corresponding step in the log
        """

        # Set mode to append to log file
        mode = 'a'

        if self.logfile is None:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'Firecrawl Log {}.txt'.format(self.log_no))

        if step == 1:
            output = "\nFirecrawlForQlik Log: {0} \n\n".format(time.ctime(time.time()))
            mode = 'w'

        elif step == 2:
            output = "Execution parameters:\n"
            output += "  Format: {0}\n".format(self.format)
            output += "  PDF Mode: {0}\n".format(self.pdf_mode)
            output += "  PDF Max Pages: {0}\n".format(self.pdf_max_pages)
            output += "  LLM Provider: {0}\n".format(self.llm_provider)
            output += "  Enable Web Search: {0}\n".format(self.enable_web_search)
            output += "  Search Limit: {0}\n".format(self.search_limit)
            output += "  Firecrawl Client: {0}\n\n".format('configured' if self.client else 'NOT configured')

        elif step == 3:
            output = "REQUEST: {0} rows x cols\nSample Data:\n\n".format(self.request_df.shape)
            output += "{0}\n...\n{1}\n\n".format(self.request_df.head().to_string(), self.request_df.tail().to_string())

        elif step == 4:
            if isinstance(self.response_df, pd.DataFrame):
                output = "RESPONSE: {0} rows x cols\nSample Data:\n\n".format(self.response_df.shape)
                output += "{0}\n...\n{1}\n\n".format(self.response_df.head().to_string(), self.response_df.tail().to_string())
            else:
                output = "RESPONSE: {0} rows\nSample Data:\n\n".format(len(self.response_df))
                output += "{0}\n\n".format(self.response_df.head().to_string())

        elif step == 5:
            output = "\nTABLE DESCRIPTION SENT TO QLIK:\n\n{0} \n\n".format(self.table)

        sys.stdout.write(output)
        with open(self.logfile, mode, encoding='utf-8') as f:
            f.write(output)

    def _print_exception(self, s, e):
        """
        Output exception message to stdout and also to the log file if debugging is required.
        """

        sys.stdout.write("\n{0}: {1} \n\n".format(s, e))

        if self.debug:
            with open(self.logfile, 'a') as f:
                f.write("\n{0}: {1} \n\n".format(s, e))
