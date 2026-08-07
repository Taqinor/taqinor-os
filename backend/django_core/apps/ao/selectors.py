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


# ── AOF166 — tableau de bord des marchés (supersede NTMAR27) ───────────────
#
# UN SEUL appel agrégé sert le tableau : le front ne compose pas six requêtes.
# Le NOM ``tableau_marches`` et l'endpoint ``/api/django/ao/tableau-marches/``
# sont REPRIS DE NTMAR27 à dessein — sans cette reprise nominative, l'ERP
# finirait avec deux tableaux de bord d'AO concurrents.
#
# AUCUN coût, AUCUNE marge, AUCUN ``prix_achat`` ne sort d'ici : l'économie
# d'un AO vit derrière ``ao_rentabilite_voir`` dans des endpoints SÉPARÉS
# (AOF2). Les montants publiés sont ceux de NOTRE OFFRE et des cautions
# IMMOBILISÉES — des engagements, jamais des coûts de revient.

#: Statuts d'un dossier ENCORE EN COURS (avant dépôt).
STATUTS_EN_COURS = (
    'identifie', 'analyse_cps', 'releve', 'etude', 'chiffrage', 'dossier',
    'pret_a_deposer', 'en_preparation',
)
#: Un marché EN EXÉCUTION = gagné (le dossier a produit un marché).
STATUTS_EN_EXECUTION = ('gagne',)
#: Une caution IMMOBILISÉE est constituée et non encore restituée.
STATUT_CAUTION_IMMOBILISEE = 'constituee'


def tableau_marches_vide():
    """Le tableau, sans société : des zéros EXPLICITES, jamais une erreur."""
    from decimal import Decimal

    return {
        'en_cours': {'total': 0, 'sous_7_jours': 0, 'en_retard': 0,
                     'par_echeance': []},
        'echeances_dues': 0,
        'reussite': {'gagnes': 0, 'perdus': 0, 'total_decides': 0,
                     'total_resultats': 0,
                     'taux_reussite_pct': Decimal('0.00')},
        'capacite': {'demontree_modules': 0, 'engagee_modules': 0,
                     'ecart_modules': 0, 'toitures_prouvees': 0},
        'cautions': {'montant_immobilise': Decimal('0.00'), 'nombre': 0,
                     'expirant_avant_ouverture': 0},
        'marches_en_execution': {'total': 0,
                                 'montant_offre_ht': Decimal('0.00')},
    }


def _en_cours(company, aujourd_hui):
    """AO en cours, RANGÉS PAR ÉCHÉANCE DE REMISE (la seule qui fait perdre)."""
    from datetime import timedelta

    from .models import AppelOffre

    qs = (AppelOffre.objects
          .filter(company=company, statut__in=STATUTS_EN_COURS)
          .order_by('date_limite', 'id'))
    horizon = aujourd_hui + timedelta(days=7)
    sous_7, en_retard, lignes = 0, 0, []
    for ao in qs:
        jours = None
        if ao.date_limite is not None:
            jours = (ao.date_limite - aujourd_hui).days
            if ao.date_limite < aujourd_hui:
                en_retard += 1
            elif ao.date_limite <= horizon:
                sous_7 += 1
        lignes.append({
            'id': ao.pk,
            'reference': ao.reference,
            'objet': ao.objet,
            'acheteur': ao.acheteur,
            'statut': ao.statut,
            'statut_display': ao.get_statut_display(),
            'date_limite': ao.date_limite,
            'jours_restants': jours,
        })
    return {'total': len(lignes), 'sous_7_jours': sous_7,
            'en_retard': en_retard, 'par_echeance': lignes}


def _capacite(company):
    """Capacité DÉMONTRÉE (variantes retenues) vs ENGAGÉE (bâtiments).

    « Démontrée » n'est pas « calculée » : seules les variantes RETENUES
    comptent, et l'écart avec l'engagement porté au bordereau est publié tel
    quel — un écart masqué est exactement ce qui rend un dossier indéfendable.
    """
    from .models import BatimentAO, VarianteCalepinage

    demontree = 0
    prouvees = 0
    for variante in VarianteCalepinage.objects.filter(
            company=company, est_retenue=True):
        demontree += int(variante.total_modules or 0)
        prouvees += 1

    engagee = 0
    for batiment in BatimentAO.objects.filter(company=company):
        engagee += int(batiment.engagement_modules or 0)

    return {'demontree_modules': demontree, 'engagee_modules': engagee,
            'ecart_modules': demontree - engagee,
            'toitures_prouvees': prouvees}


