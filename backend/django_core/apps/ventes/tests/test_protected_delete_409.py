"""Bug fix (2026-07-31) — DELETE d'un devis/facture PROTÉGÉ renvoyait 500.

Plusieurs FK ont été passées en ``on_delete=models.PROTECT`` pour empêcher la
suppression d'un devis/facture tant qu'une preuve financière ou légale
pointe encore dessus (``RegulatoryDossier.devis``, ``SubventionDossier.devis``,
``Avoir.facture``…). Django lève alors ``ProtectedError`` — REFUS CORRECT —
mais ``DevisViewSet``/``FactureViewSet`` n'ont aucun override de ``destroy()``
et ``core.exceptions.taqinor_exception_handler`` ne connaissait pas
``ProtectedError`` : elle tombait dans le seau générique et ressortait en 500
« l'appli a planté » au lieu d'un 409 « on a protégé vos données ».

Le correctif est CENTRALISÉ dans ``core.exceptions.taqinor_exception_handler``
(voir ``tests/test_error_envelope.py::ProtectedErrorTests`` pour l'unitaire
sur le handler lui-même) : ce module prouve le chemin bout-en-bout — vraie
suppression HTTP bloquée, 409 (jamais 500), message FR explicite, LES DEUX
lignes survivent — et que la protection reste SCOPÉE (un devis/une facture
sans référence protégée se supprime toujours normalement).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Devis, Facture, LigneFacture, RegulatoryDossier

User = get_user_model()


def make_company(slug='prot-co', nom='Protected Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ProtectedDevisDeleteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='prot_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='prot-client@example.com',
        )

    def _make_devis(self, reference='DEV-PROT-0001'):
        return Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
        )

    def test_delete_protected_devis_returns_409_not_500(self):
        """Un devis référencé par un dossier réglementaire (preuve ONEE/ANRE,
        on_delete=PROTECT) refuse la suppression — proprement, pas en 500."""
        devis = self._make_devis()
        dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=devis,
        )
        api = auth(self.admin)
        resp = api.delete(f'/api/django/ventes/devis/{devis.id}/')

        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('detail', resp.data)
        # Message FR clair : explique le POURQUOI, pas un stacktrace.
        self.assertIn('Suppression refusée', resp.data['detail'])
        self.assertIn('référencé', resp.data['detail'])
        # L'enveloppe machine YAPIC3 est présente EN PLUS (code stable).
        self.assertEqual(resp.data['error']['code'], 'protected_error')

        # Les DEUX lignes survivent — aucune suppression partielle.
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())
        self.assertTrue(RegulatoryDossier.objects.filter(pk=dossier.pk).exists())

    def test_delete_unreferenced_devis_still_succeeds(self):
        """La protection est SCOPÉE : un devis SANS dossier lié se supprime
        toujours normalement (pas un blocage général de la suppression)."""
        devis = self._make_devis(reference='DEV-PROT-0002')
        api = auth(self.admin)
        resp = api.delete(f'/api/django/ventes/devis/{devis.id}/')

        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(Devis.objects.filter(pk=devis.pk).exists())


class ProtectedFactureDeleteTests(TestCase):
    """``Avoir.facture`` est ``on_delete=PROTECT`` de longue date : une facture
    avec un avoir émis crashait en 500 avant le correctif du handler.

    AUD103 (2026-09) a depuis donné à ``FactureViewSet`` un ``perform_destroy``
    qui INTERCEPTE ce cas AVANT le handler central : la suppression n'est
    ouverte qu'au SUPERUTILISATEUR (``IsSuperuserOnly``, parce que supprimer
    une facture est le seul geste qui emportait les encaissements en cascade),
    seul un BROUILLON sans paiement est supprimable, et le ``ProtectedError``
    est traduit sur place en 400 français. Le contrat de ce module reste donc
    vrai — refus PROPRE, jamais une 500, les DEUX lignes survivent, protection
    SCOPÉE — mais avec le code que la vue pose elle-même (400) au lieu du 409
    du handler central. Le 409 générique reste prouvé bout-en-bout par
    ``ProtectedDevisDeleteTests`` ci-dessus (``DevisViewSet`` n'intercepte pas)
    et unitairement par ``tests/test_error_envelope.py::ProtectedErrorTests``.
    """

    def setUp(self):
        self.company = make_company(slug='prot-fac-co', nom='Protected Fac Co')
        # Palier « admin » élargi : porte roles_gerer, N'EST PAS superuser.
        self.admin = User.objects.create_user(
            username='prot_fac_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.superuser = User.objects.create_superuser(
            username='prot_fac_su', password='x', email='')
        self.superuser.company = self.company
        self.superuser.role_legacy = 'admin'
        self.superuser.save(update_fields=['company', 'role_legacy'])
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Fac',
            email='prot-fac-client@example.com',
        )
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PV-PROT-1',
            prix_vente=Decimal('1000'), quantite_stock=10, tva=Decimal('20.00'),
        )

    def _make_facture(self, reference='FAC-PROT-0001', avec_ligne=True):
        # AUD103 : seul un BROUILLON est supprimable (une facture émise porte
        # un numéro légal et s'ANNULE) — le scénario « PROTECT » se joue donc
        # désormais sur un brouillon référencé par un avoir.
        facture = Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'),
        )
        if avec_ligne:
            LigneFacture.objects.create(
                facture=facture, produit=self.produit, designation='Panneau PV',
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            )
        return facture

    def test_delete_facture_with_avoir_is_refused_cleanly_not_500(self):
        facture = self._make_facture()
        avoir = Avoir.objects.create(
            company=self.company, reference='AV-PROT-0001', facture=facture,
            client=self.client_obj, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
        )
        api = auth(self.superuser)
        resp = api.delete(f'/api/django/ventes/factures/{facture.id}/')

        # Refus PROPRE et français, jamais la 500 « l'appli a planté ».
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('detail', resp.data)
        self.assertIn('avoir', str(resp.data['detail']).lower())

        # Les DEUX lignes survivent — aucune suppression partielle.
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())
        self.assertTrue(Avoir.objects.filter(pk=avoir.pk).exists())

    def test_delete_facture_refused_for_admin_who_is_not_superuser(self):
        """AUD103 — le palier « admin » élargi ne supprime plus une facture."""
        facture = self._make_facture(reference='FAC-PROT-0003')
        api = auth(self.admin)
        resp = api.delete(f'/api/django/ventes/factures/{facture.id}/')

        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    def test_delete_unreferenced_facture_still_succeeds(self):
        """La protection reste SCOPÉE : un brouillon nu, sans avoir ni
        paiement, se supprime toujours (pas un blocage général)."""
        facture = self._make_facture(
            reference='FAC-PROT-0002', avec_ligne=False)
        api = auth(self.superuser)
        resp = api.delete(f'/api/django/ventes/factures/{facture.id}/')

        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', resp))
        self.assertFalse(Facture.objects.filter(pk=facture.pk).exists())
