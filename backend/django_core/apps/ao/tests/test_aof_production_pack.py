"""AOF153 — la production du pack est idempotente et échoue PIÈCE PAR PIÈCE.

Trois promesses :
  1. rejouer la production sur un contexte INCHANGÉ ne refabrique rien — un
     double-clic ou un retry Celery ne produit jamais deux packs ;
  2. changer le contexte change l'empreinte, donc tout se refait ;
  3. une pièce en échec laisse les autres INTACTES, nomme son motif, et
     `complet` reste faux — c'est lui qui interdit de passer « prêt à déposer ».

Plus le suivi : la progression est rapportée pièce par pièce, avec le CODE de
la pièce (un pourcentage seul ne dit pas où ça coince).

Run :
    python manage.py test apps.ao.tests.test_aof_production_pack -v2
"""
from django.test import SimpleTestCase

from apps.ao.tasks import (
    ETAT_ECHOUEE, ETAT_PRODUITE, ETAT_REPRISE, produire_pack,
)

EMPREINTE = 'a' * 64
AUTRE_EMPREINTE = 'b' * 64


class Compteur:
    """Producteur qui compte ses appels — c'est ça, mesurer l'idempotence."""

    def __init__(self, code, artefact=None, casse=False):
        self.code = code
        self.artefact = artefact if artefact is not None else 'pdf-' + code
        self.casse = casse
        self.appels = 0

    def __call__(self):
        self.appels += 1
        if self.casse:
            raise ValueError('gabarit introuvable')
        return self.artefact


def pieces(*compteurs):
    return [{'code': c.code, 'libelle': 'Pièce ' + c.code, 'producteur': c}
            for c in compteurs]


class ProductionNominaleTest(SimpleTestCase):
    def test_toutes_les_pieces_sont_produites_une_fois(self):
        compteurs = [Compteur('01'), Compteur('02'), Compteur('04')]
        rapport = produire_pack(pieces(*compteurs),
                                empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['total'], 3)
        self.assertEqual(rapport['produites'], 3)
        self.assertEqual(rapport['reprises'], 0)
        self.assertTrue(rapport['complet'])
        self.assertTrue(all(c.appels == 1 for c in compteurs))

    def test_chaque_resultat_porte_l_empreinte_qui_l_a_produit(self):
        rapport = produire_pack(pieces(Compteur('01')),
                                empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['resultats'][0]['empreinte'], EMPREINTE)
        self.assertEqual(rapport['resultats'][0]['etat'], ETAT_PRODUITE)

    def test_un_pack_vide_n_est_pas_complet(self):
        rapport = produire_pack([], empreinte_contexte=EMPREINTE)
        self.assertFalse(rapport['complet'])


class IdempotenceTest(SimpleTestCase):
    def test_un_rejeu_a_empreinte_identique_ne_refabrique_rien(self):
        compteurs = [Compteur('01'), Compteur('02')]
        premier = produire_pack(pieces(*compteurs),
                                empreinte_contexte=EMPREINTE)
        deja = {r['code']: {'empreinte': r['empreinte'],
                            'artefact': r['artefact']}
                for r in premier['resultats']}
        second = produire_pack(pieces(*compteurs),
                               empreinte_contexte=EMPREINTE,
                               deja_produites=deja)
        self.assertEqual(second['produites'], 0)
        self.assertEqual(second['reprises'], 2)
        self.assertTrue(second['complet'])
        # Le double-clic n'a PAS relancé les producteurs.
        self.assertTrue(all(c.appels == 1 for c in compteurs))
        self.assertEqual([r['etat'] for r in second['resultats']],
                         [ETAT_REPRISE, ETAT_REPRISE])

    def test_l_artefact_repris_est_l_ancien_pas_un_nouveau(self):
        deja = {'01': {'empreinte': EMPREINTE, 'artefact': 'pdf-original'}}
        rapport = produire_pack(pieces(Compteur('01', artefact='pdf-neuf')),
                                empreinte_contexte=EMPREINTE,
                                deja_produites=deja)
        self.assertEqual(rapport['resultats'][0]['artefact'], 'pdf-original')

    def test_un_contexte_modifie_refabrique_tout(self):
        compteurs = [Compteur('01'), Compteur('02')]
        deja = {c.code: {'empreinte': EMPREINTE, 'artefact': 'vieux'}
                for c in compteurs}
        rapport = produire_pack(pieces(*compteurs),
                                empreinte_contexte=AUTRE_EMPREINTE,
                                deja_produites=deja)
        self.assertEqual(rapport['produites'], 2)
        self.assertEqual(rapport['reprises'], 0)
        self.assertTrue(all(c.appels == 1 for c in compteurs))

    def test_une_piece_neuve_au_milieu_de_reprises(self):
        anciens = [Compteur('01'), Compteur('02')]
        nouveau = Compteur('05')
        deja = {c.code: {'empreinte': EMPREINTE, 'artefact': 'vieux'}
                for c in anciens}
        rapport = produire_pack(pieces(*(anciens + [nouveau])),
                                empreinte_contexte=EMPREINTE,
                                deja_produites=deja)
        self.assertEqual(rapport['reprises'], 2)
        self.assertEqual(rapport['produites'], 1)
        self.assertEqual([c.appels for c in anciens], [0, 0])
        self.assertEqual(nouveau.appels, 1)


