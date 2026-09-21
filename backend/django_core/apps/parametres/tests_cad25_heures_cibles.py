"""CAD25 — des créneaux par TYPE de touche, plus la minute d'arrivée du lead.

[TRANCHÉ 21/09/2026] 7 des 11 touches de la prise de contact et 9 des 10
barreaux après devis n'avaient AUCUNE heure cible : leur heure était celle de
l'arrivée du lead, ou celle de l'envoi du devis. Un devis fini à 19 h 50
faisait tomber « le PDF s'ouvre bien ? » à 19 h 50 le lendemain, et tous les
leads de nuit ou de week-end se regroupaient à l'ouverture.

Décision fondateur : un créneau par TYPE — MESSAGES à 09 h 30, APPELS entre
17 h 30 et 18 h 30 — posé en DÉFAUT DE SEED sur les barreaux qui n'en ont pas,
et réglable dans Paramètres comme les autres.

DEUX FAMILLES GARDENT VOLONTAIREMENT `heure_cible = None`, et ce fichier le
verrouille avec sa raison :
  * les trois gestes J0 de la prise de contact — une SÉQUENCE dans la journée
    (J0, +3 min, +2 h 30), pas un créneau : leur imposer une heure les
    écraserait sur la même minute, le défaut même que MRY5 a corrigé ;
  * les deux réveils J30/J60 — ils sont POSÉS sur un créneau d'étalement
    calculé par le placement (MRY30 : huit réveils par jour ouvré, 20 minutes
    d'écart) ; une heure imposée ferait retomber les huit sur la même minute.

Le temps est GELÉ.
"""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CADENCE_CONTACT_DEFAUT,
    CADENCE_REVEIL_DEFAUT, CRENEAU_APPEL, CRENEAU_APPEL_DEBUT,
    CRENEAU_APPEL_FIN, CRENEAU_MESSAGE, Cadence, CadenceRelanceEtape)

User = get_user_model()

#: Les canaux SILENCIEUX — même vocabulaire que `apps.crm.horaires`, repris
#: ici en littéral pour que ce fichier ne dépende d'aucun module de calcul.
CANAUX_MESSAGE = {'whatsapp', 'email'}

#: Le fuseau du terrain — nommé ici plutôt qu'importé du moteur CRM, pour que
#: ce fichier de fondation ne dépende de rien.
CASA = ZoneInfo('Africa/Casablanca')

#: Mardi 8 septembre 2026, 19 h 50 heure locale — après la fermeture des
#: appels, encore dans la fenêtre des messages : c'est l'heure d'envoi de
#: devis que la tâche nomme.
DEVIS_19H50 = datetime.datetime(2026, 9, 8, 19, 50, tzinfo=CASA)


def _est_message(canal):
    return str(canal).lower() in CANAUX_MESSAGE


class LesGabaritsPortentLeursCreneauxTests(SimpleTestCase):
    """Le « Done = » côté référentiel, sans toucher la base."""

    def test_aucun_barreau_J_PLUS_N_de_contact_nest_sans_heure(self):
        sans = [b for b in CADENCE_CONTACT_DEFAUT
                if b['delai_jours'] and b.get('heure_cible') is None]
        self.assertEqual(sans, [])

    def test_aucun_barreau_apres_devis_nest_sans_heure(self):
        sans = [b for b in CADENCE_APRES_DEVIS_DEFAUT
                if b.get('heure_cible') is None]
        self.assertEqual(sans, [])

    def test_les_messages_poses_le_sont_au_creneau_message(self):
        for gabarit in (CADENCE_CONTACT_DEFAUT, CADENCE_APRES_DEVIS_DEFAUT):
            for barreau in gabarit:
                if barreau.get('heure_cible') == CRENEAU_MESSAGE:
                    self.assertTrue(_est_message(barreau['canal']),
                                    barreau['libelle'])

    def test_les_appels_poses_le_sont_dans_la_fourchette_dappel(self):
        for gabarit in (CADENCE_CONTACT_DEFAUT, CADENCE_APRES_DEVIS_DEFAUT):
            for barreau in gabarit:
                if barreau.get('heure_cible') == CRENEAU_APPEL:
                    self.assertFalse(_est_message(barreau['canal']),
                                     barreau['libelle'])
        self.assertLessEqual(CRENEAU_APPEL_DEBUT, CRENEAU_APPEL)
        self.assertLessEqual(CRENEAU_APPEL, CRENEAU_APPEL_FIN)

    def test_les_trois_gestes_J0_gardent_leur_sequence(self):
        """L'exception assumée : J0, +3 min, +2 h 30 est une séquence dans la
        journée. Une heure imposée les écraserait sur la même minute."""
        j0 = [b for b in CADENCE_CONTACT_DEFAUT if not b['delai_jours']]
        self.assertEqual(len(j0), 3)
        for barreau in j0:
            self.assertIsNone(barreau.get('heure_cible'), barreau['libelle'])
        self.assertEqual(sorted(b['delai_minutes'] for b in j0), [0, 3, 150])

    def test_les_deux_reveils_gardent_leur_creneau_detalement(self):
        """Seconde exception : le placement (MRY30) POSE ces touches sur un
        créneau qu'il calcule — huit par jour ouvré, 20 minutes d'écart."""
        for barreau in CADENCE_REVEIL_DEFAUT:
            self.assertIsNone(barreau.get('heure_cible'), barreau['libelle'])

    def test_les_creneaux_tiennent_dans_les_fenetres_de_la_societe(self):
        """Garde-fou : jamais un créneau hors des bornes du profil société —
        et les bornes sont LUES sur le modèle, jamais recopiées."""
        champ = CompanyProfile._meta.get_field
        message_debut = champ('message_heure_debut').default
        appel_debut = champ('appel_heure_debut').default
        fermeture = champ('appel_heure_fin').default
        self.assertGreaterEqual(CRENEAU_MESSAGE, message_debut)
        self.assertLess(CRENEAU_MESSAGE, fermeture)
        self.assertGreaterEqual(CRENEAU_APPEL, appel_debut)
        self.assertLess(CRENEAU_APPEL, fermeture)


