"""QJR424 — IL NE RESTE QU'UNE DÉFINITION DU TEXTE DE CLASSEMENT.

Le ``Done =`` de QJR301 exigeait qu'il n'existe plus qu'une convention de
texte pour classer une ligne (``apps.ventes.utils.options.texte_classement``,
QF ``_blob``/``_blob_marque``). Un ``grep`` montrait qu'il en subsistait
trois copies VIVANTES hors tests :

  1. ``electrical_service._blob_ligne`` — ``"%s %s" % (designation, nom)`` ;
  2. ``quote_engine.residential.theme.warranties_for._nom`` —
     ``f"{it.get('designation','')} {it.get('_produit_nom','')}"`` ;
  3. ``solar_design.is_panel`` — ``f"{designation} {produit_nom}".lower()``.

Ce module est un DÉPLACEMENT PUR (règle permanente 1) : les trois sites
IMPORTENT désormais ``texte_classement`` au lieu de recopier sa logique ; leur
comportement de classement est vérifié IDENTIQUE à l'octet, avant/après,
sur un jeu de lignes couvrant désignation muette, nom muet, et les deux
renseignés. Restent HORS PÉRIMÈTRE, volontairement : la copie gelée de
``migrations/0109_qjr212_...`` (hygiène de migration voulue, requalifiée en
ronde 3) et ``domain/lignes.py`` (``_classe_ligne``, qui applique son
prédicat séparément à la désignation OU au nom — une sémantique DIFFÉRENTE,
jamais fusionnée à l'aveugle avec celle-ci).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr424_une_seule_definition_classement"
"""
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import electrical_service
from apps.ventes import solar_design as sd
from apps.ventes.quote_engine.residential import theme
from apps.ventes.utils.options import texte_classement

# Les trois formes couvertes par CHAQUE test de ce module (Done de QJR424) :
# désignation muette, nom muet, les deux renseignés.
DESIGNATION_MUETTE = ('', 'Onduleur hybride Deye 8kW')
NOM_MUET = ('Onduleur hybride principal', '')
LES_DEUX_RENSEIGNES = ('Équipement principal', 'Onduleur hybride Deye 8kW')
CAS = (DESIGNATION_MUETTE, NOM_MUET, LES_DEUX_RENSEIGNES)


class _Produit:
    def __init__(self, nom=''):
        self.nom = nom


class _Ligne:
    """``LigneDevis`` minimale — assez pour ``_blob_ligne`` (getattr seul)."""

    def __init__(self, designation='', produit_nom=''):
        self.designation = designation
        self.produit = _Produit(produit_nom)


class UnGrepConfirmeUneSeuleDefinitionVivante(SimpleTestCase):
    """Preuve STRUCTURELLE (lecture de source) : les trois anciennes copies
    ont disparu, remplacées par un import de la primitive canonique."""

    @staticmethod
    def _lire(chemin_relatif):
        racine_ventes = Path(electrical_service.__file__).resolve().parent
        return (racine_ventes / chemin_relatif).read_text(encoding='utf-8')

    def test_electrical_service_importe_texte_classement_et_a_supprime_sa_copie(self):
        source = self._lire('electrical_service.py')
        self.assertIn(
            'from apps.ventes.utils.options import texte_classement', source)
        self.assertIn('texte_classement(ligne.designation', source)
        # L'ANCIENNE copie locale a disparu — plus de formatage `%s %s` recopié.
        self.assertNotIn('"%s %s" % (designation, nom)', source)

    def test_theme_importe_texte_classement_et_a_supprime_sa_copie(self):
        source = self._lire('quote_engine/residential/theme.py')
        self.assertIn(
            'from apps.ventes.utils.options import texte_classement', source)
        self.assertIn(
            "texte_classement(it.get('designation', ''), "
            "it.get('_produit_nom', ''))", source)
        # L'ANCIENNE copie locale (f-string recopiée) a disparu.
        self.assertNotIn(
            "f\"{it.get('designation', '')} {it.get('_produit_nom', '')}\"",
            source)

    def test_solar_design_importe_texte_classement_et_a_supprime_sa_copie(self):
        source = self._lire('solar_design.py')
        self.assertIn(
            'from apps.ventes.utils.options import texte_classement', source)
        self.assertIn('texte_classement(designation, produit_nom).lower()',
                      source)
        # L'ANCIENNE copie locale (f-string recopiée) a disparu.
        self.assertNotIn('f"{designation} {produit_nom}".lower()', source)

    def test_le_perimetre_exclu_reste_intact(self):
        """``domain/lignes.py`` (sémantique DIFFÉRENTE, prédicat séparé sur
        désignation OU nom) n'importe PAS ``texte_classement`` — cette tâche
        ne l'a pas touché, et ne devait pas le toucher."""
        source = self._lire('domain/lignes.py')
        self.assertNotIn('texte_classement', source)
        self.assertIn('_classe_ligne', source)


