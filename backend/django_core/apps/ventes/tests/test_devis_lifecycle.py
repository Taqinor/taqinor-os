"""Tests des fonctionnalités devis : expiration à la volée (T7a), révisions
(T10) et garde d'approbation de remise (T17).

Principes vérifiés :
- l'expiration est calculée à l'affichage, ne touche jamais au statut ;
- une révision clone les lignes, lie le source, version+1, référence neuve ;
- la garde de remise est DÉSACTIVÉE par défaut (rien ne change) et bloque
  l'envoi seulement quand le founder a fixé un seuil dépassé.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company(slug='dev-life-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Devis Life Co'})[0]


class TestExpiry(TestCase):
    """T7a — expiration calculée à la volée, jamais persistée."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Exp', telephone='+212600000020')

    def _devis(self, **kw):
        return Devis.objects.create(
            company=self.company, reference=kw.pop('ref', 'DEV-EXP-0001'),
            client=self.client_obj, statut=Devis.Statut.ENVOYE, **kw)

    def test_default_validity_30_days_not_expired(self):
        d = self._devis()
        # Créé aujourd'hui : expiration = +30 j, non expiré.
        self.assertEqual(
            d.date_expiration, (d.date_creation + timedelta(days=30)).date())
        self.assertFalse(d.est_expire)

    def test_explicit_date_validite_in_past_is_expired(self):
        d = self._devis(
            date_validite=timezone.now().date() - timedelta(days=1))
        self.assertTrue(d.est_expire)
        # Le statut ne bouge JAMAIS : toujours « envoyé ».
        d.refresh_from_db()
        self.assertEqual(d.statut, Devis.Statut.ENVOYE)

    def test_setting_shortens_validity(self):
        profile = CompanyProfile.get(company=self.company)
        profile.quote_validity_days = 5
        profile.save(update_fields=['quote_validity_days'])
        d = self._devis()
        Devis.objects.filter(pk=d.pk).update(
            date_creation=timezone.now() - timedelta(days=10))
        d.refresh_from_db()
        self.assertTrue(d.est_expire)


class TestRevision(TestCase):
    """T10 — révisions / versionnage additif."""

    def setUp(self):
        self.company = make_company('rev-co')
        self.user = User.objects.create_user(
            username='rev_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Rev', telephone='+212600000021')
        self.prod = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-R',
            prix_vente=Decimal('1000'), quantite_stock=10, tva=Decimal('10'))
        self.source = Devis.objects.create(
            company=self.company, reference='DEV-REV-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            remise_globale=Decimal('5'))
        LigneDevis.objects.create(
            devis=self.source, produit=self.prod, designation='Panneau',
            quantite=Decimal('3'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('10'))
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_reviser_clones_lines_and_links(self):
        resp = self.api.post(f'/api/django/ventes/devis/{self.source.id}/reviser/')
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body['version'], 2)
        self.assertEqual(body['revision_de'], self.source.id)
        new = Devis.objects.get(id=body['id'])
        # Lignes clonées 1:1.
        self.assertEqual(new.lignes.count(), 1)
        ligne = new.lignes.first()
        self.assertEqual(ligne.quantite, Decimal('3'))
        # Lead/client conservés, référence neuve, source intact.
        self.assertEqual(new.client_id, self.source.client_id)
        self.assertNotEqual(new.reference, self.source.reference)
        # Le source expose son remplaçant.
        s_data = self.api.get(
            f'/api/django/ventes/devis/{self.source.id}/').json()
        self.assertIsNotNone(s_data['remplace_par'])
        self.assertEqual(s_data['remplace_par']['id'], new.id)

    def test_reviser_other_company_forbidden(self):
        other = make_company('rev-other')
        other_client = Client.objects.create(
            company=other, nom='X', telephone='+212600000099')
        foreign = Devis.objects.create(
            company=other, reference='DEV-OTH-0001', client=other_client)
        resp = self.api.post(f'/api/django/ventes/devis/{foreign.id}/reviser/')
        # Hors société → 404 (queryset filtré).
        self.assertEqual(resp.status_code, 404)


class TestRemiseApprobation(TestCase):
    """T17 — garde d'approbation de remise (désactivée par défaut)."""

    def setUp(self):
        self.company = make_company('remise-co')
        self.user = User.objects.create_user(
            username='remise_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Rem', telephone='+212600000022')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _devis(self, remise):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-REM-{int(remise):04d}',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            remise_globale=Decimal(str(remise)))

    def test_disabled_by_default_allows_send(self):
        d = self._devis(50)
        resp = self.api.patch(
            f'/api/django/ventes/devis/{d.id}/', {'statut': 'envoye'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, Devis.Statut.ENVOYE)

    def test_blocks_when_over_threshold(self):
        profile = CompanyProfile.get(company=self.company)
        profile.seuil_remise_approbation = Decimal('10')
        profile.save(update_fields=['seuil_remise_approbation'])
        d = self._devis(20)
        resp = self.api.patch(
            f'/api/django/ventes/devis/{d.id}/', {'statut': 'envoye'},
            format='json')
        self.assertEqual(resp.status_code, 400)
        d.refresh_from_db()
        self.assertEqual(d.statut, Devis.Statut.BROUILLON)

    def test_under_threshold_allowed(self):
        profile = CompanyProfile.get(company=self.company)
        profile.seuil_remise_approbation = Decimal('10')
        profile.save(update_fields=['seuil_remise_approbation'])
        d = self._devis(5)
        resp = self.api.patch(
            f'/api/django/ventes/devis/{d.id}/', {'statut': 'envoye'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_approval_unblocks_send(self):
        profile = CompanyProfile.get(company=self.company)
        profile.seuil_remise_approbation = Decimal('10')
        profile.save(update_fields=['seuil_remise_approbation'])
        d = self._devis(20)
        approve = self.api.post(
            f'/api/django/ventes/devis/{d.id}/approuver-remise/')
        self.assertEqual(approve.status_code, 200, approve.content)
        d.refresh_from_db()
        self.assertIsNotNone(d.remise_approuvee_par_id)
        resp = self.api.patch(
            f'/api/django/ventes/devis/{d.id}/', {'statut': 'envoye'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, Devis.Statut.ENVOYE)
