"""PARAM-CADENCE P2 — la touche porte sa clé et la visite du lead.

Contrat ``contract_samples/relance_etape_v2.json`` (champs ADDITIFS du
25/09/2026) : ``cle`` (la clé stable du barreau paramétré, lecture seule —
l'écran la lit AVANT le libellé, qu'une société peut renommer),
``visite_prevue_le`` (``Lead.visite_prevue_le``), ``visite_id`` et
``visite_retour_disponible`` (la visite terrain la plus récente du lead, lue
par le sélecteur de l'app visites).

Coût : aucune requête de visite pour un lead sans visite prévue ni effectuée ;
une lecture PAR LEAD (jamais par touche) sinon.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.visites.models import VisiteTerrain

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
URL = '/api/django/crm/relance-etapes/'
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'relance_etape_v2.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'pcad-re'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _lead(self, nom, **champs):
        return Lead.objects.create(
            company=self.company, nom=nom, stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000999', **champs)

    def _touche(self, lead, *, libelle='Appel', cle=''):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='generique', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle=libelle, cle=cle,
            due_at=GEL, due_date=GEL.date())

    def _file(self):
        resp = self.api.get(URL, {'scope': 'today'})
        self.assertEqual(resp.status_code, 200, resp.data)
        return {ligne['id']: ligne for ligne in resp.data['results']}


class FormeTests(_Base):
    slug = 'pcad-re-forme'

    def test_la_touche_a_la_forme_du_contrat(self):
        touche = self._touche(self._lead('Forme'))
        ligne = self._file()[touche.pk]
        self.assertEqual(set(ligne), set(CONTRAT['exemple']['results'][0]))

    def test_la_cle_est_servie_et_jamais_ecrite(self):
        touche = self._touche(self._lead('Cle'), libelle='Faire le devis',
                              cle='devis')
        self.assertEqual(self._file()[touche.pk]['cle'], 'devis')
        self.assertIn('cle', _serializer_read_only())

    def test_une_touche_sans_visite(self):
        touche = self._touche(self._lead('Sans'))
        ligne = self._file()[touche.pk]
        self.assertIsNone(ligne['visite_prevue_le'])
        self.assertIsNone(ligne['visite_id'])
        self.assertIs(ligne['visite_retour_disponible'], False)


class VisiteDuLeadTests(_Base):
    slug = 'pcad-re-visite'

    def test_la_visite_et_son_retour_sont_servis(self):
        lead = self._lead('Visite', visite_prevue_le=datetime.date(2026, 9, 22),
                          visite_effectuee=True)
        ancienne = VisiteTerrain.objects.create(
            company=self.company, lead=lead,
            date_prevue=datetime.date(2026, 9, 1), notes='')
        recente = VisiteTerrain.objects.create(
            company=self.company, lead=lead,
            date_prevue=datetime.date(2026, 9, 22),
            notes='Tableau saturé, accès par le garage.')
        touche = self._touche(lead)

        ligne = self._file()[touche.pk]

        self.assertEqual(ligne['visite_prevue_le'], '2026-09-22')
        self.assertEqual(ligne['visite_id'], recente.pk)
        self.assertNotEqual(ligne['visite_id'], ancienne.pk)
        self.assertIs(ligne['visite_retour_disponible'], True)

    def test_une_visite_sans_retour_ecrit(self):
        lead = self._lead('Muette', visite_prevue_le=datetime.date(2026, 9, 28))
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=lead,
            date_prevue=datetime.date(2026, 9, 28), notes='')
        touche = self._touche(lead)
        ligne = self._file()[touche.pk]
        self.assertEqual(ligne['visite_id'], visite.pk)
        self.assertIs(ligne['visite_retour_disponible'], False)

    def test_la_visite_d_une_autre_societe_ne_sort_jamais(self):
        autre = Company.objects.create(nom='Autre', slug=f'{self.slug}-b')
        lead = self._lead('Borne', visite_prevue_le=datetime.date(2026, 9, 28))
        # Une visite rattachée au lead mais tenue par une AUTRE société : le
        # sélecteur borne par la société du lead.
        VisiteTerrain.objects.create(
            company=autre, lead=lead,
            date_prevue=datetime.date(2026, 9, 28), notes='Chez le voisin.')
        touche = self._touche(lead)
        ligne = self._file()[touche.pk]
        self.assertIsNone(ligne['visite_id'])


class CoutTests(_Base):
    """Jamais une requête de visite PAR TOUCHE."""

    slug = 'pcad-re-cout'

    def _cout(self):
        with CaptureQueriesContext(connection) as ctx:
            self.api.get(URL, {'scope': 'today'})
        return len(ctx)

    def test_des_leads_sans_visite_ne_coutent_rien_de_plus(self):
        self._touche(self._lead('Un'))
        un = self._cout()
        for i in range(4):
            self._touche(self._lead(f'Autre {i}'))
        # Signature d'un N+1 : +1 requête PAR lead ajouté. Toléré : +1
        # constant (premier accès paresseux), jamais linéaire.
        self.assertLessEqual(self._cout() - un, 1)

    def test_deux_touches_du_meme_lead_lisent_la_visite_une_fois(self):
        lead = self._lead('Deux', visite_prevue_le=datetime.date(2026, 9, 28))
        VisiteTerrain.objects.create(
            company=self.company, lead=lead,
            date_prevue=datetime.date(2026, 9, 28), notes='x')
        self._touche(lead)
        une = self._cout()
        self._touche(lead, libelle='Seconde touche')
        self.assertLessEqual(self._cout() - une, 1)


def _serializer_read_only():
    from apps.crm.serializers import RelanceEtapeSerializer
    return set(RelanceEtapeSerializer.Meta.read_only_fields)
