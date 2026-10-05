"""SPL111 — golden de la lecture fiche technique de ``stock/selectors.py``.

Capture seule : ``type_fiche_produit``, ``specs_for_produit``,
``dimensions_de_pose``, ``produits_modules_qs`` et ``kit_from_produit`` sont
figés tels qu'ils sont AUJOURD'HUI. SPL114 les déplacera vers
``selectors_fiche_technique.py`` ; ce test, importé par la FAÇADE
``apps.stock.selectors``, doit rester vert sans régénérer le JSON.
L'assertion ``<fonction>.__module__ == 'apps.stock.selectors_fiche_technique'``
est ajoutée (et prouvée rouge) par SPL114.

Sections de ``golden/fiche_technique_selecteurs.json`` :
  * ``ast``       — empreintes AST des cinq fonctions (outil SPL110) ;
  * ``lecture``   — sorties des cinq fonctions sur un jeu de produits (une
                    fiche de chaque ``TypeFiche``, sans fiche, archivé) ;
  * ``produits_modules_qs`` — skus ordonnés (le nombre de requêtes est figé
                    par ``assertNumQueries`` dans le test, pas dans le JSON).

Capture (UNE fois, sur le code actuel, jamais après le déplacement) :
    GOLDEN_CAPTURE=1 docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_selecteurs
Hors capture, une section absente du JSON fait ÉCHOUER le test.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_selecteurs -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.golden.ast_fingerprint import fingerprint, verifier_section
from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import (
    dimensions_de_pose, kit_from_produit, produits_modules_qs,
    specs_for_produit, type_fiche_produit)
from authentication.models import Company

GOLDEN = 'fiche_technique_selecteurs'

# sku -> (nom, type_fiche | None = pas de fiche, champs de la fiche, archivé).
# Les noms sont choisis pour que l'ordre (nom, id) de ``produits_modules_qs``
# soit déterministe.
PRODUITS = {
    'G-MOD': ('A Module 550 Wc', 'module', {
        'pmax_wc': Decimal('550'), 'voc_v': Decimal('49.5'),
        'isc_a': Decimal('13.9'), 'vmp_v': Decimal('41.5'),
        'imp_a': Decimal('13.25'), 'rendement_pct': Decimal('21.3'),
        'longueur_mm': 2278, 'largeur_mm': 1134, 'epaisseur_mm': 30,
        'poids_kg': Decimal('27.5'), 'techno_cellule': 'N-type TOPCon',
        'bifacial': True, 'bifacialite_pct': Decimal('70.0'),
        'temp_coeff_voc_pct_c': Decimal('-0.250'),
        'temp_coeff_pmax_pct_c': Decimal('-0.300'),
        'noct_c': Decimal('43.0'), 'uc_w_m2k': Decimal('29.0'),
        'uv_w_m3sk': Decimal('0.00'),
        'degradation_annuelle_pct': Decimal('0.40'),
        'degradation_annee1_pct': Decimal('1.00'),
        'garantie_pct_a_10_ans': Decimal('92.0'),
        'garantie_pct_a_25_ans': Decimal('87.0'),
        'rendement_par_irradiance': [
            {'w_m2': 200, 'rendement_relatif_pct': 97.0},
            {'w_m2': 1000, 'rendement_relatif_pct': 100.0}],
        'tolerance_pmax_min_pct': Decimal('0.0'),
        'tolerance_pmax_max_pct': Decimal('3.0'),
    }, False),
    'G-MOD-SANSDIM': ('B Module sans dimensions', 'module', {
        'pmax_wc': Decimal('400'), 'voc_v': Decimal('37.0')}, False),
    'G-MOD-ARCH': ('C Module archivé', 'module', {
        'pmax_wc': Decimal('450'), 'longueur_mm': 2094,
        'largeur_mm': 1038}, True),
    'G-OND': ('Onduleur 10 kW', 'onduleur', {
        'ond_n_mppt': 2, 'ond_mppt_v_min': Decimal('200'),
        'ond_mppt_v_max': Decimal('800'), 'ond_v_max_abs': Decimal('1000'),
        'ond_i_max_mppt_a': Decimal('16'), 'ond_ac_kw': Decimal('10'),
        'ond_phases': 3, 'ond_rendement_euro_pct': Decimal('97.5'),
        'ond_courbe_rendement': [
            {'charge_pct': 10, 'rendement_pct': 90},
            {'charge_pct': 100, 'rendement_pct': 97}],
    }, False),
    'G-BAT': ('Batterie 10 kWh', 'batterie', {
        'bat_kwh_nominal': Decimal('10.24'),
        'bat_kwh_usable': Decimal('9.2'), 'bat_dod_pct': Decimal('90'),
        'bat_v_nominal': Decimal('51.2'), 'bat_chimie': 'LFP',
        'bat_cycles_publies': 6000,
    }, False),
    'G-OPT': ('Optimiseur 700 W', 'optimiseur', {
        'opt_pmax_in_w': Decimal('700'), 'opt_v_in_min': Decimal('8'),
        'opt_v_in_max': Decimal('80'), 'opt_i_in_max_a': Decimal('14'),
        'opt_rendement_pct': Decimal('99.5'),
        'opt_modules_par_optimiseur': 1,
        'opt_pmax_out_w': Decimal('700'),
    }, False),
    'G-POMPE': ('Pompe 5 CV', 'pompe', {
        'pompe_i_nominal_a': Decimal('9.5'),
        'pompe_q_nominal_m3h': Decimal('12'),
        'pompe_hmt_nominale_m': Decimal('60'),
    }, False),
    'G-VAR': ('Variateur pompage', 'variateur_pompage', {
        'var_voc_reco_min_v': Decimal('300'),
        'var_voc_reco_max_v': Decimal('700'),
    }, False),
    'G-AUTRE': ('Autre fiche', 'autre', {}, False),
    'G-VIDE': ('Fiche sans type', '', {}, False),
    'G-SANS': ('Produit sans fiche', None, {}, False),
}


def _jsonable(valeur):
    """Decimal -> chaîne exacte ; le reste est déjà sérialisable. Tout autre
    type est rendu par ``repr`` (un type inattendu change le golden au lieu
    de le casser)."""
    if isinstance(valeur, dict):
        return {str(k): _jsonable(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_jsonable(v) for v in valeur]
    if isinstance(valeur, Decimal):
        return 'Decimal:%s' % valeur
    if valeur is None or isinstance(valeur, (bool, int, float, str)):
        return valeur
    return 'repr:%r' % (valeur,)


class GoldenFicheTechniqueSelecteursTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='spl111-golden-co', defaults={'nom': 'SPL111 Golden'})[0]
        cls.autre_co = Company.objects.get_or_create(
            slug='spl111-golden-autre', defaults={'nom': 'SPL111 Autre'})[0]
        cls.ids = {}
        for sku, (nom, type_fiche, champs, archive) in PRODUITS.items():
            produit = Produit.objects.create(
                company=cls.co, nom=nom, sku=sku,
                prix_achat=Decimal('100'), prix_vente=Decimal('150'),
                quantite_stock=1, is_archived=archive)
            cls.ids[sku] = produit.pk
            if type_fiche is not None:
                FicheTechnique.objects.create(
                    company=cls.co, produit=produit, type_fiche=type_fiche,
                    **champs)
        # Un module d'une AUTRE société : jamais dans la liste de la société.
        autre = Produit.objects.create(
            company=cls.autre_co, nom='A Module autre société',
            sku='G-MOD-AUTRE', prix_achat=Decimal('100'),
            prix_vente=Decimal('150'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=cls.autre_co, produit=autre, type_fiche='module',
            pmax_wc=Decimal('500'))

    def _produit(self, sku):
        # Lecture fraîche : aucun cache de relation hérité de la création.
        return Produit.objects.get(pk=self.ids[sku])

    def test_spl114_lecture_vit_dans_selectors_fiche_technique(self):
        """SPL114 — les cinq sélecteurs ont déménagé dans
        ``selectors_fiche_technique.py`` ; la façade ``apps.stock.selectors``
        ré-exporte LES MÊMES objets (pas de jumeau)."""
        import importlib

        import apps.stock.selectors as facade
        module = importlib.import_module(
            'apps.stock.selectors_fiche_technique')
        for fn in (type_fiche_produit, specs_for_produit, dimensions_de_pose,
                   produits_modules_qs, kit_from_produit):
            self.assertEqual(fn.__module__,
                             'apps.stock.selectors_fiche_technique')
            self.assertIs(getattr(module, fn.__name__), fn)
            self.assertIs(getattr(facade, fn.__name__), fn)

    def test_empreintes_ast(self):
        courant = {
            fn.__name__: fingerprint(fn) for fn in (
                type_fiche_produit, specs_for_produit, dimensions_de_pose,
                produits_modules_qs, kit_from_produit)}
        verifier_section(self, GOLDEN, 'ast', courant)

    def test_lecture_des_cinq_selecteurs(self):
        """Sortie réelle (aucun mock) de chaque sélecteur, par produit."""
        courant = {}
        for sku in PRODUITS:
            produit = self._produit(sku)
            kit = kit_from_produit(produit)
            courant[sku] = {
                'type_fiche_produit': type_fiche_produit(produit),
                'specs_for_produit': _jsonable(specs_for_produit(produit)),
                'dimensions_de_pose': _jsonable(dimensions_de_pose(produit)),
                'kit_from_produit': None if kit is None else repr(kit),
            }
        # Gardes de sens indépendantes du JSON.
        self.assertEqual(courant['G-SANS']['type_fiche_produit'], '')
        self.assertEqual(courant['G-SANS']['dimensions_de_pose'], {})
        self.assertIsNone(courant['G-SANS']['kit_from_produit'])
        self.assertIsNone(courant['G-MOD-SANSDIM']['kit_from_produit'])
        self.assertIsNotNone(courant['G-MOD']['kit_from_produit'])
        self.assertEqual(courant['G-OND']['dimensions_de_pose'], {})
        verifier_section(self, GOLDEN, 'lecture', courant)

    def test_produits_modules_qs(self):
        """Ids ordonnés (par nom puis id), société de l'appelant seulement,
        archivés exclus — et UNE seule requête (``select_related``)."""
        with self.assertNumQueries(1):
            produits = list(produits_modules_qs(self.co))
            types = [p.fiche_technique.type_fiche for p in produits]
        self.assertEqual(set(types), {'module'})
        skus = [p.sku for p in produits]
        self.assertNotIn('G-MOD-ARCH', skus)
        self.assertNotIn('G-MOD-AUTRE', skus)
        verifier_section(self, GOLDEN, 'produits_modules_qs', skus)
