"""Tests ZCTR5 — Bons d'enlèvement et de restitution de location (PDF).

Couvre :
- Les deux PDF (enlèvement/restitution) se génèrent avec les bonnes données
  pour un ordre donné (contenu texte extrait, pas de crash WeasyPrint).
- Le bon de restitution reprend l'inspection et les dommages chiffrés
  (XCTR19).
- Aucune fuite de ``prix_achat`` dans le contexte de rendu.
- Aucun statut modifié par le rendu (les deux endpoints sont des GET).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import OrdreLocation
from apps.contrats.pdf_location import (
    generate_bon_enlevement_pdf,
    generate_bon_restitution_pdf,
)
from apps.crm.models import Client
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Groupe électrogène', **kwargs):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('100'),
        # Sentinelle DISTINCTIVE (jamais un petit nombre comme 42 qui entre en
        # collision avec un id/pk auto-incrémenté dans un repr d'objet du
        # contexte selon l'état de la base de test) : ne doit JAMAIS fuiter.
        prix_achat=Decimal('987654'),
        louable=True, tarif_location_jour=kwargs.pop(
            'tarif_location_jour', Decimal('500')),
        **kwargs)


def make_ordre(company, produit, client_id, **overrides):
    defaults = dict(
        date_reservation=date(2026, 7, 1),
        date_enlevement_prevue=date(2026, 7, 2),
        date_retour_prevue=date(2026, 7, 6),
    )
    defaults.update(overrides)
    return services.creer_ordre_location(
        company, client_id=client_id, produit=produit,
        numero_serie='SN-ZCTR5', **defaults)


class BonEnlevementPdfTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr5-enl', 'Zctr5Enl')
        self.produit = make_produit(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Dupont', prenom='Jean',
            telephone='+212600000020')

    def test_bon_enlevement_contient_les_bonnes_donnees(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        ordre.caution_montant = Decimal('2000')
        ordre.save(update_fields=['caution_montant'])
        pdf_bytes = generate_bon_enlevement_pdf(ordre)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 500)

    def test_bon_enlevement_ne_modifie_aucun_statut(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        generate_bon_enlevement_pdf(ordre)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreLocation.Statut.RESERVEE)

    def test_bon_enlevement_pas_de_fuite_prix_achat(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        from apps.contrats.pdf_location import _base_context

        context = _base_context(ordre)
        rendu_str = str(context)
        # La valeur d'achat distinctive n'apparaît nulle part (RULE #4) ; pas de
        # `.replace(id)` fragile — la sentinelle ne peut pas collisionner un pk.
        self.assertNotIn('987654', rendu_str)
        self.assertNotIn('prix_achat', rendu_str)


class BonRestitutionPdfTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr5-rest', 'Zctr5Rest')
        self.produit = make_produit(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Martin', prenom='Alice',
            telephone='+212600000021')

    def test_bon_restitution_reprend_inspection_et_dommages(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        ordre.date_retour_reelle = date(2026, 7, 7)
        ordre.inspection_checklist = {
            'carrosserie': 'ok', 'moteur': 'endommage'}
        ordre.inspection_releve_compteur = '1234 h'
        ordre.inspection_dommages_montant = Decimal('850')
        ordre.save(update_fields=[
            'date_retour_reelle', 'inspection_checklist',
            'inspection_releve_compteur', 'inspection_dommages_montant'])

        pdf_bytes = generate_bon_restitution_pdf(ordre)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 500)

    def test_bon_restitution_sans_dommage_toujours_genere(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        pdf_bytes = generate_bon_restitution_pdf(ordre)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_bon_restitution_ne_modifie_aucun_statut(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        generate_bon_restitution_pdf(ordre)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreLocation.Statut.RESERVEE)


class BonsLocationApiTests(TestCase):
    def setUp(self):
        self.company = make_company('zctr5-api', 'Zctr5Api')
        self.user = make_user(self.company, 'zctr5-api-resp')
        self.produit = make_produit(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Api',
            telephone='+212600000022')

    def test_endpoint_bon_enlevement(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        api = auth(self.user)
        res = api.get(
            f'/api/django/contrats/ordres-location/{ordre.id}/'
            'bon-enlevement/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_endpoint_bon_restitution(self):
        ordre = make_ordre(self.company, self.produit, self.client_obj.id)
        api = auth(self.user)
        res = api.get(
            f'/api/django/contrats/ordres-location/{ordre.id}/'
            'bon-restitution/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
