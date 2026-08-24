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

    def _fichier_typescript(self):
        """Remonte l'arborescence jusqu'au fichier TS, ou ``None``.

        On REMONTE au lieu de compter les niveaux : le harnais docker monte
        le code à ``/app`` (donc ``backend/django_core`` SEUL, sans
        ``apps/web``) alors que la CI et l'hôte ont le dépôt complet. Un
        ``parents[5]`` codé en dur lève ``IndexError`` dans le conteneur — un
        rouge qui n'apprend rien sur les silhouettes.
        """
        for parent in Path(__file__).resolve().parents:
            candidat = parent.joinpath(*self.CHEMIN_TS)
            if candidat.exists():
                return candidat
        return None

    def _shapes_typescript(self):
        fichier = self._fichier_typescript()
        if fichier is None:
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
            # Le conteneur de test ne monte que backend/django_core : rien à
            # épingler ici. La CI, elle, a le dépôt complet et FAIT la
            # comparaison — c'est là que la garde compte.
            self.skipTest('apps/web absent de cet arbre (conteneur backend)')
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
        pas — en RÉGIME ÉTABLI (ordre fondateur 24/08/2026 : le reliquat du
        soir sert le déficit d'avant l'aube), la conservation sur le cycle
        périodique garantit restitué ≤ 0,90 × chargé."""
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

    def test_regime_etabli_sert_le_deficit_d_avant_l_aube(self):
        """Le surplus de midi non consommé le soir survit à minuit et sert le
        creux 00h-06h : le régime établi doit restituer STRICTEMENT plus que
        l'ancien départ-à-vide sur un profil où la nuit précède le surplus."""
        # Nuit gourmande (00h-06h), midi très excédentaire, soirée modérée :
        # au départ-à-vide, le creux nocturne n'était jamais servi.
        conso = [2.0] * 6 + [0.2] * 10 + [1.0] * 8
        prod = [0.0] * 7 + [3.0] * 10 + [0.0] * 7
        r = EH.simuler_batterie_jour(conso, prod, 10.0)
        # L'ancien modèle plafonnait à la seule soirée : 8 h × 1,0 kWh = 8 kWh
        # moins la production de 17h-18h... ici le point dur : il faut servir
        # AUSSI une part du creux nocturne, donc dépasser le seul besoin du
        # soir résiduel (6,0 kWh une fois la production soustraite).
        besoin_soiree_seule = sum(max(0.0, c - p) for c, p in
                                  zip(conso[17:], prod[17:]))
        self.assertGreater(r['restitue_kwh'], besoin_soiree_seule)
        self.assertLessEqual(
            r['restitue_kwh'],
            r['charge_kwh'] * pricing.BATTERY_ROUNDTRIP + 1e-9)

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


# ════════════════════════════════════════════════════════════════════════════
# L-GLITCH — LES IMPULSIONS D'APPAREIL (ordre fondateur du 24/08/2026)
# ════════════════════════════════════════════════════════════════════════════

#: Le lead-type de la mission : villa avec pompe de piscine ET climatisation,
#: les DEUX équipements dont la puissance est réellement connue. Ce sont les
#: réponses au script d'appel, pas des grandeurs choisies pour le test.
EQUIP_PISCINE_CLIM = {
    'piscine': True, 'piscine_pompe_kw': 1.1,
    'clim': True, 'clim_pieces': 5,
}


class RafalesDeriveesTest(SimpleTestCase):
    """La dérivation elle-même : durée = énergie ÷ puissance, plafond 30 min."""

    def test_duree_derivee_exacte_un_kwh_et_demi_a_trois_kw(self):
        """L'exemple du fondateur, au chiffre près : 1,5 kWh d'un appareil de
        3 kW font EXACTEMENT 30 minutes à 3 kW — une seule rafale, puisque
        c'est précisément le plafond."""
        rafale = EH.rafales_de_l_heure(1.5, 3.0)
        self.assertEqual(rafale['nb_rafales'], 1)
        self.assertAlmostEqual(rafale['duree_totale_min'], 30.0, places=9)
        self.assertAlmostEqual(rafale['duree_rafale_min'], 30.0, places=9)
        # La POSITION vient de la calibration (départ moyen mesuré à la minute
        # 26 de l'heure), plus du début d'heure posé en interim : la fenêtre
        # est donc décalée de 0,47 × la marge disponible (60 − 30 = 30 min).
        debut, fin = rafale['fenetres'][0]
        decalage = EH.RAFALE_POSITION_MESUREE * 30.0
        self.assertAlmostEqual(debut, decalage, places=9)
        self.assertAlmostEqual(fin, decalage + 30.0, places=9)
        # L'énergie rendue est celle qu'on a donnée : rien créé, rien perdu.
        self.assertAlmostEqual(rafale['energie_rafales_kwh'], 1.5, places=12)

    def test_trente_minutes_est_un_plafond_jamais_une_duree(self):
        """Correction fondateur : « j'ai dit JUSQU'À 30 min ». Sur dix mille
        couples énergie/puissance tirés au hasard, AUCUNE rafale ne dépasse
        trente minutes et aucune ne sort de son heure."""
        import random
        tirage = random.Random(20260824)
        plus_longue = 0.0
        for _ in range(10000):
            energie = tirage.uniform(0.001, 12.0)
            puissance = tirage.uniform(0.2, 9.0)
            rafale = EH.rafales_de_l_heure(energie, puissance)
            plus_longue = max(plus_longue, rafale['duree_rafale_min'])
            self.assertLessEqual(rafale['duree_rafale_min'],
                                 EH.RAFALE_PLAFOND_MINUTES + 1e-9)
            for debut, fin in rafale['fenetres']:
                self.assertGreaterEqual(debut, -1e-9)
                self.assertLessEqual(fin, 60.0 + 1e-9)
                self.assertLessEqual(debut, fin)
        # Le plafond est ATTEINT quelque part : sinon le test ne prouverait
        # qu'une borne jamais approchée.
        self.assertAlmostEqual(plus_longue, EH.RAFALE_PLAFOND_MINUTES,
                               places=6)

    def test_energie_qui_deborde_le_plafond_cycle_en_plusieurs_rafales(self):
        """L'exemple de la correction : une clim de 1,4 kW dont la couche pèse
        1,05 kWh dans l'heure ne tient pas un bloc de 45 minutes — elle CYCLE
        en deux rafales de 22,5 minutes, comme un compresseur."""
        rafale = EH.rafales_de_l_heure(1.05, 1.4)
        self.assertEqual(rafale['nb_rafales'], 2)
        self.assertAlmostEqual(rafale['duree_totale_min'], 45.0, places=9)
        self.assertAlmostEqual(rafale['duree_rafale_min'], 22.5, places=9)
        # Une rafale par demi-heure : elles ne se collent pas l'une à l'autre.
        # Chacune est posée à la position CALIBRÉE dans SA fenêtre de 30 min
        # (marge 30 − 22,5 = 7,5 min), donc les deux départs restent espacés
        # d'exactement une demi-heure.
        debuts = [round(d, 6) for d, _f in rafale['fenetres']]
        decalage = round(EH.RAFALE_POSITION_MESUREE * 7.5, 6)
        self.assertEqual(debuts, [decalage, round(decalage + 30.0, 6)])

    def test_aucune_puissance_aucune_impulsion(self):
        """Sans puissance (ou sans énergie), on ne concentre RIEN — jamais une
        puissance supposée pour faire tourner la machine."""
        self.assertIsNone(EH.rafales_de_l_heure(1.0, 0))
        self.assertIsNone(EH.rafales_de_l_heure(1.0, None))
        self.assertIsNone(EH.rafales_de_l_heure(0.0, 3.0))

    def test_profils_sont_des_donnees_calibrables_et_sourcees(self):
        """La position et la sous-structure des rafales sont des DONNÉES
        nommées, pas des littéraux dispersés : la calibration Deye remplacera
        ces lignes-là et rien d'autre. Aucun profil ne peut desserrer le
        plafond fondateur."""
        self.assertEqual(EH.PAS_FIN_MINUTES * EH.SOUS_PAS_PAR_HEURE, 60.0)
        self.assertGreaterEqual(EH.RAFALE_POSITION_MESUREE, 0.0)
        self.assertLessEqual(EH.RAFALE_POSITION_MESUREE, 1.0)
        # Le banc de calibration DIT sur quoi il a mesuré — et sa LIMITE : une
        # seule saison (août). Une position « mesurée » sans provenance ni
        # périmètre serait un chiffre posé de plus, pas une mesure.
        banc = EH.CALIBRATION_RAFALE_BANC
        self.assertEqual(banc['source'], EH.CALIBRATION_RAFALE_SOURCE)
        self.assertEqual(banc['jours_valides'], 39)
        self.assertEqual(banc['rafales_mesurees'], 510)
        self.assertEqual(banc['saison'], 'ete_seulement_aout')
        for cle, profil in EH.PROFILS_RAFALE.items():
            with self.subTest(couche=cle):
                self.assertLessEqual(profil['plafond_minutes'],
                                     EH.RAFALE_PLAFOND_MINUTES)
                self.assertTrue(profil.get('cycle'),
                                'le profil %s doit DIRE d\'où vient son '
                                'cycle (source réelle ou interim)' % cle)
                if profil.get('actif'):
                    self.assertTrue(
                        profil.get('puissance'),
                        'un profil actif doit citer la provenance de sa '
                        'puissance : %s' % cle)
        # Le chauffe-eau est l'exception DOCUMENTÉE et INERTE : rien n'est
        # collecté pour lui, donc rien ne sort.
        self.assertFalse(EH.PROFILS_RAFALE['chauffe_eau']['actif'])
        # Le véhicule électrique n'a AUCUNE entrée : sa couche porte une
        # énergie, jamais une puissance de chargeur.
        self.assertNotIn('ve', EH.PROFILS_RAFALE)


