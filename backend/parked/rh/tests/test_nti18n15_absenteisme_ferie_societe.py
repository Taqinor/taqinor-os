"""Tests NTI18N15 — ``taux_absenteisme``/``_jours_absence_dans_fenetre``

consomment désormais les fériés RÉELS de la société (``notifications.Holiday``,
fixes additionnels ET mobiles saisis manuellement) au lieu de la seule table
fixe ``rh.holidays.JOURS_FERIES_FIXES_MA`` codée en dur — via
``services.feries_periode`` (même surface cross-app-safe que ZRH1), la table
dict restant le repli automatique quand aucune ``Holiday`` n'est configurée.

Périmètre RH uniquement : la sélection multi-pays de la table de repli
(NTI18N13) et le calendrier ``planning projet``/``plans_entretien_status``
cités par la tâche vivent dans d'autres apps (``apps.gestion_projet``,
``apps.sav``) et sont HORS PÉRIMÈTRE de ce module — voir le rapport de tâche.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.notifications.models import Holiday
from apps.rh import selectors
from apps.rh.models import DemandeConge, DossierEmploye, TypeAbsence

DEBUT = date(2026, 3, 1)
FIN = date(2026, 3, 31)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TauxAbsenteismeFerieSocieteTests(TestCase):
    def setUp(self):
        self.co = make_company('nti18n15-a', 'A')
        self.employes = [
            DossierEmploye.objects.create(
                company=self.co, matricule=f'A-{i}', nom=f'Nom{i}',
                prenom='P', date_embauche=date(2024, 1, 1))
            for i in range(2)
        ]
        self.conge = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True)

    def _demande(self, employe, debut, fin):
        return DemandeConge.objects.create(
            company=self.co, employe=employe, type_absence=self.conge,
            date_debut=debut, date_fin=fin, jours=Decimal('0'),
            statut=DemandeConge.Statut.VALIDEE)

    def test_jours_ouvres_periode_sans_holiday_inchange(self):
        # Mars 2026 ne recoupe aucun férié fixe marocain (table MA) : 22
        # jours ouvrés — comportement identique à avant NTI18N15.
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['jours_ouvres_periode'], 22)

    def test_jours_ouvres_periode_exclut_ferie_societe_configure(self):
        # Mardi 2026-03-17 configuré comme férié société (mobile, jamais
        # dans la table fixe) : le dénominateur perd exactement ce jour.
        Holiday.objects.create(
            company=self.co, date=date(2026, 3, 17),
            nom='Férié société test', recurrent_annuel=False)
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['jours_ouvres_periode'], 21)

    def test_conge_borne_exclut_ferie_societe_configure(self):
        # Demande du lundi 2026-03-16 au vendredi 2026-03-20 = 5 jours ouvrés
        # sans férié société. Avec le mardi 17/03 configuré comme férié
        # société, la même demande ne compte plus que 4 jours.
        self._demande(self.employes[0], date(2026, 3, 16), date(2026, 3, 20))
        sans_ferie = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(sans_ferie['par_motif']['conge'], 5.0)

        Holiday.objects.create(
            company=self.co, date=date(2026, 3, 17),
            nom='Férié société test', recurrent_annuel=False)
        avec_ferie = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(avec_ferie['par_motif']['conge'], 4.0)

    def test_isolation_societe_ferie_autre_societe_sans_effet(self):
        autre = make_company('nti18n15-b', 'B')
        Holiday.objects.create(
            company=autre, date=date(2026, 3, 17),
            nom='Férié société voisine', recurrent_annuel=False)
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['jours_ouvres_periode'], 22)
