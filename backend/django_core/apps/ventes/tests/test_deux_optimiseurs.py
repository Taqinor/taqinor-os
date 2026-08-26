# -*- coding: utf-8 -*-
"""L-2OPT — DEUX OPTIMISEURS : l'option « avec batterie » a son propre champ PV.

CE QUE CES TESTS VERROUILLENT, ET POURQUOI
------------------------------------------
Le moteur calibré (``apps.ventes.dimensionnement``) désigne DEUX gagnants
depuis DIM2 : ``recommandation`` (meilleur payback SANS stockage) et
``recommandation_avec`` (balayage CONJOINT champ × stockage). Le second
n'alimentait AUCUN chemin de génération de lignes — un devis « Les deux »
composait UN champ PV et se contentait de le regarder de deux façons, le
découpage sans/avec du PDF n'étant qu'un filtrage par MOTS-CLÉS. Panneaux,
structures, socles et pose tombaient donc dans les DEUX options à la MÊME
quantité, et une option « avec » économiquement plus grande était
inexprimable.

Cinq garanties, une classe chacune :

1. **La fusion** — deux dimensionnements DIFFÉRENTS produisent des lignes
   VARIANTÉES ; deux dimensionnements ÉGAUX produisent la composition
   historique, à la ligne près (le repli de sécurité absolu).
2. **Le devis mono « avec »** est dimensionné sur l'optimum AVEC (champ ET
   capacité de stockage), plus sur celui d'un champ sans batterie.
3. **La resynchronisation 3D** traite le calepinage comme un PLAFOND
   physique, par variante : une option qui dépasse est ramenée dessus, une
   option en dessous n'est JAMAIS augmentée.
4. **L'aval** (bon de commande / facture / chantier) respecte la variante :
   une ligne « avec » ne part jamais dans un document « sans », et
   réciproquement.
5. **Le repli** — moteur muet sur l'axe batterie ⇒ comportement d'hier, mot
   pour mot, et JAMAIS un chiffre inventé pour combler le trou.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_deux_optimiseurs -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import dimensionnement, services
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, filter_lines_for_option, option_lines,
)
from authentication.models import Company

User = get_user_model()

#: Même catalogue que celui semé par ``seed_catalogue`` — les DÉSIGNATIONS
#: font foi (c'est par elles que la composition et le moteur PDF classent).
CATALOGUE = [
    ('Panneau Jinko 550W', 'PAN550', '1100'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Batterie Dyness 10 kWh', 'BAT10', '30000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Socles', 'SOC-BET', '80'),
    ('Smart Meter', 'SMART-MET', '1800'),
    ('Wifi Dongle', 'WIFI-DON', '1200'),
    ('Accessoires', 'ACC-CAT', '2000'),
    ('Tableau De Protection AC/DC', 'TAB-PROT', '2000'),
    ('Installation', 'INST-CAT', '4800'),
    ('Transport', 'TRANS-CAT', '1000'),
]

#: L-FORFAIT — le barème AU PANNEAU vit dans le STOCK (fixe HT, par panneau HT).
#: Il est indispensable ici : c'est LUI qui fait diverger le prix de la pose
#: entre deux champs de tailles différentes, donc qui prouve la fusion.
BAREMES_FORFAIT = {
    'INST-CAT': ('2000', '250'),
    'ACC-CAT': ('0', '52.0833'),
    'TAB-PROT': ('0', '203.1250'),
}


class _Base(TestCase):
    """Catalogue résidentiel complet, fiches techniques comprises."""

    slug = 'l2opt-co'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'L2OPT'})
        self.user = User.objects.create_user(
            username='l2opt-%s' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.produits = {}
        for nom, sku, prix in CATALOGUE:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[sku] = Produit.objects.create(
                company=self.company, nom=nom, sku='%s-%s' % (sku, self.slug),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self._poser_fiches_techniques()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Deux Optimums',
            email='client-%s@example.com' % self.slug)

    def _poser_fiches_techniques(self):
        """PVFCH — « never invent numbers » : le catalogue porte ses fiches.

        Sans elles la composition « avec batterie » n'aurait AUCUNE batterie
        (le garde de tension exige une tension MESURÉE) et la conception
        électrique refuserait — on ne testerait alors plus la fusion.
        """
        FicheTechnique.objects.create(
            company=self.company, produit=self.produits['PAN550'],
            type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        for sku in ('ONDR5', 'ONDH5'):
            FicheTechnique.objects.create(
                company=self.company, produit=self.produits[sku],
                type_fiche='onduleur',
                ond_ac_kw=Decimal('5.00'), ond_phases=1, ond_n_mppt=2,
                ond_mppt_v_min=Decimal('90.0'),
                ond_mppt_v_max=Decimal('560.0'),
                ond_v_max_abs=Decimal('600.0'),
                ond_i_max_mppt_a=Decimal('13.5'),
                ond_rendement_euro_pct=Decimal('97.0'),
                ond_bat_aucune=(sku == 'ONDR5'),
                ond_bat_v_min=(None if sku == 'ONDR5' else Decimal('40.0')),
                ond_bat_v_max=(None if sku == 'ONDR5' else Decimal('60.0')))
        for sku, kwh_nom, kwh_util, charge_kw in (
                ('BAT5', '5.12', '4.60', '3.84'),
                ('BAT10', '10.24', '9.22', '5.12')):
            FicheTechnique.objects.create(
                company=self.company, produit=self.produits[sku],
                type_fiche='batterie',
                bat_kwh_nominal=Decimal(kwh_nom),
                bat_kwh_usable=Decimal(kwh_util),
                bat_dod_pct=Decimal('90.0'),
                bat_v_nominal=Decimal('51.2'),
                bat_max_charge_kw=Decimal(charge_kw))

    # ── Raccourcis ──────────────────────────────────────────────────────────
    def _catalogue(self):
        return services.catalogue_de_la_societe(self.company)

    def _lead(self, email='deux@example.com', **extra):
        return Lead.objects.create(
            company=self.company, nom='Deux', prenom='Optimums',
            email=email, **extra)

    def _empreinte(self, lignes):
        """La signature COMPLÈTE d'une composition — c'est elle qui doit être
        byte-identique quand les deux dimensionnements sont égaux."""
        return [(getattr(ligne.produit, 'sku', None), ligne.designation,
                 int(ligne.quantite), Decimal(ligne.prix_unitaire),
                 ligne.variante)
                for ligne in lignes]

    def _par_designation(self, lignes):
        """``{désignation: [(quantité, variante), ...]}`` — une désignation
        peut porter DEUX lignes quand la fusion a distingué les options."""
        carte = {}
        for ligne in lignes:
            carte.setdefault(ligne.designation, []).append(
                (int(ligne.quantite), ligne.variante))
        return carte


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA FUSION
# ═══════════════════════════════════════════════════════════════════════════
class LaFusionDesDeuxKits(_Base):
    slug = 'l2opt-fusion'

    def test_deux_dimensionnements_differents_variantent_les_lignes(self):
        """8 panneaux « sans » contre 10 « avec » : tout ce qui diffère se
        dédouble, tout ce qui coïncide reste une ligne commune."""
        lignes = services.composition_deux_optimiseurs(
            self._catalogue(), panel_watt=550,
            kwc_sans=4.4, nb_panneaux_sans=8,
            kwc_avec=5.5, nb_panneaux_avec=10,
            batterie_cible_kwh=10.0)
        carte = self._par_designation(lignes)

        # Les panneaux : DEUX lignes, une par option.
        self.assertEqual(sorted(carte['Panneau Jinko 550W']),
                         [(8, 'sans'), (10, 'avec')])
        # La ferrure suit son champ, elle aussi.
        self.assertEqual(sorted(carte['Structures acier']),
                         [(8, 'sans'), (10, 'avec')])
        self.assertEqual(sorted(carte['Socles']),
                         [(16, 'sans'), (20, 'avec')])

        # Les onduleurs : un par option, jamais commun.
        self.assertEqual(carte['Onduleur réseau Huawei 5kW Monophasé'],
                         [(1, 'sans')])
        self.assertEqual(carte['Onduleur hybride Deye 5kW Monophasé'],
                         [(1, 'avec')])
        # La batterie n'existe QUE dans l'option avec — et c'est la capacité
        # dictée par le moteur (10 kWh), pas la règle kWc/5 (qui aurait donné
        # un module de 5 kWh à 5,5 kWc).
        self.assertEqual(carte['Batterie Dyness 10 kWh'], [(1, 'avec')])
        self.assertNotIn('Batterie Dyness 5 kWh', carte)

        # Le forfait de pose se cote AU PANNEAU : deux champs = deux prix,
        # donc deux lignes (2 000 + 250×8 = 4 000 ; 2 000 + 250×10 = 4 500).
        poses = {ligne.variante: Decimal(ligne.prix_unitaire)
                 for ligne in lignes if ligne.designation == 'Installation'}
        self.assertEqual(poses,
                         {'sans': Decimal('4000.00'),
                          'avec': Decimal('4500.00')})

        # Le transport ne dépend pas du champ : UNE ligne, commune.
        self.assertEqual(carte['Transport'], [(1, '')])

    def test_toute_ligne_variante_appartient_a_une_option_reelle(self):
        """Aucune variante fantaisiste : '' , 'sans' ou 'avec', rien d'autre."""
        lignes = services.composition_deux_optimiseurs(
            self._catalogue(), panel_watt=550,
            kwc_sans=4.4, nb_panneaux_sans=8,
            kwc_avec=5.5, nb_panneaux_avec=10)
        self.assertTrue(
            {ligne.variante for ligne in lignes} <= {'', 'sans', 'avec'})
        self.assertTrue(getattr(lignes, 'variantes', False))
        self.assertEqual(lignes.nb_panneaux, 8)
        self.assertEqual(lignes.nb_panneaux_avec, 10)

    # ── LE REPLI DE SÉCURITÉ ABSOLU ─────────────────────────────────────────
    def test_dimensionnements_egaux_rendent_la_composition_historique(self):
        """MÊME nombre de panneaux ⇒ AUCUNE fusion : la composition « deux
        options » d'aujourd'hui, ligne pour ligne, toutes variantes vides.

        C'est LA garantie de non-régression du chantier : tant que le moteur
        ne dit pas deux choses différentes, un devis d'aujourd'hui est
        inchangé au bit près.
        """
        historique = services.composition_residentielle(
            self._catalogue(), kwc=4.4, panel_watt=550, nb_panneaux=8,
            deux_options=True)
        fusionnee = services.composition_deux_optimiseurs(
            self._catalogue(), panel_watt=550,
            kwc_sans=4.4, nb_panneaux_sans=8,
            kwc_avec=4.4, nb_panneaux_avec=8)

        self.assertEqual(self._empreinte(fusionnee),
                         self._empreinte(historique))
        self.assertEqual({ligne.variante for ligne in fusionnee}, {''})
        self.assertFalse(getattr(fusionnee, 'variantes', False))

    def test_optimum_avec_absent_vaut_optimum_sans(self):
        """``nb_panneaux_avec`` à 0 (moteur muet) = les deux champs sont le
        même : on retombe sur le repli, jamais sur une fusion à moitié."""
        fusionnee = services.composition_deux_optimiseurs(
            self._catalogue(), panel_watt=550,
            kwc_sans=4.4, nb_panneaux_sans=8,
            kwc_avec=None, nb_panneaux_avec=0)
        self.assertEqual(
            self._empreinte(fusionnee),
            self._empreinte(services.composition_residentielle(
                self._catalogue(), kwc=4.4, panel_watt=550, nb_panneaux=8,
                deux_options=True)))


