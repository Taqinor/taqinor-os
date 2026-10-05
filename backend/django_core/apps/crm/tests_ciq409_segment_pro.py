"""CIQ409 — segment pro SUGGÉRÉ (jamais écrit) et drapeau d'incohérence
lead ↔ devis C&I (jamais de changement automatique du type).

Contrat partagé : ``apps/crm/contract_samples/lead_pro.json`` (CIQ1, blocs
``exemple_incoherent``, ``incoherence_segment``, ``segment_suggere``).

Run :
    python manage.py test apps.crm.tests_ciq409_segment_pro -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.segment_suggere import segment_suggere
from apps.crm.serializers import incoherence_segment
from apps.ventes.domain.cycle_vie import accept_devis, mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()
SECRET = 'test-secret-ciq409'

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_pro.json').read_text(encoding='utf-8'))


def _lead(**kwargs):
    kwargs.setdefault('nom', 'P')
    return Lead(**kwargs)


class SuggestionPro(SimpleTestCase):
    def test_page_professionnel_suggestion_commercial(self):
        for page in ('/professionnel', '/en/professionnel',
                     '/ar/professionnel/'):
            bloc = segment_suggere(_lead(page=page))
            self.assertEqual(bloc['valeur'], 'commercial', page)
            self.assertIn('professionnel', bloc['raison'])

    def test_tags_odoo_usine_industriel(self):
        bloc = segment_suggere(_lead(note='Tags Odoo: Usine'))
        self.assertEqual(bloc['valeur'], 'industriel')
        self.assertIn('« usine »', bloc['raison'])

    def test_un_mot_d_industrie_l_emporte(self):
        bloc = segment_suggere(_lead(page='/professionnel',
                                     note='hôtel et atelier'))
        self.assertEqual(bloc['valeur'], 'industriel')

    def test_mots_de_commerce(self):
        for note in ('un riad à Marrakech', 'Société X', 'notre ECOLE',
                     'restaurant'):
            self.assertEqual(segment_suggere(_lead(note=note))['valeur'],
                             'commercial', note)

    def test_mot_entier_cafetiere_rien(self):
        self.assertIsNone(segment_suggere(_lead(note='une cafetière')))

    def test_societe_remplie_commercial_raison_du_contrat(self):
        bloc = segment_suggere(_lead(type_installation='residentiel',
                                     societe='Café Exemple'))
        self.assertEqual(bloc, CONTRAT['exemple_incoherent']['segment_suggere'])

    def test_seul_bill_kwh_connu_commercial(self):
        self.assertEqual(segment_suggere(_lead(
            bill_kwh=Decimal('900')))['valeur'], 'commercial')
        self.assertIsNone(segment_suggere(_lead(
            bill_kwh=Decimal('900'), facture_hiver=Decimal('1200'))))

    def test_null_si_deja_pro(self):
        for segment in ('commercial', 'industriel'):
            self.assertIsNone(segment_suggere(_lead(
                type_installation=segment, note='usine',
                page='/professionnel', societe='X SARL')), segment)


class _Base(TestCase):
    slug = 'ciq409'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'CIQ409 Co'})
        self.user = User.objects.create_user(
            username=f'{self.slug}_u', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Gérant',
            type_installation='residentiel')
        self._n = 0

    def _devis(self, mode, company=None, client=None):
        self._n += 1
        return Devis.objects.create(
            company=company or self.company,
            reference=f'DEV-{self.slug}-{self._n}',
            client=client or self.client_obj, lead=self.lead,
            statut='brouillon', taux_tva=Decimal('20.00'),
            mode_installation=mode)

    def _detail(self):
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.data


class IncoherenceCI(_Base):
    def test_lead_residentiel_devis_industriel_bloc_renseigne(self):
        devis = self._devis('industriel')
        bloc = self._detail()['incoherence_segment']
        attendu = CONTRAT['exemple_incoherent']['incoherence_segment']
        self.assertEqual(set(bloc), set(attendu))
        self.assertEqual(bloc['mode_devis'], 'industriel')
        self.assertEqual(bloc['devis'],
                         [{'id': devis.id, 'reference': devis.reference}])
        self.assertEqual(
            bloc['message'],
            'Ce lead est typé « résidentiel » mais porte un devis '
            'industriel. Changer le type du lead en « industriel » ?')

    def test_lead_pro_tous_devis_residentiels_inverse(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='commercial')
        self._devis('residentiel')
        bloc = self._detail()['incoherence_segment']
        self.assertEqual(bloc['mode_devis'], 'residentiel')

    def test_lead_commercial_devis_industriel_rien(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='commercial')
        self._devis('industriel')
        self.assertIsNone(self._detail()['incoherence_segment'])

    def test_creer_puis_accepter_le_devis_laisse_le_type(self):
        devis = self._devis('industriel')
        mark_devis_sent(devis=devis, user=self.user)
        devis.refresh_from_db()
        accept_devis(devis=devis, user=self.user, nom='Client')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.type_installation, 'residentiel')

    def test_devis_d_une_autre_societe_ignore(self):
        autre, _ = Company.objects.get_or_create(
            slug='ciq409-autre', defaults={'nom': 'CIQ409 Autre'})
        client_autre = Client.objects.create(
            company=autre, nom='Autre', email='ciq409-autre@example.com')
        self._devis('commercial', company=autre, client=client_autre)
        self.assertIsNone(self._detail()['incoherence_segment'])

    def test_liste_garde_son_nombre_de_requetes(self):
        def _compte():
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/crm/leads/')
            self.assertEqual(resp.status_code, 200)
            return resp, len(ctx.captured_queries)

        resp, avant = _compte()
        for ligne in resp.data.get('results', resp.data):
            self.assertNotIn('incoherence_segment', ligne)
            self.assertNotIn('segment_suggere', ligne)
        self._devis('industriel')
        Lead.objects.filter(pk=self.lead.pk).update(societe='Atelier SA')
        _resp, apres = _compte()
        self.assertEqual(apres, avant)

    def test_forme_du_contrat_pour_la_fonction_pure(self):
        attendu = CONTRAT['exemple_incoherent']['incoherence_segment']
        bloc = incoherence_segment('residentiel', [
            {'id': 5120, 'reference': 'DEV-2026-10-0011',
             'mode_installation': 'commercial', 'statut': 'brouillon'}])
        self.assertEqual(bloc, attendu)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookSansEcriture(_Base):
    slug = 'ciq409-wh'

    def test_lead_professionnel_sans_mode_type_toujours_vide(self):
        res = self.client.post(
            reverse('website-lead-webhook'),
            data=json.dumps({
                'fullName': 'Gérant Test',
                'phoneE164': '+212661000409',
                'whatsappOptIn': True,
                'city': 'Casablanca',
                'consent': True,
                'page': '/professionnel',
            }),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertFalse(lead.type_installation)
        detail = self.api.get(f'/api/django/crm/leads/{lead.id}/').data
        self.assertEqual(detail['segment_suggere']['valeur'], 'commercial')
        lead.refresh_from_db()
        self.assertFalse(lead.type_installation)
