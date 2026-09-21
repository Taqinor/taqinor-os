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

import copy
import json
import pathlib
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.services.modules_stock import (
    CHAMPS_REQUIS, PREFIXE_ID, SOURCE_FICHE,
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
                    'pmax_wc'):
            setattr(self, nom, champs.pop(nom, None))


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
                     poids_kg=Decimal('27.50'), pmax_wc=Decimal('580.00')))


def _produit_incomplet():
    """La fiche du SECOND : ni puissance, ni épaisseur, ni poids."""
    return _FauxProduit(
        4130, 'Module 550 Wc — fiche à compléter (exemple)',
        _FausseFiche(longueur_mm=2279, largeur_mm=1134))


class LExempleEstCeQueLeServiceProduitTest(SimpleTestCase):
    """L'échantillon committé n'est pas une description : c'est la sortie."""

    def test_la_reponse_complete_est_celle_de_l_exemple(self):
        servi = modules_disponibles_du_calepinage(
            _FauxCalepinage(), [_produit_complet(), _produit_incomplet()])
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
                    ['calepinage', 'champs_requis', 'modules',
                     'motif_liste_vide'])

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
        from apps.calepinage.views import rattachements  # noqa: F401

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