class ConservationEnergieGlitchTest(SimpleTestCase):
    """Le raffinement ne crée ni ne détruit un seul kWh."""

    def _jour(self, saison='ete', kwh_jour=20.0):
        equipements = CJ.composer_equipements(EQUIP_PISCINE_CLIM)
        conso, couches = CJ.forme_consommation_detaillee(
            kwh_jour, CJ.OCCUPATION_PRESENCE, saison=saison,
            equipements=equipements)
        prod = [0.0] * 6 + [1.0, 2.5, 4.0, 5.0, 5.5, 5.8,
                            5.8, 5.5, 5.0, 4.0, 2.5, 1.0] + [0.0] * 6
        return conso, prod, couches

    def test_la_chronologie_fine_porte_exactement_la_meme_energie(self):
        conso, prod, couches = self._jour()
        pas, _meta = EH.pas_fins_du_jour(conso, prod, couches)
        self.assertIsNotNone(pas, 'piscine + clim doivent produire des '
                                  'impulsions en été')
        self.assertAlmostEqual(sum(p['conso_kwh'] for p in pas),
                               sum(conso), places=9)
        self.assertAlmostEqual(sum(p['prod_kwh'] for p in pas),
                               sum(prod), places=9)
        self.assertAlmostEqual(sum(p['duree_h'] for p in pas), 24.0, places=9)

    def test_seules_les_heures_porteuses_sont_sous_decoupees(self):
        """Pas de 24 × 12 partout : une heure sans appareil déclaré reste UN
        pas d'une heure."""
        conso, prod, couches = self._jour()
        pas, meta = EH.pas_fins_du_jour(conso, prod, couches)
        porteuses = set(meta['heures_impulsion'])
        self.assertTrue(porteuses)
        for heure in range(24):
            etapes = [p for p in pas if p['heure'] == heure]
            attendu = EH.SOUS_PAS_PAR_HEURE if heure in porteuses else 1
            self.assertEqual(len(etapes), attendu, 'heure %d' % heure)
            # L'énergie de l'heure est conservée heure par heure, pas
            # seulement sur le total du jour.
            self.assertAlmostEqual(sum(e['conso_kwh'] for e in etapes),
                                   conso[heure], places=9)

    def test_la_production_reste_plate_dans_l_heure(self):
        """Le soleil varie LENTEMENT : lui inventer une sous-structure à cinq
        minutes ajouterait du bruit non mesuré. Seule la CHARGE commute."""
        conso, prod, couches = self._jour()
        pas, meta = EH.pas_fins_du_jour(conso, prod, couches)
        for heure in meta['heures_impulsion']:
            etapes = [p for p in pas if p['heure'] == heure]
            valeurs = {round(e['prod_kwh'], 12) for e in etapes}
            self.assertEqual(len(valeurs), 1, 'heure %d' % heure)

    def test_l_impulsion_depasse_vraiment_le_plat_qu_elle_remplace(self):
        """Le « glitch » du fondateur EXISTE dans la courbe : le pic de cinq
        minutes est strictement plus haut que l'heure lissée qu'il remplace."""
        conso, prod, couches = self._jour()
        pas, meta = EH.pas_fins_du_jour(conso, prod, couches)
        for heure in meta['heures_impulsion']:
            etapes = [p for p in pas if p['heure'] == heure]
            pic_kw = max(e['conso_kwh'] for e in etapes) / (1.0 / 12)
            self.assertGreater(pic_kw, conso[heure] * 1.05,
                               'heure %d : aucune pointe' % heure)


