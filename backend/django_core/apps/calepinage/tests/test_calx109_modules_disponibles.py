"""CALX109 — le catalogue de modules servi à l'atelier, et ce qu'il refuse.

CE QUE CE FICHIER GARDE
-----------------------
1. **L'échantillon committé EST ce que le service produit.** Les cotes de
   l'exemple sont affirmées ligne à ligne contre le producteur, avec des
   fiches fabriquées ici : si demain une cote change de nom ou de nature, ce
   fichier rougit AVANT la CI de l'écran qui l'importe.
2. **Une entrée est une entrée `modules[]` du schéma v2** (CALX82) — la même
   forme, validée contre `roof_layout_v2.schema.json`, et un document qui la
   porte passe la porte d'import RÉELLE (`services/io_layout.py`).
3. **Une fiche incomplète est listée, jamais sélectionnable**, et le motif
   NOMME le champ manquant en français : « non renseigné » n'est pas « zéro »,
   et rien ne retombe en silence sur le module d'hier (D-CALX 7).
4. **Aucun prix, aucune marge** ne peut entrer dans une entrée.

Aucune base : les fiches sont des doubles (`_FausseFiche`), exactement comme
les sélecteurs `apps.stock.selectors` les acceptent déjà. Les tests de VUE
(routage réel, 404 d'une autre société) vivent dans `RouteTest` et restent
`SimpleTestCase` : ils n'inspectent que la classe du viewset.

Run :
    python manage.py test apps.calepinage.tests.test_calx109_modules_disponibles
"""
from __future__ import annotations

import importlib
import copy
import json
import pathlib
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.modules_stock import (
    CHAMPS_REQUIS, MOTIF_AUCUNE_FICHE, MOTIF_PAR_DEFAUT_NON_RETENU, PREFIXE_ID, SOURCE_FICHE,
    _entree_module as entree_module,
    _identifiant_module as identifiant_module,
    modules_disponibles_du_calepinage,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_modules_disponibles.json')
    .read_text(encoding='utf-8'))
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Les mots qui n'ont RIEN à faire dans une entrée de catalogue (règle
#: fondateur : aucun prix d'achat ni marge dans une sortie client).
INTERDITS = ('prix', 'marge', 'cout', 'achat', 'remise', 'tva')


class _FausseFiche:
    """Une ``FicheTechnique`` de test : seuls les champs lus sont posés."""

    def __init__(self, **champs):
        self.type_fiche = champs.pop('type_fiche', 'module')
        for nom in ('longueur_mm', 'largeur_mm', 'epaisseur_mm', 'poids_kg',
                    'pmax_wc', 'sous_chaines_par_module'):
            setattr(self, nom, champs.pop(nom, None))

    def __getattr__(self, nom):
        # ``specs_for_produit`` (ACAL731) lit TOUS les champs de fiche : un
        # champ non posé vaut NULL, comme sur une vraie fiche non saisie.
        if nom.startswith('__'):
            raise AttributeError(nom)
        return None


class _FauxProduit:
    """Un ``Produit`` de test : un identifiant, un nom, une fiche."""

    def __init__(self, pk, nom, fiche=None):
        self.pk = pk
        self.nom = nom
        self.fiche_technique = fiche


class _FauxCalepinage:
    """Un calepinage NU : aucun devis, aucun document — donc aucune base."""

    pk = 1
    company = None


def _produit_complet():
    """La fiche du PREMIER module de l'exemple, cote pour cote."""
    return _FauxProduit(
        4112, 'Module monocristallin 580 Wc (exemple)',
        _FausseFiche(longueur_mm=2278, largeur_mm=1134, epaisseur_mm=35,
                     poids_kg=Decimal('27.50'), pmax_wc=Decimal('580.00'),
                     sous_chaines_par_module=3))


