"""
Tests for QJ14 — Server-side proposal email send action.

Covers:
  - POST /ventes/devis/{id}/envoyer-email/ sends an email via the locmem backend
    and creates an EmailLog record.
  - The devis is marked « envoyé » via mark_devis_sent (rule #4 — only path).
  - Idempotent: a second call on an already-envoyé devis still sends the email
    but does NOT re-stamp date_envoi or add a duplicate status chatter entry.
  - Company scoping: a request user from company A cannot reach a devis from B.
  - Missing email address (no client.email, no to_email body) → 409 + EmailLog
    with statut=echec.
  - A devis in a terminal status (accepté/refusé) is NOT regressed to envoyé,
    but the email is still delivered.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj14_email_send -v 2
"""
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.ventes.models import Devis, EmailLog, DevisActivity

User = get_user_model()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug='qj14-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': 'QJ14 Co'})[0]


def make_user(company, username=None):
    uname = username or f'u_{company.slug}'
    try:
        return User.objects.get(username=uname)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=uname, password='x',
            role_legacy='responsable', company=company)


def make_client(company, email='client@test.ma'):
    return Client.objects.create(
        company=company, nom='Tahiri', prenom='Yasmine',
        email=email, telephone='+212611000001')


def make_devis(company, user, client, statut='brouillon', ref=None):
    return Devis.objects.create(
        company=company,
        reference=ref or f'DEV-QJ14-{statut}',
        client=client,
        statut=statut,
        created_by=user,
    )


