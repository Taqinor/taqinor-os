"""CJ2b — le graphe « économies par mois » REVIENT sur le devis PDF.

ORDRE FONDATEUR (21/08/2026) : « after correcting the annual saving chart
(per month) bring it back to the quote pdf because it disappeared from there ».

CE QUE CES TESTS ÉPINGLENT, ET POURQUOI
---------------------------------------
Le graphe avait disparu pour une BONNE raison (Z2/M1, 20-19/08) : sans les
douze factures du lead, la série « avant » était fabriquée à partir de
l'économie SUPPOSÉE — circulaire, donc supprimée avec toute la couche
économique. Le prix payé : sur la quasi-totalité des devis réels, où le client
donne UNE facture d'hiver et pas douze, le document perdait aussi son −N %,
son avant/après, sa couverture et son graphe mensuel.

CJ2a a créé la troisième source qui manquait : le bloc
``etude_params['etude_horaire']`` part du montant RÉELLEMENT payé, l'inverse au
barème, intègre heure par heure la production PVGIS du chantier contre la
courbe de consommation du client, puis revalorise chaque mois au barème. Ses
douze ``facture_avant_mad`` sont une dérivation TRAÇABLE d'une saisie réelle.

Ces tests vérifient donc les deux moitiés de la règle :
  · le graphe REVIENT quand ce bloc existe (l'ancrage est réel) ;
  · Z2 reste INTACTE quand rien n'ancre le devis (le bloc n'existe pas).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_cj2b_graphe_mensuel -v 2
"""

from decimal import Decimal

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


# ════════════════════════════════════════════════════════════════════════════
# Fabrique de bloc horaire — la forme figée par
# apps/ventes/contract_samples/etude_horaire.json (PACT10).
# ════════════════════════════════════════════════════════════════════════════

#: Douze factures « avant » plausibles (MAD/mois TTC), été plus cher.
FACTURES_AVANT = [1200, 1150, 1220, 1310, 1480, 1720,
                  1900, 1880, 1560, 1350, 1240, 1200]
#: Douze économies « sans batterie » (MAD/mois), corrélées à l'ensoleillement.
ECO_SANS = [560, 590, 700, 780, 860, 900, 910, 870, 780, 680, 570, 540]
#: Douze économies « avec batterie » — toujours ≥ le côté sans (invariant M9/Z5).
ECO_AVEC = [e + 190 for e in ECO_SANS]