class ElectricalServiceBlobLigneEstIdentiqueAuNoyau(SimpleTestCase):
    """``_blob_ligne`` rend EXACTEMENT ``texte_classement`` — pas un texte
    voisin, le MÊME, sur les trois formes couvertes par le Done."""

    def test_les_trois_formes(self):
        for designation, produit_nom in CAS:
            with self.subTest(designation=designation, produit_nom=produit_nom):
                ligne = _Ligne(designation, produit_nom)
                self.assertEqual(
                    electrical_service._blob_ligne(ligne),
                    texte_classement(designation, produit_nom))


class SolarDesignIsPanelClasseIdentiquementSurLesTroisFormes(SimpleTestCase):
    """``is_panel`` doit reconnaître le mot-clé qu'il vive dans la désignation,
    dans le nom du produit lié, ou dans les deux — la fusion par
    ``texte_classement`` doit rester intacte."""

    def test_designation_muette_mot_cle_dans_le_nom_produit(self):
        self.assertTrue(sd.is_panel('', 'Panneau Canadian Solar 710W'))

    def test_nom_muet_mot_cle_dans_la_designation(self):
        self.assertTrue(sd.is_panel('Panneau 710W', ''))

    def test_les_deux_renseignes(self):
        self.assertTrue(sd.is_panel('Panneau', 'Canadian Solar 710W'))

    def test_controle_negatif_inchange(self):
        """Non-régression : un onduleur n'est toujours PAS un panneau."""
        self.assertFalse(sd.is_panel('Onduleur réseau', ''))
        self.assertFalse(sd.is_panel('', 'Onduleur réseau Huawei 10kW'))


class ThemeNomClasseIdentiquementSurLesTroisFormes(SimpleTestCase):
    """``warranties_for`` (via son ``_nom`` interne) reconnaît l'onduleur de
    la composition qu'il soit nommé par la désignation, par le produit lié,
    ou par les deux — même garantie fabricant rendue dans les trois cas."""

    def _rend_garantie_onduleur(self, designation, produit_nom):
        rows = theme.warranties_for({'items': [
            {'designation': designation, '_produit_nom': produit_nom,
             'garantie_mois': 84},
        ]})
        return next((r for r in rows if r[2] == 'Onduleur'), None)

    def test_les_trois_formes_rendent_la_meme_garantie(self):
        for designation, produit_nom in CAS:
            with self.subTest(designation=designation, produit_nom=produit_nom):
                garantie = self._rend_garantie_onduleur(designation, produit_nom)
                self.assertIsNotNone(
                    garantie,
                    f"l'onduleur ({designation!r}, {produit_nom!r}) doit être "
                    "reconnu et porter sa garantie fabricant")
                self.assertEqual(garantie, ('7', 'ans', 'Onduleur', 'garantie fabricant'))

    def test_controle_negatif_batterie_seule_ne_declenche_pas_onduleur(self):
        rows = theme.warranties_for({'items': [
            {'designation': 'Batterie', '_produit_nom': 'Dyness 10 kWh',
             'garantie_mois': 84},
        ]})
        self.assertIsNone(next((r for r in rows if r[2] == 'Onduleur'), None))
