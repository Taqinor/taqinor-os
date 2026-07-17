# flake8: noqa
"""Representative RESIDENTIAL sample quotes (dev/preview + test fixtures).

``build(variant="deux")`` returns a data dict in the shape
``builder.build_quote_data`` produces for a residential quote (only the keys the
residential renderer reads), so it can feed ``renderer._augment`` +
``render.build_html`` without a database — exactly like the commercial /
industriel / agricole ``sample_data`` modules. ``render.render_pdf`` falls back
on this module when called without data (previously a latent ImportError).

Variants:
  - "deux"  — the standard two-option villa quote (sans / avec batterie).
  - "sans"  — a mono-option grid-tied quote (no battery on the devis), the
              shape of real DEV-202607-0021.
  - "long"  — the "deux" quote with every optional block filled (factures
              savings model, seller, financing, long hypotheses) — the
              worst-case page-3 density used by the pagination guard test.
"""
from __future__ import annotations


def keys():
    return ("deux", "sans", "long")


def _cumulative(total_ttc, eco_year1, years=25, degradation=0.005,
                escalation=0.02):
    """Cumulative cashflow like pricing.compute_cashflow (simplified)."""
    cumul, out = -float(total_ttc), []
    for y in range(1, years + 1):
        saving = eco_year1 * ((1 - degradation) ** (y - 1)) * ((1 + escalation) ** (y - 1))
        cumul += saving
        out.append(round(cumul))
    return out


def _totaux(items):
    """HT/TVA/TTC chain computed from the line items (always consistent)."""
    ht = sum(it["prix_unit_ht"] * it["quantite"] for it in items)
    par_taux = {}
    for it in items:
        t = int(round(it["taux_tva"]))
        par_taux[t] = par_taux.get(t, 0) + it["prix_unit_ht"] * it["quantite"] * t / 100.0
    tva_rows = [{"taux": t, "montant": round(m)} for t, m in sorted(par_taux.items())]
    tva = sum(r["montant"] for r in tva_rows)
    return {"ht_brut": round(ht), "remise": 0, "ht_net": round(ht),
            "tva_par_taux": tva_rows, "tva": round(tva),
            "ttc": round(ht + tva)}


