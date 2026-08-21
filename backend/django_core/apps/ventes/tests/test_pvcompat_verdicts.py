# -*- coding: utf-8 -*-
"""PVCOMPAT (fondateur 20/08/2026) — la compatibilité deux à deux du stock.

Ce que ces tests ARMENT, dans l'ordre où ça compte :

1. **La sévérité est celle du NOYAU, pas une règle maison.** Les DEUX bornes de
   courant d'entrée MPPT de ``core.electrique.chaines`` n'ont pas la même
   gravité, et c'est la FICHE qui tranche (DEV-202608-0016) : l'**Imp** cumulé
   au-dessus du courant admissible fait ÉCRÊTER (alerte → ``reserve``), l'**Isc**
   cumulé au-dessus de la borne de court-circuit PUBLIÉE sort de la
   spécification constructeur (bloquant → ``incompatible``). Des tests le
   prouvent depuis le noyau lui-même, sur le MÊME onduleur réel, pour qu'une
   dérive de ce module devienne rouge au lieu de mentir dans un sens ou l'autre.
2. **Une fiche incomplète rend « inconnu », jamais un faux OK.**
3. **La forme rendue est celle du contrat COMMITTÉ**
   ``apps/stock/contract_samples/produit_compatibilites.json`` — comparée AU
   FICHIER, jamais à une liste retapée (PACT10).
4. **La composition ne meurt jamais** : un couple panneau/onduleur incompatible
   fait chercher un autre panneau, et à défaut GARDE le choix en l'ANNONÇANT.
5. **Sans raccordement déclaré, RIEN ne bouge** — la composition est
   byte-identique à celle d'avant ce lot (épinglée).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pvcompat_verdicts -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes import compatibilites as cp
from apps.ventes import services as sv
from apps.ventes import solar_design as sd

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent.parent / 'stock'
     / 'contract_samples' / 'produit_compatibilites.json'
     ).read_text(encoding='utf-8'))
CLES_RACINE = set(CONTRAT['exemple'])
CLES_BILAN = set(CONTRAT['exemple']['bilan'])
CLES_COMPOSITION = set(CONTRAT['exemple']['bilan']['composition'][0])
CLES_FAMILLE = set(CONTRAT['exemple']['familles'][0])
CLES_PRODUIT_LISTE = set(CONTRAT['exemple']['familles'][0]['produits'][0])
CLES_ENTETE = set(CONTRAT['exemple']['produit'])


# ── Faux produits (mêmes stubs que test_pv41 : le calcul ne fait que des
# ``getattr``, aucune base n'est nécessaire). Les fiches portent TOUS leurs
# champs — ``specs_for_produit`` y accède directement, comme sur un vrai
# modèle. ────────────────────────────────────────────────────────────────────
CHAMPS_FICHE = {
    'module': ('vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc',
               'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
               'longueur_mm', 'largeur_mm'),
    'onduleur': ('ond_n_mppt', 'ond_mppt_v_min', 'ond_mppt_v_max',
                 'ond_v_max_abs', 'ond_i_max_mppt_a', 'ond_ac_kw',
                 'ond_phases', 'ond_rendement_euro_pct', 'ond_v_demarrage_v',
                 'ond_isc_max_mppt_a', 'ond_bat_aucune', 'ond_bat_v_min',
                 'ond_bat_v_max'),
    'batterie': ('bat_kwh_nominal', 'bat_kwh_usable', 'bat_dod_pct',
                 'bat_v_nominal', 'bat_max_charge_kw'),
}


class _FausseFiche:
    def __init__(self, type_fiche, **champs):
        self.type_fiche = type_fiche
        for cle in CHAMPS_FICHE[type_fiche]:
            setattr(self, cle, None)
        if type_fiche == 'onduleur':
            self.ond_bat_aucune = False
        for cle, valeur in champs.items():
            setattr(self, cle, valeur)


class _FauxProduit:
    def __init__(self, pk, nom, fiche=None, prix_vente='1000',
                 garantie='5 ans', marque='', description=''):
        self.id = pk
        self.pk = pk
        self.nom = nom
        self.fiche_technique = fiche
        self.prix_vente = Decimal(str(prix_vente))
        self.garantie = garantie
        self.marque = marque
        self.description = description


def _panneau_710(pk=3, nom='Panneau Canadien Solar 710W'):
    """CS7N-710 — valeurs de la fiche constructeur SEEDÉE (Isc 18,59 A)."""
    return _FauxProduit(pk, nom, prix_vente='1500', fiche=_FausseFiche(
        'module', pmax_wc=Decimal('710.00'), voc_v=Decimal('48.30'),
        vmp_v=Decimal('40.40'), isc_a=Decimal('18.59'), imp_a=Decimal('17.59'),
        temp_coeff_voc_pct_c=Decimal('-0.250'),
        temp_coeff_pmax_pct_c=Decimal('-0.290'),
        longueur_mm=2384, largeur_mm=1303))


def _panneau_400(pk=5, nom='Panneau Jinko 400W'):
    """Petit module : deux fois moins de courant, chaînes plus courtes."""
    return _FauxProduit(pk, nom, prix_vente='900', fiche=_FausseFiche(
        'module', pmax_wc=Decimal('400.00'), voc_v=Decimal('37.00'),
        vmp_v=Decimal('31.00'), isc_a=Decimal('11.20'), imp_a=Decimal('10.60'),
        temp_coeff_voc_pct_c=Decimal('-0.270'),
        temp_coeff_pmax_pct_c=Decimal('-0.350'),
        longueur_mm=1722, largeur_mm=1134))


def _onduleur(pk, nom, **surcharges):
    """Onduleur au CONTRAT COMPLET — Deye SG05LP3 triphasé 10 kW par défaut.

    CORRECTION FONDATEUR (21/08/2026) : le parc Deye triphasé du catalogue
    (10T / 15T / 20T) est en BASSE TENSION SG05LP3 — fenêtre 160-650 V, 800 V
    absolus, PLAGE BATTERIE 40-60 V (les Dyness 51,2 V s'y accrochent). Un
    « SG01HP3 haute tension » avait été supposé par une recherche, jamais
    confirmé : aucun montage de test ne doit plus l'encoder.
    """
    champs = dict(
        ond_ac_kw=Decimal('10.00'), ond_phases=3, ond_n_mppt=2,
        ond_mppt_v_min=Decimal('160.0'), ond_mppt_v_max=Decimal('650.0'),
        ond_v_max_abs=Decimal('800.0'), ond_i_max_mppt_a=Decimal('26.0'),
        ond_rendement_euro_pct=Decimal('97.0'),
        ond_v_demarrage_v=Decimal('160.0'),
        ond_isc_max_mppt_a=Decimal('39.0'),
        ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))
    champs.update(surcharges)
    return _FauxProduit(pk, nom, prix_vente='30000',
                        fiche=_FausseFiche('onduleur', **champs))


def _onduleur_haute_tension_fictif(pk=99):
    """Onduleur HAUTE TENSION **fictif** — plage batterie 160-700 V.

    Aucune référence du catalogue n'est haute tension (correction fondateur du
    21/08/2026) : ce montage est donc DÉLIBÉRÉMENT anonyme et déclare sa plage
    en clair. Il n'existe que pour prouver qu'une batterie 51,2 V est REFUSÉE
    hors de la fenêtre — la règle, pas un produit réel.
    """
    return _onduleur(pk, 'Onduleur hybride HT fictif 10kW Triphasé',
                     ond_bat_v_min=Decimal('160.0'),
                     ond_bat_v_max=Decimal('700.0'))


def _onduleur_5k_mono(pk=12):
    """Deye SUN-5K-SG : les CHIFFRES du seeder — courant maxi par MPPT 13 A,
    Isc maxi 17 A, fenêtre 125-425 V, V_max 500 V. C'est LE cas du fondateur :
    une chaîne de CS7N-710 y apporte 17,59 A d'Imp et 18,59 A d'Isc."""
    return _onduleur(
        pk, 'Onduleur hybride Deye 5kW Monophasé',
        ond_ac_kw=Decimal('5.00'), ond_phases=1,
        ond_mppt_v_min=Decimal('125.0'), ond_mppt_v_max=Decimal('425.0'),
        ond_v_max_abs=Decimal('500.0'), ond_i_max_mppt_a=Decimal('13.0'),
        ond_v_demarrage_v=Decimal('125.0'),
        ond_isc_max_mppt_a=Decimal('17.0'),
        ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))


def _batterie(pk=7, nom='Batterie Dyness 10 kWh', v_nominal='51.2'):
    return _FauxProduit(pk, nom, prix_vente='30000', fiche=_FausseFiche(
        'batterie', bat_kwh_nominal=Decimal('10.00'),
        bat_v_nominal=(Decimal(v_nominal) if v_nominal is not None else None)))


# ═══════════════════════════════════════════════════════════════════════════
# 1. La SÉVÉRITÉ du noyau — le socle de tout le reste
# ═══════════════════════════════════════════════════════════════════════════
class SeveriteDuNoyauTest(SimpleTestCase):
    """Les DEUX bornes de courant, chacune à sa juste sévérité (DEV-202608-0016).

    C'est le noyau qui décide (``chaines._verdicts_courant``) ; ces tests
    l'interrogent DIRECTEMENT pour que la taxonomie de ce lot ne puisse pas
    dériver de la sienne. La ligne de partage est celle de la FICHE :

    * **Imp** au-dessus du courant d'entrée admissible = écrêtage. L'onduleur
      ne casse pas, il produit moins : ALERTE.
    * **Isc** au-dessus de la borne de court-circuit PUBLIÉE = la fiche
      constructeur n'autorise pas ce montage : BLOQUANT.

    Les deux cas ci-dessous tournent sur le MÊME onduleur réel (Deye 10 kW,
    26 A par entrée, 39 A d'Isc admissible) : seul le nombre de chaînes change.
    """

    def test_ecretage_sur_l_imp_est_une_alerte(self):
        """36 × 710 Wc = 2 chaînes par entrée : Imp 35,2 A > 26 A (écrêtage),
        mais Isc 37,2 A reste SOUS les 39 A publiés. Rien n'est bloqué."""
        module = sd.specs_module_pour_produit(_panneau_710())
        fenetre = sd.fenetre_onduleur_pour_produit(
            _onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
        verdicts = sd.verdicts_chaines(36, module=module, inverter=fenetre)
        self.assertTrue(verdicts['alertes_courant'],
                        'le noyau doit prononcer un verdict de courant')
        joint = ' '.join(verdicts['alertes_courant'])
        self.assertIn('MPPT', joint)
        self.assertIn('ÉCRÊTAGE', joint)
        self.assertEqual(verdicts['bloquants'], [])

    def test_isc_hors_borne_publiee_est_un_bloquant(self):
        """30 × 710 Wc = 3 chaînes par entrée : Isc 55,8 A > 39 A publiés —
        hors spécification matérielle, donc BLOQUANT."""
        module = sd.specs_module_pour_produit(_panneau_710())
        fenetre = sd.fenetre_onduleur_pour_produit(
            _onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
        verdicts = sd.verdicts_chaines(30, module=module, inverter=fenetre)
        self.assertTrue(verdicts['bloquants'])
        joint = ' '.join(verdicts['bloquants'])
        self.assertIn('55,8 A', joint)
        self.assertIn('39,0 A', joint)
        # Le verdict de courant reste LISIBLE dans la liste dédiée : le message
        # le plus grave ne doit pas être le seul à disparaître des warnings.
        self.assertTrue(any('Isc cumulé' in c
                            for c in verdicts['alertes_courant']))

    def test_string_design_publie_desormais_les_verdicts_de_courant(self):
        module = sd.specs_module_pour_produit(_panneau_710())
        fenetre = sd.fenetre_onduleur_pour_produit(_onduleur_5k_mono())
        design = sd.string_design(8, module=module, inverter=fenetre)
        self.assertTrue(
            any('MPPT' in w and ('Imp cumulé' in w or 'Isc cumulé' in w)
                for w in design['warnings']),
            design['warnings'])

    def test_sans_fiche_aucun_verdict_de_courant(self):
        """Fiches muettes ⇒ le noyau se tait : dégradé, jamais inventé."""
        verdicts = sd.verdicts_chaines(12)
        self.assertEqual(verdicts['alertes_courant'], [])
        self.assertEqual(sd.DEFAULT_MODULE['isc_a'], 0.0)
        self.assertEqual(sd.DEFAULT_MODULE['imp_a'], 0.0)
        self.assertEqual(sd.DEFAULT_INVERTER_WINDOW['i_max_mppt_a'], 0.0)
        self.assertIsNone(sd.DEFAULT_INVERTER_WINDOW['isc_max_mppt_a'])


# ═══════════════════════════════════════════════════════════════════════════
# 2. Les verdicts deux à deux
# ═══════════════════════════════════════════════════════════════════════════
class VerdictPanneauOnduleurTest(SimpleTestCase):
    def test_isc_hors_borne_donne_incompatible_avec_les_chiffres(self):
        """DEV-202608-0016 — LE couple du fondateur : 710 Wc sur Deye 5 kW.

        UNE chaîne apporte 18,59 A d'Isc dans une entrée que la fiche donne
        pour 17 A : aucun nombre de panneaux ne rend ce couple installable.
        Ce n'est donc pas « sous réserve » (ça écrête, ça marche), c'est
        INCOMPATIBLE — et c'est ce verdict que la resynchro 3D consulte
        désormais avant d'écrire quoi que ce soit.
        """
        verdict = cp.verdict_panneau_onduleur(
            _panneau_710(), _onduleur_5k_mono())
        self.assertEqual(verdict['statut'], cp.STATUT_INCOMPATIBLE)
        self.assertTrue(verdict['raisons'])
        joint = ' '.join(verdict['raisons'])
        # Les chiffres RÉELS des deux fiches, écrits à la française.
        self.assertIn('18,6 A', joint)
        self.assertIn('17,0 A', joint)
        # Aucune configuration n'est proposée : il n'y en a pas.
        self.assertIsNone(verdict['nb_panneaux'])
        self.assertEqual(verdict['detail'], '')

    def test_couple_sain_donne_compatible_sans_raison(self):
        verdict = cp.verdict_panneau_onduleur(
            _panneau_710(), _onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
        self.assertEqual(verdict['statut'], cp.STATUT_COMPATIBLE)
        self.assertEqual(verdict['raisons'], [])
        self.assertGreater(verdict['nb_panneaux'], 0)
        self.assertIn('Voc à froid', verdict['detail'])

    def test_fenetre_de_tension_impossible_donne_incompatible(self):
        # Fenêtre écrasée : aucune longueur ne tient à la fois sous la borne
        # haute à froid et au-dessus du démarrage à chaud → BLOQUANT du noyau.
        etroit = _onduleur(
            31, 'Onduleur réseau compact 3kW', ond_ac_kw=Decimal('3.00'),
            ond_phases=1, ond_mppt_v_min=Decimal('60.0'),
            ond_mppt_v_max=Decimal('60.0'), ond_v_max_abs=Decimal('60.0'),
            ond_v_demarrage_v=Decimal('60.0'),
            ond_i_max_mppt_a=Decimal('13.0'),
            ond_isc_max_mppt_a=Decimal('13.0'), ond_bat_aucune=True,
            ond_bat_v_min=None, ond_bat_v_max=None)
        verdict = cp.verdict_panneau_onduleur(_panneau_710(), etroit)
        self.assertEqual(verdict['statut'], cp.STATUT_INCOMPATIBLE)
        self.assertTrue(any('fenêtre de tension' in r
                            for r in verdict['raisons']), verdict['raisons'])

    def test_fiche_panneau_absente_donne_inconnu_motive(self):
        verdict = cp.verdict_panneau_onduleur(
            _FauxProduit(4, 'Panneau Jinko 550W'),
            _onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
        self.assertEqual(verdict['statut'], cp.STATUT_INCONNU)
        joint = ' '.join(verdict['raisons'])
        self.assertIn('courant de court-circuit Isc (A)', joint)
        self.assertIn('complétez la fiche', joint)

    def test_fiche_onduleur_incomplete_donne_inconnu_motive(self):
        sans_courant = _onduleur(14, 'Onduleur hybride Deye 10kW Triphasé',
                                 ond_i_max_mppt_a=None)
        verdict = cp.verdict_panneau_onduleur(_panneau_710(), sans_courant)
        self.assertEqual(verdict['statut'], cp.STATUT_INCONNU)
        self.assertIn('courant maxi par MPPT (A)',
                      ' '.join(verdict['raisons']))


class VerdictBatterieOnduleurTest(SimpleTestCase):
    def test_tension_dans_la_plage(self):
        verdict = cp.verdict_batterie_onduleur(
            _batterie(), _onduleur_5k_mono())
        self.assertEqual(verdict['statut'], cp.STATUT_COMPATIBLE)
        self.assertEqual(verdict['raisons'], [])
        self.assertIn('40-60 V', verdict['detail'])

    def test_tension_hors_plage(self):
        verdict = cp.verdict_batterie_onduleur(
            _batterie(), _onduleur_haute_tension_fictif())
        self.assertEqual(verdict['statut'], cp.STATUT_INCOMPATIBLE)
        self.assertIn('160-700 V', ' '.join(verdict['raisons']))

    def test_le_parc_deye_triphase_accepte_les_dyness(self):
        """Non-régression de la correction fondateur du 21/08/2026 : le Deye
        triphasé du catalogue est BASSE TENSION (40-60 V), donc une Dyness
        51,2 V s'y accroche. Aucun montage ne doit le supposer haute tension."""
        verdict = cp.verdict_batterie_onduleur(
            _batterie(), _onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
        self.assertEqual(verdict['statut'], cp.STATUT_COMPATIBLE)

    def test_onduleur_reseau_ne_prend_aucune_batterie(self):
        reseau = _onduleur(21, 'Onduleur réseau Huawei 10kW Triphasé',
                           ond_bat_aucune=True, ond_bat_v_min=None,
                           ond_bat_v_max=None)
        verdict = cp.verdict_batterie_onduleur(_batterie(), reseau)
        self.assertEqual(verdict['statut'], cp.STATUT_INCOMPATIBLE)
        self.assertIn('aucune batterie', ' '.join(verdict['raisons']))

    def test_tension_batterie_inconnue_donne_inconnu(self):
        verdict = cp.verdict_batterie_onduleur(
            _batterie(9, 'Batterie Dyness HV 16 kWh', v_nominal=None),
            _onduleur_5k_mono())
        self.assertEqual(verdict['statut'], cp.STATUT_INCONNU)
        self.assertIn('tension nominale (V)', ' '.join(verdict['raisons']))

    def test_plage_non_declaree_sur_un_hybride_donne_inconnu(self):
        """Là où la COMPOSITION retombe sur son repli mot-clé (elle doit
        produire quelque chose), l'ÉCRAN dit « inconnu » : il n'a rien à
        produire, donc rien ne l'autorise à affirmer."""
        muet = _onduleur(15, 'Onduleur hybride Deye 10kW Triphasé',
                         ond_bat_v_min=None, ond_bat_v_max=None)
        verdict = cp.verdict_batterie_onduleur(_batterie(), muet)
        self.assertEqual(verdict['statut'], cp.STATUT_INCONNU)
        self.assertIn('plage de tension batterie (V)',
                      ' '.join(verdict['raisons']))


# ═══════════════════════════════════════════════════════════════════════════
# 3. La forme rendue = le CONTRAT COMMITTÉ (comparée AU FICHIER, PACT10)
# ═══════════════════════════════════════════════════════════════════════════
class ContratCompatibilitesProduitTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.stock.models import FicheTechnique, Produit
        from authentication.models import Company
        cls.company, _ = Company.objects.get_or_create(
            slug='pvcompat-co', defaults={'nom': 'PVCOMPAT Co'})

        def produit(nom, sku, prix, garantie='5 ans'):
            return Produit.objects.create(
                company=cls.company, nom=nom, sku=sku,
                prix_vente=Decimal(str(prix)), quantite_stock=5,
                garantie=garantie)

        cls.panneau = produit('Panneau Canadien Solar 710W', 'PVC-PAN', 1500)
        FicheTechnique.objects.create(
            company=cls.company, produit=cls.panneau,
            type_fiche=FicheTechnique.TypeFiche.MODULE,
            pmax_wc=Decimal('710.00'), voc_v=Decimal('48.30'),
            vmp_v=Decimal('40.40'), isc_a=Decimal('18.59'),
            imp_a=Decimal('17.59'),
            temp_coeff_voc_pct_c=Decimal('-0.250'),
            temp_coeff_pmax_pct_c=Decimal('-0.290'),
            longueur_mm=2384, largeur_mm=1303)

        cls.onduleur = produit(
            'Onduleur hybride Deye 10kW Triphasé', 'PVC-OND', 30000)
        FicheTechnique.objects.create(
            company=cls.company, produit=cls.onduleur,
            type_fiche=FicheTechnique.TypeFiche.ONDULEUR,
            ond_ac_kw=Decimal('10.00'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('160.0'), ond_mppt_v_max=Decimal('650.0'),
            ond_v_max_abs=Decimal('800.0'), ond_i_max_mppt_a=Decimal('26.0'),
            ond_rendement_euro_pct=Decimal('97.0'),
            ond_v_demarrage_v=Decimal('160.0'),
            ond_isc_max_mppt_a=Decimal('39.0'),
            # SG05LP3 — BASSE TENSION (correction fondateur du 21/08/2026 :
            # aucune référence Deye du catalogue n'est haute tension).
            ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))

        # Une batterie SANS PRIX : l'écran Stock est INFORMATIF, elle doit
        # apparaître (le garde « prix à renseigner » est celui de la
        # composition, pas celui de la compatibilité).
        cls.batterie = produit('Batterie Dyness 10 kWh', 'PVC-BAT', 0)
        FicheTechnique.objects.create(
            company=cls.company, produit=cls.batterie,
            type_fiche=FicheTechnique.TypeFiche.BATTERIE,
            bat_kwh_nominal=Decimal('10.00'), bat_v_nominal=Decimal('51.2'))

    def test_forme_complete_pour_un_onduleur(self):
        data = sv_compat(self.onduleur, self.company)
        self.assertEqual(set(data), CLES_RACINE)
        self.assertEqual(set(data['produit']), CLES_ENTETE)
        self.assertEqual(data['produit']['famille'], 'onduleur_hybride')
        self.assertEqual(set(data['bilan']), CLES_BILAN)
        for entree in data['bilan']['composition']:
            self.assertEqual(set(entree), CLES_COMPOSITION)
        for famille in data['familles']:
            self.assertEqual(set(famille), CLES_FAMILLE)
            for produit in famille['produits']:
                self.assertEqual(set(produit), CLES_PRODUIT_LISTE)
        self.assertEqual([f['famille'] for f in data['familles']],
                         ['panneau', 'batterie'])

    def test_onduleur_installable_avec_son_panneau_et_sa_batterie(self):
        data = sv_compat(self.onduleur, self.company)
        self.assertTrue(data['installable'])
        self.assertEqual(data['bilan']['verdict'], 'installable')
        roles = [c['role'] for c in data['bilan']['composition']]
        self.assertEqual(roles, ['panneau', 'batterie'])
        panneau = data['bilan']['composition'][0]
        self.assertEqual(panneau['produit_id'], self.panneau.id)
        self.assertGreater(panneau['quantite'], 0)
        self.assertIn('Voc à froid', panneau['detail'])
        self.assertEqual(data['bilan']['problemes'], [])

    def test_produit_sans_prix_present_dans_le_vivier(self):
        """La batterie à 0 MAD est jugée comme les autres (écran informatif)."""
        data = sv_compat(self.onduleur, self.company)
        batteries = [f for f in data['familles']
                     if f['famille'] == 'batterie'][0]
        self.assertEqual([p['id'] for p in batteries['produits']],
                         [self.batterie.id])
        self.assertTrue(batteries['produits'][0]['ok'])

    def test_forme_complete_pour_un_panneau_bilan_null(self):
        data = sv_compat(self.panneau, self.company)
        self.assertEqual(set(data), CLES_RACINE)
        self.assertIsNone(data['bilan'])
        self.assertEqual([f['famille'] for f in data['familles']],
                         ['onduleur'])
        self.assertTrue(data['installable'])
        self.assertEqual(data['fiche_incomplete'], [])

    def test_aucun_prix_dans_la_reponse(self):
        blob = repr(sv_compat(self.onduleur, self.company)).lower()
        for interdit in ('prix', 'marge', 'prix_achat', '30000', '1500'):
            self.assertNotIn(interdit, blob)


def sv_compat(produit, company):
    """Passe par la FAÇADE cross-app (``ventes.selectors``), pas l'implém."""
    from apps.ventes.selectors import compatibilites_du_produit
    return compatibilites_du_produit(produit, company)


# ═══════════════════════════════════════════════════════════════════════════
# 4. L'endpoint (company-scopé)
# ═══════════════════════════════════════════════════════════════════════════
class EndpointCompatibilitesTest(TestCase):
    def setUp(self):
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='pvcompat-api', defaults={'nom': 'PVCOMPAT API'})
        self.autre, _ = Company.objects.get_or_create(
            slug='pvcompat-api2', defaults={'nom': 'PVCOMPAT API 2'})
        self.user = User.objects.create_user(
            username='pvcompatuser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 10kW Triphasé',
            sku='PVC-API-OND', prix_vente=Decimal('30000'), quantite_stock=1)
        self.etranger = Produit.objects.create(
            company=self.autre, nom='Onduleur hybride Deye 8kW Triphasé',
            sku='PVC-API-X', prix_vente=Decimal('25000'), quantite_stock=1)

    def _get(self, produit):
        return self.api.get(
            '/api/django/stock/produits/%s/compatibilites/' % produit.id)

    def test_forme_contractuelle(self):
        reponse = self._get(self.produit)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(set(reponse.json()), CLES_RACINE)

    def test_produit_d_une_autre_societe_est_404(self):
        self.assertEqual(self._get(self.etranger).status_code, 404)

    def test_sans_jeton_refuse(self):
        self.assertIn(APIClient().get(
            '/api/django/stock/produits/%s/compatibilites/'
            % self.produit.id).status_code, (401, 403))


# ═══════════════════════════════════════════════════════════════════════════
# 5. La COMPOSITION — repli, avertissement, raccordement, stabilité
# ═══════════════════════════════════════════════════════════════════════════
def _catalogue(*, avec_hybride_mono=True, avec_hybride_tri=True,
               panneaux=None):
    produits = list(panneaux if panneaux is not None else [_panneau_710()])
    produits.append(_onduleur(21, 'Onduleur réseau Huawei 10kW Triphasé',
                              ond_bat_aucune=True, ond_bat_v_min=None,
                              ond_bat_v_max=None))
    if avec_hybride_tri:
        # Plage batterie 40-60 V (défaut SG05LP3) : la Dyness 51,2 V s'y
        # accroche, donc aucun avertissement PVOND « vivier batterie vide »
        # (antérieur à ce lot) ne brouille les épingles de composition.
        produits.append(_onduleur(13, 'Onduleur hybride Deye 10kW Triphasé'))
    if avec_hybride_mono:
        produits.append(_onduleur_5k_mono())
    produits.append(_batterie())
    return produits


class CompositionCoupleElectriqueTest(SimpleTestCase):
    """``composition_residentielle`` reste PURE : on lui passe des faux
    produits, elle ne requête rien."""

    def test_sans_raccordement_les_choix_sont_ceux_d_hier(self):
        """ÉPINGLE de non-régression : 7,1 kWc, catalogue sain, aucun
        raccordement déclaré ⇒ l'onduleur ≥ 80 % de la puissance (10 kW,
        triphasé au-delà de 10 kW) et le panneau au wattage exact — exactement
        les règles d'avant PVCOMPAT — et AUCUN avertissement."""
        avertissements = []
        lignes = sv.composition_residentielle(
            _catalogue(), kwc=7.1, panel_watt=710, nb_panneaux=10,
            avec_batterie=True, avertissements=avertissements)
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', designations)
        self.assertIn('Panneau Canadien Solar 710W', designations)
        self.assertNotIn('Onduleur hybride Deye 5kW Monophasé', designations)
        self.assertEqual(avertissements, [])

    def test_couple_hors_borne_est_annonce_sans_tuer_la_composition(self):
        """Catalogue dont le SEUL hybride est le Deye 5 kW, et rien d'autre
        au wattage : depuis DEV-202608-0016 le couple 710 Wc / 5 kW est
        INCOMPATIBLE (Isc 18,6 A > 17 A publiés), pas « sous réserve ».

        La règle « jamais une composition morte » tient toujours : les deux
        lignes restent, et le motif porte les chiffres des DEUX fiches. C'est
        ensuite le schéma unifilaire qui refusera de dessiner ce montage, et
        la resynchro 3D qui refusera de l'écrire.
        """
        avertissements = []
        lignes = sv.composition_residentielle(
            _catalogue(avec_hybride_tri=False), kwc=3.55, panel_watt=710,
            nb_panneaux=5, avec_batterie=True, avertissements=avertissements)
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', designations)
        # La composition n'est PAS morte, et le motif porte les chiffres.
        self.assertIn('Panneau Canadien Solar 710W', designations)
        self.assertTrue(avertissements)
        joint = ' '.join(avertissements)
        self.assertIn('INCOMPATIBLE', joint)
        self.assertIn('18,6 A', joint)
        self.assertIn('17,0 A', joint)

    def test_panneau_incompatible_declenche_un_repli_annonce(self):
        """Le 710 Wc dépasse à lui seul la tension maximale de cet onduleur
        (Voc à froid 51,9 V > 45 V — BLOQUANT du noyau) ; le 400 Wc (Voc à
        froid 40,0 V) passe → la composition CHANGE de panneau et l'annonce."""
        etroit = _onduleur(
            31, 'Onduleur hybride Deye 3kW Monophasé',
            ond_ac_kw=Decimal('3.00'), ond_phases=1,
            ond_mppt_v_min=Decimal('20.0'), ond_mppt_v_max=Decimal('45.0'),
            ond_v_max_abs=Decimal('45.0'), ond_v_demarrage_v=Decimal('20.0'),
            ond_i_max_mppt_a=Decimal('40.0'),
            ond_isc_max_mppt_a=Decimal('40.0'),
            ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))
        catalogue = [_panneau_710(), _panneau_400(), etroit, _batterie()]
        avertissements = []
        lignes = sv.composition_residentielle(
            catalogue, kwc=2.84, panel_watt=710, nb_panneaux=4,
            avec_batterie=True, avertissements=avertissements)
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Panneau Jinko 400W', designations)
        self.assertNotIn('Panneau Canadien Solar 710W', designations)
        self.assertTrue(any('remplacé pour compatibilité électrique' in a
                            for a in avertissements), avertissements)

    def test_aucun_panneau_ne_va_le_choix_est_garde_et_annonce(self):
        """Jamais une composition morte : le panneau d'origine reste, le
        problème est NOMMÉ."""
        impossible = _onduleur(
            32, 'Onduleur hybride Micro 1kW Monophasé',
            ond_ac_kw=Decimal('1.00'), ond_phases=1,
            ond_mppt_v_min=Decimal('60.0'), ond_mppt_v_max=Decimal('60.0'),
            ond_v_max_abs=Decimal('60.0'), ond_v_demarrage_v=Decimal('60.0'),
            ond_i_max_mppt_a=Decimal('13.0'),
            ond_isc_max_mppt_a=Decimal('13.0'),
            ond_bat_v_min=Decimal('40.0'), ond_bat_v_max=Decimal('60.0'))
        avertissements = []
        lignes = sv.composition_residentielle(
            [_panneau_710(), impossible, _batterie()], kwc=1.42,
            panel_watt=710, nb_panneaux=2, avec_batterie=True,
            avertissements=avertissements)
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Panneau Canadien Solar 710W', designations)
        self.assertTrue(any('INCOMPATIBLE' in a for a in avertissements),
                        avertissements)


class CompositionRaccordementTest(SimpleTestCase):
    def test_monophase_ecarte_les_onduleurs_triphases(self):
        avertissements = []
        lignes = sv.composition_residentielle(
            _catalogue(), kwc=7.1, panel_watt=710, nb_panneaux=10,
            avec_batterie=True, avertissements=avertissements,
            phase='monophase')
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', designations)
        self.assertNotIn('Onduleur hybride Deye 10kW Triphasé', designations)

    def test_monophase_sans_candidat_replie_et_avertit(self):
        avertissements = []
        lignes = sv.composition_residentielle(
            _catalogue(avec_hybride_mono=False), kwc=7.1, panel_watt=710,
            nb_panneaux=10, avec_batterie=True,
            avertissements=avertissements, phase='monophase')
        designations = [ligne.designation for ligne in lignes]
        # Jamais un devis sans onduleur : on garde le triphasé…
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', designations)
        # … et on le DIT, une seule fois.
        replis = [a for a in avertissements if 'monophasé déclaré' in a]
        self.assertEqual(len(replis), 1, avertissements)

    def test_triphase_ne_restreint_pas_le_vivier(self):
        """Un abonnement triphasé accepte un onduleur monophasé : le vivier
        reste entier, seule la préférence de départage devient dure."""
        avertissements = []
        lignes = sv.composition_residentielle(
            _catalogue(), kwc=7.1, panel_watt=710, nb_panneaux=10,
            avec_batterie=True, avertissements=avertissements,
            phase='triphase')
        designations = [ligne.designation for ligne in lignes]
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', designations)
        self.assertEqual(
            [a for a in avertissements if 'déclaré' in a], [])

    def test_raccordement_inconnu_ne_change_rien(self):
        reference = [ligne.designation for ligne in
                     sv.composition_residentielle(
                         _catalogue(), kwc=7.1, panel_watt=710,
                         nb_panneaux=10, avec_batterie=True)]
        for valeur in ('inconnu', '', None):
            avec = [ligne.designation for ligne in
                    sv.composition_residentielle(
                        _catalogue(), kwc=7.1, panel_watt=710,
                        nb_panneaux=10, avec_batterie=True, phase=valeur)]
            self.assertEqual(avec, reference, valeur)

    def test_normalisation_des_valeurs_de_lead(self):
        self.assertEqual(cp.normaliser_phase('monophase'), cp.PHASE_MONO)
        self.assertEqual(cp.normaliser_phase('mono'), cp.PHASE_MONO)
        self.assertEqual(cp.normaliser_phase('triphase'), cp.PHASE_TRI)
        self.assertEqual(cp.normaliser_phase('tri'), cp.PHASE_TRI)
        self.assertIsNone(cp.normaliser_phase('inconnu'))
        self.assertIsNone(cp.normaliser_phase(None))
        self.assertIsNone(cp.normaliser_phase(''))
