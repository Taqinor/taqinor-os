"""ACAL89 (C-ACAL-104/106/009) — les portes de « Générer le devis » du module.

* la COPIE d'un calepinage lié ne réutilise jamais le brouillon de
  l'original : un NOUVEAU devis lui est créé (porte PUB-10 : 500 avant) ;
* un double clic rend le MÊME devis (200, ``deduplique``), client seul compris ;
* un calepinage déjà lié à un devis non réutilisable (envoyé, ou brouillon
  d'une autre empreinte) répond 409 NOMMÉ ``{detail, devis, reference,
  revision_possible}`` sans créer de devis ni re-pointer le lien ;
* un lead agricole est refusé 409 ``{type_installation}`` ;
* la réponse porte ``avertissements`` / ``marques_manquantes`` (contrat
  ``calepinage_publication.json``).

Source réelle : ``build_devis_from_layout``, ``lier_devis``,
``devis_brouillon_pour_layout`` et ``devis_modifiabilite`` — aucun mock ;
catalogue semé comme les tests ventes (``seed_catalogue``).
"""
from __future__ import annotations

import copy
from decimal import Decimal
import json
import re
from pathlib import Path

from django.test import SimpleTestCase, TransactionTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import dupliquer
from apps.crm.models import Client, Lead
from apps.ventes.horaire.conso import CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_publication.json').read_text(encoding='utf-8'))
#: ACAL170 — la réponse de GÉNÉRER porte en plus la clé ``electrique``,
#: publiée par le contrat jumeau ``calepinage_publication_electrique.json``.
CONTRAT_ELECTRIQUE = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_publication_electrique.json').read_text(encoding='utf-8'))

TOIT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


#: ACAL983 — la liste committée des défauts non saisis (lue aussi par le test web).
DEFAUTS = json.loads(
    (Path(__file__).resolve().parent / 'fixtures' / 'defauts_annonces.json')
    .read_text(encoding='utf-8'))
PORTES_REJOUEES = {'generer_devis', 'pose', 'estimateur'}


def url_generer(pk):
    return f'{url_detail(pk)}generer-devis/'


class DefautsAnnoncesSansBaseTest(SimpleTestCase):
    """ACAL983 — la liste est complète, et l'allée du Terrain n'est jamais
    appliquée sans saisie (saisie : l'entraxe calculé est publié à côté)."""

    def test_chaque_defaut_a_sa_porte_et_sa_reponse(self):
        self.assertTrue(DEFAUTS['defauts'])
        for defaut in DEFAUTS['defauts']:
            self.assertIn(defaut['porte'], PORTES_REJOUEES, defaut['cle'])
            for cle in ('cle', 'valeur_origine', 'cas', 'reponse'):
                self.assertTrue(defaut[cle], f"{defaut['cle']} : « {cle} » vide")

    def test_allee_du_terrain_absente_sans_saisie_annoncee_si_saisie(self):
        from apps.calepinage.moteur_service import politique_du_sol

        from .test_api_pose import _terrain

        lignes = [d for d in DEFAUTS['defauts'] if d['porte'] == 'pose']
        self.assertEqual([d['cle'] for d in lignes], ['allee_terrain'])
        _politique, bloc = politique_du_sol(_terrain(), {'latitude_deg': 30.4})
        self.assertEqual(bloc['politique'], lignes[0]['reponse']['politique'])
        self.assertEqual(bloc['entraxe_applique_m'], bloc['entraxe_calcule_m'])
        _politique, saisie = politique_du_sol(_terrain(0.6), {'latitude_deg': 30.4})
        self.assertEqual(saisie['politique'], 'ALLEE_SAISIE')
        self.assertLess(saisie['entraxe_applique_m'], saisie['entraxe_calcule_m'])


#: Critique 22/11 (D2) — zone 42 + champ au sol 176 (même toit qu'ACAL968).
DOC_TOIT_ET_SOL = {
    'scenario': 'reseau',
    'zones': [{'id': 'z1', 'label': 'Zone 1', 'geometry': {'count': 42, 'kwc': 23.1},
               'result': {'count': 42, 'kwc': 23.1}}],
    'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 550,
                      'engine': {'modules': 176}}]}


