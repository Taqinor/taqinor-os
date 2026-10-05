"""CIQ303 — ``synthese_ci(data)`` (1/2) : système, énergie, provenance et
degré de certitude d'un devis C&I, par UNE fonction serveur PURE.

Tests PURS (``SimpleTestCase``, aucune base) sur une charge utile fabriquée à
la forme de ``build_quote_data`` et de la sortie moteur ``etude_ci`` (contrat
``etude_ci_preview.json``, CIQ2).
"""
import copy
import json

from django.test import SimpleTestCase

from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_SANS_ETUDE,
    STATUT_FERME,
    STATUT_SOUS_RESERVE,
    synthese_ci,
)

FACTURES = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900,
            12100, 10200, 9900]
PROV_FACTURE = {"origine": "lead", "detail": "facture", "date": "2026-09-10"}
PROV_CLIENT = {"origine": "lead", "detail": "client", "date": "2026-09-10"}


def _etude_ci(**surcharges):
    etude = {
        "entrees_resolues": {
            "kwh_mensuels": {"valeur": list(FACTURES),
                             "provenance": dict(PROV_FACTURE)},
            "tension": {"valeur": "bt", "provenance": dict(PROV_CLIENT)},
        },
        "sous_reserve_visite": {"valeur": False, "motif": None},
        "profil_charge": {"methode": "declare", "archetype": None},
        "bilan": {"production_kwh": 95425, "autoconso_kwh": 69466,
                  "taux_autoconso": 0.728, "taux_couverture": 0.466},
        "version": "ci-1",
    }
    etude.update(surcharges)
    return etude


def _data(etude_ci=None, **surcharges):
    data = {
        "mode_installation": "commercial",
        "langue_sortie": "fr",
        "puissance_kwc": 55.0,
        "nb_panneaux": 100,
        # La production « par ville » du pricing : JAMAIS servie à côté.
        "prod_kwh": 84480,
        "etude": {"etude_ci": etude_ci} if etude_ci is not None else {},
        "payment_terms": {"acompte": 50, "materiel": 40, "solde": 10},
        "total_sans": 297000.0,
        "total_avec": 397000.0,
        "sans_ok": True,
        "avec_ok": False,
    }
    data.update(surcharges)
    return data


