# flake8: noqa
"""Representative INDUSTRIEL sample quote (dev/preview + test fixture).

``build()`` returns a data dict in the shape ``builder.build_quote_data`` produces
for an industriel quote (only the keys the industriel renderer reads), so it can
feed ``renderer._augment`` + ``render.build_html`` (or ``render_pdf_bytes``)
without a database.
"""
from __future__ import annotations


#: Prix TTC de la ligne onduleur de la fixture (2 × 62 000 HT à 20 %) — c'est
#: ce montant que ``pricing`` provisionne pour le remplacement de l'année 12.
_ONDULEUR_TTC = 2 * 62000.0 * 1.20


def _cashflow(invest, economie_an1):
    """Série canonique — MÊME fonction que le builder, jamais une saisie."""
    from ..pricing import compute_cashflow_payback
    return compute_cashflow_payback(invest, economie_an1,
                                    inverter_replace_cost=_ONDULEUR_TTC)


def _hypotheses():
    """Hypothèses DÉCLARÉES du même modèle (dégradation, provision…)."""
    from ..pricing import cashflow_assumptions
    return cashflow_assumptions(inverter_replace_cost=_ONDULEUR_TTC)


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
        "eco_s_ann": 420000,
        "roi_s": 3.1,
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
            "taux_autoconso": 88.0, "taux_couverture": 67.7,
            "economies_annuelles": 420000, "payback": 3.1, "prix_kwc": 7000,
        },
        # QJR120 — la page 2 lit le cashflow CANONIQUE servi par le builder
        # (``pricing.compute_cashflow_payback``), plus une droite plate locale.
        # La fixture le produit par la MÊME fonction, avec l'investissement et
        # l'économie annuelle qu'elle déclare — aucun chiffre saisi à la main.
        "total_sans": 1750000,
        "cashflow_sans": _cashflow(1750000, 420000)["cumulative"],
        "cashflow_assumptions": _hypotheses(),
        "entreprise": {},
        "site_url": "taqinor.ma",
        "accepte_par_nom": "",
        "date_acceptation": "",
        "validity_days": 30,
    }