def _produit_incomplet():
    """La fiche du SECOND : ni puissance, ni épaisseur, ni poids."""
    return _FauxProduit(
        4130, 'Module 550 Wc — fiche à compléter (exemple)',
        _FausseFiche(longueur_mm=2279, largeur_mm=1134))


class LExempleEstCeQueLeServiceProduitTest(SimpleTestCase):
    """L'échantillon committé n'est pas une description : c'est la sortie."""

    def test_la_reponse_complete_est_celle_de_l_exemple(self):
        # ACAL174 sert ``modules[].favori`` (posé par ACAL9, M0) : la
        # réponse EST l'exemple, sans table d'attente. L'exemple épingle le
        # module 4112 : la société de ce calepinage l'a dans ses favoris
        # (``ParametresCalepinage.favoris_materiel``, lu par le sélecteur).
        calepinage = _FauxCalepinage()
        calepinage.company = object()
        with mock.patch(
                'apps.calepinage.selectors.parametres_de_societe',
                return_value={'favoris_materiel': {'modules': [4112]}}):
            servi = modules_disponibles_du_calepinage(
                calepinage, [_produit_incomplet(), _produit_complet()])
        # D-ACAL-71 : `en_stock` est posé par la VUE (stock réel) — on rejoue ce que la vue sert, le stock mocké
        # rendant les ids que l'exemple dit en stock ; l'exemple n'est jamais amputé de la clé.
        from apps.calepinage.services.disponibilite_stock import marquer_en_stock

        en_stock = {e['module']['produitId'] for e in CONTRAT['exemple']['modules'] if e.get('en_stock')}
        with mock.patch('apps.stock.selectors_disponibilite.produits_en_stock', return_value=en_stock):
            marquer_en_stock(calepinage.company, servi['modules'], lambda entree: entree['module']['produitId'])
        self.assertEqual(servi, CONTRAT['exemple'])

    def test_un_catalogue_sans_fiche_module_est_celui_de_l_exemple_vide(self):
        servi = modules_disponibles_du_calepinage(_FauxCalepinage(), [])
        self.assertEqual(servi, CONTRAT['exemple_vide'])

    def test_les_quatre_cles_sont_toujours_servies(self):
        for produits in ([], [_produit_complet()], [_produit_incomplet()]):
            with self.subTest(nombre=len(produits)):
                servi = modules_disponibles_du_calepinage(
                    _FauxCalepinage(), produits)
                self.assertEqual(
                    sorted(servi),
                    ['calepinage', 'champs_requis', 'kwc_selon_watt', 'modules',
                     'motif_liste_vide', 'panneaux_selon_watt'])

    def test_e9_la_taille_de_la_conception_comptee_dans_chaque_puissance_offerte(self):
        """Lane E9 (T4-X2-001 / T4-X9-005) — conception de 8 × 550 W = 4,40 kWc, liste à 710
        et 715 Wc : ``panneaux_selon_watt`` = la même puissance crête au panneau près, par LA
        règle du moteur (``panneaux_pour_la_meme_puissance``), jamais le compte de la conception
        reporté tel quel (8 × 710 W = 5,68 kWc, +29 %). Sans conception complète : ``{}``."""
        def module(pk, watt):
            return _FauxProduit(pk, 'Module %d Wc' % watt, _FausseFiche(
                longueur_mm=2384, largeur_mm=1303, pmax_wc=Decimal(watt)))

        conception = {'etat': 'complet', 'option_retenue': 'sans', 'valeurs': {'sans': {
            'nb_panneaux': {'valeur': 8}, 'puissance_kwc': {'valeur': 4.4}}}}
        cible = 'apps.calepinage.services.devis_retenu.conception_du_calepinage'
        with mock.patch(cible, return_value=conception):
            servi = modules_disponibles_du_calepinage(_FauxCalepinage(), [module(1, 710), module(2, 715)])
        self.assertEqual(servi['panneaux_selon_watt'], {'710': 6, '715': 6})
        # T4-X8-011 — le kWc de CE compte dans CE module, servi à côté (6 × 710 W = 4,26 kWc) : jamais le kWc de
        # la conception (4,40) à côté d'un compte d'un autre module, jamais une multiplication dans le navigateur.
        self.assertEqual(servi['kwc_selon_watt'], {'710': 4.26, '715': 4.29})
        with mock.patch(cible, return_value={'etat': 'refus', 'valeurs': {}}):
            servi = modules_disponibles_du_calepinage(_FauxCalepinage(), [module(1, 710)])
        self.assertEqual(servi['panneaux_selon_watt'], {})
        self.assertEqual(servi['kwc_selon_watt'], {})

    def test_l_identifiant_est_stable_et_derive_du_produit(self):
        entree = entree_module(_produit_complet())
        self.assertEqual(entree['module']['id'], identifiant_module(4112))
        self.assertEqual(entree['module']['id'], PREFIXE_ID + '4112')
        self.assertEqual(entree_module(_produit_complet())['module']['id'],
                         entree['module']['id'])

    def test_les_cotes_sont_des_nombres_json(self):
        module = entree_module(_produit_complet())['module']
        for champ in ('longueurMm', 'largeurMm', 'epaisseurMm', 'poidsKg',
                      'pmaxWc'):
            with self.subTest(champ=champ):
                self.assertIsInstance(module[champ], float)
        json.dumps(module)  # aucun Decimal ne survit jusqu'à la réponse


