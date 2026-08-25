"""L-DESSIN (ordre fondateur 25/08/2026) — le tracé de toit du client ARRIVE
et se VOIT.

« When the client draws his roof i still do not receive the drawing. »

Le contour atterrissait déjà dans ``Lead.roof_outline`` (couvert par
``tests_qk1_webhook_qualification`` / ``tests_roof_point``) mais RIEN dans la
fiche ne l'annonçait : ni l'historique, ni la notification. Ces tests
épinglent les deux reçus ajoutés côté serveur — le rendu visuel, lui, est
gardé côté ERP (``frontend traceToit.test.mjs`` +
``TraceToitClient.test.jsx``).

Les tests d'historique partent du POST webhook RÉEL (le seul point d'entrée du
site), donc aucun chemin non représentatif. Ceux de notification appellent
``notify_new_lead`` directement, comme ``tests_qj2_seller_notifications`` —
c'est le seul montage déterministe pour garantir un destinataire.
"""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead, LeadActivity

SECRET = 'test-secret-trace-toit'

#: Contour plausible (≥ 3 sommets), dans l'ordre d'axes réel [lat, lng].
CONTOUR = [
    [33.589, -7.603],
    [33.589, -7.6028],
    [33.5892, -7.6028],
    [33.5892, -7.603],
]


def payload_site(**extra):
    """Charge utile de la forme émise par apps/web (capture-lead.ts)."""
    base = {
        'fullName': 'Nadia Berrada',
        'phoneE164': '+212661222333',
        'whatsappOptIn': True,
        'city': 'Casablanca',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'consent': True,
        'qualified': True,
        'page': '/devis/mon-toit',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TraceToitWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Trace Co', slug='trace-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def notes_trace(self, lead):
        return LeadActivity.objects.filter(
            lead=lead, body__startswith='Toit dessiné par le client')

    def test_contour_persiste_et_laisse_une_note_dans_l_historique(self):
        """Le tracé arrive en base ET l'historique le DIT (le « reçu »)."""
        res = self.post(payload_site(
            roofPoint={'lat': 33.5891, 'lng': -7.6029},
            roofOutline=CONTOUR))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])

        # (a) la donnée : le contour COMPLET, dans l'ordre d'axes du site.
        self.assertEqual(lead.roof_outline, CONTOUR)
        self.assertEqual(lead.roof_point, {'lat': 33.5891, 'lng': -7.6029})

        # (b) le reçu : une note d'historique, avec le nombre RÉEL de sommets.
        notes = self.notes_trace(lead)
        self.assertEqual(notes.count(), 1, 'exactement une note de tracé')
        note = notes.first()
        self.assertIn('4 points', note.body)
        self.assertIn('Toiture & site', note.body)
        # Multi-tenant : la note appartient à la société du lead, jamais au
        # payload, et n'est attribuée à aucun utilisateur (écriture serveur).
        self.assertEqual(note.company, lead.company)
        self.assertIsNone(note.user)

    def test_sans_contour_aucune_note_de_trace(self):
        """Un lead sans tracé ne fabrique JAMAIS une note « toit dessiné »."""
        res = self.post(payload_site(roofPoint={'lat': 33.5891, 'lng': -7.6029}))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.roof_outline)
        self.assertEqual(self.notes_trace(lead).count(), 0)

    def test_contour_malforme_ni_range_ni_note(self):
        """Moins de 3 sommets : ce n'est pas un polygone — rien n'est écrit."""
        res = self.post(payload_site(roofOutline=[[33.589, -7.603]]))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.roof_outline)
        self.assertEqual(self.notes_trace(lead).count(), 0)

    def test_contour_arrive_sur_le_renvoi_moins_de_60s_note_une_seule_fois(self):
        """Le visiteur soumet, dessine, re-soumet dans la minute : le tracé
        est noté À SON ARRIVÉE, et une seule fois (pas de doublon quand un
        troisième renvoi reporte le même contour)."""
        res1 = self.post(payload_site())
        self.assertEqual(res1.status_code, 201, res1.content)
        lead = Lead.objects.get(pk=res1.json()['lead_id'])
        self.assertEqual(self.notes_trace(lead).count(), 0)

        # 2e envoi (< 60 s, même téléphone) : le contour arrive.
        res2 = self.post(payload_site(roofOutline=CONTOUR))
        self.assertEqual(res2.status_code, 200, res2.content)
        lead.refresh_from_db()
        self.assertEqual(lead.roof_outline, CONTOUR)
        self.assertEqual(self.notes_trace(lead).count(), 1)

        # 3e envoi identique : rien de nouveau, donc aucune 2e note.
        res3 = self.post(payload_site(roofOutline=CONTOUR))
        self.assertEqual(res3.status_code, 200, res3.content)
        lead.refresh_from_db()
        self.assertEqual(self.notes_trace(lead).count(), 1)


class TraceToitNotificationTests(TestCase):
    """Le second canal de « réception » : la notification d'arrivée du lead.

    Même montage que `tests_qj2_seller_notifications` (owner explicite) — le
    seul chemin déterministe pour que `notify_new_lead` ait un destinataire."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        self.company = Company.objects.create(nom='Trace Notif', slug='trace-notif')
        self.owner = get_user_model().objects.create_user(
            username='vendeur_trace', password='x',
            company=self.company, role_legacy='responsable')

    def corps(self, **champs):
        from apps.crm.services import notify_new_lead
        from apps.notifications.models import Notification

        lead = Lead.objects.create(
            company=self.company, nom='Nadia Berrada',
            telephone='0661222333', owner=self.owner, **champs)
        notify_new_lead(lead)
        return ' '.join(
            Notification.objects.filter(
                recipient=self.owner, event_type='lead_new')
            .values_list('body', flat=True))

    def test_notification_d_arrivee_annonce_le_trace(self):
        corps = self.corps(roof_outline=CONTOUR)
        self.assertIn('DESSINÉ le contour de son toit', corps)
        self.assertIn('4 points', corps)

    def test_notification_muette_sans_trace(self):
        """Sans contour, la notification ne parle JAMAIS de tracé."""
        corps = self.corps()
        self.assertNotEqual(corps, '', 'la notification doit bien exister')
        self.assertNotIn('DESSINÉ', corps)

    def test_contour_degenere_non_annonce(self):
        """Moins de 3 sommets : ce n'est pas un tracé — rien n'est annoncé."""
        corps = self.corps(roof_outline=[[33.589, -7.603]])
        self.assertNotIn('DESSINÉ', corps)
