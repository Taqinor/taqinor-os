"""NTEXT27 — automatisation : déclencheur sur objet custom.

``TriggerType.CUSTOM_RECORD_SAVED`` (``trigger_config={'object_code': 'x'}``)
se déclenche à la création/modification d'un ``CustomRecord`` — filtré sur
l'objet précis, jamais les autres objets personnalisés de la société.
"""
import itertools

from django.test import TestCase

from authentication.models import Company
from apps.customfields.models import CustomObjectDef, CustomRecord

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(
        slug=f'ntext27-co-{n}', nom=f'NTEXT27 Co {n}')


class CustomRecordTriggerTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.objet_a = CustomObjectDef.objects.create(
            company=self.co, code='suivi-qualite', libelle='Suivi qualité')
        self.objet_b = CustomObjectDef.objects.create(
            company=self.co, code='visiteurs', libelle='Visiteurs')

    def _rule(self, object_code=''):
        cfg = {'object_code': object_code} if object_code else {}
        return AutomationRule.objects.create(
            company=self.co, nom='Sur objet custom',
            trigger_type=TriggerType.CUSTOM_RECORD_SAVED, trigger_config=cfg,
            action_type=ActionType.CREATE_ACTIVITY,
            action_config={'body': 'déclenché'})

    def _runs(self):
        return AutomationRun.objects.filter(company=self.co)

    def test_creation_dun_enregistrement_de_lobjet_cible_declenche(self):
        self._rule(object_code='suivi-qualite')
        CustomRecord.objects.create(
            company=self.co, objet=self.objet_a, data={'titre': 'x'})
        # Le déclenchement TIRE bien (un run est journalisé) ; l'action
        # CREATE_ACTIVITY choisie ici n'a de chatter que pour un lead — sur
        # un CustomRecord, elle NOOP proprement (comportement inchangé
        # d'AUTOMATION, hors périmètre NTEXT27 qui porte sur le déclencheur).
        self.assertEqual(self._runs().count(), 1)
        self.assertEqual(
            self._runs().first().status, AutomationRun.Status.NOOP)

    def test_enregistrement_dun_autre_objet_ne_declenche_pas(self):
        self._rule(object_code='suivi-qualite')
        CustomRecord.objects.create(
            company=self.co, objet=self.objet_b, data={})
        self.assertEqual(self._runs().count(), 0)

    def test_sans_object_code_matche_tout_objet_personnalise(self):
        self._rule(object_code='')
        CustomRecord.objects.create(
            company=self.co, objet=self.objet_a, data={})
        CustomRecord.objects.create(
            company=self.co, objet=self.objet_b, data={})
        self.assertEqual(self._runs().count(), 2)

    def test_modification_declenche_aussi(self):
        self._rule(object_code='visiteurs')
        record = CustomRecord.objects.create(
            company=self.co, objet=self.objet_b, data={})
        self.assertEqual(self._runs().count(), 1)
        record.data = {'nom': 'Visiteur X'}
        record.save()
        self.assertEqual(self._runs().count(), 2)

    def test_isolation_societe(self):
        autre_co = make_company()
        self._rule(object_code='suivi-qualite')
        objet_autre = CustomObjectDef.objects.create(
            company=autre_co, code='suivi-qualite', libelle='Suivi qualité')
        CustomRecord.objects.create(
            company=autre_co, objet=objet_autre, data={})
        self.assertEqual(self._runs().count(), 0)
        self.assertEqual(
            AutomationRun.objects.filter(company=autre_co).count(), 0)
