"""El contrato del servidor: si estas pruebas pasan, Claude Code y evaluar.py pueden usarlo.

    uv run pytest -q

Llaman al servidor en memoria, igual que lo haría Claude Code, y piden datos reales al BCRP.
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def test_buscar_encuentra_el_ipc():
    r = llamar("buscar_series", texto="ipc 12 meses", limite=5)
    assert "PN01273PM" in [x["codigo"] for x in r]
    assert {"codigo", "nombre", "frecuencia"} <= r[0].keys()


def test_cuatro_herramientas_como_minimo():
    nombres = {t.name for t in asyncio.run(_con_cliente(lambda c: c.list_tools()))}
    assert {"buscar_series", "serie", "resumen"} <= nombres
    assert len(nombres) >= 4, "falta su herramienta propia"


def test_serie_mensual():
    r = llamar("serie", codigo="PN01271PM", desde="2025-01", hasta="2025-12")
    assert len(r["datos"]) == 12
    assert r["datos"][0]["periodo"] == "2025-01"
    assert r["datos"][2]["valor"] == pytest.approx(0.81, abs=0.01)   # IPC de Lima, marzo de 2025
    assert r["fuente"].startswith("https://estadisticas.bcrp.gob.pe")


def test_serie_diaria():
    r = llamar("serie", codigo="PD04638PD", desde="2026-10-01", hasta="2026-10-15")
    assert r["datos"][0]["periodo"] == "2026-10-01"
    assert r["datos"][-1] == {"periodo": "2026-10-15", "valor": pytest.approx(3.428, abs=0.001)}


def test_resumen_sin_cuentas_a_mano():
    r = llamar("resumen", codigo="PN01273PM", desde="2025-12", hasta="2026-09")
    assert r["primero"]["valor"] == pytest.approx(1.51, abs=0.01)
    assert r["ultimo"]["valor"] == pytest.approx(4.55, abs=0.01)
    assert r["maximo"]["periodo"] == "2026-09"
    assert {"cambio", "variacion_pct", "promedio", "minimo"} <= r.keys()


def test_codigo_inexistente_da_un_error_claro():
    with pytest.raises(ToolError, match="XX999"):
        llamar("serie", codigo="XX999", desde="2025-01", hasta="2025-02")


def test_un_recurso():
    async def contar(c):
        return len(await c.list_resources()) + len(await c.list_resource_templates())
    assert asyncio.run(_con_cliente(contar)) >= 1


def test_un_prompt():
    assert len(asyncio.run(_con_cliente(lambda c: c.list_prompts()))) >= 1


def test_comparar_alinea_periodos_y_correlaciona(monkeypatch):
    # Datos inventados para saber la respuesta: solo coinciden enero, marzo y mayo. Ahí A es 1, 2, 3 y B es 1, 3, 2,
    # y su correlación es 0.5 a mano. Los valores 100 y -50 no coinciden: si se colaran, cambiarían el resultado.
    datos = {"PN01271PM": {"2025-01": 1, "2025-02": 100, "2025-03": 2, "2025-05": 3},
             "PN01273PM": {"2025-01": 1, "2025-03": 3, "2025-04": -50, "2025-05": 2}}

    def serie_falsa(codigo, desde, hasta):
        return {"codigo": codigo, "nombre": codigo, "frecuencia": "Mensual", "fuente": f"https://bcrp.test/{codigo}",
                "datos": [{"periodo": p, "valor": v} for p, v in datos[codigo].items()]}

    monkeypatch.setattr("server.serie", serie_falsa)
    r = llamar("comparar_series", codigo_a="PN01271PM", codigo_b="PN01273PM", desde="2025-01", hasta="2025-05")
    assert r["periodos_coincidentes"] == 3
    assert r["correlacion"] == pytest.approx(0.5)
    assert r["a"]["promedio"] == pytest.approx(2) and r["b"]["promedio"] == pytest.approx(2)
    assert r["a"]["primero"] == {"periodo": "2025-01", "valor": 1} and r["a"]["ultimo"] == {"periodo": "2025-05", "valor": 3}
    assert r["b"]["primero"] == {"periodo": "2025-01", "valor": 1} and r["b"]["ultimo"] == {"periodo": "2025-05", "valor": 2}
    assert r["fuentes"] == ["https://bcrp.test/PN01271PM", "https://bcrp.test/PN01273PM"]


def test_comparar_rechaza_frecuencias_distintas():
    with pytest.raises(ToolError, match="PN01271PM es mensual y PD04638PD es diaria"):
        llamar("comparar_series", codigo_a="PN01271PM", codigo_b="PD04638PD", desde="2025-01", hasta="2025-12")
