"""Tests NTCON18 — Photo-rapport hebdomadaire automatique.

Couvre : OPT-IN strict (aucun envoi sans abonnement actif), collecte des
photos de la PÉRIODE sur les trois sources (chantier + réserves NTCON1 +
journal NTCON6) sans fuite d'un autre chantier, no-op propre sans clé email,
envoi réel avec clé (PDF en pièce jointe + ``dernier_envoi`` posé), et la
commande de gestion (y compris son refus d'une date invalide).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    AbonnementRapportPhoto, JournalChantier, ReserveChantier,
)

from .helpers import attach, make_chantier, make_company, make_user

PDF_FAKE = b'%PDF-1.4 test'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _datee(attachment, jour):
    """Force la date de dépôt (``created_at`` est ``auto_now_add``)."""
    from apps.records.models import Attachment
    Attachment.objects.filter(pk=attachment.pk).update(
        created_at=timezone.make_aware(
            datetime(jour.year, jour.month, jour.day, 12, 0)))


class RapportPhotoHebdoTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.au = timezone.localdate()
        self.du = self.au - timedelta(days=6)

        # MinIO n'est jamais joint par un test : les octets sont simulés
        # (le code réel passe par ``records.storage.fetch_attachment``).
        patcher = patch(
            'apps.records.storage.fetch_attachment',
            return_value=(b'octets-image-simules', None))
        self.fetch_attachment = patcher.start()
        self.addCleanup(patcher.stop)

        self.reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, description='Fissure')
        self.journal = JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=self.au)

        _datee(attach(self.co, self.user, self.chantier, 'pendant', 'a.png'),
               self.au)
        _datee(attach(self.co, self.user, self.reserve, 'apres', 'b.png'),
               self.au - timedelta(days=2))
        _datee(attach(self.co, self.user, self.journal, '', 'c.png'),
               self.au - timedelta(days=3))
        # Hors période (il y a 30 jours) — ne doit JAMAIS apparaître.
        _datee(attach(self.co, self.user, self.chantier, 'avant', 'vieux.png'),
               self.au - timedelta(days=30))

        # Autre chantier de la MÊME société — jamais mélangé.
        self.autre_chantier = make_chantier(self.co)
        _datee(
            attach(self.co, self.user, self.autre_chantier, 'pendant', 'x.png'),
            self.au)

    # ── Collecte ────────────────────────────────────────────────────────
    def test_collecte_les_trois_sources_de_la_periode(self):
        photos = services.collecter_photos_periode(
            self.chantier, self.du, self.au)
        noms = sorted(p['filename'] for p in photos)
        self.assertEqual(noms, ['a.png', 'b.png', 'c.png'])
        self.assertEqual(
            sorted({p['source'] for p in photos}),
            ['Chantier', 'Journal', 'Réserve'])

    def test_photo_d_un_autre_chantier_exclue(self):
        photos = services.collecter_photos_periode(
            self.autre_chantier, self.du, self.au)
        self.assertEqual([p['filename'] for p in photos], ['x.png'])

    def test_octets_embarques_en_data_uri(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'octets-image-simules', None)):
            photos = services.collecter_photos_periode(
                self.chantier, self.du, self.au)
        self.assertTrue(all(
            p['data_uri'].startswith('data:image/png;base64,')
            for p in photos))

    # ── Opt-in / envoi ──────────────────────────────────────────────────
    def test_opt_in_strict_sans_abonnement_aucun_envoi(self):
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au)
        self.assertEqual(resultat['examines'], 0)
        self.assertEqual(resultat['envoyes'], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_abonnement_inactif_ignore(self):
        AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=self.chantier, actif=False,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au)
        self.assertEqual(resultat['examines'], 0)

    @override_settings(EMAIL_BACKEND=LOCMEM, ANYMAIL={})
    def test_sans_cle_email_noop_propre(self):
        abonnement = AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=self.chantier,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au)
        self.assertEqual(resultat['examines'], 1)
        self.assertEqual(resultat['envoyes'], 0)
        self.assertFalse(resultat['email_configure'])
        self.assertEqual(len(mail.outbox), 0)
        abonnement.refresh_from_db()
        self.assertIsNone(abonnement.dernier_envoi)

    @override_settings(
        EMAIL_BACKEND=LOCMEM, ANYMAIL={'SENDGRID_API_KEY': 'sg-key'})
    def test_envoi_avec_cle_joint_le_pdf(self):
        abonnement = AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=self.chantier,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE) as rendu:
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au)
        self.assertEqual(resultat['envoyes'], 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['moe@example.com'])
        self.assertEqual(len(message.attachments), 1)
        self.assertEqual(message.attachments[0][2], 'application/pdf')
        # Le rendu n'a reçu QUE les photos de la période (3).
        self.assertEqual(len(rendu.call_args[0][3]), 3)
        abonnement.refresh_from_db()
        self.assertEqual(abonnement.dernier_envoi, self.au)

    @override_settings(
        EMAIL_BACKEND=LOCMEM, ANYMAIL={'SENDGRID_API_KEY': 'sg-key'})
    def test_dry_run_n_envoie_rien(self):
        AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=self.chantier,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au, dry_run=True)
        self.assertEqual(resultat['envoyes'], 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND=LOCMEM, ANYMAIL={'SENDGRID_API_KEY': 'sg-key'})
    def test_chantier_sans_photo_compte_a_part(self):
        chantier_vide = make_chantier(self.co)
        AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=chantier_vide,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            resultat = services.envoyer_rapports_photo_hebdo(
                du=self.du, au=self.au)
        self.assertEqual(resultat['sans_photo'], 1)
        self.assertEqual(resultat['envoyes'], 0)

    # ── Commande de gestion ─────────────────────────────────────────────
    def test_commande_dry_run(self):
        AbonnementRapportPhoto.objects.create(
            company=self.co, chantier=self.chantier,
            destinataires=['moe@example.com'])
        with patch('apps.btp_chantier.pdf.render_rapport_photo_pdf',
                   return_value=PDF_FAKE):
            call_command('rapport_photo_hebdo', '--dry-run')
        self.assertEqual(len(mail.outbox), 0)

    def test_commande_refuse_une_date_invalide(self):
        with self.assertRaises(CommandError) as ctx:
            call_command('rapport_photo_hebdo', '--du', '12-2026-01')
        self.assertIn('--du', str(ctx.exception))

    def test_commande_refuse_une_periode_inversee(self):
        with self.assertRaises(CommandError):
            call_command(
                'rapport_photo_hebdo', '--du', '2026-03-01',
                '--au', '2026-02-01')
