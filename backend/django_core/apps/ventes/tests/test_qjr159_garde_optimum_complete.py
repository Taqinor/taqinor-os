"""QJR159 — la garde « un optimum ne se publie que s'il décrit CE devis »
couvre TOUS les nombres du moteur.

``_optimum_decrit_ce_devis`` n'était appelée qu'à UN endroit et ne protégeait
que ``residuel_kwh_mois``, ``tranche_apres`` et ``remplissage.moyen``. Trois
trous vérifiés :

(a) la carte « Part des pointes rattrapée par la batterie » n'avait AUCUNE
    garde de configuration : ``_part_glitch_pct`` ne testait que ``_sans > 0``,
    ni ``BATTERIE_KWH_TOTAL``, ni ``_capacite_batterie_vendue()``, ni
    ``ONEPAGE_BRANCHE`` — sur un devis résidentiel SANS stockage mais avec un
    équipement à impulsions (piscine, clim), elle sortait « 0 % » et annonçait
    le bénéfice d'un composant ABSENT du devis ;
(b) le bloc bancable (P50, P90, ratio de performance, cascade de pertes) était
    publié sans aucune preuve qu'il décrive le champ PV vendu : le builder
    recopie ``etude_params['simulation']`` sans condition et cette clé ne fait
    pas partie des études rafraîchies — un devis redimensionné après l'étude
    imprimait le productible d'un AUTRE champ PV à côté de sa vraie
    « Puissance crête » ;
(c) même quand la garde passe, elle prouve l'appartenance à l'option AVEC
    (``_capacite_batterie_vendue`` suit ``ONEPAGE_BRANCHE``, que le builder
    fixe à ``'avec'`` pour tout devis à deux options, y compris en
    ``pdf_mode='full'``) sans jamais l'ÉCRIRE.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr159_garde_optimum_complete -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur


ETUDE_GLITCH = {
    "etude_horaire": {"annuel": {"part_glitch_sans_kwh": 180.0,
                                 "part_glitch_batterie_kwh": 120.0}},
}

SIMULATION = {
    "zones": [{"label": "Pan Sud", "kwc": 7.7,
               "base_production_kwh": 12486}],
    "pr": {"p50_kwh": 12486, "p90_kwh": 10200,
           "performance_ratio": 0.812,
           "loss_breakdown": {"temperature": 8.0, "soiling": 3.0}},
}


class _EtatMoteur(SimpleTestCase):
    """Pose/restaure les globales du moteur (il en écrit à l'ingestion)."""

    NOMS = ("ETUDE", "KWC", "NB_PAN", "BATTERIE_KWH_TOTAL", "ONEPAGE_BRANCHE",
            "SCENARIO", "PUISSANCE_INCONNUE")

    #: Certaines globales n'existent qu'après ``apply_quote_data``.
    _ABSENT = object()

    def setUp(self):
        self._sauvegarde = {n: getattr(moteur, n, self._ABSENT)
                            for n in self.NOMS}

    def tearDown(self):
        for nom, valeur in self._sauvegarde.items():
            if valeur is self._ABSENT:
                if hasattr(moteur, nom):
                    delattr(moteur, nom)
            else:
                setattr(moteur, nom, valeur)

    def _poser(self, **etat):
        for nom, valeur in etat.items():
            setattr(moteur, nom, valeur)


class TestTrouA_CartePointes(_EtatMoteur):
    """(a) — la carte des pointes exige une batterie RÉELLEMENT vendue."""

    def test_sans_stockage_la_carte_disparait(self):
        self._poser(ETUDE=ETUDE_GLITCH, BATTERIE_KWH_TOTAL=0.0,
                    ONEPAGE_BRANCHE=None, SCENARIO="Sans batterie")
        self.assertIsNone(moteur._part_glitch_pct())

    def test_branche_sans_du_document_la_carte_disparait(self):
        # Capacité présente sur l'option AVEC, mais le document ne chiffre
        # que la branche SANS : rien n'est vendu qui rattrape les pointes.
        self._poser(ETUDE=ETUDE_GLITCH, BATTERIE_KWH_TOTAL=5.0,
                    ONEPAGE_BRANCHE="sans", SCENARIO="Sans batterie")
        self.assertIsNone(moteur._part_glitch_pct())

    def test_avec_stockage_vendu_la_carte_est_rendue(self):
        self._poser(ETUDE=ETUDE_GLITCH, BATTERIE_KWH_TOTAL=5.0,
                    ONEPAGE_BRANCHE="avec",
                    SCENARIO="Les deux (Sans + Avec)")
        self.assertEqual(moteur._part_glitch_pct(), 67)

    def test_jamais_zero_pour_cent_sur_un_devis_sans_batterie(self):
        """Le cas exact du constat : équipement à impulsions, pas de batterie
        rattrapée — l'ancienne fonction rendait « 0 % »."""
        etude = {"etude_horaire": {"annuel": {
            "part_glitch_sans_kwh": 180.0, "part_glitch_batterie_kwh": 0.0}}}
        self._poser(ETUDE=etude, BATTERIE_KWH_TOTAL=0.0,
                    ONEPAGE_BRANCHE=None, SCENARIO="Sans batterie")
        self.assertIsNone(moteur._part_glitch_pct())


class TestTrouB_BlocBancable(_EtatMoteur):
    """(b) — le bloc bancable prouve qu'il décrit le champ PV vendu."""

    def test_concordance_le_bloc_est_rendu(self):
        self._poser(KWC=7.7, PUISSANCE_INCONNUE=False)
        self.assertTrue(moteur._bankable_decrit_ce_champ(SIMULATION))
        self.assertIn("Production P50", moteur._bankable_block_html(SIMULATION))

    def test_champ_pv_different_le_bloc_est_omis(self):
        # Devis redimensionné APRÈS l'étude : 12 kWc vendus, 7,7 simulés.
        self._poser(KWC=12.0, PUISSANCE_INCONNUE=False)
        self.assertFalse(moteur._bankable_decrit_ce_champ(SIMULATION))
        self.assertEqual(moteur._bankable_block_html(SIMULATION), "")

    def test_tolerance_d_arrondi_acceptee(self):
        self._poser(KWC=7.71, PUISSANCE_INCONNUE=False)
        self.assertTrue(moteur._bankable_decrit_ce_champ(SIMULATION))

    def test_un_panneau_de_plus_est_refuse(self):
        # 14 → 15 panneaux de 550 W : +0,55 kWc, bien au-delà d'un arrondi.
        self._poser(KWC=8.25, PUISSANCE_INCONNUE=False)
        self.assertFalse(moteur._bankable_decrit_ce_champ(SIMULATION))

    def test_puissance_inconnue_ou_zones_illisibles_refusees(self):
        self._poser(KWC=7.7, PUISSANCE_INCONNUE=True)
        self.assertFalse(moteur._bankable_decrit_ce_champ(SIMULATION))
        self._poser(KWC=7.7, PUISSANCE_INCONNUE=False)
        for mauvais in ({}, {"zones": []}, {"zones": "x"},
                        {"zones": [{"kwc": "?"}]}, {"zones": [{}]},
                        {"zones": [{"kwc": 0}]}):
            with self.subTest(entree=mauvais):
                self.assertFalse(moteur._bankable_decrit_ce_champ(mauvais))
                self.assertEqual(moteur._bankable_block_html(mauvais), "")

    def test_somme_de_plusieurs_zones(self):
        sim = {**SIMULATION, "zones": [
            {"kwc": 4.0}, {"kwc": 3.7}]}
        self._poser(KWC=7.7, PUISSANCE_INCONNUE=False)
        self.assertTrue(moteur._bankable_decrit_ce_champ(sim))


class TestTrouC_BrancheNommee(_EtatMoteur):
    """(c) — la branche décrite est ÉCRITE, pas seulement prouvée."""

    def test_document_a_deux_options_nomme_l_option_avec(self):
        self._poser(SCENARIO="Les deux (Sans + Avec)",
                    BATTERIE_KWH_TOTAL=5.0, ONEPAGE_BRANCHE="avec")
        self.assertIn("option avec batterie", moteur._branche_nommee())
        self.assertIn("option avec batterie", moteur._branche_phrase())

    def test_document_mono_option_ne_precise_rien(self):
        self._poser(SCENARIO="Avec batterie", BATTERIE_KWH_TOTAL=5.0,
                    ONEPAGE_BRANCHE="avec")
        self.assertEqual(moteur._branche_nommee(), "")
        self.assertEqual(moteur._branche_phrase(), "")

    def test_sans_batterie_vendue_aucune_precision(self):
        self._poser(SCENARIO="Les deux (Sans + Avec)",
                    BATTERIE_KWH_TOTAL=0.0, ONEPAGE_BRANCHE=None)
        self.assertEqual(moteur._branche_nommee(), "")
