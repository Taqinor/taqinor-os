"""
XMFG15 — Analyse d'écarts par ordre + tableau de bord atelier (INTERNE).

Couvre :
  * l'analyse par ordre est juste sur un cas testé (coût prévu != coût réel,
    temps prévu != temps réel) ;
  * le panneau atelier agrège et filtre par période (en_retard/en_cours/
    termines, taux de rebut, écart moyen) ;
  * permissions : responsable/admin uniquement (coûts d'achat).

Run :
    python manage.py test apps.installations.tests_xmfg15_analyse -v2
"""
import itertools
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, EtapeAssemblage,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg15-co-{n}', defaults={'nom': nom or f'XMFG15 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg15-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100, prix_achat=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=prix_achat,
        quantite_stock=stock)


class TestAnalyseEcartsOrdre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=50, prix_achat=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)

    def test_analyse_ecart_cout_et_temps(self):
        EtapeAssemblage.objects.create(
            kit=self.kit, ordre=1, libelle='Câblage', duree_attendue_min=10)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A1', kit=self.kit, quantite=3)
        # instancie étapes puis coche avec un temps réel différent du prévu.
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/etapes/')
        etape = ordre.etapes.first()
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/etapes/'
            f'{etape.etape_modele_id}/cocher/',
            {'fait': 'true', 'duree_reelle_min': 25}, format='json')
        # clôture : consomme 2×3=6 unités à 100 MAD prévu ; le backflush réel
        # utilise les lignes copiées (identiques ici, pas de bris volontaire).
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': 3}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/analyse/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data
        # coût prévu = 2 (qté/kit) × 3 (kits) × 100 = 600 ; réel identique ici
        # (aucun rebut déclaré) → écart 0.
        self.assertAlmostEqual(data['cout']['prevu'], 600.0)
        self.assertAlmostEqual(data['cout']['reel'], 600.0)
        self.assertAlmostEqual(data['cout']['ecart'], 0.0)
        self.assertEqual(data['temps']['prevu'], 10)
        self.assertEqual(data['temps']['reel'], 25)
        self.assertEqual(data['temps']['ecart'], 15)

    def test_analyse_avec_rebut_gonfle_cout_reel(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A2', kit=self.kit, quantite=1)
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': 1}, format='json')
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/declarer-rebut/',
            {'produit': self.comp1.id, 'quantite': 1, 'motif': 'casse'},
            format='json')
        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/analyse/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data
        # prévu = 2×100 = 200 ; réel = sortie 200 + rebut 100 = 300.
        self.assertAlmostEqual(data['cout']['prevu'], 200.0)
        self.assertAlmostEqual(data['cout']['reel'], 300.0)
        self.assertAlmostEqual(data['cout']['ecart'], 100.0)
        self.assertEqual(data['rebut']['quantite'], 1)
        self.assertAlmostEqual(data['rebut']['cout'], 100.0)

    def test_permission_refusee_role_limite(self):
        limited = make_user(self.company, role='technicien')
        api = auth(limited)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-A3', kit=self.kit, quantite=1)
        resp = api.get(f'{BASE}/ordres-assemblage/{ordre.id}/analyse/')
        self.assertEqual(resp.status_code, 403)


class TestPanneauAtelier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=50, prix_achat=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=1)

    def test_panneau_agrege_en_retard_en_cours_termines(self):
        hier = date.today() - timedelta(days=1)
        en_retard = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-B1', kit=self.kit,
            quantite=1, date_prevue=hier)
        en_cours = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-B2', kit=self.kit,
            quantite=1, statut=OrdreAssemblage.Statut.EN_COURS)
        termine = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-B3', kit=self.kit, quantite=1)
        self.api.post(
            f'{BASE}/ordres-assemblage/{termine.id}/terminer/',
            {'quantite_produite': 1}, format='json')

        resp = self.api.get(f'{BASE}/ordres-assemblage/atelier/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data
        self.assertEqual(data['totaux']['nb_en_retard'], 1)
        self.assertEqual(data['totaux']['nb_en_cours'], 1)
        self.assertEqual(data['totaux']['nb_termines'], 1)
        ids_en_retard = {o['id'] for o in data['en_retard']}
        self.assertIn(en_retard.id, ids_en_retard)
        ids_en_cours = {o['id'] for o in data['en_cours']}
        self.assertIn(en_cours.id, ids_en_cours)

    def test_panneau_filtre_periode_termines(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-B4', kit=self.kit, quantite=1)
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': 1}, format='json')

        futur_debut = (timezone.now() + timedelta(days=1)).date()
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/atelier/'
            f'?date_debut={futur_debut.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['totaux']['nb_termines'], 0)

    def test_permission_refusee_role_limite(self):
        limited = make_user(self.company, role='technicien')
        api = auth(limited)
        resp = api.get(f'{BASE}/ordres-assemblage/atelier/')
        self.assertEqual(resp.status_code, 403)
