"""CAL27 — le manifeste plateforme ne déclare que ce qui est CÂBLÉ.

Ce qui est prouvé ici :

* les trois surfaces déclarées le sont RÉELLEMENT : la recherche globale
  trouve un calepinage par son TITRE, le chatter ``records`` accepte le
  calepinage comme cible, et le modèle est enregistré côté champs perso ;
* les quatre autres surfaces restent VIDES — un identifiant déclaré sans
  câblage est un mensonge que la matrice de couverture détecte à l'envers ;
* aucune dérive inter-surfaces n'est introduite (chatter ⇄ recherche).

Run :
    python manage.py test apps.calepinage.tests.test_platform -v2
"""
from apps.calepinage.models import Calepinage
from apps.calepinage.platform import PLATFORM

from .test_api_liste import BaseApiCalepinage


class ManifestePlateformeTest(BaseApiCalepinage):
    def test_surfaces_declarees(self):
        self.assertEqual(PLATFORM['module'], 'calepinage')
        self.assertEqual(PLATFORM['searchable_models'],
                         ['calepinage.calepinage'])
        self.assertEqual(PLATFORM['record_targets'],
                         ['calepinage.calepinage'])
        self.assertEqual(PLATFORM['customfield_models'], ['calepinage'])

    def test_surfaces_non_cablees_restent_vides(self):
        for surface in ('import_specs', 'automation_state_fields',
                        'kpi_providers'):
            self.assertEqual(PLATFORM[surface], [], surface)
        self.assertEqual(PLATFORM['agent_actions_module'], '')

    def test_le_calepinage_est_une_cible_de_chatter(self):
        from apps.records.models import ALLOWED_TARGETS

        self.assertIn(('calepinage', 'calepinage'), ALLOWED_TARGETS)

    def test_la_recherche_globale_trouve_par_le_titre(self):
        Calepinage.objects.create(company=self.company, lead_id=self.lead.pk,
                                  titre='Toiture Bouskoura')
        reponse = self.api.get('/api/django/reporting/search/',
                               {'q': 'Bouskoura'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        groupes = {g['type']: g for g in reponse.data.get('groups', [])}
        self.assertIn('calepinage', groupes)
        self.assertTrue(any('Bouskoura' in r['label']
                            for r in groupes['calepinage']['results']))

    def test_aucune_derive_inter_surfaces_nouvelle(self):
        from core import platform_coverage

        nouvelles = {cle for cle in platform_coverage.new_drift(
            platform_coverage.platform.collect_platform_manifests())
            if cle[0].startswith('calepinage.')}
        self.assertEqual(nouvelles, set())
