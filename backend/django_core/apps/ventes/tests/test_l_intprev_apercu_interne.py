"""L-INTPREV (fondateur 25/08/2026) — second jeton « aperçu interne » sur
ShareLink : « both the quote link and the question link should have a
secondary internal link that commercial can visit without triggering the
notification ». Ce fichier couvre le côté PROPOSITION (ventes) uniquement —
le côté questionnaire (crm) est une autre lane.

ENQUÊTE — ce qui se déclenche AUJOURD'HUI à l'ouverture CLIENT (public_views.py) :
  1. ``_stamp_view`` (L123) — ``ShareLink.view_count``/``first_viewed_at``/
     ``last_viewed_at`` + miroir marketing ``_enregistrer_ouverture_marketing``
     → ``apps.marketing.models.OuverturePartage``.
  2. ``_notify_first_open`` (L176), sur la PREMIÈRE ouverture :
       a. ``noter_devis_ouvert`` (crm/services.py) — note chatter
          ``LeadActivity`` « Le client a ouvert le devis X » PUIS
          ``avancer_stage_sur_ouverture_devis`` (YLEAD10) : avance le
          ``Lead.stage`` à FOLLOW_UP + une SECONDE ``LeadActivity``
          (MODIFICATION, champ stage).
       b. ``notify_devis_opened`` — notification in-app (+ Web Push best-
          effort) au owner du lead (``apps.notifications.models.Notification``).
       c. ``_notifier_variante_consultee`` — notif à l'auteur du devis de
          base si CE devis est une variante CPQ (hors périmètre de ce test :
          aucun devis variante ici).
  3. ``proposal_engagement`` (beacon XSAL16) — ``ShareLink.engagement`` +
     au seuil, ``deep_engagement_logged_at`` + une note chatter « a commencé
     à lire en détail ».

Ce fichier prouve que le jeton INTERNE (``ShareLink.token_interne``) résout
le MÊME lien/devis SANS DÉCLENCHER AUCUN DE CES MÉCANISMES (b), refuse la
SIGNATURE (c), et que le mint (share-link) expose bien
``token_interne``/``path_interne`` — jamais branchés sur WhatsApp/l'envoi
(couvert côté frontend par DevisTab.test.jsx).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_intprev_apercu_interne -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.marketing.models import OuverturePartage
from apps.notifications.models import Notification
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import _resolve_share_link_by_token
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Interne', prenom='Test', email='',
        telephone='')


def make_lead(company, owner=None, stage=stages.QUOTE_SENT):
    return Lead.objects.create(
        company=company, nom='Prospect Interne', stage=stage, owner=owner)


def make_devis(company, client_obj, ref, lead=None):
    """Même patron que test_l_niv_otp_lecture.py : 2 lignes classifiables
    (onduleur réseau + panneau) — suffisant pour que build_quote_data (donc
    proposal_data/proposal_pdf) réussisse."""
    devis = Devis.objects.create(
        company=company, reference=ref, client=client_obj, lead=lead,
        statut='envoye', taux_tva=Decimal('20'))
    for desig, qty, pu in [('Onduleur réseau Deye 8kW', '1', '14000'),
                           ('Panneau Canadian Solar 550W', '10', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{ref[-6:]}-{desig[:8]}',
            prix_vente=Decimal(pu), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def make_link(devis, otp_lecture=False):
    """Un ShareLink créé via l'ORM porte déjà les DEUX jetons (default du
    champ) — comme tout lien miné après cette migration."""
    return ShareLink.objects.create(
        company=devis.company, devis=devis, otp_lecture=otp_lecture)


_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-INTPREV.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub',
)


# ═══════════════════════════════════════════════════════════════════════════
# (a) résolution — jeton public ET jeton interne
# ═══════════════════════════════════════════════════════════════════════════

class TestResolutionDesDeuxJetons(TestCase):
    def setUp(self):
        self.company = make_company('lintprev-resolve')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-R1')
        self.link = make_link(self.devis)

    def test_les_deux_jetons_different_et_sont_uniques(self):
        self.assertTrue(self.link.token)
        self.assertTrue(self.link.token_interne)
        self.assertNotEqual(self.link.token, self.link.token_interne)

    def test_jeton_public_resout_via_interne_false(self):
        link, via_interne = _resolve_share_link_by_token(self.link.token)
        self.assertEqual(link.pk, self.link.pk)
        self.assertFalse(via_interne)

    def test_jeton_interne_resout_via_interne_true(self):
        link, via_interne = _resolve_share_link_by_token(self.link.token_interne)
        self.assertEqual(link.pk, self.link.pk)
        self.assertTrue(via_interne)

    def test_jeton_inconnu_ne_resout_rien(self):
        link, via_interne = _resolve_share_link_by_token('inconnu-xyz')
        self.assertIsNone(link)
        self.assertFalse(via_interne)

    def test_lien_expire_ne_resout_par_aucun_jeton(self):
        from datetime import timedelta
        from django.utils import timezone
        self.link.expires_at = timezone.now() - timedelta(days=1)
        self.link.save(update_fields=['expires_at'])
        link_pub, _ = _resolve_share_link_by_token(self.link.token)
        link_int, _ = _resolve_share_link_by_token(self.link.token_interne)
        self.assertIsNone(link_pub)
        self.assertIsNone(link_int)

    def test_endpoint_public_document_accepte_les_deux_jetons(self):
        with _PATCH_GEN, _PATCH_DL:
            resp_pub = APIClient().get(
                f'/api/django/public/document/{self.link.token}/')
            resp_int = APIClient().get(
                f'/api/django/public/document/{self.link.token_interne}/')
        self.assertEqual(resp_pub.status_code, 200)
        self.assertEqual(resp_int.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# (b) ZÉRO trace via le jeton interne — un mécanisme par test, public vs interne
# ═══════════════════════════════════════════════════════════════════════════

class TestZeroTraceCompteurDeVues(TestCase):
    """(b.1) view_count/first_viewed_at/last_viewed_at — public_document,
    proposal_data, proposal_pdf."""

    def setUp(self):
        self.company = make_company('lintprev-stamp')
        self.client_obj = make_client_obj(self.company)

    def _devis_et_lien(self, ref):
        devis = make_devis(self.company, self.client_obj, ref)
        return devis, make_link(devis)

    def test_public_document_jeton_interne_ne_stampe_pas(self):
        _, link = self._devis_et_lien('DEV-IP-S1')
        with _PATCH_GEN, _PATCH_DL:
            resp = APIClient().get(
                f'/api/django/public/document/{link.token_interne}/')
        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 0)
        self.assertIsNone(link.first_viewed_at)
        self.assertIsNone(link.last_viewed_at)

    def test_public_document_jeton_public_stampe_toujours(self):
        """Témoin positif : le jeton public continue de stamper (rien cassé)."""
        _, link = self._devis_et_lien('DEV-IP-S2')
        with _PATCH_GEN, _PATCH_DL:
            resp = APIClient().get(
                f'/api/django/public/document/{link.token}/')
        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 1)
        self.assertIsNotNone(link.first_viewed_at)

    def test_proposal_data_jeton_interne_ne_stampe_pas(self):
        _, link = self._devis_et_lien('DEV-IP-S3')
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{link.token_interne}/data/')
        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 0)
        self.assertIsNone(link.first_viewed_at)

    def test_proposal_pdf_jeton_interne_ne_stampe_pas(self):
        _, link = self._devis_et_lien('DEV-IP-S4')
        with _PATCH_GEN, _PATCH_DL:
            resp = DjangoClient().get(
                f'/api/django/public/proposal/{link.token_interne}/pdf/')
        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 0)
        self.assertIsNone(link.first_viewed_at)

    def test_deux_ouvertures_via_interne_deux_fois_zero(self):
        """Idempotent : répéter l'aperçu interne n'accumule jamais rien."""
        _, link = self._devis_et_lien('DEV-IP-S5')
        for _ in range(3):
            resp = DjangoClient().get(
                f'/api/django/public/proposal/{link.token_interne}/data/')
            self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 0)


class TestZeroTraceMiroirMarketing(TestCase):
    """(b.1 bis) OuverturePartage — jamais écrit via le jeton interne."""

    def setUp(self):
        self.company = make_company('lintprev-mkt')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-M1')
        self.link = make_link(self.devis)

    def test_jeton_interne_ne_cree_aucune_ouverture_partage(self):
        self.assertEqual(OuverturePartage.objects.filter(
            company=self.company).count(), 0)
        DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/')
        self.assertEqual(OuverturePartage.objects.filter(
            company=self.company).count(), 0)

    def test_jeton_public_cree_une_ouverture_partage(self):
        DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(OuverturePartage.objects.filter(
            company=self.company).count(), 1)


class TestZeroTraceChatterEtStageFunnel(TestCase):
    """(b.2.a) LeadActivity (note + avance YLEAD10) — jamais via l'interne."""

    def setUp(self):
        self.company = make_company('lintprev-chatter')
        self.client_obj = make_client_obj(self.company)
        self.owner = User.objects.create_user(
            username='lintprev-owner', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = make_lead(self.company, owner=self.owner)
        self.devis = make_devis(
            self.company, self.client_obj, 'DEV-IP-C1', lead=self.lead)
        self.link = make_link(self.devis)

    def test_jeton_interne_ne_pose_aucune_note_ni_avance_de_stage(self):
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_jeton_public_pose_la_note_et_avance_le_stage(self):
        """Témoin positif : le comportement QJ1/YLEAD10 existant n'a pas
        bougé pour le jeton public."""
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.FOLLOW_UP)
        notes = LeadActivity.objects.filter(lead=self.lead)
        self.assertTrue(any(
            'ouvert le devis DEV-IP-C1' in (n.body or '') for n in notes))


