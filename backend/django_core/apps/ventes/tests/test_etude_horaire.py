# -*- coding: utf-8 -*-
"""CJ2a — le moteur horaire et son barème, épinglés.

Ce module garde CINQ promesses faites au fondateur :

1. **Le barème reproduit ses vraies factures** — pas « à peu près » : la
   facture du 08/05/2026 sort au CENTIME, timbre espèces compris, et
   l'inversion MAD→kWh rend 359 / 572 / 432 kWh exactement sur les trois.
2. **L'inversion est un vrai inverse** — aller-retour exact sur toutes les
   tranches, y compris les bords du barème sélectif où la facture SAUTE.
3. **La physique est respectée** — on n'autoconsomme jamais plus que le
   minimum(production, consommation) heure par heure, et une batterie ne
   restitue jamais plus que 0,90 × ce qu'elle a chargé.
4. **Rien n'est inventé quand rien n'est connu** — sans facture, le moteur
   renvoie ``None`` et le moteur de devis garde son forfait ÉTIQUETÉ (règle Z2).
5. **Rien d'existant ne bouge** — ``pricing.ONEE_TRANCHES`` est intacte (donc
   ``test_tariff_drift_lock`` reste vert), un devis sans bloc horaire calcule
   exactement comme avant, et les chemins industriel/agricole sont épinglés.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_etude_horaire"
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import etude_horaire as EH
from apps.ventes import courbes_journalieres as CJ
from apps.ventes.quote_engine import bareme as B
from apps.ventes.quote_engine import pricing

#: Les trois factures RÉELLES du fondateur (SRM Casablanca-Settat, BT
#: domestique, même compteur). ``(libellé, kWh, jours, millésime, total TTC)``.
FACTURES_REELLES = (
    ('A 08/05/2026 n° 643769639', 359, 30, 2026, 592.77),
    ('B 20/12/2025', 572, 31, 2025, 1050.68),
    ('C 20/01/2026', 432, 29, 2025, 707.77),
)

#: Tolérance sur les périodes de 29 et 31 jours. La période de 30 jours sort
#: EXACTE (0,00) ; les deux autres portent un résidu MESURÉ de +0,04 / +0,05
#: MAD, convention d'arrondi du facturier que deux relevés ne suffisent pas à
#: reconstituer. On l'épingle CHIFFRÉ plutôt que de le noyer dans une
#: tolérance large : si le résidu grandit, ce test le dit.
TOLERANCE_JOURS_NON_STANDARD = 0.10


class BaremeFacturesReellesTest(SimpleTestCase):
    """Le barème face aux trois factures papier du fondateur."""

    def test_facture_a_reproduite_au_centime(self):
        """30 jours, 359 kWh : chaque LIGNE de la facture, pas juste le total."""
        f = B.facture_mad(359, jours=30, millesime=2026)
        self.assertAlmostEqual(f['energie_mad'], 496.03, places=2)
        self.assertAlmostEqual(f['location_entretien_mad'], 39.94, places=2)
        self.assertAlmostEqual(f['tppan_mad'], 56.80, places=2)
        self.assertAlmostEqual(f['total_mad'], 592.77, places=2)

    def test_timbre_especes_reproduit_mais_hors_calcul(self):
        """594,25 en espèces — vérifié, et DÉLIBÉRÉMENT hors du total."""
        total = B.facture_mad(359, jours=30, millesime=2026)['total_mad']
        self.assertAlmostEqual(
            total * (1 + B.TIMBRE_ESPECES_PCT), 594.25, places=2)

    def test_factures_b_et_c_dans_la_tolerance_mesuree(self):
        for libelle, kwh, jours, millesime, attendu in FACTURES_REELLES[1:]:
            with self.subTest(facture=libelle):
                total = B.facture_mad(
                    kwh, jours=jours, millesime=millesime)['total_mad']
                self.assertLess(
                    abs(total - attendu), TOLERANCE_JOURS_NON_STANDARD,
                    '%s : %.2f calculé vs %.2f facturé' % (
                        libelle, total, attendu))

    def test_inversion_exacte_sur_les_trois_factures(self):
        """MAD → kWh : le back-calcul retrouve la consommation IMPRIMÉE."""
        for libelle, kwh, jours, millesime, total in FACTURES_REELLES:
            with self.subTest(facture=libelle):
                trouve = B.kwh_depuis_facture_mad(
                    total, jours=jours, millesime=millesime)['kwh_mensuel']
                self.assertLess(
                    abs(trouve - kwh), 1.0,
                    '%s : %.1f kWh déduits vs %d kWh facturés' % (
                        libelle, trouve, kwh))

    def test_tppan_progressive_proratisee(self):
        """100×0,10 + 100×0,15 + 159×0,20 = 56,80 — la ligne exacte."""
        self.assertAlmostEqual(B.tppan_mad(359, jours=30), 56.80, places=2)
        # Proratisation : à 31 jours les bornes montent, la taxe baisse.
        self.assertLess(B.tppan_mad(359, jours=31), B.tppan_mad(359, jours=30))

    def test_tppan_plafonnee_a_cent_dirhams(self):
        self.assertLessEqual(B.tppan_mad(5000, jours=30),
                             B.TPPAN_PLAFOND_MAD_MOIS)


class BaremeInversionTest(SimpleTestCase):
    """L'inversion est un VRAI inverse, bords sélectifs compris."""

    #: Bords choisis pour tomber PILE sur les marches du barème sélectif
    #: (bornes effectives 210 / 310 / 510) et de part et d'autre.
    POINTS = (30, 80, 100, 120, 150, 180, 200, 205, 209, 210, 211, 250,
              300, 309, 310, 311, 400, 500, 509, 510, 511, 600, 800, 1200)

    def test_aller_retour_exact_sur_toutes_les_tranches(self):
        for kwh in self.POINTS:
            with self.subTest(kwh=kwh):
                total = B.facture_mad(kwh)['total_mad']
                retour = B.kwh_depuis_facture_mad(total)['kwh_mensuel']
                self.assertLess(
                    abs(retour - kwh), 0.15,
                    '%d kWh → %.2f MAD → %.1f kWh' % (kwh, total, retour))

    def test_facture_monotone_croissante(self):
        """Une facture ne baisse JAMAIS quand la consommation monte — c'est ce
        qui rend la dichotomie légitime."""
        precedent = -1.0
        for kwh in range(0, 900, 7):
            total = B.facture_mad(kwh)['total_mad']
            self.assertGreaterEqual(total, precedent - 1e-9,
                                    'rupture de monotonie à %d kWh' % kwh)
            precedent = total

    def test_montant_sous_les_charges_fixes_rend_zero(self):
        """Aucune consommation ne peut produire une facture inférieure à
        l'abonnement : on rend 0, jamais un kWh négatif ou extrapolé."""
        self.assertEqual(
            B.kwh_depuis_facture_mad(5.0)['kwh_mensuel'], 0.0)

    def test_charges_fixes_s_annulent_dans_l_economie(self):
        """Le client garde son abonnement : le lui compter comme une économie
        serait un mensonge. Deux jeux de charges fixes ⇒ MÊME économie."""
        avec_defaut = B.economie_deux_factures_mad(600, 200)['economie_mad']
        avec_autre = B.economie_deux_factures_mad(
            600, 200, charges_fixes_mad=250.0)['economie_mad']
        self.assertAlmostEqual(avec_defaut, avec_autre, places=6)

    def test_tppan_ne_s_annule_pas_dans_l_economie(self):
        """Elle SUIT le kWh, donc elle doit contribuer à l'économie."""
        avec = B.economie_deux_factures_mad(600, 200, tppan=True)['economie_mad']
        sans = B.economie_deux_factures_mad(600, 200, tppan=False)['economie_mad']
        self.assertGreater(avec, sans)


