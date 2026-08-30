# -*- coding: utf-8 -*-
"""QJR137 — le rendement aller-retour batterie est SOURCÉ, ou DÉCLARÉ.

``quote_engine.pricing.BATTERY_ROUNDTRIP = 0.90`` était un forfait de code que
rien ne pouvait sourcer, alors qu'il borne ``restitue_kwh`` du simulateur →
``auto_jour_avec`` → ``bareme.economie_deux_factures_mad`` : **l'économie
« avec batterie » montrée au client**. Contraste relevé par l'audit QJR79 : la
CAPACITÉ, elle, était bien lue sur la fiche — la profondeur de décharge était
sourcée, le rendement non, et aucun champ ne pouvait le porter.

``FicheTechnique.bat_rendement_ar_pct`` (migration 0136, additive) le porte
désormais. Les deux branches sont épinglées ici :

* PUBLIÉ → la valeur de la fiche est appliquée, elle voyage dans le bloc
  d'étude, et les hypothèses affichées disent « valeur publiée sur la fiche » ;
* NON PUBLIÉ → l'hypothèse de référence 0,90 s'applique, la forme du bloc
  d'étude ne bouge PAS (contrat ``CLES_RACINE_HISTORIQUES``) et les hypothèses
  affichées DISENT que c'est une hypothèse.

Tests purs — aucune base, aucun réseau (table PVGIS de référence Casablanca).
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH
from apps.ventes.quote_engine.pricing import (
    BATTERY_ROUNDTRIP,
    cashflow_assumptions,
)
from apps.stock.selectors import specs_for_produit


# ── Doubles de test : une fiche batterie minimale, comme ``specs_for_produit``
# la lit (elle accède aux champs PV5 en direct, aux champs récents par getattr).
class _FausseFiche:
    type_fiche = 'batterie'

    def __init__(self, rendement_pct=None):
        self.bat_kwh_nominal = Decimal('5.12')
        self.bat_kwh_usable = Decimal('4.60')
        self.bat_dod_pct = Decimal('90.0')
        self.bat_v_nominal = Decimal('51.2')
        self.bat_max_charge_kw = None
        self.bat_max_decharge_kw = None
        self.bat_max_modules_par_banc = None
        self.bat_rendement_ar_pct = rendement_pct


class _FauxProduit:
    def __init__(self, fiche=None):
        self.fiche_technique = fiche


class _FausseLigne:
    def __init__(self, produit, quantite=1, designation='Batterie 5 kWh'):
        self.produit = produit
        self.quantite = quantite
        self.designation = designation


def _ligne(rendement_pct=None, **kwargs):
    return _FausseLigne(_FauxProduit(_FausseFiche(rendement_pct)), **kwargs)


class SelecteurStockTests(SimpleTestCase):
    """Le champ traverse la frontière cross-app par le sélecteur de ``stock``."""

    def test_le_selecteur_publie_le_rendement_quand_la_fiche_le_porte(self):
        specs = specs_for_produit(_FauxProduit(_FausseFiche(Decimal('95.0'))))
        self.assertEqual(specs['rendement_ar_pct'], Decimal('95.0'))

    def test_une_fiche_muette_omet_la_cle(self):
        specs = specs_for_produit(_FauxProduit(_FausseFiche(None)))
        self.assertNotIn('rendement_ar_pct', specs)
        # ... et le reste du bloc batterie est inchangé.
        self.assertEqual(specs['kwh_usable'], Decimal('4.60'))


class LectureDesLignesTests(SimpleTestCase):
    """``rendement_batterie_des_lignes`` : prouvé, ou rien."""

    def test_une_fiche_publiee_est_lue(self):
        res = EH.rendement_batterie_des_lignes(
            [_ligne(Decimal('95.0'))], roles=['batterie'])
        self.assertAlmostEqual(res['rendement'], 0.95, places=6)
        self.assertEqual(res['source'], EH.RENDEMENT_SOURCE_FICHE)

    def test_deux_fiches_publiees_retiennent_la_plus_basse(self):
        """Un rendement de banque ne se moyenne pas : on borne, prudemment."""
        res = EH.rendement_batterie_des_lignes(
            [_ligne(Decimal('95.0')), _ligne(Decimal('88.0'))],
            roles=['batterie', 'batterie'])
        self.assertAlmostEqual(res['rendement'], 0.88, places=6)

    def test_une_seule_fiche_muette_rend_la_banque_non_prouvee(self):
        res = EH.rendement_batterie_des_lignes(
            [_ligne(Decimal('95.0')), _ligne(None)],
            roles=['batterie', 'batterie'])
        self.assertIsNone(res['rendement'])
        self.assertEqual(res['source'], EH.RENDEMENT_SOURCE_HYPOTHESE)

    def test_aucune_ligne_batterie_rend_l_hypothese(self):
        res = EH.rendement_batterie_des_lignes(
            [_FausseLigne(_FauxProduit(None), designation='Panneau 550 W')],
            roles=['panneau'])
        self.assertIsNone(res['rendement'])
        self.assertEqual(res['source'], EH.RENDEMENT_SOURCE_HYPOTHESE)

    def test_une_ligne_a_quantite_nulle_est_ignoree(self):
        res = EH.rendement_batterie_des_lignes(
            [_ligne(Decimal('95.0'), quantite=0)], roles=['batterie'])
        self.assertIsNone(res['rendement'])

    def test_valeur_aberrante_ne_devient_jamais_un_rendement(self):
        for aberrant in (Decimal('0'), Decimal('-5.0')):
            res = EH.rendement_batterie_des_lignes(
                [_ligne(aberrant)], roles=['batterie'])
            self.assertIsNone(res['rendement'], msg=str(aberrant))

    def test_lignes_illisibles_ne_levent_jamais(self):
        res = EH.rendement_batterie_des_lignes(None)
        self.assertIsNone(res['rendement'])
        self.assertEqual(res['source'], EH.RENDEMENT_SOURCE_HYPOTHESE)


class MoteurHoraireTests(SimpleTestCase):
    """Les deux branches, jusqu'à l'économie « avec batterie »."""

    VILLE = 'Casablanca'

    def _conso(self, mad=2500):
        conso, _source, _detail = EH.profil_depuis_factures(
            facture_hiver_mad=mad)
        return conso

    def _etude(self, **extra):
        base = dict(kwc=8.0, conso_kwh_mensuelles=self._conso(),
                    ville=self.VILLE, occupation=CJ.OCCUPATION_PRESENCE,
                    batterie_kwh_utile=10.0)
        base.update(extra)
        return EH.calculer_etude_horaire(**base)

    def test_le_rendement_publie_change_l_economie_avec_batterie(self):
        bas = self._etude(batterie_rendement=0.70)
        haut = self._etude(batterie_rendement=0.99)
        self.assertIsNotNone(bas)
        self.assertIsNotNone(haut)
        self.assertGreater(haut['annuel']['economie_avec_mad'],
                           bas['annuel']['economie_avec_mad'])
        # L'option SANS batterie ne bouge pas d'un centime : le rendement ne
        # borne que ce qui transite par la batterie.
        self.assertEqual(haut['annuel']['economie_sans_mad'],
                         bas['annuel']['economie_sans_mad'])

    def test_le_rendement_publie_voyage_avec_sa_source(self):
        etude = self._etude(batterie_rendement=0.95,
                            batterie_rendement_source=EH.RENDEMENT_SOURCE_FICHE)
        self.assertEqual(etude['rendement_batterie'], 0.95)
        self.assertEqual(etude['rendement_batterie_source'],
                         EH.RENDEMENT_SOURCE_FICHE)

    def test_sans_rendement_publie_la_forme_du_bloc_ne_bouge_pas(self):
        """Le parc de devis déjà calculé garde sa forme À L'OCTET."""
        etude = self._etude()
        self.assertNotIn('rendement_batterie', etude)
        self.assertNotIn('rendement_batterie_source', etude)

    def test_sans_rendement_publie_le_resultat_est_celui_d_avant(self):
        """Le repli applique EXACTEMENT ``BATTERY_ROUNDTRIP``, comme avant."""
        implicite = self._etude()
        explicite = self._etude(batterie_rendement=BATTERY_ROUNDTRIP,
                                batterie_rendement_source=None)
        # Seules les deux clés additives distinguent les deux blocs.
        explicite.pop('rendement_batterie', None)
        explicite.pop('rendement_batterie_source', None)
        self.assertEqual(implicite, explicite)

    def test_un_rendement_aberrant_retombe_sur_l_hypothese(self):
        for aberrant in (0.0, -0.5, 1.5, None, 'x'):
            etude = self._etude(batterie_rendement=aberrant)
            self.assertNotIn('rendement_batterie', etude, msg=repr(aberrant))


