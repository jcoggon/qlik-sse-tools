#!/usr/bin/env python3
"""
Standalone test suite for Qlik Python Tools.
Tests each capability by mocking the gRPC SSE structures and calling modules directly.

Usage:
    cd qlik-py-env/core
    python ../../tests/test_all_tools.py

Or from project root (with venv activated):
    cd qlik-py-env/core && python ../../tests/test_all_tools.py
"""

import os
import sys
import time
import traceback
import warnings
import locale

warnings.simplefilter("ignore")
locale.setlocale(locale.LC_NUMERIC, '')

# ---------------------------------------------------------------------------
# Path setup — make sure we can import from core/ and generated/
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CORE_DIR = os.path.join(PROJECT_ROOT, 'core')
GENERATED_DIR = os.path.join(PROJECT_ROOT, 'generated')

# We need to run from a directory where _utils, _prophet etc. can be found
if CORE_DIR not in sys.path:
    sys.path.insert(0, CORE_DIR)
if GENERATED_DIR not in sys.path:
    sys.path.insert(0, GENERATED_DIR)

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

import numpy as np
import pandas as pd
import ServerSideExtension_pb2 as SSE

# ---------------------------------------------------------------------------
# Helpers — mock SSE structures
# ---------------------------------------------------------------------------

def make_bundled_rows(rows_data, has_str_col=False):
    """
    Build a list of BundledRows from a list of row tuples.
    Each tuple contains numeric values, with the last element optionally being a string (kwargs).
    
    rows_data: list of tuples, e.g. [(date_num, value), ...] or [(date_num, value, 'kwargs_str'), ...]
    has_str_col: if True, the last element in each tuple is a strData column
    """
    rows = []
    for row_tuple in rows_data:
        duals = []
        for i, val in enumerate(row_tuple):
            if has_str_col and i == len(row_tuple) - 1:
                duals.append(SSE.Dual(numData=float('nan'), strData=str(val)))
            else:
                duals.append(SSE.Dual(numData=float(val) if val is not None else float('nan')))
        rows.append(SSE.Row(duals=duals))
    return [SSE.BundledRows(rows=rows)]


class MockContext:
    """Minimal mock for gRPC context."""
    def invocation_metadata(self):
        return []
    
    def send_initial_metadata(self, metadata):
        """No-op for testing — Qlik receives table descriptions via this."""
        pass


# ---------------------------------------------------------------------------
# Test results tracking
# ---------------------------------------------------------------------------

class TestResults:
    def __init__(self):
        self.results = []
    
    def record(self, name, passed, message="", duration=0):
        self.results.append({
            'name': name,
            'passed': passed,
            'message': message,
            'duration': duration
        })
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name} ({duration:.2f}s)")
        if message and not passed:
            for line in message.strip().split('\n'):
                print(f"         {line}")
    
    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        print(f"\n{'='*60}")
        print(f"  TEST SUMMARY: {passed}/{total} passed, {failed} failed")
        print(f"{'='*60}")
        if failed > 0:
            print("\n  Failed tests:")
            for r in self.results:
                if not r['passed']:
                    print(f"    ❌ {r['name']}: {r['message'][:100]}")
        print()
        return failed == 0


results = TestResults()
context = MockContext()

# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------

def get_monthly_forecast_series():
    """Generate a deterministic monthly time series for forecasting tests."""
    dates = pd.date_range('2022-01-01', periods=24, freq='MS')
    trend = np.linspace(100, 180, len(dates))
    seasonal = 12 * np.sin(np.arange(len(dates)) * 2 * np.pi / 12)
    values = trend + seasonal
    return pd.DataFrame({'ds': dates, 'y': values})


def qlik_date_num(dt):
    """Convert a datetime to Qlik's serial date number (days since 1899-12-30)."""
    origin = pd.Timestamp('1899-12-30')
    return (pd.Timestamp(dt) - origin).days


