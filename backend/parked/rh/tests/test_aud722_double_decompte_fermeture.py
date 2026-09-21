"""AUD722 — plus de double décompte congé personnel ↔ fermeture collective.

DÉFAUT (rouge avant ce correctif), dans les DEUX sens :

* `appliquer_fermeture` ne dédoublonnait que contre les `DemandeConge` générées
  par CETTE fermeture (tag `motif`), jamais contre une `DemandeConge`
  personnelle VALIDÉE préexistante chevauchant la période — puis appelait
  `valider_demande()`, qui incrémente `SoldeConge.pris` sans aucun contrôle de
  chevauchement. Les jours communs étaient retirés DEUX FOIS du solde ;
* symétriquement, `jour_bloque_conflit` — seul contrôle appelé à la soumission —
  n'interroge que `JourBloqueConge`, jamais `PeriodeFermeture` ni les
  `DemandeConge` déjà validées.

Après correctif : les jours déjà couverts sont retirés du décompte dans les deux
sens, un employé entièrement couvert n'est plus re-généré, et une demande
entièrement couverte est refusée explicitement.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DemandeConge,
    DossierEmploye,
    PeriodeFermeture,
    SoldeConge,
    TypeAbsence,
)

User = get_user_model()

DEMANDES = '/api/django/rh/demandes-conge/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DoubleDecompteFermetureTests(TestCase):
    """Le scénario exact de la tâche : congé 10→20 août, fermeture 15→25."""

    def setUp(self):
        self.co = make_company('aud722', 'A')
        self.rh = make_user(self.co, 'aud722-rh')
        self.type_cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=False, deduit_solde=True)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='F1', nom='Tazi', prenom='Reda',
            statut=DossierEmploye.Statut.ACTIF)
        SoldeConge.objects.create(
            company=self.co, employe=self.emp, annee=2026,
            acquis=Decimal('30.00'))

    def _conge_valide(self, debut, fin):
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.type_cp,
            date_debut=debut, date_fin=fin,
            jours=services.calculer_jours_demande(self.type_cp, debut, fin))
        services.valider_demande(demande, decide_par=self.rh)
        return demande

    def _solde(self):
        return SoldeConge.objects.get(
            company=self.co, employe=self.emp, annee=2026).pris

    def test_fermeture_ne_recompte_pas_les_jours_deja_valides(self):
        # Congé personnel 10→20 août = 11 jours calendaires, déjà décomptés.
        self._conge_valide(date(2026, 8, 10), date(2026, 8, 20))
        self.assertEqual(self._solde(), Decimal('11'))

        fermeture = PeriodeFermeture.objects.create(
            company=self.co, libelle='Fermeture annuelle',
            date_debut=date(2026, 8, 15), date_fin=date(2026, 8, 25),
            type_absence=self.type_cp)
        creees = services.appliquer_fermeture(fermeture)

        # Une demande est bien créée pour la partie NON déjà couverte…
        self.assertEqual(len(creees), 1)
        # 15→25 = 11 jours, dont 15→20 (6 jours) déjà pris → 5 restants.
        self.assertEqual(creees[0].jours, Decimal('5'))
        # … et le solde n'a été décrémenté que de ces 5 jours.
        self.assertEqual(self._solde(), Decimal('16'))

    def test_employe_entierement_couvert_est_saute(self):
        self._conge_valide(date(2026, 8, 1), date(2026, 8, 31))
        pris_avant = self._solde()
        fermeture = PeriodeFermeture.objects.create(
            company=self.co, libelle='Pont', date_debut=date(2026, 8, 15),
            date_fin=date(2026, 8, 20), type_absence=self.type_cp)
        creees = services.appliquer_fermeture(fermeture)
        self.assertEqual(creees, [])
        self.assertEqual(self._solde(), pris_avant)
        # La fermeture est tout de même marquée appliquée (idempotence).
        fermeture.refresh_from_db()
        self.assertTrue(fermeture.appliquee)

    def test_sans_chevauchement_le_comportement_est_inchange(self):
        fermeture = PeriodeFermeture.objects.create(
            company=self.co, libelle='Fermeture', date_debut=date(2026, 8, 10),
            date_fin=date(2026, 8, 12), type_absence=self.type_cp)
        creees = services.appliquer_fermeture(fermeture)
        self.assertEqual(len(creees), 1)
        self.assertEqual(creees[0].jours, Decimal('3'))
        self.assertEqual(self._solde(), Decimal('3'))


class ChevauchementASoumissionTests(TestCase):
    """Le sens symétrique : une NOUVELLE demande sur des jours déjà validés."""

    def setUp(self):
        self.co = make_company('aud722-b', 'B')
        self.rh = make_user(self.co, 'aud722-b-rh')
        self.type_cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=False, deduit_solde=True)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='G1', nom='Chraibi', prenom='Sanae',
            statut=DossierEmploye.Statut.ACTIF)
        demande = DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.type_cp,
            date_debut=date(2026, 8, 10), date_fin=date(2026, 8, 20),
            jours=Decimal('11'))
        services.valider_demande(demande, decide_par=self.rh)

    def _demander(self, debut, fin):
        return auth(self.rh).post(DEMANDES, {
            'employe': self.emp.id, 'type_absence': self.type_cp.id,
            'date_debut': debut, 'date_fin': fin,
        })

    def test_chevauchement_partiel_ne_recompte_que_le_reste(self):
        resp = self._demander('2026-08-18', '2026-08-22')
        self.assertEqual(resp.status_code, 201, resp.data)
        # 18→22 = 5 jours, dont 18/19/20 déjà validés → 2 jours seulement.
        self.assertEqual(Decimal(resp.data['jours']), Decimal('2'))

    def test_periode_entierement_couverte_refusee(self):
        resp = self._demander('2026-08-12', '2026-08-15')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('deux fois', str(resp.data))
        self.assertEqual(
            DemandeConge.objects.filter(date_debut=date(2026, 8, 12)).count(),
            0)

    def test_periode_sans_chevauchement_inchangee(self):
        resp = self._demander('2026-09-01', '2026-09-03')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('3'))

    def test_une_demande_non_validee_ne_bloque_rien(self):
        """Seul un congé VALIDÉ a déjà touché le solde."""
        DemandeConge.objects.create(
            company=self.co, employe=self.emp, type_absence=self.type_cp,
            date_debut=date(2026, 10, 1), date_fin=date(2026, 10, 5),
            jours=Decimal('5'))
        resp = self._demander('2026-10-01', '2026-10-05')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('5'))