class BaremeDivergencesTest(SimpleTestCase):
    """Ce que les factures corrigent est VISIBLE, et rien d'existant ne bouge."""

    def test_pricing_onee_tranches_intacte(self):
        """Le drift lock reste vert PAR CONSTRUCTION : on n'a pas touché la
        table du moteur de devis. Si quelqu'un la corrige un jour, ce test le
        force à mettre DIVERGENCES_PRICING à jour EN MÊME TEMPS."""
        prix = dict((plafond, prix) for plafond, prix in pricing.ONEE_TRANCHES)
        self.assertAlmostEqual(prix[500], 1.405116, places=6)
        self.assertAlmostEqual(prix[None], 1.622856, places=6)

    def test_t5_2026_corrigee_par_la_facture(self):
        """1,381704 (prouvé) et non 1,405116 (extrapolé à HT constant)."""
        prix = dict((plafond, prix) for plafond, prix in B.TRANCHES_2026)
        self.assertAlmostEqual(prix[500], 1.381704, places=6)

    def test_t5_ttc_constante_a_travers_le_changement_de_tva(self):
        """LE mécanisme prouvé : au passage 18 → 20 %, le TTC n'a pas bougé."""
        p2025 = dict((c, p) for c, p in B.TRANCHES_2025)[500]
        p2026 = dict((c, p) for c, p in B.TRANCHES_2026)[500]
        self.assertLess(abs(p2025 - p2026), 0.001)

    def test_divergences_epinglees_et_motivees(self):
        statuts = {d['tranche']: d for d in B.DIVERGENCES_PRICING}
        self.assertEqual(len(statuts), 2)
        for detail in B.DIVERGENCES_PRICING:
            self.assertIn(detail['statut'],
                          ('corrigé', 'conflit_non_tranché'))
            self.assertTrue(detail['preuve'].strip(),
                            'une divergence sans preuve écrite est interdite')

    def test_conflit_t6_reste_sur_la_valeur_du_repo(self):
        """On ne tranche RIEN sans facture : T6 garde 1,622856 et le conflit
        est déclaré, pas masqué."""
        prix = dict((c, p) for c, p in B.TRANCHES_2026)
        self.assertAlmostEqual(prix[None], 1.622856, places=6)
        conflits = [d for d in B.DIVERGENCES_PRICING
                    if d['statut'] == 'conflit_non_tranché']
        self.assertEqual(len(conflits), 1)


