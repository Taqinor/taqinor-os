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


def _client_de(company):
    """Le client OBLIGATOIRE d'un ``Devis`` (``client`` est un FK NOT NULL).

    Ces suites n'éprouvent ni le client ni la résolution de lead : elles
    ont juste besoin d'un devis qui EXISTE en base. Même patron que les
    fixtures voisines (``test_payload_paliers_batterie``,
    ``test_payload_couverture_batterie``) — jamais un devis orphelin.
    """
    return Client.objects.get_or_create(
        company=company, nom='Client %s' % company.slug, defaults={})[0]


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


def _contexte_factice(devis, *, module_kwh=5.0, capacite=None, plafond=None,
                      physique=None, remise=1.0):
    """Un contexte de dérivation sans catalogue ni base — la mécanique seule.

    TROIS NOMBRES DE TOIT, ET LEUR HIÉRARCHIE EST TOUT LE SUJET.
    ``plafond`` est ce que le commercial a DESSINÉ
    (``dimensionnement.plafond_toit_du_devis``) ; ``capacite`` est ce que la
    géométrie réelle TIENT (``calepinage_options.capacite_toit_du_devis``) ;
    ``physique`` est le MUR du tracé client (``aire ÷ empreinte``,
    ``dimensionnement.plafond_physique_du_devis``), ajouté le 28/08/2026 —
    c'est la seule borne qui subsiste sur un devis AUTOMATIQUE, dont le layout
    contour-seul n'a rien de mesurable.

    ``toit_max`` — le seul que la dérivation lit — est recopié ici EAGERLY
    (un ``SimpleNamespace`` ne porte pas la propriété du vrai
    :class:`~apps.ventes.offres_tailles._Contexte`) MAIS IL EST CALCULÉ PAR LA
    VRAIE RÈGLE (``dimensionnement.plus_grande_contenance``) : une fixture qui
    réimplémenterait la hiérarchie finirait par diverger de la production, et
    ces tests-ci verdiraient sur une règle qui n'existe plus. Un test qui veut
    bouger le verdict de toit peut toujours réécrire ``toit_max`` directement.
    """
    from apps.ventes.dimensionnement import plus_grande_contenance
    contexte = SimpleNamespace(
        devis=devis, entrees={}, panel_watt=710.0, catalogue=[],
        marques={}, ordre=[], module_batterie_kwh=module_kwh,
        facteur_remise=remise, plafond_toit=plafond, capacite_toit=capacite,
        plafond_physique=physique,
        toit_max=plus_grande_contenance(capacite, plafond, physique))
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

    def test_recommande_LIT_la_courbe_servie_au_lieu_de_la_refaire(self):
        # F1 — LE test de non-régression. ``cashflow_sans`` EST la série que la
        # page trace ; son dernier point + le prix = les économies encaissées.
        # Refaire le calcul ici donnerait un autre nombre (voir le test
        # suivant), et la carte finirait ailleurs que la courbe au-dessus.
        data = {'cashflow_sans': [-90000, -80000, 12345],
                'cashflow_avec': [-100000, 4321]}
        self.assertEqual(ot._cumul_servi(data, 'sans', 100000.0), 112345.0)
        self.assertEqual(ot._cumul_servi(data, 'avec', 100000.0), 104321.0)

    def test_sans_courbe_servie_aucun_cumul_reconstitue(self):
        self.assertIsNone(ot._cumul_servi({}, 'sans', 100000.0))
        self.assertIsNone(ot._cumul_servi({'cashflow_sans': []}, 'sans', 1.0))
        self.assertIsNone(ot._cumul_servi({'cashflow_sans': [1]}, 'sans', 0))

    def test_les_DEUX_arguments_de_la_page_changent_le_resultat(self):
        # F1 — la preuve que les omettre n'était pas anodin : sans
        # ``battery_share``, le moteur applique l'abattement 0,90 à TOUTE
        # l'économie (le bug Z5 que le fondateur a fait corriger le 20/08) ;
        # sans ``inverter_replace_cost``, aucune provision n'est retranchée.
        nu = ot._cumul_moteur(100000.0, 10000.0, stockage=True,
                              part_batterie=None, cout_onduleur_ttc=None)
        comme_la_page = ot._cumul_moteur(
            100000.0, 10000.0, stockage=True, part_batterie=0.3,
            cout_onduleur_ttc=20000.0)
        self.assertIsNotNone(nu)
        self.assertIsNotNone(comme_la_page)
        self.assertNotEqual(nu, comme_la_page)

    def test_la_part_batterie_reprend_la_formule_de_pricing(self):
        # (avec − sans) / avec, bornée à zéro — au caractère près.
        self.assertAlmostEqual(
            ot._part_batterie({'taux_autoconso_avec': 0.9,
                               'taux_autoconso_sans': 0.6}),
            (0.9 - 0.6) / 0.9)
        self.assertEqual(
            ot._part_batterie({'taux_autoconso_avec': 0.5,
                               'taux_autoconso_sans': 0.8}), 0.0)
        self.assertIsNone(ot._part_batterie({'taux_autoconso_avec': 0}))
        self.assertIsNone(ot._part_batterie({}))

    def test_aucune_provision_onduleur_sans_ligne_onduleur(self):
        # Q1 — le prix RÉEL de la ligne, jamais un pourcentage de repli.
        lignes = [SimpleNamespace(quantite=10, prix_unitaire=1000,
                                  produit=None)]
        self.assertIsNone(ot._cout_onduleur_ttc(lignes, ['panneau'], 1.0))

    def test_la_provision_onduleur_est_remisee_comme_le_prix(self):
        lignes = [SimpleNamespace(quantite=1, prix_unitaire=10000,
                                  produit=None)]
        plein = ot._cout_onduleur_ttc(lignes, ['onduleur_hybride'], 1.0)
        remise = ot._cout_onduleur_ttc(lignes, ['onduleur_hybride'], 0.9)
        self.assertEqual(plein, 12000.0)          # 10 000 × 1,20 (TVA repli)
        self.assertEqual(remise, round(plein * 0.9, 2))

    def test_aucune_entree_aucun_cumul(self):
        self.assertIsNone(ot._cumul_moteur(
            None, 10000.0, stockage=False, part_batterie=None,
            cout_onduleur_ttc=None))
        self.assertIsNone(ot._cumul_moteur(
            100000.0, 0, stockage=False, part_batterie=None,
            cout_onduleur_ttc=None))

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
        # QX39 — la série cumulée que la page trace déjà.
        'cashflow_sans': [-95000, -80000, 222899.45],
        'cashflow_avec': [-130000, -110000, 277299.75],
    }

    def _bloc_horaire(self, kwc=12.1):
        """Un bloc horaire qui PASSE la garde anti-périmé de ``pricing``."""
        return {
            'kwc': kwc,
            'annuel': {
                'production_kwh': 19140.0, 'consommation_kwh': 21000.0,
                'economie_sans_mad': 13260.4, 'economie_avec_mad': 17880.9,
                'couverture_sans': 0.61, 'couverture_avec': 0.794,
                'taux_autoconso_sans': 0.628, 'taux_autoconso_avec': 0.926,
            },
            'mois': [{'economie_sans_mad': 1105.0,
                      'economie_avec_mad': 1490.0} for _ in range(12)],
        }

    def _contexte(self, kwc=12.1):
        devis = SimpleNamespace(
            etude_params={'etude_horaire': self._bloc_horaire(kwc)},
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

    def test_le_cumul_25_ans_est_le_BOUT_de_la_courbe_servie(self):
        # F1 — 222 899,45 (dernier point) + 108 900,55 (prix) = 331 800,00.
        sans = ot._carte_du_devis(self._contexte(), self.DATA, 'sans')
        self.assertEqual(sans['economies_cumulees_25_ans_mad'], 331800.0)

    def test_un_bloc_horaire_PERIME_ne_sert_aucun_taux(self):
        # F2 — LE test de non-régression. Le bloc a été calculé à 12,1 kWc ;
        # la carte « avec » de ce devis à deux options fait 14,3 kWc. Ses
        # chiffres décrivent donc une AUTRE installation : la garde CJ2a de
        # ``pricing._lire_etude_horaire`` les refuse, et la carte les OMET
        # plutôt que d'afficher « couverture 79,4 % » à côté du bon prix.
        avec = ot._carte_du_devis(self._contexte(), self.DATA, 'avec')
        self.assertNotIn('couverture_pct', avec)
        self.assertNotIn('taux_autoconsommation_pct', avec)
        # Le reste de la carte reste servi.
        self.assertEqual(avec['prix_ttc'], 142700.25)

    def test_un_bloc_horaire_A_JOUR_sert_les_taux_de_la_variante(self):
        # Le cas normal (devis mono-champ) : le bloc décrit bien cette taille.
        contexte = self._contexte(kwc=14.3)
        avec = ot._carte_du_devis(contexte, self.DATA, 'avec')
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

    def test_un_bloc_horaire_TRONQUE_est_refuse_comme_perime(self):
        # Onze mois au lieu de douze : la garde de ``pricing`` refuse — et
        # cette carte-ci n'a pas le droit d'être plus laxiste que le PDF.
        bloc = self._bloc_horaire()
        bloc['mois'] = bloc['mois'][:11]
        contexte = _contexte_factice(SimpleNamespace(
            etude_params={'etude_horaire': bloc}, reference='DEV-X'))
        sans = ot._carte_du_devis(contexte, self.DATA, 'sans')
        self.assertNotIn('couverture_pct', sans)

    def test_sans_calepinage_aucun_verdict_de_toit(self):
        sans = ot._carte_du_devis(self._contexte(), self.DATA, 'sans')
        self.assertNotIn('toit_ok', sans)

    def test_avec_calepinage_le_verdict_de_toit_est_reel(self):
        # LE VERDICT SE LIT SUR LA CONTENANCE, pas sur le nombre de panneaux
        # dessinés : c'est ``toit_max`` que ``_ajouter_toit`` interroge.
        contexte = self._contexte()
        contexte.capacite_toit = contexte.toit_max = 24
        self.assertIs(
            ot._carte_du_devis(contexte, self.DATA, 'sans')['toit_ok'], True)
        # 26 panneaux ne tiennent pas sur un toit qui en accepte 24.
        self.assertIs(
            ot._carte_du_devis(contexte, self.DATA, 'avec')['toit_ok'], False)

    def test_le_verdict_de_toit_suit_la_CONTENANCE_pas_le_dessin(self):
        # LA RÉGRESSION QUE CE TEST INTERDIT (26/08/2026). Le commercial a
        # dessiné 22 panneaux ; la géométrie du toit en tient 30. Comparer au
        # DESSIN aurait collé « cette taille dépasse votre toit » à une carte de
        # 26 panneaux que le toit accepte parfaitement — et l'aurait collé
        # PRÉCISÉMENT à la carte Max, le jour où elle se met enfin à proposer
        # davantage.
        contexte = self._contexte()
        contexte.plafond_toit = 22
        contexte.capacite_toit = 30
        contexte.toit_max = 30
        self.assertIs(
            ot._carte_du_devis(contexte, self.DATA, 'avec')['toit_ok'], True)

    def test_le_mur_physique_ne_prononce_AUCUN_verdict_par_carte(self):
        # DEVIS AUTOMATIQUE (revue Fable, 28/08/2026) : rien de mesurable, un
        # tracé qui porte un mur physique. Le mur PLAFONNE la carte Max, mais un
        # contour peut n'avoir été tracé QUE PARTIELLEMENT — il n'a donc le
        # droit ni de dire « ça rentre » ni de dire « ça dépasse » sur une
        # carte : ``toit_ok`` est OMIS, dans les deux sens.
        contexte = self._contexte()
        contexte.plafond_toit = 22
        contexte.capacite_toit = None
        contexte.plafond_physique = 60
        contexte.toit_max = 60
        self.assertNotIn('toit_ok',
                         ot._carte_du_devis(contexte, self.DATA, 'avec'))
        # Y compris quand la carte DÉPASSE le mur : la carte du devis OFFICIEL
        # sur un tracé partiel ne doit jamais s'afficher « dépasse votre
        # toit ». Le mur, lui, continue de plafonner Max (testé côté
        # ``_champs_des_tailles``).
        contexte.plafond_physique = 24
        contexte.toit_max = 24
        self.assertNotIn('toit_ok',
                         ot._carte_du_devis(contexte, self.DATA, 'avec'))

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
                 capacite=None, physique=None, cartes=None):
        devis = SimpleNamespace(
            etude_params={'dimensionnement': {'tableau': tableau}},
            offres_tailles_config=config, reference='DEV-X')
        contexte = _contexte_factice(devis, plafond=plafond,
                                     capacite=capacite, physique=physique)
        cartes = cartes or {'sans': _carte(), 'avec': _carte()}

        def _moteur(_contexte_, nb, _config=None, *, avec_servable=True):
            # Le faux moteur HONORE ``avec_servable`` exactement comme le vrai :
            # un mock qui l'ignorerait ferait passer un test que la production
            # échouerait (la variante batterie doit disparaître AVANT le calcul,
            # pas être filtrée après).
            return {'sans': dict(cartes['sans'], nb_panneaux=nb),
                    'avec': (dict(cartes['avec'], nb_panneaux=nb)
                             if avec_servable else None)}

        with mock.patch.object(ot, '_contexte', return_value=contexte), \
                mock.patch.object(ot, '_carte_moteur', side_effect=_moteur), \
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

    def test_max_est_LA_CONTENANCE_du_toit_quand_un_calepinage_existe(self):
        # LA CORRECTION DU 26/08/2026, ARMÉE. « Max » n'est plus la dernière
        # taille du BALAYAGE rabotée par le toit : c'est LA CONTENANCE du toit
        # elle-même. Le balayage s'arrête à 26 ; la géométrie tient 28 ⇒ Max
        # vaut 28. Sous l'ancienne règle il valait 26, c'est-à-dire moins que ce
        # que le toit accepte — et sur un devis réel, exactement le champ déjà
        # dessiné, donc une carte qui ne proposait rien.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (26, 9.0), (34, 11.0)),
            capacite=28)
        self.assertEqual(bloc['plafond_toit_panneaux'], 28)
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 28)

    def test_max_DEPASSE_le_champ_dessine_le_bug_du_devis_live(self):
        # LE BUG, REPRODUIT À L'IDENTIQUE. Sur le devis live test15 le
        # commercial avait dessiné 15 panneaux ; « Recommandé » est
        # resynchronisé sur ce dessin, et « Max » s'ancrait sur LE MÊME nombre
        # ⇒ les deux cartes portaient 15, la signature les dédupliquait, et
        # trois cartes n'apparaissaient JAMAIS. La contenance mesurée (24) rend
        # la troisième carte à sa raison d'être.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (15, 8.0)),
            data={'nb_panneaux_sans': 15,
                  'variantes_servables': ['sans', 'avec']},
            # LES CARTES SUIVENT LE DEVIS, ET IL FAUT LE DIRE AU HARNAIS.
            # ``_deriver`` bouchonne ``_carte_du_devis`` par ``dict(cartes[v])``
            # SANS réécrire ``nb_panneaux`` — c'est fidèle à la production, où
            # la carte « Recommandé » est REPRISE telle quelle du devis et
            # n'est jamais recomposée. Les cartes par défaut portent 22 (le
            # champ de ``DATA``) : sans ce pin, « Recommandé » annonçait 22
            # alors que ``data`` dit 15, et le test comparait deux fixtures
            # entre elles. ``_carte_moteur``, lui, réécrit bien le champ —
            # d'où Éco et Max corrects sans rien préciser.
            cartes={'sans': _carte(nb_panneaux=15),
                    'avec': _carte(nb_panneaux=15)},
            plafond=15, capacite=24)
        cles = [o['cle'] for o in bloc['offres']]
        self.assertEqual(cles, ['eco', 'recommande', 'max'])
        recommande = next(o for o in bloc['offres']
                          if o['cle'] == 'recommande')
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(recommande['sans']['nb_panneaux'], 15)
        self.assertEqual(maxi['sans']['nb_panneaux'], 24)
        self.assertGreater(maxi['sans']['nb_panneaux'],
                           recommande['sans']['nb_panneaux'])

    def test_toit_sature_max_converge_au_lieu_de_depasser(self):
        # LE COLLAPSE RESTE, MAIS SEULEMENT POUR UNE VRAIE CONVERGENCE : le
        # devis (22) occupe DÉJÀ toute la contenance mesurée (22). « Max » n'a
        # rien à proposer et disparaît. On ne fabrique pas une taille plus
        # grande que le toit.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)), capacite=22)
        self.assertNotIn('max', [o['cle'] for o in bloc['offres']])

    def test_une_contenance_SOUS_le_devis_ne_rapetisse_jamais_la_carte_max(self):
        # Garde-fou de non-régression : si la contenance mesurée tombe SOUS le
        # champ du devis (layout dont le ``result.panels`` déclaré dépasse les
        # panneaux réellement sérialisés), « Max » ne devient pas une carte plus
        # PETITE que « Recommandé » — elle converge et disparaît.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)), capacite=18)
        self.assertNotIn('max', [o['cle'] for o in bloc['offres']])

    def test_sans_calepinage_max_reste_la_derniere_taille_du_balayage(self):
        # LE REPLI EST INCHANGÉ : sans calepinage, aucune contenance n'est
        # mesurable et « Max » reste la dernière taille éligible du balayage,
        # avec ses bornes à lui. Aucune clé de plafond n'est publiée.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)))
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 34)
        self.assertNotIn('plafond_toit_panneaux', bloc)

    # ── DEVIS AUTOMATIQUE : LE LAYOUT CONTOUR-SEUL (28/08/2026) ───────────
    #
    # ``services.zone_toit_depuis_contour`` pose le tracé du client et écrit
    # ``result.panels`` = LA CIBLE VENDUE, sans sérialiser un seul panneau.
    # Donc : ``capacite_toit`` = None (rien à mesurer) et ``plafond_toit`` =
    # le champ du devis. Lire ce dernier comme un plafond de toit effondrait
    # Max sur Recommandé sur TOUS les devis automatiques — et la simple
    # présence du layout court-circuitait le repli « dernière taille éligible ».

    def test_devis_AUTO_contour_seul_max_redevient_la_derniere_taille(self):
        # LE BUG ORDONNÉ, REPRODUIT : 22 panneaux vendus et dessinés, aucune
        # géométrie mesurable, un tracé qui pourrait en porter 60. Max doit
        # valoir 34 (la dernière taille éligible), PAS 22.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            plafond=22, capacite=None, physique=60)
        cles = [o['cle'] for o in bloc['offres']]
        self.assertEqual(cles, ['eco', 'recommande', 'max'])
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        recommande = next(o for o in bloc['offres']
                          if o['cle'] == 'recommande')
        self.assertEqual(maxi['sans']['nb_panneaux'], 34)
        self.assertGreater(maxi['sans']['nb_panneaux'],
                           recommande['sans']['nb_panneaux'])

    def test_devis_AUTO_sans_trace_exploitable_max_reste_le_balayage(self):
        # Aucun mur physique lisible (pas de fiche technique, tracé illisible) :
        # le dessin ne reprend PAS la main pour autant. Max reste la dernière
        # taille éligible — jamais le champ vendu.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            plafond=22, capacite=None, physique=None)
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 34)

    def test_le_MUR_PHYSIQUE_du_trace_plafonne_vraiment_max(self):
        # Un petit toit : le balayage irait à 34, la surface n'en porte que 26.
        # Max est PLAFONNÉ, jamais proposé au-delà du physiquement possible.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            plafond=22, capacite=None, physique=26)
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 26)

    def test_le_mur_physique_ne_PROPOSE_jamais_un_champ(self):
        # Le mur (60) est au-dessus de tout le balayage (34) : il ne fait que
        # refuser l'impossible, il ne pousse JAMAIS Max au-delà d'une taille
        # que le balayage a réellement jugée éligible.
        bloc = self._deriver(tableau=_tableau((10, 6.0), (22, 8.0)),
                             plafond=22, capacite=None, physique=60)
        # 22 == le devis : Max converge et disparaît plutôt que d'inventer 60.
        self.assertNotIn('max', [o['cle'] for o in bloc['offres']])

    def test_max_du_repli_ne_descend_JAMAIS_sous_le_devis(self):
        # REVUE FABLE (28/08/2026) — le plancher de la branche mesurée existe
        # aussi dans le repli : balayage court (16) et tracé PARTIEL (mur 14)
        # sous le champ du devis (22) ⇒ Max ne devient pas une carte plus
        # PETITE que « Recommandé » — elle converge sur le devis et disparaît,
        # exactement comme dans la branche mesurée. Un ordre Éco → Recommandé →
        # Max où Max serait la plus petite carte est un mensonge d'affichage.
        bloc = self._deriver(tableau=_tableau((10, 6.0), (16, 8.0)),
                             plafond=None, capacite=None, physique=14)
        cles = [o['cle'] for o in bloc['offres']] if bloc else []
        self.assertNotIn('max', cles)
        for offre in (bloc or {}).get('offres', []):
            if offre['cle'] == 'recommande':
                continue
            self.assertLessEqual(offre['sans']['nb_panneaux'], 22)

    def test_le_mur_physique_n_est_JAMAIS_publie_comme_plafond_de_toit(self):
        # « plafond_toit_panneaux » nomme LA CONTENANCE MESURÉE. Le mur (aire ÷
        # empreinte) est large par construction : le publier sous ce nom
        # annoncerait au client un toit qu'aucun calepinage ne saurait remplir.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)),
            plafond=22, capacite=None, physique=60)
        self.assertNotIn('plafond_toit_panneaux', bloc)

    def test_le_compte_DESSINE_seul_ne_publie_aucun_plafond(self):
        # Ni contenance ni tracé : aucune borne de toit, donc aucune clé — et
        # surtout pas le champ vendu déguisé en plafond.
        bloc = self._deriver(
            tableau=_tableau((10, 6.0), (22, 8.0), (34, 11.0)), plafond=22)
        self.assertNotIn('plafond_toit_panneaux', bloc)
        maxi = next(o for o in bloc['offres'] if o['cle'] == 'max')
        self.assertEqual(maxi['sans']['nb_panneaux'], 34)

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

        def _moteur(_contexte_, nb, _config=None, *, avec_servable=True):
            return {'sans': dict(sans_batterie, nb_panneaux=nb),
                    'avec': (dict(sans_batterie, nb_panneaux=nb)
                             if avec_servable else None)}

        def _devis_carte(_contexte_, _data, variante):
            # La référence est FIABLE : sans ce marqueur, « ce qui change » se
            # tait (et le test ne prouverait rien).
            return dict(_carte(), _familles_fiables=True)

        with mock.patch.object(ot, '_contexte', return_value=contexte), \
                mock.patch.object(ot, '_carte_moteur', side_effect=_moteur), \
                mock.patch.object(ot, '_carte_du_devis',
                                  side_effect=_devis_carte):
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

    # ── ENVOI 1/2/3 OPTIONS (fondateur, 28/08/2026) ───────────────────────
    #
    # Le vendeur choisit dans le dialogue d'envoi COMBIEN de tailles le client
    # voit. Le filtrage a lieu APRÈS la dérivation — filtrer avant changerait
    # les chiffres des cartes restantes (« ce qui change » se calcule contre
    # Recommandé, et la convergence le regarde lui aussi).

    def _publique(self, cles_servies):
        devis = SimpleNamespace(reference='DEV-X')
        trois = {'offres': [{'cle': 'eco'}, {'cle': 'recommande'},
                            {'cle': 'max'}]}
        with mock.patch.object(ot, 'deriver', return_value=trois):
            return ot.offres_tailles_publique(devis, {}, cles_servies)

    def test_ENVOI_defaut_None_sert_les_trois_tailles(self):
        # Tout lien DÉJÀ envoyé (aucune case posée) garde ses trois cartes.
        bloc = self._publique(None)
        self.assertEqual([o['cle'] for o in bloc['offres']],
                         ['eco', 'recommande', 'max'])

    def test_ENVOI_deux_options_ne_sert_que_la_taille_gardee(self):
        for gardee in ('eco', 'max'):
            with self.subTest(gardee=gardee):
                bloc = self._publique({'recommande', gardee})
                self.assertEqual(
                    sorted(o['cle'] for o in bloc['offres']),
                    sorted(['recommande', gardee]))

    def test_ENVOI_une_seule_option_fait_DISPARAITRE_la_section(self):
        # C'est exactement ce que le vendeur demande : la page redevient
        # celle d'avant les cartes. Le seuil de deux porte sur les cartes
        # SERVIES, pas sur les cartes dérivables.
        self.assertIsNone(self._publique({'recommande'}))

    def test_ENVOI_recommande_n_est_JAMAIS_retirable(self):
        # C'est LE devis : la seule carte autorisée à ouvrir la signature.
        # Même un ensemble qui l'oublie le récupère.
        bloc = self._publique({'eco', 'max'})
        self.assertIn('recommande', [o['cle'] for o in bloc['offres']])

    def test_ENVOI_le_filtrage_ne_MUTE_pas_le_bloc_derive(self):
        # Le bloc dérivé est aussi lu par l'API vendeur et par les dessins
        # par option : le filtrage public ne doit pas le rogner sous eux.
        devis = SimpleNamespace(reference='DEV-X')
        trois = {'offres': [{'cle': 'eco'}, {'cle': 'recommande'},
                            {'cle': 'max'}]}
        with mock.patch.object(ot, 'deriver', return_value=trois):
            ot.offres_tailles_publique(devis, {}, {'recommande', 'eco'})
        self.assertEqual([o['cle'] for o in trois['offres']],
                         ['eco', 'recommande', 'max'])


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

    def test_les_prix_par_kwc_du_contrat_sont_CEUX_du_serveur(self):
        # F7 — PACT10 : la lane web construit CONTRE ce fichier. Une valeur à
        # deux décimales lui ferait écrire un formateur pour un nombre que le
        # serveur n'émet jamais (il fait ``float(round(prix / kwc))``).
        for cle, exemple in self.contrat.items():
            if not cle.startswith('exemple') or not isinstance(exemple, dict):
                continue
            bloc = exemple.get('offres_tailles')
            if not isinstance(bloc, dict):
                continue
            for offre in bloc.get('offres') or []:
                for variante in ('sans', 'avec'):
                    carte = offre.get(variante) or {}
                    if 'prix_par_kwc_ttc' not in carte:
                        continue
                    self.assertEqual(
                        carte['prix_par_kwc_ttc'],
                        ot._prix_par_kwc(carte['prix_ttc'],
                                         carte['puissance_kwc']),
                        '%s/%s/%s' % (cle, offre['cle'], variante))

    def test_le_contrat_declare_les_DEUX_cases_d_envoi_de_tailles(self):
        # PACT10 — la lane web et la lane ERP construisent CONTRE ce fichier :
        # les deux clés de sections doivent y être nommées, et le contrat doit
        # dire que « Recommandé » n'est pas retirable (sans quoi le dialogue
        # d'envoi finirait par proposer de la décocher).
        note = self.contrat['notes']['options_envoyees']
        for cle in ('taille_eco', 'taille_max'):
            self.assertIn(cle, note)
            self.assertIn(cle, ShareLink.SECTIONS_CLES)
        self.assertNotIn('taille_recommande', ShareLink.SECTIONS_CLES)

    def test_le_contrat_dit_que_le_seuil_porte_sur_les_cartes_SERVIES(self):
        self.assertIn('SERVIES',
                      self.contrat['notes']['deux_tailles_minimum'])

    def test_aucun_champ_PRIVE_ne_figure_au_contrat(self):
        brut = CONTRAT.read_text(encoding='utf-8')
        self.assertNotIn('"_familles_fiables"', brut)

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

