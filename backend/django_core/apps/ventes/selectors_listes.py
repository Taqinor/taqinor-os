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

    devis_qs = (Devis.objects
                .defer('etude_params')
                .annotate(**{annote: _extrait(chemin)
                             for chemin, annote in ANNOTATION_PAR_CLE.items()}))
    return (
        Prefetch(prefixe, queryset=devis_qs),
        f'{prefixe}__lignes__produit',
        f'{prefixe}__superseded_by',
    )
