"""ADEV52 (C-ADEV-019) — UNE règle d'expiration, servie et appliquée.

``utils/expiry.is_expired`` (fin du dernier jour de validité à l'heure du
Maroc) est servie à la page (``offre_expiree``, ``date_expiration``) et
appliquée à l'acceptation CLIENT — lien public et portail : 409 ``expiree``,
aucune signature, devis ``envoye``. L'acceptation INTERNE garde son
comportement (un commercial peut enregistrer une acceptation tardive).
Sonde VA p6 : ``is_expired True`` puis accept 200.

Test-du-test : retirer le contrôle ``is_expired`` d'``accept_devis`` (chemin
client) ⇒ ``test_accept_public_expire_409`` échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev52_expiration_une_regle -v 2
"""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.tests.test_ntprt10_mes_devis import make_portal_user
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink
from apps.ventes.public.signature_views import empreinte_contenu
from apps.ventes.utils.expiry import is_expired
from authentication.models import Company, CustomUser

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'proposal_accept.json').read_text(encoding='utf-8'))
REFUS_EXPIREE = CONTRAT['reponses_409']['expiree']


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ExpirationUneRegleTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ADEV52 Co',
                                              slug='adev52-co')
        self.admin = User.objects.create_user(
            username='adev52_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='adev52@example.com')
        self.portail_user = make_portal_user(
            self.company, 'adev52-portail',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_obj.id)
        self.n = 0
        patcher = mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _devis(self, date_validite):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ADEV52-{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.admin,
            date_validite=date_validite)
        for i, (nom, qte, pu) in enumerate((
                ('Onduleur réseau Deye 8kW', '1', '14000'),
                ('Panneau 550W', '10', '1100'))):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'A52-{self.n}-{i}',
                prix_vente=Decimal(pu), quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), ordre=i)
        return devis

    def _public(self, devis):
        lien = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()))
        return APIClient().post(
            f'/api/django/public/proposal/{lien.token}/accept/',
            {'nom': 'Client', 'consent_esign': True,
             'empreinte_contenu': empreinte_contenu(devis)}, format='json')

    def _lire(self, devis):
        lien = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()))
        with mock.patch('apps.ventes.public_views._notify_open'):
            resp = APIClient().get(
                f'/api/django/public/proposal/{lien.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def _assert_rien_ecrit(self, devis):
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(DevisSignature.objects.filter(devis=devis).exists())

    def test_accept_public_expire_409(self):
        devis = self._devis(timezone.localdate() - timedelta(days=3))
        self.assertTrue(is_expired(devis))
        resp = self._public(devis)
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data, REFUS_EXPIREE)
        self._assert_rien_ecrit(devis)

    def test_portail_expire_409(self):
        devis = self._devis(timezone.localdate() - timedelta(days=3))
        api = APIClient()
        api.force_authenticate(user=self.portail_user)
        resp = api.post(
            f'/api/django/portail/mes-devis/{devis.id}/accepter/',
            {'nom': 'Client', 'consent_esign': True}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self._assert_rien_ecrit(devis)

    def test_dernier_jour_accepte(self):
        # Dernier jour de validité, 13:30 UTC (= 14:30 au Maroc) : la page
        # disait « expirée » (12:00 UTC) ; le serveur accepte, toute la journée
        # locale.
        devis = self._devis(date(2026, 10, 15))
        with freeze_time('2026-10-15T13:30:00Z'):
            self.assertFalse(self._lire(devis)['offre_expiree'])
            resp = self._public(devis)
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_offre_expiree_servie(self):
        expire = self._devis(timezone.localdate() - timedelta(days=3))
        corps = self._lire(expire)
        self.assertIs(corps['offre_expiree'], True)
        self.assertEqual(corps['date_expiration'],
                         expire.date_validite.isoformat())
        # Rien de signable : aucune empreinte servie.
        self.assertNotIn('empreinte_contenu', corps)
        valide = self._devis(timezone.localdate() + timedelta(days=5))
        corps = self._lire(valide)
        self.assertIs(corps['offre_expiree'], False)
        self.assertIn('empreinte_contenu', corps)

    def test_interne_garde_l_acceptation_tardive(self):
        devis = self._devis(timezone.localdate() - timedelta(days=3))
        api = APIClient()
        api.force_authenticate(user=self.admin)
        resp = api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                        {'nom': 'Client', 'option': 'sans_batterie'},
                        format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        # CLAUSE PERSISTANCE côté client : un expiré refusé reste « envoye ».
        refuse = self._devis(timezone.localdate() - timedelta(days=3))
        self._public(refuse)
        self._assert_rien_ecrit(refuse)