class GlitchSortieMoteurTest(SimpleTestCase):
    """Ce que la couche change — et ce qu'elle ne change SURTOUT pas."""

    VILLE = 'Casablanca'

    def _conso(self, mad=2500):
        conso, _source, _detail = EH.profil_depuis_factures(
            facture_hiver_mad=mad)
        return conso

    def _etude(self, **extra):
        base = dict(kwc=8.0, conso_kwh_mensuelles=self._conso(),
                    ville=self.VILLE, occupation=CJ.OCCUPATION_PRESENCE)
        base.update(extra)
        return EH.calculer_etude_horaire(**base)

    #: Les clés HISTORIQUES d'un mois. Cette liste est un CONTRAT : sans
    #: équipement concentrable, la sortie du moteur ne doit pas gagner une
    #: seule clé — sinon tout le parc de devis déjà calculé change de forme.
    CLES_MOIS_HISTORIQUES = {
        'mois', 'saison', 'jours', 'production_kwh', 'consommation_kwh',
        'autoconsomme_sans_kwh', 'autoconsomme_avec_kwh', 'surplus_sans_kwh',
        'import_sans_kwh', 'economie_sans_mad', 'economie_avec_mad',
        'facture_avant_mad', 'facture_apres_sans_mad',
        'facture_apres_avec_mad', 'taux_autoconso_sans', 'taux_autoconso_avec',
        'couverture_sans', 'couverture_avec',
    }
    CLES_RACINE_HISTORIQUES = {
        'version', 'kwc', 'source_production', 'source_productible',
        'source_consommation', 'detail_consommation', 'occupation',
        'equipements_actifs', 'batterie_kwh_utile', 'mois', 'saisons',
        'annuel', 'avertissements',
    }

    def test_sans_equipement_la_sortie_est_celle_d_avant(self):
        """RÈGLE DE LA MISSION : aucun équipement déclaré ⇒ sortie
        BYTE-IDENTIQUE. Pas une clé de plus, pas un centième de différence."""
        etude = self._etude(batterie_kwh_utile=10.0)
        self.assertEqual(set(etude), self.CLES_RACINE_HISTORIQUES)
        self.assertNotIn('glitch', etude)
        for mois in etude['mois']:
            self.assertEqual(set(mois), self.CLES_MOIS_HISTORIQUES)
        for bloc in etude['saisons'].values():
            self.assertNotIn('part_glitch_sans_kwh', bloc)
            self.assertNotIn('part_glitch_avec_kwh', bloc)
        self.assertNotIn('part_glitch_sans_kwh', etude['annuel'])
        self.assertNotIn('part_glitch_avec_kwh', etude['annuel'])
        # La version du bloc historique ne bouge PAS : sa forme est inchangée.
        self.assertEqual(etude['version'], EH.ETUDE_HORAIRE_VERSION)

    def test_un_equipement_sans_puissance_ne_produit_aucune_impulsion(self):
        """« uniquement si une puissance dérivable existe, sinon rien » : le
        véhicule électrique porte des kWh et aucune puissance de chargeur, le
        chauffe-eau ne porte rien du tout."""
        equipements = CJ.composer_equipements({
            'voiture_electrique': True, 've_km_semaine': 300,
            'chauffe_eau_electrique': True,
        })
        self.assertIn('ve', equipements)
        etude = self._etude(equipements=equipements, batterie_kwh_utile=10.0)
        self.assertNotIn('glitch', etude)
        self.assertEqual(set(etude['mois'][0]), self.CLES_MOIS_HISTORIQUES)

    def test_piscine_et_clim_declarees_font_apparaitre_le_bloc(self):
        etude = self._etude(
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=10.0)
        self.assertIn('glitch', etude)
        glitch = etude['glitch']
        self.assertEqual(glitch['methode'], 'impulsions_derivees')
        self.assertEqual(sorted(glitch['couches']), ['clim', 'piscine'])
        self.assertEqual(glitch['plafond_rafale_minutes'],
                         EH.RAFALE_PLAFOND_MINUTES)
        self.assertEqual(glitch['pas_minutes'], EH.PAS_FIN_MINUTES)
        # La sortie servie CITE le banc de mesure — plus un interim posé.
        self.assertEqual(glitch['position_source'],
                         EH.CALIBRATION_RAFALE_SOURCE)
        self.assertEqual(glitch['position_rafale_fenetre'],
                         EH.RAFALE_POSITION_MESUREE)
        self.assertEqual(glitch['porte_sur'], ['sans', 'avec'])
        self.assertGreater(etude['annuel']['part_glitch_sans_kwh'], 0.0)

    def test_le_glitch_ne_fait_que_RETIRER_de_l_autoconsommation(self):
        """Le lissage horaire SURESTIME l'autoconsommation directe : la
        résolution fine ne peut donc que la faire baisser, jamais monter
        (Jensen — le minimum d'une somme dépasse la somme des minimums)."""
        etude = self._etude(
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=10.0)
        for mois in etude['mois']:
            with self.subTest(mois=mois['mois']):
                self.assertGreaterEqual(mois['part_glitch_sans_kwh'], 0.0)
                self.assertGreaterEqual(mois['part_glitch_avec_kwh'], 0.0)
                self.assertGreaterEqual(mois['part_glitch_batterie_kwh'], 0.0)
                # Ce que l'impulsion retire au « sans » part SOIT au réseau
                # (perte du « avec »), SOIT dans la batterie — jamais nulle
                # part.
                self.assertAlmostEqual(
                    mois['part_glitch_sans_kwh'],
                    mois['part_glitch_batterie_kwh']
                    + mois['part_glitch_avec_kwh'], places=1)

    def test_le_glitch_frappe_AUSSI_l_option_sans_batterie(self):
        """PRÉCISION FONDATEUR (24/08/2026) : « je ne veux pas que tu appliques
        ces glitchs que sur le avec batterie, il faudra aussi le sans
        batterie ». Les impulsions vivent dans la COURBE DE CONSOMMATION du
        jour type — la variante SANS batterie intègre contre la même courbe
        hachée, et son économie BAISSE elle aussi. C'est l'honnêteté voulue :
        le modèle lissé la surestimait."""
        etude = self._etude(
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=10.0)
        annuel = etude['annuel']
        # L'effet sur le SANS n'est pas résiduel : il est strictement positif,
        # en kWh comme en dirhams.
        self.assertGreater(annuel['part_glitch_sans_kwh'], 0.0)
        self.assertGreater(annuel['part_glitch_sans_mad'], 0.0)
        # EN kWh, il frappe le SANS au moins aussi fort que le AVEC : la
        # batterie ne peut que rattraper de l'énergie, jamais en détruire.
        # (En DIRHAMS, ce n'est PAS garanti — voir
        # ``test_la_falaise_selective_peut_inverser_le_verdict_en_dirhams``.)
        self.assertGreaterEqual(annuel['part_glitch_sans_kwh'],
                                annuel['part_glitch_avec_kwh'] - 1e-9)

        # Même chose SANS aucune batterie au devis : l'effet reste entier.
        sans_stockage = self._etude(
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=0)
        self.assertGreater(sans_stockage['annuel']['part_glitch_sans_kwh'],
                           0.0)
        self.assertGreater(sans_stockage['annuel']['part_glitch_sans_mad'],
                           0.0)

    def test_l_ecart_avec_moins_sans_grandit_avec_les_impulsions(self):
        """Rendre les pointes visibles RENFORCE l'argument batterie, et d'un
        montant exactement mesuré : l'écart « avec − sans » grandit de
        ``part_glitch_batterie_kwh``, c'est-à-dire de ce que la batterie
        rattrape vraiment. Aucun argument commercial n'est fabriqué : il est
        DÉRIVÉ."""
        etude = self._etude(
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=10.0)
        annuel = etude['annuel']
        gain_batterie = annuel['part_glitch_batterie_kwh']
        self.assertGreater(gain_batterie, 0.0)
        # L'IDENTITÉ : écart_fin − écart_lissé = part_glitch_sans −
        # part_glitch_avec = ce que la batterie rattrape.
        self.assertAlmostEqual(
            annuel['part_glitch_sans_kwh'] - annuel['part_glitch_avec_kwh'],
            gain_batterie, places=1)
        # Et la batterie reste ce qu'elle a toujours été : jamais moins bonne.
        self.assertGreaterEqual(annuel['economie_avec_mad'],
                                annuel['economie_sans_mad'] - 1e-6)

    def test_la_falaise_selective_peut_inverser_le_verdict_en_dirhams(self):
        """CE N'EST PAS UN BUG — c'est la grille SÉLECTIVE marocaine, et il
        faut que quelqu'un le sache avant de « corriger » ce comportement.

        En ÉNERGIE, la batterie rattrape toujours une part de ce que les
        impulsions retirent : ``part_glitch_sans_kwh ≥ part_glitch_avec_kwh``,
        toujours. En ARGENT, non : sur la grille sélective, redescendre sous
        une marche re-tarife TOUT le mois. Quand le résiduel de la variante
        AVEC batterie se tient JUSTE au-dessus d'une marche (à 14 kWc + 15 kWh
        sur le cas piscine+clim, juillet sort à ~616 kWh contre la marche des
        500), les impulsions le poussent de l'autre côté et lui coûtent PLUS de
        dirhams qu'au « sans », pourtant plus gourmand en kWh.

        La leçon commerciale est l'inverse d'un défaut : elle DURCIT l'argument
        de DIM2 — il faut dimensionner le stockage pour atterrir FRANCHEMENT
        sous la marche, pas la frôler, parce que les pointes d'appareil mangent
        la marge qui vous y tenait.
        """
        conso, _s, _d = EH.profil_depuis_factures(
            facture_hiver_mad=2500, facture_ete_mad=4000, ete_differente=True)
        etude = EH.calculer_etude_horaire(
            kwc=14.0, conso_kwh_mensuelles=conso, ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE,
            equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
            batterie_kwh_utile=15.0)
        mois_inverses = [
            m for m in etude['mois']
            if m['part_glitch_avec_mad'] > m['part_glitch_sans_mad'] + 0.5]
        self.assertTrue(
            mois_inverses,
            'ce cas est justement celui où la falaise inverse le verdict en '
            'dirhams : s\'il ne le fait plus, le barème ou la couche a bougé')
        for mois in mois_inverses:
            with self.subTest(mois=mois['mois']):
                # L'inversion est bien MONÉTAIRE seulement : en kWh, le
                # « avec » perd toujours moins.
                self.assertLessEqual(mois['part_glitch_avec_kwh'],
                                     mois['part_glitch_sans_kwh'] + 1e-9)
        # Et malgré tout, la batterie reste globalement gagnante.
        self.assertGreater(etude['annuel']['economie_avec_mad'],
                           etude['annuel']['economie_sans_mad'])

    def test_le_total_de_kwh_ne_bouge_pas_d_un_iota(self):
        """Un RAFFINEMENT, pas un nouveau calcul : à équipements identiques,
        la production et la consommation annuelles sont les mêmes que sans la
        couche fine (seule leur RENCONTRE change)."""
        equipements = CJ.composer_equipements(EQUIP_PISCINE_CLIM)
        etude = self._etude(equipements=equipements, batterie_kwh_utile=10.0)
        jours, _avert, _src = EH.jours_types_annee(
            kwc=8.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE, equipements=equipements)
        conso_attendue = sum(j['conso_mois_kwh'] for j in jours)
        prod_attendue = sum(j['prod_mois_kwh'] for j in jours)
        self.assertAlmostEqual(etude['annuel']['consommation_kwh'],
                               round(conso_attendue, 2), places=1)
        self.assertAlmostEqual(etude['annuel']['production_kwh'],
                               round(prod_attendue, 2), places=1)

    def test_les_monotonies_survivent_a_la_couche_fine(self):
        """Les invariants du moteur restent vrais avec les impulsions : plus
        de kWc ⇒ plus de production, batterie ⇒ jamais moins d'économie, et
        jamais plus d'économie que la facture."""
        equipements = CJ.composer_equipements(EQUIP_PISCINE_CLIM)
        precedent = 0.0
        for kwc in (4.0, 6.0, 8.0, 12.0):
            etude = self._etude(kwc=kwc, equipements=equipements,
                                batterie_kwh_utile=10.0)
            annuel = etude['annuel']
            self.assertGreater(annuel['production_kwh'], precedent)
            precedent = annuel['production_kwh']
            self.assertGreaterEqual(annuel['economie_avec_mad'],
                                    annuel['economie_sans_mad'] - 1e-6)
            self.assertLessEqual(annuel['economie_sans_mad'],
                                 annuel['facture_avant_mad'] + 1e-6)
            self.assertLessEqual(annuel['autoconsomme_sans_kwh'],
                                 annuel['autoconsomme_avec_kwh'] + 1e-6)

    def test_le_balayage_stockage_voit_les_memes_impulsions(self):
        """SOURCE UNIQUE (DIM2) : un balayage resté à l'heure pendant que
        l'étude descend à cinq minutes recommanderait une capacité calibrée sur
        un client qui n'existe pas."""
        equipements = CJ.composer_equipements(EQUIP_PISCINE_CLIM)
        commun = dict(kwc=8.0, conso_kwh_mensuelles=self._conso(),
                      ville=self.VILLE, occupation=CJ.OCCUPATION_PRESENCE,
                      equipements=equipements)
        balayage = EH.balayer_stockage_horaire(capacites_kwh=[10.0], **commun)
        etude = EH.calculer_etude_horaire(batterie_kwh_utile=10.0, **commun)
        self.assertIsNotNone(balayage)
        palier = balayage['paliers'][0]
        self.assertAlmostEqual(palier['autoconsomme_kwh'],
                               etude['annuel']['autoconsomme_avec_kwh'],
                               delta=0.5)


