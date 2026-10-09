"""AFAC9 (C-AFAC-003 + C-AFAC-011 + C-AFAC-014) — LA porte unique
d'encaissement ``exiger_facture_encaissable`` : seule une facture ÉMISE ou EN
RETARD s'encaisse ; un acompte d'un bon signé au domicile ne s'encaisse pas
avant le J+7 (CAD122, D-AFAC-C7 : sur TOUT encaissement) ; une avance rejetée
ne se ventile pas ; ``FactureSerializer`` porte ``encaissable`` et
``motif_non_encaissable`` (contrat ``facture_encaissable.json``).

Rejoue les sondes FBC-3 (brouillon encaissé 201), FUI-9 (groupé sur annulée
201), FENC-4/FPAY-4 (acompte J0 201), FENC-7 (avance rejetée ventilée 201).
Endpoints et services réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_porte_encaissement"
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
BASE = '/api/django/ventes/factures/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class PorteEncaissementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC9 Co', slug=f'afac9-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac9_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Porte', prenom='AFAC9',
            email=f'afac9-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _facture(self, statut, ttc=Decimal('1200'), **kw):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC9-{_nxt():04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc, **kw)

    def _acompte_domicile_signe_aujourdhui(self):
        from apps.ventes.models import BonCommande, Devis, Facture
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AFAC9-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        BonCommande.objects.create(
            company=self.company, reference=f'BC-AFAC9-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME, signe_au_domicile=True,
            date_signature_domicile=timezone.localdate())
        return self._facture(
            Facture.Statut.EMISE, devis=devis,
            type_facture=Facture.TypeFacture.ACOMPTE)

    def _payer(self, facture, montant='100'):
        return self.api.post(
            f'{BASE}{facture.id}/enregistrer-paiement/',
            {'montant': montant, 'date_paiement': str(timezone.localdate()),
             'mode': 'virement'}, format='json')

    def _nb_paiements(self, facture):
        from apps.ventes.models import Paiement
        return Paiement.objects.filter(facture=facture).count()

    # ── enregistrer-paiement ────────────────────────────────────────────
    def test_brouillon_enregistrer_paiement_refuse(self):
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.BROUILLON)
        r = self._payer(f)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('non émise', r.data['detail'])
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.BROUILLON)
        self.assertEqual(self._nb_paiements(f), 0)

    def test_annulee_enregistrer_paiement_refuse(self):
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.ANNULEE)
        self.assertEqual(self._payer(f).status_code, 400)
        self.assertEqual(self._nb_paiements(f), 0)

    def test_acompte_j0_enregistrer_paiement_refuse(self):
        f = self._acompte_domicile_signe_aujourdhui()
        r = self._payer(f)
        self.assertEqual(r.status_code, 400, r.data)
        seuil = (timezone.localdate() + timedelta(days=7)).strftime('%d/%m/%Y')
        self.assertIn(f'Acompte non encaissable avant le {seuil}',
                      r.data['detail'])
        self.assertEqual(self._nb_paiements(f), 0)

    def test_emise_s_encaisse_comme_avant(self):
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.EMISE)
        r = self._payer(f, '1200')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)

    # ── encaissement groupé ─────────────────────────────────────────────
    def test_groupe_sur_annulee_ou_brouillon_refuse(self):
        from apps.ventes.models import Facture, Paiement
        emise = self._facture(Facture.Statut.EMISE)
        for statut in (Facture.Statut.ANNULEE, Facture.Statut.BROUILLON):
            autre = self._facture(statut)
            r = self.api.post(f'{BASE}encaissement-groupe/', {
                'client': self.client_obj.id, 'montant': '2400',
                'mode': 'virement', 'date': str(timezone.localdate()),
                'factures': [emise.id, autre.id]}, format='json')
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn(autre.reference, r.data['detail'])
        self.assertFalse(
            Paiement.objects.filter(company=self.company).exists())

    def test_groupe_acompte_j0_refuse(self):
        from apps.ventes.models import Paiement
        f = self._acompte_domicile_signe_aujourdhui()
        r = self.api.post(f'{BASE}encaissement-groupe/', {
            'client': self.client_obj.id, 'montant': '100',
            'mode': 'especes', 'date': str(timezone.localdate()),
            'factures': [f.id]}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(
            Paiement.objects.filter(company=self.company).exists())

    # ── lien de paiement ────────────────────────────────────────────────
    def test_lien_paiement_brouillon_et_acompte_refuses(self):
        from apps.ventes.models import Facture, PaymentLink
        for f in (self._facture(Facture.Statut.BROUILLON),
                  self._acompte_domicile_signe_aujourdhui()):
            r = self.api.post(f'{BASE}{f.id}/lien-paiement/')
            self.assertEqual(r.status_code, 400, r.data)
            self.assertFalse(PaymentLink.objects.filter(facture=f).exists())

    # ── abandonner-solde ────────────────────────────────────────────────
    def test_abandonner_solde_brouillon_refuse(self):
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.BROUILLON)
        r = self.api.post(f'{BASE}{f.id}/abandonner-solde/',
                          {'motif': 'irrecouvrable'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.BROUILLON)
        self.assertIsNone(f.abandon_montant)

    # ── paiement avec retenue ───────────────────────────────────────────
    def test_paiement_avec_retenue_brouillon_refuse(self):
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.BROUILLON)
        r = self.api.post(
            f'/api/django/ventes/paiements/factures/{f.id}/'
            'paiement-avec-retenue/',
            {'montant': '1000', 'date_paiement': str(timezone.localdate()),
             'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '75'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(self._nb_paiements(f), 0)

    # ── ventilation d'avance ────────────────────────────────────────────
    def test_ventiler_sur_brouillon_refuse(self):
        from apps.ventes.models import AffectationPaiement, Facture
        from apps.ventes.services import enregistrer_avance
        f = self._facture(Facture.Statut.BROUILLON)
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('500'), date_paiement=date.today(),
            mode='virement', created_by=self.user)
        r = self.api.post(f'/api/django/ventes/paiements/{avance.id}/ventiler/',
                          {'facture': f.id, 'montant': '500'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(AffectationPaiement.objects.filter(
            facture=f).exists())

    def test_avance_rejetee_non_ventilable(self):
        from apps.ventes.models import AffectationPaiement, Facture, Paiement
        from apps.ventes.services import enregistrer_avance
        f = self._facture(Facture.Statut.EMISE, ttc=Decimal('10000'))
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('5000'), date_paiement=date.today(),
            mode='cheque', created_by=self.user)
        Paiement.objects.filter(pk=avance.pk).update(
            statut=Paiement.Statut.REJETE, motif_rejet='Chèque impayé')
        # L'avance rejetée sort de la liste des avances disponibles.
        lues = self.api.get('/api/django/ventes/paiements/'
                            'avances-non-affectees/',
                            {'client': self.client_obj.id})
        self.assertEqual(lues.status_code, 200, lues.data)
        self.assertNotIn(avance.id, [p['id'] for p in lues.data])
        du_avant = f.montant_du
        r = self.api.post(f'/api/django/ventes/paiements/{avance.id}/ventiler/',
                          {'facture': f.id, 'montant': '5000'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(AffectationPaiement.objects.filter(
            paiement=avance).exists())
        f.refresh_from_db()
        self.assertEqual(f.montant_du, du_avant)

    # ── service de bascule et récepteur FG370 ───────────────────────────
    def test_marquer_facture_soldee_ne_bascule_jamais_un_brouillon(self):
        from apps.ventes.domain.encaissements import marquer_facture_soldee
        from apps.ventes.models import Facture
        f = self._facture(Facture.Statut.BROUILLON)
        self.assertFalse(marquer_facture_soldee(f, force=True))
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.BROUILLON)

    def test_recepteur_capture_carte_sur_brouillon_ne_cree_rien(self):
        from apps.ventes.models import Facture
        from core import payment as core_payment
        f = self._facture(Facture.Statut.BROUILLON)
        tx = core_payment.creer_transaction(
            self.company, montant=Decimal('1200'), target=f)
        core_payment.marquer_paye(tx, external_ref='PSP-AFAC9-1')
        self.assertEqual(self._nb_paiements(f), 0)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.BROUILLON)

    # ── sérialiseur : encaissable / motif_non_encaissable ───────────────
    def test_serializer_encaissable(self):
        from apps.ventes.models import Facture
        emise = self._facture(Facture.Statut.EMISE)
        brouillon = self._facture(Facture.Statut.BROUILLON)
        soldee = self._facture(Facture.Statut.PAYEE)
        acompte = self._acompte_domicile_signe_aujourdhui()
        r = self.api.get(BASE)
        self.assertEqual(r.status_code, 200, r.data)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        par_id = {row['id']: row for row in rows}
        self.assertTrue(par_id[emise.id]['encaissable'])
        self.assertIsNone(par_id[emise.id]['motif_non_encaissable'])
        self.assertFalse(par_id[brouillon.id]['encaissable'])
        self.assertEqual(par_id[brouillon.id]['motif_non_encaissable'],
                         "Facture non émise : émettez-la avant d'encaisser.")
        self.assertEqual(par_id[soldee.id]['motif_non_encaissable'],
                         'Facture soldée : plus rien à encaisser.')
        self.assertFalse(par_id[acompte.id]['encaissable'])
        self.assertIn('Acompte non encaissable avant le',
                      par_id[acompte.id]['motif_non_encaissable'])
