# flake8: noqa
"""Representative COMMERCIAL sample quotes (dev/preview + test fixtures).

``build(category='hotel')`` returns a data dict in the shape
``builder.build_quote_data`` produces for a commercial quote (only the keys the
commercial renderer reads), so it can feed ``renderer._augment`` +
``render.build_html`` without a database. Category drives the category-aware
cover + P2 block.
"""
from __future__ import annotations

_ANSWERS = {
    "hotel": {"chambres": 48, "occupation_pct": 62, "piscine": True},
    "restaurant": {"chambres_froides": 3, "horaires": "continu", "cuisson": "gaz"},
    "boulangerie": {"four": "electrique", "cuisson_nocturne": True},
    "froid": {"temperature_consigne": -18, "volume_m3": 800, "saisonnalite_recolte": True},
    "ecole": {"effectif": 420, "internat": False, "fermeture_estivale": True},
    "bureau": {"effectif": 60, "clim": True},
}


def keys():
    return ("hotel", "restaurant", "boulangerie", "froid", "ecole", "bureau", "autre")


def build(category: str = "hotel") -> dict:
    bills = [18000, 16000, 19000, 22000, 26000, 30000,
             33000, 32000, 27000, 22000, 19000, 17000]
    etude = {
        "kwc": 90.0, "production_annuelle": 144000, "conso_annuelle": 190000,
        "taux_autoconso": 78.0, "taux_couverture": 59.1,
        "economies_annuelles": 165000, "payback": 3.4, "prix_kwc": 7200,
        "categorie_commerciale": category,
    }
    etude.update(_ANSWERS.get(category, {}))
    return {
        "ref": "DEV-COM-DEMO",
        "date": "16/07/2026",
        "client_name": "Hôtel Atlas Riad SARL",
        "client_full": "Hôtel Atlas Riad SARL",
        "client_addr": "Avenue Mohammed VI",
        "client_city": "Marrakech",
        "client_phone": "+212 5 24 00 00 00",
        "inst_type": "Commerciale",
        "mode_installation": "commercial",
        "puissance_kwc": 90.0,
        "nb_panneaux": 127,
        "watt_par_panneau": 710,
        "prod_kwh": 144000,
        "conso_annuelle_kwh": 190000,
        "eco_s_ann": 165000,
        "roi_s": 3.4,
        "display_total": 640000,
        "totaux_all": {"ht_brut": 533333, "remise": 0, "ht_net": 533333,
                       "tva": 106667, "ttc": 640000},
        "factures_mensuelles": bills,
        "all_items": [
            {"designation": "Panneau Jinko 710W", "marque": "Jinko", "quantite": 127,
             "prix_unit_ht": 1150.0, "prix_unit_ttc": 1265.0, "taux_tva": 10},
            {"designation": "Onduleur réseau Huawei 100kW Triphasé", "marque": "Huawei",
             "quantite": 1, "prix_unit_ht": 60000.0, "prix_unit_ttc": 72000.0, "taux_tva": 20},
            {"designation": "Structures acier", "marque": "", "quantite": 127,
             "prix_unit_ht": 400.0, "prix_unit_ttc": 480.0, "taux_tva": 20},
            {"designation": "Installation", "marque": "", "quantite": 1,
             "prix_unit_ht": 90000.0, "prix_unit_ttc": 108000.0, "taux_tva": 20},
        ],
        "payment_terms": {"acompte": 50, "materiel": 40, "solde": 10},
        "etude": etude,
        "entreprise": {},
        "site_url": "taqinor.ma",
        "accepte_par_nom": "",
        "date_acceptation": "",
        "validity_days": 30,
    }
