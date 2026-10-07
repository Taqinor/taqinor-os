"""ALEA9 — ``POST /api/django/visites/visites/`` délègue à
``services.planifier_visite`` : mêmes gardes, aucun doublon, une seule note.

Rejoue la sonde V4 LVIS-5 : aujourd'hui 201, 201 et une note doublée
(« Visite technique créée. » + « Visite technique planifiée le … »).
"""
import datetime

from django.utils import timezone

from apps.crm.models import LeadActivity
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import (
    BUREAU, VisiteTerrainBase, auth, make_user)

URL = '/api/django/visites/visites/'


class PlanificationUniqueTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.api_bureau = auth(self.bureau)
        self.inactif = make_user(self.company, 'alea9-inactif', BUREAU)
        self.inactif.is_active = False
        self.inactif.save(update_fields=['is_active'])
        self.aujourdhui = timezone.localdate()
        self.hier = self.aujourdhui - datetime.timedelta(days=1)
        self.demain = self.aujourdhui + datetime.timedelta(days=1)

    def _en_attente(self):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.commercial,
            statut=VisiteTerrain.Statut.BROUILLON,
            date_prevue=self.aujourdhui + datetime.timedelta(days=5))

    def _notes_visite(self):
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Visite technique')
        return list(notes.values_list('body', flat=True))

    def test_create_date_passee_refusee(self):
        resp = self.api_bureau.post(
            URL, {'lead': self.lead.id, 'date_prevue': self.hier.isoformat()},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('date_prevue', resp.data)
        self.assertIn('passé', resp.data['date_prevue'][0])
        self.assertFalse(VisiteTerrain.objects.filter(lead=self.lead).exists())

    def test_create_commercial_inactif_refuse(self):
        resp = self.api_bureau.post(
            URL, {'lead': self.lead.id, 'date_prevue': self.hier.isoformat(),
                  'commercial': self.inactif.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('date_prevue', resp.data)
        self.assertIn('commercial', resp.data)
        self.assertFalse(VisiteTerrain.objects.filter(lead=self.lead).exists())

    def test_create_replanifie_sans_doublon(self):
        attente = self._en_attente()
        refus = self.api_bureau.post(
            URL, {'lead': self.lead.id, 'date_prevue': self.hier.isoformat(),
                  'commercial': self.inactif.id}, format='json')
        self.assertEqual(refus.status_code, 400, refus.data)
        resp = self.api_bureau.post(
            URL, {'lead': self.lead.id,
                  'date_prevue': self.demain.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['id'], attente.id)
        self.assertEqual(
            VisiteTerrain.objects.filter(lead=self.lead).count(), 1)
        attente.refresh_from_db()
        self.assertEqual(attente.date_prevue, self.demain)
        # Le rendez-vous déplacé garde son assigné.
        self.assertEqual(attente.commercial_id, self.commercial.id)

    def test_create_une_seule_note(self):
        self._en_attente()
        self.api_bureau.post(
            URL, {'lead': self.lead.id, 'date_prevue': self.hier.isoformat(),
                  'commercial': self.inactif.id}, format='json')
        self.api_bureau.post(
            URL, {'lead': self.lead.id,
                  'date_prevue': self.demain.isoformat()}, format='json')
        notes = self._notes_visite()
        self.assertEqual(len(notes), 1, notes)
        self.assertTrue(notes[0].startswith('Visite technique planifiée le'),
                        notes)

    def test_creation_datee_sans_attente_une_seule_note(self):
        resp = self.api_bureau.post(
            URL, {'lead': self.lead.id,
                  'date_prevue': self.demain.isoformat()}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        notes = self._notes_visite()
        self.assertEqual(len(notes), 1, notes)
        self.assertNotIn('Visite technique créée', notes[0])
        visite = VisiteTerrain.objects.get(pk=resp.data['id'])
        # Sans ``commercial`` dans le corps, le créateur est assigné.
        self.assertEqual(visite.commercial_id, self.bureau.id)
