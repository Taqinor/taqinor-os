"""AMOT31 (C-AMOT-032) — le moteur de dimensionnement ne compte que les
lignes VENDUES (``lignes_vendues(devis, option)`` = ``compte_dans_totaux`` +
variante) : une ligne optionnelle « Batterie 5 kWh » ne change aucune
capacité, aucun module, aucun facteur de remise, et « Appliquer » ne l'écrit
jamais.

Rejoue VB (devis 48 sans batterie + option batterie : ``cap 5.0``,
``module 5.0``, matériel batterie, ``modules 1``).

Test-du-test : retirer le filtre ``compte_dans_totaux`` de ``lignes_vendues``
⇒ ``test_option_ne_change_rien`` échoue.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.domain import dimensionnement_devis as DD


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


def _ligne(designation, qte, pu, *, optionnelle=False, variante='',
           remise='0'):
    return SimpleNamespace(
        designation=designation, quantite=Decimal(qte),
        prix_unitaire=Decimal(pu), remise=Decimal(remise),
        optionnelle=optionnelle, variante=variante, est_ligne_produit=True,
        compte_dans_totaux=not optionnelle, produit=None, type_ligne='produit')


BASE = [_ligne('Panneau mono 550W', '10', '1100'),
        _ligne('Onduleur réseau Huawei 5kW', '1', '8000')]
OPTION_BATTERIE = _ligne('Batterie 5 kWh', '1', '15000', optionnelle=True)


def _devis(lignes, regles=2, remise_globale='10'):
    return SimpleNamespace(lignes=_Lignes(lignes), regles_calcul=regles,
                           remise_globale=Decimal(remise_globale),
                           reference='DEV-AMOT31')


class LignesVenduesTests(SimpleTestCase):
    def test_option_ne_change_rien(self):
        sans = _devis(BASE)
        avec_option = _devis(BASE + [OPTION_BATTERIE])
        self.assertEqual(DD.lignes_vendues(avec_option), BASE)
        self.assertIsNone(DD.capacite_batterie_des_lignes(avec_option))
        self.assertEqual(DD.facteur_remise_du_devis(avec_option),
                         DD.facteur_remise_du_devis(sans))
        self.assertIsNone(DD.module_batterie_du_devis(avec_option))

    def test_variante(self):
        lignes = BASE + [_ligne('Batterie 5 kWh', '1', '15000',
                                variante='avec')]
        devis = _devis(lignes)
        self.assertEqual(len(DD.lignes_vendues(devis, 'sans')), 2)
        self.assertEqual(len(DD.lignes_vendues(devis, 'avec')), 3)

    def test_regles_d_origine_lecture_d_hier(self):
        devis = _devis(BASE + [OPTION_BATTERIE], regles=1)
        self.assertIn(OPTION_BATTERIE, DD._lignes_produit_du_devis(devis))