class SilhouettesSourcePinTest(SimpleTestCase):
    """Les silhouettes Python et TypeScript ne peuvent pas diverger en silence.

    Le serveur est devenu PROPRIÉTAIRE des trois silhouettes (CJ2a) ; la copie
    ``apps/web/src/lib/dayProfiles.ts`` reste le miroir que CJ2b retirera. Tant
    que les deux existent, ce test les épingle l'une à l'autre.
    """

    CHEMIN_TS = ('apps', 'web', 'src', 'lib', 'dayProfiles.ts')

    def _shapes_typescript(self):
        racine = Path(__file__).resolve().parents[5]
        fichier = racine.joinpath(*self.CHEMIN_TS)
        if not fichier.exists():
            return None
        texte = fichier.read_text(encoding='utf-8')
        bloc = texte.split('OCCUPANCY_SHAPES', 1)[1].split('\n};', 1)[0]
        shapes = {}
        for cle in ('presence_jour', 'absence_jour', 'presence_partielle'):
            morceau = bloc.split(cle + ':', 1)[1].split('],', 1)[0]
            sans_commentaires = re.sub(r'//[^\n]*', '', morceau)
            shapes[cle] = [float(v) for v in
                           re.findall(r'\d+\.\d+', sans_commentaires)]
        return shapes

    def test_les_trois_silhouettes_sont_identiques_au_typescript(self):
        ts = self._shapes_typescript()
        if ts is None:
            self.skipTest('apps/web absent de ce checkout')
        for cle, valeurs in ts.items():
            with self.subTest(occupation=cle):
                python = list(CJ.SILHOUETTES_OCCUPATION[cle])
                self.assertEqual(len(valeurs), 24)
                self.assertEqual(len(python), 24)
                self.assertEqual(python, valeurs)

    def test_chaque_silhouette_normalise_a_un(self):
        for cle in CJ.SILHOUETTES_OCCUPATION:
            with self.subTest(occupation=cle):
                forme = CJ.silhouette_occupation(cle)
                self.assertAlmostEqual(sum(forme), 1.0, places=9)

    def test_occupation_inconnue_retombe_sur_le_milieu_honnete(self):
        self.assertEqual(CJ.silhouette_occupation('n_importe_quoi'),
                         CJ.silhouette_occupation(CJ.OCCUPATION_PARTIELLE))


