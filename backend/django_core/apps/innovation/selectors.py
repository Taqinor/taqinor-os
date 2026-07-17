"""Sélecteurs (lecture seule) du module ``apps.innovation``.

Fonctions utilitaires que d'autres apps peuvent importer **via import local**
(dans le corps d'une fonction, jamais au niveau module) pour éviter les
dépendances cycliques et respecter les contrats d'import CI-enforced.
"""


def idees_par_statut(company):
    """NTIDE6 — nombre d'idées par statut (KPI cards du tableau de bord)."""
    from django.db.models import Count, Q

    from .models import Idee

    S = Idee.Statut
    # NTIDE18 — une idée en brouillon reste interne à son auteur : jamais
    # comptée dans les agrégats admin (mêmes chiffres qu'avant qu'elle soit
    # publiée). NTIDE19 — une idée masquée (modération) ne s'affiche plus
    # « dans les listes » : le tableau de bord est un agrégat de liste, donc
    # exclue aussi (reste consultable via le détail ``?include_archived=1``).
    qs = Idee.objects.filter(company=company, draft=False, archived=False)
    compte = qs.aggregate(
        ouvert=Count('id', filter=Q(statut=S.OUVERT)),
        examinee=Count('id', filter=Q(statut=S.EXAMINEE)),
        retenue=Count('id', filter=Q(statut=S.RETENUE)),
        realisee=Count('id', filter=Q(statut=S.REALISEE)),
        fermee=Count('id', filter=Q(statut=S.FERMEE)),
        total=Count('id'),
    )
    return {
        'ouvert': compte['ouvert'] or 0,
        'examinee': compte['examinee'] or 0,
        'retenue': compte['retenue'] or 0,
        'realisee': compte['realisee'] or 0,
        'fermee': compte['fermee'] or 0,
        'total': compte['total'] or 0,
    }


def top_votes(company, limit=5):
    """NTIDE6 — top N idées les plus populaires (par votes), plus récente
    d'abord en cas d'égalité."""
    from .models import Idee

    qs = (Idee.objects.filter(company=company, draft=False, archived=False)
          .order_by('-votes_count', '-created_at')[:limit])
    return list(qs.values('id', 'titre', 'votes_count', 'statut', 'contexte'))


def plus_recentes(company, limit=5):
    """NTIDE6 — N idées les plus récemment proposées."""
    from .models import Idee

    qs = (Idee.objects.filter(company=company, draft=False, archived=False)
          .order_by('-created_at', '-id')[:limit])
    return list(qs.values(
        'id', 'titre', 'votes_count', 'statut', 'contexte', 'created_at'))


def heat_par_contexte(company):
    """NTIDE6 — nombre d'idées par contexte (heat-chart), plus fréquent
    d'abord. Les idées sans contexte renseigné sont ignorées."""
    from django.db.models import Count

    from .models import Idee

    qs = (Idee.objects.filter(company=company, draft=False, archived=False)
          .exclude(contexte='')
          .values('contexte')
          .annotate(nombre=Count('id'))
          .order_by('-nombre', 'contexte'))
    return [{'contexte': r['contexte'], 'nombre': r['nombre']} for r in qs]


def contextes_frequents(company, limit=5):
    """NTIDE10 — top N contextes existants par fréquence (autocomplétion du
    formulaire proposer une idée, NTIDE8/NTIDE9)."""
    return [row['contexte'] for row in heat_par_contexte(company)[:limit]]


def idees_similaires(company, texte, limit=3):
    """NTIDE20 — « Existe-t-il une idée similaire ? » : recherche simple
    ``icontains`` titre+description (même patron que ``apps.kb.selectors``),
    top N par votes (plus de votes = plus consolidée), plus récente d'abord
    en cas d'égalité. Exclut les brouillons d'autrui (invisibles/hors sujet
    pour la dédup) et les idées masquées (modération, NTIDE19)."""
    from django.db.models import Q

    from .models import Idee

    texte = (texte or '').strip()
    if not texte:
        return []
    qs = (Idee.objects.filter(company=company, draft=False, archived=False)
          .filter(Q(titre__icontains=texte) | Q(description__icontains=texte))
          .order_by('-votes_count', '-created_at')[:limit])
    return list(qs.values('id', 'titre', 'contexte', 'votes_count', 'statut'))


