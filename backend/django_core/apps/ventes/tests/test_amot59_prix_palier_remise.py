"""AMOT59 (C-AMOT-035) — le curseur batterie de la page client publie le prix
de VENTE d'un palier (coût catalogue × facteur de remise du devis, arrondi au
palier ``PAS_ARRONDI_DEVIS``) par UNE fonction ``prix_client_composition``
partagée avec l'échelle et les cartes Éco/Max ; payback recalculé sur ce prix.

Rejoue VB (devis 47, ``remise_globale = 10`` : curseur ``cout_ttc`` 49 082,08
avant ET après remise, échelle 49 322,08 → 44 389,87).

Test-du-test : remettre ``'cout_ttc': palier.get('cout_ttc')`` brut ⇒
``test_curseur_prix_remise`` échoue.
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.domain import dimensionnement_devis as DD
from apps.ventes.public.payload_batterie import _balayage_stockage_publique
from apps.ventes.quote_engine.pricing import payback_publiable


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


def _devis(remise='10', regles=2):
    ligne = SimpleNamespace(
        designation='Panneau mono 550W', quantite=Decimal('10'),
        prix_unitaire=Decimal('1000'), remise=Decimal('0'), variante='',
        optionnelle=False, est_ligne_produit=True, compte_dans_totaux=True)
    return SimpleNamespace(lignes=_Lignes([ligne]), regles_calcul=regles,
                           remise_globale=Decimal(remise),
                           reference='DEV-AMOT59')


def _dimensionnement(cout=49322.08, economie=6000.0):
    return {'recommandation_avec': {'balayage_stockage': [{
        'capacite_kwh': 5.0, 'cout_ttc': cout, 'economie_mad': economie,
        'payback_annees': round(cout / economie, 2),
        'lignes_batterie': [{'quantite': 1}],
        'remplissage': {'moyen': 0.9}}]}}


class PrixPalierRemiseTests(SimpleTestCase):
    def test_fonction_partagee(self):
        self.assertEqual(DD.prix_client_au_facteur(49322.08, 0.9), 44300.0)
        self.assertEqual(DD.prix_client_composition(49322.08, _devis()),
                         44300.0)
        self.assertEqual(DD.prix_client_composition(49322.08, _devis('0')),
                         49300.0)

    def test_curseur_prix_remise(self):
        bloc = _balayage_stockage_publique(_dimensionnement(), _devis())
        palier = bloc['paliers'][0] if isinstance(bloc, dict) else bloc[0]
        self.assertEqual(palier['cout_ttc'], 44300.0)
        attendu = payback_publiable(44300.0, 6000.0)
        self.assertEqual(palier['payback_annees'], round(attendu['annees'], 2))

    def test_regles_d_origine_passe_directe(self):
        bloc = _balayage_stockage_publique(_dimensionnement(), _devis(regles=1))
        palier = bloc['paliers'][0] if isinstance(bloc, dict) else bloc[0]
        self.assertEqual(palier['cout_ttc'], 49322.08)
