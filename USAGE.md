# Qlik Python Tools — SSE Function Reference (v3.0.0)

> **Server-Side Extension (SSE)** for Qlik Sense client-managed.
> Extends Qlik's expression library with Python-powered machine learning, forecasting, NLP, and LLM capabilities.

---

## Table of Contents

- [Setup](#setup)
- [Connection Configuration in Qlik](#connection-configuration-in-qlik)
- [Function Types](#function-types)
- [1. Clustering (HDBSCAN)](#1-clustering-hdbscan)
- [2. Correlation](#2-correlation)
- [3. Time Series Forecasting (Prophet)](#3-time-series-forecasting-prophet)
- [4. Machine Learning (scikit-learn / XGBoost / LightGBM / Keras)](#4-machine-learning-scikit-learn--xgboost--lightgbm--keras)
- [5. Natural Language Processing (spaCy)](#5-natural-language-processing-spacy)
- [6. Association Rules](#6-association-rules)
- [7. General Predict (sklearn / Keras / REST)](#7-general-predict-sklearn--keras--rest)
- [8. LLM — Azure OpenAI (GPT)](#8-llm--azure-openai-gpt)
- [9. LLM — Azure AI Foundry (Claude)](#9-llm--azure-ai-foundry-claude)
- [10. Web Scraping & Document Parsing (Firecrawl)](#10-web-scraping--document-parsing-firecrawl)
- [Environment Variables (.env)](#environment-variables-env)
- [Keyword Arguments (kwargs)](#keyword-arguments-kwargs)
- [Available Estimators](#available-estimators)

---

## Setup

### Windows (Customer Server)

```bat
:: 1. Create your .env file from the template
copy .env.example .env
:: 2. Edit .env with your actual credentials
:: 3. Initialize the environment
Qlik-Py-Init.bat
:: 4. Start the SSE
Qlik-Py-Start.bat
```

### macOS (Testing)

```bash
# 1. Create your .env file from the template
cp .env.example .env
# 2. Edit .env with your actual credentials
# 3. Initialize the environment
./Qlik-Py-Init.sh
# 4. Start the SSE
./Qlik-Py-Start.sh
```

---

## Connection Configuration in Qlik

In Qlik Sense (Client-Managed), configure the analytic connection in the QMC:

| Setting | Value |
|---------|-------|
| **Name** | `PythonSSE` (or any name — this becomes `<AAI>` below) |
| **Host** | `localhost` |
| **Port** | `50055` |

After configuring, all functions are called as:

- **Chart expression**: `<AAI>.FunctionName(param1, param2, ...)`
- **Load script**: `EXTENSION <AAI>.FunctionName(TableName{field1, field2, ...})`

Replace `<AAI>` with your analytic connection name throughout this document.

---

## Function Types

| Type | Code | Description | Used In |
|------|------|-------------|---------|
| **Scalar** | `0` | One output row per input row | Chart expressions |
| **Aggregation** | `1` | All rows aggregated to a single value | Chart expressions |
| **Tensor** | `2` | Multiple rows in, multiple rows out | Load script (reload) |

---

## 1. Clustering (HDBSCAN)

Density-based clustering that automatically determines the number of clusters.

### Cluster (ID: 0) — Scalar

Cluster rows based on numeric features.

**Chart expression:**
```
<AAI>.Cluster(dimension, feature1 & '|' & feature2, 'arg1=val1|arg2=val2')
```

**Example:**
```
<AAI>.Cluster(ProductID, Sales & '|' & Margin & '|' & Turnover, 'min_cluster_size=5')
```

### Cluster_by_Dim (ID: 1) — Scalar

Cluster a measure grouped by two dimensions (e.g. pivot-style).

**Chart expression:**
```
<AAI>.Cluster_by_Dim(Dimension1, Dimension2, Measure, 'kwargs')
```

**Example:**
```
<AAI>.Cluster_by_Dim(Customer, Product, Sum(Sales), 'min_cluster_size=3')
```

### Cluster_Geo (ID: 2) — Scalar

Cluster geographic data using latitude and longitude.

**Chart expression:**
```
<AAI>.Cluster_Geo(LocationID, Latitude, Longitude, 'min_cluster_size=10')
```

---

## 2. Correlation

### Correlation (ID: 3) — Scalar

Calculate the correlation between two series with a specified method.

**Chart expression:**
```
<AAI>.Correlation(Series1, Series2, 'pearson')
```

Correlation types: `pearson`, `kendall`, `spearman`

### Pearson (ID: 4) — Scalar

Shortcut for Pearson correlation.

**Chart expression:**
```
<AAI>.Pearson(Series1, Series2)
```

---

## 3. Time Series Forecasting (Prophet)

Uses Facebook/Meta Prophet for time series forecasting. Ideal for demand forecasting with seasonality.

### Prophet (ID: 5) — Scalar

Forecast a time series with optional arguments.

**Chart expression:**
```
<AAI>.Prophet(Date, Value, 'arg1=val1|arg2=val2')
```

**Example — Stock reorder forecasting:**
```
<AAI>.Prophet(
    OrderDate,
    Sum(Quantity),
    'freq=D|periods=30|return=yhat|debug=true'
)
```

**Common kwargs:**
- `freq` — Frequency: `D` (daily), `W` (weekly), `M` (monthly)
- `periods` — Number of future periods to forecast
- `return` — What to return: `yhat`, `trend`, `seasonal`, `yhat_lower`, `yhat_upper`, `y_then_yhat`, `residual`, `all`
- `take_log` — `true` to apply log transform
- `debug` — `true` for execution logs

### Prophet_Basic (ID: 6) — Scalar

Simplified Prophet with no optional arguments (uses defaults).

```
<AAI>.Prophet_Basic(Date, Value)
```

### Prophet_Holidays (ID: 7) — Scalar

Prophet with holiday effects.

```
<AAI>.Prophet_Holidays(Date, Value, HolidayName, 'freq=D|periods=30')
```

### Prophet_Seasonality (ID: 8) — Scalar

Return seasonality components from the Prophet model.

```
<AAI>.Prophet_Seasonality(SeasonName, TimeSeries, Holidays, 'kwargs')
```

### Prophet_Multivariate (ID: 40) — Scalar

Prophet with additional regressors (external variables).

```
<AAI>.Prophet_Multivariate(Date, Value, Holidays, RegressorValues, RegressorArgs, 'kwargs')
```

**Example — Forecast with promotion effects:**
```
<AAI>.Prophet_Multivariate(
    OrderDate,
    Sum(Quantity),
    HolidayName,
    IsPromotion & '|' & Temperature,
    'prior_scale=10|mode=additive',
    'freq=D|periods=30|return=yhat'
)
```

### Prophet_Seasonality_Multivariate (ID: 41) — Scalar

Seasonality decomposition for multivariate Prophet.

```
<AAI>.Prophet_Seasonality_Multivariate(SeasonName, TimeSeries, Holidays, Regressors, RegressorArgs, 'kwargs')
```

---

## 4. Machine Learning (scikit-learn / XGBoost / LightGBM / Keras)

Full ML pipeline: setup → define features → train → predict. Models are persisted to disk.

### Workflow Overview

```
1. sklearn_Setup / sklearn_Setup_Adv     → Create & configure model
2. sklearn_Set_Features                   → Define feature columns
3. Keras_Set_Layers (optional)            → Define neural network architecture
4. sklearn_Fit                            → Train the model
5. sklearn_Predict / sklearn_Bulk_Predict → Get predictions
6. sklearn_Get_Metrics                    → Evaluate performance
```

### sklearn_Setup (ID: 9) — Tensor (Load Script)

Create and configure a model.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Setup(Setup{
    model_name, estimator_args, scaler_args, execution_args
});
```

**Example — XGBoost regressor for demand prediction:**
```qlik
Setup:
LOAD * INLINE [
    model_name, estimator_args, scaler_args, execution_args
    demand_model, estimator=XGBRegressor|n_estimators=100|learning_rate=0.1|max_depth=6, scaler=StandardScaler, test_size=0.2|debug=true
];

Result:
LOAD * EXTENSION <AAI>.sklearn_Setup(Setup{model_name, estimator_args, scaler_args, execution_args});
```

### sklearn_Setup_Adv (ID: 21) — Tensor (Load Script)

Advanced setup with metric selection and dimensionality reduction.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Setup_Adv(Setup{
    model_name, estimator_args, scaler_args, metric_args, dim_reduction_args, execution_args
});
```

### sklearn_Set_Features (ID: 10) — Tensor (Load Script)

Define feature columns and their types.

```qlik
Features:
LOAD * INLINE [
    model_name, feature_name, var_type, data_type, strategy, strategy_args
    demand_model, DayOfWeek, feature, int, one_hot_encoding,
    demand_model, Month, feature, int, one_hot_encoding,
    demand_model, AvgPrice, feature, float, none,
    demand_model, IsPromotion, feature, int, none,
    demand_model, Quantity, target, float, none,
];

LOAD * EXTENSION <AAI>.sklearn_Set_Features(Features{
    model_name, feature_name, var_type, data_type, strategy, strategy_args
});
```

**var_type values:** `feature`, `target`, `identifier`, `excluded`
**data_type values:** `int`, `float`, `str`
**strategy values:** `none`, `one_hot_encoding`, `hashing`, `text_similarity`, `count_vectorizing`, `tf_idf`

### sklearn_Get_Features (ID: 11) — Tensor (Load Script)

Retrieve the feature definitions for a model.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Get_Features(Params{model_name});
```

### sklearn_Fit (ID: 12) — Tensor (Load Script)

Train the model with data.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Fit(TrainingData{model_name, feature1, feature2, ..., target});
```

**Example:**
```qlik
LOAD * EXTENSION <AAI>.sklearn_Fit(TrainingData{
    model_name, DayOfWeek, Month, AvgPrice, IsPromotion, Quantity
});
```

### sklearn_Partial_Fit (ID: 13) — Tensor (Load Script)

Incrementally train the model with new data (for estimators that support it).

```qlik
LOAD * EXTENSION <AAI>.sklearn_Partial_Fit(NewData{model_name, feature1, feature2, ..., target});
```

### sklearn_Predict (ID: 14) — Scalar (Chart Expression)

Get predictions in a chart expression.

```
<AAI>.sklearn_Predict('demand_model', DayOfWeek & '|' & Month & '|' & AvgPrice & '|' & IsPromotion)
```

### sklearn_Bulk_Predict (ID: 15) — Tensor (Load Script)

Get predictions for a batch of data during reload.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Bulk_Predict(PredictionData{
    model_name, key, feature1, feature2, ...
});
```

### sklearn_Predict_Proba (ID: 16) — Scalar (Chart Expression)

Get prediction probabilities for classifiers.

```
<AAI>.sklearn_Predict_Proba('stockout_classifier', Feature1 & '|' & Feature2)
```

### sklearn_Bulk_Predict_Proba (ID: 17) — Tensor (Load Script)

Bulk prediction probabilities during reload.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Bulk_Predict_Proba(Data{model_name, key, feature1, feature2, ...});
```

### sklearn_Fit_Predict (ID: 27) — Scalar (Chart Expression)

Fit and predict in one step (for clustering estimators).

```
<AAI>.sklearn_Fit_Predict('kmeans_model', Feature1 & '|' & Feature2)
```

### sklearn_Bulk_Fit_Predict (ID: 28) — Scalar (Chart Expression)

Bulk fit and predict in one step.

```
<AAI>.sklearn_Bulk_Fit_Predict('kmeans_model', Key & '|' & Feature1 & '|' & Feature2)
```

### sklearn_Fit_Transform (ID: 26) — Tensor (Load Script)

Fit and transform data (for decomposition like PCA).

```qlik
LOAD * EXTENSION <AAI>.sklearn_Fit_Transform(Data{model_name, key, feature1, feature2, ...});
```

### sklearn_Get_Metrics (ID: 18) — Tensor (Load Script)

Retrieve evaluation metrics after training.

```qlik
Metrics:
LOAD * EXTENSION <AAI>.sklearn_Get_Metrics(Params{model_name});
```

### sklearn_Calculate_Metrics (ID: 22) — Tensor (Load Script)

Calculate metrics on new data.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Calculate_Metrics(TestData{model_name, feature1, ..., target});
```

### sklearn_Get_Confusion_Matrix (ID: 23) — Tensor (Load Script)

Get the confusion matrix for a classifier.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Get_Confusion_Matrix(Params{model_name});
```

### sklearn_Set_Param_Grid (ID: 24) — Tensor (Load Script)

Set up a hyperparameter grid for grid search.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Set_Param_Grid(Grid{model_name, estimator_args, grid_search_args});
```

### sklearn_Get_Best_Params (ID: 25) — Tensor (Load Script)

Get the best parameters from grid search.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Get_Best_Params(Params{model_name});
```

### sklearn_Explain_Importances (ID: 29) — Tensor (Load Script)

Get feature importances for the model.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Explain_Importances(Params{model_name});
```

### sklearn_List_Models (ID: 19) — Tensor (Load Script)

List all saved models matching a pattern.

```qlik
LOAD * EXTENSION <AAI>.sklearn_List_Models(Params{search_pattern});
```

### sklearn_Get_Features_Expression (ID: 20) — Tensor (Load Script)

Get the Qlik expression needed to call sklearn_Predict for a model.

```qlik
LOAD * EXTENSION <AAI>.sklearn_Get_Features_Expression(Params{model_name});
```

### Sequence Prediction Functions

For time-series / sequential models:

| ID | Name | Type | Description |
|----|------|------|-------------|
| 36 | `sklearn_Predict_Sequence` | Tensor | Predict sequences (load script) |
| 37 | `sklearn_Bulk_Predict_Sequence` | Tensor | Bulk sequence prediction |
| 38 | `sklearn_Predict_Proba_Sequence` | Tensor | Sequence probability prediction |
| 39 | `sklearn_Bulk_Predict_Proba_Sequence` | Tensor | Bulk sequence probability prediction |
| 42 | `sklearn_Calculate_Metrics_Sequence` | Tensor | Metrics for sequence models |

All take: `model_name, key, feature1, feature2, ...`

```qlik
LOAD * EXTENSION <AAI>.sklearn_Predict_Sequence(Data{model_name, key, feature1, feature2, ...});
```

### Keras Neural Network Functions

### Keras_Set_Layers (ID: 34) — Tensor (Load Script)

Define the architecture of a Keras Sequential neural network.

```qlik
Architecture:
LOAD * INLINE [
    model_name, sort_order, layer_type, args, kwargs
    demand_nn, 1, Dense, [64], input_shape=(10,)|activation=relu
    demand_nn, 2, Dropout, [0.3],
    demand_nn, 3, Dense, [32], activation=relu
    demand_nn, 4, Dense, [1], activation=linear
    demand_nn, 5, Compilation, , loss=mse|optimizer=adam
];

LOAD * EXTENSION <AAI>.Keras_Set_Layers(Architecture{
    model_name, sort_order, layer_type, args, kwargs
});
```

### Keras_Get_History (ID: 35) — Tensor (Load Script)

Get training history (loss per epoch) for a Keras model.

```qlik
LOAD * EXTENSION <AAI>.Keras_Get_History(Params{model_name});
```

---

## 5. Natural Language Processing (spaCy)

Named Entity Recognition (NER) using spaCy v3.

### spaCy_Get_Entities (ID: 30) — Tensor (Load Script)

Extract named entities from text using the default model (`en_core_web_sm`).

```qlik
LOAD * EXTENSION <AAI>.spaCy_Get_Entities(TextData{key, text, kwargs});
```

**Example:**
```qlik
Entities:
LOAD key, text, entity, entity_type, start, end
EXTENSION <AAI>.spaCy_Get_Entities(Documents{DocID, DocText, ''});
```

### spaCy_Get_Entities_From_Model (ID: 31) — Tensor (Load Script)

Extract entities using a custom trained model.

```qlik
LOAD * EXTENSION <AAI>.spaCy_Get_Entities_From_Model(TextData{key, text, model_name, kwargs});
```

### spaCy_Retrain (ID: 32) — Tensor (Load Script)

Retrain a spaCy NER model with custom training data.

```qlik
LOAD * EXTENSION <AAI>.spaCy_Retrain(TrainData{text, entity, entity_type, model_name, kwargs});
```

**kwargs for retraining:**
- `base_model` — Base model to start from (default: `en_core_web_sm`)
- `blank` — `true` to start from a blank model
- `epochs` — Number of training epochs (default: `100`)
- `batch_size` — Batch size or compound/decay schedule (e.g. `4.0;32.0;1.001`)
- `drop` — Dropout rate (default: `0.25`)
- `test` — Ratio of data to hold out for testing (e.g. `0.2`)
- `debug` — `true` for execution logs

---

## 6. Association Rules

### Association_Rules (ID: 33) — Tensor (Load Script)

Mine association rules (market basket analysis).

```qlik
LOAD * EXTENSION <AAI>.Association_Rules(Transactions{group, item, kwargs});
```

**Example — Find products frequently ordered together:**
```qlik
Rules:
LOAD group, item, rule, support, confidence, lift
EXTENSION <AAI>.Association_Rules(Orders{OrderID, ProductName, 'min_support=0.01|min_confidence=0.2'});
```

---

## 7. General Predict (sklearn / Keras / REST)

Unified prediction interface that can call sklearn models, Keras models, or REST endpoints.

### Predict (ID: 43) — Scalar (Chart Expression)

```
<AAI>.Predict('model_name', Feature1 & '|' & Feature2, 'arg1=val1')
```

**kwargs:**
- `load_script` — `true` if called from load script
- `model_type` — `sklearn`, `keras`, or `rest`
- For REST: `endpoint`, `json`, `response` kwargs

### Bulk_Predict (ID: 44) — Tensor (Load Script)

```qlik
LOAD * EXTENSION <AAI>.Bulk_Predict(Data{model_name, key, feature1, feature2, ..., kwargs});
```

### Get_Features_Expression (ID: 45) — Tensor (Load Script)

Get the Qlik expression for calling Predict with a model.

```qlik
LOAD * EXTENSION <AAI>.Get_Features_Expression(Params{model_name});
```

---

## 8. LLM — Azure OpenAI (GPT)

Send prompts to Azure OpenAI GPT models and get responses back in Qlik.

### LLM_Chat (ID: 46) — Scalar (Chart Expression)

Send a prompt per row, get a response string.

```
<AAI>.LLM_Chat(
    'What reorder quantity do you recommend for ' & ProductName & ' given current stock ' & StockLevel & '?',
    'system_prompt=You are an inventory management expert.|temperature=0.3|max_tokens=500'
)
```

**Practical examples:**

```
// Summarize sales data per product
<AAI>.LLM_Chat(
    'Summarize this sales trend: ' & concat(DISTINCT MonthYear & ':' & Sum(Sales), '; '),
    'system_prompt=You are a retail analyst. Be concise.'
)

// Generate product descriptions
<AAI>.LLM_Chat(
    'Write a 50-word product description for: ' & ProductName & '. Category: ' & Category,
    'temperature=0.8|max_tokens=200'
)

// Classify customer feedback
<AAI>.LLM_Chat(
    'Classify this feedback as Positive, Negative, or Neutral: ' & FeedbackText,
    'system_prompt=Respond with only one word: Positive, Negative, or Neutral.|temperature=0'
)
```

### LLM_Chat_Bulk (ID: 47) — Tensor (Load Script)

Send prompts in bulk during reload. Returns key, prompt, and response columns.

```qlik
// Prepare prompts
Prompts:
LOAD
    ProductID as key,
    'Analyze demand pattern and suggest reorder point for product ' & ProductName
        & '. Average daily sales: ' & Avg(DailySales)
        & '. Lead time: ' & LeadTimeDays & ' days.'
        & '. Current stock: ' & CurrentStock as prompt,
    'system_prompt=You are a supply chain analyst. Return only a JSON with reorder_point and reorder_quantity.' as kwargs
RESIDENT Products;

// Call the LLM
LLM_Results:
LOAD key, prompt, response
EXTENSION <AAI>.LLM_Chat_Bulk(Prompts{key, prompt, kwargs});
```

**kwargs:**

| Kwarg | Default | Description |
|-------|---------|-------------|
| `system_prompt` | *(none)* | System message to set LLM behavior |
| `temperature` | `0.7` | 0.0 = deterministic, 1.0 = creative |
| `max_tokens` | `2048` | Maximum response length |
| `debug` | `false` | Set `true` for execution logs |

Kwargs are pipe-separated: `system_prompt=You are an expert.|temperature=0.3|max_tokens=500`

---

## 9. LLM — Azure AI Foundry (Claude)

Send prompts to Anthropic Claude models (Haiku, Opus, Sonnet) via Azure AI Foundry.

### LLM_Claude_Chat (ID: 48) — Scalar (Chart Expression)

```
<AAI>.LLM_Claude_Chat(
    'Analyze this inventory data and recommend actions: ' & InventorySummary,
    'model=sonnet|system_prompt=You are a supply chain optimization expert.|temperature=0.3'
)
```

**Model selection:**

| Kwarg Value | Model | Best For |
|-------------|-------|----------|
| `model=haiku` | Claude Haiku 4.5 | Fast, cheap — classification, simple Q&A |
| `model=sonnet` | Claude Sonnet 4.5 | **Default** — balanced speed/quality |
| `model=opus` | Claude Opus 4.5 | Best quality — complex analysis |

**Examples:**

```
// Quick classification with Haiku (fast & cheap)
<AAI>.LLM_Claude_Chat(
    'Is this product at risk of stockout? Stock: ' & Stock & ', Avg Daily Sales: ' & AvgSales & ', Lead Time: ' & LeadTime & ' days. Answer YES or NO.',
    'model=haiku|temperature=0'
)

// Deep analysis with Opus
<AAI>.LLM_Claude_Chat(
    'Perform root cause analysis on why ' & ProductName & ' had ' & StockoutDays & ' stockout days last quarter. Historical data: ' & SalesHistory,
    'model=opus|system_prompt=You are a senior supply chain consultant.|max_tokens=4096'
)
```

### LLM_Claude_Chat_Bulk (ID: 49) — Tensor (Load Script)

Bulk Claude processing during reload.

```qlik
// Prepare prompts
ClaudePrompts:
LOAD
    ProductID as key,
    'Given: Product=' & ProductName & ', Category=' & Category
        & ', AvgDailySales=' & Round(Avg(DailySales), 0.1)
        & ', LeadTimeDays=' & LeadTime
        & ', SafetyStockDays=' & SafetyDays
        & '. Calculate the optimal reorder point and economic order quantity.'
        as prompt,
    'model=sonnet|system_prompt=You are an inventory optimization AI. Return JSON: {"reorder_point": N, "eoq": N, "reasoning": "..."}|temperature=0.2'
        as kwargs
RESIDENT Products;

// Call Claude
ClaudeResults:
LOAD key, prompt, response
EXTENSION <AAI>.LLM_Claude_Chat_Bulk(ClaudePrompts{key, prompt, kwargs});
```

**kwargs (same as GPT, plus `model`):**

| Kwarg | Default | Description |
|-------|---------|-------------|
| `model` | `sonnet` | Claude model: `haiku`, `opus`, `sonnet` |
| `system_prompt` | *(none)* | System message |
| `temperature` | `0.7` | 0.0 = deterministic, 1.0 = creative |
| `max_tokens` | `2048` | Maximum response length |
| `debug` | `false` | Set `true` for execution logs |

---

## 10. Web Scraping & Document Parsing (Firecrawl)

Scrape webpages, parse documents (PDF, Excel, Word), extract structured data, and search the web.
Supports both **remote URLs** (via the [Firecrawl](https://firecrawl.dev) API) and **local files** (parsed locally).

**Requirements:**
- `FIRECRAWL_API_KEY` in `.env` (required for remote URLs and web search)
- Local file parsing works without an API key (uses `pdfplumber`, `pandas`, `python-docx`)

### Firecrawl_Scrape (ID: 51) — Scalar (Chart Expression)

Scrape a URL or parse a local file. Returns content as markdown text.

```
// Scrape a competitor webpage
<AAI>.Firecrawl_Scrape(
    'https://competitor.com/pricing',
    'format=markdown'
)

// Parse a remote PDF catalogue (auto mode — text with OCR fallback)
<AAI>.Firecrawl_Scrape(
    'https://competitor.com/catalogue.pdf',
    'format=markdown'
)

// Force OCR on a scanned PDF price list
<AAI>.Firecrawl_Scrape(
    'https://competitor.com/pricelist.pdf',
    'format=markdown|pdf_mode=ocr'
)

// Parse a local PDF file
<AAI>.Firecrawl_Scrape(
    'C:\Data\competitor_pricelist.pdf',
    'format=markdown'
)

// Parse a local Excel spreadsheet
<AAI>.Firecrawl_Scrape(
    '/data/prices.xlsx',
    ''
)
```

### Firecrawl_Scrape_Bulk (ID: 52) — Tensor (Load Script)

Scrape multiple URLs or files during reload. Returns key, source, and content columns.

```qlik
// Prepare sources
Sources:
LOAD
    CompetitorID as key,
    CompetitorURL as source,
    'format=markdown|pdf_mode=auto' as kwargs
RESIDENT Competitors;

// Scrape all sources
ScrapedContent:
LOAD key, source, content
EXTENSION <AAI>.Firecrawl_Scrape_Bulk(Sources{key, source, kwargs});
```

### Firecrawl_Extract (ID: 53) — Scalar (Chart Expression)

Extract structured data from a URL or local file using a natural language prompt. Returns a JSON string.

```
// Extract pricing from a competitor webpage
<AAI>.Firecrawl_Extract(
    'https://competitor.com/tyres',
    'Extract all tyre product names, sizes, and prices as a JSON array',
    'enable_web_search=true'
)

// Extract from a remote PDF catalogue with OCR
<AAI>.Firecrawl_Extract(
    'https://competitor.com/catalogue.pdf',
    'Extract all product names and prices',
    'pdf_mode=ocr'
)

// Extract from a local PDF (uses LLM for structured extraction)
<AAI>.Firecrawl_Extract(
    'C:\Data\catalogue.pdf',
    'Extract product names, sizes, and prices',
    'llm_provider=openai'
)

// Extract from a local Word document
<AAI>.Firecrawl_Extract(
    '/data/competitor_report.docx',
    'Extract all pricing information',
    'llm_provider=claude'
)
```

### Firecrawl_Extract_Bulk (ID: 54) — Tensor (Load Script)

Extract structured data from multiple URLs or files during reload.

```qlik
// Prepare extraction tasks
ExtractTasks:
LOAD
    CompetitorID as key,
    CompetitorURL as source,
    'Extract product name, price, and availability as JSON' as prompt,
    'enable_web_search=false' as kwargs
RESIDENT Competitors;

// Run extraction
ExtractedData:
LOAD key, source, extracted
EXTENSION <AAI>.Firecrawl_Extract_Bulk(ExtractTasks{key, source, prompt, kwargs});
```

### Firecrawl_Search (ID: 55) — Scalar (Chart Expression)

Search the web and return results as a JSON string.

```
// Search for competitor pricing
<AAI>.Firecrawl_Search(
    'auto truck tyre pricing South Africa 2026',
    'limit=5'
)

// Search with content scraping (returns full page content with results)
<AAI>.Firecrawl_Search(
    'competitor tyre prices wholesale',
    'limit=3|scrape_content=true'
)
```

### Firecrawl_Search_Bulk (ID: 56) — Tensor (Load Script)

Bulk web search during reload.

```qlik
// Prepare search queries
Queries:
LOAD
    QueryID as key,
    SearchTerm as query,
    'limit=5|location=South Africa' as kwargs
RESIDENT SearchTerms;

// Run searches
SearchResults:
LOAD key, query, results
EXTENSION <AAI>.Firecrawl_Search_Bulk(Queries{key, query, kwargs});
```

### Firecrawl_Agent (ID: 57) — Scalar (Chart Expression)

Run a Firecrawl Agent to autonomously research and extract data from websites.
The agent searches, navigates, and gathers data — no need to know the exact pages.
Optionally provide a URL to focus the agent on a specific site; leave empty for open research.

```
// Research a competitor site for pricing data
<AAI>.Firecrawl_Agent(
    'https://www.fundityres.co.za',
    'Find all 315/80R22.5 truck tyre products with brand, price, and availability',
    'model=spark-1-mini|max_credits=100'
)

// Open research — no URL needed
<AAI>.Firecrawl_Agent(
    '',
    'Find truck tyre pricing from South African online retailers for size 315/80R22.5',
    'model=spark-1-pro|max_credits=500'
)

// Multiple URLs — semicolon separated
<AAI>.Firecrawl_Agent(
    'https://tyrebox.co.za;https://shortysgroup.co.za',
    'Compare truck tyre prices across these two retailers',
    'max_credits=200'
)
```

### Firecrawl_Agent_Bulk (ID: 58) — Tensor (Load Script)

Run agent research tasks in bulk during reload.

```qlik
// Prepare agent tasks per competitor
AgentTasks:
LOAD
    CompetitorID as key,
    CompetitorURL as source,
    'Find all truck tyre products with brand, size, price, and stock status' as prompt,
    'model=spark-1-mini|max_credits=100' as kwargs
RESIDENT Competitors;

// Run agent research
AgentResults:
LOAD key, source, result
EXTENSION <AAI>.Firecrawl_Agent_Bulk(AgentTasks{key, source, prompt, kwargs});
```

### Firecrawl kwargs

| Kwarg | Default | Applies To | Description |
|-------|---------|------------|-------------|
| `format` | `markdown` | Scrape | Output format: `markdown`, `html`, `summary`, `links` |
| `only_main_content` | *(auto)* | Scrape | `true` to strip navigation/footer |
| `timeout` | *(default)* | Scrape | Request timeout in milliseconds |
| `pdf_mode` | `auto` | Scrape, Extract | PDF parsing: `auto`, `fast` (text-only), `ocr` (force OCR) |
| `pdf_max_pages` | *(all)* | Scrape, Extract | Maximum PDF pages to process |
| `enable_web_search` | `false` | Extract | Allow Firecrawl to follow links outside the domain |
| `schema` | *(none)* | Extract | JSON schema string for structured output |
| `llm_provider` | `openai` | Extract (local) | LLM for local file extraction: `openai`, `claude` |
| `max_content_chars` | `50000` | Extract (local) | Max characters sent to LLM |
| `limit` | *(default)* | Search | Maximum number of search results |
| `location` | *(auto)* | Search | Location for search (e.g., `South Africa`, `Germany`) |
| `tbs` | *(none)* | Search | Time filter: `qdr:d` (24h), `qdr:w` (week), `qdr:m` (month) |
| `scrape_content` | `false` | Search | Also scrape full content from search results |
| `model` | `spark-1-mini` | Agent | Agent model: `spark-1-mini` (cheap) or `spark-1-pro` (accurate) |
| `max_credits` | `2500` | Agent | Maximum credits to spend on the agent task |
| `debug` | `false` | All | Set `true` for execution logs |

### Supported document types

| Type | Remote (URL) | Local File | How |
|------|:---:|:---:|-----|
| Webpages | Yes | — | Firecrawl API (JS rendering, anti-bot) |
| PDF | Yes | Yes | Remote: Firecrawl (OCR capable). Local: `pdfplumber` |
| Excel (.xlsx, .xls) | Yes | Yes | Remote: Firecrawl. Local: `pandas` + `openpyxl` |
| Word (.docx) | Yes | Yes | Remote: Firecrawl. Local: `python-docx` |
| CSV, TXT | — | Yes | Built-in Python |

---

## Environment Variables (.env)

Create a `.env` file in the project root (copy from `.env.example`):

```env
# Azure OpenAI (GPT models)
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-11-01-preview

# Azure AI Foundry (Claude models)
AZURE_FOUNDRY_API_KEY=your-foundry-key
AZURE_FOUNDRY_API_VERSION=2024-05-01-preview
AZURE_CLAUDE_HAIKU=claude-haiku-4-5
AZURE_CLAUDE_OPUS=claude-opus-4-5
AZURE_CLAUDE_SONNET=claude-sonnet-4-5
AZURE_FOUNDRY_CLAUDE_API_ENDPOINT=https://your-resource.openai.azure.com/anthropic

# Firecrawl (Web Scraping & Document Parsing)
FIRECRAWL_API_KEY=your-firecrawl-api-key
```

The `.env` file is automatically loaded at SSE startup and is gitignored for security.

---

## Keyword Arguments (kwargs)

All functions that accept a `kwargs` / `other_args` parameter use the same format:

```
'key1=value1|key2=value2|key3=value3'
```

**Pipe `|` is the delimiter.** Example:

```
'system_prompt=You are an expert.|temperature=0.3|max_tokens=1000|debug=true'
```

---

## Available Estimators

All of these can be passed as `estimator=Name` in `sklearn_Setup`:

### Classifiers

| Estimator | Package | Best For |
|-----------|---------|----------|
| `XGBClassifier` | XGBoost | **Top pick for tabular classification** |
| `LGBMClassifier` | LightGBM | **Fast on large datasets, handles categoricals** |
| `RandomForestClassifier` | sklearn | Robust general-purpose |
| `GradientBoostingClassifier` | sklearn | Good accuracy, slower than XGB/LGBM |
| `AdaBoostClassifier` | sklearn | Boosting with weak learners |
| `ExtraTreesClassifier` | sklearn | Fast, good for feature selection |
| `LogisticRegression` | sklearn | Linear, interpretable |
| `SVC` | sklearn | Support vector machines |
| `KNeighborsClassifier` | sklearn | Instance-based |
| `MLPClassifier` | sklearn | Simple neural network |
| `DecisionTreeClassifier` | sklearn | Interpretable, single tree |
| `KerasClassifier` | scikeras | Custom neural network |
| `BaggingClassifier` | sklearn | Ensemble bagging |
| `GaussianNB` | sklearn | Naive Bayes |
| `BernoulliNB` | sklearn | Naive Bayes for binary features |
| `MultinomialNB` | sklearn | Naive Bayes for count data |
| `SGDClassifier` | sklearn | Stochastic gradient descent |
| `Perceptron` | sklearn | Linear classifier |
| `RidgeClassifier` | sklearn | Ridge regularized |
| `PassiveAggressiveClassifier` | sklearn | Online learning |
| `LinearSVC` | sklearn | Linear SVM |
| `NuSVC` | sklearn | Nu-SVM |
| `XGBRFClassifier` | XGBoost | Random forest via XGBoost |

### Regressors

| Estimator | Package | Best For |
|-----------|---------|----------|
| `XGBRegressor` | XGBoost | **Top pick for tabular regression (demand forecasting)** |
| `LGBMRegressor` | LightGBM | **Fast, great for many SKUs** |
| `RandomForestRegressor` | sklearn | Robust general-purpose |
| `GradientBoostingRegressor` | sklearn | Good accuracy |
| `LinearRegression` | sklearn | Simple linear model |
| `Ridge` / `RidgeCV` | sklearn | L2 regularized |
| `Lasso` / `LassoCV` | sklearn | L1 regularized (feature selection) |
| `ElasticNet` / `ElasticNetCV` | sklearn | L1+L2 regularized |
| `SVR` | sklearn | Support vector regression |
| `KNeighborsRegressor` | sklearn | Instance-based |
| `MLPRegressor` | sklearn | Simple neural network |
| `DecisionTreeRegressor` | sklearn | Interpretable, single tree |
| `KerasRegressor` | scikeras | Custom neural network |
| `AdaBoostRegressor` | sklearn | Boosting |
| `ExtraTreesRegressor` | sklearn | Fast ensemble |
| `BaggingRegressor` | sklearn | Ensemble bagging |
| `SGDRegressor` | sklearn | Stochastic gradient descent |
| `BayesianRidge` | sklearn | Bayesian linear |
| `ARDRegression` | sklearn | Automatic relevance determination |
| `HuberRegressor` | sklearn | Robust to outliers |
| `RANSACRegressor` | sklearn | Robust to outliers |
| `TheilSenRegressor` | sklearn | Robust to outliers |
| `XGBRFRegressor` | XGBoost | Random forest via XGBoost |

### Clustering (via sklearn_Fit_Predict)

`KMeans`, `MiniBatchKMeans`, `DBSCAN`, `AffinityPropagation`, `AgglomerativeClustering`, `Birch`, `MeanShift`, `SpectralClustering`, `FeatureAgglomeration`

### Dimensionality Reduction (via sklearn_Fit_Transform)

`PCA`, `KernelPCA`, `IncrementalPCA`, `TruncatedSVD`, `FactorAnalysis`, `FastICA`, `NMF`, `SparsePCA`, `DictionaryLearning`, `LatentDirichletAllocation`, `MiniBatchDictionaryLearning`, `MiniBatchSparsePCA`

---

## Quick Reference — All Functions

| ID | Function Name | Type | Category |
|----|--------------|------|----------|
| 0 | `Cluster` | Scalar | Clustering |
| 1 | `Cluster_by_Dim` | Scalar | Clustering |
| 2 | `Cluster_Geo` | Scalar | Clustering |
| 3 | `Correlation` | Scalar | Statistics |
| 4 | `Pearson` | Scalar | Statistics |
| 5 | `Prophet` | Scalar | Forecasting |
| 6 | `Prophet_Basic` | Scalar | Forecasting |
| 7 | `Prophet_Holidays` | Scalar | Forecasting |
| 8 | `Prophet_Seasonality` | Scalar | Forecasting |
| 9 | `sklearn_Setup` | Tensor | ML Setup |
| 10 | `sklearn_Set_Features` | Tensor | ML Setup |
| 11 | `sklearn_Get_Features` | Tensor | ML Info |
| 12 | `sklearn_Fit` | Tensor | ML Training |
| 13 | `sklearn_Partial_Fit` | Tensor | ML Training |
| 14 | `sklearn_Predict` | Scalar | ML Prediction |
| 15 | `sklearn_Bulk_Predict` | Tensor | ML Prediction |
| 16 | `sklearn_Predict_Proba` | Scalar | ML Prediction |
| 17 | `sklearn_Bulk_Predict_Proba` | Tensor | ML Prediction |
| 18 | `sklearn_Get_Metrics` | Tensor | ML Evaluation |
| 19 | `sklearn_List_Models` | Tensor | ML Info |
| 20 | `sklearn_Get_Features_Expression` | Tensor | ML Info |
| 21 | `sklearn_Setup_Adv` | Tensor | ML Setup |
| 22 | `sklearn_Calculate_Metrics` | Tensor | ML Evaluation |
| 23 | `sklearn_Get_Confusion_Matrix` | Tensor | ML Evaluation |
| 24 | `sklearn_Set_Param_Grid` | Tensor | ML Tuning |
| 25 | `sklearn_Get_Best_Params` | Tensor | ML Tuning |
| 26 | `sklearn_Fit_Transform` | Tensor | ML Transform |
| 27 | `sklearn_Fit_Predict` | Scalar | ML Prediction |
| 28 | `sklearn_Bulk_Fit_Predict` | Scalar | ML Prediction |
| 29 | `sklearn_Explain_Importances` | Tensor | ML Evaluation |
| 30 | `spaCy_Get_Entities` | Tensor | NLP |
| 31 | `spaCy_Get_Entities_From_Model` | Tensor | NLP |
| 32 | `spaCy_Retrain` | Tensor | NLP |
| 33 | `Association_Rules` | Tensor | Mining |
| 34 | `Keras_Set_Layers` | Tensor | Deep Learning |
| 35 | `Keras_Get_History` | Tensor | Deep Learning |
| 36 | `sklearn_Predict_Sequence` | Tensor | ML Prediction |
| 37 | `sklearn_Bulk_Predict_Sequence` | Tensor | ML Prediction |
| 38 | `sklearn_Predict_Proba_Sequence` | Tensor | ML Prediction |
| 39 | `sklearn_Bulk_Predict_Proba_Sequence` | Tensor | ML Prediction |
| 40 | `Prophet_Multivariate` | Scalar | Forecasting |
| 41 | `Prophet_Seasonality_Multivariate` | Scalar | Forecasting |
| 42 | `sklearn_Calculate_Metrics_Sequence` | Tensor | ML Evaluation |
| 43 | `Predict` | Scalar | General Predict |
| 44 | `Bulk_Predict` | Tensor | General Predict |
| 45 | `Get_Features_Expression` | Tensor | General Predict |
| 46 | `LLM_Chat` | Scalar | LLM (GPT) |
| 47 | `LLM_Chat_Bulk` | Tensor | LLM (GPT) |
| 48 | `LLM_Claude_Chat` | Scalar | LLM (Claude) |
| 49 | `LLM_Claude_Chat_Bulk` | Tensor | LLM (Claude) |

---

## Stock Reorder Example — End-to-End

Here's a complete example combining multiple SSE functions for a stock reorder project:

### 1. Forecast demand with Prophet (Chart Expression)

```
// 30-day demand forecast per product
<AAI>.Prophet(
    OrderDate,
    Sum(Quantity),
    'freq=D|periods=30|return=yhat'
)
```

### 2. Train an XGBoost reorder model (Load Script)

```qlik
// Setup
Setup:
LOAD * INLINE [
    model_name, estimator_args, scaler_args, execution_args
    reorder_model, estimator=XGBRegressor|n_estimators=200|learning_rate=0.05|max_depth=8, scaler=RobustScaler, test_size=0.2|random_state=42
];
LOAD * EXTENSION <AAI>.sklearn_Setup(Setup{model_name, estimator_args, scaler_args, execution_args});

// Features
Features:
LOAD * INLINE [
    model_name, feature_name, var_type, data_type, strategy, strategy_args
    reorder_model, AvgDailySales, feature, float, none,
    reorder_model, SalesVariance, feature, float, none,
    reorder_model, LeadTimeDays, feature, int, none,
    reorder_model, Category, feature, str, one_hot_encoding,
    reorder_model, DayOfWeek, feature, int, one_hot_encoding,
    reorder_model, Month, feature, int, one_hot_encoding,
    reorder_model, ReorderQty, target, float, none,
];
LOAD * EXTENSION <AAI>.sklearn_Set_Features(Features{model_name, feature_name, var_type, data_type, strategy, strategy_args});

// Train
LOAD * EXTENSION <AAI>.sklearn_Fit(TrainingData{model_name, AvgDailySales, SalesVariance, LeadTimeDays, Category, DayOfWeek, Month, ReorderQty});
```

### 3. Predict reorder quantities (Chart Expression)

```
<AAI>.sklearn_Predict(
    'reorder_model',
    AvgDailySales & '|' & SalesVariance & '|' & LeadTimeDays & '|' & Category & '|' & DayOfWeek & '|' & Month
)
```

### 4. Use Claude for reorder recommendations (Chart Expression)

```
<AAI>.LLM_Claude_Chat(
    'Product: ' & ProductName
    & '. Predicted demand: ' & Round(PredictedDemand, 1) & ' units/day'
    & '. Current stock: ' & CurrentStock
    & '. Lead time: ' & LeadTime & ' days'
    & '. Recommend: reorder point, reorder quantity, and safety stock.',
    'model=haiku|system_prompt=You are a supply chain AI. Return a brief JSON response.|temperature=0'
)
```

### 5. Cluster products by demand pattern (Chart Expression)

```
<AAI>.Cluster(
    ProductID,
    AvgDailySales & '|' & SalesVariance & '|' & SeasonalityIndex,
    'min_cluster_size=5'
)
```
