# flake8: noqa
"""Representative AGRICOLE sample quotes (dev/preview + test fixtures).

Each ``build(key)`` returns a data dict in the SAME shape ``builder.build_quote_data``
produces for an agricole quote, so it can be fed straight to
``renderer._augment`` + ``render.build_html`` (or ``render_pdf_bytes``) to preview
the premium proposal without a database. Three scenarios span the market:
small olive (surface pump / butane), mid citrus (immergé / butane), large date
palm (immergé / diesel).
"""
from __future__ import annotations


def _canonical_totaux(items, discount_pct=0.0):
    """Mirror builder._canonical_totaux: HT → remise → TVA (par taux) → TTC."""
    ht_brut = round(sum(r["quantite"] * r["prix_unit_ht"] for r in items), 2)
    remise = round(ht_brut * discount_pct / 100, 2) if discount_pct > 0 else 0.0
    ht_net = round(ht_brut - remise, 2)
    buckets = {}
    for r in items:
        rate = float(r.get("taux_tva", 20))
        buckets[rate] = buckets.get(rate, 0.0) + r["quantite"] * r["prix_unit_ht"]
    if len(buckets) <= 1:
        rate = next(iter(buckets), 20.0)
        tva = round(ht_net * rate / 100, 2)
        tva_par_taux = [{"taux": rate, "montant": tva, "ht_net": ht_net}]
    else:
        rates = sorted(buckets)
        nets = {r: round(buckets[r] * (1 - discount_pct / 100), 2) for r in rates}
        nets[rates[-1]] = round(nets[rates[-1]] + (ht_net - sum(nets.values())), 2)
        tva_par_taux = [{"taux": r, "montant": round(nets[r] * r / 100, 2),
                         "ht_net": nets[r]} for r in rates]
        tva = round(sum(b["montant"] for b in tva_par_taux), 2)
    ttc_exact = round(ht_net + tva, 2)
    return {"ht_brut": ht_brut, "remise": remise, "ht_net": ht_net,
            "tva": tva, "tva_par_taux": tva_par_taux, "ttc": round(ttc_exact),
            "ttc_exact": ttc_exact, "ttc_avant": round(ht_brut * 1.2)}


def _item(designation, marque, qty, pu_ht, taux=20, description="", garantie=""):
    return {"designation": designation, "marque": marque, "description": description,
            "garantie": garantie, "quantite": float(qty),
            "prix_unit_ht": float(pu_ht),
            "prix_unit_ttc": round(pu_ht * (1 + taux / 100), 2),
            "taux_tva": float(taux)}


