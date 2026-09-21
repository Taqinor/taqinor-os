"""CAD20 — « jamais plus d'un appel ET d'un message par jour » s'exécute.

La règle était ÉCRITE dans le référentiel des cadences
(`apps/parametres/models_relance.py`) et appliquée NULLE PART. Deux façons de
la violer sans qu'aucun garde-fou ne bronche :

  * le recalage sur les jours ouvrés empile tout seul — un J+13 dominical et
    un J+14 retombent sur le même lundi, deux appels d'un lead du vendredi
    aussi ;
  * le fondateur pouvait décaler un délai depuis Paramètres et poser trois
    appels le même jour.

La garde vit dans `apps.crm.cadence_temps.un_geste_par_jour`, appelée en
DERNIER par `calculer_echeances_cadence` : une touche en trop glisse d'un jour
ouvré, à la même heure, recalée sur la fenêtre de son canal. Rien n'est
ajouté, retiré ni réordonné.

DEUX EXEMPTIONS, testées ici :
  * les trois gestes J0 du Protocole v3 (message d'identité, appel
    d'ouverture, appel 2) — ils sont VOULUS ensemble ;
  * le rendez-vous dominical, qui doit rester un dimanche.

Le temps est GELÉ.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CADENCE_CONTACT_DEFAUT)

User = get_user_model()

#: Lundi 7 septembre 2026, 07:00 — avant toute ouverture.
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)
LUNDI = datetime.date(2026, 9, 7)
JOURS_DARRIVEE = [LUNDI + datetime.timedelta(days=n) for n in range(7)]
VENDREDI = datetime.date(2026, 9, 11)
SAMEDI = datetime.date(2026, 9, 12)


def _a(jour, heure=11, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _genre(canal):
    return 'message' if horaires.est_un_message(canal) else 'appel'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class LeGabaritLuiMemeRespecteLaRegleTests(SimpleTestCase):
    """« La règle du fichier et le comportement disent la même chose » — on
    commence par le FICHIER : les gabarits livrés respectent-ils la règle
    qu'ils énoncent ?"""

    def _par_delai(self, gabarit):
        compte = {}
        for barreau in gabarit:
            cle = (barreau['delai_jours'], _genre(str(barreau['canal'])))
            compte[cle] = compte.get(cle, 0) + 1
        return compte

    def test_la_prise_de_contact_ne_double_QUE_a_J0(self):
        for (delai, genre), nombre in self._par_delai(
                CADENCE_CONTACT_DEFAUT).items():
            if delai == 0:
                continue
            self.assertEqual(nombre, 1, (delai, genre))

    def test_les_trois_gestes_J0_sont_bien_deux_appels_et_un_message(self):
        """L'exception, énoncée : c'est la promesse « rappelé dans les cinq
        minutes »."""
        compte = self._par_delai(CADENCE_CONTACT_DEFAUT)
        self.assertEqual(compte[(0, 'appel')], 2)
        self.assertEqual(compte[(0, 'message')], 1)

    def test_le_suivi_apres_devis_ne_double_jamais(self):
        for (delai, genre), nombre in self._par_delai(
                CADENCE_APRES_DEVIS_DEFAUT).items():
            self.assertEqual(nombre, 1, (delai, genre))


class _Base(TestCase):
    slug = 'cad20'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)

    def _partition(self, depart, cadence='contact'):
        return calculer_echeances_cadence(self.lead, cadence, depart)

    def _par_ordre(self, depart, cadence='contact'):
        return {g.ordre: e.astimezone(horaires.CASABLANCA)
                for g, e in self._partition(depart, cadence)}


