"""CAD10 — le motif de refus, FACULTATIF, dans le panneau « Refus ».

Avant : « Refus » posait l'étape « Décider la suite » sans demander pourquoi,
et le motif n'était exigé que bien plus tard, à la mise en « perdu » — quand
personne ne se souvient de ce que le client a dit.

Done : le refus SANS motif passe toujours ; le motif choisi atterrit sur la
ligne de chatter de la touche (jamais sur ``Lead.motif_perte`` : « perdu »
reste une décision humaine, MRY22). Contrat partagé : la réponse porte les
clés de l'exemple committé ``relance_etape_v2.json``.
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
from apps.crm.models import Lead, LeadActivity, MotifPerte, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad10'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD10 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        MotifPerte.objects.create(company=self.company, nom='Prix')
        MotifPerte.objects.create(company=self.company, nom='Ancien motif',
                                  archived=True)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Nadia', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661001001')
        quand = MERCREDI + datetime.timedelta(hours=1)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=4,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 3', due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date())
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _refus(self, **corps):
        corps.setdefault('outcome', 'refuse')
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/fait/',
            corps, format='json')

    def _ligne(self):
        return LeadActivity.objects.get(
            lead=self.lead, kind=LeadActivity.Kind.APPEL, outcome='refuse')


class MotifFacultatifTests(_Base):
    slug = 'cad10-base'

    def test_le_refus_sans_motif_passe_toujours(self):
        resp = self._refus()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('Motif de refus', self._ligne().body)

    def test_le_motif_choisi_atterrit_sur_la_ligne_de_chatter(self):
        resp = self._refus(motif_refus='prix')
        self.assertEqual(resp.status_code, 200, resp.data)
        # Le libellé EXACT de la liste, même saisi sans la casse.
        self.assertIn('Motif de refus : Prix.', self._ligne().body)

    def test_jamais_sur_le_motif_de_perte_du_lead(self):
        self._refus(motif_refus='Prix')
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)
        self.assertIn(self.lead.motif_perte, (None, ''))


class RefusNommeTests(_Base):
    slug = 'cad10-refus'

    def test_un_motif_hors_liste_nomme_le_champ(self):
        resp = self._refus(motif_refus='Trop cher selon le voisin')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('« Motif du refus »',
                      resp.data['erreurs']['motif_refus'])
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_un_motif_archive_est_refuse(self):
        resp = self._refus(motif_refus='Ancien motif')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('motif_refus', resp.data['erreurs'])

    def test_le_motif_d_une_autre_societe_est_refuse(self):
        autre = Company.objects.create(nom='Voisine', slug='cad10-voisine')
        MotifPerte.objects.create(company=autre, nom='Concurrent')
        resp = self._refus(motif_refus='Concurrent')
        self.assertEqual(resp.status_code, 400)

    def test_un_motif_sans_refus_est_refuse(self):
        resp = self._refus(outcome='non_joint', motif_refus='Prix')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('« Refus »', resp.data['erreurs']['motif_refus'])


class ContratPartageTests(_Base):
    slug = 'cad10-contrat'

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._refus(motif_refus='Prix')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(resp.data) - {'prochaine_touche'},
                         set(contrat['exemple']['results'][0]))
