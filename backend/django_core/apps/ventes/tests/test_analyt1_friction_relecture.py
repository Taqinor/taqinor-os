"""ANALYT1 (audit item 64, 26/08/2026) — analytics d'engagement PAR SECTION
sur la page publique de proposition, et le signal de FRICTION qui en découle.

Étend XSAL16 (``ShareLink.engagement`` — voir ``test_xsal16_engagement_
proposition.py``, jamais touché ici) : le beacon ``POST public/proposal/
<token>/engagement/`` accepte désormais un ``visit_id`` optionnel (identifiant
de PAGE-LOAD, jamais persisté côté client au-delà de l'onglet — voir
``apps/web/src/lib/engagementBeacon.ts``) qui permet de compter des VISITES
DISTINCTES par section, plutôt que de simples battements. Doctrine Proposify :
une proposition PERDANTE est re-consultée davantage qu'une proposition
GAGNANTE — relire la même section sur ≥3 visites distinctes déclenche UNE note
chatter (jamais plus, jamais montrée au client) via le même idiome que
``deep_engagement_logged_at``.

Couvre aussi :
  - le whitelist étendu (les 6 nouvelles sections réelles de la page actuelle) ;
  - l'action ERP ``DevisViewSet.lecture_client`` (IsResponsableOrAdmin,
    enregistrement VX199 des deux côtés) ;
  - l'exclusion du jeton d'aperçu interne (déjà couverte côté « zéro écriture »
    par ``test_l_intprev_apercu_interne.py`` — ici on vérifie spécifiquement
    qu'aucune visite/friction n'est comptée).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_analyt1_friction_relecture -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisActivity, ShareLink

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class _Base(TestCase):
    def setUp(self):
        self.company = _company('analyt1-co')
        self.user = User.objects.create_user(
            username='analyt1user', password='x', company=self.company,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alami', telephone='0612345678')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ANALYT1-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            created_by=self.user)
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _post(self, section, seconds=5, visit_id=None, token=None):
        body = {'section': section, 'seconds': seconds}
        if visit_id is not None:
            body['visit_id'] = visit_id
        return self.api.post(
            f'/api/django/public/proposal/{token or self.link.token}/engagement/',
            body, format='json')


# ── 1. Whitelist étendue — les 6 sections RÉELLES de la page actuelle ────────

class SectionWhitelistExtensionTests(_Base):
    def test_les_six_nouvelles_sections_sont_acceptees(self):
        sections = ('tailles', 'options', 'graphs', 'economies',
                    'calepinage', 'sld')
        for section in sections:
            resp = self._post(section, seconds=3)
            self.assertEqual(resp.status_code, 204, section)
        self.link.refresh_from_db()
        for section in sections:
            self.assertIn(section, self.link.engagement)
            self.assertEqual(self.link.engagement[section]['seconds'], 3)

    def test_les_anciennes_sections_historiques_restent_acceptees(self):
        # 'hero'/'prix'/'etude'/'garanties'/'signature' — comportement XSAL16
        # inchangé, jamais retiré.
        for section in ('hero', 'prix', 'etude', 'garanties', 'signature'):
            resp = self._post(section, seconds=1)
            self.assertEqual(resp.status_code, 204, section)

    def test_une_section_toujours_inconnue_reste_rejetee_silencieusement(self):
        resp = self._post('bogus-section', seconds=5)
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertNotIn('bogus-section', self.link.engagement or {})


# ── 2. Visites distinctes (visit_id) ─────────────────────────────────────────

class VisitesDistinctesTests(_Base):
    def test_meme_visit_id_ne_compte_qu_une_seule_visite(self):
        self._post('options', seconds=5, visit_id='visit-aaa')
        self._post('options', seconds=7, visit_id='visit-aaa')
        self.link.refresh_from_db()
        slot = self.link.engagement['options']
        self.assertEqual(slot['hits'], 2)          # deux battements
        self.assertEqual(slot['visits'], 1)        # une seule visite
        self.assertEqual(slot['seconds'], 12)       # cumul inchangé

    def test_deux_visit_id_differents_comptent_deux_visites(self):
        self._post('sld', seconds=5, visit_id='visit-aaa')
        self._post('sld', seconds=5, visit_id='visit-bbb')
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement['sld']['visits'], 2)

    def test_sans_visit_id_aucune_visite_comptee_mais_seconds_hits_intacts(self):
        # Repli défensif : un beacon front antérieur à cette lane (sans
        # visit_id) continue de fonctionner EXACTEMENT comme avant (XSAL16).
        self._post('economies', seconds=9)
        self.link.refresh_from_db()
        slot = self.link.engagement['economies']
        self.assertEqual(slot['seconds'], 9)
        self.assertEqual(slot['hits'], 1)
        self.assertEqual(slot.get('visits', 0), 0)

    def test_visit_id_malforme_est_ignore_silencieusement(self):
        self._post('sld', seconds=5, visit_id='a b !')  # espace/point d'exclam.
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement['sld'].get('visits', 0), 0)

    def test_visit_id_par_section_sont_independants(self):
        self._post('options', seconds=1, visit_id='visit-1')
        self._post('sld', seconds=1, visit_id='visit-1')
        self._post('sld', seconds=1, visit_id='visit-2')
        self.link.refresh_from_db()
        self.assertEqual(self.link.engagement['options']['visits'], 1)
        self.assertEqual(self.link.engagement['sld']['visits'], 2)

    def test_visites_bornees_a_vingt_par_section(self):
        for i in range(25):
            self._post('options', seconds=1, visit_id=f'visit-{i}')
        self.link.refresh_from_db()
        self.assertLessEqual(len(self.link.engagement['options']['visit_ids']), 20)


# ── 3. Signal de FRICTION — 3 visites distinctes, une note, jamais deux ─────

class FrictionAlertTests(_Base):
    def test_trois_visites_distinctes_declenchent_une_note_chatter(self):
        self._post('options', seconds=1, visit_id='v1')
        self._post('options', seconds=1, visit_id='v2')
        self.assertIsNone(ShareLink.objects.get(pk=self.link.pk).friction_alert_logged_at)
        self._post('options', seconds=1, visit_id='v3')  # 3e visite distincte

        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.friction_alert_logged_at)
        self.assertEqual(self.link.friction_alert_section, 'options')
        notes = DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE)
        self.assertTrue(
            notes.filter(body__icontains='relit').exists(),
            [n.body for n in notes])

    def test_deux_visites_distinctes_ne_declenchent_rien(self):
        self._post('sld', seconds=1, visit_id='v1')
        self._post('sld', seconds=1, visit_id='v2')
        self.link.refresh_from_db()
        self.assertIsNone(self.link.friction_alert_logged_at)

    def test_une_seule_alerte_par_lien_jamais_deux(self):
        for i in range(3):
            self._post('options', seconds=1, visit_id=f'opt-{i}')
        self.link.refresh_from_db()
        first_logged_at = self.link.friction_alert_logged_at
        self.assertIsNotNone(first_logged_at)
        count_after_first = DevisActivity.objects.filter(devis=self.devis).count()

        # Une AUTRE section franchit AUSSI le seuil ensuite — toujours UNE
        # seule alerte par lien (jamais une par section).
        for i in range(3):
            self._post('sld', seconds=1, visit_id=f'sld-{i}')
        self.link.refresh_from_db()
        self.assertEqual(self.link.friction_alert_logged_at, first_logged_at)
        self.assertEqual(self.link.friction_alert_section, 'options')
        count_after_second = DevisActivity.objects.filter(devis=self.devis).count()
        self.assertEqual(count_after_first, count_after_second)

    def test_re_franchir_le_seuil_sur_la_meme_section_ne_reloggue_pas(self):
        for i in range(5):
            self._post('options', seconds=1, visit_id=f'opt-{i}')
        self.link.refresh_from_db()
        self.assertEqual(len(self.link.engagement['options']['visit_ids']), 5)
        count = DevisActivity.objects.filter(devis=self.devis).count()
        self.assertGreaterEqual(count, 1)
        # Une note de plus n'apparaît QUE si un autre déclencheur (deep
        # engagement) la pose — jamais un doublon de friction.
        friction_notes = DevisActivity.objects.filter(
            devis=self.devis, body__icontains='relit')
        self.assertEqual(friction_notes.count(), 1)


# ── 4. Jeton d'aperçu interne — zéro trace (mêmes garanties que L-INTPREV) ──

class AperçuInterneAucuneVisiteTests(_Base):
    def test_aucune_visite_ni_friction_via_le_jeton_interne(self):
        for i in range(5):
            self._post('options', seconds=1, visit_id=f'v{i}',
                       token=self.link.token_interne)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.engagement)
        self.assertIsNone(self.link.friction_alert_logged_at)


# ── 5. Isolation tenancy ──────────────────────────────────────────────────

class TenancyIsolationTests(_Base):
    def test_la_note_de_friction_ne_fuit_pas_vers_une_autre_societe(self):
        other_company = _company('analyt1-other')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', telephone='0600000099')
        other_devis = Devis.objects.create(
            company=other_company, reference='DEV-ANALYT1-OTHER',
            client=other_client, statut=Devis.Statut.ENVOYE)
        other_link = ShareLink.for_devis(other_devis)

        for i in range(3):
            self._post('options', seconds=1, visit_id=f'v{i}')
        other_link.refresh_from_db()
        self.assertIsNone(other_link.friction_alert_logged_at)
        self.assertFalse(DevisActivity.objects.filter(devis=other_devis).exists())


# ── 6. Surface ERP — DevisViewSet.lecture_client ─────────────────────────────

class LectureClientEndpointTests(_Base):
    def _auth(self, role_legacy='responsable', company=None):
        user = User.objects.create_user(
            username=f'lc-{role_legacy}-{id(self)}', password='x',
            company=company or self.company, role_legacy=role_legacy)
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def test_VX199_lecture_client_est_inscrite_dans_get_permissions(self):
        from authentication.permissions import IsResponsableOrAdmin
        from apps.ventes.views.devis import DevisViewSet
        vue = DevisViewSet()
        vue.action = 'lecture_client'
        classes = [type(p) for p in vue.get_permissions()]
        self.assertEqual(classes, [IsResponsableOrAdmin])

    def test_un_role_normal_recoit_403(self):
        api = self._auth(role_legacy='normal')
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertEqual(resp.status_code, 403)

    def test_un_responsable_recoit_200_avec_les_visites_et_la_friction(self):
        for i in range(3):
            self._post('options', seconds=2, visit_id=f'v{i}')
        api = self._auth(role_legacy='responsable')
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['sections']['options']['visits'], 3)
        self.assertEqual(data['sections']['options']['seconds'], 6)
        self.assertEqual(data['friction']['section'], 'options')
        self.assertIsNotNone(data['friction']['declenche_le'])

    def test_sans_beacon_les_deux_cles_restent_vides(self):
        api = self._auth(role_legacy='admin')
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['sections'], {})
        self.assertIsNone(data['friction'])

    def test_jamais_de_visit_ids_bruts_exposes(self):
        self._post('options', seconds=2, visit_id='some-visit-id-123')
        api = self._auth(role_legacy='responsable')
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertNotIn(b'some-visit-id-123', resp.content)
        self.assertNotIn(b'visit_ids', resp.content)

    def test_un_devis_d_une_autre_societe_repond_404(self):
        other_company = _company('analyt1-lc-other')
        api = self._auth(role_legacy='responsable', company=other_company)
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertEqual(resp.status_code, 404)

    def test_ne_fuit_jamais_prix_achat(self):
        api = self._auth(role_legacy='admin')
        resp = api.get(f'/api/django/ventes/devis/{self.devis.pk}/lecture-client/')
        self.assertNotIn(b'prix_achat', resp.content)
