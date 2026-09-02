"""CRX31 — hygiène des surfaces publiques du CRM.

Trois trous distincts, tous atteignables SANS authentification :

  1. l'empreinte de visiteur ``SalleVenteVue.ip_hash`` était un SHA-256 salé par
     le jeton du lien — un sel CONNU de quiconque détient le lien, donc une
     table d'IPv4 reconstructible et une ré-identification possible. Elle est
     désormais clavée par ``SECRET_KEY`` (HMAC) ;
  2. le champ ``adresse`` (``TextField``, aucune limite SQL) était le seul texte
     du mapping public sans tranche : un POST anonyme pouvait écrire des
     mégaoctets par lead ;
  3. le lien de questionnaire acceptait un nombre ILLIMITÉ de photos (10 Mo
     chacune) — un seul lien suffisait à remplir le magasin de fichiers.

(Le mot de passe salle-vente hors chaîne de requête est QJR420, et la
déduplication du signal d'intérêt est vérifiée dans
``tests_ntcrm27_signal_interet.py`` — pas dupliquée ici.)
"""
import hashlib
import hmac

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm.models import Client, SalleVente, SalleVenteVue


class EmpreinteVisiteurClaveeTests(TestCase):
    """CRX31 (1) — ``ip_hash`` = HMAC(SECRET_KEY, jeton|ip réelle)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX31', slug='taqinor-crx31')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client CRX31')
        self.salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj, titre='Salle CRX31')

    def _visiter(self, ip):
        anon = APIClient()
        resp = anon.get(
            f'/api/django/crm/salle-vente/{self.salle.token}/',
            HTTP_X_FORWARDED_FOR=ip)
        self.assertEqual(resp.status_code, 200)
        return SalleVenteVue.objects.filter(salle=self.salle).latest('id')

    def test_empreinte_est_un_hmac_clave_pas_un_sha256_nu(self):
        ip = '203.0.113.7'
        vue = self._visiter(ip)
        message = ('%s|%s' % (self.salle.token, ip)).encode('utf-8')

        attendu = hmac.new(
            settings.SECRET_KEY.encode('utf-8'), message,
            hashlib.sha256).hexdigest()
        self.assertEqual(vue.ip_hash, attendu)

        # Le SHA-256 nu (calculable par le porteur du lien) ne doit PLUS
        # correspondre : sans SECRET_KEY, la table n'est pas reconstructible.
        self.assertNotEqual(vue.ip_hash, hashlib.sha256(message).hexdigest())
        # Et l'IP n'est jamais stockée en clair.
        self.assertNotIn(ip, vue.ip_hash)
        self.assertEqual(len(vue.ip_hash), 64)

    def test_deux_visiteurs_distincts_ont_deux_empreintes(self):
        premiere = self._visiter('203.0.113.7').ip_hash
        seconde = self._visiter('203.0.113.8').ip_hash
        self.assertNotEqual(premiere, seconde)


class AdresseBorneeTests(TestCase):
    """CRX31 (2) — l'adresse du mapping public est tranchée."""

    def test_adresse_tronquee_a_la_borne(self):
        from apps.crm.webhooks import (
            MAX_LONGUEUR_ADRESSE, _map_payload_to_fields)

        champs = _map_payload_to_fields({'adresse': 'A' * 5000})
        self.assertEqual(len(champs['adresse']), MAX_LONGUEUR_ADRESSE)

    def test_adresse_normale_intacte(self):
        from apps.crm.webhooks import _map_payload_to_fields

        adresse = '12 rue des Palmiers, Résidence Anfa, Casablanca'
        champs = _map_payload_to_fields({'adresse': adresse})
        self.assertEqual(champs['adresse'], adresse)


class PlafondPhotosQuestionnaireTests(TestCase):
    """CRX31 (3) — plafond de photos par lien de questionnaire."""

    def setUp(self):
        from apps.crm.models import Lead

        self.company = Company.objects.create(
            nom='Taqinor CRX31 Q', slug='taqinor-crx31-q')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead photos')

    def _poser_photos(self, combien):
        """Crée ``combien`` pièces jointes portant le préfixe du questionnaire
        (sans passer par MinIO — c'est le COMPTAGE qu'on borne ici)."""
        from django.contrib.contenttypes.models import ContentType

        from apps.crm.models import Lead
        from apps.crm.questionnaire import PREFIXE_FICHIER_QUESTIONNAIRE
        from apps.records.models import Attachment

        ct = ContentType.objects.get_for_model(Lead)
        for i in range(combien):
            Attachment.objects.create(
                company=self.company, content_type=ct, object_id=self.lead.pk,
                file_key=f'attachments/crx31-{i}.jpg',
                filename=f'{PREFIXE_FICHIER_QUESTIONNAIRE}facture-{i}.jpg',
                size=10, mime='image/jpeg')

    def test_sous_le_plafond_la_photo_passe_au_stockage(self):
        from unittest import mock

        from apps.crm import questionnaire

        self._poser_photos(questionnaire.PLAFOND_PHOTOS_PAR_LIEN - 1)
        with mock.patch(
                'apps.crm.intake_photo.attach_capture_photo',
                return_value='ATTACHÉ') as attach:
            resultat = questionnaire._enregistrer_photo(
                self.lead, 'photo_facture', 'data:image/jpeg;base64,AAAA')
        self.assertEqual(resultat, 'ATTACHÉ')
        attach.assert_called_once()

    def test_au_plafond_la_photo_est_refusee_sans_toucher_au_stockage(self):
        from unittest import mock

        from apps.crm import questionnaire

        self._poser_photos(questionnaire.PLAFOND_PHOTOS_PAR_LIEN)
        with mock.patch(
                'apps.crm.intake_photo.attach_capture_photo') as attach:
            resultat = questionnaire._enregistrer_photo(
                self.lead, 'photo_facture', 'data:image/jpeg;base64,AAAA')
        self.assertIsNone(resultat)
        attach.assert_not_called()
