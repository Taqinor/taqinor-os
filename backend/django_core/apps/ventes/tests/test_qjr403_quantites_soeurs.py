"""QJR403 / QJR4-1 — quand la quantité de la ligne panneau dominante est
réécrite, ses quantités SŒURS le sont aussi.

TEST ROUGE D'ABORD. ``pipeline._appliquer_preseance_quantite`` écrivait
``lignes_in[dominante.index]['quantite'] = str(quantite)`` depuis
``taille.nb_panneaux`` — et RIEN d'autre. Or les quantités dérivées du MÊME
compte ne sont posées qu'à la COMPOSITION (``domain/composition`` :
``ajouter('panneau', panneau, nb)``, ``ajouter(role_structure, structure, nb)``,
``ajouter('socle', premier('socle'), nb * 2)``).

Sur le chemin ``MODE_ECRIRE`` — celui auquel ``ecrire_lignes`` est liée — le
devis sortait donc avec un nombre de panneaux À JOUR et une structure / des
socles PÉRIMÉS : N panneaux montés sur M structures. Une nomenclature fausse et
un prix faux (confirmé HAUT par la ronde de vérification V3) : ``ecrire`` et
``reconcilier`` ne se composaient pas.

Le rapport sœur reste celui de la composition (structure = nb, socle = nb × 2)
et n'est JAMAIS recalculé selon une seconde formule :
``composition.quantites_derivees_du_compte`` en est la seule définition, et les
deux chemins la consomment.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr403_quantites_soeurs"
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.composition import quantites_derivees_du_compte
from apps.ventes.domain.pipeline import _appliquer_preseance_quantite
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


def _specs(nb_panneaux):
    """Les specs de l'écrivain pour un kit composé à ``nb_panneaux``."""
    derivees = quantites_derivees_du_compte(nb_panneaux)
    return [
        {'designation': 'Onduleur réseau Huawei 10kW Triphasé',
         'quantite': '1', 'prix_unitaire': '16666.67', 'ordre': 0},
        {'designation': 'Panneau Canadian Solar 710W',
         'quantite': str(nb_panneaux), 'prix_unitaire': '1166.67',
         'ordre': 1},
        {'designation': 'Structure acier',
         'quantite': str(derivees['structure']), 'prix_unitaire': '416.67',
         'ordre': 2},
        {'designation': 'Socle béton',
         'quantite': str(derivees['socle']), 'prix_unitaire': '120',
         'ordre': 3},
        {'designation': 'Installation', 'quantite': '1',
         'prix_unitaire': '5000', 'ordre': 4},
    ]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._seq = 0

    def _devis(self, cible=None):
        self._seq += 1
        devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Panneau Canadian Solar 710W', '10', '1166.67')],
            reference='DEV-QJR403-%04d' % self._seq)
        if cible is not None:
            from apps.ventes.domain import overrides as registre
            registre.ecrire_colonne(
                devis,
                registre.fusionner(
                    devis, {'taille.nb_panneaux': {'valeur': cible}},
                    utilisateur=self.user))
        return devis


class LesSoeursSuiventLaDominante(_Base):

    def test_structure_et_socle_suivent_le_nouveau_compte(self):
        """ROUGE AVANT : la structure gardait N et le socle N × 2."""
        specs = _specs(10)
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(par_designation['Panneau Canadian Solar 710W'], '14')
        self.assertEqual(par_designation['Structure acier'], '14')
        self.assertEqual(par_designation['Socle béton'], '28')

    def test_les_lignes_etrangeres_au_compte_ne_bougent_pas(self):
        specs = _specs(10)
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(
            par_designation['Onduleur réseau Huawei 10kW Triphasé'], '1')
        self.assertEqual(par_designation['Installation'], '1')

    def test_une_soeur_verrouillee_reste_souveraine(self):
        """D12 — ``quantite_manuelle`` est la quantité TAPÉE par le vendeur."""
        specs = _specs(10)
        for spec in specs:
            if spec['designation'] == 'Socle béton':
                spec['quantite_manuelle'] = True
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(par_designation['Structure acier'], '14')
        self.assertEqual(par_designation['Socle béton'], '20')


class SansSurchargeRienNeBouge(_Base):
    """Un devis dont la quantité dominante n'est PAS surchargée est
    inchangé — au centime comme à l'octet."""

    def test_les_specs_sont_identiques(self):
        specs = _specs(10)
        avant = [dict(spec) for spec in specs]
        _appliquer_preseance_quantite(self._devis(), specs)
        self.assertEqual(specs, avant)

    def test_une_cible_egale_au_compte_ne_reecrit_rien(self):
        specs = _specs(10)
        avant = [dict(spec) for spec in specs]
        _appliquer_preseance_quantite(self._devis(cible=10), specs)
        self.assertEqual(specs, avant)


class UneSeuleDefinitionDuRapportSoeur(SimpleTestCase):
    """La composition et le pipeline lisent LA MÊME définition."""

    def test_le_rapport_est_celui_de_la_composition(self):
        for nb in (0, 1, 7, 14, 26):
            self.assertEqual(quantites_derivees_du_compte(nb),
                             {'structure': nb, 'socle': nb * 2})

    def test_une_valeur_illisible_ne_fabrique_aucune_quantite(self):
        self.assertEqual(quantites_derivees_du_compte(None),
                         {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte('abc'),
                         {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte(Decimal('-3')),
                         {'structure': 0, 'socle': 0})
