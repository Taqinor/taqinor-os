"""CAL195 — le schéma unifilaire sort enfin du moteur de devis.

Ce qui est prouvé ici :

* la porte cross-app ``apps.ventes.selectors.schema_unifilaire_svg`` rend,
  POUR UN DEVIS, EXACTEMENT ce que rendait le chemin existant
  (``electrical_service.rendre_schema_du_devis``, celui que
  ``quote_engine.builder._sld_svg`` appelle) — non-régression BYTE À BYTE ;
* un appelant qui porte déjà les objets du moteur électrique obtient LE MÊME
  dessin, sans devis ;
* sans de quoi dessiner, la porte rend ``None`` — jamais une planche à
  moitié vraie (discipline PVFCH-ANNEXE) ;
* AUCUNE app n'importe ``apps.ventes.quote_engine`` hors d'``apps.ventes``
  (règle #4 : le moteur REND, il ne s'importe pas).

Ces essais sont PURS : ni base, ni WeasyPrint. Le dessin est produit par
``core.electrique.schema``, un module pur.

Run :
    python manage.py test apps.ventes.tests.test_cal195_schema_unifilaire -v2
"""
import inspect
import pathlib
import re

from django.test import SimpleTestCase

from apps.ventes.selectors import schema_unifilaire_svg

RACINE_APPS = pathlib.Path(__file__).resolve().parents[3] / 'apps'


class PorteSchemaUnifilaireTest(SimpleTestCase):
    def test_sans_objets_aucun_dessin(self):
        self.assertIsNone(schema_unifilaire_svg())
        self.assertIsNone(schema_unifilaire_svg(entree=object()))
        self.assertIsNone(schema_unifilaire_svg(resultat=object()))

    def test_un_devis_delegue_au_chemin_existant_sans_rien_ajouter(self):
        """Non-régression : la porte ne fait que DÉLÉGUER — pas un paramètre
        de plus, pas un repli de plus. Le SVG d'un devis ne peut donc pas
        changer d'un octet."""
        source = inspect.getsource(schema_unifilaire_svg)
        self.assertIn('rendre_schema_du_devis', source)
        # Aucun dessin ici : la porte n'écrit pas une balise SVG.
        self.assertNotIn('<svg', source)
        self.assertNotIn('<path', source)

    def test_le_devis_rend_le_meme_objet_que_le_chemin_historique(self):
        from apps.ventes import selectors as _selectors

        temoin = object()
        appels = []

        class _FauxDevis:
            pass

        import apps.ventes.electrical_service as _es
        original = _es.rendre_schema_du_devis

        def _faux(devis, *, standard=False):
            appels.append((devis, standard))
            return temoin

        _es.rendre_schema_du_devis = _faux
        try:
            devis = _FauxDevis()
            self.assertIs(
                _selectors.schema_unifilaire_svg(devis=devis), temoin)
            self.assertEqual(appels, [(devis, False)])
        finally:
            _es.rendre_schema_du_devis = original

    def test_les_objets_du_moteur_donnent_le_meme_dessin(self):
        """Un appelant sans devis (le calepinage) passe par le MÊME moteur."""
        import core.electrique.schema as _schema

        temoin = '<svg>planche</svg>'
        vus = {}

        original = _schema.rendre_schema

        def _faux(entree, resultat, *, cartouche=None, standard=False):
            vus.update(entree=entree, resultat=resultat, cartouche=cartouche)
            return temoin

        _schema.rendre_schema = _faux
        try:
            entree, resultat = object(), object()
            rendu = schema_unifilaire_svg(
                entree=entree, resultat=resultat,
                cartouche={'client': 'Atlas'})
            self.assertEqual(rendu, temoin)
            self.assertIs(vus['entree'], entree)
            self.assertIs(vus['resultat'], resultat)
            self.assertEqual(vus['cartouche'], {'client': 'Atlas'})
        finally:
            _schema.rendre_schema = original

    #: DETTE CONSTATÉE, NOMMÉE PLUTÔT QUE MASQUÉE (20/09/2026) : un import du
    #: moteur vendorisé hors d'``apps.ventes`` existe déjà dans le dépôt —
    #: ``apps/crm/public_views.py`` (page publique de proposition). CAL195 ne
    #: le corrige pas (hors de ses ``Files:``) mais refuse d'élargir la garde
    #: en silence : la dérogation est LISTÉE ici, donc visible en revue, et
    #: toute NOUVELLE app qui importerait le moteur reste rouge.
    DEROGATIONS_QUOTE_ENGINE = ('crm/public_views.py',)

    def test_aucune_app_n_importe_le_moteur_de_devis(self):
        """Règle #4 : ``quote_engine`` REND, il ne s'importe pas depuis une
        autre app. ``apps.calepinage`` — l'app que CAL195 branche sur le
        schéma — passe par ``apps.ventes.selectors``, jamais par le moteur."""
        motif = re.compile(r'(from|import)\s+apps\.ventes\.quote_engine')
        for fichier in RACINE_APPS.rglob('*.py'):
            # Les TESTS d'une autre app peuvent légitimement rendre un PDF de
            # devis (c'est le comportement qu'ils vérifient) : la règle porte
            # sur le code de production.
            if ('ventes' in fichier.parts or 'migrations' in fichier.parts
                    or 'tests' in fichier.parts
                    or fichier.name.startswith('test')):
                continue
            relatif = fichier.relative_to(RACINE_APPS).as_posix()
            if relatif in self.DEROGATIONS_QUOTE_ENGINE:
                continue
            self.assertIsNone(
                motif.search(fichier.read_text(encoding='utf-8')),
                f'{relatif} importe apps.ventes.quote_engine : le moteur de '
                'devis ne s\'importe pas hors d\'apps.ventes (règle #4).')

    def test_les_derogations_listees_existent_encore(self):
        """Une dérogation qui n'a plus lieu d'être doit DISPARAÎTRE de la
        liste, pas y dormir : le test devient rouge quand la dette est
        remboursée."""
        motif = re.compile(r'(from|import)\s+apps\.ventes\.quote_engine')
        for relatif in self.DEROGATIONS_QUOTE_ENGINE:
            fichier = RACINE_APPS / relatif
            self.assertTrue(fichier.exists(), relatif)
            self.assertIsNotNone(
                motif.search(fichier.read_text(encoding='utf-8')),
                f'{relatif} n\'importe plus le moteur : retirez-le de '
                'DEROGATIONS_QUOTE_ENGINE.')