class SurfacesCocheesSansBaseTest(SimpleTestCase):
    """Critique 22/11 — D2 (devis partiel ACAL968 : à jour, ombrage de SES
    pans, planche) et soupçon 2 (faux 409 ``module_substitue``)."""

    @staticmethod
    def _pivot(document):
        from types import SimpleNamespace

        from apps.ventes.domain.geometrie import layout_hash

        return SimpleNamespace(roof_layout=document, layout_hash=layout_hash(document))

    def _devis_partiel(self, cles):
        from apps.calepinage.services.devis import _layout_des_surfaces

        return self._pivot(_layout_des_surfaces(copy.deepcopy(DOC_TOIT_ET_SOL), cles))

    def test_devis_partiel_frais_a_jour_puis_perime_si_sa_surface_change(self):
        from apps.ventes.selectors_calepinage import _conception_a_jour

        devis = self._devis_partiel(['s1'])
        self.assertIs(_conception_a_jour(devis, self._pivot(DOC_TOIT_ET_SOL)), True)
        change = copy.deepcopy(DOC_TOIT_ET_SOL)
        change['poseSurfaces'][0]['engine']['modules'] = 150
        self.assertIs(_conception_a_jour(devis, self._pivot(change)), False)
        retiree = copy.deepcopy(DOC_TOIT_ET_SOL)
        retiree['poseSurfaces'] = []
        self.assertIs(_conception_a_jour(devis, self._pivot(retiree)), False)
        # La surface NON chiffrée change : ce que le devis vend est inchangé.
        autre = copy.deepcopy(DOC_TOIT_ET_SOL)
        autre['zones'][0]['geometry'].update(count=40, kwc=22.0)
        self.assertIs(_conception_a_jour(devis, self._pivot(autre)), True)
        # Devis complet : comparaison inchangée.
        self.assertIs(_conception_a_jour(self._pivot(DOC_TOIT_ET_SOL),
                                         self._pivot(DOC_TOIT_ET_SOL)), True)

    def test_selection_ancienne_avec_pan_existant_a_jour(self):
        """ACAL1249 — devis partiel créé avant X4 : sa sélection rangée cite le
        pan EXISTANT A (Critique D1, jamais vendu) et le pan neuf z1. La
        sélection LUE ignore A : à jour tant que z1 n'a pas changé, périmé
        sinon ; l'auditeur juge la même copie ; la sélection rangée reste."""
        from apps.calepinage.services.devis import _layout_des_surfaces
        from apps.ventes.coherence.regles_calepinage import _document_chiffre
        from apps.ventes.selectors_calepinage import _conception_a_jour

        doc = copy.deepcopy(DOC_TOIT_ET_SOL)
        doc['zones'].insert(0, {'id': 'A', 'label': 'Existant', 'existant': True,
                                'geometry': {'count': 8, 'kwc': 4.4}})
        copie = _layout_des_surfaces(copy.deepcopy(doc), ['z1'])
        copie['choixConception']['surfacesChiffrees'] = ['A', 'z1']  # rangée avant X4
        devis = self._pivot(copie)
        self.assertIs(_conception_a_jour(devis, self._pivot(doc)), True)
        self.assertEqual(devis.roof_layout['choixConception']['surfacesChiffrees'], ['A', 'z1'])
        self.assertEqual(_document_chiffre(devis, self._pivot(doc))['poseSurfaces'], [])  # sa copie, pas tout
        # La resynchronisation relit la même sélection : plus de refus « Cochez au moins une surface ».
        from apps.calepinage.services.devis import _selection_du_devis
        self.assertEqual(_selection_du_devis(devis, self._pivot(doc)), ['z1'])
        change = copy.deepcopy(doc)
        change['zones'][1]['geometry'].update(count=40, kwc=22.0)
        self.assertIs(_conception_a_jour(devis, self._pivot(change)), False)

    def test_ombrage_du_devis_partiel_est_celui_de_ses_pans(self):
        from apps.calepinage.selectors import _perte_ombrage_chiffree

        def cascade(avant, perte):
            return {'etapes': [{'etape': 'horizon', 'kwh_avant': avant, 'perte_kwh': perte}]}
        lignes = [{'pan': 'Zone 1', 'cascade': cascade(1000, 100)},
                  {'pan': 's1', 'cascade': cascade(3000, 30)}]
        site = cascade(4000, 130)
        self.assertEqual(_perte_ombrage_chiffree(self._devis_partiel(['s1']), lignes, site), 1.0)
        self.assertEqual(_perte_ombrage_chiffree(self._devis_partiel(['z1']), lignes, site), 10.0)
        self.assertEqual(_perte_ombrage_chiffree(self._pivot(DOC_TOIT_ET_SOL), lignes, site), 3.25)
        # Le pan chiffré n'a pas SA cascade : aucune ombre empruntée à l'autre.
        self.assertIsNone(_perte_ombrage_chiffree(self._devis_partiel(['s1']), lignes[:1], site))

    def test_planche_du_devis_partiel_dessine_sa_copie(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage import selectors as cal_selectors
        from apps.calepinage import services as cal_services
        from apps.ventes.quote_engine.artefacts_rendu import _planche_calepinage

        calepinage = SimpleNamespace(layout_hash='c' * 64, version_moteur='v1',
                                     roof_layout=DOC_TOIT_ET_SOL)
        for devis, attendu in ((self._devis_partiel(['s1']), 'partiel'),
                               (self._pivot(DOC_TOIT_ET_SOL), None)):
            devis.pk, devis.company = 7, None
            with mock.patch.object(cal_selectors, 'calepinage_du_devis', return_value=calepinage), \
                    mock.patch.object(cal_selectors, 'conception_figee_du_devis', return_value=None), \
                    mock.patch.object(cal_services, 'texte_d_empreinte', return_value='pied') as pied, \
                    mock.patch.object(cal_services, 'rendre_planche_svg', return_value='') as rendu:
                _planche_calepinage(devis)
            document = rendu.call_args.kwargs.get('document')
            if attendu:
                self.assertIs(document, devis.roof_layout)
                self.assertEqual(pied.call_args.args[0], devis.layout_hash)
            else:
                self.assertIsNone(document)
                self.assertEqual(pied.call_args.args[0], 'c' * 64)

    def test_pan_pave_sans_kwc_lisible_pas_de_faux_409(self):
        """Soupçon 2 — pan A 10 × 585 W + pan B 6 modules sans puissance,
        ``result`` racine 9,36 kWc : la composition lit 9,36 ; la garde ne
        refuse plus, et refuse toujours un vrai module substitué."""
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.devis import DevisRefuse, _garde_module_substitue

        doc = {'scenario': 'reseau', 'modules': [{'id': 'm1', 'pmaxWc': 585}],
               'zones': [{'id': 'A', 'label': 'A', 'geometry': {'moduleId': 'm1', 'panels': [{}] * 10}},
                         {'id': 'B', 'label': 'B', 'geometry': {'panels': [{}] * 6}}],
               'result': {'count': 16, 'kwc': 9.36}}
        with mock.patch('apps.ventes.selectors_calepinage.lignes_produits_calepinage',
                        return_value=[]):
            _garde_module_substitue(SimpleNamespace(etude_params={'puissance_kwc': 9.36}), doc)
            with self.assertRaises(DevisRefuse) as refus:
                _garde_module_substitue(SimpleNamespace(etude_params={'puissance_kwc': 8.8}), doc)
        self.assertEqual(refus.exception.donnees['kwc_dessine'], 9.36)


class ModuleSubstitueSurfaceSansBaseTest(SimpleTestCase):
    """ACAL1440 — le 409 ``module_substitue`` d'une surface de pose seule nomme la
    surface et dit de changer le module du pan ; celui d'un toit garde son texte."""

    LIGNES = 'apps.ventes.selectors_calepinage.lignes_produits_calepinage'
    PANNEAU = [{'designation': 'Panneau Canadien Solar 710W', 'quantite': 50}]

    def _refus(self, doc, compose):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.devis import DevisRefuse, _garde_module_substitue

        with mock.patch(self.LIGNES, return_value=self.PANNEAU):
            with self.assertRaises(DevisRefuse) as refus:
                _garde_module_substitue(SimpleNamespace(etude_params={'puissance_kwc': compose}), doc)
        return refus.exception

    def test_champ_au_sol_seul_dit_quoi_changer_et_ou(self):
        doc = {'schema_version': 2, 'poseSurfaces': [
            {'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 720,
             'engine': {'modules': 50}}]}
        refus = self._refus(doc, 35.5)
        self.assertEqual(refus.statut, 409)
        self.assertEqual(refus.donnees['code'], 'module_substitue')
        self.assertEqual(refus.donnees['detail'], (
            "Champ au sol 1 : son module (« 720 W ») n'est pas celui que le catalogue compose "
            "(« Panneau Canadien Solar 710W »). Changez le module du pan, puis ré-enregistrez le contour."))

    def test_contrat_porte_le_refus_de_surface_servi(self):
        """ACAL1700 — le contrat épingle la forme du refus de surface : mêmes clés que
        le refus d'un toit, valeurs égales à celles servies (mutant : retirer
        ``kwc_compose`` de l'exemple ⇒ échec)."""
        doc = {'schema_version': 2, 'poseSurfaces': [
            {'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 720,
             'engine': {'modules': 50}}]}
        refus = self._refus(doc, 35.5)
        exemple = CONTRAT['exemple_409_module_substitue_surface']
        self.assertEqual(sorted(exemple), sorted(CONTRAT['exemple_409_module_substitue']))
        self.assertEqual(refus.donnees, exemple)

    def test_toit_garde_le_texte_actuel(self):
        doc = {'schema_version': 2, 'zones': [
            {'id': 'z1', 'label': 'Zone 1', 'geometry': {'count': 50, 'kwc': 36.0}}]}
        detail = self._refus(doc, 35.5).donnees['detail']
        self.assertIn("Choisissez le module du catalogue dans l'atelier puis relancez.", detail)
        self.assertNotIn('Changez le module du pan', detail)


class ModuleSubstitueArrondiSansBaseTest(SimpleTestCase):
    """Recette 26/11 (35 × 715 W) — le kWc composé que lit la garde est celui de la VRAIE composition
    (``kwc_lu_des_panneaux`` : arrondi à deux décimales, 25,025 -> 25,02), jamais un littéral. L'écart
    d'arrondi n'est pas un module substitué ; un vrai module changé l'est, et le refus nomme les deux
    puissances sans jamais imprimer deux chiffres égaux."""

    LIGNES = 'apps.ventes.selectors_calepinage.lignes_produits_calepinage'
    SELECTION = 'apps.ventes.domain.scenario._lignes_du_kwc'

    @staticmethod
    def _doc(nombre, watt, kwc_arrondi=None, plans=1):
        """``nombre`` modules de ``watt`` W répartis sur ``plans`` pans (le premier prend le reste)."""
        parts = [nombre // plans + (nombre % plans if i == 0 else 0) for i in range(plans)]
        zones = []
        for i, part in enumerate(parts):
            geo = {'moduleId': 'm1', 'panels': [{}] * part}
            if kwc_arrondi is not None and plans == 1:
                geo['kwc'] = kwc_arrondi
            zones.append({'id': 'Z%d' % i, 'label': 'Z%d' % i, 'geometry': geo})
        return {'scenario': 'reseau', 'modules': [{'id': 'm1', 'pmaxWc': watt}], 'zones': zones}

    @staticmethod
    def _lignes(nombre, watt):
        from types import SimpleNamespace

        return [SimpleNamespace(designation='Panneau Canadien Solar %sW' % watt, produit=None,
                                quantite=nombre, type_ligne='produit')]

    def _garde(self, doc, nombre, watt):
        """La garde face à la composition RÉELLE de ``nombre`` × ``watt`` W : kWc composé calculé par
        ``kwc_lu_des_panneaux``, lignes panneau lues par ``ventes`` (``panneaux_composes_du_devis``)."""
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.devis import _garde_module_substitue
        from apps.ventes.quote_engine.lignes_classement import kwc_lu_des_panneaux

        lignes = self._lignes(nombre, watt)
        kwc = kwc_lu_des_panneaux(lignes)
        devis = SimpleNamespace(etude_params={'puissance_kwc': kwc}, lignes=object())
        with mock.patch(self.LIGNES, return_value=[{'designation': lignes[0].designation, 'quantite': nombre}]), \
                mock.patch(self.SELECTION, return_value=(lignes, lignes)):
            _garde_module_substitue(devis, doc)
        return kwc

    def test_cas_reel_35_fois_715_arrondi_de_la_composition_aucun_refus(self):
        """La recette en direct : 25,025 dessiné au watt près, 25,02 composé par la vraie règle."""
        self.assertEqual(self._garde(self._doc(35, 715), 35, 715), 25.02)
        self._garde(self._doc(35, 715, kwc_arrondi=25.02), 35, 715)
        self._garde(self._doc(35, 715, kwc_arrondi=25.03), 35, 715)

    def test_demi_centimes_reels_de_la_composition_aucun_refus(self):
        valeurs = {}
        for nombre, watt in ((35, 715), (33, 715), (37, 715), (13, 585), (7, 705)):
            valeurs[(nombre, watt)] = self._garde(self._doc(nombre, watt), nombre, watt)
        self.assertEqual(valeurs, {(35, 715): 25.02, (33, 715): 23.59, (37, 715): 26.45,
                                   (13, 585): 7.61, (7, 705): 4.93})

    def test_balayage_meme_module_des_deux_cotes_jamais_de_refus(self):
        for watt in (540, 550, 585, 590, 595, 610, 615, 620, 705, 710, 715, 720):
            for nombre in range(1, 121):
                tel = nombre * watt / 1000
                for arrondi in (None, round(tel - 0.0005, 2), round(tel + 0.0005, 2)):
                    with self.subTest(nombre=nombre, watt=watt, arrondi=arrondi):
                        self._garde(self._doc(nombre, watt, kwc_arrondi=arrondi), nombre, watt)

    def test_balayage_watts_decimaux_sur_un_deux_trois_pans_jamais_de_refus(self):
        """Un module à 577,5 W (lu 577 au catalogue) réparti sur 1 à 3 pans : jamais de refus."""
        for watt, lu in ((577.5, 577), (582.5, 582), (707.5, 707)):
            for plans in (1, 2, 3):
                for nombre in range(plans, 121):
                    with self.subTest(nombre=nombre, watt=watt, plans=plans):
                        self._garde(self._doc(nombre, watt, plans=plans), nombre, lu)

    def test_vrai_changement_de_module_refuse_et_nomme_les_deux_puissances(self):
        from apps.calepinage.services.devis import DevisRefuse

        for plans in (1, 3):
            with self.subTest(plans=plans), self.assertRaises(DevisRefuse) as refus:
                self._garde(self._doc(36, 715, plans=plans), 36, 710)
            detail = refus.exception.donnees['detail']
            self.assertEqual((refus.exception.statut, refus.exception.donnees['code']), (409, 'module_substitue'))
            self.assertIn('Le dessin porte 36 panneaux de 715 W, soit 25,74 kWc ; '
                          'le catalogue compose 36 panneaux de 710 W, soit 25,56 kWc', detail)
            self.assertIn("Choisissez le module du catalogue dans l'atelier", detail)

    def test_nombre_de_panneaux_different_refuse(self):
        from apps.calepinage.services.devis import DevisRefuse

        with self.assertRaises(DevisRefuse):
            self._garde(self._doc(35, 715), 34, 715)

    def test_refus_imprime_les_chiffres_compares_jamais_deux_chiffres_egaux(self):
        from apps.calepinage.services.devis import DevisRefuse

        perime = self._doc(35, 710, kwc_arrondi=25.02)  # kwc stocké périmé = le composé, module 710 W posé
        mixte = {'scenario': 'reseau', 'modules': [{'id': 'm1', 'pmaxWc': 715}, {'id': 'm2', 'pmaxWc': 710}],
                 'zones': [{'id': 'A', 'label': 'A', 'geometry': {'moduleId': 'm1', 'panels': [{}] * 20}},
                           {'id': 'B', 'label': 'B', 'geometry': {'moduleId': 'm2', 'panels': [{}] * 15}}]}
        sans_module = {'scenario': 'reseau', 'zones': [
            {'id': 'A', 'label': 'A', 'geometry': {'count': 50, 'kwc': 36.0}}]}
        cas = [('même compte, autre watt', self._doc(35, 715, kwc_arrondi=25.02), 35, 710),
               ('kwc périmé égal au composé', perime, 35, 715),
               ('modules mêlés', mixte, 35, 700),
               ('repli sans puissance unitaire', sans_module, 50, 700)]
        for nom, doc, nombre, watt in cas:
            with self.subTest(nom), self.assertRaises(DevisRefuse) as refus:
                self._garde(doc, nombre, watt)
            detail = refus.exception.donnees['detail']
            figures = re.findall(r'Le dessin porte (.+?) ; le catalogue compose (.+?) \(', detail)
            self.assertEqual(len(figures), 1, detail)
            self.assertNotEqual(*figures[0], detail)
        with self.assertRaises(DevisRefuse) as refus:
            self._garde(mixte, 35, 700)
        self.assertIn('Le dessin porte 35 panneaux, soit 24,95 kWc ; le catalogue compose 35 panneaux de 700 W, '
                      'soit 24,50 kWc', refus.exception.donnees['detail'])

    def test_fonction_pure(self):
        from decimal import Decimal

        from apps.calepinage.services.devis import _chiffres_distincts, _module_est_substitue

        self.assertEqual(_chiffres_distincts(0.714, 0.7104), ('0,714', '0,710'))
        same = [(35, Decimal(715))]
        self.assertFalse(_module_est_substitue(25.025, 25.02, same, [(35, 715)]))
        self.assertTrue(_module_est_substitue(25.025, 24.85, same, [(35, 710)]))
        self.assertTrue(_module_est_substitue(25.025, 24.99, same, [(34, 715)]))
        self.assertFalse(_module_est_substitue(25.02, 25.03))  # repli : deux demi-unités d'affichage
        self.assertTrue(_module_est_substitue(25.02, 24.85))


class KwcComposeSansCleSansBaseTest(SimpleTestCase):
    """ACAL1417 — ``etude_params`` sans ``puissance_kwc`` : le kWc vendu se lit des
    lignes du devis (règle unique de ventes), pour la question de taille comme pour
    la garde du module substitué."""

    LIGNES_32_4 = 'apps.ventes.services.puissance_kwc_du_devis'

    def test_question_de_taille_dit_le_kwc_et_le_ttc(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import devis as service
        from apps.ventes.services import MOTIF_FACTURE_ABSENTE

        devis = SimpleNamespace(etude_params={}, total_ttc=Decimal('156900'))
        cible = {'panneaux': None, 'kwc': None, 'source': 'factures', 'refus': 'Aucune facture.',
                 'motif_code': MOTIF_FACTURE_ABSENTE}
        with mock.patch.object(service, '_cible_du_calepinage', return_value=cible):
            with mock.patch(self.LIGNES_32_4, return_value=32.4):
                with self.assertRaises(service.DevisRefuse) as question:
                    service._garde_taille(devis, SimpleNamespace(lead_id=3, company=None), False)
        self.assertEqual(question.exception.donnees['kwc'], 32.4)
        self.assertIn('32,40 kWc', question.exception.donnees['detail'])
        self.assertIn('156 900,00 MAD TTC', question.exception.donnees['detail'])

    def test_module_substitue_se_declenche_sans_la_cle(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.devis import DevisRefuse, _garde_module_substitue

        doc = {'scenario': 'reseau', 'modules': [{'id': 'm1', 'pmaxWc': 585}],
               'zones': [{'id': 'A', 'label': 'A', 'geometry': {'moduleId': 'm1', 'panels': [{}] * 16}}],
               'result': {'count': 16, 'kwc': 9.36}}
        devis = SimpleNamespace(etude_params={})
        with mock.patch('apps.ventes.selectors_calepinage.lignes_produits_calepinage', return_value=[]):
            with mock.patch(self.LIGNES_32_4, return_value=9.36):
                _garde_module_substitue(devis, doc)  # même kWc : aucun refus
            with mock.patch(self.LIGNES_32_4, return_value=8.8), self.assertRaises(DevisRefuse) as refus:
                _garde_module_substitue(devis, doc)
        self.assertEqual(refus.exception.donnees['kwc_compose'], 8.8)


class RecetteR2SansBaseTest(SimpleTestCase):
    """Recette R2 du 22/11/2026 — R2-17 (pose au-delà de 2 × la cible des
    factures : la question ACAL922), R2-22 (brouillon libre né avant le
    calepinage : 409 ``devis_existant``), R2-10 (``layout_finalise`` annoncé une
    fois après une génération réussie)."""

    CIBLE = {'panneaux': 4, 'panel_watt': 550, 'kwc': 2.2, 'source': 'factures',
             'refus': None, 'motif_code': None}

    def _poser(self, panneaux, cible, confirmer=False):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import devis as service

        devis = SimpleNamespace(etude_params={'puissance_kwc': 46.2}, total_ttc=Decimal('244500'))
        lignes = [{'designation': 'Panneau 550 W', 'quantite': Decimal(panneaux)},
                  {'designation': 'Onduleur réseau 10 kW', 'quantite': Decimal('1')}]
        with mock.patch.object(service, '_cible_du_calepinage', return_value=cible), \
                mock.patch('apps.ventes.selectors_calepinage.lignes_produits_calepinage',
                           return_value=lignes):
            service._garde_taille(devis, SimpleNamespace(lead_id=3, company=None), confirmer)

    def test_lot8_ordre_de_generation_lie_avant_brouillon_libre(self):
        """Lot 8 (B1) — l'ordre partagé par « Générer » et l'aperçu : un lien actif tranche AVANT
        tout brouillon libre (rendu s'il est le brouillon rendu, sinon « déjà rattaché ») ; les
        brouillons libres ne sont lus qu'en l'absence de lien et de brouillon rendu."""
        from apps.calepinage.services.devis import (
            ISSUE_BROUILLON_LIBRE, ISSUE_COMPOSER, ISSUE_DEJA_RATTACHE, ISSUE_RENDU, _ordre_de_generation,
        )

        lie, rendu, libre = object(), object(), object()
        lus = []

        def libres():
            lus.append(1)
            return [libre]
        self.assertEqual(_ordre_de_generation(lie, lie, libres), (ISSUE_RENDU, lie))
        self.assertEqual(_ordre_de_generation(lie, None, libres), (ISSUE_DEJA_RATTACHE, lie))
        self.assertEqual(_ordre_de_generation(None, rendu, libres), (ISSUE_RENDU, rendu))
        self.assertEqual(lus, [])
        self.assertEqual(_ordre_de_generation(None, None, libres), (ISSUE_BROUILLON_LIBRE, [libre]))
        self.assertEqual(_ordre_de_generation(None, None, list), (ISSUE_COMPOSER, None))

    def test_r2_17_pose_au_dela_de_deux_fois_la_cible_pose_la_question(self):
        from apps.calepinage.services.devis import FACTEUR_POSE_SUR_CIBLE, DevisRefuse

        with self.assertRaises(DevisRefuse) as question:
            self._poser(84, self.CIBLE)
        self.assertEqual(question.exception.statut, 409)
        self.assertEqual(question.exception.donnees, CONTRAT['exemple_409_confirmation_taille_pose'])
        # La borne : 2 × 4 = 8 passe, 9 demande ; « Confirmer » passe toujours.
        self._poser(FACTEUR_POSE_SUR_CIBLE * 4, self.CIBLE)
        with self.assertRaises(DevisRefuse):
            self._poser(FACTEUR_POSE_SUR_CIBLE * 4 + 1, self.CIBLE)
        self._poser(84, self.CIBLE, confirmer=True)

    def test_revue_acal1738_motif_structure_de_la_question(self):
        """Revue ACAL1738 — le 409 ``confirmation_taille`` nomme son motif : ``facture_absente`` quand ``refus`` est
        celui de la cible (l'écran tait alors le bandeau qui le répète), ``pose_sur_cible`` au-delà de 2 × la cible
        (mutant : sans ``motif`` ⇒ échec)."""
        from apps.calepinage.services.devis import DevisRefuse
        from apps.ventes.services import MOTIF_FACTURE_ABSENTE

        sans_facture = {'panneaux': None, 'source': None, 'motif_code': MOTIF_FACTURE_ABSENTE,
                        'refus': CONTRAT['exemple_409_confirmation_taille']['refus']}
        with self.assertRaises(DevisRefuse) as question:
            self._poser(84, sans_facture)
        self.assertEqual(question.exception.donnees['motif'], 'facture_absente')
        self.assertEqual(question.exception.donnees['motif'], CONTRAT['exemple_409_confirmation_taille']['motif'])
        self.assertEqual(question.exception.donnees['refus'], sans_facture['refus'])
        with self.assertRaises(DevisRefuse) as pose:
            self._poser(84, self.CIBLE)
        self.assertEqual(pose.exception.donnees['motif'], 'pose_sur_cible')

    def test_r2_17_sans_cible_des_factures_aucune_question(self):
        for cible in ({**self.CIBLE, 'source': 'lead'},  # taille souhaitée saisie
                      {'panneaux': None, 'panel_watt': None, 'kwc': None, 'source': 'lead',
                       'refus': 'Lead commercial/industriel : étude C&I.', 'motif_code': None}):
            with self.subTest(cible=cible):
                self._poser(84, cible)

    def test_r2_22_choix_invalides_nomment_le_champ(self):
        from apps.calepinage.services.devis import DevisRefuse, _choix_de_generation

        for rattacher, autre in (('76', False), (True, False), (76, True)):
            with self.subTest(rattacher=rattacher, autre=autre):
                with self.assertRaises(DevisRefuse) as refus:
                    _choix_de_generation(False, rattacher, autre)
                self.assertEqual(refus.exception.champ, 'rattacher_devis')
        self.assertEqual(_choix_de_generation(True, 76, False)['rattacher_devis'], 76)

    def _libres(self, choix, *, lie=None):
        from datetime import datetime, timedelta, timezone as tz
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.devis import _brouillon_libre_choisi, _choix_de_generation

        ne_le = datetime(2026, 11, 22, 5, 0, tzinfo=tz.utc)
        tous = {pk: SimpleNamespace(pk=pk, reference=ref, is_active=True, total_ttc=Decimal(ttc),
                                    date_creation=ne_le + timedelta(minutes=minutes))
                for pk, ref, ttc, minutes in ((70, 'DEV-202611-0010', '9000', -60),
                                              (76, 'DEV-202611-0013', '115800', -30),
                                              (80, 'DEV-202611-0020', '5000', 30))}
        lignes = [{'id': 70, 'statut': 'envoye'}, {'id': 76, 'statut': 'brouillon'},
                  {'id': 80, 'statut': 'brouillon'}]
        with mock.patch('apps.ventes.selectors.devis_par_mode_pour_lead', return_value=lignes), \
                mock.patch('apps.ventes.selectors.get_devis_by_pk', side_effect=tous.get), \
                mock.patch('apps.calepinage.selectors.calepinage_du_devis', return_value=lie):
            return _brouillon_libre_choisi(SimpleNamespace(created_at=ne_le), None,
                                           SimpleNamespace(pk=89), _choix_de_generation(False, *choix))

    def test_r2_22_brouillon_libre_anterieur_question_puis_rattachement(self):
        from apps.calepinage.services.devis import DevisRefuse

        with self.assertRaises(DevisRefuse) as question:
            self._libres((None, False))
        self.assertEqual(question.exception.statut, 409)
        # 80 est né APRÈS le calepinage, 70 est envoyé : seul 76 est nommé.
        self.assertEqual(question.exception.donnees, CONTRAT['exemple_409_devis_existant'])
        self.assertEqual(self._libres((CONTRAT['corps_rattacher_devis']['rattacher_devis'], False)).pk, 76)
        for jamais in (70, 80):  # envoyé, ou né après : jamais rattaché par cette voie
            with self.subTest(devis=jamais):
                with self.assertRaises(DevisRefuse) as refus:
                    self._libres((jamais, False))
                self.assertEqual((refus.exception.statut, refus.exception.champ), (409, 'rattacher_devis'))
        # Déjà porté par un calepinage : aucun brouillon libre, aucune question.
        self.assertIsNone(self._libres((None, False), lie=object()))

    def test_r2_10_annonce_une_fois_apres_une_generation_reussie(self):
        from types import SimpleNamespace
        from unittest import mock

        from core import events

        from apps.calepinage.services import devis as service

        devis, user = SimpleNamespace(pk=71), object()
        for issue, attendues in (((devis, True), 1), ((devis, False), 0),
                                 (service.DevisRefuse('non', statut=409), 0)):
            with self.subTest(issue=issue):
                rappels = []
                generer = (mock.patch.object(service, '_generer', side_effect=issue)
                           if isinstance(issue, Exception)
                           else mock.patch.object(service, '_generer', return_value=issue))
                with generer, \
                        mock.patch('apps.calepinage.services.feu_vert.verifier_avant_publication'), \
                        mock.patch.object(service, '_exiger_layout', return_value={'zones': []}), \
                        mock.patch.object(service, '_lead_et_client', return_value=(None, object())), \
                        mock.patch.object(service, '_garde_electrique', return_value={}), \
                        mock.patch.object(service, '_consigner_et_servir', return_value={}), \
                        mock.patch('django.db.transaction.on_commit', side_effect=rappels.append), \
                        mock.patch.object(events.layout_finalise, 'send') as envoi:
                    try:
                        service.generer_devis(SimpleNamespace(company=None), user=user)
                    except service.DevisRefuse:
                        pass
                    self.assertEqual(len(rappels), attendues)
                    envoi.assert_not_called()  # jamais DANS la transaction
                    for rappel in rappels:
                        rappel()
                    self.assertEqual(envoi.call_count, attendues)
                    if attendues:
                        self.assertEqual(envoi.call_args.kwargs, {
                            'sender': 'calepinage.services.devis', 'devis': devis, 'user': user})


class GenererDevisPortesTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        seed_catalogue(self.company)
        # ACAL922 — leads DIMENSIONNÉS (taille souhaitée) : aucune question.
        Lead.objects.filter(pk__in=(self.lead.pk, self.lead_2.pk)).update(
            taille_souhaitee_kwc=Decimal('5'))
        self.original = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL89-A')
        enregistrer_layout(self.original, copy.deepcopy(TOIT), user=self.user)

    def _generer(self, calepinage):
        return self.api.post(url_generer(calepinage.pk), {}, format='json')

    def test_copie_genere_nouveau_devis_sans_500(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        # ACAL187 — source OUVERTE : la copie vise un autre lead.
        copie = dupliquer(self.original, user=self.user,
                          lead_id=self.lead_2.pk)
        # ACON11 — la production de la source ne suit pas une copie vers un
        # autre lead : la copie est re-simulée (ici, résultat reposé).
        self.assertNotIn('result', copie.roof_layout)
        enregistrer_layout(copie, copy.deepcopy(TOIT), user=self.user)

        reponse = self._generer(copie)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotEqual(reponse.data['devis'], premier.data['devis'])
        copie.refresh_from_db()
        self.original.refresh_from_db()
        self.assertEqual(copie.devis_id, reponse.data['devis'])
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_double_clic_dedup_meme_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(self.original)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['deduplique'])
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_montants_differents_du_brouillon_rendu_409(self):
        """ACON49 — un second POST dédupliqué qui demande une autre TVA ou
        une autre remise : 409 nommant le champ, brouillon inchangé ; sans
        montant, ou le même : 200 ``deduplique``."""
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        devis = Devis.objects.get(pk=premier.data['devis'])
        tva, remise = devis.taux_tva, devis.remise_globale
        url = url_generer(self.original.pk)
        for corps, champ in (({'taux_tva': 10}, 'taux_tva'),
                             ({'remise_globale': 5}, 'remise_globale')):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
                self.assertEqual(list(reponse.data), [champ])
                self.assertIn(devis.reference, reponse.data[champ])
        from apps.calepinage.services.devis import _pourcentage_lisible

        self.assertEqual(self.api.post(
            url, {'taux_tva': 10}, format='json').data['taux_tva'],
            f'Le devis {devis.reference} existe déjà à '
            f'{_pourcentage_lisible(tva)} % : changez la TVA depuis le devis.')
        for corps in ({}, {'taux_tva': str(tva)}):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)
                self.assertTrue(reponse.data['deduplique'])
        devis.refresh_from_db()
        self.assertEqual((devis.taux_tva, devis.remise_globale),
                         (tva, remise))
        self.assertEqual(Devis.objects.filter(
            company=self.company).count(), 1)

    def test_montants_differents_brouillon_reutilisable_409(self):
        """ACON95 — la garde ACON49 sur le chemin « brouillon réutilisable
        NON lié » (``_brouillon_reutilisable``) : autre TVA ou autre remise ⇒
        409 nommant le champ, C non relié, D inchangé ; sans montant ⇒ 200
        ``deduplique`` et C relié à D."""
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        devis = Devis.objects.get(pk=premier.data['devis'])
        tva, remise = devis.taux_tva, devis.remise_globale
        Calepinage.objects.filter(pk=self.original.pk).update(devis=None)
        url = url_generer(self.original.pk)
        for corps, champ in (({'taux_tva': 10}, 'taux_tva'),
                             ({'remise_globale': 5}, 'remise_globale')):
            with self.subTest(corps=corps):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 409, reponse.data)
                self.assertEqual(list(reponse.data), [champ])
                self.original.refresh_from_db()
                self.assertIsNone(self.original.devis_id)
        devis.refresh_from_db()
        self.assertEqual((devis.taux_tva, devis.remise_globale),
                         (tva, remise))
        reponse = self.api.post(url, {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['deduplique'])
        self.assertEqual(reponse.data['devis'], devis.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, devis.pk)

    def test_client_seul_deux_clics_un_devis(self):
        client = Client.objects.create(company=self.company,
                                       nom='Client seul ACAL89')
        seul = Calepinage.objects.create(company=self.company,
                                         client=client, titre='QA-ACAL89-C')
        enregistrer_layout(seul, copy.deepcopy(TOIT), user=self.user)
        # ACAL922 — sans lead, la taille se CONFIRME au premier clic.
        premier = self.api.post(url_generer(seul.pk),
                                CONTRAT['corps_confirmer_taille'], format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(seul)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_lie_envoye_409_nomme_sans_nouveau_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        Devis.objects.filter(pk=premier.data['devis']).update(
            statut=Devis.Statut.ENVOYE)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_409_deja_rattache']))
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn(premier.data['reference'], reponse.data['detail'])
        self.assertIn('Resynchroniser le devis', reponse.data['detail'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lie_brouillon_autre_empreinte_409_sans_re_liaison(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        autre = copy.deepcopy(TOIT)
        autre['result'] = dict(autre['result'], panels=10, kwc=5.5)
        autre['areas'][0]['azimuth'] = 170
        enregistrer_layout(self.original, autre, user=self.user)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn('revision_possible', reponse.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lead_ci_marche_du_lead_et_brouillon_d_un_autre_marche_409(self):
        """ACON90 (D-ACON-1) — « Générer le devis » sur un lead industriel :
        devis INDUSTRIEL ; un brouillon RÉSIDENTIEL de même empreinte lié à
        un calepinage d'un lead industriel : 409 ``{devis}`` sans nouveau
        devis ; ``from-layout`` : même refus, texte aussi sous ``detail``."""
        industriel = Lead.objects.create(company=self.company, nom='Usine',
                                         type_installation='industriel')
        c = Calepinage.objects.create(company=self.company,
                                      lead_id=industriel.pk, titre='ACON90-C')
        enregistrer_layout(c, copy.deepcopy(TOIT), user=self.user)
        reponse = self._generer(c)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(Devis.objects.get(pk=reponse.data['devis'])
                         .mode_installation, 'industriel')

        autre = Lead.objects.create(company=self.company, nom='Usine 2',
                                    type_installation='industriel')
        c2 = Calepinage.objects.create(company=self.company,
                                       lead_id=autre.pk, titre='ACON90-C2')
        enregistrer_layout(c2, copy.deepcopy(TOIT), user=self.user)
        c2.refresh_from_db()
        residentiel = Devis.objects.create(
            company=self.company, client=self.client_a, lead=autre,
            reference='DEV-ACON90-1', layout_hash=c2.layout_hash,
            mode_installation='residentiel')
        Calepinage.objects.filter(pk=c2.pk).update(devis=residentiel)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(c2)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('DEV-ACON90-1', str(reponse.data['devis']))
        self.assertIn('marché résidentiel', str(reponse.data['devis']))

        Calepinage.objects.filter(pk=c2.pk).update(devis=None)
        reponse = self.api.post(
            '/api/django/ventes/devis/from-layout/',
            {'layout': c2.roof_layout, 'lead': autre.pk}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['detail'], reponse.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_lead_agricole_409(self):
        agricole = Lead.objects.create(company=self.company,
                                       nom='Ferme Souss',
                                       type_installation='agricole')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=agricole.pk, titre='QA-ACAL89-AGR')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data,
                         CONTRAT['exemple_409_lead_agricole'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

    def test_kwh_contredit_par_les_factures_409_aux_deux_portes(self):
        # ADVS26 — 46 kWh/mois pour 10 000 MAD de facture : même refus
        # qu'``/atomic``, rien de créé (règle fondateur du 30/09/2026).
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('46'), facture_hiver=Decimal('10000'))
        reponses = (
            self.api.post('/api/django/ventes/devis/from-layout/',
                          {'layout': copy.deepcopy(TOIT), 'lead': self.lead.pk},
                          format='json'),
            self._generer(self.original))
        for reponse in reponses:
            self.assertEqual(reponse.status_code, 409, reponse.data)
            self.assertEqual(reponse.data['code'], CODE_KWH_INCOHERENT)
            self.assertEqual(reponse.data['detail'], MESSAGE_KWH_INCOHERENT)
        self.assertFalse(Devis.objects.filter(lead_id=self.lead.pk).exists())
        self.original.refresh_from_db()
        self.assertIsNone(self.original.devis_id)

    def test_kwh_coherent_les_deux_portes_creent(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('650'), facture_hiver=Decimal('1200'))
        reponse = self.api.post(
            '/api/django/ventes/devis/from-layout/',
            {'layout': copy.deepcopy(TOIT), 'lead': self.lead.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertIn(self._generer(self.original).status_code, (200, 201))

    def test_devis_genere_range_l_ombrage_servi(self):
        """ACON85 — les études du devis sont rafraîchies APRÈS le lien au
        calepinage : ``calepinage_du_devis`` trouve alors la conception et
        l'ombrage servi entre dans le bloc horaire (mutant : rafraîchir
        avant ``_lier`` ⇒ le dernier rafraîchissement voit un devis nu)."""
        from unittest import mock

        from apps.ventes import services as ventes_services

        vus = []
        reel = ventes_services.rafraichir_etudes_du_devis

        def espion(devis, *args, **kwargs):
            vus.append(Calepinage.objects.filter(devis_id=devis.pk).exists())
            return reel(devis, *args, **kwargs)

        with mock.patch.object(ventes_services, 'rafraichir_etudes_du_devis',
                               side_effect=espion):
            reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(vus)
        self.assertTrue(vus[-1], vus)

    def test_reponse_porte_avertissements(self):
        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT_ELECTRIQUE['exemple']))
        self.assertTrue(set(CONTRAT['exemple']) <= set(reponse.data))
        # REP-935 — la clé ``electrique`` sert aussi ``etat`` et ``points``.
        self.assertEqual(sorted(reponse.data['electrique']),
                         sorted(CONTRAT_ELECTRIQUE['exemple']['electrique']))
        self.assertEqual(
            sorted(CONTRAT_ELECTRIQUE['exemple_avec_manquantes']['electrique']),
            sorted(CONTRAT_ELECTRIQUE['exemple']['electrique']))
        self.assertIsInstance(reponse.data['avertissements'], list)
        self.assertIsInstance(reponse.data['marques_manquantes'], list)
        second = self._generer(self.original)
        self.assertEqual(sorted(second.data),
                         sorted(set(CONTRAT['exemple_deduplique'])
                                | {'electrique'}))

    def test_hypotheses_toit_non_confirmees_nommees(self):
        """ACAL426 — pan en pente sans source : deux avertissements nommés ;
        avec source : aucun ; toit plat : aucun ; jamais de blocage."""
        def doc(**champs):
            pan = {'id': 'A', 'label': 'A', 'roofType': 'pitched',
                   'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                   'pitchDeg': 22, 'facingAzimuthDeg': 180, **champs}
            d = copy.deepcopy(TOIT)
            d['zones'] = [pan]
            return d

        from apps.calepinage.services.hypotheses_toit import (
            avertissements_hypotheses)

        self.assertEqual(avertissements_hypotheses(doc()), [
            "Pan « A » : la pente (22°) n'a jamais été confirmée — "
            "confirmez-la avant d'envoyer le devis.",
            "Pan « A » : la face (180°) n'a jamais été confirmée — "
            "confirmez-la avant d'envoyer le devis."])
        self.assertEqual(len(avertissements_hypotheses(
            doc(pitchSource={'mode': 'degres'}))), 1)
        self.assertEqual(avertissements_hypotheses(doc(
            pitchSource={'mode': 'degres'}, facingManual=True)), [])
        self.assertEqual(avertissements_hypotheses(doc(
            pitchSource={'mode': 'degres'},
            facingAzimuthSource='releve')), [])
        self.assertEqual(avertissements_hypotheses(
            doc(roofType='flat')), [])
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL426')
        enregistrer_layout(calepinage, doc(), user=self.user)
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(any('la pente (22°)' in m
                            for m in reponse.data['avertissements']))
        self.assertTrue(any('la face (180°)' in m
                            for m in reponse.data['avertissements']))

    def test_module_substitue_409_sans_devis(self):
        """ACAL914 — 100 × 720 W dessinés (72,00 kWc) contre un catalogue à
        550 W : 409 ``module_substitue`` nommant les deux kWc, aucun devis
        (mutant : retirer l'appel de la garde ⇒ 201)."""
        doc = copy.deepcopy(TOIT)
        doc['zones'] = [{
            'id': 'A', 'label': 'A', 'roofType': 'flat',
            'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
            'geometry': {'count': 100, 'kwc': 72.0, 'azimuthDeg': 180.0,
                         'tiltDeg': 10.0},
            'result': {'count': 100, 'kwc': 72.0}}]
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL914')
        enregistrer_layout(calepinage, doc, user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_409_module_substitue']))
        self.assertEqual(reponse.data['code'], 'module_substitue')
        self.assertEqual(reponse.data['kwc_dessine'], 72.0)
        self.assertNotEqual(reponse.data['kwc_compose'], 72.0)
        self.assertTrue(reponse.data['detail'].startswith(
            'Le dessin porte 72,00 kWc ; le catalogue compose '))
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

    def test_acal922_sans_facture_ni_taille_question_puis_201(self):
        """ACAL922 — lead résidentiel sans facture ni taille souhaitée : 409
        ``confirmation_taille`` portant le kWc et le TTC du devis composé,
        aucun devis ; confirmé ⇒ 201 aux MÊMES chiffres (mutant : créer sans
        la garde ⇒ 201 d'emblée, échec)."""
        from core.electrique.types import fr

        nu = Lead.objects.create(company=self.company, nom='Villa sans facture')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=nu.pk, titre='QA-ACAL922')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        question = self._generer(calepinage)
        self.assertEqual(question.status_code, 409, question.data)
        self.assertEqual(sorted(question.data),
                         sorted(CONTRAT['exemple_409_confirmation_taille']))
        self.assertEqual((question.data['code'], question.data['champ']),
                         ('confirmation_taille', 'confirmer_taille'))
        self.assertIn('facture', question.data['refus'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

        reponse = self.api.post(url_generer(calepinage.pk),
                                CONTRAT['corps_confirmer_taille'], format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['devis'])
        kwc = float(devis.etude_params['puissance_kwc'])
        ttc = Decimal(str(devis.total_ttc)).quantize(Decimal('0.01'))
        self.assertEqual(question.data['kwc'], kwc)
        self.assertEqual(question.data['total_ttc'], str(ttc))
        self.assertEqual(question.data['detail'], (
            'Aucune facture ni taille souhaitée sur le lead : le devis remplit '
            'le toit (%s kWc, %s MAD TTC). Confirmez, ou renseignez la facture '
            'du lead.' % (fr(kwc, 2),
                          f'{ttc:,.2f}'.replace(',', ' ').replace('.', ','))))

    def _cas_sans_facture(self):
        nu = Lead.objects.create(company=self.company, nom='Villa ACAL983')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=nu.pk, titre='QA-ACAL983-taille')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        return calepinage

    def _cas_module_720(self):
        doc = copy.deepcopy(TOIT)
        doc['zones'] = [{
            'id': 'A', 'label': 'A', 'roofType': 'flat',
            'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
            'geometry': {'count': 100, 'kwc': 72.0, 'azimuthDeg': 180.0,
                         'tiltDeg': 10.0},
            'result': {'count': 100, 'kwc': 72.0}}]
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL983-module')
        enregistrer_layout(calepinage, doc, user=self.user)
        return calepinage

    def test_acal983_defauts_annonces_jamais_un_prix_sans_question(self):
        """ACAL983 — chaque défaut `generer_devis` de la liste committée rend
        sa question 409 nommée et AUCUN devis (mutant : retirer la garde de
        taille ⇒ 201, échec nommant la clé)."""
        cas = {'taille_sans_facture': self._cas_sans_facture,
               'module_absent_du_catalogue': self._cas_module_720}
        lignes = [d for d in DEFAUTS['defauts'] if d['porte'] == 'generer_devis']
        self.assertEqual(sorted(d['cle'] for d in lignes), sorted(cas))
        for defaut in lignes:
            calepinage = cas[defaut['cle']]()
            avant = Devis.objects.filter(company=self.company).count()
            reponse = self._generer(calepinage)
            attendu = defaut['reponse']
            self.assertEqual((reponse.status_code, reponse.data.get('code')),
                             (attendu['statut'], attendu['code']),
                             f"{defaut['cle']} : {defaut['valeur_origine']} a fixé un devis")
            self.assertEqual(Devis.objects.filter(company=self.company).count(),
                             avant, defaut['cle'])

    def test_r2_10_generation_reussie_note_le_lead_une_fois(self):
        """Recette R2-10 — « Générer le devis » écrit UNE note « Conception 3D
        finalisée » au lead (après la transaction) ; la dédup n'en écrit pas."""
        from apps.crm.models import LeadActivity

        notes = LeadActivity.objects.filter(lead=self.lead, body__startswith='Conception 3D finalisée')
        with self.captureOnCommitCallbacks(execute=True):
            premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(notes.count(), 1)
        self.assertEqual(notes.get().user_id, self.user.pk)
        with self.captureOnCommitCallbacks(execute=True):
            second = self._generer(self.original)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(notes.count(), 1)

    def _brouillon_puis_calepinage(self):
        """R2-22 — le devis automatique d'abord, puis « Dessiner le toit »."""
        ancien = Devis.objects.create(company=self.company, client=self.client_a,
                                      lead=self.lead, reference='DEV-R222-0001')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-R2-22')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        return ancien, calepinage

    def test_r2_22_brouillon_anterieur_question_puis_creer_un_autre(self):
        ancien, calepinage = self._brouillon_puis_calepinage()
        avant = Devis.objects.filter(company=self.company).count()
        question = self._generer(calepinage)
        self.assertEqual(question.status_code, 409, question.data)
        self.assertEqual(sorted(question.data), sorted(CONTRAT['exemple_409_devis_existant']))
        self.assertEqual((question.data['code'], question.data['devis']), ('devis_existant', ancien.pk))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)
        reponse = self.api.post(url_generer(calepinage.pk), CONTRAT['corps_creer_autre_devis'],
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotEqual(reponse.data['devis'], ancien.pk)

    def test_r2_22_rattacher_au_brouillon_jamais_a_un_envoye(self):
        ancien, calepinage = self._brouillon_puis_calepinage()
        Devis.objects.filter(pk=ancien.pk).update(statut=Devis.Statut.ENVOYE)
        refus = self.api.post(url_generer(calepinage.pk), {'rattacher_devis': ancien.pk}, format='json')
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual(list(refus.data), ['rattacher_devis'])
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)
        Devis.objects.filter(pk=ancien.pk).update(statut=Devis.Statut.BROUILLON)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self.api.post(url_generer(calepinage.pk), {'rattacher_devis': ancien.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['devis'], ancien.pk)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.devis_id, ancien.pk)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), avant)

    def test_acal968_champ_seul_coche_176_resynchro_comprise(self):
        """ACAL968 (D-ACAL-37) — zone 42 + champ au sol 176, seul le champ
        coché ⇒ 176 modules, sélection écrite au devis et relue par la
        resynchro SANS corps ⇒ 176 ; vide ou clé inconnue ⇒ 400 nommant
        ``surfaces_chiffrees``. Mutant : composer tout ⇒ 218 ⇒ rouge."""
        doc = {
            'scenario': 'reseau',
            'zones': [{'id': 'z1', 'label': 'Zone 1', 'roofType': 'flat',
                       'vertices': [[0, 0], [30, 0], [30, 20], [0, 20]],
                       'geometry': {'count': 42, 'kwc': 23.1, 'azimuthDeg': 180.0, 'tiltDeg': 10.0},
                       'result': {'count': 42, 'kwc': 23.1}}],
            'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1', 'moduleWc': 550,
                              'contourM': [[0, 0], [40, 0], [40, 25], [0, 25]], 'areaM2': 1000,
                              'rowAzimuthDeg': 90, 'tiltDeg': 25,
                              'engine': {'modules': 176, 'tables': [], 'rowPitchM': 4.2}}]}
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL968')
        enregistrer_layout(calepinage, doc, user=self.user)
        url = url_generer(calepinage.pk)
        for mauvais in ([], ['inconnue'], 's1'):
            refus = self.api.post(url, {'surfaces_chiffrees': mauvais}, format='json')
            self.assertEqual(refus.status_code, 400, refus.data)
            self.assertEqual(sorted(refus.data), sorted(CONTRAT['exemple_400_surfaces_chiffrees']))
        reponse = self.api.post(url, CONTRAT['corps_surfaces_chiffrees'], format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['devis'])

        def panneaux(devis):
            return sum(int(ligne.quantite) for ligne in devis.lignes.all()
                       if 'panneau' in (ligne.designation or '').lower())
        self.assertEqual(panneaux(devis), 176)
        self.assertEqual(devis.roof_layout['choixConception']['surfacesChiffrees'], ['s1'])
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.roof_layout['zones'][0]['geometry']['count'], 42)  # jamais réécrit
        sync = self.api.post(f'{url_detail(calepinage.pk)}sync-devis/', {}, format='json')
        self.assertEqual(sync.status_code, 200, sync.data)
        devis.refresh_from_db()
        self.assertEqual(panneaux(devis), 176)


class GenererDevisConcurrentTest(TransactionTestCase):
    """ACON46 — deux « Générer le devis » CONCURRENTS sur le même calepinage :
    le verrou de ligne les sérialise, UN devis sur le lead, la seconde rend la
    dédup (``cree`` faux). Deux fils, chacun sa connexion ; la première
    génération est ralentie DANS la création (jamais de barrière qui
    bloquerait sous le verrou)."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        from authentication.models import Company

        self.company = Company.objects.create(nom='ACON46 Co',
                                              slug='acon46-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='acon46', password='x', company=self.company, role=role)
        self.lead = Lead.objects.create(company=self.company,
                                        nom='Toiture ACON46',
                                        taille_souhaitee_kwc=Decimal('5'))
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACON46')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)

    def test_deux_generations_concurrentes_un_seul_devis(self):
        import threading
        from unittest import mock

        from django.db import connection

        from apps.calepinage.services.devis import generer_devis
        from apps.ventes.services import build_devis_from_layout as vraie

        dans_la_creation = threading.Event()
        second_lance = threading.Event()
        resultats, erreurs = [], []

        def lente(*args, **kwargs):
            dans_la_creation.set()
            # La seconde génération est lancée PENDANT la création (poignée
            # de main, jamais une attente fixe).
            second_lance.wait(30)
            return vraie(*args, **kwargs)

        def generer(signal=None):
            try:
                if signal is not None:
                    signal.set()
                cal = Calepinage.objects.get(pk=self.calepinage.pk)
                resultats.append(generer_devis(cal, user=self.user,
                                               journal={}))
            except Exception as erreur:  # noqa: BLE001 — remonté par l'assertion
                erreurs.append(erreur)
            finally:
                connection.close()

        with mock.patch('apps.ventes.services.build_devis_from_layout',
                        side_effect=lente):
            premier = threading.Thread(target=generer)
            premier.start()
            self.assertTrue(dans_la_creation.wait(30))
            second = threading.Thread(target=generer,
                                      kwargs={'signal': second_lance})
            second.start()
            premier.join(60)
            second.join(60)

        self.assertEqual(erreurs, [])
        self.assertEqual(sorted(cree for _devis, cree in resultats),
                         [False, True])
        self.assertEqual(Devis.objects.filter(lead=self.lead).count(), 1)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.devis_id, resultats[0][0].pk)
