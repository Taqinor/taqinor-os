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
