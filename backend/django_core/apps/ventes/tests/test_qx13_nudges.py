"""QX13 — relances de devis visibles + réalistes + URLs qui atterrissent.

  * ``client_links`` produit ``/proposition/<token>`` (jamais ``/proposal/``) et
    chaque chemin émis existe dans la table de routes du site ;
  * la branche wa_draft crée une vraie Notification (DEVIS_NUDGE_DUE) ;
  * suppression : relance planifiée / engagement récent → pas de relance.
"""
import pathlib
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, ShareLink
from apps.ventes.utils import client_links

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
# parents: [0]=tests [1]=ventes [2]=apps [3]=django_core [4]=backend [5]=repo
# root. apps/web vit à la RACINE du dépôt, pas sous backend/ → parents[5].
WEB_PAGES = (pathlib.Path(__file__).resolve().parents[5]
             / 'apps' / 'web' / 'src' / 'pages')


class Qx13ClientLinksTests(TestCase):
    def test_proposition_path_is_correct(self):
        self.assertEqual(client_links.proposition_path('abc'),
                         '/proposition/abc')
        self.assertNotIn('/proposal/', client_links.proposition_path('abc'))

    @override_settings(SITE_URL='https://taqinor.ma')
    def test_proposition_url_absolute(self):
        self.assertEqual(client_links.proposition_url('t'),
                         'https://taqinor.ma/proposition/t')

    def test_every_emitted_path_exists_in_website_routes(self):
        # Chaque chemin client-facing RÉELLEMENT émis doit correspondre à un
        # fichier [token].astro du site (garde anti-lien-mort). Seul
        # « /proposition » est émis aujourd'hui (nudges QX13). La page
        # « /suivi/<token> » est WEB_PLAN WJ115 (session site) : l'endpoint ERP
        # /suivi (QX34) existe mais AUCUN message client n'émet encore ce lien —
        # réactiver l'assertion /suivi quand WJ115 aura livré la page.
        checks = {
            client_links.proposition_path('X'): 'proposition',
        }
        for _path, folder in checks.items():
            # PV84 — la route est devenue un attrape-tout ``[...token].astro``
            # (elle accepte /proposition/<token> ET /proposition/<slug>/<token>,
            # le token = dernier segment). L'ancien nom reste accepté pour ne
            # pas re-rougir si la page redevenait un paramètre simple.
            candidats = [WEB_PAGES / folder / '[...token].astro',
                         WEB_PAGES / folder / '[token].astro']
            self.assertTrue(
                any(c.exists() for c in candidats),
                f'Route site manquante pour {folder} : {candidats}')


class Pv84CheminPropositionSlugTests(TestCase):
    """ADEV97 (remplace PV84) — le lien client ne porte PLUS le nom du client :
    ``chemin_proposition`` produit ``/proposition/<token>`` (aucune donnée
    personnelle dans une capacité qu'on transfère). Les liens PV84 déjà
    envoyés (``/proposition/<slug>/<token>``) restent servis par la route
    attrape-tout du site (le token est le dernier segment)."""

    def setUp(self):
        self.company = Company.objects.create(nom='PV84 Co')

    def _devis(self, nom='', prenom='', lead=None):
        client = Client.objects.create(
            company=self.company, nom=nom, prenom=prenom,
            email=f'pv84-{nom}-{prenom}-{Client.objects.count()}@ex.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-PV84-{Devis.objects.count()}',
            client=client, lead=lead, taux_tva=Decimal('20'),
            statut=Devis.Statut.BROUILLON)

    def test_aucun_nom_dans_le_chemin(self):
        for nom, prenom in (('Aït Benhaddou', 'Éléonore'), ('Alaoui', 'Karim'),
                            ('A' * 80, ''), ('', '')):
            with self.subTest(nom=nom):
                devis = self._devis(nom=nom, prenom=prenom)
                self.assertEqual(
                    client_links.chemin_proposition(devis, 'tok'),
                    '/proposition/tok')

    def test_ni_lead_ni_telephone_ni_email(self):
        lead = Lead.objects.create(
            company=self.company, nom='Fallback', prenom='Lead')
        devis = self._devis(nom='Karim', prenom='Alaoui', lead=lead)
        devis.client.telephone = '+212600000000'
        devis.client.save(update_fields=['telephone'])
        chemin = client_links.chemin_proposition(devis, 'tok')
        for fuite in ('karim', 'alaoui', 'fallback', '600000000', '@'):
            self.assertNotIn(fuite, chemin.lower())

    def test_meme_chemin_que_proposition_path(self):
        devis = self._devis(nom='Alaoui', prenom='Karim')
        self.assertEqual(client_links.chemin_proposition(devis, 'tok'),
                         client_links.proposition_path('tok'))
        self.assertTrue(client_links.url_proposition(devis, 'tok')
                        .endswith('/proposition/tok'))


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Qx13NudgeNotificationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX13 Co')
        self.seller = User.objects.create_user(
            username='qx13_seller', password='x', role_legacy='commercial',
            company=self.company, email='')  # pas d'email → branche wa_draft
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX13',
            telephone='+212600000049')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX1301',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.seller,
            date_envoi=timezone.now() - timedelta(days=11))

    def test_due_nudge_creates_notification_with_working_link(self):
        from apps.ventes.services import send_devis_followup_nudges
        from apps.notifications.models import Notification
        from apps.notifications.types_evenements import EventType
        send_devis_followup_nudges()
        notif = Notification.objects.filter(
            recipient=self.seller,
            event_type=EventType.DEVIS_NUDGE_DUE).first()
        self.assertIsNotNone(notif)
        self.assertIn(str(self.devis.id), notif.link)
        # Le corps porte le lien proposition (jamais /proposal/).
        self.assertNotIn('/proposal/', notif.body or '')

    def test_suppressed_when_relance_planned(self):
        from apps.ventes.services import send_devis_followup_nudges
        from apps.notifications.models import Notification
        lead = Lead.objects.create(
            company=self.company, nom='Lead', telephone='+212600000049',
            relance_date=timezone.localdate() + timedelta(days=3))
        self.devis.lead = lead
        self.devis.save(update_fields=['lead'])
        send_devis_followup_nudges()
        self.assertFalse(Notification.objects.filter(
            recipient=self.seller).exists())

    def test_suppressed_when_recent_engagement(self):
        from apps.ventes.services import send_devis_followup_nudges
        from apps.notifications.models import Notification
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            last_viewed_at=timezone.now())
        send_devis_followup_nudges()
        self.assertFalse(Notification.objects.filter(
            recipient=self.seller).exists())
