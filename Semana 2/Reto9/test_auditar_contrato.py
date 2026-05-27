from auditar_contrato import audit


def test_cliente_corregido_cumple_contrato_openapi():
    result = audit("../Reto1/openapi_ver2.yaml")

    assert result["conformity"] == "100%"
    assert result["findings"] == []
    assert result["checked_operations"] == 6
