"""AUD304 — la suppression d'un chantier est gardée par son statut.

Défaut d'origine : `InstallationViewSet` routait `destroy` vers `IsAdminRole()`
et n'avait AUCUN `perform_destroy`/`destroy` surchargé — le `perform_destroy`
nu de DRF, donc `instance.delete()`. Or 12 FK enfants sont en
`on_delete=CASCADE`, dont `CommissioningRecord` (recette IEC 62446-1),
`HandoverPack` (dossier de remise), `JalonProjet`, `DocumentProjet` et
`Intervention` : un DELETE sur un chantier RÉCEPTIONNÉ renvoyait 204 et
emportait toute la trace de conformité, sans restauration possible.

Après correctif : au-delà du seuil « Planifié » de l'entonnoir canonique, le
DELETE est refusé en 409 avec une raison FR ; en deçà il reste autorisé.

Run :
    python manage.py test apps.installations.tests_aud304_suppression_chantier -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import CommissioningRecord, Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud304-co-{n}', defaults={'nom': f'AUD304 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_admin(company):
    """Compte admin legacy (`role_legacy='admin'` → `is_admin_role` True)."""
    return User.objects.create_user(
        username=f'aud304-admin-{next(_seq)}', password='x', company=company,
        role_legacy='admin')


class SuppressionChantierGardeeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_admin(self.company)
        self.api = auth(self.admin)

    def _chantier(self, statut):
        return Installation.objects.create(
            company=self.company, reference=f'AUD304-{next(_seq)}',
            statut=statut)

    def test_delete_chantier_receptionne_refuse_et_conserve_la_recette(self):
        """ROUGE avant AUD304 : 204 + CommissioningRecord cascadé."""
        inst = self._chantier(Installation.Statut.RECEPTIONNE)
        record = CommissioningRecord.objects.create(
            company=self.company, installation=inst)
        r = self.api.delete(f'{BASE}/{inst.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('detail', r.data)
        self.assertIn('Réceptionné', r.data['detail'])
        self.assertTrue(Installation.objects.filter(pk=inst.pk).exists())
        self.assertTrue(CommissioningRecord.objects.filter(
            pk=record.pk).exists())

    def test_delete_refuse_au_dela_du_seuil_pour_chaque_statut(self):
        for statut in (Installation.Statut.EN_COURS,
                       Installation.Statut.INSTALLE,
                       Installation.Statut.RECEPTIONNE,
                       Installation.Statut.CLOTURE):
            with self.subTest(statut=statut):
                inst = self._chantier(statut)
                r = self.api.delete(f'{BASE}/{inst.id}/')
                self.assertEqual(r.status_code, 409, r.data)
                self.assertTrue(
                    Installation.objects.filter(pk=inst.pk).exists())

    def test_delete_refuse_sur_un_statut_herite_au_dela_du_seuil(self):
        # « Mise en service » se rabat sur « Réceptionné » (LEGACY_STATUT_MAP).
        inst = self._chantier(Installation.Statut.MISE_EN_SERVICE)
        r = self.api.delete(f'{BASE}/{inst.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(Installation.objects.filter(pk=inst.pk).exists())

    def test_delete_autorise_en_deca_du_seuil(self):
        for statut in (Installation.Statut.SIGNE,
                       Installation.Statut.MATERIEL_COMMANDE,
                       Installation.Statut.PLANIFIE,
                       Installation.Statut.A_PLANIFIER):
            with self.subTest(statut=statut):
                inst = self._chantier(statut)
                r = self.api.delete(f'{BASE}/{inst.id}/')
                self.assertEqual(r.status_code, 204, getattr(r, 'data', None))
                self.assertFalse(
                    Installation.objects.filter(pk=inst.pk).exists())
