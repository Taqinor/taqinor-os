# -*- coding: utf-8 -*-
"""QJR608 — deux wattages de repli NOMMÉS, un propriétaire chacun.

* ``domain.lignes.LAYOUT_WATT_REPLI = 550`` — le repli d'un layout (ou d'une
  composition) qui ne dit aucun wattage ;
* ``domain.taille._AUTO_PANEL_WATT = 710`` — le panneau catalogue par défaut.

Les deux valeurs ne sont PAS unifiées (entrées différentes). La garde AST :
dans ``apps/ventes/{domain,views}``, chaque littéral n'apparaît qu'UNE fois —
sa définition.

Run :
    python manage.py test apps.ventes.tests.test_watt_defauts_uniques -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

VENTES = Path(__file__).resolve().parents[1]


def _occurrences(valeur):
    trouves = []
    for dossier in ('domain', 'views'):
        for fichier in sorted((VENTES / dossier).rglob('*.py')):
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.Constant)
                        and not isinstance(noeud.value, bool)
                        and noeud.value in (valeur, float(valeur),
                                            str(valeur))):
                    trouves.append('%s:%s' % (
                        fichier.relative_to(VENTES).as_posix(), noeud.lineno))
    return trouves


class DeuxWattagesNommes(SimpleTestCase):

    def test_550_defini_une_fois_dans_lignes(self):
        occ = _occurrences(550)
        self.assertEqual(len(occ), 1, occ)
        self.assertTrue(occ[0].startswith('domain/lignes.py:'), occ)

    def test_710_defini_une_fois_dans_taille(self):
        occ = _occurrences(710)
        self.assertEqual(len(occ), 1, occ)
        self.assertTrue(occ[0].startswith('domain/taille.py:'), occ)

    def test_valeurs_inchangees(self):
        from apps.ventes.domain.lignes import (
            CIBLE_WATT_DEFAUT, LAYOUT_WATT_REPLI)
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        self.assertEqual(LAYOUT_WATT_REPLI, 550)
        self.assertEqual(CIBLE_WATT_DEFAUT, LAYOUT_WATT_REPLI)
        self.assertEqual(_AUTO_PANEL_WATT, 710)


# ── D-ACAL-169 — le panneau PAR DÉFAUT des choix automatiques ────────────────
# « always use 715w everywhere » : la puissance ET le produit viennent du
# panneau désigné au stock, jamais d'un littéral ; sans désigné, la règle
# d'aujourd'hui est rendue telle quelle (710 Wc, rien n'est dit).
from types import SimpleNamespace  # noqa: E402 — bloc D-ACAL-169 (D-ENF22)
from unittest import mock  # noqa: E402 — bloc D-ACAL-169 (D-ENF22)

_RESUME = 'apps.stock.selectors_panneau_defaut.resume_panneau_par_defaut'


def _resume(source='designe', produit_id=42, nom='Panneau Longi 715W', pmax_wc=715, motif=None):
    if source != 'designe':
        produit_id = nom = pmax_wc = None
    return {'produit_id': produit_id, 'nom': nom, 'pmax_wc': pmax_wc, 'source': source, 'motif': motif}


def _auto(resume=None):
    from apps.ventes.domain.panneau_defaut import panneau_auto
    with mock.patch(_RESUME, return_value=resume or _resume()):
        return panneau_auto(SimpleNamespace(pk=1))


def _produit(pk, nom, prix='1000'):
    return SimpleNamespace(pk=pk, id=pk, nom=nom, prix_vente=prix, is_archived=False, categorie=None,
                           fiche_technique=None, role_devis=None)


class PanneauAutoDuStock(SimpleTestCase):
    """``panneau_defaut.panneau_auto`` : UNE lecture du résumé du stock."""

    def test_designe_donne_son_produit_et_sa_puissance(self):
        auto = _auto()
        self.assertEqual((auto.produit_id, auto.watt, auto.motif, auto.source), (42, 715, None, 'designe'))
        self.assertEqual(auto.prefere(715), 42)
        self.assertEqual(auto.prefere(715.0), 42)

    def test_aucun_designe_rend_la_regle_d_aujourd_hui_sans_rien_dire(self):
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        auto = _auto(_resume(source='aucun', motif="Aucun panneau par défaut n'est désigné : x."))
        self.assertEqual((auto.produit_id, auto.watt, auto.motif), (None, _AUTO_PANEL_WATT, None))
        self.assertIsNone(auto.prefere(_AUTO_PANEL_WATT))

    def test_designe_inutilisable_rend_la_regle_d_aujourd_hui_et_dit_pourquoi(self):
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        for source in ('archive', 'sans_prix', 'pas_un_panneau', 'watt_contradictoire'):
            with self.subTest(source=source):
                auto = _auto(_resume(source=source, motif='Le panneau désigné est %s.' % source))
                self.assertEqual((auto.produit_id, auto.watt), (None, _AUTO_PANEL_WATT))
                self.assertEqual(auto.motif, 'Le panneau désigné est %s.' % source)
                self.assertIsNone(auto.prefere(715))

    def test_designe_sans_puissance_lisible_n_est_jamais_compose_a_710(self):
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        auto = _auto(_resume(pmax_wc=None))
        self.assertEqual((auto.produit_id, auto.watt, auto.source), (None, _AUTO_PANEL_WATT, 'refuse'))
        self.assertIn('Panneau Longi 715W', auto.motif)

    def test_une_puissance_tapee_garde_la_regle_d_aujourd_hui(self):
        auto = _auto()
        self.assertIsNone(auto.prefere(550))
        self.assertIsNone(auto.prefere(None))

    def test_sans_societe_ni_stock_lisible_rien_ne_change(self):
        from apps.ventes.domain.panneau_defaut import aucun_panneau_auto, panneau_auto
        self.assertEqual(panneau_auto(None), aucun_panneau_auto())
        with mock.patch(_RESUME, side_effect=ValueError('stock illisible')), \
                self.assertLogs('apps.ventes.domain.panneau_defaut', level='WARNING'):
            self.assertEqual(panneau_auto(SimpleNamespace(pk=1)), aucun_panneau_auto())

    def test_resume_servi_a_l_ecran(self):
        self.assertEqual(_auto().resume(), {
            'produit_id': 42, 'nom': 'Panneau Longi 715W', 'pmax_wc': 715, 'source': 'designe', 'motif': None})
        refuse = _auto().refus('la composition', 'raison').resume()
        self.assertEqual((refuse['produit_id'], refuse['pmax_wc'], refuse['source']), (None, None, 'refuse'))
        self.assertIn('la composition (raison)', refuse['motif'])


class LaCompositionAccepteLePanneauParDefaut(SimpleTestCase):
    """``panneau_auto_composition`` : l'acceptation de la composition résidentielle."""

    def _auto(self, catalogue, marques=None, resume=None):
        from apps.ventes.domain.panneau_defaut import panneau_auto_composition
        reglages = SimpleNamespace(catalogue=catalogue, marques=marques or {}, ordre_lignes=None)
        with mock.patch(_RESUME, return_value=resume or _resume()):
            return panneau_auto_composition(SimpleNamespace(pk=1), reglages=reglages)

    def test_au_catalogue_tarife_et_classe_panneau(self):
        auto = self._auto([_produit(42, 'Panneau Longi 715W')])
        self.assertEqual((auto.produit_id, auto.watt), (42, 715))

    def test_le_watt_vient_de_la_lecture_de_la_composition(self):
        # Contrat du stock : chaque moteur lit le watt du produit à SA façon (ici le nom).
        auto = self._auto([_produit(42, 'Panneau Longi 715W')], resume=_resume(pmax_wc=716))
        self.assertEqual(auto.watt, 715)
        sans_watt_au_nom = self._auto([_produit(42, 'Panneau Longi bifacial')], resume=_resume(pmax_wc=716))
        self.assertEqual(sans_watt_au_nom.watt, 716)

    def test_absent_ou_non_tarife_regle_d_aujourd_hui_dite(self):
        from apps.ventes.domain.taille import _AUTO_PANEL_WATT
        for catalogue in ([], [_produit(42, 'Panneau Longi 715W', prix=None)]):
            with self.subTest(catalogue=catalogue):
                auto = self._auto(catalogue)
                self.assertEqual((auto.produit_id, auto.watt, auto.source), (None, _AUTO_PANEL_WATT, 'refuse'))
                self.assertIn('la composition', auto.motif)

    def test_marque_epinglee_differente_regle_d_aujourd_hui_dite(self):
        auto = self._auto([_produit(42, 'Panneau Longi 715W')], marques={'panneau': 'Jinko'})
        self.assertIsNone(auto.produit_id)
        self.assertIn('« Jinko »', auto.motif)


