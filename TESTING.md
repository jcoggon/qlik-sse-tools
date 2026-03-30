# Qlik Python Tools — Testing & Verification Guide

> Standalone test suite and usage reference for verifying all capabilities work correctly
> without requiring a running Qlik Sense environment.

---

## Quick Start

```bash
# From the project root, with the virtual environment initialized:
cd qlik-py-env/core
python ../../tests/test_all_tools.py
```

> **Why `cd qlik-py-env/core`?** The SSE modules use relative imports and relative paths
> (e.g., `../models/` for saved models). The server is designed to run from this directory,
> so the tests must also run from here to match the runtime environment.

Expected output (all 16 tests should pass):

```
============================================================
  Qlik Python Tools — Test Suite
============================================================
  Python:  3.13.11
  NumPy:   2.4.2
  Pandas:  2.3.3
============================================================

--- Module Tests ---
  ✅ PASS  Import all modules
  ✅ PASS  NumPy/Pandas compatibility
  ✅ PASS  ML Keras stubs (no AttributeError)
  ✅ PASS  LLM module import

--- Utility Tests ---
  ✅ PASS  Utils kwargs parsing
  ✅ PASS  Utils count_placeholders
  ✅ PASS  Utils number parsing (atof/atoi)

--- Correlation Tests ---
  ✅ PASS  Correlation (Pearson/Spearman/Kendall)

--- Prophet Tests ---
  ✅ PASS  Prophet Forecasting
  ✅ PASS  Prophet pipe-delimited kwargs
  ✅ PASS  Prophet comma-delimited kwargs

--- StatsForecast Tests ---
  ✅ PASS  StatsForecast (AutoARIMA)
  ✅ PASS  StatsForecast (AutoETS)

--- Clustering Tests ---
  ✅ PASS  HDBSCAN Clustering

--- NLP Tests ---
  ✅ PASS  spaCy NER

--- Common Functions Tests ---
  ✅ PASS  Association Rules

============================================================
  TEST SUMMARY: 16/16 passed, 0 failed
============================================================
```

---

## Prerequisites (Fresh System Setup)

Follow **every step** below. Skipping any will cause test failures.

### Step 1: Initialize the virtual environment
This creates `qlik-py-env/`, installs all Python packages, and copies source code into the venv.
```bash
./Qlik-Py-Init.sh        # macOS/Linux
Qlik-Py-Init.bat          # Windows
```

### Step 2: Install the spaCy English model
Required for the NER (Named Entity Recognition) test. Without this, the spaCy test will be skipped.
```bash
./qlik-py-env/bin/python -m spacy download en_core_web_sm    # macOS/Linux
qlik-py-env\Scripts\python -m spacy download en_core_web_sm  # Windows
```

### Step 3: Install openpyxl
Required for reading the Excel sample data files used in tests.
```bash
./qlik-py-env/bin/pip install openpyxl    # macOS/Linux
qlik-py-env\Scripts\pip install openpyxl  # Windows
```

### Step 4: Install optional packages for advanced analytics
An interactive installer is provided to add extra capabilities (larger spaCy models, Jupyter, etc.):
```bash
./Qlik-Py-Extras.sh          # macOS/Linux (interactive)
Qlik-Py-Extras.bat            # Windows (interactive)
```

Or use command-line options:
```bash
# Install a pre-defined bundle
./Qlik-Py-Extras.sh --bundle essentials    # spaCy small + Excel support
./Qlik-Py-Extras.sh --bundle analytics     # NLP + ML + Visualization
./Qlik-Py-Extras.sh --bundle nlp           # All spaCy models
./Qlik-Py-Extras.sh --bundle developer     # Everything + Jupyter

# Install specific packages
./Qlik-Py-Extras.sh spacy_md jupyter

# Install everything
./Qlik-Py-Extras.sh --all

# Show what's installed vs available
./Qlik-Py-Extras.sh --list
```

**Available packages:**

