"""ACAL264 — le module de CHAQUE pan fait le kWc, les chaînes et la simulation.

Constat C-ACAL-042 : ``bloc_pose`` multipliait TOUS les modules par le seul
``module_produit`` de l'entrée — deux pans de 10 modules à 550 Wc et 400 Wc
faisaient 11,0 kWc au lieu de 9,5, et le pan B était chaîné avec la fiche du
550 (tensions fausses).

Désormais chaque pan porte SON module (``PanPose.module``, fiche lue par le
sélecteur du stock) ; ``module_produit`` n'est plus que le défaut d'un pan
sans module. Un champ à plusieurs modèles est chaîné modèle par modèle, sur
des entrées MPPT disjointes : aucune chaîne ne mélange deux modules.

Test-du-test : revenir à un seul ``module.pmax_wc`` dans ``bloc_pose`` rend
11,0 et fait échouer ``test_bloc_pose_kwc_par_module``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_module_par_pan -v2
"""
from __future__ import annotations

import copy
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.chaines import bloc_pose, concevoir_par_pan
from apps.calepinage.services.electrique import (
    CLE_ENTREE, conception_du_calepinage, temperatures_site,
)
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis

from .test_api_liste import BaseApiCalepinage

FICHE_550 = {'vmp_v': 41.6, 'voc_v': 49.8, 'isc_a': 14.0, 'imp_a': 13.2,
             'pmax_wc': 550.0, 'temp_coeff_voc_pct_c': -0.27,
             'temp_coeff_pmax_pct_c': -0.35}
FICHE_400 = {'vmp_v': 34.0, 'voc_v': 41.0, 'isc_a': 12.5, 'imp_a': 11.8,
             'pmax_wc': 400.0, 'temp_coeff_voc_pct_c': -0.29,
             'temp_coeff_pmax_pct_c': -0.37}
ONDULEUR = {'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
            'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0,
            'phases': 3}


def _layout(produit_550=1, produit_400=2):
    return {
        'version': 2,
        'modules': [
            {'id': 'm550', 'produitId': produit_550, 'pmaxWc': 550,
             'libelle': 'Module 550'},
            {'id': 'm400', 'produitId': produit_400, 'pmaxWc': 400,
             'libelle': 'Module 400'},
        ],
        'zones': [
            {'id': 'A', 'label': 'A', 'facingAzimuthDeg': 180.0,
             'pitchDeg': 15.0, 'geometry': {'count': 10, 'moduleId': 'm550'}},
            {'id': 'B', 'label': 'B', 'facingAzimuthDeg': 90.0,
             'pitchDeg': 15.0, 'geometry': {'count': 10, 'moduleId': 'm400'}},
        ],
    }


def _temperatures():
    return temperatures_site(
        saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0})


def _concevoir(layout, fiches_modules=None):
    return concevoir_par_pan(
        layout, module_specs=FICHE_550, onduleur_specs=ONDULEUR,
        temperatures=_temperatures(), module_designation='Module 550',
        onduleur_designation='Onduleur 10 kW',
        fiches_modules=fiches_modules)


FICHES = {2: {'specs': FICHE_400, 'designation': 'Module 400'}}


