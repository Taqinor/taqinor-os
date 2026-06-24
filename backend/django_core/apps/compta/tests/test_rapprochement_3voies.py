"""Tests FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur).

Couvre : création BC avec lignes, réception, facture fournisseur (saisie
manuelle) ; rapprochement 3 voies avec calcul d'écarts ; approbation/rejet ;
isolement multi-société (société B ne voit pas les données de A).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    BonCommandeFournisseur,
    FactureFournisseur,
    LigneBonCommandeFournisseur,
    LigneReceptionMarchandise,
    Rapprochement3Voies,
    ReceptionMarchandise,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x',
        company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bc(company, *, montant_ligne=Decimal('1000'), qte=Decimal('10'),
        date_commande=None, reference='BC-001'):
    """Crée un BC simple avec une ligne à 100 MAD HT × 10 = 1000 MAD HT."""
    return services.creer_bon_commande(
        company,
        date_commande=date_commande or date(2026, 1, 5),
        reference=reference,
        fournisseur_nom='Fournisseur Test',
        lignes=[{
            'designation': 'Panneaux 400W',
            'quantite': str(qte),
            'prix_unitaire_ht': str(montant_ligne / qte),
        }],
    )


def _reception(company, bc, *, qte_recue=Decimal('10'),
               date_reception=None):
    """Crée une réception complète du BC."""
    ligne_bc = bc.lignes_bc.first()
    return services.creer_reception(
        company, bc,
        date_reception=date_reception or date(2026, 1, 10),
        lignes=[{
            'ligne_bc_id': ligne_bc.id,
            'quantite_recue': str(qte_recue),
        }],
    )


def _facture(company, *, montant_ht=Decimal('1000'), reference='FAC-2026-001',
             date_facture=None):
    """Crée une facture fournisseur avec le montant HT indiqué."""
    return services.creer_facture_fournisseur(
        company,
        reference=reference,
        date_facture=date_facture or date(2026, 1, 12),
        montant_ht=montant_ht,
        fournisseur_nom='Fournisseur Test',
    )


# ── Tests service ─────────────────────────────────────────────────────────────

class BonCommandeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg131', 'FG131 Co')

    def test_creer_bc_calcule_montant_ht(self):
        bc = _bc(self.co)
        self.assertEqual(bc.montant_ht, Decimal('1000.00'))
        self.assertEqual(bc.company_id, self.co.id)
        self.assertEqual(bc.lignes_bc.count(), 1)

    def test_creer_bc_montant_ttc(self):
        bc = _bc(self.co)
        # 1000 HT × 1.20 = 1200 TTC
        self.assertEqual(bc.montant_ttc, Decimal('1200.00'))

    def test_creer_bc_ligne_quantite_nulle_refuse(self):
        with self.assertRaises((ValidationError, Exception)):
            services.creer_bon_commande(
                self.co,
                date_commande=date(2026, 1, 5),
                lignes=[{
                    'designation': 'Test', 'quantite': '0',
                    'prix_unitaire_ht': '100',
                }],
            )


class ReceptionServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg131-rec', 'FG131 Rec')

    def test_creer_reception_complete(self):
        bc = _bc(self.co)
        rec = _reception(self.co, bc)
        self.assertEqual(rec.company_id, self.co.id)
        self.assertEqual(rec.bon_commande_id, bc.id)
        self.assertEqual(rec.lignes_reception.count(), 1)
        lr = rec.lignes_reception.first()
        self.assertEqual(lr.quantite_recue, Decimal('10'))

    def test_creer_reception_bc_autre_societe_refuse(self):
        autre = make_company('fg131-autre', 'Autre')
        bc_autre = _bc(autre)
        with self.assertRaises(ValidationError):
            _reception(self.co, bc_autre)

    def test_creer_reception_ligne_bc_inconnue_refuse(self):
        bc = _bc(self.co)
        bc2 = _bc(self.co, reference='BC-002')
        ligne_bc2 = bc2.lignes_bc.first()
        with self.assertRaises(ValidationError):
            services.creer_reception(
                self.co, bc,
                date_reception=date(2026, 1, 10),
                lignes=[{
                    'ligne_bc_id': ligne_bc2.id,
                    'quantite_recue': '5',
                }],
            )


class FactureFournisseurServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg131-ff', 'FG131 FF')

    def test_creer_facture_calcule_tva_ttc(self):
        fac = _facture(self.co)
        self.assertEqual(fac.montant_ht, Decimal('1000.00'))
        self.assertEqual(fac.montant_tva, Decimal('200.00'))
        self.assertEqual(fac.montant_ttc, Decimal('1200.00'))

    def test_creer_facture_reference_unique_par_societe(self):
        _facture(self.co)
        with self.assertRaises(Exception):
            _facture(self.co, reference='FAC-2026-001')

    def test_creer_facture_meme_reference_autre_societe_ok(self):
        autre = make_company('fg131-ff-b', 'FG131 FF B')
        _facture(self.co, reference='FAC-001')
        fac2 = _facture(autre, reference='FAC-001')
        self.assertEqual(fac2.company_id, autre.id)


# ── Tests rapprochement 3 voies ───────────────────────────────────────────────

class Rapprochement3VoiesServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg131-r3v', 'FG131 R3V')
        self.bc = _bc(self.co, montant_ligne=Decimal('1000'))
        self.rec = _reception(self.co, self.bc)
        self.fac = _facture(self.co, montant_ht=Decimal('1000'))

    def test_creer_rapprochement_calcule_montants(self):
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, self.fac)
        self.assertEqual(rap.montant_commande_ht, Decimal('1000.00'))
        self.assertEqual(rap.montant_recu_ht, Decimal('1000.00'))
        self.assertEqual(rap.montant_facture_ht, Decimal('1000.00'))
        self.assertEqual(rap.ecart_commande_facture_ht, Decimal('0.00'))
        self.assertEqual(rap.ecart_recu_facture_ht, Decimal('0.00'))
        self.assertEqual(rap.statut, Rapprochement3Voies.Statut.EN_COURS)

    def test_ecart_non_nul_quand_facture_superieure(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1050'),
                           reference='FAC-2026-002')
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, fac_sup)
        self.assertEqual(rap.ecart_commande_facture_ht, Decimal('50.00'))
        self.assertEqual(rap.ecart_recu_facture_ht, Decimal('50.00'))
        self.assertTrue(rap.paiement_bloque)

    def test_ecart_reception_partielle(self):
        # On reçoit seulement 8/10 mais la facture est pour 10.
        rec_partielle = _reception(self.co, self.bc, qte_recue=Decimal('8'),
                                   date_reception=date(2026, 1, 11))
        fac = _facture(self.co, montant_ht=Decimal('1000'),
                       reference='FAC-2026-003')
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, rec_partielle, fac)
        # Reçu HT = 8 × 100 = 800, facturé = 1000 → écart reçu/facturé = +200
        self.assertEqual(rap.montant_recu_ht, Decimal('800.00'))
        self.assertEqual(rap.ecart_recu_facture_ht, Decimal('200.00'))

    def test_approuver_ecart_nul_ok(self):
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, self.fac)
        services.valider_rapprochement_3voies(rap, approuver=True)
        rap.refresh_from_db()
        self.assertEqual(rap.statut, Rapprochement3Voies.Statut.APPROUVE)
        self.assertTrue(rap.est_approuve)
        self.assertFalse(rap.paiement_bloque)

    def test_approuver_ecart_hors_tolerance_refuse(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1050'),
                           reference='FAC-2026-004')
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, fac_sup, tolerance_ht=Decimal('30'))
        with self.assertRaises(ValidationError):
            services.valider_rapprochement_3voies(rap, approuver=True)
        rap.refresh_from_db()
        self.assertEqual(rap.statut, Rapprochement3Voies.Statut.EN_COURS)

    def test_approuver_ecart_dans_tolerance_ok(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1020'),
                           reference='FAC-2026-005')
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, fac_sup, tolerance_ht=Decimal('50'))
        services.valider_rapprochement_3voies(rap, approuver=True)
        rap.refresh_from_db()
        self.assertEqual(rap.statut, Rapprochement3Voies.Statut.APPROUVE)

    def test_rejeter_rapprochement(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1200'),
                           reference='FAC-2026-006')
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, fac_sup)
        services.valider_rapprochement_3voies(rap, approuver=False,
                                               notes='Montant incorrect')
        rap.refresh_from_db()
        self.assertEqual(rap.statut, Rapprochement3Voies.Statut.REJETE)
        self.assertTrue(rap.paiement_bloque)
        self.assertEqual(rap.notes, 'Montant incorrect')

    def test_approuver_deux_fois_refuse(self):
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, self.fac)
        services.valider_rapprochement_3voies(rap, approuver=True)
        with self.assertRaises(ValidationError):
            services.valider_rapprochement_3voies(rap, approuver=True)

    def test_bc_autre_societe_refuse(self):
        autre = make_company('fg131-r3v-b', 'Autre B')
        bc_b = _bc(autre)
        with self.assertRaises(ValidationError):
            services.creer_rapprochement_3voies(
                self.co, bc_b, self.rec, self.fac)

    def test_facture_autre_societe_refuse(self):
        autre = make_company('fg131-r3v-c', 'Autre C')
        fac_b = _facture(autre, reference='FAC-B-001')
        with self.assertRaises(ValidationError):
            services.creer_rapprochement_3voies(
                self.co, self.bc, self.rec, fac_b)

    def test_reception_ne_correspond_pas_bc_refuse(self):
        bc2 = _bc(self.co, reference='BC-002')
        rec2 = _reception(self.co, bc2)
        with self.assertRaises(ValidationError):
            services.creer_rapprochement_3voies(
                self.co, self.bc, rec2, self.fac)

    def test_resume_rapprochement(self):
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, self.fac, tolerance_ht=Decimal('10'))
        resume = selectors.resume_rapprochement_3voies(rap)
        self.assertEqual(resume['montant_commande_ht'], Decimal('1000.00'))
        self.assertEqual(resume['montant_recu_ht'], Decimal('1000.00'))
        self.assertEqual(resume['montant_facture_ht'], Decimal('1000.00'))
        self.assertEqual(resume['ecart_commande_facture_ht'], Decimal('0.00'))
        self.assertEqual(resume['ecarts_dans_tolerance'], True)
        self.assertEqual(resume['paiement_bloque'], True)  # pas encore approuvé

    def test_factures_a_valider_selector(self):
        # Crée une facture sans rapprochement approuvé => doit figurer.
        a_valider = selectors.factures_fournisseur_a_valider(self.co)
        ids = [f.id for f in a_valider]
        self.assertIn(self.fac.id, ids)
        # Approuve le rapprochement => la facture n'est plus bloquée.
        rap = services.creer_rapprochement_3voies(
            self.co, self.bc, self.rec, self.fac)
        services.valider_rapprochement_3voies(rap, approuver=True)
        a_valider_apres = selectors.factures_fournisseur_a_valider(self.co)
        ids_apres = [f.id for f in a_valider_apres]
        self.assertNotIn(self.fac.id, ids_apres)


# ── Tests isolation multi-société ─────────────────────────────────────────────

class IsolationMultiSocieteTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg131-iso-a', 'FG131 Iso A')
        self.co_b = make_company('fg131-iso-b', 'FG131 Iso B')
        self.user_a = make_user(self.co_a, 'fg131-user-a')
        self.user_b = make_user(self.co_b, 'fg131-user-b')
        # Données de A
        self.bc_a = _bc(self.co_a)
        self.rec_a = _reception(self.co_a, self.bc_a)
        self.fac_a = _facture(self.co_a)

    def test_api_bc_scopee_societe(self):
        api_a = auth(self.user_a)
        api_b = auth(self.user_b)
        resp_a = api_a.get('/api/django/compta/bons-commande-fournisseur/')
        resp_b = api_b.get('/api/django/compta/bons-commande-fournisseur/')
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)
        ids_a = [r['id'] for r in resp_a.data['results']
                 if isinstance(resp_a.data, dict) and 'results' in resp_a.data]
        ids_b = [r['id'] for r in resp_b.data['results']
                 if isinstance(resp_b.data, dict) and 'results' in resp_b.data]
        # B ne voit aucun BC de A.
        if ids_a and ids_b:
            for id_a in ids_a:
                self.assertNotIn(id_a, ids_b)

    def test_api_factures_fournisseur_scopee(self):
        api_b = auth(self.user_b)
        resp = api_b.get('/api/django/compta/factures-fournisseur/')
        self.assertEqual(resp.status_code, 200)
        # Résultats de B seulement (B n'a pas de facture)
        data = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        for item in data:
            # On ne peut pas voir la facture de A directement, mais on s'assure
            # que les IDs retournés n'incluent pas la facture de A.
            self.assertNotEqual(item['id'], self.fac_a.id)

    def test_api_rapprochement_scopee(self):
        # Crée un rap chez A
        rap_a = services.creer_rapprochement_3voies(
            self.co_a, self.bc_a, self.rec_a, self.fac_a)
        api_b = auth(self.user_b)
        resp = api_b.get('/api/django/compta/rapprochements-3voies/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        ids = [r['id'] for r in data]
        self.assertNotIn(rap_a.id, ids)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'fg131-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/bons-commande-fournisseur/')
        self.assertEqual(resp.status_code, 403)


# ── Tests endpoint CRUD ───────────────────────────────────────────────────────

class Rapprochement3VoiesAPITests(TestCase):
    def setUp(self):
        self.co = make_company('fg131-api', 'FG131 API')
        self.user = make_user(self.co, 'fg131-api-user')
        self.api = auth(self.user)
        self.bc = _bc(self.co)
        self.rec = _reception(self.co, self.bc)
        self.fac = _facture(self.co)

    def test_creer_bc_via_endpoint(self):
        resp = self.api.post(
            '/api/django/compta/bons-commande-fournisseur/creer-avec-lignes/',
            {
                'date_commande': '2026-02-01',
                'reference': 'BC-API-001',
                'fournisseur_nom': 'Four API',
                'lignes': [
                    {
                        'designation': 'Onduleur 5kW',
                        'quantite': '2',
                        'prix_unitaire_ht': '3500',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(str(resp.data['montant_ht'])), Decimal('7000.00'))

    def test_creer_rapprochement_et_approuver(self):
        # Création du rapprochement.
        resp = self.api.post(
            '/api/django/compta/rapprochements-3voies/',
            {
                'bon_commande': self.bc.id,
                'reception': self.rec.id,
                'facture': self.fac.id,
                'tolerance_ht': '50',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        rap_id = resp.data['id']
        self.assertEqual(resp.data['statut'], 'en_cours')
        # Les écarts doivent être nuls (BC=1000, reçu=1000, facturé=1000).
        self.assertEqual(
            Decimal(str(resp.data['ecart_commande_facture_ht'])),
            Decimal('0.00'))
        # Résumé.
        resp_r = self.api.get(
            f'/api/django/compta/rapprochements-3voies/{rap_id}/resume/')
        self.assertEqual(resp_r.status_code, 200)
        self.assertTrue(resp_r.data['ecarts_dans_tolerance'])
        # Approbation.
        resp_a = self.api.post(
            f'/api/django/compta/rapprochements-3voies/{rap_id}/approuver/',
            {'notes': 'Contrôle OK'},
            format='json',
        )
        self.assertEqual(resp_a.status_code, 200, resp_a.data)
        self.assertEqual(resp_a.data['statut'], 'approuve')
        # La facture n'est plus bloquée.
        resp_av = self.api.get(
            '/api/django/compta/factures-fournisseur/a-valider/')
        self.assertEqual(resp_av.status_code, 200)
        ids_bloques = [f['id'] for f in resp_av.data]
        self.assertNotIn(self.fac.id, ids_bloques)

    def test_rejeter_rapprochement(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1200'),
                           reference='FAC-REJET-001')
        resp = self.api.post(
            '/api/django/compta/rapprochements-3voies/',
            {
                'bon_commande': self.bc.id,
                'reception': self.rec.id,
                'facture': fac_sup.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        rap_id = resp.data['id']
        resp_r = self.api.post(
            f'/api/django/compta/rapprochements-3voies/{rap_id}/rejeter/',
            {'notes': 'Montant en litige'},
            format='json',
        )
        self.assertEqual(resp_r.status_code, 200, resp_r.data)
        self.assertEqual(resp_r.data['statut'], 'rejete')

    def test_approuver_ecart_hors_tolerance_retourne_400(self):
        fac_sup = _facture(self.co, montant_ht=Decimal('1200'),
                           reference='FAC-TOL-001')
        resp = self.api.post(
            '/api/django/compta/rapprochements-3voies/',
            {
                'bon_commande': self.bc.id,
                'reception': self.rec.id,
                'facture': fac_sup.id,
                'tolerance_ht': '10',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        rap_id = resp.data['id']
        resp_a = self.api.post(
            f'/api/django/compta/rapprochements-3voies/{rap_id}/approuver/')
        self.assertEqual(resp_a.status_code, 400)
