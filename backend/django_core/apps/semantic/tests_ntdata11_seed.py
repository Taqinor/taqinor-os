"""NTDATA11 — `seed_metriques` : les 8 métriques cœur, semées par société.

Couvre :
  * les 8 clés sont créées, par société ;
  * IDEMPOTENCE : deux exécutions = mêmes 8 métriques, valeurs INCHANGÉES ;
  * ADDITIVITÉ : une métrique éditée par le fondateur n'est jamais réécrite ;
  * les adaptateurs compta/crm sont bien enregistrés (registre `semantic`) ;
  * une métrique d'adaptateur refuse un regroupement (un scalaire n'a pas de
    dimensions) et dit pourquoi, en français.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.semantic import adapters, services
from apps.semantic.management.commands.seed_metriques import METRIQUES_COEUR
from apps.semantic.models import MetricDefinition
from authentication.models import Company

# SOLMVP (2026-09-21) — ``compta`` (fournisseur des adaptateurs ``dso`` et
# ``marge_brute``) est une app PARQUÉE (Groupe SOLMVP, MVP solaire) : son
# ``ready()`` n'enregistre plus rien, donc ``compta.dso``/``compta.marge_
# brute`` ont disparu du registre ``apps.semantic.adapters`` (vérifié en
# shell Django). Les 8 métriques cœur (dont ``dso``) restent SEMÉES telles
# quelles (``test_huit_metriques_coeur``, inchangé) — seule leur RÉSOLUTION
# dégrade proprement, exactement comme ``AdaptateurInconnu`` le prévoyait
# déjà pour un module désactivé.

CLES_ATTENDUES = {
    'ca_ht', 'ca_ttc', 'panier_moyen', 'taux_conversion', 'mrr',
    'marge_brute', 'dso', 'valeur_pipeline_ponderee',
}


class SeedMetriquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA11 SA',
                                             slug='ntdata11-sa')

    def _seed(self):
        sortie = StringIO()
        call_command('seed_metriques', company=self.company.id, stdout=sortie)
        return sortie.getvalue()

    def test_huit_metriques_coeur(self):
        self.assertEqual({s['cle'] for s in METRIQUES_COEUR}, CLES_ATTENDUES)
        self._seed()
        cles = set(MetricDefinition.objects
                   .filter(company=self.company)
                   .values_list('cle', flat=True))
        self.assertEqual(cles, CLES_ATTENDUES)

    def test_idempotent_deux_executions(self):
        self._seed()
        avant = {
            m.cle: (m.libelle, m.dataset, m.mesure, m.filtres, m.unite,
                    m.format, m.updated_at)
            for m in MetricDefinition.objects.filter(company=self.company)
        }
        self._seed()
        apres = {
            m.cle: (m.libelle, m.dataset, m.mesure, m.filtres, m.unite,
                    m.format, m.updated_at)
            for m in MetricDefinition.objects.filter(company=self.company)
        }
        self.assertEqual(len(apres), 8)
        self.assertEqual(avant, apres)

    def test_metrique_editee_par_le_fondateur_intacte(self):
        self._seed()
        metrique = MetricDefinition.objects.get(company=self.company,
                                                cle='ca_ht')
        metrique.libelle = 'CA HT (définition maison)'
        metrique.mesure = {'field': 'montant_ttc', 'agg': 'sum'}
        metrique.save()
        self._seed()
        metrique.refresh_from_db()
        self.assertEqual(metrique.libelle, 'CA HT (définition maison)')
        self.assertEqual(metrique.mesure, {'field': 'montant_ttc',
                                           'agg': 'sum'})

    def test_ca_sans_brouillon(self):
        # AANA61 : les trois métriques CA sont semées sans brouillon.
        self._seed()
        for cle in ('ca_ht', 'ca_ttc', 'panier_moyen'):
            m = MetricDefinition.objects.get(company=self.company, cle=cle)
            self.assertEqual(m.filtres,
                             {'statut__in': ['emise', 'payee', 'en_retard']})

    def test_migration_realigne_les_defauts_seuls(self):
        import importlib
        from django.apps import apps as parc
        mig = importlib.import_module(
            'apps.semantic.migrations.0004_aana_ca_sans_brouillon')
        autre = Company.objects.create(nom='AANA61 B', slug='aana61-b')
        self._seed()
        call_command('seed_metriques', company=autre.id, stdout=StringIO())
        MetricDefinition.objects.filter(cle__in=mig.CLES).update(
            filtres=mig.ANCIEN)
        retouche = MetricDefinition.objects.get(company=autre, cle='ca_ht')
        retouche.filtres = {'statut__in': ['payee']}
        retouche.save()
        nb_retouche = retouche.versions.count()
        mig.realigner(parc, None)
        ca = MetricDefinition.objects.get(company=self.company, cle='ca_ht')
        self.assertEqual(ca.filtres, mig.NOUVEAU)
        self.assertEqual(list(ca.versions.values_list('version', flat=True)),
                         [2, 1])  # v1 du semis + v2 de la migration
        retouche.refresh_from_db()
        self.assertEqual(retouche.filtres, {'statut__in': ['payee']})
        self.assertEqual(retouche.versions.count(), nb_retouche)
        mig.realigner(parc, None)  # second passage : rien d'écrit
        self.assertEqual(ca.versions.count(), 2)

    def test_seed_par_societe(self):
        autre = Company.objects.create(nom='NTDATA11 Autre',
                                       slug='ntdata11-autre')
        self._seed()
        self.assertEqual(
            MetricDefinition.objects.filter(company=autre).count(), 0)
        call_command('seed_metriques', company=autre.id, stdout=StringIO())
        self.assertEqual(
            MetricDefinition.objects.filter(company=autre).count(), 8)

    def test_adaptateurs_enregistres(self):
        enregistres = adapters.list_adapters()
        # compta.dso / compta.marge_brute : voir la note SOLMVP en tête de
        # fichier — compta est parqué, plus enregistré.
        self.assertIn('crm.pipeline_pondere', enregistres)
        self.assertNotIn('compta.dso', enregistres)
        self.assertNotIn('compta.marge_brute', enregistres)

    def test_metrique_adaptateur_refuse_un_regroupement(self):
        self._seed()
        with self.assertRaises(services.MetriqueNonResolvable) as ctx:
            services.resolve_metric(self.company, None, 'dso',
                                    group_by=['mois'])
        self.assertIn('adaptateur', str(ctx.exception))

    def test_dso_resolu_par_l_adaptateur(self):
        self._seed()
        # compta (fournisseur de l'adaptateur DSO) est parqué (Groupe
        # SOLMVP) : plus aucun adaptateur ``compta.dso`` n'est enregistré.
        # Le résolveur le dit en clair (module désactivé) plutôt que de
        # rendre un faux zéro — même famille d'erreur que
        # ``test_metrique_adaptateur_refuse_un_regroupement``.
        with self.assertRaises(services.MetriqueNonResolvable) as ctx:
            services.resolve_metric(self.company, None, 'dso')
        self.assertIn('désactivé', str(ctx.exception))

    def test_pipeline_pondere_resolu_par_l_adaptateur(self):
        self._seed()
        res = services.resolve_metric(
            self.company, None, 'valeur_pipeline_ponderee')
        self.assertEqual(res['lignes'], [])
        self.assertIsNotNone(res['valeur'])
