"""CAD23 — le rendez-vous dominical se cale sur le dimanche le PLUS PROCHE.

[TRANCHÉ 21/09/2026] `prochain_dimanche` prenait le premier dimanche ≥ J+5,
d'où une dérive mesurée de J+5 (lead du mardi) à J+11 (lead du mercredi) : le
rendez-vous glissait d'une semaine entière, et la touche J+7 du protocole,
née APRÈS lui, arrivait déjà en retard.

Décision fondateur : le dimanche le plus proche du J+N visé, AVANT ou après.
La veille compte autant que le lendemain. Le principe ne bouge pas — une
seule touche le dimanche, 16 h-19 h, pour les prospects qu'on ne trouve
jamais en semaine — et ni le nombre ni l'ordre des touches ne changent.

Ce que ce fichier verrouille :
  * `horaires.dimanche_le_plus_proche` choisit bien le plus proche des deux
    dimanches qui encadrent la cible, et ne remonte jamais sous son
    `plancher` (l'ancre de la cadence) ;
  * sur les 7 jours d'arrivée et les DEUX cadences qui portent une touche
    dominicale, l'écart entre le J+N visé et la date posée ne dépasse jamais
    3 jours, et la touche dominicale reste UNIQUE ;
  * `prochain_dimanche` n'est pas touchée : elle répond toujours à « le
    prochain dimanche à partir de tel instant ».

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

User = get_user_model()

#: Lundi 7 septembre 2026, 07:00 — avant toute ouverture.
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)
LUNDI = datetime.date(2026, 9, 7)
JOURS_DARRIVEE = [LUNDI + datetime.timedelta(days=n) for n in range(7)]

#: L'écart maximal toléré entre le J+N visé et le dimanche posé (Done CAD23).
ECART_MAX_JOURS = 3

#: Étiquette qui débloque le barreau « dimanche famille » du suivi après
#: devis — sans elle, `apres_devis` n'a aucune touche dominicale (MRY4).
TAG_FAMILLE = 'Décision à plusieurs'


def _q(jour, heure=11, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class DimancheLePlusProcheTests(SimpleTestCase):
    """La règle de date, isolée de toute base."""

    def _plus_proche(self, jour, heure=11, **kwargs):
        return horaires.dimanche_le_plus_proche(
            _q(jour, heure), **kwargs).astimezone(horaires.CASABLANCA)

    def test_un_mercredi_prend_le_dimanche_DAVANT(self):
        """Mercredi 9 : le dimanche 6 est à 3 jours, le 13 à 4."""
        quand = self._plus_proche(datetime.date(2026, 9, 9))
        self.assertEqual(quand.date(), datetime.date(2026, 9, 6))
        self.assertEqual((quand.hour, quand.minute), (16, 30))

    def test_un_jeudi_prend_le_dimanche_DAPRES(self):
        """Jeudi 10 : le dimanche 13 est à 3 jours, le 6 à 4."""
        quand = self._plus_proche(datetime.date(2026, 9, 10))
        self.assertEqual(quand.date(), datetime.date(2026, 9, 13))

    def test_une_cible_dominicale_reste_ce_dimanche(self):
        quand = self._plus_proche(datetime.date(2026, 9, 13), heure=12)
        self.assertEqual(quand.date(), datetime.date(2026, 9, 13))
        self.assertEqual((quand.hour, quand.minute), (16, 30))

    def test_un_dimanche_apres_la_fermeture_passe_au_suivant(self):
        quand = self._plus_proche(datetime.date(2026, 9, 13), heure=20)
        self.assertEqual(quand.date(), datetime.date(2026, 9, 20))

    def test_un_dimanche_dans_la_fenetre_ne_recule_jamais(self):
        quand = self._plus_proche(datetime.date(2026, 9, 13), heure=17)
        self.assertEqual((quand.date(), quand.hour), (
            datetime.date(2026, 9, 13), 17))

    def test_le_plancher_interdit_un_dimanche_avant_lancre(self):
        """Le dimanche le plus proche d'un lundi est la VEILLE : sans
        plancher, une touche J+1 tomberait avant l'arrivée du lead."""
        sans = self._plus_proche(LUNDI)
        self.assertEqual(sans.date(), datetime.date(2026, 9, 6))
        avec = self._plus_proche(LUNDI, plancher=_q(LUNDI))
        self.assertEqual(avec.date(), datetime.date(2026, 9, 13))

    def test_la_sortie_reste_dans_le_fuseau_dentree(self):
        entree = _q(datetime.date(2026, 9, 9)).astimezone(
            datetime.timezone.utc)
        resultat = horaires.dimanche_le_plus_proche(entree)
        self.assertEqual(resultat.tzinfo, datetime.timezone.utc)

    def test_prochain_dimanche_nest_PAS_touchee(self):
        """Garde négative : l'autre fonction garde son contrat — le prochain
        dimanche ≥ l'instant donné, jamais celui d'avant."""
        quand = horaires.prochain_dimanche(
            _q(datetime.date(2026, 9, 9))).astimezone(horaires.CASABLANCA)
        self.assertEqual(quand.date(), datetime.date(2026, 9, 13))