class LeChoixDuPanneauDeLaComposition(SimpleTestCase):
    """``composition_residentielle._choisir_panneau`` — ``prefere_id``."""

    POOL = [_produit(7, 'Panneau Canadien Solar 715W'), _produit(42, 'Panneau Longi 715W'),
            _produit(9, 'Panneau Jinko 550W')]

    def test_sans_prefere_le_choix_d_aujourd_hui(self):
        from apps.ventes.domain.composition_residentielle import _choisir_panneau
        self.assertEqual(_choisir_panneau(self.POOL, 715)[2].pk, 7)  # « Canadien » gagne l'égalité
        self.assertEqual(_choisir_panneau(self.POOL, 715, None)[2].pk, 7)

    def test_le_panneau_par_defaut_passe_devant_a_sa_puissance(self):
        from apps.ventes.domain.composition_residentielle import _choisir_panneau
        tries, exacts, panneau = _choisir_panneau(self.POOL, 715, 42)
        self.assertEqual(panneau.pk, 42)
        self.assertEqual(sorted(c[1].pk for c in exacts), [7, 42])  # replis PVCOMPAT inchangés
        self.assertEqual(len(tries), 3)

    def test_hors_vivier_le_choix_d_aujourd_hui(self):
        from apps.ventes.domain.composition_residentielle import _choisir_panneau
        self.assertEqual(_choisir_panneau(self.POOL, 715, 999)[2].pk, 7)