class LePanneauParDefautDeLaSocieteDemarreLeCalepinageTest(SimpleTestCase):
    """D-ACAL-169 — un seul panneau par défaut par société (désigné au stock) : quand rien d'autre ne décide, c'est
    le PREMIER module servi, donc celui que l'atelier pose d'office (``moduleDeDepart``). Sans panneau désigné, la
    réponse est celle d'aujourd'hui, octet pour octet (les tests ci-dessus, inchangés, le disent aussi)."""

    SELECTEUR = 'apps.stock.selectors_panneau_defaut.panneau_par_defaut'

    def _calepinage(self):
        calepinage = _FauxCalepinage()
        calepinage.company = mock.Mock(pk=7)  # société ENREGISTRÉE : le sélecteur du stock est lu
        return calepinage

    def _produit_715(self, fiche=True):
        return _FauxProduit(4140, 'Module monocristallin 715 Wc (exemple)', _FausseFiche(
            longueur_mm=2384, largeur_mm=1303, epaisseur_mm=33, poids_kg=Decimal('33'),
            pmax_wc=Decimal('715')) if fiche else None)

    def _servi(self, defaut, produits, du_devis=None, favoris=(4112,)):
        with mock.patch('apps.calepinage.selectors.parametres_de_societe',
                        return_value={'favoris_materiel': {'modules': list(favoris)}}), \
                mock.patch(self.SELECTEUR, return_value=defaut), \
                mock.patch('apps.calepinage.services.modules_stock._module_de_la_conception',
                           return_value=du_devis):
            return modules_disponibles_du_calepinage(self._calepinage(), produits)

    def test_le_panneau_par_defaut_utilisable_est_le_premier_module_servi(self):
        servi = self._servi(self._produit_715(), [_produit_complet(), self._produit_715()])
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4140, 4112])
        # Le favori (4112) passait en tête sans panneau par défaut : le panneau par défaut le précède.
        from apps.calepinage.services.disponibilite_stock import marquer_en_stock

        with mock.patch('apps.stock.selectors_disponibilite.produits_en_stock', return_value={4140}):
            marquer_en_stock(self._calepinage().company, servi['modules'], lambda e: e['module']['produitId'])
        self.assertEqual(servi, CONTRAT['exemple_avec_panneau_par_defaut'])

    def test_sans_panneau_par_defaut_aucune_cle_et_l_ordre_d_aujourd_hui(self):
        servi = self._servi(None, [self._produit_715(), _produit_complet()])
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4112, 4140])  # favori d'abord
        self.assertTrue(all('par_defaut' not in e for e in servi['modules']))

    def test_rejeu_un_pan_neuf_part_du_panneau_par_defaut_meme_si_la_conception_dit_un_autre_module(self):
        """D-ACAL-169 (rejeu) — 715 Wc désigné, conception du lead au 710 : le premier module d'un pan NEUF était
        « CS 710W — module de départ » (le module de la conception en tête). L'atelier pose d'office le premier
        choisissable (``moduleDeDepart``) : c'est désormais le panneau par défaut utilisable."""
        servi = self._servi(self._produit_715(), [_produit_complet(), self._produit_715()], du_devis='4112')
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4140, 4112])
        premier = next(e for e in servi['modules'] if e['selectionnable'])
        self.assertTrue(premier['par_defaut'])
        self.assertEqual(premier['module']['id'], 'produit-4140')

    def test_rejeu_un_pan_existant_garde_son_module_il_reste_servi_et_choisissable(self):
        """D-ACAL-169 (rejeu) — un pan EXISTANT (ou un calepinage enregistré) cite son module par
        ``zones[].geometry.moduleId`` : ce module reste servi, choisissable, au même identifiant stable, juste
        après le panneau par défaut. Rien n'est réécrit dans le document."""
        servi = self._servi(self._produit_715(), [_produit_complet(), self._produit_715()], du_devis='4112')
        cite = next(e for e in servi['modules'] if e['module']['id'] == 'produit-4112')
        self.assertTrue(cite['selectionnable'])
        self.assertNotIn('par_defaut', cite)

    def test_un_panneau_par_defaut_grise_laisse_la_tete_au_module_de_la_conception(self):
        incomplet = _FauxProduit(4140, 'Module 715 Wc', _FausseFiche(longueur_mm=2384, largeur_mm=1303))
        servi = self._servi(incomplet, [_produit_complet(), incomplet], du_devis='4112')
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4112, 4140])

    def test_une_fiche_incomplete_n_ouvre_pas_le_calepinage_et_le_dit(self):
        incomplet = _FauxProduit(4140, 'Module 715 Wc', _FausseFiche(longueur_mm=2384, largeur_mm=1303))
        servi = self._servi(incomplet, [_produit_complet(), incomplet])
        # L'ordre d'aujourd'hui (le favori en tête), le panneau par défaut listé, grisé, avec sa raison.
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4112, 4140])
        entree = servi['modules'][1]
        self.assertTrue(entree['par_defaut'])
        self.assertFalse(entree['selectionnable'])
        self.assertTrue(entree['motif'].startswith(MOTIF_PAR_DEFAUT_NON_RETENU))
        self.assertIn('la puissance crête (Wc)', entree['motif'])
        self.assertIsNone(servi['motif_liste_vide'])

    def test_un_panneau_par_defaut_sans_fiche_module_est_liste_et_grise(self):
        servi = self._servi(self._produit_715(fiche=False), [])
        self.assertEqual([e['module']['produitId'] for e in servi['modules']], [4140])
        entree = servi['modules'][0]
        self.assertTrue(entree['par_defaut'] and not entree['selectionnable'])
        self.assertTrue(entree['motif'].startswith(MOTIF_PAR_DEFAUT_NON_RETENU))
        # Aucun module sélectionnable ni fiche « module » au catalogue : le motif de liste vide reste celui d'avant.
        self.assertEqual(servi['motif_liste_vide'], MOTIF_AUCUNE_FICHE)

    def test_sans_societe_enregistree_le_stock_n_est_pas_lu(self):
        with mock.patch(self.SELECTEUR) as lecture:
            servi = modules_disponibles_du_calepinage(_FauxCalepinage(), [_produit_complet()])
        lecture.assert_not_called()
        self.assertTrue(all('par_defaut' not in e for e in servi['modules']))