class TestZeroTraceNotificationOwner(TestCase):
    """(b.2.b) Notification in-app au owner — jamais via l'interne."""

    def setUp(self):
        self.company = make_company('lintprev-notif')
        self.client_obj = make_client_obj(self.company)
        self.owner = User.objects.create_user(
            username='lintprev-owner2', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = make_lead(self.company, owner=self.owner)
        self.devis = make_devis(
            self.company, self.client_obj, 'DEV-IP-N1', lead=self.lead)
        self.link = make_link(self.devis)

    def test_jeton_interne_ne_notifie_jamais_le_owner(self):
        # Recalage CI 25/08 — la FIXTURE elle-même notifie déjà le owner
        # (signal PRÉ-EXISTANT ``lead_assigned`` sur transition d'owner à la
        # création du lead, apps.notifications.signals.lead_post_save —
        # présent sur main avant ce lot, prouvé par repro SQLite). Le
        # zéro-trace de l'aperçu interne se mesure donc en DELTA autour du
        # GET : aucune notification NOUVELLE, quelle qu'elle soit.
        avant = Notification.objects.filter(recipient=self.owner).count()
        DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/')
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(), avant)

    def test_jeton_public_notifie_le_owner(self):
        avant = Notification.objects.filter(recipient=self.owner).count()
        DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertGreater(
            Notification.objects.filter(recipient=self.owner).count(), avant)