def bloc_horaire(kwc=5.68, source_consommation='facture_hiver',
                 factures_avant=None):
    """Bloc ``etude_horaire`` minimal mais VALIDE pour ``_lire_etude_horaire``.

    Ne porte que ce que le lecteur défensif exige — un bloc réel en porte
    beaucoup plus (saisons, taux par mois, avertissements). Le contrat, c'est
    la présence et la nature des clés lues, pas leur voisinage.
    """
    avant = list(factures_avant if factures_avant is not None
                 else FACTURES_AVANT)
    mois = [{
        'mois': i + 1,
        'economie_sans_mad': ECO_SANS[i],
        'economie_avec_mad': ECO_AVEC[i],
        'facture_avant_mad': avant[i],
        'facture_apres_sans_mad': max(0, avant[i] - ECO_SANS[i]),
        'facture_apres_avec_mad': max(0, avant[i] - ECO_AVEC[i]),
    } for i in range(12)]
    return {
        'version': 1,
        'kwc': kwc,
        'source_consommation': source_consommation,
        'mois': mois,
        'annuel': {
            'production_kwh': 9764.0,
            'consommation_kwh': 7838.0,
            'economie_sans_mad': float(sum(ECO_SANS)),
            'economie_avec_mad': float(sum(ECO_AVEC)),
            'taux_autoconso_sans': 0.41,
            'taux_autoconso_avec': 0.64,
            'facture_avant_mad': float(sum(avant)),
            'facture_apres_sans_mad': float(sum(avant) - sum(ECO_SANS)),
            'facture_apres_avec_mad': float(sum(avant) - sum(ECO_AVEC)),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# 1. LE LECTEUR DÉFENSIF — ce qu'il accepte, ce qu'il refuse
# ════════════════════════════════════════════════════════════════════════════

class LectureBlocHoraireTests(SimpleTestCase):
    """``pricing._lire_etude_horaire`` — fonction PURE, aucune BD."""

    def _lire(self, bloc, kwc=5.68):
        from apps.ventes.quote_engine.pricing import _lire_etude_horaire
        return _lire_etude_horaire(bloc, kwc)

    def test_la_serie_avant_et_sa_source_remontent(self):
        """CJ2b — les douze ``facture_avant_mad`` et la provenance de la
        consommation sortent du bloc, prêtes pour le document."""
        lu = self._lire(bloc_horaire())
        self.assertIsNotNone(lu)
        self.assertEqual(lu['factures_avant_monthly'], FACTURES_AVANT)
        self.assertEqual(lu['source_consommation'], 'facture_hiver')

    def test_une_serie_avant_incomplete_est_refusee_sans_casser_le_reste(self):
        """Un mois sans facture ⇒ PAS de série « avant » (on n'en invente pas
        onze douzièmes), mais les économies, elles, restent lisibles."""
        bloc = bloc_horaire()
        del bloc['mois'][4]['facture_avant_mad']
        lu = self._lire(bloc)
        self.assertIsNotNone(lu)
        self.assertIsNone(lu['factures_avant_monthly'])
        self.assertEqual(lu['eco_s_monthly'], ECO_SANS)

    def test_une_facture_nulle_invalide_la_serie(self):
        """Garde stricte : douze valeurs STRICTEMENT positives, sinon rien."""
        bloc = bloc_horaire(factures_avant=[0] + FACTURES_AVANT[1:])
        self.assertIsNone(self._lire(bloc)['factures_avant_monthly'])

    def test_un_bloc_perime_ne_remonte_rien_du_tout(self):
        """GARDE DE FRAÎCHEUR (``_HORAIRE_TOLERANCE_KWC``) — un bloc calculé
        pour 5,68 kWc ne décrit pas un devis repuissancé à 9 kWc : il est
        refusé EN ENTIER, série « avant » comprise. Un chiffre précis et faux
        est pire qu'un repli honnête."""
        self.assertIsNone(self._lire(bloc_horaire(kwc=5.68), kwc=9.0))


# ════════════════════════════════════════════════════════════════════════════
# 2. LA SYNTHÈSE — l'économie cesse d'être seulement « en creux »
# ════════════════════════════════════════════════════════════════════════════

class SyntheseEconomiesTests(SimpleTestCase):
    """``renderer.synthese_economies`` — fonction PURE, aucune BD."""

    def _data(self, **extra):
        base = {
            'savings_estimated': False,
            'factures_reelles': True,
            'factures_mensuelles': list(FACTURES_AVANT),
            'eco_a_monthly': list(ECO_AVEC),
            'eco_s_monthly': list(ECO_SANS),
            'prod_kwh': 9764,
            'conso_annuelle_kwh': 7838,
            'tarif_kwh': 1.35,
            'deux_options': True,
            'avec_ok': True,
        }
        base.update(extra)
        return base

    def test_la_serie_economies_egale_exactement_l_ecart_des_barres(self):
        """CJ2b — les nombres imprimés au-dessus des barres SONT l'écart entre
        les deux barres, par construction. ``eco_a_monthly`` ne suffirait pas :
        ``bills_after`` est planché à 0, donc sur un mois où l'économie
        dépasserait la facture, la série et le dessin diffèreraient."""
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies)
        synth = synthese_economies(self._data())
        self.assertIsNotNone(synth)
        attendu = [b - a for b, a in zip(synth['bills_before'],
                                         synth['bills_after'])]
        self.assertEqual(synth['eco_mensuelles'], attendu)
        self.assertEqual(synth['eco_mensuelles_total'],
                         synth['annual_before'] - synth['annual_after'])

    def test_le_plancher_a_zero_est_respecte_par_la_serie(self):
        """Économie mensuelle supérieure à la facture : la barre « après »
        s'arrête à 0 et le chiffre imprimé s'arrête AVEC elle."""
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies)
        enorme = [f * 3 for f in FACTURES_AVANT]
        synth = synthese_economies(self._data(eco_a_monthly=enorme))
        self.assertEqual(synth['bills_after'], [0] * 12)
        self.assertEqual(synth['eco_mensuelles'], list(FACTURES_AVANT))
        self.assertNotEqual(synth['eco_mensuelles'], enorme)

    def test_l_option_decrite_par_la_serie_est_nommee(self):
        """Q2 — le document ne montre qu'un seul jeu de chiffres ; il doit dire
        LEQUEL. Deux options ⇒ la série décrit l'option avec batterie."""
        from apps.ventes.quote_engine.residential.renderer import (
            synthese_economies)
        self.assertEqual(
            synthese_economies(self._data())['eco_option'], 'avec')
        self.assertEqual(
            synthese_economies(self._data(deux_options=False, avec_ok=False)
                               )['eco_option'], 'sans')

    def test_z2_intacte_sans_aucun_ancrage(self):
        """La règle qui a fait disparaître le graphe reste EXACTEMENT en place :
        tarif de repli + ni factures ni conso saisie ⇒ aucune synthèse."""
        from apps.ventes.quote_engine.residential.renderer import (
            ancrage_reel_absent, synthese_economies)
        nu = self._data(savings_estimated=True, factures_reelles=False,
                        conso_annuelle_kwh=None)
        self.assertTrue(ancrage_reel_absent(nu))
        self.assertIsNone(synthese_economies(nu))


