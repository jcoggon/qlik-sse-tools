import os
import sys
import time
import warnings
import base64
import json
import pandas as pd

# Suppress warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore")

import _llm_backends as backends
from _llm_cli import LLMError, cli_row_limit, cli_text
import _utils as utils
import ServerSideExtension_pb2 as SSE

# Add Generated folder to module path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PARENT_DIR, 'generated'))

class LLMForQlik:
    """
    A class to provide Azure OpenAI LLM capabilities for Qlik.
    Sends prompts to an Azure OpenAI deployment and returns the response.
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

        self.client = None
        self.deployment = None
        self.backend = os.environ.get("QLIK_LLM_CHAT_BACKEND", "azure_openai").strip().lower()

    def chat(self, load_script=False):
        """
        Send a prompt to the Azure OpenAI LLM and return the response.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.LLM_Chat('Summarize the following sales data: ' & concat(SalesInfo, '; '), 'debug=false')
        :<AAI Connection Name>.LLM_Chat('What reorder quantity do you recommend for product ' & ProductName & '?', 'system_prompt=You are an inventory management expert.')
        """

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['key', 'prompt', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData']
            col_headers = ['prompt', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        self._set_params('' if self.request_df.empty else self.request_df['kwargs'].iloc[0])

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each unique prompt and get responses
        responses = []

        for i in self.request_df.index:
            prompt = self.request_df.loc[i, 'prompt']

            try:
                response_text = self._call_llm(prompt)
            except Exception as e:
                response_text = "Error: {}".format(str(e))
                if self.debug:
                    self._print_exception("LLM call failed", e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], prompt, response_text))
            else:
                responses.append(response_text)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'prompt', 'response'])

            # Send the response table description to Qlik
            self._send_table_description("chat_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    def _call_llm(self, prompt):
        """
        Make a call to the Azure OpenAI API.
        """

        messages = []

        # Add system prompt if specified
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        messages.append({"role": "user", "content": prompt})

        if self.client is None:
            self.deployment = backends.openai_model(self.backend)
            self.client = backends.openai_client(self.backend, responses=False)
        options = {"temperature": self.temperature} if self.temperature_explicit or self.backend == "azure_openai" else {}
        response = self.client.chat.completions.create(
            model=self.deployment, messages=messages, max_completion_tokens=self.max_tokens, **options,
        )

        return response.choices[0].message.content

    def response(self, load_script=False):
        """Run a one-shot text or structured response through the configured backend."""
        if load_script:
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['key', 'prompt', 'kwargs']
        else:
            row_template = ['strData', 'strData']
            col_headers = ['prompt', 'kwargs']

        self.request_df = utils.request_df(self.request, row_template, col_headers)
        self.backend = backends.responses_backend()
        self._set_params('' if self.request_df.empty else self.request_df['kwargs'].iloc[0])
        cli_limit = cli_row_limit() if self.backend == "codex_cli" else None

        responses = []
        for i in self.request_df.index:
            prompt = self.request_df.loc[i, 'prompt']
            try:
                if cli_limit is not None and len(self.request_df) > cli_limit:
                    raise LLMError(f"Codex CLI accepts at most {cli_limit} rows per SSE call.")
                response_text = self._call_response(prompt)
            except Exception as e:
                response_text = "Error: {}".format(str(e))
                if self.debug:
                    self._print_exception("Responses API call failed", e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], prompt, response_text))
            else:
                responses.append(response_text)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'prompt', 'response'])
            self._send_table_description("chat_bulk")
        else:
            self.response_df = pd.Series(responses)
        return self.response_df

    def _call_response(self, prompt):
        generation = backends.Generation(
            prompt, instructions=self.system_prompt, max_tokens=self.max_tokens,
            temperature=self.temperature if self.temperature_explicit else None,
            schema=self.json_schema, schema_name=self.json_schema_name, store=self.store,
            previous_response_id=self.previous_response_id,
        )
        if self.backend in {"openai", "azure_openai"}:
            if self.client is None:
                self.deployment = backends.openai_model(self.backend)
                self.client = backends.openai_client(self.backend)
            return backends.api_response(self.client, self.deployment, generation)[0]
        if self.store or self.previous_response_id:
            raise LLMError("The selected backend accepts stateless requests only.")
        if self.backend == "codex_cli":
            if self.temperature_explicit:
                raise LLMError("Codex CLI does not support temperature.")
            return cli_text(
                "codex", prompt, model=os.environ.get("QLIK_LLM_CODEX_MODEL"), instructions=self.system_prompt,
                schema=self.json_schema, max_tokens=self.max_tokens,
            )
        if self.backend == "gemini":
            return backends.gemini_text(generation)
        if self.backend == "ollama":
            return backends.ollama_text(generation)
        raise LLMError("QLIK_LLM_RESPONSES_BACKEND must be azure_openai, openai, codex_cli, gemini or ollama.")

    def _set_params(self, kwargs):
        """
        Set input parameters based on the request.
        """

        # If key word arguments were included in the request, get the parameters and values
        self.kwargs = {} if len(kwargs) == 0 else utils.get_kwargs(kwargs)

        # Set the debug option for generating execution logs
        self.debug = self.kwargs.pop('debug', 'false').lower() == 'true' and self.backend != "codex_cli"

        # Additional information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'LLM Log {}.txt'.format(self.log_no))
            self._print_log(1)

        # Set the system prompt for the LLM
        self.system_prompt = self.kwargs.pop('system_prompt', None)

        # Set the temperature for the LLM (controls randomness, 0.0 = deterministic, 1.0 = creative)
        self.temperature_explicit = 'temperature' in self.kwargs
        self.temperature = float(self.kwargs.pop('temperature', '0.7'))

        # Set the max tokens for the LLM response
        self.max_tokens = int(self.kwargs.pop('max_tokens', '2048'))

        # Responses API options. JSON schemas are base64url encoded so their
        # commas do not conflict with the SSE kwargs delimiter.
        self.previous_response_id = self.kwargs.pop('previous_response_id', None)
        self.store = self.kwargs.pop('store', 'false').lower() == 'true'
        self.json_schema_name = self.kwargs.pop('json_schema_name', 'qlik_response')
        schema_b64 = self.kwargs.pop('json_schema_b64', None)
        self.json_schema = None
        if schema_b64:
            padding = '=' * (-len(schema_b64) % 4)
            decoded = base64.urlsafe_b64decode(schema_b64 + padding).decode('utf-8')
            self.json_schema = json.loads(decoded)

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(2)

        # Remove the kwargs column from the request_df
        self.request_df = self.request_df.drop(['kwargs'], axis=1)

    def _send_table_description(self, variant):
        """
        Send the table description to Qlik as meta data.
        Used when the SSE is called from the Qlik load script.
        """

        # Set up the table description to send as metadata to Qlik
        self.table = SSE.TableDescription()
        self.table.name = "SSE-Response-LLM"
        self.table.numberOfRows = len(self.response_df)

        # Set up fields for the table
        if variant == "chat_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="prompt")
            self.table.fields.add(name="response")

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(5)

        # Send table description
        table_header = (('qlik-tabledescription-bin', self.table.SerializeToString()),)
        self.context.send_initial_metadata(table_header)

    def _print_log(self, step):
        """
        Output useful information to stdout and the log file if debugging is required.
        :step: Print the corresponding step in the log
        """

        # Set mode to append to log file
        mode = 'a'

        if self.logfile is None:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'LLM Log {}.txt'.format(self.log_no))

        if step == 1:
            output = "\nLLMForQlik Log: {0} \n\n".format(time.ctime(time.time()))
            mode = 'w'

        elif step == 2:
            output = "Execution parameters:\n"
            output += "  Deployment: {0}\n".format(self.deployment)
            output += "  Temperature: {0}\n".format(self.temperature)
            output += "  Max Tokens: {0}\n".format(self.max_tokens)
            output += "  System Prompt: {0}\n\n".format(self.system_prompt)

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


class ClaudeForQlik:
    """
    A class to provide Azure AI Foundry Claude LLM capabilities for Qlik.
    Supports Claude Haiku, Opus, and Sonnet models via Azure AI Foundry.
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

        self.backend = backends.claude_backend()
        self.client = None

    def chat(self, load_script=False):
        """
        Send a prompt to the Azure AI Foundry Claude LLM and return the response.
        Can be called from a chart expression or the load script in Qlik.

        :Qlik expression examples:
        :<AAI Connection Name>.LLM_Claude_Chat('Analyze this sales trend: ' & SalesData, 'model=sonnet')
        :<AAI Connection Name>.LLM_Claude_Chat('Recommend reorder quantity for ' & ProductName, 'model=opus|system_prompt=You are an inventory expert.')
        """

        if load_script:
            # Load script variant includes a key column
            row_template = ['strData', 'strData', 'strData']
            col_headers = ['key', 'prompt', 'kwargs']
        else:
            # Chart expression variant
            row_template = ['strData', 'strData']
            col_headers = ['prompt', 'kwargs']

        # Create a Pandas DataFrame for the request data
        self.request_df = utils.request_df(self.request, row_template, col_headers)

        # Get the argument strings from the request dataframe
        self._set_params('' if self.request_df.empty else self.request_df['kwargs'].iloc[0])
        cli_limit = cli_row_limit() if self.backend == "claude_cli" else None

        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each unique prompt and get responses
        responses = []

        for i in self.request_df.index:
            prompt = self.request_df.loc[i, 'prompt']

            try:
                if cli_limit is not None and len(self.request_df) > cli_limit:
                    raise LLMError(f"Claude CLI accepts at most {cli_limit} rows per SSE call.")
                response_text = self._call_claude(prompt)
            except Exception as e:
                response_text = "Error: {}".format(str(e))
                if self.debug:
                    self._print_exception("Claude call failed", e)

            if load_script:
                responses.append((self.request_df.loc[i, 'key'], prompt, response_text))
            else:
                responses.append(response_text)

        if load_script:
            self.response_df = pd.DataFrame(responses, columns=['key', 'prompt', 'response'])

            # Send the response table description to Qlik
            self._send_table_description("chat_bulk")
        else:
            self.response_df = pd.Series(responses)

        # Print the response to the logs
        if self.debug:
            self._print_log(4)

        return self.response_df

    def _call_claude(self, prompt):
        if self.backend == "claude_cli":
            if self.temperature is not None:
                raise LLMError("Claude CLI does not support temperature.")
            return cli_text(
                "claude", prompt, model=self.model, instructions=self.system_prompt, max_tokens=self.max_tokens,
            )
        if self.client is None:
            self.client = backends.claude_client(self.backend)
        return backends.claude_api_text(self.client, self.backend, self.model, backends.Generation(
            prompt, instructions=self.system_prompt, max_tokens=self.max_tokens, temperature=self.temperature,
        ))

    def _set_params(self, kwargs):
        """
        Set input parameters based on the request.
        """

        # If key word arguments were included in the request, get the parameters and values
        self.kwargs = {} if len(kwargs) == 0 else utils.get_kwargs(kwargs)

        # Set the debug option for generating execution logs
        self.debug = self.kwargs.pop('debug', 'false').lower() == 'true' and self.backend != "claude_cli"

        # Additional information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'Claude Log {}.txt'.format(self.log_no))
            self._print_log(1)

        # Set the Claude model: haiku, opus, or sonnet (default: sonnet)
        self.model = backends.claude_model(self.backend, self.kwargs.pop('model', None))

        # Set the system prompt for the LLM
        self.system_prompt = self.kwargs.pop('system_prompt', None)

        # Set the temperature for the LLM (controls randomness, 0.0 = deterministic, 1.0 = creative)
        temperature = self.kwargs.pop('temperature', '0.7' if self.backend == 'foundry' else None)
        self.temperature = float(temperature) if temperature is not None else None

        # Set the max tokens for the LLM response
        self.max_tokens = int(self.kwargs.pop('max_tokens', '2048'))

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(2)

        # Remove the kwargs column from the request_df
        self.request_df = self.request_df.drop(['kwargs'], axis=1)

    def _send_table_description(self, variant):
        """
        Send the table description to Qlik as meta data.
        Used when the SSE is called from the Qlik load script.
        """

        # Set up the table description to send as metadata to Qlik
        self.table = SSE.TableDescription()
        self.table.name = "SSE-Response-Claude"
        self.table.numberOfRows = len(self.response_df)

        # Set up fields for the table
        if variant == "chat_bulk":
            self.table.fields.add(name="key")
            self.table.fields.add(name="prompt")
            self.table.fields.add(name="response")

        # Debug information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self._print_log(5)

        # Send table description
        table_header = (('qlik-tabledescription-bin', self.table.SerializeToString()),)
        self.context.send_initial_metadata(table_header)

    def _print_log(self, step):
        """
        Output useful information to stdout and the log file if debugging is required.
        :step: Print the corresponding step in the log
        """

        # Set mode to append to log file
        mode = 'a'

        if self.logfile is None:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'Claude Log {}.txt'.format(self.log_no))

        if step == 1:
            output = "\nClaudeForQlik Log: {0} \n\n".format(time.ctime(time.time()))
            mode = 'w'

        elif step == 2:
            output = "Execution parameters:\n"
            output += "  Model: {0}\n".format(self.model)
            output += "  Temperature: {0}\n".format(self.temperature)
            output += "  Max Tokens: {0}\n".format(self.max_tokens)
            output += "  System Prompt: {0}\n\n".format(self.system_prompt)

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
