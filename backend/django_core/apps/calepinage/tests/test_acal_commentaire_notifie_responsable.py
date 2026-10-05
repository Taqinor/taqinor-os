# -*- coding: utf-8 -*-
"""ACAL293 — une note du chatter d'un calepinage notifie son responsable.

LE CONSTAT (C-ACAL-145)
-----------------------
``services/commentaires.py`` (CAL205) notifiait le responsable d'un
commentaire… mais AUCUNE route ne l'appelait : l'écran note par
``POST chatter/noter/`` (plateforme ``records``), qui ne prévenait personne.
Le jumeau est supprimé ; la notification vit désormais dans la vue du module,
après l'écriture de la note par ``records`` (inchangée).

Ce qui est prouvé ici, par la ROUTE HTTP réelle :

* A note sur un calepinage dont R est responsable ⇒ R reçoit UNE notification
  ``chat_message`` avec le lien ``/calepinage/<id>`` et l'extrait ;
* A = R ⇒ aucune notification ;
* sans responsable ⇒ le propriétaire du lead est notifié (défaut gravé).

Run :
    python manage.py test apps.calepinage.tests.test_acal_commentaire_notifie_responsable
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.calepinage.models import Calepinage
from apps.notifications.models import Notification
from apps.notifications.types_evenements import EventType

from .test_api_liste import BaseApiCalepinage, url_detail

User = get_user_model()


def url_noter(pk):
    return f'{url_detail(pk)}chatter/noter/'


class NoteNotifieLeResponsableTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.responsable = User.objects.create_user(
            username='resp_acal293', password='x', company=self.company,
            role=self.role)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            responsable=self.responsable)

    def _noter(self, calepinage, texte='Vérifier la pente du pan Sud.'):
        reponse = self.api.post(url_noter(calepinage.pk), {'body': texte},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse

    def test_note_notifie_le_responsable(self):
        self._noter(self.calepinage)
        notes = Notification.objects.filter(recipient=self.responsable)
        self.assertEqual(notes.count(), 1)
        note = notes.get()
        self.assertEqual(note.event_type, EventType.CHAT_MESSAGE)
        self.assertEqual(note.link, '/calepinage/%d' % self.calepinage.pk)
        self.assertEqual(note.body, 'Vérifier la pente du pan Sud.')
        self.assertIn(self.user.username, note.title)
        self.assertEqual(note.company_id, self.company.pk)
        # L'auteur ne se notifie pas lui-même.
        self.assertFalse(Notification.objects.filter(
            recipient=self.user).exists())

    def test_auteur_responsable_sans_notification(self):
        propre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Hangar',
            responsable=self.user)
        self._noter(propre)
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.CHAT_MESSAGE).exists())

    def test_sans_responsable_proprietaire_du_lead(self):
        self.lead.owner = self.responsable
        self.lead.save(update_fields=['owner'])
        orphelin = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans resp.')
        self._noter(orphelin, 'Relevé à refaire.')
        # (l'attribution du lead notifie déjà son propriétaire : seule la
        # notification de la NOTE est comptée ici.)
        note = Notification.objects.get(recipient=self.responsable,
                                        event_type=EventType.CHAT_MESSAGE)
        self.assertEqual(note.link, '/calepinage/%d' % orphelin.pk)
        self.assertEqual(note.body, 'Relevé à refaire.')
