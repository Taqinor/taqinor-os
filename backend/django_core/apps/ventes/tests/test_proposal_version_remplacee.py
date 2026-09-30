"""QJR536 (Groupe QJR5, contrat QJR501) — le lien public d'une version
REMPLACÉE le dit : ``remplace_par = {reference, url}`` ; ``url`` n'est servie
que si la version en vigueur a été ENVOYÉE et porte un lien valide ; une
version d'une AUTRE société n'est jamais suivie ; le statut n'est jamais
modifié et le jeton de v1 ne sert jamais le contenu de v2.

PACT10 — les formes attendues viennent de l'échantillon COMMITTÉ
``contract_samples/proposal_data.json`` (fragments
``exemple_remplace_par_envoye`` / ``exemple_remplace_par_brouillon``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_proposal_version_remplacee"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = json.loads((Path(__file__).resolve().parent.parent
                      / 'contract_samples' / 'proposal_data.json')
                     .read_text(encoding='utf-8'))


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ProposalVersionRemplacee(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR536 Co', slug='qjr536-co')
        self.user = User.objects.create_user(
            username='qjr536_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR536',
            email='qjr536@example.test', telephone='+212600005360')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR536-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut=Devis.Statut.ENVOYE, company=None, client=None,
               note=''):
        self.n += 1
        devis = Devis.objects.create(
            company=company or self.company,
            reference=f'DEV-{MONTH}-536{self.n}',
            client=client or self.client_obj, statut=statut,
            taux_tva=Decimal('20'), created_by=self.user, note=note)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis

    @staticmethod
    def _remplacer(v1, v2):
        Devis.objects.filter(pk=v1.pk).update(
            is_active=False, superseded_by=v2)
        v1.refresh_from_db()

    def _payload(self, devis):
        lien = ShareLink.for_devis(devis)
        r = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data

    def test_devis_non_remplace_null(self):
        v1 = self._devis(note='Pose prévue en mars.')
        data = self._payload(v1)
        self.assertIsNone(data['remplace_par'])
        self.assertEqual(data['note_client'], 'Pose prévue en mars.')

    def test_v2_brouillon_url_null(self):
        attendu = CONTRAT['exemple_remplace_par_brouillon']['remplace_par']
        v1 = self._devis()
        v2 = self._devis(Devis.Statut.BROUILLON)
        self._remplacer(v1, v2)
        data = self._payload(v1)
        self.assertEqual(set(data['remplace_par']), set(attendu))
        self.assertEqual(data['remplace_par'],
                         {'reference': v2.reference, 'url': None})
        # Le jeton de v1 sert v1 (lien, pas redirection) ; statut intact.
        self.assertEqual(data['reference'], v1.reference)
        v1.refresh_from_db()
        self.assertEqual(v1.statut, Devis.Statut.ENVOYE)

    def test_v2_envoyee_avec_lien_url(self):
        attendu = CONTRAT['exemple_remplace_par_envoye']['remplace_par']
        v1 = self._devis()
        v2 = self._devis(Devis.Statut.ENVOYE)
        lien_v2 = ShareLink.for_devis(v2)
        self._remplacer(v1, v2)
        data = self._payload(v1)
        self.assertEqual(set(data['remplace_par']), set(attendu))
        self.assertEqual(data['remplace_par']['reference'], v2.reference)
        self.assertTrue(data['remplace_par']['url'].startswith('/proposition/'))
        self.assertTrue(data['remplace_par']['url'].endswith(lien_v2.token))
        self.assertEqual(data['reference'], v1.reference)

    def test_v2_envoyee_sans_lien_url_null(self):
        """Aucun lien n'est CRÉÉ par la lecture publique."""
        v1 = self._devis()
        v2 = self._devis(Devis.Statut.ENVOYE)
        self._remplacer(v1, v2)
        data = self._payload(v1)
        self.assertEqual(data['remplace_par'],
                         {'reference': v2.reference, 'url': None})
        self.assertFalse(ShareLink.objects.filter(devis=v2).exists())

    def test_chaine_suivie_jusqu_a_la_derniere_version(self):
        v1 = self._devis()
        v2 = self._devis()
        v3 = self._devis(Devis.Statut.BROUILLON)
        self._remplacer(v1, v2)
        self._remplacer(v2, v3)
        data = self._payload(v1)
        self.assertEqual(data['remplace_par']['reference'], v3.reference)

    def test_v2_d_une_autre_societe_jamais_suivie(self):
        autre = Company.objects.create(nom='Autre', slug='qjr536-autre')
        client_autre = Client.objects.create(
            company=autre, nom='X', prenom='Y', telephone='+212600005369')
        v1 = self._devis()
        etranger = self._devis(Devis.Statut.ENVOYE, company=autre,
                               client=client_autre)
        ShareLink.for_devis(etranger)
        self._remplacer(v1, etranger)
        data = self._payload(v1)
        self.assertIsNone(data['remplace_par'])
