import os
import sys
import warnings
import numpy as np
import pandas as pd
try:
    import ServerSideExtension_pb2 as SSE
except ModuleNotFoundError:
    from generated import ServerSideExtension_pb2 as SSE

# Suppress warnings
if not sys.warnoptions:
    warnings.simplefilter("ignore")

from statsforecast import StatsForecast
from statsforecast.models import (
    AutoARIMA, AutoETS, AutoTheta, AutoCES,
    MSTL, SeasonalNaive, Naive, HistoricAverage,
    WindowAverage, SeasonalWindowAverage,
    ADIDA, CrostonClassic, CrostonOptimized, CrostonSBA, IMAPA, TSB
)

# Add Generated folder to module path.
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PARENT_DIR, 'generated'))

# Map of model name strings to statsforecast model classes
MODEL_MAP = {
    # Automatic model selection
    'autoarima': AutoARIMA,
    'autoets': AutoETS,
    'autotheta': AutoTheta,
    'autoces': AutoCES,
    # Decomposition
    'mstl': MSTL,
    # Baseline models
    'naive': Naive,
    'seasonalnaive': SeasonalNaive,
    'historicaverage': HistoricAverage,
    'windowaverage': WindowAverage,
    'seasonalwindowaverage': SeasonalWindowAverage,
    # Intermittent demand (stock/inventory)
    'adida': ADIDA,
    'crostonclassic': CrostonClassic,
    'crostonoptimized': CrostonOptimized,
    'crostonsba': CrostonSBA,
    'imapa': IMAPA,
    'tsb': TSB,
}

REQUIRES_SEASON_LENGTH = {'mstl', 'seasonalnaive', 'seasonalwindowaverage'}


def build_statsforecast_model(model_name, season_length=None, model_kwargs=None):
    """Build a validated StatsForecast model for SSE and REST callers."""
    normalized = model_name.lower()
    model_class = MODEL_MAP.get(normalized)
    if model_class is None:
        raise ValueError(
            f"Unknown model '{model_name}'. Available models: {', '.join(sorted(MODEL_MAP.keys()))}"
        )
    params = dict(model_kwargs or {})
    if season_length is not None:
        params['season_length'] = season_length
    if normalized in REQUIRES_SEASON_LENGTH and season_length is None:
        raise ValueError(
            f"Model '{model_name}' requires season_length (for example 12 for monthly or 7 for daily)"
        )
    try:
        return model_class(**params)
    except TypeError as exc:
        raise ValueError(f"Invalid parameters for {model_class.__name__}: {exc}") from exc


