"""NTI18N52 — sélecteur dédié des deux KPI i18n de ``reporting.KpiAlerte``.

Même patron que ``p2p_kpi.py`` / ``technicien_scorecard.py`` : ce module AGRÈGE
et n'importe aucun modèle métier — il lit ce qui existe déjà et rend ``None``
plutôt qu'un chiffre approché quand la donnée n'existe pas.

``couverture_i18n_pct`` — part des composants de page de l'interface migrés
vers le cadre i18n (useI18n/useT). Source : le DERNIER
``core.I18nCoverageSnapshot`` de la société, produit par le job Beat
hebdomadaire NTI18N39. Aucun recomptage ici : le chiffre est celui que
``scripts/extract_i18n_strings.py`` a mesuré. ``None`` tant qu'aucun
instantané n'existe (job jamais passé, ou passé sans mesure exploitable) —
jamais 0, qui affirmerait « aucun écran migré » alors que la vérité est
« pas encore mesuré ».

``documents_non_fr_pct`` — **VOLONTAIREMENT ``None``, et voici pourquoi.** La
tâche prévoyait de le calculer « depuis les logs d'activité ``DevisActivity``
existants ». Vérification faite dans le code :

  * ``ventes.DevisActivity.Kind`` ne contient que ``creation`` /
    ``modification`` / ``note`` — AUCUN évènement « PDF généré » ;
  * aucun helper de ``apps/ventes/activity.py`` ne journalise une génération
    de document, et ``/proposal`` (``apps/ventes/views/devis.py``) n'en écrit
    aucun : il rend le PDF et le diffuse ;
  * la langue de sortie est RÉSOLUE au rendu
    (``apps.parametres.i18n_resolver.resolve_langue_sortie``) puis passée au
    moteur — elle n'est PERSISTÉE nulle part.

Il n'existe donc, à ce jour, aucune trace de la langue d'un PDF généré. Le KPI
rend ``None`` (donc aucun franchissement de seuil, aucune notification, tuile
masquée) au lieu d'un substitut trompeur : compter les clients dont
``langue_document != 'fr'`` mesurerait une PRÉFÉRENCE client, pas des documents
RÉELLEMENT produits dans cette langue, et l'afficher sous ce libellé serait un
chiffre inventé.

MOITIÉ MANQUANTE À CONSTRUIRE (hors périmètre de cette lane, ``apps/ventes``) :
journaliser la langue à la génération — une activité ``DevisActivity`` (ou un
champ dédié) écrite par ``/proposal`` avec la ``langue_sortie`` déjà résolue.
Ce KPI se branchera dessus sans rien changer ici, dès que la trace existe.
"""

CLE_COUVERTURE = 'couverture_i18n_pct'
CLE_DOCUMENTS_NON_FR = 'documents_non_fr_pct'

# Motif lisible rendu à côté du KPI absent (jamais un silence, jamais un 0).
RAISON_DOCUMENTS_NON_FR = (
    "Aucune trace de la langue d'un PDF généré n'existe en base : "
    "`/proposal` résout la langue au rendu sans la journaliser, et "
    "`DevisActivity` n'a pas d'évènement « document généré ». Le KPI restera "
    'absent jusqu\'à ce que la génération écrive cette trace (apps/ventes).'
)


def couverture_i18n_pct(company):
    """Dernière couverture i18n mesurée pour la société, ou ``None``.

    UNE seule requête (dernier instantané par ``-semaine``), quel que soit le
    nombre de devis de la société : ce KPI ne lit aucun devis.
    """
    from core.models import I18nCoverageSnapshot

    valeur = (I18nCoverageSnapshot.objects
              .filter(company=company)
              .order_by('-semaine')
              .values_list('couverture_pct', flat=True)
              .first())
    return valeur


def documents_non_fr_pct(company):  # noqa: ARG001 — signature homogène
    """Toujours ``None`` : la donnée source n'existe pas (voir le docstring).

    ZÉRO requête — on ne va pas chercher un chiffre qu'aucune table ne porte.
    """
    return None


def kpis_i18n(company):
    """Les deux KPI i18n en un appel, forme homogène avec ``kpis_btp``/
    ``kpis_juridiques`` : un dict clé → valeur (``None`` = non mesurable)."""
    return {
        CLE_COUVERTURE: couverture_i18n_pct(company),
        CLE_DOCUMENTS_NON_FR: documents_non_fr_pct(company),
    }