class ModuleParPanTest(SimpleTestCase):

    def test_bloc_pose_kwc_par_module(self):
        pose = bloc_pose(_concevoir(_layout(), FICHES))

        self.assertEqual([(p['pan'], p['kwc']) for p in pose['pans']],
                         [('A', 5.5), ('B', 4.0)])
        self.assertEqual(pose['kwc'], 9.5)
        self.assertNotEqual(pose['kwc'], 11.0)
        self.assertEqual(pose['total_modules'], 20)
        # Deux puissances : aucun nombre unique n'est vrai.
        self.assertIsNone(pose['puissance_module_wc'])
        self.assertEqual([p['module_id'] for p in pose['pans']],
                         ['m550', 'm400'])

    def test_sans_fiche_resolue_la_puissance_du_document(self):
        # Produit non résolu : le pan garde ``modules[].pmaxWc`` du document,
        # jamais le module par défaut.
        pose = bloc_pose(_concevoir(_layout()))
        self.assertEqual(pose['kwc'], 9.5)

    def test_pan_sans_fiche_resolue_alerte_nommee(self):
        # ACAL358 (C-ACAL-VER-005) — module saisi à la main : plus de
        # chaînage silencieux avec la fiche par défaut.
        layout = _layout(produit_400=None)
        layout['modules'][1]['libelle'] = 'M400 saisi'
        alertes = _concevoir(layout).alertes
        self.assertTrue(any(
            'Pan « B »' in a and 'M400 saisi' in a and 'sans fiche' in a
            and 'Module 550' in a for a in alertes), alertes)
        # Un produit désigné mais introuvable / d'une autre société.
        conception = concevoir_par_pan(
            _layout(), module_specs=FICHE_550, onduleur_specs=ONDULEUR,
            temperatures=_temperatures(), module_designation='Module 550',
            onduleur_designation='Onduleur 10 kW', produits_sans_fiche=(2,))
        self.assertTrue(any('Pan « B »' in a and 'sans fiche' in a
                            for a in conception.alertes), conception.alertes)
        # Module par défaut ou fiche résolue : aucune alerte nouvelle.
        for alertes in (_concevoir(_layout(), FICHES).alertes,
                        _concevoir(_layout()).alertes):
            self.assertFalse(any('sans fiche' in a for a in alertes),
                             alertes)

    def test_entree_servie_liste_le_module_de_chaque_pan(self):
        # ACAL359 — ``materiel.modules_par_pan`` : un module par pan, dans
        # l'ordre du document, avec l'état de sa fiche (cas du module saisi
        # sans fiche ; la fiche du stock réel est lue par le test suivant).
        from apps.calepinage.services.electrique import (
            entree_electrique_servie,
        )

        class Nu:
            pk = 1
            company = None
            devis_id = None
            resultat = None
            roof_layout = _layout(produit_400=None)

        Nu.roof_layout['modules'][1]['libelle'] = 'M400 saisi'
        servi = entree_electrique_servie(Nu(), {})
        self.assertEqual(
            [(p['pan'], p['module_id'], p['fiche_resolue'])
             for p in servi['materiel']['modules_par_pan']],
            [('A', 'm550', False), ('B', 'm400', False)])
        self.assertEqual(
            servi['materiel']['modules_par_pan'][1]['designation'], 'M400 saisi')

    def test_champ_mono_module_inchange(self):
        layout = copy.deepcopy(_layout())
        layout['zones'][1]['geometry']['moduleId'] = 'm550'
        pose = bloc_pose(_concevoir(layout))
        self.assertEqual(pose['kwc'], 11.0)
        self.assertEqual(pose['puissance_module_wc'], 550.0)

    def test_chaine_ne_melange_pas_deux_modules(self):
        conception = _concevoir(_layout(), FICHES)

        self.assertFalse(conception.fiche_incomplete, conception.manquantes)
        self.assertTrue(conception.chaines)
        vmp_du_pan = {'A': FICHE_550['vmp_v'], 'B': FICHE_400['vmp_v']}
        mppt_du_pan = {}
        for chaine in conception.chaines:
            # La tension STC de la chaîne est celle de SON module, jamais
            # celle de l'autre pan.
            self.assertAlmostEqual(chaine.vmp_stc_v,
                                   chaine.nb_modules * vmp_du_pan[chaine.pan],
                                   places=6)
            mppt_du_pan.setdefault(chaine.pan, set()).add(chaine.mppt)
        # Deux modèles ne partagent jamais une entrée MPPT.
        self.assertFalse(mppt_du_pan['A'] & mppt_du_pan['B'])
        # Une seule numérotation des chaînes.
        reperes = [c.repere for c in conception.chaines]
        self.assertEqual(len(reperes), len(set(reperes)))
        # L'écart de module est PUBLIÉ en nommant le pan.
        self.assertTrue(any('Pan « B »' in a and 'Module 400' in a
                            for a in conception.alertes), conception.alertes)


