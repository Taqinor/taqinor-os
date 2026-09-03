"""SOL2(c)/(d) — beat et overrides d'énumération suivent l'édition.

(c) Le planificateur Celery ne doit plus planifier les tâches d'une app
    parquée : leur module n'étant pas chargé, chaque tick produirait un
    `NotRegistered` et une entrée en file que plus aucun worker ne consomme.
(d) Un `ENUM_NAME_OVERRIDES` qui pointe vers un modèle d'app parquée fait
    échouer la génération du schéma OpenAPI.

Les deux filtres sont NEUTRES en édition complète (défaut CI) — c'est
l'invariant principal gardé ici.
"""
from django.conf import settings
from django.test import TestCase

from erp_agentique.celery import filtrer_beat_apps_parquees
from erp_agentique.settings import editions


class BeatFiltreEditionTests(TestCase):
    PLANNING = {
        'mrp-recalculer': {'task': 'mrp.recalculer_besoins_nocturne'},
        'sante-alertes': {'task': 'sante.alertes_prise_en_charge_expirant'},
        'education-seances': {'task': 'education.generer_seances_semaine'},
        'immobilier-loyers': {'task': 'immobilier.generer_echeances_loyer'},
        'ventes-overdue': {'task': 'ventes.check_overdue_factures'},
        'core-heartbeat': {'task': 'core.beat_heartbeat'},
    }

    def test_edition_complete_identite(self):
        self.assertEqual(
            filtrer_beat_apps_parquees(self.PLANNING, 'full'), self.PLANNING)

    def test_edition_solaire_retire_les_apps_parquees(self):
        restant = filtrer_beat_apps_parquees(self.PLANNING, 'solar')
        self.assertEqual(
            sorted(restant), ['core-heartbeat', 'ventes-overdue'])

    def test_planning_reel_sans_tache_d_app_parquee_en_solaire(self):
        """Le planning RÉEL du dépôt ne garde aucune tâche parquée."""
        from erp_agentique import celery as celery_module

        planning = celery_module.app.conf.beat_schedule
        restant = filtrer_beat_apps_parquees(planning, 'solar')
        prefixes = tuple(
            f'{cle}.' for cle in editions.modules_parques('solar'))
        fuites = [
            nom for nom, entree in restant.items()
            if str(entree.get('task', '')).startswith(prefixes)
        ]
        self.assertEqual(fuites, [])
        # …et l'édition complète garde TOUT (dont les tâches mrp/sante).
        self.assertEqual(
            filtrer_beat_apps_parquees(planning, 'full'), planning)

    def test_planning_charge_coherent_avec_l_edition_courante(self):
        """Le planning EFFECTIVEMENT chargé suit `settings.TAQINOR_EDITION`."""
        from erp_agentique import celery as celery_module

        taches = {
            str(e.get('task', ''))
            for e in celery_module.app.conf.beat_schedule.values()
        }
        if settings.TAQINOR_EDITION == editions.EDITION_FULL:
            self.assertIn('mrp.recalculer_besoins_nocturne', taches)
        else:
            prefixes = tuple(
                f'{cle}.' for cle in editions.modules_parques())
            self.assertEqual(
                [t for t in taches if t.startswith(prefixes)], [])


class EnumOverridesEditionTests(TestCase):
    def test_overrides_coherents_avec_l_edition_courante(self):
        overrides = settings.SPECTACULAR_SETTINGS['ENUM_NAME_OVERRIDES']
        if settings.TAQINOR_EDITION == editions.EDITION_FULL:
            # Aucun churn de schéma en édition complète : tout est conservé.
            self.assertIn('EtatGeneralPieceEnum', overrides)
            self.assertIn('MotifRebutOFEnum', overrides)
        else:
            self.assertNotIn('EtatGeneralPieceEnum', overrides)
            self.assertNotIn('MotifRebutOFEnum', overrides)

    def test_filtrage_solaire_retire_immobilier_et_mrp(self):
        overrides = settings.SPECTACULAR_SETTINGS['ENUM_NAME_OVERRIDES']
        filtre = editions.filtrer_chemins(overrides, 'solar')
        self.assertNotIn('EtatGeneralPieceEnum', filtre)
        self.assertNotIn('MotifRebutOFEnum', filtre)
        # Les overrides des apps GARDÉES survivent tous.
        self.assertIn('OrientationPanneauEnum', filtre)
        self.assertIn('MotifRebutEnum', filtre)

    def test_reglage_edition_expose_dans_les_settings(self):
        self.assertIn(settings.TAQINOR_EDITION, editions.EDITIONS)