# ═══════════════════════════════════════════════════════════════════════════
# 2. LE DEVIS AUTO LIT recommandation_avec
# ═══════════════════════════════════════════════════════════════════════════
class LeDevisAutoSuitLOptimumAvec(_Base):
    slug = 'l2opt-auto'

    #: Ce que le moteur calibré renvoie : 8 panneaux sans stockage, 10 avec —
    #: et 10 kWh de batterie sur ce second champ.
    OPTIMUM_AVEC = {'nb_panneaux': 10, 'kwc': 5.5, 'panel_watt': 550,
                    'batterie_kwh': 10.0}

    def _auto(self, *, scenario, optimum_avec, email):
        with patch.object(services, 'profil_reel_existe', return_value=True), \
                patch.object(services, '_panneaux_dimensionnement_horaire',
                             return_value=(8, 550, 'moteur_horaire',
                                           optimum_avec)):
            return services.build_devis_auto(
                lead=self._lead(email=email), user=self.user,
                company=self.company, scenario=scenario)

    def test_mono_avec_est_dimensionne_sur_loptimum_avec(self):
        """Le devis ne propose QUE le stockage : il doit être dimensionné sur
        le champ que l'axe batterie a choisi (10 panneaux), et porter la
        capacité de ce même optimum (10 kWh) — pas les 8 panneaux d'un champ
        sans batterie que personne n'achètera, ni les 5 kWh de la règle kWc/5.
        """
        devis = self._auto(scenario='avec', optimum_avec=self.OPTIMUM_AVEC,
                           email='mono-avec@example.com')
        carte = self._par_designation(devis.lignes.all())

        self.assertEqual(carte['Panneau Jinko 550W'], [(10, '')])
        self.assertEqual(carte['Batterie Dyness 10 kWh'], [(1, '')])
        self.assertNotIn('Batterie Dyness 5 kWh', carte)
        self.assertEqual(carte['Onduleur hybride Deye 5kW Monophasé'],
                         [(1, '')])
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', carte)
        # Devis MONO-option : aucune ligne n'a de raison de porter une variante.
        self.assertEqual({li.variante for li in devis.lignes.all()}, {''})

    def test_mono_sans_ignore_completement_loptimum_avec(self):
        """L'axe batterie ne concerne pas un devis « sans batterie » : le champ
        reste celui de ``recommandation`` (8 panneaux)."""
        devis = self._auto(scenario='sans', optimum_avec=self.OPTIMUM_AVEC,
                           email='mono-sans@example.com')
        carte = self._par_designation(devis.lignes.all())
        self.assertEqual(carte['Panneau Jinko 550W'], [(8, '')])
        self.assertEqual({li.variante for li in devis.lignes.all()}, {''})

    def test_les_deux_composent_les_deux_champs(self):
        devis = self._auto(scenario='les_deux',
                           optimum_avec=self.OPTIMUM_AVEC,
                           email='les-deux@example.com')
        carte = self._par_designation(devis.lignes.all())
        self.assertEqual(sorted(carte['Panneau Jinko 550W']),
                         [(8, 'sans'), (10, 'avec')])
        self.assertEqual(carte['Batterie Dyness 10 kWh'], [(1, 'avec')])
        # Le scénario stocké reste « Les deux » : le moteur PDF doit rendre la
        # comparaison, pas un libellé mono.
        self.assertEqual((devis.etude_params or {}).get('scenario'),
                         services.SCENARIO_LES_DEUX)

    # ── LE REPLI : moteur muet sur l'axe batterie ───────────────────────────
    def test_recommandation_avec_indisponible_ne_change_rien(self):
        """Aucune configuration « avec » livrable ⇒ les deux options se
        composent sur le MÊME champ, exactement comme aujourd'hui : aucune
        ligne variantée, et surtout aucun chiffre inventé."""
        devis = self._auto(scenario='les_deux', optimum_avec=None,
                           email='repli@example.com')
        carte = self._par_designation(devis.lignes.all())
        self.assertEqual(carte['Panneau Jinko 550W'], [(8, '')])
        self.assertEqual({li.variante for li in devis.lignes.all()}, {''})
        # 4,4 kWc → la règle historique kWc/5 : un module de 5 kWh.
        self.assertEqual(carte['Batterie Dyness 5 kWh'], [(1, '')])

    def test_le_pompage_reste_hors_de_ce_chantier(self):
        """Garde-fou : le devis auto refuse toujours un lead NON résidentiel.

        L-2OPT ne vit que dans la composition RÉSIDENTIELLE ; l'agricole
        (pompage — jamais de batterie) et l'industriel n'y passent même pas.
        """
        lead = self._lead(email='pompage@example.com',
                          type_installation='agricole')
        with patch.object(services, 'profil_reel_existe', return_value=True), \
                patch.object(services, '_panneaux_dimensionnement_horaire',
                             return_value=(8, 550, 'moteur_horaire',
                                           self.OPTIMUM_AVEC)):
            with self.assertRaises(services.AutoDevisError):
                services.build_devis_auto(
                    lead=lead, user=self.user, company=self.company,
                    scenario='les_deux')

    def test_lecture_de_la_recommandation_avec_du_moteur(self):
        """``_recommandation_avec_rendue`` ne retient que du CHIFFRÉ, et
        répond ``None`` — donc « repli » — à tout le reste."""
        lu = services._recommandation_avec_rendue(
            {'panneaux': 12, 'kwc': 6.6, 'panel_watt': 550,
             'batterie_kwh': 15.0, 'payback_avec_annees': 6.2})
        self.assertEqual(lu, {'nb_panneaux': 12, 'kwc': 6.6,
                              'panel_watt': 550, 'batterie_kwh': 15.0})
        for muet in (None, {}, {'panneaux': 0}, {'panneaux': 'douze'},
                     'pas un dict'):
            self.assertIsNone(services._recommandation_avec_rendue(muet), muet)
        # Une capacité nulle n'est pas une capacité : on ne la transmet pas.
        self.assertIsNone(
            services._recommandation_avec_rendue(
                {'panneaux': 8, 'batterie_kwh': 0})['batterie_kwh'])


