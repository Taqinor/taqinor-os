"""VAO7 — le catalogue des sources : seed rejouable, sources désactivées
jamais collectées, aucune URL de portail en dur hors de la table.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.veille_ao.management.commands.seed_veille_sources import (
    SOURCES, seed_sources_pour_societe,
)
from apps.veille_ao.models import SourceVeille, TypeSource
from authentication.models import Company

MODULE_DIR = Path(__file__).resolve().parent.parent

#: Le seed est le SEUL fichier autorisé à écrire une URL de source en clair.
FICHIERS_AUTORISES_URL = {
    'management/commands/seed_veille_sources.py',
}


class SeedIdempotentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Sources')
        cls.autre = Company.objects.create(nom='Autre Sources')

    def test_seed_cree_toutes_les_sources(self):
        crees = seed_sources_pour_societe(self.company)
        self.assertEqual(crees, len(SOURCES))
        self.assertEqual(
            SourceVeille.objects.filter(company=self.company).count(),
            len(SOURCES))

    def test_seed_rejoue_ne_cree_aucun_doublon(self):
        seed_sources_pour_societe(self.company)
        recrees = seed_sources_pour_societe(self.company)
        self.assertEqual(recrees, 0)
        self.assertEqual(
            SourceVeille.objects.filter(company=self.company).count(),
            len(SOURCES))

    def test_seed_ne_touche_jamais_une_source_existante(self):
        """Un réglage du fondateur survit à un re-seed (additif seulement)."""
        seed_sources_pour_societe(self.company)
        source = SourceVeille.objects.get(company=self.company, code='pmmp')
        source.libelle = 'Portail (renommé par le fondateur)'
        source.cadence_heures = 168
        source.actif = True
        source.save()

        seed_sources_pour_societe(self.company)

        source.refresh_from_db()
        self.assertEqual(source.libelle, 'Portail (renommé par le fondateur)')
        self.assertEqual(source.cadence_heures, 168)
        self.assertTrue(source.actif)

    def test_seed_est_scope_par_societe(self):
        seed_sources_pour_societe(self.company)
        self.assertEqual(
            SourceVeille.objects.filter(company=self.autre).count(), 0)
        seed_sources_pour_societe(self.autre)
        self.assertEqual(
            SourceVeille.objects.filter(company=self.autre).count(),
            len(SOURCES))

    def test_codes_du_seed_sont_uniques(self):
        codes = [ligne[0] for ligne in SOURCES]
        self.assertEqual(len(codes), len(set(codes)))


class SourcesSemeesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Phase')
        seed_sources_pour_societe(cls.company)

    def test_portes_humaines_actives(self):
        for code in ('saisie_manuelle', 'tuyau_partenaire', 'import_fichier'):
            source = SourceVeille.objects.get(
                company=self.company, code=code)
            self.assertTrue(source.actif, code)

    def test_portail_officiel_seme_desarme(self):
        """Règle #5 : le collecteur naît désarmé — le seed ne l'arme pas."""
        pmmp = SourceVeille.objects.get(company=self.company, code='pmmp')
        self.assertEqual(pmmp.type_source, TypeSource.PORTAIL_OFFICIEL)
        self.assertFalse(pmmp.actif)

    def test_sources_de_phase_2_creees_inactives(self):
        phase_2 = SourceVeille.objects.filter(
            company=self.company,
            type_source__in=[TypeSource.PORTAIL_SECTORIEL,
                             TypeSource.AGREGATEUR])
        self.assertTrue(phase_2.exists())
        self.assertFalse(phase_2.filter(actif=True).exists())


class SourceDesactiveeJamaisCollecteeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Collecte')

    def _source(self, **kwargs):
        params = {
            'company': self.company,
            'code': 'src',
            'libelle': 'Source',
            'type_source': TypeSource.PORTAIL_OFFICIEL,
            'url_base': 'https://exemple.test',
            'actif': True,
        }
        params.update(kwargs)
        return SourceVeille.objects.create(**params)

    def test_source_active_est_collectable(self):
        source = self._source()
        self.assertTrue(source.est_collectable_automatiquement)
        self.assertIn(source, SourceVeille.objects.collectables())

    def test_source_desactivee_n_est_jamais_collectee(self):
        source = self._source(actif=False)
        self.assertFalse(source.est_collectable_automatiquement)
        self.assertNotIn(source, SourceVeille.objects.collectables())

    def test_porte_humaine_n_est_jamais_collectee(self):
        """Un tuyau partenaire est une porte HUMAINE : rien à interroger."""
        source = self._source(
            code='humain', type_source=TypeSource.TUYAU_PARTENAIRE,
            url_base='')
        self.assertFalse(source.est_collectable_automatiquement)
        self.assertNotIn(source, SourceVeille.objects.collectables())

    def test_source_sans_url_n_est_jamais_collectee(self):
        source = self._source(code='sans-url', url_base='')
        self.assertFalse(source.est_collectable_automatiquement)
        self.assertNotIn(source, SourceVeille.objects.collectables())

    def test_collectables_reste_scope_par_societe(self):
        autre = Company.objects.create(nom='Autre Collecte')
        self._source()
        collectables = SourceVeille.objects.filter(
            company=autre).collectables()
        self.assertEqual(collectables.count(), 0)


class AucuneUrlEnDurTests(SimpleTestCase):
    """« Aucun littéral d'URL de portail hors de cette table. »

    Coder « le portail » en dur condamnerait chaque extension à toucher le
    collecteur. Cette garde balaie tout le module (le collecteur inclus, dès
    qu'il existera) et n'excepte QUE le fichier de seed, qui est la table.
    """

    def _fichiers_du_module(self):
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            if relatif in FICHIERS_AUTORISES_URL:
                continue
            yield relatif, chemin

    def test_aucune_url_http_en_dur_dans_le_module(self):
        fautifs = []
        for relatif, chemin in self._fichiers_du_module():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Constant):
                    continue
                if not isinstance(noeud.value, str):
                    continue
                texte = noeud.value
                if 'http://' in texte or 'https://' in texte:
                    fautifs.append(f'{relatif}:{noeud.lineno}')
        self.assertEqual(
            fautifs, [],
            "URL en dur hors de la table des sources — elle doit venir de "
            f"SourceVeille.url_base : {fautifs}")

    def test_aucun_hote_de_portail_en_dur_dans_le_module(self):
        hotes = ('marchespublics.gov.ma', 'etendering.masen.ma',
                 'safakat.cdg.ma')
        fautifs = []
        for relatif, chemin in self._fichiers_du_module():
            contenu = chemin.read_text(encoding='utf-8')
            for hote in hotes:
                if hote in contenu:
                    fautifs.append(f'{relatif} ({hote})')
        self.assertEqual(fautifs, [], fautifs)
