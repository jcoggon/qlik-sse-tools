import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _handler_map_from_source():
    tree = ast.parse((ROOT / "core" / "__main__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ExtensionService":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "functions":
                    for statement in item.body:
                        if isinstance(statement, ast.Return):
                            return ast.literal_eval(statement.value)
    raise AssertionError("ExtensionService.functions mapping was not found")


def test_function_registry_is_unique_and_contiguous():
    definitions = json.loads((ROOT / "core" / "functions.json").read_text(encoding="utf-8"))["Functions"]
    ids = [item["Id"] for item in definitions]
    names = [item["Name"] for item in definitions]

    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))
    assert sorted(ids) == list(range(len(ids)))


def test_every_registered_function_has_a_handler():
    definitions = json.loads((ROOT / "core" / "functions.json").read_text(encoding="utf-8"))["Functions"]
    handlers = _handler_map_from_source()

    assert set(handlers) == {item["Id"] for item in definitions}
    assert all(isinstance(name, str) and name.startswith("_") for name in handlers.values())


def test_protobuf_sources_and_generated_bindings_are_packaged():
    required = {
        "generated/ServerSideExtension.proto",
        "generated/ServerSideExtension_pb2.py",
        "generated/ServerSideExtension_pb2_grpc.py",
    }
    assert all((ROOT / path).is_file() for path in required)
