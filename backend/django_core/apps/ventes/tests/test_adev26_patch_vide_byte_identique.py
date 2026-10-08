"""ADEV26 (C-ADEV-035) — un PATCH de devis qui ne change AUCUNE entrée
d'étude ne ré-écrit plus les quatre études (``force_etudes=True`` retiré de
ce cas) : test métamorphique « PATCH vide ⇒ objet identique ». Quand une
étude d'un ENVOYÉ est réellement ré-écrite, la trace « Corrigé après envoi —
étude » et le marqueur ``resync_apres_envoi`` sont posés.

Sonde VB p7 : devis résidentiel ENVOYÉ, ``PATCH {}`` → ``ville_calcul``
réécrit (le lead a une ville que l'étude n'a pas encore consignée), aucune
activité. La fixture reproduit exactement cet écart : ``ville_calcul`` en
base ≠ ville du lead — toute relance des études le ré-écrit.

Test-du-test : remettre ``force_etudes=True`` inconditionnel dans
``perform_update`` ⇒ ``test_patch_vide_envoye_identique`` échoue.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_adev26_patch_vide_byte_identique"
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis
from authentication.models import Company

User = get_user_model()
MOIS = timezone.now().strftime('%Y%m')

#: Une ``ville_calcul`` PÉRIMÉE (le lead est à Casablanca) : toute relance
#: des études la ré-écrit (``pipeline.consigner_ville_calcul``).
ETUDE_INITIALE = {
    'scenario': 'Sans batterie',
    'ville_calcul': {'ville': 'Rabat', 'reference': 'Rabat'},
}


class PatchVideTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ADEV26 Co', slug='adev26-co')
        self.user = User.objects.create_user(
            username='adev26_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV26',
            email='adev26@example.test', telephone='+212600002600')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ADEV26',
            telephone='+212600002601', client=self.client_obj,
            ville='Casablanca')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ADEV26-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-A26{self.n}',
            client=self.client_obj, lead=self.lead, statut=statut,
            mode_installation='residentiel',
            taux_tva=Decimal('20'), created_by=self.user,
            etude_params=json.loads(json.dumps(ETUDE_INITIALE)))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0)
        return devis

    def _patch(self, devis, corps):
        return self.api.patch(
            f'/api/django/ventes/devis/{devis.pk}/', corps, format='json')

    @staticmethod
    def _octets(devis):
        """``etude_params`` relu en base, sérialisé de façon canonique."""
        valeur = Devis.objects.values_list(
            'etude_params', flat=True).get(pk=devis.pk)
        return json.dumps(valeur, sort_keys=True)

    def test_patch_vide_envoye_identique(self):
        devis = self._devis(Devis.Statut.ENVOYE)
        avant = self._octets(devis)
        activites = DevisActivity.objects.filter(devis=devis).count()

        reponse = self._patch(devis, {})
        self.assertEqual(reponse.status_code, 200, reponse.content)

        # CLAUSE PERSISTANCE : GET puis comparaison octet à octet.
        self.assertEqual(
            self.api.get(f'/api/django/ventes/devis/{devis.pk}/').status_code,
            200)
        self.assertEqual(self._octets(devis), avant)
        self.assertEqual(
            DevisActivity.objects.filter(devis=devis).count(), activites)
        # CLAUSE CLIENT : pas de « Document mis à jour le » sans changement.
        devis.refresh_from_db()
        self.assertNotIn('resync_apres_envoi', devis.etude_params or {})
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_patch_vide_brouillon_identique(self):
        devis = self._devis(Devis.Statut.BROUILLON)
        avant = self._octets(devis)

        reponse = self._patch(devis, {})
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(self._octets(devis), avant)

        # Un PATCH qui ne change que ``date_validite`` ne ré-écrit pas les
        # études non plus (champ d'en-tête lu par aucune étude).
        nouvelle = (timezone.now().date() + timedelta(days=45)).isoformat()
        reponse = self._patch(devis, {'date_validite': nouvelle})
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(self._octets(devis), avant)
        devis.refresh_from_db()
        self.assertEqual(devis.date_validite.isoformat(), nouvelle)

    def test_entree_etude_trace_envoye(self):
        devis = self._devis(Devis.Statut.ENVOYE)
        avant = self._octets(devis)

        # Le marché est une ENTRÉE d'étude : les études repartent (forcées)
        # et ré-écrivent au moins la ``ville_calcul`` périmée.
        reponse = self._patch(devis, {'mode_installation': 'commercial'})
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertNotEqual(self._octets(devis), avant)

        devis.refresh_from_db()
        self.assertEqual(
            (devis.etude_params or {}).get('ville_calcul', {}).get('ville'),
            'Casablanca')
        corrections = DevisActivity.objects.filter(
            devis=devis, field='correction_apres_envoi')
        self.assertEqual(corrections.count(), 1)
        self.assertIn('étude', corrections.get().body)
        self.assertTrue(
            (devis.etude_params or {}).get('resync_apres_envoi', {})
            .get('date'))
        # Règle #4 : la correction ne change jamais le statut.
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