_SCENARIOS = {
    # ── Mid citrus — Souss-Massa, forage immergé, butane ─────────────────────
    "agrumes": {
        "ref": "DEV-AGRI-2601", "client": ("Ahmed", "El Mansouri"),
        "addr": "Douar Ouled Teima, Taroudant", "phone": "+212 6 61 23 45 67",
        "discount": 5.0, "fuel": "butane",
        "etude": {
            "pompe_cv": "7.5", "pompe_kw": 5.5,
            "pompe_nom": "Pompe immergée 4\" 7,5 CV — 380 V",
            "type_pompe": "immergee", "alim": "tri",
            "hmt_m": 60, "debit_souhaite_m3h": 15, "debit_hmt_m3h": 16,
            "heures_pompage": 7, "m3_jour": 112, "profondeur_m": 80,
            "distance_m": 30, "champ_kwc": 7.1,
            "crop": "agrumes", "region": "souss-massa", "surface_ha": 2.0,
            "irrigation_method": "goutte", "source": "forage",
            "hmt_static": 45, "hmt_drawdown": 8, "hmt_lift": 4, "hmt_friction": 3,
        },
        "kwc": 7.1, "nb": 10, "watt": 710,
        "items": [
            _item("Pompe immergée 4\" 7,5 CV (380V)", "OSP", 1, 14500, 20,
                  "Pompe immergée inox, moteur 5,5 kW, refoulement 2\".", "2 ans"),
            _item("Variateur solaire VEICHI 7,5 kW (380V)", "VEICHI", 1, 9800, 20,
                  "Variateur solaire MPPT, protection manque d'eau & survitesse.", "5 ans"),
            _item("Afficheur variateur SI22", "VEICHI", 1, 650, 20),
            _item("Panneau photovoltaïque 710 Wc", "Canadian Solar", 10, 1150, 10,
                  "Module monocristallin TOPCon haut rendement.", "25 ans (perf.)"),
            _item("Structure de fixation acier galvanisé", "TAQINOR", 10, 320, 20),
            _item("Socle béton", "TAQINOR", 20, 60, 20),
            _item("Câble solaire 6 mm² (m)", "TAQINOR", 30, 18, 20),
            _item("Installation & mise en service", "TAQINOR", 1, 6500, 20),
            _item("Transport & logistique", "TAQINOR", 1, 1800, 20),
        ],
    },
    # ── Small olive — Saïss, puits + pompe de surface, butane ────────────────
    "olivier": {
        "ref": "DEV-AGRI-2602", "client": ("Fatima", "Berrada"),
        "addr": "Aïn Taoujdate, Saïss", "phone": "+212 6 62 98 76 54",
        "discount": 0.0, "fuel": "butane",
        "etude": {
            "pompe_cv": "5.5", "pompe_kw": 4.0,
            "pompe_nom": "Pompe de surface 5,5 CV — 380 V",
            "type_pompe": "surface", "alim": "tri",
            "hmt_m": 45, "debit_souhaite_m3h": 12, "debit_hmt_m3h": 12,
            "heures_pompage": 7, "m3_jour": 84, "profondeur_m": 18,
            "distance_m": 20, "champ_kwc": 5.68,
            "crop": "olivier", "region": "saiss", "surface_ha": 1.5,
            "irrigation_method": "goutte", "source": "puits",
            "hmt_static": 16, "hmt_drawdown": 4, "hmt_lift": 20, "hmt_friction": 5,
        },
        "kwc": 5.68, "nb": 8, "watt": 710,
        "items": [
            _item("Pompe de surface 5,5 CV (380V)", "Pedrollo", 1, 9200, 20,
                  "Pompe centrifuge de surface, corps fonte.", "2 ans"),
            _item("Variateur solaire VEICHI 5,5 kW (380V)", "VEICHI", 1, 7600, 20,
                  "Variateur solaire MPPT avec protections intégrées.", "5 ans"),
            _item("Afficheur variateur SI22", "VEICHI", 1, 650, 20),
            _item("Panneau photovoltaïque 710 Wc", "Canadian Solar", 8, 1150, 10,
                  "Module monocristallin TOPCon haut rendement.", "25 ans (perf.)"),
            _item("Structure de fixation acier galvanisé", "TAQINOR", 8, 320, 20),
            _item("Socle béton", "TAQINOR", 16, 60, 20),
            _item("Câble solaire 6 mm² (m)", "TAQINOR", 20, 18, 20),
            _item("Installation & mise en service", "TAQINOR", 1, 5200, 20),
            _item("Transport & logistique", "TAQINOR", 1, 1500, 20),
        ],
    },
    # ── Large date palm — Drâa-Tafilalet, forage immergé, diesel ─────────────
    "dattier": {
        "ref": "DEV-AGRI-2603", "client": ("Brahim", "Ait Oufkir"),
        "addr": "Zagora, Drâa-Tafilalet", "phone": "+212 6 63 11 22 33",
        "discount": 8.0, "fuel": "diesel",
        "etude": {
            "pompe_cv": "15", "pompe_kw": 11.0,
            "pompe_nom": "Pompe immergée 6\" 15 CV — 380 V",
            "type_pompe": "immergee", "alim": "tri",
            "hmt_m": 75, "debit_souhaite_m3h": 35, "debit_hmt_m3h": 36,
            "heures_pompage": 7, "m3_jour": 252, "profondeur_m": 110,
            "distance_m": 45, "champ_kwc": 15.62,
            "crop": "dattier", "region": "draa-tafilalet", "surface_ha": 2.8,
            "irrigation_method": "goutte", "source": "forage",
            "hmt_static": 58, "hmt_drawdown": 9, "hmt_lift": 4, "hmt_friction": 4,
        },
        "kwc": 15.62, "nb": 22, "watt": 710,
        "items": [
            _item("Pompe immergée 6\" 15 CV (380V)", "OSP", 1, 32000, 20,
                  "Pompe immergée inox 6\", moteur 11 kW, gros débit.", "2 ans"),
            _item("Variateur solaire VEICHI 15 kW (380V)", "VEICHI", 1, 18500, 20,
                  "Variateur solaire MPPT 15 kW, protections complètes.", "5 ans"),
            _item("Afficheur variateur SI22", "VEICHI", 1, 650, 20),
            _item("Panneau photovoltaïque 710 Wc", "Canadian Solar", 22, 1150, 10,
                  "Module monocristallin TOPCon haut rendement.", "25 ans (perf.)"),
            _item("Structure de fixation acier galvanisé", "TAQINOR", 22, 320, 20),
            _item("Socle béton", "TAQINOR", 44, 60, 20),
            _item("Câble solaire 10 mm² (m)", "TAQINOR", 45, 26, 20),
            _item("Installation & mise en service", "TAQINOR", 1, 11000, 20),
            _item("Transport & logistique", "TAQINOR", 1, 3200, 20),
        ],
    },
}


def keys():
    return list(_SCENARIOS.keys())


def build(key="agrumes") -> dict:
    s = _SCENARIOS[key]
    items = [dict(it) for it in s["items"]]
    totaux = _canonical_totaux(items, s["discount"])
    etude = dict(s["etude"])
    etude["current_fuel"] = s["fuel"]
    prenom, nom = s["client"]
    return {
        "ref": s["ref"], "date": "21/06/2026",
        "client_name": f"{prenom} {nom}", "client_full": f"{prenom} {nom}",
        "client_addr": s["addr"], "client_phone": s["phone"], "client_ice": "",
        "inst_type": "Agricole",
        "puissance_kwc": s["kwc"], "nb_panneaux": s["nb"], "watt_par_panneau": s["watt"],
        "all_items": items, "totaux_all": totaux,
        "display_total": totaux["ttc"], "discount_pct": s["discount"],
        "payment_terms": {"acompte": 30, "materiel": 60, "solde": 10},
        "mode_installation": "agricole", "etude": etude,
        "tva_note": ("TVA : 10% panneaux photovoltaïques · "
                     "20% autres équipements et prestations"),
        "validity_days": 30, "site_url": "taqinor.ma",
        "show_subsidy": True, "show_fuel_comparison": True,
        "show_environmental": True, "show_schematic": True, "show_water_yield": True,
        "_company_id": None,
        "accepte_par_nom": "", "date_acceptation": "",
    }
