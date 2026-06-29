"""N91/F21 — synchro IDEMPOTENTE de la capture terrain hors-ligne.

Couvre :
  * rejouer la même clé d'op = no-op (le 2e envoi ne ré-applique pas l'effet) ;
  * last-write-wins sur des opérations contradictoires ;
  * isolation multi-société (un locataire ne peut pas viser la cible d'un autre,
    ni rejouer/voir l'op d'un autre via la même valeur de clé) ;
  * lot malformé rejeté (ops non-liste, lot trop grand, op_type inconnu,
    client_op_id manquant) ;
  * la couverture du flux complet (N91 : checklist chantier + signature PV ;
    F21 : check-in, matériel, consommé, réserve, sécurité, série).

Run :
    python manage.py test apps.installations.tests_field_sync -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from apps.installations.models import (
    ComponentSerial, FieldOp, Intervention, Reserve,
)
from apps.installations.services import create_installation_from_devis
from apps.installations import field_sync

User = get_user_model()
_seq = itertools.count(1)
SYNC_URL = '/api/django/installations/sync/'


def make_company(slug, nom='Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, role_legacy='admin'):
    n = next(_seq)
    return User.objects.create_user(
        username=f'u{n}', email=f'u{n}@ex.invalid', password='pw',
        company=company, role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Onduleur', stock=10):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=Decimal('100'), prix_achat=Decimal('60'),
        quantite_stock=stock)


def make_chantier(company, user, lines=None):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Cli',
        email=f's-{company.id}-{n}@ex.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Cli', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in (lines or []):
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_intervention(inst, company, user):
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention='pose',
        created_by=user)


class FieldSyncBaseTest(TestCase):
    def setUp(self):
        self.company = make_company('sync-co')
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.iv = make_intervention(self.inst, self.company, self.user)


class IdempotencyTests(FieldSyncBaseTest):
    def test_replay_same_key_is_noop(self):
        """Rejouer la même clé n'ajoute PAS une 2e réserve : 1re = applied,
        2e = replayed, et le résultat mémorisé est renvoyé à l'identique."""
        op = {'client_op_id': 'op-aaa', 'op_type': 'intervention.reserve',
              'payload': {'intervention': self.iv.id, 'description': 'Reprise joint'}}
        r1 = self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['applied'], 1)
        self.assertEqual(r1.data['results'][0]['status'], 'applied')
        first_result = r1.data['results'][0]['result']

        r2 = self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(r2.data['applied'], 0)
        self.assertEqual(r2.data['replayed'], 1)
        self.assertEqual(r2.data['results'][0]['status'], 'replayed')
        self.assertEqual(r2.data['results'][0]['result'], first_result)
        # Effet appliqué UNE seule fois.
        self.assertEqual(Reserve.objects.filter(intervention=self.iv).count(), 1)
        self.assertEqual(
            FieldOp.objects.filter(company=self.company, client_op_id='op-aaa').count(), 1)

    def test_duplicate_keys_in_one_batch_apply_once(self):
        """Deux ops identiques dans le MÊME lot : la 2e est un rejeu."""
        op = {'client_op_id': 'op-dup', 'op_type': 'intervention.checkin',
              'payload': {'intervention': self.iv.id, 'lat': 33.5, 'lng': -7.6}}
        r = self.api.post(SYNC_URL, {'ops': [op, op]}, format='json')
        self.assertEqual(r.data['applied'], 1)
        self.assertEqual(r.data['replayed'], 1)

    def test_serial_not_duplicated_on_replay(self):
        produit = make_produit(self.company)
        op = {'client_op_id': 'op-ser', 'op_type': 'intervention.serial',
              'payload': {'intervention': self.iv.id, 'produit': produit.id,
                          'numero_serie': 'SN-123'}}
        self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(
            ComponentSerial.objects.filter(intervention=self.iv).count(), 1)


class LastWriteWinsTests(FieldSyncBaseTest):
    def test_distinct_keys_last_write_wins_on_checklist(self):
        """Deux ops DISTINCTES (clés différentes) qui cochent puis décochent la
        même étape : la dernière appliquée gagne."""
        inst = make_chantier(self.company, self.user)
        # Matérialise la checklist + prend une étape réelle.
        from apps.installations.services import ensure_checklist_items
        items = ensure_checklist_items(inst)
        cle = items[0].cle
        coche = {'client_op_id': 'c1', 'op_type': 'chantier.cocher_checklist',
                 'payload': {'chantier': inst.id, 'cle': cle, 'fait': True}}
        decoche = {'client_op_id': 'c2', 'op_type': 'chantier.cocher_checklist',
                   'payload': {'chantier': inst.id, 'cle': cle, 'fait': False}}
        r = self.api.post(SYNC_URL, {'ops': [coche, decoche]}, format='json')
        self.assertEqual(r.data['applied'], 2)
        item = inst.checklist.get(cle=cle)
        self.assertFalse(item.fait)  # dernière écriture = décoché

    def test_consommation_quantity_overwrite_not_increment(self):
        produit = make_produit(self.company, stock=20)
        inst = make_chantier(self.company, self.user, lines=[(produit, 5)])
        iv = make_intervention(inst, self.company, self.user)
        from apps.installations import field_capture
        cons = field_capture.ensure_consommation(iv)
        ligne = cons.lignes.first()
        op1 = {'client_op_id': 'q1', 'op_type': 'intervention.consommation_ligne',
               'payload': {'intervention': iv.id, 'ligne': ligne.id,
                           'quantite_utilisee': 3}}
        op2 = {'client_op_id': 'q2', 'op_type': 'intervention.consommation_ligne',
               'payload': {'intervention': iv.id, 'ligne': ligne.id,
                           'quantite_utilisee': 7}}
        self.api.post(SYNC_URL, {'ops': [op1, op2]}, format='json')
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_utilisee, Decimal('7'))  # remplacé, pas 10


