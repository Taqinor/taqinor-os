"""Fixtures partagées des tests NTMAR (einvoice) — pas un fichier de tests."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def seller_profile(company, **extra):
    prof = CompanyProfile.get(company=company)
    prof.nom = extra.get('nom', 'Vendeur SARL')
    prof.ice = extra.get('ice', 'ICE-EINV-001')
    prof.identifiant_fiscal = extra.get('identifiant_fiscal', 'IF-EINV-1')
    prof.rc = extra.get('rc', 'RC-EINV-1')
    prof.save()
    return prof


def make_facture(company, *, reference=None, ice_client='ICE-CLIENT-EINV'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='EINV',
        email='einv@client.ma', telephone='+212600009001',
        adresse='Casa', type_client='entreprise', ice=ice_client)
    produit = Produit.objects.create(
        company=company, nom='Panneau', sku=f'EINV-{reference or "X"}',
        prix_vente=Decimal('1000'), prix_achat=Decimal('700'),
        quantite_stock=50, tva=Decimal('20.00'))
    facture = Facture.objects.create(
        company=company, reference=reference or f'FAC-{MONTH}-EINV1',
        client=client, statut=Facture.Statut.EMISE,
        taux_tva=Decimal('20.00'),
        conditions_paiement='Virement à 30 jours')
    LigneFacture.objects.create(
        facture=facture, produit=produit, designation='Panneau PV 550W',
        quantite=Decimal('4'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'))
    return facture
