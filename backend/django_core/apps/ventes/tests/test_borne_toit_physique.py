"""LA BORNE DE TOIT, EN UN SEUL ENDROIT (ordre fondateur, 28/08/2026).

CE QUE CES TESTS PROTÈGENT.

Un devis AUTOMATIQUE naît avec un layout CONTOUR-SEUL
(``services.zone_toit_depuis_contour``) : le tracé du client y est recopié,
mais AUCUN panneau n'y est sérialisé et ``result.panels`` n'y porte que la
CIBLE VENDUE. Deux conséquences, et c'est tout le bug :

* rien n'y est mesurable — ``calepinage_options.capacite_toit_du_devis`` rend
  ``None`` ;
* l'ancienne règle retombait alors sur le compte DESSINÉ, c'est-à-dire sur ce
  qu'on venait de vendre. « Ce toit accepte exactement ce que je vous vends » :
  Max valait Recommandé, la troisième carte s'effondrait sur TOUS les devis
  automatiques, et la simple présence du layout court-circuitait en plus le
  repli « dernière taille éligible du balayage ».

La règle corrigée vit ici, et NULLE PART AILLEURS
(``dimensionnement.plus_grande_contenance``) : la contenance MESURÉE commande ;
à défaut, la seule borne honnête est le MUR PHYSIQUE du tracé (aire ÷ empreinte
d'un panneau) ; le dessin ne borne plus rien — il reste la cible de
resynchronisation.

Aucun accès base : la mécanique seule, sur des devis factices.
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import dimensionnement as dim


def _zone(*sommets):
    return {'vertices': [list(p) for p in sommets]}


CARRE = ((-7.58, 33.57), (-7.579, 33.57), (-7.579, 33.571), (-7.58, 33.571))


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA RÈGLE — « ce toit accepte N panneaux »
# ═══════════════════════════════════════════════════════════════════════════

class PlusGrandeContenanceTests(SimpleTestCase):

    def test_la_contenance_mesuree_commande(self):
        self.assertEqual(dim.plus_grande_contenance(28, None, None), 28)

    def test_le_dessin_reste_un_PLANCHER_sous_la_contenance(self):
        # Un layout dont le ``result.panels`` déclaré dépasse les panneaux
        # réellement sérialisés : on ne RÉTRÉCIT pas une borne qui existait.
        self.assertEqual(dim.plus_grande_contenance(24, 30, None), 30)

    def test_le_mur_physique_ne_gonfle_JAMAIS_une_contenance_mesuree(self):
        # La géométrie a parlé : le mur (large par construction) ne la
        # contredit pas. Une carte ne doit jamais annoncer un nombre que son
        # propre calepinage ne saurait dessiner.
        self.assertEqual(dim.plus_grande_contenance(24, None, 90), 24)

    def test_LE_BUG_le_dessin_seul_ne_borne_plus_rien(self):
        # LA CORRECTION, ARMÉE. Sans mesure, le compte DESSINÉ (= la cible
        # vendue sur un devis automatique) ne vaut plus un plafond de toit.
        self.assertIsNone(dim.plus_grande_contenance(None, 22, None))

    def test_sans_mesure_c_est_le_mur_physique_et_lui_seul(self):
        self.assertEqual(dim.plus_grande_contenance(None, 22, 60), 60)

    def test_rien_du_tout_aucune_borne_de_toit(self):
        self.assertIsNone(dim.plus_grande_contenance(None, None, None))
        self.assertIsNone(dim.plus_grande_contenance(0, 0, 0))


# ═══════════════════════════════════════════════════════════════════════════
# 2. LE TRACÉ — deux sources réelles, aucune géométrie inventée
# ═══════════════════════════════════════════════════════════════════════════

class ContourDuDevisTests(SimpleTestCase):

    def test_les_zones_du_layout_sont_la_source_prioritaire(self):
        devis = SimpleNamespace(roof_layout={'zones': [_zone(*CARRE)]},
                                lead=None)
        self.assertEqual(dim.contour_du_devis_lnglat(devis),
                         [[list(p) for p in CARRE]])

    def test_plusieurs_zones_sont_TOUTES_rendues(self):
        devis = SimpleNamespace(
            roof_layout={'zones': [_zone(*CARRE), _zone(*CARRE)]}, lead=None)
        self.assertEqual(len(dim.contour_du_devis_lnglat(devis)), 2)

    def test_un_anneau_de_moins_de_trois_sommets_est_ECARTE(self):
        # Un polygone commence à trois sommets — on n'en répare aucun.
        devis = SimpleNamespace(
            roof_layout={'zones': [_zone(*CARRE[:2])]}, lead=None)
        self.assertEqual(dim.contour_du_devis_lnglat(devis), [])

    def test_un_sommet_illisible_est_ecarte_sans_faire_tomber_la_zone(self):
        zone = _zone(*CARRE)
        zone['vertices'].append(['nord', 'ouest'])
        devis = SimpleNamespace(roof_layout={'zones': [zone]}, lead=None)
        self.assertEqual(dim.contour_du_devis_lnglat(devis),
                         [[list(p) for p in CARRE]])

    def test_le_repli_est_le_TRACE_DU_LEAD(self):
        # Convention ``Lead.roof_outline`` = ``[lat, lng]`` ; la sortie est en
        # ``[lng, lat]`` — c'est ``services.contour_client_lnglat`` qui le dit,
        # on ne réécrit pas la conversion ici.
        lead = SimpleNamespace(roof_outline=[[lat, lng] for lng, lat in CARRE])
        devis = SimpleNamespace(roof_layout=None, lead=lead)
        self.assertEqual(dim.contour_du_devis_lnglat(devis),
                         [[list(p) for p in CARRE]])

    def test_ni_layout_ni_lead_aucun_contour(self):
        devis = SimpleNamespace(roof_layout=None, lead=None)
        self.assertEqual(dim.contour_du_devis_lnglat(devis), [])


# ═══════════════════════════════════════════════════════════════════════════
# 3. LE MUR PHYSIQUE — délégué, sommé, mémoïsé, jamais deviné
# ═══════════════════════════════════════════════════════════════════════════

class PlafondPhysiqueDuDevisTests(SimpleTestCase):

    def _devis(self, zones=1):
        return SimpleNamespace(
            roof_layout={'zones': [_zone(*CARRE) for _ in range(zones)]},
            lead=None, company=None)

    def test_il_DELEGUE_la_formule_de_surface(self):
        # Aucune seconde formule d'aire ici : c'est
        # ``services.plafond_physique_du_contour`` qui prononce le nombre.
        with mock.patch('apps.ventes.services._panneau_pour_calepinage',
                        return_value=(object(), None)), \
                mock.patch('apps.ventes.services.plafond_physique_du_contour',
                           return_value=40) as borne:
            self.assertEqual(dim.plafond_physique_du_devis(self._devis()), 40)
        self.assertEqual(borne.call_count, 1)

    def test_plusieurs_zones_se_SOMMENT(self):
        # Chaque zone est un morceau de toit réel : deux pans portent la somme
        # de leurs plafonds, jamais le plus grand des deux.
        with mock.patch('apps.ventes.services._panneau_pour_calepinage',
                        return_value=(object(), None)), \
                mock.patch('apps.ventes.services.plafond_physique_du_contour',
                           return_value=40):
            self.assertEqual(dim.plafond_physique_du_devis(self._devis(2)), 80)

    def test_sans_contour_aucun_mur(self):
        devis = SimpleNamespace(roof_layout=None, lead=None, company=None)
        self.assertIsNone(dim.plafond_physique_du_devis(devis))

    def test_un_panneau_sans_fiche_technique_ne_vaut_AUCUN_mur(self):
        # ``plafond_physique_du_contour`` rend ``None`` dès qu'une dimension
        # manque : un mur inventé serait pire que pas de mur.
        with mock.patch('apps.ventes.services._panneau_pour_calepinage',
                        return_value=(None, None)), \
                mock.patch('apps.ventes.services.plafond_physique_du_contour',
                           return_value=None):
            self.assertIsNone(dim.plafond_physique_du_devis(self._devis()))

    def test_une_lecture_qui_LEVE_ne_vaut_aucun_mur(self):
        with mock.patch('apps.ventes.services._panneau_pour_calepinage',
                        side_effect=RuntimeError('catalogue indisponible')):
            self.assertIsNone(dim.plafond_physique_du_devis(self._devis()))

    def test_le_resultat_est_MEMOISE_sur_l_instance(self):
        # L'endpoint public n'est pas caché : il interroge la borne une fois
        # par carte ET par variante. Une seule lecture catalogue, pas sept.
        devis = self._devis()
        with mock.patch('apps.ventes.services._panneau_pour_calepinage',
                        return_value=(object(), None)) as panneau, \
                mock.patch('apps.ventes.services.plafond_physique_du_contour',
                           return_value=40):
            for _ in range(3):
                self.assertEqual(dim.plafond_physique_du_devis(devis), 40)
        self.assertEqual(panneau.call_count, 1)
