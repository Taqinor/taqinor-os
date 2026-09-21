"""CAL239 — la préséance entre le calepinage 3D et la variante AO 2D.

LE DANGER QUE CE MODULE FERME
-----------------------------
Depuis CAL30-CAL32, une affaire porte DEUX systèmes de variantes qui se
ressemblent assez pour être confondus : ``ao.VarianteCalepinage`` (2D, studio
AO, celle qui engage devant l'acheteur) et ``calepinage.CalepinageVariante``
(3D, module neutre, document de travail). Aucune tâche ne disait lequel fait
foi — le premier agent qui branchera la nomenclature 3D (CAL185) sur le
bordereau produira un dossier dont les quantités ne correspondent plus aux
planches déposées. C'est un motif d'écartement d'offre.

LA RÈGLE (``docs/calepinage-module.md``, section « Préséance »)
--------------------------------------------------------------
La variante 2D RETENUE est la source OPPOSABLE du bordereau et de la fabrique
documentaire. Le calepinage 3D est le document de TRAVAIL. La nomenclature
CAL185 ne peut JAMAIS alimenter un bordereau AO. Aucun modèle n'est fusionné.

CE QUE CE MODULE VERROUILLE
---------------------------
  1. ``LigneBordereau.variante`` pointe ``ao.VarianteCalepinage``, et rien
     d'autre.
  2. Aucune origine de quantité issue du module 3D n'entre dans
     ``LigneBordereau.QuantiteSource``.
  3. Aucun module PRODUCTEUR du bordereau AO ne lit ``apps.calepinage``
     (garde de SOURCE : elle échoue à l'écriture, pas à l'exécution).
  4. Les deux modèles de variantes restent DISTINCTS : deux apps, deux
     tables, deux chaînes de migrations.
  5. La règle est ÉCRITE, et le fichier qui la porte existe.

Run :
    python manage.py test apps.ao.tests.test_preseance_calepinage -v2
"""
import pathlib
import re

from django.apps import apps as registre
from django.test import SimpleTestCase

from apps.ao.models import LigneBordereau, VarianteCalepinage

#: tests → ao → apps → django_core → backend → racine du dépôt.
RACINE = pathlib.Path(__file__).resolve().parents[5]
DOC_REGLE = RACINE / 'docs' / 'calepinage-module.md'
FABRIQUE = pathlib.Path(__file__).resolve().parents[1] / 'fabrique'

#: Les modules PURS qui PRODUISENT le bordereau d'appel d'offres. Cette liste
#: est la SURFACE gardée : y ajouter un module producteur, c'est le soumettre
#: à la règle. Elle n'inclut PAS ``views.py``/``services.py`` (fichiers
#: partagés par tout le domaine, et qui lisent légitimement le module 3D pour
#: l'atelier — CAL32/CAL241) : la garde vise les producteurs, pas le domaine.
PRODUCTEURS_DU_BORDEREAU = (
    'report_quantites.py',
    'import_bordereau.py',
    'montants.py',
    'bibliotheque_prix.py',
    'ordonnancement.py',
    'derivations.py',
)

#: Tout ce qui nommerait le module 3D depuis un producteur de bordereau.
MOTIFS_INTERDITS = (
    re.compile(r'\bapps\.calepinage\b'),
    re.compile(r'\bCalepinageVariante\b'),
    re.compile(r'\bcalepinage_id\b'),
)


class LeBordereauEstServiParLaVariante2d(SimpleTestCase):
    def test_la_ligne_pointe_le_modele_2d_de_l_ao(self):
        cible = LigneBordereau._meta.get_field('variante').related_model

        self.assertIs(cible, VarianteCalepinage)
        self.assertEqual(cible._meta.app_label, 'ao')

    def test_aucune_origine_de_quantite_ne_vient_du_module_3d(self):
        """Les quatre origines connues, et pas une cinquième « 3D »."""
        valeurs = {choix.value for choix in LigneBordereau.QuantiteSource}

        self.assertEqual(
            valeurs, {'calepinage', 'manuelle', 'catalogue', 'acheteur'})

    def test_aucun_champ_de_ligne_ne_pointe_le_module_3d(self):
        """Un FK vers ``calepinage`` suffirait à rouvrir la porte."""
        cibles = {champ.related_model._meta.app_label
                  for champ in LigneBordereau._meta.get_fields()
                  if getattr(champ, 'related_model', None) is not None}

        self.assertNotIn('calepinage', cibles)


class AucunProducteurDuBordereauNeLitLeModule3d(SimpleTestCase):
    """Garde de SOURCE : elle échoue à l'écriture du code, pas au déploiement.

    C'est exactement la classe de régression que CAL239 anticipe — brancher
    CAL185 sur le bordereau « parce que c'est plus riche ».
    """

    def test_la_surface_gardee_existe_vraiment(self):
        """Un fichier renommé ne doit pas éteindre la garde en silence."""
        manquants = [nom for nom in PRODUCTEURS_DU_BORDEREAU
                     if not (FABRIQUE / nom).is_file()]
        self.assertEqual(manquants, [])

    def test_aucun_ne_nomme_le_module_calepinage(self):
        fautes = []
        for nom in PRODUCTEURS_DU_BORDEREAU:
            source = (FABRIQUE / nom).read_text(encoding='utf-8')
            for numero, ligne in enumerate(source.splitlines(), start=1):
                for motif in MOTIFS_INTERDITS:
                    if motif.search(ligne):
                        fautes.append(f'{nom}:{numero} — {ligne.strip()}')

        self.assertEqual(
            fautes, [],
            "Un producteur du bordereau AO lit le module Calepinage 3D. "
            "La variante 2D RETENUE est la seule source opposable du "
            "bordereau (docs/calepinage-module.md, section « Préséance »).")


class LesDeuxModelesRestentDistincts(SimpleTestCase):
    def test_deux_apps_deux_classes(self):
        variante_3d = registre.get_model('calepinage', 'CalepinageVariante')

        self.assertIsNot(variante_3d, VarianteCalepinage)
        self.assertEqual(variante_3d._meta.app_label, 'calepinage')
        self.assertEqual(VarianteCalepinage._meta.app_label, 'ao')

    def test_deux_tables_distinctes(self):
        variante_3d = registre.get_model('calepinage', 'CalepinageVariante')

        self.assertNotEqual(variante_3d._meta.db_table,
                            VarianteCalepinage._meta.db_table)

    def test_la_variante_3d_ne_porte_aucune_fk_vers_l_ao(self):
        """Les chaînes de migrations restent mono-écrivain (CAL5)."""
        variante_3d = registre.get_model('calepinage', 'CalepinageVariante')
        cibles = {champ.related_model._meta.app_label
                  for champ in variante_3d._meta.get_fields()
                  if getattr(champ, 'related_model', None) is not None}

        self.assertNotIn('ao', cibles)


class LaRegleEstEcrite(SimpleTestCase):
    """Une règle qui ne vit que dans un test n'est lue par personne."""

    def test_le_document_existe(self):
        self.assertTrue(DOC_REGLE.is_file(), f'{DOC_REGLE} est introuvable')

    def test_il_porte_les_quatre_affirmations(self):
        texte = DOC_REGLE.read_text(encoding='utf-8')

        for attendu in ('Préséance', 'OPPOSABLE', 'document de TRAVAIL',
                        'CAL185', 'Aucun modèle n\'est fusionné'):
            self.assertIn(attendu, texte)
