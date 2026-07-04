"""
XMFG4 — Cycle de vie complet de l'ordre d'assemblage : dates, responsable,
annulation, chatter.

Couvre :
  * `date_prevue` et `responsable` éditables ;
  * `annuler` motivé fonctionne et libère les réservations ;
  * `annuler` interdite après mouvement de stock (`stock_mouvemente=True`) ;
  * `annuler` sans motif rejetée ;
  * le chatter journalise création + modifications + note manuelle ;
  * la liste est filtrable par `statut`/`date_prevue`/`responsable`.

Run :
    python manage.py test apps.installations.tests_xmfg4_lifecycle -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, ReservationAssemblage,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg4-co-{n}', defaults={'nom': nom or f'XMFG4 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestLifecycle(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)

    def test_date_prevue_et_responsable_editables(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 2,
            'date_prevue': '2026-08-01', 'responsable': self.user.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        ordre = OrdreAssemblage.objects.get(id=resp.data['id'])
        self.assertEqual(str(ordre.date_prevue), '2026-08-01')
        self.assertEqual(ordre.responsable_id, self.user.id)

    def test_annuler_motive_libere_reservations(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A1', kit=self.kit, quantite=1)
        from apps.installations.services import seed_reservations_assemblage
        seed_reservations_assemblage(ordre)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/annuler/',
            {'motif_annulation': 'Erreur de saisie'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.ANNULE)
        self.assertEqual(ordre.motif_annulation, 'Erreur de saisie')
        resa = ReservationAssemblage.objects.get(ordre=ordre, produit=self.comp1)
        self.assertFalse(resa.active)

    def test_annuler_sans_motif_rejete(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A2', kit=self.kit, quantite=1)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/annuler/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_annuler_apres_mouvement_stock_interdite(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A3', kit=self.kit, quantite=1)
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/annuler/',
            {'motif_annulation': 'Trop tard'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_chatter_creation_modification_note(self):
        resp = self.api.post(f'{BASE}/ordres-assemblage/', {
            'kit': self.kit.id, 'quantite': 2,
        }, format='json')
        ordre_id = resp.data['id']

        hist = self.api.get(f'{BASE}/ordres-assemblage/{ordre_id}/historique/')
        self.assertEqual(hist.status_code, 200, hist.content)
        kinds = [h['kind'] for h in hist.data]
        self.assertIn('creation', kinds)

        note_resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre_id}/noter/',
            {'body': 'Attention manque de vis'}, format='json')
        self.assertEqual(note_resp.status_code, 201, note_resp.content)

        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre_id}/demarrer/', {}, format='json')
        hist2 = self.api.get(f'{BASE}/ordres-assemblage/{ordre_id}/historique/')
        kinds2 = [h['kind'] for h in hist2.data]
        self.assertIn('note', kinds2)
        self.assertIn('modification', kinds2)

    def test_liste_filtrable_par_statut_date_responsable(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-F1', kit=self.kit, quantite=1,
            date_prevue='2026-09-01', responsable=self.user)
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/?statut=planifie&responsable='
            f'{self.user.id}&date_prevue=2026-09-01')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        ids = [r['id'] for r in results]
        self.assertIn(ordre.id, ids)
