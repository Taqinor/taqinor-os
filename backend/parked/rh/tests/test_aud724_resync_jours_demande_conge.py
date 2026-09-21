"""AUD724 — `DemandeConge` : `jours` suit enfin les dates modifiées.

DÉFAUT (rouge avant ce correctif) : `DemandeCongeSerializer` exposait
`date_debut`/`date_fin` en écriture normale ; `read_only_fields` protégeait
`jours` — et `DemandeCongeViewSet` n'avait AUCUN `perform_update`. Seul
`perform_create` recalculait `jours` via `calculer_jours_demande`, et
`valider_demande` utilise `demande.jours` tel quel sans jamais le recalculer.
Étendre une demande SOUMISE de 5 à 10 jours laissait donc `jours` figé à 5 : le
solde décompté ne correspondait plus à la période réellement approuvée.

Après correctif : `jours` est recalculé à chaque modification tant que la
demande est SOUMISE (avec le même anti double-décompte qu'à la création), et
une demande DÉCIDÉE (validée / refusée / annulée) n'est plus modifiable du
tout — son solde est déjà passé.
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


class ResyncJoursDemandeTests(TestCase):
    def setUp(self):
        self.co = make_company('aud724', 'A')
        self.rh = make_user(self.co, 'aud724-rh')
        self.type_cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=False, deduit_solde=True)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='H1', nom='Tazi', prenom='Reda')
        SoldeConge.objects.create(
            company=self.co, employe=self.emp, annee=2026,
            acquis=Decimal('30.00'))
        resp = auth(self.rh).post(DEMANDES, {
            'employe': self.emp.id, 'type_absence': self.type_cp.id,
            'date_debut': '2026-08-10', 'date_fin': '2026-08-14',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.demande = DemandeConge.objects.get(pk=resp.data['id'])
        self.assertEqual(self.demande.jours, Decimal('5'))

    def test_etendre_les_dates_recalcule_les_jours(self):
        resp = auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'date_fin': '2026-08-19'})
        self.assertEqual(resp.status_code, 200, resp.data)
        # 10 → 19 août = 10 jours calendaires.
        self.assertEqual(Decimal(resp.data['jours']), Decimal('10'))
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.jours, Decimal('10'))

    def test_reduire_les_dates_recalcule_les_jours(self):
        resp = auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'date_fin': '2026-08-11'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('2'))

    def test_le_solde_decompte_correspond_a_la_periode_approuvee(self):
        """Le vrai symptôme : `valider_demande` décomptait l'ancien nombre."""
        auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'date_fin': '2026-08-19'})
        self.demande.refresh_from_db()
        services.valider_demande(self.demande, decide_par=self.rh)
        solde = SoldeConge.objects.get(
            company=self.co, employe=self.emp, annee=2026)
        self.assertEqual(solde.pris, Decimal('10'))

    def test_demande_validee_n_est_plus_modifiable(self):
        services.valider_demande(self.demande, decide_par=self.rh)
        resp = auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'date_fin': '2026-08-19'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.date_fin, date(2026, 8, 14))
        self.assertEqual(self.demande.jours, Decimal('5'))

    def test_demande_refusee_n_est_plus_modifiable(self):
        services.refuser_demande(
            self.demande, decide_par=self.rh, motif_refus='Effectif')
        resp = auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'date_fin': '2026-08-19'})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_modifier_un_champ_libre_ne_casse_pas_le_decompte(self):
        resp = auth(self.rh).patch(
            f'{DEMANDES}{self.demande.pk}/', {'motif': 'Congé annuel'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('5'))
