"""
CH3 — Fiche de recette IEC 62446-1 (mise en service structurée).

Couvre :
  * un chantier enregistre un jeu d'essais IEC 62446-1 structuré (une fiche par
    chantier, idempotente) sans détruire les champs libres historiques ;
  * un relevé I-V calcule son écart Pmax et lève le drapeau de défaut ;
  * le gate « Mise en service » (CH2) REQUIERT une fiche PASSÉE : une fiche non
    conforme bloque, une fiche conforme (ou conforme avec réserves) débloque ;
  * repli historique : un chantier d'avant CH3 avec `mes_*` renseignés n'est
    pas bloqué rétroactivement ;
  * scope multi-société de l'API.

Run :
    python manage.py test apps.installations.tests_ch3_commissioning -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    CommissioningRecord, Installation,
)
from apps.installations.services import (
    compute_iv_ecart, ensure_commissioning_record, seed_stages,
    verifier_transition_statut,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ch3-co-{n}', defaults={'nom': f'CH3 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ch3-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, statut=Installation.Statut.EN_COURS):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CH3',
        email=f'ch3-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CH3-{n}', client=client,
        statut=statut)


class CommissioningRecordServiceTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_ensure_record_idempotent(self):
        inst = make_installation(self.company)
        r1 = ensure_commissioning_record(inst)
        r2 = ensure_commissioning_record(inst)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(
            CommissioningRecord.objects.filter(installation=inst).count(), 1)
        self.assertEqual(r1.company_id, self.company.id)

    def test_champs_libres_historiques_conserves(self):
        inst = make_installation(self.company)
        inst.mes_pv_notes = 'PV signé le 12/06'
        inst.mes_production_test = Decimal('5.4')
        inst.save(update_fields=['mes_pv_notes', 'mes_production_test'])
        ensure_commissioning_record(inst)
        inst.refresh_from_db()
        # La fiche structurée ne détruit rien.
        self.assertEqual(inst.mes_pv_notes, 'PV signé le 12/06')
        self.assertEqual(inst.mes_production_test, Decimal('5.4'))

    def test_iv_ecart_et_defaut(self):
        from apps.installations.models import CommissioningIVReading
        inst = make_installation(self.company)
        record = ensure_commissioning_record(inst)
        # Sous-performance de 10 % → défaut détecté.
        reading = CommissioningIVReading(
            record=record, company=self.company, string_label='S1',
            pmax_mesure_w=Decimal('900'), pmax_attendu_w=Decimal('1000'))
        compute_iv_ecart(reading)
        self.assertEqual(reading.ecart_pmax_pct, Decimal('-10.00'))
        self.assertTrue(reading.defaut_detecte)
        # Écart faible → pas de défaut.
        ok = CommissioningIVReading(
            record=record, company=self.company, string_label='S2',
            pmax_mesure_w=Decimal('990'), pmax_attendu_w=Decimal('1000'))
        compute_iv_ecart(ok)
        self.assertFalse(ok.defaut_detecte)


class CommissioningGateTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def test_fiche_non_conforme_bloque_le_gate(self):
        inst = make_installation(self.company)
        record = ensure_commissioning_record(inst)
        record.resultat = CommissioningRecord.Resultat.NON_CONFORME
        record.save(update_fields=['resultat'])
        inst.refresh_from_db()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertTrue(any('62446' in r for r in raisons), raisons)

    def test_fiche_conforme_debloque(self):
        inst = make_installation(self.company)
        record = ensure_commissioning_record(inst)
        record.resultat = CommissioningRecord.Resultat.CONFORME
        record.save(update_fields=['resultat'])
        inst.refresh_from_db()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertEqual(raisons, [])

    def test_fiche_reserves_debloque(self):
        inst = make_installation(self.company)
        record = ensure_commissioning_record(inst)
        record.resultat = CommissioningRecord.Resultat.RESERVES
        record.save(update_fields=['resultat'])
        inst.refresh_from_db()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertEqual(raisons, [])

    def test_repli_historique_ne_bloque_pas(self):
        # Aucune fiche structurée, mais des mes_* renseignés (chantier d'avant
        # CH3) → pas de blocage rétroactif.
        inst = make_installation(self.company)
        inst.mes_production_test = Decimal('6.0')
        inst.save(update_fields=['mes_production_test'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertEqual(raisons, [])


class CommissioningApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_ouvrir_et_lire_recette(self):
        inst = make_installation(self.company)
        r = self.api.post(f'{BASE}/chantiers/{inst.id}/recette/')
        self.assertEqual(r.status_code, 201, r.data)
        rid = r.data['id']
        r2 = self.api.get(f'{BASE}/chantiers/{inst.id}/recette/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['id'], rid)

    def test_maj_resultat_et_iv(self):
        inst = make_installation(self.company)
        rec = ensure_commissioning_record(inst, self.user)
        r = self.api.patch(
            f'{BASE}/recettes-commissioning/{rec.id}/',
            {'resultat': 'conforme', 'isolement_mohm': '2.5',
             'isolement_ok': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['passe'])
        r2 = self.api.post(
            f'{BASE}/recettes-commissioning/{rec.id}/ajouter-iv/',
            {'string_label': 'S1', 'pmax_mesure_w': '800',
             'pmax_attendu_w': '1000'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertTrue(r2.data['defaut_detecte'])
        self.assertEqual(Decimal(str(r2.data['ecart_pmax_pct'])),
                         Decimal('-20.00'))

    def test_scope_par_societe(self):
        autre = make_company()
        inst_autre = make_installation(autre)
        rec = ensure_commissioning_record(inst_autre)
        # Le demandeur ne voit jamais la fiche d'une autre société.
        r = self.api.get(f'{BASE}/recettes-commissioning/{rec.id}/')
        self.assertEqual(r.status_code, 404)