def build(variant: str = "deux") -> dict:
    # ── Line items (catalogue prices: panels 10 % TVA, the rest 20 %) ───────
    panneaux = {"designation": "Panneau Canadien Solar 710W",
                "marque": "Canadien Solar", "quantite": 8,
                "prix_unit_ht": 1273.0, "taux_tva": 10}
    ond_reseau = {"designation": "Onduleur réseau Huawei 5kW Monophasé",
                  "marque": "Huawei", "quantite": 1,
                  "prix_unit_ht": 11667.0, "taux_tva": 20}
    ond_hybride = {"designation": "Onduleur hybride Deye 5kW Monophasé",
                   "marque": "Deye", "quantite": 1,
                   "prix_unit_ht": 16667.0, "taux_tva": 20}
    batterie = {"designation": "Batterie Lithium Dyness 5,12 kWh",
                "marque": "Deyness", "quantite": 1,
                "prix_unit_ht": 13333.0, "taux_tva": 20}
    tableau = {"designation": "Tableau De Protection AC/DC", "marque": "",
               "quantite": 1, "prix_unit_ht": 1250.0, "taux_tva": 20}
    structures = {"designation": "Structure de fixation aluminium", "marque": "",
                  "quantite": 8, "prix_unit_ht": 250.0, "taux_tva": 20}
    install = {"designation": "Installation", "marque": "", "quantite": 1,
               "prix_unit_ht": 4000.0, "taux_tva": 20}

    sans_items = [panneaux, ond_reseau, tableau, structures, install]
    avec_items = [panneaux, ond_hybride, batterie, tableau, structures, install]
    totaux_sans, totaux_avec = _totaux(sans_items), _totaux(avec_items)

    bills = [1500, 1450, 1550, 1600, 1750, 2100,
             2400, 2350, 1950, 1700, 1550, 1500]          # ≈ 21 400 MAD/an
    eco_s_ann, eco_a_ann = 10650, 14750
    eco_a_monthly = [round(eco_a_ann * b / sum(bills)) for b in bills]
    roi_s = round(totaux_sans["ttc"] / eco_s_ann, 1)
    roi_a = round(totaux_avec["ttc"] / eco_a_ann, 1)

    d = {
        "ref": "DEV-RES-DEMO",
        "date": "17/07/2026",
        "client_name": "Mohammed Lahlou",
        "client_full": "Mohammed Lahlou",
        "client_addr": "12 rue des Orangers, Californie",
        "client_city": "Casablanca",
        "client_phone": "+212 6 61 00 00 00",
        "inst_type": "Résidentielle",
        "mode_installation": "residentiel",
        "puissance_kwc": 5.68,
        "nb_panneaux": 8,
        "watt_par_panneau": 710,
        "prod_kwh": 9378,
        "conso_annuelle_kwh": 12000,
        "tarif_kwh": 1.75,
        "sans_items": sans_items,
        "avec_items": avec_items,
        "totaux_sans": totaux_sans,
        "totaux_avec": totaux_avec,
        "total_sans": totaux_sans["ttc"],
        "total_avec": totaux_avec["ttc"],
        "eco_s_ann": eco_s_ann,
        "eco_a_ann": eco_a_ann,
        "roi_s": roi_s,
        "roi_a": roi_a,
        "factures_mensuelles": bills,
        "eco_a_monthly": eco_a_monthly,
        "cashflow_sans": _cumulative(totaux_sans["ttc"], eco_s_ann),
        "cashflow_avec": _cumulative(totaux_avec["ttc"], eco_a_ann),
        "sans_bullets": ["8 panneaux 710 W",
                         "Onduleur réseau Huawei 5kW Monophasé",
                         "Structures + installation complète"],
        "avec_bullets": ["8 panneaux 710 W",
                         "Onduleur hybride Deye 5kW",
                         "Batterie Lithium 5,12 kWh — vos soirées sur batterie"],
        "deux_options": True,
        "avec_ok": True,
        "payment_terms": {"acompte": 30, "materiel": 60, "solde": 10},
        "tva_note": ("TVA : 10% panneaux photovoltaïques · "
                     "20% autres équipements et prestations"),
        "savings_method": {
            "model": "estimation", "approximatif": True,
            "ligne_methode": (
                "Estimation : production annuelle × part autoconsommée × tarif "
                "kWh (loi 82-21 : seul l'autoconsommé est valorisé — détail "
                "dans nos hypothèses). Fournissez une facture réelle pour un "
                "calcul par tranche exact."),
            "exemple": None,
        },
        "hypotheses": {
            "titre": "Nos hypothèses",
            "items": [
                "Tarif électricité retenu : 1,75 MAD/kWh (estimation)",
                "Économies valorisées sur l'autoconsommation uniquement "
                "(loi 82-21) — le surplus injecté n'est pas rémunéré (rachat "
                "BT résidentiel différé par l'ANRE) ; plafond d'injection "
                "20 % pré-intégré dans les taux d'autoconsommation.",
                "Production estimée : ≈ 1651 kWh par kWc et par an "
                "(irradiation moyenne au Maroc).",
                "Dégradation panneau 0,5 %/an et escalade du tarif électrique "
                "2 %/an (hypothèse prudente) intégrées au calcul de "
                "rentabilité.",
                "Estimations non contractuelles ; toute hausse future du "
                "tarif électrique améliore votre rentabilité.",
            ],
        },
        "financing": {"indicatif": True,
                      "credit": {"mensualite": 620, "duree_mois": 120,
                                 "programme_nom": "Crédit vert résidentiel"}},
        "links": {"signer":
                  "taqinor.ma/proposition/rKJtbjsY-qTML35ZnjQ9Lt_v4_demo"},
        "entreprise": {"nom": "TAQINOR Solutions",
                       "email": "contact@taqinor.ma",
                       "telephone": "+212 6 61 85 04 10"},
        "site_url": "taqinor.ma",
        "validity_days": 30,
    }

    if variant == "sans":
        # Mono-option grid-tied — the DEV-202607-0021 shape (extreme numbers
        # kept: they stress big-figure layout paths).
        pan70 = dict(panneaux, quantite=70, taux_tva=20)
        items = [pan70, dict(ond_reseau)]
        tot = _totaux(items)
        bills21 = [7000, 8500, 12000, 14500, 16200, 16800,
                   16900, 14300, 12400, 9200, 7900, 6900]
        eco_s = 122057
        d.update({
            "sans_items": items, "avec_items": items,
            "totaux_sans": tot, "totaux_avec": tot,
            "total_sans": tot["ttc"], "total_avec": tot["ttc"],
            "puissance_kwc": 49.7, "nb_panneaux": 70, "prod_kwh": 82055,
            "conso_annuelle_kwh": None, "eco_s_ann": eco_s, "eco_a_ann": eco_s,
            "roi_s": 1.4, "roi_a": 1.4,
            "factures_mensuelles": bills21,
            "eco_a_monthly": [round(eco_s * b / sum(bills21)) for b in bills21],
            "cashflow_sans": _cumulative(tot["ttc"], eco_s),
            "cashflow_avec": _cumulative(tot["ttc"], eco_s),
            "deux_options": False, "avec_ok": False,
            "sans_bullets": ["70 panneaux 710 W",
                             "Onduleur réseau Huawei 5kW Monophasé",
                             "Structures + installation complète"],
            "client_name": "Srdgsdg", "client_full": "Srdgsdg",
            "client_addr": "casablanca, casablanca", "client_city": "casablanca",
            "client_phone": "+212661850412",
            "tva_note": "TVA : 20 % appliquée sur l'ensemble des équipements "
                        "et travaux.",
            "financing": {"indicatif": True,
                          "credit": {"mensualite": 1342, "duree_mois": 120,
                                     "programme_nom": "Crédit vert résidentiel"}},
        })

    elif variant == "long":
        # Page-3 density torture: factures model with exemple + seller +
        # everything else already on. Used by the pagination guard.
        d["savings_method"] = {
            "model": "factures", "approximatif": True,
            "facture_actuelle": 21400, "facture_avec_solaire": 6650,
            "economie": 14750,
            "ligne_methode": (
                "Chaque kWh est valorisé au prix de SA tranche (barème "
                "progressif du distributeur) : facture actuelle moins facture "
                "résiduelle après autoconsommation — jamais un prix moyen "
                "inventé."),
            "exemple": ("Facture actuelle ≈ 21 400 DH/an → avec solaire "
                        "≈ 6 650 DH/an → économie ≈ 14 750 DH/an"),
        }
        d["seller"] = {"nom": "Reda Kasri",
                       "telephone": "+212 6 61 85 04 10"}
        d["client_addr"] = ("Résidence Les Jardins d'Anfa, appartement 12, "
                            "45 boulevard d'Anfa, quartier Racine")

    return d
