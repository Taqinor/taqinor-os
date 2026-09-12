"""NTDATA42 — DÉTECTION D'ANOMALIE sur les séries de métriques (job Beat).

LE PROBLÈME QU'IL RÈGLE. Une alerte de seuil (XPLT6/NTDATA13/NTDATA41) exige
qu'on ait D'ABORD deviné le bon nombre : « alerte si le CA passe sous 200 000 ».
Personne ne connaît ce nombre pour chacune des dizaines de métriques d'une
société — donc personne ne configure, donc « le CA anormalement bas en mars »
n'est vu qu'au moment où quelqu'un ouvre le bon écran.

CE QUE CE JOB FAIT. Pour chaque métrique ACTIVE de chaque société
OPÉRATIONNELLE, il calcule la série mensuelle (``semantic.selectors``) et
demande au scorer EXISTANT (``core.anomaly.scan_for_outliers``, z-score) quels
points s'écartent de leur propre habitude. Chaque point aberrant devient un
``core.AnomalyFlag`` — la table générique déjà utilisée par les autres
détections du dépôt, jamais une seconde.

AUCUN SEUIL À CONFIGURER, ET AUCUN FAUX POSITIF PAR CONSTRUCTION. Le z-score
d'un point d'une série de ``n`` valeurs ne peut pas dépasser
``(n - 1) / √n`` — c'est une borne arithmétique, pas un réglage. Avec
:data:`SEUIL_Z` = 2,5 il faut donc AU MOINS 9 périodes complètes pour qu'un
signalement soit seulement POSSIBLE : une métrique jeune ne peut pas produire
d'anomalie, quoi qu'il arrive dans ses chiffres. C'est voulu — trois mois de
données ne permettent pas de dire ce qui est « habituel ».

CE QU'IL NE FAIT PAS. Il ne notifie personne (un ``AnomalyFlag`` se consulte),
ne modifie aucune donnée métier, et n'invente aucune valeur : une période sans
valeur est OMISE de la série (``SUM`` d'un ensemble vide vaut ``NULL`` — un
mois sans facture n'est pas « 0 MAD mesuré »), et la période EN COURS est
exclue (elle est incomplète par construction).
"""
import logging

logger = logging.getLogger(__name__)

#: Écarts-types au-delà desquels un point est signalé. 2,5 : au-dessus, la
#: borne ``(n-1)/√n`` repousserait le premier signalement possible à 12
#: périodes ; en dessous, une série courte produirait du bruit.
SEUIL_Z = 2.5

#: Longueur MINIMALE de série exploitable. Sous 6 points, « l'habitude » n'est
#: pas une notion : on ne distingue pas un point aberrant d'une tendance.
MIN_POINTS = 6

#: Type de sujet des signalements (chaîne générique — ``core`` n'importe aucune
#: app, et ``AnomalyFlag`` ne porte donc pas de FK métier).
SUBJECT_TYPE = 'semantic.MetricDefinition'


def _periode_iso(valeur):
    """``AAAA-MM`` d'une borne de période (les séries sont mensuelles)."""
    import datetime

    if isinstance(valeur, (datetime.datetime, datetime.date)):
        return '%04d-%02d' % (valeur.year, valeur.month)
    return str(valeur or '')[:7]


def detecter_anomalies_metriques(company=None):
    """Signale les points aberrants des métriques. Renvoie un récapitulatif.

    ``company`` restreint à une société (recalcul ciblé) ; sinon toutes les
    sociétés OPÉRATIONNELLES sont balayées. Chaque société et chaque métrique
    sont ISOLÉES : une erreur sur l'une n'interrompt jamais les suivantes.

    ``user=None`` est transmis délibérément au résolveur : un job n'a pas
    d'acteur, donc aucun champ sous permission (AUD801) ne lui est lisible —
    une métrique posée sur un champ gated ne mesure alors rien, ce qui est le
    bon défaut pour une tâche planifiée.
    """
    from authentication.selectors import active_companies
    from core.anomaly import record_outliers, scan_for_outliers

    from . import selectors as semantic_selectors
    from .models import MetricDefinition

    societes = [company] if company is not None else list(active_companies())
    recap = []
    for societe in societes:
        nb_flags = 0
        definitions = MetricDefinition.objects.filter(
            company=societe, actif=True).order_by('cle')
        for definition in definitions:
            try:
                points = semantic_selectors.periodes_completes(
                    semantic_selectors.serie_temporelle(
                        societe, None, definition.cle))
            except Exception:  # noqa: BLE001 — une métrique ne bloque pas le reste
                logger.exception(
                    'NTDATA42 : série indisponible pour « %s » (société %s)',
                    definition.cle, societe.pk)
                continue
            if len(points) < MIN_POINTS:
                continue
            libelle = definition.libelle or definition.cle
            serie = [
                {
                    # L'identité d'un signalement = LA MÉTRIQUE ET LA PÉRIODE :
                    # deux mois aberrants de la même métrique sont deux faits
                    # distincts, pas un doublon à écraser.
                    'id': '%s:%s' % (definition.pk,
                                     _periode_iso(point['periode'])),
                    'value': point['valeur'],
                    'label': '%s en %s' % (
                        libelle, _periode_iso(point['periode'])),
                    'metrique': definition.cle,
                    'periode': _periode_iso(point['periode']),
                }
                for point in points
            ]
            candidats = scan_for_outliers(
                serie, z_threshold=SEUIL_Z, min_points=MIN_POINTS)
            if not candidats:
                continue
            try:
                flags = record_outliers(
                    candidats, company=societe,
                    subject_type=SUBJECT_TYPE, metric=definition.cle[:80])
            except Exception:  # noqa: BLE001 — défensif par métrique
                logger.exception(
                    'NTDATA42 : signalement impossible pour « %s » '
                    '(société %s)', definition.cle, societe.pk)
                continue
            nb_flags += len(flags)
        recap.append({'company': societe.pk, 'nb_anomalies': nb_flags})
    return recap


try:
    from celery import shared_task

    @shared_task(name='semantic.detecter_anomalies_metriques')
    def detecter_anomalies_metriques_task():
        """Tâche Beat hebdomadaire (NTDATA42)."""
        detecter_anomalies_metriques()
except ImportError:  # pragma: no cover - celery absent en environnement nu
    pass
