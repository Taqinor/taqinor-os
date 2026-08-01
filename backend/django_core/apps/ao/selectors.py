"""Selectors du module Appels d'offres (``apps.ao``).

Point d'entrée des LECTURES cross-app du domaine AO (CLAUDE.md : les autres
apps lisent ``ao`` via ``apps.ao.selectors`` ou par string-FK, jamais via
``apps.ao.models``).

AOF17 — le lien AO ↔ lead, SANS couplage
----------------------------------------
``AppelOffre.lead_id`` est un ``PositiveIntegerField`` OPAQUE, PAS une FK vers
``crm.Lead`` — et c'est délibéré : c'est exactement ce qui tient le contrat
import-linter ``ao-models-decoupled`` (``apps.ao.models`` n'importe AUCUN
``models`` du cœur métier). Un agent bien intentionné voudra un jour le
« réparer » en vraie FK : **c'est interdit**, et un test le verrouille
(``apps/ao/tests/test_lien_crm.py``).

Conséquence pratique : le CRM liste les AO d'un lead par ``ao_par_lead`` (ici),
et ``ao`` lit le lead par ``crm.selectors`` (jamais ``crm.models``).
"""
from __future__ import annotations


def ao_par_lead(company, lead_id):
    """Les appels d'offres d'un lead, bornés à la société (lecture seule).

    Point d'entrée cross-app : le CRM affiche « les AO de ce lead » sans jamais
    importer ``apps.ao.models``. Un ``lead_id`` vide renvoie un queryset VIDE
    (jamais tous les AO de la société — un filtre absent ne doit pas se muer en
    absence de filtre).
    """
    from .models import AppelOffre

    if not lead_id:
        return AppelOffre.objects.none()
    return AppelOffre.objects.filter(company=company, lead_id=lead_id)


def compte_ao_par_lead(company, lead_id):
    """Nombre d'AO rattachés à un lead (badge CRM), borné à la société."""
    return ao_par_lead(company, lead_id).count()


def points_a_lever(appel_offre):
    """AOF24 — la liste « à confirmer à l'exécution », DÉRIVÉE de la donnée.

    Deux sources, jamais une saisie libre :

    * chaque cote au statut ``A_CONFIRMER`` d'une chaîne du dossier — une cote
      orange qui n'apparaîtrait pas ici serait un DÉFAUT, pas une omission
      acceptable (un test le vérifie) ;
    * chaque obstacle ACTIF non engageable (lu sur plan, deviné, déclaré par le
      client) — il entre dans le calcul mais n'engage pas.

    Renvoie une liste de dicts ``{type, reference, libelle, detail}``, triée
    de façon stable pour que deux rendus successifs soient comparables.
    """
    from .models import ChaineCotes, ObstacleAO

    points = []
    chaines = ChaineCotes.objects.filter(
        company=appel_offre.company,
        toiture__batiment__appel_offre=appel_offre,
    ).select_related('toiture')
    for chaine in chaines:
        for segment in chaine.cotes_a_confirmer:
            points.append({
                'type': 'cote',
                'reference': f'{chaine.libelle} · {segment.get("libelle", "")}',
                'libelle': 'Cote à confirmer à l\'exécution',
                'detail': (
                    f'valeur retenue {segment.get("valeur_m")} m'
                    + (f' (annoncée {segment["valeur_annoncee_m"]} m)'
                       if segment.get('valeur_annoncee_m') is not None else '')
                ),
            })

    obstacles = ObstacleAO.objects.filter(
        company=appel_offre.company,
        toiture__batiment__appel_offre=appel_offre,
        actif=True,
    ).select_related('toiture')
    for obstacle in obstacles:
        if obstacle.engageable:
            continue
        points.append({
            'type': 'obstacle',
            'reference': obstacle.repere or f'#{obstacle.pk}',
            'libelle': 'Obstacle non relevé — à confirmer sur site',
            'detail': (
                f'{obstacle.get_nature_display()} · '
                f'{obstacle.get_provenance_display()}'
            ),
        })
    return sorted(points, key=lambda p: (p['type'], p['reference']))


def mention_cartouche(appel_offre):
    """AOF24 — mention de base du cartouche, ou ``None``.

    Prend le relevé le plus RÉCENT du dossier : c'est celui qui fait foi.
    """
    releve = appel_offre.releves.order_by('-date_visite', '-id').first()
    return releve.mention_cartouche if releve is not None else None


def fiche_lead_de_l_ao(appel_offre):
    """Fiche-carte LECTURE SEULE du lead lié, ou ``None``.

    Passe par ``apps.crm.selectors.lead_card`` — jamais ``apps.crm.models``.
    """
    if not appel_offre.lead_id:
        return None
    from apps.crm.selectors import lead_card

    return lead_card(appel_offre.lead_id, appel_offre.company)


# ── AOF163 — lecture cross-app du moteur PARTAGÉ, sans projet AO ───────────
#
# ``apps.ventes`` (villa / devis résidentiel) lit le moteur PAR ICI : c'est le
# contrat de frontière du dépôt (les autres apps lisent ``ao`` via
# ``apps.ao.selectors``, jamais via ``apps.ao.models`` ni ``apps.ao.services``
# en direct). Le calcul reste sans effet de bord : aucune ligne AO n'est créée.

def calepinage_sans_projet(*, surface, kits, parametres, obstacles=(),
                           zones=(), politique=None, repere='SURFACE'):
    """Calepine une enveloppe libre — LECTURE PURE, zéro écriture.

    Point d'entrée nommé pour les consommateurs hors AO (villa). Il délègue au
    service partagé d'AOF163 : un seul moteur, un seul format d'entrée.
    """
    from .services import calepiner_surface

    return calepiner_surface(
        surface=surface, kits=kits, parametres=parametres,
        obstacles=obstacles, zones=zones, politique=politique, repere=repere)


def calepinage_villa(area, *, ordre='lnglat', kit=None, retrait_m=None,
                     pas_recherche_m=0.01):
    """Calepine une toiture villa (``AreaRecord``) — LECTURE PURE.

    ``ordre`` reste un argument EXPLICITE jusqu'ici : aucun appelant ne doit
    pouvoir hériter d'un défaut deviné sur l'ordre lat/lng.
    """
    from .services import calepiner_villa

    return calepiner_villa(area, ordre=ordre, kit=kit, retrait_m=retrait_m,
                           pas_recherche_m=pas_recherche_m)
