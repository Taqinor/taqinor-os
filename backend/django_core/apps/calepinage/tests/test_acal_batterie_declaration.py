"""ACAL166 — la batterie et le mode hors réseau se DÉCLARENT dans l'entrée
électrique, et la simulation les lit là (plus sur ``roof_layout.battery``).

Ce qui est prouvé ici (fonctions réelles, produits réels en base, aucune
doublure de la déclaration) :

* une stratégie déclarée donne une déclaration que l'étape batterie SIMULE
  (bloc non nul — jusqu'ici : « aucune stratégie ») ;
* le produit et les packs par défaut viennent de la ligne batterie du devis lié,
  avec leur provenance ; une saisie explicite l'emporte ;
* sans stratégie, le bloc est OMIS en la nommant — aucune n'est supposée ;
* le mode hors réseau déclaré est lu dans l'entrée ;
* une forme refusée NOMME son champ (``batterie.<champ>``).

Run :
    python manage.py test apps.calepinage.tests.test_acal_batterie_declaration -v2
"""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, EntreeInvalide, enregistrer_entree, entree_stockee,
)
from apps.calepinage.services.etapes import batterie as bloc
from apps.calepinage.services.simulation import (
    _declaration_batterie, _section_de_l_entree,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage
from .test_calx188_batterie import contexte_de_test, serie_de_test

FICHE = dict(bat_kwh_nominal=10.0, bat_kwh_usable=9.0, bat_dod_pct=90.0,
             bat_rendement_ar_pct=94.0, bat_cycles_publies=6000,
             bat_max_charge_kw=5.0, bat_max_decharge_kw=5.0)

#: La ligne batterie du devis lié, telle que ``equipements_du_calepinage`` la rend.
CIBLE_EQUIPEMENTS = ('apps.calepinage.services.equipements'
                     '.equipements_du_calepinage')


class Declaration(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 10 kWh', sku='ACAL166-B',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=self.produit,
            type_fiche='batterie', **FICHE)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Batterie',
            roof_layout={'zones': []}, resultat={})

    def _declaration(self, saisie, *, devis=None):
        donnees = {'batterie': saisie} if saisie is not None else {}
        with mock.patch(CIBLE_EQUIPEMENTS,
                        return_value={'batterie': devis}):
            return _declaration_batterie(
                self.calepinage, donnees, {'produits': {}}, self.company)

    def _bloc(self, declaration):
        contexte = contexte_de_test(heures=48)
        contexte[bloc.CLE_CONTEXTE] = declaration
        return bloc.bloc_batterie(serie_de_test(heures=48), contexte)[1]

    def test_strategie_declaree_donne_un_bloc_non_nul(self):
        declaration = self._declaration(
            {'produit': self.produit.pk, 'strategie': 'autoconso',
             'packs': 2})

        resultat = self._bloc(declaration)

        self.assertEqual(declaration['strategie'], 'autoconso')
        self.assertEqual(declaration['groupes'][0]['packs'], 2)
        self.assertEqual(declaration['provenance']['produit'], 'explicite')
        self.assertIsNotNone(resultat['total'], resultat['motif_absence'])

    def test_defaut_produit_et_packs_du_devis(self):
        declaration = self._declaration(
            {'strategie': 'autoconso'},
            devis={'produit': self.produit.pk, 'quantite': 3.0})

        self.assertEqual(declaration['groupes'][0]['packs'], 3)
        self.assertEqual(declaration['provenance'],
                         {'produit': 'devis', 'packs': 'devis'})

    def test_saisie_explicite_l_emporte_sur_le_devis(self):
        declaration = self._declaration(
            {'produit': self.produit.pk, 'packs': 1,
             'strategie': 'autoconso'},
            devis={'produit': self.produit.pk, 'quantite': 3.0})

        self.assertEqual(declaration['groupes'][0]['packs'], 1)
        self.assertEqual(declaration['provenance'],
                         {'produit': 'explicite', 'packs': 'explicite'})

    def test_sans_strategie_motif_nomme(self):
        declaration = self._declaration(
            None, devis={'produit': self.produit.pk, 'quantite': 1.0})

        resultat = self._bloc(declaration)

        # Produit et packs viennent du devis, mais AUCUNE stratégie n'est supposée.
        self.assertNotIn('strategie', declaration)
        self.assertIsNone(resultat['total'])
        self.assertIn('strategie', resultat['motif_absence'])

    def test_sans_batterie_ni_devis_aucune_declaration(self):
        self.assertEqual(self._declaration(None), {})

    def test_hors_reseau_declare_est_lu_dans_l_entree(self):
        donnees = {'hors_reseau': {'actif': True, 'jours_autonomie': 2}}

        self.assertEqual(_section_de_l_entree(donnees, 'hors_reseau'),
                         {'actif': True, 'jours_autonomie': 2})
        self.assertEqual(_section_de_l_entree({}, 'hors_reseau'), {})

    def test_forme_refusee_nomme_le_champ(self):
        for saisie, champ in (
                ({'strategie': 'inventee'}, 'batterie.strategie'),
                ({'couplage': 'xx'}, 'batterie.couplage'),
                ({'packs': 0}, 'batterie.packs'),
                ({'heures_charge': [25]}, 'batterie.heures_charge'),
                ({'inconnu': 1}, 'batterie.inconnu')):
            with self.subTest(champ=champ):
                with self.assertRaises(EntreeInvalide) as refus:
                    enregistrer_entree(self.calepinage, {'batterie': saisie})
                self.assertEqual(refus.exception.champ, champ)
        with self.assertRaises(EntreeInvalide) as refus:
            enregistrer_entree(self.calepinage,
                               {'hors_reseau': {'jours_autonomie': -1}})
        self.assertEqual(refus.exception.champ,
                         'hors_reseau.jours_autonomie')

    def test_declaration_enregistree_et_relue_telle_quelle(self):
        saisie = {'strategie': 'autoconso', 'packs': 2, 'couplage': 'ac'}

        enregistrer_entree(self.calepinage,
                           {'batterie': saisie,
                            'hors_reseau': {'actif': False}})

        self.calepinage.refresh_from_db()
        stockee = entree_stockee(self.calepinage)
        self.assertEqual(stockee['batterie'], saisie)
        self.assertEqual(stockee['hors_reseau'], {'actif': False})
        self.assertIn(CLE_ENTREE, self.calepinage.resultat)
        # La déclaration n'entre pas dans le document : layout_hash inchangé.
        self.assertNotIn('battery', self.calepinage.roof_layout)