| Key | Package | Size | Description |
|-----|---------|------|-------------|
| `spacy_sm` | spaCy English (Small) | 15 MB | Basic NER — installed by default |
| `spacy_md` | spaCy English (Medium) | 40 MB | Better accuracy + word vectors |
| `spacy_lg` | spaCy English (Large) | 560 MB | Best accuracy + 685k word vectors |
| `spacy_trf` | spaCy English (Transformer) | 400+ MB | Highest accuracy (GPU recommended) |
| `openpyxl` | Excel File Support | <1 MB | Read/write .xlsx files |
| `jupyter` | Jupyter Notebook | ~100 MB | Interactive notebooks from docs/ |
| `deep_learning` | TensorFlow + Keras | 500+ MB | Neural network models |
| `plotly` | Plotly + Matplotlib | ~50 MB | Interactive visualizations |

### Step 5: Run the test suite
```bash
cd qlik-py-env/core
python ../../tests/test_all_tools.py
```

All 16 tests should pass. If any fail, check the [Troubleshooting](#troubleshooting) section below.

---

## Important: Source File Synchronization

The SSE runs from `qlik-py-env/core/`, **not** from `core/`.

If you edit files in `core/` (the source directory), those changes will **not take effect** until
they are copied to `qlik-py-env/core/`. The server start scripts (`Qlik-Py-Start.sh` / `.bat`)
automatically sync source files before launching. You can also sync manually:

```bash
cp core/*.py qlik-py-env/core/
```

> **Rule of thumb**: Edit in `core/`, then either restart the server (auto-syncs) or manually copy.

---

## LLM Tests — Important Limitation

The test suite verifies that LLM modules **import correctly**, but does **not** make actual API calls.
To fully test Azure OpenAI or Claude integrations, you must:

1. Configure your `.env` file with valid credentials (see [LLM Chat](#llm-chat-azure-openai) section)
2. Start the SSE server: `./Qlik-Py-Start.sh`
3. Call the LLM functions from Qlik Sense or via a gRPC client

---

## What the Tests Cover (16 Tests)

### 1. Module Imports
Verifies all 8 core modules load without errors:
- Prophet, HDBSCAN, scikit-learn/XGBoost/LightGBM, spaCy, Common Functions, LLM Integrations, StatsForecast, Firecrawl

### 2. NumPy/Pandas Compatibility
Confirms no deprecated APIs are used:
- `np.nan` instead of removed `np.NaN` (NumPy 2.0+)
- `pd.concat()` instead of removed `DataFrame.append()` (Pandas 2.0+)
- Scans source files for any remaining `np.NaN` references

### 3. ML Keras Stubs
Verifies `KerasClassifierForQlik` and `KerasRegressorForQlik` exist as `None` at module level (lazy-loaded), preventing `AttributeError` before TensorFlow is loaded.

### 4. LLM Module Import
Confirms `LLMForQlik` and `ClaudeForQlik` classes are importable. Actual API calls require Azure credentials configured in `.env`.

### 5. Utility Functions
- **kwargs parsing**: Comma-delimited (`key=val,key2=val2`), values containing `=`, entries without `=` are skipped
- **count_placeholders**: Correctly counts trailing zero/NaN values in a series
- **Number parsing**: `atof()` and `atoi()` handle strings and empty values

### 6. Correlation
Tests Pearson, Spearman, and Kendall correlation coefficients using known correlated data.

### 7. Prophet Forecasting
Tests with bike-sharing monthly data (`docs/bike-sharing/day.csv`):
- **Pipe-delimited kwargs**: `freq=MS|return=yhat|debug=false` (format used by Qlik apps)
- **Comma-delimited kwargs**: `freq=MS,return=yhat,debug=false` (legacy format)
- Verifies forecast length matches request, future periods are non-NaN

### 8. StatsForecast
Tests AutoARIMA and AutoETS models with the same bike-sharing data. Verifies forecast output length matches input.

### 9. HDBSCAN Clustering
Generates 3 clear synthetic clusters (30 points each) and verifies HDBSCAN finds at least 2 distinct clusters.

### 10. spaCy NER
Tests named entity recognition on sample sentences containing known entities (Apple Inc., Elon Musk, Berlin, etc.). Skips gracefully if `en_core_web_sm` model is not installed.

### 11. Association Rules
Tests the Apriori algorithm with market basket data (8 transactions of bread/milk/eggs/butter). Verifies rules are found with `min_support=0.2, min_confidence=0.3`.

---

## Sample Data

The project includes sample data in `docs/`:

| File | Description | Best For |
|------|-------------|----------|
| `docs/bike-sharing/day.csv` | Daily bike rental counts (731 days) | Prophet, StatsForecast |
| `docs/HR-Employee-Attrition.xlsx` | HR employee data with features | scikit-learn, Keras |
| `docs/VIC-Emergency-Department-Attendances.xlsx` | Monthly hospital attendance (40 hospitals) | Prophet (multi-series) |
| `docs/hands-on/data/Train Test.xlsx` | Train/test split data | scikit-learn |

---

## Keyword Argument Formats

The SSE functions accept keyword arguments in the last column. **Which delimiter to use depends on the module:**

### Pipe-delimited (Prophet, StatsForecast, Clustering only)
```
freq=MS|return=yhat|periods=12|debug=false
```
These three modules auto-detect: if `|` appears in the string, it splits on `|`; otherwise on `,`.

### Comma-delimited (all other modules)
```
estimator=RandomForestClassifier,overwrite=true,debug=false
```
Used by: scikit-learn, spaCy, LLM, Claude, Common Functions, and `_utils.get_kwargs()`.

### Pipe-or-comma (Firecrawl)
```
format=markdown|pdf_mode=ocr|debug=true
```
Firecrawl normalizes `|` to `,` internally before parsing, so both delimiters work.

### Comma-delimited with type annotations (Common Functions typed params)
```
min_support=0.2|float,min_confidence=0.3|float,debug=false|bool
```
The `|` inside values denotes the data type (parsed by `get_kwargs_by_type`), while `,` is the argument delimiter.

> **Critical**: scikit-learn, spaCy, LLM, and Claude kwargs **must** use commas. Using pipes in these modules will cause parsing failures.
> Firecrawl accepts both `|` and `,` — pipes are normalized to commas before parsing.

---

## Qlik Expression Quick Reference

Below, `PyTools` is the AAI connection name configured in Qlik. Replace it with your actual connection name.

### Correlation (Functions 3–4)
```
// Pearson correlation (default) — Function: Pearson
PyTools.Pearson(concat(Value1, ';'), concat(Value2, ';'))

// With method specified — Function: Correlation
PyTools.Correlation(concat(Value1, ';'), concat(Value2, ';'), 'spearman')
```
The two series are passed as semicolon-separated strings. Third argument accepts `'pearson'`, `'spearman'`, or `'kendall'`.

### Prophet Forecasting (Functions 5–8, 40–41)
```
// Basic forecast — Function: Prophet
PyTools.Prophet(MonthStartDate, sum(Value), 'return=yhat, freq=MS, debug=true')

// Without kwargs — Function: Prophet_Basic
PyTools.Prophet_Basic(MonthStartDate, sum(Value))

// With holidays — Function: Prophet_Holidays
PyTools.Prophet_Holidays(Date, sum(Value), Holiday, 'return=yhat, freq=D, debug=true')

// Seasonality (load script, returns multiple columns) — Function: Prophet_Seasonality
PyTools.Prophet_Seasonality(Month, $(vSeries), $(vHolidays), 'seasonality=yearly, freq=MS')

// Multivariate with added regressors — Function: Prophet_Multivariate
PyTools.Prophet_Multivariate(Date, sum(Value), Holiday, AddedRegressors, RegressorArgs, 'return=yhat, freq=D')

// Multivariate seasonality (load script) — Function: Prophet_Seasonality_Multivariate
PyTools.Prophet_Seasonality_Multivariate(Month, $(vSeries), $(vHolidays), $(vRegressors), $(vRegressorArgs), 'freq=MS')
```

**Prophet kwargs delimiter**: supports both `,` and `|` (auto-detected).

**Prophet Parameters:**
- `freq` — Time series frequency: `D` (daily), `W` (weekly), `MS` (month start), `QS` (quarter start), `YS` (year start)
- `return` — Output column: `yhat`, `yhat_upper`, `yhat_lower`, `trend`, `y_then_yhat`, `y_then_yhat_upper`, `y_then_yhat_lower`, `seasonal`, `residual`
- `take_log` — Log-transform values before forecasting: `true`/`false` (default `true`)
- `cap` / `floor` — Logistic growth bounds (enables logistic growth model)
- `changepoint_prior_scale` — Trend flexibility (default `0.05`, increase for more flexible)
- `interval_width` — Uncertainty interval width (default `0.8` = 80%)
- `lower_window` / `upper_window` — Extend holidays by N days before/after
- `seasonality_mode` — `additive` (default) or `multiplicative`
- `debug` — Print execution details: `true`/`false`
- `load_script` — Return DataFrame for load script: `true`/`false`

### StatsForecast (Function 50)
```
// AutoARIMA — Function: StatsForecast
PyTools.StatsForecast(Date, sum(Value), 'model=AutoARIMA, freq=MS, periods=12, return=yhat')

// AutoETS with confidence intervals
PyTools.StatsForecast(Date, sum(Value), 'model=AutoETS, freq=MS, periods=6, return=yhat_upper, level=95')
```

**StatsForecast kwargs delimiter**: supports both `,` and `|` (auto-detected).

**StatsForecast Models:**
- **Automatic**: `AutoARIMA`, `AutoETS`, `AutoTheta`, `AutoCES`
- **Decomposition**: `MSTL`
- **Baseline**: `Naive`, `SeasonalNaive`, `HistoricAverage`, `WindowAverage`, `SeasonalWindowAverage`
- **Intermittent Demand**: `ADIDA`, `CrostonClassic`, `CrostonOptimized`, `CrostonSBA`, `IMAPA`, `TSB`

**StatsForecast Parameters:**
- `model` — Model name (default `AutoARIMA`)
- `freq` — Frequency (default `MS`)
- `periods` — Forecast horizon (default `12`)
- `return` — `yhat`, `yhat_upper`, `yhat_lower`, `y_then_yhat`
- `level` — Confidence level, e.g. `95` (default `95`)
- `season_length` — Seasonal period (auto-detected if omitted)
- `take_log` — Log-transform: `true`/`false`
- `n_jobs` — Parallel jobs (default `1`)

### HDBSCAN Clustering (Functions 0–2)
```
// Standard clustering — Function: Cluster
PyTools.Cluster(Dimension, sum(Feature1) & ';' & sum(Feature2), 'scaler=standard, min_cluster_size=10')

// Two-dimension clustering (load script) — Function: Cluster_by_Dim
PyTools.Cluster_by_Dim(Dimension1, Dimension2, sum(Measure), 'scaler=standard, load_script=true')

// Geospatial clustering — Function: Cluster_Geo
PyTools.Cluster_Geo(Location, Latitude, Longitude, 'min_cluster_size=5')
```

**Clustering kwargs delimiter**: supports both `,` and `|` (auto-detected).

**Clustering Parameters:**
- `scaler` — `standard`, `robust`, `minmax`, `maxabs`, `quantile`, `none`
- `min_cluster_size` — Minimum points per cluster (default auto)
- `min_samples` — Core point threshold
- `debug` — `true`/`false`
- `load_script` — `true`/`false`

### Association Rules (Function 33)
```
// Market basket analysis — Function: Association_Rules
PyTools.Association_Rules(TransactionID, ProductName, 'min_support=0.2|float,min_confidence=0.5|float')
```
**Kwargs delimiter**: comma (with `|` used for type annotations inside values).

### spaCy NER (Functions 30–32)
```
// Named entity recognition — Function: spaCy_Get_Entities
PyTools.spaCy_Get_Entities(ID, TextField, 'debug=false')

// With custom model — Function: spaCy_Get_Entities_From_Model
PyTools.spaCy_Get_Entities_From_Model(ID, TextField, ModelName, 'custom=true')

// Retrain a model — Function: spaCy_Retrain
PyTools.spaCy_Retrain(Text, Entity, EntityType, ModelName, 'base_model=en_core_web_sm,epochs=100,test=0.3')
```
**Kwargs delimiter**: comma.

spaCy returns a table with columns: `key`, `entity`, `start`, `end`, `type`, `description`.

### scikit-learn / XGBoost / LightGBM (Functions 9–29, 34–39, 42)
```
// Setup a model — Function: sklearn_Setup
PyTools.sklearn_Setup(ModelName, EstimatorArgs, ScalerArgs, ExecutionArgs)
// Example:
PyTools.sklearn_Setup('MyModel', 'estimator=RandomForestClassifier,n_estimators=100|int', 'scaler=StandardScaler', 'overwrite=true,test_size=0.3|float')

// Advanced setup with metrics and dim reduction — Function: sklearn_Setup_Adv
PyTools.sklearn_Setup_Adv(ModelName, EstimatorArgs, ScalerArgs, MetricArgs, DimReductionArgs, ExecutionArgs)

// Set features — Function: sklearn_Set_Features
PyTools.sklearn_Set_Features(ModelName, FeatureName, VarType, DataType, Strategy, StrategyArgs)

// Get features — Function: sklearn_Get_Features
PyTools.sklearn_Get_Features(ModelName)

// Train — Function: sklearn_Fit
PyTools.sklearn_Fit(ModelName, Features)

// Predict in chart — Function: sklearn_Predict
PyTools.sklearn_Predict(ModelName, Feature1 & '|' & Feature2 & '|' & Feature3)

// Predict in load script — Function: sklearn_Bulk_Predict
PyTools.sklearn_Bulk_Predict(ModelName, Key, Feature1 & '|' & Feature2 & '|' & Feature3)

// Predict probabilities — Function: sklearn_Predict_Proba
PyTools.sklearn_Predict_Proba(ModelName, Feature1 & '|' & Feature2)

// Predict probabilities (load script) — Function: sklearn_Bulk_Predict_Proba
PyTools.sklearn_Bulk_Predict_Proba(ModelName, Key, Feature1 & '|' & Feature2)

// Get metrics — Function: sklearn_Get_Metrics
PyTools.sklearn_Get_Metrics(ModelName)

// List models — Function: sklearn_List_Models
PyTools.sklearn_List_Models('*')     // or a search pattern

// Get features expression — Function: sklearn_Get_Features_Expression
PyTools.sklearn_Get_Features_Expression(ModelName)

// Feature importance — Function: sklearn_Explain_Importances
PyTools.sklearn_Explain_Importances(ModelName)

// Fit and predict — Function: sklearn_Fit_Predict
PyTools.sklearn_Fit_Predict(ModelName, Features)

// Grid search — Function: sklearn_Set_Param_Grid
PyTools.sklearn_Set_Param_Grid(ModelName, EstimatorArgs, GridSearchArgs)

// Get best params — Function: sklearn_Get_Best_Params
PyTools.sklearn_Get_Best_Params(ModelName)
```

**Kwargs delimiter**: comma. Features use `|` as a column separator (not a kwargs delimiter).

**Keras Deep Learning (Functions 34–35):**
```
// Set model layers — Function: Keras_Set_Layers
PyTools.Keras_Set_Layers(ModelName, SortOrder, LayerType, Args, Kwargs)

// Get training history — Function: Keras_Get_History
PyTools.Keras_Get_History(ModelName)
```

### General Predict (Functions 43–45)
For pre-trained models saved to disk (sklearn, Keras, or REST API):
```
// Predict in chart — Function: Predict
PyTools.Predict(ModelName, Feature1 & '|' & Feature2, 'debug=false')

// Predict in load script — Function: Bulk_Predict
PyTools.Bulk_Predict(ModelName, Key, Feature1 & '|' & Feature2, 'debug=false')

// Get features expression — Function: Get_Features_Expression
PyTools.Get_Features_Expression(ModelName)
```
**Kwargs delimiter**: comma (with `|` for type annotations).

Requires a YAML model definition file in `../models/` describing the model path, type, and features.

### LLM Chat — Azure OpenAI (Functions 46–47)
```
// Chart expression — Function: LLM_Chat
PyTools.LLM_Chat('What is the trend for ' & ProductName & '?', 'system_prompt=You are a data analyst.')

// Load script — Function: LLM_Chat_Bulk
PyTools.LLM_Chat_Bulk(Key, Prompt, 'system_prompt=You are an expert,temperature=0.5,max_tokens=4096')
```

**Kwargs delimiter**: comma.

**LLM Parameters:**
- `system_prompt` — System message for the LLM
- `temperature` — Randomness (default `0.7`, range 0.0–1.0)
- `max_tokens` — Maximum response tokens (default `2048`)
- `debug` — `true`/`false`

**Requires `.env` configuration:**
```
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.2
AZURE_OPENAI_API_VERSION=2025-11-01-preview
```

### Claude Chat — Azure AI Foundry (Functions 48–49)
```
// Chart expression — Function: LLM_Claude_Chat
PyTools.LLM_Claude_Chat('Analyze: ' & Data, 'model=sonnet,system_prompt=You are an analyst.')

// Load script — Function: LLM_Claude_Chat_Bulk
PyTools.LLM_Claude_Chat_Bulk(Key, Prompt, 'model=opus,system_prompt=Be concise.')
```

**Kwargs delimiter**: comma.

**Claude Models**: `haiku`, `sonnet`, `opus` (mapped to env vars `AZURE_CLAUDE_HAIKU`, `AZURE_CLAUDE_SONNET`, `AZURE_CLAUDE_OPUS`)

**Requires `.env` configuration:**
```
AZURE_CLAUDE_API_KEY=your-key
AZURE_CLAUDE_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_CLAUDE_SONNET=claude-sonnet-model-name
AZURE_CLAUDE_HAIKU=claude-haiku-model-name
AZURE_CLAUDE_OPUS=claude-opus-model-name
```

### Firecrawl — Web Scraping, Extraction & Agent (Functions 51–58)
```
// Scrape a URL — Function: Firecrawl_Scrape
PyTools.Firecrawl_Scrape('https://competitor.com/pricing', 'format=markdown')

// Scrape in load script — Function: Firecrawl_Scrape_Bulk
PyTools.Firecrawl_Scrape_Bulk(Key, URL, 'format=markdown|pdf_mode=auto')

// Extract structured data — Function: Firecrawl_Extract
PyTools.Firecrawl_Extract('https://competitor.com/tyres', 'Extract product names and prices', '')

// Extract in load script — Function: Firecrawl_Extract_Bulk
PyTools.Firecrawl_Extract_Bulk(Key, URL, Prompt, '')

// Web search — Function: Firecrawl_Search
PyTools.Firecrawl_Search('truck tyre prices South Africa', 'limit=5|location=South Africa')

// Search in load script — Function: Firecrawl_Search_Bulk
PyTools.Firecrawl_Search_Bulk(Key, Query, 'limit=5')

// Agent research — Function: Firecrawl_Agent
PyTools.Firecrawl_Agent('https://competitor.com', 'Find all tyre products with brand, size, and price', 'model=spark-1-mini|max_credits=200')

// Agent in load script — Function: Firecrawl_Agent_Bulk
PyTools.Firecrawl_Agent_Bulk(Key, URL, Prompt, 'model=spark-1-mini|max_credits=200')
```

**Kwargs delimiter**: pipe or comma (both work).

**Firecrawl Parameters (Scrape):** `format`, `only_main_content`, `timeout`, `pdf_mode`, `pdf_max_pages`
**Firecrawl Parameters (Extract):** `schema`, `enable_web_search`, `llm_provider`, `max_content_chars`
**Firecrawl Parameters (Search):** `limit`, `location`, `tbs`, `scrape_content`
**Firecrawl Parameters (Agent):** `model` (`spark-1-mini`/`spark-1-pro`), `max_credits`, `schema`

**Requires `.env` configuration:**
```
FIRECRAWL_API_KEY=your-firecrawl-api-key
```

> **Note:** Like LLM tests, the test suite verifies that the Firecrawl module **imports correctly** but does not make API calls. Use `test_firecrawl.py` in the project root for live API testing.

---

## Complete Function Reference

All 59 registered SSE functions:

| ID | Function Name | Module | Type |
|----|---------------|--------|------|
| 0 | `Cluster` | Clustering | Scalar |
| 1 | `Cluster_by_Dim` | Clustering | Scalar |
| 2 | `Cluster_Geo` | Clustering | Scalar |
| 3 | `Correlation` | Correlation | Scalar |
| 4 | `Pearson` | Correlation | Scalar |
| 5 | `Prophet` | Prophet | Scalar |
| 6 | `Prophet_Basic` | Prophet | Scalar |
| 7 | `Prophet_Holidays` | Prophet | Scalar |
| 8 | `Prophet_Seasonality` | Prophet | Scalar |
| 9 | `sklearn_Setup` | scikit-learn | Tensor |
| 10 | `sklearn_Set_Features` | scikit-learn | Tensor |
| 11 | `sklearn_Get_Features` | scikit-learn | Tensor |
| 12 | `sklearn_Fit` | scikit-learn | Tensor |
| 13 | `sklearn_Partial_Fit` | scikit-learn | Tensor |
| 14 | `sklearn_Predict` | scikit-learn | Scalar |
| 15 | `sklearn_Bulk_Predict` | scikit-learn | Tensor |
| 16 | `sklearn_Predict_Proba` | scikit-learn | Scalar |
| 17 | `sklearn_Bulk_Predict_Proba` | scikit-learn | Tensor |
| 18 | `sklearn_Get_Metrics` | scikit-learn | Tensor |
| 19 | `sklearn_List_Models` | scikit-learn | Tensor |
| 20 | `sklearn_Get_Features_Expression` | scikit-learn | Tensor |
| 21 | `sklearn_Setup_Adv` | scikit-learn | Tensor |
| 22 | `sklearn_Calculate_Metrics` | scikit-learn | Tensor |
| 23 | `sklearn_Get_Confusion_Matrix` | scikit-learn | Tensor |
| 24 | `sklearn_Set_Param_Grid` | scikit-learn | Tensor |
| 25 | `sklearn_Get_Best_Params` | scikit-learn | Tensor |
| 26 | `sklearn_Fit_Transform` | scikit-learn | Tensor |
| 27 | `sklearn_Fit_Predict` | scikit-learn | Scalar |
| 28 | `sklearn_Bulk_Fit_Predict` | scikit-learn | Scalar |
| 29 | `sklearn_Explain_Importances` | scikit-learn | Tensor |
| 30 | `spaCy_Get_Entities` | spaCy | Tensor |
| 31 | `spaCy_Get_Entities_From_Model` | spaCy | Tensor |
| 32 | `spaCy_Retrain` | spaCy | Tensor |
| 33 | `Association_Rules` | Common | Tensor |
| 34 | `Keras_Set_Layers` | scikit-learn | Tensor |
| 35 | `Keras_Get_History` | scikit-learn | Tensor |
| 36 | `sklearn_Predict_Sequence` | scikit-learn | Tensor |
| 37 | `sklearn_Bulk_Predict_Sequence` | scikit-learn | Tensor |
| 38 | `sklearn_Predict_Proba_Sequence` | scikit-learn | Tensor |
| 39 | `sklearn_Bulk_Predict_Proba_Sequence` | scikit-learn | Tensor |
| 40 | `Prophet_Multivariate` | Prophet | Scalar |
| 41 | `Prophet_Seasonality_Multivariate` | Prophet | Scalar |
| 42 | `sklearn_Calculate_Metrics_Sequence` | scikit-learn | Tensor |
| 43 | `Predict` | Common | Scalar |
| 44 | `Bulk_Predict` | Common | Tensor |
| 45 | `Get_Features_Expression` | Common | Tensor |
| 46 | `LLM_Chat` | LLM | Scalar |
| 47 | `LLM_Chat_Bulk` | LLM | Tensor |
| 48 | `LLM_Claude_Chat` | Claude | Scalar |
| 49 | `LLM_Claude_Chat_Bulk` | Claude | Tensor |
| 50 | `StatsForecast` | StatsForecast | Scalar |
| 51 | `Firecrawl_Scrape` | Firecrawl | Scalar |
| 52 | `Firecrawl_Scrape_Bulk` | Firecrawl | Tensor |
| 53 | `Firecrawl_Extract` | Firecrawl | Scalar |
| 54 | `Firecrawl_Extract_Bulk` | Firecrawl | Tensor |
| 55 | `Firecrawl_Search` | Firecrawl | Scalar |
| 56 | `Firecrawl_Search_Bulk` | Firecrawl | Tensor |
| 57 | `Firecrawl_Agent` | Firecrawl | Scalar |
| 58 | `Firecrawl_Agent_Bulk` | Firecrawl | Tensor |

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `np.NaN was removed` | NumPy 2.0+ | Replace `np.NaN` with `np.nan` |
| `DataFrame has no attribute 'append'` | Pandas 2.0+ | Use `pd.concat()` instead |
| `dictionary update sequence element #0 has length 5` | `arg.split("=")` on values containing `=` | Use `arg.split("=", 1)` |
| `dictionary update sequence element #0 has length 1` | Pipe-delimited args parsed with comma delimiter | Use `\|` auto-detection in parser |
| `Invalid frequency: MS\|periods=3\|...` | kwargs not split — pipe used as delimiter but parser used comma | Parser auto-detects `\|` vs `,` |
| `Length mismatch: Expected axis has N elements, new values have M` | Prophet deduplicates dates internally | Merge forecast back to request dates |
| `IndexError: list index out of range` (StatsForecast) | First request bundle has no rows | Iterate bundles to find first non-empty one |
| `module '_machine_learning' has no attribute 'KerasClassifierForQlik'` | Keras not loaded yet | Initialize stubs as `None` at module level |
| `Missing credentials` (LLM) | Azure API keys not set | Configure `.env` file |
| `Firecrawl API key not configured` | `FIRECRAWL_API_KEY` not in `.env` | Add key to `.env` file |
| `Website Not Supported` (Firecrawl) | Facebook/Instagram blocked | Social media not supported by Firecrawl |
| `Can't find model 'en_core_web_sm'` | spaCy model not downloaded | `python -m spacy download en_core_web_sm` |

---

## Adding New Tests

The test script at `tests/test_all_tools.py` uses mock SSE structures to call modules directly. To add a new test:

```python
def test_my_feature():
    t0 = time.time()
    try:
        # Build SSE request data
        rows_data = []
        for ...:
            duals = [
                SSE.Dual(numData=1.0),          # numeric column
                SSE.Dual(strData="text"),        # string column
            ]
            rows_data.append(duals)
        
        sse_rows = [SSE.Row(duals=d) for d in rows_data]
        request = [SSE.BundledRows(rows=sse_rows)]
        
        # Call the module
        instance = MyClass(request, context)
        result = instance.my_method()
        
        # Assert expected results
        assert len(result) > 0
        
        results.record("My Feature", True, duration=time.time()-t0)
    except Exception as e:
        results.record("My Feature", False, str(e), time.time()-t0)
```

Then add `test_my_feature()` to the `main()` function.