class LeSeedEcritLesCreneauxTests(TestCase):
    """Ils arrivent bien en base, et restent réglables par société."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad25-seed', defaults={'nom': 'cad25-seed'})
        CompanyProfile.objects.get_or_create(company=self.company)

    def test_la_touche_J1_du_suivi_apres_devis_est_seedee_a_0930(self):
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_DEVIS)
        etape = CadenceRelanceEtape.objects.get(
            company=self.company, cadence=Cadence.APRES_DEVIS, ordre=1)
        self.assertEqual(etape.heure_cible, CRENEAU_MESSAGE)

    def test_un_appel_de_suivi_est_seede_dans_la_fourchette(self):
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_DEVIS)
        etape = CadenceRelanceEtape.objects.get(
            company=self.company, cadence=Cadence.APRES_DEVIS, ordre=2)
        self.assertGreaterEqual(etape.heure_cible, CRENEAU_APPEL_DEBUT)
        self.assertLessEqual(etape.heure_cible, CRENEAU_APPEL_FIN)

    def test_le_seed_ne_rehabille_jamais_un_barreau_personnalise(self):
        """L'éditeur reste la source de vérité par société : un rejeu du seed
        ne réécrit pas une heure que le fondateur a changée."""
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_DEVIS)
        etape = CadenceRelanceEtape.objects.get(
            company=self.company, cadence=Cadence.APRES_DEVIS, ordre=1)
        etape.heure_cible = datetime.time(11, 15)
        etape.save(update_fields=['heure_cible'])
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.APRES_DEVIS)
        etape.refresh_from_db()
        self.assertEqual(etape.heure_cible, datetime.time(11, 15))


class UnDevisEnvoyeA1950Tests(TestCase):
    """Le second « Done = », vérifié sur le moteur de cadence."""

    def setUp(self):
        gel = frozen(DEVIS_19H50)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad25-devis', defaults={'nom': 'cad25-devis'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad25-devis-u', password='x',
            role_legacy='responsable', company=self.company)

    def test_la_touche_J1_part_a_0930_et_non_a_1950(self):
        # Import fonction-local : ce référentiel de FONDATION ne dépend pas du
        # moteur CRM — c'est le test qui vérifie l'effet de bout en bout.
        from apps.crm.models import Lead
        from apps.crm.services import calculer_echeances_cadence

        lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)
        premiere = None
        for gabarit, echeance in calculer_echeances_cadence(
                lead, 'apres_devis', DEVIS_19H50):
            if gabarit.ordre == 1:
                premiere = echeance.astimezone(CASA)
        self.assertIsNotNone(premiere)
        self.assertEqual((premiere.hour, premiere.minute),
                         (CRENEAU_MESSAGE.hour, CRENEAU_MESSAGE.minute))
        self.assertNotEqual((premiere.hour, premiere.minute), (19, 50))
