"""PV79 — l'événement ``layout_finalise`` et sa note au chatter du lead.

Trois garanties :

* l'événement est DÉCLARÉ au bus ``core.events`` ET catalogué
  (``core.event_catalog``) — sans quoi la couverture NTPLT12/WIR139 rougit ;
* il est émis à la création depuis un calepinage ET à une resynchronisation
  RÉUSSIE — jamais quand rien n'a changé ;
* ``crm`` réagit en posant une note « Conception 3D finalisée — X kWc » au
  chatter du lead, sans que ``ventes`` importe jamais ``crm``.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv79_layout_finalise -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis
from authentication.models import Company
from core import event_catalog, events
from core.event_coverage import (
    catalog_payload_mismatches, catalogued_but_undeclared,
    uncatalogued_events,
)

User = get_user_model()


class CatalogueEvenementTest(SimpleTestCase):
    """Le bus et le catalogue ne peuvent pas diverger (NTPLT12 / WIR139)."""

    def test_signal_declare(self):
        self.assertTrue(hasattr(events, 'layout_finalise'))

    def test_signal_catalogue(self):
        self.assertIn('layout_finalise', event_catalog.CATALOG)
        entree = event_catalog.CATALOG['layout_finalise']
        self.assertEqual(set(entree['payload']), {'devis', 'user'})
        self.assertTrue(entree['description'])

    def test_couverture_globale_intacte(self):
        self.assertNotIn('layout_finalise', uncatalogued_events())
        self.assertNotIn('layout_finalise', catalogued_but_undeclared())
        self.assertNotIn('layout_finalise', catalog_payload_mismatches())


class NoteChatterTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv79-acme")
        self.user = User.objects.create_user(
            username="pv79_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom="Lead PV79", telephone="0600000079")
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV79", email="pv79@example.com")

    def _devis(self, lead=None, layout=None):
        return Devis.objects.create(
            company=self.company, reference="DV-PV79-%s" % Devis.objects.count(),
            client=self.crm_client, lead=lead,
            roof_layout=layout if layout is not None
            else {'result': {'kwc': 7.7}})

    def _notes(self):
        return list(LeadActivity.objects
                    .filter(lead=self.lead, kind=LeadActivity.Kind.NOTE)
                    .values_list('body', flat=True))

    def test_note_posee_avec_la_puissance(self):
        devis = self._devis(lead=self.lead)
        events.layout_finalise.send(sender='test', devis=devis,
                                    user=self.user)
        notes = self._notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0], 'Conception 3D finalisée — 7,7 kWc')

    def test_note_sans_puissance_ne_fabrique_pas_de_zero(self):
        devis = self._devis(lead=self.lead, layout={'zones': []})
        events.layout_finalise.send(sender='test', devis=devis,
                                    user=self.user)
        self.assertEqual(self._notes(), ['Conception 3D finalisée'])

    def test_devis_sans_lead_ne_note_rien(self):
        devis = self._devis(lead=None)
        events.layout_finalise.send(sender='test', devis=devis,
                                    user=self.user)
        self.assertEqual(LeadActivity.objects.filter(
            kind=LeadActivity.Kind.NOTE).count(), 0)

    def test_note_porte_lauteur_et_la_societe(self):
        devis = self._devis(lead=self.lead)
        events.layout_finalise.send(sender='test', devis=devis,
                                    user=self.user)
        note = LeadActivity.objects.get(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertEqual(note.user_id, self.user.id)
        self.assertEqual(note.company_id, self.company.id)

    def test_aucun_statut_de_devis_touche(self):
        devis = self._devis(lead=self.lead)
        statut = devis.statut
        events.layout_finalise.send(sender='test', devis=devis,
                                    user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, statut)


class EmissionDepuisSyncLayoutTest(TestCase):
    """L'émission est câblée sur le chemin de resynchronisation (PV18)."""

    def setUp(self):
        from apps.stock.models import Produit
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        self.company = Company.objects.create(nom="Acme", slug="pv79c-acme")
        self.user = User.objects.create_user(
            username='pv79c_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client PV79c')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead PV79c', telephone='0600000080')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV79-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=100)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-PV79C-1',
            client=self.crm_client, lead=self.lead, created_by=self.user)
        self.devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('980'), ordre=1)

    def _corps(self, panels=16, kwc=8.8):
        return {'scenario': 'reseau', 'panelWatt': 550,
                'result': {'panels': panels, 'kwc': kwc,
                           'annualKwh': 14000, 'savings': 12000}}

    def _post(self, corps):
        return self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % self.devis.id,
            corps, format='json')

    def _notes(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE).count()

    def test_resynchronisation_pose_une_note(self):
        resp = self._post(self._corps(panels=16))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.data['inchange'])
        self.assertEqual(self._notes(), 1)

    def test_meme_layout_ne_pose_rien(self):
        corps = self._corps(panels=16)
        self._post(corps)
        avant = self._notes()
        resp = self._post(corps)
        self.assertTrue(resp.data['inchange'])
        self.assertEqual(self._notes(), avant)   # rien ne s'est passé

    def test_conflit_409_ne_pose_rien(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        resp = self._post(self._corps(panels=16))
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._notes(), 0)

    def test_abonne_en_echec_ne_casse_pas_la_finalisation(self):
        from unittest import mock

        from apps.ventes.views.devis import _emettre_layout_finalise

        with mock.patch('core.events.layout_finalise.send',
                        side_effect=RuntimeError('abonné cassé')):
            _emettre_layout_finalise(self.devis, self.user)  # ne lève pas
