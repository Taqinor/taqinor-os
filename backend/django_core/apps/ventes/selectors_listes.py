"""AOOM1 — sélecteurs LECTURE SEULE de PRÉCHARGEMENT, pour les LISTES d'autres
apps qui sérialisent des devis.

Même famille que ``selectors_cadence`` / ``selectors_facturation`` : une surface
de lecture cross-app exposée par ``ventes``, que ``crm`` appelle sans jamais
importer ``apps.ventes.models`` (frontière M3).

Pourquoi un module à part et non ``selectors.py`` : ce dernier est un FICHIER
MUR de 2 079 lignes, dont la garde C20 (``scripts/check_forme_code.py``)
interdit la croissance — budget 0 ligne nette.
"""
from __future__ import annotations


def prefetch_devis_liste_leads(prefixe='devis'):
    """AOOM1 — LE préchargement des devis d'une LISTE de leads, SANS leur
    ``etude_params``.

    Rend le tuple à passer tel quel à ``prefetch_related(*…)`` depuis
    ``apps.crm`` : les devis, leurs lignes AVEC produit (ERR-PERF-CRM-N1 : la
    garde de cache de ``lignes_avec_produit`` n'économise la requête que si
    chaque ligne porte DÉJÀ son produit) et le successeur d'une V1 remplacée
    (``devis_modifiabilite`` lit ``superseded_by.reference``).

    CE QUI CHANGE (incident du 02/11/2026, mesuré sur la copie anonymisée de
    la production) : les devis arrivent ``defer('etude_params')`` + les seuls
    chemins que la liste lit (``scenario``, ``nombre_proprietes``,
    ``resync_apres_envoi.date``) ANNOTÉS en SQL —
    :data:`~apps.ventes.utils.annotations_devis.ANNOTATION_PAR_CLE` en est
    l'unique table. Les 225 devis d'une page de 200 leads portaient 39,3 Mio
    de JSON ``etude_params`` (jusqu'à 1,45 Mio pour un seul devis : l'étude
    horaire C&I), décodés en ~123 Mio d'objets Python à CHAQUE requête pour
    lire ces trois chemins — +254 Mio de RSS définitifs par worker, 3 Gio de
    conteneur saturés, 17 workers tués par le noyau dans la journée.

    Aucun montant ne change : les lecteurs passent tous par
    ``utils.annotations_devis.cle_etude``, qui rend la même valeur ET le même
    type. Un lecteur d'un chemin NON annoté coûterait une requête PAR DEVIS
    (champ déferré) — le budget de requêtes de
    ``apps/crm/tests_perf_n1_leads.py`` rougit alors, il ne se tait pas.
    """
    from django.db.models import Prefetch

    return (
        Prefetch(prefixe, queryset=_devis_sans_etude()),
        f'{prefixe}__lignes__produit',
        f'{prefixe}__superseded_by',
    )


def prefetch_devis_resume(prefixe='devis'):
    """ACVI94 — le préchargement RÉSUMÉ des devis d'une liste de leads (cockpit,
    objectifs, attribution) : statut, dates et montants sans le JSON d'étude.

    Les chemins de ``ANNOTATION_PAR_CLE`` restent annotés : ``total_ttc`` lit
    ``scenario`` et ``nombre_proprietes`` par ``cle_etude`` ; sans eux, chaque
    lecture de montant rechargerait la colonne déferrée, devis par devis."""
    from django.db.models import Prefetch

    return (Prefetch(prefixe, queryset=_devis_sans_etude()),)


def _devis_sans_etude():
    """Les devis ``defer('etude_params')`` avec ses seuls chemins lus ANNOTÉS."""
    from django.db.models.fields.json import KeyTransform

    from .models import Devis
    from .utils.annotations_devis import ANNOTATION_PAR_CLE

    def _extrait(chemin):
        """``etude_params -> … -> derniere_cle`` pour un chemin imbriqué.

        ``->`` (``KeyTransform``) à TOUS les niveaux, jamais ``->>`` : le
        résultat reste du jsonb, que Django redécode — un entier revient
        ``int``, une chaîne ``str``, comme la lecture du JSON. ``->>``
        ramènerait tout en texte et ``nombre_proprietes`` stocké ``3.0``
        deviendrait ``int('3.0')`` → ValueError → 1 villa : un TOTAL FAUX.
        """
        cles = (chemin,) if isinstance(chemin, str) else tuple(chemin)
        expression = 'etude_params'
        for cle in cles:
            expression = KeyTransform(cle, expression)
        return expression

    return (Devis.objects
            .defer('etude_params')
            .annotate(**{annote: _extrait(chemin)
                         for chemin, annote in ANNOTATION_PAR_CLE.items()}))