# ═══════════════════════════════════════════════════════════════════════════
# 3. LA RESYNCHRONISATION 3D — LE CALEPINAGE EST UN PLAFOND
# ═══════════════════════════════════════════════════════════════════════════
class LeCalepinagePlafonneChaqueOption(_Base):
    slug = 'l2opt-resync'

    def _devis_variante(self, *, sans, avec):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-L2OPT-%s-%s' % (sans, avec),
            client=self.client_obj,
            statut=Devis.Statut.BROUILLON, created_by=self.user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params={'scenario': services.SCENARIO_LES_DEUX})
        pan = self.produits['PAN550']
        LigneDevis.objects.create(
            devis=devis, produit=pan, designation=pan.nom,
            quantite=Decimal(str(sans)), prix_unitaire=Decimal('1100'),
            variante='sans', ordre=1)
        LigneDevis.objects.create(
            devis=devis, produit=pan, designation=pan.nom,
            quantite=Decimal(str(avec)), prix_unitaire=Decimal('1100'),
            variante='avec', ordre=2)
        for sku, variante, quantite in (
                ('STR-ACIER', 'sans', sans), ('STR-ACIER', 'avec', avec),
                ('SOC-BET', 'sans', sans * 2), ('SOC-BET', 'avec', avec * 2)):
            produit = self.produits[sku]
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal(produit.prix_vente), variante=variante)
        for sku, variante in (('ONDR5', 'sans'), ('ONDH5', 'avec'),
                              ('BAT10', 'avec')):
            produit = self.produits[sku]
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'),
                prix_unitaire=Decimal(produit.prix_vente), variante=variante)
        return devis

    @staticmethod
    def _layout(panels):
        return {'scenario': 'reseau', 'panelWatt': 550,
                'result': {'panels': panels,
                           'kwc': round(panels * 550 / 1000.0, 3)}}

    def _quantites(self, devis, designation):
        return {li.variante: int(li.quantite)
                for li in devis.lignes.filter(designation=designation)}

    def test_seule_loption_qui_deborde_est_ramenee_au_plafond(self):
        """9 panneaux tiennent sur le toit : l'option « avec » (10) est
        ramenée à 9, l'option « sans » (8) n'est PAS montée à 9 — l'optimum
        économique a le droit de choisir moins que le toit."""
        devis = self._devis_variante(sans=8, avec=10)
        resultat = services.sync_devis_from_layout(
            devis, self._layout(9), self.user)

        self.assertEqual(self._quantites(devis, 'Panneau Jinko 550W'),
                         {'sans': 8, 'avec': 9})
        # La ferrure suit le compte DE SA VARIANTE.
        self.assertEqual(self._quantites(devis, 'Structures acier'),
                         {'sans': 8, 'avec': 9})
        self.assertEqual(self._quantites(devis, 'Socles'),
                         {'sans': 16, 'avec': 18})
        # Le compte rendu annonce l'option 1, jamais la somme des deux paniers.
        self.assertEqual(resultat['panneaux'], 8)
        self.assertFalse(resultat['inchange'])

    def test_un_toit_qui_ecrete_sous_le_sans_fait_converger_les_deux_options(
            self):
        """VERROU DU TOIT — quand le calepinage ne tient PAS plus que le
        compte « sans » lui-même, les DEUX options débordent et sont
        ramenées au MÊME plafond : la divergence entre les deux optimiseurs
        ne survit pas à un toit trop petit pour porter ne serait-ce que
        l'option la plus modeste.

        Contraste avec ``test_seule_loption_qui_deborde_est_ramenee_au_
        plafond`` juste au-dessus (toit à 9 : seule l'option « avec » (10)
        déborde, elles restent divergentes 8/9). Ici le toit tombe à 6 —
        SOUS le compte « sans » (8) — donc les deux options débordent et
        convergent sur le même compte écrêté.
        """
        devis = self._devis_variante(sans=8, avec=10)
        resultat = services.sync_devis_from_layout(
            devis, self._layout(6), self.user)

        quantites = self._quantites(devis, 'Panneau Jinko 550W')
        self.assertEqual(
            quantites, {'sans': 6, 'avec': 6},
            'un toit à 6 panneaux (sous le compte « sans » de 8) doit '
            'ramener LES DEUX options au même plafond : obtenu %s'
            % quantites)
        self.assertEqual(
            quantites['sans'], quantites['avec'],
            'le verrou du toit doit faire CONVERGER les deux optimiseurs '
            'quand aucun des deux ne tient sur le toit : sans=%s avec=%s'
            % (quantites.get('sans'), quantites.get('avec')))
        # La ferrure suit, elle aussi, le même plafond des deux côtés.
        self.assertEqual(self._quantites(devis, 'Structures acier'),
                         {'sans': 6, 'avec': 6})
        self.assertEqual(self._quantites(devis, 'Socles'),
                         {'sans': 12, 'avec': 12})
        self.assertEqual(resultat['panneaux'], 6)
        self.assertFalse(resultat['inchange'])

    def test_un_toit_plus_grand_n_augmente_aucune_option(self):
        """20 panneaux posables : ni l'une ni l'autre option ne grossit."""
        devis = self._devis_variante(sans=8, avec=10)
        services.sync_devis_from_layout(devis, self._layout(20), self.user)
        self.assertEqual(self._quantites(devis, 'Panneau Jinko 550W'),
                         {'sans': 8, 'avec': 10})
        self.assertEqual(self._quantites(devis, 'Structures acier'),
                         {'sans': 8, 'avec': 10})

    def test_la_batterie_et_les_deux_onduleurs_survivent(self):
        """Garde L-2OPT conservée : un calepinage « réseau » ne retire ni la
        batterie ni l'onduleur de l'option qu'elle sert."""
        devis = self._devis_variante(sans=8, avec=10)
        services.sync_devis_from_layout(devis, self._layout(9), self.user)
        designations = set(devis.lignes.values_list('designation', flat=True))
        self.assertIn('Batterie Dyness 10 kWh', designations)
        self.assertIn('Onduleur réseau Huawei 5kW Monophasé', designations)
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', designations)
        self.assertEqual((devis.etude_params or {}).get('scenario'),
                         services.SCENARIO_LES_DEUX)

    def test_deux_lignes_variantees_ne_font_pas_deux_modeles(self):
        """L'avertissement « ce devis porte N modèles de panneau différents »
        ne doit PAS se déclencher pour deux lignes variantées du MÊME modèle,
        sinon tout devis à deux optimiseurs crierait au faux problème."""
        devis = self._devis_variante(sans=8, avec=10)
        cible = services.cible_depuis_lignes(devis)
        self.assertEqual(
            [a for a in cible['avertissements'] if 'modèles' in a], [])
        # La cible dessinée par l'écran 3D est celle de l'option 1.
        self.assertEqual(cible['panneaux'], 8)
        # CTX3D (25/08/2026) — CETTE ASSERTION DISAIT LE DÉFAUT. Le scénario se
        # lisait sur TOUTES les lignes : la cible annonçait « avec_batterie »
        # au-dessus du compte de panneaux de l'option SANS (dont l'onduleur est
        # RÉSEAU et qui ne porte aucune batterie) — une installation que rien
        # ne décrit. Les quatre grandeurs viennent maintenant du MÊME
        # sous-ensemble ; l'option 2 a sa propre vue (``variante='avec'``, et
        # la clé ``cible_avec`` du contexte PV17).
        self.assertEqual(cible['scenario'], 'reseau')
        self.assertFalse(cible['batterie'])
        avec = services.cible_depuis_lignes(devis, variante='avec')
        self.assertEqual((avec['panneaux'], avec['scenario']),
                         (10, 'avec_batterie'))


