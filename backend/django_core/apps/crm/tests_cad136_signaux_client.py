"""CAD136 — questionnaire rempli, photo de facture reçue : plus de silence.

Audit L3 du 21/09/2026, section CAD-K. Répondre à une section du
questionnaire enrichissait le lead, recalculait le score et écrivait une note
— sans AUCUNE notification, et ``derniere_reponse_at`` n'était relu par
personne dans tout le dépôt ; la photo de facture envoyée depuis le site était
attachée (avec OCR si la clé est active) sans prévenir personne. Le client
vient pourtant de passer cinq minutes sur NOTRE formulaire.

Ce fichier verrouille :

  * les DEUX événements notifient le responsable ;
  * la photo appelle « préparer le devis » — de la PRODUCTION, pas une
    relance (nuance du round 2) ;
  * aucun type d'événement neuf, et un signal inconnu ne notifie rien ;
  * best-effort : ni une réponse ni une photo ne retombent sur une cloche en
    panne.

NON FAIT ICI, et pourquoi : la TOUCHE « questionnaire complété, appeler »
passe par la mécanique de CAD130 (``@after: CAD130`` sur la tâche), qui n'est
pas construite — la règle de composition interdit d'en bricoler un substitut.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile

User = get_user_model()


class SignauxClientTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad136', defaults={'nom': 'cad136'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad136-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.CONTACTED,
            owner=self.acteur, telephone='0600000091')

    def test_le_questionnaire_notifie_le_responsable(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_QUESTIONNAIRE,
                detail='Section « Toiture » renseignée.')
        self.assertTrue(notifier.called)
        self.assertIn(self.acteur, list(notifier.call_args.args[0]))
        self.assertIn('questionnaire', notifier.call_args.args[2].lower())

    def test_la_photo_notifie_le_responsable(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_PHOTO_FACTURE)
        self.assertTrue(notifier.called)
        self.assertIn(self.acteur, list(notifier.call_args.args[0]))

    def test_la_photo_appelle_la_production_pas_une_relance(self):
        """Nuance du round 2 : « préparer le devis », jamais « relancer »."""
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_PHOTO_FACTURE)
        corps = notifier.call_args.kwargs['body']
        self.assertIn('PRÉPARER LE DEVIS', corps)
        self.assertIn('production', corps)
        self.assertNotIn('relancer', corps.lower())

    def test_le_detail_est_repris_sans_rien_inventer(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_QUESTIONNAIRE,
                detail='Section « Toiture » renseignée.')
        self.assertIn('Section « Toiture » renseignée.',
                      notifier.call_args.kwargs['body'])

    def test_un_signal_inconnu_ne_notifie_rien(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(self.lead, 'inconnu')
        self.assertFalse(notifier.called)

    def test_un_lead_sans_societe_ne_notifie_rien(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                Lead(nom='Sans société'), services.SIGNAL_QUESTIONNAIRE)
        self.assertFalse(notifier.called)

    def test_aucun_type_devenement_neuf(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_PHOTO_FACTURE)
        self.assertEqual(notifier.call_args.args[1], 'devis_opened')

    def test_une_cloche_en_panne_ne_fait_rien_retomber(self):
        with patch('apps.notifications.services.notify_many',
                   side_effect=RuntimeError('cloche indisponible')):
            services.notifier_signal_client(
                self.lead, services.SIGNAL_QUESTIONNAIRE)

    def test_le_lien_mene_a_la_fiche_du_lead(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_client(
                self.lead, services.SIGNAL_QUESTIONNAIRE)
        self.assertEqual(notifier.call_args.kwargs['link'],
                         f'/crm/leads/{self.lead.pk}')
