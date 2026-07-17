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
    # publiée).
    qs = Idee.objects.filter(company=company, draft=False)
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

    qs = (Idee.objects.filter(company=company, draft=False)
          .order_by('-votes_count', '-created_at')[:limit])
    return list(qs.values('id', 'titre', 'votes_count', 'statut', 'contexte'))


def plus_recentes(company, limit=5):
    """NTIDE6 — N idées les plus récemment proposées."""
    from .models import Idee

    qs = (Idee.objects.filter(company=company, draft=False)
          .order_by('-created_at', '-id')[:limit])
    return list(qs.values(
        'id', 'titre', 'votes_count', 'statut', 'contexte', 'created_at'))


def heat_par_contexte(company):
    """NTIDE6 — nombre d'idées par contexte (heat-chart), plus fréquent
    d'abord. Les idées sans contexte renseigné sont ignorées."""
    from django.db.models import Count

    from .models import Idee

    qs = (Idee.objects.filter(company=company, draft=False)
          .exclude(contexte='')
          .values('contexte')
          .annotate(nombre=Count('id'))
          .order_by('-nombre', 'contexte'))
    return [{'contexte': r['contexte'], 'nombre': r['nombre']} for r in qs]


def contextes_frequents(company, limit=5):
    """NTIDE10 — top N contextes existants par fréquence (autocomplétion du
    formulaire proposer une idée, NTIDE8/NTIDE9)."""
    return [row['contexte'] for row in heat_par_contexte(company)[:limit]]


def tableau_bord_idees(company):
    """NTIDE6 — agrégat complet du tableau de bord admin (une seule lecture)."""
    return {
        'par_statut': idees_par_statut(company),
        'top_votes': top_votes(company),
        'plus_recentes': plus_recentes(company),
        'heat_contexte': heat_par_contexte(company),
    }