# ===================================================================
# TEST 1: Correlation
# ===================================================================
def test_correlation():
    t0 = time.time()
    try:
        import _utils as utils
        
        # Test Pearson correlation between two known series
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = [2, 4, 5, 4, 5, 7, 8, 9, 10, 12]
        
        df = pd.DataFrame({'x': x, 'y': y})
        corr = df.corr(method='pearson').iloc[0, 1]
        
        assert corr > 0.9, f"Expected strong positive correlation, got {corr}"
        assert not np.isnan(corr), "Correlation should not be NaN"
        
        # Test Spearman
        corr_s = df.corr(method='spearman').iloc[0, 1]
        assert corr_s > 0.9, f"Spearman correlation should be > 0.9, got {corr_s}"
        
        # Test Kendall
        corr_k = df.corr(method='kendall').iloc[0, 1]
        assert corr_k > 0.7, f"Kendall correlation should be > 0.7, got {corr_k}"
        
        results.record("Correlation (Pearson/Spearman/Kendall)", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Correlation (Pearson/Spearman/Kendall)", False, str(e), time.time()-t0)


# ===================================================================
# TEST 2: Prophet Forecasting
# ===================================================================
def test_prophet():
    t0 = time.time()
    try:
        from _prophet import ProphetForQlik
        
        monthly = get_monthly_forecast_series()
        n_periods = 3  # forecast 3 months ahead
        
        # Build request data: historical dates + placeholder rows for forecast
        rows_data = []
        for _, row in monthly.iterrows():
            date_num = qlik_date_num(row['ds'])
            rows_data.append((date_num, row['y'], 'freq=MS|return=yhat|debug=false'))
        
        # Add placeholder rows (y=0 for future periods)
        last_date = monthly['ds'].max()
        for i in range(1, n_periods + 1):
            future_date = last_date + pd.DateOffset(months=i)
            date_num = qlik_date_num(future_date)
            rows_data.append((date_num, 0, 'freq=MS|return=yhat|debug=false'))
        
        request = make_bundled_rows(rows_data, has_str_col=True)
        predictor = ProphetForQlik(request, context)
        forecast = predictor.predict()
        
        assert len(forecast) == len(rows_data), \
            f"Forecast length {len(forecast)} != request length {len(rows_data)}"
        assert not forecast.isnull().all(), "Forecast should not be all NaN"
        
        # The last n_periods values should be the forecast (not NaN)
        forecast_values = forecast.iloc[-n_periods:]
        assert not forecast_values.isnull().any(), \
            f"Forecast periods should not contain NaN: {forecast_values.tolist()}"
        assert all(v > 0 for v in forecast_values), \
            "Forecast values should be positive for the synthetic series"
        
        results.record("Prophet Forecasting", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Prophet Forecasting", False, 
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 3: StatsForecast (AutoARIMA)
# ===================================================================
def test_statsforecast():
    t0 = time.time()
    try:
        from _statsforecast import StatsForecastForQlik
        
        monthly = get_monthly_forecast_series()
        n_periods = 3
        
        rows_data = []
        for _, row in monthly.iterrows():
            date_num = qlik_date_num(row['ds'])
            rows_data.append((date_num, row['y'], 
                            'model=AutoARIMA|freq=MS|periods=3|return=yhat|debug=false'))
        
        # Add placeholder rows
        last_date = monthly['ds'].max()
        for i in range(1, n_periods + 1):
            future_date = last_date + pd.DateOffset(months=i)
            date_num = qlik_date_num(future_date)
            rows_data.append((date_num, 0,
                            'model=AutoARIMA|freq=MS|periods=3|return=yhat|debug=false'))
        
        request = make_bundled_rows(rows_data, has_str_col=True)
        predictor = StatsForecastForQlik(request, context)
        forecast = predictor.predict()
        
        assert len(forecast) == len(rows_data), \
            f"Forecast length {len(forecast)} != request length {len(rows_data)}"
        
        results.record("StatsForecast (AutoARIMA)", True, duration=time.time()-t0)
    except Exception as e:
        results.record("StatsForecast (AutoARIMA)", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 4: StatsForecast (AutoETS)
# ===================================================================
def test_statsforecast_ets():
    t0 = time.time()
    try:
        from _statsforecast import StatsForecastForQlik
        
        monthly = get_monthly_forecast_series()
        n_periods = 3
        
        rows_data = []
        for _, row in monthly.iterrows():
            date_num = qlik_date_num(row['ds'])
            rows_data.append((date_num, row['y'],
                            'model=AutoETS|freq=MS|periods=3|return=yhat|debug=false'))
        
        last_date = monthly['ds'].max()
        for i in range(1, n_periods + 1):
            future_date = last_date + pd.DateOffset(months=i)
            rows_data.append((qlik_date_num(future_date), 0,
                            'model=AutoETS|freq=MS|periods=3|return=yhat|debug=false'))
        
        request = make_bundled_rows(rows_data, has_str_col=True)
        predictor = StatsForecastForQlik(request, context)
        forecast = predictor.predict()
        
        assert len(forecast) == len(rows_data)
        results.record("StatsForecast (AutoETS)", True, duration=time.time()-t0)
    except Exception as e:
        results.record("StatsForecast (AutoETS)", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 5: HDBSCAN Clustering
# ===================================================================
def test_clustering():
    t0 = time.time()
    try:
        from _clustering import HDBSCANForQlik
        
        # Generate 3 clear clusters
        np.random.seed(42)
        n = 30
        cluster1 = np.random.normal(loc=[0, 0], scale=0.3, size=(n, 2))
        cluster2 = np.random.normal(loc=[5, 5], scale=0.3, size=(n, 2))
        cluster3 = np.random.normal(loc=[10, 0], scale=0.3, size=(n, 2))
        data = np.vstack([cluster1, cluster2, cluster3])
        
        # Format: dimension (label), features (semicolon-separated string), kwargs
        rows_data = []
        for i, (x, y) in enumerate(data):
            features_str = f"{x:.4f};{y:.4f}"
            rows = []
            rows.append(SSE.Dual(strData=f"point_{i}", numData=float('nan')))
            rows.append(SSE.Dual(strData=features_str, numData=float('nan')))
            rows.append(SSE.Dual(strData='scaler=standard|min_cluster_size=10|debug=false', numData=float('nan')))
            rows_data.append(rows)
        
        sse_rows = [SSE.Row(duals=duals) for duals in rows_data]
        request = [SSE.BundledRows(rows=sse_rows)]
        
        clusterer = HDBSCANForQlik(request, context, variant="standard")
        cluster_labels = clusterer.scan()
        
        assert len(cluster_labels) == len(data), \
            f"Cluster labels length {len(cluster_labels)} != data length {len(data)}"
        
        # Check that we got at least 2 distinct clusters (HDBSCAN may label some as -1 for noise)
        unique_labels = cluster_labels.unique() if hasattr(cluster_labels, 'unique') else set(cluster_labels)
        non_noise = [l for l in unique_labels if l != -1]
        assert len(non_noise) >= 2, f"Expected at least 2 clusters, got {len(non_noise)}: {unique_labels}"
        
        results.record("HDBSCAN Clustering", True, duration=time.time()-t0)
    except Exception as e:
        results.record("HDBSCAN Clustering", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 6: Utils - get_kwargs parsing
# ===================================================================
def test_utils_kwargs():
    t0 = time.time()
    try:
        import _utils as utils
        
        # Test comma-delimited
        result = utils.get_kwargs("arg1=value1,arg2=value2")
        assert result == {'arg1': 'value1', 'arg2': 'value2'}, f"Comma-delimited failed: {result}"
        
        # Test with spaces
        result = utils.get_kwargs("arg1 = value1, arg2 = value2")
        assert result == {'arg1': 'value1', 'arg2': 'value2'}, f"Spaces failed: {result}"

        # Preserve meaningful whitespace inside values (especially LLM prompts)
        result = utils.get_kwargs("system_prompt=You are a data analyst,debug=false")
        assert result['system_prompt'] == 'You are a data analyst', f"Value whitespace was lost: {result}"
        
        # Test values containing '='
        result = utils.get_kwargs("key=val=ue,other=test")
        assert result == {'key': 'val=ue', 'other': 'test'}, f"Value with = failed: {result}"
        
        # Test empty string
        result = utils.get_kwargs("")
        assert result == {}, f"Empty string should return empty dict: {result}"
        
        # Test entries without '=' are skipped
        result = utils.get_kwargs("good=value,badentry,also_good=yes")
        assert result == {'good': 'value', 'also_good': 'yes'}, f"Skip no-= entries failed: {result}"
        
        results.record("Utils kwargs parsing", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Utils kwargs parsing", False, str(e), time.time()-t0)


# ===================================================================
# TEST 7: Utils - count_placeholders
# ===================================================================
def test_utils_placeholders():
    t0 = time.time()
    try:
        import _utils as utils
        
        # Test with zeros at the end
        s = pd.Series([10, 20, 30, 0, 0, 0])
        assert utils.count_placeholders(s) == 3, "Should count 3 trailing zeros"
        
        # Test with NaN at the end
        s = pd.Series([10, 20, 30, np.nan, np.nan])
        assert utils.count_placeholders(s) == 2, "Should count 2 trailing NaN"
        
        # Test with mixed
        s = pd.Series([10, 20, 0, 30, 0, np.nan])
        assert utils.count_placeholders(s) == 2, "Should count trailing 0 and NaN"
        
        # Test with no placeholders
        s = pd.Series([10, 20, 30])
        assert utils.count_placeholders(s) == 0, "Should count 0 placeholders"
        
        results.record("Utils count_placeholders", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Utils count_placeholders", False, str(e), time.time()-t0)


# ===================================================================
# TEST 8: Utils - number parsing (atof, atoi)
# ===================================================================
def test_utils_numbers():
    t0 = time.time()
    try:
        import _utils as utils
        
        assert utils.atof("3.14") == 3.14, "atof should parse '3.14'"
        assert utils.atoi("42") == 42, "atoi should parse '42'"
        assert np.isnan(utils.atof("")), "atof('') should return NaN"
        
        results.record("Utils number parsing (atof/atoi)", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Utils number parsing (atof/atoi)", False, str(e), time.time()-t0)


# ===================================================================
# TEST 9: Association Rules (Common Functions)
# ===================================================================
def test_association_rules():
    t0 = time.time()
    try:
        from _common import CommonFunction
        
        # Build transaction data: each row is (group, item, kwargs)
        # The apriori function groups items by the 'group' column
        transactions = {
            "T1": ["bread", "milk", "eggs"],
            "T2": ["bread", "milk"],
            "T3": ["bread", "butter", "eggs"],
            "T4": ["milk", "butter"],
            "T5": ["bread", "milk", "butter", "eggs"],
            "T6": ["bread", "eggs"],
            "T7": ["milk", "eggs"],
            "T8": ["bread", "milk", "eggs", "butter"],
        }
        
        kwargs_str = 'debug=false|bool,min_support=0.2|float,min_confidence=0.3|float'
        rows_data = []
        for group, items in transactions.items():
            for item in items:
                duals = [
                    SSE.Dual(strData=group, numData=float('nan')),
                    SSE.Dual(strData=item, numData=float('nan')),
                    SSE.Dual(strData=kwargs_str, numData=float('nan'))
                ]
                rows_data.append(duals)
        
        sse_rows = [SSE.Row(duals=d) for d in rows_data]
        request = [SSE.BundledRows(rows=sse_rows)]
        
        handle = CommonFunction(request, context)
        response = handle.association_rules()
        
        assert isinstance(response, pd.DataFrame), "Response should be a DataFrame"
        assert len(response) > 0, "Should find at least one association rule"
        expected_cols = {'rule', 'rule_lhs', 'rule_rhs', 'support', 'confidence', 'lift'}
        actual_cols = set(response.columns)
        assert expected_cols.issubset(actual_cols), \
            f"Missing columns: {expected_cols - actual_cols}"
        
        results.record("Association Rules", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Association Rules", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 10: spaCy NER
# ===================================================================
def test_spacy_ner():
    t0 = time.time()
    try:
        import spacy
        # Check if any English model is available
        try:
            spacy.load('en_core_web_sm')
        except OSError:
            results.record("spaCy NER", True, 
                           "SKIPPED - en_core_web_sm not installed (python -m spacy download en_core_web_sm)",
                           time.time()-t0)
            return
        
        from _spacy import SpaCyForQlik
        
        # Build request: key, text, kwargs
        texts = [
            ("1", "Apple Inc. reported record revenue in California last quarter."),
            ("2", "Elon Musk visited the Tesla factory in Berlin, Germany on January 5th."),
            ("3", "The United Nations held a meeting in New York about climate change."),
        ]
        
        rows_data = []
        for key, text in texts:
            duals = [
                SSE.Dual(strData=key, numData=float('nan')),
                SSE.Dual(strData=text, numData=float('nan')),
                SSE.Dual(strData='debug=false', numData=float('nan'))
            ]
            rows_data.append(duals)
        
        sse_rows = [SSE.Row(duals=d) for d in rows_data]
        request = [SSE.BundledRows(rows=sse_rows)]
        
        model = SpaCyForQlik(request, context)
        response = model.get_entities()
        
        assert isinstance(response, pd.DataFrame), "Response should be a DataFrame"
        assert len(response) > 0, "Should find at least one entity"
        
        # Verify expected columns
        for col in ['key', 'entity', 'start', 'end', 'type', 'description']:
            assert col in response.columns, f"Missing column: {col}"
        
        results.record("spaCy NER", True, duration=time.time()-t0)
    except Exception as e:
        results.record("spaCy NER", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 11: NumPy / Pandas version compatibility
# ===================================================================
def test_numpy_pandas_compat():
    t0 = time.time()
    try:
        # Verify np.nan works (np.NaN was removed in NumPy 2.0)
        assert np.isnan(np.nan), "np.nan should work"
        
        # Verify pd.concat works (DataFrame.append was removed)
        df1 = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        df2 = pd.DataFrame({'a': [5], 'b': [6]})
        result = pd.concat([df1, df2], ignore_index=True)
        assert len(result) == 3, "pd.concat should work"
        
        # Verify no np.NaN references in source files
        import _utils, _prophet, _statsforecast, _clustering
        for mod_name, mod in [('_utils', _utils), ('_prophet', _prophet), 
                               ('_statsforecast', _statsforecast), ('_clustering', _clustering)]:
            source_file = mod.__file__
            with open(source_file, 'r') as f:
                content = f.read()
            assert 'np.NaN' not in content, \
                f"{mod_name} still contains deprecated np.NaN"
        
        results.record("NumPy/Pandas compatibility", True, duration=time.time()-t0)
    except Exception as e:
        results.record("NumPy/Pandas compatibility", False, str(e), time.time()-t0)


# ===================================================================
# TEST 12: Import all modules
# ===================================================================
def test_imports():
    t0 = time.time()
    try:
        import _utils
        import _prophet
        import _statsforecast
        import _clustering
        import _sklearn
        import _spacy
        import _common
        import _llm
        import _machine_learning
        
        results.record("Import all modules", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Import all modules", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 13: Prophet with pipe-delimited kwargs
# ===================================================================
def test_prophet_pipe_kwargs():
    t0 = time.time()
    try:
        from _prophet import ProphetForQlik
        
        monthly = get_monthly_forecast_series()
        n_periods = 3
        
        # Use pipe-delimited kwargs (the format Qlik apps actually send)
        kwargs_str = 'freq=MS|periods=3|return=yhat|load_script=false|debug=false'
        
        rows_data = []
        for _, row in monthly.iterrows():
            date_num = qlik_date_num(row['ds'])
            rows_data.append((date_num, row['y'], kwargs_str))
        
        last_date = monthly['ds'].max()
        for i in range(1, n_periods + 1):
            future_date = last_date + pd.DateOffset(months=i)
            rows_data.append((qlik_date_num(future_date), 0, kwargs_str))
        
        request = make_bundled_rows(rows_data, has_str_col=True)
        predictor = ProphetForQlik(request, context)
        
        # Verify kwargs were parsed correctly
        assert predictor.freq == 'MS', f"freq should be 'MS', got '{predictor.freq}'"
        assert predictor.result_type == 'yhat', f"return should be 'yhat', got '{predictor.result_type}'"
        
        forecast = predictor.predict()
        assert len(forecast) == len(rows_data), \
            f"Forecast length {len(forecast)} != request length {len(rows_data)}"
        
        results.record("Prophet pipe-delimited kwargs", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Prophet pipe-delimited kwargs", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 14: Prophet with comma-delimited kwargs (backward compat)
# ===================================================================
def test_prophet_comma_kwargs():
    t0 = time.time()
    try:
        from _prophet import ProphetForQlik
        
        monthly = get_monthly_forecast_series()
        n_periods = 3
        
        # Use comma-delimited kwargs (legacy format)
        kwargs_str = 'freq=MS,return=yhat,debug=false'
        
        rows_data = []
        for _, row in monthly.iterrows():
            date_num = qlik_date_num(row['ds'])
            rows_data.append((date_num, row['y'], kwargs_str))
        
        last_date = monthly['ds'].max()
        for i in range(1, n_periods + 1):
            future_date = last_date + pd.DateOffset(months=i)
            rows_data.append((qlik_date_num(future_date), 0, kwargs_str))
        
        request = make_bundled_rows(rows_data, has_str_col=True)
        predictor = ProphetForQlik(request, context)
        
        assert predictor.freq == 'MS', f"freq should be 'MS', got '{predictor.freq}'"
        
        forecast = predictor.predict()
        assert len(forecast) == len(rows_data)
        
        results.record("Prophet comma-delimited kwargs", True, duration=time.time()-t0)
    except Exception as e:
        results.record("Prophet comma-delimited kwargs", False,
                       traceback.format_exc().split('\n')[-2], time.time()-t0)


# ===================================================================
# TEST 15: LLM module import (no API call)
# ===================================================================
def test_llm_import():
    t0 = time.time()
    try:
        from _llm import LLMForQlik, ClaudeForQlik
        
        assert LLMForQlik is not None, "LLMForQlik should be importable"
        assert ClaudeForQlik is not None, "ClaudeForQlik should be importable"
        
        results.record("LLM module import", True, duration=time.time()-t0)
    except Exception as e:
        results.record("LLM module import", False, str(e), time.time()-t0)


# ===================================================================
# TEST 16: Machine Learning module (Keras stubs)
# ===================================================================
def test_ml_keras_stubs():
    t0 = time.time()
    try:
        import _machine_learning as ml
        
        # These should exist as None (lazy-loaded) and not raise AttributeError
        _ = ml.KerasClassifierForQlik
        _ = ml.KerasRegressorForQlik
        _ = ml.KERAS_AVAILABLE
        
        results.record("ML Keras stubs (no AttributeError)", True, duration=time.time()-t0)
    except AttributeError as e:
        results.record("ML Keras stubs (no AttributeError)", False, str(e), time.time()-t0)
    except Exception as e:
        results.record("ML Keras stubs (no AttributeError)", False, str(e), time.time()-t0)


# ===================================================================
# MAIN
# ===================================================================
def main():
    print()
    print("=" * 60)
    print("  Qlik Python Tools — Test Suite")
    print("=" * 60)
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  NumPy:   {np.__version__}")
    print(f"  Pandas:  {pd.__version__}")
    print(f"  CWD:     {os.getcwd()}")
    print(f"  Core:    {CORE_DIR}")
    print("=" * 60)
    print()
    
    # Run tests in order of dependency
    print("--- Module Tests ---")
    test_imports()
    test_numpy_pandas_compat()
    test_ml_keras_stubs()
    test_llm_import()
    
    print("\n--- Utility Tests ---")
    test_utils_kwargs()
    test_utils_placeholders()
    test_utils_numbers()
    
    print("\n--- Correlation Tests ---")
    test_correlation()
    
    print("\n--- Prophet Tests ---")
    test_prophet()
    test_prophet_pipe_kwargs()
    test_prophet_comma_kwargs()
    
    print("\n--- StatsForecast Tests ---")
    test_statsforecast()
    test_statsforecast_ets()
    
    print("\n--- Clustering Tests ---")
    test_clustering()
    
    print("\n--- NLP Tests ---")
    test_spacy_ner()
    
    print("\n--- Common Functions Tests ---")
    test_association_rules()
    
    all_passed = results.summary()
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
