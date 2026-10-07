# flake8: noqa
"""Representative INDUSTRIEL sample quote (dev/preview + test fixture).

``build()`` returns a data dict in the shape ``builder.build_quote_data`` produces
for an industriel quote (only the keys the industriel renderer reads), so it can
feed ``renderer._augment`` + ``render.build_html`` (or ``render_pdf_bytes``)
without a database.
"""
from __future__ import annotations


def economie_ci(exemple="exemple_industriel_mt"):
    """Le bloc PUBLIC ``economie_ci`` d'un exemple du contrat partagé
    (``contract_samples/economie_ci.json``) — pour tester la page finance.

    CIQ342 — la page finance ne lit plus qu'``synthese_ci['argent']`` (le
    bloc du moteur C&I) : un test qui a besoin d'une rentabilité pose ce
    bloc sur ``data['economie_ci']`` AVANT ``renderer._augment``, exactement
    comme le builder. ``economie_ci_publique`` retire la vue interne."""
    import copy
    import json
    from pathlib import Path

    from apps.ventes.economie_ci import economie_ci_publique
    chemin = (Path(__file__).resolve().parents[2] / "contract_samples"
              / "economie_ci.json")
    contrat = json.loads(chemin.read_text(encoding="utf-8"))
    return economie_ci_publique(copy.deepcopy(contrat[exemple]))


def build() -> dict:
    bills = [42000, 39000, 45000, 51000, 58000, 66000,
             71000, 69000, 60000, 52000, 44000, 41000]
    return {
        "ref": "DEV-IND-DEMO",
        "date": "16/07/2026",
        "client_name": "Société Atlas Industrie SARL",
        "client_full": "Société Atlas Industrie SARL",
        "client_addr": "Zone industrielle Sidi Brahim",
        "client_city": "Fès",
        "client_phone": "+212 5 35 00 00 00",
        "inst_type": "Industrielle",
        "mode_installation": "industriel",
        "puissance_kwc": 250.0,
        "nb_panneaux": 352,
        "watt_par_panneau": 710,
        "prod_kwh": 400000,
        "conso_annuelle_kwh": 520000,
        "display_total": 1750000,
        "totaux_all": {"ttc": 1750000},
        "factures_mensuelles": bills,
        "all_items": [
            {"designation": "Panneau Canadien Solar 710W", "quantite": 352,
             "prix_unit_ht": 1166.0, "taux_tva": 10},
            {"designation": "Onduleur réseau Huawei 100kW Triphasé", "quantite": 2,
             "prix_unit_ht": 62000.0, "taux_tva": 20},
            {"designation": "Structures acier", "quantite": 352, "prix_unit_ht": 400.0,
             "taux_tva": 20},
            {"designation": "Installation", "quantite": 1, "prix_unit_ht": 180000.0,
             "taux_tva": 20},
        ],
        "payment_terms": {"acompte": 50, "materiel": 40, "solde": 10},
        "etude": {
            "kwc": 250.0, "production_annuelle": 400000, "conso_annuelle": 520000,
            "prix_kwc": 7000,
        },
        # CIQ301 — plus de ``eco_s_ann``/``roi_s``/``cashflow_*`` fabriqués
        # (C3-VA-01) : le renderer C&I ne les reprend plus. Voir
        # ``economie_ci()`` pour tester la page finance (CIQ342).
        "total_sans": 1750000,
        "entreprise": {},
        "site_url": "taqinor.ma",
        "accepte_par_nom": "",
        "date_acceptation": "",
        "validity_days": 30,
    }