class TestZeroTraceBeaconEngagement(TestCase):
    """(b.3) POST engagement (XSAL16) — 204 systématique, mais AUCUNE écriture
    d'engagement/note chatter via le jeton interne."""

    def setUp(self):
        self.company = make_company('lintprev-eng')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-E1')
        self.link = make_link(self.devis)
        self.api = DjangoClient()

    def test_beacon_jeton_interne_204_sans_ecriture(self):
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token_interne}/engagement/',
            {'section': 'prix', 'seconds': 25}, content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.engagement)
        self.assertIsNone(self.link.deep_engagement_logged_at)

    def test_beacon_jeton_public_ecrit_bien_engagement(self):
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/engagement/',
            {'section': 'prix', 'seconds': 25}, content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.engagement)
        self.assertIsNotNone(self.link.deep_engagement_logged_at)


class TestOtpLectureJamaisExigeViaInterne(TestCase):
    """(c) otp_lecture=True sur le lien : bloque le public (403), jamais
    l'interne (200) — « OTP non exigé, c'est le commercial »."""

    def setUp(self):
        self.company = make_company('lintprev-otp')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-O1')
        self.link = make_link(self.devis, otp_lecture=True)

    def test_public_bloque_sans_otp(self):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 403)

    def test_interne_jamais_bloque_meme_otp_lecture_actif(self):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/')
        self.assertEqual(resp.status_code, 200)

    def test_interne_pdf_jamais_bloque(self):
        with _PATCH_GEN, _PATCH_DL:
            resp = DjangoClient().get(
                f'/api/django/public/proposal/{self.link.token_interne}/pdf/')
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════
# (d) signature refusée via le jeton interne
# ═══════════════════════════════════════════════════════════════════════════