# ═══════════════════════════════════════════════════════════════════════════
# 4. L'AVAL RESPECTE LA VARIANTE
# ═══════════════════════════════════════════════════════════════════════════
class LAvalNeMelangeJamaisLesOptions(_Base):
    slug = 'l2opt-aval'

    def _devis_variante(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-L2OPT-AVAL',
            client=self.client_obj,
            statut=Devis.Statut.BROUILLON, created_by=self.user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params={'scenario': services.SCENARIO_LES_DEUX})
        pan = self.produits['PAN550']
        for variante, quantite in (('sans', 8), ('avec', 10)):
            LigneDevis.objects.create(
                devis=devis, produit=pan, designation=pan.nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal('1100'), variante=variante)
        for sku, variante in (('ONDR5', 'sans'), ('ONDH5', 'avec'),
                              ('BAT10', 'avec'), ('TRANS-CAT', '')):
            produit = self.produits[sku]
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'),
                prix_unitaire=Decimal(produit.prix_vente), variante=variante)
        return devis

    def test_le_bon_de_commande_sans_ne_prend_que_le_champ_sans(self):
        devis = self._devis_variante()
        lignes = option_lines(devis, SANS_BATTERIE)
        quantites = {li.designation: int(li.quantite) for li in lignes}
        self.assertEqual(quantites['Panneau Jinko 550W'], 8)
        self.assertNotIn('Batterie Dyness 10 kWh', quantites)
        self.assertNotIn('Onduleur hybride Deye 5kW Monophasé', quantites)
        self.assertIn('Onduleur réseau Huawei 5kW Monophasé', quantites)
        # La ligne COMMUNE part dans les deux documents.
        self.assertIn('Transport', quantites)
        # Une seule ligne de panneaux : jamais les deux options commandées.
        self.assertEqual(
            len([li for li in lignes
                 if li.designation == 'Panneau Jinko 550W']), 1)

    def test_le_bon_de_commande_avec_ne_prend_que_le_champ_avec(self):
        devis = self._devis_variante()
        lignes = option_lines(devis, AVEC_BATTERIE)
        quantites = {li.designation: int(li.quantite) for li in lignes}
        self.assertEqual(quantites['Panneau Jinko 550W'], 10)
        self.assertIn('Batterie Dyness 10 kWh', quantites)
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', quantites)
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', quantites)
        self.assertIn('Transport', quantites)

    def test_lacceptation_ne_touche_ni_statut_ni_lignes(self):
        """L'acceptation ENREGISTRE le choix ; c'est le filtre aval qui s'en
        sert. La chaîne de statuts reste celle d'hier (règle #4)."""
        devis = self._devis_variante()
        devis.statut = Devis.Statut.ENVOYE
        devis.save(update_fields=['statut'])
        nb_lignes = devis.lignes.count()

        services.accept_devis(devis=devis, user=self.user, nom='Client',
                              option=SANS_BATTERIE)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.option_acceptee, SANS_BATTERIE)
        self.assertEqual(devis.lignes.count(), nb_lignes)
        self.assertEqual(
            {int(li.quantite) for li in option_lines(devis)
             if li.designation == 'Panneau Jinko 550W'}, {8})

    def test_le_filtre_pur_reste_celui_dhier_sur_une_ligne_commune(self):
        """Non-régression : une ligne SANS variante (toutes celles d'hier)
        reste classée par les MOTS-CLÉS, mot pour mot."""
        class _Ligne:
            def __init__(self, designation, variante=''):
                self.designation = designation
                self.variante = variante
                self.produit = None

        lignes = [_Ligne('Panneau Jinko 550W'),
                  _Ligne('Batterie Dyness 10 kWh'),
                  _Ligne('Onduleur hybride Deye 5kW'),
                  _Ligne('Onduleur réseau Huawei 5kW')]
        sans = [li.designation
                for li in filter_lines_for_option(lignes, SANS_BATTERIE)]
        avec = [li.designation
                for li in filter_lines_for_option(lignes, AVEC_BATTERIE)]
        self.assertEqual(sans, ['Panneau Jinko 550W',
                                'Onduleur réseau Huawei 5kW'])
        self.assertEqual(avec, ['Panneau Jinko 550W',
                                'Batterie Dyness 10 kWh',
                                'Onduleur hybride Deye 5kW'])
        # Sans option : rien n'est filtré, comme avant.
        self.assertEqual(len(filter_lines_for_option(lignes, '')), 4)

    def test_f14_une_ligne_declaree_contredisant_les_mots_cles_reste_dans_son_panier(self):
        """F14 — une ligne DÉCLARÉE ('sans'/'avec') tranche SEULE, même quand
        les mots-clés la contrediraient. Une batterie taguée 'sans' (résidu de
        composition, ou correction manuelle du vendeur) doit rester dans le
        panier « sans » : c'est exactement ce que rend le PDF
        (``builder._repartir_options``, la déclaration prime) — écran et PDF
        doivent facturer la MÊME chose, jamais l'écran qui l'oublie."""
        class _Ligne:
            def __init__(self, designation, variante):
                self.designation = designation
                self.variante = variante
                self.produit = None

        lignes = [_Ligne('Panneau Jinko 550W', ''),
                  _Ligne('Batterie Dyness 10 kWh', 'sans'),
                  _Ligne('Onduleur hybride Deye 5kW', 'avec'),
                  _Ligne('Onduleur réseau Huawei 5kW', 'avec')]
        sans = [li.designation
                for li in filter_lines_for_option(lignes, SANS_BATTERIE)]
        avec = [li.designation
                for li in filter_lines_for_option(lignes, AVEC_BATTERIE)]
        # La batterie déclarée 'sans' PART dans le panier sans (contrat F14),
        # et jamais dans le panier avec malgré son mot-clé.
        self.assertIn('Batterie Dyness 10 kWh', sans)
        self.assertNotIn('Batterie Dyness 10 kWh', avec)
        # L'onduleur réseau déclaré 'avec' reste dans le panier avec malgré
        # son mot-clé (symétrique).
        self.assertIn('Onduleur réseau Huawei 5kW', avec)
        self.assertNotIn('Onduleur réseau Huawei 5kW', sans)


