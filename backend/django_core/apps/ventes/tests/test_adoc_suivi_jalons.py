"""ADOC121 — jalons du suivi public dérivés du statut réel (D-ADOC-3).

« Installation » n'est plus « Fait » à la signature ; une ligne annulée ou
rejetée ne coche rien ; ``date`` porte une date ISO, jamais un statut. Les
jalons « Matériel » / « Installation » sont lus des jalons portail
SYNCHRONISÉS du chantier (phases ``appro`` / ``pose``), la même ligne que
« Mes chantiers ». Contrat : ``contract_samples/suivi_public.json`` (ADOC112).
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.services import create_installation_from_devis
from apps.portail import selectors as portail_selectors
from apps.portail.services import upsert_jalon_chantier
from apps.ventes.models import (
    BonCommande, Devis, Facture, Paiement, ShareLink,
)
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'suivi_public.json')
CLES = ['accepte', 'acompte', 'materiel', 'installation', 'facture']


class SuiviJalonsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADOC121 Co')
        self.user = User.objects.create_user(
            username='adoc121', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADOC121',
            telephone='+212600000121')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ADOC12101',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            date_acceptation=datetime.date(2026, 8, 26),
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()
        self.chantier, _ = create_installation_from_devis(
            self.devis, self.user, self.company)

    def _get(self):
        resp = self.api.get(f'/api/django/ventes/suivi/{self.link.token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp, {m['key']: m for m in resp.data['milestones']}

    def _jalon(self, cle, jour=datetime.date(2026, 10, 2)):
        upsert_jalon_chantier(
            self.company, self.chantier.id, cle, cle.title(),
            atteint=True, date_jalon=jour)

    def _facture(self, statut):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A{statut[:3]}1',
            client=self.client_obj, devis=self.devis, statut=statut,
            taux_tva=Decimal('20'))

    def test_installation_pas_faite_a_la_signature(self):
        self.assertIsNotNone(self.chantier)
        _, ms = self._get()
        self.assertTrue(ms['accepte']['done'])
        self.assertFalse(ms['installation']['done'])
        self.assertFalse(ms['materiel']['done'])
        self.assertIsNone(ms['installation']['date'])

    def test_appro_puis_pose_cochent_avec_la_date_du_jalon(self):
        self._jalon('appro', datetime.date(2026, 9, 15))
        _, ms = self._get()
        self.assertTrue(ms['materiel']['done'])
        self.assertEqual(ms['materiel']['date'], '2026-09-15')
        self.assertFalse(ms['installation']['done'])
        self._jalon('pose')
        _, ms = self._get()
        self.assertTrue(ms['installation']['done'])
        self.assertEqual(ms['installation']['date'], '2026-10-02')
        # relecture : même verdict (lecture pure)
        _, ms2 = self._get()
        self.assertEqual(ms, ms2)

    def test_lignes_annulees_ou_rejetees_ne_cochent_rien(self):
        f = self._facture(Facture.Statut.EMISE)
        Paiement.objects.create(
            company=self.company, facture=f, montant=Decimal('1000'),
            date_paiement=timezone.localdate(), mode=Paiement.Mode.VIREMENT,
            statut=Paiement.Statut.REJETE)
        f.statut = Facture.Statut.ANNULEE
        f.save(update_fields=['statut'])
        BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-ADOC12101',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.ANNULE)
        _, ms = self._get()
        self.assertFalse(ms['acompte']['done'])
        self.assertFalse(ms['facture']['done'])
        self.assertFalse(ms['materiel']['done'])
        # brouillon : pas encore facturé
        f.statut = Facture.Statut.BROUILLON
        f.save(update_fields=['statut'])
        _, ms = self._get()
        self.assertFalse(ms['facture']['done'])
        # émise : facturé
        f.statut = Facture.Statut.EMISE
        f.save(update_fields=['statut'])
        _, ms = self._get()
        self.assertTrue(ms['facture']['done'])

    def test_chantier_annule_ne_coche_ni_materiel_ni_installation(self):
        self._jalon('appro')
        self._jalon('pose')
        self.chantier.annule = True
        self.chantier.save(update_fields=['annule'])
        _, ms = self._get()
        self.assertFalse(ms['materiel']['done'])
        self.assertFalse(ms['installation']['done'])

    def test_dates_iso_jamais_statut(self):
        self._jalon('pose')
        _, ms = self._get()
        for m in ms.values():
            if m['date'] is not None:
                datetime.date.fromisoformat(m['date'])
            self.assertNotIn(m['date'], ('signe', 'a_planifier'))

    def test_parite_suivi_portail_meme_jalon(self):
        self._jalon('pose', datetime.date(2026, 10, 2))
        _, ms = self._get()
        ligne = next(
            j for j in portail_selectors.jalons_du_chantier(
                self.company, self.chantier.id)
            if j.cle_phase == 'pose')
        self.assertEqual(ms['installation']['done'], ligne.atteint)
        self.assertEqual(ms['installation']['date'],
                         ligne.date_jalon.isoformat())

    def test_reponse_conforme_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        resp, ms = self._get()
        exemple = contrat['exemple']
        self.assertEqual(list(ms), CLES)
        self.assertEqual([m['key'] for m in exemple['milestones']], CLES)
        for cle in CLES:
            self.assertEqual(set(ms[cle]),
                             set(exemple['milestones'][CLES.index(cle)]))
        self.assertIn('reference', resp.data)
        self.assertIn('generated_at', resp.data)
