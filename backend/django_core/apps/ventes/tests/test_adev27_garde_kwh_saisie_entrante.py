"""ADEV27 (C-ADEV-038) — la garde « kWh déclaré vs factures » de
``replace-lines`` juge la saisie ENTRANTE (après écriture, dans la
transaction), comme ``/atomic`` : même corps ⇒ même verdict sur les deux
chemins.

Rejoue la sonde VB p10 : lead à ``conso_mensuelle_kwh=40`` face à
``facture_hiver=3000`` (incohérent tant que rien d'autre n'est saisi) ; le
corps porte ``etude_params.conso_kwh_mensuelles=[300]*12`` — 12 kWh mesurés
qui priment sur le kWh déclaré et neutralisent donc la garde. Avant :
``atomic`` → 201, ``replace-lines`` → 400 (jugé sur l'état d'AVANT).

Test-du-test : remettre ``_garde_kwh_declare(devis)`` AVANT l'écriture dans
``replace_lines`` ⇒ ``test_parite_replace_lines_atomic`` échoue.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_adev27_garde_kwh_saisie_entrante"
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.horaire.conso import CODE_KWH_INCOHERENT
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MOIS = timezone.now().strftime('%Y%m')
MESURES = [300] * 12


class GardeKwhSaisieEntranteTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ADEV27 Co', slug='adev27-co')
        self.user = User.objects.create_user(
            username='adev27_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV27',
            email='adev27@example.test', telephone='+212600002700')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ADEV27',
            telephone='+212600002701', ville='Casablanca',
            client=self.client_obj, facture_hiver=Decimal('3000'),
            ete_differente=False, conso_mensuelle_kwh=Decimal('40'))
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ADEV27-PV', prix_vente=Decimal('1450'), quantite_stock=50)
        # Le devis 48 de la sonde : brouillon lié au lead, une ligne, aucune
        # mesure posée (le kWh déclaré du lead chiffrerait).
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MOIS}-A2701',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            created_by=self.user, etude_params={'scenario': 'Sans batterie'})
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation='Ligne d origine', quantite=Decimal('4'),
            prix_unitaire=Decimal('1450'), remise=Decimal('0'), ordre=0)

    def _lignes(self):
        return [{'produit': self.produit.id, 'designation': self.produit.nom,
                 'quantite': '6', 'prix_unitaire': '1450'}]

    def _replace(self, etude):
        corps = {'lignes': self._lignes()}
        if etude is not None:
            corps['etude_params'] = etude
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.pk}/replace-lines/',
            corps, format='json')

    def _atomic(self, etude):
        corps = {'lead': self.lead.id, 'taux_tva': '20',
                 'lignes': self._lignes()}
        if etude is not None:
            corps['etude_params'] = etude
        return self.api.post('/api/django/ventes/devis/atomic/', corps,
                             format='json')

    def _etat(self):
        """Lignes + ``etude_params`` relus en base (comparaison octet)."""
        lignes = list(LigneDevis.objects.filter(devis_id=self.devis.pk)
                      .order_by('ordre', 'id')
                      .values_list('designation', 'quantite'))
        etude = Devis.objects.values_list(
            'etude_params', flat=True).get(pk=self.devis.pk)
        return lignes, json.dumps(etude, sort_keys=True)

    def test_parite_replace_lines_atomic(self):
        etude = {'conso_kwh_mensuelles': MESURES}
        r_replace = self._replace(etude)
        r_atomic = self._atomic(etude)
        # La saisie ENTRANTE est cohérente : les deux chemins enregistrent.
        self.assertEqual(r_replace.status_code, 200, r_replace.content)
        self.assertEqual(r_atomic.status_code, 201, r_atomic.content)
        self.devis.refresh_from_db()
        self.assertEqual(
            (self.devis.etude_params or {}).get('conso_kwh_mensuelles'),
            MESURES)

    def test_incoherent_400_rollback(self):
        # Saisie incohérente (aucune mesure ; le kWh déclaré 40 contredit la
        # facture 3 000 MAD) : même refus sur les deux chemins, rien d'écrit.
        avant = self._etat()
        nb_devis = Devis.objects.filter(company=self.company).count()
        etude = {'scenario': 'Avec batterie'}

        r_replace = self._replace(etude)
        self.assertEqual(r_replace.status_code, 400, r_replace.content)
        self.assertEqual(r_replace.data['code'], CODE_KWH_INCOHERENT)
        # CLAUSE PERSISTANCE : GET puis lignes et ``etude_params`` inchangés
        # (le choix d'écran écrit sous la transaction est annulé).
        self.assertEqual(
            self.api.get(
                f'/api/django/ventes/devis/{self.devis.pk}/').status_code,
            200)
        self.assertEqual(self._etat(), avant)

        r_atomic = self._atomic(etude)
        self.assertEqual(r_atomic.status_code, 400, r_atomic.content)
        self.assertEqual(r_atomic.data['code'], CODE_KWH_INCOHERENT)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), nb_devis)