# ════════════════════════════════════════════════════════════════════════════
# 3. LE GRAPHE — la série chiffrée est réellement dessinée
# ════════════════════════════════════════════════════════════════════════════

@tag('pdf')
class GrapheMensuelTests(SimpleTestCase):
    """``charts.bill_before_after`` (matplotlib). Jamais un test de PIXELS :
    on vérifie qu'une image est produite et qu'ajouter la série la CHANGE —
    c'est la seule affirmation qu'un test peut honnêtement porter ici."""

    def _apres(self):
        return [max(0, b - e) for b, e in zip(FACTURES_AVANT, ECO_AVEC)]

    def test_la_serie_chiffree_modifie_reellement_l_image(self):
        from apps.ventes.quote_engine.residential import charts
        apres = self._apres()
        eco = [b - a for b, a in zip(FACTURES_AVANT, apres)]
        sans = charts.bill_before_after(FACTURES_AVANT, apres)
        avec = charts.bill_before_after(FACTURES_AVANT, apres, eco)
        for uri in (sans, avec):
            self.assertTrue(uri.startswith('data:image/png;base64,'))
        self.assertNotEqual(sans, avec,
                            'la série d\'économies n\'a rien changé au rendu')

    def test_sans_serie_le_rendu_reste_celui_d_avant_cj2b(self):
        """Repli : ``economies=None`` ⇒ ancien graphe, au bit près. Aucun
        appelant historique ne change de sortie."""
        from apps.ventes.quote_engine.residential import charts
        apres = self._apres()
        self.assertEqual(charts.bill_before_after(FACTURES_AVANT, apres),
                         charts.bill_before_after(FACTURES_AVANT, apres, None))

    def test_une_serie_mal_dimensionnee_retombe_sur_l_ancien_rendu(self):
        """Onze valeurs ⇒ on n'écrit rien plutôt que d'aligner des chiffres sur
        les mauvais mois."""
        from apps.ventes.quote_engine.residential import charts
        apres = self._apres()
        eco11 = [b - a for b, a in zip(FACTURES_AVANT, apres)][:11]
        self.assertEqual(charts.bill_before_after(FACTURES_AVANT, apres, eco11),
                         charts.bill_before_after(FACTURES_AVANT, apres))

    def test_la_mention_estimation_change_l_image(self):
        """Motif Z2 — « variation mensuelle estimée » est bien PORTÉE par le
        graphe (elle vit dans l'image, pas dans l'en-tête HTML : cet en-tête
        est une rangée flex que RENDERING_NOTES.md interdit d'alourdir)."""
        from apps.ventes.quote_engine.residential import charts
        apres = self._apres()
        eco = [b - a for b, a in zip(FACTURES_AVANT, apres)]
        self.assertNotEqual(
            charts.bill_before_after(FACTURES_AVANT, apres, eco),
            charts.bill_before_after(FACTURES_AVANT, apres, eco,
                                     variation_estimee=True))

    def test_build_all_transmet_la_serie(self):
        """La chaîne complète : ``synthese_economies`` → ``build_all`` →
        ``bill_before_after``. Sans ce maillon, le graphe reviendrait vide de
        chiffres sans qu'aucun test ne le voie."""
        from apps.ventes.quote_engine.residential import charts
        apres = self._apres()
        eco = [b - a for b, a in zip(FACTURES_AVANT, apres)]
        data = {'bills_before': list(FACTURES_AVANT), 'bills_after': apres,
                'eco_mensuelles': eco, 'coverage_pct': 62, 'nb_panneaux': 8,
                'total_sans': 52800, 'total_avec': 79200,
                'eco_s_ann': sum(ECO_SANS), 'eco_a_ann': sum(ECO_AVEC),
                'roi_s': 6.2, 'roi_a': 6.5}
        self.assertEqual(charts.build_all(data)['bill'],
                         charts.bill_before_after(FACTURES_AVANT, apres, eco))

    def test_z2_le_graphe_n_est_meme_pas_calcule(self):
        """Synthèse masquée ⇒ ``build_all`` ne produit que le calepinage."""
        from apps.ventes.quote_engine.residential import charts
        rendu = charts.build_all({'masquer_synthese': True, 'nb_panneaux': 8})
        self.assertEqual(set(rendu), {'roof'})


