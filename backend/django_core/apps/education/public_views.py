"""Endpoints PUBLICS (sans login) du portail parents — NTEDU31/32/34.

Le parent s'identifie par le ``token_acces`` de son ``CompteParent``
(NTEDU31, MÊME PATRON que ``apps.portail.ComptePortailClient``/FG228,
résolu ICI par un sélecteur LECTURE SEULE puisque ``CompteParent`` vit dans
CETTE MÊME app — pas de frontière cross-app). Le parent ne voit JAMAIS que
les élèves de SA PROPRE famille (filtrage serveur strict par
``compte.famille_id`` — testé, jamais un id de famille lu depuis l'URL/le
corps de requête).

Données JAMAIS exposées ici : ``Produit.prix_achat`` ou toute donnée
d'achat/marge interne (règle #4 étendue par analogie, NTEDU32) — ce module
ne lit d'ailleurs jamais le catalogue produit, seulement l'échéancier de
scolarité (``LigneEcheance`` : libellé/montant/date/statut, aucun champ de
coût interne).

Protections : X-Robots-Tag noindex sur chaque réponse ; throttle
cache-based par IP (30 req/min), même patron que
``apps.contrats.public_views``.
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle


class EducationPortailThrottle(SimpleRateThrottle):
    """Limite le débit du portail parents par IP (cache-based, sans dépendance)."""
    scope = 'education_portail'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def _noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien de portail est invalide ou n'existe pas."},
        status=status.HTTP_404_NOT_FOUND,
    ))


def _resoudre_compte(token):
    """Résout le ``CompteParent`` ACTIF par token (même app, pas de
    frontière cross-app). Met à jour ``derniere_connexion`` au passage
    (best-effort — un échec d'écriture n'empêche jamais la lecture)."""
    from .models import CompteParent

    compte = CompteParent.objects.filter(
        token_acces=token, actif=True).select_related('famille').first()
    if compte is None:
        return None
    try:
        from django.utils import timezone
        compte.derniere_connexion = timezone.now()
        compte.save(update_fields=['derniere_connexion'])
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        pass
    return compte


def _serialize_eleve(eleve):
    return {
        'id': eleve.id,
        'nom': eleve.nom,
        'prenom': eleve.prenom,
        'classe': str(eleve.classe) if eleve.classe_id else None,
        'statut': eleve.statut,
        'statut_display': eleve.get_statut_display(),
        'numero_dossier': eleve.numero_dossier,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([EducationPortailThrottle])
def portail_mes_eleves(request, token):
    """NTEDU31 — liste des élèves de la famille du compte portail (lecture
    seule). GET /api/django/public/education/portail/<token>/eleves/

    Filtrage STRICT par ``compte.famille_id`` : un compte parent ne peut
    JAMAIS lister les élèves d'une autre famille, même en connaissant leurs
    id (le queryset ne les contient simplement pas)."""
    compte = _resoudre_compte(token)
    if compte is None:
        return _not_found()

    eleves = compte.famille.eleves.select_related('classe').order_by(
        'nom', 'prenom')
    return _noindex(Response({
        'famille': compte.famille.nom,
        'count': eleves.count(),
        'results': [_serialize_eleve(e) for e in eleves],
    }))


def _serialize_ligne(ligne):
    return {
        'id': ligne.id,
        'libelle': ligne.libelle,
        'montant': str(ligne.montant),
        'date_echeance': ligne.date_echeance.isoformat(),
        'statut': ligne.statut,
        'statut_display': ligne.get_statut_display(),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([EducationPortailThrottle])
def portail_echeancier(request, token):
    """NTEDU32 — échéancier de scolarité (lecture seule) de chaque enfant de
    la famille. GET /api/django/public/education/portail/<token>/echeancier/

    Le paiement en ligne reste hors périmètre ici (aligné QJ24, non
    redupliqué) : le bouton « Payer » reste un lien MANUEL
    (virement/espèces à l'école) — ``paiement_en_ligne_disponible`` est
    TOUJOURS ``False`` tant qu'aucune passerelle gated n'est branchée.
    AUCUN champ de coût/marge interne (``Produit.prix_achat`` ou
    équivalent) n'est ni lu ni exposé par cette vue."""
    compte = _resoudre_compte(token)
    if compte is None:
        return _not_found()

    from .models import EcheancierScolarite

    echeanciers = (EcheancierScolarite.objects
                   .filter(eleve__famille=compte.famille)
                   .select_related('eleve').prefetch_related('lignes')
                   .order_by('-id'))
    results = []
    for ech in echeanciers:
        results.append({
            'id': ech.id,
            'eleve': f'{ech.eleve.prenom} {ech.eleve.nom}',
            'montant_total': str(ech.montant_total),
            'nombre_echeances': ech.nombre_echeances,
            'lignes': [_serialize_ligne(ligne) for ligne in ech.lignes.all()],
        })
    return _noindex(Response({
        'count': len(results),
        'results': results,
        'paiement_en_ligne_disponible': False,
        'moyens_paiement_manuel': (
            'Virement bancaire ou espèces auprès du secrétariat.'),
    }))


def _serialize_liste_attente(inscription):
    return {
        'id': inscription.id,
        'eleve': (
            f'{inscription.eleve.prenom} {inscription.eleve.nom}'),
        'classe_demandee': (
            str(inscription.classe_demandee)
            if inscription.classe_demandee_id else None),
        'position': inscription.position_liste_attente,
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([EducationPortailThrottle])
def portail_liste_attente(request, token):
    """NTEDU34 — position en liste d'attente de chaque enfant de la
    famille. GET /api/django/public/education/portail/<token>/liste-attente/

    La position renvoyée est TOUJOURS celle stockée sur ``Inscription.
    position_liste_attente``, recalculée côté serveur à CHAQUE variation
    (``services.recalculer_liste_attente`` — jamais une valeur figée à la
    création) : jamais de second calcul ici qui pourrait diverger."""
    compte = _resoudre_compte(token)
    if compte is None:
        return _not_found()

    from .models import Inscription

    qs = (Inscription.objects
          .filter(eleve__famille=compte.famille,
                  statut=Inscription.Statut.LISTE_ATTENTE)
          .select_related('eleve', 'classe_demandee')
          .order_by('position_liste_attente', 'date_demande', 'id'))
    return _noindex(Response({
        'count': qs.count(),
        'results': [_serialize_liste_attente(i) for i in qs],
    }))