class TestSyntheseCiCoeur(SimpleTestCase):

    def test_etude_moteur_complete_toutes_les_cles(self):
        s = synthese_ci(_data(_etude_ci()))
        for cle in ("version", "segment", "statut_etude", "a_confirmer",
                    "provenance", "systeme", "baseline", "energie",
                    "option_servie", "echeancier", "omissions"):
            self.assertIn(cle, s)
        self.assertEqual(s["segment"], "commercial")
        self.assertEqual(s["statut_etude"], STATUT_FERME)
        self.assertEqual(s["systeme"], {"kwc": 55, "nb_panneaux": 100,
                                        "production_kwh_an": 95425})
        self.assertEqual(s["energie"]["taux_autoconso_pct"], 72.8)
        self.assertEqual(s["energie"]["taux_couverture_pct"], 46.6)
        self.assertEqual(s["energie"]["methode"], "horaire_declare")
        self.assertEqual(set(s["energie"]["definitions"]),
                         {"autoconso", "couverture"})
        self.assertEqual(s["baseline"], {"source": "factures",
                                         "estimation": False,
                                         "factures_mensuelles": FACTURES})
        self.assertEqual(s["provenance"]["kwh_mensuels"], PROV_FACTURE)
        self.assertEqual(s["provenance"]["tension"], PROV_CLIENT)
        self.assertEqual(s["option_servie"], "sans_batterie")
        self.assertEqual(s["omissions"], [])

    def test_echeancier_au_centime_qui_somme_au_total(self):
        s = synthese_ci(_data(_etude_ci()))
        self.assertEqual([j["jalon"] for j in s["echeancier"]],
                         ["commande", "livraison", "mise_en_service"])
        self.assertEqual([j["pct"] for j in s["echeancier"]], [50, 40, 10])
        self.assertEqual([j["montant_ttc"] for j in s["echeancier"]],
                         [148500.0, 118800.0, 29700.0])
        self.assertAlmostEqual(
            sum(j["montant_ttc"] for j in s["echeancier"]), 297000.0, 2)

    def test_profil_type_methode_estimation(self):
        s = synthese_ci(_data(_etude_ci(
            profil_charge={"methode": "archetype",
                           "archetype": {"cle": "bureau"}})))
        self.assertEqual(s["energie"]["methode"], "archetype_estimation")

    def test_sous_reserve_visite_statut_et_a_confirmer(self):
        s = synthese_ci(_data(
            _etude_ci(sous_reserve_visite={
                "valeur": True, "motif": "site MT : relevé à la visite"}),
            mode_installation="industriel",
            entrees_ci_lead={"entrees": [], "manquants": [
                "compteur_puissance_kva", "type_toiture",
                "surface_toiture_m2", "jours_ouverture"]}))
        self.assertEqual(s["statut_etude"], STATUT_SOUS_RESERVE)
        cles = [a["cle"] for a in s["a_confirmer"]]
        self.assertEqual(cles, ["visite", "puissance_souscrite_kva", "toit"])
        self.assertEqual(s["a_confirmer"][0]["libelle"],
                         "site MT : relevé à la visite")

    def test_sans_etude_moteur_energie_absente_avec_motif(self):
        s = synthese_ci(_data(None))
        self.assertNotIn("energie", s)
        self.assertNotIn("baseline", s)
        self.assertIsNone(s["systeme"]["production_kwh_an"])
        blocs = {o["bloc"]: o["motif"] for o in s["omissions"]}
        self.assertEqual(blocs["energie"], MOTIF_SANS_ETUDE)
        self.assertIn("systeme.production_kwh_an", blocs)
        # Sans étude moteur, le document est préliminaire.
        self.assertEqual(s["statut_etude"], STATUT_SOUS_RESERVE)

    def test_une_seule_production_servie(self):
        s = synthese_ci(_data(_etude_ci()))
        blob = json.dumps(s, ensure_ascii=False)
        self.assertNotIn("84480", blob)
        self.assertEqual(s["systeme"]["production_kwh_an"], 95425)

    def test_kwh_declares_et_mois_interpoles(self):
        etude = _etude_ci()
        etude["entrees_resolues"]["kwh_mensuels"]["provenance"] = PROV_CLIENT
        s = synthese_ci(_data(etude))
        self.assertEqual(s["baseline"], {"source": "kwh_declares",
                                         "estimation": True})
        etude = _etude_ci()
        trous = list(FACTURES)
        trous[3] = None
        etude["entrees_resolues"]["kwh_mensuels"]["valeur"] = trous
        s = synthese_ci(_data(etude))
        self.assertEqual(s["baseline"]["source"], "mois_interpoles")
        self.assertTrue(s["baseline"]["estimation"])

    def test_option_batterie_ci302(self):
        s = synthese_ci(_data(
            _etude_ci(), option_servie="sans",
            option_batterie={"lignes": [{"designation": "x"}],
                             "totaux": {"ttc": 100000.0},
                             "valeur_chiffree": None,
                             "motif": "valeur non chiffrée"}))
        self.assertEqual(s["option_servie"], "sans_batterie")
        self.assertEqual(s["option_batterie"],
                         {"totaux": {"ttc": 100000.0},
                          "valeur_chiffree": None,
                          "motif": "valeur non chiffrée"})

    def test_definitions_dans_la_langue_du_document(self):
        for langue in ("en", "ar"):
            s = synthese_ci(_data(_etude_ci(), langue_sortie=langue))
            self.assertNotEqual(
                s["energie"]["definitions"]["autoconso"],
                "part de la production consommée sur place")

    def test_hors_ci_none_et_pure(self):
        self.assertIsNone(synthese_ci(_data(
            _etude_ci(), mode_installation="residentiel")))
        self.assertIsNone(synthese_ci(None))
        data = _data(_etude_ci())
        avant = copy.deepcopy(data)
        self.assertEqual(synthese_ci(data), synthese_ci(data))
        self.assertEqual(data, avant)

    def test_aucun_prix_achat(self):
        data = _data(_etude_ci())
        data["all_items"] = [{"designation": "x", "prix_achat": 1}]
        self.assertNotIn("prix_achat", json.dumps(synthese_ci(data)))
