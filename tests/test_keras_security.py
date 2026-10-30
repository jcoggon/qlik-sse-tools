"""Optional real TensorFlow/scikeras compatibility on disposable models only."""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "core"), str(ROOT / "generated")]


def build_model():
    import keras
    return keras.Sequential([keras.layers.Input((2,)), keras.layers.Dense(1)])


@pytest.mark.parametrize("suffix", [".keras", ".h5"])
def test_trusted_keras_roundtrip(tmp_path, suffix):
    pytest.importorskip("tensorflow")
    import _security as security
    import keras
    model = build_model()
    x = np.array([[1.0, 2.0]], dtype="float32")
    expected = model(x).numpy()
    path = tmp_path / ("trusted" + suffix)
    model.save(path)
    loaded = security.load_keras_model(keras, path)
    np.testing.assert_allclose(loaded(x).numpy(), expected)


def test_persistent_scikeras_roundtrip(tmp_path):
    pytest.importorskip("tensorflow")
    pytest.importorskip("scikeras")
    from scikeras.wrappers import KerasRegressor
    from sklearn.pipeline import Pipeline
    from _machine_learning import PersistentModel
    x = np.array([[1.0, 2.0]], dtype="float32")
    estimator = KerasRegressor(model=build_model, loss="mean_squared_error")
    estimator.initialize(x, np.array([1.0]))
    expected = estimator.model_(x).numpy()
    model = PersistentModel()
    model.using_keras = True
    model.pipe = Pipeline([("estimator", estimator)])
    model.save("fixture", str(tmp_path) + "/")
    loaded = PersistentModel().load("fixture", str(tmp_path) + "/")
    np.testing.assert_allclose(loaded.pipe.named_steps["estimator"].model_(x).numpy(), expected)


def test_keras_archive_rejects_virtual_hdf5_weights(tmp_path):
    pytest.importorskip("tensorflow")
    import h5py
    import keras
    import _security as security
    original = tmp_path / "original.keras"
    build_model().save(original)
    with zipfile.ZipFile(original) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    weights = tmp_path / "weights.h5"
    weights.write_bytes(members["model.weights.h5"])
    external = tmp_path / "controlled-external.h5"
    with h5py.File(external, "w") as data:
        data.create_dataset("fixture", data=np.zeros((2, 1), dtype="float32"))
    with h5py.File(weights, "r+") as data:
        group = data["layers/dense/vars"]
        del group["0"]
        layout = h5py.VirtualLayout(shape=(2, 1), dtype="float32")
        layout[:] = h5py.VirtualSource(str(external), "fixture", shape=(2, 1))
        group.create_virtual_dataset("0", layout)
    members["model.weights.h5"] = weights.read_bytes()
    modified = tmp_path / "virtual.keras"
    with zipfile.ZipFile(modified, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match="virtual Dataset"):
        security.load_keras_model(keras, modified)


def test_keras_rejects_shape_metadata_without_allocating_declared_array(tmp_path):
    pytest.importorskip("tensorflow")
    import h5py
    from keras.src.saving.saving_lib import safe_get_h5_dataset
    path = tmp_path / "shape-metadata.h5"
    with h5py.File(path, "w") as data:
        data.create_dataset("fixture", shape=(1 << 30,), dtype="float64", chunks=(1024,), fillvalue=0)
        assert data["fixture"].id.get_storage_size() == 0
        with pytest.raises(ValueError, match="shape bomb"):
            safe_get_h5_dataset(data, "fixture")
    assert path.stat().st_size < 64 * 1024
