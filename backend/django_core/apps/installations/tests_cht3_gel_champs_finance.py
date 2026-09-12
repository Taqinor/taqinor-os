"""CHT3 — Gel post-clôture des champs à conséquence financière/stock.

Durcissement SCOPÉ (pas un bug) : la BoM est déjà « gelée » contre l'édition
du DEVIS (services.py) ; ici on la gèle aussi contre l'édition du CHANTIER
une fois `cloture_verrouillee` (patron `InstallationSerializer.validate`,
crm/serializers.py:794-803). `dossier_statut`/`regime_8221`/`parc_actif`/
`mes_*`/notes restent éditables — le dossier 82-21 continue de vivre après
la clôture travaux.

Run :
    python manage.py test apps.installations.tests_cht3_gel_champs_finance -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'cht3-co-{n}', defaults={'nom': f'CHT3 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_responsable(company):
    return User.objects.create_user(
        username=f'cht3-resp-{next(_seq)}', password='x', company=company,
        role_legacy='responsable')


class GelChampsFinanceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.responsable = make_responsable(self.company)

    def test_patch_bom_sur_cloture_refuse(self):
        inst = Installation.objects.create(
            company=self.company, reference='CHT3-1',
            statut=Installation.Statut.CLOTURE, cloture_verrouillee=True)
        r = auth(self.responsable).patch(
            f'{BASE}/{inst.id}/',
            {'bom': [{'produit_id': 1, 'designation': 'Panneau X',
                      'quantite': 2}]},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        inst.refresh_from_db()
        self.assertEqual(inst.bom, [])

    def test_patch_dossier_statut_sur_cloture_passe(self):
        """82-21 vit après la clôture travaux — jamais gelé par CHT3."""
        inst = Installation.objects.create(
            company=self.company, reference='CHT3-2',
            statut=Installation.Statut.CLOTURE, cloture_verrouillee=True)
        r = auth(self.responsable).patch(
            f'{BASE}/{inst.id}/',
            {'dossier_statut': Installation.DossierStatut.A_DEPOSER},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(
            inst.dossier_statut, Installation.DossierStatut.A_DEPOSER)

    def test_patch_bom_sur_non_clos_passe(self):
        inst = Installation.objects.create(
            company=self.company, reference='CHT3-3',
            statut=Installation.Statut.EN_COURS)
        r = auth(self.responsable).patch(
            f'{BASE}/{inst.id}/',
            {'bom': [{'produit_id': 1, 'designation': 'Panneau X',
                      'quantite': 2}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(len(inst.bom), 1)
