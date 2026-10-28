"""CIQ318 — bloc « Offre de financement » facultatif, construit seulement
depuis l'offre écrite saisie par le vendeur (D-CIQ-15).

Tests PURS : ``ci/blocs.bloc_financement`` sur la synthèse servie, le bloc
``financement`` produit par la VRAIE fonction ``economie_ci.financement_ci``.
"""
from django.test import SimpleTestCase

from apps.ventes.economie_ci import financement_ci
from apps.ventes.quote_engine.ci.blocs import bloc_financement
from apps.ventes.quote_engine.montants import fmt_centimes

BASE_HT = {"base": "ht", "economie_annee1_ht_mad": 246350.0,
           "economie_annee1_ttc_mad": 295620.0}
OFFRE = {"source": "offre écrite de Prêteur Exemple du 15/09/2026",
         "nature": "credit", "base_echeance": "ht", "duree_mois": 84,
         "echeance_mad": 12000, "preteur": "Prêteur Exemple",
         "reference_offre": "OFF-01", "date_offre": "2026-09-15"}


def _synthese(offre, base_eco=BASE_HT, **reglages):
    financement = financement_ci(offre, base_eco,
                                 mode_installation="industriel", **reglages)
    argent = {"base": base_eco["base"]}
    if financement is not None:
        argent["financement"] = financement
    return {"argent": argent}


class BlocFinancement(SimpleTestCase):

    def test_offre_absente_chaine_vide(self):
        self.assertEqual(bloc_financement(_synthese(None)), "")
        self.assertEqual(bloc_financement({}), "")
        self.assertEqual(bloc_financement({"argent": None}), "")

    def test_offre_de_credit_meme_base(self):
        synthese = _synthese(dict(OFFRE))
        html = bloc_financement(synthese)
        fin = synthese["argent"]["financement"]
        self.assertIn("Offre de crédit de Prêteur Exemple", html)
        self.assertIn(f"{fmt_centimes(fin['echeance_mad'])}&#160;MAD HT sur "
                      "84 mois", html)
        self.assertIn(f"{fmt_centimes(fin['economie_mensuelle_moyenne_mad'])}"
                      "&#160;MAD HT", html)
        self.assertNotIn("TTC", html)
        self.assertNotIn("taux", html.lower())

    def test_credit_bail_sans_levee_libelle_generique(self):
        offre = dict(OFFRE, nature="credit_bail")
        html = bloc_financement(_synthese(offre))
        self.assertIn("Offre de financement", html)
        self.assertNotIn("crédit-bail", html.lower())

    def test_credit_bail_leve_par_le_reglage(self):
        offre = dict(OFFRE, nature="credit_bail")
        html = bloc_financement(_synthese(
            offre, mention_credit_bail_autorisee=True))
        self.assertIn("Offre de crédit-bail", html)

    def test_preteur_jamais_nomme_sans_reference(self):
        offre = dict(OFFRE, reference_offre="")
        html = bloc_financement(_synthese(offre))
        self.assertNotIn("Prêteur Exemple du", html)

    # CEC15 (affichage) — apport, frais et retour de l'offre, lus servis.
    def test_apport_frais_et_retour_de_l_offre_imprimes(self):
        synthese = _synthese(dict(OFFRE, apport_mad=180000, frais_mad=5000))
        fin = synthese["argent"]["financement"]
        html = bloc_financement(synthese)
        self.assertIn("Apport à la signature&#160;: "
                      f"{fmt_centimes(180000)}&#160;MAD", html)
        self.assertIn(f"Frais de l'offre&#160;: {fmt_centimes(5000)}&#160;MAD",
                      html)
        retour = f"{fin['retour_offre_ans']:.1f}".replace(".", ",")
        self.assertIn(f"Retour sur l'offre&#160;: {retour}&nbsp;ans", html)
        # l'écart mensuel reste imprimé tel que servi
        self.assertIn(f"{fmt_centimes(fin['ecart_mensuel_mad'])}&#160;MAD HT",
                      html)

    def test_sans_apport_ni_retour_servi_lignes_omises(self):
        synthese = _synthese(dict(OFFRE))
        synthese["argent"]["financement"].pop("retour_offre_ans", None)
        html = bloc_financement(synthese)
        self.assertNotIn("Apport", html)
        self.assertNotIn("Frais de l'offre", html)
        self.assertNotIn("Retour sur l'offre", html)

    def test_libelles_traduits_en_anglais(self):
        synthese = _synthese(dict(OFFRE, apport_mad=180000))
        html = bloc_financement(synthese, doc={"langue_sortie": "en"})
        self.assertIn("Deposit at signature", html)
        self.assertIn("Payback with the offer", html)