class UneEntreeEstUneEntreeDuDocumentTest(SimpleTestCase):
    """La forme servie est celle du catalogue `modules[]` du v2 (CALX82)."""

    def _validateur(self):
        from jsonschema import Draft202012Validator

        return Draft202012Validator(SCHEMA)

    def test_les_champs_sont_exactement_ceux_du_schema(self):
        attendus = set(SCHEMA['$defs']['moduleDocument']['properties'])
        for produit in (_produit_complet(), _produit_incomplet()):
            with self.subTest(produit=produit.pk):
                self.assertEqual(set(entree_module(produit)['module']),
                                 attendus)

    def test_un_document_qui_porte_ces_modules_est_valide(self):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['modules'] = [
            entree_module(_produit_complet())['module'],
            entree_module(_produit_incomplet())['module'],
        ]
        document['zones'][0]['geometry']['moduleId'] = identifiant_module(4112)
        self.assertEqual(
            [(list(e.absolute_path), e.message)
             for e in self._validateur().iter_errors(document)], [])

    def test_le_document_passe_la_porte_d_import_reelle(self):
        from apps.calepinage.services.io_layout import valider_document

        document = copy.deepcopy(SCHEMA['exemple'])
        document['modules'] = [entree_module(_produit_complet())['module']]
        document['zones'][0]['geometry']['moduleId'] = identifiant_module(4112)
        valider_document(document)

    def test_sous_chaines_servies_et_null_sans_le_champ(self):
        # ACAL731 — 3 sur la fiche ⇒ 3 ; fiche sans le champ ⇒ ``None``,
        # jamais 1 (un défaut de 1 est le mutant).
        self.assertEqual(entree_module(_produit_complet())['module']
                         ['sousChaines'], 3)
        self.assertIsNone(entree_module(_produit_incomplet())['module']
                          ['sousChaines'])
        sans_fiche = _FauxProduit(7, 'Panneau sans fiche (exemple)')
        self.assertIsNone(entree_module(sans_fiche)['module']['sousChaines'])

    def test_la_provenance_est_toujours_publiee(self):
        for produit in (_produit_complet(), _produit_incomplet()):
            with self.subTest(produit=produit.pk):
                self.assertEqual(entree_module(produit)['module']['source'],
                                 SOURCE_FICHE)


