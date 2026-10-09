"""ADEV51 (C-ADEV-018) — la signature engage l'empreinte du contenu VU.

``proposal_data`` sert ``empreinte_contenu`` (SHA-256 de
``modifiabilite.empreinte_visible``) ; la page la renvoie à ``/accept/`` ; si
le devis a été corrigé SUR PLACE entre la lecture et la signature (D-QJR5-1),
ou si l'empreinte manque, ``/accept/`` répond 409 ``empreinte_perimee`` et
n'écrit rien (sonde VA p12 : accept 200 au nouveau montant).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev51_empreinte_signature -v 2
"""
import json
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink

CONTRAT_ACCEPT = (Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'proposal_accept.json')


class EmpreinteSignatureTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='adev51', defaults={'nom': 'adev51'})
        client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV51',
            email='adev51@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV51-0001',
            client=client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='ADEV51-P',
            prix_vente=Decimal('1100'), quantite_stock=50)
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau 550W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))
        # Vocabulaire du classifieur d'options du moteur (réseau) : sans
        # onduleur, la lecture publique refuse le devis (404).
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Deye 8kW',
            sku='ADEV51-O', prix_vente=Decimal('14000'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation='Onduleur réseau Deye 8kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis, token=str(uuid.uuid4()))
        self.api = APIClient()

    def _lire(self):
        with mock.patch('apps.ventes.public_views._notify_open'):
            resp = self.api.get(
                f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def _signer(self, empreinte=None):
        corps = {'nom': 'M. Client', 'consent_esign': True}
        if empreinte is not None:
            corps['empreinte_contenu'] = empreinte
        with mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/public/proposal/{self.link.token}/accept/',
                corps, format='json')

    def _assert_rien_ecrit(self, resp):
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['code'], 'empreinte_perimee')
        attendu = json.loads(CONTRAT_ACCEPT.read_text(encoding='utf-8'))
        self.assertEqual(
            resp.data, attendu['reponses_409']['empreinte_perimee'])
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(
            DevisSignature.objects.filter(devis=self.devis).exists())

    def test_correction_entre_lecture_et_signature_409(self):
        lu = self._lire()
        e0 = lu['empreinte_contenu']
        # Correction SUR PLACE d'un envoyé (D-QJR5-1) : +1 sur une ligne.
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite=Decimal('11'))
        self.assertNotEqual(self._lire()['empreinte_contenu'], e0)
        self._assert_rien_ecrit(self._signer(e0))
        # CLAUSE PERSISTANCE : relire après le 409 → toujours rien de signé.
        self.assertFalse(self._lire()['accepted'])

    def test_empreinte_courante_200(self):
        lu = self._lire()
        resp = self._signer(lu['empreinte_contenu'])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)

    def test_empreinte_absente_409(self):
        self._assert_rien_ecrit(self._signer())

    def test_empreinte_absente_de_la_lecture_quand_rien_n_est_signable(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ACCEPTE)
        self.assertNotIn('empreinte_contenu', self._lire())
