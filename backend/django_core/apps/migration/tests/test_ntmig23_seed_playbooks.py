"""Tests NTMIG23 — commande ``seed_playbooks``.

Critère d'acceptation : ``seed_playbooks`` deux fois = mêmes playbooks,
contenu INCHANGÉ si déjà personnalisé.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.kb.models import KbArticle
from apps.migration.playbooks import (
    PHASES, PLAYBOOKS, cle_graine, structure_pour)
from apps.migration.services import instancier_playbook

from ._base import make_company


class Ntmig23SeedPlaybooksTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig23', 'NTMIG23')

    def _seed(self, **options):
        sortie = StringIO()
        call_command('seed_playbooks', stdout=sortie, **options)
        return sortie.getvalue()

    def _playbooks(self):
        return KbArticle.objects.filter(
            company=self.company,
            type_article=KbArticle.TypeArticle.PLAYBOOK)

    def test_seed_cree_les_six_playbooks(self):
        self._seed(company='ntmig23')
        self.assertEqual(self._playbooks().count(), len(PLAYBOOKS))
        for definition in PLAYBOOKS:
            article = self._playbooks().get(
                tags__contains=cle_graine(definition['cle']))
            self.assertEqual(article.titre, definition['titre'])
            self.assertEqual(article.statut, KbArticle.Statut.PUBLIE)
            self.assertEqual(len(article.contenu_structure), len(PHASES))
            # Le corps texte reste lisible en recherche plein texte.
            self.assertIn(definition['resume'], article.corps)

    def test_deux_passages_ne_dupliquent_rien(self):
        self._seed(company='ntmig23')
        avant = list(self._playbooks().values_list('id', flat=True))
        self._seed(company='ntmig23')
        apres = list(self._playbooks().values_list('id', flat=True))
        self.assertEqual(avant, apres)
        self.assertEqual(self._playbooks().count(), len(PLAYBOOKS))

    def test_playbook_personnalise_jamais_reecrit(self):
        self._seed(company='ntmig23')
        article = self._playbooks().get(
            tags__contains=cle_graine('crm_ventes'))
        article.titre = 'Go-live Ventes (version Reda)'
        article.contenu_structure = [
            {'cle': 'a_moi', 'titre': 'Ma phase', 'etapes': [
                {'cle': 'a1', 'libelle': 'Mon étape'}]}]
        article.save()

        self._seed(company='ntmig23')

        relu = KbArticle.objects.get(pk=article.pk)
        self.assertEqual(relu.titre, 'Go-live Ventes (version Reda)')
        self.assertEqual(len(relu.contenu_structure), 1)
        # Et surtout : aucun doublon recréé sous le titre d'origine.
        self.assertEqual(self._playbooks().count(), len(PLAYBOOKS))

    def test_seed_scope_par_societe(self):
        autre = make_company('ntmig23-bis', 'NTMIG23 bis')
        self._seed(company='ntmig23')
        self.assertFalse(KbArticle.objects.filter(company=autre).exists())
        # Sans --company, toutes les sociétés sont servies.
        self._seed()
        self.assertEqual(
            KbArticle.objects.filter(
                company=autre,
                type_article=KbArticle.TypeArticle.PLAYBOOK).count(),
            len(PLAYBOOKS))

    def test_societe_inconnue_leve_une_erreur_claire(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._seed(company='societe-qui-nexiste-pas')

    def test_cles_d_etapes_uniques_dans_chaque_playbook(self):
        """Deux étapes de même clé feraient mentir la progression NTMIG22."""
        for definition in PLAYBOOKS:
            cles = [etape['cle']
                    for phase in structure_pour(definition)
                    for etape in phase['etapes']]
            self.assertEqual(len(cles), len(set(cles)), definition['cle'])

    def test_playbook_seede_est_instanciable(self):
        """Bout en bout : un playbook seedé alimente une checklist NTMIG22."""
        self._seed(company='ntmig23')
        article = self._playbooks().get(
            tags__contains=cle_graine('compta'))
        instance = instancier_playbook(article, company=self.company)
        self.assertGreater(instance.nb_etapes, 0)
        self.assertEqual(instance.progression, 0)
        self.assertEqual(instance.playbook_titre, article.titre)
