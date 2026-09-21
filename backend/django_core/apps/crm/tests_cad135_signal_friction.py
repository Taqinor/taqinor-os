"""CAD135 — « le client relit le prix » arrive enfin au responsable.

Audit L3 du 21/09/2026, section CAD-K. Quand un client revient plusieurs fois
sur la même section (le prix, l'étude), le système écrit lui-même « signal de
friction, un appel peut débloquer la décision » — dans l'historique du DEVIS,
sans aucune notification ; même sort pour « a commencé à lire en détail ».
Personne ne les lisait, sauf à ouvrir cet onglet par hasard.

Ce fichier verrouille le chemin commun :

  * un signal de friction produit une ligne au chatter du LEAD et une
    notification au responsable, avec le lien pour appeler ;
  * une lecture en détail fait de même, avec son propre libellé ;
  * la note reste SYSTÈME (``user=None``) — elle ne fait jamais avancer le
    funnel (règle du 07/09/2026) ;
  * et rien ne classe ni ne priorise : « le signal le plus prédictif » reste
    une hypothèse tant que CAD87 ne l'a pas mesuré.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity
from apps.parametres.models import CompanyProfile

User = get_user_model()


class SignalLectureTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='cad135', defaults={'nom': 'cad135'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad135-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='0600000081')

    def _notes(self):
        return list(LeadActivity.objects.filter(lead=self.lead))

    def test_friction_ecrit_une_ligne_au_chatter_du_lead(self):
        services.notifier_signal_lecture(
            'DV-135', self.lead, friction_section='prix')
        notes = self._notes()
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('relit la section', notes[0].body)
        self.assertIn('prix', notes[0].body)
        self.assertIn('DV-135', notes[0].body)

    def test_friction_notifie_le_responsable(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_lecture(
                'DV-135', self.lead, friction_section='prix')
        self.assertTrue(notifier.called)
        destinataires = notifier.call_args.args[0]
        self.assertIn(self.acteur, list(destinataires))

    def test_la_notification_porte_le_lien_pour_appeler(self):
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_lecture(
                'DV-135', self.lead, friction_section='prix')
        corps = notifier.call_args.kwargs['body']
        self.assertIn('wa.me', corps)

    def test_lecture_en_detail_a_son_propre_libelle(self):
        services.notifier_signal_lecture(
            'DV-135', self.lead, resume='prix (30s)')
        note = self._notes()[0]
        self.assertIn('en détail', note.body)
        self.assertIn('prix (30s)', note.body)
        self.assertNotIn('relit la section', note.body)

    def test_la_note_est_systeme_et_ne_fait_pas_avancer_le_funnel(self):
        """Règle du 07/09/2026 : le funnel ne bouge que sur une réponse."""
        avant = self.lead.stage
        services.notifier_signal_lecture(
            'DV-135', self.lead, friction_section='étude')
        self.lead.refresh_from_db()
        self.assertIsNone(self._notes()[0].user)
        self.assertEqual(self.lead.stage, avant)

    def test_un_lead_sans_societe_ne_casse_rien(self):
        orphelin = Lead(nom='Sans société')
        services.notifier_signal_lecture('DV-135', orphelin,
                                         friction_section='prix')
        self.assertEqual(LeadActivity.objects.filter(lead=orphelin).count(), 0)

    def test_une_notification_en_echec_laisse_la_note_ecrite(self):
        """Best-effort : le fait consigné survit à une cloche en panne."""
        with patch('apps.notifications.services.notify_many',
                   side_effect=RuntimeError('cloche indisponible')):
            services.notifier_signal_lecture(
                'DV-135', self.lead, friction_section='prix')
        self.assertEqual(len(self._notes()), 1)

    def test_aucun_type_devenement_neuf(self):
        """Le signal emprunte le chemin de « devis ouvert », pas un autre."""
        with patch('apps.notifications.services.notify_many') as notifier:
            services.notifier_signal_lecture(
                'DV-135', self.lead, friction_section='prix')
        self.assertEqual(notifier.call_args.args[1], 'devis_opened')