class MaterielDuDevisTests(TestCase):
    """F4/F5 — la carte nomme le matériel DE SA VARIANTE, classé comme le
    catalogue le classe."""

    def _devis_deux_options(self):
        from authentication.models import Company
        company = Company.objects.create(slug='mat', nom='mat')
        devis = Devis.objects.create(
            company=company, reference='DEV-MAT-01', statut='envoye',
            client=_client_de(company), taux_tva=Decimal('20'),
            mode_installation='residentiel')
        lignes = (
            ('Panneau Canadien Solar 710W', '', '14'),
            ('Onduleur réseau Huawei 10kW Monophasé', 'sans', '1'),
            ('Onduleur hybride Deye 10kW Monophasé', 'avec', '1'),
            ('Batterie Dyness 5 kWh', 'avec', '2'),
        )
        for nom, variante, qte in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente='1000',
                marque=nom.split()[1], quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), variante=variante)
        return devis

    def test_la_carte_SANS_ne_nomme_ni_batterie_ni_onduleur_hybride(self):
        # Le bug : lire toutes les lignes faisait lister la BATTERIE sur la
        # carte « sans batterie » — la carte décrivait l'autre option.
        materiel, _ = ot._materiel_du_devis(self._devis_deux_options(), 'sans')
        familles = {e['famille'] for e in materiel}
        self.assertNotIn('batterie', familles)
        onduleur = next(e for e in materiel if e['famille'] == 'onduleur')
        self.assertEqual(onduleur['role'], 'onduleur_reseau')

    def test_la_carte_AVEC_nomme_l_onduleur_HYBRIDE_et_la_batterie(self):
        # Le bug symétrique : la première ligne onduleur rencontrée était
        # celle du RÉSEAU, donc la carte « avec batterie » annonçait un
        # onduleur incapable de gérer une batterie.
        materiel, _ = ot._materiel_du_devis(self._devis_deux_options(), 'avec')
        familles = {e['famille'] for e in materiel}
        self.assertIn('batterie', familles)
        onduleur = next(e for e in materiel if e['famille'] == 'onduleur')
        self.assertEqual(onduleur['role'], 'onduleur_hybride')

    def test_les_lignes_COMMUNES_sont_dans_les_deux_cartes(self):
        # UN seul devis pour les deux lectures : le construire dans la boucle
        # recréait la Company slug='mat' dans la même transaction (violation
        # d'unicité — rouge CI ronde 3).
        devis = self._devis_deux_options()
        for variante in ('sans', 'avec'):
            materiel, _ = ot._materiel_du_devis(devis, variante)
            self.assertIn('panneau', {e['famille'] for e in materiel})

    def test_le_role_vient_du_classifieur_CATALOGUE(self):
        # F5 — même source des deux côtés : ``services.classer_produit``, celui
        # que la composition utilise pour poser ses rôles.
        self.assertEqual(ot._role_de_la_ligne('Onduleur hybride Deye 10kW'),
                         'onduleur_hybride')
        self.assertEqual(ot._role_de_la_ligne('Onduleur réseau Huawei 10kW'),
                         'onduleur_reseau')
        self.assertEqual(ot._role_de_la_ligne('Panneau 710W'), 'panneau')
        self.assertIsNone(ot._role_de_la_ligne('Forfait déplacement'))

    def test_une_ligne_non_classee_se_SIGNALE(self):
        from authentication.models import Company
        company = Company.objects.create(slug='mat2', nom='mat2')
        devis = Devis.objects.create(
            company=company, reference='DEV-MAT-02', statut='envoye',
            client=_client_de(company), taux_tva=Decimal('20'),
            mode_installation='residentiel')
        produit = Produit.objects.create(
            company=company, nom='Boîtier exotique', prix_vente='500',
            quantite_stock=1)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Boîtier exotique',
            quantite=Decimal('1'), prix_unitaire=Decimal('500'),
            remise=Decimal('0'))
        _materiel, tout_classe = ot._materiel_du_devis(devis, 'sans')
        self.assertIs(tout_classe, False)

    def test_une_reference_NON_FIABLE_fait_taire_ce_qui_change(self):
        # F5 — une famille manquée côté référence ferait accuser les autres
        # tailles d'un ajout imaginaire. Mieux vaut aucune comparaison.
        offres = [
            {'cle': 'recommande',
             'sans': {'familles': ['panneau'], '_familles_fiables': False}},
            {'cle': 'eco', 'sans': {'familles': ['onduleur', 'panneau']}},
        ]
        ot._poser_diff_familles(offres)
        self.assertNotIn('familles_diff', offres[1]['sans'])

    def test_une_reference_FIABLE_publie_ce_qui_change(self):
        offres = [
            {'cle': 'recommande',
             'sans': {'familles': ['batterie', 'panneau'],
                      '_familles_fiables': True}},
            {'cle': 'eco', 'sans': {'familles': ['panneau']}},
        ]
        ot._poser_diff_familles(offres)
        self.assertEqual(offres[1]['sans']['familles_diff'],
                         {'ajoutees': [], 'retirees': ['batterie']})

    def test_les_champs_PRIVES_ne_sortent_jamais(self):
        offres = [{'cle': 'recommande',
                   'sans': {'familles': ['panneau'],
                            '_familles_fiables': True}}]
        ot._retirer_champs_prives(offres)
        self.assertEqual(list(offres[0]['sans']), ['familles'])


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
            client=_client_de(company), taux_tva=Decimal('20'),
            mode_installation='residentiel')

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

    def test_ecrire_ne_gele_NI_ne_bouge_prix_par_kwc(self):
        # SCA47 — ``Devis.save`` DÉRIVE ET GÈLE ``prix_par_kwc`` (write-once)
        # dès qu'un kWc et un total existent. Passer par ``save(update_fields=…)``
        # aurait donc pu figer, au passage d'une exploration, une colonne
        # interne que ce geste ne concerne pas. On écrit LA colonne, seule.
        devis = self._devis()
        devis.etude_params = {'puissance_kwc': 12.1}
        devis.save()
        gele_avant = devis.prix_par_kwc
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        devis.refresh_from_db()
        self.assertEqual(devis.prix_par_kwc, gele_avant)

    def test_ecrire_ne_fait_pas_passer_le_devis_pour_MODIFIE(self):
        # VX98 — ``updated_at`` (auto_now) aurait avancé et la page aurait
        # affiché « modifié il y a N minutes » sur un devis dont rien de
        # contractuel n'a bougé.
        devis = self._devis()
        avant = Devis.objects.values_list(
            'updated_at', flat=True).get(pk=devis.pk)
        ot.enregistrer_config(devis, 'eco', {'nb_panneaux': 12})
        apres = Devis.objects.values_list(
            'updated_at', flat=True).get(pk=devis.pk)
        self.assertEqual(avant, apres)

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

    def test_IMBRIQUE_le_refus_fonctionne_aussi_comme_CHAMP(self):
        # F6 — LE test qui manquait. Construit avec ``data=``, DRF pose
        # ``initial_data`` ; IMBRIQUÉ comme champ d'un parent — le seul chemin
        # que la production prend — il ne le pose PAS, et lire
        # ``self.initial_data`` depuis ``validate()`` levait un AttributeError
        # (500 sur chaque PATCH). Le refus vit maintenant dans
        # ``to_internal_value``, qui reçoit le dict brut dans les DEUX cas.
        from apps.ventes.serializers import OffreTailleEcritureSerializer
        serializer = OffreTailleEcritureSerializer(
            data={'cle': 'eco',
                  'config': {'nb_panneaux': 12, 'prix_ttc': 1}},
            context={'company': self.company})
        self.assertFalse(serializer.is_valid())
        self.assertIn('prix_ttc', json.dumps(serializer.errors))

    def test_IMBRIQUE_une_config_legitime_passe(self):
        from apps.ventes.serializers import OffreTailleEcritureSerializer
        serializer = OffreTailleEcritureSerializer(
            data={'cle': 'eco', 'config': {'nb_panneaux': 12}},
            context={'company': self.company})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data['config']['nb_panneaux'], 12)

    def test_un_produit_SANS_PRIX_est_refuse(self):
        # F3 — le catalogue en contient délibérément (les 11 pompes OSP sont
        # « prix à renseigner »). Substituer un produit à 0 MAD afficherait
        # une batterie GRATUITE sur une carte client.
        gratuit = Produit.objects.create(
            company=self.company, nom='Batterie sans prix', prix_vente='0',
            quantite_stock=1)
        serializer = self._config({'equipements': {'batterie': gratuit.pk}})
        self.assertFalse(serializer.is_valid())
        self.assertIn('batterie', serializer.errors['equipements'])

    def test_zero_module_de_batterie_est_refuse_BRUYAMMENT(self):
        # « Sans batterie » s'exprime par la VARIANTE, pas par zéro module :
        # la carte « avec » aurait disparu sans que personne ne sache pourquoi.
        serializer = self._config({'batterie_nb_modules': 0})
        self.assertFalse(serializer.is_valid())
        self.assertIn('batterie_nb_modules', serializer.errors)

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

    def test_section_economies_decochee_retire_les_tailles(self):
        # Ce bloc EST un bloc d'économies (prix, économie, payback, cumul
        # 25 ans) : décocher « Économies » dans le dialogue d'envoi doit les
        # emporter ensemble, sinon la case est contournable par une autre
        # section de la même page.
        devis = self._devis('pub-section')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            payload = self._payload(devis, sections={'economies': False})
        self.assertNotIn('offres_tailles', payload)

    def test_sections_par_defaut_servent_les_tailles(self):
        devis = self._devis('pub-defaut')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            payload = self._payload(devis)
        self.assertIn('offres_tailles', payload)

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

    def test_patch_LEGITIME_repond_200_et_pas_500(self):
        # F6 — LE test de bout en bout qui manquait. Mes tests unitaires
        # construisaient le sérialiseur avec ``data=`` : un chemin que la
        # production ne prend JAMAIS. Ici on passe par l'action réelle, donc
        # par le sérialiseur IMBRIQUÉ — celui qui levait un AttributeError
        # (HTTP 500) sur CHAQUE appel, légitime ou non.
        devis = self._devis('api-200')
        with mock.patch('apps.ventes.offres_tailles.deriver',
                        return_value=self._BLOC):
            resp = self._client(devis).patch(
                '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk,
                {'cle': 'eco', 'config': {'nb_panneaux': 18}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])

    def test_patch_d_un_champ_derive_repond_400_ET_PAS_500(self):
        # Le pendant du précédent : le refus doit être un 400 LISIBLE, pas un
        # 500 — et surtout pas un 200 « ignoré en silence », ce qu'un
        # ``getattr(self, 'initial_data', {})`` aurait produit (DRF écarte les
        # clés inconnues, donc le champ serait passé sans un mot).
        devis = self._devis('api-400')
        resp = self._client(devis).patch(
            '/api/django/ventes/devis/%s/offres-tailles/config/' % devis.pk,
            {'cle': 'eco', 'config': {'nb_panneaux': 18,
                                      'economie_annuelle_mad': 99999}},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertIn('economie_annuelle_mad', json.dumps(resp.json()))

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


class AppliquerAuDevisTests(_Base):
    """« RECOMMANDÉ » EST LE DEVIS : l'ajuster doit RECOMPOSER le devis.

    LE TROU QUE CES TESTS FERMENT (ordre fondateur, 29/08/2026). Écrire la
    configuration d'une taille n'écrit QUE ``offres_tailles_config``. Pour Éco
    et Max c'est le contrat exact — ce sont des explorations. Pour
    « Recommandé », la carte se mettait à être dérivée par le moteur pendant
    que le devis officiel — ses lignes, ses totaux, son PDF, la page du client
    — ne bougeait pas d'un panneau : « les modifications ne changent rien au
    devis », mot pour mot.

    Chaque test ci-dessous protège UNE garde, et aucune n'est décorative :
    l'exploration reste une exploration, le statut n'est jamais écrit, une
    ligne négociée n'est jamais réécrite en silence, un refus n'écrit RIEN, et
    la configuration appliquée est CONSOMMÉE (le devis devient la vérité).
    """

    def _prepare(self, slug, config, *, statut='brouillon'):
        """Un devis portant une configuration « Recommandé » à appliquer."""
        devis = self._devis(slug)
        Devis.objects.filter(pk=devis.pk).update(statut=statut)
        devis.refresh_from_db()
        ot.enregistrer_config(devis, 'recommande', config)
        return devis

    def _contexte(self, devis):
        """Le contexte RÉDUIT à ce que ``appliquer_au_devis`` lui demande.

        Le moteur de dérivation a ses propres tests ; ici on éprouve la
        RECOMPOSITION, pas le balayage. Le wattage est celui du panneau que la
        fixture vend, pour que le kWc recomposé décrive bien ce devis-là.
        """
        return SimpleNamespace(panel_watt=710.0,
                               entrees={'company': devis.company})

    def _panneaux(self, devis):
        return int(devis.lignes.get(
            designation__startswith='Panneau').quantite)

    # ── Le geste NOMINAL ────────────────────────────────────────────────────

    def test_appliquer_RECOMPOSE_les_lignes_du_devis(self):
        devis = self._prepare('app-ok', {'nb_panneaux': 20})
        self.assertEqual(self._panneaux(devis), 14)
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            resume = ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        self.assertEqual(self._panneaux(devis), 20)
        self.assertEqual(resume['panneaux_avant'], 14)
        self.assertEqual(resume['panneaux'], 20)

    def test_la_config_appliquee_est_CONSOMMEE(self):
        # Le devis EST désormais la vérité : un marqueur « Ajusté » résiduel
        # ferait redériver la carte par le moteur au lieu de la REPRENDRE du
        # devis — et afficherait un badge que plus rien ne distingue.
        devis = self._prepare('app-consomme', {'nb_panneaux': 18})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        self.assertNotIn('recommande', ot.lire_config_stockee(devis))

    def test_le_chatter_dit_QUI_a_applique_QUOI(self):
        from apps.ventes.models import DevisActivity
        devis = self._prepare('app-chatter', {'nb_panneaux': 19})
        user = self._user(devis.company)
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            ot.appliquer_au_devis(devis, 'recommande', utilisateur=user)
        activite = DevisActivity.objects.filter(
            devis=devis, field='offres_tailles.recommande').first()
        self.assertIsNotNone(activite)
        self.assertEqual(activite.user_id, user.pk)
        self.assertEqual(activite.company_id, devis.company_id)
        self.assertEqual(activite.old_value, '14 panneaux')
        self.assertIn('19 panneaux', activite.new_value)

    def test_le_STATUT_n_est_JAMAIS_ecrit(self):
        # Règle #4 : ce chemin LIT les statuts, il ne les écrit pas.
        devis = self._prepare('app-statut', {'nb_panneaux': 20})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')

    def test_la_banque_batterie_suit_le_compte_demande(self):
        devis = self._prepare('app-batt', {'nb_panneaux': 16,
                                           'batterie_nb_modules': 5})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        ligne = devis.lignes.get(designation__startswith='Batterie')
        self.assertEqual(int(ligne.quantite), 5)

    # ── Les REFUS, et le fait qu'ils n'écrivent RIEN ────────────────────────

    def test_ECO_et_MAX_ne_s_appliquent_JAMAIS_au_devis(self):
        # Ce sont des cartes d'EXPLORATION montrées à côté de l'offre : les
        # appliquer effacerait la comparaison que le client est en train de
        # lire.
        devis = self._prepare('app-eco', {'nb_panneaux': 20})
        for cle in ('eco', 'max'):
            with self.assertRaises(ot.ApplicationImpossible):
                ot.appliquer_au_devis(devis, cle)
        devis.refresh_from_db()
        self.assertEqual(self._panneaux(devis), 14)

    def test_un_devis_ACCEPTE_est_refuse_et_INTOUCHE(self):
        devis = self._prepare('app-accepte', {'nb_panneaux': 20},
                              statut='accepte')
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            with self.assertRaises(ot.ApplicationImpossible) as capture:
                ot.appliquer_au_devis(devis, 'recommande')
        self.assertFalse(capture.exception.revision_possible)
        devis.refresh_from_db()
        self.assertEqual(self._panneaux(devis), 14)
        self.assertEqual(devis.statut, 'accepte')
        # La configuration reste : rien n'a été consommé puisque rien n'a été
        # appliqué.
        self.assertIn('recommande', ot.lire_config_stockee(devis))

    def test_un_devis_ENVOYE_renvoie_vers_la_REVISION(self):
        devis = self._prepare('app-envoye', {'nb_panneaux': 20},
                              statut='envoye')
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            with self.assertRaises(ot.ApplicationImpossible) as capture:
                ot.appliquer_au_devis(devis, 'recommande')
        self.assertTrue(capture.exception.revision_possible)
        devis.refresh_from_db()
        self.assertEqual(self._panneaux(devis), 14)

    def test_sans_configuration_ajustee_il_n_y_a_RIEN_a_appliquer(self):
        devis = self._devis('app-vide')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        devis.refresh_from_db()
        with self.assertRaises(ot.ApplicationImpossible) as capture:
            ot.appliquer_au_devis(devis, 'recommande')
        self.assertIn('Aucune configuration', capture.exception.detail)

    def test_une_ligne_NEGOCIEE_refuse_la_substitution_et_n_ecrit_RIEN(self):
        # Une substitution re-tarife la ligne : passer par-dessus un prix ou
        # une remise négociés détruirait une décision commerciale que personne
        # n'a demandé de revoir. Et le refus est TRANSACTIONNEL — la
        # resynchronisation déjà faite est annulée avec lui.
        devis = self._devis('app-nego')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        devis.refresh_from_db()
        ligne = devis.lignes.get(designation__startswith='Panneau')
        ligne.remise = Decimal('10')
        ligne.save(update_fields=['remise'])
        autre = Produit.objects.create(
            company=devis.company, nom='Panneau JA Solar 600W',
            prix_vente=Decimal('1000'), quantite_stock=10)
        ot.enregistrer_config(devis, 'recommande', {
            'nb_panneaux': 25, 'equipements': {'panneau': autre.pk}})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            with self.assertRaises(ot.ApplicationImpossible) as capture:
                ot.appliquer_au_devis(devis, 'recommande')
        self.assertIn('négoci', capture.exception.detail)
        devis.refresh_from_db()
        ligne.refresh_from_db()
        # NI la substitution NI le compte de panneaux n'ont été écrits.
        self.assertEqual(self._panneaux(devis), 14)
        self.assertTrue(ligne.designation.startswith('Panneau Canadien'))
        self.assertIn('recommande', ot.lire_config_stockee(devis))

    def test_une_substitution_au_prix_CATALOGUE_passe(self):
        devis = self._devis('app-subst')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        devis.refresh_from_db()
        autre = Produit.objects.create(
            company=devis.company, nom='Panneau JA Solar 600W',
            prix_vente=Decimal('1000'), quantite_stock=10)
        ot.enregistrer_config(devis, 'recommande', {
            'nb_panneaux': 17, 'equipements': {'panneau': autre.pk}})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            resume = ot.appliquer_au_devis(devis, 'recommande')
        devis.refresh_from_db()
        ligne = devis.lignes.get(produit=autre)
        self.assertEqual(ligne.designation, 'Panneau JA Solar 600W')
        self.assertEqual(Decimal(ligne.prix_unitaire), Decimal('1000.00'))
        self.assertEqual(resume['substitutions'],
                         {'panneau': 'Panneau JA Solar 600W'})


class ApiAppliquerTests(_Base):
    """L'endpoint ``offres-tailles/appliquer`` — garde, refus, multi-société."""

    URL = '/api/django/ventes/devis/%s/offres-tailles/appliquer/'

    def _api(self, company):
        api = APIClient()
        api.force_authenticate(self._user(company))
        return api

    def _contexte(self, devis):
        return SimpleNamespace(panel_watt=710.0,
                               entrees={'company': devis.company})

    def test_appliquer_recompose_et_repond_200(self):
        devis = self._devis('api-app')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        devis.refresh_from_db()
        ot.enregistrer_config(devis, 'recommande', {'nb_panneaux': 21})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            resp = self._api(devis.company).post(
                self.URL % devis.pk, {'cle': 'recommande'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['applique']['panneaux'], 21)
        devis.refresh_from_db()
        self.assertEqual(
            int(devis.lignes.get(designation__startswith='Panneau').quantite),
            21)

    def test_ECO_repond_400_avec_son_motif_EN_FRANCAIS(self):
        devis = self._devis('api-app-eco')
        Devis.objects.filter(pk=devis.pk).update(statut='brouillon')
        resp = self._api(devis.company).post(
            self.URL % devis.pk, {'cle': 'eco'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Recommandé', str(resp.json()['detail']))

    def test_un_devis_ENVOYE_repond_400_et_dit_REVISION_POSSIBLE(self):
        devis = self._devis('api-app-envoye')
        ot.enregistrer_config(devis, 'recommande', {'nb_panneaux': 21})
        with mock.patch.object(ot, '_contexte', side_effect=self._contexte):
            resp = self._api(devis.company).post(
                self.URL % devis.pk, {'cle': 'recommande'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIs(resp.json()['revision_possible'], True)

    def test_un_devis_d_une_AUTRE_societe_repond_404_jamais_403(self):
        devis = self._devis('api-app-a')
        autre = self._company('api-app-b')
        resp = self._api(autre).post(
            self.URL % devis.pk, {'cle': 'recommande'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_l_action_est_fermee_a_un_visiteur(self):
        devis = self._devis('api-app-anon')
        resp = APIClient().post(self.URL % devis.pk, {'cle': 'recommande'},
                                format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_VX199_l_action_est_inscrite_dans_get_permissions(self):
        from authentication.permissions import IsResponsableOrAdmin
        from apps.ventes.views.devis import DevisViewSet
        vue = DevisViewSet()
        vue.action = 'offres_tailles_appliquer'
        self.assertEqual([type(p) for p in vue.get_permissions()],
                         [IsResponsableOrAdmin])


class ChaineJusquAuPayloadTests(_Base):
    """LA PREUVE DE BOUT EN BOUT : une taille ajustée ATTEINT la page client.

    Les tests de dérivation prouvent que ``deriver`` lit la configuration
    stockée ; celui-ci prouve que le PAYLOAD PUBLIC la porte — c'est-à-dire
    que la chaîne complète (``public_views`` → ``offres_tailles_publique`` →
    ``deriver`` → configuration stockée → carte) n'a AUCUN maillon coupé, ni
    cache, ni filtre d'envoi qui l'avalerait. Sans ce pin, un ajustement Éco
    pouvait cesser d'atteindre le client sans qu'aucun test ne rougisse.

    ``deriver`` N'EST PAS BOUCHONNÉ ICI (c'est tout l'intérêt) : seuls le
    contexte catalogue et le moteur de carte le sont, exactement comme dans
    ``DerivationTests``.
    """

    def _payload_avec_config(self, devis, config):
        contexte = _contexte_factice(devis)
        devis.etude_params = dict(devis.etude_params or {}, dimensionnement={
            'tableau': _tableau((10, 6.0), (22, 8.0), (34, 11.0))})
        devis.offres_tailles_config = config
        devis.save(update_fields=['etude_params', 'offres_tailles_config'])

        def _moteur(_contexte_, nb, _config=None, *, avec_servable=True):
            return {'sans': dict(_carte(), nb_panneaux=nb), 'avec': None}

        with mock.patch.object(ot, '_contexte', return_value=contexte), \
                mock.patch.object(ot, '_carte_moteur', side_effect=_moteur), \
                mock.patch.object(
                    ot, '_carte_du_devis',
                    side_effect=lambda _c, _d, v: dict(_carte(),
                                                       nb_panneaux=22)):
            return self._payload(devis)

    def test_une_taille_ECO_ajustee_ATTEINT_la_page_client(self):
        devis = self._devis('chaine-eco')
        payload = self._payload_avec_config(devis, {
            'eco': {'config': {'nb_panneaux': 12}, 'ajuste': True}})
        eco = next(o for o in payload['offres_tailles']['offres']
                   if o['cle'] == 'eco')
        self.assertIs(eco['ajuste'], True)
        self.assertEqual(eco['sans']['nb_panneaux'], 12)

    def test_sans_ajustement_la_page_client_montre_le_champ_du_MOTEUR(self):
        # Le contre-test : sans lui, un « 12 » codé en dur passerait aussi.
        devis = self._devis('chaine-moteur')
        payload = self._payload_avec_config(devis, None)
        eco = next(o for o in payload['offres_tailles']['offres']
                   if o['cle'] == 'eco')
        self.assertIs(eco['ajuste'], False)
        self.assertEqual(eco['sans']['nb_panneaux'], 10)
