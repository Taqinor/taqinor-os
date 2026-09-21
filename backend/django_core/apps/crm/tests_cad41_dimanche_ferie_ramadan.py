"""CAD41 — la touche du dimanche ne court-circuite plus fériés ni Ramadan.

Constat de l'audit L3 du 21/09/2026 : ``if dimanche and d.weekday() == 6:
return (DIMANCHE_DEBUT, DIMANCHE_FIN, None)`` était évalué AVANT
``_jour_ouvre`` et AVANT ``est_en_ramadan``. Un Aïd tombant un dimanche
recevait donc quand même l'appel de 16 h 30 — exactement le scénario que
CAD40 veut éviter, même après avoir fait le travail — et, pendant le
Ramadan, la touche restait posée à 16 h 30 en plein jeûne, dans le creux
pré-ftour, jusqu'à 4 dimanches par an.

Les DEUX cas du Done :
  * dimanche férié → la touche est reportée (au dimanche SUIVANT, jamais au
    lundi : le seul rendez-vous dominical du protocole ne se transforme pas
    en appel de semaine) ;
  * dimanche en Ramadan → la touche tombe dans la fenêtre du mois.

Aucune touche n'est ajoutée, retirée ni réordonnée : c'est le PLACEMENT de la
touche 8 du protocole qui est corrigé.
"""
import datetime

from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.notifications.models import Holiday
from apps.parametres.models import CompanyProfile

#: Dimanche 15 mars 2026 — en plein Ramadan dans la période saisie ci-dessous.
DIMANCHE_RAMADAN = datetime.date(2026, 3, 15)
#: Dimanche 24 mai 2026 — hors Ramadan, libre, sert de témoin.
DIMANCHE_LIBRE = datetime.date(2026, 5, 24)
#: Dimanche 31 mai 2026 — le dimanche suivant le précédent.
DIMANCHE_SUIVANT = datetime.date(2026, 5, 31)

RAMADAN_DEBUT = datetime.date(2026, 2, 18)
RAMADAN_FIN = datetime.date(2026, 3, 19)


def _quand(jour, heure, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad41'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        self.profil = CompanyProfile.objects.create(company=self.company)

    def _ferie(self, jour, nom='Aïd al-Adha', recurrent=False):
        return Holiday.objects.create(
            company=self.company, date=jour, nom=nom,
            recurrent_annuel=recurrent)

    def _en_ramadan(self):
        self.profil.ramadan_debut = RAMADAN_DEBUT
        self.profil.ramadan_fin = RAMADAN_FIN
        self.profil.save(update_fields=['ramadan_debut', 'ramadan_fin'])


class DimancheTemoinTests(_Base):
    slug = 'cad41-temoin'

    def test_un_dimanche_ordinaire_garde_sa_fenetre_16h_19h(self):
        """Anti-régression : le rendez-vous dominical n'est pas supprimé."""
        self.assertEqual(
            horaires.fenetre_du_jour(
                DIMANCHE_LIBRE, self.company, dimanche=True),
            (horaires.DIMANCHE_DEBUT, horaires.DIMANCHE_FIN, None))
        self.assertEqual(
            horaires.prochain_creneau_appel(
                _quand(DIMANCHE_LIBRE, 16, 30), self.company, dimanche=True),
            _quand(DIMANCHE_LIBRE, 16, 30))

    def test_sans_le_drapeau_dimanche_rien_ne_change(self):
        """Le dimanche reste fermé pour toutes les AUTRES touches."""
        self.assertIsNone(
            horaires.fenetre_du_jour(DIMANCHE_LIBRE, self.company))


class DimancheFerieTests(_Base):
    slug = 'cad41-ferie'

    def test_un_dimanche_ferie_n_a_plus_de_fenetre(self):
        self._ferie(DIMANCHE_LIBRE)
        self.assertIsNone(
            horaires.fenetre_du_jour(
                DIMANCHE_LIBRE, self.company, dimanche=True))

    def test_la_touche_est_reportee_au_dimanche_SUIVANT(self):
        """Jamais au lundi : le seul rendez-vous dominical du protocole ne se
        transforme pas en appel de semaine."""
        self._ferie(DIMANCHE_LIBRE)
        creneau = horaires.prochain_creneau_appel(
            _quand(DIMANCHE_LIBRE, 16, 30), self.company, dimanche=True)
        self.assertEqual(creneau.date(), DIMANCHE_SUIVANT)
        self.assertEqual(creneau.weekday(), 6)
        self.assertEqual(creneau.hour, horaires.DIMANCHE_DEBUT.hour)

    def test_deux_dimanches_feries_de_suite_sautent_au_troisieme(self):
        self._ferie(DIMANCHE_LIBRE)
        self._ferie(DIMANCHE_SUIVANT, nom='Aïd al-Adha (2e jour)')
        creneau = horaires.prochain_creneau_appel(
            _quand(DIMANCHE_LIBRE, 16, 30), self.company, dimanche=True)
        self.assertEqual(creneau.date(),
                         DIMANCHE_SUIVANT + datetime.timedelta(days=7))

    def test_un_ferie_un_autre_jour_ne_ferme_pas_le_dimanche(self):
        """Anti-faux-vert : c'est bien la date du dimanche qui est lue."""
        self._ferie(DIMANCHE_LIBRE - datetime.timedelta(days=1))
        self.assertEqual(
            horaires.fenetre_du_jour(
                DIMANCHE_LIBRE, self.company, dimanche=True),
            (horaires.DIMANCHE_DEBUT, horaires.DIMANCHE_FIN, None))


class DimancheEnRamadanTests(_Base):
    slug = 'cad41-ramadan'

    def test_la_fenetre_du_dimanche_devient_celle_du_ramadan(self):
        self._en_ramadan()
        self.assertEqual(
            horaires.fenetre_du_jour(
                DIMANCHE_RAMADAN, self.company, dimanche=True),
            (datetime.time(9, 0), datetime.time(15, 0), None))

    def test_16h30_en_plein_jeune_n_est_plus_un_creneau(self):
        self._en_ramadan()
        self.assertFalse(
            horaires.est_dans_fenetre(
                _quand(DIMANCHE_RAMADAN, 16, 30), self.company,
                dimanche=True))

    def test_la_touche_tombe_dans_la_fenetre_du_ramadan_le_MEME_dimanche(self):
        """Le second cas du Done : pas une semaine plus tard."""
        self._en_ramadan()
        creneau = horaires.prochain_creneau_appel(
            _quand(DIMANCHE_RAMADAN, 16, 30), self.company, dimanche=True)
        self.assertEqual(creneau.date(), DIMANCHE_RAMADAN)
        self.assertTrue(
            horaires.est_dans_fenetre(creneau, self.company, dimanche=True))

    def test_un_dimanche_de_ramadan_ET_ferie_reste_reporte(self):
        """Le férié prime : on ne rappelle personne le jour de la fête, même
        dans la fenêtre du mois."""
        self._en_ramadan()
        self._ferie(DIMANCHE_RAMADAN, nom='Aïd al-Fitr')
        self.assertIsNone(
            horaires.fenetre_du_jour(
                DIMANCHE_RAMADAN, self.company, dimanche=True))
