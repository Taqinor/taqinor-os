"""QJR518 (Groupe QJR5, D-QJR5-1) — une correction après envoi est tracée à
UN seul point d'appel (``domain/modifiabilite``) : instantané de l'état vu
par le client, chatter « corrigé après envoi » (devis ET lead), marqueur
``resync_apres_envoi`` (« Document mis à jour le … ») ; statut, référence et
jeton intouchés.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_correction_apres_envoi"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity
from apps.stock.models import Produit
from apps.ventes.models import (
    ConfigurationDevisSnapshot, Devis, DevisActivity, LigneDevis, ShareLink)
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class CorrectionApresEnvoi(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR518 Co', slug='qjr518-co')
        self.user = User.objects.create_user(
            username='qjr518_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR518',
            email='qjr518@example.test', telephone='+212600005180')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR518',
            telephone='+212600005181', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR518-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut=Devis.Statut.ENVOYE):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-518{self.n}',
            client=self.client_obj, lead=self.lead, statut=statut,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0)
        return devis

    @staticmethod
    def _corrections(devis):
        return DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi')

    def _replace(self, devis, prix):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': [{'produit': self.produit.id, 'quantite': '10',
                         'prix_unitaire': prix, 'ordre': 0,
                         'designation': self.produit.nom}]},
            format='json')

    def test_prix_change_trace_une_correction(self):
        devis = self._devis()
        reference = devis.reference
        lien = ShareLink.for_devis(devis)
        r = self._replace(devis, '900')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.reference, reference)
        self.assertEqual(self._corrections(devis).count(), 1)
        self.assertIn('lignes', self._corrections(devis).get().body)
        # L'instantané = les lignes D'AVANT (l'état vu par le client).
        snap = ConfigurationDevisSnapshot.objects.filter(
            devis=devis).order_by('-date_creation', '-id').first()
        self.assertIsNotNone(snap)
        prix_snap = [li['prix_unitaire'] for li in snap.contenu['lignes']]
        self.assertEqual([Decimal(p) for p in prix_snap], [Decimal('1000')])
        # « Document mis à jour le … » exposé sur la proposition publique.
        marqueur = (devis.etude_params or {}).get('resync_apres_envoi')
        self.assertIsNotNone(marqueur)
        self.assertIn('date', marqueur)
        pub = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(pub.status_code, 200, pub.content)
        self.assertIsNotNone(pub.data.get('resync_apres_envoi'))
        # Reflet sur le lead.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='corrigé après envoi').exists())

    def test_lignes_identiques_aucune_trace(self):
        devis = self._devis()
        r = self._replace(devis, '1000')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._corrections(devis).count(), 0)
        devis.refresh_from_db()
        self.assertIsNone(
            (devis.etude_params or {}).get('resync_apres_envoi'))

    def test_patch_remise_trace(self):
        devis = self._devis()
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'remise_globale': '3'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._corrections(devis).count(), 1)
        self.assertIn('en-tête', self._corrections(devis).get().body)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_patch_note_trace(self):
        """D-QJR5-6 — la note est un texte CLIENT."""
        devis = self._devis()
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'note': 'Pose en mars.'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('note', self._corrections(devis).get().body)

    def test_patch_devis_lignes_trace_et_marqueur(self):
        devis = self._devis()
        ligne = devis.lignes.get()
        r = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                           {'quantite': '12'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._corrections(devis).count(), 1)
        devis.refresh_from_db()
        self.assertIsNotNone(
            (devis.etude_params or {}).get('resync_apres_envoi'))

    def test_option_recommandee_tracee(self):
        devis = self._devis()
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/etude-params/',
                           {'recommended_option': 'avec_batterie'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('option recommandée',
                      self._corrections(devis).get().body)

    def test_brouillon_rien(self):
        devis = self._devis(Devis.Statut.BROUILLON)
        self.assertEqual(self._replace(devis, '900').status_code, 200)
        self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                       {'remise_globale': '3'}, format='json')
        self.assertEqual(self._corrections(devis).count(), 0)
        devis.refresh_from_db()
        self.assertIsNone(
            (devis.etude_params or {}).get('resync_apres_envoi'))
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='corrigé après envoi').exists())