# ---------------------------------------------------------------------------
# T4-X4-005 — la liste des devis (``/ventes/devis``) paginée PAR LE SERVEUR :
# l'écran chargeait TOUS les devis (590 pour un responsable ≈ 48 Mo) pour
# filtrer, chercher et compter dans le navigateur. Les filtres et la synthèse
# de l'en-tête sont calculés ici, sur la portée déjà bornée par la vue.
# ---------------------------------------------------------------------------
#: Statuts effectifs de la liste : le statut stocké, sauf qu'un devis en
#: attente dont la validité est passée se lit « expire » (T7, ``utils.expiry``).
STATUTS_EFFECTIFS = ('brouillon', 'envoye', 'accepte', 'refuse', 'expire')


def filtrer_liste_devis(qs, company, *, q=None, statut_effectif=None,
                        actifs=False, auteurs=None):
    """Recherche (référence ou nom du client), statut effectif, versions
    remplacées masquées, auteurs — les mêmes règles que l'écran appliquait
    aux devis chargés, appliquées en SQL."""
    from django.db.models import Q
    from django.utils import timezone

    from .utils.expiry import q_expire_a_la_volee

    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(client__nom__icontains=q))
    if statut_effectif:
        expire = q_expire_a_la_volee(company, timezone.localdate())
        if statut_effectif == 'expire':
            qs = qs.filter(Q(statut='expire') | expire)
        elif statut_effectif in ('brouillon', 'envoye'):
            qs = qs.filter(statut=statut_effectif).exclude(expire)
        else:
            qs = qs.filter(statut=statut_effectif)
    if actifs:
        qs = qs.filter(is_active=True)
    if auteurs:
        qs = qs.filter(created_by_id__in=auteurs)
    return qs


def synthese_liste_devis(qs, company):
    """L'en-tête de la liste sur TOUTE la portée (pas sur la page) : nombre et
    total affiché par statut effectif des devis en jeu, devis à relancer
    (envoyés, validité ≤ 7 jours), option batterie des acceptés, versions
    remplacées. Le total d'argent est ``display_totals`` — le MÊME que la
    colonne « Total TTC » de chaque ligne (``total_affiche``), jamais un
    second calcul ; les devis sont lus par paquets (mémoire bornée)."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from core.money import quantize_mad

    from .quote_engine.builder import display_totals
    from .utils.expiry import is_expired, q_expiration

    jour = timezone.localdate()
    par_statut = {s: {'count': 0, 'total': Decimal('0')} for s in STATUTS_EFFECTIFS}
    en_jeu = (qs.filter(is_active=True).order_by('pk')
              .prefetch_related(None)
              .prefetch_related('lignes', 'lignes__produit',
                                'lignes__produit__fiche_technique'))
    for devis in en_jeu.iterator(chunk_size=50):
        cle = 'expire' if is_expired(devis, today=jour) else devis.statut
        cellule = par_statut.setdefault(cle, {'count': 0, 'total': Decimal('0')})
        cellule['count'] += 1
        cellule['total'] += Decimal(str(display_totals(
            devis, lignes_prechargees=True)['total'] or 0))
    for cellule in par_statut.values():  # une seule règle d'arrondi de l'argent (core.money)
        cellule['total'] = float(quantize_mad(cellule['total']))
    a_relancer = (qs.filter(is_active=True, statut='envoye')
                  .filter(q_expiration(company, apres=jour,
                                       avant=jour + timedelta(days=7)))
                  .values('id', 'reference'))
    acceptes = qs.filter(statut='accepte')
    return {
        'total': qs.count(),
        'remplaces': qs.filter(is_active=False).count(),
        'par_statut': par_statut,
        'a_relancer': [{'id': d['id'], 'reference': d['reference']}
                       for d in a_relancer],
        'batterie': {
            'avec': acceptes.filter(option_acceptee='avec_batterie').count(),
            'sans': acceptes.filter(option_acceptee='sans_batterie').count(),
        },
    }
