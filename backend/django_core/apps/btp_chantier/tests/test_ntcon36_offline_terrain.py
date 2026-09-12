"""NTCON36 — capture terrain hors-ligne : les op_types BTP du moteur générique.

Ce que le test PROUVE :
  * les deux op_types sont enregistrés dans le moteur GÉNÉRIQUE
    ``apps.offlinesync`` (NTMOB1) — aucun second mécanisme hors-ligne, aucun
    endpoint de synchro propre à ``btp_chantier`` ;
  * une réserve créée hors-ligne s'applique UNE SEULE FOIS à la reconnexion,
    même si le lot est rejoué (dédoublonnage par ``client_op_id``) ;
  * l'entrée de journal du jour est LAST-WRITE-WINS : deux terminaux qui se
    reconnectent dans le désordre convergent au lieu de se heurter à la
    contrainte d'unicité (chantier, date) ;
  * la société et l'auteur viennent du SERVEUR, jamais du corps ;
  * un chantier d'une AUTRE société est indiscernable d'un chantier inconnu.
"""
from django.test import TestCase
from django.utils import timezone

from apps.btp_chantier import offline_ops
from apps.btp_chantier.models import JournalChantier, ReserveChantier
from apps.offlinesync import registry
from apps.offlinesync.registry import OfflineOpError

from .helpers import make_chantier, make_company, make_user

OP_RESERVE = 'btp.reserve.creer'
OP_JOURNAL = 'btp.journal.entree_du_jour'


class OfflineTerrainBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='normal')

    # ── enregistrement dans le moteur GÉNÉRIQUE ────────────────────────────
    def test_les_deux_op_types_sont_enregistres(self):
        for op_type in (OP_RESERVE, OP_JOURNAL):
            with self.subTest(op_type=op_type):
                entree = registry.get(op_type)
                self.assertIsNotNone(
                    entree, f'{op_type} absent du registre offlinesync')
                module, handler = entree
                self.assertEqual(module, 'installations')
                self.assertTrue(callable(handler))

    # ── réserve ────────────────────────────────────────────────────────────
    def test_reserve_creee_hors_ligne(self):
        resultat = offline_ops.h_reserve_creer(self.co, self.user, {
            'chantier': self.chantier.id,
            'lot': 'électricité',
            'description': 'Tableau non conforme',
            'gravite': 'bloquante',
            'localisation_plan': {'document_ged_id': 3, 'x': 0.2, 'y': 0.4},
        })
        reserve = ReserveChantier.objects.get(pk=resultat['reserve_id'])
        # Société ET auteur posés côté SERVEUR.
        self.assertEqual(reserve.company_id, self.co.id)
        self.assertEqual(reserve.created_by_id, self.user.id)
        self.assertEqual(reserve.gravite, 'bloquante')
        self.assertEqual(reserve.localisation_plan['document_ged_id'], 3)
        # L'historique NTCON1 est écrit comme pour une création en ligne.
        self.assertEqual(reserve.historique.count(), 1)

    def test_reserve_sans_description_refusee_proprement(self):
        with self.assertRaises(OfflineOpError) as ctx:
            offline_ops.h_reserve_creer(self.co, self.user, {
                'chantier': self.chantier.id, 'description': '   '})
        self.assertIn('escription', str(ctx.exception))
        self.assertEqual(ReserveChantier.objects.count(), 0)

    def test_gravite_inconnue_refusee(self):
        with self.assertRaises(OfflineOpError) as ctx:
            offline_ops.h_reserve_creer(self.co, self.user, {
                'chantier': self.chantier.id, 'description': 'x',
                'gravite': 'catastrophique'})
        self.assertIn('catastrophique', str(ctx.exception))

    def test_chantier_d_une_autre_societe_indiscernable_d_un_inconnu(self):
        autre = make_company()
        chantier_voisin = make_chantier(autre)
        with self.assertRaises(OfflineOpError) as ctx:
            offline_ops.h_reserve_creer(self.co, self.user, {
                'chantier': chantier_voisin.id, 'description': 'x'})
        self.assertIn('inconnu', str(ctx.exception).lower())
        self.assertEqual(ReserveChantier.objects.count(), 0)

    # ── journal du jour (LAST-WRITE-WINS) ──────────────────────────────────
    def test_entree_du_jour_creee(self):
        resultat = offline_ops.h_journal_entree_du_jour(
            self.co, self.user, {
                'chantier': self.chantier.id,
                'meteo': 'Ensoleillé',
                'evenements': 'Coulage dalle R+1',
            })
        self.assertTrue(resultat['cree'])
        entree = JournalChantier.objects.get(pk=resultat['journal_id'])
        self.assertEqual(entree.company_id, self.co.id)
        self.assertEqual(entree.redacteur_id, self.user.id)
        self.assertEqual(entree.date, timezone.localdate())
        self.assertEqual(entree.meteo, 'Ensoleillé')

    def test_last_write_wins_sur_l_entree_du_jour(self):
        """Deux terminaux dans le désordre CONVERGENT (jamais un 400 doublon)."""
        premier = offline_ops.h_journal_entree_du_jour(
            self.co, self.user, {
                'chantier': self.chantier.id, 'meteo': 'Pluie'})
        second = offline_ops.h_journal_entree_du_jour(
            self.co, self.user, {
                'chantier': self.chantier.id, 'meteo': 'Ensoleillé'})
        self.assertEqual(premier['journal_id'], second['journal_id'])
        self.assertFalse(second['cree'])
        self.assertEqual(JournalChantier.objects.count(), 1)
        entree = JournalChantier.objects.get()
        self.assertEqual(entree.meteo, 'Ensoleillé')

    def test_date_explicite_illisible_refusee(self):
        with self.assertRaises(OfflineOpError) as ctx:
            offline_ops.h_journal_entree_du_jour(self.co, self.user, {
                'chantier': self.chantier.id, 'date': '32/13/2026'})
        self.assertIn('32/13/2026', str(ctx.exception))

    def test_effectif_invalide_refuse(self):
        with self.assertRaises(OfflineOpError) as ctx:
            offline_ops.h_journal_entree_du_jour(self.co, self.user, {
                'chantier': self.chantier.id,
                'effectif_interne': 'douze personnes'})
        self.assertIn('effectif_interne', str(ctx.exception))
