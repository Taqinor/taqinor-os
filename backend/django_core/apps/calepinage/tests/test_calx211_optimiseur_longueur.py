# -*- coding: utf-8 -*-
"""CALX211 — la longueur de chaîne à optimiseurs, fermée SEULEMENT par la fiche.

Avant CALX60, la fiche optimiseur ne publiait que ses bornes d'ENTRÉE : la
longueur de chaîne du système restait « non vérifiable » et le repli prudent
(fenêtre module/onduleur) tenait lieu de réponse. CALX60 a ajouté les deux
champs de SORTIE qui manquaient.

Deux cas, et la frontière est la leçon :

* **fiche complète** (``opt_v_out_nominal_v`` ET ``opt_modules_max_par_chaine``)
  ⇒ la longueur est FERMÉE par la fiche, et la règle DIT laquelle
  (``longueur_source`` cite les deux champs et la désignation du produit) ;
* **fiche partielle** (l'un des deux manque) ⇒ le message « non vérifiable »
  d'aujourd'hui est conservé MOT POUR MOT : une demi-borne n'est pas une
  borne (D-CALX 7).

Aucun chiffre en dur : la borne est celle de la fiche, ou elle n'existe pas.

``SimpleTestCase`` : aucune base.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx211_optimiseur_longueur -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    CHAMP_OPT_MODULES_MAX, CHAMP_OPT_V_OUT, CLE_OPT_MODULES_MAX,
    CLE_OPT_V_OUT, REFERENCE_SOLAREDGE_DESIGNER, REGLE_CHAINE_MODULE,
    REGLE_CHAINE_OPTIMISEUR, _regle_de_chaine,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}

#: La fiche d'avant CALX60 : bornes d'ENTRÉE seulement.
OPTIMISEUR_ENTREE_SEULE = {
    'pmax_in_w': 800.0, 'v_in_min': 12.0, 'v_in_max': 60.0,
    'i_in_max_a': 20.0, 'modules_par_optimiseur': 1,
}

#: La fiche complète : les deux champs de SORTIE sont publiés.
OPTIMISEUR_COMPLET = dict(OPTIMISEUR_ENTREE_SEULE,
                          **{CLE_OPT_V_OUT: 400.0, CLE_OPT_MODULES_MAX: 25})

#: Le texte de repli, repris ici pour prouver qu'il ne bouge PAS.
_MORCEAUX_NON_VERIFIABLE = (
    'longueur de chaîne admissible du système à optimiseurs',
    'la fiche ne publie ni tension de sortie régulée ni nombre maximal '
    'de modules par chaîne',
    'repli PRUDENT',
)


class _FicheObjet:
    """Un double de fiche qui n'est PAS un dict — lecture par ``getattr``."""

    def __init__(self, **champs):
        for nom, valeur in champs.items():
            setattr(self, nom, valeur)


class FicheCompleteTest(SimpleTestCase):
    """Les deux champs publiés : la longueur est fermée, et la règle le dit."""

    def test_la_longueur_est_fermee_par_la_borne_de_la_fiche(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR_COMPLET,
                                 designation='Optimiseur d essai')

        self.assertEqual(regle['regle'], REGLE_CHAINE_OPTIMISEUR)
        self.assertEqual(regle['longueur_max_modules'], 25)

    def test_la_source_cite_les_deux_champs_et_le_produit(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR_COMPLET,
                                 designation='Optimiseur d essai')

        self.assertIn('Optimiseur d essai', regle['longueur_source'])
        self.assertIn(CHAMP_OPT_MODULES_MAX, regle['longueur_source'])
        self.assertIn(CHAMP_OPT_V_OUT, regle['longueur_source'])
        self.assertEqual(regle['longueur_reference'],
                         REFERENCE_SOLAREDGE_DESIGNER)

    def test_plus_aucune_borne_non_verifiable(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR_COMPLET)

        # ACAL662 — seule reste la compatibilité (aucune liste publiée).
        self.assertEqual(len(regle['bornes_non_verifiables']), 1)
        self.assertIn('la fiche ne publie pas de liste',
                      regle['bornes_non_verifiables'][0])

    def test_une_fiche_qui_n_est_pas_un_dict_est_lue_par_getattr(self):
        # ``_champ_de_fiche`` lit le champ par ``getattr`` quand la fiche
        # n'est pas le dict PLAT du sélecteur (double de test, fiche
        # partiellement peuplée) : absent ≡ non publié, jamais zéro.
        from apps.calepinage.services.electrique import _champ_de_fiche

        fiche = _FicheObjet(**{CLE_OPT_V_OUT: 400.0,
                               CLE_OPT_MODULES_MAX: 25})
        self.assertEqual(_champ_de_fiche(fiche, CLE_OPT_MODULES_MAX), 25)
        self.assertIsNone(_champ_de_fiche(fiche, 'champ_absent'))


