"""ALEA41 — le contrat `.importlinter` qui interdit au CRM d'importer les vues
d'autres domaines existe, et ses exceptions sont NOMMÉES (jamais un joker)."""
import configparser
from pathlib import Path

CFG = Path(__file__).resolve().parents[2] / "backend" / "django_core" / ".importlinter"
SECTION = "importlinter:contract:crm-n-importe-pas-les-vues-d-autres-domaines"


def _cfg():
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(CFG, encoding="utf-8")
    return cp


def _lines(cp, key):
    return [x.strip() for x in cp[SECTION].get(key, "").splitlines() if x.strip()]


def test_contrat_present_et_nomme():
    cp = _cfg()
    assert cp.has_section(SECTION)
    assert cp[SECTION]["type"] == "forbidden"
    assert _lines(cp, "source_modules") == ["apps.crm"]
    assert set(_lines(cp, "forbidden_modules")) == {
        "apps.visites.views", "apps.ventes.views"}


def test_exceptions_nommees_jamais_de_joker():
    for exc in _lines(_cfg(), "ignore_imports"):
        assert "*" not in exc
        src, sep, dst = exc.partition(" -> ")
        assert sep and src.startswith("apps.crm") and dst