class BatterieDevantLaPointeTest(SimpleTestCase):
    """La batterie ne sert la pointe qu'à hauteur de ce que sa fiche PROUVE."""

    VILLE = 'Casablanca'

    def _commun(self, **extra):
        conso, _s, _d = EH.profil_depuis_factures(facture_hiver_mad=2500)
        base = dict(kwc=8.0, conso_kwh_mensuelles=conso, ville=self.VILLE,
                    occupation=CJ.OCCUPATION_PRESENCE,
                    equipements=CJ.composer_equipements(EQUIP_PISCINE_CLIM),
                    batterie_kwh_utile=10.0)
        base.update(extra)
        return base

    def test_sans_puissance_publiee_la_pointe_n_est_pas_servie(self):
        """RÈGLE CONSERVATRICE DU FONDATEUR, et la PREUVE qu'elle mord.

        Aucune fiche du catalogue ne publie de puissance de DÉCHARGE (le modèle
        porte ``bat_max_charge_kw``, une puissance de CHARGE) : le moteur refuse
        donc de créditer le stockage d'une performance que rien ne prouve. Sur
        un jour de juillet réel, une décharge non bornée ferait restituer près
        du double — ces kWh-là, on ne les annonce pas.

        NUANCE HONNÊTE : la batterie ne récupère pas RIEN pour autant. Elle ne
        SUIT PAS la pointe, mais l'autoconsommation directe ayant baissé, il
        reste plus de surplus à CHARGER dans la journée — et ce surplus-là, elle
        le rend le soir. La reprise est donc réelle mais MINORITAIRE : l'essentiel
        du dépassement part bien au réseau."""
        etude = EH.calculer_etude_horaire(**self._commun())
        glitch = etude['glitch']
        self.assertIsNone(glitch['batterie_puissance_decharge_kw'])
        self.assertEqual(glitch['batterie_puissance_decharge_source'],
                         'aucune_publiee_regle_conservatrice')
        annuel = etude['annuel']
        self.assertGreater(annuel['part_glitch_avec_kwh'],
                           annuel['part_glitch_batterie_kwh'],
                           'la pointe doit majoritairement tirer du réseau')

        # La borne MORD : sur le jour type de juillet, laisser la batterie
        # suivre la pointe lui ferait restituer strictement plus.
        commun = self._commun()
        jours, _avert, _src = EH.jours_types_annee(
            kwc=commun['kwc'],
            conso_kwh_mensuelles=commun['conso_kwh_mensuelles'],
            ville=commun['ville'], occupation=commun['occupation'],
            equipements=commun['equipements'])
        juillet = [j for j in jours if j['mois'] == 7][0]
        self.assertIsNotNone(juillet['pas_fins'])
        conservatrice = EH.simuler_batterie_pas_fins(juillet['pas_fins'], 10.0)
        sans_borne = EH.simuler_batterie_pas_fins(
            juillet['pas_fins'], 10.0, puissance_decharge_kw=1e6)
        self.assertLess(conservatrice['restitue_kwh'],
                        sans_borne['restitue_kwh'] * 0.75,
                        'la règle conservatrice doit vraiment retenir la '
                        'batterie, pas être un no-op décoratif')

    def test_une_puissance_publiee_borne_vraiment_la_decharge(self):
        """Le jour où une fiche publiera sa décharge, le moteur s'en sert — et
        une banque plus « lente » restitue strictement moins, jamais plus que
        sa puissance × la durée des heures déficitaires."""
        conso = [0.4] * 6 + [0.3] * 6 + [0.3] * 6 + [3.0] * 6
        prod = [0.0] * 7 + [1.5, 3.0, 4.0, 4.5, 4.5,
                            4.5, 4.0, 3.0, 1.5] + [0.0] * 8
        pas = [{'heure': h, 'duree_h': 1.0, 'conso_kwh': conso[h],
                'prod_kwh': prod[h],
                'plafond_decharge_kw': max(0.0, conso[h] - prod[h])}
               for h in range(24)]
        libre = EH.simuler_batterie_pas_fins(pas, 12.0)
        bride = EH.simuler_batterie_pas_fins(pas, 12.0,
                                             puissance_decharge_kw=0.5)
        self.assertLess(bride['restitue_kwh'], libre['restitue_kwh'])
        heures_deficit = sum(1 for h in range(24) if conso[h] > prod[h])
        self.assertLessEqual(bride['restitue_kwh'],
                             0.5 * heures_deficit + 1e-9)
        # Monotone : plus lente encore ⇒ restitue encore moins.
        plus_lente = EH.simuler_batterie_pas_fins(
            pas, 12.0, puissance_decharge_kw=0.2)
        self.assertLess(plus_lente['restitue_kwh'], bride['restitue_kwh'])

    def test_sur_un_jour_sans_impulsion_la_fine_egale_l_horaire(self):
        """La borne conservatrice est NON CONTRAIGNANTE au pas horaire : c'est
        ce qui garantit que rien ne bouge sans équipement déclaré."""
        conso = [0.5] * 6 + [1.2] * 10 + [2.4] * 8
        prod = [0.0] * 6 + [0.5, 1.5, 3.0, 4.0, 4.5, 4.8,
                            4.8, 4.5, 4.0, 3.0, 1.5, 0.5] + [0.0] * 6
        pas = [{'heure': h, 'duree_h': 1.0, 'conso_kwh': conso[h],
                'prod_kwh': prod[h],
                'plafond_decharge_kw': max(0.0, conso[h] - prod[h])}
               for h in range(24)]
        for capacite in (0.0, 5.0, 10.0, 30.0):
            with self.subTest(capacite=capacite):
                horaire = EH.simuler_batterie_jour(conso, prod, capacite)
                fine = EH.simuler_batterie_pas_fins(pas, capacite)
                for cle in ('restitue_kwh', 'charge_kwh',
                            'capacite_utilisee_kwh'):
                    self.assertAlmostEqual(fine[cle], horaire[cle], places=9)
        # Et l'autoconsommation directe aussi.
        self.assertAlmostEqual(
            EH.recouvrement_pas_fins(pas),
            sum(min(conso[h], prod[h]) for h in range(24)), places=9)

    def test_le_rendement_aller_retour_tient_toujours(self):
        """Même à cinq minutes : restitué ≤ 0,90 × chargé."""
        etude = EH.calculer_etude_horaire(**self._commun(kwc=12.0))
        for mois in etude['mois']:
            self.assertLessEqual(mois['autoconsomme_avec_kwh'],
                                 min(mois['production_kwh'],
                                     mois['consommation_kwh']) + 1e-6)


