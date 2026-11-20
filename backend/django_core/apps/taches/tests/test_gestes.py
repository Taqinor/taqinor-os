"""TCH33 — Annuler côté serveur : `enregistrer_geste`, `annuler_geste` et les aides `op_*`.

Base requise (`TestCase`) : joué par la CI. Deux sociétés réelles (`'a'`, `'b'`), deux comptes dans
la société A. Chaque test lit l'état STOCKÉ après l'annulation (jamais un espion).
"""
import datetime
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.choix import StatutRappel, StatutTache
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Rappel, Tache
from apps.taches.services.gestes import (
    annuler_geste,
    enregistrer_geste,
    op_champ,
    op_creation,
    op_suppression_douce,
    op_suppression_dure,
    titres_des_gestes,
)
from apps.taches.selectors.base import taches_de
from apps.taches.tests import fabriques
from core.models import DeletionRecord

J = datetime.date(2026, 11, 17)


class GesteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _renommer(self, tache, titre):
        avant = tache.titre
        tache.titre = titre
        tache.save(update_fields=['titre'])
        return op_champ('tache', tache, 'titre', avant)

    # --- Restauration ------------------------------------------------------------------

    def test_restaure_un_champ(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        rendu = annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Avant')
        self.assertEqual(rendu, {'restaurees': [{'objet': 'tache', 'id': tache.pk}],
                                 'conflits': [], 'deja': False})
        geste.refresh_from_db()
        self.assertIsNotNone(geste.annule_le)

    def test_restaure_un_jour_et_une_heure_ensemble(self):
        tache = fabriques.tache(self.u1)
        tache.jour_prevu, tache.heure_debut, tache.moment = J, datetime.time(10, 0), 'matin'
        tache.save()
        ops = [op_champ('tache', tache, 'jour_prevu', None),
               op_champ('tache', tache, 'heure_debut', None),
               op_champ('tache', tache, 'moment', '')]
        geste = enregistrer_geste(self.u1, 'planification', 'Placée à 10:00', ops)
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual((tache.jour_prevu, tache.heure_debut, tache.moment), (None, None, ''))

    def test_deux_ecritures_du_meme_champ_rendent_la_plus_ancienne(self):
        tache = fabriques.tache(self.u1, titre='Un')
        ops = [self._renommer(tache, 'Deux'), self._renommer(tache, 'Trois')]
        geste = enregistrer_geste(self.u1, 'lot', '2 modifiées', ops)
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Un')

    def test_idempotent(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        annuler_geste(self.u1, geste.pk)
        tache.titre = 'Encore'
        tache.save(update_fields=['titre'])
        self.assertEqual(annuler_geste(self.u1, geste.pk),
                         {'restaurees': [], 'conflits': [], 'deja': True})
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Encore')

    # --- Conflits ------------------------------------------------------------------------

    def test_conflit_modifiee_depuis(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        Tache.objects.filter(pk=tache.pk).update(titre='Changée ailleurs')
        rendu = annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Changée ailleurs')
        self.assertEqual(rendu['conflits'], [{'objet': 'tache', 'id': tache.pk, 'raison': 'modifiee_depuis'}])
        self.assertEqual(rendu['restaurees'], [])

    def test_un_conflit_laisse_l_objet_entier(self):
        tache = fabriques.tache(self.u1, titre='Avant', priorite=0)
        tache.titre, tache.priorite = 'Après', 3
        tache.save()
        ops = [op_champ('tache', tache, 'titre', 'Avant'), op_champ('tache', tache, 'priorite', 0)]
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', ops)
        Tache.objects.filter(pk=tache.pk).update(priorite=1)
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual((tache.titre, tache.priorite), ('Après', 1))

    def test_partiel_200(self):
        une, deux = fabriques.tache(self.u1, titre='A'), fabriques.tache(self.u1, titre='B')
        ops = [self._renommer(une, 'A2'), self._renommer(deux, 'B2')]
        geste = enregistrer_geste(self.u1, 'lot', '2 modifiées', ops)
        Tache.objects.filter(pk=deux.pk).update(titre='B3')
        rendu = annuler_geste(self.u1, geste.pk)
        une.refresh_from_db()
        deux.refresh_from_db()
        self.assertEqual((une.titre, deux.titre), ('A', 'B3'))
        self.assertEqual(rendu['restaurees'], [{'objet': 'tache', 'id': une.pk}])
        self.assertEqual([c['id'] for c in rendu['conflits']], [deux.pk])

    def test_nom_repris_depuis_est_un_conflit(self):
        projet = fabriques.projet(self.u1, nom='Alpha')
        projet.nom = 'Beta'
        projet.save(update_fields=['nom'])
        geste = enregistrer_geste(self.u1, 'modification', 'Modifié', [op_champ('projet', projet, 'nom', 'Alpha')])
        fabriques.projet(self.u1, nom='alpha')
        rendu = annuler_geste(self.u1, geste.pk)
        projet.refresh_from_db()
        self.assertEqual(projet.nom, 'Beta')
        self.assertEqual(rendu['conflits'], [{'objet': 'projet', 'id': projet.pk, 'raison': 'nom_pris'}])

    def test_objet_disparu_est_un_conflit(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        tache.soft_delete(self.u1, record=False)
        rendu = annuler_geste(self.u1, geste.pk)
        self.assertEqual(rendu['conflits'], [{'objet': 'tache', 'id': tache.pk, 'raison': 'introuvable'}])

    # --- Liste blanche et propriétaires (invariants 9, 21) -------------------------------

    def test_champ_hors_liste_blanche_ignore(self):
        tache = fabriques.tache(self.u1, titre='Avant', client_id='abc')
        ops = [
            self._renommer(tache, 'Après'),
            {'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'proprietaire',
             'avant': self.voisin.pk, 'apres': self.u1.pk},
            {'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'client_id',
             'avant': 'pirate', 'apres': 'abc'},
            {'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'company',
             'avant': self.b.pk, 'apres': self.a.pk},
        ]
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', ops)
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Avant')
        self.assertEqual((tache.proprietaire_id, tache.client_id, tache.company_id),
                         (self.u1.pk, 'abc', self.a.pk))

    def test_op_champ_refuse_un_champ_hors_liste(self):
        tache = fabriques.tache(self.u1)
        with self.assertRaises(ValueError):
            op_champ('tache', tache, 'proprietaire', self.voisin)
        with self.assertRaises(ValueError):
            op_creation('jeton_acces', tache)

    def test_fk_restauree_reverifiee_meme_proprietaire(self):
        mien = fabriques.projet(self.u1)
        a_lui = fabriques.projet(self.voisin)
        tache = fabriques.tache(self.u1, projet=mien)
        op = {'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'projet',
              'avant': a_lui.pk, 'apres': mien.pk}
        geste = enregistrer_geste(self.u1, 'deplacement', 'Déplacée', [op])
        rendu = annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.projet_id, mien.pk)
        self.assertEqual(rendu['conflits'], [{'objet': 'tache', 'id': tache.pk, 'raison': 'introuvable'}])

    def test_fk_restauree_du_meme_proprietaire(self):
        ancien, nouveau = fabriques.projet(self.u1), fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=ancien)
        tache.projet = nouveau
        tache.save(update_fields=['projet'])
        geste = enregistrer_geste(self.u1, 'deplacement', 'Déplacée',
                                  [op_champ('tache', tache, 'projet', ancien)])
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.projet_id, ancien.pk)

    def test_objet_d_un_autre_compte_jamais_touche(self):
        a_lui = fabriques.tache(self.voisin, titre='À lui')
        op = {'op': 'champ', 'objet': 'tache', 'id': a_lui.pk, 'champ': 'titre',
              'avant': 'Volé', 'apres': 'À lui'}
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [op])
        rendu = annuler_geste(self.u1, geste.pk)
        a_lui.refresh_from_db()
        self.assertEqual(a_lui.titre, 'À lui')
        self.assertEqual(rendu['conflits'][0]['raison'], 'introuvable')

    def test_lien_retire_puis_lien_refuse(self):
        ct = ContentType.objects.get_by_natural_key('crm', 'lead')
        tache = fabriques.tache(self.u1, content_type=ct, object_id=999999, lien_etat='ok')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée',
                                  [{'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'lien',
                                    'avant': None, 'apres': {'cible': 'crm.lead', 'id': 999999}}])
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual((tache.content_type_id, tache.object_id, tache.lien_etat), (None, None, ''))
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée',
                                  [{'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'lien',
                                    'avant': {'cible': 'crm.lead', 'id': 999999}, 'apres': None}])
        rendu = annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertIsNone(tache.content_type_id)
        self.assertEqual(rendu['conflits'][0]['raison'], 'introuvable')

    def _geste_qui_repose(self, tache, lien):
        return enregistrer_geste(self.u1, 'modification', 'Modifiée',
                                 [{'op': 'champ', 'objet': 'tache', 'id': tache.pk, 'champ': 'lien',
                                   'avant': lien, 'apres': None}])

    def test_lien_repose_par_la_porte_cible_visible(self):
        """Le lien reposé est revérifié par `selectors.liens.cible_visible` (portée du compte) : sorti
        de sa portée, il est refusé ; visible, il est reposé `ok` à l'identifiant de la cible."""
        lien = {'cible': 'crm.lead', 'id': 4242}
        tache = fabriques.tache(self.u1)
        with mock.patch('apps.taches.selectors.liens.cible_visible', return_value=False) as porte:
            rendu = annuler_geste(self.u1, self._geste_qui_repose(tache, lien).pk)
        porte.assert_called_once_with(self.u1, 'crm.lead', 4242)
        tache.refresh_from_db()
        self.assertIsNone(tache.content_type_id)
        self.assertEqual(rendu['conflits'][0]['raison'], 'introuvable')
        with mock.patch('apps.taches.selectors.liens.cible_visible', return_value=True):
            annuler_geste(self.u1, self._geste_qui_repose(tache, lien).pk)
        tache.refresh_from_db()
        self.assertEqual((tache.content_type, tache.object_id, tache.lien_etat),
                         (ContentType.objects.get_by_natural_key('crm', 'lead'), 4242, 'ok'))

    # --- Propriétaire du geste, ancienneté ------------------------------------------------

    def test_geste_d_un_autre_compte_404(self):
        tache = fabriques.tache(self.voisin, titre='Avant')
        geste = enregistrer_geste(self.voisin, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        with self.assertRaises(Http404):
            annuler_geste(self.u1, geste.pk)
        with self.assertRaises(Http404):
            annuler_geste(self.ailleurs, geste.pk)
        tache.refresh_from_db()
        self.assertEqual(tache.titre, 'Après')

    def test_geste_de_plus_de_7_jours_404(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = enregistrer_geste(self.u1, 'modification', 'Modifiée', [self._renommer(tache, 'Après')])
        GesteAnnulable.objects.filter(pk=geste.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=8))
        with self.assertRaises(Http404):
            annuler_geste(self.u1, geste.pk)
        with self.assertRaises(Http404):
            annuler_geste(self.u1, 'pas-un-id')

    def test_type_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            enregistrer_geste(self.u1, 'corbeille', 'x', [])

    def test_message_borne_et_societe_du_compte(self):
        geste = enregistrer_geste(self.u1, 'creation', 'x' * 300, [])
        self.assertEqual(len(geste.message), 200)
        self.assertEqual((geste.company_id, geste.proprietaire_id), (self.a.pk, self.u1.pk))

    # --- Créations et suppressions -------------------------------------------------------

    def test_defaire_une_creation_supprime_sans_corbeille(self):
        tache = fabriques.tache(self.u1)
        geste = enregistrer_geste(self.u1, 'creation', 'Ajoutée', [op_creation('tache', tache)])
        rendu = annuler_geste(self.u1, geste.pk)
        tache = Tache.all_objects.get(pk=tache.pk)
        self.assertTrue(tache.is_deleted)
        self.assertFalse(DeletionRecord.objects.filter(object_id=tache.pk).exists())
        self.assertEqual(rendu['restaurees'], [{'objet': 'tache', 'id': tache.pk}])

    def test_projet_ne_vide_supprime_mais_pas_s_il_a_servi(self):
        projet = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=projet)
        geste = enregistrer_geste(self.u1, 'creation', 'Ajoutée',
                                  [op_creation('projet', projet), op_creation('tache', tache)])
        autre = fabriques.tache(self.u1, projet=projet)
        rendu = annuler_geste(self.u1, geste.pk)
        self.assertTrue(Tache.all_objects.get(pk=tache.pk).is_deleted)
        self.assertTrue(Projet.objects.filter(pk=projet.pk).exists())
        self.assertTrue(Tache.objects.filter(pk=autre.pk).exists())
        self.assertEqual(rendu['conflits'], [{'objet': 'projet', 'id': projet.pk, 'raison': 'modifiee_depuis'}])

    def test_defaire_une_suppression_douce_restaure(self):
        tache = fabriques.tache(self.u1)
        tache.soft_delete(self.u1, record=False)
        geste = enregistrer_geste(self.u1, 'suppression', 'Supprimée',
                                  [op_suppression_douce('tache', tache)])
        annuler_geste(self.u1, geste.pk)
        self.assertTrue(Tache.objects.filter(pk=tache.pk).exists())

    def test_projet_et_ses_taches_restaures_en_un_geste(self):
        projet = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=projet)
        tache.soft_delete(self.u1, record=False)
        projet.soft_delete(self.u1, record=False)
        ops = [op_suppression_douce('tache', tache), op_suppression_douce('projet', projet)]
        geste = enregistrer_geste(self.u1, 'suppression', 'Supprimés', ops)
        annuler_geste(self.u1, geste.pk)
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual(tache.projet_id, projet.pk)
        self.assertTrue(Projet.objects.filter(pk=projet.pk).exists())

    def test_tache_restauree_seule_revient_dans_a_trier(self):
        projet = fabriques.projet(self.u1)
        tache = fabriques.tache(self.u1, projet=projet)
        tache.soft_delete(self.u1, record=False)
        projet.soft_delete(self.u1, record=False)
        geste = enregistrer_geste(self.u1, 'suppression', 'Supprimée',
                                  [op_suppression_douce('tache', tache)])
        annuler_geste(self.u1, geste.pk)
        tache = Tache.objects.get(pk=tache.pk)
        self.assertEqual((tache.projet_id, tache.triee_le), (None, None))

    def test_sous_tache_restauree_dont_le_parent_reste_supprime_est_detachee(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        enfant.soft_delete(self.u1, record=False)
        geste = enregistrer_geste(self.u1, 'suppression', 'Supprimée', [op_suppression_douce('tache', enfant)])
        parent.soft_delete(self.u1, record=False)
        annuler_geste(self.u1, geste.pk)
        relue = Tache.objects.get(pk=enfant.pk)
        self.assertIsNone(relue.parent_id)
        self.assertIn(enfant.pk, [t.pk for t in taches_de(self.u1)])

    def test_annuler_la_suppression_d_un_parent_garde_ses_sous_taches_attachees(self):
        from apps.taches.services.taches import supprimer_tache
        parent = fabriques.tache(self.u1)
        enfants = [fabriques.tache(self.u1, parent=parent) for _ in range(2)]
        geste = supprimer_tache(self.u1, parent.pk)
        annuler_geste(self.u1, geste.pk)
        self.assertTrue(Tache.objects.filter(pk=parent.pk).exists())
        for enfant in enfants:
            self.assertEqual(Tache.objects.get(pk=enfant.pk).parent_id, parent.pk)

    def test_sous_tache_restauree_dont_le_parent_est_vivant_reste_attachee(self):
        parent = fabriques.tache(self.u1)
        enfant = fabriques.tache(self.u1, parent=parent)
        enfant.soft_delete(self.u1, record=False)
        geste = enregistrer_geste(self.u1, 'suppression', 'Supprimée', [op_suppression_douce('tache', enfant)])
        annuler_geste(self.u1, geste.pk)
        self.assertEqual(Tache.objects.get(pk=enfant.pk).parent_id, parent.pk)

    def test_defaire_une_suppression_dure_recree_au_meme_pk(self):
        tache = fabriques.tache(self.u1, jour_prevu=J)
        rappel = Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache,
                                       jour=J, heure=datetime.time(9, 0))
        pk = rappel.pk
        op = op_suppression_dure('rappel', rappel, {'tache': tache.pk, 'jour': J,
                                                    'heure': datetime.time(9, 0), 'statut': 'en_attente'})
        rappel.delete()
        geste = enregistrer_geste(self.u1, 'rappel', 'Rappel retiré', [op])
        annuler_geste(self.u1, geste.pk)
        rappel = Rappel.objects.get(pk=pk)
        self.assertEqual((rappel.tache_id, rappel.jour, rappel.heure, rappel.statut, rappel.proprietaire_id),
                         (tache.pk, J, datetime.time(9, 0), StatutRappel.EN_ATTENTE, self.u1.pk))

    def test_suppression_dure_refuse_une_fk_etrangere(self):
        a_lui = fabriques.tache(self.voisin, jour_prevu=J)
        op = {'op': 'suppression_dure', 'objet': 'rappel', 'id': 987654,
              'valeurs': {'tache': a_lui.pk, 'jour': J.isoformat(), 'heure': '09:00:00'}}
        geste = enregistrer_geste(self.u1, 'rappel', 'Rappel retiré', [op])
        rendu = annuler_geste(self.u1, geste.pk)
        self.assertFalse(Rappel.objects.filter(pk=987654).exists())
        self.assertEqual(rendu['conflits'][0]['raison'], 'introuvable')

    def test_statut_et_fait_le_restaures(self):
        tache = fabriques.tache(self.u1)
        tache.statut, tache.fait_le = StatutTache.FAIT, timezone.now()
        tache.save()
        ops = [op_champ('tache', tache, 'statut', StatutTache.A_FAIRE),
               op_champ('tache', tache, 'fait_le', None)]
        geste = enregistrer_geste(self.u1, 'terminaison', 'Faite', ops)
        annuler_geste(self.u1, geste.pk)
        tache.refresh_from_db()
        self.assertEqual((tache.statut, tache.fait_le), (StatutTache.A_FAIRE, None))