def tableau_bord_idees(company):
    """NTIDE6 — agrégat complet du tableau de bord admin (une seule lecture)."""
    return {
        'par_statut': idees_par_statut(company),
        'top_votes': top_votes(company),
        'plus_recentes': plus_recentes(company),
        'heat_contexte': heat_par_contexte(company),
    }


def users_for_campaign(company, campagne):
    """NTIDE26 — utilisateurs de ``company`` dont le rôle FIN (``role.nom``,
    ``apps.roles``) figure dans le segment de ``campagne`` (liste
    ``segment`` + ``cible_departement`` en repli mono-cible).

    Departement (NTFPA1, ``apps.fpa``) n'étant PAS une dépendance de ce
    module (jamais un import cross-app, cf. ``models.CampagneInnovation``),
    le nom stocké est comparé au nom du RÔLE fin de l'utilisateur qu'il
    s'agisse d'un rôle (``ROLES_CIBLABLES``) ou — le jour où une société
    câble Departement — d'un nom de département repris tel quel côté rôle
    (même mécanique de repli que ``InnovationSettings.segment_defaut``,
    NTIDE7). Un utilisateur sans rôle fin assigné (compte hérité) n'est
    jamais ciblé — un segment nommé exige un rôle nommé.

    Renvoie un queryset vide si la campagne n'a ni ``segment`` ni
    ``cible_departement`` (rien à cibler)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    noms = list(campagne.segment or [])
    if campagne.cible_departement:
        noms.append(campagne.cible_departement)
    if not noms:
        return User.objects.none()
    return (User.objects.filter(company=company, role__nom__in=noms)
            .distinct())


def campagne_active_pour_utilisateur(user):
    """NTIDE27 — la campagne ACTIVE (s'il y en a une) dont le segment matche
    le rôle FIN de ``user`` (même règle que ``users_for_campaign``, en sens
    inverse : depuis l'utilisateur vers LA campagne à lui montrer sur le
    formulaire « Proposer une idée »). La plus récente en cas de plusieurs
    correspondances. ``None`` si l'utilisateur n'a pas de rôle fin, ou si
    aucune campagne active ne le cible.

    Filtrage fait en PYTHON (pas de lookup JSON spécifique au backend) : le
    nombre de campagnes ACTIVES d'une société reste petit, et ``contains``
    sur un ``JSONField`` diverge selon le moteur de base de données."""
    from .models import CampagneInnovation

    role_nom = getattr(getattr(user, 'role', None), 'nom', None)
    if not role_nom:
        return None
    qs = (CampagneInnovation.objects.filter(
        company_id=user.company_id, statut=CampagneInnovation.Statut.ACTIVE)
        .order_by('-created_at', '-id'))
    for campagne in qs:
        if campagne.cible_departement == role_nom or role_nom in (campagne.segment or []):
            return campagne
    return None


def timeline(company, statut=None, contexte=None):
    """NTIDE23 — nombre d'idées PROPOSÉES par jour (``created_at``), filtres
    statut/contexte optionnels, ordre chronologique croissant (adapté à un
    graphe Recharts). Mêmes exclusions que le tableau de bord (NTIDE6) : une
    idée brouillon (NTIDE18) ou masquée (NTIDE19) n'apparaît pas dans un
    agrégat de liste."""
    from django.db.models import Count
    from django.db.models.functions import TruncDate

    from .models import Idee

    qs = Idee.objects.filter(company=company, draft=False, archived=False)
    if statut:
        qs = qs.filter(statut=statut)
    if contexte:
        qs = qs.filter(contexte__iexact=contexte)
    qs = (qs.annotate(jour=TruncDate('created_at'))
          .values('jour')
          .annotate(nombre=Count('id'))
          .order_by('jour'))
    return [{'date': row['jour'].isoformat(), 'nombre': row['nombre']}
            for row in qs if row['jour'] is not None]