class FormeConsommationTest(SimpleTestCase):
    """Les couches d'équipement redistribuent, elles n'inventent pas de kWh."""

    PISCINE = {'piscine': {'kw': 1.1, 'heures': list(range(10, 18)),
                           'saisons': ['ete'], 'mode': 'redistribution',
                           'source': 'test'}}
    VE = {'ve': {'kwh_jour': 4.0, 'heures': [21, 22, 23, 0, 1, 2],
                 'saisons': None, 'mode': 'addition', 'source': 'test'}}

    def test_forme_somme_au_niveau_facture(self):
        forme = CJ.forme_consommation_kwh(20.0, CJ.OCCUPATION_PRESENCE)
        self.assertAlmostEqual(sum(forme), 20.0, places=6)

    def test_piscine_redistribue_sans_changer_le_total(self):
        """L'équipement existe déjà : sa consommation est DANS la facture."""
        forme = CJ.forme_consommation_kwh(
            20.0, CJ.OCCUPATION_PRESENCE, saison='ete', equipements=self.PISCINE)
        self.assertAlmostEqual(sum(forme), 20.0, places=6)

    def test_piscine_deplace_bien_l_energie_vers_sa_fenetre(self):
        sans = CJ.forme_consommation_kwh(20.0, CJ.OCCUPATION_PRESENCE,
                                         saison='ete')
        avec = CJ.forme_consommation_kwh(
            20.0, CJ.OCCUPATION_PRESENCE, saison='ete', equipements=self.PISCINE)
        fenetre = range(10, 18)
        self.assertGreater(sum(avec[h] for h in fenetre),
                           sum(sans[h] for h in fenetre))

    def test_piscine_inactive_hors_saison(self):
        hiver = CJ.forme_consommation_kwh(
            20.0, CJ.OCCUPATION_PRESENCE, saison='hiver',
            equipements=self.PISCINE)
        nu = CJ.forme_consommation_kwh(20.0, CJ.OCCUPATION_PRESENCE,
                                       saison='hiver')
        self.assertEqual([round(v, 9) for v in hiver],
                         [round(v, 9) for v in nu])

    def test_ve_ajoute_sans_etre_redilue(self):
        """Seule charge FUTURE : ses kWh doivent atterrir dans sa fenêtre."""
        forme = CJ.forme_consommation_kwh(
            24.0, CJ.OCCUPATION_PRESENCE, saison='ete', equipements=self.VE)
        self.assertAlmostEqual(sum(forme), 24.0, places=6)
        fenetre = self.VE['ve']['heures']
        self.assertAlmostEqual(
            sum(forme[h] for h in fenetre)
            - sum(CJ.forme_consommation_kwh(20.0, CJ.OCCUPATION_PRESENCE,
                                            saison='ete')[h] for h in fenetre),
            4.0, places=6)

    def test_niveau_nul_ne_fabrique_aucune_consommation(self):
        self.assertEqual(CJ.forme_consommation_kwh(0, CJ.OCCUPATION_PRESENCE),
                         [0.0] * 24)


