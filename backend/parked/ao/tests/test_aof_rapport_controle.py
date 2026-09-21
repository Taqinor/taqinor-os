"""AOF148 — le rapport de contrôle prouve CE QU'IL A CONTRÔLÉ.

Trois promesses :
  1. reproductible — deux rendus des mêmes entrées donnent le même HTML ;
  2. l'empreinte du pack est IMPRIMÉE sur la pièce ;
  3. régénérer le pack après le rapport rend celui-ci PÉRIMÉ.

Plus l'archivage : le rapport est rattaché à son dossier par
``records.Attachment`` — aucun nouveau ``FileField`` dans `apps/ao`.

Run :
    python manage.py test apps.ao.tests.test_aof_rapport_controle -v2
"""
from django.test import SimpleTestCase, TestCase

from apps.ao.fabrique.rendus.rapport_controle import (
    archiver_rapport, construire_rapport, est_perime, rendre_rapport_html,
)

EMPREINTE = 'a1b2c3d4' + 'f' * 56
HORODATAGE = '01/08/2026 14:32'

CONTROLES = [
    {'code': 'MONTANT_UNIQUE', 'severite': 'information',
     'message': 'Montant identique sur toutes les pièces.', 'objet': '',
     'bloquant': False},
    {'code': 'LETTRES_CHIFFRES', 'severite': 'bloquant',
     'message': 'Arrêté en lettres divergent du total en chiffres.',
     'objet': 'bordereau', 'bloquant': True},
    {'code': 'FICHE_ORPHELINE', 'severite': 'avertissement',
     'message': "Fiche technique sans équipement actif.", 'objet': 'annexe 4',
     'bloquant': False},
]


def rapport(controles=None, **surcharges):
    parametres = {
        'empreinte_pack': EMPREINTE,
        'horodatage': HORODATAGE,
        'reference_dossier': 'AODOS-2026-08-0001',
    }
    parametres.update(surcharges)
    return construire_rapport(
        CONTROLES if controles is None else controles, **parametres)


class CompositionTest(SimpleTestCase):
    def test_le_verdict_suit_les_bloquants(self):
        self.assertEqual(rapport()['verdict'], 'REFUSÉ')
        propres = [c for c in CONTROLES if not c['bloquant']]
        self.assertEqual(rapport(propres)['verdict'], 'CONFORME')

    def test_les_severites_sont_comptees(self):
        compte = {bloc['severite']: bloc['nombre']
                  for bloc in rapport()['par_severite']}
        self.assertEqual(compte['bloquant'], 1)
        self.assertEqual(compte['avertissement'], 1)
        self.assertEqual(compte['information'], 1)
        self.assertEqual(rapport()['total'], 3)

    def test_sans_empreinte_le_rapport_est_refuse(self):
        with self.assertRaises(ValueError) as capture:
            construire_rapport(CONTROLES, empreinte_pack='',
                               horodatage=HORODATAGE)
        self.assertIn('prouverait rien', str(capture.exception))

    def test_sans_horodatage_le_rapport_est_refuse(self):
        with self.assertRaises(ValueError):
            construire_rapport(CONTROLES, empreinte_pack=EMPREINTE,
                               horodatage='')

    def test_les_pieces_hors_controle_sont_comptees_et_nommees(self):
        resultat = rapport(pieces_hors_controle=[
            {'code': '08', 'libelle': 'Caution bancaire',
             'motif': 'fournie par la banque'},
        ])
        self.assertEqual(resultat['nombre_hors_controle'], 1)
        html = rendre_rapport_html(resultat)
        self.assertIn('Caution bancaire', html)
        self.assertIn('fournie par la banque', html)


class ReproductibiliteTest(SimpleTestCase):
    def test_deux_rendus_identiques_donnent_le_meme_html(self):
        self.assertEqual(rendre_rapport_html(rapport()),
                         rendre_rapport_html(rapport()))

    def test_aucun_horodatage_implicite_n_est_pris(self):
        """Le module ne lit jamais l'heure : elle est FOURNIE."""
        premier = rendre_rapport_html(rapport())
        second = rendre_rapport_html(rapport(horodatage='02/08/2026 09:00'))
        self.assertNotEqual(premier, second)
        self.assertIn('01/08/2026 14:32', premier)


class EmpreinteEtPeremptionTest(SimpleTestCase):
    def test_l_empreinte_du_pack_est_imprimee(self):
        html = rendre_rapport_html(rapport())
        self.assertIn(EMPREINTE, html)

    def test_un_pack_regenere_perime_le_rapport(self):
        resultat = rapport()
        self.assertFalse(est_perime(resultat, EMPREINTE))
        # Le pack est régénéré : nouvelle empreinte, même papier.
        self.assertTrue(est_perime(resultat, 'z' * 64))

    def test_une_empreinte_absente_perime_aussi(self):
        self.assertTrue(est_perime(rapport(), ''))
        self.assertTrue(est_perime({}, EMPREINTE))


class ArchivageTest(TestCase):
    """Le rapport est livré par ``records.Attachment`` — pas de FileField."""

    def test_le_rapport_est_rattache_a_son_dossier(self):
        from apps.ao.models import AppelOffre
        from authentication.models import Company

        company = Company.objects.create(nom='AOF148 Co', slug='aof148-co')
        appel = AppelOffre.objects.create(
            company=company, reference='AO-148-1', objet='Rapport')
        piece = archiver_rapport(
            appel, cle_objet='ao/1/AODOS-1/RC/a-a1b2c3d4.pdf',
            nom='rapport_controle.pdf', taille=1234, company=company)
        self.assertEqual(piece.object_id, appel.pk)
        self.assertEqual(piece.company, company)
        self.assertEqual(piece.mime, 'application/pdf')
        # La clé porte l'empreinte : deux rapports ne s'écrasent jamais.
        self.assertIn('a1b2c3d4', piece.file_key)

    def test_la_societe_est_deduite_de_la_cible_si_absente(self):
        from apps.ao.models import AppelOffre
        from authentication.models import Company

        company = Company.objects.create(nom='AOF148 Bis', slug='aof148-bis')
        appel = AppelOffre.objects.create(
            company=company, reference='AO-148-2', objet='Rapport')
        piece = archiver_rapport(appel, cle_objet='k', nom='r.pdf')
        self.assertEqual(piece.company, company)
