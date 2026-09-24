"""CAD156 — « Je vous rappelle jeudi à 18 h » : l'heure promise a un champ.

Avant : ``relance_date`` est une DATE et le journal d'appel (``CallLogPopover``)
ne PATCHait qu'elle — l'heure convenue au téléphone se perdait, alors que le
report d'une touche, lui, accepte une heure.

Done : ``relance_heure`` voyage avec ``relance_date`` dans le MÊME PATCH et
emprunte le chemin du report de touche (``reporter_prochaine_touche``) : l'heure
saisie se retrouve sur la touche reportée. Un seul système de rappel (MRY10),
aucune migration. Contrat partagé : ``lead_relance_heure.json`` (le corps
envoyé, les clés relues de la réponse, le refus nommé).
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 23/09/2026, 10 h à Casablanca ; le rappel promis : jeudi 18 h.
MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class HeureDeRappelTests(TestCase):

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD156 Solaire',
                                              slug='cad156')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad156-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661112233')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=4,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 3',
            due_at=MERCREDI, due_date=MERCREDI.date(),
            cadence_depart=MERCREDI)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.contrat = _contrat('lead_relance_heure')

    def _patch(self, corps):
        return self.api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                              corps, format='json')

    def test_l_heure_saisie_se_retrouve_sur_la_touche_reportee(self):
        corps = self.contrat['corps']
        resp = self._patch(corps)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        local = self.etape.due_at.astimezone(horaires.CASABLANCA)
        self.assertEqual(local.date().isoformat(), corps['relance_date'])
        self.assertEqual(local.strftime('%H:%M'), corps['relance_heure'])
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        # La réponse porte les clés que l'écran relit (contrat).
        self.assertTrue(set(self.contrat['exemple']) <= set(resp.data))
        self.assertEqual(resp.data['relance_date'], corps['relance_date'])

    def test_une_heure_seule_reporte_meme_si_la_date_ne_change_pas(self):
        jeudi = self.contrat['corps']['relance_date']
        self._patch({'relance_date': jeudi})
        self.etape.refresh_from_db()
        self.assertNotEqual(
            self.etape.due_at.astimezone(horaires.CASABLANCA).strftime(
                '%H:%M'), '18:00')
        self._patch({'relance_date': jeudi, 'relance_heure': '18:00'})
        self.etape.refresh_from_db()
        self.assertEqual(
            self.etape.due_at.astimezone(horaires.CASABLANCA).strftime(
                '%H:%M'), '18:00')

    def test_une_heure_illisible_est_refusee_avant_toute_ecriture(self):
        avant = self.etape.due_at
        resp = self._patch({'relance_date': '2026-09-24',
                            'relance_heure': '18h'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('relance_heure', resp.data)
        self.assertIn('« 18h »', str(resp.data['relance_heure']))
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.relance_date)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.due_at, avant)

    def test_une_heure_sans_date_est_refusee_en_nommant_le_champ(self):
        resp = self._patch({'relance_heure': '18:00'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('relance_heure', resp.data)

    def test_sans_heure_le_comportement_historique_est_inchange(self):
        resp = self._patch({'relance_date': '2026-09-24'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(
            self.etape.due_at.astimezone(horaires.CASABLANCA).date(),
            datetime.date(2026, 9, 24))
