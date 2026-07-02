"""QG9 — Pourcentage configurable des variantes de devis (défaut 20 %).

Couvre :
  * défaut : sans config, ``dupliquer-variante`` produit les échelles 0.8 / 1.0
    / 1.2 (± 20 %) ;
  * valeur changée : la config société pilote les échelles ;
  * override par requête (``variante_pct`` ou ``scales``) ;
  * endpoint ``variante-config`` : GET ouvert, PUT réservé Directeur /
    Commercial responsable (403 sinon) ;
  * scoping société de la config.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, role=None, legacy='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VariantePctScalingTests(TestCase):
    def setUp(self):
        self.company = _company('qg9-co')
        self.user = _user(self.company, 'qg9-user')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QG9')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-1',
            prix_vente=Decimal('1000'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QG9-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Panneau',
            quantite=Decimal('100'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'))
        self.api = _api(self.user)

    def _dupliquer(self, body=None):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/dupliquer-variante/',
            body or {}, format='json')

    def _variant_quantities(self):
        variants = Devis.objects.filter(
            company=self.company, version_parent=self.devis).order_by('version')
        out = []
        for v in variants:
            ln = v.lignes.first()
            out.append(float(ln.quantite) if ln else None)
        return out

    def test_default_pct_is_20(self):
        resp = self._dupliquer()
        self.assertEqual(resp.status_code, 201)
        # 100 × [0.8, 1.0, 1.2] = [80, 100, 120]
        self.assertEqual(sorted(self._variant_quantities()), [80.0, 100.0, 120.0])

    def test_configured_pct_drives_scales(self):
        profile = CompanyProfile.get(company=self.company)
        profile.variante_pct = Decimal('30')
        profile.save(update_fields=['variante_pct'])
        self._dupliquer()
        # 100 × [0.7, 1.0, 1.3] = [70, 100, 130]
        self.assertEqual(sorted(self._variant_quantities()), [70.0, 100.0, 130.0])

    def test_request_override_variante_pct(self):
        self._dupliquer(body={'variante_pct': 10})
        # 100 × [0.9, 1.0, 1.1] = [90, 100, 110]
        self.assertEqual(sorted(self._variant_quantities()), [90.0, 100.0, 110.0])

    def test_request_override_explicit_scales(self):
        self._dupliquer(body={'scales': [0.5, 1.0, 1.5]})
        self.assertEqual(sorted(self._variant_quantities()), [50.0, 100.0, 150.0])


class VarianteConfigEndpointTests(TestCase):
    def setUp(self):
        self.company = _company('qg9-cfg')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur', permissions=['ventes_voir'])
        self.comm_role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=['ventes_voir'])
        self.viewer_role = Role.objects.create(
            company=self.company, nom='Viewer', permissions=['ventes_voir'])
        self.directeur = _user(self.company, 'qg9-dir', role=self.dir_role)
        self.commercial = _user(self.company, 'qg9-comm', role=self.comm_role)
        self.viewer = _user(self.company, 'qg9-viewer', role=self.viewer_role,
                            legacy='normal')

    def _get(self, user):
        return _api(user).get('/api/django/ventes/devis/variante-config/')

    def _put(self, user, pct):
        return _api(user).put(
            '/api/django/ventes/devis/variante-config/',
            {'variante_pct': pct}, format='json')

    def test_get_default_open_to_all(self):
        resp = self._get(self.viewer)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(resp.data['variante_pct']), Decimal('20'))

    def test_directeur_can_change(self):
        resp = self._put(self.directeur, 25)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            CompanyProfile.get(company=self.company).variante_pct,
            Decimal('25'))

    def test_commercial_responsable_can_change(self):
        resp = self._put(self.commercial, 15)
        self.assertEqual(resp.status_code, 200)

    def test_viewer_forbidden(self):
        resp = self._put(self.viewer, 30)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            CompanyProfile.get(company=self.company).variante_pct,
            Decimal('20'))  # inchangé

    def test_invalid_pct_rejected(self):
        resp = self._put(self.directeur, 150)
        self.assertEqual(resp.status_code, 400)

    def test_company_scoped(self):
        other = _company('qg9-autre')
        other_role = Role.objects.create(
            company=other, nom='Directeur', permissions=['ventes_voir'])
        other_dir = _user(other, 'qg9-other-dir', role=other_role)
        self._put(self.directeur, 33)
        # La config de l'autre société reste au défaut.
        self.assertEqual(
            Decimal(self._get(other_dir).data['variante_pct']), Decimal('20'))