class TestSignatureRefuseeViaInterne(TestCase):
    def setUp(self):
        self.company = make_company('lintprev-sign')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-A1')
        self.link = make_link(self.devis)

    def test_signature_via_jeton_interne_404_generique(self):
        resp = DjangoClient().post(
            f'/api/django/public/proposal/{self.link.token_interne}/accept/',
            {'nom': 'Commercial Curieux', 'consent_esign': True},
            content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')

    def test_message_404_identique_a_un_jeton_invalide(self):
        """« 403/404 générique » : jamais un message qui distingue le jeton
        interne d'un jeton simplement invalide."""
        resp_interne = DjangoClient().post(
            f'/api/django/public/proposal/{self.link.token_interne}/accept/',
            {'nom': 'X', 'consent_esign': True}, content_type='application/json')
        resp_inconnu = DjangoClient().post(
            '/api/django/public/proposal/totalement-inconnu/accept/',
            {'nom': 'X', 'consent_esign': True}, content_type='application/json')
        self.assertEqual(resp_interne.status_code, resp_inconnu.status_code)
        self.assertEqual(resp_interne.json(), resp_inconnu.json())


# ═══════════════════════════════════════════════════════════════════════════
# (d bis) R4 (27/08/2026) — AUCUNE ACTION CLIENT VIA LE JETON D'APERÇU
#
# La signature était le SEUL endpoint d'action gardé. Les autres actions du
# parcours public — demander à être rappelé, faire partir un code OTP chez le
# client, activer une option payante, déclarer un virement — répondaient
# normalement au jeton interne : un aperçu commercial écrivait donc dans le
# chatter, notifiait le vendeur, envoyait un message au client, ou changeait
# le périmètre facturé du devis. Chaque endpoint est ici pris DEUX FOIS : le
# jeton interne doit être refusé (403 + message français), le jeton public
# doit garder EXACTEMENT son comportement.
#
# La LECTURE (suivi post-signature) suit la règle inverse et la prouve aussi :
# elle reste ouverte à l'aperçu, sans effet de bord (il n'y en a aucun).
# ═══════════════════════════════════════════════════════════════════════════

class TestAucuneActionClientViaJetonInterne(TestCase):
    def setUp(self):
        self.company = make_company('lintprev-r4')
        self.client_obj = make_client_obj(self.company)
        self.owner = User.objects.create_user(
            username='lintprev-r4-owner', password='x',
            role_legacy='responsable', company=self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-R4')
        self.devis.created_by = self.owner
        self.devis.save(update_fields=['created_by'])
        self.link = make_link(self.devis)
        self.api = DjangoClient()

    def _post(self, chemin, token, corps=None):
        return self.api.post(
            f'/api/django/public/proposal/{token}/{chemin}',
            corps if corps is not None else {},
            content_type='application/json')

    def _assert_refus_interne(self, resp):
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertIn('Aperçu interne', resp.json()['detail'])

    # ── Demande de rappel (chatter + notification du vendeur) ────────────────

    def test_contact_interne_refuse_et_ne_laisse_aucune_trace(self):
        from apps.ventes.models import DevisActivity
        notes_avant = DevisActivity.objects.filter(devis=self.devis).count()
        notifs_avant = Notification.objects.filter(
            recipient=self.owner).count()

        resp = self._post('contact/', self.link.token_interne,
                          {'channel': 'rappel', 'message': 'Rappelez-moi'})

        self._assert_refus_interne(resp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=self.devis).count(),
            notes_avant)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(),
            notifs_avant)

    def test_contact_public_transmet_toujours(self):
        resp = self._post('contact/', self.link.token,
                          {'channel': 'rappel', 'message': 'Rappelez-moi'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json()['already_sent'])

    # ── OTP de SIGNATURE (part chez le client) ──────────────────────────────

    def test_otp_signature_interne_refuse(self):
        self._assert_refus_interne(
            self._post('otp/', self.link.token_interne))

    def test_otp_signature_public_inchange(self):
        resp = self._post('otp/', self.link.token)
        self.assertEqual(resp.status_code, 200, resp.content)

    # ── OTP de LECTURE (part chez le client, déverrouille la page) ───────────

    def test_otp_lecture_demander_interne_refuse(self):
        self._assert_refus_interne(
            self._post('otp-lecture/demander/', self.link.token_interne))

    def test_otp_lecture_verifier_interne_refuse(self):
        self._assert_refus_interne(
            self._post('otp-lecture/verifier/', self.link.token_interne,
                       {'otp_code': '000000'}))

    def test_otp_lecture_public_inchange(self):
        """Lien sans ``otp_lecture`` : le public reçoit toujours son « aucun
        code requis » — le garde ne s'est pas mis en travers."""
        for chemin in ('otp-lecture/demander/', 'otp-lecture/verifier/'):
            resp = self._post(chemin, self.link.token, {'otp_code': '0'})
            self.assertEqual(resp.status_code, 200, resp.content)

    # ── Activation d'une option (change le périmètre facturé) ───────────────

    def test_activer_option_interne_refuse_avant_toute_lecture_du_corps(self):
        self._assert_refus_interne(
            self._post('activer-option/', self.link.token_interne,
                       {'ligne_id': 1}))

    def test_activer_option_public_atteint_toujours_la_validation(self):
        """Témoin : le jeton public n'est PAS refusé — il va jusqu'au contrôle
        du corps (400 « Option invalide » sur un ligne_id absent)."""
        resp = self._post('activer-option/', self.link.token, {})
        self.assertEqual(resp.status_code, 400, resp.content)

    # ── Déclaration de virement (chatter + notification du vendeur) ──────────

    def test_virement_interne_refuse_et_ne_laisse_aucune_trace(self):
        from apps.ventes.models import DevisActivity
        notes_avant = DevisActivity.objects.filter(devis=self.devis).count()
        notifs_avant = Notification.objects.filter(
            recipient=self.owner).count()

        resp = self._post('virement/', self.link.token_interne)

        self._assert_refus_interne(resp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=self.devis).count(),
            notes_avant)
        self.assertEqual(
            Notification.objects.filter(recipient=self.owner).count(),
            notifs_avant)

    def test_virement_public_notifie_toujours_le_vendeur(self):
        notifs_avant = Notification.objects.filter(
            recipient=self.owner).count()
        resp = self._post('virement/', self.link.token)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreater(
            Notification.objects.filter(recipient=self.owner).count(),
            notifs_avant)


