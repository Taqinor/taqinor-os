"""ZMKT7 — Recettes de séquence Odoo-style manquantes (double opt-in, tag
hot contacts, prioriser leads chauds).

Couvre : la commande ajoute les 3 recettes sans toucher les existantes,
re-run = no-op, chacune activable en un clic, tests (idempotence, actions
posées).
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.compta.models import EtapeSequence, SequenceRelance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RecettesOdooStyleTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt7', 'ZMKT7')

    def _run(self):
        out = StringIO()
        call_command(
            'seed_sequences_marketing', '--company-slug', 'zmkt7', stdout=out)
        return out.getvalue()

    def test_ajoute_3_recettes_zmkt7(self):
        self._run()
        for nom in ('Double opt-in', 'Taguer contacts chauds',
                    'Prioriser leads chauds'):
            self.assertTrue(
                SequenceRelance.objects.filter(company=self.co, nom=nom).exists(),
                f'{nom} manquante')

    def test_ne_touche_pas_recettes_xmkt20_existantes(self):
        self._run()
        avant = SequenceRelance.objects.filter(
            company=self.co, nom='Bienvenue nouveau lead').count()
        self._run()
        apres = SequenceRelance.objects.filter(
            company=self.co, nom='Bienvenue nouveau lead').count()
        self.assertEqual(avant, apres)
        self.assertEqual(avant, 1)

    def test_rerun_no_op_zmkt7(self):
        self._run()
        avant = SequenceRelance.objects.filter(company=self.co).count()
        self._run()
        apres = SequenceRelance.objects.filter(company=self.co).count()
        self.assertEqual(avant, apres)

    def test_taguer_contacts_chauds_action_posee(self):
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Taguer contacts chauds')
        etape = seq.etapes.first()
        self.assertEqual(etape.type_etape, EtapeSequence.TypeEtape.ACTION_CRM)
        self.assertEqual(etape.action_crm['action'], 'tag')
        self.assertEqual(etape.action_crm['params']['tag'], 'chaud')

    def test_prioriser_leads_chauds_condition_clic(self):
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Prioriser leads chauds')
        etape = seq.etapes.first()
        self.assertEqual(etape.condition, EtapeSequence.Condition.A_CLIQUE)
        self.assertEqual(etape.action_crm['action'], 'tache')

    def test_double_optin_recette_activable(self):
        self._run()
        seq = SequenceRelance.objects.get(company=self.co, nom='Double opt-in')
        seq.actif = True
        seq.save(update_fields=['actif'])
        seq.refresh_from_db()
        self.assertTrue(seq.actif)
        self.assertEqual(seq.etapes.count(), 2)