class StatsForecastForQlik:
    """
    A class to provide Nixtla StatsForecast functions for Qlik.
    Supports AutoARIMA, AutoETS, AutoTheta, MSTL, intermittent demand models, and more.
    Significantly faster than Prophet for most statistical forecasting tasks.
    """

    # Counter used to name log files for instances of the class
    log_no = 0

    # Qlik date epoch
    qlik_cal_start = pd.Timestamp('1899-12-30')
    qlik_cal_unit = 'D'

    def __init__(self, request, context):
        """
        Class initializer.
        :param request: an iterable sequence of RowData
        :param context: gRPC context
        """
        self.request = request
        self.context = context

        # Create a Pandas DataFrame with columns ds (date) and y (value)
        self.request_df = pd.DataFrame(
            [(row.duals[0].numData, row.duals[1].numData)
             for request_rows in self.request
             for row in request_rows.rows],
            columns=['ds', 'y']
        )

        # Handle null value rows
        self.NaT_df = self.request_df.loc[self.request_df.ds.isnull()].copy()
        if len(self.NaT_df) > 0:
            self.NaT_df.loc[:, 'y'] = 0
            self.request_df = self.request_df.loc[self.request_df.ds.notnull()]

        # Parse parameters from the third column
        self._set_params()

        # Convert Qlik serial dates to datetime
        self.request_df['ds'] = pd.to_datetime(
            self.request_df['ds'],
            unit=self.qlik_cal_unit,
            origin=self.qlik_cal_start
        )

        # Sort by date
        self.request_df = self.request_df.sort_values('ds')
        self.request_index = self.request_df.loc[:, 'ds']

        # Separate historical data from forecast horizon placeholders
        self.input_df = self.request_df.iloc[:-self.periods].copy()
        self.input_df = self.input_df.reset_index(drop=True)

        if self.debug:
            self._print_log(1)

    def _set_params(self):
        """
        Parse keyword arguments from the request.
        Expected format in third column: 'model=AutoARIMA, freq=MS, periods=12, return=yhat, debug=false'
        """
        # Get the number of columns in the request by finding the first non-empty bundle
        first_row = None
        for bundle in self.request:
            if len(bundle.rows) > 0:
                first_row = bundle.rows[0]
                break

        if first_row is not None:
            cols = len(first_row.duals)
        else:
            cols = 2

        # The last column contains the keyword arguments
        if cols > 2 and first_row is not None:
            args_str = first_row.duals[cols - 1].strData
        else:
            args_str = ''

        # Parse the argument string into a dictionary
        # Support both pipe-delimited (Prophet/sklearn style) and comma-delimited formats
        self.kwargs = {}
        if args_str:
            # Auto-detect delimiter: use pipe if present, otherwise comma
            delimiter = '|' if '|' in args_str else ','
            for pair in args_str.split(delimiter):
                pair = pair.strip()
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    self.kwargs[key.strip().lower()] = value.strip()

        # Extract known parameters with defaults
        self.model_name = self.kwargs.pop('model', 'AutoARIMA').lower()
        self.freq = self.kwargs.pop('freq', 'MS')
        self.periods = int(self.kwargs.pop('periods', '12'))
        self.return_type = self.kwargs.pop('return', 'yhat')
        self.debug = self.kwargs.pop('debug', 'false').lower() == 'true'
        self.take_log = self.kwargs.pop('take_log', 'false').lower() == 'true'
        self.level = self.kwargs.pop('level', '95')
        self.season_length = self.kwargs.pop('season_length', None)
        self.n_jobs = int(self.kwargs.pop('n_jobs', '1'))

        # Parse confidence level(s)
        try:
            self.level = [int(x.strip()) for x in self.level.split(';')]
        except ValueError:
            self.level = [95]

        # Parse season_length if provided
        if self.season_length is not None:
            try:
                self.season_length = int(self.season_length)
            except ValueError:
                self.season_length = None

        # Parse any remaining kwargs as model parameters
        self.model_kwargs = {}
        for key, value in self.kwargs.items():
            try:
                self.model_kwargs[key] = int(value)
            except ValueError:
                try:
                    self.model_kwargs[key] = float(value)
                except ValueError:
                    self.model_kwargs[key] = value

    def predict(self):
        """
        Run the forecast and return results.
        """
        # Check minimum data requirement
        if len(self.input_df) < 2:
            return pd.Series([np.nan] * (len(self.request_df) + len(self.NaT_df)))

        # Apply log transform if requested
        if self.take_log:
            self.input_df.loc[:, 'y'] = np.log(self.input_df.loc[:, 'y'].clip(lower=1e-10))

        sf_df = self._to_statsforecast_frame(self.input_df)
        model_instance = self._build_model()

        # Create the StatsForecast object
        sf = StatsForecast(
            models=[model_instance],
            freq=self.freq,
            n_jobs=self.n_jobs
        )

        # Fit and predict
        sf.fit(sf_df)
        forecast_df = sf.predict(h=self.periods, level=self.level)

        if self.debug:
            self._print_log(2, forecast_df)

        # Map return type to column name
        result = self._extract_result(forecast_df)

        # Reverse log transform if applied
        if self.take_log:
            result = np.exp(result)

        # Build the full response matching the request length
        # Historical values + forecast values
        historical = self.input_df['y'].values
        if self.take_log:
            # Already reversed above, but historical was transformed
            historical = np.exp(historical)

        response = self._build_response(historical, result)

        return response

    def _to_statsforecast_frame(self, frame):
        sf_df = frame[['ds', 'y']].copy()
        sf_df.insert(0, 'unique_id', 'series_1')
        return sf_df

    def _build_model(self):
        return build_statsforecast_model(
            self.model_name,
            season_length=self.season_length,
            model_kwargs=self.model_kwargs,
        )

    def forecast_table(self):
        """Return future timestamps, point forecasts, and calibrated/native intervals."""
        if len(self.input_df) < 2:
            raise ValueError('At least two historical rows are required for interval forecasting')
        sf_df = self._to_statsforecast_frame(self.input_df)
        sf = StatsForecast(models=[self._build_model()], freq=self.freq, n_jobs=self.n_jobs)
        forecast = sf.forecast(df=sf_df, h=self.periods, level=self.level)
        model_col = MODEL_MAP[self.model_name].__name__
        level = self.level[0]
        lo_col = f'{model_col}-lo-{level}'
        hi_col = f'{model_col}-hi-{level}'
        if lo_col not in forecast or hi_col not in forecast:
            raise ValueError(f"Model {model_col} did not return {level}% prediction intervals")
        result = forecast[['ds', model_col, lo_col, hi_col]].copy()
        result.columns = ['date', 'forecast', 'lower', 'upper']
        if self.take_log:
            result[['forecast', 'lower', 'upper']] = np.exp(result[['forecast', 'lower', 'upper']])
        result['date'] = (result['date'] - self.qlik_cal_start) / pd.Timedelta(days=1)
        self._send_table_description(result, 'StatsForecast-Intervals')
        return result

    def anomaly_table(self):
        """Return fitted intervals and flag observations outside those intervals."""
        history = self.request_df[['ds', 'y']].copy()
        if len(history) < 8:
            raise ValueError('At least eight historical rows are required for anomaly detection')
        sf_df = self._to_statsforecast_frame(history)
        sf = StatsForecast(models=[self._build_model()], freq=self.freq, n_jobs=self.n_jobs)
        sf.forecast(df=sf_df, h=1, level=self.level, fitted=True)
        fitted = sf.forecast_fitted_values()
        model_col = MODEL_MAP[self.model_name].__name__
        level = self.level[0]
        lo_col = f'{model_col}-lo-{level}'
        hi_col = f'{model_col}-hi-{level}'
        if lo_col not in fitted or hi_col not in fitted:
            raise ValueError(f"Model {model_col} did not return fitted {level}% prediction intervals")
        result = fitted[['ds', 'y', model_col, lo_col, hi_col]].copy()
        result.columns = ['date', 'actual', 'expected', 'lower', 'upper']
        result['is_anomaly'] = (
            (result['actual'] < result['lower']) | (result['actual'] > result['upper'])
        ).astype(float)
        result['date'] = (result['date'] - self.qlik_cal_start) / pd.Timedelta(days=1)
        self._send_table_description(result, 'StatsForecast-Anomalies')
        return result

    def _send_table_description(self, frame, name):
        table = SSE.TableDescription(name=name, numberOfRows=len(frame))
        for column in frame.columns:
            table.fields.add(name=column)
        self.context.send_initial_metadata((('qlik-tabledescription-bin', table.SerializeToString()),))

    def _extract_result(self, forecast_df):
        """
        Extract the requested column from the forecast DataFrame.
        """
        # Get the model column name (statsforecast uses the model class name)
        model_class = MODEL_MAP.get(self.model_name)
        model_col = model_class.__name__

        return_type = self.return_type.lower()

        if return_type in ('yhat', 'forecast', model_col.lower()):
            col = model_col
        elif return_type in ('yhat_upper', 'upper', 'hi'):
            col = f'{model_col}-hi-{self.level[0]}'
        elif return_type in ('yhat_lower', 'lower', 'lo'):
            col = f'{model_col}-lo-{self.level[0]}'
        else:
            # Try exact column name match
            col = self.return_type

        if col in forecast_df.columns:
            return forecast_df[col].values
        else:
            available = ', '.join(forecast_df.columns.tolist())
            raise ValueError(
                f"Column '{col}' not found in forecast results. "
                f"Available columns: {available}"
            )

    def _build_response(self, historical, forecast):
        """
        Build the response series matching the original request length.
        For y_then_yhat style: return actuals for historical, forecast for future.
        For yhat style: return NaN for historical, forecast for future.
        """
        return_type = self.return_type.lower()
        n_hist = len(historical)
        total = len(self.request_df)

        if return_type.startswith('y_then_'):
            # Return actual values for historical, then forecasted values
            result = np.concatenate([historical, forecast])
        else:
            # Return NaN for historical rows, forecast for future rows
            result = np.concatenate([np.full(n_hist, np.nan), forecast])

        # Trim or pad to match request length
        if len(result) < total:
            result = np.concatenate([result, np.full(total - len(result), np.nan)])
        elif len(result) > total:
            result = result[:total]

        # Add back NaT rows
        if len(self.NaT_df) > 0:
            result = np.concatenate([result, np.zeros(len(self.NaT_df))])

        return pd.Series(result)

    def _print_log(self, step, data=None):
        """Output debug information to terminal and log file."""
        StatsForecastForQlik.log_no += 1
        path = os.path.join(
            os.getcwd(), 'logs',
            'StatsForecast Log {}.txt'.format(StatsForecastForQlik.log_no)
        )

        if step == 1:
            output = (
                "\n\n--- StatsForecast Debug ---\n"
                f"Model: {self.model_name}\n"
                f"Frequency: {self.freq}\n"
                f"Periods: {self.periods}\n"
                f"Return: {self.return_type}\n"
                f"Level: {self.level}\n"
                f"Season Length: {self.season_length}\n"
                f"Take Log: {self.take_log}\n"
                f"Model kwargs: {self.model_kwargs}\n"
                f"Input rows: {len(self.input_df)}\n"
                f"Total request rows: {len(self.request_df)}\n"
                f"\nInput data (first 10 rows):\n{self.input_df.head(10).to_string()}\n"
            )
        elif step == 2:
            output = f"\nForecast results:\n{data.to_string()}\n"
        else:
            output = ""

        sys.stdout.write(output)

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(output)
        except Exception:
            pass