def _cautions(company):
    """Cautions IMMOBILISÉES : constituées, non restituées (repris de NTMAR27)."""
    from decimal import Decimal

    from django.db.models import Sum

    from .models import CautionSoumission

    qs = CautionSoumission.objects.filter(
        company=company, statut=STATUT_CAUTION_IMMOBILISEE)
    total = qs.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    expirantes = sum(
        1 for caution in qs.select_related('appel_offre')
        if caution.expire_avant_ouverture)
    return {'montant_immobilise': total, 'nombre': qs.count(),
            'expirant_avant_ouverture': expirantes}


def _marches_en_execution(company):
    """Marchés GAGNÉS, avec le montant de NOTRE OFFRE (jamais un coût)."""
    from decimal import Decimal

    from django.db.models import Sum

    from .models import AppelOffre

    qs = AppelOffre.objects.filter(company=company,
                                   statut__in=STATUTS_EN_EXECUTION)
    montant = qs.aggregate(t=Sum('montant_offre_ht'))['t'] or Decimal('0.00')
    return {'total': qs.count(), 'montant_offre_ht': montant}


def tableau_marches(company, *, a_la_date=None):
    """Le tableau de bord des marchés, en UN SEUL appel agrégé.

    Six blocs : AO en cours par échéance de remise, échéances dues, réussite
    (CALCULÉE depuis ``ResultatAO``, jamais saisie), capacité démontrée vs
    engagée, cautions immobilisées, marchés en exécution.
    """
    from django.utils import timezone

    from .services import echeances_ao_dues, taux_reussite_ao

    if company is None:
        return tableau_marches_vide()
    aujourd_hui = a_la_date or timezone.now().date()
    return {
        'en_cours': _en_cours(company, aujourd_hui),
        'echeances_dues': len(echeances_ao_dues(company,
                                                a_la_date=aujourd_hui)),
        # Le taux de réussite est DÉRIVÉ de ResultatAO — jamais un champ saisi.
        'reussite': taux_reussite_ao(company),
        'capacite': _capacite(company),
        'cautions': _cautions(company),
        'marches_en_execution': _marches_en_execution(company),
    }


# ── VAO31 — l'ISSUE d'un lot d'affaires, pour la mesure d'attribution ──────
#
# La veille (``apps.veille_ao``) doit répondre à « d'où vient réellement le
# chiffre d'affaires » : avis reçus → retenus → convertis → GAGNÉS. Le dernier
# maillon est une donnée d'``apps.ao``, et il se lit ICI — jamais en important
# ``apps.ao.models`` depuis une autre app (frontière CLAUDE.md).
#
# Ces fonctions prennent des IDENTIFIANTS (le lien veille→AO est un entier
# opaque, jamais une FK) et restent bornées à la société de l'appelant.

def issues_par_ids(company, appel_offre_ids):
    """``{id: statut}`` pour ces affaires, bornées à ``company``.

    Un identifiant inconnu — ou appartenant à une AUTRE société — est
    simplement ABSENT du résultat : l'appelant ne peut donc rien déduire de
    l'existence d'une affaire qui ne lui appartient pas.
    """
    from .models import AppelOffre

    identifiants = [i for i in (appel_offre_ids or []) if i]
    if company is None or not identifiants:
        return {}
    return dict(
        AppelOffre.objects.filter(company=company, pk__in=identifiants)
        .values_list('pk', 'statut'))


def statuts_gagnes():
    """Les statuts qui comptent comme GAGNÉS (source unique de vérité)."""
    from .models import AppelOffre

    return (AppelOffre.Statut.GAGNE,)


def statuts_perdus():
    """Les statuts qui comptent comme PERDUS ou abandonnés."""
    from .models import AppelOffre

    return (AppelOffre.Statut.PERDU, AppelOffre.Statut.ABANDONNE)
