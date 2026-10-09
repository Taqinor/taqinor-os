"""AFAC17 (C-AFAC-013, D-AFAC-C2 a) — corriger un paiement mal saisi :

* ``POST paiements/<id>/reaffecter/ {facture_cible}`` : vers une facture
  encaissable du MÊME client, sous verrou des deux factures, chatter
  ancien → nouveau, statuts redérivés (ATOT8) ;
* ``POST paiements/<id>/annuler-saisie/ {motif}`` : état ``annule_saisie``
  daté, motivé, signé, hors du payé — distinct d'un rejet bancaire (aucun
  ``paiement_rejete``, plus de quittance, plus rejetable).

Rejoue la sonde FENC-6 (« POST reaffecter, annuler … → 404 ; statuts du
paiement = ['encaisse','rejete'] »). Endpoints, services et modèles réels,
aucun mock.

Test-du-test : ne plus exclure ``annule_saisie`` de ``montant_paye``
(``Paiement.STATUTS_NON_COMPTES``) ⇒ ``test_annuler_saisie_hors_paye``
échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_correction_paiement"
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
BASE = '/api/django/ventes/paiements'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class CorrectionPaiementTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC17 {n}', slug=f'afac17-{n}')
        self.user = User.objects.create_user(
            username=f'afac17_resp_{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Correction', prenom='AFAC17',
            email=f'afac17-{n}@example.invalid')
        self.autre_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='AFAC17',
            email=f'afac17-autre-{n}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _facture(self, client=None, statut='emise', ttc='12000'):
        from apps.ventes.models import Facture
        ttc = Decimal(ttc)
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC17-{_nxt():04d}',
            client=client or self.client_obj, statut=statut,
            taux_tva=Decimal('20'), montant_ht=ttc / Decimal('1.2'),
            montant_tva=ttc - ttc / Decimal('1.2'), montant_ttc=ttc,
            date_echeance=date.today() + timedelta(days=30),
            created_by=self.user)

    def _paiement(self, facture, montant='5000', mode='virement'):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date.today(), mode=mode, created_by=self.user)

    def _relire(self, obj):
        return type(obj).objects.get(pk=obj.pk)

    # ── réaffecter ──────────────────────────────────────────────────────
    def test_reaffecter_meme_client(self):
        from apps.ventes.models import FactureActivity
        a, b = self._facture(), self._facture()
        p = self._paiement(a)
        r = self.api.post(f'{BASE}/{p.id}/reaffecter/',
                          {'facture_cible': b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data),
                         {'paiement', 'facture_source', 'facture_cible'})
        self.assertEqual(r.data['facture_source']['montant_du'], '12000.00')
        self.assertEqual(r.data['facture_cible']['montant_du'], '7000.00')
        # CLAUSE PERSISTANCE — relu en base.
        self.assertEqual(self._relire(p).facture_id, b.id)
        self.assertEqual(self._relire(a).montant_du, Decimal('12000.00'))
        self.assertEqual(self._relire(b).montant_du, Decimal('7000.00'))
        for f in (a, b):
            self.assertTrue(FactureActivity.objects.filter(
                facture=f, field='paiement_reaffecte').exists())

    def test_reaffecter_solde_et_rouvre(self):
        a, b = self._facture(), self._facture(ttc='5000')
        p = self._paiement(a)
        r = self.api.post(f'{BASE}/{p.id}/reaffecter/',
                          {'facture_cible': b.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._relire(b).statut, 'payee')
        self.assertEqual(self._relire(a).statut, 'emise')

    def test_reaffecter_autre_client_refuse(self):
        a, c = self._facture(), self._facture(client=self.autre_client)
        p = self._paiement(a)
        r = self.api.post(f'{BASE}/{p.id}/reaffecter/',
                          {'facture_cible': c.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'facture_autre_client')
        self.assertEqual(self._relire(p).facture_id, a.id)

    def test_reaffecter_cible_non_encaissable(self):
        a, brouillon = self._facture(), self._facture(statut='brouillon')
        p = self._paiement(a)
        r = self.api.post(f'{BASE}/{p.id}/reaffecter/',
                          {'facture_cible': brouillon.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'cible_non_encaissable')
        self.assertEqual(self._relire(p).facture_id, a.id)

    # ── annuler la saisie ───────────────────────────────────────────────
    def test_annuler_saisie_hors_paye(self):
        from apps.ventes.domain.encaissements import recalculer_statut_paiement
        a = self._facture()
        p = self._paiement(a, montant='12000')
        recalculer_statut_paiement(a)
        self.assertEqual(self._relire(a).statut, 'payee')
        r = self.api.post(f'{BASE}/{p.id}/annuler-saisie/', {},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'motif_requis')
        r = self.api.post(f'{BASE}/{p.id}/annuler-saisie/',
                          {'motif': 'Montant saisi 12 000 au lieu de 1 200'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'annule_saisie')
        self.assertEqual(r.data['annule_par_nom'], self.user.username)
        self.assertTrue(r.data['annule_le'])
        # CLAUSE PERSISTANCE — paiement conservé, daté ; facture rouverte.
        p = self._relire(p)
        self.assertEqual(p.statut, 'annule_saisie')
        self.assertIsNotNone(p.annule_le)
        self.assertEqual(p.annule_par_id, self.user.id)
        self.assertEqual(p.motif_annulation,
                         'Montant saisi 12 000 au lieu de 1 200')
        a = self._relire(a)
        self.assertEqual(a.montant_paye, Decimal('0'))
        self.assertEqual(a.montant_du, Decimal('12000.00'))
        self.assertEqual(a.statut, 'emise')
        # Jamais une seconde annulation.
        r = self.api.post(f'{BASE}/{p.id}/annuler-saisie/',
                          {'motif': 'encore'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)

    def test_annuler_saisie_n_est_pas_un_rejet(self):
        from core.events import paiement_rejete
        recus = []

        def _ecoute(sender, **kwargs):
            recus.append(kwargs)
        paiement_rejete.connect(_ecoute, weak=False)
        self.addCleanup(paiement_rejete.disconnect, _ecoute)
        a = self._facture()
        p = self._paiement(a)
        r = self.api.post(f'{BASE}/{p.id}/annuler-saisie/',
                          {'motif': 'Doublon de saisie'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(recus, [])
        self.assertNotEqual(self._relire(p).statut, 'rejete')
        # Plus de quittance, plus de rejet bancaire.
        r = self.api.get(f'{BASE}/{p.id}/recu-pdf/')
        self.assertEqual(r.status_code, 409)
        r = self.api.post(f'{BASE}/{p.id}/rejeter/', {'motif': 'impayé'},
                          format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(recus, [])

    def test_paiement_remis_refuse(self):
        from apps.ventes.models import (
            LigneRemiseEncaissement, RemiseEncaissement,
        )
        a, b = self._facture(), self._facture()
        p = self._paiement(a, mode='especes')
        remise = RemiseEncaissement.objects.create(
            company=self.company, technicien=self.user,
            reference=f'REM-AFAC17-{_nxt()}', date_collecte=date.today(),
            montant_declare=Decimal('5000'), created_by=self.user)
        LigneRemiseEncaissement.objects.create(remise=remise, paiement=p)
        r = self.api.post(f'{BASE}/{p.id}/reaffecter/',
                          {'facture_cible': b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'paiement_remis_en_banque')
        r = self.api.post(f'{BASE}/{p.id}/annuler-saisie/',
                          {'motif': 'Erreur'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'paiement_remis_en_banque')
        p = self._relire(p)
        self.assertEqual(p.facture_id, a.id)
        self.assertEqual(p.statut, 'encaisse')
