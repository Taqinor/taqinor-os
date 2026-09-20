"""CAL205 — commentaires sur un calepinage (primitive plateforme).

Ce qui est prouvé ici :

* un commentaire se dépose et se lit par la primitive ``records.Comment``
  (aucun second modèle) ;
* un corps vide, ou un calepinage non enregistré, est refusé en nommant le
  champ ;
* le RESPONSABLE (créateur) du calepinage est notifié d'un nouveau
  commentaire — le nom affiché est celui de l'AUTEUR résolu, jamais un
  prénom codé en dur ;
* l'auteur du commentaire ne se notifie pas lui-même.

Run :
    python manage.py test apps.calepinage.tests.test_cal205_commentaires -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.commentaires import (
    CommentaireInvalide, commentaires_du_calepinage, deposer_commentaire,
)
from apps.notifications.models import Notification
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()


class DeposerCommentaireTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Comment Co',
                                              slug='comment-co-205')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.responsable = User.objects.create_user(
            username='resp_205', password='x', company=self.company,
            role=self.role)
        self.commentateur = User.objects.create_user(
            username='commentateur_205', password='x', company=self.company,
            role=self.role)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=42, titre='Villa Anfa',
            cree_par=self.responsable)

    def test_depot_puis_lecture(self):
        deposer_commentaire(self.calepinage, 'Vérifier la marge nord.',
                            user=self.commentateur)
        lignes = list(commentaires_du_calepinage(self.calepinage))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].body, 'Vérifier la marge nord.')
        self.assertEqual(lignes[0].author, self.commentateur)

    def test_corps_vide_refuse(self):
        with self.assertRaises(CommentaireInvalide) as ctx:
            deposer_commentaire(self.calepinage, '   ',
                                user=self.commentateur)
        self.assertEqual(ctx.exception.champ, 'body')

    def test_calepinage_non_enregistre_refuse(self):
        vierge = Calepinage(company=self.company, lead_id=1)
        with self.assertRaises(CommentaireInvalide) as ctx:
            deposer_commentaire(vierge, 'texte', user=self.commentateur)
        self.assertEqual(ctx.exception.champ, 'calepinage')

    def test_responsable_notifie_nom_resolu_jamais_en_dur(self):
        deposer_commentaire(self.calepinage, 'Un commentaire.',
                            user=self.commentateur)
        notif = Notification.objects.filter(recipient=self.responsable).first()
        self.assertIsNotNone(notif)
        self.assertIn(self.commentateur.username, notif.title)

    def test_auteur_ne_se_notifie_pas_lui_meme(self):
        deposer_commentaire(self.calepinage, 'Auto-commentaire.',
                            user=self.responsable)
        self.assertFalse(
            Notification.objects.filter(recipient=self.responsable).exists())

    def test_calepinage_vide_liste_vide(self):
        self.assertEqual(list(commentaires_du_calepinage(self.calepinage)),
                         [])
