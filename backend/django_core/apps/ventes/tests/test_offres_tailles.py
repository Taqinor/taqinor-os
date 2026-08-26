"""TAILLES (ordre fondateur, 26/08/2026) — Éco / Recommandé / Max.

CE QUE CES TESTS PROTÈGENT, ET POURQUOI CHACUN EXISTE.

1. **Recommandé EST le devis.** Ses nombres doivent être les valeurs SERVIES,
   au centime et au panneau près — jamais un second calcul. C'est la classe
   d'incident « 21 contre 22 » : deux chemins voisins, deux arrondis, deux
   chiffres pour la même installation, et un client qui lit deux prix.
2. **La convergence COLLAPSE, elle ne pousse jamais Recommandé dehors.** Un
   devis bien dimensionné a son optimum SUR le devis : dédupliquer dans
   l'ordre d'affichage aurait laissé « Éco » absorber le devis officiel et
   fait disparaître la seule carte autorisée à ouvrir la signature.
3. **L'omission plutôt que la substitution.** Non résidentiel, pompage, pas de
   tableau de dimensionnement, pas d'option batterie servable : la clé (ou la
   variante) DISPARAÎT. Jamais un zéro, jamais un forfait.
4. **Aucun chiffre dérivé n'entre par l'API.** Le sérialiseur REFUSE en 400 —
   il n'ignore pas en silence, sans quoi le vendeur croirait avoir fixé un
   prix que l'écran n'afficherait jamais.
5. **Indépendance par taille.** Éditer ou régénérer une taille laisse les deux
   autres bit à bit intactes, marqueur ``ajuste`` compris.
6. **La forme SERVIE est celle du CONTRAT** (PACT10) — sans quoi la page et le
   serveur repartiraient chacun avec la leur.
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes import offres_tailles as ot
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'offres_tailles.json')


def _tableau(*paires):
    """Un tableau de dimensionnement SYNTHÉTIQUE (panneaux, payback).

    Seules les clés que ``tailles_eligibles`` et
    ``point_depart_meilleur_payback`` lisent sont posées : le but est
    d'éprouver le CHOIX des trois champs, pas de rejouer le balayage (qui a
    déjà ses propres tests).
    """
    return [{
        'panneaux': panneaux,
        'kwc': round(panneaux * 0.71, 2),
        'composable': True,
        'verdicts_bloquants_sans': [],
        'payback_sans_annees': payback,
        'couverture_sans': 0.5,
    } for panneaux, payback in paires]


def _contexte_factice(devis, *, module_kwh=5.0, plafond=None, remise=1.0):
    """Un contexte de dérivation sans catalogue ni base — la mécanique seule."""
    contexte = SimpleNamespace(
        devis=devis, entrees={}, panel_watt=710.0, catalogue=[],
        marques={}, ordre=[], module_batterie_kwh=module_kwh,
        facteur_remise=remise, plafond_toit=plafond)
    contexte.etude_kwargs = {}
    return contexte


def _carte(nb_panneaux=22, prix=100000.0):
    """Une carte complète — toutes les clés facultatives présentes."""
    return {
        'nb_panneaux': nb_panneaux,
        'puissance_kwc': round(nb_panneaux * 0.71, 3),
        'prix_ttc': prix,
        'prix_par_kwc_ttc': 6400.0,
        'economie_annuelle_mad': 13000.0,
        'payback_annees': 7.7,
        'couverture_pct': 61.0,
        'taux_autoconsommation_pct': 62.8,
        'production_annuelle_kwh': 19140.0,
        'economies_cumulees_25_ans_mad': 311800.0,
        'batterie': {'nb_modules': 3, 'module_kwh': 5.0,
                     'capacite_utile_kwh': 13.5, 'remplissage_ok': True},
        'materiel': [{'role': 'panneau', 'famille': 'panneau',
                      'marque': 'Longi', 'modele': 'Panneau 550 W',
                      'garantie_ans': 12}],
        'familles': ['batterie', 'onduleur', 'panneau'],
        'toit_ok': True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Les petits lecteurs — l'OMISSION est une décision, pas un accident
# ═══════════════════════════════════════════════════════════════════════════

class LecteursTests(SimpleTestCase):

    def test_positif_omet_le_zero_et_le_negatif(self):
        # Un zéro n'est pas une mesure : c'est l'ABSENCE de mesure. Le champ
        # doit disparaître de la carte plutôt qu'afficher « 0 MAD ».
        self.assertIsNone(ot._positif(0))
        self.assertIsNone(ot._positif(-1))
        self.assertIsNone(ot._positif(None))
        self.assertIsNone(ot._positif('pas un nombre'))
        self.assertEqual(ot._positif('12.5'), 12.5)

    def test_pct_preserve_le_zero_mais_pas_le_none(self):
        # Une couverture réellement nulle EST une information ; un moteur qui
        # n'a pas répondu ne l'est pas.
        self.assertEqual(ot._pct(0.0), 0.0)
        self.assertIsNone(ot._pct(None))
        self.assertEqual(ot._pct(0.6135), 61.4)

    def test_payback_none_quand_non_chiffrable(self):
        self.assertIsNone(ot._payback(100.0, 0))
        self.assertIsNone(ot._payback(0, 100.0))
        self.assertIsNone(ot._payback(None, None))
        self.assertEqual(ot._payback(1000.0, 100.0), 10.0)

    def test_prix_par_kwc_arrondi_comme_le_moteur_de_rendu(self):
        # ``quote_engine.builder`` fait ``round(total / kwc)`` : la page ne
        # crée PAS une seconde surface d'arrondi.
        self.assertEqual(ot._prix_par_kwc(100000.0, 12.1), float(round(
            100000.0 / 12.1)))
        self.assertIsNone(ot._prix_par_kwc(0, 12.1))
        self.assertIsNone(ot._prix_par_kwc(100000.0, 0))

    def test_garantie_lue_sur_la_fiche_seulement(self):
        # RÈGLE DE LA FICHE : pas de ``garantie_mois``, pas de garantie
        # affichée — jamais une durée « standard » supposée.
        self.assertIsNone(ot._garantie_ans(SimpleNamespace()))
        self.assertIsNone(ot._garantie_ans(
            SimpleNamespace(garantie_mois=None)))
        # Moins de douze mois : la carte parle en années, « 0 an » mentirait
        # sur une garantie de six mois.
        self.assertIsNone(ot._garantie_ans(SimpleNamespace(garantie_mois=6)))
        self.assertEqual(
            ot._garantie_ans(SimpleNamespace(garantie_mois=144)), 12)


class FamillesTests(SimpleTestCase):

    def test_familles_bornees_aux_trois_comparables(self):
        # Comparabilité : Recommandé lit les LIGNES du devis, Éco/Max une
        # composition catalogue. Servir la liste complète d'un côté et
        # partielle de l'autre ferait dire à « ce qui change » que l'offre Éco
        # ajoute la structure et le transport — un mensonge d'artefact.
        roles = ['panneau', 'onduleur_hybride', 'batterie', 'structure_acier',
                 'cable_dc', 'transport', 'installation']
        self.assertEqual(ot._familles(None, roles=roles),
                         ['batterie', 'onduleur', 'panneau'])

    def test_role_inconnu_n_est_reclasse_dans_aucune_famille(self):
        self.assertEqual(ot._familles(None, roles=['ovni_du_catalogue']), [])

    def test_diff_omise_quand_rien_ne_change(self):
        # Une table de comparaison vide n'apprend rien : le bloc est OMIS.
        self.assertIsNone(ot._diff_familles(['panneau'], ['panneau']))

    def test_diff_dit_la_batterie_retiree(self):
        self.assertEqual(
            ot._diff_familles(['onduleur', 'panneau'],
                              ['batterie', 'onduleur', 'panneau']),
            {'ajoutees': [], 'retirees': ['batterie']})


class Cumul25AnsTests(SimpleTestCase):

    def test_somme_les_flux_annuels_jamais_le_cumul_net(self):
        # ``cumulative`` part de ``-investissement`` : le lire imposerait de
        # ré-ajouter le prix (une soustraction puis une addition = deux
        # occasions de se tromper de signe). On somme les flux.
        cumul = ot._cumul_25_ans(100000.0, 10000.0, avec_batterie=False)
        self.assertIsNotNone(cumul)
        # Sans hausse tarifaire (TARIFF_ESCALATION = 0) et avec la seule
        # dégradation panneau, 25 ans valent un peu MOINS que 25 × l'année 1.
        self.assertLess(cumul, 25 * 10000.0)
        self.assertGreater(cumul, 20 * 10000.0)

    def test_aucune_entree_aucun_cumul(self):
        self.assertIsNone(ot._cumul_25_ans(None, 10000.0, avec_batterie=False))
        self.assertIsNone(ot._cumul_25_ans(100000.0, 0, avec_batterie=False))

    def test_escalade_tarifaire_reste_a_zero(self):
        # La page imprime « aucune hausse tarifaire supposée » AU-DESSUS du
        # chiffre : ce drapeau doit rester nul tant que le fondateur n'a pas
        # fourni de source pour une escalade.
        _horizon, escalade = ot._horizon_et_escalade()
        self.assertEqual(escalade, 0)


# ═══════════════════════════════════════════════════════════════════════════
# 2. LE CŒUR — Recommandé REPREND les valeurs servies, il ne recalcule rien
# ═══════════════════════════════════════════════════════════════════════════

class CarteDuDevisTests(SimpleTestCase):
    """La carte Recommandé, servie depuis ``build_quote_data``."""

    DATA = {
        'nb_panneaux_sans': 22, 'nb_panneaux_avec': 26,
        'puissance_kwc_sans': 12.1, 'puissance_kwc_avec': 14.3,
        'totaux_sans': {'ttc': 108900.55}, 'totaux_avec': {'ttc': 142700.25},
        'eco_s_ann': 13260.4, 'eco_a_ann': 17880.9,
        'roi_s': 8.21, 'roi_a': 7.98,
        'prod_kwh_sans': 19140.0, 'prod_kwh_avec': 22620.0,
    }

    def _contexte(self):
        devis = SimpleNamespace(
            etude_params={'etude_horaire': {'annuel': {
                'couverture_sans': 0.61, 'couverture_avec': 0.794,
                'taux_autoconso_sans': 0.628, 'taux_autoconso_avec': 0.926,
            }}},
            reference='DEV-X')
        return _contexte_factice(devis)

    def test_les_nombres_sont_EXACTEMENT_ceux_servis(self):
        # LE test central de ce chantier. Chaque nombre de la carte
        # « Recommandé » doit être le nombre que la page affiche déjà pour
        # l'offre officielle — pas un recalcul « équivalent ».
        contexte = self._contexte()
        sans = ot._carte_du_devis(contexte, self.DATA, 'sans')
        self.assertEqual(sans['nb_panneaux'], 22)
        self.assertEqual(sans['puissance_kwc'], 12.1)
        self.assertEqual(sans['prix_ttc'], 108900.55)
        self.assertEqual(sans['economie_annuelle_mad'], 13260.4)
        self.assertEqual(sans['payback_annees'], 8.21)
        self.assertEqual(sans['production_annuelle_kwh'], 19140.0)

        avec = ot._carte_du_devis(contexte, self.DATA, 'avec')
        self.assertEqual(avec['nb_panneaux'], 26)
        self.assertEqual(avec['prix_ttc'], 142700.25)
        self.assertEqual(avec['economie_annuelle_mad'], 17880.9)
        self.assertEqual(avec['payback_annees'], 7.98)

    def test_le_payback_servi_prime_sur_un_recalcul(self):
        # ``roi_s`` est ce que la page affiche. Le recalculer donnerait
        # 108900.55 / 13260.4 = 8.21 ici — mais sur un devis où les deux
        # divergent, c'est le SERVI qui doit gagner, jamais notre division.
        data = dict(self.DATA, roi_s=9.99)
        sans = ot._carte_du_devis(self._contexte(), data, 'sans')
        self.assertEqual(sans['payback_annees'], 9.99)

    def test_les_deux_taux_viennent_du_bloc_horaire_du_devis(self):
        sans = ot._carte_du_devis(self._contexte(), self.DATA, 'sans')
        self.assertEqual(sans['couverture_pct'], 61.0)
        self.assertEqual(sans['taux_autoconsommation_pct'], 62.8)
        avec = ot._carte_du_devis(self._contexte(), self.DATA, 'avec')
        self.assertEqual(avec['couverture_pct'], 79.4)
        self.assertEqual(avec['taux_autoconsommation_pct'], 92.6)

    def test_sans_bloc_horaire_les_taux_sont_OMIS_jamais_estimes(self):
        contexte = _contexte_factice(
            SimpleNamespace(etude_params={}, reference='DEV-X'))
        sans = ot._carte_du_devis(contexte, self.DATA, 'sans')
        self.assertNotIn('couverture_pct', sans)
        self.assertNotIn('taux_autoconsommation_pct', sans)
        # …mais tout le reste est servi : une carte partielle vaut mieux
        # qu'une carte absente ou qu'un chiffre inventé.
        self.assertEqual(sans['prix_ttc'], 108900.55)

    def test_sans_calepinage_aucun_verdict_de_toit(self):
        sans = ot._carte_du_devis(self._contexte(), self.DATA, 'sans')
        self.assertNotIn('toit_ok', sans)

    def test_avec_calepinage_le_verdict_de_toit_est_reel(self):
        contexte = self._contexte()
        contexte.plafond_toit = 24
        self.assertIs(
            ot._carte_du_devis(contexte, self.DATA, 'sans')['toit_ok'], True)
        # 26 panneaux ne tiennent pas sur un toit qui en accepte 24.
        self.assertIs(
            ot._carte_du_devis(contexte, self.DATA, 'avec')['toit_ok'], False)

    def test_devis_sans_taille_servie_aucune_carte(self):
        contexte = self._contexte()
        self.assertIsNone(ot._carte_du_devis(contexte, {}, 'sans'))


# ═══════════════════════════════════════════════════════════════════════════
# 3. L'ORCHESTRATION — collapse, ordre, gating de la variante batterie
# ═══════════════════════════════════════════════════════════════════════════

class DerivationTests(SimpleTestCase):
    """``deriver`` sans catalogue : la mécanique des trois tailles, isolée."""

    DATA = {'nb_panneaux_sans': 22, 'variantes_servables': ['sans', 'avec']}

    def _deriver(self, *, tableau, data=None, config=None, plafond=None,
                 cartes=None):
        devis = SimpleNamespace(
            etude_params={'dimensionnement': {'tableau': tableau}},
            offres_tailles_config=config, reference='DEV-X')
        contexte = _contexte_factice(devis, plafond=plafond)
        cartes = cartes or {'sans': _carte(), 'avec': _carte()}
        with mock.patch.object(ot, '_contexte', return_value=contexte), \
                mock.patch.object(
                    ot, '_carte_moteur',
                    side_effect=lambda _c, n, _cfg=None: {
                        'sans': dict(cartes['sans'], nb_panneaux=n),
                        'avec': dict(cartes['avec'], nb_panneaux=n)}), \
                mock.patch.object(
                    ot, '_carte_du_devis',
                    side_effect=lambda _c, _d, v: dict(cartes[v])):
            return ot.deriver(devis, self.DATA if data is None else data)

    def test_trois_tailles_distinctes_trois_offres_dans_l_ordre(self):
        bloc = self._deriver(tableau=_tableau((10, 6.0), (22, 8.0),
                                              (34, 11.0)))
        self.assertEqual([o['cle'] for o in bloc['offres']],
                         ['eco', 'recommande', 'max'])
        self.assertEqual([o['titre'] for o in bloc['offres']],
                         ['Éco', 'Recommandé', 'Max'])

    def test_eco_est_le_MEILLEUR_PAYBACK_du_balayage(self):
        bloc = self._deriver(tableau=_tableau((10, 9.0), (16, 5.0),
                                              (22, 8.0), (34, 11.0)))
        eco = next(o for o in bloc['offres'] if o['cle'] == 'eco')
        self.assertEqual(eco['sans']['nb_panneaux'], 16)

    def test_max_est_borne_par_le_TOIT_quand_un_calepinage_existe(self):
        # 34 panneaux ne tiennent pas sur un toit qui en accepte 28 : « Max »
        # s'arrête à 26 — jamais un panneau au-delà d'une borne physique.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (26, 9.0), (34, 11.0)),
            plafond=28)
        self.assertEqual(bloc['plafond_toit_panneaux'], 28)
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 26)

    def test_toit_sature_max_converge_au_lieu_de_depasser(self):
        # Le devis occupe DÉJÀ tout le toit : « Max » n'a rien à proposer et
        # disparaît. On ne fabrique pas une taille plus grande que le toit.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)), plafond=24)
        self.assertNotIn('max', [o['cle'] for o in bloc['offres']])

    def test_CONVERGENCE_recommande_survit_jamais_eco(self):
        # LE piège. Optimum == devis == 22 panneaux : dédupliquer dans l'ordre
        # d'affichage aurait laissé « Éco » absorber le devis officiel et fait
        # disparaître la seule carte autorisée à ouvrir la signature.
        bloc = self._deriver(tableau=_tableau((22, 5.0), (34, 11.0)))
        cles = [o['cle'] for o in bloc['offres']]
        self.assertIn('recommande', cles)
        self.assertNotIn('eco', cles)
        recommande = next(o for o in bloc['offres']
                          if o['cle'] == 'recommande')
        self.assertIs(recommande['est_le_devis'], True)

    def test_CONVERGENCE_totale_une_seule_offre_jamais_un_intermediaire(self):
        # Tout converge sur le devis : UNE carte. On ne fabrique pas une
        # taille intermédiaire pour remplir les trois emplacements.
        bloc = self._deriver(tableau=_tableau((22, 5.0)))
        self.assertEqual([o['cle'] for o in bloc['offres']], ['recommande'])

    def test_variante_avec_absente_quand_le_devis_ne_la_sert_pas(self):
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            data={'nb_panneaux_sans': 22, 'variantes_servables': ['sans']})
        self.assertIs(bloc['avec_servable'], False)
        for offre in bloc['offres']:
            self.assertNotIn('avec', offre)
            self.assertIn('sans', offre)
            # Le CTA non plus ne propose pas une banque que ce devis ne peut
            # pas servir.
            self.assertEqual(offre['config']['batterie_nb_modules'], 0)

    def test_sans_tableau_de_dimensionnement_seul_le_devis_subsiste(self):
        bloc = self._deriver(tableau=[])
        self.assertEqual([o['cle'] for o in bloc['offres']], ['recommande'])

    def test_sans_taille_de_devis_aucune_ancre_aucun_bloc(self):
        # Les deux autres tailles n'auraient rien à quoi se comparer.
        bloc = self._deriver(tableau=_tableau((10, 6.0)),
                             data={'variantes_servables': ['sans']})
        self.assertIsNone(bloc)

    def test_une_taille_ajustee_porte_son_marqueur(self):
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            config={'eco': {'config': {'nb_panneaux': 12}, 'ajuste': True}})
        eco = next(o for o in bloc['offres'] if o['cle'] == 'eco')
        self.assertIs(eco['ajuste'], True)
        self.assertEqual(eco['sans']['nb_panneaux'], 12)
        # Les deux autres restent « moteur ».
        for cle in ('recommande', 'max'):
            offre = next(o for o in bloc['offres'] if o['cle'] == cle)
            self.assertIs(offre['ajuste'], False)

    def test_recommande_ajuste_cesse_d_etre_LE_devis(self):
        # Le CTA de signature ne doit plus s'ouvrir : l'état affiché n'égale
        # plus le devis officiel.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            config={'recommande': {'config': {'nb_panneaux': 30},
                                   'ajuste': True}})
        recommande = next(o for o in bloc['offres']
                          if o['cle'] == 'recommande')
        self.assertIs(recommande['est_le_devis'], False)
        self.assertIs(recommande['recommande'], True)

    def test_ce_qui_change_se_dit_en_FAMILLES_et_jamais_sur_la_reference(self):
        # Éco n'a pas de batterie ; le devis en a une. La différence se dit
        # « batterie retirée » — jamais « il manque 2 × BAT-XX 5 kWh »
        # (anticopie). Et la carte de RÉFÉRENCE ne porte aucun diff : elle
        # est ce à quoi on compare.
        devis = SimpleNamespace(
            etude_params={'dimensionnement': {
                'tableau': _tableau((10, 6.0), (22, 8.0))}},
            offres_tailles_config=None, reference='DEV-X')
        contexte = _contexte_factice(devis)
        sans_batterie = dict(_carte(), familles=['onduleur', 'panneau'])
        sans_batterie.pop('batterie')
        with mock.patch.object(ot, '_contexte', return_value=contexte), \
                mock.patch.object(
                    ot, '_carte_moteur',
                    side_effect=lambda _c, n, _cfg=None: {
                        'sans': dict(sans_batterie, nb_panneaux=n),
                        'avec': dict(sans_batterie, nb_panneaux=n)}), \
                mock.patch.object(
                    ot, '_carte_du_devis',
                    side_effect=lambda _c, _d, v: dict(_carte())):
            bloc = ot.deriver(devis, self.DATA)

        eco = next(o for o in bloc['offres'] if o['cle'] == 'eco')
        self.assertEqual(eco['sans']['familles_diff'],
                         {'ajoutees': [], 'retirees': ['batterie']})
        recommande = next(o for o in bloc['offres']
                          if o['cle'] == 'recommande')
        self.assertNotIn('familles_diff', recommande['sans'])

    def test_le_module_batterie_du_devis_est_publie(self):
        bloc = self._deriver(tableau=_tableau((10, 6.0), (22, 8.0)))
        self.assertEqual(bloc['module_batterie_kwh'], 5.0)

    def test_publique_exige_DEUX_tailles(self):
        # Une section « Explorer d'autres tailles » qui n'en montre qu'une
        # n'explore rien : la clé est ABSENTE plutôt que servie à moitié.
        devis = SimpleNamespace(reference='DEV-X')
        with mock.patch.object(ot, 'deriver',
                               return_value={'offres': [{'cle': 'recommande'}]}):
            self.assertIsNone(ot.offres_tailles_publique(devis, {}))
        with mock.patch.object(
                ot, 'deriver',
                return_value={'offres': [{'cle': 'eco'},
                                         {'cle': 'recommande'}]}):
            self.assertIsNotNone(ot.offres_tailles_publique(devis, {}))

    def test_publique_ne_leve_JAMAIS(self):
        devis = SimpleNamespace(reference='DEV-X')
        with mock.patch.object(ot, 'deriver',
                               side_effect=RuntimeError('moteur cassé')):
            self.assertIsNone(ot.offres_tailles_publique(devis, {}))


# ═══════════════════════════════════════════════════════════════════════════
# 4. LE CONTRAT (PACT10) — la forme servie EST la forme partagée
# ═══════════════════════════════════════════════════════════════════════════

class ContratTests(SimpleTestCase):

    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_le_contrat_vise_le_bon_endpoint(self):
        self.assertEqual(self.contrat['endpoint'],
                         'GET /api/django/public/proposal/<token>/data/')

    def test_les_trois_cles_et_leurs_titres_sont_ceux_du_contrat(self):
        offres = self.contrat['exemple']['offres_tailles']['offres']
        self.assertEqual([o['cle'] for o in offres], list(ot.CLES))
        for offre in offres:
            self.assertEqual(offre['titre'], ot.TITRES[offre['cle']])

    def test_aucune_cle_de_carte_hors_contrat(self):
        # La garde qui empêche les deux moitiés d'inventer deux formes : toute
        # clé que le serveur peut émettre doit être DÉCLARÉE dans l'exemple.
        declarees = set()
        for offre in self.contrat['exemple']['offres_tailles']['offres']:
            for variante in ('sans', 'avec'):
                declarees |= set(offre.get(variante) or {})
        emises = set(_carte()) | {'familles_diff'}
        self.assertEqual(emises - declarees, set(),
                         'clés émises par le serveur et absentes du contrat')

    def test_aucune_cle_racine_hors_contrat(self):
        declarees = set(self.contrat['exemple']['offres_tailles'])
        emises = {'avec_servable', 'offres', 'module_batterie_kwh',
                  'plafond_toit_panneaux', 'escalade_tarifaire_pct',
                  'horizon_annees'}
        self.assertEqual(emises - declarees, set())

    def test_aucune_cle_d_offre_hors_contrat(self):
        declarees = set(self.contrat['exemple']['offres_tailles']['offres'][0])
        emises = {'cle', 'titre', 'recommande', 'est_le_devis', 'ajuste',
                  'config', 'sans', 'avec'}
        self.assertEqual(emises - declarees, set())

    def test_la_banque_declare_exactement_ce_que_le_serveur_emet(self):
        declarees = set()
        for offre in self.contrat['exemple']['offres_tailles']['offres']:
            declarees |= set((offre.get('avec') or {}).get('batterie') or {})
        self.assertEqual(
            declarees,
            {'nb_modules', 'module_kwh', 'capacite_utile_kwh',
             'remplissage_ok'})

    def test_aucune_autonomie_en_HEURES_n_est_promise(self):
        # Le moteur n'en calcule aucune : `couverture_batterie_publique`
        # exprime l'autonomie en PACKS et en kWh. Servir une durée exigerait
        # de diviser une capacité par une puissance moyenne inventée — le
        # chiffre non vérifié que la règle « zéro chiffre inventé » interdit.
        brut = CONTRAT.read_text(encoding='utf-8')
        self.assertNotIn('"autonomie_heures"', brut)
        self.assertIn('pas_d_autonomie_en_heures', self.contrat['notes'])

    def test_le_contrat_declare_le_refus_des_champs_derives(self):
        regles = self.contrat['api_vendeur']['ecriture_config']['regles']
        texte = ' '.join(regles)
        for champ in ('prix_ttc', 'economie_annuelle_mad', 'payback_annees',
                      'couverture_pct'):
            self.assertIn(champ, texte)

    def test_aucun_prix_d_achat_ni_marge_dans_le_contrat(self):
        # RÈGLE #4 — un prix d'achat ne doit jamais approcher une sortie
        # client, contrat compris.
        brut = CONTRAT.read_text(encoding='utf-8')
        for interdit in ('prix_achat', 'marge', 'cout_achat'):
            self.assertNotIn(interdit, brut)


# ═══════════════════════════════════════════════════════════════════════════
# 5. LA CONFIGURATION STOCKÉE — indépendance par taille
# ═══════════════════════════════════════════════════════════════════════════

class SubstitutionTests(TestCase):
    """Remplacer un produit doit changer le prix, la capacité ET le NOM.

    Le piège : rechiffrer sans renommer ferait afficher le panneau du moteur
    au-dessus du prix du remplaçant — une installation qui n'existe pas.
    """

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(slug='sub', nom='sub')

    def _lignes(self):
        """Une composition minimale en mémoire (aucun moteur sollicité)."""
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau 710 W', prix_vente='1000',
            marque='Canadian', quantite_stock=10)
        batterie = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', prix_vente='12000',
            marque='Dyness', quantite_stock=10)
        lignes = [
            SimpleNamespace(produit=panneau, designation='Panneau 710 W',
                            quantite=10, prix_unitaire=1000),
            SimpleNamespace(produit=batterie, designation='Batterie 5 kWh',
                            quantite=2, prix_unitaire=12000),
        ]
        lignes = type('Compo', (list,), {})(lignes)
        lignes.roles = ['panneau', 'batterie']
        return lignes

    def test_le_prix_suit_le_produit_substitue(self):
        lignes = self._lignes()
        premium = Produit.objects.create(
            company=self.company, nom='Panneau 600 W premium',
            prix_vente='2000', marque='Longi', quantite_stock=10)
        vue = {'cout_ht': 34000.0, 'cout_ttc': 40800.0, 'lignes': []}
        rechiffree = ot._substituer(vue, lignes, {'panneau': premium})
        # 10 × 2000 (au lieu de 1000) + 2 × 12000 = 44 000 HT.
        self.assertEqual(rechiffree['cout_ht'], 44000.0)
        self.assertGreater(rechiffree['cout_ttc'], vue['cout_ttc'])

    def test_le_NOM_affiche_suit_le_produit_substitue(self):
        lignes = self._lignes()
        premium = Produit.objects.create(
            company=self.company, nom='Panneau 600 W premium',
            prix_vente='2000', marque='Longi', garantie_mois=300,
            quantite_stock=10)
        materiel = ot._materiel_de_composition(
            lignes, lignes.roles, {'panneau': premium})
        panneau = next(e for e in materiel if e['famille'] == 'panneau')
        self.assertEqual(panneau['modele'], 'Panneau 600 W premium')
        self.assertEqual(panneau['marque'], 'Longi')
        self.assertEqual(panneau['garantie_ans'], 25)

    def test_la_CAPACITE_suit_la_batterie_substituee(self):
        # Sans cela, la carte annonçait la capacité de l'ANCIENNE batterie
        # au-dessus du prix de la nouvelle — et l'étude horaire tournait sur
        # cette capacité fantôme.
        lignes = self._lignes()
        grosse = Produit.objects.create(
            company=self.company, nom='Batterie 10 kWh', prix_vente='22000',
            marque='Deye', quantite_stock=10)
        vue = {'cout_ht': 0.0, 'cout_ttc': 0.0, 'lignes': [
            {'role': 'batterie', 'designation': 'Batterie 5 kWh',
             'quantite': 2}]}
        rechiffree = ot._substituer(vue, lignes, {'batterie': grosse})
        self.assertGreater(rechiffree['batterie_kwh'], 10.0)

    def test_sans_substitution_la_vue_est_rendue_TELLE_QUELLE(self):
        vue = {'cout_ht': 34000.0, 'cout_ttc': 40800.0}
        self.assertIs(ot._substituer(vue, self._lignes(), {}), vue)
        self.assertIs(ot._substituer(vue, self._lignes(), None), vue)

    def test_un_produit_disparu_laisse_le_produit_du_moteur(self):
        # Le sérialiseur a déjà refusé les identifiants hors société ; ici on
        # ne parle que d'un produit supprimé APRÈS l'ajustement.
        self.assertEqual(ot._resoudre_substitutions({'panneau': 999999}), {})
        self.assertEqual(ot._resoudre_substitutions({'panneau': 'abc'}), {})
        self.assertEqual(ot._resoudre_substitutions(None), {})


class ConfigStockeeTests(TestCase):

    def _devis(self):
        from authentication.models import Company
        company = Company.objects.create(slug='cfg', nom='cfg')
        return Devis.objects.create(
            company=company, reference='DEV-CFG-01', statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel')

    def test_une_forme_illisible_est_traitee_comme_vide(self):
        # Un champ édité à la main ne doit pas appliquer une demi-configuration.
        devis = self._devis()
        devis.offres_tailles_config = {'eco': 'pas un dict'}
        self.assertEqual(ot.lire_config_stockee(devis), {})
        devis.offres_tailles_config = ['pas un dict non plus']
        self.assertEqual(ot.lire_config_stockee(devis), {})

    def test_ecrire_une_taille_laisse_les_autres_BIT_A_BIT(self):
        devis = self._devis()
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        ot.enregistrer_config(devis, 'max', {'nb_panneaux': 40})
        avant = json.dumps(devis.offres_tailles_config['eco'], sort_keys=True)
        ot.enregistrer_config(devis, 'max', {'nb_panneaux': 44})
        apres = json.dumps(devis.offres_tailles_config['eco'], sort_keys=True)
        self.assertEqual(avant, apres)
        self.assertEqual(
            devis.offres_tailles_config['max']['config']['nb_panneaux'], 44)

    def test_regenerer_ne_touche_QUE_la_taille_nommee(self):
        devis = self._devis()
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        ot.enregistrer_config(devis, 'max', {'nb_panneaux': 40})
        ot.regenerer_taille(devis, 'eco')
        self.assertNotIn('eco', devis.offres_tailles_config)
        self.assertIn('max', devis.offres_tailles_config)
        self.assertIs(devis.offres_tailles_config['max']['ajuste'], True)

    def test_ecrire_ne_touche_NI_lignes_NI_statut_NI_totaux(self):
        # RÈGLE #4 — une taille est une exploration.
        devis = self._devis()
        avant = (devis.statut, devis.taux_tva, devis.remise_globale,
                 devis.lignes.count())
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        devis.refresh_from_db()
        self.assertEqual(
            (devis.statut, devis.taux_tva, devis.remise_globale,
             devis.lignes.count()), avant)

    def test_taille_inconnue_refusee(self):
        devis = self._devis()
        with self.assertRaises(ValueError):
            ot.enregistrer_config(devis, 'premium', {'nb_panneaux': 12})
        with self.assertRaises(ValueError):
            ot.regenerer_taille(devis, 'premium')

    def test_regenerer_la_derniere_taille_remet_le_champ_a_NULL(self):
        devis = self._devis()
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        ot.regenerer_taille(devis, 'eco')
        devis.refresh_from_db()
        self.assertIsNone(devis.offres_tailles_config)


# ═══════════════════════════════════════════════════════════════════════════
# 6. LE SÉRIALISEUR — refuser, jamais ignorer
# ═══════════════════════════════════════════════════════════════════════════

class SerialiseurTests(TestCase):

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(slug='ser', nom='ser')
        self.autre = Company.objects.create(slug='autre', nom='autre')

    def _config(self, donnees, company=None):
        from apps.ventes.serializers import OffreTailleConfigSerializer
        return OffreTailleConfigSerializer(
            data=donnees, context={'company': company or self.company})

    def test_chaque_champ_derive_est_REFUSE_jamais_ignore(self):
        # Ignorer en silence ferait croire au vendeur qu'il a fixé un prix que
        # l'écran n'afficherait jamais.
        for champ in ot.CHAMPS_DERIVES:
            serializer = self._config({'nb_panneaux': 12, champ: 1})
            self.assertFalse(serializer.is_valid(),
                             '%s aurait dû être refusé' % champ)
            self.assertIn(champ, serializer.errors)

    def test_un_champ_inconnu_est_refuse(self):
        serializer = self._config({'nb_panneaux': 12, 'ristourne': 10})
        self.assertFalse(serializer.is_valid())
        self.assertIn('ristourne', serializer.errors)

    def test_une_configuration_vide_est_refusee(self):
        self.assertFalse(self._config({}).is_valid())

    def test_la_configuration_legitime_passe(self):
        serializer = self._config({'nb_panneaux': 16,
                                   'batterie_nb_modules': 2})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['nb_panneaux'], 16)

    def test_un_produit_d_une_AUTRE_societe_est_refuse(self):
        # La frontière multi-société se tient ICI, une seule fois.
        etranger = Produit.objects.create(
            company=self.autre, nom='Panneau étranger', prix_vente='1000',
            quantite_stock=1)
        serializer = self._config({'equipements': {'panneau': etranger.pk}})
        self.assertFalse(serializer.is_valid())
        self.assertIn('panneau', serializer.errors['equipements'])

    def test_un_produit_de_MA_societe_passe(self):
        mien = Produit.objects.create(
            company=self.company, nom='Panneau maison', prix_vente='1000',
            quantite_stock=1)
        serializer = self._config({'equipements': {'panneau': mien.pk}})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_un_role_inconnu_est_refuse(self):
        mien = Produit.objects.create(
            company=self.company, nom='Panneau maison', prix_vente='1000',
            quantite_stock=1)
        serializer = self._config({'equipements': {'ovni': mien.pk}})
        self.assertFalse(serializer.is_valid())

    def test_la_cle_de_taille_est_bornee_aux_trois(self):
        from apps.ventes.serializers import OffreTailleEcritureSerializer
        serializer = OffreTailleEcritureSerializer(
            data={'cle': 'premium', 'config': {'nb_panneaux': 12}},
            context={'company': self.company})
        self.assertFalse(serializer.is_valid())
        self.assertIn('cle', serializer.errors)


# ═══════════════════════════════════════════════════════════════════════════
# 7. BOUT EN BOUT — le payload public et l'API vendeur
# ═══════════════════════════════════════════════════════════════════════════

class _Base(TestCase):
    """Fixture calquée sur ``test_payload_paliers_batterie._PayloadBase``."""

    LIGNES = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 5 kWh', '2', '12500.00'),
    )

    def _company(self, slug):
        from authentication.models import Company
        return Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]

    def _user(self, company, role='responsable'):
        return User.objects.create_user(
            username='u-%s-%s' % (company.slug, role), password='x',
            company=company, role_legacy=role)

    def _devis(self, slug, *, mode='residentiel', avec_batterie=True):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom='Client %s' % slug, defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        devis = Devis.objects.create(
            company=company, reference='DEV-%s-01' % slug.upper(),
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        lignes = list(self.LIGNES) if avec_batterie else list(self.LIGNES[:2])
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _payload(self, devis, **kwargs):
        link = ShareLink.objects.create(
            company=devis.company, devis=devis, **kwargs)
        resp = APIClient().get(
            '/api/django/public/proposal/%s/data/' % link.token)
        self.assertEqual(resp.status_code, 200)
        return resp.json()


class PayloadPubliqueTests(_Base):

    _BLOC = {
        'avec_servable': True,
        'escalade_tarifaire_pct': 0,
        'horizon_annees': 25,
        'offres': [{'cle': 'eco', 'titre': 'Éco', 'recommande': False,
                    'est_le_devis': False, 'ajuste': False,
                    'config': {'nb_panneaux': 10},
                    'sans': {'nb_panneaux': 10, 'prix_ttc': 52800.0}},
                   {'cle': 'recommande', 'titre': 'Recommandé',
                    'recommande': True, 'est_le_devis': True,
                    'ajuste': False, 'config': {'nb_panneaux': 14},
                    'sans': {'nb_panneaux': 14, 'prix_ttc': 71400.0}}],
    }

    def test_la_cle_est_servie_quand_le_moteur_derive(self):
        devis = self._devis('pub-ok')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            payload = self._payload(devis)
        self.assertEqual(payload['offres_tailles'], self._BLOC)

    def test_un_devis_POMPAGE_n_a_aucune_taille(self):
        devis = self._devis('pub-pompage', mode='agricole')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC) as derive:
            payload = self._payload(devis)
        self.assertNotIn('offres_tailles', payload)
        # La garde est en AMONT : le moteur n'est même pas sollicité.
        derive.assert_not_called()

    def test_un_devis_INDUSTRIEL_n_a_aucune_taille(self):
        devis = self._devis('pub-indus', mode='industriel')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            payload = self._payload(devis)
        self.assertNotIn('offres_tailles', payload)

    def test_un_moteur_qui_LEVE_ne_casse_jamais_la_page(self):
        devis = self._devis('pub-boom')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        side_effect=RuntimeError('moteur cassé')):
            payload = self._payload(devis)
        self.assertNotIn('offres_tailles', payload)
        # Les clés voisines restent servies : la panne est confinée.
        self.assertIn('variantes_servables', payload)
        self.assertIn('quote', payload)

    def test_UNE_seule_taille_n_est_pas_servie(self):
        devis = self._devis('pub-une')
        seule = dict(self._BLOC, offres=self._BLOC['offres'][:1])
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=seule):
            payload = self._payload(devis)
        self.assertNotIn('offres_tailles', payload)

    def test_les_deux_niveaux_de_partage_servent_la_MEME_chose(self):
        devis = self._devis('pub-niv')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            standard = self._payload(devis, niveau=ShareLink.NIVEAU_STANDARD)
            confiance = self._payload(devis, niveau=ShareLink.NIVEAU_CONFIANCE)
        self.assertEqual(standard['offres_tailles'],
                         confiance['offres_tailles'])

    def test_aucun_prix_d_achat_ne_fuit_dans_le_bloc(self):
        devis = self._devis('pub-marge')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            payload = self._payload(devis)
        brut = json.dumps(payload['offres_tailles'])
        for interdit in ('prix_achat', 'marge', 'cout_achat'):
            self.assertNotIn(interdit, brut)


class ApiVendeurTests(_Base):

    _BLOC = PayloadPubliqueTests._BLOC

    def _client(self, devis, role='responsable'):
        api = APIClient()
        api.force_authenticate(user=self._user(devis.company, role))
        return api

    def test_lecture_sert_les_tailles(self):
        devis = self._devis('api-lire')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            resp = self._client(devis).get(
                '/api/django/ventes/devis/%s/offres-tailles/' % devis.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.json()['editable'], True)
        self.assertEqual(resp.json()['offres_tailles'], self._BLOC)

    def test_devis_non_derivable_dit_POURQUOI(self):
        devis = self._devis('api-muet')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=None):
            resp = self._client(devis).get(
                '/api/django/ventes/devis/%s/offres-tailles/' % devis.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.json()['editable'], False)
        self.assertTrue(resp.json()['raison_non_editable'])

    def test_lecture_ne_tombe_pas_si_le_moteur_leve(self):
        devis = self._devis('api-boom')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        side_effect=RuntimeError('moteur cassé')):
            resp = self._client(devis).get(
                '/api/django/ventes/devis/%s/offres-tailles/' % devis.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertIs(resp.json()['editable'], False)

    def test_patch_enregistre_la_config_et_marque_ajuste(self):
        devis = self._devis('api-patch')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            resp = self._client(devis).patch(
                '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk,
                {'cle': 'eco', 'config': {'nb_panneaux': 18}}, format='json')
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        entree = devis.offres_tailles_config['eco']
        self.assertEqual(entree['config']['nb_panneaux'], 18)
        self.assertIs(entree['ajuste'], True)
        self.assertTrue(entree['modifie_le'])
        self.assertIsNotNone(entree['modifie_par'])

    def test_patch_d_un_champ_DERIVE_repond_400(self):
        devis = self._devis('api-derive')
        resp = self._client(devis).patch(
            '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk,
            {'cle': 'eco', 'config': {'nb_panneaux': 18, 'prix_ttc': 1}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix_ttc', json.dumps(resp.json()))
        devis.refresh_from_db()
        # RIEN n'a été stocké : un refus est un refus, pas un enregistrement
        # partiel.
        self.assertIn(devis.offres_tailles_config, (None, {}))

    def test_patch_n_affecte_QUE_la_taille_nommee(self):
        devis = self._devis('api-isole')
        api = self._client(devis)
        url = '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            api.patch(url, {'cle': 'eco', 'config': {'nb_panneaux': 18}},
                      format='json')
            api.patch(url, {'cle': 'max', 'config': {'nb_panneaux': 40}},
                      format='json')
            api.patch(url, {'cle': 'max', 'config': {'nb_panneaux': 44}},
                      format='json')
        devis.refresh_from_db()
        self.assertEqual(
            devis.offres_tailles_config['eco']['config']['nb_panneaux'], 18)
        self.assertEqual(
            devis.offres_tailles_config['max']['config']['nb_panneaux'], 44)

    def test_regenerer_ne_touche_QUE_la_taille_nommee(self):
        devis = self._devis('api-regen')
        api = self._client(devis)
        url = '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            api.patch(url, {'cle': 'eco', 'config': {'nb_panneaux': 18}},
                      format='json')
            api.patch(url, {'cle': 'max', 'config': {'nb_panneaux': 40}},
                      format='json')
            resp = api.post(
                '/api/django/ventes/devis/%s/offres-tailles/regenerer/'
                % devis.pk, {'cle': 'eco'}, format='json')
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        self.assertNotIn('eco', devis.offres_tailles_config)
        self.assertEqual(
            devis.offres_tailles_config['max']['config']['nb_panneaux'], 40)

    def test_une_taille_inconnue_repond_400(self):
        devis = self._devis('api-inconnue')
        resp = self._client(devis).post(
            '/api/django/ventes/devis/%s/offres-tailles/regenerer/' % devis.pk,
            {'cle': 'premium'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_un_devis_d_une_AUTRE_societe_repond_404_jamais_403(self):
        # Aucun oracle d'existence : un 403 dirait « ce devis existe ».
        devis = self._devis('api-mien')
        etrangere = self._company('api-etrangere')
        api = APIClient()
        api.force_authenticate(user=self._user(etrangere))
        for methode, url in (
                ('get', '/api/django/ventes/devis/%s/offres-tailles/'),
                ('patch', '/api/django/ventes/devis/%s/offres-tailles/config/'),
                ('post',
                 '/api/django/ventes/devis/%s/offres-tailles/regenerer/')):
            resp = getattr(api, methode)(url % devis.pk, {}, format='json')
            self.assertEqual(resp.status_code, 404, url)

    def test_les_trois_actions_sont_fermees_a_un_visiteur(self):
        devis = self._devis('api-anon')
        api = APIClient()
        for methode, url in (
                ('get', '/api/django/ventes/devis/%s/offres-tailles/'),
                ('patch', '/api/django/ventes/devis/%s/offres-tailles/config/'),
                ('post',
                 '/api/django/ventes/devis/%s/offres-tailles/regenerer/')):
            resp = getattr(api, methode)(url % devis.pk, {}, format='json')
            self.assertIn(resp.status_code, (401, 403), url)

    def test_VX199_les_trois_actions_sont_inscrites_dans_get_permissions(self):
        # Le piège : sans inscription, l'action tombe sur le repli
        # ``IsAdminRole`` et son ``permission_classes`` n'est JAMAIS consulté.
        # On compare donc la garde EFFECTIVE, pas la garde déclarée.
        from authentication.permissions import IsResponsableOrAdmin
        from apps.ventes.views.devis import DevisViewSet
        for action in ('offres_tailles', 'offres_tailles_config',
                       'offres_tailles_regenerer'):
            vue = DevisViewSet()
            vue.action = action
            classes = [type(p) for p in vue.get_permissions()]
            self.assertEqual(classes, [IsResponsableOrAdmin], action)
