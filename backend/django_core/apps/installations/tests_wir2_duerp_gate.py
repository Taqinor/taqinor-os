"""
WIR2 — Le gate DUERP (document unique) est câblé à la transition de POSE.

`qhse.services.exiger_document_unique` (QHSE22) était testé mais JAMAIS appelé
par `installations`. Cette suite prouve le câblage réel : entrer en pose
(montage physique = statut EN_COURS) REFUSE tant qu'aucun document unique
d'évaluation des risques (DUERP) validé non vide n'existe pour le chantier —
via la frontière services de qhse (aucun import de modèle cross-app).

Couvre :
  * un chantier avant pose SANS DUERP refuse la transition vers la pose, avec
    un message FRANÇAIS clair (« document unique … avant la pose ») ;
  * une fois le DUERP validé (≥ 1 ligne), la transition passe ;
  * le gate ne se déclenche QU'AU PASSAGE dans la pose : un chantier déjà en
    pose (EN_COURS) n'est pas re-gaté vers l'aval ;
  * un recul de statut n'est jamais bloqué ;
  * une société SANS étapes configurées garde le comportement historique
    (aucun blocage — interrupteur) ;
  * niveau API : PATCH statut vers la pose renvoie 400 sans DUERP, 200 après ;
    l'action `avancer-etape` applique le même gate.

Run :
    python manage.py test apps.installations.tests_wir2_duerp_gate -v2
"""
import itertools
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.services import (
    seed_stages, verifier_transition_statut,
)
from apps.qhse.models import EvaluationRisque, LigneEvaluationRisque

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'wir2-co-{n}', defaults={'nom': f'WIR2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'wir2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, statut=Installation.Statut.SIGNE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='WIR2',
        email=f'wir2-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-WIR2-{n}', client=client,
        statut=statut)


def valider_duerp(company, chantier_id):
    """Crée un DUERP validé NON VIDE (lève l'exigence QHSE22) pour un chantier."""
    ev = EvaluationRisque.objects.create(
        company=company, titre='DUERP', statut=EvaluationRisque.Statut.VALIDEE,
        reference=f'DUER-WIR2-{chantier_id}', chantier_id=chantier_id,
        date_evaluation=date(2026, 6, 1))
    LigneEvaluationRisque.objects.create(
        company=company, evaluation=ev, danger='Chute de hauteur',
        gravite=4, probabilite=3)
    return ev


def _est_raison_duerp(raisons):
    return any('document unique' in r.lower() or 'duerp' in r.lower()
               for r in raisons)


class DuerpPoseGateServiceTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def test_pose_refusee_sans_duerp(self):
        # Chantier signé (avant pose) ; aucun DUERP → entrer en pose (EN_COURS)
        # est refusé avec un message français explicite.
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.EN_COURS)
        self.assertTrue(raisons)
        self.assertTrue(_est_raison_duerp(raisons), raisons)
        self.assertTrue(any('pose' in r.lower() for r in raisons), raisons)

    def test_pose_autorisee_apres_duerp_valide(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        valider_duerp(self.company, inst.id)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.EN_COURS)
        self.assertEqual(raisons, [])

    def test_duerp_brouillon_ne_leve_pas_le_gate(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        ev = EvaluationRisque.objects.create(
            company=self.company, titre='DUERP', reference='DUER-BR',
            statut=EvaluationRisque.Statut.BROUILLON, chantier_id=inst.id,
            date_evaluation=date(2026, 6, 1))
        LigneEvaluationRisque.objects.create(
            company=self.company, evaluation=ev, danger='Chute',
            gravite=4, probabilite=3)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.EN_COURS)
        self.assertTrue(_est_raison_duerp(raisons), raisons)

    def test_duerp_autre_societe_ne_leve_pas_le_gate(self):
        # Le DUERP d'une AUTRE société ne débloque jamais notre chantier.
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        autre = make_company()
        valider_duerp(autre, inst.id)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.EN_COURS)
        self.assertTrue(_est_raison_duerp(raisons), raisons)

    def test_deja_en_pose_pas_de_re_gate_duerp(self):
        # Un chantier DÉJÀ en pose (EN_COURS) n'est pas re-gaté DUERP vers
        # l'aval — l'exigence porte sur l'ENTRÉE en pose.
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        inst.mes_production_test = None  # aucune fiche de recette
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        # La mise en service (IEC 62446-1) peut bloquer, mais JAMAIS le DUERP.
        self.assertFalse(_est_raison_duerp(raisons), raisons)

    def test_recul_de_statut_jamais_bloque(self):
        inst = make_installation(
            self.company, statut=Installation.Statut.EN_COURS)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.SIGNE)
        self.assertEqual(raisons, [])

    def test_societe_sans_etapes_configurees_pas_de_gate(self):
        autre = make_company()  # aucune étape amorcée
        inst = make_installation(autre, statut=Installation.Statut.SIGNE)
        raisons = verifier_transition_statut(
            inst, Installation.Statut.EN_COURS)
        self.assertEqual(raisons, [])


class DuerpPoseGateApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_patch_statut_pose_refuse_sans_duerp(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('statut', r.data)
        self.assertTrue(_est_raison_duerp(r.data['statut']), r.data)

    def test_patch_statut_pose_autorise_apres_duerp(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        valider_duerp(self.company, inst.id)
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, Installation.Statut.EN_COURS)

    def test_avancer_etape_pose_bloque_sans_duerp(self):
        inst = make_installation(self.company, statut=Installation.Statut.SIGNE)
        r = self.api.post(
            f'{BASE}/chantiers/{inst.id}/avancer-etape/',
            {'etape': 'montage_mecanique'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('raisons', r.data)
        self.assertTrue(_est_raison_duerp(r.data['raisons']), r.data)
