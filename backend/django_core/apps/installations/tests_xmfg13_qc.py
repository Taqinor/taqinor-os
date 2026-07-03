"""
XMFG13 — Contrôle qualité de fin d'assemblage (gate avant clôture).

Couvre :
  * kit SANS modèle QC → `terminer` inchangé (comportement actuel) ;
  * kit AVEC modèle QC actif → `terminer` bloqué tant que la checklist n'est
    pas entièrement passée ;
  * un item en échec ouvre une `qhse.NonConformite` liée à l'ordre ;
  * `forcer=true` + motif (responsable/admin) débloque la clôture.

Run :
    python manage.py test apps.installations.tests_xmfg13_qc -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, ControleQualiteModele,
    ControleQualiteItemModele,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg13-co-{n}', defaults={'nom': nom or f'XMFG13 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg13-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestControleQualite(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=1)

    def test_kit_sans_modele_terminer_inchange(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC1', kit=self.kit, quantite=1)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.TERMINE)

    def test_kit_avec_modele_bloque_cloture_tant_que_incomplet(self):
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Test tension 220V', ordre=1)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC2', kit=self.kit, quantite=1)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.PLANIFIE)

    def test_checklist_passee_debloque_cloture(self):
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        item = ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Test tension 220V', ordre=1)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC3', kit=self.kit, quantite=1)
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/')
        resp_item = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/{item.id}/',
            {'resultat': 'pass'}, format='json')
        self.assertEqual(resp_item.status_code, 200, resp_item.content)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_item_en_echec_ouvre_ncr(self):
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        item = ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Test isolement', ordre=1)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC4', kit=self.kit, quantite=1)
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/')
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/{item.id}/',
            {'resultat': 'fail'}, format='json')
        from apps.qhse.models import NonConformite
        ncr = NonConformite.objects.filter(
            company=self.company, ordre_assemblage=ordre).first()
        self.assertIsNotNone(ncr)
        self.assertEqual(ncr.statut, NonConformite.Statut.OUVERTE)

    def test_forcer_avec_motif_debloque_cloture(self):
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Test tension 220V', ordre=1)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC5', kit=self.kit, quantite=1)

        resp_no_motif = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'forcer': 'true'}, format='json')
        self.assertEqual(resp_no_motif.status_code, 400, resp_no_motif.content)

        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/', {
                'forcer': 'true', 'motif_forcage': 'Urgence client',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreAssemblage.Statut.TERMINE)

    def test_tolerance_deduit_pass_fail_automatique(self):
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        item = ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Tension mesurée', ordre=1,
            valeur_min=210, valeur_max=230, unite='V')
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-QC6', kit=self.kit, quantite=1)
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/')
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/controle-qualite/{item.id}/',
            {'valeur_mesuree': '250'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['resultat'], 'fail')