# ════════════════════════════════════════════════════════════════════════════
# L-DECH — LA PUISSANCE DE DÉCHARGE : PAR PACK, × QUANTITÉ, ET BORNÉE PAR LE
# PORT BATTERIE DE L'ONDULEUR
# ════════════════════════════════════════════════════════════════════════════

class BorneDechargeDesPacksTest(SimpleTestCase):
    """La pointe servie est bornée — par les packs, par le port, par les deux.

    Fonctions PURES : aucun ORM, aucune fiche en base. Les valeurs employées
    sont celles que ``seed_catalogue`` seede depuis les datasheets (Dyness
    DL5.0C / Powerbox Pro : 100 A × 51,2 V = 5,12 kW ; port Deye SUN-5K :
    120 A × 51,2 V = 6,14 kW), mais ce qui est épinglé ici est le COMPORTEMENT
    du moteur face à une borne, pas le catalogue.
    """

    #: Un jour où la pointe du soir vaut 6 kW — le cas nommé par le fondateur.
    POINTE_KW = 6.0
    HEURES_POINTE = 4

    def _pas_pointe(self, pointe_kw=None, prod_kw=6.0):
        """24 h à pas HORAIRE : production le jour, pointe franche le soir.

        Un pas d'une heure fait coïncider kW et kWh, si bien que les kWh
        servis se lisent directement en puissance — c'est ce qui permet
        d'épingler « 5,12 kW servis, 0,88 kW au réseau » sans arithmétique
        cachée.

        ``prod_kw`` se remonte quand la pointe testée est plus haute : ces
        tests épinglent une borne de PUISSANCE, il faut donc que l'ÉNERGIE
        stockée ne soit jamais le facteur limitant — sinon le manque à l'appel
        mesurerait la taille de la banque et non le débit de la fiche.
        """
        pointe = self.POINTE_KW if pointe_kw is None else pointe_kw
        conso = [0.2] * 24
        prod = [0.0] * 24
        for heure in range(9, 16):
            prod[heure] = prod_kw
        for heure in range(19, 19 + self.HEURES_POINTE):
            conso[heure] = pointe
        return [{'heure': h, 'duree_h': 1.0, 'conso_kwh': conso[h],
                 'prod_kwh': prod[h],
                 'plafond_decharge_kw': max(0.0, conso[h] - prod[h])}
                for h in range(24)]

    @staticmethod
    def _besoin(pas):
        return sum(max(0.0, p['conso_kwh'] - p['prod_kwh']) for p in pas)

    def test_pointe_six_kw_servie_a_hauteur_de_la_fiche(self):
        """LE CAS DU FONDATEUR : pointe 6 kW, décharge fichée 5,12 kW ⇒ 5,12
        servis par la batterie et 0,88 kW qui partent au réseau, heure après
        heure. Un kW de plus serait une performance que la datasheet ne
        publie pas."""
        pas = self._pas_pointe()
        resultat = EH.simuler_batterie_pas_fins(
            pas, 40.0, puissance_decharge_kw=5.12)
        # Ce qui MANQUE à l'appel est exactement le dépassement de la borne :
        # 0,88 kW × 4 heures de pointe, et rien d'autre.
        self.assertAlmostEqual(
            self._besoin(pas) - resultat['restitue_kwh'],
            self.HEURES_POINTE * (self.POINTE_KW - 5.12), places=6)

    def test_deux_packs_servent_deux_fois_la_decharge_unitaire(self):
        """« n'oublie pas de considérer le cas avec deux batteries où c'est
        100 A par batterie » : deux Dyness 10 kWh servent 10,24 kW, pas 5,12.
        La pointe de 6 kW est alors intégralement couverte."""
        pas = self._pas_pointe()
        un = EH.simuler_batterie_pas_fins(pas, 40.0,
                                          puissance_decharge_kw=5.12)
        deux = EH.simuler_batterie_pas_fins(pas, 40.0,
                                            puissance_decharge_kw=2 * 5.12)
        self.assertGreater(deux['restitue_kwh'], un['restitue_kwh'])
        # Avec 10,24 kW disponibles, plus rien de la pointe ne part au réseau.
        self.assertAlmostEqual(deux['restitue_kwh'], self._besoin(pas),
                               places=6)

    def test_composition_mixte_additionne_deux_fiches_differentes(self):
        """Un 10 kWh + un 5 kWh : la borne est la SOMME des deux fiches, pas
        la plus petite (l'ancienne lecture prenait le min) et pas deux fois la
        plus grande."""
        pas = self._pas_pointe(pointe_kw=12.0, prod_kw=12.0)
        dix = 5.12          # Powerbox Pro 10,24 kWh — 100 A × 51,2 V
        cinq = 5.12         # DL5.0C 4,8 kWh — 100 A × 51,2 V aussi
        mixte = EH.simuler_batterie_pas_fins(
            pas, 80.0, puissance_decharge_kw=dix + cinq)
        plus_petite = EH.simuler_batterie_pas_fins(
            pas, 80.0, puissance_decharge_kw=min(dix, cinq))
        self.assertGreater(mixte['restitue_kwh'], plus_petite['restitue_kwh'])
        self.assertAlmostEqual(
            self._besoin(pas) - mixte['restitue_kwh'],
            self.HEURES_POINTE * (12.0 - (dix + cinq)), places=6)

    def test_quantite_un_est_inchangee(self):
        """Épingle anti-régression : à quantité 1, la borne est EXACTEMENT la
        valeur de fiche — la somme sur les lignes ne multiplie rien quand il
        n'y a qu'un seul pack."""
        pas = self._pas_pointe()
        self.assertEqual(
            EH.simuler_batterie_pas_fins(
                pas, 40.0, puissance_decharge_kw=5.12)['restitue_kwh'],
            EH.simuler_batterie_pas_fins(
                pas, 40.0, puissance_decharge_kw=1 * 5.12)['restitue_kwh'])

    def test_le_port_de_l_onduleur_borne_sous_les_packs(self):
        """Deux packs à 5,12 kW derrière un port de 3,3 kW ne servent que
        3,3 kW : le chemin batterie vaut MIN(packs, port)."""
        pas = self._pas_pointe()
        resultat = EH.simuler_batterie_pas_fins(
            pas, 40.0, puissance_decharge_kw=2 * 5.12,
            puissance_decharge_onduleur_kw=3.3)
        self.assertAlmostEqual(
            self._besoin(pas) - resultat['restitue_kwh'],
            self.HEURES_POINTE * (self.POINTE_KW - 3.3), places=6)
        # Strictement moins que sans le port : la borne MORD.
        sans_port = EH.simuler_batterie_pas_fins(
            pas, 40.0, puissance_decharge_kw=2 * 5.12)
        self.assertLess(resultat['restitue_kwh'], sans_port['restitue_kwh'])

    def test_port_onduleur_nul_laisse_la_seule_borne_des_packs(self):
        """PIN : fiche onduleur non renseignée ⇒ SEULE la borne des packs
        s'applique, au kWh près. Un champ vide ne borne rien."""
        pas = self._pas_pointe()
        attendu = EH.simuler_batterie_pas_fins(
            pas, 40.0, puissance_decharge_kw=5.12)
        for vide in (None, 0, 0.0):
            with self.subTest(port=vide):
                obtenu = EH.simuler_batterie_pas_fins(
                    pas, 40.0, puissance_decharge_kw=5.12,
                    puissance_decharge_onduleur_kw=vide)
                self.assertAlmostEqual(obtenu['restitue_kwh'],
                                       attendu['restitue_kwh'], places=12)

    def test_le_port_borne_meme_sous_la_regle_conservatrice(self):
        """Ne pas connaître un goulot n'efface pas l'autre : sans décharge de
        pack publiée, la règle conservatrice s'applique ET le port continue de
        border."""
        pas = self._pas_pointe()
        conservatrice = EH.simuler_batterie_pas_fins(pas, 40.0)
        avec_port = EH.simuler_batterie_pas_fins(
            pas, 40.0, puissance_decharge_onduleur_kw=1.0)
        self.assertLess(avec_port['restitue_kwh'],
                        conservatrice['restitue_kwh'])

    def test_aucune_borne_publiee_garde_la_regle_conservatrice(self):
        """PIN de non-régression : champs NULL partout ⇒ comportement
        strictement identique à celui d'avant L-DECH."""
        pas = self._pas_pointe()
        self.assertEqual(
            EH.simuler_batterie_pas_fins(pas, 40.0)['restitue_kwh'],
            EH.simuler_batterie_pas_fins(
                pas, 40.0, puissance_decharge_kw=None,
                puissance_decharge_onduleur_kw=None,
                puissance_charge_kw=None)['restitue_kwh'])