class FichePartielleTest(SimpleTestCase):
    """Une demi-borne n'est pas une borne : le texte d'avant est conservé."""

    def test_sans_les_deux_champs_le_message_est_inchange(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR, OPTIMISEUR_ENTREE_SEULE)

        # ACAL662 — + la compatibilité non vérifiable (aucune liste).
        self.assertEqual(len(regle['bornes_non_verifiables']), 2)
        for morceau in _MORCEAUX_NON_VERIFIABLE:
            self.assertIn(morceau, regle['bornes_non_verifiables'][0])
        self.assertIsNone(regle['longueur_max_modules'])
        self.assertEqual(regle['longueur_source'], '')

    def test_la_tension_seule_ne_ferme_rien(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR,
                                 dict(OPTIMISEUR_ENTREE_SEULE,
                                      **{CLE_OPT_V_OUT: 400.0}))

        self.assertIsNone(regle['longueur_max_modules'])
        self.assertEqual(len(regle['bornes_non_verifiables']), 2)  # ACAL662

    def test_le_nombre_de_modules_seul_ne_ferme_rien(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR,
                                 dict(OPTIMISEUR_ENTREE_SEULE,
                                      **{CLE_OPT_MODULES_MAX: 25}))

        self.assertIsNone(regle['longueur_max_modules'])
        self.assertEqual(len(regle['bornes_non_verifiables']), 2)  # ACAL662

    def test_un_nombre_de_modules_nul_ne_ferme_rien(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR,
                                 dict(OPTIMISEUR_COMPLET,
                                      **{CLE_OPT_MODULES_MAX: 0}))

        self.assertIsNone(regle['longueur_max_modules'])


class SansOptimiseurTest(SimpleTestCase):
    """Le régime module garde les mêmes clés, toutes à vide."""

    def test_les_cles_de_longueur_sont_presentes_et_nulles(self):
        regle = _regle_de_chaine(MODULE, ONDULEUR, None)

        self.assertEqual(regle['regle'], REGLE_CHAINE_MODULE)
        self.assertIsNone(regle['longueur_max_modules'])
        self.assertEqual(regle['longueur_source'], '')
        self.assertEqual(regle['longueur_reference'], '')


class EntreeMultiModulesTest(SimpleTestCase):
    """ACAL646 — la puissance d'entrée est celle de TOUS les modules de
    l'entrée (modules par optimiseur × fiche) ; tension et courant restent
    comparés module par module."""

    MODULE_220 = dict(MODULE, pmax_wc=220.0)

    def _verdicts(self, optimiseur):
        regle = _regle_de_chaine(self.MODULE_220, ONDULEUR, optimiseur,
                                 designation='Optimiseur d essai')
        return {v['code']: v for v in regle['verdicts_entree']}

    def test_deux_modules_de_220_sur_400_sortent_au_dessus(self):
        verdicts = self._verdicts(dict(OPTIMISEUR_ENTREE_SEULE,
                                       pmax_in_w=400.0,
                                       modules_par_optimiseur=2))
        puissance = verdicts['optimiseur_pmax_in_w']
        self.assertFalse(puissance['conforme'])
        self.assertIn('440 Wc AU-DESSUS DE 400 Wc', puissance['detail'])
        self.assertTrue(verdicts['optimiseur_v_in_max']['conforme'])

    def test_ratio_absent_compare_un_module_et_le_dit(self):
        optimiseur = dict(OPTIMISEUR_ENTREE_SEULE, pmax_in_w=400.0)
        optimiseur.pop('modules_par_optimiseur')
        puissance = self._verdicts(optimiseur)['optimiseur_pmax_in_w']
        self.assertTrue(puissance['conforme'])
        self.assertIn('220 Wc sous 400 Wc', puissance['detail'])
        self.assertIn('un module comparé', puissance['detail'])


class CompatibiliteOnduleurTest(SimpleTestCase):
    """ACAL662 — l'onduleur retenu doit figurer, par son SKU, dans la liste
    des onduleurs compatibles publiée par la fiche de l'optimiseur."""

    def _ligne(self, optimiseur, sku):
        regle = _regle_de_chaine(MODULE, ONDULEUR, optimiseur,
                                 designation='Optimiseur X', onduleur_sku=sku)
        lignes = {v['code']: v for v in regle['verdicts_entree']}
        return lignes['optimiseur_onduleur_compatible'], regle

    def test_onduleur_absent_de_la_liste_bloquant_nomme(self):
        ligne, _r = self._ligne(dict(OPTIMISEUR_COMPLET,
                                     onduleurs_compatibles=['SKU-A']), 'SKU-B')
        self.assertIs(ligne['conforme'], False)
        self.assertTrue(ligne['bloquant'])
        self.assertIn("l'optimiseur Optimiseur X n'est pas déclaré compatible "
                      "avec SKU-B par sa fiche", ligne['detail'])

    def test_onduleur_de_la_liste_conforme_par_sku_jamais_par_nom(self):
        ligne, _r = self._ligne(dict(OPTIMISEUR_COMPLET,
                                     onduleurs_compatibles=['SKU-B']), 'SKU-B')
        self.assertIs(ligne['conforme'], True)
        ligne, _r = self._ligne(dict(OPTIMISEUR_COMPLET, onduleurs_compatibles=[
            'Optimiseur X']), 'SKU-B')
        self.assertIs(ligne['conforme'], False)

    def test_liste_vide_ou_absente_non_verifiable(self):
        for optimiseur in (dict(OPTIMISEUR_COMPLET, onduleurs_compatibles=[]),
                           OPTIMISEUR_COMPLET):
            ligne, regle = self._ligne(optimiseur, 'SKU-B')
            self.assertIsNone(ligne['conforme'])
            self.assertIn('la fiche ne publie pas de liste', ligne['detail'])
            self.assertEqual(len(regle['bornes_non_verifiables']), 1)

    def test_onduleur_sans_sku_non_verifiable(self):
        ligne, _r = self._ligne(dict(OPTIMISEUR_COMPLET,
                                     onduleurs_compatibles=['SKU-A']), None)
        self.assertIsNone(ligne['conforme'])
        self.assertIn('onduleur non désigné', ligne['detail'])
