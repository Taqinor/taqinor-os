"""YSTCK4 — Retour chantier : matériel non posé rapporté au dépôt.

`consume_reservations`/`validate_consommation` sortent le stock au chantier
mais rien ne permettait de faire remonter le surplus non installé. Ces tests
couvrent :

  * rapporter 3 unités d'un chantier crée un MouvementStock ENTREE tracé au
    chantier (référence `RETOUR-<reference>`) et ré-augmente le stock ;
  * le coût réel consommé (F11) diminue en conséquence ;
  * un retour supérieur à la quantité réellement sortie est refusé ;
  * l'idempotence (ré-valider un retour déjà validé échoue proprement) ;
  * isolation tenant sur le endpoint.

Run :
    python manage.py test apps.installations.tests_ystck4_retour_materiel -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import (
    Installation, Intervention, MaterielConsommation, ConsommationLigne,
    RetourMateriel, RetourMaterielLigne,
)
from apps.installations.services import (
    valider_retour_materiel, quantite_retournable,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ystck4-co-{n}', defaults={'nom': f'YSTCK4 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ystck4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company, statut=Installation.Statut.INSTALLE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='YSTCK4',
        email=f'ystck4-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-YSTCK4-{n}', client=client,
        statut=statut)


def make_produit(company, quantite_stock=Decimal('0')):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Câble solaire {n}',
        prix_vente=Decimal('10'), quantite_stock=quantite_stock)


def make_consommation_validee(company, installation, produit, quantite_utilisee):
    """Simule une réconciliation F11 VALIDÉE ayant réellement sorti le stock
    (stock_applique=True) — la seule source qui alimente le retournable."""
    interv = Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE)
    cons = MaterielConsommation.objects.create(
        company=company, intervention=interv, valide=True)
    ConsommationLigne.objects.create(
        company=company, consommation=cons, produit=produit,
        designation=produit.nom, quantite_prevue=quantite_utilisee,
        quantite_utilisee=quantite_utilisee, stock_applique=True)
    return interv, cons


class TestRetourMaterielService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.inst = make_installation(self.company)
        self.produit = make_produit(self.company, quantite_stock=Decimal('0'))
        make_consommation_validee(self.company, self.inst, self.produit,
                                  Decimal('10'))

    def test_retour_valide_cree_mouvement_entree_et_augmente_stock(self):
        retour = RetourMateriel.objects.create(
            company=self.company, installation=self.inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('3'))

        applied = valider_retour_materiel(retour, self.user)
        self.assertEqual(applied, 1)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('3'))

        from apps.stock.models import MouvementStock
        mvt = MouvementStock.objects.get(
            produit=self.produit, reference=f'RETOUR-{self.inst.reference}')
        self.assertEqual(mvt.type_mouvement, MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(mvt.quantite, Decimal('3'))

        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourMateriel.Statut.VALIDE)

    def test_retour_superieur_a_sorti_est_refuse(self):
        retour = RetourMateriel.objects.create(
            company=self.company, installation=self.inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('11'))

        with self.assertRaises(ValueError):
            valider_retour_materiel(retour, self.user)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('0'))
        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourMateriel.Statut.BROUILLON)

    def test_retournable_diminue_apres_un_premier_retour_valide(self):
        retour1 = RetourMateriel.objects.create(
            company=self.company, installation=self.inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour1, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('6'))
        valider_retour_materiel(retour1, self.user)

        self.assertEqual(
            quantite_retournable(self.inst, self.produit.id), Decimal('4'))

        retour2 = RetourMateriel.objects.create(
            company=self.company, installation=self.inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour2, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('5'))
        with self.assertRaises(ValueError):
            valider_retour_materiel(retour2, self.user)

    def test_revalider_retour_deja_valide_echoue(self):
        retour = RetourMateriel.objects.create(
            company=self.company, installation=self.inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('2'))
        valider_retour_materiel(retour, self.user)
        with self.assertRaises(ValueError):
            valider_retour_materiel(retour, self.user)


class TestRetourMaterielEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.produit = make_produit(self.company)
        make_consommation_validee(self.company, self.inst, self.produit,
                                  Decimal('5'))

    def test_creer_et_valider_via_api(self):
        r = self.api.post(
            f'{BASE}/retours-materiel/',
            {'installation': self.inst.id, 'note': 'Câble non utilisé'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        retour_id = r.data['id']

        r2 = self.api.post(
            f'{BASE}/retour-materiel-lignes/',
            {'retour': retour_id, 'produit': self.produit.id,
             'quantite': '3'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)

        r3 = self.api.post(f'{BASE}/retours-materiel/{retour_id}/valider/')
        self.assertEqual(r3.status_code, 200, r3.data)
        self.assertEqual(r3.data['statut'], 'valide')

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('3'))

    def test_cross_company_installation_refusee(self):
        other_inst = make_installation(self.other_company)
        r = self.api.post(
            f'{BASE}/retours-materiel/',
            {'installation': other_inst.id}, format='json')
        self.assertEqual(r.status_code, 400)