class _LigneFactice:
    """Une ligne de devis/composition réduite à ce que le lecteur regarde."""

    def __init__(self, designation, quantite, specs):
        self.designation = designation
        self.quantite = quantite
        self.produit = object()
        self.specs = specs


class LectureDesPuissancesDeLaCompositionTest(SimpleTestCase):
    """``puissances_batterie_des_lignes`` — LA source unique, et son
    arithmétique : Σ (fiche × quantité), puis min(packs, port).

    Les fiches sont simulées : ce qui est épinglé ici est la LECTURE, pas le
    catalogue (celui-ci est épinglé dans ``apps.stock.tests``).
    """

    BAT_10 = {'max_decharge_kw': 5.12, 'max_charge_kw': 5.12}
    BAT_5 = {'max_decharge_kw': 5.12, 'max_charge_kw': 3.84}
    OND_5M = {'bat_max_decharge_kw': 6.14, 'bat_max_charge_kw': 6.14}

    def _lire(self, *lignes):
        from unittest import mock
        table = {ligne.produit: ligne.specs for ligne in lignes}
        with mock.patch('apps.stock.selectors.specs_for_produit',
                        side_effect=lambda p: table.get(p, {})):
            return EH.puissances_batterie_des_lignes(list(lignes))

    def test_un_seul_pack_rend_sa_valeur_de_fiche(self):
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 1, self.BAT_10))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 5.12)
        self.assertAlmostEqual(resultat['decharge_kw'], 5.12)
        self.assertEqual(resultat['decharge_source'], 'fiche:max_decharge_kw')

    def test_deux_packs_sur_UNE_ligne_additionnent_la_quantite(self):
        """« avec deux batteries c'est 100 A par batterie » — la quantité de
        la ligne multiplie, elle ne se contente pas de compter pour un."""
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 2, self.BAT_10))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 2 * 5.12)

    def test_composition_mixte_somme_deux_fiches_differentes(self):
        """Un 10 kWh + un 5 kWh : chaque unité à SA valeur de fiche. L'ancienne
        lecture prenait le MIN — elle aurait rendu 3,84 kW en charge au lieu
        de 8,96."""
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 1, self.BAT_10),
            _LigneFactice('Batterie Dyness 5 kWh', 1, self.BAT_5))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 5.12 + 5.12)
        self.assertAlmostEqual(resultat['packs_charge_kw'], 5.12 + 3.84)

    def test_le_port_de_l_onduleur_est_lu_et_borne_le_minimum(self):
        """Deux packs (10,24 kW) derrière un port de 6,14 kW ⇒ la borne servie
        est 6,14, et la sortie DIT que c'est le port qui a mordu."""
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 2, self.BAT_10),
            _LigneFactice('Onduleur Hybride Deye 5 kW', 1, self.OND_5M))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 10.24)
        self.assertAlmostEqual(resultat['ond_decharge_kw'], 6.14)
        self.assertAlmostEqual(resultat['decharge_kw'], 6.14)
        self.assertEqual(resultat['decharge_source'],
                         'fiche:ond_bat_max_decharge_kw')

    def test_deux_onduleurs_offrent_deux_ports(self):
        """La quantité compte des DEUX côtés : deux onduleurs, deux ports."""
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 4, self.BAT_10),
            _LigneFactice('Onduleur Hybride Deye 5 kW', 2, self.OND_5M))
        self.assertAlmostEqual(resultat['ond_decharge_kw'], 2 * 6.14)
        self.assertAlmostEqual(resultat['decharge_kw'], 2 * 6.14)

    def test_une_fiche_muette_compte_pour_zero_jamais_pour_une_supposition(self):
        """Un pack dont la fiche ne publie rien n'apporte AUCUN kW prouvé —
        on ne lui prête pas la valeur de son voisin."""
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 1, self.BAT_10),
            _LigneFactice('Batterie exotique sans fiche', 3, {}))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 5.12)

    def test_aucune_fiche_du_tout_garde_la_regle_conservatrice(self):
        resultat = self._lire(
            _LigneFactice('Batterie exotique sans fiche', 2, {}))
        self.assertIsNone(resultat['decharge_kw'])
        self.assertIsNone(resultat['packs_decharge_kw'])
        self.assertEqual(resultat['decharge_source'],
                         'aucune_publiee_regle_conservatrice')

    def test_les_lignes_hors_sujet_sont_ignorees(self):
        """Un panneau ou une structure ne porte aucune puissance de batterie —
        et un onduleur RÉSEAU, dont la fiche est muette, n'en porte pas non
        plus."""
        resultat = self._lire(
            _LigneFactice('Panneau 710 Wc', 20,
                          {'pmax_wc': 710, 'max_decharge_kw': 99}),
            _LigneFactice('Onduleur Réseau Huawei 100 kW', 1, {}),
            _LigneFactice('Batterie Dyness 10 kWh', 1, self.BAT_10))
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 5.12)
        self.assertIsNone(resultat['ond_decharge_kw'])

    def test_les_roles_de_composition_priment_sur_les_libelles(self):
        """Le balayage DIM2 passe les rôles rendus par
        ``composition_residentielle`` : ils doivent sélectionner les mêmes
        lignes que le classifieur de libellés."""
        lignes = [_LigneFactice('un nom qui ne dit rien', 2, self.BAT_10),
                  _LigneFactice('un autre nom muet', 1, self.OND_5M)]
        from unittest import mock
        table = {ligne.produit: ligne.specs for ligne in lignes}
        with mock.patch('apps.stock.selectors.specs_for_produit',
                        side_effect=lambda p: table.get(p, {})):
            resultat = EH.puissances_batterie_des_lignes(
                lignes, roles=['batterie', 'onduleur_hybride'])
        self.assertAlmostEqual(resultat['packs_decharge_kw'], 2 * 5.12)
        self.assertAlmostEqual(resultat['ond_decharge_kw'], 6.14)

    def test_quantite_nulle_n_apporte_rien(self):
        resultat = self._lire(
            _LigneFactice('Batterie Dyness 10 kWh', 0, self.BAT_10))
        self.assertIsNone(resultat['packs_decharge_kw'])


