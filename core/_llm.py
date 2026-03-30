import os
import sys
import time
import warnings
import numpy as np
import pandas as pd

# Suppress warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore")

from openai import AzureOpenAI
import anthropic

import _utils as utils
import ServerSideExtension_pb2 as SSE

# Add Generated folder to module path
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PARENT_DIR, 'generated'))

# Map of short model names to environment variable keys for Claude models
CLAUDE_MODELS = {
    'haiku': 'AZURE_CLAUDE_HAIKU',
    'opus': 'AZURE_CLAUDE_OPUS',
    'sonnet': 'AZURE_CLAUDE_SONNET',
}

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

        # Initialize the Azure OpenAI client from environment variables
        self.client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-11-01-preview"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        )
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

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
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)
        
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
        
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,
            temperature=self.temperature,
            max_completion_tokens=self.max_tokens,
        )

        return response.choices[0].message.content

    def _set_params(self, kwargs):
        """
        Set input parameters based on the request.
        """
        
        # If key word arguments were included in the request, get the parameters and values
        self.kwargs = {} if len(kwargs) == 0 else utils.get_kwargs(kwargs)
            
        # Set the debug option for generating execution logs
        self.debug = False if 'debug' not in self.kwargs else ('true' == self.kwargs.pop('debug').lower())
            
        # Additional information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'LLM Log {}.txt'.format(self.log_no))
            self._print_log(1)
        
        # Set the system prompt for the LLM
        self.system_prompt = self.kwargs.pop('system_prompt', None)

        # Set the temperature for the LLM (controls randomness, 0.0 = deterministic, 1.0 = creative)
        self.temperature = float(self.kwargs.pop('temperature', '0.7'))

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

        # Initialize the Anthropic client for Azure AI Foundry
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("AZURE_FOUNDRY_API_KEY"),
            base_url=os.environ.get("AZURE_FOUNDRY_CLAUDE_API_ENDPOINT"),
        )
        self.api_version = os.environ.get("AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview")

        # Default to Sonnet
        self.model = os.environ.get("AZURE_CLAUDE_SONNET", "claude-sonnet-4-5")

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
        if 'kwargs' in self.request_df.columns:
            kwargs = self.request_df.loc[0, 'kwargs']
            self._set_params(kwargs)
        
        # Print the request dataframe to the logs
        if self.debug:
            self._print_log(3)

        # Process each unique prompt and get responses
        responses = []

        for i in self.request_df.index:
            prompt = self.request_df.loc[i, 'prompt']
            
            try:
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
        """
        Make a call to the Azure AI Foundry Claude API.
        """

        # Build the messages list
        messages = [{"role": "user", "content": prompt}]
        
        # Build the API call kwargs
        api_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Add system prompt if specified (Anthropic uses a top-level system parameter)
        if self.system_prompt:
            api_kwargs["system"] = self.system_prompt

        # Add Azure API version as extra header
        response = self.client.messages.create(
            **api_kwargs,
            extra_headers={"api-version": self.api_version},
        )

        return response.content[0].text

    def _set_params(self, kwargs):
        """
        Set input parameters based on the request.
        """
        
        # If key word arguments were included in the request, get the parameters and values
        self.kwargs = {} if len(kwargs) == 0 else utils.get_kwargs(kwargs)
            
        # Set the debug option for generating execution logs
        self.debug = False if 'debug' not in self.kwargs else ('true' == self.kwargs.pop('debug').lower())
            
        # Additional information is printed to the terminal and logs if the paramater debug = true
        if self.debug:
            self.__class__.log_no += 1
            self.logfile = os.path.join(os.getcwd(), 'logs', 'Claude Log {}.txt'.format(self.log_no))
            self._print_log(1)
        
        # Set the Claude model: haiku, opus, or sonnet (default: sonnet)
        model_key = self.kwargs.pop('model', 'sonnet').lower()
        if model_key in CLAUDE_MODELS:
            self.model = os.environ.get(CLAUDE_MODELS[model_key], model_key)
        else:
            # Allow passing a full model name directly
            self.model = model_key

        # Set the system prompt for the LLM
        self.system_prompt = self.kwargs.pop('system_prompt', None)

        # Set the temperature for the LLM (controls randomness, 0.0 = deterministic, 1.0 = creative)
        self.temperature = float(self.kwargs.pop('temperature', '0.7'))

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
