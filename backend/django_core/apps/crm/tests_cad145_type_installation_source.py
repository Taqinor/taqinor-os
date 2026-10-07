"""CAD145 — `type_installation` a une source unique pour le scoring, les
playbooks et les textes ; `SiteProfile.type_installation` est un champ
CLIENT distinct, jamais lu par ces trois surfaces.

`apps.crm.models.SiteProfile` duplique `type_installation` (et d'autres
taxonomies) parce qu'il vit à un autre niveau — réutilisable sur un devis
SANS lead — pas par dérive. Ce module PROUVE structurellement que
`scoring.py` et `services.py` (qui portent le scoring, l'évaluation des
playbooks et le rendu des textes de cadence) ne référencent même pas
`SiteProfile` : ils ne PEUVENT donc pas lire son `type_installation`. Un
test statique (lecture du fichier source) plutôt qu'un test ORM : ces deux
modules n'ont besoin d'aucune base pour être vérifiés, et le test tourne
localement (``SimpleTestCase``).
"""
import pathlib

from django.test import SimpleTestCase

_ICI = pathlib.Path(__file__).resolve().parent

#: Fichiers qui portent les trois surfaces citées par le Done de CAD145 —
#: le scoring et l'évaluation des playbooks/textes vivent tous deux dans
#: `services.py` (rendu des messages) et `scoring.py` (calcul du score).
_FICHIERS_A_VERIFIER = ('scoring.py', 'services.py')


class SourceUniqueTypeInstallationTests(SimpleTestCase):

    def test_scoring_et_services_ne_referencent_jamais_siteprofile(self):
        """Anti-faux-vert incluse : si l'un de ces fichiers importait un jour
        `SiteProfile`, ce test s'arrêterait ici plutôt que de laisser un
        futur lecteur de `.type_installation` passer inaperçu."""
        for nom in _FICHIERS_A_VERIFIER:
            chemin = _ICI / nom
            texte = chemin.read_text(encoding='utf-8')
            with self.subTest(fichier=nom):
                self.assertNotIn(
                    'SiteProfile', texte,
                    f'{nom} référence SiteProfile — vérifier qu\'il ne lit '
                    'pas SiteProfile.type_installation (CAD145 : la source '
                    'unique du scoring/playbooks/textes reste Lead.'
                    'type_installation).')

    def test_lead_porte_bien_le_champ_type_installation(self):
        from apps.crm.models import Lead
        self.assertIn('type_installation',
                      [f.name for f in Lead._meta.get_fields()])

    def test_siteprofile_porte_aussi_le_champ_mais_a_un_autre_usage(self):
        """Les deux champs existent : ce test verrouille qu'on ne les a pas
        fusionnés par erreur (perte du pré-remplissage devis SANS lead)."""
        from apps.crm.models import SiteProfile
        self.assertIn('type_installation',
                      [f.name for f in SiteProfile._meta.get_fields()])
