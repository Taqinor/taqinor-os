"""ODX14 — la configuration de vente (FG209–221) est relogée de compta vers
``apps.ventes``, tables physiques préservées (``compta_<model>``), shims compta
de ré-export conservés. State-only (SeparateDatabaseAndState) — aucune donnée
déplacée, aucun SQL.

Run :
    python manage.py test apps.ventes.tests.test_odx14_ventes_config_split -v2
"""
from django.test import TestCase


CONFIG_MODELS = [
    ('CodePromotion', 'compta_codepromotion'),
    ('ModeleDevis', 'compta_modeledevis'),
    ('SessionGuidedSelling', 'compta_sessionguidedselling'),
    ('DemandeApprobationConfig', 'compta_demandeapprobationconfig'),
    ('ECatalogue', 'compta_ecatalogue'),
    ('DocumentProposition', 'compta_documentproposition'),
    ('SimulationPublique', 'compta_simulationpublique'),
    ('SimulationFinancement', 'compta_simulationfinancement'),
    ('OffreFinancement', 'compta_offrefinancement'),
    ('LigneIncitation', 'compta_ligneincitation'),
    ('EcheancierPaiement', 'compta_echeancierpaiement'),
    ('TranchePaiement', 'compta_tranchepaiement'),
]


class TestODX14Relocation(TestCase):
    def test_models_live_in_ventes_with_preserved_db_tables(self):
        import apps.ventes.models as vm
        import apps.compta.models as cm
        for name, table in CONFIG_MODELS:
            model = getattr(vm, name)
            # Le shim compta ré-exporte EXACTEMENT la même classe (retiré ODX22).
            self.assertIs(model, getattr(cm, name), name)
            # Table physique préservée + app_label déplacé vers ventes.
            self.assertEqual(model._meta.db_table, table, name)
            self.assertEqual(model._meta.app_label, 'ventes', name)

    def test_scoped_create_on_preserved_table(self):
        # Un create réel écrit bien dans la table historique (state-only : la
        # table n'a jamais bougé), scopé société.
        from authentication.models import Company
        from apps.ventes.models import CodePromotion
        import datetime
        company, _ = Company.objects.get_or_create(
            slug='odx14-co', defaults={'nom': 'ODX14 Co'})
        cp = CodePromotion.objects.create(
            company=company, code='AID-5', date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 12, 31))
        self.assertEqual(cp._meta.db_table, 'compta_codepromotion')
        self.assertTrue(
            CodePromotion.objects.filter(company=company, code='AID-5').exists())
