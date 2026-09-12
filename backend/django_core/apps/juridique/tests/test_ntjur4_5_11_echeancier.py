"""Prérequis NTJUR4/NTJUR5/NTJUR11 — échéancier procédural et honoraires.

Couvre les garanties dont NTJUR12 (budget) et NTJUR20 (timeline) dépendent :
date limite en jours OUVRÉS, report d'audience non destructif, référence de
note d'honoraires anti-collision.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.juridique import services
from apps.juridique.models import (
    Audience, CabinetAvocat, DelaiPrescription, DossierJuridique,
    MandatAvocat, NoteHonoraires,
)

from ._base import auth, make_admin, make_company

AUDIENCES = '/api/django/juridique/audiences/'
DELAIS = '/api/django/juridique/delais-prescription/'
NOTES = '/api/django/juridique/notes-honoraires/'


class EcheancierTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-ech-co', 'Juridique Ech')
        self.autre = make_company('jur-ech-autre', 'Juridique Ech Autre')
        self.admin = make_admin(self.company, 'jur-ech-admin')
        self.api = auth(self.admin)
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Procédure commerciale', date_ouverture=date(2026, 1, 5))
        self.cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Tazi')
        self.mandat = MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=self.cabinet,
            date_mandat=date(2026, 1, 6),
            montant_forfait=Decimal('40000'))

    # ── NTJUR4 — délais en jours ouvrés ──────────────────────────────────
    def test_date_limite_saute_week_ends_et_feries(self):
        """5 jours ouvrés depuis le vendredi 2026-01-09 : le week-end est
        sauté, donc la limite tombe APRÈS le 14 (5 jours calendaires)."""
        resp = self.api.post(DELAIS, {
            'dossier': self.dossier.id,
            'type_delai': DelaiPrescription.TypeDelai.DELAI_APPEL,
            'date_declenchement': '2026-01-09',
            'duree_jours': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        limite = DelaiPrescription.objects.get(pk=resp.data['id']).date_limite
        self.assertGreater(limite, date(2026, 1, 14))
        attendue = services.calculer_date_limite(
            self.company, date(2026, 1, 9), 5)
        self.assertEqual(limite, attendue)

    def test_date_limite_n_est_jamais_saisie_par_le_client(self):
        resp = self.api.post(DELAIS, {
            'dossier': self.dossier.id,
            'date_declenchement': '2026-02-02',
            'duree_jours': 3,
            'date_limite': '2030-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotEqual(
            DelaiPrescription.objects.get(pk=resp.data['id']).date_limite,
            date(2030, 1, 1))

    def test_expirants_ne_liste_que_la_fenetre_demandee(self):
        from django.utils import timezone
        from datetime import timedelta

        proche = DelaiPrescription.objects.create(
            company=self.company, dossier=self.dossier,
            date_declenchement=timezone.localdate(), duree_jours=5,
            date_limite=timezone.localdate() + timedelta(days=5))
        DelaiPrescription.objects.create(
            company=self.company, dossier=self.dossier,
            date_declenchement=timezone.localdate(), duree_jours=200,
            date_limite=timezone.localdate() + timedelta(days=200))
        resp = self.api.get(f'{DELAIS}expirants/?within=30')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([row['id'] for row in resp.data], [proche.id])

    def test_delai_d_un_dossier_d_une_autre_societe_refuse(self):
        etranger = DossierJuridique.objects.create(
            company=self.autre, reference='JUR-2026-9001',
            titre='Hors société', date_ouverture=date(2026, 1, 5))
        resp = self.api.post(DELAIS, {
            'dossier': etranger.id,
            'date_declenchement': '2026-02-02',
            'duree_jours': 3,
        }, format='json')
        # Le sérialiseur refuse explicitement (400 nommant « dossier ») —
        # jamais une création silencieuse dans la mauvaise société.
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('dossier', resp.data)
        self.assertFalse(DelaiPrescription.objects.exists())

    # ── NTJUR5 — report d'audience non destructif ────────────────────────
    def test_reporter_une_audience_cree_une_ligne_et_garde_l_historique(self):
        audience = Audience.objects.create(
            company=self.company, dossier=self.dossier,
            date_audience=date(2026, 3, 10))
        resp = self.api.post(f'{AUDIENCES}{audience.id}/reporter/',
                             {'date_audience': '2026-04-14',
                              'motif': 'Renvoi contradictoire'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        audience.refresh_from_db()
        self.assertEqual(audience.statut, Audience.Statut.REPORTEE)
        self.assertIn('Renvoi contradictoire', audience.resultat)
        nouvelle = Audience.objects.get(pk=resp.data['id'])
        self.assertEqual(nouvelle.reporte_depuis_id, audience.id)
        self.assertEqual(nouvelle.date_audience, date(2026, 4, 14))
        self.assertEqual(self.dossier.audiences.count(), 2)

    def test_une_audience_tenue_ne_se_reporte_plus(self):
        audience = Audience.objects.create(
            company=self.company, dossier=self.dossier,
            date_audience=date(2026, 3, 10),
            statut=Audience.Statut.TENUE)
        resp = self.api.post(f'{AUDIENCES}{audience.id}/reporter/',
                             {'date_audience': '2026-04-14'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(self.dossier.audiences.count(), 1)

    # ── NTJUR11 — notes d'honoraires ─────────────────────────────────────
    def test_reference_de_note_anti_collision(self):
        premiere = self.api.post(NOTES, {
            'mandat': self.mandat.id, 'date_facture': '2026-02-01',
            'montant_ht': '10000.00', 'montant_ttc': '12000.00',
        }, format='json')
        self.assertEqual(premiere.status_code, 201, premiere.data)
        seconde = self.api.post(NOTES, {
            'mandat': self.mandat.id, 'date_facture': '2026-02-02',
            'montant_ht': '5000.00', 'montant_ttc': '6000.00',
        }, format='json')
        NoteHonoraires.objects.filter(pk=seconde.data['id']).delete()
        troisieme = self.api.post(NOTES, {
            'mandat': self.mandat.id, 'date_facture': '2026-02-03',
            'montant_ht': '1000.00', 'montant_ttc': '1200.00',
        }, format='json')
        self.assertNotEqual(troisieme.data['reference'],
                            seconde.data['reference'])
        self.assertTrue(troisieme.data['reference'].startswith('NHJ-'))

    def test_statut_de_note_avance_par_action_seulement(self):
        cree = self.api.post(NOTES, {
            'mandat': self.mandat.id, 'date_facture': '2026-02-01',
            'montant_ht': '10000.00', 'montant_ttc': '12000.00',
        }, format='json')
        note_id = cree.data['id']
        self.api.patch(f'{NOTES}{note_id}/', {'statut': 'payee'},
                       format='json')
        self.assertEqual(
            NoteHonoraires.objects.get(pk=note_id).statut,
            NoteHonoraires.Statut.RECUE)
        self.api.post(f'{NOTES}{note_id}/valider/', {}, format='json')
        self.assertEqual(
            NoteHonoraires.objects.get(pk=note_id).statut,
            NoteHonoraires.Statut.VALIDEE)
