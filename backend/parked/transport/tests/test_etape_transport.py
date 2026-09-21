"""NTLOG3 — étapes de transport : avancement automatique du statut de
l'ordre quand une étape est marquée « fait ». NTLOG8 — chaque changement
écrit une ligne de chatter horodatée."""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.records.models import Activity, Attachment
from apps.transport.models import EtapeTransport, OrdreTransport

from ._helpers import auth, make_company, make_user

ORDRES_BASE = '/api/django/transport/ordres-transport/'
ETAPES_BASE = '/api/django/transport/etapes-transport/'


class EtapeTransportTests(TestCase):
    def setUp(self):
        self.co_a = make_company('transport-et-a', 'A')
        self.co_b = make_company('transport-et-b', 'B')
        self.user_a = make_user(self.co_a, 'transport-et-a')
        self.user_b = make_user(self.co_b, 'transport-et-b')
        self.ordre = OrdreTransport.objects.create(
            company=self.co_a, statut=OrdreTransport.Statut.PLANIFIE)
        self.e1 = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=1,
            type_etape=EtapeTransport.TypeEtape.ENLEVEMENT)
        self.e2 = EtapeTransport.objects.create(
            company=self.co_a, ordre=self.ordre, sequence=2,
            type_etape=EtapeTransport.TypeEtape.LIVRAISON)

    def _patch_statut(self, api, etape, statut):
        return api.patch(
            f'{ETAPES_BASE}{etape.id}/', {'statut_etape': statut},
            format='json')

    # ── Avancement automatique du statut de l'ordre ───────────────────────
    def test_premiere_etape_faite_passe_ordre_en_cours(self):
        api = auth(self.user_a)
        resp = self._patch_statut(
            api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, OrdreTransport.Statut.EN_COURS)

    def test_toutes_etapes_faites_passe_ordre_livre(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self._patch_statut(api, self.e2, EtapeTransport.StatutEtape.FAIT)
        self.ordre.refresh_from_db()
        self.assertEqual(self.ordre.statut, OrdreTransport.Statut.LIVRE)

    def test_etape_incident_ne_livre_pas_l_ordre(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        self._patch_statut(api, self.e2, EtapeTransport.StatutEtape.INCIDENT)
        self.ordre.refresh_from_db()
        self.assertNotEqual(self.ordre.statut, OrdreTransport.Statut.LIVRE)

    def test_lecture_imbriquee_des_etapes(self):
        resp = auth(self.user_a).get(f'{ORDRES_BASE}{self.ordre.id}/etapes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    # ── NTLOG8 — chatter horodaté sur le changement de statut ─────────────
    def test_changement_statut_etape_ecrit_une_ligne_de_chatter(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        ct = ContentType.objects.get_for_model(OrdreTransport)
        # e1 A_FAIRE->FAIT fait AUSSI avancer l'ordre PLANIFIE->EN_COURS
        # (``services.recalculer_statut_ordre``) : DEUX lignes de chatter
        # s'écrivent sur le MÊME ordre dans la même requête (l'une
        # ``field='etape_statut'`` pour l'étape, l'autre ``field='statut'``
        # pour le roll-up de l'ordre) — filtrer par ``field`` cible sans
        # ambiguïté celle que NTLOG8 teste ici (``.latest('created_at')``
        # seul ramassait la ligne 'statut' écrite juste après, la plus
        # récente).
        entries = Activity.objects.filter(
            content_type=ct, object_id=self.ordre.id, field='etape_statut')
        self.assertTrue(entries.exists())
        entry = entries.latest('created_at')
        self.assertEqual(entry.old_value, EtapeTransport.StatutEtape.A_FAIRE)
        self.assertEqual(entry.new_value, EtapeTransport.StatutEtape.FAIT)
        self.assertEqual(entry.created_by, self.user_a)

    def test_chatter_visible_via_endpoint_generique(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        resp = api.get(f'{ORDRES_BASE}{self.ordre.id}/chatter/historique/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data) >= 1)

    def test_statut_inchange_ne_duplique_pas_le_chatter(self):
        api = auth(self.user_a)
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        ct = ContentType.objects.get_for_model(OrdreTransport)
        count_avant = Activity.objects.filter(
            content_type=ct, object_id=self.ordre.id).exclude(kind='').count()
        self._patch_statut(api, self.e1, EtapeTransport.StatutEtape.FAIT)
        count_apres = Activity.objects.filter(
            content_type=ct, object_id=self.ordre.id).exclude(kind='').count()
        self.assertEqual(count_avant, count_apres)

    # ── NTLOG9 — preuve de livraison (POD) ────────────────────────────────
    def test_livrer_sans_piece_jointe_refuse(self):
        resp = auth(self.user_a).post(f'{ETAPES_BASE}{self.e2.id}/livrer/')
        self.assertEqual(resp.status_code, 400)
        self.e2.refresh_from_db()
        self.assertEqual(
            self.e2.statut_etape, EtapeTransport.StatutEtape.A_FAIRE)

    def test_livrer_avec_piece_jointe_cloture_l_etape(self):
        ct = ContentType.objects.get_for_model(EtapeTransport)
        Attachment.objects.create(
            company=self.co_a, content_type=ct, object_id=self.e2.id,
            file_key='transport/x/pod.jpg', filename='pod.jpg')
        resp = auth(self.user_a).post(f'{ETAPES_BASE}{self.e2.id}/livrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.e2.refresh_from_db()
        self.assertEqual(
            self.e2.statut_etape, EtapeTransport.StatutEtape.FAIT)

    # ── Isolation multi-société ────────────────────────────────────────
    def test_etape_cross_tenant_404(self):
        resp = auth(self.user_b).patch(
            f'{ETAPES_BASE}{self.e1.id}/', {'statut_etape': 'fait'},
            format='json')
        self.assertEqual(resp.status_code, 404)
