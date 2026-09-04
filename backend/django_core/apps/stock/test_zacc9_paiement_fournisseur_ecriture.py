"""ZACC9 — Comptabilisation + garde de sur-paiement du règlement fournisseur
(parité Register Payment).

Couvre :
  * un paiement > solde dû est refusé (400) sur
    `factures-fournisseur/{id}/paiements/` (POST) ;
  * un paiement valide poste une écriture comptable équilibrée réduisant le
    solde du bon montant (débit 4411 / crédit trésorerie), UNIQUEMENT quand
    `COMPTA_AUTO_ECRITURES` est actif (comportement historique OFF par
    défaut) ;
  * re-poster (rejouer l'événement) le même paiement n'écrit jamais deux
    fois (idempotence côté récepteur compta) ;
  * cross-company : une facture d'une autre société → 404.
  * AUD208 — le verrou `select_for_update` posé sur la facture AVANT de
    re-vérifier le solde dû SOUS verrou : preuve mécanique (SELECT ... FOR
    UPDATE émis) + preuve de course RÉELLE (deux threads, deux paiements
    chacun valide isolément mais dont la somme dépasse le solde dû — le
    second doit être refusé).

Run:
    python manage.py test \
        apps.stock.test_zacc9_paiement_fournisseur_ecriture -v 2
"""
import threading
import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import FactureFournisseur, Fournisseur
from apps.compta.models import EcritureComptable
from apps.compta import services as compta_services

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zacc9Base(TestCase):
    def setUp(self):
        self.company = _company('zacc9-co')
        self.user = _user(
            self.company, 'zacc9-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZACC9')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ZACC9-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
            statut=FactureFournisseur.Statut.A_PAYER)

    def _paiements_url(self):
        return (f'/api/django/stock/factures-fournisseur/'
                f'{self.facture.id}/paiements/')


class TestGardeSurPaiement(Zacc9Base):
    def test_paiement_superieur_au_solde_du_refuse(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '150', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_paiement_egal_au_solde_du_accepte(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_paiement_partiel_puis_depassement_du_reste_refuse(self):
        resp1 = self.api.post(self._paiements_url(), {
            'montant': '100', 'mode': 'virement'}, format='json')
        self.assertEqual(resp1.status_code, 201, resp1.data)
        # Reste dû = 20 ; tenter 50 doit être refusé.
        resp2 = self.api.post(self._paiements_url(), {
            'montant': '50', 'mode': 'virement'}, format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)


@override_settings(COMPTA_AUTO_ECRITURES=True)
class TestEcritureComptable(Zacc9Base):
    def test_paiement_valide_poste_ecriture_equilibree(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ecr = EcritureComptable.objects.get(
            company=self.company, source_type='paiement_fournisseur')
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.total_credit, Decimal('120'))
        fourn = ecr.lignes.get(compte__numero='4411')
        self.assertEqual(fourn.debit, Decimal('120'))

    def test_reduit_le_solde_du_bon_montant(self):
        self.api.post(self._paiements_url(), {
            'montant': '50', 'mode': 'virement'}, format='json')
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.solde_du, Decimal('70'))

    def test_rejouer_le_meme_paiement_necrit_pas_deux_fois(self):
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        from apps.stock.models import PaiementFournisseur
        paiement = PaiementFournisseur.objects.get(facture=self.facture)
        # Rejoue directement le service compta (simule un ré-abonné) :
        # idempotence garantie par `_ecriture_existante`.
        compta_services.ecriture_pour_paiement_fournisseur(paiement)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.company,
                source_type='paiement_fournisseur').count(), 1)


class TestOffParDefaut(Zacc9Base):
    def test_sans_toggle_aucune_ecriture(self):
        self.assertFalse(compta_services.auto_ecritures_actif())
        resp = self.api.post(self._paiements_url(), {
            'montant': '120', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.company,
                source_type='paiement_fournisseur').count(), 0)


