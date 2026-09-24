"""CAD11 — raccourci « Numéro invalide / a bloqué » et ``est_junk`` visible.

Avant : un numéro mort épuisait les six tentatives du protocole — Répondeur
et Occupé retombaient sur « non joint » avec une note, ``LeadActivity``
n'a aucune valeur « numéro invalide », et ``MotifPerte.est_junk`` vivait au
niveau du lead, à trois écrans de la touche.

Done (côté serveur) : le lead ressort PERDU avec un motif ``est_junk`` quand
la proposition « perdu, motif junk » est acceptée, AUCUNE nouvelle valeur
d'énumération n'est ajoutée, et ``lead_est_junk`` est exposé sur la touche.
Contrat partagé : la touche porte exactement les clés de l'exemple committé
``relance_etape_v2.json`` (qui déclare ``lead_est_junk``).
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
from apps.crm.serializers import RelanceEtapeSerializer
from apps.parametres.models import CompanyProfile

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


class _Base(TestCase):
    slug = 'cad11'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD11 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        MotifPerte.objects.create(company=self.company,
                                  nom='Numéro invalide', est_junk=True)
        MotifPerte.objects.create(company=self.company, nom='Prix')
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Inconnu', stage=stages.NEW,
            owner=self.acteur, telephone='+212661001101')
        quand = MERCREDI + datetime.timedelta(minutes=3)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=MERCREDI)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _fait(self, **corps):
        corps.setdefault('outcome', 'non_joint')
        corps.setdefault('note', 'Numéro invalide')
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/fait/',
            corps, format='json')


class PerduJunkTests(_Base):
    slug = 'cad11-junk'

    def test_le_lead_ressort_perdu_avec_un_motif_junk(self):
        resp = self._fait(perdu_junk='numéro invalide')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.perdu)
        self.assertEqual(self.lead.motif_perte, 'Numéro invalide')
        self.assertTrue(MotifPerte.objects.get(
            company=self.company, nom=self.lead.motif_perte).est_junk)
        # Aucune touche ne reste ouverte, aucune n'est née (ni barreau
        # suivant, ni réveil) : un lead perdu n'a pas de suite.
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='reveil').exists())
        # La touche elle-même reste close « non joint » avec sa note typée.
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.outcome, 'non_joint')
        self.assertEqual(self.etape.note, 'Numéro invalide')

    def test_la_bascule_est_journalisee(self):
        self._fait(perdu_junk='Numéro invalide')
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='perdu').exists())

    def test_sans_la_proposition_la_cadence_continue(self):
        resp = self._fait()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def test_aucune_nouvelle_valeur_d_enumeration(self):
        self._fait(perdu_junk='Numéro invalide')
        valeurs = {k for k, _ in LeadActivity.OUTCOMES}
        self.assertEqual(valeurs, {'', 'joint', 'non_joint', 'rappel',
                                   'refuse', 'interesse', 'visite_acceptee'})
        self.assertTrue(set(LeadActivity.objects.filter(
            lead=self.lead).values_list('outcome', flat=True)) <= valeurs)


class RefusNommeTests(_Base):
    slug = 'cad11-refus'

    def test_un_motif_non_junk_est_refuse(self):
        resp = self._fait(perdu_junk='Prix')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('« Marquer perdu (junk) »',
                      resp.data['erreurs']['perdu_junk'])
        self.lead.refresh_from_db()
        self.assertFalse(self.lead.perdu)

    def test_hors_non_joint_la_proposition_est_refusee(self):
        resp = self._fait(outcome='joint', perdu_junk='Numéro invalide')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('perdu_junk', resp.data['erreurs'])


class EstJunkVisibleTests(_Base):
    slug = 'cad11-visible'

    def test_lead_est_junk_sur_la_touche(self):
        self.assertFalse(
            RelanceEtapeSerializer(self.etape).data['lead_est_junk'])
        self._fait(perdu_junk='Numéro invalide')
        self.etape.refresh_from_db()
        self.assertTrue(
            RelanceEtapeSerializer(self.etape).data['lead_est_junk'])

    def test_un_perdu_commercial_n_est_pas_junk(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            perdu=True, motif_perte='Prix')
        self.etape.refresh_from_db()
        self.assertFalse(
            RelanceEtapeSerializer(self.etape).data['lead_est_junk'])

    def test_la_forme_est_celle_du_contrat_partage(self):
        contrat = json.loads((CONTRATS / 'relance_etape_v2.json')
                             .read_text(encoding='utf-8'))
        exemple = contrat['exemple']['results'][0]
        self.assertIn('lead_est_junk', exemple)
        self.assertEqual(set(RelanceEtapeSerializer(self.etape).data),
                         set(exemple))
