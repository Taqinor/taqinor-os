"""Copilote vague 2 — libellés des tickets SAV et des équipements du parc
nommés dans l'aperçu d'une proposition de l'assistant, pour ``GET
/api/django/agent/libelles/`` et ``erp.ouvrir`` (résolveur ``libelles_sav`` de
la table ``apps/agent/libelles.py``).

Lecture seule, bornée à la SOCIÉTÉ, au droit de LIRE (``sav_voir`` pour un
ticket, ``equipement_voir`` pour un équipement — les gardes de lecture de
``TicketViewSet`` / ``EquipementViewSet``) et à la PORTÉE de leurs listes
(ticket : créé par soi, dont on est technicien, ou de l'équipe ; équipement :
créé par l'équipe ou parc d'un chantier visible). Un objet inconnu, d'une autre
société ou hors portée est ABSENT. Jamais la description du problème (texte
tiers), un coût ni un téléphone : une référence, un nom, un statut.
"""


def _nom_client(client):
    return (getattr(client, 'nom', '') or '').strip()


def _ticket_en_clair(ticket):
    """« SAV-202611-0007 — Benali (Nouveau) »."""
    tete = ' — '.join(p for p in (ticket.reference, _nom_client(ticket.client)) if p)
    return f'{tete} ({ticket.get_statut_display()})'


def _equipement_en_clair(equipement):
    """« Onduleur Deye SUN-6K — n° 2311-0045 — Benali »."""
    client = (equipement.installation.client if equipement.installation_id
              and equipement.installation.client_id else equipement.client_vente)
    serie = (equipement.numero_serie or '').strip()
    morceaux = ((equipement.produit.nom or '').strip(),
                f'n° {serie}' if serie else '', _nom_client(client))
    return ' — '.join(m for m in morceaux if m)


def _equipements_visibles(user):
    """Même portée que ``EquipementViewSet.get_queryset`` (ACSV58)."""
    from django.db.models import Q

    from core.scoping import visible_user_ids

    from apps.installations.selectors import chantiers_visibles

    from .models import Equipement

    qs = Equipement.objects.filter(company_id=user.company_id)
    ids = visible_user_ids(user)
    if ids is not None:
        qs = qs.filter(Q(created_by__in=ids)
                       | Q(installation__in=chantiers_visibles(user)))
    return qs


def libelles_sav(user, *, ticket=None, equipement=None):
    """``{'ticket': …, 'equipement': …}`` pour les identifiants donnés que
    ``user`` voit (les autres clés manquent)."""
    from core.scoping import scope_queryset
    from core.permissions import _user_has_or_legacy

    from .models import Ticket

    if getattr(user, 'company_id', None) is None:
        return {}
    out = {}
    if ticket and _user_has_or_legacy(user, 'sav_voir'):
        trouve = scope_queryset(
            Ticket.objects.filter(company_id=user.company_id), user,
            ['technicien_responsable', 'created_by'],
        ).filter(pk=ticket).select_related('client').first()
        if trouve is not None:
            out['ticket'] = _ticket_en_clair(trouve)
    if equipement and _user_has_or_legacy(user, 'equipement_voir'):
        trouve = (_equipements_visibles(user).filter(pk=equipement)
                  .select_related('produit', 'installation__client',
                                  'client_vente').first())
        if trouve is not None:
            out['equipement'] = _equipement_en_clair(trouve)
    return out
