"""ACAL34 (C-ACAL-109) — UNE enveloppe ventes ``resynchroniser_conception``
(resynchro + quatre études) appelée par ``sync-layout`` ET par
« Resynchroniser le devis » du module calepinage.

* après la resynchro depuis le MODULE, l'étude horaire et les profils
  comparatifs décrivent les lignes (16 panneaux, plus 12) ;
* parité : le JSON public de la proposition (économies, retour) est le même
  par la voie module et par la voie ventes, pour un jumeau ;
* un renvoi identique (``inchange``) ne rafraîchit rien : ``etude_params``
  octet-identique.

Fixtures calquées sur ``test_l_pcmp_profils_comparatifs`` (Casablanca, table
de référence PVGIS, aucun accès réseau) ; ``rafraichir_etudes_du_devis`` et
``sync_devis_from_layout`` RÉELS, jamais mockés.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_resync_parite"
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis, LigneDevis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
WATT = 710


def _layout(panneaux):
    return {
        'scenario': 'reseau',
        'panelWatt': WATT,
        'result': {'panels': panneaux, 'kwc': round(panneaux * WATT / 1000,
                                                    2),
                   'annualKwh': 14000, 'savings': 12000},
    }


def _quote(data):
    bloc = data.get('quote')
    return bloc if isinstance(bloc, dict) else data


class ResyncParite(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL34 Co',
                                              slug='acal34-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal34', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Client ACAL34')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='A34-PAN', prix_vente=Decimal('1166.67'),
            prix_achat=Decimal('700'), quantite_stock=100)
        Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 10kW Monophasé',
            sku='A34-OND', prix_vente=Decimal('14000'),
            prix_achat=Decimal('9000'), quantite_stock=100)
        self.n = 0

    def _devis(self):
        """Un brouillon de 12 panneaux dont les études sont CALCULÉES."""
        self.n += 1
        lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='ACAL34-%d' % self.n,
            telephone='+21260000034%d' % self.n, ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-34{self.n:02d}',
            client=self.client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={}, created_by=self.user,
            roof_layout=_layout(12), layout_hash=layout_hash(_layout(12)))
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('12'), prix_unitaire=Decimal('1166.67'),
            remise=Decimal('0'))
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        self.assertIsNotNone((devis.etude_params or {}).get('etude_horaire'))
        return devis

    def _sync_module(self, devis, panneaux):
        layout = _layout(panneaux)
        calepinage = Calepinage.objects.filter(devis=devis).first()
        if calepinage is None:
            calepinage = Calepinage.objects.create(
                company=self.company, lead_id=devis.lead_id, devis=devis,
                titre='ACAL34', roof_layout=layout,
                layout_hash=layout_hash(layout))
        return self.api.post(
            f'/api/django/calepinage/calepinages/{calepinage.pk}/sync-devis/',
            {}, format='json')

    def _sync_ventes(self, devis, panneaux):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/sync-layout/',
            _layout(panneaux), format='json')

    def test_resync_module_rafraichit_etude_horaire_et_profils(self):
        devis = self._devis()
        r = self._sync_module(devis, 16)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['inchange'])
        devis.refresh_from_db()
        self.assertEqual(
            int(devis.lignes.get(produit=self.panneau).quantite), 16)
        attendu = round(16 * WATT / 1000, 2)
        etude = devis.etude_params or {}
        self.assertAlmostEqual(float(etude['etude_horaire']['kwc']), attendu,
                               places=2)
        profils = etude.get('profils_comparatifs')
        self.assertIsInstance(profils, dict)
        self.assertAlmostEqual(float(profils['kwc_devis']), attendu,
                               places=2)

    def test_parite_voie_module_voie_ventes_json_public(self):
        module = self._devis()
        ventes = self._devis()
        self.assertEqual(self._sync_module(module, 16).status_code, 200)
        self.assertEqual(self._sync_ventes(ventes, 16).status_code, 200)
        publics = []
        for devis in (module, ventes):
            lien = ShareLink.for_devis(devis)
            pub = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/')
            self.assertEqual(pub.status_code, 200, pub.content)
            publics.append(_quote(pub.data))
        q_module, q_ventes = publics
        for cle in ('eco_s_ann', 'roi_s'):
            with self.subTest(cle=cle):
                self.assertIsNotNone(q_ventes.get(cle), cle)
                self.assertEqual(q_module.get(cle), q_ventes.get(cle))

    def test_resync_inchange_ne_rafraichit_rien(self):
        devis = self._devis()
        self.assertEqual(self._sync_module(devis, 16).status_code, 200)
        devis.refresh_from_db()
        avant = json.dumps(devis.etude_params, sort_keys=True, default=str)
        r = self._sync_module(devis, 16)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['inchange'])
        devis.refresh_from_db()
        self.assertEqual(
            json.dumps(devis.etude_params, sort_keys=True, default=str),
            avant)
