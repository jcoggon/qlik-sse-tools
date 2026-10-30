"""Offline qualification of frozen notebook, Plotly and transformer bundles."""

import importlib.metadata


def main():
    import jupyterlab
    import notebook
    import ipykernel
    import plotly.graph_objects as go
    import spacy
    import spacy_curated_transformers  # noqa: F401
    import torch

    assert jupyterlab.__version__ == importlib.metadata.version("jupyterlab")
    assert notebook.__version__ == importlib.metadata.version("notebook")
    assert ipykernel.__version__ == importlib.metadata.version("ipykernel")
    figure = go.Figure(go.Bar(x=["A", "B"], y=[1, 2]))
    assert '"type":"bar"' in figure.to_json()
    # Construct a tiny registered encoder and execute a tensor layer; no model download.
    nlp = spacy.blank("en")
    nlp.add_pipe("curated_transformer", config={"model": {"@architectures": "spacy-curated-transformers.BertTransformer.v1",
                 "vocab_size": 100, "hidden_width": 8, "intermediate_width": 16,
                 "num_attention_heads": 2, "num_hidden_layers": 1,
                 "with_spans": {"@architectures": "spacy-curated-transformers.WithStridedSpans.v1"},
                 "piece_encoder": {"@architectures": "spacy-curated-transformers.WordpieceEncoder.v1"}}})
    assert torch.nn.Linear(2, 1)(torch.ones((1, 2))).shape == (1, 1)
    # Registration/construction checked above; production tokenizers and
    # pretrained weights remain separately selected assets.
    print({name: importlib.metadata.version(name) for name in (
        "jupyterlab", "notebook", "ipykernel", "plotly", "spacy-curated-transformers", "torch")})


if __name__ == "__main__":
    main()