class CompanyIsolationTests(FieldSyncBaseTest):
    def test_cannot_target_other_company_intervention(self):
        other = make_company('sync-other')
        other_user = make_user(other)
        other_inst = make_chantier(other, other_user)
        other_iv = make_intervention(other_inst, other, other_user)
        op = {'client_op_id': 'x1', 'op_type': 'intervention.checkin',
              'payload': {'intervention': other_iv.id, 'lat': 1, 'lng': 1}}
        r = self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(r.data['errors'], 1)
        self.assertEqual(r.data['results'][0]['status'], 'error')
        # Aucun FieldOp écrit pour une op en échec.
        self.assertFalse(FieldOp.objects.filter(client_op_id='x1').exists())

    def test_same_key_isolated_per_company(self):
        """La même valeur de clé chez deux sociétés ne collisionne pas : chacune
        applique la sienne, aucune ne rejoue celle de l'autre."""
        other = make_company('sync-other2')
        other_user = make_user(other)
        other_inst = make_chantier(other, other_user)
        other_iv = make_intervention(other_inst, other, other_user)
        op_a = {'client_op_id': 'shared', 'op_type': 'intervention.reserve',
                'payload': {'intervention': self.iv.id, 'description': 'A'}}
        op_b = {'client_op_id': 'shared', 'op_type': 'intervention.reserve',
                'payload': {'intervention': other_iv.id, 'description': 'B'}}
        self.api.post(SYNC_URL, {'ops': [op_a]}, format='json')
        rb = auth(other_user).post(SYNC_URL, {'ops': [op_b]}, format='json')
        self.assertEqual(rb.data['applied'], 1)  # PAS un rejeu
        self.assertEqual(
            FieldOp.objects.filter(client_op_id='shared').count(), 2)

    def test_requires_authentication(self):
        r = APIClient().post(SYNC_URL, {'ops': []}, format='json')
        self.assertIn(r.status_code, (401, 403))


class MalformedBatchTests(FieldSyncBaseTest):
    def test_ops_not_a_list_rejected(self):
        r = self.api.post(SYNC_URL, {'ops': {'nope': 1}}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_batch_too_large_rejected(self):
        ops = [{'client_op_id': f'op-{i}', 'op_type': 'intervention.checkin',
                'payload': {'intervention': self.iv.id}}
               for i in range(field_sync.MAX_BATCH + 1)]
        r = self.api.post(SYNC_URL, {'ops': ops}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_unknown_op_type_is_per_op_error_not_500(self):
        op = {'client_op_id': 'op-u', 'op_type': 'intervention.nope',
              'payload': {'intervention': self.iv.id}}
        r = self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['errors'], 1)

    def test_missing_client_op_id_is_error(self):
        op = {'op_type': 'intervention.checkin',
              'payload': {'intervention': self.iv.id}}
        r = self.api.post(SYNC_URL, {'ops': [op]}, format='json')
        self.assertEqual(r.data['errors'], 1)

    def test_non_dict_op_is_error_not_crash(self):
        r = self.api.post(SYNC_URL, {'ops': ['oops']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['errors'], 1)


class FullFlowTests(FieldSyncBaseTest):
    def test_full_intervention_flow_in_one_batch(self):
        """F21 — un lot couvrant le flux complet s'applique et reste rejouable."""
        produit = make_produit(self.company)
        ops = [
            {'client_op_id': 'f1', 'op_type': 'intervention.depart_depot',
             'payload': {'intervention': self.iv.id}},
            {'client_op_id': 'f2', 'op_type': 'intervention.checkin',
             'payload': {'intervention': self.iv.id, 'lat': 33.5, 'lng': -7.6}},
            {'client_op_id': 'f3', 'op_type': 'intervention.serial',
             'payload': {'intervention': self.iv.id, 'produit': produit.id,
                         'numero_serie': 'SN-9'}},
            {'client_op_id': 'f4', 'op_type': 'intervention.reserve',
             'payload': {'intervention': self.iv.id, 'description': 'Reprise'}},
            {'client_op_id': 'f5', 'op_type': 'intervention.cocher_safety',
             'payload': {'intervention': self.iv.id, 'cle': 'epi_portes'}},
            {'client_op_id': 'f6', 'op_type': 'intervention.signer_client',
             'payload': {'intervention': self.iv.id,
                         'signature_client': 'data:img', 'signataire_nom': 'M. Client'}},
            {'client_op_id': 'f7', 'op_type': 'intervention.retour',
             'payload': {'intervention': self.iv.id}},
        ]
        r = self.api.post(SYNC_URL, {'ops': ops}, format='json')
        self.assertEqual(r.data['applied'], 7, r.data)
        self.iv.refresh_from_db()
        self.assertIsNotNone(self.iv.arrivee_site_le)
        self.assertIsNotNone(self.iv.signe_le)
        self.assertEqual(self.iv.signataire_nom, 'M. Client')
        # Rejeu intégral = no-op.
        r2 = self.api.post(SYNC_URL, {'ops': ops}, format='json')
        self.assertEqual(r2.data['replayed'], 7)
        self.assertEqual(r2.data['applied'], 0)