class UneFicheIncompleteEstListeeEtNommeeTest(SimpleTestCase):
    """Listée, grisée, et le motif dit QUEL champ manque."""

    def test_une_fiche_sans_puissance_n_est_pas_selectionnable(self):
        entree = entree_module(_produit_incomplet())
        self.assertFalse(entree['selectionnable'])
        self.assertEqual(entree['champs_manquants'], ['pmaxWc'])
        self.assertIn('puissance crête', entree['motif'])

    def test_une_fiche_sans_cotes_nomme_les_trois_champs(self):
        produit = _FauxProduit(7, 'Panneau sans fiche (exemple)')
        entree = entree_module(produit)
        self.assertEqual(entree['champs_manquants'], list(CHAMPS_REQUIS))
        for morceau in ('longueur', 'largeur', 'puissance crête'):
            with self.subTest(morceau=morceau):
                self.assertIn(morceau, entree['motif'])

    def test_une_fiche_incomplete_reste_listee(self):
        servi = modules_disponibles_du_calepinage(
            _FauxCalepinage(), [_produit_incomplet()])
        self.assertEqual(len(servi['modules']), 1)
        self.assertIsNotNone(servi['motif_liste_vide'])
        self.assertIn('longueur', servi['motif_liste_vide'])

    def test_epaisseur_et_poids_ne_grisent_jamais_une_fiche(self):
        produit = _FauxProduit(
            9, 'Module sans poids (exemple)',
            _FausseFiche(longueur_mm=2000, largeur_mm=1000, pmax_wc=450))
        entree = entree_module(produit)
        self.assertTrue(entree['selectionnable'])
        self.assertIsNone(entree['module']['poidsKg'])
        self.assertIsNone(entree['module']['epaisseurMm'])

    def test_une_cote_nulle_ou_negative_est_non_renseignee(self):
        produit = _FauxProduit(
            11, 'Module aux cotes illisibles (exemple)',
            _FausseFiche(longueur_mm=0, largeur_mm=-1, pmax_wc=580))
        entree = entree_module(produit)
        self.assertIsNone(entree['module']['longueurMm'])
        self.assertIsNone(entree['module']['largeurMm'])
        self.assertEqual(entree['champs_manquants'],
                         ['longueurMm', 'largeurMm'])

    def test_une_fiche_d_une_autre_famille_ne_livre_aucune_cote(self):
        """Un onduleur n'est pas un module : rien n'est repris de sa fiche."""
        produit = _FauxProduit(
            13, 'Onduleur hybride (exemple)',
            _FausseFiche(type_fiche='onduleur', longueur_mm=500,
                         largeur_mm=400, pmax_wc=5000))
        entree = entree_module(produit)
        self.assertFalse(entree['selectionnable'])
        self.assertIsNone(entree['module']['longueurMm'])

    def test_un_libelle_vide_ne_sort_jamais_vide(self):
        produit = _FauxProduit(17, '   ', _FausseFiche(longueur_mm=2000))
        self.assertEqual(entree_module(produit)['module']['libelle'],
                         'Module 17')

    def test_le_motif_de_liste_vide_distingue_les_deux_cas(self):
        sans_fiche = modules_disponibles_du_calepinage(
            _FauxCalepinage(), [])['motif_liste_vide']
        fiches_incompletes = modules_disponibles_du_calepinage(
            _FauxCalepinage(), [_produit_incomplet()])['motif_liste_vide']
        self.assertNotEqual(sans_fiche, fiches_incompletes)
        self.assertIsNone(modules_disponibles_du_calepinage(
            _FauxCalepinage(), [_produit_complet()])['motif_liste_vide'])


