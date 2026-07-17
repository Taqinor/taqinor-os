"""Lectures de `apps.entites` — jamais d'écriture ici (cf. services.py)."""
from .models import Entite


def get_company_entite(company, entite_id):
    """Renvoie l'`Entite` `entite_id` bornée à `company`, ou None."""
    try:
        return Entite.objects.get(company=company, pk=entite_id)
    except (Entite.DoesNotExist, ValueError, TypeError):
        return None


def entite_tree(company):
    """NTADM1 — arbre des entités de `company` (`?tree=1`), racines d'abord.

    Renvoie une liste imbriquée de dicts {id, code, nom, actif, enfants:[...]}.
    """
    entites = list(Entite.objects.filter(company=company).order_by('nom'))
    by_parent = {}
    for e in entites:
        by_parent.setdefault(e.parent_id, []).append(e)

    def _node(e):
        return {
            'id': e.id,
            'code': e.code,
            'nom': e.nom,
            'actif': e.actif,
            'enfants': [_node(c) for c in by_parent.get(e.id, [])],
        }

    return [_node(e) for e in by_parent.get(None, [])]


def entites_actives_count(company):
    return Entite.objects.filter(company=company, actif=True).count()