class LeChoixDesMoteursCiEtPompage(SimpleTestCase):
    """``panneau_defaut.choisir_avec_defaut`` — l'acceptation propre au moteur."""

    CANDIDATS = [((True, True, 720.0, -1), _produit(1, 'Panneau 720W'), {}),
                 ((True, True, 715.0, -42), _produit(42, 'Panneau Longi 715W'), {}),
                 ((False, True, 0, -5), _produit(5, 'Panneau 600W'), {})]

    def test_accepte_le_designe(self):
        from apps.ventes.domain.panneau_defaut import choisir_avec_defaut
        choisi, motif = choisir_avec_defaut(_auto(), self.CANDIDATS, lambda c: c[0] and c[1],
                                            moteur='m', raison='r')
        self.assertEqual((choisi[1].pk, motif), (42, None))

    def test_refuse_par_le_moteur_regle_d_aujourd_hui_dite(self):
        from apps.ventes.domain.panneau_defaut import choisir_avec_defaut
        choisi, motif = choisir_avec_defaut(_auto(_resume(produit_id=5, nom='Panneau 600W')),
                                            self.CANDIDATS, lambda c: c[0] and c[1], moteur='m', raison='r')
        self.assertIsNone(choisi)
        self.assertIn('m (r)', motif)
        choisi, motif = choisir_avec_defaut(_auto(_resume(produit_id=77)), self.CANDIDATS,
                                            lambda c: True, moteur='m', raison='r')
        self.assertIsNone(choisi)
        self.assertIn('absent', motif)

    def test_sans_designe_rien_ne_change(self):
        from apps.ventes.domain.panneau_defaut import aucun_panneau_auto, choisir_avec_defaut
        self.assertEqual(choisir_avec_defaut(None, self.CANDIDATS, bool, moteur='m', raison='r'), (None, None))
        self.assertEqual(choisir_avec_defaut(aucun_panneau_auto(), self.CANDIDATS, bool, moteur='m', raison='r'),
                         (None, None))
        motif = 'Le panneau désigné « X » est archivé : x.'
        self.assertEqual(choisir_avec_defaut(_auto(_resume(source='archive', motif=motif)), self.CANDIDATS, bool,
                                             moteur='m', raison='r'), (None, motif))


