"""Lectures publiques du répertoire ``Tiers`` (ARC17).

Point d'entrée READ que les autres apps consommeront (ARC18/19) sans importer
``tiers.models`` : ``tiers`` reste une couche fondation, les domaines
dépendent d'elle, jamais l'inverse.
"""
from .models import Tiers


def tiers_base_qs():
    """Queryset de base (non filtré société) sur les tiers.

    L'appelant DOIT le scoper par société (``.filter(company=…)``) — le
    ``TenantMixin`` du viewset le fait pour l'API.
    """
    return Tiers.objects.all()


def tiers_for_company(company):
    """Tiers d'une société donnée."""
    return Tiers.objects.filter(company=company)


def clients(company):
    """Tiers d'une société marqués comme clients."""
    return tiers_for_company(company).filter(is_client=True)


def fournisseurs(company):
    """Tiers d'une société marqués comme fournisseurs."""
    return tiers_for_company(company).filter(is_fournisseur=True)


def get_tiers(company, tiers_id):
    """Récupère un tiers scopé société, ou ``None``."""
    return tiers_for_company(company).filter(pk=tiers_id).first()


# ── ARC20 — Recoupement « qui est ce tiers ? » (lecture seule) ──────────────

def _norm(value):
    """Clé de rapprochement épurée (minuscules, sans espaces de bord). Vide si
    la valeur ne porte rien de significatif."""
    return str(value or '').strip().lower()


def find_by_ice(company, ice):
    """Tiers d'une société portant cet ICE (insensible à la casse/espaces).

    Company-scopé : jamais de fuite inter-société. Renvoie un queryset (0..n)
    — plusieurs lignes signalent une duplication inter-référentielle (rapport
    ARC20). Vide si l'ICE fourni est vide."""
    ice_n = _norm(ice)
    if not ice_n:
        return Tiers.objects.none()
    return tiers_for_company(company).filter(ice__iexact=ice_n)


def find_by_email(company, email):
    """Tiers d'une société portant cet email (insensible à la casse).

    Company-scopé. Renvoie un queryset (0..n). Vide si l'email est vide."""
    email_n = _norm(email)
    if not email_n:
        return Tiers.objects.none()
    return tiers_for_company(company).filter(email__iexact=email_n)


def find_duplicates(company):
    """ARC20 — Rapport LECTURE SEULE des doublons inter-référentiels d'une
    société : le MÊME ICE ou le MÊME email porté par PLUSIEURS fiches ``Tiers``
    (ex. un acteur enregistré à la fois comme Fournisseur et comme Partenaire —
    le scout masterdata constate zéro linkage aujourd'hui).

    N'effectue AUCUNE fusion, AUCUNE écriture : renvoie une liste de clusters,
    chacun ::

        {
          'cle': 'ice' | 'email',
          'valeur': '<valeur normalisée>',
          'tiers': [ {id, nom, roles: {...}}, ... ],  # ≥ 2 membres
        }

    Strictement company-scopé (deux sociétés partageant un même ICE/email ne
    forment JAMAIS un cluster commun). Les valeurs vides sont ignorées.
    """
    clusters = []
    qs = tiers_for_company(company).only(
        'id', 'nom', 'prenom', 'raison_sociale', 'ice', 'email',
        'is_client', 'is_fournisseur', 'is_partenaire', 'is_soustraitant')
    rows = list(qs)

    for cle, getter in (('ice', lambda t: _norm(t.ice)),
                        ('email', lambda t: _norm(t.email))):
        buckets = {}
        for t in rows:
            val = getter(t)
            if not val:
                continue
            buckets.setdefault(val, []).append(t)
        for val, membres in buckets.items():
            if len(membres) < 2:
                continue
            clusters.append({
                'cle': cle,
                'valeur': val,
                'tiers': [
                    {
                        'id': t.id,
                        'nom': t.nom_complet,
                        'roles': {
                            'client': t.is_client,
                            'fournisseur': t.is_fournisseur,
                            'partenaire': t.is_partenaire,
                            'soustraitant': t.is_soustraitant,
                        },
                    }
                    for t in membres
                ],
            })
    # Tri stable : d'abord par clé (ice avant email), puis par valeur.
    clusters.sort(key=lambda c: (c['cle'], c['valeur']))
    return clusters