class TestSuiviPublicLectureOuverteAuJetonInterne(TestCase):
    """R4 — le suivi post-signature est une LECTURE PURE (aucun stamp, aucun
    chatter, aucune notification dans ``selectors.devis_milestones``) : le
    commercial doit le voir comme le client, exactement comme pour
    ``proposal_data`` / ``proposal_pdf`` / ``public_document``."""

    def setUp(self):
        self.company = make_company('lintprev-suivi')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-SU1')
        self.link = make_link(self.devis)
        self.api = DjangoClient()

    def _suivi(self, token):
        return self.api.get(f'/api/django/public/suivi/{token}/')

    def test_le_jeton_interne_lit_le_meme_suivi_que_le_public(self):
        pub = self._suivi(self.link.token)
        interne = self._suivi(self.link.token_interne)
        self.assertEqual(pub.status_code, 200, pub.content)
        self.assertEqual(interne.status_code, 200, interne.content)
        # ``generated_at`` est un horodatage de rendu — le reste doit coller.
        attendu = pub.json()
        obtenu = interne.json()
        attendu.pop('generated_at', None)
        obtenu.pop('generated_at', None)
        self.assertEqual(obtenu, attendu)

    def test_le_suivi_interne_ne_stampe_aucune_vue(self):
        self._suivi(self.link.token_interne)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)
        self.assertIsNone(self.link.first_viewed_at)

    def test_un_jeton_inconnu_reste_un_404(self):
        self.assertEqual(self._suivi('totalement-inconnu').status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════
# (e) mint (share-link) expose token_interne/path_interne
# ═══════════════════════════════════════════════════════════════════════════

class TestMintExposeJetonInterne(TestCase):
    def setUp(self):
        self.company = make_company('lintprev-mint')
        self.user = User.objects.create_user(
            username='lintprev-mint-u', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-MT1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_share_link_expose_token_interne_et_path_interne(self):
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('token_interne', resp.data)
        self.assertIn('path_interne', resp.data)
        self.assertTrue(resp.data['token_interne'])
        self.assertNotEqual(resp.data['token_interne'], resp.data['token'])
        self.assertIn(resp.data['token_interne'], resp.data['path_interne'])
        # Même construction de chemin que le lien public (slug + jeton).
        self.assertTrue(resp.data['path_interne'].startswith('/proposition/'))

    def test_mint_repete_renvoie_le_meme_jeton_interne(self):
        premier = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/')
        second = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/')
        self.assertEqual(
            premier.data['token_interne'], second.data['token_interne'])
        self.assertEqual(premier.data['token'], second.data['token'])

    def test_jeton_interne_effectif_genere_paresseusement_si_absent(self):
        """Garde défensive : un lien qui existerait sans jeton interne (cas
        limite hors backfill) en reçoit un à la demande, jamais None."""
        link = ShareLink.objects.create(
            company=self.company, devis=self.devis, token_interne=None)
        self.assertIsNone(link.token_interne)
        jeton = link.jeton_interne_effectif()
        self.assertTrue(jeton)
        link.refresh_from_db()
        self.assertEqual(link.token_interne, jeton)


# ═══════════════════════════════════════════════════════════════════════════
# (f) payload identique aux deux jetons + clé apercu_interne correcte
# ═══════════════════════════════════════════════════════════════════════════

class TestPayloadIdentiqueEtDrapeauApercuInterne(TestCase):
    def setUp(self):
        self.company = make_company('lintprev-payload')
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.client_obj, 'DEV-IP-P1')
        self.link = make_link(self.devis)

    def test_apercu_interne_false_sur_le_jeton_public(self):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['apercu_interne'])

    def test_apercu_interne_true_sur_le_jeton_interne(self):
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['apercu_interne'])

    def test_le_reste_du_payload_est_identique(self):
        """Même devis, même page — seule la clé apercu_interne diffère (et,
        indirectement, tout ce que _stamp_view aurait changé côté public :
        aucune clé du payload ne dépend de view_count/first_viewed_at)."""
        pub = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token}/data/').json()
        interne = DjangoClient().get(
            f'/api/django/public/proposal/{self.link.token_interne}/data/').json()
        pub.pop('apercu_interne')
        interne.pop('apercu_interne')
        self.assertEqual(pub, interne)