class LeDevisExistantLitSonProprePanneau(SimpleTestCase):
    """LA RÈGLE (``panneau_defaut``) : un devis EXISTANT se calcule sur SA ligne panneau (brouillon), jamais sur le
    défaut ni sur 710 ; un devis envoyé garde le calcul d'aujourd'hui."""

    LIGNE = 'apps.ventes.domain.geometrie._produit_panneau_du_devis'

    def _du_devis(self, devis, produit=_produit(7, 'Panneau Jinko 550W')):
        from apps.ventes.domain.panneau_defaut import panneau_du_devis
        with mock.patch(self.LIGNE, return_value=produit), mock.patch(_RESUME, return_value=_resume()):
            return panneau_du_devis(devis)

    def test_brouillon_sa_ligne_panneau(self):
        auto = self._du_devis(SimpleNamespace(pk=3, statut='brouillon'))
        self.assertEqual((auto.produit_id, auto.watt, auto.source), (7, 550, 'devis'))
        self.assertEqual(auto.prefere(550), 7)

    def test_envoye_accepte_ou_sans_ligne_la_regle_d_aujourd_hui(self):
        from apps.ventes.domain.panneau_defaut import aucun_panneau_auto
        for statut in ('envoye', 'accepte', 'refuse', 'expire'):
            with self.subTest(statut=statut):
                self.assertEqual(self._du_devis(SimpleNamespace(pk=3, statut=statut)), aucun_panneau_auto())
        self.assertEqual(self._du_devis(SimpleNamespace(pk=3, statut='brouillon'), produit=None),
                         aucun_panneau_auto())

    def test_un_seul_predicat_devis_a_naitre(self):
        from apps.ventes.domain.panneau_defaut import devis_a_naitre, panneau_du_contexte
        self.assertTrue(devis_a_naitre(None))
        self.assertTrue(devis_a_naitre(SimpleNamespace(pk=None, statut='brouillon')))
        self.assertFalse(devis_a_naitre(SimpleNamespace(pk=3, statut='brouillon')))
        reglages = SimpleNamespace(catalogue=[_produit(42, 'Panneau Longi 715W')], marques={}, ordre_lignes=None)
        with mock.patch(self.LIGNE, return_value=_produit(7, 'Panneau Jinko 550W')), \
                mock.patch(_RESUME, return_value=_resume()):
            neuf = panneau_du_contexte(SimpleNamespace(pk=1), SimpleNamespace(pk=None), reglages=reglages)
            existant = panneau_du_contexte(SimpleNamespace(pk=1), SimpleNamespace(pk=3, statut='brouillon'),
                                           reglages=reglages)
        self.assertEqual((neuf.produit_id, neuf.watt), (42, 715))
        self.assertEqual((existant.produit_id, existant.watt), (7, 550))

    def test_le_moteur_qui_refuse_le_panneau_du_devis_le_dit(self):
        auto = self._du_devis(SimpleNamespace(pk=3, statut='brouillon'))
        self.assertIn('Le panneau du devis « Panneau Jinko 550W »', auto.refus("l'étude C&I", 'r').motif)


