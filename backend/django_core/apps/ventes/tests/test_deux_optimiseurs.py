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
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import services
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
        self.assertEqual(cible['scenario'], 'avec_batterie')


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