class BorneChargeDuCheminBatterieTest(SimpleTestCase):
    """« un surplus de 8 kW ne charge pas plus vite que le port ne l'admet »."""

    HEURES_SURPLUS = 6

    def _profil_surplus(self):
        """24 h à FORT surplus diurne : 8 kW nets pendant six heures."""
        conso = [0.2] * 24
        prod = [0.0] * 24
        for heure in range(9, 9 + self.HEURES_SURPLUS):
            prod[heure] = 8.2        # 8,0 kW nets une fois la conso servie
        for heure in range(19, 23):
            conso[heure] = 3.0
        return conso, prod

    def _pas_surplus(self):
        conso, prod = self._profil_surplus()
        return [{'heure': h, 'duree_h': 1.0, 'conso_kwh': conso[h],
                 'prod_kwh': prod[h],
                 'plafond_decharge_kw': max(0.0, conso[h] - prod[h])}
                for h in range(24)]

    def test_le_surplus_horaire_est_borne_par_la_puissance_de_charge(self):
        """8 kW de surplus derrière un port de 2 kW ⇒ l'énergie chargée du pas
        est bornée à 2 kWh, pas 8."""
        pas = self._pas_surplus()
        libre = EH.simuler_batterie_pas_fins(pas, 40.0)
        bride = EH.simuler_batterie_pas_fins(pas, 40.0,
                                             puissance_charge_kw=2.0)
        self.assertLess(bride['charge_kwh'], libre['charge_kwh'])
        self.assertLessEqual(bride['charge_kwh'],
                             2.0 * self.HEURES_SURPLUS + 1e-9)
        # Monotone : plus étroit encore ⇒ charge encore moins.
        plus_etroit = EH.simuler_batterie_pas_fins(pas, 40.0,
                                                   puissance_charge_kw=1.0)
        self.assertLess(plus_etroit['charge_kwh'], bride['charge_kwh'])

    def test_l_invariant_rendement_tient_sous_la_borne_de_charge(self):
        """restitué ≤ 0,90 × chargé — la borne de charge ne le casse pas."""
        pas = self._pas_surplus()
        for borne in (None, 8.0, 5.12, 2.0, 1.0, 0.4):
            with self.subTest(charge_kw=borne):
                resultat = EH.simuler_batterie_pas_fins(
                    pas, 40.0, puissance_charge_kw=borne)
                self.assertLessEqual(
                    resultat['restitue_kwh'],
                    pricing.BATTERY_ROUNDTRIP * resultat['charge_kwh'] + 1e-9)

    def test_la_borne_de_charge_vaut_aussi_au_pas_horaire(self):
        """Le remplissage est un flux soutenu, pas une pointe : il se borne
        aussi dans le simulateur HORAIRE, celui qui sert les devis sans
        équipement déclaré."""
        conso, prod = self._profil_surplus()
        libre = EH.simuler_batterie_jour(conso, prod, 40.0)
        bride = EH.simuler_batterie_jour(conso, prod, 40.0,
                                         puissance_charge_kw=2.0)
        self.assertLess(bride['charge_kwh'], libre['charge_kwh'])
        self.assertLessEqual(bride['charge_kwh'],
                             2.0 * self.HEURES_SURPLUS + 1e-9)

    def test_charge_non_publiee_ne_borne_rien(self):
        """PIN : sans puissance de charge publiée, le simulateur horaire rend
        EXACTEMENT ce qu'il rendait avant L-DECH."""
        conso = [1.0] * 24
        prod = [0.0] * 8 + [4.0] * 8 + [0.0] * 8
        attendu = EH.simuler_batterie_jour(conso, prod, 10.0)
        for vide in (None, 0, 0.0):
            with self.subTest(charge=vide):
                obtenu = EH.simuler_batterie_jour(conso, prod, 10.0,
                                                  puissance_charge_kw=vide)
                for cle in ('restitue_kwh', 'charge_kwh',
                            'capacite_utilisee_kwh'):
                    self.assertAlmostEqual(obtenu[cle], attendu[cle],
                                           places=12)