class LeMoteurHoraireRecoitLePanneauDuDevis(SimpleTestCase):
    """Revue 3 — ``taille._panneaux_dimensionnement_horaire(panneau=…)`` le transmet au balayage ; sans lui
    (devis à naître) l'appel au balayage est celui d'aujourd'hui, au mot près."""

    def _appel(self, **kw):
        from apps.ventes.domain.taille import _panneaux_dimensionnement_horaire
        entrees = SimpleNamespace(
            company=None, conso_kwh_mensuelles=[300] * 12, ville='Casablanca', lat=None, lon=None,
            occupation=None, equipements=None, source_conso='kwh', jour_reference=None, gamme_nom_devis=None,
            tranches=None, charges_fixes_mad=None, hors_reseau=False)
        reco = {'recommandation': {'panneaux': 8, 'panel_watt': 710}, 'recommandation_avec': None}
        with mock.patch('apps.ventes.domain.entrees.entrees_depuis_lead', return_value=entrees), \
                mock.patch('apps.ventes.dimensionnement.recommander_taille', return_value=reco) as moteur:
            resultat = _panneaux_dimensionnement_horaire(lead=object(), company=None, phase=None, **kw)
        return resultat, moteur.call_args.kwargs

    def test_sans_panneau_l_appel_d_aujourd_hui(self):
        resultat, kwargs = self._appel()
        self.assertEqual(tuple(resultat)[:2], (8, 710))
        self.assertNotIn('panneau', kwargs)

    def test_le_panneau_du_devis_va_au_balayage(self):
        from apps.ventes.domain.panneau_defaut import PanneauAuto
        panneau = PanneauAuto(produit_id=7, watt=550, nom='Panneau Jinko 550W', source='devis')
        _resultat, kwargs = self._appel(panneau=panneau)
        self.assertIs(kwargs['panneau'], panneau)


class AucunLitteral715(SimpleTestCase):
    """La puissance du panneau par défaut vient du produit désigné, jamais d'un littéral."""

    def test_715_jamais_ecrit_dans_domain_ni_views(self):
        self.assertEqual(_occurrences(715), [])


# ── D-ACAL-169 (c), fondateur 27/11/2026 — la marque épinglée gagne PARTOUT ──
# Le résidentiel refusait déjà un panneau par défaut d'une autre marque que celle épinglée sur la gamme ; l'étude
# C&I et l'étude de pompage le refusent aussi, avec la MÊME phrase, et retiennent un panneau de la marque.
_MARQUE = 'apps.ventes.domain.catalogue.marque_preferee'


def _pour_etude(marque, devis=None, resume=None):
    from apps.ventes.domain.panneau_defaut import panneau_pour_etude
    with mock.patch(_RESUME, return_value=resume or _resume()), mock.patch(_MARQUE, return_value=marque):
        return panneau_pour_etude(SimpleNamespace(pk=1), devis)


