"""AUD157 — liste des factures : N+1 fermé et KPI d'argent avec UN propriétaire.

(a) FAC-14 : le queryset ne préfetchait que ``lignes`` alors que
``FactureSerializer`` sérialise pour CHAQUE facture les paiements imbriqués,
les avoirs, ``montant_paye`` (→ paiements + affectations_paiement),
``montant_du`` (→ + notes_debit + retenues_subies) et ``mentions_manquantes``
(→ un ``CompanyProfile.get`` NON mémoïsé) — soit ≈6 requêtes par facture.

(b) FAC-13 : le KPI « Encaissé ce mois » vivait dans ``FactureList.jsx`` et
sommait ``p.montant`` SANS filtrer ``p.statut`` — l'écran affichait un encaissé
qui comptait des chèques revenus impayés, avec une définition différente de
``Facture.montant_paye``.

PACT10 — ce test AFFIRME l'exemple de réponse committé dans
``apps/ventes/contract_samples/factures_kpis.json`` : les DEUX moitiés lisent
le même fichier, jamais un mock écrit à la main.
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()
_CTR = [0]

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'factures_kpis.json')


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestFacturesKpis(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD157 Co', slug=f'aud157-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud157_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD157', prenom='Client',
            telephone='+212600000157')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD157-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)

    def _facture(self, *, echeance=None,
                 statut=Facture.Statut.EMISE, ht='10000'):
        facture = Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference=f'FAC-AUD157-{_nxt()}', statut=statut,
            taux_tva=Decimal('20'), date_echeance=echeance)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal(ht),
            taux_tva=Decimal('20'))
        return facture

    def _paiement(self, facture, montant, date, statut=None):
        return Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal(montant), date_paiement=date,
            mode=Paiement.Mode.CHEQUE,
            **({'statut': statut} if statut else {}))

    # ── (b) FAC-13 — le KPI a un propriétaire, et il exclut les rejetés ──

    def test_encaisse_du_mois_exclut_un_paiement_rejete(self):
        """ROUGE avant le correctif : l'écran comptait le chèque impayé."""
        aujourdhui = timezone.localdate()
        facture = self._facture(echeance=aujourdhui + timedelta(days=30))
        self._paiement(facture, '3000', aujourdhui)
        self._paiement(facture, '5000', aujourdhui,
                       statut=Paiement.Statut.REJETE)

        resp = self.api.get('/api/django/ventes/factures/kpis/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(Decimal(resp.data['encaisse_mois']), Decimal('3000'))

    def test_encaisse_du_mois_egale_la_somme_des_montant_paye(self):
        aujourdhui = timezone.localdate()
        f1 = self._facture(echeance=aujourdhui + timedelta(days=30))
        f2 = self._facture(echeance=aujourdhui + timedelta(days=30))
        self._paiement(f1, '3000', aujourdhui)
        self._paiement(f2, '4500', aujourdhui)
        self._paiement(f2, '9999', aujourdhui, statut=Paiement.Statut.REJETE)

        resp = self.api.get('/api/django/ventes/factures/kpis/')
        attendu = sum(
            (f.montant_paye for f in Facture.objects.filter(
                company=self.company)), Decimal('0'))
        self.assertEqual(Decimal(resp.data['encaisse_mois']), attendu)
        self.assertEqual(Decimal(resp.data['encaisse_mois']), Decimal('7500'))

    def test_encours_retard_et_a_echoir(self):
        aujourdhui = timezone.localdate()
        en_retard = self._facture(echeance=aujourdhui - timedelta(days=10))
        bientot = self._facture(echeance=aujourdhui + timedelta(days=3))
        self._facture(echeance=aujourdhui + timedelta(days=60))
        # Un brouillon et une annulée n'entrent JAMAIS dans l'encours.
        self._facture(echeance=aujourdhui,
                      statut=Facture.Statut.BROUILLON)
        self._facture(echeance=aujourdhui, statut=Facture.Statut.ANNULEE)

        resp = self.api.get('/api/django/ventes/factures/kpis/')
        self.assertEqual(resp.data['nb_impayees'], 3)
        self.assertEqual(resp.data['nb_en_retard'], 1)
        self.assertEqual(Decimal(resp.data['total_en_retard']),
                         en_retard.montant_du)
        self.assertEqual(Decimal(resp.data['total_a_echoir_7j']),
                         bientot.montant_du)
        self.assertEqual(Decimal(resp.data['total_du']), Decimal('36000'))

    def test_borne_a_la_societe(self):
        """Le sélecteur agrège le queryset DÉJÀ scopé du viewset."""
        autre = Company.objects.create(
            nom='AUD157 B', slug=f'aud157b-{_nxt()}')
        client_b = Client.objects.create(
            company=autre, nom='B', prenom='C', telephone='+212600000159')
        f = Facture.objects.create(
            company=autre, client=client_b,
            reference=f'FAC-AUD157-{_nxt()}', statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'))
        Paiement.objects.create(
            company=autre, facture=f, montant=Decimal('99999'),
            date_paiement=timezone.localdate(), mode=Paiement.Mode.VIREMENT)

        resp = self.api.get('/api/django/ventes/factures/kpis/')
        self.assertEqual(Decimal(resp.data['encaisse_mois']), Decimal('0'))
        self.assertEqual(resp.data['nb_impayees'], 0)

    # ── PACT10 — la forme servie EST celle du contrat committé ──

    def test_forme_conforme_au_contrat_pact10(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.assertEqual(
            contrat['endpoint'], 'GET /api/django/ventes/factures/kpis/')
        aujourdhui = timezone.localdate()
        facture = self._facture(echeance=aujourdhui + timedelta(days=3))
        self._paiement(facture, '1000', aujourdhui)

        resp = self.api.get('/api/django/ventes/factures/kpis/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        for cle, valeur in contrat['exemple'].items():
            with self.subTest(cle=cle):
                self.assertIsInstance(resp.data[cle], type(valeur))

    # ── (a) FAC-14 — le budget de requêtes ne suit plus le portefeuille ──

    def test_budget_requetes_liste_independant_du_nombre_de_factures(self):
        aujourdhui = timezone.localdate()

        def _cout(n):
            for _ in range(n):
                f = self._facture(echeance=aujourdhui + timedelta(days=10))
                self._paiement(f, '1000', aujourdhui)
            # Le PREMIER appel crée le `CompanyProfile` de la société
            # (`CompanyProfile.get` = get_or_create : SELECT + SAVEPOINT +
            # INSERT + RELEASE au lieu d'un simple SELECT ensuite). Ce coût
            # d'amorçage n'est pas une croissance avec le portefeuille : on
            # mesure les deux points À CHAUD, sinon le premier relevé est
            # gonflé de quelques requêtes et le test « N+1 » ment dans les
            # deux sens.
            self.api.get('/api/django/ventes/factures/')
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/ventes/factures/')
                self.assertEqual(resp.status_code, 200, resp.content)
            return len(ctx.captured_queries)

        cout_1 = _cout(1)
        cout_5 = _cout(4)
        self.assertEqual(
            cout_1, cout_5,
            f'N+1 liste factures : {cout_1} requêtes pour 1 facture, '
            f'{cout_5} pour 5.')