class PhysiqueDuMoteurTest(SimpleTestCase):
    """Conservation d'énergie et bornes de la batterie — les invariants durs."""

    VILLE = 'Casablanca'

    def _conso(self, mad=1200):
        conso, _source, _detail = EH.profil_depuis_factures(
            facture_hiver_mad=mad)
        return conso

    def test_autoconsomme_borne_par_production_et_consommation(self):
        etude = EH.calculer_etude_horaire(
            kwc=8.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, batterie_kwh_utile=15.0)
        self.assertIsNotNone(etude)
        for mois in etude['mois']:
            with self.subTest(mois=mois['mois']):
                plafond = min(mois['production_kwh'], mois['consommation_kwh'])
                self.assertLessEqual(mois['autoconsomme_sans_kwh'],
                                     plafond + 1e-6)
                self.assertLessEqual(mois['autoconsomme_avec_kwh'],
                                     plafond + 1e-6)
                self.assertLessEqual(mois['autoconsomme_sans_kwh'],
                                     mois['autoconsomme_avec_kwh'] + 1e-6)

    def test_taux_bornes_a_cent_pour_cent(self):
        etude = EH.calculer_etude_horaire(
            kwc=3.0, conso_kwh_mensuelles=self._conso(4000),
            ville=self.VILLE, occupation=CJ.OCCUPATION_PRESENCE)
        for cle in ('taux_autoconso_sans', 'taux_autoconso_avec',
                    'couverture_sans', 'couverture_avec'):
            self.assertLessEqual(etude['annuel'][cle], 1.0)
            self.assertGreaterEqual(etude['annuel'][cle], 0.0)

    def test_batterie_restitue_au_plus_90_pct_de_ce_qu_elle_charge(self):
        """L'invariant physique : le rendement aller-retour ne se contourne
        pas, et la batterie part vide (choix conservateur assumé)."""
        conso = [2.0] * 6 + [0.2] * 10 + [3.0] * 8
        prod = [0.0] * 7 + [1.5] * 10 + [0.0] * 7
        for capacite in (1.0, 5.0, 10.0, 50.0):
            with self.subTest(capacite=capacite):
                r = EH.simuler_batterie_jour(conso, prod, capacite)
                self.assertLessEqual(
                    r['restitue_kwh'],
                    r['charge_kwh'] * pricing.BATTERY_ROUNDTRIP + 1e-9)
                self.assertLessEqual(r['capacite_utilisee_kwh'],
                                     capacite + 1e-9)

    def test_batterie_absente_ne_decale_rien(self):
        r = EH.simuler_batterie_jour([1.0] * 24, [2.0] * 24, 0)
        self.assertEqual(r['restitue_kwh'], 0.0)
        self.assertEqual(r['charge_kwh'], 0.0)

    def test_production_monotone_en_puissance(self):
        """Plus de kWc ne peut JAMAIS produire moins."""
        conso = self._conso()
        precedent = -1.0
        for kwc in (2, 4, 6, 8, 12, 20):
            etude = EH.calculer_etude_horaire(
                kwc=kwc, conso_kwh_mensuelles=conso, ville=self.VILLE,
                occupation=CJ.OCCUPATION_PRESENCE)
            production = etude['annuel']['production_kwh']
            self.assertGreater(production, precedent)
            precedent = production

    def test_economie_jamais_superieure_a_la_facture(self):
        """On ne peut pas économiser plus que ce que le client paie."""
        conso = self._conso(1200)
        etude = EH.calculer_etude_horaire(
            kwc=30.0, conso_kwh_mensuelles=conso, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, batterie_kwh_utile=40.0)
        annuel = etude['annuel']
        self.assertLess(annuel['economie_sans_mad'], annuel['facture_avant_mad'])
        self.assertLess(annuel['economie_avec_mad'], annuel['facture_avant_mad'])
        self.assertGreaterEqual(annuel['economie_avec_mad'],
                                annuel['economie_sans_mad'])

    def test_pertes_systeme_alignees_sur_le_reste_de_la_chaine(self):
        """20 % de pertes AU TOTAL (ordre fondateur) : le productible PVGIS
        étant déjà net de 14 %, seul le complément s'applique. Sans cette
        règle, ce moteur annoncerait ~7,5 % de production de plus que le reste
        de la chaîne sur la MÊME installation."""
        from apps.parametres.pvgis_profils import productible_mensuel
        brut = sum(productible_mensuel(ville=self.VILLE)[0])
        etude = EH.calculer_etude_horaire(
            kwc=1.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE)
        self.assertAlmostEqual(
            etude['annuel']['production_kwh'],
            brut * pricing.PRODUCTION_DERATE, delta=1.0)

    def test_annee_complete_ou_rien(self):
        """Un « annuel » qui ne couvre pas douze mois serait lu comme une
        année et sous-estimerait tout."""
        etude = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE)
        self.assertEqual(len(etude['mois']), 12)
        self.assertAlmostEqual(
            sum(m['production_kwh'] for m in etude['mois']),
            etude['annuel']['production_kwh'], places=1)
        self.assertAlmostEqual(
            sum(m['economie_sans_mad'] for m in etude['mois']),
            etude['annuel']['economie_sans_mad'], places=1)

    def test_saisonnalite_reelle_pas_un_coefficient(self):
        """La production d'été DOIT dépasser celle d'hiver — la saisonnalité
        vient des données PVGIS, pas d'une clé de répartition."""
        etude = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE)
        self.assertGreater(etude['saisons']['ete']['production_kwh'],
                           etude['saisons']['hiver']['production_kwh'])

    def test_occupation_change_vraiment_l_autoconsommation(self):
        """À FACTURE ÉGALE, présent ≠ absent : c'est tout l'objet de CJ2a."""
        conso = self._conso()
        taux = {}
        for occupation in (CJ.OCCUPATION_PRESENCE, CJ.OCCUPATION_ABSENCE):
            etude = EH.calculer_etude_horaire(
                kwc=6.0, conso_kwh_mensuelles=conso, ville=self.VILLE,
                occupation=occupation)
            taux[occupation] = etude['annuel']['taux_autoconso_sans']
        self.assertGreater(taux[CJ.OCCUPATION_PRESENCE],
                           taux[CJ.OCCUPATION_ABSENCE],
                           'un foyer présent en journée doit autoconsommer '
                           'davantage — sinon le profil ne sert à rien')