class EchecParPieceTest(SimpleTestCase):
    def test_une_piece_en_echec_laisse_les_autres_intactes(self):
        bons = [Compteur('01'), Compteur('04')]
        casse = Compteur('02', casse=True)
        rapport = produire_pack(pieces(bons[0], casse, bons[1]),
                                empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['produites'], 2)
        self.assertEqual(len(rapport['echecs']), 1)
        self.assertFalse(rapport['complet'])
        self.assertTrue(all(c.appels == 1 for c in bons))
        etats = {r['code']: r['etat'] for r in rapport['resultats']}
        self.assertEqual(etats, {'01': ETAT_PRODUITE, '02': ETAT_ECHOUEE,
                                 '04': ETAT_PRODUITE})

    def test_le_motif_de_l_echec_est_nomme(self):
        rapport = produire_pack(pieces(Compteur('02', casse=True)),
                                empreinte_contexte=EMPREINTE)
        motif = rapport['echecs'][0]['motif']
        self.assertIn('ValueError', motif)
        self.assertIn('gabarit introuvable', motif)

    def test_une_piece_sans_producteur_est_un_echec_nomme(self):
        rapport = produire_pack([{'code': '07', 'libelle': 'Annexe'}],
                                empreinte_contexte=EMPREINTE)
        self.assertEqual(rapport['echecs'][0]['motif'],
                         'aucun producteur fourni')
        self.assertFalse(rapport['complet'])

    def test_rejouer_apres_un_echec_ne_refait_que_la_piece_fautive(self):
        bon = Compteur('01')
        casse = Compteur('02', casse=True)
        premier = produire_pack(pieces(bon, casse),
                                empreinte_contexte=EMPREINTE)
        deja = {r['code']: {'empreinte': r.get('empreinte'),
                            'artefact': r.get('artefact')}
                for r in premier['resultats'] if r['etat'] == ETAT_PRODUITE}
        repare = Compteur('02')
        second = produire_pack(pieces(bon, repare),
                               empreinte_contexte=EMPREINTE,
                               deja_produites=deja)
        self.assertTrue(second['complet'])
        self.assertEqual(bon.appels, 1)   # jamais refait
        self.assertEqual(repare.appels, 1)


class SuiviTest(SimpleTestCase):
    def test_la_progression_est_rapportee_piece_par_piece_avec_son_code(self):
        vus = []
        produire_pack(pieces(Compteur('01'), Compteur('02'), Compteur('04')),
                      empreinte_contexte=EMPREINTE,
                      progression=lambda faites, total, code: vus.append(
                          (faites, total, code)))
        self.assertEqual(vus, [(1, 3, '01'), (2, 3, '02'), (3, 3, '04')])

    def test_le_journal_trace_chaque_etat(self):
        lignes = []
        deja = {'01': {'empreinte': EMPREINTE, 'artefact': 'x'}}
        produire_pack(pieces(Compteur('01'), Compteur('02', casse=True)),
                      empreinte_contexte=EMPREINTE, deja_produites=deja,
                      journal=lambda code, etat, detail: lignes.append(
                          (code, etat)))
        self.assertEqual(lignes, [('01', ETAT_REPRISE), ('02', ETAT_ECHOUEE)])