# ═══════════════════════════════════════════════════════════════════════════
# 5. L'ÉTUDE DE DIMENSIONNEMENT NE PEUT RIEN CASSER
# ═══════════════════════════════════════════════════════════════════════════
class LEtudeDeDimensionnementResteInoffensive(_Base):
    slug = 'l2opt-etude'

    def test_rafraichir_dimensionnement_ne_leve_jamais_et_ne_touche_rien(self):
        """``rafraichir_dimensionnement_devis`` porte ``recommandation`` ET
        ``recommandation_avec`` dans ``etude_params`` — et RIEN d'autre : ni
        statut, ni ligne, ni total, même quand le moteur explose."""
        # Un lead FACTURÉ : sans lui le profil serait vide et l'étude
        # s'arrêterait AVANT le moteur — le test ne prouverait plus rien.
        lead = self._lead(email='etude@example.com',
                          facture_hiver=Decimal('1200'))
        devis = Devis.objects.create(
            company=self.company, reference='DEV-L2OPT-ETUDE',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ENVOYE, created_by=self.user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL)
        produit = self.produits['PAN550']
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal('8'), prix_unitaire=Decimal('1100'))
        avant = (devis.statut, devis.lignes.count(), devis.total_ttc,
                 devis.etude_params)

        with patch('apps.ventes.dimensionnement.recommander_taille',
                   side_effect=RuntimeError('moteur en panne')):
            self.assertIsNone(
                services.rafraichir_dimensionnement_devis(devis, force=True))

        devis.refresh_from_db()
        self.assertEqual(
            (devis.statut, devis.lignes.count(), devis.total_ttc,
             devis.etude_params), avant)


# ═══════════════════════════════════════════════════════════════════════════
# 6. LA DOCTRINE D'OPTIMUM (25/08/2026)
# ═══════════════════════════════════════════════════════════════════════════
def _ligne_tableau(panneaux, cout, economie, couverture, paliers=None):
    """Une ligne de tableau FABRIQUÉE — la forme que rend ``balayer_tailles``.

    Les tableaux de ces tests sont synthétiques À DESSEIN : ils épinglent la
    RÈGLE (quel pas est admis, jusqu'où on monte), pas les chiffres du
    catalogue. Les chiffres RÉELS du moteur sont épinglés, eux, par
    ``test_dimensionnement_exemples`` sur le catalogue semé.
    """
    payback = dimensionnement._payback(cout, economie)
    return {
        'panneaux': panneaux, 'kwc': round(panneaux * 0.55, 3),
        'composable': True,
        'payback_sans_annees': None if payback is None else round(payback, 2),
        'cout_sans_ttc': cout, 'economie_sans_mad': economie,
        'couverture_sans': couverture,
        'verdicts_bloquants_sans': [], 'verdicts_bloquants_avec': [],
        'batterie_disponible': bool(paliers),
        'payback_avec_annees': (paliers[0]['payback_annees']
                                if paliers else None),
        'residuel_kwh_mois': 400.0,
        'batterie_kwh': paliers[0]['capacite_kwh'] if paliers else 0.0,
        'balayage_stockage': list(paliers or []),
    }


def _palier_tableau(capacite, cout, economie, residuel):
    """Un palier de ``balayage_stockage`` FABRIQUÉ."""
    payback = dimensionnement._payback(cout, economie)
    return {
        'capacite_kwh': capacite, 'cout_ttc': cout, 'economie_mad': economie,
        'payback_annees': None if payback is None else round(payback, 2),
        'residuel_kwh_mois': residuel, 'tranche_apres': {'libelle': 'T'},
        'couverture': 0.7, 'taux_autoconso': 0.6,
        'remplissage': {'moyen': 1.0, 'pire_mois': {'ratio': 1.0}},
        'lignes': [], 'lignes_batterie': [],
    }


