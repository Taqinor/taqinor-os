"""XMKT20 — Recettes de séquences prêtes à l'emploi (seed).

Couvre : la commande crée les 5 recettes désactivées par défaut, re-run =
no-op, chaque recette est activable en un clic.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.compta.models import EtapeSequence, SequenceRelance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SeedSequencesMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt20', 'XMKT20')

    def _run(self):
        out = StringIO()
        call_command(
            'seed_sequences_marketing', '--company-slug', 'xmkt20', stdout=out)
        return out.getvalue()

    def test_cree_recettes_desactivees(self):
        self._run()
        sequences = SequenceRelance.objects.filter(company=self.co)
        # 5 recettes XMKT20 + 3 recettes ZMKT7 (double opt-in, tag hot
        # contacts, prioriser leads chauds) = 8.
        self.assertEqual(sequences.count(), 8)
        for seq in sequences:
            self.assertFalse(seq.actif)

    def test_rerun_no_op(self):
        self._run()
        avant = SequenceRelance.objects.filter(company=self.co).count()
        self._run()
        apres = SequenceRelance.objects.filter(company=self.co).count()
        self.assertEqual(avant, apres)

    def test_etapes_creees_par_recette(self):
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Relance devis envoyé')
        self.assertEqual(EtapeSequence.objects.filter(sequence=seq).count(), 3)

    def test_recette_activable_en_un_clic(self):
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Bienvenue nouveau lead')
        seq.actif = True
        seq.save(update_fields=['actif'])
        seq.refresh_from_db()
        self.assertTrue(seq.actif)

    def test_reveil_base_froide_utilise_stage_cold(self):
        from apps.crm.stages import COLD
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Réveil base froide')
        self.assertEqual(seq.stage_declencheur, COLD)

    def test_ne_touche_pas_sequence_existante(self):
        SequenceRelance.objects.create(
            company=self.co, nom='Bienvenue nouveau lead', actif=True)
        self._run()
        seq = SequenceRelance.objects.get(
            company=self.co, nom='Bienvenue nouveau lead')
        # Reste active (jamais touchée par le seed).
        self.assertTrue(seq.actif)
        self.assertEqual(
            SequenceRelance.objects.filter(
                company=self.co, nom='Bienvenue nouveau lead').count(), 1)
