"""CAD21 — l'heure imposée d'une touche survit au changement de jour.

`prochain_creneau_appel` ne savait que RECALER un instant dans la fenêtre de
son jour : dès qu'une touche passait au jour ouvré suivant, elle repartait de
l'OUVERTURE et son heure imposée était effacée. L'« Appel 4 » prévu à 18 h —
l'heure où un particulier est rentré chez lui — ressortait à 09 h le lundi
matin, et le réglage « Heure cible » de l'écran Paramètres ne tenait pas sa
promesse une fois sur trois. Les quatre heures imposées du protocole sont
10:30 (Appel 3), 18:00 (Appel 4), 10:30 (Appel 5 dominical) et 15:00
(Appel 6).

Ce que ce fichier verrouille :
  * `prochain_creneau_appel(..., heure_cible=…)` recombine la date du prochain
    jour ouvré avec l'heure imposée AVANT le contrôle de fenêtre ;
  * le GARDE-FOU : quand l'heure visée ne tient pas dans la fenêtre de ce
    jour-là — fermeture, pause de la prière du vendredi, fenêtre resserrée du
    Ramadan, fenêtre dominicale —, on retombe sur l'ouverture. Une touche ne
    sort JAMAIS de sa fenêtre pour honorer une heure cible ;
  * au niveau de la cadence, les trois heures imposées de la prise de contact
    tiennent pour les 7 jours d'arrivée.

Note de composition : le JOUR de sortie est gouverné par CAD19 (l'ancre unique
sur l'origine ouvrable) et CAD20 (un seul appel par jour) ; CAD21 ne promet
que l'HEURE. Les cas à la journée près sont donc vérifiés sur
`prochain_creneau_appel` elle-même, qui est la fonction que la tâche nomme.

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Lundi 7 septembre 2026, 07:00 — avant toute ouverture.
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)
LUNDI = datetime.date(2026, 9, 7)
JOURS_DARRIVEE = [LUNDI + datetime.timedelta(days=n) for n in range(7)]

DIMANCHE_13 = datetime.date(2026, 9, 13)
LUNDI_14 = datetime.date(2026, 9, 14)
JEUDI_10 = datetime.date(2026, 9, 10)
VENDREDI_11 = datetime.date(2026, 9, 11)
SAMEDI_12 = datetime.date(2026, 9, 12)

#: Les heures imposées du Protocole v3, par ordre de barreau (hors dominical,
#: dont l'heure est celle de la fenêtre 16 h-19 h).
HEURES_IMPOSEES = {4: datetime.time(10, 30),
                   6: datetime.time(18, 0),
                   10: datetime.time(15, 0)}


def _q(jour, heure, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad21'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _creneau(self, quand, **kwargs):
        return horaires.prochain_creneau_appel(
            quand, self.company, **kwargs
        ).astimezone(horaires.CASABLANCA)


class LHeureImposeeSurvitAuChangementDeJourTests(_Base):
    """Le cœur de CAD21, sur la fonction que la tâche nomme."""

    slug = 'cad21-survit'

    def test_un_appel_de_18h_un_dimanche_ressort_lundi_18h(self):
        """Le cas de la tâche : l'« Appel 4 », pas à 09 h le lundi matin."""
        quand = self._creneau(_q(DIMANCHE_13, 18), canal='appel',
                              heure_cible=datetime.time(18, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 18, 0))

    def test_un_appel_de_10h30_un_dimanche_ressort_lundi_10h30(self):
        """Le second cas de la tâche : l'« Appel 3 »."""
        quand = self._creneau(_q(DIMANCHE_13, 10, 30), canal='appel',
                              heure_cible=datetime.time(10, 30))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 10, 30))

    def test_sans_heure_cible_le_comportement_ne_change_pas(self):
        """Garde négative : le repli reste l'ouverture, comme avant."""
        quand = self._creneau(_q(DIMANCHE_13, 18), canal='appel')
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 9, 0))

    def test_le_jour_de_depart_nest_jamais_recompose(self):
        """Un instant DÉJÀ joignable sort inchangé : l'heure cible ne sert
        qu'à recomposer un AUTRE jour."""
        quand = self._creneau(_q(LUNDI_14, 11), canal='appel',
                              heure_cible=datetime.time(18, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 11, 0))


