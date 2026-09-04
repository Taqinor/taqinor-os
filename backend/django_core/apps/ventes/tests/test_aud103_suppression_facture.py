"""AUD103 (FICHE-DEL) — supprimer une facture n'emporte plus les encaissements.

``FactureViewSet`` ne surchargeait NI ``destroy`` NI ``perform_destroy`` :
DRF appelait ``instance.delete()`` nu. Conséquences prouvées par lecture des
``on_delete`` un par un :

  * aucune garde de statut — une facture ÉMISE, EN_RETARD ou PAYÉE se
    supprimait aussi bien qu'un brouillon, alors qu'``annuler`` refuse
    explicitement une facture payée ;
  * aucun verrou de période — la garde YLEDG3 était câblée en sept points,
    jamais sur ``destroy`` ;
  * la cascade emportait ``Paiement`` (des MAD réellement encaissés), pendant
    que l'écriture au grand livre — non liée par FK — survivait en orphelin ;
  * « admin seulement » était FAUX : ``IsAdminRole`` passe pour tout rôle
    portant ``roles_gerer``, donc un « Directeur » supprimait une facture
    payée et ses encaissements.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta.models import PeriodeComptable
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Avoir, Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSuppressionFacture(TestCase):
    def setUp(self):
        from apps.roles.models import ALL_PERMISSIONS, Role

        self.company, _ = Company.objects.get_or_create(
            slug='aud103-co', defaults={'nom': 'AUD103 Co'})
        # Un rôle « Directeur » PORTEUR de roles_gerer mais SANS superuser :
        # c'est exactement le profil que l'ancien IsAdminRole laissait entrer.
        self.role_directeur = Role.objects.create(
            company=self.company, nom=f'Directeur {_nxt()}',
            permissions=ALL_PERMISSIONS)
        self.directeur = User.objects.create_user(
            username=f'aud103_dir_{_nxt()}', password='x',
            role=self.role_directeur, role_legacy='admin',
            company=self.company)
        self.superuser = User.objects.create_superuser(
            username=f'aud103_su_{_nxt()}', password='x', email='')
        self.superuser.company = self.company
        self.superuser.role_legacy = 'admin'
        self.superuser.save(update_fields=['company', 'role_legacy'])
        self.api_dir = _auth(self.directeur)
        self.api_su = _auth(self.superuser)
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD103', prenom='Client',
            email='aud103@example.com', telephone='+212600000103')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AUD103-{_nxt()}',
            prix_vente=Decimal('5000'), quantite_stock=10)

    def _facture(self, statut=Facture.Statut.BROUILLON, avec_ligne=True):
        n = _nxt()
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD103-{n:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))
        if avec_ligne:
            LigneFacture.objects.create(
                facture=facture, produit=self.produit,
                designation='Onduleur', quantite=Decimal('1'),
                prix_unitaire=Decimal('5000'), taux_tva=Decimal('20'))
        return facture

    def _url(self, facture):
        return f'/api/django/ventes/factures/{facture.id}/'

    # ── Le scénario destructeur exact : ÉMISE + paiement ──────────────────

    def test_facture_emise_avec_paiement_refusee_et_paiement_intact(self):
        facture = self._facture(statut=Facture.Statut.EMISE)
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('1000'),
            date_paiement=date(2026, 3, 1), mode='virement')
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())
        self.assertTrue(Paiement.objects.filter(pk=paiement.pk).exists())

    def test_facture_payee_refusee(self):
        facture = self._facture(statut=Facture.Statut.PAYEE)
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    def test_brouillon_avec_paiement_refuse(self):
        """Un brouillon qui porte de l'argent n'est pas supprimable non plus."""
        facture = self._facture()
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('10'),
            date_paiement=date(2026, 3, 1), mode='especes')
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    # ── Verrou de période ─────────────────────────────────────────────────

    def test_facture_dans_periode_cloturee_refusee(self):
        facture = self._facture()
        Facture.objects.filter(pk=facture.pk).update(
            date_emission=date(2026, 2, 10))
        PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    # ── Permission : « admin » élargi ≠ superutilisateur ──────────────────

    def test_role_roles_gerer_non_superuser_refuse(self):
        self.assertTrue(self.directeur.is_admin_role)
        self.assertFalse(self.directeur.is_superuser)
        facture = self._facture()
        resp = self.api_dir.delete(self._url(facture))
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    # ── ProtectedError traduit, plus une 500 ──────────────────────────────

    def test_facture_avec_avoir_repond_400_francais(self):
        facture = self._facture()
        Avoir.objects.create(
            company=self.company, reference=f'AV-AUD103-{_nxt()}',
            facture=facture, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertIn('avoir', str(resp.data).lower())
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())

    # ── Le cas légitime reste possible ────────────────────────────────────

    def test_brouillon_nu_reste_supprimable_par_le_superutilisateur(self):
        facture = self._facture(avec_ligne=False)
        resp = self.api_su.delete(self._url(facture))
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', resp))
        self.assertFalse(Facture.objects.filter(pk=facture.pk).exists())


class TestPaiementProtege(TestCase):
    """Le filet CÔTÉ MODÈLE : PROTECT, pas CASCADE (admin Django, shell…)."""

    def test_suppression_directe_dune_facture_payee_leve_protected_error(self):
        from django.db.models import ProtectedError

        company, _ = Company.objects.get_or_create(
            slug='aud103-model', defaults={'nom': 'AUD103 Modèle'})
        client = Client.objects.create(
            company=company, nom='Modèle', prenom='AUD103',
            telephone='+212600000104')
        facture = Facture.objects.create(
            company=company, reference=f'FAC-AUD103-M{_nxt()}',
            client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        paiement = Paiement.objects.create(
            company=company, facture=facture, montant=Decimal('1200'),
            date_paiement=date(2026, 3, 1), mode='virement')
        with self.assertRaises(ProtectedError):
            facture.delete()
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())
        self.assertTrue(Paiement.objects.filter(pk=paiement.pk).exists())
