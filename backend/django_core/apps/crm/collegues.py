"""Collègues à qui confier du travail (19/11/2026) — UNE définition de la liste.

Le sélecteur de responsable des écrans (``views.assignable_users``) et la
recherche de l'assistant (``views_assistant.collegues_assistant``) lisent la
MÊME liste : comptes actifs de la société de l'appelant. L'assistant ne voit
donc jamais un compte que l'écran ne propose pas.

Incident du 19/11/2026 : l'assistant demandait au fondateur « l'identifiant
utilisateur » d'une collègue. Une personne se désigne par son NOM ; cette
recherche rend l'identifiant à partir du nom, sans accent ni casse, et les noms
les plus proches quand rien ne correspond (« Meriem » pour « Meryem »).
"""
import difflib
import unicodedata

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

#: Ratio minimal (``difflib``) pour citer un nom « proche » d'une recherche
#: sans résultat ; trois noms au plus.
RATIO_PROCHE = 0.6
PROCHES_MAX = 3


def collegues_assignables(user):
    """Comptes ACTIFS de la société de ``user``. Sans société : aucun compte,
    sauf pour un superutilisateur (tous les comptes actifs)."""
    from authentication.models import CustomUser

    qs = CustomUser.objects.filter(is_active=True)
    if user.company_id:
        return qs.filter(company=user.company)
    if not user.is_superuser:
        return qs.none()
    return qs


def _sans_accent(texte):
    """Minuscules, sans accent, espaces repliés : « Méryem  ALAOUI » →
    « meryem alaoui »."""
    decompose = unicodedata.normalize('NFKD', texte or '')
    nu = ''.join(c for c in decompose if not unicodedata.combining(c))
    return ' '.join(nu.casefold().split())


def _ligne(compte):
    prenom = (compte.first_name or '').strip()
    famille = (compte.last_name or '').strip()
    return {
        'id': compte.pk,
        'nom': ' '.join(p for p in (prenom, famille) if p) or compte.username,
        'prenom': prenom,
        'nom_de_famille': famille,
        'identifiant': compte.username,
        'poste': compte.poste or '',
        'role': compte.role.nom if compte.role_id else '',
        'actif': bool(compte.is_active),
    }


def _mots(compte):
    parties = (compte.first_name or '', compte.last_name or '', compte.username or '')
    return _sans_accent(' '.join(parties)).split()


def _proximite(terme, compte):
    """Meilleur ratio entre le terme et un mot (ou le nom complet) du compte."""
    mots = _mots(compte)
    candidats = mots + [' '.join(mots)]
    return max((difflib.SequenceMatcher(None, terme, m).ratio()
                for m in candidats), default=0.0)


def chercher_collegues(user, q='', limite=20):
    """``(total, lignes, proches)`` — les collègues de :func:`collegues_assignables`
    dont prénom, nom ou identifiant contiennent chaque mot de ``q`` (sans
    accent ni casse) ; ``q`` vide = tous. Sans résultat, ``proches`` cite au
    plus :data:`PROCHES_MAX` collègues au nom voisin, sinon ``[]``."""
    comptes = list(collegues_assignables(user).select_related('role')
                   .order_by('username'))
    termes = _sans_accent(q).split()
    trouves = [c for c in comptes
               if all(t in ' '.join(_mots(c)) for t in termes)]
    proches = []
    if termes and not trouves:
        terme = ' '.join(termes)
        notes = sorted(((_proximite(terme, c), c.username, c) for c in comptes),
                       key=lambda n: (-n[0], n[1]))
        proches = [_ligne(c) for ratio, _nom, c in notes[:PROCHES_MAX]
                   if ratio >= RATIO_PROCHE]
    return len(trouves), [_ligne(c) for c in trouves[:limite]], proches


PARAMETRES_MENU = [OpenApiParameter(
    'permission', OpenApiTypes.STR, OpenApiParameter.QUERY, required=False,
    description="Code d'une permission ERP : ne propose que les comptes qui la portent "
                "(ex. calepinage_voir pour le responsable d'un calepinage)."), OpenApiParameter(
    'lead', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False,
    description="Lead du calepinage qu'on confie (avec permission=calepinage_voir) : un compte qui ne lit que "
                "par sa visite n'est proposé que s'il a une visite sur ce lead. Un identifiant inconnu ou d'une "
                "autre société est ignoré, comme l'absence de lead.")]


def lead_du_menu(user, brut):
    """T4-X3-016 — l'identifiant du lead de ``?lead=`` s'il est entier ET de la société de ``user`` ;
    sinon ``None`` (ignoré, exactement comme « pas de lead » : rien ne dit qu'il existe ailleurs)."""
    from .models import Lead

    if not str(brut or '').isdigit():
        return None
    ok = Lead.objects.filter(pk=int(brut), company_id=getattr(user, 'company_id', None)).exists()
    return int(brut) if ok else None


def filtrer_par_permission(collegues, permission, lead=None, user=None):
    """T4-X3-016 — les collègues qui PORTENT ``permission`` (un code du registre des permissions) :
    même prédicat que le serveur du module (``ScopedPermission`` → ``_user_has_or_legacy``), pour
    qu'un sélecteur ne propose que des comptes qui peuvent ouvrir ce qu'on leur confie. Sans code :
    la liste telle quelle. Code inconnu : refus 400 nommé (``ValidationError``).
    ``lead`` (brut, ``?lead=``, lu pour ``user`` par ``lead_du_menu``) : le lead du calepinage qu'on confie
    — un compte qui ne lit que par sa visite n'est proposé que s'il a une visite sur ce lead. Vit ici, pas
    dans ``views.py`` (plus de 2 000 lignes, qui ne grossit pas)."""
    permission = (permission or '').strip()
    if not permission:
        return collegues
    from rest_framework.exceptions import ValidationError

    from apps.roles.permissions_registre import ALL_PERMISSIONS
    from core.permissions import _user_has_or_legacy

    if permission not in ALL_PERMISSIONS:
        raise ValidationError({'permission': 'Permission inconnue.'})
    porteurs = [u for u in collegues.select_related('role') if _user_has_or_legacy(u, permission)]
    if permission == 'calepinage_voir':
        lead_id = lead_du_menu(user, lead)
        # Porter le code ne suffit pas : un compte qui ne lit que par le relevé n'ouvre un calepinage
        # que par SA visite (D-ACAL-106/126) — le menu ne propose que qui l'ouvrira (la règle vit au module).
        from apps.calepinage.selectors import peut_ouvrir_une_fois_responsable

        porteurs = [u for u in porteurs if peut_ouvrir_une_fois_responsable(u, lead_id)]
    return porteurs