class LaMarqueEpingleeGagneDansLesEtudes(SimpleTestCase):
    """``panneau_pour_etude`` + la sélection RÉELLE de chaque étude (``etude_ci_module.module_ci_retenu``,
    ``pompage.lire_catalogue``) ; fiches et catalogue simulés (aucune base)."""

    REFUS = 'la marque épinglée des panneaux est « Jinko »'
    COMPLETE = {'vmp_v': 41.0, 'voc_v': 49.0, 'isc_a': 18.0, 'imp_a': 17.0,
                'temp_coeff_voc_pct_c': None, 'temp_coeff_pmax_pct_c': None}

    @staticmethod
    def _produits():
        from decimal import Decimal

        def produit(pk, nom, marque):
            return SimpleNamespace(pk=pk, id=pk, nom=nom, sku='', marque=marque, prix_vente=Decimal('1500'),
                                   role_devis='panneau', tva=None, paliers_prix_vente=[])
        return [produit(42, 'Panneau Longi 715W', 'Longi'), produit(9, 'Panneau Jinko 600W', 'Jinko'),
                produit(1, 'Panneau Trina 720W', 'Trina')]

    def _ci(self, marque):
        from apps.ventes.domain.etude_ci_module import module_ci_retenu
        pmax = {42: 715, 9: 600, 1: 720}
        alertes = []
        with mock.patch('apps.stock.selectors.specs_for_produit', side_effect=lambda p: {'pmax_wc': pmax[p.pk]}), \
                mock.patch('apps.calepinage.services.chaines.specs_module', return_value=(None, [])):
            module, _spec = module_ci_retenu({p.pk: p for p in self._produits()},
                                             panneau_defaut=_pour_etude(marque), alertes=alertes)
        return module['produit'], [a['message'] for a in alertes if a['code'] == 'panneau_par_defaut']

    def _pompage(self, marque):
        from apps.ventes.domain import pompage
        pmax = {42: 715.0, 9: 600.0, 1: 720.0}
        alertes = []
        with mock.patch('apps.stock.selectors.produits_pompage', return_value=[]), \
                mock.patch('apps.ventes.domain.catalogue.catalogue_de_la_societe', return_value=self._produits()), \
                mock.patch.object(pompage, '_specs_module', side_effect=lambda p: dict(self.COMPLETE,
                                                                                       pmax_wc=pmax[p.pk])):
            catalogue = pompage.lire_catalogue(object(), panneau_defaut=_pour_etude(marque), alertes=alertes)
        return catalogue['panneau']['id'], [a['message'] for a in alertes if a['code'] == 'panneau_par_defaut']

    def test_marque_epinglee_autre_le_defaut_n_est_pas_retenu_et_c_est_dit(self):
        for etude, moteur in ((self._ci, "l'étude C&I"), (self._pompage, "l'étude de pompage")):
            with self.subTest(moteur=moteur):
                retenu, motifs = etude('Jinko')
                self.assertEqual(retenu, 9)  # le panneau de la marque épinglée, jamais le 715 W Longi
                self.assertEqual(len(motifs), 1, motifs)
                self.assertIn('« Panneau Longi 715W »', motifs[0])
                self.assertIn(moteur, motifs[0])
                self.assertIn(self.REFUS, motifs[0])

    def test_sans_marque_ou_de_la_marque_du_defaut_rien_ne_change(self):
        for etude in (self._ci, self._pompage):
            for marque in (None, '', 'Longi', 'longi '):
                with self.subTest(etude=etude.__name__, marque=marque):
                    self.assertEqual(etude(marque), (42, []))

    def test_sans_marque_le_panneau_d_aujourd_hui_a_l_identique(self):
        from apps.ventes.domain.panneau_defaut import panneau_auto
        with mock.patch(_RESUME, return_value=_resume()):
            aujourd_hui = panneau_auto(SimpleNamespace(pk=1))
        self.assertEqual(_pour_etude(None), aujourd_hui)
        self.assertEqual(getattr(_pour_etude('Jinko'), 'marque', None), 'Jinko')

    def test_un_devis_existant_garde_son_panneau_sans_marque(self):
        from apps.ventes.domain.panneau_defaut import aucun_panneau_auto
        ligne = 'apps.ventes.domain.geometrie._produit_panneau_du_devis'
        with mock.patch(ligne, return_value=_produit(7, 'Panneau Longi 550W')):
            brouillon = _pour_etude('Jinko', SimpleNamespace(pk=3, statut='brouillon'))
            envoye = _pour_etude('Jinko', SimpleNamespace(pk=3, statut='envoye'))
        self.assertEqual((brouillon.produit_id, brouillon.watt, getattr(brouillon, 'marque', None)), (7, 550, None))
        self.assertEqual(envoye, aucun_panneau_auto())

    def test_la_meme_phrase_qu_en_residentiel(self):
        from apps.ventes.domain.panneau_defaut import panneau_auto_composition
        reglages = SimpleNamespace(catalogue=[_produit(42, 'Panneau Longi 715W')], marques={'panneau': 'Jinko'},
                                   ordre_lignes=None)
        with mock.patch(_RESUME, return_value=_resume()):
            residentiel = panneau_auto_composition(SimpleNamespace(pk=1), reglages=reglages)
        self.assertIn(self.REFUS, residentiel.motif)


