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


def calepinage_villa(area, *, ordre='lnglat', kit=None, produit_panneau=None,
                     company=None, retrait_m=None, pas_recherche_m=0.01,
                     famille=None):
    """Calepine une toiture villa (``AreaRecord``) — LECTURE PURE.

    ``ordre`` reste un argument EXPLICITE jusqu'ici : aucun appelant ne doit
    pouvoir hériter d'un défaut deviné sur l'ordre lat/lng.

    ``produit_panneau`` (PV12) — identifiant OU instance de ``stock.Produit``,
    résolu DANS ``company`` : le calepinage est alors posé sur le panneau
    réellement vendu. Une fiche technique incomplète retombe sur le kit villa
    par défaut, jamais sur une géométrie devinée.

    ``famille`` (PV66) — ``SUD`` ou ``EST_OUEST`` : la forme de table, pas le
    panneau. Absente, le calcul est celui d'avant PV66, à l'identique.
    """
    from .services import calepiner_villa

    return calepiner_villa(area, ordre=ordre, kit=kit,
                           produit_panneau=produit_panneau, company=company,
                           retrait_m=retrait_m,
                           pas_recherche_m=pas_recherche_m, famille=famille)


# ── PV68 — synthèse de calepinage d'une AFFAIRE ────────────────────────────
#
# L'écran « Affaire » affichait ses toitures une par une : le total de modules
# d'un dossier à cinq bâtiments n'existait NULLE PART, et se refaisait à la
# main — donc faux un jour sur deux. Ce sélecteur le calcule, à partir de la
# variante RETENUE de chaque toiture et d'elle seule (les alternatives et les
# sensibilités sont des hypothèses, pas l'offre).
#
# AUCUN coût, AUCUNE marge : la synthèse ne publie que de la géométrie et des
# comptes (règle AOF2 — l'économie vit derrière ``ao_rentabilite_voir``).

def synthese_calepinage_affaire(appel_offre, company=None):
    """La synthèse de calepinage d'une affaire — UN retour, TOUTES les clés.

    ``appel_offre`` : instance OU identifiant. Avec un identifiant, ``company``
    devient OBLIGATOIRE — sans elle, la synthèse d'une autre société
    remonterait, et un total faux est pire qu'un total absent.

    Rend TOUJOURS le même dictionnaire, même sans aucune toiture :
    ``total_modules``, ``total_kwc``, ``toitures_total``,
    ``toitures_calepinees`` et une ligne PAR TOITURE. Les toitures NON
    calepinées y figurent aussi, ``calepinee: False`` — c'est justement le
    trou qu'un chargé d'affaires doit voir, et le taire ferait passer un
    dossier incomplet pour un dossier fini.
    """
    from .models import ToitureAO, VarianteCalepinage

    if company is None:
        company = getattr(appel_offre, 'company', None)
    if company is None:
        raise ValueError(
            "La synthèse de calepinage se lit toujours dans une société : "
            'fournissez `company` avec un identifiant d\'affaire.')
    appel_offre_id = getattr(appel_offre, 'pk', appel_offre)

    toitures = list(ToitureAO.objects.filter(
        company=company, batiment__appel_offre_id=appel_offre_id
    ).select_related('batiment').order_by(
        'batiment__code', 'code_document', 'id'))
    retenues = {
        variante.toiture_id: variante
        for variante in VarianteCalepinage.objects.filter(
            company=company, appel_offre_id=appel_offre_id, est_retenue=True)
    }

    lignes = []
    total_modules = 0
    total_kwc = 0.0
    for toiture in toitures:
        variante = retenues.get(toiture.pk)
        modules = int((variante.total_modules or 0) if variante else 0)
        kwc = float((variante.puissance_kwc or 0) if variante else 0.0)
        total_modules += modules
        total_kwc += kwc
        preuve = (variante.preuve or {}) if variante else {}
        lignes.append({
            'toiture': toiture.pk,
            'code_document': toiture.code_document or '',
            'designation': toiture.designation or '',
            'batiment': toiture.batiment_id,
            'batiment_code': toiture.batiment.code or '',
            'calepinee': variante is not None,
            'variante': variante.pk if variante else None,
            'variante_nom': variante.nom if variante else '',
            'statut': variante.statut if variante else '',
            'modules': modules,
            'kwc': round(kwc, 3),
            'optimal': preuve.get('optimal'),
            'methode': preuve.get('methode') or '',
        })

    return {
        'total_modules': total_modules,
        'total_kwc': round(total_kwc, 3),
        'toitures_total': len(toitures),
        'toitures_calepinees': sum(1 for ligne in lignes if ligne['calepinee']),
        'toitures': lignes,
    }


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