class TestMultiTenant(Zacc9Base):
    def test_facture_autre_societe_404(self):
        autre = _company('zacc9-autre')
        autre_user = _user(autre, 'zacc9-autre-user',
                           permissions=['stock_modifier', 'stock_voir'])
        autre_api = _api(autre_user)
        resp = autre_api.post(self._paiements_url(), {
            'montant': '10', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 404)


class TestAUD208LeVerrouEstPose(Zacc9Base):
    """Preuve mécanique : les DEUX chemins de paiement émettent bien un
    ``SELECT ... FOR UPDATE`` sur la facture avant d'enregistrer le
    règlement — sans lui, aucune sérialisation n'existe contre le
    sur-paiement concurrent (AUD208)."""

    def _verrous(self, requetes):
        return [q['sql'] for q in requetes.captured_queries
                if 'FOR UPDATE' in q['sql']]

    def test_le_post_paiements_verrouille_la_facture(self):
        with CaptureQueriesContext(connection) as requetes:
            resp = self.api.post(self._paiements_url(), {
                'montant': '50', 'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            self._verrous(requetes),
            "aucun SELECT ... FOR UPDATE : le POST .../paiements/ ne "
            "verrouille plus la facture — deux paiements concurrents "
            "peuvent à nouveau dépasser le solde dû en silence.")

    def test_le_create_paiement_fournisseur_verrouille_la_facture(self):
        with CaptureQueriesContext(connection) as requetes:
            resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
                'facture': self.facture.id, 'montant': '50',
                'mode': 'virement'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            self._verrous(requetes),
            "aucun SELECT ... FOR UPDATE : "
            "PaiementFournisseurViewSet.create ne verrouille plus la "
            "facture.")


class TestAUD208DeuxPaiementsConcurrentsNeDepassentPlusLeSolde(
        TransactionTestCase):
    """LE test : deux VRAIS threads, deux connexions DB, deux paiements sur
    la MÊME facture, chacun VALIDE isolément (< solde dû) mais dont la SOMME
    le dépasse.

    ``TransactionTestCase`` (et non ``TestCase``) — comme
    ``apps/ventes/tests/test_qjr223_overrides_concurrence.py`` : un thread
    réel reçoit sa PROPRE connexion DB hors de la transaction atomique du
    test ; sous ``TestCase`` il ne verrait jamais les données commitées par
    l'autre thread. ``TransactionTestCase`` commite réellement, donc les
    deux threads se voient — la course ne peut se rejouer qu'ainsi.

    AVANT AUD208 : ``PaiementFournisseurSerializer.validate()`` lit
    ``facture.solde_du`` HORS verrou, avant même l'ouverture de la
    transaction de la vue — les deux threads lisent le MÊME solde dû de
    départ (120), chacun poste 70 (< 120 isolément), et les DEUX passent :
    140 réglés sur une facture de 120.
    """

    def setUp(self):
        self.company = _company('zacc9-aud208-co')
        self.user = _user(
            self.company, 'zacc9-aud208-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZACC9 AUD208')
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ZACC9-AUD208-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'),
            statut=FactureFournisseur.Statut.A_PAYER)

    def tearDown(self):
        connection.close()

    def test_le_second_paiement_est_refuse_apres_le_verrou_du_premier(self):
        acquis = threading.Event()
        b_a_tente = threading.Event()
        relacher = threading.Event()
        resultats = {}

        from apps.stock import services as stock_services
        original = stock_services.verrouiller_facture_fournisseur_et_verifier_solde

        def verrouiller_instrumente(facture, montant):
            if not acquis.is_set():
                # Thread A : acquiert RÉELLEMENT le verrou (SELECT ... FOR
                # UPDATE, dans le transaction.atomic() ouvert par la vue),
                # puis attend — le verrou reste tenu tout le temps de
                # l'attente.
                res = original(facture, montant)
                acquis.set()
                relacher.wait(5)
                return res
            # Thread B : signale qu'il s'apprête à tenter le MÊME verrou
            # (donc à bloquer réellement tant que A ne l'a pas relâché),
            # puis tente pour de vrai.
            b_a_tente.set()
            return original(facture, montant)

        stock_services.verrouiller_facture_fournisseur_et_verifier_solde = (
            verrouiller_instrumente)
        try:
            def thread_a():
                api = _api(self.user)
                r = api.post('/api/django/stock/paiements-fournisseur/', {
                    'facture': self.facture.id, 'montant': '70',
                    'mode': 'virement'}, format='json')
                resultats['a'] = (r.status_code, r.data)
                connection.close()

            def thread_b():
                api = _api(self.user)
                r = api.post('/api/django/stock/paiements-fournisseur/', {
                    'facture': self.facture.id, 'montant': '70',
                    'mode': 'virement'}, format='json')
                resultats['b'] = (r.status_code, r.data)
                connection.close()

            ta = threading.Thread(target=thread_a)
            ta.start()
            self.assertTrue(
                acquis.wait(5), 'le thread A n’a jamais acquis le verrou')

            tb = threading.Thread(target=thread_b)
            tb.start()
            self.assertTrue(
                b_a_tente.wait(5), 'le thread B n’a jamais tenté le verrou')
            # Attend que le SELECT ... FOR UPDATE de B soit RÉELLEMENT
            # bloqué dans PostgreSQL AVANT de relâcher A — une attente de
            # CONDITION, jamais un délai arbitraire (le défaut d'origine est
            # justement une course de timing). Observée dans
            # ``pg_locks.granted = false``, même patron que test_qjr223.

            def _b_bloque_sur_le_verrou():
                with connection.cursor() as curseur:
                    curseur.execute(
                        "SELECT count(*) FROM pg_locks WHERE granted = false")
                    return curseur.fetchone()[0] > 0
            pacage = threading.Event()  # jamais signalé : pur régulateur
            limite = time.monotonic() + 5
            while not _b_bloque_sur_le_verrou():
                self.assertLess(
                    time.monotonic(), limite,
                    'le SELECT FOR UPDATE de B ne s’est jamais bloqué en base')
                pacage.wait(0.05)

            relacher.set()
            ta.join(10)
            tb.join(10)
            self.assertFalse(ta.is_alive(), 'le thread A ne s’est jamais terminé')
            self.assertFalse(tb.is_alive(), 'le thread B ne s’est jamais terminé')
        finally:
            stock_services.verrouiller_facture_fournisseur_et_verifier_solde = (
                original)

        # A (premier à acquérir le verrou) réussit ; B, en relisant le solde
        # dû SOUS verrou APRÈS le commit de A, est refusé (140 > 120).
        self.assertEqual(resultats['a'][0], 201, resultats['a'][1])
        self.assertEqual(resultats['b'][0], 400, resultats['b'][1])

        self.facture.refresh_from_db()
        self.assertEqual(
            self.facture.total_paye, Decimal('70.00'),
            "AVANT AUD208 : les DEUX paiements de 70 passaient — 140 réglés "
            "sur une facture de 120.")
        self.assertEqual(self.facture.solde_du, Decimal('50.00'))