class HypothesesAffichees(SimpleTestCase):
    """« mention d'hypothèse quand le repli s'applique » — la note le DIT."""

    def _note_stockage(self, **kwargs):
        notes = cashflow_assumptions(stockage=True, **kwargs)['notes']
        return next(n for n in notes if 'aller-retour' in n)

    def test_le_repli_est_annonce_comme_une_hypothese(self):
        note = self._note_stockage()
        self.assertIn('hypothèse de référence', note)
        self.assertIn('ne publie pas', note)
        self.assertIn(str(round(BATTERY_ROUNDTRIP * 100)), note)

    def test_une_valeur_publiee_est_annoncee_comme_telle(self):
        note = self._note_stockage(
            battery_roundtrip=0.95,
            battery_roundtrip_source='fiche:bat_rendement_ar_pct')
        self.assertIn('publiée sur la fiche', note)
        self.assertNotIn('hypothèse de référence', note)
        self.assertIn('95', note)

    def test_le_bloc_dit_la_provenance_et_le_pourcentage_applique(self):
        publie = cashflow_assumptions(
            stockage=True, battery_roundtrip=0.95,
            battery_roundtrip_source='fiche:bat_rendement_ar_pct')
        self.assertTrue(publie['battery_roundtrip_publie'])
        self.assertEqual(publie['battery_roundtrip_pct'], 95)
        self.assertEqual(publie['battery_roundtrip_source'],
                         'fiche:bat_rendement_ar_pct')

        repli = cashflow_assumptions(stockage=True)
        self.assertFalse(repli['battery_roundtrip_publie'])
        self.assertEqual(repli['battery_roundtrip_pct'],
                         round(BATTERY_ROUNDTRIP * 100))
        self.assertEqual(repli['battery_roundtrip_source'],
                         'hypothese:pricing.BATTERY_ROUNDTRIP')

    def test_une_valeur_illisible_retombe_sur_l_hypothese_declaree(self):
        for aberrant in (0, -0.5, 1.5, 'x', None):
            bloc = cashflow_assumptions(stockage=True,
                                        battery_roundtrip=aberrant)
            self.assertFalse(bloc['battery_roundtrip_publie'],
                             msg=repr(aberrant))
            self.assertEqual(bloc['battery_roundtrip_pct'],
                             round(BATTERY_ROUNDTRIP * 100))

    def test_sans_stockage_aucune_note_de_rendement(self):
        notes = cashflow_assumptions(stockage=False, battery_roundtrip=0.95)
        self.assertFalse([n for n in notes['notes'] if 'aller-retour' in n])
        self.assertFalse(notes['battery_roundtrip_applique'])
