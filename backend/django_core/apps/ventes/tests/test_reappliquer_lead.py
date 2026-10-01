"""QJR588 (contrat QJR505 ``devis_reappliquer_lead.json``) — la dérive
lead → devis se RÉSOUT : « reprendre les valeurs du lead »
(``reappliquer-lead``) ou « garder celles du devis » (``acquitter-derive``).
Brouillon et envoyé sur place (envoyé : statut inchangé, instantané, chatter
« corrigé après envoi ») ; accepté → 400 ``devis_fige``, rien d'écrit.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.ventes.models import (
    ConfigurationDevisSnapshot, Devis, DevisActivity, LigneDevis)
from apps.ventes.services import build_devis_auto
from apps.ventes.tests.test_auto_pipeline import (
    VILLE_ANCRE, make_company, seed_catalogue)

User = get_user_model()
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'devis_reappliquer_lead.json')


class TestReappliquerLead(TestCase):
    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.company = make_company('qjr588-co')
        self.user = User.objects.create_user(
            username='qjr588_resp', password='x', role_legacy='responsable',
            company=self.company)
        seed_catalogue(self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Derive', prenom='Lead',
            email='qjr588@example.com', ville=VILLE_ANCRE,
            facture_hiver=Decimal('900'))
        self.devis = build_devis_auto(
            lead=self.lead, user=self.user, company=self.company)
        # Une ligne au prix NÉGOCIÉ (verrou manuel) : jamais réécrite.
        self.negociee = LigneDevis.objects.create(
            devis=self.devis, designation='Prestation négociée',
            quantite=Decimal('1'), prix_unitaire=Decimal('777'),
            remise=Decimal('0'), prix_manuel=True, ordre=99)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, suffixe):
        return f'/api/django/ventes/devis/{self.devis.id}/{suffixe}/'

    def _derive(self):
        r = self.api.get(f'/api/django/ventes/devis/{self.devis.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data.get('lead_valeurs_modifiees') or []

    def _panneaux(self):
        from apps.ventes.offres_tailles import _compter_panneaux_du_devis
        return _compter_panneaux_du_devis(
            Devis.objects.get(pk=self.devis.pk))

    def _modifier_lead(self):
        self.lead.facture_hiver = Decimal('1500')
        self.lead.save(update_fields=['facture_hiver'])

    def test_reprendre_les_valeurs_du_lead(self):
        avant = self._panneaux()
        self._modifier_lead()
        self.assertEqual(self._derive(), ['facture_hiver'])
        r = self.api.post(self._url('reappliquer-lead'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(set(r.data), set(self.contrat['exemple']))
        self.assertEqual(r.data['champs_repris'], ['facture_hiver'])
        self.assertEqual(r.data['devis']['lead_valeurs_modifiees'] or [], [])
        self.assertGreater(self._panneaux(), avant)
        self.negociee.refresh_from_db()
        self.assertEqual(self.negociee.prix_unitaire, Decimal('777'))
        self.assertTrue(self.negociee.prix_manuel)
        self.assertEqual(self._derive(), [])

    def test_envoye_corrige_sur_place(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        self._modifier_lead()
        instantanes = ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).count()
        r = self.api.post(self._url('reappliquer-lead'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertTrue(r.data['corrige_apres_envoi'])
        self.assertGreater(ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).count(), instantanes)
        self.assertTrue(DevisActivity.objects.filter(
            devis=self.devis, field='correction_apres_envoi').exists())

    def test_accepte_400_rien_ecrit(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ACCEPTE)
        self._modifier_lead()
        lignes = list(LigneDevis.objects.filter(devis=self.devis)
                      .values_list('id', 'quantite'))
        for suffixe in ('reappliquer-lead', 'acquitter-derive'):
            r = self.api.post(self._url(suffixe), {}, format='json')
            self.assertEqual(r.status_code, 400, r.content)
            self.assertEqual(r.json(), self.contrat['exemple_400'])
        self.assertEqual(list(LigneDevis.objects.filter(devis=self.devis)
                              .values_list('id', 'quantite')), lignes)

    def test_garder_les_valeurs_du_devis(self):
        self._modifier_lead()
        lignes = list(LigneDevis.objects.filter(devis=self.devis)
                      .order_by('id')
                      .values_list('id', 'quantite', 'prix_unitaire'))
        r = self.api.post(self._url('acquitter-derive'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['champs_repris'], [])
        self.assertFalse(r.data['corrige_apres_envoi'])
        self.assertEqual(self._derive(), [])
        self.assertEqual(list(LigneDevis.objects.filter(devis=self.devis)
                              .order_by('id')
                              .values_list('id', 'quantite', 'prix_unitaire')),
                         lignes)

    def test_autre_societe_404(self):
        autre = make_company('qjr588-autre')
        intrus = User.objects.create_user(
            username='qjr588_intrus', password='x', role_legacy='responsable',
            company=autre)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(intrus)}')
        r = api.post(self._url('reappliquer-lead'), {}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