# ── Le MÊME atelier 3D pour l'AO que pour la villa ─────────────────────────
#
# L'écran de conception 3D (``frontend/src/pages/ventes/ToitureDesign.jsx``)
# existe déjà et sert deux modes (« lead », « devis »). Le mode « ao » le
# RÉUTILISE — jamais une seconde implémentation : la géométrie AO relevée
# (``ToitureAO`` + ``ZoneAO``, repère LOCAL MÉTRIQUE) est reprojetée en degrés
# À LA FRONTIÈRE (``apps/ao/geometrie.py``, AOF19) pour hydrater le builder.
#
# UN SEUL appel, UN SEUL dict, TOUTES les clés TOUJOURS présentes (contrat
# ``apps/ao/contract_samples/ao_design_context.json``, PACT10). Un panier vide
# vaut ``[]``, une valeur inconnue vaut ``None``/``''`` — jamais une clé
# absente : c'est un ``.map()`` sur ``undefined`` en production.
#
# LECTURE PURE : aucun statut, aucune toiture, aucun layout n'est écrit ici.

def statuts_conception_figee():
    """Statuts pour lesquels le dossier est PARTI (ou clos) : le calepinage ne
    se remodifie plus depuis l'atelier.

    DÉRIVÉE des énumérations du modèle (jamais des chaînes recopiées) et
    réutilise les deux sources existantes ``statuts_gagnes``/``statuts_perdus``
    — un statut renommé ne peut donc pas laisser une porte ouverte ici.
    """
    from .models import AppelOffre

    return (AppelOffre.Statut.DEPOSE,) + statuts_gagnes() + statuts_perdus()


def raison_conception_figee(appel_offre):
    """Motif FRANÇAIS de lecture seule de l'atelier 3D, ou ``''``.

    SOURCE UNIQUE de la phrase : le contexte de conception l'affiche au
    chargement et le refus d'écriture (409) la renvoie — deux formulations
    différentes pour la même règle seraient un écart que personne ne verrait.
    """
    if appel_offre is None \
            or appel_offre.statut not in statuts_conception_figee():
        return ''
    return ('Affaire « %s » : le dossier est parti chez l\'acheteur — le '
            'calepinage ne se modifie plus.'
            % appel_offre.get_statut_display())


def _config_carte_builder():
    """Clés carte du builder 3D — MIROIR de ``apps/ventes/views/roof_config.py``.

    Mêmes variables d'environnement (``PUBLIC_MAPTILER_KEY`` /
    ``PUBLIC_MAPBOX_TOKEN``), même forme ``{available, maptilerKey,
    mapboxToken}`` que le contexte devis : l'écran lit la carte DANS le contexte
    plutôt que d'enchaîner un second appel. C'est de la CONFIGURATION (aucune
    donnée société, aucune écriture) — la lire ici évite de faire dépendre le
    domaine AO du domaine ventes pour une clé d'API.
    """
    import os

    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return {
        'available': bool(maptiler),
        'maptilerKey': maptiler,
        'mapboxToken': mapbox or None,
    }


def _toiture_de_reference(company, appel_offre_id):
    """La toiture qui porte la vue 3D de l'affaire — choix DÉTERMINISTE.

    Une affaire peut compter plusieurs bâtiments et plusieurs toitures ; le
    builder, lui, s'ouvre sur UN site. On prend la première toiture ANCRÉE
    (``origine_lat``/``origine_lng`` renseignées — la seule reprojetable en
    degrés), à défaut la première tout court, dans un ordre stable
    (bâtiment, code de planche, id). Un tri instable ferait bouger la vue d'un
    chargement à l'autre sans qu'aucune donnée n'ait changé.
    """
    from .models import ToitureAO

    toitures = list(
        ToitureAO.objects.filter(
            company=company, batiment__appel_offre_id=appel_offre_id
        ).select_related('batiment').prefetch_related('zones')
        .order_by('batiment__ordre', 'batiment__code', 'code_document', 'id'))
    if not toitures:
        return None
    for toiture in toitures:
        if toiture.origine_lat is not None and toiture.origine_lng is not None:
            return toiture
    return toitures[0]