class LaDoctrineDOptimum(SimpleTestCase):
    """« L'optimum = celui qui réduit la facture le PLUS, avec un ROI
    raisonnable — pas seulement le meilleur payback. »

    LE MEILLEUR PAYBACK EST DEVENU LE POINT DE DÉPART, PLUS LE POINT
    D'ARRIVÉE : on monte tant que chaque dirham ajouté se rembourse dans la vie
    de ce qu'il achète — dix ans pour des panneaux, sept pour du stockage.

    Tous les écarts de payback de ces fixtures sont VOLONTAIREMENT supérieurs à
    ``EGALITE_PAYBACK_ANNEES`` : sinon c'est le départage historique (« à
    égalité, meilleure couverture ») qui choisirait, et ces tests ne
    prouveraient rien de la montée.
    """

    #: 8 panneaux = LE MEILLEUR PAYBACK (5,00 ans) — l'ancien choix.
    #: 9 panneaux : pas marginal 9 000 / 1 000 =  9,0 ans ≤ 10 → ADMIS.
    #: 10 panneaux : pas marginal 8 000 /   500 = 16,0 ans > 10 → REFUSÉ.
    TABLEAU = None

    def setUp(self):
        self.TABLEAU = [
            _ligne_tableau(8, 40000, 8000, 0.50),
            _ligne_tableau(9, 49000, 9000, 0.56),
            _ligne_tableau(10, 57000, 9500, 0.60),
        ]

    def test_les_deux_horizons_sont_ceux_de_la_duree_de_vie(self):
        """Le stockage vit moins longtemps que les panneaux, donc son dirham a
        moins de temps pour se rembourser : son seuil est le plus STRICT."""
        self.assertEqual(dimensionnement.HORIZON_MARGINAL_PV, 10)
        self.assertEqual(dimensionnement.HORIZON_MARGINAL_BATTERIE, 7)
        self.assertLess(dimensionnement.HORIZON_MARGINAL_BATTERIE,
                        dimensionnement.HORIZON_MARGINAL_PV)

    def test_un_pas_qui_ne_rapporte_rien_n_a_pas_de_prix(self):
        """« L'optimum s'arrête quand des panneaux en plus n'apportent que des
        gains négligeables » : aucun seuil de « négligeable » n'est inventé —
        un pas qui coûte sans rapporter n'a tout simplement PAS de ratio."""
        ratio = dimensionnement.ratio_pas_marginal
        self.assertEqual(ratio(100, 10, 200, 20), 10.0)
        self.assertIsNone(ratio(100, 10, 200, 10))   # coûte, ne rapporte rien
        self.assertIsNone(ratio(100, 10, 90, 8))     # moins cher ET moins bon
        self.assertEqual(ratio(100, 10, 90, 12), 0.0)  # gratuit et meilleur

    def test_la_montee_prend_la_plus_grande_taille_dont_chaque_pas_tient(self):
        """PIN DÉPLACÉ (25/08/2026) — ANCIEN : 8 panneaux (meilleur payback pur,
        5,00 ans). NOUVEAU : 9 panneaux (payback global 5,44 ans), parce que le
        9ᵉ panneau se rembourse en 9,0 ans, sous l'horizon de 10 ans. Le 10ᵉ,
        lui, mettrait 16,0 ans : la montée s'arrête là."""
        ancien = min(self.TABLEAU, key=lambda x: x['payback_sans_annees'])
        self.assertEqual(ancien['panneaux'], 8)

        reco, motivation = dimensionnement.choisir_recommandation(self.TABLEAU)
        self.assertEqual(reco['panneaux'], 9)
        self.assertEqual(reco['payback_sans_annees'], 5.44)
        self.assertIn('9.0', motivation)
        self.assertIn('10 ans', motivation)

    def test_le_payback_global_reste_sous_l_horizon(self):
        """LA PROPRIÉTÉ MATHÉMATIQUE, vérifiée plutôt qu'affirmée.

        Départ à 3,00 ans puis SIX pas marginaux à 9,50 ans chacun — tous
        admis. Si « chaque pas ≤ H » n'impliquait pas « payback global ≤ H »,
        la doctrine promettrait un ROI qu'elle ne tient pas. L'inégalité des
        médiants dit le contraire, et ce test le constate sur le vrai code.
        """
        tableau = [_ligne_tableau(8, 30000, 10000, 0.40)]
        cout, economie = 30000, 10000
        for rang in range(6):
            cout, economie = cout + 9500, economie + 1000
            tableau.append(_ligne_tableau(9 + rang, cout, economie,
                                          0.42 + 0.02 * rang))

        reco, _motivation = dimensionnement.choisir_recommandation(tableau)
        self.assertEqual(reco['panneaux'], 14, 'les six pas doivent passer')
        self.assertLessEqual(reco['payback_sans_annees'],
                             dimensionnement.HORIZON_MARGINAL_PV)
        # ... et il s'est bien DÉGRADÉ par rapport au départ : la doctrine
        # ACHÈTE de la réduction de facture avec du payback, elle ne prétend
        # pas faire mieux sur les deux tableaux à la fois.
        self.assertGreater(reco['payback_sans_annees'], 3.0)
        self.assertGreater(reco['economie_sans_mad'],
                           tableau[0]['economie_sans_mad'])

    def test_dossier_faible_retombe_sur_le_choix_pur_meilleur_payback(self):
        """GARDE DU DOSSIER FAIBLE : meilleur payback déjà au-delà de dix ans ⇒
        aucune montée. La nouvelle doctrine ne peut JAMAIS rendre un dossier
        plus mauvais qu'avant le 25/08."""
        self.assertFalse(dimensionnement.depart_dans_horizon(10.5))
        self.assertTrue(dimensionnement.depart_dans_horizon(10.0))
        self.assertFalse(dimensionnement.depart_dans_horizon(None))
        self.assertFalse(dimensionnement.depart_dans_horizon(0))

        faible = [_ligne_tableau(8, 100000, 8000, 0.50),
                  _ligne_tableau(9, 115000, 8400, 0.56)]
        reco, motivation = dimensionnement.choisir_recommandation(faible)
        self.assertEqual(reco['panneaux'], 8)
        self.assertEqual(reco, min(faible,
                                   key=lambda x: x['payback_sans_annees']))
        self.assertIn('10 ans', motivation)

    def test_horizon_ramene_au_meilleur_payback_reproduit_l_ancien_choix(self):
        """LE BOUTON EST BIEN LE BOUTON : ramener l'horizon au meilleur payback
        du dossier redonne, à la ligne près, le choix pur d'avant le 25/08."""
        with patch.object(dimensionnement, 'HORIZON_MARGINAL_PV', 5.0), \
                patch.object(dimensionnement,
                             'HORIZON_MARGINAL_BATTERIE', 5.0):
            reco, _motivation = dimensionnement.choisir_recommandation(
                self.TABLEAU)
        self.assertEqual(reco['panneaux'], 8)
        self.assertEqual(reco, min(self.TABLEAU,
                                   key=lambda x: x['payback_sans_annees']))

    # ── LA GRILLE CONJOINTE champ × stockage ────────────────────────────────
    def test_un_pas_de_stockage_est_juge_a_sept_ans(self):
        """5 → 10 kWh coûte 6,0 ans : ADMIS (≤ 7). 10 → 15 kWh en coûte 9,0 :
        REFUSÉ — et c'est bien le seuil BATTERIE qui l'arrête, puisque 9,0 ans
        passerait sans problème l'horizon de dix ans des panneaux."""
        grille = [_ligne_tableau(
            8, 20000, 8000, 0.50,
            paliers=[_palier_tableau(5.0, 30000, 10000, 320.0),
                     _palier_tableau(10.0, 42000, 12000, 260.0),
                     _palier_tableau(15.0, 51000, 13000, 230.0)])]
        reco, motivation = dimensionnement.choisir_recommandation_avec(grille)
        self.assertEqual(reco['batterie_kwh'], 10.0)
        self.assertEqual(reco['payback_avec_annees'], 3.5)
        self.assertIn('7 ans', motivation)
        self.assertLessEqual(reco['payback_avec_annees'],
                             dimensionnement.HORIZON_MARGINAL_PV)

    def test_un_pas_de_champ_est_juge_a_dix_ans(self):
        """Le MÊME pas de 9,0 ans, mais qui achète des PANNEAUX, est admis."""
        grille = [
            _ligne_tableau(8, 20000, 8000, 0.50,
                           paliers=[_palier_tableau(5.0, 30000, 10000, 320.0)]),
            _ligne_tableau(10, 26000, 9000, 0.60,
                           paliers=[_palier_tableau(5.0, 39000, 11000, 250.0)]),
        ]
        reco, motivation = dimensionnement.choisir_recommandation_avec(grille)
        self.assertEqual((reco['panneaux'], reco['batterie_kwh']), (10, 5.0))
        self.assertIn('10 ans', motivation)

    def test_un_pas_mixte_est_juge_au_seuil_du_stockage(self):
        """Un pas qui monte les DEUX dimensions n'est pas décomposable ici : il
        est jugé au seuil de son composant DOMINANT, le stockage (sept ans)."""
        courant = {'panneaux': 8, 'capacite_kwh': 5.0}
        self.assertEqual(
            dimensionnement.horizon_du_pas(
                courant, {'panneaux': 8, 'capacite_kwh': 10.0}),
            dimensionnement.HORIZON_MARGINAL_BATTERIE)
        self.assertEqual(
            dimensionnement.horizon_du_pas(
                courant, {'panneaux': 10, 'capacite_kwh': 5.0}),
            dimensionnement.HORIZON_MARGINAL_PV)
        self.assertEqual(
            dimensionnement.horizon_du_pas(
                courant, {'panneaux': 10, 'capacite_kwh': 10.0}),
            dimensionnement.HORIZON_MARGINAL_BATTERIE)

    def test_la_ligne_du_tableau_n_est_jamais_mutee(self):
        """``recommandation_avec`` rend une COPIE : la même ligne sert aussi la
        recommandation SANS batterie et reste dans ``tableau``, où le rapport
        l'imprime. La muter ferait afficher au tableau un stockage qu'il n'a
        pas évalué pour cette taille."""
        grille = [_ligne_tableau(
            8, 20000, 8000, 0.50,
            paliers=[_palier_tableau(5.0, 30000, 10000, 320.0),
                     _palier_tableau(10.0, 42000, 12000, 260.0)])]
        avant = dict(grille[0])
        reco, _motivation = dimensionnement.choisir_recommandation_avec(grille)
        self.assertEqual(reco['batterie_kwh'], 10.0)
        self.assertEqual(grille[0], avant)
        self.assertEqual(grille[0]['batterie_kwh'], 5.0)
        # La copie porte bien les colonnes « avec » du palier RETENU.
        self.assertEqual(reco['cout_avec_ttc'], 42000)
        self.assertEqual(reco['economie_avec_mad'], 12000)
        self.assertEqual(reco['residuel_kwh_mois'], 260.0)

    def test_grille_vide_ne_recommande_rien_et_le_dit(self):
        """Aucun point livrable ⇒ ``None`` + un motif en français, jamais une
        configuration inventée pour ne pas laisser l'écran vide."""
        reco, motivation = dimensionnement.choisir_recommandation_avec([])
        self.assertIsNone(reco)
        self.assertIn('aucune configuration', motivation)


