"""AMOT39 (C-AMOT-048) — ``synthese_ci`` reconnaît TOUTE feuille de
consommation que le moteur C&I peut retenir.

Avant : ``CLES_CONSOMMATION`` ne listait que cinq clés ; un lead à
``kwh_mensuel_declare`` ou ``bill_kwh`` (sonde VC lci4c) donnait une étude
CHIFFRÉE (couverture 27,6 %) et, sur la même page, « consommation de référence
non résolue par le moteur C&I ».

Les cas sont produits par le VRAI ``domain/etude_ci._consommation`` (aucun
mock) : chaque feuille est posée seule dans une ``_Resolution``, le moteur dit
la feuille qu'il retient, puis ``entrees_resolues()`` alimente
``synthese_ci``. Les deux conversions MAD (``facture_hiver_mad``,
``factures_mad`` en montants) exigent un tarif BT sourcé : elles sont jouées
sur les entrées résolues directement (même forme).
"""
from django.test import SimpleTestCase

from apps.ventes.domain import etude_ci as moteur
from apps.ventes.quote_engine.ci.synthese import (
    CLES_CONSOMMATION, MOTIF_BASELINE_ABSENTE, synthese_ci,
)

PROV_FACTURE = {"origine": "lead", "detail": "facture", "date": "2026-09-10"}
PROV_CLIENT = {"origine": "lead", "detail": "client", "date": "2026-09-10"}
MOIS = [20000 + 100 * m for m in range(12)]
RELEVES = [{"mois": "2026-%02d" % (m + 1), "kwh": MOIS[m]} for m in range(12)]

#: (feuille posée, valeur, provenance, source attendue, estimation attendue)
CAS_MOTEUR = (
    ("kwh_mensuels", list(MOIS), PROV_FACTURE, "factures", False),
    ("kwh_mensuel_declare", 20000, PROV_CLIENT, "kwh_declares", True),
    ("kwh_annuel", 240000, PROV_CLIENT, "kwh_declares", True),
    ("factures_mad", list(RELEVES), PROV_FACTURE, "factures", False),
    ("releve_kwh", list(RELEVES), PROV_FACTURE, "factures", False),
    ("bill_kwh", 18000, PROV_CLIENT, "kwh_declares", True),
)


def _data(entrees):
    return {
        "mode_installation": "industriel",
        "langue_sortie": "fr",
        "puissance_kwc": 50.0,
        "nb_panneaux": 90,
        "etude": {"etude_ci": {
            "entrees_resolues": entrees,
            "sous_reserve_visite": {"valeur": False, "motif": None},
            "profil_charge": {"methode": "declare"},
            "bilan": {"production_kwh": 79482, "taux_autoconso": 0.81,
                      "taux_couverture": 0.276},
        }},
        "payment_terms": {"acompte": 50, "materiel": 40, "solde": 10},
        "sans_ok": True,
        "avec_ok": False,
    }


def _motif_baseline(s):
    return next((o["motif"] for o in s["omissions"]
                 if o.get("bloc") == "baseline"), None)


class BaselineFeuillesTests(SimpleTestCase):

    def test_feuilles_retenues_par_le_moteur(self):
        for feuille, valeur, prov, source, estimation in CAS_MOTEUR:
            with self.subTest(feuille=feuille):
                res = moteur._Resolution()
                res.poser(feuille, valeur, prov)
                conso, retenue = moteur._consommation(res, {}, [], [])
                # Prémisse : le moteur CHIFFRE bien depuis cette feuille.
                self.assertIsNotNone(conso)
                self.assertEqual(retenue, feuille)
                self.assertIn(retenue, CLES_CONSOMMATION)
                s = synthese_ci(_data(res.entrees_resolues()))
                self.assertIn("baseline", s, f"{feuille} non reconnue")
                self.assertEqual(s["baseline"]["source"], source)
                self.assertIs(s["baseline"]["estimation"], estimation)
                self.assertIsNone(_motif_baseline(s))

    def test_conversions_mad_reconnues(self):
        # facture d'hiver (MAD) convertie par le moteur : estimation.
        s = synthese_ci(_data({"facture_hiver_mad": {
            "valeur": 4200, "provenance": dict(PROV_CLIENT)}}))
        self.assertEqual(s["baseline"], {"source": "kwh_declares",
                                         "estimation": True})
        self.assertIsNone(_motif_baseline(s))

    def test_toutes_les_sorties_du_moteur_listees(self):
        # Les sept feuilles que ``_consommation`` peut renvoyer.
        for feuille in ("kwh_mensuels", "kwh_mensuel_declare", "kwh_annuel",
                        "factures_mad", "releve_kwh", "facture_hiver_mad",
                        "bill_kwh"):
            self.assertIn(feuille, CLES_CONSOMMATION)

    def test_non_resolue_seulement_sans_consommation(self):
        s = synthese_ci(_data({"tension": {
            "valeur": "bt", "provenance": dict(PROV_CLIENT)}}))
        self.assertNotIn("baseline", s)
        self.assertEqual(_motif_baseline(s), MOTIF_BASELINE_ABSENTE)