class LeGardeFouDeLaFenetreTests(_Base):
    """« Plutôt le comportement actuel que sortir de la fenêtre. »"""

    slug = 'cad21-garde-fou'

    def test_une_heure_cible_apres_la_fermeture_retombe_sur_louverture(self):
        quand = self._creneau(_q(DIMANCHE_13, 21), canal='appel',
                              heure_cible=datetime.time(21, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 9, 0))

    def test_une_heure_cible_dans_la_pause_du_vendredi_retombe(self):
        """La prière du vendredi ne s'applique qu'aux APPELS."""
        quand = self._creneau(_q(JEUDI_10, 23), canal='appel',
                              heure_cible=datetime.time(12, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (VENDREDI_11, 9, 0))

    def test_un_message_a_la_meme_heure_le_vendredi_la_garde(self):
        """Un message est silencieux : il ne dérange personne à la mosquée."""
        quand = self._creneau(_q(JEUDI_10, 23), canal='whatsapp',
                              heure_cible=datetime.time(12, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (VENDREDI_11, 12, 0))

    def test_pendant_le_RAMADAN_une_heure_du_soir_retombe_sur_louverture(self):
        """La fenêtre se resserre (10 h-14 h par défaut) : 18 h n'existe
        plus ce jour-là."""
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = datetime.date(2026, 9, 1)
        profil.ramadan_fin = datetime.date(2026, 9, 30)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        quand = self._creneau(_q(DIMANCHE_13, 18), canal='appel',
                              heure_cible=datetime.time(18, 0))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 10, 0))

    def test_pendant_le_RAMADAN_une_heure_de_la_fenetre_est_gardee(self):
        profil = CompanyProfile.objects.get(company=self.company)
        profil.ramadan_debut = datetime.date(2026, 9, 1)
        profil.ramadan_fin = datetime.date(2026, 9, 30)
        profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])
        quand = self._creneau(_q(DIMANCHE_13, 11, 30), canal='appel',
                              heure_cible=datetime.time(11, 30))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (LUNDI_14, 11, 30))

    def test_la_fenetre_dominicale_refuse_une_heure_de_semaine(self):
        """16 h-19 h : 10 h 30 un dimanche n'existe pas."""
        quand = self._creneau(_q(SAMEDI_12, 10, 30), canal='appel',
                              dimanche=True,
                              heure_cible=datetime.time(10, 30))
        self.assertEqual((quand.date(), quand.hour, quand.minute),
                         (DIMANCHE_13, 16, 0))


class LesHeuresDuProtocoleTiennentTests(_Base):
    """Au niveau de la CADENCE : ce que la commerciale voit dans sa file."""

    slug = 'cad21-cadence'

    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)

    def _par_ordre(self, depart):
        return {
            gabarit.ordre: echeance.astimezone(horaires.CASABLANCA)
            for gabarit, echeance in calculer_echeances_cadence(
                self.lead, 'contact', depart)
        }

    def test_les_trois_heures_imposees_tiennent_les_sept_jours(self):
        for jour in JOURS_DARRIVEE:
            plan = self._par_ordre(_q(jour, 11))
            for ordre, heure in HEURES_IMPOSEES.items():
                self.assertEqual(
                    (plan[ordre].hour, plan[ordre].minute),
                    (heure.hour, heure.minute), (jour, ordre))

    def test_un_lead_du_vendredi_19h45_garde_son_appel_4_a_18h(self):
        """Le cas nommé par la tâche : 18:00, jamais 09:00. Le JOUR est celui
        que CAD19 (ancre unique) et CAD20 (un appel par jour) lui donnent."""
        plan = self._par_ordre(_q(VENDREDI_11, 19, 45))
        self.assertEqual((plan[6].hour, plan[6].minute), (18, 0))
        self.assertNotEqual((plan[6].hour, plan[6].minute), (9, 0))

    def test_un_lead_du_samedi_garde_son_appel_3_a_10h30(self):
        plan = self._par_ordre(_q(SAMEDI_12, 11))
        self.assertEqual((plan[4].hour, plan[4].minute), (10, 30))

    def test_la_touche_dominicale_garde_son_heure_de_fenetre(self):
        """Garde négative : l'heure cible du gabarit (10:30) ne s'applique
        JAMAIS au rendez-vous dominical — il reste au milieu de 16 h-19 h."""
        for jour in JOURS_DARRIVEE:
            for gabarit, echeance in calculer_echeances_cadence(
                    self.lead, 'contact', _q(jour, 11)):
                if getattr(gabarit, 'dimanche_ok', False):
                    locale = echeance.astimezone(horaires.CASABLANCA)
                    self.assertEqual(locale.weekday(), 6, (jour,))
                    self.assertEqual((locale.hour, locale.minute), (16, 30),
                                     (jour,))

    def test_aucune_touche_ne_sort_de_sa_fenetre(self):
        for jour in JOURS_DARRIVEE:
            for gabarit, echeance in calculer_echeances_cadence(
                    self.lead, 'contact', _q(jour, 11)):
                self.assertTrue(
                    horaires.est_dans_fenetre(
                        echeance, self.company,
                        dimanche=bool(getattr(gabarit, 'dimanche_ok', False)),
                        canal=gabarit.canal),
                    (jour, gabarit.ordre))