# ════════════════════════════════════════════════════════════════════════════
# 4. LE DOCUMENT RENDU — pagination et boîtes non nulles (WeasyPrint)
# ════════════════════════════════════════════════════════════════════════════

@tag('pdf')
class DocumentAvecGrapheTests(TestCase):
    """Le graphe enrichi ne déborde d'aucune page. On mesure les BOÎTES du PDF
    réellement rendu (``renderer._measure_page_slack``, PyMuPDF) — jamais des
    pixels."""

    def _rendu(self, variant='deux'):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import (
            render, renderer, sample_data)
        d = renderer._augment(sample_data.build(variant))
        html = render.build_html(d)
        return d, html, HTML(string=html).render()

    def test_la_carte_du_graphe_mensuel_est_bien_la(self):
        """Le fondateur ne la voyait plus : elle est présente, et elle porte
        une image (jamais une carte vide)."""
        d, html, _ = self._rendu()
        self.assertIn('class="c1-bill"', html)
        self.assertIn('Votre facture mois par mois', html)
        self.assertIn('data:image/png;base64', html)
        self.assertEqual(len(d['eco_mensuelles']), 12)

    def test_la_pagination_ne_bouge_pas(self):
        """La série chiffrée vit DANS l'image, dont la hauteur CSS est fixe
        (33,5 mm) : la couverture ne peut pas grandir, donc le nombre de pages
        de chaque variante reste celui que la garde anti-débordement exige."""
        from apps.ventes.quote_engine.residential import sample_data
        attendu = {'deux': 3, 'sans': 3, 'long': 3, 'plus5': 3, 'plus10': 4}
        for variant in sample_data.keys():
            with self.subTest(variant=variant):
                _, _, doc = self._rendu(variant)
                self.assertEqual(len(doc.pages), attendu[variant])

    def test_aucune_page_ne_garde_un_grand_vide(self):
        """QRES62 — les boîtes mesurées sur le PDF réel : aucun vide résiduel
        exploitable > 12 mm, sur AUCUNE variante."""
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in sample_data.keys():
            with self.subTest(variant=variant):
                pdf = renderer.render_pdf_bytes(sample_data.build(variant))
                residuel = renderer._measure_page_slack(pdf)
                self.assertTrue(all(v <= 12 for v in residuel.values()),
                                f'{variant} : vides résiduels {residuel}')