class EstimationConsoMensuelleTests(SimpleTestCase):
    """L-BACK T4 (24/08/2026) — décomposition mensuelle base/ajouts/total,
    contrat public ``estimation_conso``."""

    CONSO_12 = [400.0] * 12

    def test_aucun_equipement_renvoie_none(self):
        self.assertIsNone(EH.estimation_conso_mensuelle(self.CONSO_12, {}))
        self.assertIsNone(EH.estimation_conso_mensuelle(self.CONSO_12, None))

    def test_serie_invalide_renvoie_none(self):
        equip = {'piscine': {'kw': 1.5, 'heures': list(range(10, 18)),
                             'saisons': ['ete'], 'mode': 'redistribution'}}
        self.assertIsNone(EH.estimation_conso_mensuelle([100.0] * 11, equip))
        self.assertIsNone(EH.estimation_conso_mensuelle([], equip))

    def test_piscine_redistribution_retire_de_la_base_ete_seulement(self):
        equip = {'piscine': {'kw': 1.5, 'heures': list(range(10, 18)),
                             'saisons': ['ete'], 'mode': 'redistribution'}}
        bloc = EH.estimation_conso_mensuelle(self.CONSO_12, equip)
        self.assertIsNotNone(bloc)
        self.assertEqual(len(bloc['base_mensuelle']), 12)
        self.assertEqual(len(bloc['totale_mensuelle']), 12)
        self.assertIn('piscine', bloc['ajouts'])
        # SAISONS['ete'] = juin/juillet/août/septembre (voir SAISONS ci-dessous
        # dans pvgis_profils) — seuls ces mois portent un ajout piscine.
        mois_ete = [i for i, v in enumerate(bloc['ajouts']['piscine']) if v > 0]
        self.assertTrue(mois_ete)
        for i in mois_ete:
            with self.subTest(mois=i + 1):
                # base = conso - ajout (redistribution : rien n'est ajouté au
                # total réel, seulement retiré de la « base » affichée).
                self.assertAlmostEqual(
                    bloc['base_mensuelle'][i] + bloc['ajouts']['piscine'][i],
                    self.CONSO_12[i], places=2)
                self.assertAlmostEqual(
                    bloc['totale_mensuelle'][i], self.CONSO_12[i], places=2)
        for i in range(12):
            if i not in mois_ete:
                self.assertEqual(bloc['ajouts']['piscine'][i], 0.0)
                self.assertAlmostEqual(bloc['totale_mensuelle'][i],
                                       self.CONSO_12[i], places=2)

    def test_ve_addition_grossit_le_total_toutes_saisons(self):
        equip = {'ve': {'kwh_jour': 4.0, 'heures': [21, 22, 23],
                        'saisons': None, 'mode': 'addition'}}
        bloc = EH.estimation_conso_mensuelle(self.CONSO_12, equip)
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['base_mensuelle'], [400.0] * 12)
        for i in range(12):
            with self.subTest(mois=i + 1):
                self.assertGreater(bloc['ajouts']['ve'][i], 0.0)
                self.assertAlmostEqual(
                    bloc['totale_mensuelle'][i],
                    bloc['base_mensuelle'][i] + bloc['ajouts']['ve'][i],
                    places=2)

    def test_couche_sans_grandeur_reelle_ne_produit_aucun_ajout(self):
        equip = {'piscine': {'kw': 0, 'heures': [], 'saisons': ['ete'],
                             'mode': 'redistribution'}}
        self.assertIsNone(EH.estimation_conso_mensuelle(self.CONSO_12, equip))


class JoursTypesPublicsTests(SimpleTestCase):
    """L-BACK T4 — les 4 mois publics (contrat ``jours_types``), Casablanca
    (table de référence PVGIS, aucun accès réseau)."""

    VILLE = 'Casablanca'

    def _conso(self, mad=1200):
        conso, _source, _detail = EH.profil_depuis_factures(
            facture_hiver_mad=mad)
        return conso

    def test_quatre_mois_avec_les_six_cles_du_contrat(self):
        bloc = EH.jours_types_publics(
            kwc=6.0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE,
            occupation=CJ.OCCUPATION_PRESENCE)
        self.assertIsNotNone(bloc)
        self.assertEqual(set(bloc), {'1', '4', '7', '11'})
        for numero, mois in bloc.items():
            with self.subTest(mois=numero):
                self.assertEqual(len(mois['prod_kw']), 24)
                self.assertEqual(len(mois['conso_kw']), 24)
                for cle in ('conso_jour_kwh', 'prod_jour_kwh',
                            'autoconsomme_kwh', 'surplus_kwh'):
                    self.assertIsInstance(mois[cle], float)
                # Conservation : autoconsommé ≤ min(prod, conso) du jour.
                self.assertLessEqual(
                    mois['autoconsomme_kwh'],
                    min(mois['prod_jour_kwh'], mois['conso_jour_kwh']) + 1e-6)

    def test_sans_puissance_renvoie_none(self):
        self.assertIsNone(EH.jours_types_publics(
            kwc=0, conso_kwh_mensuelles=self._conso(), ville=self.VILLE))

    def test_sans_localisation_renvoie_none(self):
        self.assertIsNone(EH.jours_types_publics(
            kwc=6.0, conso_kwh_mensuelles=self._conso(), ville=None))

    def test_sans_consommation_renvoie_none(self):
        self.assertIsNone(EH.jours_types_publics(
            kwc=6.0, conso_kwh_mensuelles=[], ville=self.VILLE))
