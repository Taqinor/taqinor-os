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
    une seule ligne) et apparaît bien au rapport de conformité ;
  * PACT10/PACT13 — la réponse RÉELLE de `GET /annonces/?active=1` a
    exactement la forme de l'exemple COMMITTÉ
    (`contract_samples/annonces_actives.json`), celui-là même
    qu'`AnnoncesPage.test.jsx` importe au lieu d'écrire son propre mock. Sans
    cette moitié-ci, l'exemple pourrirait dans son coin — ce que le README de
    `contract_samples/` désigne comme pire que pas d'exemple du tout.
"""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from .models import Annonce, AnnonceLecture, EventType, Notification

User = get_user_model()

ECHANTILLON = (Path(__file__).resolve().parent
               / 'contract_samples' / 'annonces_actives.json')
ANNONCES_URL = '/api/django/notifications/annonces/'


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


class ContratAnnoncesActivesTests(TestCase):
    """PACT10/PACT13 — l'exemple COMMITTÉ est la forme RÉELLE du serveur.

    `AnnoncesPage.test.jsx` importe ce même fichier (`exempleContrat(
    'notifications', 'annonces_actives')`) au lieu d'écrire son mock : si le
    serveur change de forme, l'exemple doit changer et le test frontend casse
    tout seul, sans réunion ni discipline humaine.
    """

    ENVELOPPE = ['count', 'next', 'previous', 'results']

    def setUp(self):
        self.company = _company('WIR177 Contrat')
        self.user = _user(self.company, 'wir177-contrat', 'responsable')
        self.contrat = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _reponse_active(self):
        resp = self.api.get(ANNONCES_URL, {'active': 1})
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_l_exemple_annonce_l_endpoint_reel(self):
        self.assertEqual(self.contrat['endpoint'],
                         f'GET {ANNONCES_URL}')

    def test_l_enveloppe_paginee_est_celle_du_serveur(self):
        """`count/next/previous/results` — l'écran lit `results`."""
        resp = self._reponse_active()
        self.assertEqual(sorted(resp.data), self.ENVELOPPE)
        for variante in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(self.contrat[variante]), self.ENVELOPPE,
                             variante)

    def test_les_cles_d_une_annonce_sont_celles_de_l_exemple(self):
        """Aucune clé inventée, aucune clé omise : la comparaison est faite sur
        une annonce RÉELLEMENT sérialisée par le serveur."""
        Annonce.objects.create(
            company=self.company, titre='Contrat',
            corps='Corps de contrôle.', lecture_obligatoire=True,
            publiee=True, date_publication_effective=timezone.now())
        resp = self._reponse_active()
        self.assertEqual(resp.data['count'], 1)
        reelle = resp.data['results'][0]
        for ligne in self.contrat['exemple']['results']:
            self.assertEqual(sorted(ligne), sorted(reelle))

    def test_les_champs_lus_par_l_ecran_existent_vraiment(self):
        """Les 7 clés que `AnnoncesPage.jsx` lit — une seule absente et l'écran
        affiche un vide silencieux (le défaut du 03/08/2026)."""
        Annonce.objects.create(
            company=self.company, titre='Contrat 2', corps='C',
            publiee=True, date_publication_effective=timezone.now())
        reelle = self._reponse_active().data['results'][0]
        for champ in ('id', 'titre', 'corps', 'auteur_username', 'epinglee',
                      'lecture_obligatoire', 'date_publication_effective'):
            with self.subTest(champ=champ):
                self.assertIn(champ, reelle)

    def test_active_1_ecarte_les_non_publiees_et_les_expirees(self):
        """Ce que le `pourquoi` de l'exemple annonce : `?active=1` ne sert que
        des annonces publiées ET non expirées."""
        publiee = Annonce.objects.create(
            company=self.company, titre='Visible', publiee=True,
            date_publication_effective=timezone.now())
        Annonce.objects.create(
            company=self.company, titre='Brouillon', publiee=False)
        Annonce.objects.create(
            company=self.company, titre='Expirée', publiee=True,
            date_publication_effective=timezone.now() - timedelta(days=30),
            date_expiration=timezone.now() - timedelta(days=1))
        ids = [r['id'] for r in self._reponse_active().data['results']]
        self.assertEqual(ids, [publiee.pk])

    def test_l_exemple_vide_est_un_AUTRE_ETAT_pas_une_autre_forme(self):
        resp = self._reponse_active()
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(list(resp.data['results']), [])
        self.assertEqual(self.contrat['exemple_vide']['results'], [])
