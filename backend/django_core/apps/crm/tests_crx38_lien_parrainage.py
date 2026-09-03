"""CRX38 — le lien de parrainage post-signature (PUB69) atteint enfin le
commercial.

CE QUI ÉTAIT FAUX. ``ventes.services.installation_share_link`` existe, est
testé (PUB69) et fabrique le lien « mon installation » d'un devis ACCEPTÉ —
celui que le client peut faire suivre, porteur des UTM
``parrainage_whatsapp`` qui mesurent le bouche-à-oreille organique. AUCUN code
ne l'appelait : la capacité était complète et ORPHELINE, donc le canal de
parrainage n'existait que sur le papier.

LA RÈGLE. À l'acceptation du devis — l'instant exact de l'enchantement — le
commercial reçoit le lien DÉJÀ PRÊT, avec le message WhatsApp tout fait.
Aucun envoi automatique au client : c'est un humain qui décide.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_crx38_lien_parrainage -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client, Lead
from apps.notifications.models import Notification
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
TITRE = 'Lien de parrainage prêt'


class _Base(TestCase):
    slug = 'crx38'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.commercial = User.objects.create_user(
            username='%s-commercial' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='CRX38',
            email='%s@example.invalid' % self.slug)
        self._n = 0

    def _devis(self, *, statut=Devis.Statut.ACCEPTE, lead=None,
               created_by=None):
        self._n += 1
        return Devis.objects.create(
            company=self.company,
            reference='DEV-%s-CRX38%02d' % (MONTH, self._n),
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'), created_by=created_by)

    def _accepter(self, devis):
        with self.captureOnCommitCallbacks(execute=True):
            devis_accepted.send(
                sender=None, devis=devis, user=None, ancien_statut='envoye')

    def _notifs(self):
        return [n for n in Notification.objects.all() if TITRE in n.title]


class LeCommercialRecoitLeLienPret(_Base):
    """LE TEST ROUGE — aujourd'hui personne n'appelle PUB69."""

    slug = 'crx38-recoit'

    def test_le_proprietaire_du_lead_est_notifie(self):
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', owner=self.commercial)
        devis = self._devis(lead=lead)
        Notification.objects.all().delete()   # ignore la notif d'assignation

        self._accepter(devis)

        notifs = self._notifs()
        self.assertEqual(
            len(notifs), 1,
            "le lien de parrainage n'atteint personne : PUB69 reste orphelin.")
        self.assertEqual(notifs[0].recipient_id, self.commercial.pk)
        self.assertEqual(notifs[0].company_id, self.company.pk)

    def test_le_corps_porte_le_lien_utm_et_le_message_whatsapp(self):
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', owner=self.commercial)
        devis = self._devis(lead=lead)
        Notification.objects.all().delete()

        self._accepter(devis)

        corps = self._notifs()[0].body
        link = ShareLink.objects.filter(devis=devis).first()
        self.assertIsNotNone(
            link, 'le ShareLink PUB69 doit avoir été créé (ou réutilisé).')
        self.assertIn(link.token, corps)
        self.assertIn('utm_campaign=parrainage_whatsapp', corps)
        self.assertIn('https://wa.me/?text=', corps)

    def test_a_defaut_de_lead_le_createur_du_devis_est_notifie(self):
        devis = self._devis(created_by=self.commercial)
        Notification.objects.all().delete()

        self._accepter(devis)

        notifs = self._notifs()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].recipient_id, self.commercial.pk)


class LesCasOuRienNePart(_Base):
    slug = 'crx38-silence'

    def test_un_devis_non_accepte_ne_produit_aucun_lien(self):
        """La garde PUB69 tient : avant signature, ce n'est pas encore « son
        installation »."""
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', owner=self.commercial)
        devis = self._devis(statut=Devis.Statut.ENVOYE, lead=lead)
        Notification.objects.all().delete()

        self._accepter(devis)

        self.assertEqual(self._notifs(), [])
        self.assertFalse(ShareLink.objects.filter(devis=devis).exists())

    def test_sans_destinataire_personne_n_est_notifie(self):
        """Ni propriétaire de lead ni créateur : on ne choisit pas au hasard."""
        devis = self._devis()
        Notification.objects.all().delete()

        self._accepter(devis)

        self.assertEqual(self._notifs(), [])

    def test_un_echec_du_lien_ne_casse_jamais_l_acceptation(self):
        lead = Lead.objects.create(
            company=self.company, nom='Bennani', owner=self.commercial)
        devis = self._devis(lead=lead)
        Notification.objects.all().delete()

        with mock.patch('apps.ventes.services.installation_share_link',
                        side_effect=RuntimeError('boom')):
            self._accepter(devis)      # ne doit pas lever

        self.assertEqual(self._notifs(), [])
