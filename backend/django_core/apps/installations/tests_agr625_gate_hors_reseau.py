"""AGR625 — chantier HORS RÉSEAU (régime ``declaration_hors_reseau``, loi
82-21 art. 3, posé par AGR602) : gate 82-21 CONSULTATIF, étape PTO « sans
objet », pièce ``dossier_8221`` facultative.

Run :
    python manage.py test apps.installations.tests_agr625_gate_hors_reseau -v2
"""
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, StageModele
from apps.installations.services import (
    AVERTISSEMENT_DECLARATION_HORS_RESEAU, REFERENCE_DECLARATION_HORS_RESEAU,
    assemble_handover_pieces, seed_stages, stage_gate_status,
    verifier_transition_statut,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'agr625-co-{n}', defaults={'nom': f'AGR625 Co {n}'})
    return company


def make_installation(company, hors_reseau=True,
                      statut=Installation.Statut.SIGNE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='AGR625',
        email=f'agr625-{company.id}-{n}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=f'CHT-AGR625-{n}', client=client,
        statut=statut, type_installation=(
            'agricole' if hors_reseau else 'residentiel'))
    if hors_reseau:
        inst.regime_8221 = Installation.Regime8221.DECLARATION_HORS_RESEAU
        inst.raccordement_reseau = (
            Installation.RaccordementReseau.HORS_RESEAU)
    else:
        inst.regime_8221 = Installation.Regime8221.DECLARATION_BT
    inst.dossier_statut = Installation.DossierStatut.A_DEPOSER
    inst.save()
    return inst


class GateHorsReseauTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def _stage(self, cle):
        return StageModele.objects.get(company=self.company, cle=cle)

    def test_autorisations_non_bloquee_avec_avertissement(self):
        inst = make_installation(self.company)
        st = stage_gate_status(inst, self._stage('autorisations'))
        self.assertTrue(st['bloquant'])
        self.assertTrue(st['satisfait'])
        self.assertEqual(st['raisons'], [])
        self.assertEqual(
            st['avertissements'], [AVERTISSEMENT_DECLARATION_HORS_RESEAU])
        # Le passage franchit « autorisations » : jamais bloqué par le
        # dossier (l'avertissement n'est pas une raison).
        raisons = verifier_transition_statut(
            inst, Installation.Statut.MATERIEL_COMMANDE)
        self.assertFalse(any('82-21' in r for r in raisons), raisons)
        self.assertFalse(any('art. 3' in r for r in raisons), raisons)

    def test_inspection_raccordement_sans_objet(self):
        inst = make_installation(self.company)
        st = stage_gate_status(inst, self._stage('inspection_raccordement'))
        self.assertTrue(st['sans_objet'])
        self.assertTrue(st['satisfait'])
        self.assertEqual(st['raisons'], [])
        # Même rendue bloquante par le Directeur, elle n'est jamais exigée.
        StageModele.objects.filter(
            company=self.company, cle='inspection_raccordement').update(
            bloquant=True, exige_dossier=True)
        st = stage_gate_status(inst, self._stage('inspection_raccordement'))
        self.assertTrue(st['satisfait'])

    def test_piece_dossier_8221_facultative(self):
        inst = make_installation(self.company)
        pieces = assemble_handover_pieces(inst)['pieces']
        dossier = next(p for p in pieces if p['type'] == 'dossier_8221')
        self.assertFalse(dossier['obligatoire'])
        self.assertEqual(
            dossier['reference'], REFERENCE_DECLARATION_HORS_RESEAU)
        self.assertFalse(dossier['present'])

    def test_residentiel_inchange(self):
        inst = make_installation(self.company, hors_reseau=False)
        st = stage_gate_status(inst, self._stage('autorisations'))
        self.assertFalse(st['satisfait'])
        self.assertTrue(any('82-21' in r for r in st['raisons']))
        self.assertEqual(st['avertissements'], [])
        pto = stage_gate_status(inst, self._stage('inspection_raccordement'))
        self.assertFalse(pto['sans_objet'])
        pieces = assemble_handover_pieces(inst)['pieces']
        dossier = next(p for p in pieces if p['type'] == 'dossier_8221')
        self.assertTrue(dossier['obligatoire'])
        self.assertEqual(dossier['reference'], 'À déposer')


class EtapesHorsReseauApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.user = User.objects.create_user(
            username=f'agr625-{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_etapes_hors_reseau_et_contrat(self):
        inst = make_installation(self.company)
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/etapes/')
        self.assertEqual(r.status_code, 200, r.data)
        etapes = {e['cle']: e for e in r.data['etapes']}
        self.assertTrue(etapes['inspection_raccordement']['sans_objet'])
        self.assertEqual(
            etapes['autorisations']['avertissements'],
            [AVERTISSEMENT_DECLARATION_HORS_RESEAU])
        self.assertTrue(etapes['autorisations']['satisfait'])
        # Le test AFFIRME le contrat partagé (mêmes clés, mêmes types).
        exemple = _contrat('parcours_etapes_chantier')['exemple']
        self.assertEqual(set(r.data), set(exemple))
        for ex in exemple['etapes']:
            servi = etapes[ex['cle']]
            self.assertEqual(set(servi), set(ex))
            for cle, val in ex.items():
                self.assertIsInstance(
                    servi[cle], type(val), f'{ex["cle"]}.{cle}')
            self.assertEqual(servi['sans_objet'], ex['sans_objet'])
            self.assertEqual(servi['avertissements'], ex['avertissements'])
