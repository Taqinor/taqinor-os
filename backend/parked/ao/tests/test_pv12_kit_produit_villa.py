"""PV12 — le calepinage villa se pose sur le PANNEAU RÉELLEMENT VENDU.

Jusqu'ici la villa ne savait poser qu'un seul module : ``KIT_VILLA_720``, une
constante du moteur. Un devis résidentiel qui vend un 450 Wc affichait donc un
plan calculé sur un 720 Wc — le nombre de panneaux dessiné n'était pas celui
qu'on installe.

Ce module prouve trois choses, et rien d'autre :

  1. **Le produit gagne** — passer ``produit_panneau`` fait entrer la géométrie
     de SA fiche technique (PV5) dans le calcul : le kit retenu porte le SKU du
     produit, et sur une géométrie différente le compte CHANGE.
  2. **La résolution est SCOPÉE SOCIÉTÉ** — un identifiant se résout dans
     ``company`` ; le produit d'une autre société est refusé, jamais silencieux.
  3. **Une fiche incomplète retombe sur ``KIT_VILLA_720``, inchangé** — le
     moteur ne devine jamais une géométrie, et l'absence d'une dimension ne
     doit pas produire un plan plausible et faux.

Run :
    python manage.py test apps.ao.tests.test_pv12_kit_produit_villa -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ao import selectors, services
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company
from core.calepinage.adaptateurs.villa import Projection
from core.calepinage.types import KIT_VILLA_720

#: Ancre géographique (Casablanca) — sans importance métier : elle ne sert qu'à
#: l'aller-retour mètres -> degrés du lecteur de cartes.
LAT0, LNG0 = 33.5731, -7.5898

#: Toiture d'essai CENTRÉE sur l'ancre : 14 m est-ouest × 10 m nord-sud.
DEMI_LARGEUR_M, DEMI_HAUTEUR_M = 7.0, 5.0


def _area_villa():
    """L'``AreaRecord`` du lecteur de cartes pour cette toiture, sans obstacle."""
    projection = Projection(lat0_deg=LAT0, lng0_deg=LNG0)
    points = []
    for est, nord in ((-DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
                      (DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
                      (DEMI_LARGEUR_M, DEMI_HAUTEUR_M),
                      (-DEMI_LARGEUR_M, DEMI_HAUTEUR_M)):
        lat, lng = projection.vers_geo(est, nord)
        points.append([lng, lat])
    return {'id': 'VILLA_PV12', 'polygon': points, 'flat': True,
            'tilt': 0.0, 'azimuth': 180.0, 'obstacles': []}


class BasePv12(TestCase):
    """Deux sociétés : le cloisonnement se prouve, il ne se raconte pas."""

    def setUp(self):
        self.company = Company.objects.create(nom='PV12 Co', slug='pv12-co')
        self.autre = Company.objects.create(nom='PV12 Autre',
                                            slug='pv12-autre')

    def _produit(self, *, company=None, sku='PV12-720', nom='Module 720 Wc',
                 longueur_mm=2384, largeur_mm=1303, pmax_wc='720.00',
                 avec_fiche=True):
        produit = Produit.objects.create(
            company=company or self.company, nom=nom, sku=sku,
            prix_vente=Decimal('2950.00'))
        if avec_fiche:
            FicheTechnique.objects.create(
                company=produit.company, produit=produit,
                type_fiche=FicheTechnique.TypeFiche.MODULE,
                longueur_mm=longueur_mm, largeur_mm=largeur_mm,
                pmax_wc=None if pmax_wc is None else Decimal(pmax_wc))
        return produit

    def _villa(self, **kwargs):
        return services.calepiner_villa(_area_villa(), **kwargs)


class LeProduitEntreDansLeCalcul(BasePv12):
    """Le kit posé est celui de la fiche technique du produit vendu."""

    def test_le_kit_retenu_porte_le_sku_du_produit(self):
        produit = self._produit()
        sortie = self._villa(produit_panneau=produit, company=self.company)
        codes = {kit.code for kit in sortie['entree'].kits}
        self.assertEqual(codes, {'PV12-720'})
        self.assertNotIn(KIT_VILLA_720.code, codes)

    def test_une_geometrie_de_module_differente_change_le_compte(self):
        """Un 450 Wc de 1,722 × 1,134 ne donne PAS le compte d'un 720 Wc."""
        produit = self._produit(sku='PV12-450', nom='Module 450 Wc',
                                longueur_mm=1722, largeur_mm=1134,
                                pmax_wc='450.00')
        avec_produit = self._villa(produit_panneau=produit,
                                   company=self.company)
        par_defaut = self._villa()
        self.assertEqual(par_defaut['entree'].kits[0].code, KIT_VILLA_720.code)
        self.assertNotEqual(avec_produit['resultat'].modules,
                            par_defaut['resultat'].modules)
        self.assertGreater(avec_produit['resultat'].modules, 0)

    def test_un_identifiant_est_accepte_comme_une_instance(self):
        produit = self._produit()
        par_instance = self._villa(produit_panneau=produit,
                                   company=self.company)
        par_identifiant = self._villa(produit_panneau=produit.pk,
                                      company=self.company)
        self.assertEqual(par_identifiant['resultat'].modules,
                         par_instance['resultat'].modules)
        self.assertEqual(par_identifiant['entree'].kits[0].code, 'PV12-720')

    def test_un_kit_explicite_prime_sur_le_produit(self):
        """``kit=`` est déjà un choix : le produit ne le renverse pas."""
        produit = self._produit(sku='PV12-450', longueur_mm=1722,
                                largeur_mm=1134, pmax_wc='450.00')
        sortie = self._villa(kit=KIT_VILLA_720, produit_panneau=produit,
                             company=self.company)
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)


class LaResolutionEstScopeeSociete(BasePv12):
    """Un panneau d'une autre société n'entre JAMAIS dans un calcul."""

    def test_un_identifiant_d_une_autre_societe_est_refuse(self):
        etranger = self._produit(company=self.autre, sku='PV12-ETR')
        with self.assertRaises(ValueError):
            self._villa(produit_panneau=etranger.pk, company=self.company)

    def test_une_instance_d_une_autre_societe_est_refusee(self):
        etranger = self._produit(company=self.autre, sku='PV12-ETR2')
        with self.assertRaises(ValueError):
            self._villa(produit_panneau=etranger, company=self.company)

    def test_un_identifiant_sans_societe_est_refuse(self):
        produit = self._produit()
        with self.assertRaises(ValueError):
            self._villa(produit_panneau=produit.pk)

    def test_un_identifiant_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            self._villa(produit_panneau=999999, company=self.company)


class LaFicheIncompleteRetombeSurLeKitVilla(BasePv12):
    """Sans les trois grandeurs requises, la géométrie n'est pas devinée."""

    def _compte_par_defaut(self):
        return self._villa()['resultat'].modules

    def test_un_produit_sans_fiche_technique(self):
        produit = self._produit(avec_fiche=False)
        sortie = self._villa(produit_panneau=produit, company=self.company)
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)
        self.assertEqual(sortie['resultat'].modules, self._compte_par_defaut())

    def test_une_fiche_sans_dimensions(self):
        produit = self._produit(longueur_mm=None, largeur_mm=None)
        sortie = self._villa(produit_panneau=produit, company=self.company)
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)
        self.assertEqual(sortie['resultat'].modules, self._compte_par_defaut())

    def test_une_fiche_sans_puissance(self):
        produit = self._produit(pmax_wc=None)
        sortie = self._villa(produit_panneau=produit, company=self.company)
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)
        self.assertEqual(sortie['resultat'].modules, self._compte_par_defaut())

    def test_des_dimensions_incoherentes(self):
        """Largeur > longueur : ``kit_from_produit`` refuse, on ne devine pas."""
        produit = self._produit(longueur_mm=1134, largeur_mm=1722)
        sortie = self._villa(produit_panneau=produit, company=self.company)
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)


class LeSelectorEstLaPorteCrossApp(BasePv12):
    """``apps.ventes`` lit le moteur par ``apps.ao.selectors``, jamais autrement."""

    def test_le_selector_transmet_le_produit_et_la_societe(self):
        produit = self._produit(sku='PV12-450', longueur_mm=1722,
                                largeur_mm=1134, pmax_wc='450.00')
        par_selector = selectors.calepinage_villa(
            _area_villa(), produit_panneau=produit, company=self.company)
        par_service = services.calepiner_villa(
            _area_villa(), produit_panneau=produit, company=self.company)
        self.assertEqual(par_selector['entree'].kits[0].code, 'PV12-450')
        self.assertEqual(par_selector['resultat'].modules,
                         par_service['resultat'].modules)

    def test_le_selector_sans_produit_reste_sur_le_kit_villa(self):
        sortie = selectors.calepinage_villa(_area_villa())
        self.assertEqual(sortie['entree'].kits[0].code, KIT_VILLA_720.code)