# ════════════════════════════════════════════════════════════════════════════
# 5. LE CHEMIN COMPLET — un devis RÉEL retrouve sa couche économique
# ════════════════════════════════════════════════════════════════════════════

class AncrageParLeBlocHoraireTests(TestCase):
    """``build_quote_data`` : le bloc horaire vaut ancrage réel."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    #: PV86/Z1 — un document à DEUX options n'existe que si le devis porte
    #: vraiment les deux onduleurs ET une batterie réelle (aucune batterie de
    #: synthèse). Mêmes lignes que ``test_quote_engine_builder`` : 14 × 550 Wc
    #: ⇒ 7,70 kWc, la puissance que le bloc horaire de ces tests décrit.
    LIGNES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
    ]
    KWC = 7.70

    def _devis(self, ref, etude_params):
        return make_devis(self.company, self.user, self.client_obj,
                          self.LIGNES, reference=ref,
                          etude_params=etude_params)

    def test_le_bloc_horaire_rend_la_serie_avant_et_donc_le_graphe(self):
        """LE TEST DE LA MISSION. Sans douze factures du lead — le cas courant —
        le document perdait TOUTE sa couche économique. Le bloc horaire la lui
        rend, sans qu'un seul chiffre soit inventé."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        devis = self._devis('DEV-CJ2B-OK',
                            {**DEUX_OPTIONS, 'etude_horaire': bloc_horaire(self.KWC)})
        data = build_quote_data(devis)
        self.assertEqual(data['savings_model'], 'horaire')
        self.assertEqual(data['factures_source'], 'etude_horaire')
        self.assertTrue(data['factures_reelles'])
        self.assertEqual(data['factures_mensuelles'], FACTURES_AVANT)
        self.assertFalse(renderer.ancrage_reel_absent(data))
        self.assertIsNotNone(renderer.synthese_economies(data))
        d = renderer._augment(data)
        self.assertFalse(d['masquer_synthese'])
        self.assertEqual(len(d['eco_mensuelles']), 12)

    def test_les_douze_factures_du_lead_restent_prioritaires(self):
        """Quand le client a VRAIMENT donné douze factures, ce sont elles —
        jamais la reconstitution du barème."""
        from apps.ventes.quote_engine.builder import build_quote_data
        reelles = [999, 1001, 1002, 1003, 1004, 1005,
                   1006, 1007, 1008, 1009, 1010, 1011]
        devis = self._devis('DEV-CJ2B-12F',
                            {**DEUX_OPTIONS, 'etude_horaire': bloc_horaire(self.KWC),
                             'factures_mensuelles_reelles': reelles})
        data = build_quote_data(devis)
        self.assertEqual(data['factures_source'], 'lead_12_mois')
        self.assertEqual(data['factures_mensuelles'], reelles)

    def test_une_facture_d_hiver_repetee_est_etiquetee_estimation(self):
        """Motif Z2 — le NIVEAU vient d'une facture payée, mais la VARIATION
        d'un mois à l'autre est une hypothèse tant que le client n'a donné
        qu'un point. Le document le dit."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis(
            'DEV-CJ2B-EST',
            {**DEUX_OPTIONS,
             'etude_horaire': bloc_horaire(
                 self.KWC, source_consommation='facture_hiver')})
        data = build_quote_data(devis)
        self.assertTrue(data['factures_mensuelles_estimation'])
        self.assertEqual(data['source_consommation'], 'facture_hiver')

    def test_douze_releves_reels_ne_sont_pas_etiquetes_estimation(self):
        """À l'inverse : douze points réels ⇒ la variation est MESURÉE, aucune
        mention « estimation » ne doit ternir un vrai relevé."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis(
            'DEV-CJ2B-REEL',
            {**DEUX_OPTIONS,
             'etude_horaire': bloc_horaire(
                 self.KWC,
                 source_consommation='factures_mensuelles_reelles')})
        data = build_quote_data(devis)
        self.assertFalse(data['factures_mensuelles_estimation'])

    def test_z2_reste_intacte_sur_un_devis_sans_rien(self):
        """LA MOITIÉ QUI PROTÈGE. Aucun bloc horaire, aucune facture, aucune
        conso ⇒ la couche économique reste OMISE, exactement comme avant CJ2b.
        L'ancrage n'a été élargi qu'aux devis qui portent une vraie facture."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.residential import renderer
        data = build_quote_data(self._devis('DEV-CJ2B-NU', dict(DEUX_OPTIONS)))
        self.assertIsNone(data['factures_source'])
        self.assertFalse(data['factures_reelles'])
        self.assertIsNone(data['factures_mensuelles'])
        self.assertTrue(renderer.ancrage_reel_absent(data))
        self.assertIsNone(renderer.synthese_economies(data))
        self.assertTrue(renderer._augment(data)['masquer_synthese'])

    def test_un_bloc_perime_ne_ressuscite_pas_le_graphe(self):
        """Un bloc calculé pour une AUTRE puissance ne doit rien ancrer : le
        devis retombe sur le repli étiqueté, pas sur douze factures qui
        décrivent une autre installation."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis(
            'DEV-CJ2B-PERIME',
            {**DEUX_OPTIONS, 'etude_horaire': bloc_horaire(kwc=22.0)})
        data = build_quote_data(devis)
        self.assertNotEqual(data['savings_model'], 'horaire')
        self.assertIsNone(data['factures_source'])
        self.assertIsNone(data['factures_mensuelles'])

    def test_aucun_prix_d_achat_ni_marge_ne_sort(self):
        """Règle #4 — la couche économique rendue ne porte AUCUNE donnée
        interne. On scanne le RENDU monétaire, pas des nombres nus."""
        import json
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-CJ2B-CONF',
                            {**DEUX_OPTIONS, 'etude_horaire': bloc_horaire(self.KWC)})
        data = build_quote_data(devis)
        blob = json.dumps(data, default=str).lower()
        # Mêmes marqueurs que la garde de non-régression historique
        # (``test_qx49_proposal_payload``) — un seul vocabulaire pour la
        # confidentialité, jamais deux listes qui divergent.
        for interdit in ('prix_achat', 'marge'):
            self.assertNotIn(interdit, blob)


