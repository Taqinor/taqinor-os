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

Vague 2 (CAD130 construite) — les GESTES entrent dans la file :

  * répondre au questionnaire pose UNE touche « Questionnaire complété —
    appeler » par la mécanique de CAD130 (jamais deux, même sur neuf
    sections) ;
  * la photo de FACTURE pose la tâche de production « Préparer et envoyer le
    devis (ou fixer un rappel) » — et AUCUNE relance ; une photo de compteur
    ou de tableau ne suffit pas à chiffrer et ne pose rien.
"""
import base64
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, questionnaire, services, stages
from apps.crm.intake_photo import attach_capture_photo, est_photo_de_facture
from apps.crm.models import Lead, QuestionnaireLien, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mercredi 23/09/2026, 10 h à Casablanca — fenêtre d'appel ouverte.
MERCREDI_10H = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

FAUX_JPEG_B64 = base64.b64encode(b'\xff\xd8\xff\xe0' + b'0' * 120).decode()
FAUX_META = {'file_key': 'attachments/cad136.jpg', 'filename': 'facture.jpg',
             'size': 124, 'mime': 'image/jpeg'}
LIBELLE_QUESTIONNAIRE = services.TOUCHES_SIGNAL[services.SIGNAL_QUESTIONNAIRE]


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


# ── Vague 2 : la nature de la photo (pur) ────────────────────────────────────

class NaturePhotoTests(SimpleTestCase):

    def test_la_photo_du_site_est_une_facture_par_defaut(self):
        self.assertTrue(est_photo_de_facture({'photo': 'x'},
                                             'photo-capture.jpg'))
        self.assertTrue(est_photo_de_facture({}, 'questionnaire-facture.jpg'))

    def test_compteur_et_tableau_ne_sont_pas_une_facture(self):
        self.assertFalse(est_photo_de_facture({}, 'questionnaire-compteur.jpg'))
        self.assertFalse(est_photo_de_facture({}, 'questionnaire-tableau.png'))
        self.assertFalse(est_photo_de_facture({'meterPhoto': 'x'},
                                              'photo-capture.jpg'))


# ── Vague 2 : les gestes entrent dans la file (en base) ─────────────────────

class GestesDansLaFileTests(TestCase):

    def setUp(self):
        gel = frozen(MERCREDI_10H)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD136 Vague 2',
                                              slug='cad136-vague2')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad136-v2-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', stage=stages.CONTACTED,
            owner=self.acteur, telephone='0600000092')

    def _repondre(self, lien, section, reponses):
        with patch('apps.notifications.services.notify_many') as notifier:
            questionnaire.appliquer_section(lien, section, reponses)
        return notifier

    def test_le_questionnaire_pose_une_touche_appeler(self):
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead,
            questions={'gps': True, 'occupation': True})
        notifier = self._repondre(lien, 'gps',
                                  {'gps_lat': 34.0, 'gps_lng': -6.8})
        self.assertTrue(notifier.called)
        touche = RelanceEtape.objects.get(lead=self.lead,
                                          libelle=LIBELLE_QUESTIONNAIRE)
        self.assertEqual(touche.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(touche.canal, RelanceEtape.Canal.APPEL)
        # La prochaine minute joignable : la fenêtre est ouverte, c'est
        # maintenant.
        self.assertEqual(touche.due_at, MERCREDI_10H)

    def test_neuf_sections_une_seule_touche(self):
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead,
            questions={'gps': True, 'occupation': True})
        self._repondre(lien, 'gps', {'gps_lat': 34.0, 'gps_lng': -6.8})
        self._repondre(lien, 'occupation', {'occupation_jour': 'present'})
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, libelle=LIBELLE_QUESTIONNAIRE).count(), 1)

    def _photo(self, lead, **payload):
        meta = dict(FAUX_META)
        with patch('apps.records.storage.store_attachment',
                   return_value=(meta, None)), \
                patch('apps.notifications.services.notify_many') as notifier:
            attach_capture_photo(lead, {'photo': FAUX_JPEG_B64, **payload})
        return notifier

    def test_la_photo_pose_preparer_le_devis_et_non_une_relance(self):
        notifier = self._photo(self.lead)
        self.assertTrue(notifier.called)
        etapes = list(RelanceEtape.objects.filter(lead=self.lead))
        self.assertEqual([e.libelle for e in etapes],
                         [services.FILET_JOINT_LIBELLE])
        etape = etapes[0]
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        # Tâche de production : la cadence hors protocole, jamais un barreau
        # de relance, jamais une touche signal.
        self.assertEqual(etape.cadence, 'generique')
        self.assertNotIn(etape.libelle, services.TOUCHES_SIGNAL.values())
        # Demain, au prochain créneau d'appel (même délai que le filet
        # « client joint » et que la pièce reçue sur WhatsApp).
        self.assertEqual(etape.due_date,
                         MERCREDI_10H.date() + datetime.timedelta(days=1))
        self.assertTrue(horaires.est_dans_fenetre(
            etape.due_at, self.company, canal=etape.canal))

    def test_deux_photos_une_seule_tache(self):
        self._photo(self.lead)
        self._photo(self.lead)
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, libelle=services.FILET_JOINT_LIBELLE).count(), 1)

    def test_une_photo_de_compteur_ne_pose_rien(self):
        self._photo(self.lead, photoFilename='questionnaire-compteur.jpg')
        self.assertFalse(RelanceEtape.objects.filter(lead=self.lead).exists())

    def test_rien_sur_un_lead_perdu(self):
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        self._photo(self.lead)
        self.assertFalse(RelanceEtape.objects.filter(lead=self.lead).exists())
