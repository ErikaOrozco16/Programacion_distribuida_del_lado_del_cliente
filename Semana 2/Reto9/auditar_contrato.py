from __future__ import annotations

import json
from pathlib import Path

from cliente_corregido import EcoMarketContractClient


EXPECTED = {
    ("GET", "/productos"): "listar_productos",
    ("POST", "/productos"): "crear_producto",
    ("GET", "/productos/{id}"): "obtener_producto",
    ("PUT", "/productos/{id}"): "actualizar_producto_total",
    ("PATCH", "/productos/{id}"): "actualizar_producto_parcial",
    ("DELETE", "/productos/{id}"): "eliminar_producto",
}


def load_contract(path: str | Path) -> dict:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    paths: dict[str, dict[str, dict[str, dict]]] = {}
    current_path: str | None = None
    current_method: str | None = None
    in_paths = False
    in_responses = False

    for raw_line in lines:
        if not raw_line.strip() or raw_line.strip() == "yaml":
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = raw_line.strip()

        if text == "paths:":
            in_paths = True
            continue
        if text == "components:":
            break
        if not in_paths:
            continue

        if indent == 2 and text.endswith(":"):
            current_path = text[:-1]
            paths[current_path] = {}
            current_method = None
            in_responses = False
            continue
        if current_path and indent == 4 and text.endswith(":"):
            key = text[:-1]
            if key in {"get", "post", "put", "patch", "delete"}:
                current_method = key
                paths[current_path][current_method] = {"responses": {}}
                in_responses = False
            continue
        if current_path and current_method and indent == 6 and text == "responses:":
            in_responses = True
            continue
        if current_path and current_method and in_responses and indent == 8 and text.endswith(":"):
            status = text[:-1].strip("'\"")
            paths[current_path][current_method]["responses"][status] = {}

    return {"paths": paths}


def audit(contract_path: str | Path) -> dict:
    contract = load_contract(contract_path)
    paths = contract["paths"]
    client_ops = EcoMarketContractClient.operations
    findings = []

    for (method, path), operation_name in EXPECTED.items():
        method_lower = method.lower()
        if path not in paths:
            findings.append({"severity": "error", "message": f"Falta ruta {path}"})
            continue
        if method_lower not in paths[path]:
            findings.append({"severity": "error", "message": f"Falta metodo {method} {path}"})
            continue
        if operation_name not in client_ops:
            findings.append({"severity": "error", "message": f"El cliente no implementa {operation_name}"})
            continue
        call = client_ops[operation_name]
        if call.method != method or call.path != path:
            findings.append({"severity": "error", "message": f"{operation_name} apunta a {call.method} {call.path}, no a {method} {path}"})
        responses = paths[path][method_lower].get("responses", {})
        if str(call.success_status) not in responses:
            findings.append({"severity": "error", "message": f"{operation_name} espera {call.success_status}, pero el contrato no lo declara"})

    protected = {"crear_producto", "actualizar_producto_total", "actualizar_producto_parcial", "eliminar_producto"}
    for name in protected:
        if not client_ops[name].requires_auth:
            findings.append({"severity": "error", "message": f"{name} debe requerir autenticacion"})

    return {
        "checked_operations": len(EXPECTED),
        "findings": findings,
        "conformity": "100%" if not findings else "incompleta",
    }


if __name__ == "__main__":
    result = audit(Path(__file__).parent.parent / "Reto1" / "openapi_ver2.yaml")
    print(json.dumps(result, indent=2, ensure_ascii=False))