class UnSeulGestePaJourTests(_Base):
    """Le « Done = » : vert sur les 7 jours d'arrivée."""

    slug = 'cad20-sept-jours'

    def _verifier(self, depart, cadence):
        seaux = {}
        for gabarit, echeance in self._partition(depart, cadence):
            jour = echeance.astimezone(horaires.CASABLANCA).date()
            cle = (jour, _genre(gabarit.canal))
            exemptee = (not gabarit.delai_jours
                        or bool(getattr(gabarit, 'dimanche_ok', False)))
            seaux.setdefault(cle, []).append((gabarit.ordre, exemptee))
        for cle, occupants in seaux.items():
            if len(occupants) == 1:
                continue
            # Un seul cas de doublon toléré : des touches TOUTES exemptées
            # (les trois gestes J0 du protocole).
            self.assertTrue(
                all(exemptee for _ordre, exemptee in occupants),
                (cadence, depart.date(), cle, occupants))

    def test_la_prise_de_contact_sur_les_sept_jours_darrivee(self):
        for jour in JOURS_DARRIVEE:
            self._verifier(_a(jour), 'contact')

    def test_le_suivi_apres_devis_sur_les_sept_jours_darrivee(self):
        for jour in JOURS_DARRIVEE:
            self._verifier(_a(jour), 'apres_devis')

    def test_le_nombre_et_lordre_des_touches_ne_changent_pas(self):
        for jour in JOURS_DARRIVEE:
            ordres = [g.ordre for g, _e in self._partition(_a(jour))]
            self.assertEqual(ordres, list(range(1, 12)), jour)


class LesExemptionsTests(_Base):
    """Ce que la garde ne touche JAMAIS."""

    slug = 'cad20-exemptions'

    def test_les_trois_gestes_J0_restent_sur_la_meme_journee(self):
        for jour in JOURS_DARRIVEE:
            plan = self._par_ordre(_a(jour))
            jours_j0 = {plan[ordre].date() for ordre in (1, 2, 3)}
            self.assertEqual(len(jours_j0), 1, (jour, plan))

    def test_les_deux_appels_J0_tiennent_dans_la_meme_journee(self):
        """C'est L'exception : deux appels le même jour, voulus."""
        plan = self._par_ordre(_a(LUNDI))
        self.assertEqual(plan[2].date(), plan[3].date())
        self.assertLess(plan[2], plan[3])

    def test_le_rendez_vous_dominical_nest_jamais_decale_hors_dimanche(self):
        for jour in JOURS_DARRIVEE:
            for gabarit, echeance in self._partition(_a(jour)):
                if getattr(gabarit, 'dimanche_ok', False):
                    self.assertEqual(
                        echeance.astimezone(horaires.CASABLANCA).weekday(),
                        6, (jour, gabarit.ordre))


class UneToucheEnTropGlisseDunJourTests(_Base):
    """Les deux empilements réels que le recalage produisait tout seul."""

    slug = 'cad20-glisse'

    def test_deux_appels_pousses_sur_le_meme_lundi_sont_separes(self):
        """Lead du vendredi : le J+1 (samedi) et le J+2 (dimanche) sont tous
        deux des APPELS recalés sur le lundi. Le second glisse au mardi."""
        plan = self._par_ordre(_a(VENDREDI))
        self.assertEqual(plan[4].date(), datetime.date(2026, 9, 14))
        self.assertEqual(plan[6].date(), datetime.date(2026, 9, 15))

    def test_les_deux_derniers_messages_apres_devis_sont_separes(self):
        """J+13 tombe un dimanche, recalé au lundi — le J+14 est déjà ce
        lundi-là. Le second glisse au mardi."""
        plan = self._par_ordre(_a(SAMEDI), 'apres_devis')
        self.assertEqual(plan[9].date(), datetime.date(2026, 9, 28))
        self.assertEqual(plan[10].date(), datetime.date(2026, 9, 29))

    def test_la_touche_glissee_reste_dans_la_fenetre_de_son_canal(self):
        for cadence in ('contact', 'apres_devis'):
            for jour in JOURS_DARRIVEE:
                for gabarit, echeance in self._partition(_a(jour), cadence):
                    self.assertTrue(
                        horaires.est_dans_fenetre(
                            echeance, self.company,
                            dimanche=bool(
                                getattr(gabarit, 'dimanche_ok', False)),
                            canal=gabarit.canal),
                        (cadence, jour, gabarit.ordre))

    def test_une_touche_glissee_ne_recule_jamais(self):
        """Le décalage va toujours vers l'AVANT : une touche n'est jamais
        avancée pour faire de la place."""
        for jour in JOURS_DARRIVEE:
            depart = _a(jour)
            origine = horaires.prochain_creneau_appel(
                depart, self.company, canal='whatsapp')
            for gabarit, echeance in self._partition(depart):
                self.assertGreaterEqual(
                    echeance, origine, (jour, gabarit.ordre))