def _ids_produits(obj):
    if isinstance(obj, dict):
        for cle, valeur in obj.items():
            if cle in ('produit', 'id') and isinstance(valeur, int):
                yield valeur
            yield from _ids_produits(valeur)
    elif isinstance(obj, list):
        for valeur in obj:
            yield from _ids_produits(valeur)


class _MarqueEpingleeDeBout:
    """Les points d'entrée RÉELS (``POST etude-ci/preview`` → ``etude_ci.etudier_ci``, ``POST
    etude-pompage/preview`` → ``pompage.etudier_pompage``) : le panneau des fixtures (« Panneau 710W », marque
    Longi) est le panneau par défaut ; un panneau Jinko 700W tarifé à fiche complète est au catalogue."""

    @classmethod
    def _ajouter_jinko(cls):
        from decimal import Decimal

        from apps.stock.models import FicheTechnique, Produit
        Produit.objects.filter(pk=cls.panneau.pk).update(panneau_par_defaut=True, marque='Longi')
        cls.jinko = Produit.objects.create(company=cls.co, nom='Panneau Jinko 700W', marque='Jinko',
                                           prix_vente=Decimal('1200'), prix_achat=Decimal('600'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.jinko, type_fiche='module', pmax_wc=Decimal('700'), vmp_v=Decimal('40'),
            voc_v=Decimal('48'), isc_a=Decimal('18'), imp_a=Decimal('17'))

    def _epingler(self, marque):
        from apps.ventes.models import ParametresGammes
        ParametresGammes.objects.update_or_create(company=self.co, defaults={'marques': {
            ParametresGammes.SLOT_ESSENTIELLE: {'panneau': marque}}})

    def _etude(self):
        data = self.post(self.corps())
        ids = set(_ids_produits(data))
        motifs = [a.get('message') for a in data.get('alertes') or [] if a.get('code') == 'panneau_par_defaut']
        return ids, motifs

    def test_marque_epinglee_autre_le_defaut_n_est_pas_retenu(self):
        self._epingler('Jinko')
        ids, motifs = self._etude()
        self.assertIn(self.jinko.pk, ids)
        self.assertNotIn(self.panneau.pk, ids)
        self.assertEqual(len(motifs), 1, motifs)
        self.assertIn('la marque épinglée des panneaux est « Jinko »', motifs[0])

    def test_sans_marque_ou_de_la_marque_du_defaut_le_defaut_reste(self):
        for marque in (None, 'Longi'):
            with self.subTest(marque=marque):
                if marque:
                    self._epingler(marque)
                ids, motifs = self._etude()
                self.assertIn(self.panneau.pk, ids)
                self.assertNotIn(self.jinko.pk, ids)
                self.assertEqual(motifs, [])


from apps.ventes.tests import test_agr121_etude_pompage_preview as _pompage_t  # noqa: E402 — bloc D-ACAL-169 (D-ENF22)
from apps.ventes.tests import test_ciq118_etude_ci_preview as _ci_t  # noqa: E402 — bloc D-ACAL-169 (D-ENF22)

_BasePompage, _BaseCi = _pompage_t._Base, _ci_t._Base


class EtudeCiMarqueEpinglee(_MarqueEpingleeDeBout, _BaseCi):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._ajouter_jinko()


class EtudePompageMarqueEpinglee(_MarqueEpingleeDeBout, _BasePompage):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._ajouter_jinko()
