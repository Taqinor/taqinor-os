"""AOF159 — les six cibles de la cascade sont un REGISTRE, pas une mémoire.

Trois promesses :
  1. ajouter au gabarit une pièce qui porte un montant SANS la déclarer cible
     fait rougir ce test — c'est le seul mécanisme qui survit à l'ajout d'une
     dixième pièce dans six mois ;
  2. un changement de prix PÉRIME les six cibles et refuse « prêt à déposer » ;
  3. l'historique restitue les deltas du cas réel :
     5 413 680 → 5 219 280 → 4 999 920 TTC.

Run :
    python manage.py test apps.ao.tests.test_aof_propagation -v2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ao.fabrique.propagation import (
    CIBLES_CASCADE, CibleNonDeclaree, DepotRefuse, codes_cibles,
    historique_deltas, marquer_perimes, verifier_pret_a_deposer,
    verifier_registre,
)

EMPREINTE_V3 = 'c' * 64
EMPREINTE_V2 = 'b' * 64


def gabarit_reel():
    """Les pièces du pack FRDISI, avec le drapeau « porte un montant »."""
    return [
        {'code': '00', 'libelle': 'Checklist partenaire',
         'porte_montant': True},
        {'code': '01', 'libelle': 'Lettre de soumission',
         'porte_montant': True},
        {'code': '02', 'libelle': 'Mémoire technique', 'porte_montant': True},
        {'code': '03', 'libelle': "Acte d'engagement", 'porte_montant': True},
        {'code': '04', 'libelle': 'Bordereau des prix', 'porte_montant': True},
        {'code': '05', 'libelle': 'Simulation 25 ans', 'porte_montant': True},
        {'code': '06', 'libelle': 'Planches A3', 'porte_montant': False},
        {'code': '07', 'libelle': 'Annexe fiches techniques',
         'porte_montant': False},
        {'code': '08', 'libelle': 'Dossier administratif',
         'porte_montant': False},
    ]


def artefacts(empreinte=EMPREINTE_V3):
    return [{'code': cible['code'], 'libelle': cible['libelle'],
             'empreinte_cascade': empreinte} for cible in CIBLES_CASCADE]


class RegistreTest(SimpleTestCase):
    def test_les_six_cibles_sont_declarees(self):
        self.assertEqual(len(CIBLES_CASCADE), 6)
        self.assertEqual(codes_cibles(),
                         {'00', '01', '02', '03', '04', '05'})

    def test_le_gabarit_reel_passe_le_registre(self):
        self.assertTrue(verifier_registre(gabarit_reel()))

    def test_une_piece_chiffree_non_declaree_fait_rougir(self):
        """LE test qui empêche la liste de vieillir en silence."""
        gabarit = gabarit_reel()
        gabarit.append({'code': '10', 'libelle': 'Décomposition du prix global',
                        'porte_montant': True})
        with self.assertRaises(CibleNonDeclaree) as capture:
            verifier_registre(gabarit)
        self.assertIn('10', str(capture.exception))
        self.assertIn('Décomposition du prix global', str(capture.exception))

    def test_une_piece_sans_montant_n_a_pas_a_etre_declaree(self):
        gabarit = gabarit_reel()
        gabarit.append({'code': '11', 'libelle': 'Attestation de visite',
                        'porte_montant': False})
        self.assertTrue(verifier_registre(gabarit))


class PeremptionTest(SimpleTestCase):
    def test_un_changement_de_prix_perime_les_six_cibles(self):
        marques = marquer_perimes(artefacts(EMPREINTE_V2), EMPREINTE_V3)
        self.assertEqual(len(marques), 6)
        self.assertTrue(all(m['perime'] for m in marques))

    def test_les_cibles_a_jour_ne_sont_pas_perimees(self):
        marques = marquer_perimes(artefacts(EMPREINTE_V3), EMPREINTE_V3)
        self.assertFalse(any(m['perime'] for m in marques))

    def test_marquer_ne_mute_pas_les_entrees_d_origine(self):
        origine = artefacts(EMPREINTE_V2)
        marquer_perimes(origine, EMPREINTE_V3)
        self.assertTrue(all('perime' not in a for a in origine))

    def test_le_depot_est_refuse_tant_qu_une_cible_est_perimee(self):
        entrees = artefacts(EMPREINTE_V3)
        entrees[2]['empreinte_cascade'] = EMPREINTE_V2
        with self.assertRaises(DepotRefuse) as capture:
            verifier_pret_a_deposer(entrees, EMPREINTE_V3)
        self.assertIn('périmées', str(capture.exception))
        self.assertIn(entrees[2]['code'], str(capture.exception))

    def test_une_cible_ABSENTE_refuse_aussi_le_depot(self):
        """Une cible absente ne déclenche aucun signal : pire que périmée."""
        entrees = [a for a in artefacts() if a['code'] != '03']
        with self.assertRaises(DepotRefuse) as capture:
            verifier_pret_a_deposer(entrees, EMPREINTE_V3)
        self.assertIn('absentes', str(capture.exception))
        self.assertIn('03', str(capture.exception))

    def test_six_cibles_a_jour_laissent_passer(self):
        marques = verifier_pret_a_deposer(artefacts(), EMPREINTE_V3)
        self.assertEqual(len(marques), 6)


def versions_reelles():
    return [
        {'version': 1, 'date': '2026-07-20', 'motif': 'offre initiale',
         'total_ttc': Decimal('5413680'),
         'lignes': {'01': Decimal('1800000'), '03': Decimal('900000'),
                    '13': Decimal('300000')}},
        {'version': 2, 'date': '2026-07-24', 'motif': 'remise commerciale',
         'total_ttc': Decimal('5219280'),
         'lignes': {'01': Decimal('1700000'), '03': Decimal('880000'),
                    '13': Decimal('300000')}},
        {'version': 3, 'date': '2026-07-27',
         'motif': 'bascule batterie 2 800 → 2 600',
         'total_ttc': Decimal('4999920'),
         'lignes': {'01': Decimal('1652000'), '03': Decimal('748800'),
                    '13': Decimal('261800')}},
    ]


class HistoriqueTest(SimpleTestCase):
    def test_les_deltas_du_cas_reel_sont_restitues(self):
        transitions = historique_deltas(versions_reelles())
        self.assertEqual(len(transitions), 2)
        self.assertEqual(transitions[0]['total_avant'], Decimal('5413680'))
        self.assertEqual(transitions[0]['total_apres'], Decimal('5219280'))
        self.assertEqual(transitions[0]['delta_total'], Decimal('-194400'))
        self.assertEqual(transitions[1]['total_apres'], Decimal('4999920'))
        self.assertEqual(transitions[1]['delta_total'], Decimal('-219360'))

    def test_le_mouvement_total_du_dossier_est_lisible(self):
        transitions = historique_deltas(versions_reelles())
        cumul = sum((t['delta_total'] for t in transitions), Decimal('0'))
        self.assertEqual(cumul, Decimal('4999920') - Decimal('5413680'))

    def test_les_deltas_par_ligne_sont_tries_par_ampleur(self):
        transitions = historique_deltas(versions_reelles())
        deuxieme = transitions[1]
        self.assertEqual([d['numero'] for d in deuxieme['lignes']],
                         ['03', '01', '13'])
        self.assertEqual(deuxieme['lignes'][0]['delta'], Decimal('-131200'))

    def test_une_ligne_inchangee_n_apparait_pas_dans_le_delta(self):
        transitions = historique_deltas(versions_reelles())
        premiere = transitions[0]
        self.assertNotIn('13', [d['numero'] for d in premiere['lignes']])

    def test_le_motif_de_chaque_mouvement_est_porte(self):
        transitions = historique_deltas(versions_reelles())
        self.assertIn('bascule batterie', transitions[1]['motif'])

    def test_une_seule_version_ne_produit_aucune_transition(self):
        self.assertEqual(historique_deltas(versions_reelles()[:1]), [])
        self.assertEqual(historique_deltas([]), [])
