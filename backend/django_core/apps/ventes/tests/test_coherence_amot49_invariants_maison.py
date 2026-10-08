"""AMOT49 (C-AMOT-038) — règles nocturnes des invariants maison
``DOC_RENDU_SANS_MARGE`` et ``DOC_POMPAGE_SANS_ONDULEUR_BATTERIE`` + le
tableau ``INVARIANTS_MAISON → règle`` testé (gouvernance).

Rejoue VB (registre sans aucune règle marge/pompage).

Test-du-test : retirer ``DOC_RENDU_SANS_MARGE`` du registre ⇒
``test_gouvernance`` la nomme.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.coherence import regles_invariants as RI
from apps.ventes.coherence.registre import REGISTRE, charger_regles


class _Ctx:
    def __init__(self, data):
        self._data = data

    def donnees_devis(self, devis):
        return self._data


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


def _devis(mode='residentiel', prix_achat=None):
    lignes = []
    if prix_achat is not None:
        lignes.append(SimpleNamespace(
            produit=SimpleNamespace(prix_achat=prix_achat)))
    return SimpleNamespace(pk=1, reference='DEV-AMOT49', company_id=1,
                           mode_installation=mode, lignes=_Lignes(lignes))


class InvariantsMaisonTests(SimpleTestCase):
    def setUp(self):
        charger_regles()

    def _run(self, regle_id, devis, data):
        regle = REGISTRE[regle_id]
        return regle.check(regle, devis, _Ctx(data))

    def test_regles_enregistrees(self):
        self.assertIn('DOC_RENDU_SANS_MARGE', REGISTRE)
        self.assertIn('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE', REGISTRE)

    def test_cle_prix_achat_injectee(self):
        data = {'all_items': [{'designation': 'Panneau', 'prix_achat': 900}]}
        v = self._run('DOC_RENDU_SANS_MARGE', _devis(), data)
        self.assertEqual(len(v), 1)
        self.assertIn('prix_achat', v[0].message)

    def test_valeur_egale_a_un_prix_achat(self):
        data = {'all_items': [{'designation': 'Panneau', 'prix_unit_ht': 777.5}]}
        v = self._run('DOC_RENDU_SANS_MARGE', _devis(prix_achat=777.5), data)
        self.assertEqual(len(v), 1)

    def test_rendu_propre(self):
        data = {'all_items': [{'designation': 'Panneau', 'prix_unit_ht': 1100,
                               'quantite': 1.0}],
                'totaux_all': {'ttc': 13200}}
        self.assertEqual(
            self._run('DOC_RENDU_SANS_MARGE', _devis(prix_achat=1), data), [])

    def test_onduleur_dans_un_devis_agricole(self):
        data = {'all_items': [{'designation': 'Onduleur réseau 5kW',
                               'quantite': 1},
                              {'designation': 'Variateur VEICHI 5,5 kW',
                               'quantite': 1}]}
        v = self._run('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
                      _devis('agricole'), data)
        self.assertEqual(len(v), 1)
        self.assertIn('Onduleur', v[0].message)

    def test_pompage_propre_et_residentiel_ignore(self):
        propre = {'all_items': [{'designation': 'Pompe immergée OSP 30',
                                 'quantite': 1}]}
        self.assertEqual(self._run('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
                                   _devis('agricole'), propre), [])
        batterie = {'all_items': [{'designation': 'Batterie 5 kWh',
                                   'quantite': 1}]}
        self.assertEqual(self._run('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
                                   _devis('residentiel'), batterie), [])

    def test_gouvernance(self):
        self.assertEqual(RI.invariants_sans_regle(), [])
