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
