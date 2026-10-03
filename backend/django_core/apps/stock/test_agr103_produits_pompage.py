"""AGR103 — une seule lecture serveur du catalogue pompage :
``stock.selectors.produits_pompage`` (forme de ``produit_pompage.json``).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.stock.models import Categorie, FicheTechnique, Produit
from apps.stock.selectors import produits_pompage
from authentication.models import Company

CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_pompage.json')
    .read_text(encoding='utf-8'))


def _cles_recursives(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _cles_recursives(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _cles_recursives(v)


class ProduitsPompageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr103-co', defaults={'nom': 'AGR103 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='agr103-autre', defaults={'nom': 'AGR103 Autre'})[0]

    def _p(self, nom, **kw):
        kw.setdefault('prix_vente', Decimal('100'))
        kw.setdefault('prix_achat', Decimal('60'))
        kw.setdefault('company', self.co)
        return Produit.objects.create(nom=nom, **kw)

    def _lire(self, **kw):
        return {e['nom']: e for e in produits_pompage(self.co, **kw)}

    def test_pompe_triphase_sans_tension_alimentation_tri_classement_nom(self):
        self._p('Pompe immergée solaire 4 CV Triphasé', pompe_cv='4')
        e = self._lire()['Pompe immergée solaire 4 CV Triphasé']
        self.assertEqual(e['alimentation'], 'tri')
        self.assertEqual(e['classement'], 'nom')
        self.assertEqual(e['role_pompage'], 'pompe')
        self.assertEqual(e['type_pompe'], 'immergee')

    def test_pompe_monophase_et_surface_lues_du_nom(self):
        self._p('Pompe de surface solaire 1.5 CV Monophasé')
        e = self._lire()['Pompe de surface solaire 1.5 CV Monophasé']
        self.assertEqual(e['alimentation'], 'mono')
        self.assertEqual(e['type_pompe'], 'surface')

    def test_alimentation_priorite_declaree_puis_tension_puis_nom(self):
        self._p('Pompe X Triphasé', alimentation='mono')
        self._p('Pompe Y Triphasé', tension_v=220)
        e = self._lire()
        self.assertEqual(e['Pompe X Triphasé']['alimentation'], 'mono')
        self.assertEqual(e['Pompe Y Triphasé']['alimentation'], 'mono')

    def test_regle_stricte_2200w_nest_pas_220v(self):
        self._p('Variateur VEICHI SI23 2200W')
        e = self._lire()['Variateur VEICHI SI23 2200W']
        self.assertEqual(e['alimentation'], '')

    def test_declare_prime_sur_le_nom(self):
        self._p('Électropompe submersible 4 pouces', role_pompage='pompe',
                type_pompe='immergee')
        e = self._lire()['Électropompe submersible 4 pouces']
        self.assertEqual(e['classement'], 'declare')
        self.assertEqual(e['type_pompe'], 'immergee')

    def test_classement_categorie(self):
        cat = Categorie.objects.create(
            company=self.co, nom='Pompes AGR103', type_equipement='pompe')
        self._p('Groupe électropompe 3 pouces', categorie=cat)
        e = self._lire()['Groupe électropompe 3 pouces']
        self.assertEqual(e['classement'], 'categorie')
        self.assertEqual(e['role_pompage'], 'pompe')

    def test_variateur_et_afficheur(self):
        self._p('VARIATEUR VEICHI SI23 5.5KW 380V', pompe_kw='5.5',
                tension_v=380)
        self._p('AFFICHEUR VEICHI SI22')
        e = self._lire()
        self.assertEqual(
            e['VARIATEUR VEICHI SI23 5.5KW 380V']['role_pompage'],
            'variateur_pompage')
        self.assertEqual(
            e['AFFICHEUR VEICHI SI22']['role_pompage'], 'afficheur_variateur')

    def test_produit_non_pompage_ignore(self):
        self._p('Panneau 550W')
        self.assertNotIn('Panneau 550W', self._lire())

    def test_autre_societe_jamais_servie(self):
        self._p('Pompe autre société', company=self.autre)
        self._p('Pompe ma société')
        noms = {e['nom'] for e in produits_pompage(self.co)}
        self.assertIn('Pompe ma société', noms)
        self.assertNotIn('Pompe autre société', noms)

    def test_archives_exclus_et_prix_connu(self):
        self._p('Pompe archivée', is_archived=True)
        self._p('Pompe sans prix', prix_vente=Decimal('0'))
        e = self._lire()
        self.assertNotIn('Pompe archivée', e)
        self.assertFalse(e['Pompe sans prix']['prix_connu'])
        self.assertNotIn('Pompe sans prix', self._lire(avec_prix=True))

    def test_aucune_cle_prix_achat_ni_marge(self):
        self._p('Pompe secrète', prix_achat=Decimal('12345.67'))
        resultat = produits_pompage(self.co)
        cles = set(_cles_recursives(resultat))
        for interdit in CONTRAT['element_produits_pompage']['interdit']:
            self.assertNotIn(interdit, cles)
        self.assertNotIn('12345.67', json.dumps(resultat))

    def test_cles_egales_au_contrat(self):
        self._p('Pompe contrat')
        e = produits_pompage(self.co)[0]
        self.assertEqual(
            set(e), set(CONTRAT['element_produits_pompage']['cles']))
        self.assertEqual(
            set(e['courbe_source']), {'document', 'date', 'page'})

    def test_fiche_variateur_jointe(self):
        v = self._p('Variateur pompage fiche', pompe_kw='5.5')
        FicheTechnique.objects.create(
            company=self.co, produit=v, type_fiche='variateur_pompage',
            var_v_sortie_v=Decimal('380'))
        e = self._lire()['Variateur pompage fiche']
        self.assertEqual(e['fiche']['type_fiche'], 'variateur_pompage')
        self.assertEqual(e['fiche']['var_v_sortie_v'], 380.0)
        self.assertIsNone(e['fiche']['var_voc_reco_min_v'])

    def test_nombre_de_requetes_borne(self):
        for i in range(8):
            v = self._p(f'Variateur pompage {i}', pompe_kw='5.5')
            FicheTechnique.objects.create(
                company=self.co, produit=v, type_fiche='variateur_pompage')
        with self.assertNumQueries(1):
            produits_pompage(self.co)
