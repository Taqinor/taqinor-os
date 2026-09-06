"""AUD824 — l'import clients (mode « créer ») déduplique enfin sur le téléphone.

Constat d'audit (le ROUGE figé ici) : ``dataimport.services._doublon_client``
ne testait que ``f.get('email')``. Sans email il renvoyait systématiquement
``None`` — contrairement à son jumeau ``_doublon_lead``, qui replie sur le
téléphone. Or ``apps.crm.models.Client`` ne porte AUCUNE ``UniqueConstraint``
sur (company, email) ni sur (company, telephone) : rien, ni en Python ni en
base, n'arrêtait la ligne.

Conséquence : un fichier clients réel (nom + téléphone + adresse, sans colonne
email — le cas ordinaire d'un carnet d'adresses terrain) rejoué deux fois créait
un DEUXIÈME ``Client`` identique à chaque passage, sans erreur ni avertissement.
L'aperçu mentait de la même façon : il rejoue le MÊME ``_doublon_client`` et
annonçait donc « création » pour une ligne qui allait dupliquer.

Ce que le correctif fait : aligner ``_doublon_client`` sur le patron de
``_doublon_lead`` (email d'abord, repli téléphone).

Ce que le correctif NE fait PAS, délibérément : ajouter une
``UniqueConstraint(company, email)`` sur ``Client``. La base de production
porte des emails de remplissage issus de la synchronisation Odoo (plusieurs
fiches partagent la même valeur) : une contrainte unique échouerait à la
migration sur de la donnée réelle. La déduplication reste applicative, et c'est
elle qui est prouvée ici.

Run :
    python manage.py test apps.dataimport.test_aud824_clients_doublon_telephone -v2
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()

COMMIT = '/api/django/imports/commit/'
DRY_RUN = '/api/django/imports/dry-run/'

# Carnet d'adresses terrain : nom + téléphone + adresse, AUCUNE colonne email.
CSV_SANS_EMAIL = 'Nom,Telephone,Adresse\nBennani,+212600112233,12 rue Al Massira\n'


class AUD824ClientDoublonTelephoneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='imp-aud824', defaults={'nom': 'Imp AUD824'})[0]
        self.user = User.objects.create_user(
            username='imp_aud824', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _csv(self, content, name='clients.csv'):
        return SimpleUploadedFile(
            name, content.encode('utf-8'), content_type='text/csv')

    def _commit(self, content):
        return self.api.post(
            COMMIT, {'file': self._csv(content), 'target': 'clients'},
            format='multipart')

    def _dry_run(self, content):
        return self.api.post(
            DRY_RUN, {'file': self._csv(content), 'target': 'clients'},
            format='multipart')

    # ── ROUGE — le rejeu d'un fichier sans email créait un doublon complet ──

    def test_rejeu_sans_email_ne_cree_pas_un_deuxieme_client(self):
        first = self._commit(CSV_SANS_EMAIL)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['created'], 1, first.data)

        second = self._commit(CSV_SANS_EMAIL)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            second.data['created'], 0,
            'le rejeu a recréé un client : la déduplication ne replie pas sur '
            'le téléphone (AUD824)')

        self.assertEqual(
            Client.objects.filter(
                company=self.company, telephone='+212600112233').count(),
            1,
            'deux Client identiques pour le même téléphone après un simple '
            'rejeu du fichier (AUD824)')

    def test_l_apercu_annonce_la_ligne_comme_ignoree(self):
        """L'aperçu doit désigner EXACTEMENT ce que le commit ferait."""
        self.assertEqual(self._commit(CSV_SANS_EMAIL).data['created'], 1)

        apercu = self._dry_run(CSV_SANS_EMAIL)
        self.assertEqual(apercu.status_code, 200, apercu.data)
        resume = apercu.data['resume']
        self.assertEqual(
            resume['ignoree'], 1,
            "l'aperçu annonce « création » pour une ligne que le commit va "
            f'ignorer comme doublon (AUD824) — résumé : {resume}')
        self.assertEqual(resume['creation'], 0, resume)

    # ── Non-régression : le repli téléphone ne doit rien casser d'autre ─────

    def test_deux_clients_de_telephones_differents_sont_bien_crees(self):
        resp = self._commit(
            'Nom,Telephone\nBennani,+212600112233\nAlaoui,+212600445566\n')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 2, resp.data)

    def test_la_deduplication_par_email_reste_prioritaire(self):
        self.assertEqual(
            self._commit(
                'Nom,Email,Telephone\n'
                'Bennani,aud824@example.invalid,+212600999888\n'
            ).data['created'], 1)
        # Même email, téléphone DIFFÉRENT -> toujours un doublon (email d'abord).
        resp = self._commit(
            'Nom,Email,Telephone\n'
            'Bennani,aud824@example.invalid,+212600777666\n')
        self.assertEqual(resp.data['created'], 0, resp.data)
        self.assertEqual(
            Client.objects.filter(
                company=self.company, email='aud824@example.invalid').count(), 1)

    def test_une_ligne_sans_email_ni_telephone_reste_creable(self):
        """Sans aucun contact, il n'y a rien à rapprocher : la ligne passe."""
        resp = self._commit('Nom,Adresse\nSans Contact,Route de Safi\n')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1, resp.data)

    def test_le_telephone_d_une_autre_societe_n_est_pas_un_doublon(self):
        """Multi-tenant : le rapprochement reste scopé par ``company``."""
        autre = Company.objects.get_or_create(
            slug='imp-aud824-bis', defaults={'nom': 'Imp AUD824 bis'})[0]
        Client.objects.create(
            company=autre, nom='Bennani', telephone='+212600112233')
        resp = self._commit(CSV_SANS_EMAIL)
        self.assertEqual(resp.data['created'], 1, resp.data)
