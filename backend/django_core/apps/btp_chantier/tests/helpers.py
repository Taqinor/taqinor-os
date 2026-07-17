"""Aides de test partagées du vertical BTP/EPC (Groupe NTCON)."""
import itertools

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntcon-co-{n}', defaults={'nom': nom or f'NTCON Co {n}'})
    return company


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'ntcon-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, **kwargs):
    from apps.installations.models import Installation
    n = next(_seq)
    kwargs.setdefault('reference', f'CH-{company.id}-{n}')
    return Installation.objects.create(company=company, **kwargs)


def attach(company, user, instance, phase, name='photo.png'):
    """Crée un ``records.Attachment`` ciblant ``instance`` (générique)."""
    from apps.records.models import Attachment
    ct = ContentType.objects.get_for_model(instance.__class__)
    return Attachment.objects.create(
        company=company, content_type=ct, object_id=instance.id,
        uploaded_by=user, phase=phase,
        file_key=f'attachments/{name}', filename=name,
        size=1, mime='image/png')


def make_client_crm(company, **kwargs):
    """Crée un ``crm.Client`` (NTCON7/8/9/11 — factures d'acompte)."""
    from apps.crm.models import Client
    n = next(_seq)
    kwargs.setdefault('nom', f'Client {n}')
    return Client.objects.create(company=company, **kwargs)


def make_projet_lie(company, chantier, **kwargs):
    """Crée un ``gestion_projet.Projet`` + rattachement ``ProjetChantier``
    (référence lâche) au ``chantier`` — NTCON9/NTCON11."""
    from apps.gestion_projet.models import Projet, ProjetChantier
    n = next(_seq)
    kwargs.setdefault('code', f'PRJ-{n}')
    kwargs.setdefault('nom', f'Projet {n}')
    projet = Projet.objects.create(company=company, **kwargs)
    ProjetChantier.objects.create(
        company=company, projet=projet, chantier_id=chantier.pk)
    return projet


def make_ressource_profil(company, **kwargs):
    from apps.gestion_projet.models import RessourceProfil
    n = next(_seq)
    kwargs.setdefault('nom', f'Ressource {n}')
    return RessourceProfil.objects.create(company=company, **kwargs)


def make_timesheet(company, projet, ressource, **kwargs):
    from apps.gestion_projet.models import Timesheet
    kwargs.setdefault('date', '2026-07-01')
    kwargs.setdefault('heures', 8)
    kwargs.setdefault('cout', 0)
    kwargs.setdefault('facturable', True)
    kwargs.setdefault('statut', Timesheet.Statut.APPROUVEE)
    return Timesheet.objects.create(
        company=company, projet=projet, ressource=ressource, **kwargs)


def make_situation(company, projet, numero=1, **kwargs):
    from apps.gestion_projet.models import SituationTravaux
    kwargs.setdefault('periode', '2026-07-01')
    kwargs.setdefault('statut', SituationTravaux.Statut.FACTUREE)
    return SituationTravaux.objects.create(
        company=company, projet=projet, numero=numero, **kwargs)


def make_ligne_situation(company, situation, **kwargs):
    from apps.gestion_projet.models import LigneSituation
    n = next(_seq)
    kwargs.setdefault('libelle', f'Ligne {n}')
    kwargs.setdefault('montant_periode', 0)
    return LigneSituation.objects.create(
        company=company, situation=situation, **kwargs)


def make_fournisseur(company, **kwargs):
    from apps.stock.models import Fournisseur
    n = next(_seq)
    kwargs.setdefault('nom', f'Sous-traitant {n}')
    return Fournisseur.objects.create(company=company, **kwargs)


def make_ordre_sous_traitance(company, chantier, sous_traitant, **kwargs):
    from apps.installations.models_ordre_soustraitance import OrdreSousTraitance
    n = next(_seq)
    kwargs.setdefault('reference', f'OST-{company.id}-{n}')
    kwargs.setdefault('prestation', 'Prestation de test')
    kwargs.setdefault('montant', 0)
    return OrdreSousTraitance.objects.create(
        company=company, chantier=chantier, sous_traitant=sous_traitant,
        **kwargs)


def make_produit(company, prix_achat=0, prix_vente=0, **kwargs):
    from apps.stock.models import Produit
    n = next(_seq)
    kwargs.setdefault('nom', f'Produit {n}')
    return Produit.objects.create(
        company=company, prix_achat=prix_achat, prix_vente=prix_vente,
        **kwargs)


def make_reservation_stock(company, chantier, produit, quantite=1, **kwargs):
    from apps.installations.models_chantier import StockReservation
    return StockReservation.objects.create(
        company=company, installation=chantier, produit=produit,
        quantite=quantite, **kwargs)