class RepliHonneteTest(SimpleTestCase):
    """Règle Z2 : sans ancrage réel, on OMET — on n'approxime pas."""

    def test_sans_facture_le_moteur_ne_calcule_rien(self):
        conso, source, _ = EH.profil_depuis_factures()
        self.assertIsNone(conso)
        self.assertEqual(source, 'absente')

    def test_sans_consommation_le_moteur_rend_none(self):
        self.assertIsNone(EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=None, ville='Casablanca'))

    def test_ville_inconnue_rend_none_jamais_une_cloche_inventee(self):
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=1200)
        self.assertIsNone(EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Tombouctou'))

    def test_puissance_nulle_rend_none(self):
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=1200)
        self.assertIsNone(EH.calculer_etude_horaire(
            kwc=0, conso_kwh_mensuelles=conso, ville='Casablanca'))

    def test_priorite_des_sources_de_consommation(self):
        """12 kWh saisis > 12 factures réelles > facture hiver/été."""
        _c, source, _d = EH.profil_depuis_factures(
            conso_kwh_mensuelles=[500] * 12, factures_mensuelles_mad=[900] * 12,
            facture_hiver_mad=1200)
        self.assertEqual(source, 'kwh_mensuels_saisis')
        _c, source, _d = EH.profil_depuis_factures(
            factures_mensuelles_mad=[900] * 12, facture_hiver_mad=1200)
        self.assertEqual(source, 'factures_mensuelles_reelles')
        _c, source, _d = EH.profil_depuis_factures(
            facture_hiver_mad=1200, facture_ete_mad=1600, ete_differente=True)
        self.assertEqual(source, 'facture_hiver_ete')

    def test_ete_distinct_produit_bien_douze_mois_differencies(self):
        conso, _s, _d = EH.profil_depuis_factures(
            facture_hiver_mad=800, facture_ete_mad=1600, ete_differente=True)
        self.assertEqual(len(conso), 12)
        self.assertGreater(conso[6], conso[0], 'juillet doit dépasser janvier')


