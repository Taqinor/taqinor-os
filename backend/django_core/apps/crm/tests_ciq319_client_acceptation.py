"""CIQ319 (complément) — l'identité d'entreprise déclarée à l'acceptation en
ligne d'un devis C&I remonte au Client QUI N'EN A PAS, par le service CRM
``completer_client_depuis_acceptation`` (contrat CIQ8) ; un ICE différent
déjà présent n'est jamais écrasé (drapeau ``divergence_ice``).

Chemin RÉEL : POST public ``/api/django/public/proposal/<token>/accept/``
(PDF signé neutralisé comme dans ``test_ciq319_acceptation_entreprise``).
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.crm.clients_identite import completer_client_depuis_acceptation

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'ventes' / 'contract_samples'
     / 'acceptation_entreprise.json').read_text(encoding='utf-8'))
ENTREPRISE = dict(CONTRAT['exemple']['entreprise'])


class CompleterClientService(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ319c Co')
        self.autre = Company.objects.create(nom='CIQ319c Autre')

    def _client(self, **kw):
        champs = dict(company=self.company, nom='Karim Exemple',
                      email=None, telephone='+212600000391')
        champs.update(kw)
        return Client.objects.create(**champs)

    def test_ice_ecrit_quand_absent(self):
        client = self._client()
        ecrits = completer_client_depuis_acceptation(
            client.pk, self.company, raison_sociale='', ice=ENTREPRISE['ice'])
        client.refresh_from_db()
        self.assertEqual(client.ice, ENTREPRISE['ice'])
        self.assertEqual(client.type_client, Client.TypeClient.ENTREPRISE)
        self.assertIn('ice', ecrits)

    def test_ice_different_jamais_ecrase(self):
        client = self._client(ice='111111111111111',
                              type_client=Client.TypeClient.ENTREPRISE)
        ecrits = completer_client_depuis_acceptation(
            client.pk, self.company, ice=ENTREPRISE['ice'])
        client.refresh_from_db()
        self.assertEqual(client.ice, '111111111111111')
        self.assertEqual(ecrits, [])

    def test_raison_sociale_seulement_si_a_confirmer(self):
        a_confirmer = self._client(raison_sociale_a_confirmer=True)
        completer_client_depuis_acceptation(
            a_confirmer.pk, self.company,
            raison_sociale=ENTREPRISE['raison_sociale'])
        a_confirmer.refresh_from_db()
        self.assertEqual(a_confirmer.nom, ENTREPRISE['raison_sociale'])
        self.assertFalse(a_confirmer.raison_sociale_a_confirmer)

        nomme = self._client(nom='Hôtel Déjà Nommé',
                             telephone='+212600000392')
        completer_client_depuis_acceptation(
            nomme.pk, self.company,
            raison_sociale=ENTREPRISE['raison_sociale'])
        nomme.refresh_from_db()
        self.assertEqual(nomme.nom, 'Hôtel Déjà Nommé')

    def test_borne_a_la_societe(self):
        client = self._client()
        ecrits = completer_client_depuis_acceptation(
            client.pk, self.autre, ice=ENTREPRISE['ice'])
        client.refresh_from_db()
        self.assertEqual(ecrits, [])
        self.assertFalse(client.ice)

    def test_rejouer_idempotent(self):
        client = self._client(raison_sociale_a_confirmer=True)
        premier = completer_client_depuis_acceptation(
            client.pk, self.company, **{
                'raison_sociale': ENTREPRISE['raison_sociale'],
                'ice': ENTREPRISE['ice']})
        self.assertTrue(premier)
        second = completer_client_depuis_acceptation(
            client.pk, self.company, **{
                'raison_sociale': 'Autre SARL', 'ice': ENTREPRISE['ice']})
        self.assertEqual(second, [])
        client.refresh_from_db()
        self.assertEqual(client.nom, ENTREPRISE['raison_sociale'])


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AcceptationRemonteAuClient(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ319c API')
        self.seller = User.objects.create_user(
            username='ciq319c_seller', password='x',
            role_legacy='commercial', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Karim Exemple',
            email='ciq319c@example.test', telephone='+212600000393',
            raison_sociale_a_confirmer=True)
        self.api = APIClient()
        self.n = 0

    def _devis(self, mode):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        self.n += 10
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-C9{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.seller,
            mode_installation=mode)
        for i, nom in enumerate(('Panneau Canadien Solar 710W',
                                 'Onduleur réseau Huawei 10kW Triphasé')):
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                sku=f'C9{self.n}-{i}',
                prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
        return devis

    def _post(self, devis, entreprise=None):
        from apps.ventes.models import ShareLink
        from apps.ventes.public.signature_views import empreinte_contenu
        link = ShareLink.for_devis(devis)
        # ADEV51 — le corps renvoie l'empreinte du contenu lu.
        corps = {'nom': 'Karim Exemple', 'consent_esign': True,
                 'empreinte_contenu': empreinte_contenu(devis)}
        if entreprise is not None:
            corps['entreprise'] = entreprise
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                corps, format='json')

    def test_acceptation_ci_complete_le_client(self):
        resp = self._post(self._devis('industriel'), ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.ice, ENTREPRISE['ice'])
        self.assertEqual(self.client_obj.nom, ENTREPRISE['raison_sociale'])
        self.assertEqual(self.client_obj.type_client,
                         Client.TypeClient.ENTREPRISE)

    def test_ice_different_non_ecrase_et_drapeau(self):
        from apps.ventes.domain.cycle_vie import divergence_ice
        self.client_obj.ice = '111111111111111'
        self.client_obj.save(update_fields=['ice'])
        devis = self._devis('commercial')
        self.assertEqual(self._post(devis, ENTREPRISE).status_code, 200)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.ice, '111111111111111')
        self.assertTrue(divergence_ice(devis, ENTREPRISE['ice']))

    def test_residentiel_ne_touche_pas_le_client(self):
        resp = self._post(self._devis('residentiel'), ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.client_obj.refresh_from_db()
        self.assertFalse(self.client_obj.ice)
        self.assertEqual(self.client_obj.nom, 'Karim Exemple')
