"""CAL245 — le bloc « calepinage retenu » sur le détail chantier (endpoint).

Couvre :
  * ``InstallationSerializer.calepinage`` sert le bloc
    ``{calepinage_id, kwc, nb_modules, planche_url, plan_pose_url}`` pour un
    chantier issu d'un calepinage RETENU, ``None`` sinon (contrat
    ``apps/installations/contract_samples/calepinage_retenu.json``, PACT10) ;
  * aucune migration n'accompagne cette lane : ``Installation`` ne gagne
    aucun champ calepinage (règle fondateur 12/09/2026).

Run :
    python manage.py test apps.installations.tests_cal245_bloc_calepinage -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.serializers import InstallationSerializer
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(nom=f'CAL245 Co {n}', slug=f'cal245-co-{n}')


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CAL245',
        email=f'cal245-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CAL245-{n}', client=client,
        taux_tva=Decimal('20'))


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CAL245-{n}', client=client,
        devis=devis)


class TestBlocCalepinageSerializer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def test_chantier_sans_devis_rend_null(self):
        chantier = make_installation(self.company, self.client_obj)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_avec_devis_sans_calepinage_rend_null(self):
        chantier = make_installation(self.company, self.client_obj, self.devis)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_issu_d_un_calepinage_rend_le_bloc(self):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis)
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True,
                resultat={'pose': {'kwc': 8.64, 'total_modules': 12}})
        chantier = make_installation(self.company, self.client_obj, self.devis)

        data = InstallationSerializer(chantier).data
        bloc = data['calepinage']
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['calepinage_id'], calepinage.id)
        self.assertEqual(bloc['kwc'], 8.64)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['planche_url'], f'/calepinage/{calepinage.id}')
        self.assertEqual(
            bloc['plan_pose_url'], f'/ventes/devis/{self.devis.id}/3d')

    def test_installation_ne_gagne_aucun_champ_calepinage(self):
        """Aucune migration chantier n'accompagne CAL245 : le bloc est un
        SerializerMethodField calculé, jamais une colonne persistée."""
        noms_champs = {f.name for f in Installation._meta.get_fields()}
        for interdit in ('calepinage', 'calepinage_id', 'calepinage_retenu'):
            self.assertNotIn(interdit, noms_champs)
