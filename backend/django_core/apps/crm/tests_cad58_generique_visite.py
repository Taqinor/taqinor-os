"""CAD58 — le canal VISITE quitte la cadence générique : J+35 est un appel.

[TRANCHÉ 21/09/2026] Le barreau 5 de ``CADENCE_RELANCE_DEFAUT`` portait
``canal: VISITE`` à J+35 sans poser AUCUNE condition de devis, alors que la
décision fondateur du 15/09 est « visite technique JAMAIS avant le devis,
proposée après ».

Garde-fou : les 5 barreaux de la générique ne sont ni supprimés ni
réordonnés — seul le canal du dernier change. Et une société seedée AVANT
cette date garde sa ligne en base (``seed_cadence`` ne retouche jamais un
barreau existant) : la normalisation a donc lieu à la MATÉRIALISATION, là où
la touche devient réelle.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    CANAL_VISITE, calculer_echeances_cadence, initialiser_plan_relance,
)
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCE_RELANCE_DEFAUT, CADENCES_DEFAUT, CadenceRelanceEtape,
    CanalRelance,
)

User = get_user_model()

#: Lundi 7 septembre 2026, 10 h — l'ancre de la cadence.
DEPART = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 2 novembre 2026, 10 h — APRÈS le J+35, pour que la touche soit
#: matérialisée (la cadence est réactive : seules les échéances passées plus
#: la première à venir naissent d'un coup).
MAINTENANT = datetime.datetime(2026, 11, 2, 10, 0,
                               tzinfo=horaires.CASABLANCA)


class GabaritsParDefautTests(SimpleTestCase):
    def test_plus_aucun_barreau_de_gabarit_ne_porte_le_canal_visite(self):
        """Le premier Done, sur TOUS les gabarits."""
        for cadence, barreaux in CADENCES_DEFAUT.items():
            for barreau in barreaux:
                with self.subTest(cadence=cadence, ordre=barreau['ordre']):
                    self.assertNotEqual(barreau['canal'], CanalRelance.VISITE)

    def test_le_J35_de_la_generique_est_un_APPEL(self):
        dernier = CADENCE_RELANCE_DEFAUT[-1]
        self.assertEqual(dernier['delai_jours'], 35)
        self.assertEqual(dernier['canal'], CanalRelance.APPEL)

    def test_la_generique_garde_ses_CINQ_barreaux_dans_l_ordre(self):
        """Ni supprimés, ni réordonnés — seul le canal du dernier change."""
        self.assertEqual([b['ordre'] for b in CADENCE_RELANCE_DEFAUT],
                         [1, 2, 3, 4, 5])
        self.assertEqual([b['delai_jours'] for b in CADENCE_RELANCE_DEFAUT],
                         [2, 5, 10, 20, 35])


class GabaritLegacyTests(TestCase):
    """Une société seedée AVANT le 21/09/2026 garde sa ligne `visite`."""

    def setUp(self):
        from testkit.time import frozen

        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(slug='cad58', nom='cad58')
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad58-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            stage=stages.CONTACTED)
        # LA ligne héritée : un barreau générique encore en `visite`.
        self.barreau = CadenceRelanceEtape.objects.create(
            company=self.company, cadence='generique', ordre=5,
            delai_jours=35, delai_minutes=0, heure_cible=None,
            canal=CanalRelance.VISITE, libelle='Dernière relance',
            template_cle='', actif=True)

    def test_la_touche_MATERIALISEE_n_est_jamais_une_visite(self):
        initialiser_plan_relance(
            self.lead, self.acteur, cadence='generique', depart=DEPART)
        touches = self.lead.relance_etapes.filter(cadence='generique')
        self.assertTrue(touches.exists())
        for touche in touches:
            with self.subTest(ordre=touche.ordre):
                self.assertNotEqual(touche.canal, CANAL_VISITE)
        self.assertEqual(touches.get(ordre=5).canal, RelanceEtape.Canal.APPEL)

    def test_le_gabarit_en_base_n_est_PAS_reecrit_en_douce(self):
        """`seed_cadence` ne retouche jamais un barreau existant : la
        normalisation a lieu à la matérialisation, pas dans le référentiel."""
        initialiser_plan_relance(
            self.lead, self.acteur, cadence='generique', depart=DEPART)
        self.barreau.refresh_from_db()
        self.assertEqual(self.barreau.canal, CanalRelance.VISITE)

    def test_le_calcul_des_echeances_utilise_la_fenetre_d_APPEL(self):
        """Un `visite` legacy ne doit pas emprunter la fenêtre des messages."""
        echeances = calculer_echeances_cadence(
            self.lead, 'generique', DEPART)
        self.assertTrue(echeances)
        _gabarit, echeance = echeances[-1]
        locale = echeance.astimezone(horaires.CASABLANCA)
        self.assertGreaterEqual(locale.time(), datetime.time(9, 0))
