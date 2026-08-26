"""WIR177 — les notifications d'annonce pointent sur une route qui EXISTE.

Constat corrigé : `publish_annonce` et `sweep_annonce_reminders` posaient
`link='/annonces/<pk>'`. Cette route n'a JAMAIS été déclarée côté routeur —
chaque notification d'annonce publiée et chaque relance de lecture menaient
donc à un 404, et l'accusé de lecture XKB6 n'était appelable de nulle part
(le rapport de conformité restait vide pour toujours).

L'écran destinataire est désormais `/annonces` et lit `?annonce=<pk>` pour
déplier l'annonce visée (`frontend/src/features/notifications/AnnoncesPage.jsx`,
route déclarée dans `frontend/src/router/index.jsx`).

Ce module PROUVE :
  * publication → `link` == `/annonces?annonce=<pk>` (plus jamais le chemin
    `/annonces/<pk>`) ;
  * relance de lecture → EXACTEMENT le même lien ;
  * l'accusé de lecture par l'API est IDEMPOTENT (second clic : 200, toujours
    une seule ligne) et apparaît bien au rapport de conformité.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from .models import Annonce, AnnonceLecture, EventType, Notification

User = get_user_model()


def _company(nom='WIR177 Co'):
    return Company.objects.create(nom=nom)


def _user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


class LienAnnoncePublieeTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.destinataire = _user(self.company, 'wir177-dest')

    def test_publication_pointe_sur_la_route_reelle(self):
        from .services import publish_annonce
        annonce = Annonce.objects.create(
            company=self.company, titre='Nouvelle procédure',
            corps='À appliquer dès lundi.', lecture_obligatoire=True)
        publish_annonce(annonce)

        notif = Notification.objects.filter(
            company=self.company, recipient=self.destinataire,
            event_type=EventType.ANNONCE_PUBLISHED).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.link, f'/annonces?annonce={annonce.pk}')
        # Le chemin mort n'est plus produit nulle part.
        self.assertNotIn(f'/annonces/{annonce.pk}', notif.link)

    def test_relance_de_lecture_pointe_sur_le_meme_lien(self):
        from .services import sweep_annonce_reminders
        annonce = Annonce.objects.create(
            company=self.company, titre='Consignes QHSE',
            lecture_obligatoire=True, publiee=True,
            date_publication_effective=timezone.now() - timedelta(days=10))
        envoyees = sweep_annonce_reminders(self.company, delay_days=2)
        self.assertGreaterEqual(envoyees, 1)

        relance = Notification.objects.filter(
            company=self.company, recipient=self.destinataire,
            event_type=EventType.ANNONCE_READ_REMINDER).first()
        self.assertIsNotNone(relance)
        self.assertEqual(relance.link, f'/annonces?annonce={annonce.pk}')


class AccuseLectureIdempotentTests(TestCase):
    def setUp(self):
        self.company = _company('WIR177 Accusé')
        self.user = _user(self.company, 'wir177-lecteur')
        self.annonce = Annonce.objects.create(
            company=self.company, titre='Règlement intérieur',
            lecture_obligatoire=True, publiee=True,
            date_publication_effective=timezone.now())
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)

    def _url(self):
        return (f'/api/django/notifications/annonces/'
                f'{self.annonce.pk}/accuser-lecture/')

    def test_second_clic_idempotent(self):
        """Le bouton « J'ai lu et compris » peut être rejoué sans doublon."""
        premier = self.client_api.post(self._url())
        second = self.client_api.post(self._url())
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            AnnonceLecture.objects.filter(
                annonce=self.annonce, utilisateur=self.user).count(), 1)

    def test_accuse_apparait_au_rapport_de_conformite(self):
        from .services import annonce_compliance_report
        self.client_api.post(self._url())
        rapport = annonce_compliance_report(self.annonce)
        self.assertEqual([ligne['user_id'] for ligne in rapport['lus']],
                         [self.user.pk])
        self.assertEqual(rapport['manquants'], [])
        self.assertEqual(rapport['total_cibles'], 1)
