"""ADEV13 (C-ADEV-005) — blocage crédit / avertissement de vente bloquant :
UNE garde dans ``accept_devis``, appliquée par les TROIS portes.

* interne ``POST /ventes/devis/<id>/accepter/`` : 403 ``sale_warning`` (inchangé) ;
* public ``POST /public/proposal/<token>/accept/`` : 409
  ``{detail, code: "validation_requise"}`` au message NEUTRE du contrat
  ``proposal_accept.json`` (aucun motif interne exposé) ;
* portail ``POST /portail/mes-devis/<id>/accepter/`` : 409 au même message.

Après chaque refus : devis ``envoye``, aucune ``DevisSignature``, aucun
``devis_accepted`` (donc aucun chantier). Sans blocage, les trois acceptent.

Test-du-test : remettre la garde dans la seule vue interne ⇒
``test_public_refuse_si_bloquant`` échoue (le public accepte).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev13_gardes_acceptation_trois_portes -v 2
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.tests.test_ntprt10_mes_devis import make_portal_user
from apps.ventes.models import Devis, DevisSignature, ShareLink
from authentication.models import Company, CustomUser

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'proposal_accept.json').read_text(encoding='utf-8'))
REFUS_NEUTRE = CONTRAT['reponses_409']['validation_requise']
MOTIF_INTERNE = 'Impayés anciens — validation direction'


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class GardesTroisPortesTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='ADEV13 Co', slug='adev13-co')
        self.admin = User.objects.create_user(
            username='adev13_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bloqué', email='adev13@example.com',
            avertissement_vente=MOTIF_INTERNE, avertissement_bloquant=True)
        self.portail_user = make_portal_user(
            self.company, 'adev13-portail',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_obj.id)
        self.n = 0
        self.evenements = []
        from core.events import devis_accepted

        def _ecoute(sender, **kwargs):
            self.evenements.append(kwargs.get('devis'))

        devis_accepted.connect(_ecoute, dispatch_uid='adev13', weak=False)
        self.addCleanup(devis_accepted.disconnect, dispatch_uid='adev13')
        patcher = patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _devis(self):
        self.n += 1
        return Devis.objects.create(
            company=self.company, reference=f'DEV-ADEV13-{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.admin)

    def _debloquer(self):
        Client.objects.filter(pk=self.client_obj.pk).update(
            avertissement_bloquant=False)

    # ── les trois portes ──────────────────────────────────────────────────
    def _interne(self, devis):
        api = APIClient()
        api.force_authenticate(user=self.admin)
        return api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                        {'nom': 'Client', 'option': 'sans_batterie'},
                        format='json')

    def _public(self, devis):
        lien = ShareLink.for_devis(devis)
        return APIClient().post(
            f'/api/django/public/proposal/{lien.token}/accept/',
            {'nom': 'Client', 'option': 'sans_batterie',
             'consent_esign': True}, format='json')

    def _portail(self, devis):
        api = APIClient()
        api.force_authenticate(user=self.portail_user)
        return api.post(
            f'/api/django/portail/mes-devis/{devis.id}/accepter/',
            {'nom': 'Client', 'option': 'sans_batterie',
             'consent_esign': True}, format='json')

    def _assert_rien_ecrit(self, devis):
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(DevisSignature.objects.filter(devis=devis).exists())
        self.assertEqual(self.evenements, [])

    def _assert_refus_neutre(self, reponse):
        self.assertEqual(reponse.status_code, 409, reponse.content)
        corps = reponse.json()
        self.assertEqual(corps['detail'], REFUS_NEUTRE['detail'])
        # CLAUSE CLIENT : aucun motif interne exposé.
        self.assertNotIn(MOTIF_INTERNE, reponse.content.decode('utf-8'))
        return corps

    def test_public_refuse_si_bloquant(self):
        devis = self._devis()
        corps = self._assert_refus_neutre(self._public(devis))
        self.assertEqual(corps, REFUS_NEUTRE)
        self._assert_rien_ecrit(devis)

    def test_portail_refuse_si_bloquant(self):
        devis = self._devis()
        self._assert_refus_neutre(self._portail(devis))
        self._assert_rien_ecrit(devis)

    def test_interne_inchange(self):
        devis = self._devis()
        reponse = self._interne(devis)
        self.assertEqual(reponse.status_code, 403, reponse.content)
        self.assertTrue(reponse.data.get('sale_warning'))
        self.assertIn(MOTIF_INTERNE, reponse.data['detail'])
        self._assert_rien_ecrit(devis)

    def test_service_garde_sans_vue(self):
        """La règle vit dans le service : ``accept_devis(user=None)`` direct."""
        from apps.ventes.domain.cycle_vie import AcceptationBloquee
        from apps.ventes.services import AcceptError, accept_devis
        devis = self._devis()
        with self.assertRaises(AcceptError) as ctx:
            accept_devis(devis=devis, user=None, nom='X',
                         option='sans_batterie')
        self.assertIsInstance(ctx.exception, AcceptationBloquee)
        self.assertEqual(ctx.exception.code, 'validation_requise')
        self._assert_rien_ecrit(devis)

    def test_sans_blocage_trois_acceptent(self):
        self._debloquer()
        for porte in (self._interne, self._public, self._portail):
            with self.subTest(porte=porte.__name__):
                devis = self._devis()
                reponse = porte(devis)
                self.assertEqual(reponse.status_code, 200, reponse.content)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(len(self.evenements), 3)