def make_api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def url(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/envoyer-email/'


def rendu_ok(test):
    """ADVS12 — pièce jointe bouchonnée pour un ``setUp`` : le moteur REFUSE
    ces devis de test sans ligne, et un refus n'envoie plus rien."""
    for correctif in (
            mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', return_value='k.pdf'),
            mock.patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF')):
        correctif.start()
        test.addCleanup(correctif.stop)


# ─── Tests ─────────────────────────────────────────────────────────────────────

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailAction(TestCase):
    """POST envoyer-email/ — envoi, EmailLog, statut."""

    def setUp(self):
        self.company = make_company('qj14-main')
        self.user = make_user(self.company)
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company, 'yasmine@test.ma')
        rendu_ok(self)

    def test_email_sent_and_log_created(self):
        """An email is delivered and an EmailLog record is written."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-001')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        # EmailLog created with statut=envoye
        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(log.company, self.company)
        self.assertIn('yasmine@test.ma', log.to_email)

    def test_devis_marked_envoye_via_service(self):
        """The devis is flipped to « envoyé » through mark_devis_sent (rule #4)."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-002')
        self.assertEqual(devis.statut, 'brouillon')

        self.api.post(url(devis.id), {}, format='json')

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')
        self.assertIsNotNone(devis.date_envoi)

    def test_chatter_entry_written(self):
        """A chatter (DevisActivity) note is written after send."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-003')
        self.api.post(url(devis.id), {}, format='json')
        # At least one activity entry exists (from mark_devis_sent or chatter note)
        self.assertTrue(
            DevisActivity.objects.filter(devis=devis).exists(),
            'Expected at least one DevisActivity entry after email send')

    def test_idempotent_already_envoye(self):
        """Calling again on an already-envoyé devis sends the email but does NOT
        re-stamp date_envoi or add a duplicate status chatter entry."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-004')

        # First call — flips to envoyé
        self.api.post(url(devis.id), {}, format='json')
        devis.refresh_from_db()
        first_stamp = devis.date_envoi
        status_activities_before = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION,
            new_value='Envoyé').count()

        # Second call — email resent, no re-stamp
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.date_envoi, first_stamp,
                         'date_envoi must not change on re-send')
        status_activities_after = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION,
            new_value='Envoyé').count()
        self.assertEqual(
            status_activities_before, status_activities_after,
            'No duplicate status chatter entry on idempotent re-send')

    @override_settings(SITE_URL='https://plateforme.exemple.test')
    def test_lien_proposition_absolu_dans_le_corps(self):
        """APDF104 (rejeu en direct) — le corps par défaut porte l'URL ABSOLUE de
        la proposition (``url_proposition``, celle du PDF), jamais le seul
        chemin relatif « /proposition/<jeton> », inutilisable dans un e-mail."""
        from django.core import mail
        from apps.ventes.models import ShareLink
        from apps.ventes.utils.client_links import url_proposition
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-ABS')
        mail.outbox = []
        self.api.post(url(devis.id), {}, format='json')
        token = ShareLink.objects.filter(devis=devis).latest('created_at').token
        corps = mail.outbox[-1].body
        self.assertIn(url_proposition(devis, token), corps)
        self.assertTrue(url_proposition(devis, token).startswith('https://plateforme.exemple.test/'))
        self.assertNotIn(f'\n/proposition/{token}', corps)

    def test_custom_to_email_in_body(self):
        """Body to_email overrides client.email."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-005')
        resp = self.api.post(url(devis.id),
                             {'to_email': 'autre@dest.ma'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        log = EmailLog.objects.filter(devis=devis).last()
        self.assertIsNotNone(log)
        self.assertEqual(log.to_email, 'autre@dest.ma')

    def test_piece_jointe_au_format_memorise(self):
        """AMOT117 (C-AMOT-VER-050) — sans ``pdf_mode`` dans la requête, la
        pièce jointe suit le format du dernier rendu persisté ; un
        ``pdf_mode`` explicite prime ; sans rendu mémorisé : « full »."""
        from unittest import mock
        from apps.ventes.models import ShareLink
        cas = (({'pdf_mode': 'onepage'}, {}, 'onepage'),
               ({'pdf_mode': 'onepage'}, {'pdf_mode': 'full'}, 'full'),
               (None, {}, 'full'))
        for i, (memo, corps, attendu) in enumerate(cas):
            devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                               f'DEV-QJ14-FMT{i}')
            if memo is not None:
                Devis.objects.filter(pk=devis.pk).update(pdf_render_meta={'options': memo})
            with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                            return_value='k.pdf') as rendu, \
                    mock.patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF'):
                resp = self.api.post(url(devis.id), dict(corps), format='json')
            self.assertEqual(resp.status_code, 200, resp.data)
            opts = rendu.call_args.args[1]
            self.assertEqual(opts['pdf_mode'], attendu, (memo, corps))
            self.assertEqual(opts['share_token'],
                             ShareLink.objects.filter(devis=devis).latest('created_at').token)
            self.assertIs(rendu.call_args.kwargs.get('persist'), False)

    def _devis_de_lead_cree_il_y_a_20_jours(self, reference):
        """Un brouillon chiffré d'un lead, sans validité : le repli du moteur
        (création + délai) diffère de la date que l'envoi pose."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.crm.models import Lead
        from apps.parametres.models import CompanyProfile
        from apps.ventes.tests._quote_engine_common import make_devis as devis_chiffre
        profil = CompanyProfile.get(self.company)
        profil.quote_validity_days = 30
        profil.save()
        lead = Lead.objects.create(
            company=self.company, nom='Validite', prenom=reference, ville='Casablanca',
            telephone='+2126000130' + reference[-2:], email='validite@test.ma')
        devis = devis_chiffre(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '12', '1166.67', '20'),
            ('Onduleur réseau 5kW', '1', '14000', '20'),
        ], reference=reference)
        Devis.objects.filter(pk=devis.pk).update(
            lead=lead, date_validite=None,
            date_creation=timezone.now() - timedelta(days=20))
        devis.refresh_from_db()
        return devis

    def test_piece_jointe_imprime_la_validite_posee(self):
        """ADVS13 (C-ADVS-010) — le rendu suit la pose de la validité : le PDF
        joint imprime ``date_validite`` relue, pas le repli du moteur."""
        from apps.ventes.quote_engine import builder
        devis = self._devis_de_lead_cree_il_y_a_20_jours('DEV-QJ14-V01')
        vu = {}
        vrai = builder.build_quote_data

        def _batir(d, options=None, *a, **kw):
            data = vrai(d, options, *a, **kw)
            vu['valid_until'] = data['valid_until']
            return data

        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                        side_effect=builder.generate_premium_devis_pdf), \
                mock.patch.object(builder, 'build_quote_data', side_effect=_batir), \
                mock.patch('apps.ventes.quote_engine.residential.renderer.render_pdf_bytes',
                           return_value=b'%PDF-1.4 test'), \
                mock.patch('apps.ventes.utils.pdf._upload_pdf', return_value='cle/test.pdf'):
            resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')
        self.assertIsNotNone(devis.date_validite)
        self.assertEqual(vu['valid_until'], devis.date_validite.strftime('%d/%m/%Y'))

    def test_renvoi_d_un_envoye_ne_change_pas_la_validite(self):
        """ADVS13 — devis déjà envoyé : date inchangée."""
        from datetime import date
        devis = make_devis(self.company, self.user, self.client_obj, 'envoye', 'DEV-QJ14-V02')
        Devis.objects.filter(pk=devis.pk).update(date_validite=date(2031, 1, 15))
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.date_validite, date(2031, 1, 15))

    def test_rendu_ou_envoi_en_echec_annule_tout(self):
        """ADVS13 — rendu ou envoi en échec : brouillon, validité vide, aucun
        plan de relance, aucune note « envoyé » ; l'EmailLog ``echec`` reste."""
        from apps.crm.models import LeadActivity
        cas = (('V03', {'side_effect': ValueError('refus du moteur')}, None, 409),
               ('V04', {'return_value': 'k.pdf'}, (False, 'boom'), 502))
        for suffixe, rendu, envoi, attendu in cas:
            devis = self._devis_de_lead_cree_il_y_a_20_jours(f'DEV-QJ14-{suffixe}')
            with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', **rendu), \
                    mock.patch('apps.ventes.email_service._send', return_value=envoi):
                resp = self.api.post(url(devis.id), {}, format='json')
            self.assertEqual(resp.status_code, attendu, resp.data)
            self.assertEqual(resp.data['devis_statut'], 'brouillon')
            devis.refresh_from_db()
            self.assertEqual(devis.statut, 'brouillon')
            self.assertIsNone(devis.date_envoi)
            self.assertIsNone(devis.date_validite)
            self.assertFalse(LeadActivity.objects.filter(
                lead_id=devis.lead_id, body__icontains='Plan de relance').exists())
            self.assertFalse(DevisActivity.objects.filter(devis=devis, body__icontains='envoyé (à').exists())
            self.assertEqual(EmailLog.objects.get(devis=devis).statut, EmailLog.Statut.ECHEC)

    def test_corps_mal_type_400_sans_envoi(self):
        """ENF11 — un champ de mauvais type (entier, null) ou un corps non
        objet est refusé (400) AVANT tout effet : pas d'EmailLog, pas d'envoi."""
        devis = make_devis(self.company, self.user, self.client_obj, 'brouillon',
                           'DEV-QJ14-005B')
        # api-fuzz : une adresse mal formée est un 400, plus un 502 SMTP.
        for corps in ({'to_email': 5}, {'sujet': None}, {'pdf_mode': 1},
                      {'gamme_envoi': []}, [1, 2],
                      {'to_email': 'pas une adresse'}):
            resp = self.api.post(url(devis.id), corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.data))
        self.assertFalse(EmailLog.objects.filter(devis=devis).exists())

    def test_missing_email_returns_409_and_logs_echec(self):
        """No client email + no to_email in body → 409 (refus d état, ENF11) + EmailLog echec."""
        client_no_email = Client.objects.create(
            company=self.company, nom='Inconnu', telephone='+212611000002')
        devis = make_devis(self.company, self.user, client_no_email, 'brouillon',
                           'DEV-QJ14-006')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)

        log = EmailLog.objects.filter(devis=devis).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailScoping(TestCase):
    """Company scoping: another company's devis must not be reachable."""

    def setUp(self):
        self.company_a = make_company('qj14-a')
        self.company_b = make_company('qj14-b')
        self.user_a = make_user(self.company_a, 'u_qj14a')
        self.client_b = make_client(self.company_b, 'b@test.ma')
        self.devis_b = make_devis(self.company_b, self.user_a, self.client_b,
                                  'brouillon', 'DEV-QJ14-B1')
        self.api_a = make_api(self.user_a)

    def test_cross_company_devis_returns_404(self):
        """User from company A cannot reach a devis from company B."""
        resp = self.api_a.post(url(self.devis_b.id), {}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailTerminalStatus(TestCase):
    """A terminal-status devis (accepté/refusé) is never regressed."""

    def setUp(self):
        self.company = make_company('qj14-term')
        self.user = make_user(self.company, 'u_qj14t')
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company, 'term@test.ma')
        rendu_ok(self)

    def test_accepted_devis_not_regressed(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'accepte',
                           'DEV-QJ14-T1')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte',
                         'accepté devis must not be regressed to envoyé')

    def test_refused_devis_not_regressed(self):
        devis = make_devis(self.company, self.user, self.client_obj, 'refuse',
                           'DEV-QJ14-T2')
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'refuse',
                         'refusé devis must not be regressed to envoyé')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestEnvoyerEmailEchecNeMarquePas(TestCase):
    """QJR519 — un email en ÉCHEC ne marque plus le devis envoyé : 502, devis
    brouillon, date_envoi None, stage du lead inchangé, EmailLog ECHEC."""

    def setUp(self):
        from apps.crm import stages
        from apps.crm.models import Lead
        self.company = make_company('qj14-echec')
        self.user = make_user(self.company, 'u_qj14e')
        self.api = make_api(self.user)
        self.client_obj = make_client(self.company, 'echec@test.ma')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='Echec',
            telephone='+212600005190', stage=stages.CONTACTED)
        self.stage_initial = self.lead.stage

    def _devis_sans_onduleur(self, reference):
        from apps.ventes.tests._quote_engine_common import make_devis as devis_chiffre
        return devis_chiffre(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '8', '1166.67', '20'),
            ('Structure aluminium toiture', '1', '300', '20'),
        ], reference=reference)

    def test_rendu_refuse_aucun_mail_reste_brouillon(self):
        """ADVS12 (C-ADVS-009) — devis sans onduleur : le VRAI moteur refuse le
        rendu ; 409 nommé, aucun mail « ci-joint » sans PDF, devis brouillon."""
        devis = self._devis_sans_onduleur('DEV-QJ14-R1')
        with mock.patch('apps.ventes.email_service._send') as envoi:
            resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['code'], 'pdf_refuse')
        self.assertIn('onduleur', resp.data['detail'])
        self.assertEqual(resp.data['devis_statut'], 'brouillon')
        envoi.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertIsNone(devis.date_envoi)
        log = EmailLog.objects.get(devis=devis)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)
        self.assertIn('onduleur', log.erreur)

    def test_panne_de_stockage_502_pdf_indisponible(self):
        """ADVS12 — autre panne (rendu, stockage) : 502 ``pdf_indisponible``,
        le motif technique reste dans l'EmailLog, rien ne part."""
        devis = make_devis(self.company, self.user, self.client_obj,
                           'brouillon', 'DEV-QJ14-R2')
        with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', return_value='k.pdf'), \
                mock.patch('apps.ventes.utils.pdf.download_pdf', side_effect=OSError('minio muet')), \
                mock.patch('apps.ventes.email_service._send') as envoi:
            resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 502, resp.data)
        self.assertEqual(resp.data['code'], 'pdf_indisponible')
        self.assertNotIn('minio', resp.data['detail'])
        envoi.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertIn('minio muet', EmailLog.objects.get(devis=devis).erreur)

    def _cgv(self, puce):
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.objects.update_or_create(
            company=self.company, defaults={'cgv_bullets': [puce]})

    def test_envoi_avorte_ne_gele_pas_les_cgv(self):
        """ADVS29 (C-ADVS-008) — envoi avorté (aucune adresse, échec SMTP), CGV
        retouchées, envoi réussi : le gel et le PDF joint portent les CGV du
        jour ; rien n'est écrit par la tentative avortée."""
        def puces(clauses):
            return [c['bullets'] for c in clauses or []
                    if isinstance(c, dict) and c.get('type') == 'cgv_gelees']

        for suffixe, premier_corps, smtp, statut in (
                ('A1', {}, (True, ''), 409), ('A2', {'to_email': 'a@test.ma'}, (False, 'boom'), 502)):
            client = Client.objects.create(company=self.company, nom='Sans adresse',
                                           telephone='+2126110029' + suffixe[-1:] + '0')
            devis = make_devis(self.company, self.user, client, 'brouillon', f'DEV-QJ14-{suffixe}')
            avant = list(devis.clauses_appliquees or [])
            self._cgv('CGV A')
            imprime = {}

            def rendre(devis_id, *a, **k):
                imprime['puces'] = puces(Devis.objects.get(pk=devis_id).clauses_appliquees)
                return 'k.pdf'

            with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', side_effect=rendre), \
                    mock.patch('apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF'):
                with mock.patch('apps.ventes.email_service._send', return_value=smtp):
                    resp = self.api.post(url(devis.id), premier_corps, format='json')
                self.assertEqual(resp.status_code, statut, resp.data)
                devis.refresh_from_db()
                self.assertEqual(list(devis.clauses_appliquees or []), avant)
                self._cgv('CGV B')
                resp = self.api.post(url(devis.id), {'to_email': 'b@test.ma'}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)
            devis.refresh_from_db()
            self.assertEqual(puces(devis.clauses_appliquees), [['CGV B']])
            self.assertEqual(imprime['puces'], [['CGV B']])

    def test_echec_smtp_ne_marque_pas_envoye(self):
        rendu_ok(self)
        devis = make_devis(self.company, self.user, self.client_obj,
                           'brouillon', 'DEV-QJ14-E1')
        devis.lead = self.lead
        devis.save(update_fields=['lead'])
        with mock.patch('apps.ventes.email_service._send',
                        return_value=(False, 'boom')):
            resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 502, resp.data)
        self.assertIn('boom', resp.data['detail'])
        self.assertEqual(resp.data['email_statut'], EmailLog.Statut.ECHEC)
        self.assertEqual(resp.data['devis_statut'], 'brouillon')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertIsNone(devis.date_envoi)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, self.stage_initial)
        log = EmailLog.objects.get(devis=devis)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)
        self.assertEqual(log.erreur, 'boom')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_backend_console_ne_marque_pas_envoye(self):
        """AMSG28 (C-AMSG-008) — backend console : rien ne part, donc échec
        nommé, devis brouillon sans date d'envoi, lead inchangé, EmailLog échec."""
        from apps.ventes.email_service import EMAIL_NON_OPERATIONNEL
        rendu_ok(self)
        devis = make_devis(self.company, self.user, self.client_obj,
                           'brouillon', 'DEV-QJ14-C1')
        devis.lead = self.lead
        devis.save(update_fields=['lead'])
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 502, resp.data)
        self.assertIn(EMAIL_NON_OPERATIONNEL, resp.data['detail'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
        self.assertIsNone(devis.date_envoi)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, self.stage_initial)
        log = EmailLog.objects.get(devis=devis)
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)
        self.assertEqual(log.erreur, EMAIL_NON_OPERATIONNEL)
