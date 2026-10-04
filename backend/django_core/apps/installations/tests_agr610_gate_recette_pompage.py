"""AGR610 — gate « Mise en service » et pack de remise d'un chantier
AGRICOLE jugés sur la recette POMPAGE (AGR608), jamais sur IEC 62446-1.

Run :
    python manage.py test apps.installations.tests_agr610_gate_recette_pompage -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import (
    CommissioningRecord, Installation, RecettePompage, StageModele,
)
from apps.installations.services import (
    assemble_handover_pieces, seed_stages, stage_gate_status,
    verifier_transition_statut,
)

_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'agr610-co-{n}', defaults={'nom': f'AGR610 Co {n}'})
    return company


def make_installation(company, type_installation='agricole',
                      statut=Installation.Statut.EN_COURS):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='AGR610',
        email=f'agr610-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-AGR610-{n}', client=client,
        statut=statut, type_installation=type_installation)


class GateRecettePompageTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.mes = StageModele.objects.get(
            company=self.company, cle='mise_en_service')

    def test_agricole_sans_recette_bloque(self):
        inst = make_installation(self.company)
        st = stage_gate_status(inst, self.mes)
        self.assertFalse(st['satisfait'])
        self.assertIn('Recette pompage non enregistrée.', st['raisons'])
        raisons = verifier_transition_statut(
            inst, Installation.Statut.INSTALLE)
        self.assertTrue(
            any('Recette pompage non enregistrée' in r for r in raisons))

    def test_recette_conforme_passe(self):
        inst = make_installation(self.company)
        RecettePompage.objects.create(
            company=self.company, installation=inst, resultat='conforme')
        self.assertTrue(stage_gate_status(inst, self.mes)['satisfait'])
        self.assertEqual(verifier_transition_statut(
            inst, Installation.Statut.INSTALLE), [])

    def test_recette_non_conforme_bloque(self):
        inst = make_installation(self.company)
        RecettePompage.objects.create(
            company=self.company, installation=inst,
            resultat='non_conforme')
        st = stage_gate_status(inst, self.mes)
        self.assertFalse(st['satisfait'])
        self.assertTrue(
            any(r.startswith('Recette pompage non conforme')
                for r in st['raisons']))

    def test_iec_passee_seule_ne_suffit_pas_en_agricole(self):
        inst = make_installation(self.company)
        CommissioningRecord.objects.create(
            company=self.company, installation=inst, resultat='conforme')
        inst.mes_production_test = Decimal('5.0')
        inst.save(update_fields=['mes_production_test'])
        st = stage_gate_status(inst, self.mes)
        self.assertFalse(st['satisfait'])
        self.assertIn('Recette pompage non enregistrée.', st['raisons'])

    def test_residentiel_inchange(self):
        inst = make_installation(self.company, 'residentiel')
        st = stage_gate_status(inst, self.mes)
        self.assertIn(
            'Fiche de recette IEC 62446-1 non enregistrée.', st['raisons'])
        CommissioningRecord.objects.create(
            company=self.company, installation=inst, resultat='conforme')
        inst = Installation.objects.get(pk=inst.pk)
        self.assertTrue(stage_gate_status(inst, self.mes)['satisfait'])


class PackRecettePompageTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def _piece(self, inst):
        pieces = assemble_handover_pieces(inst)['pieces']
        return next(p for p in pieces if p['type'] == 'commissioning')

    def test_agricole_pv_recette_pompage(self):
        inst = make_installation(self.company)
        piece = self._piece(inst)
        self.assertEqual(piece['libelle'], 'Procès-verbal de recette pompage')
        self.assertTrue(piece['obligatoire'])
        self.assertFalse(piece['present'])
        RecettePompage.objects.create(
            company=self.company, installation=inst, resultat='reserves')
        piece = self._piece(inst)
        self.assertTrue(piece['present'])
        self.assertEqual(piece['reference'], 'Conforme avec réserves')

    def test_residentiel_certificat_iec(self):
        inst = make_installation(self.company, 'residentiel')
        piece = self._piece(inst)
        self.assertEqual(piece['libelle'], 'Certificat de recette IEC 62446-1')
        self.assertFalse(piece['present'])