class _Base(TestCase):
    slug = 'cad23'

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
            ville='Bouskoura', owner=self.acteur, tags=TAG_FAMILLE)

    def _dominicales(self, depart, cadence):
        """`[(gabarit, échéance locale)]` des touches `dimanche_ok`."""
        return [(gabarit, echeance.astimezone(horaires.CASABLANCA))
                for gabarit, echeance in calculer_echeances_cadence(
                    self.lead, cadence, depart)
                if getattr(gabarit, 'dimanche_ok', False)]


class LEcartNeDepassePasTroisJoursTests(_Base):
    """Le « Done = », paramétré sur les 7 jours d'arrivée."""

    slug = 'cad23-ecart'

    def test_la_prise_de_contact_sur_les_sept_jours_darrivee(self):
        self._verifier('contact')

    def test_le_suivi_apres_devis_sur_les_sept_jours_darrivee(self):
        self._verifier('apres_devis')

    def _verifier(self, cadence):
        for jour in JOURS_DARRIVEE:
            depart = _q(jour)
            origine = horaires.prochain_creneau_appel(
                depart, self.company, canal='whatsapp'
            ).astimezone(horaires.CASABLANCA)
            dominicales = self._dominicales(depart, cadence)
            # Garde-fou du protocole : UNE seule touche dominicale.
            self.assertEqual(len(dominicales), 1, (cadence, jour))
            gabarit, quand = dominicales[0]
            self.assertEqual(quand.weekday(), 6, (cadence, jour))
            vise = origine.date() + datetime.timedelta(
                days=gabarit.delai_jours)
            self.assertLessEqual(
                abs((quand.date() - vise).days), ECART_MAX_JOURS,
                (cadence, jour, quand.date(), vise))
            # Jamais avant l'arrivée du lead.
            self.assertGreaterEqual(quand, origine, (cadence, jour))

    def test_elle_reste_dans_la_fenetre_dominicale(self):
        for cadence in ('contact', 'apres_devis'):
            for jour in JOURS_DARRIVEE:
                for _gabarit, quand in self._dominicales(_q(jour), cadence):
                    self.assertTrue(
                        horaires.est_dans_fenetre(
                            quand, self.company, dimanche=True),
                        (cadence, jour, quand))

    def test_la_derive_dune_semaine_a_disparu(self):
        """Le constat de la tâche, énoncé comme propriété : l'écart maximal
        sur la semaine tenait de J+5 à J+11 ; il ne dépasse plus 3 jours."""
        ecarts = []
        for jour in JOURS_DARRIVEE:
            depart = _q(jour)
            origine = horaires.prochain_creneau_appel(
                depart, self.company, canal='whatsapp'
            ).astimezone(horaires.CASABLANCA)
            gabarit, quand = self._dominicales(depart, 'contact')[0]
            vise = origine.date() + datetime.timedelta(
                days=gabarit.delai_jours)
            ecarts.append(abs((quand.date() - vise).days))
        self.assertLessEqual(max(ecarts), ECART_MAX_JOURS, ecarts)


class LeResteDuProtocoleNeBougePasTests(_Base):
    """Garde-fou : on ne déplace QUE la touche dominicale."""

    slug = 'cad23-garde-fou'

    def test_le_nombre_et_lordre_des_touches_sont_intacts(self):
        for jour in JOURS_DARRIVEE:
            ordres = [gabarit.ordre for gabarit, _e
                      in calculer_echeances_cadence(
                          self.lead, 'contact', _q(jour))]
            self.assertEqual(ordres, list(range(1, 12)), jour)

    def test_aucune_autre_touche_ne_tombe_un_dimanche(self):
        for cadence in ('contact', 'apres_devis'):
            for jour in JOURS_DARRIVEE:
                for gabarit, echeance in calculer_echeances_cadence(
                        self.lead, cadence, _q(jour)):
                    locale = echeance.astimezone(horaires.CASABLANCA)
                    if not getattr(gabarit, 'dimanche_ok', False):
                        self.assertLess(locale.weekday(), 5,
                                        (cadence, jour, gabarit.ordre))