def _toiture_vers_contexte(toiture):
    """Bloc ``geometrie.toiture`` : le relevé AO tel qu'il est, sans invention."""
    if toiture is None:
        return None
    return {
        'id': toiture.pk,
        'code_document': toiture.code_document or '',
        'designation': toiture.designation or '',
        'surface_m2': str(toiture.surface_m2 or '0.000'),
        'angle_nord_deg': str(toiture.angle_nord_deg or '0.00'),
        'parametres_calepinage': toiture.parametres_calepinage or {},
        'zones': [
            {
                'id': zone.pk,
                'repere': zone.repere or '',
                'nature': zone.nature,
                'sommets': zone.sommets or [],
                'retrait_m': str(zone.retrait_m or '0.00'),
                'hauteur_m': (str(zone.hauteur_m)
                              if zone.hauteur_m is not None else None),
            }
            for zone in toiture.zones.all()
        ],
    }


def _contour_en_degres(toiture):
    """Contour LOCAL MÉTRIQUE → ``[[lat, lng], …]``, ou ``[]``.

    ORDRE DES AXES (AOF19) : la conversion passe explicitement par
    ``local_m_vers_lnglat`` puis ``lnglat_vers_latlng`` — le builder et le lead
    CRM parlent ``[lat, lng]``, le repère de frontière est ``[lng, lat]``, et
    seule une fonction NOMMÉE a le droit d'échanger les deux.

    Sans ancre géographique sur la toiture, on rend ``[]`` : reprojeter un
    repère local depuis le point GPS du SITE placerait le bâtiment à côté de
    lui-même, ce qui est pire qu'un contour absent.
    """
    from .geometrie import lnglat_vers_latlng, local_m_vers_lnglat

    if toiture is None or not toiture.contour_local_m:
        return []
    if toiture.origine_lat is None or toiture.origine_lng is None:
        return []
    origine = [float(toiture.origine_lng), float(toiture.origine_lat)]
    return lnglat_vers_latlng(
        local_m_vers_lnglat(toiture.contour_local_m, origine))