class PlancheDuModulePoseTest(SimpleTestCase):
    """R7-N2 (module posé) — défaut du 26/11 : la planche NOMMAIT le module posé
    (ACAL1910) mais imprimait la puissance du défaut (« 7 × 710 Wc » sous 715 W
    posés). Le module de la planche porte maintenant le nom ET la puissance de la
    même fiche ; les chaînes, ``bloc_pose`` et ``materiel`` ne bougent pas.
    Vraies fonctions : ``concevoir_par_pan``, ``_nommer_module_pose``,
    ``resultat_electrique_complet``, ``document_schema_electrique``,
    ``rendre_schema_electrique_svg``."""

    MATERIEL = {'module': FICHE_550, 'designations': {'module': 'Module 550'}, 'fiches_modules': FICHES}

    @staticmethod
    def _svg(conception):
        from apps.calepinage.services.electrique import resultat_electrique_complet
        from core.electrique.schema_electrique import (
            document_schema_electrique, rendre_schema_electrique_svg)

        return rendre_schema_electrique_svg(document_schema_electrique(
            conception.entree, resultat_electrique_complet(conception)))

    def _planche(self, layout, materiel=None):
        from apps.calepinage.services.electrique import _nommer_module_pose

        materiel = materiel or self.MATERIEL
        conception = _concevoir(layout, materiel['fiches_modules'] and FICHES)
        return conception, _nommer_module_pose(conception, materiel, layout)

    def test_le_defaut_pose_nulle_part_la_planche_dit_le_module_pose(self):
        layout = _layout()
        layout['zones'][0]['geometry']['moduleId'] = 'm400'  # tout le toit en 400, défaut 550
        avant, planche = self._planche(layout)
        self.assertRegex(self._svg(avant), r'550(,0)? Wc')  # le défaut du 26/11
        self.assertEqual((planche.entree.module.designation, planche.entree.module.pmax_wc),
                         ('Module 400', 400.0))
        svg = self._svg(planche)
        self.assertRegex(svg, r'400(,0)? Wc')
        self.assertNotRegex(svg, r'550(,0)? Wc')
        # Les chaînes et la pose sont celles calculées avant le renommage.
        self.assertEqual(planche.chaines, avant.chaines)
        self.assertEqual(bloc_pose(planche)['pans'], bloc_pose(avant)['pans'])
        self.assertEqual(self.MATERIEL['module'], FICHE_550)

    def test_toit_mixte_nom_et_puissance_du_meme_module_dominant(self):
        layout = _layout()
        layout['zones'][1]['geometry']['count'] = 13  # 13 × 400 contre 10 × 550
        avant, planche = self._planche(layout)
        self.assertEqual((planche.entree.module.designation, planche.entree.module.pmax_wc),
                         ('Module 400', 400.0))
        self.assertEqual(bloc_pose(planche)['pans'], bloc_pose(avant)['pans'])
        # Égalité (10/10) : le défaut reste, rien n'est renommé.
        egal, inchange = self._planche(_layout())
        self.assertIs(inchange, egal)

    def test_fiche_posee_sans_puissance_la_ligne_d_aujourd_hui(self):
        sans_pmax = {c: v for c, v in FICHE_400.items() if c != 'pmax_wc'}
        materiel = dict(self.MATERIEL, fiches_modules={2: {'specs': sans_pmax, 'designation': 'Module 400'}})
        layout = _layout()
        layout['zones'][1]['geometry']['count'] = 13
        _avant, planche = self._planche(layout, materiel)
        self.assertEqual((planche.entree.module.designation, planche.entree.module.pmax_wc),
                         ('Module 400', 550.0))

    def test_pan_sans_module_garde_la_puissance_du_defaut(self):
        layout = _layout()
        layout['zones'][1]['geometry']['count'] = 20  # 20 × 400 contre 10 + 4 au défaut
        layout['zones'].append({'id': 'C', 'label': 'C', 'facingAzimuthDeg': 180.0,
                                'pitchDeg': 15.0, 'geometry': {'count': 4}})
        avant, planche = self._planche(layout)
        self.assertEqual([pan.label for pan in avant.pans if pan.module is None], ['C'])
        self.assertEqual((planche.entree.module.designation, planche.entree.module.pmax_wc),
                         ('Module 400', 550.0))
        self.assertEqual(bloc_pose(planche)['pans'], bloc_pose(avant)['pans'])

    def test_sans_pan_d_un_autre_produit_rien_ne_change(self):
        layout = copy.deepcopy(_layout())
        layout['zones'][1]['geometry']['moduleId'] = 'm550'
        materiel = dict(self.MATERIEL, fiches_modules={})
        avant, planche = self._planche(layout, materiel)
        self.assertIs(planche, avant)


