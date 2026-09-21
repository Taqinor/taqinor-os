"""NTCON31 — API publique + webhooks des objets BTP.

Ce que le test PROUVE :
  * les quatre ressources (réserves, RFI, visas, DGD) sont lisibles par CLÉ
    d'API sous le scope ``read:btp``, et une clé sans ce scope reçoit 403 ;
  * la société vient TOUJOURS de la clé — jamais de fuite cross-tenant ;
  * AUCUN coût interne n'est servi (déboursé, pénalités, prix d'achat) ;
  * un abonné webhook externe reçoit bien la notification à la levée d'une
    réserve, à la réponse d'un RFI, à l'approbation d'un visa et à la
    finalisation d'un DGD — via le bus ``core.events``, jamais un appel direct
    ``btp_chantier`` → ``publicapi`` ;
  * un REFUS de visa n'émet PAS ``visa.approuve``.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    DecompteGeneral, ReserveChantier, VisaDocument,
)
from apps.publicapi.constants import (
    EVENT_BTP_DGD_FINALISE, EVENT_BTP_RESERVE_LEVEE, EVENT_BTP_RFI_REPONDU,
    EVENT_BTP_VISA_APPROUVE, SCOPE_READ_BTP, SCOPE_READ_LEADS,
)
from apps.publicapi.models import ApiKey

from .helpers import attach, make_chantier, make_company, make_user

RACINE = '/api/public/v1/btp/'


def _key_client(raw):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw}')
    return api


def _rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    if isinstance(data, dict) and 'data' in data:
        contenu = data['data']
        if isinstance(contenu, dict) and 'results' in contenu:
            return contenu['results']
        return contenu
    return data


class PublicApiBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.cle, self.raw = ApiKey.issue(
            company=self.co, label='MOE externe', scopes=[SCOPE_READ_BTP])
        self.api = _key_client(self.raw)

        self.reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='électricité',
            localisation_plan={'document_ged_id': 1, 'x': 0.1, 'y': 0.1},
            description='Tableau non conforme', gravite='bloquante',
            created_by=self.user)
        self.rfi = services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.user,
            question='Section de câble ?')
        self.visa = VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=9,
            reference='VIS-1', statut=VisaDocument.Statut.SOUMIS,
            soumis_par=self.user, delai_revue_jours=7)
        self.dgd = DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-1',
            montant_marche_initial_ht=100000, solde_du_ht=15000,
            statut=DecompteGeneral.Statut.NOTIFIE, cree_par=self.user)

    # ── lecture par clé d'API ──────────────────────────────────────────────
    def test_les_quatre_ressources_sont_lisibles(self):
        for route, attendu in (
                ('reserves/', self.reserve.id),
                ('rfi/', self.rfi.id),
                ('visas/', self.visa.id),
                ('decomptes-generaux/', self.dgd.id)):
            with self.subTest(route=route):
                resp = self.api.get(RACINE + route)
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertIn(attendu, [r['id'] for r in _rows(resp)])

    def test_cle_sans_scope_btp_refusee(self):
        _cle, raw = ApiKey.issue(
            company=self.co, label='Sans BTP', scopes=[SCOPE_READ_LEADS])
        for route in ('reserves/', 'rfi/', 'visas/', 'decomptes-generaux/'):
            with self.subTest(route=route):
                self.assertEqual(
                    _key_client(raw).get(RACINE + route).status_code, 403)

    def test_sans_cle_refuse(self):
        self.assertIn(
            APIClient().get(RACINE + 'reserves/').status_code, (401, 403))

    def test_societe_vient_de_la_cle(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        voisine = ReserveChantier.objects.create(
            company=autre, chantier=autre_chantier, lot='CVC',
            localisation_plan={}, description='Réserve voisine',
            gravite='mineure')
        ids = [r['id'] for r in _rows(self.api.get(RACINE + 'reserves/'))]
        self.assertIn(self.reserve.id, ids)
        self.assertNotIn(voisine.id, ids)

    def test_aucun_cout_interne_expose(self):
        """Ni déboursé, ni pénalités, ni prix d'achat dans les charges utiles."""
        interdits = (
            'prix_achat', 'debourse', 'déboursé', 'marge',
            'penalite_calculee_cache', 'historique_deverrouillage',
        )
        for route in ('reserves/', 'rfi/', 'visas/', 'decomptes-generaux/'):
            texte = str(self.api.get(RACINE + route).data).lower()
            for terme in interdits:
                with self.subTest(route=route, terme=terme):
                    self.assertNotIn(terme.lower(), texte)

    def test_filtre_inconnu_refuse(self):
        """Liste blanche de filtres (base PublicReadOnlyViewSet)."""
        resp = self.api.get(RACINE + 'reserves/', {'description': 'x'})
        self.assertEqual(resp.status_code, 400)

    def test_filtre_autorise(self):
        resp = self.api.get(RACINE + 'reserves/', {'statut': 'ouverte'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(_rows(resp)), 1)

    # ── webhooks via le bus core.events ────────────────────────────────────
    def _lever_la_reserve(self):
        attach(self.co, self.user, self.reserve, 'apres')
        return services.lever_reserve(
            self.reserve, user=self.user, signature_nom='A. Benali')

    def test_webhook_a_la_levee_d_une_reserve(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as envoi:
            self._lever_la_reserve()
        envoi.assert_called_once()
        company_id, event, payload = envoi.call_args[0]
        self.assertEqual(company_id, self.co.id)
        self.assertEqual(event, EVENT_BTP_RESERVE_LEVEE)
        self.assertEqual(payload['reserve_id'], self.reserve.id)
        self.assertEqual(payload['statut'], ReserveChantier.Statut.LEVEE)
        self.assertIsNotNone(payload['date_levee'])

    def test_webhook_a_la_reponse_d_un_rfi(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as envoi:
            services.repondre_rfi(self.rfi, auteur=self.user, texte='3G2,5')
        envoi.assert_called_once()
        company_id, event, payload = envoi.call_args[0]
        self.assertEqual(company_id, self.co.id)
        self.assertEqual(event, EVENT_BTP_RFI_REPONDU)
        self.assertEqual(payload['rfi_id'], self.rfi.id)
        self.assertIsNotNone(payload['reponse_id'])

    def test_webhook_a_l_approbation_d_un_visa(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as envoi:
            services.approuver_visa(self.visa, user=self.user)
        envoi.assert_called_once()
        company_id, event, payload = envoi.call_args[0]
        self.assertEqual(company_id, self.co.id)
        self.assertEqual(event, EVENT_BTP_VISA_APPROUVE)
        self.assertEqual(payload['reference'], 'VIS-1')

    def test_refus_de_visa_n_emet_pas_approuve(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as envoi:
            services.refuser_visa(
                self.visa, user=self.user, observations='non conforme')
        envoi.assert_not_called()

    def test_webhook_a_la_finalisation_d_un_dgd(self):
        with mock.patch('apps.publicapi.delivery.dispatch_event') as envoi:
            services.finaliser_dgd(self.dgd, user=self.user)
        envoi.assert_called_once()
        company_id, event, payload = envoi.call_args[0]
        self.assertEqual(company_id, self.co.id)
        self.assertEqual(event, EVENT_BTP_DGD_FINALISE)
        self.assertEqual(payload['reference'], 'DGD-1')
        # Montant CONTRACTUEL, en chaîne (jamais un float, jamais un coût).
        self.assertEqual(payload['solde_du_ht'], str(self.dgd.solde_du_ht))

    def test_un_webhook_en_echec_ne_casse_pas_le_geste_metier(self):
        """Best-effort : la réserve est levée même si la livraison explose."""
        with mock.patch('apps.publicapi.delivery.dispatch_event',
                        side_effect=RuntimeError('réseau HS')):
            self._lever_la_reserve()
        self.reserve.refresh_from_db()
        self.assertEqual(self.reserve.statut, ReserveChantier.Statut.LEVEE)

    # ── abonnement réel (Webhook enregistré) ───────────────────────────────
    def test_abonne_externe_est_mis_en_file(self):
        """Le critère d'acceptation : un abonné externe EST notifié.

        On arrête la chaîne à la mise en file Celery (``deliver_webhook.delay``)
        — au-delà c'est le transport commun, déjà couvert par les tests de
        ``apps.publicapi``.
        """
        from apps.publicapi.models import Webhook

        abonne = Webhook.objects.create(
            company=self.co, label='MOE', target_url='https://moe.test/hook',
            secret='s3cr3t', events=[EVENT_BTP_RESERVE_LEVEE], enabled=True)
        muet = Webhook.objects.create(
            company=self.co, label='Autre', target_url='https://x.test/hook',
            secret='s3cr3t', events=['lead.created'], enabled=True)
        with mock.patch('apps.publicapi.tasks.deliver_webhook.delay') as file:
            self._lever_la_reserve()
        appels = [appel[0] for appel in file.call_args_list]
        self.assertEqual(len(appels), 1, appels)
        self.assertEqual(appels[0][0], abonne.id)
        self.assertEqual(appels[0][1], EVENT_BTP_RESERVE_LEVEE)
        self.assertNotIn(muet.id, [a[0] for a in appels])
