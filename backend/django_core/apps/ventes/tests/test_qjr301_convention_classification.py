"""QJR301 — UNE seule convention de texte pour classer une ligne.

TEST ROUGE D'ABORD (ronde 3, constat T2). Il y en avait QUATRE, avec des
divergences prouvées dans les DEUX sens :

  1. le noyau classe sur désignation + NOM DU PRODUIT (``options._blob``) ;
  2. les paniers du PDF classaient sur la désignation SEULE
     (``builder._item_classement``) ;
  3. la répartition du PDF avait une troisième lecture (``builder._blob_item``) ;
  4. le garde-fou legacy en portait une quatrième, avec ses propres mots-clés
     en dur, sa propre détection d'onduleur et un ``any`` là où le noyau exige
     ``all`` (``generate_devis_premium._guard_huawei_accessories``).

Conséquences reproduites ici : un mot-clé qui ne vit que dans le NOM du produit
était vu par le noyau et pas par les paniers PDF ; un panier mixte Huawei +
Deye était jugé « Huawei » par le legacy et « non-Huawei » par le noyau.

Et le prédicat lui-même laissait passer ``wi-fi`` avec trait d'union.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr301_convention_classification"
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import builder
from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.utils.options import (
    _blob, _blob_marque, est_accessoire_huawei, retirer_accessoires_huawei,
    texte_classement, texte_marque,
)


class _Produit:
    def __init__(self, nom='', marque=''):
        self.nom = nom
        self.marque = marque


class _Ligne:
    """Une ``LigneDevis`` minimale — la convention de texte est pure."""

    def __init__(self, designation='', produit_nom='', produit_marque=''):
        self.designation = designation
        self.produit = _Produit(produit_nom, produit_marque)


def _item(designation='', produit_nom='', marque=''):
    return {'designation': designation, 'marque': marque,
            '_produit_nom': produit_nom, 'quantite': 1,
            'prix_unit_ht': 1000.0, 'prix_unit_ttc': 1200.0,
            'taux_tva': 20.0}


class UneSeuleDefinitionDuTexte(SimpleTestCase):
    """Les adaptateurs rendent le MÊME texte, par la MÊME fonction."""

    def test_l_adaptateur_ligne_et_l_adaptateur_item_concordent(self):
        ligne = _Ligne('Accessoire monitoring', 'Smart Meter DTSU666', 'Huawei')
        item = _item('Accessoire monitoring', 'Smart Meter DTSU666', 'Huawei')
        self.assertEqual(_blob(ligne), builder._item_classement(item))
        self.assertEqual(_blob_marque(ligne), builder._item_marque(item))

    def test_la_repartition_lit_le_meme_texte_que_les_paniers(self):
        """``_blob_item`` était la TROISIÈME lecture : c'est le MÊME texte."""
        self.assertIs(builder._blob_item, builder._item_classement)

    def test_les_deux_conventions_sont_celles_du_noyau(self):
        self.assertEqual(texte_classement('A', 'B'), 'A B')
        self.assertEqual(texte_marque('A', 'B', 'C'), 'A B C')


class LeMotCleVitDansLeNomDuProduit(SimpleTestCase):
    """(1) et (2) — ROUGE AVANT : le PDF ne lisait que la désignation."""

    def test_accessoire_nomme_seulement_par_le_produit(self):
        ligne = _Ligne('Accessoire monitoring', 'Smart Meter DTSU666')
        item = _item('Accessoire monitoring', 'Smart Meter DTSU666')
        self.assertTrue(est_accessoire_huawei(_blob(ligne)))
        self.assertTrue(
            est_accessoire_huawei(builder._item_classement(item)),
            'le panier PDF doit classer cette ligne comme le noyau')

    def test_onduleur_nomme_seulement_par_le_produit(self):
        ligne = _Ligne('Équipement principal', 'Onduleur hybride Deye 8kW')
        item = _item('Équipement principal', 'Onduleur hybride Deye 8kW')
        self.assertTrue(builder._is_inverter(_blob(ligne)))
        self.assertTrue(
            builder._is_inverter(builder._item_classement(item)),
            'le panier PDF doit voir cet onduleur comme le noyau')


class PanierMixteTrancheSurAll(SimpleTestCase):
    """(3) — ROUGE AVANT : le legacy disait « Huawei » (``any``), le noyau
    « non-Huawei » (``all``, le PREMIER onduleur étranger suffit)."""

    ROWS = [
        _item('Onduleur réseau Huawei 10kW', marque='Huawei'),
        _item('Onduleur hybride Deye 10kW', marque='Deye'),
        _item('Smart Meter'),
    ]

    def test_le_noyau_retire_l_accessoire(self):
        garde = retirer_accessoires_huawei(
            list(self.ROWS), classement=builder._item_classement,
            marque=builder._item_marque)
        self.assertNotIn('Smart Meter',
                         [it['designation'] for it in garde])

    def test_le_moteur_de_rendu_ne_reclasse_plus(self):
        """QJR408 — le garde-fou legacy est SUPPRIMÉ : il reclassait après le
        retrait de ``_produit_nom``, donc sur la désignation seule. Il ne reste
        qu'une passe, celle du builder — épinglée juste au-dessus."""
        self.assertFalse(hasattr(moteur, '_guard_huawei_accessories'))

    def test_un_panier_tout_huawei_garde_son_accessoire(self):
        rows = [_item('Onduleur réseau Huawei 10kW', marque='Huawei'),
                _item('Smart Meter')]
        garde = retirer_accessoires_huawei(
            rows, classement=builder._item_classement,
            marque=builder._item_marque)
        self.assertIn('Smart Meter', [it['designation'] for it in garde])


class WiFiAvecTraitDUnion(SimpleTestCase):
    """(4) — ROUGE AVANT : ``"wifi" in d`` ratait toutes ces orthographes."""

    def test_les_orthographes_usuelles_sont_reconnues(self):
        for texte in ('Passerelle Wi-Fi Deye', 'CLÉ WI-FI', 'Module wi fi',
                      'Clé Wifi (dongle)', 'Wifi Dongle'):
            self.assertTrue(est_accessoire_huawei(texte), texte)

    def test_aucun_faux_positif_sur_les_autres_familles(self):
        for texte in ('Onduleur hybride Deye 10kW', 'Panneau mono 550W',
                      'Batterie Dyness 10 kWh', 'Structures acier'):
            self.assertFalse(est_accessoire_huawei(texte), texte)
