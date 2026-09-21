"""NTDOC12 — Accès par viewer nommé avec expiration individuelle.

Couvre :
  * deux viewers de la même salle ont des liens ET des expirations
    INDÉPENDANTES ; révoquer l'un ne touche pas l'autre ;
  * l'endpoint public se résout UNIQUEMENT par jeton (404 sur inconnu ou
    révoqué — indistinct, aucune fuite), 410 sur expiré ;
  * aucun listing public n'existe ;
  * la consultation est horodatée sur le bon viewer ;
  * isolation société sur la gestion des accès.

Horloge FIGÉE : toutes les dates d'expiration sont construites par rapport à un
instant de référence explicite, jamais comparées à un ``now()`` vivant.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.datarooms import selectors, services
from apps.datarooms.models import AccesSalleDonnees

from ._base import auth, make_admin, make_company, make_document


REFERENCE = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0, 0))


class NtDoc12Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc12-a', 'Ntdoc12 A')
        self.co_b = make_company('ntdoc12-b', 'Ntdoc12 B')
        self.admin_a = make_admin(self.co_a, 'ntdoc12-admin-a')
        self.admin_b = make_admin(self.co_b, 'ntdoc12-admin-b')
        self.api = auth(self.admin_a)
        self.salle = services.creer_salle(
            company=self.co_a, nom='Levée série A', created_by=self.admin_a)
        self.doc = make_document(self.co_a, 'Business plan')
        services.ajouter_documents(self.salle, [self.doc])


class AccesIndependantsTests(NtDoc12Base):
    def test_deux_viewers_ont_liens_et_expirations_distincts(self):
        a = services.inviter_viewer(
            self.salle, nom='Investisseur A', email='a@example.com',
            expires_at=REFERENCE + datetime.timedelta(days=30))
        b = services.inviter_viewer(
            self.salle, nom='Investisseur B', email='b@example.com',
            expires_at=REFERENCE + datetime.timedelta(days=1))
        self.assertNotEqual(a.token, b.token)
        self.assertNotEqual(a.expires_at, b.expires_at)
        # À J+2 (horloge injectée), B est expiré, A ne l'est pas.
        instant = REFERENCE + datetime.timedelta(days=2)
        self.assertFalse(a.est_expire(now=instant))
        self.assertTrue(b.est_expire(now=instant))

    def test_revoquer_un_viewer_ne_touche_pas_l_autre(self):
        a = services.inviter_viewer(self.salle, nom='Viewer A')
        b = services.inviter_viewer(self.salle, nom='Viewer B')
        services.revoquer_acces(a)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertTrue(a.revoque)
        self.assertFalse(b.revoque)
        self.assertEqual(
            services.resoudre_acces_public(a.token)[0],
            services.ACCES_INTROUVABLE)
        self.assertEqual(
            services.resoudre_acces_public(b.token)[0], services.ACCES_OK)

    def test_revocation_idempotente(self):
        a = services.inviter_viewer(self.salle, nom='Viewer A')
        services.revoquer_acces(a)
        services.revoquer_acces(a)
        a.refresh_from_db()
        self.assertTrue(a.revoque)

    def test_expiration_globale_de_la_salle_ferme_tous_les_liens(self):
        self.salle.expires_at = REFERENCE
        self.salle.save(update_fields=['expires_at'])
        a = services.inviter_viewer(self.salle, nom='Viewer A')
        a.refresh_from_db()
        self.assertTrue(
            a.est_expire(now=REFERENCE + datetime.timedelta(minutes=1)))


class EndpointPublicTests(NtDoc12Base):
    def _url(self, token):
        return f'/api/django/datarooms/public/{token}/'

    def test_jeton_valide_sert_le_sommaire(self):
        acces = services.inviter_viewer(self.salle, nom='Investisseur A')
        reponse = self.client.get(self._url(acces.token))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['salle']['nom'], 'Levée série A')
        self.assertEqual(reponse.data['viewer']['nom'], 'Investisseur A')
        self.assertEqual(
            [d['nom'] for d in reponse.data['documents']], ['Business plan'])
        self.assertIn('noindex', reponse['X-Robots-Tag'])

    def test_document_masque_absent_du_sommaire(self):
        ligne = selectors.documents_de_salle(self.salle).first()
        ligne.visible = False
        ligne.save(update_fields=['visible'])
        acces = services.inviter_viewer(self.salle, nom='Viewer')
        reponse = self.client.get(self._url(acces.token))
        self.assertEqual(reponse.data['documents'], [])

    def test_jeton_inconnu_404(self):
        self.assertEqual(self.client.get(self._url('inexistant')).status_code,
                         404)

    def test_jeton_revoque_indistinct_d_un_inconnu(self):
        acces = services.inviter_viewer(self.salle, nom='Viewer')
        services.revoquer_acces(acces)
        revoque = self.client.get(self._url(acces.token))
        inconnu = self.client.get(self._url('inexistant'))
        self.assertEqual(revoque.status_code, 404)
        self.assertEqual(revoque.data['detail'], inconnu.data['detail'])

    def test_jeton_expire_410(self):
        acces = services.inviter_viewer(
            self.salle, nom='Viewer',
            expires_at=timezone.now() - datetime.timedelta(hours=1))
        self.assertEqual(self.client.get(self._url(acces.token)).status_code,
                         410)

    def test_aucun_listing_public(self):
        """La racine publique n'existe pas : seul un jeton exact résout."""
        self.assertEqual(
            self.client.get('/api/django/datarooms/public/').status_code, 404)

    def test_consultation_horodatee_sur_le_bon_viewer(self):
        a = services.inviter_viewer(self.salle, nom='Viewer A')
        b = services.inviter_viewer(self.salle, nom='Viewer B')
        self.client.get(self._url(a.token))
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertIsNotNone(a.derniere_consultation)
        self.assertIsNone(b.derniere_consultation)


class ApiGestionAccesTests(NtDoc12Base):
    def test_creation_pose_societe_et_jeton_cote_serveur(self):
        reponse = self.api.post('/api/django/datarooms/acces/', {
            'salle': self.salle.pk, 'nom': 'Investisseur A',
            'email': 'a@example.com',
            # Tentatives d'injection : ignorées côté serveur.
            'company': self.co_b.pk, 'token': 'jeton-choisi', 'revoque': True,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        acces = AccesSalleDonnees.objects.get(pk=reponse.data['id'])
        self.assertEqual(acces.company_id, self.co_a.pk)
        self.assertNotEqual(acces.token, 'jeton-choisi')
        self.assertFalse(acces.revoque)
        self.assertIn(acces.token, reponse.data['lien_public'])

    def test_salle_d_une_autre_societe_refusee(self):
        salle_b = services.creer_salle(
            company=self.co_b, nom='Salle voisine', created_by=self.admin_b)
        reponse = self.api.post('/api/django/datarooms/acces/', {
            'salle': salle_b.pk, 'nom': 'Intrus',
        }, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_action_revoquer(self):
        acces = services.inviter_viewer(self.salle, nom='Viewer')
        reponse = self.api.post(
            f'/api/django/datarooms/acces/{acces.pk}/revoquer/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        acces.refresh_from_db()
        self.assertTrue(acces.revoque)
