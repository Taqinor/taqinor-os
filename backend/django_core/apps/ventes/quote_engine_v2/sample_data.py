# flake8: noqa
"""Sample data for the v2 PROTOTYPE — reuses the LIVE build_quote_data mapping
(so totals/option-split are real), then augments with the new v2 fields
(bills before/after, coverage %, website links). No DB; stand-in Devis."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace


def _produit(nom, marque="", description="", garantie=""):
    return SimpleNamespace(nom=nom, marque=marque, description=description,
                           garantie=garantie)


def _ligne(designation, pu_ht, qte, taux=20, prod=None, remise=0):
    return SimpleNamespace(designation=designation,
                           prix_unitaire=Decimal(str(pu_ht)),
                           quantite=Decimal(str(qte)), remise=Decimal(str(remise)),
                           taux_tva=Decimal(str(taux)), produit=prod)


class _Lignes:
    def __init__(self, rows): self._rows = rows
    def select_related(self, *a, **k): return self
    def all(self): return list(self._rows)


def _khalil_devis():
    pan = _produit("Panneau 710 Wc", "Canadian Solar",
                   "Monocristallin N-Type TOPCon, haut rendement.",
                   "12 ans produit / 30 ans 87,4%")
    ondr = _produit("Onduleur réseau triphasé", "Huawei",
                    "Onduleur string triphasé, supervision FusionSolar.", "10 ans")
    ondh = _produit("Onduleur hybride 10 kW", "Deye",
                    "Hybride avec gestion batterie + backup secteur.", "10 ans")
    bat = _produit("Batterie 10 kWh", "Deye",
                   "Stockage lithium LiFePO4, 6000 cycles.", "10 ans")
    sm = _produit("Smart Meter", "Huawei", "Compteur intelligent triphasé.", "5 ans")
    wifi = _produit("Wifi Dongle", "Huawei", "Module de communication WiFi.", "2 ans")
    lignes = [
        _ligne("Onduleur réseau triphasé", 16666.67, 1, 20, ondr),
        _ligne("Onduleur hybride 10 kW", 33333.33, 1, 20, ondh),
        _ligne("Batterie 10 kWh", 25000, 1, 20, bat),
        _ligne("Panneaux 710 Wc", 1272.73, 16, 10, pan),   # reform 10 %
        _ligne("Smart Meter", 1500, 1, 20, sm),
        _ligne("Wifi Dongle", 1000, 1, 20, wifi),
        _ligne("Structures acier", 416.67, 16, 20),
        _ligne("Socles", 66.67, 32, 20),
        _ligne("Accessoires", 2000, 1, 20),
        _ligne("Tableau De Protection AC/DC", 2500, 1, 20),
        _ligne("Installation", 6000, 1, 20),
        _ligne("Transport", 833.33, 1, 20),
    ]
    client = SimpleNamespace(prenom="Khalil", nom="Serbouti",
                             adresse="Lot. Al Manar, Bouskoura, Casablanca",
                             telephone="0661 85 04 10", ice="")
    return SimpleNamespace(
        client=client, taux_tva=Decimal(20), remise_globale=Decimal(0),
        lignes=_Lignes(lignes), etude_params={}, mode_installation="residentiel",
        reference="DEV-202606-0070", date_creation=datetime(2026, 6, 6),
        company=None, accepte_par_nom="", date_acceptation=None, total_ttc=Decimal(0))


def build():
    """Return the full v2 data dict (live mapping + new fields)."""
    import sys
    from pathlib import Path
    dj = Path(__file__).resolve().parents[3]   # backend/django_core
    if str(dj) not in sys.path:
        sys.path.insert(0, str(dj))
    from apps.ventes.quote_engine.builder import build_quote_data

    devis = _khalil_devis()
    d = build_quote_data(devis, {"pdf_mode": "full"})

    # ── New v2 fields ────────────────────────────────────────────────────────
    before = list(d["factures_mensuelles"])
    after = [max(0, round(b - s)) for b, s in zip(before, d["eco_a_monthly"])]
    annual_before = sum(before)
    annual_after = sum(after)
    # Consumption estimate from bill (ONEE avg ~1.3 MAD/kWh) -> coverage %.
    conso_kwh = max(1, round(annual_before / 1.3))
    coverage = max(40, min(99, round(d["prod_kwh"] / conso_kwh * 100)))

    d.update({
        "client_city": "Casablanca",
        "client_full": "Khalil Serbouti",
        "bills_before": before,
        "bills_after": after,
        "annual_before": annual_before,
        "annual_after": annual_after,
        "coverage_pct": coverage,
        "validity_days": 30,
        "site_url": "taqinor.ma",
        "links": {
            "realisations": "taqinor.ma/realisations",
            "avis": "taqinor.ma/avis",
            "produits": "taqinor.ma/produits",
            "garanties": "taqinor.ma/garanties",
            "signer": "taqinor.ma/signer/DEV-202606-0070",
        },
    })
    return d