# ═══════════════════════════════════════════════════════════════════════════
# 7. L'ÉCHELLE DE PALIERS BATTERIE
# ═══════════════════════════════════════════════════════════════════════════
#: Le CONTRAT, mot pour mot (PACT10) : la lane qui sert cette échelle à l'écran
#: code contre CES clés, ni plus ni moins.
CLES_PALIER_ECHELLE = {
    'capacite_kwh', 'nb_batteries_5', 'nb_batteries_10', 'nb_panneaux',
    'puissance_kwc', 'prix_ttc', 'economies_annuelles', 'payback_annees',
    'remplissage_ok', 'retenu',
}


class LEchelleDePaliersBatterie(_Base):
    """« more than just 2 batteries in the web page battery option ; extra
    batteries might add extra panels with extra cost, that is still fine »
    (fondateur, 25/08/2026).

    LA RÈGLE DU 24/08 EST RETOURNÉE, PAS ABANDONNÉE : « batteries toujours
    pleines » ne REJETTE plus un palier trop gros pour le champ — elle TIRE les
    panneaux nécessaires pour le charger.
    """

    slug = 'l2opt-echelle'

    def _devis_residentiel(self, *, email, occupation_jour=None,
                           facture_hiver=1200, roof_layout=None):
        lead = self._lead(email=email, ville='Casablanca',
                          facture_hiver=Decimal(str(facture_hiver)),
                          ete_differente=False,
                          **({'occupation_jour': occupation_jour}
                             if occupation_jour else {}))
        return Devis.objects.create(
            company=self.company, reference='DEV-ECH-%s' % email.split('@')[0],
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=self.user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            roof_layout=roof_layout, etude_params={})

    def test_le_contrat_la_monotonie_et_le_palier_retenu(self):
        """UN SEUL balayage pour les trois garanties structurelles (le calcul
        coûte douze jours types par taille de champ sondée)."""
        devis = self._devis_residentiel(email='echelle@example.com')
        # Le bloc de dimensionnement d'abord : il fixe les MÊMES entrées que
        # l'échelle (jamais un second calcul sur d'autres hypothèses). Il ne
        # décide en revanche PLUS du palier marqué « retenu » — voir plus bas.
        bloc = services.rafraichir_dimensionnement_devis(devis, force=True)
        self.assertIsNotNone(bloc, 'profil non exploitable : le test ne '
                                   'prouverait plus rien')

        # Finding #5b (revue critique 25/08/2026) — « Retenu pour ce devis »
        # doit suivre les LIGNES RÉELLEMENT VENDUES, pas l'optimum du moteur :
        # le générateur pose les lignes sur un champ ARRONDI (``autoFillLines``
        # cible ``round(kwc/5)×5``), si bien que les deux capacités divergent
        # régulièrement — la pilule affichait alors le prix d'une AUTRE
        # capacité que celle du devis. On vend donc ici UNE batterie de 10 kWh
        # (9,22 kWh UTILES d'après sa fiche technique, cf. le catalogue de
        # cette classe) et c'est CETTE capacité que le marquage doit désigner.
        LigneDevis.objects.create(
            devis=devis, produit=self.produits['BAT10'],
            designation='Batterie Dyness 10 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('30000'))

        echelle = dimensionnement.echelle_paliers_batterie(devis)
        self.assertIsInstance(echelle, list)
        self.assertTrue(
            echelle,
            'aucun palier de batterie dérivable sur un profil pourtant '
            'exploitable — l\'écran batterie serait vide')

        for palier in echelle:
            self.assertEqual(set(palier), CLES_PALIER_ECHELLE, palier)
            self.assertGreater(palier['capacite_kwh'], 0, palier)
            self.assertGreater(palier['nb_panneaux'], 0, palier)
            self.assertGreater(palier['prix_ttc'], 0, palier)
            self.assertIsInstance(palier['nb_batteries_5'], int)
            self.assertIsInstance(palier['nb_batteries_10'], int)
            self.assertIsInstance(palier['remplissage_ok'], bool)
            self.assertIsInstance(palier['retenu'], bool)
            # Règle #4 : aucun prix d'achat, aucune marge ne fuit ici.
            self.assertNotIn('prix_achat', palier)
            self.assertNotIn('marge', palier)

        capacites = [p['capacite_kwh'] for p in echelle]
        self.assertEqual(capacites, sorted(set(capacites)),
                         'les paliers ne montent pas strictement : %s'
                         % capacites)
        # Plus de batteries ⇒ jamais MOINS de panneaux (le champ est tiré par
        # la banque à charger).
        panneaux = [p['nb_panneaux'] for p in echelle]
        for avant, apres in zip(panneaux, panneaux[1:]):
            self.assertGreaterEqual(
                apres, avant,
                'le champ DIMINUE quand la banque grandit : %s' % panneaux)
        # ``remplissage_ok=False`` ne peut être que le DERNIER palier.
        for palier in echelle[:-1]:
            self.assertTrue(palier['remplissage_ok'], palier)

        # ── Finding #5b — le marquage suit les LIGNES, jamais le moteur ──────
        vendue = dimensionnement.capacite_batterie_des_lignes(devis)
        self.assertIsNotNone(
            vendue, 'la ligne batterie vendue doit être lue : sans elle le '
                    'test ne prouverait plus rien')
        self.assertGreater(vendue, 0)

        retenus = [p for p in echelle if p['retenu']]
        correspond = [p for p in echelle
                      if abs(p['capacite_kwh'] - vendue) < 0.05]
        # L'INVARIANT, sans condition : un palier est marqué SI ET SEULEMENT SI
        # l'échelle propose EXACTEMENT la capacité vendue — jamais un marquage
        # approché (le prix affiché serait celui d'un autre kit), jamais deux.
        self.assertEqual(
            bool(retenus), bool(correspond),
            'marquage et capacité vendue (%s kWh) divergent : %s'
            % (vendue, capacites))
        self.assertLessEqual(len(retenus), 1, capacites)
        for palier in retenus:
            self.assertAlmostEqual(palier['capacite_kwh'], vendue, places=1)

    def test_bathomo_devis_a_5_kwh_echelle_denominee_en_5_kwh_seulement(self):
        """BATHOMO (fondateur 26/08/2026) — « if the quote has 5 kWh
        batteries the web page should only show 5 kWh batteries ». Ce devis
        vend une ligne 5 kWh ; le catalogue de cette classe porte AUSSI le
        10 kWh (en stock) — sans le pin, certains rangs choisiraient le
        10 kWh (économie/tie-break). Avec le pin, TOUS les rangs restent en
        modules 5 kWh, jusqu'à ce que le champ (ou le toit) arrête
        l'échelle."""
        devis = self._devis_residentiel(email='pin5-ech@example.com')
        LigneDevis.objects.create(
            devis=devis, produit=self.produits['BAT5'],
            designation='Batterie Dyness 5 kWh',
            quantite=Decimal('1'), prix_unitaire=Decimal('16000'))

        self.assertEqual(dimensionnement.module_batterie_du_devis(devis), 5.0)

        echelle = dimensionnement.echelle_paliers_batterie(devis)
        self.assertTrue(echelle, 'échelle vide : le test ne prouverait rien')
        for palier in echelle:
            self.assertEqual(
                palier['nb_batteries_10'], 0,
                'un rang de l\'échelle a basculé vers le 10 kWh alors que '
                'ce devis vend du 5 kWh : %s' % palier)
            self.assertGreater(palier['nb_batteries_5'], 0, palier)

    def test_bathomo_10_kwh_a_stock_zero_jamais_laddere(self):
        """BATHOMO — LE bug réel : ``BAT-DEY-10`` à 0 en stock (aucune ligne
        vendue sur ce devis, donc aucun pin) ne doit JAMAIS apparaître dans
        l'échelle — même garde que la composition (``_batterie_en_stock``),
        héritée automatiquement puisque le balayage compose CHAQUE rang par
        ``composition_residentielle``."""
        Produit.objects.filter(pk=self.produits['BAT10'].pk).update(
            quantite_stock=0)
        devis = self._devis_residentiel(email='stock0-ech@example.com')
        echelle = dimensionnement.echelle_paliers_batterie(devis)
        self.assertTrue(echelle, 'échelle vide : le test ne prouverait rien')
        for palier in echelle:
            self.assertEqual(
                palier['nb_batteries_10'], 0,
                'un rang propose du 10 kWh alors que son stock est à 0 : %s'
                % palier)
            self.assertGreater(palier['nb_batteries_5'], 0, palier)

    def test_le_plafond_du_toit_borne_chaque_palier(self):
        """Le calepinage est un PLAFOND PHYSIQUE : l'échelle ne propose jamais
        des panneaux qui ne tiennent pas, et un toit plus petit ne peut que
        RESTREINDRE la liste — jamais l'allonger."""
        sans_toit = self._devis_residentiel(email='sanstoit@example.com')
        libre = dimensionnement.echelle_paliers_batterie(sans_toit)

        plafond = 6
        avec_toit = self._devis_residentiel(
            email='avectoit@example.com',
            roof_layout={'scenario': 'reseau', 'panelWatt': 550,
                         'result': {'panels': plafond,
                                    'kwc': round(plafond * 550 / 1000.0, 3)}})
        self.assertEqual(dimensionnement.plafond_toit_du_devis(avec_toit),
                         plafond)
        borne = dimensionnement.echelle_paliers_batterie(avec_toit)

        for palier in borne:
            self.assertLessEqual(
                palier['nb_panneaux'], plafond,
                'un palier propose %d panneaux sur un toit qui en porte %d'
                % (palier['nb_panneaux'], plafond))
        self.assertLessEqual(
            len(borne), len(libre),
            'le plafond du toit a ALLONGÉ l\'échelle : %s vs %s'
            % ([p['capacite_kwh'] for p in borne],
               [p['capacite_kwh'] for p in libre]))

    def test_le_profil_absent_reclame_moins_de_panneaux_pour_la_meme_banque(
            self):
        """CONSÉQUENCE PRÉDITE PAR LE FONDATEUR — un foyer ABSENT en journée
        autoconsomme moins directement, donc son surplus quotidien est PLUS
        GROS à champ égal, donc la même banque se remplit avec MOINS de
        panneaux. Son échelle est mécaniquement plus généreuse.

        Les deux profils ont la MÊME facture : seule l'occupation change.
        """
        present = self._devis_residentiel(email='present-ech@example.com',
                                          occupation_jour='present')
        absent = self._devis_residentiel(email='absent-ech@example.com',
                                         occupation_jour='absent')
        ech_present = dimensionnement.echelle_paliers_batterie(present)
        ech_absent = dimensionnement.echelle_paliers_batterie(absent)
        self.assertTrue(ech_present and ech_absent,
                        'échelle vide : le test ne prouverait rien')

        print('')
        print('ECHELLE BATTERIE — present vs absent (meme facture)')
        for titre, echelle in (('present', ech_present),
                               ('absent ', ech_absent)):
            print('  %s : %s' % (titre, ', '.join(
                '%s kWh -> %d pan.' % (p['capacite_kwh'], p['nb_panneaux'])
                for p in echelle)))

        par_capacite_present = {p['capacite_kwh']: p['nb_panneaux']
                                for p in ech_present}
        communes = [p for p in ech_absent
                    if p['capacite_kwh'] in par_capacite_present]
        self.assertTrue(communes, 'aucune capacité commune à comparer')
        for palier in communes:
            self.assertLessEqual(
                palier['nb_panneaux'],
                par_capacite_present[palier['capacite_kwh']],
                'à %s kWh, le profil ABSENT réclame plus de panneaux que le '
                'profil PRÉSENT — le surplus ne serait plus le sien'
                % palier['capacite_kwh'])
        self.assertGreaterEqual(
            len(ech_absent), len(ech_present),
            'l\'échelle du profil absent doit être au moins aussi généreuse')

    def test_un_devis_non_residentiel_ou_sans_facture_rend_une_liste_vide(self):
        """Rien de dérivable ⇒ liste VIDE, jamais un chiffre inventé pour
        remplir l'écran."""
        agricole = self._devis_residentiel(email='agricole-ech@example.com')
        agricole.mode_installation = Devis.ModeInstallation.AGRICOLE
        agricole.save(update_fields=['mode_installation'])
        self.assertEqual(dimensionnement.echelle_paliers_batterie(agricole), [])

        sans_facture = Devis.objects.create(
            company=self.company, reference='DEV-ECH-VIDE',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params={})
        self.assertEqual(
            dimensionnement.echelle_paliers_batterie(sans_facture), [])

    def test_le_moteur_en_panne_rend_une_liste_vide_sans_lever(self):
        """Un aperçu ne casse jamais un écran (et n'écrit rien)."""
        devis = self._devis_residentiel(email='panne-ech@example.com')
        with patch('apps.ventes.dimensionnement._echelle_paliers_batterie',
                   side_effect=RuntimeError('moteur en panne')):
            self.assertEqual(
                dimensionnement.echelle_paliers_batterie(devis), [])