class AucunPrixNiMargeTest(SimpleTestCase):
    """Le document dit ce qu'EST un module, jamais ce qu'il coûte."""

    def test_aucune_cle_d_argent_dans_une_entree(self):
        entree = entree_module(_produit_complet())
        for cle in list(entree) + list(entree['module']):
            for interdit in INTERDITS:
                with self.subTest(cle=cle, interdit=interdit):
                    self.assertNotIn(interdit, cle.lower())

    def test_l_echantillon_ne_porte_aucune_cle_d_argent(self):
        texte = json.dumps(CONTRAT['exemple'], ensure_ascii=False).lower()
        for interdit in ('prix_achat', 'marge', 'remise'):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, texte)


class RouteTest(SimpleTestCase):
    """La route existe, en GET, rattachée au viewset pivot."""

    def _action(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet
        importlib.import_module('apps.calepinage.views.rattachements')

        par_nom = {a.__name__: a
                   for a in CalepinageViewSet.get_extra_actions()}
        return par_nom.get('modules_disponibles')

    def test_l_action_est_decouverte_par_le_routeur(self):
        self.assertIsNotNone(
            self._action(),
            "L'action « modules_disponibles » n'est pas rattachée : la ligne "
            "d'import doit vivre en fin de views/rattachements.py.")

    def test_elle_est_en_lecture_seule(self):
        self.assertEqual(set(self._action().mapping), {'get'})

    def test_le_chemin_est_celui_du_contrat(self):
        from django.urls import reverse

        _verbe, _, route = CONTRAT['endpoint'].partition(' ')
        self.assertEqual(reverse('calepinage-modules-disponibles', args=('1',)),
                         route.replace('<int:pk>', '1'))

    def test_le_nom_d_attribut_est_celui_de_la_fonction(self):
        """Piège DRF : l'attribut de classe et ``__name__`` doivent coïncider."""
        from apps.calepinage.views.calepinages import CalepinageViewSet

        self.assertEqual(CalepinageViewSet.modules_disponibles.__name__,
                         'modules_disponibles')
