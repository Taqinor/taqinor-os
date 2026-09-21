"""Tests NTCON22 — Rapport hebdomadaire d'avancement (PDF interne/MOE).

Couvre : agrégats sur une période donnée (lots vs planning, réserves créées/
levées de la période, RFI en cours, effectifs moyens du journal NTCON6),
endpoint PDF, refus d'une période invalide, et refus cross-tenant.
Aucun coût, aucun prix d'achat — document strictement interne.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier import selectors
from apps.btp_chantier.models import JournalChantier, Lot, ReserveChantier

from .helpers import auth, make_chantier, make_company, make_lot, make_user

RAPPORT = '/api/django/btp-chantier/chantiers/{}/rapport-avancement/'
PDF_FAKE = b'%PDF-1.4 test'


class RapportAvancementTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.au = timezone.localdate()
        self.du = self.au - timedelta(days=6)
        self.api = auth(self.user)

    def test_agregats_lots_et_retard(self):
        make_lot(
            self.co, self.chantier, nom='Gros-œuvre', ordre=1,
            date_fin_prevue=date(2026, 1, 1),
            date_fin_reelle=date(2026, 1, 11), statut=Lot.Statut.TERMINE)
        donnees = selectors.rapport_avancement(self.chantier, self.du, self.au)
        lot = donnees['lots'][0]
        self.assertEqual(lot['nom'], 'Gros-œuvre')
        self.assertEqual(lot['jours_retard'], 10)
        self.assertEqual(lot['date_fin_reelle'], date(2026, 1, 11))

    def test_reserves_de_la_periode(self):
        levee = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Levée',
            statut=ReserveChantier.Statut.LEVEE,
            date_levee=timezone.now())
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Ouverte',
            gravite=ReserveChantier.Gravite.BLOQUANTE)
        donnees = selectors.rapport_avancement(self.chantier, self.du, self.au)
        reserves = donnees['reserves']
        self.assertEqual(reserves['creees_periode'], 2)
        self.assertEqual(reserves['levees_periode'], 1)
        self.assertEqual(reserves['ouvertes'], 1)
        self.assertEqual(reserves['bloquantes_ouvertes'], 1)
        self.assertTrue(levee.pk)

    def test_effectif_moyen_sur_les_jours_renseignes(self):
        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=self.au,
            effectif_interne={'macon': 4}, effectif_sous_traitant={'1': 2})
        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date=self.au - timedelta(days=1),
            effectif_interne={'macon': 6}, effectif_sous_traitant={'1': 4})
        # Hors période : ne doit pas entrer dans la moyenne.
        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date=self.au - timedelta(days=30),
            effectif_interne={'macon': 100})
        donnees = selectors.rapport_avancement(self.chantier, self.du, self.au)
        effectif = donnees['effectif_moyen']
        self.assertEqual(effectif['jours_renseignes'], 2)
        self.assertEqual(effectif['moyenne_interne'], 5.0)
        self.assertEqual(effectif['moyenne_sous_traitant'], 3.0)

    def test_endpoint_renvoie_un_pdf(self):
        with patch('apps.btp_chantier.pdf.render_rapport_avancement_pdf',
                   return_value=PDF_FAKE) as rendu:
            resp = self.api.get(RAPPORT.format(self.chantier.id), {
                'du': str(self.du), 'au': str(self.au)})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        donnees = rendu.call_args[0][1]
        self.assertEqual(donnees['du'], self.du)
        self.assertEqual(donnees['au'], self.au)

    def test_periode_invalide_refusee(self):
        resp = self.api.get(
            RAPPORT.format(self.chantier.id), {'du': '01-2026-03'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('du', resp.data)

    def test_periode_inversee_refusee(self):
        resp = self.api.get(RAPPORT.format(self.chantier.id), {
            'du': '2026-03-01', 'au': '2026-02-01'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('du', resp.data)

    def test_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.get(RAPPORT.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