def contexte_conception_affaire(appel_offre, company):
    """Tout ce que l'atelier 3D doit savoir d'une AFFAIRE, en UN SEUL appel.

    Rend ``None`` quand l'affaire appartient à une AUTRE société (l'appelant
    répond alors 404 — jamais d'oracle d'existence). Sinon un dict à la forme
    FIXE, miroir exact du contrat devis (``affaire`` y remplace ``devis``) :

        {affaire: {id, reference, reference_acheteur, statut, objet, acheteur,
                   maitre_ouvrage},
         geometrie: {source, roof_layout, pin, outline, toiture},
         cible: {panneaux, kwc, panel_watt, scenario, batterie, surface_m2},
         carte: {available, maptilerKey, mapboxToken},
         modifiable, raison_lecture_seule, avertissements}

    ``geometrie.source`` vaut ``'affaire'`` (une session 3D est déjà
    enregistrée sur l'affaire — elle PRIME), ``'toiture'`` (contour relevé
    reprojeté depuis son ancre), ``'site'`` (seul le point GPS du site est
    connu) ou ``'none'``. ``modifiable`` est faux — avec un motif FRANÇAIS dans
    ``raison_lecture_seule`` — dès que le dossier est déposé ou clos.
    ``raison_lecture_seule`` vaut ``''`` quand l'affaire est modifiable, jamais
    ``None``.
    """
    if appel_offre is None:
        return None
    # Garde société DÉFENSIVE (le queryset de l'appelant borne déjà) : un
    # superutilisateur sans société passe outre, comme partout ailleurs.
    company_id = getattr(company, 'id', None)
    if company_id is not None and appel_offre.company_id != company_id:
        return None

    societe = appel_offre.company
    toiture = _toiture_de_reference(societe, appel_offre.pk)
    outline = _contour_en_degres(toiture)

    # ── Épingle : l'ancre de la toiture d'abord, le point du site ensuite ──
    pin = None
    pin_de_la_toiture = False
    if toiture is not None and toiture.origine_lat is not None \
            and toiture.origine_lng is not None:
        pin = {'lat': float(toiture.origine_lat),
               'lng': float(toiture.origine_lng)}
        pin_de_la_toiture = True
    elif appel_offre.site_gps_lat is not None \
            and appel_offre.site_gps_lng is not None:
        pin = {'lat': float(appel_offre.site_gps_lat),
               'lng': float(appel_offre.site_gps_lng)}

    layout = appel_offre.roof_layout \
        if isinstance(appel_offre.roof_layout, dict) else None
    if layout:
        source = 'affaire'
    elif outline or pin_de_la_toiture:
        # ``'toiture'`` dès que la géométrie servie VIENT de la toiture — y
        # compris quand seule son ANCRE existe (relevé GPS posé, plan pas
        # encore tracé) : l'étiquette dit d'où sort le point affiché, et le
        # point affiché est alors celui de la toiture, pas le GPS du site.
        source = 'toiture'
    elif pin:
        source = 'site'
    else:
        source = 'none'

    # ── Cible : ce que les variantes RETENUES engagent aujourd'hui ──
    synthese = synthese_calepinage_affaire(appel_offre, company=societe)
    panneaux = int(synthese['total_modules'] or 0)
    kwc = float(synthese['total_kwc'] or 0.0)
    if not panneaux:
        panneaux = int(appel_offre.engagement_modules_batiments
                       or appel_offre.engagement_modules or 0)
    # Le wattage n'est JAMAIS saisi côté AO : il se DÉRIVE du couple
    # modules/puissance des variantes retenues, et vaut 0 tant que l'un des
    # deux manque (une valeur par défaut inventée fausserait le calepinage).
    panel_watt = int(round(kwc * 1000.0 / panneaux)) if (panneaux and kwc) else 0

    avertissements = []
    if toiture is None:
        avertissements.append(
            'Aucune toiture relevée sur cette affaire : commencez par relever '
            'une toiture.')
    elif not outline:
        # ``_contour_en_degres`` rend ``[]`` dans DEUX cas qui n'appellent PAS
        # le même geste : contour non tracé, ou ancre géographique absente.
        # Les confondre envoyait l'utilisateur re-saisir une ancre déjà posée.
        nom_toiture = (toiture.code_document or toiture.designation
                       or f'#{toiture.pk}')
        if not toiture.contour_local_m:
            avertissements.append(
                'La toiture « %s » n\'a aucun contour relevé : il n\'y a rien '
                'à reprojeter sur la carte. Tracez son contour.' % nom_toiture)
        else:
            avertissements.append(
                'La toiture « %s » n\'a aucune ancre géographique : son '
                'contour ne peut pas être reprojeté sur la carte.'
                % nom_toiture)
    if source == 'none':
        avertissements.append(
            'Aucune géométrie connue pour cette affaire : commencez par situer '
            'le site sur la carte.')

    raison = raison_conception_figee(appel_offre)

    return {
        'affaire': {
            'id': appel_offre.pk,
            'reference': appel_offre.reference,
            'reference_acheteur': appel_offre.reference_acheteur or '',
            'statut': appel_offre.statut,
            'objet': appel_offre.objet or '',
            'acheteur': appel_offre.acheteur or '',
            'maitre_ouvrage': appel_offre.maitre_ouvrage or '',
        },
        'geometrie': {
            'source': source,
            'roof_layout': layout,
            'pin': pin,
            'outline': outline,
            'toiture': _toiture_vers_contexte(toiture),
        },
        'cible': {
            'panneaux': panneaux,
            'kwc': round(kwc, 3),
            'panel_watt': panel_watt,
            'scenario': '',
            'batterie': False,
            'surface_m2': str(appel_offre.surface_toitures_m2),
        },
        'carte': _config_carte_builder(),
        'modifiable': not raison,
        'raison_lecture_seule': raison,
        'avertissements': avertissements,
    }