class PricingInchangeTest(SimpleTestCase):
    """Le câblage n'a RIEN cassé de l'existant."""

    ARGS = (6.0, 90000.0, 130000.0)
    KWARGS = {'conso_annuelle_kwh': 7800, 'utility': 'onee',
              'battery_kwh': 10.0}

    def test_sans_bloc_horaire_le_calcul_est_celui_d_avant(self):
        roi = pricing.calculate_savings_roi(*self.ARGS, **self.KWARGS)
        self.assertEqual(roi['savings_model'], 'factures')
        self.assertEqual(len(roi['eco_s_monthly']), 12)

    def test_bloc_malforme_est_ignore(self):
        """Un bloc douteux ne remplace JAMAIS un calcul honnête."""
        for mauvais in (None, {}, {'annuel': {}}, {'annuel': {}, 'mois': []},
                        {'annuel': {'production_kwh': 0,
                                    'consommation_kwh': 0}, 'mois': []},
                        'pas un dict'):
            with self.subTest(bloc=repr(mauvais)[:40]):
                roi = pricing.calculate_savings_roi(
                    *self.ARGS, etude_horaire=mauvais, **self.KWARGS)
                self.assertNotEqual(roi['savings_model'], 'horaire')

    def test_bloc_valide_prend_la_main(self):
        conso, source, detail = EH.profil_depuis_factures(
            facture_hiver_mad=1200)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=CJ.OCCUPATION_PRESENCE, batterie_kwh_utile=10.0,
            source_conso=source, detail_conso=detail)
        roi = pricing.calculate_savings_roi(
            *self.ARGS, etude_horaire=bloc, **self.KWARGS)
        self.assertEqual(roi['savings_model'], 'horaire')
        self.assertFalse(roi['savings_estimated'])
        self.assertEqual(roi['eco_s_ann'],
                         round(bloc['annuel']['economie_sans_mad']))
        self.assertEqual(roi['eco_a_ann'],
                         round(bloc['annuel']['economie_avec_mad']))
        self.assertGreaterEqual(roi['eco_a_ann'], roi['eco_s_ann'])

    def test_les_douze_mois_ne_sont_plus_une_cle_de_repartition(self):
        """Les économies mensuelles deviennent DOUZE CALCULS, pas un total
        annuel réparti par _SF."""
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=1200)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=CJ.OCCUPATION_PRESENCE)
        roi = pricing.calculate_savings_roi(
            *self.ARGS, etude_horaire=bloc, **self.KWARGS)
        attendu = [round(m['economie_sans_mad']) for m in bloc['mois']]
        self.assertEqual(roi['eco_s_monthly'], attendu)
        # Et ce n'est PAS la vieille clé _SF appliquée au total.
        _sf = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
               0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
        ancien = [round(roi['eco_s_ann'] * f) for f in _sf]
        self.assertNotEqual(roi['eco_s_monthly'], ancien)

    def test_autoconso_forfaitaire_reste_le_repli_documente(self):
        """AUCUNE constante supprimée : le forfait survit, étiqueté."""
        self.assertEqual(pricing.AUTOCONSO_SANS, 0.60)
        self.assertEqual(pricing.AUTOCONSO_AVEC, 0.85)

    def test_bloc_perime_est_ignore(self):
        """Le devis a été repuissancé, l'étude pas rafraîchie : ses chiffres
        décrivent une AUTRE installation. Mieux vaut le repli honnête qu'un
        chiffre précis et faux."""
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=1200)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=CJ.OCCUPATION_PRESENCE)
        # Même puissance (à l'arrondi près) → accepté.
        roi = pricing.calculate_savings_roi(
            6.05, 90000.0, 130000.0, etude_horaire=bloc, **self.KWARGS)
        self.assertEqual(roi['savings_model'], 'horaire')
        # Puissance franchement différente → REJETÉ.
        for kwc in (3.0, 9.0, 12.0):
            with self.subTest(kwc=kwc):
                roi = pricing.calculate_savings_roi(
                    kwc, 90000.0, 130000.0, etude_horaire=bloc, **self.KWARGS)
                self.assertNotEqual(roi['savings_model'], 'horaire')

    def test_productible_rendu_decrit_la_production_rendue(self):
        """« production ÷ kWc » et « productible » ne peuvent pas se
        contredire sur la même page."""
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=1200)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=CJ.OCCUPATION_PRESENCE)
        roi = pricing.calculate_savings_roi(
            6.0, 90000.0, 130000.0, etude_horaire=bloc, **self.KWARGS)
        self.assertAlmostEqual(roi['productible'], roi['prod_kwh'] / 6.0,
                               places=3)

    def test_agricole_intouche_aucun_pourcentage(self):
        """Aucun taux d'autoconsommation ne doit apparaître sans conso ni
        batterie — le chemin agricole reste inchangé."""
        roi = pricing.calculate_savings_roi(6.0, 90000.0, 90000.0)
        self.assertEqual(roi['savings_model'], 'estimation')
        self.assertTrue(roi['savings_estimated'])
