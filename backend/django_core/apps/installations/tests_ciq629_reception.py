"""CIQ629 — réception provisoire puis définitive : la définitive n'est
prononcée qu'une fois toutes les réserves levées.
"""
import datetime
import json
from pathlib import Path

from django.test import TestCase

from apps.installations.models import InstallationActivity, Reserve
from apps.installations.selectors import reception_chantier
from apps.installations.services import (
    creer_reserve_chantier, lever_reserve_chantier,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_installation, make_user,
)
from apps.parametres.models import CompanyProfile

_CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
            / 'recette_ci.json')


class ReceptionDefinitiveTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.inst.date_reception = datetime.date(2026, 10, 13)
        self.inst.save(update_fields=['date_reception'])
        self.url = f'{BASE}/chantiers/{self.inst.id}/reception-definitive/'

    def test_delai_hors_calendrier_pas_de_500(self):
        """ERR-ENF11 (cron 41296444614) : « year 77984948 is out of range »."""
        profil = CompanyProfile.get(self.company)
        profil.delai_reception_definitive_mois = 2147483647
        profil.save(update_fields=['delai_reception_definitive_mois'])
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['date_definitive_prevue'])

    def test_reserve_ouverte_definitive_refusee(self):
        creer_reserve_chantier(self.inst, self.user, description='Coffret AC',
                               origine='reception')
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)  # ERR-ENF11 : refus d'état = 409
        self.assertIn('Coffret AC', r.data['detail'])
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception_definitive)

    def test_avant_provisoire_refusee(self):
        self.inst.date_reception = None
        self.inst.save(update_fields=['date_reception'])
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 409)  # ERR-ENF11 : refus d'état = 409
        self.assertIn('provisoire', r.data['detail'])

    def _reserve_avec_ticket(self, description):
        from apps.sav.services import create_corrective_ticket
        reserve = creer_reserve_chantier(
            self.inst, self.user, description=description, origine='reception')
        reserve.ticket = create_corrective_ticket(
            company=self.company, client=self.inst.client,
            installation=self.inst, description=description,
            created_by=self.user)
        reserve.save(update_fields=['ticket'])
        return reserve

    def test_reserve_et_ticket_se_ferment_ensemble(self):
        """ACSV66 — résoudre le ticket lève la réserve ; lever la réserve
        résout le ticket (transition système) ; ticket déjà clos : rien."""
        from apps.sav.models import Ticket
        r1 = self._reserve_avec_ticket('Onduleur mal fixé A')
        r2 = self._reserve_avec_ticket('Onduleur mal fixé B')
        # Machine d'états YDOCF1 : nouveau → en_cours → resolu → cloture.
        for action in ('demarrer', 'resoudre', 'cloturer'):
            rep = self.api.post(
                f'/api/django/sav/tickets/{r1.ticket_id}/{action}/', {}, format='json')
            self.assertEqual(rep.status_code, 200, rep.data)
        r1.refresh_from_db()
        self.assertEqual(r1.statut, Reserve.Statut.RESOLUE)
        self.assertEqual(r1.levee_par, self.user)
        self.assertIn(r1.ticket.reference, r1.resolution)
        rep = self.api.post(f'{BASE}/chantiers/{self.inst.id}/reserves/{r2.id}/lever/', {}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        r2.ticket.refresh_from_db()
        self.assertEqual(r2.ticket.statut, Ticket.Statut.RESOLU)
        self.assertEqual(self.api.post(self.url, {}, format='json').status_code, 200)

    def test_toutes_levees_date_posee_et_journalisee(self):
        reserve = creer_reserve_chantier(
            self.inst, self.user, description='Coffret AC',
            origine='reception')
        lever_reserve_chantier(reserve, self.user)
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertIsNotNone(self.inst.date_reception_definitive)
        self.assertEqual(r.data['date_reception_definitive'],
                         self.inst.date_reception_definitive.isoformat())
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst,
            body__startswith='Réception définitive').exists())
        self.assertEqual(Reserve.objects.filter(statut='ouverte').count(), 0)

    def test_delai_douze_mois_date_prevue(self):
        profil = CompanyProfile.get(self.company)
        profil.delai_reception_definitive_mois = 12
        profil.save()
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertEqual(bloc['date_definitive_prevue'], '2027-10-13')

    def test_avant_date_prevue_ou_annule_409_derogation_directeur(self):
        """ACSV35 (C-ACSV-045, D-ACSV-1) — délai 12 mois, provisoire d'hier :
        409 pour un Responsable, 403 s'il donne un motif ; un Directeur avec
        motif la prononce (note) ; chantier annulé : 409. ROUGE AVANT : 200."""
        from django.utils import timezone

        from apps.installations.models import Installation, InstallationActivity
        profil = CompanyProfile.get(self.company)
        profil.delai_reception_definitive_mois = 12
        profil.save()
        hier = timezone.localdate() - datetime.timedelta(days=1)
        Installation.objects.filter(pk=self.inst.pk).update(date_reception=hier)
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Réception définitive possible à partir du', r.data['detail'])
        r = self.api.post(self.url, {'motif_derogation': 'client pressé'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception_definitive)
        directeur = make_user(self.company, role='admin')
        r = auth(directeur).post(self.url, {'motif_derogation': 'client pressé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertIsNotNone(self.inst.date_reception_definitive)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__contains='par dérogation Directeur').exists())
        Installation.objects.filter(pk=self.inst.pk).update(annule=True, date_reception_definitive=None)
        r = self.api.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('chantier annulé', r.data['detail'])

    def test_delai_non_saisi_date_prevue_null(self):
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertIsNone(bloc['date_definitive_prevue'])
        self.assertTrue(bloc['definitive_possible'])

    def test_autre_societe_404(self):
        autre = make_company()
        inst_autre = make_installation(autre)
        r = self.api.post(
            f'{BASE}/chantiers/{inst_autre.id}/reception-definitive/', {},
            format='json')
        self.assertEqual(r.status_code, 404)
        self.assertIsNone(reception_chantier(self.company, inst_autre.id))

    def test_patch_generique_ne_pose_pas_la_definitive(self):
        self.api.patch(f'{BASE}/chantiers/{self.inst.id}/',
                       {'date_reception_definitive': '2027-01-01'},
                       format='json')
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception_definitive)

    def test_bloc_conforme_au_contrat(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['reception']
        bloc = reception_chantier(self.company, self.inst.id)
        self.assertEqual(set(bloc), set(modele))