class TitresDesGestesTests(TestCase):
    """R2-125 — « 09:12 Faite · Appeler le fournisseur » : le titre de la tâche touchée, lu côté serveur."""

    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def _geste(self, type_, message, *taches):
        return enregistrer_geste(self.u1, type_, message, [op_creation('tache', t) for t in taches])

    def test_un_geste_sur_une_tache_dit_son_titre(self):
        tache = fabriques.tache(self.u1, titre='Appeler le fournisseur')
        geste = self._geste('terminaison', 'Faite', tache)
        self.assertEqual(titres_des_gestes(self.u1, [geste]), {geste.pk: 'Appeler le fournisseur'})

    def test_le_titre_est_celui_d_aujourd_hui_et_une_tache_supprimee_garde_le_sien(self):
        tache = fabriques.tache(self.u1, titre='Avant')
        geste = self._geste('modification', 'Modifiée', tache)
        Tache.all_objects.filter(pk=tache.pk).update(titre='Après', is_deleted=True)
        self.assertEqual(titres_des_gestes(self.u1, [geste]), {geste.pk: 'Après'})

    def test_un_geste_sur_plusieurs_taches_n_a_pas_de_titre_sauf_une_terminaison(self):
        premiere, seconde = fabriques.tache(self.u1, titre='Routine'), fabriques.tache(self.u1, titre='Suivante')
        lot = self._geste('lot', '2 reportées', premiere, seconde)
        faite = self._geste('terminaison', 'Faite', premiere, seconde)
        self.assertEqual(titres_des_gestes(self.u1, [lot, faite]), {faite.pk: 'Routine'})

    def test_un_collage_range_dans_un_projet_existant_nomme_ce_projet_en_une_seule_lecture(self):
        projet = fabriques.projet(self.u1, nom='Pompage Douar Ouled Saleh')
        autre = fabriques.projet(self.u1, nom='Salon')
        deux = [fabriques.tache(self.u1, projet=projet) for _ in range(2)]
        melange = [fabriques.tache(self.u1, projet=projet), fabriques.tache(self.u1, projet=autre)]
        sans = [fabriques.tache(self.u1), fabriques.tache(self.u1)]
        lot = self._geste('creation', '2 tâches créées', *deux)
        pas_meme_projet = self._geste('creation', '2 tâches créées', *melange)
        sans_projet = self._geste('creation', '2 tâches créées', *sans)
        # des tâches REPORTÉES (champ, pas création) ne sont pas un collage : pas de nom
        reportees = enregistrer_geste(self.u1, 'creation', '2 tâches créées',
                                      [op_creation('tache', deux[0]), op_champ('tache', deux[1], 'titre', 'Avant')])
        with self.assertNumQueries(2):  # les tâches créées, puis les noms de projet : jamais une requête par ligne
            rendu = titres_des_gestes(self.u1, [lot, pas_meme_projet, sans_projet, reportees])
        self.assertEqual(rendu, {lot.pk: 'Pompage Douar Ouled Saleh'})

    def test_un_geste_sans_tache_n_a_pas_de_titre(self):
        geste = enregistrer_geste(self.u1, 'rythme', 'Garder ce rythme', [])
        self.assertEqual(titres_des_gestes(self.u1, [geste]), {})

    def test_jamais_le_titre_d_une_tache_d_un_autre_compte(self):
        chez_lui = fabriques.tache(self.ailleurs, titre='Secret')
        geste = self._geste('terminaison', 'Faite', chez_lui)  # un geste mal formé : l'id d'une tâche étrangère
        self.assertEqual(titres_des_gestes(self.u1, [geste]), {})

    def test_la_route_sert_le_titre_a_l_ecran_et_jamais_a_l_assistant(self):
        tache = fabriques.tache(self.u1, titre='Appeler le fournisseur')
        geste = self._geste('terminaison', 'Faite', tache)
        api = APIClient()
        api.force_authenticate(self.u1)
        ecran = api.get('/api/django/taches/gestes/').json()['results']
        self.assertEqual([(g['id'], g['message'], g['titre']) for g in ecran],
                         [(geste.pk, 'Faite', 'Appeler le fournisseur')])
        assistant = api.get('/api/django/taches/gestes/', HTTP_X_TAQINOR_ASSISTANT='1').json()['results']
        self.assertEqual([(g['id'], g['titre']) for g in assistant], [(geste.pk, None)])

    def test_derniers_gestes_seulement_sur_des_taches_ou_des_projets(self):
        """R3-008 — « Derniers gestes » : une réponse de carte (« OK »), une préférence (« Noté : … ») et un réglage du
        rythme n'y sont plus ; un report et une décision d'À revoir sur une tâche y restent, avec leur titre ; une ★
        dit le titre de sa tâche (« Essentielle · … »), posée sur une ligne neuve comme sur une ligne remplacée."""
        from apps.taches.models.rythme import IncitationCoach
        from apps.taches.services import journee as services_journee
        from apps.taches.services import rythme
        from apps.taches.services.planification import planifier
        from apps.taches.services.taches import trancher_tache
        fabriques.reglages(self.u1)
        jour = timezone.localdate()
        carte = IncitationCoach.objects.create(company=self.a, proprietaire=self.u1, type='constat', cle='C5',
                                               canal='ecran', jour=jour, expire_le=jour + datetime.timedelta(days=7),
                                               donnees={'p': 57, 'n': 51, 'h1': 10, 'h2': 12})
        rythme.repondre_carte(self.u1, carte.pk, 'ok', jour)
        rythme.poser_preference(self.u1, 'heure_limite', '19:00', 'ecran')
        rythme.regler_rythme(self.u1, {'mode': 'pousser', 'objectif': 7}, jour)
        projet = fabriques.projet(self.u1)
        reportee = fabriques.tache(self.u1, projet=projet, titre='Appeler le notaire', jour_prevu=jour)
        planifier(reportee, acteur=self.u1, jour_prevu=jour + datetime.timedelta(days=2))
        a_revoir = fabriques.tache(self.u1, projet=projet, titre='Relancer Settat', reports=3,
                                   jour_prevu=jour - datetime.timedelta(days=2))
        trancher_tache(self.u1, a_revoir.pk, 'garder')
        etoile = fabriques.tache(self.u1, projet=projet, titre='Devis Benali', jour_prevu=jour)
        maintenant = timezone.localtime()
        services_journee.marquer_essentielle(self.u1, etoile.pk, True, maintenant)
        services_journee.marquer_essentielle(self.u1, etoile.pk, False, maintenant)
        api = APIClient()
        api.force_authenticate(self.u1)
        lignes = [(g['message'], g['titre']) for g in api.get('/api/django/taches/gestes/').json()['results']]
        self.assertEqual([titre for _message, titre in lignes],
                         ['Devis Benali', 'Devis Benali', 'Relancer Settat', 'Appeler le notaire'])
        self.assertEqual([message for message, _titre in lignes][:2], ['Plus essentielle', 'Essentielle'])
        self.assertFalse([m for m, _t in lignes if m == 'OK' or m.startswith('Noté') or m.startswith('Objectif')])

    def test_la_revue_qui_met_en_pause_le_dit(self):
        from apps.taches.services.projets import decider_revue
        projet = fabriques.projet(self.u1, nom='Salon Solaire')
        _revue, _projet, geste = decider_revue(self.u1, projet.pk, {'semaine': timezone.localdate(),
                                                                    'decision': 'pause'})
        self.assertEqual(geste.message, 'Revue : Salon Solaire en pause')
        autre = fabriques.projet(self.u1)
        _revue, _projet, geste = decider_revue(self.u1, autre.pk, {'semaine': timezone.localdate(),
                                                                   'decision': 'garder'})
        self.assertEqual(geste.message, 'Revue enregistrée')

    def test_une_seule_requete_pour_tous_les_gestes(self):
        gestes = [self._geste('terminaison', 'Faite', fabriques.tache(self.u1)) for _ in range(4)]
        with self.assertNumQueries(1):
            titres_des_gestes(self.u1, gestes)

    # --- R4 couture : un geste sur un PROJET ou une ÉTIQUETTE nomme ce qui a changé -------------------------------

    def _geste_projet(self, projet, champ, avant, type_='modification', message='Projet modifié'):
        return enregistrer_geste(self.u1, type_, message, [op_champ('projet', projet, champ, avant)])

    def test_un_geste_sur_un_projet_dit_son_nom_renomme_couleur_priorite(self):
        projet = fabriques.projet(self.u1, nom='Ancien nom', priorite=0)
        projet.nom, projet.couleur, projet.priorite = 'Salon Solaire', 'ciel', 2
        projet.save(update_fields=['nom', 'couleur', 'priorite'])
        renomme = self._geste_projet(projet, 'nom', 'Ancien nom')
        recolore = self._geste_projet(projet, 'couleur', 'terre')
        priorise = self._geste_projet(projet, 'priorite', 0)
        self.assertEqual(titres_des_gestes(self.u1, [renomme, recolore, priorise]),
                         {renomme.pk: 'Salon Solaire', recolore.pk: 'Salon Solaire', priorise.pk: 'Salon Solaire'})

    def test_une_pause_de_revue_et_une_revue_sans_autre_ecriture_nomment_le_projet(self):
        from apps.taches.services.projets import decider_revue
        en_pause = fabriques.projet(self.u1, nom='Salon Solaire')
        gardee = fabriques.projet(self.u1, nom='Site web')
        semaine = timezone.localdate()
        _revue, _projet, geste_pause = decider_revue(self.u1, en_pause.pk, {'semaine': semaine, 'decision': 'pause'})
        _revue, _projet, geste_garde = decider_revue(self.u1, gardee.pk, {'semaine': semaine, 'decision': 'garder'})
        self.assertEqual(titres_des_gestes(self.u1, [geste_pause, geste_garde]),
                         {geste_pause.pk: 'Salon Solaire', geste_garde.pk: 'Site web'})

    def test_terminer_ou_supprimer_un_projet_nomme_le_projet_pas_sa_premiere_tache(self):
        from apps.taches.services.projets import supprimer_projet, terminer_projet
        a_terminer = fabriques.projet(self.u1, nom='Étude Benali')
        fabriques.tache(self.u1, projet=a_terminer, titre='Appeler le notaire')
        fabriques.tache(self.u1, projet=a_terminer, titre='Relancer Settat')
        a_supprimer = fabriques.projet(self.u1, nom='Vieux projet')
        fabriques.tache(self.u1, projet=a_supprimer, titre='Une seule tâche')
        termine = terminer_projet(self.u1, a_terminer.pk, issue='atteint', taches_ouvertes='boite').geste
        supprime = supprimer_projet(self.u1, a_supprimer.pk).geste
        self.assertEqual(titres_des_gestes(self.u1, [termine, supprime]),
                         {termine.pk: 'Étude Benali', supprime.pk: 'Vieux projet'})

    def test_un_geste_d_etiquette_dit_son_nom_meme_apres_sa_suppression(self):
        from apps.taches.services.etiquettes import creer_etiquette, modifier_etiquette, supprimer_etiquette
        etiquette, cree = creer_etiquette(self.u1, nom='magasin')
        _etiquette, renomme = modifier_etiquette(self.u1, etiquette.pk, {'nom': 'courses'})
        self.assertEqual(titres_des_gestes(self.u1, [cree, renomme]), {cree.pk: 'courses', renomme.pk: 'courses'})
        supprime = supprimer_etiquette(self.u1, etiquette.pk)
        self.assertEqual(titres_des_gestes(self.u1, [supprime]), {supprime.pk: 'courses'})

    def test_jamais_le_nom_d_un_projet_ni_d_une_etiquette_d_un_autre_compte(self):
        from apps.taches.models.taches import Etiquette
        chez_lui = fabriques.projet(self.ailleurs, nom='Secret')
        etiquette = Etiquette.objects.create(company=self.b, proprietaire=self.ailleurs, nom='secrete')
        sur_projet = enregistrer_geste(self.u1, 'modification', 'Projet modifié', [op_creation('projet', chez_lui)])
        sur_etiquette = enregistrer_geste(self.u1, 'creation', 'Étiquette créée', [op_creation('etiquette', etiquette)])
        self.assertEqual(titres_des_gestes(self.u1, [sur_projet, sur_etiquette]), {})

    def test_une_lecture_groupee_par_type_jamais_par_ligne(self):
        from apps.taches.services.etiquettes import creer_etiquette, modifier_etiquette
        projet = fabriques.projet(self.u1, nom='Salon Solaire')
        etiquette, _cree = creer_etiquette(self.u1, nom='magasin')
        _etiquette, renomme = modifier_etiquette(self.u1, etiquette.pk, {'nom': 'courses'})
        gestes = [self._geste_projet(projet, 'nom', 'Avant') for _ in range(3)] + [renomme]
        with self.assertNumQueries(2):  # un seul SELECT pour les trois gestes de projet, un pour l'étiquette
            titres_des_gestes(self.u1, gestes)

    def test_la_route_sert_le_nom_du_projet_a_l_ecran_et_jamais_a_l_assistant(self):
        from apps.taches.services.projets import decider_revue
        projet = fabriques.projet(self.u1, nom='Salon Solaire')
        _revue, _projet, geste = decider_revue(self.u1, projet.pk, {'semaine': timezone.localdate(),
                                                                    'decision': 'pause'})
        api = APIClient()
        api.force_authenticate(self.u1)
        ecran = api.get('/api/django/taches/gestes/').json()['results']
        self.assertEqual([(g['id'], g['titre']) for g in ecran], [(geste.pk, 'Salon Solaire')])
        assistant = api.get('/api/django/taches/gestes/', HTTP_X_TAQINOR_ASSISTANT='1').json()['results']
        self.assertEqual([(g['id'], g['titre']) for g in assistant], [(geste.pk, None)])