@tag('pdf')
class LibelleEconomieTests(TestCase):
    """« Économie estimée » vs « Économie calculée » — le mot suit le modèle."""

    def _cover(self, savings_model):
        from apps.ventes.quote_engine.residential import (
            renderer, sample_data)
        from apps.ventes.quote_engine.residential import cover
        d = renderer._augment(
            {**sample_data.build('deux'), 'savings_model': savings_model})
        from apps.ventes.quote_engine.residential import render as r_render
        return cover.build(r_render.build_ctx(d))

    def test_le_moteur_horaire_dit_calculee(self):
        """CJ2b — « we cannot see the real calculated saving » : un chiffre
        intégré heure par heure n'est pas une estimation, et ne doit plus se
        présenter comme telle."""
        html = self._cover('horaire')
        self.assertIn('Économie calculée', html)
        self.assertNotIn('Économie estimée', html)

    def test_le_repli_forfaitaire_dit_toujours_estimee(self):
        """Et l'inverse : hors moteur horaire, le mot « estimée » reste — une
        estimation présentée comme un calcul serait le défaut symétrique."""
        for modele in ('factures', 'estimation', None):
            with self.subTest(modele=modele):
                self.assertIn('Économie estimée', self._cover(modele))


class DecimalNonRegressionTests(SimpleTestCase):
    """Garde-fou : la série « avant » sort en entiers JSON-sérialisables, pas
    en ``Decimal`` (le payload public et le cache PDF les traversent)."""

    def test_la_serie_est_faite_d_entiers(self):
        from apps.ventes.quote_engine.pricing import _lire_etude_horaire
        serie = _lire_etude_horaire(bloc_horaire(), 5.68)[
            'factures_avant_monthly']
        for valeur in serie:
            self.assertIsInstance(valeur, int)
            self.assertNotIsInstance(valeur, Decimal)
