"""CADV8 (C-CADV-008) — la relance cadencée des devis (QJ4) saute tout devis
dont le lead est « ne plus contacter » (loi 09-08 art. 9, ACRM17) : ni
notification, ni brouillon wa.me, ni ligne ``DevisNudgeLog``. L'opposition
levée, le palier dû part au passage suivant.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_facture_relances_devis_opposition"
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.crm import stages

User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    DEVIS_NUDGE_DAYS=[2, 5, 10])
class NudgeOppositionTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client, Lead
        from apps.ventes.models import Devis
        from authentication.models import Company
        self.company = Company.objects.create(nom='CADV8', slug='cadv8-co')
        self.vendeur = User.objects.create_user(
            username='cadv8_vendeur', password='x', role_legacy='responsable',
            company=self.company, email='vendeur-cadv8@example.invalid')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='CADV8',
            email='cadv8@example.invalid')
        self.oppose = Lead.objects.create(
            company=self.company, nom='Oppose', stage=stages.QUOTE_SENT,
            telephone='+212612340008', ne_plus_contacter=True)
        normal = Lead.objects.create(
            company=self.company, nom='Normal', stage=stages.QUOTE_SENT,
            telephone='+212612340009')
        # Midi local de J-3 (jours calendaires à Casablanca, cf. QJ4).
        envoi = datetime.combine(
            timezone.localdate() - timedelta(days=3), time(12, 0),
            tzinfo=timezone.get_current_timezone())
        self.devis_oppose, self.devis_normal = (
            Devis.objects.create(
                company=self.company, reference=f'DEV-CADV8-{n}',
                client=client, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), date_envoi=envoi,
                created_by=self.vendeur)
            for n, lead in (('O', self.oppose), ('N', normal)))

    def test_lead_oppose_ne_recoit_aucune_relance(self):
        from apps.ventes.models import DevisNudgeLog
        from apps.ventes.services import send_devis_followup_nudges

        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertFalse(DevisNudgeLog.objects.filter(
            devis=self.devis_oppose).exists())
        self.assertEqual(DevisNudgeLog.objects.filter(
            devis=self.devis_normal).count(), 1)

        # Opposition levée ⇒ le palier dû part au passage suivant.
        self.oppose.ne_plus_contacter = False
        self.oppose.save(update_fields=['ne_plus_contacter'])
        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertEqual(DevisNudgeLog.objects.filter(
            devis=self.devis_oppose).count(), 1)

    def _devis_archive_et_perdu(self):
        from apps.crm.models import Lead
        from apps.ventes.models import Devis
        leads = [Lead.objects.create(
            company=self.company, nom=nom, stage=stages.QUOTE_SENT,
            telephone=tel, **etat) for nom, tel, etat in (
                ('Archive', '+212612340010', {'is_archived': True}),
                ('Perdu', '+212612340011', {'perdu': True}))]
        return leads, [Devis.objects.create(
            company=self.company, reference=f'DEV-ASUP42-{n}',
            client=self.devis_normal.client, lead=lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=self.devis_normal.date_envoi, created_by=self.vendeur)
            for n, lead in enumerate(leads)]

    def test_lead_archive_ou_perdu_ne_recoit_aucune_relance(self):
        """ASUP42 (C-ASUP-016) — lead archivé ou perdu : aucun DevisNudgeLog,
        aucune notification ; le témoin part ; lead restauré ⇒ le palier part.
        Mutant : retirer `is_archived` du prédicat ⇒ échec."""
        from apps.notifications.models import Notification
        from apps.ventes.models import DevisNudgeLog
        from apps.ventes.services import send_devis_followup_nudges
        (archive, perdu), ecartes = self._devis_archive_et_perdu()
        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertEqual(DevisNudgeLog.objects.filter(
            devis=self.devis_normal).count(), 1)
        for d in ecartes:
            self.assertFalse(DevisNudgeLog.objects.filter(devis=d).exists())
            self.assertFalse(Notification.objects.filter(
                link=f'/ventes/devis?devis={d.id}').exists())
        archive.is_archived = False
        archive.save(update_fields=['is_archived'])
        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertTrue(DevisNudgeLog.objects.filter(devis=ecartes[0]).exists())

    def test_moteur_d_engagement_saute_le_lead_archive(self):
        """ASUP42 — `engagement_followup_engine` 25 h+ après l'envoi, lien jamais
        ouvert : rien pour les leads archivé et perdu, le témoin est signalé."""
        from apps.notifications.models import Notification
        from apps.ventes.models import ShareLink
        from apps.ventes.scheduled import engagement_followup_engine
        _leads, ecartes = self._devis_archive_et_perdu()
        for d in [self.devis_normal, *ecartes]:
            ShareLink.for_devis(d)
        engagement_followup_engine()
        self.assertTrue(Notification.objects.filter(
            link=f'/ventes/devis?devis={self.devis_normal.id}').exists())
        for d in ecartes:
            self.assertFalse(Notification.objects.filter(
                link=f'/ventes/devis?devis={d.id}').exists())
            self.assertFalse(ShareLink.objects.get(devis=d).engagement_triggers_fired)

    def test_lead_supprime_ne_recoit_aucune_relance(self):
        """ASUP58 (C-ASUP-VER2-105) — lead mis à la corbeille : ni
        DevisNudgeLog, ni notification (relance et moteur d'engagement) ;
        restauré ⇒ le palier part au passage suivant. Mutant : retirer
        ``avec_corbeille=True`` de ``_lead_ecarte`` ⇒ échec."""
        from apps.crm.models import Lead
        from apps.notifications.models import Notification
        from apps.ventes.models import Devis, DevisNudgeLog, ShareLink
        from apps.ventes.scheduled import engagement_followup_engine
        from apps.ventes.services import send_devis_followup_nudges
        lead = Lead.objects.create(
            company=self.company, nom='Supprime', stage=stages.QUOTE_SENT,
            telephone='+212612340012')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASUP58-S',
            client=self.devis_normal.client, lead=lead,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=self.devis_normal.date_envoi, created_by=self.vendeur)
        lead.soft_delete(self.vendeur)
        self.assertEqual(send_devis_followup_nudges(), 1)  # le témoin seul
        for d in (self.devis_normal, devis):
            ShareLink.for_devis(d)
        engagement_followup_engine()
        self.assertFalse(DevisNudgeLog.objects.filter(devis=devis).exists())
        self.assertFalse(Notification.objects.filter(
            link=f'/ventes/devis?devis={devis.id}').exists())
        self.assertFalse(ShareLink.objects.get(devis=devis).engagement_triggers_fired)
        Lead.all_objects.get(pk=lead.pk).restore()
        # ASOC86 — la restauration rejoue la prochaine étape du lead : le suivi
        # (RelanceEtape ouverte) reprend la relance, et MRY7 / QX13 diffèrent
        # alors QJ4 pour ne pas doubler le message au client.
        from apps.crm.models import RelanceEtape
        from apps.ventes.domain.recouvrement import _lead_ecarte
        ouvertes = RelanceEtape.objects.filter(
            lead_id=lead.pk, statut=RelanceEtape.Statut.A_FAIRE)
        self.assertTrue(ouvertes.exists())
        self.assertFalse(_lead_ecarte(devis))
        # Sans suivi ouvert ni rappel planifié, le palier QJ4 repart au passage
        # suivant : la corbeille n'écarte plus le devis une fois restauré.
        ouvertes.update(statut=RelanceEtape.Statut.ANNULEE)
        Lead.objects.filter(pk=lead.pk).update(relance_date=None)
        self.assertEqual(send_devis_followup_nudges(), 1)
        self.assertEqual(DevisNudgeLog.objects.filter(devis=devis).count(), 1)

    def test_brouillon_client_texte_client_numero_e164(self):
        """AMSG39 (C-AMSG-027) — le brouillon wa.me de la notification vise le
        numéro E.164 du client et porte le gabarit CLIENT `devis_unique` de la
        société (jamais le mot au vendeur ni « TAQINOR ») ; numéro non
        normalisable ⇒ pas de brouillon. Mutant : remettre `msg_fr` ⇒ échec."""
        import urllib.parse
        from apps.crm.models import Client
        from apps.notifications.models import Notification
        from apps.parametres.models_company import CompanyProfile
        from apps.ventes.domain import recouvrement
        from apps.ventes.models import Devis
        from apps.ventes.services import send_devis_followup_nudges
        from apps.ventes.utils.whatsapp import build_single_devis_whatsapp
        profil = CompanyProfile.get(company=self.company)
        profil.nom = 'Soleil Nord'
        profil.save()
        envoi = self.devis_normal.date_envoi

        def devis(n, tel):
            client = Client.objects.create(
                company=self.company, nom=f'Tel{n}', prenom='AMSG39',
                email=f'amsg39-{n}@example.invalid', telephone=tel)
            return Devis.objects.create(
                company=self.company, reference=f'DEV-AMSG39-{n}',
                client=client, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), date_envoi=envoi,
                created_by=self.vendeur)
        valide, invalide = devis(1, '0600000058'), devis(2, '12')
        send_devis_followup_nudges()

        def corps(d):
            return Notification.objects.get(
                recipient=self.vendeur,
                link=f'/ventes/devis?devis={d.id}').body
        prefixe = 'Brouillon WhatsApp : https://wa.me/212600000058?text='
        ligne = next(x for x in corps(valide).splitlines()
                     if x.startswith('Brouillon WhatsApp'))
        self.assertTrue(ligne.startswith(prefixe), ligne)
        texte = urllib.parse.unquote(ligne[len(prefixe):])
        self.assertEqual(texte, build_single_devis_whatsapp(None, valide)[0])
        self.assertIn('DEV-AMSG39-1', texte)
        self.assertNotIn('Pensez à relancer', texte)
        self.assertNotIn('TAQINOR', texte)
        self.assertNotIn('Brouillon WhatsApp', corps(invalide))
        for gabarit in (recouvrement._NUDGE_MSG_FR, recouvrement._NUDGE_MSG_AR):
            self.assertNotIn('TAQINOR', gabarit)
            self.assertIn('{signature}', gabarit)

    def test_brouillon_vise_le_contact_du_lead(self):
        """AMSG86 (C-AMSG-VER1-103) — devis lié à un lead ET à un client : le
        brouillon vise le WhatsApp du lead (règle AMSG33), le témoin sans lead
        garde le téléphone du client. Mutant : remettre `client.telephone` ⇒
        échec."""
        from apps.crm.models import Client, Lead
        from apps.notifications.models import Notification
        from apps.ventes.models import Devis
        from apps.ventes.services import send_devis_followup_nudges
        client = Client.objects.create(
            company=self.company, nom='Tel', prenom='AMSG86',
            email='amsg86@example.invalid', telephone='0600000058')
        lead = Lead.objects.create(
            company=self.company, nom='Lead AMSG86', stage=stages.QUOTE_SENT,
            whatsapp='+212612340021', telephone='+212612340022')
        lie, temoin = (Devis.objects.create(
            company=self.company, reference=f'DEV-AMSG86-{n}', client=client,
            lead=le_lead, statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=self.devis_normal.date_envoi, created_by=self.vendeur)
            for n, le_lead in ((1, lead), (2, None)))
        send_devis_followup_nudges()

        def ligne(d):
            corps = Notification.objects.get(
                recipient=self.vendeur,
                link=f'/ventes/devis?devis={d.id}').body
            return next(x for x in corps.splitlines()
                        if x.startswith('Brouillon WhatsApp'))
        self.assertTrue(ligne(lie).startswith(
            'Brouillon WhatsApp : https://wa.me/212612340021?text='),
            ligne(lie))
        self.assertTrue(ligne(temoin).startswith(
            'Brouillon WhatsApp : https://wa.me/212600000058?text='),
            ligne(temoin))

    def test_journal_sans_numero_ni_texte_client(self):
        """AMSG87 (C-AMSG-VER1-104) — la ligne « QJ4 nudge wa_draft » garde
        référence, niveau, jours et vendeur, sans numéro, ni `wa.me`, ni lien
        de proposition, ni texte du gabarit ; la notification garde le
        brouillon. Mutant : remettre `wa_url` dans l'appel ⇒ échec."""
        from apps.crm.models import Client
        from apps.notifications.models import Notification
        from apps.ventes.models import Devis
        from apps.ventes.services import send_devis_followup_nudges
        from apps.ventes.utils.whatsapp import build_single_devis_whatsapp
        client = Client.objects.create(
            company=self.company, nom='Journal', prenom='AMSG87',
            email='amsg87@example.invalid', telephone='0600000058')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AMSG87-1', client=client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=self.devis_normal.date_envoi, created_by=self.vendeur)
        with self.assertLogs('apps.ventes.services', 'INFO') as journal:
            send_devis_followup_nudges()
        ligne = next(m for m in journal.output
                     if 'QJ4 nudge wa_draft' in m and 'DEV-AMSG87-1' in m)
        self.assertIn('niveau=0', ligne)
        self.assertIn('j+2', ligne)
        self.assertIn('cadv8_vendeur', ligne)
        texte = build_single_devis_whatsapp(None, devis)[0]
        premiere = next(x for x in texte.splitlines() if x.strip())
        for interdit in ('212600000058', '0600000058', 'wa.me', '/proposal',
                         '/proposition', premiere):
            self.assertNotIn(interdit, ligne)
        self.assertIn('Brouillon WhatsApp : https://wa.me/212600000058',
                      Notification.objects.get(
                          recipient=self.vendeur,
                          link=f'/ventes/devis?devis={devis.id}').body)