class ModuleParPanStockReelTest(BaseApiCalepinage):
    """Fiches RÉELLES du stock, lues par le sélecteur — aucun mock."""

    def _produit(self, nom, type_fiche, **champs):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL264-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(company=self.company, produit=produit,
                                      type_fiche=type_fiche, **champs)
        return produit

    def test_entree_servie_liste_le_module_de_chaque_pan(self):
        # ACAL359 — fiches RÉELLES : A = fiche 550 (défaut du devis), B =
        # fiche 400 du stock ; puis B au module saisi sans fiche.
        from apps.calepinage.services.electrique import (
            entree_electrique_servie,
        )

        cles = ('vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc')
        m550 = self._produit('Module 550', 'module',
                             **{c: FICHE_550[c] for c in cles})
        m400 = self._produit('Module 400', 'module',
                             **{c: FICHE_400[c] for c in cles})
        devis = Devis.objects.create(company=self.company,
                                     client=self.client_a,
                                     reference='DEV-ACAL359-1')
        LigneDevis.objects.create(
            devis=devis, produit=m550, designation=m550.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('100'),
            type_ligne='produit', variante='')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=devis, titre='ACAL359',
            roof_layout=_layout(produit_550=m550.pk, produit_400=m400.pk))

        pans = entree_electrique_servie(
            calepinage, {})['materiel']['modules_par_pan']
        self.assertEqual([p['pan'] for p in pans], ['A', 'B'])
        self.assertEqual([p['produit_id'] for p in pans], [m550.pk, m400.pk])
        self.assertTrue(all(p['fiche_resolue'] for p in pans))
        self.assertEqual(pans[1]['designation'], m400.nom.strip())

        calepinage.roof_layout = _layout(produit_550=m550.pk,
                                         produit_400=None)
        calepinage.roof_layout['modules'][1]['libelle'] = 'M400 saisi'
        pans = entree_electrique_servie(
            calepinage, {})['materiel']['modules_par_pan']
        self.assertTrue(pans[0]['fiche_resolue'])
        self.assertFalse(pans[1]['fiche_resolue'])
        self.assertEqual(pans[1]['designation'], 'M400 saisi')

    def test_bloc_pose_kwc_par_module_stock_reel(self):
        m550 = self._produit('Module 550', 'module', **{
            cle: FICHE_550[cle] for cle in
            ('vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc')})
        m400 = self._produit('Module 400', 'module', **{
            cle: FICHE_400[cle] for cle in
            ('vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc')})
        onduleur = self._produit(
            'Onduleur 10 kW', 'onduleur', ond_n_mppt=2, ond_mppt_v_min=150.0,
            ond_mppt_v_max=800.0, ond_v_max_abs=1000.0,
            ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3)
        devis = Devis.objects.create(company=self.company,
                                     client=self.client_a,
                                     reference='DEV-ACAL264-1')
        for produit in (m550, onduleur):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                type_ligne='produit', variante='')
        # ACAL2013 — le module et l'onduleur par défaut viennent de la conception du lead.
        from .test_acal_cible_lead import ranger_conception
        ranger_conception(lead=self.lead, nb=20, module=m550.nom, module_produit=m550.pk, onduleur={
            'produit': onduleur.pk, 'designation': onduleur.nom, 'quantite': 1})
        layout = _layout(produit_550=m550.pk, produit_400=m400.pk)
        # Le document recopie une puissance FAUSSE pour B : la fiche du stock
        # prime.
        layout['modules'][1]['pmaxWc'] = 999
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=devis, titre='ACAL264', roof_layout=layout,
            resultat={CLE_ENTREE: {'temperature_min_c': -5.0,
                                   'temperature_max_c': 70.0}})

        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)

        # ACAL1910 — égalité de modules posés : la planche garde le module par défaut.
        self.assertEqual(conception.entree.module.designation, materiel['designations']['module'])
        self.assertEqual(materiel['produits']['module'], m550.pk)
        self.assertIn(m400.pk, materiel['fiches_modules'])
        pose = bloc_pose(conception)
        self.assertEqual([(p['pan'], p['kwc']) for p in pose['pans']],
                         [('A', 5.5), ('B', 4.0)])
        self.assertEqual(pose['kwc'], 9.5)
        # ACAL1910 — 13 modules 400 posés contre 10 du défaut : le champ de la planche (entree.module,
        # lu par core.electrique.schema « Modules … ») nomme le module POSÉ.
        layout['zones'][1]['geometry']['count'] = 13
        calepinage.roof_layout = layout
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(conception.entree.module.designation, materiel['fiches_modules'][m400.pk]['designation'])
        self.assertNotEqual(conception.entree.module.designation, materiel['designations']['module'])
