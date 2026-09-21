"""NTJUR20 — timeline unifiée du dossier juridique.

Critère d'acceptation : « la timeline d'un dossier avec 3 audiences et 2 notes
d'honoraires affiche 5+ événements triés chronologiquement sans requête
supplémentaire côté frontend ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.juridique.models import (
    Audience, CabinetAvocat, DelaiPrescription, DossierJuridique,
    MandatAvocat, NoteHonoraires,
)

from ._base import auth, make_admin, make_company

URL = '/api/django/juridique/dossiers/'


class TimelineDossierTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-t20-co', 'Juridique T20')
        self.admin = make_admin(self.company, 'jur-t20-admin')
        self.api = auth(self.admin)
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Contentieux social', date_ouverture=date(2026, 1, 5))
        cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Berrada')
        self.mandat = MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=cabinet,
            date_mandat=date(2026, 1, 6), montant_forfait=Decimal('20000'))

    def test_trois_audiences_et_deux_notes_font_cinq_evenements_tries(self):
        for jour in (10, 20, 30):
            Audience.objects.create(
                company=self.company, dossier=self.dossier,
                date_audience=date(2026, 3, jour))
        for index, jour in enumerate((5, 15), start=1):
            NoteHonoraires.objects.create(
                company=self.company, mandat=self.mandat,
                reference=f'NHJ-202604-000{index}',
                date_facture=date(2026, 4, jour),
                montant_ht=Decimal('1000'), montant_ttc=Decimal('1200'))
        resp = self.api.get(f'{URL}{self.dossier.id}/timeline/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(len(resp.data), 5)
        horodatages = [e['horodatage'] for e in resp.data]
        self.assertEqual(horodatages, sorted(horodatages, reverse=True))
        types = {e['type'] for e in resp.data}
        self.assertIn('audience', types)
        self.assertIn('note_honoraires', types)

    def test_les_quatre_sources_apparaissent(self):
        Audience.objects.create(
            company=self.company, dossier=self.dossier,
            date_audience=date(2026, 3, 10))
        DelaiPrescription.objects.create(
            company=self.company, dossier=self.dossier,
            date_declenchement=date(2026, 2, 1), duree_jours=10,
            date_limite=date(2026, 2, 15))
        NoteHonoraires.objects.create(
            company=self.company, mandat=self.mandat,
            reference='NHJ-202604-0009', date_facture=date(2026, 4, 1),
            montant_ht=Decimal('900'), montant_ttc=Decimal('1080'))
        # Le chatter : une transition de statut l'alimente (records.Activity).
        self.api.post(f'{URL}{self.dossier.id}/changer-statut/',
                      {'statut': 'instruction', 'motif': 'Assignation reçue'},
                      format='json')
        resp = self.api.get(f'{URL}{self.dossier.id}/timeline/')
        types = {e['type'] for e in resp.data}
        self.assertEqual(
            types, {'chatter', 'audience', 'delai', 'note_honoraires'})

    def test_timeline_vide_pour_un_dossier_neuf(self):
        vierge = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0002',
            titre='Nouveau', date_ouverture=date(2026, 1, 5))
        resp = self.api.get(f'{URL}{vierge.id}/timeline/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])

    def test_timeline_d_un_dossier_d_une_autre_societe_est_404(self):
        autre = make_company('jur-t20-autre', 'Juridique T20 Autre')
        etranger = DossierJuridique.objects.create(
            company=autre, reference='JUR-2026-9001', titre='Hors société',
            date_ouverture=date(2026, 1, 5))
        resp = self.api.get(f'{URL}{etranger.id}/timeline/')
        self.assertEqual(resp.status_code, 404)
