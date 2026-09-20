"""NTI18N51 — détection des traductions manquantes en production.

Quand le glossaire (NTI18N25) n'a pas la variante demandée, le libellé replie
sur le français et le document part : correct, mais SILENCIEUX. Ce module
enregistre le repli dans un COMPTEUR (``TraductionManquante``) que la tâche
hebdomadaire de ``scheduled.py`` transforme en UNE notification groupée.

DEUX GARANTIES QUI FONT TOUT L'INTÉRÊT :

  * jamais une ligne de journal par requête. Un libellé de statut est un chemin
    chaud (chaque liste en affiche des dizaines) : une trace par appel noierait
    le journal sans rien dire de plus qu'un compteur. Ici, un repli = un
    ``UPDATE`` d'une ligne, et ZÉRO écriture quand la traduction existe — donc
    zéro coût sur une installation dont le glossaire est complet, qui est l'état
    du dépôt aujourd'hui ;
  * jamais une exception qui remonte. Une panne du compteur ne doit pas casser
    l'affichage d'un statut, encore moins un rendu PDF.

L'incrément passe par ``F()`` (jamais lire-puis-écrire) : deux workers qui
constatent le même manque en même temps comptent bien deux occurrences.
"""
import logging

logger = logging.getLogger(__name__)

#: Préfixe des clés de glossaire des statuts métier — la clé enregistrée porte
#: son domaine pour rester lisible dans la notification
#: (``statuts.devis.brouillon``).
PREFIXE_STATUTS = 'statuts'

#: Langue source du glossaire : replier du FR sur le FR n'est pas un manque.
LANGUE_SOURCE = 'fr'


def cle_statut(domaine: str, cle: str) -> str:
    """Clé de compteur d'un statut métier (domaine inclus)."""
    return f'{PREFIXE_STATUTS}.{domaine}.{cle}'


def enregistrer_repli(company, langue: str, cle: str) -> bool:
    """Compte un repli FR pour ``(company, langue, cle)``.

    Renvoie ``True`` quand une occurrence a bien été comptée. Ne fait rien (et
    renvoie ``False``) sans société, sans clé, ou pour la langue source — et
    n'élève JAMAIS : l'appelant est un chemin d'affichage.
    """
    if company is None or not cle:
        return False
    langue = (langue or '').strip()
    if not langue or langue == LANGUE_SOURCE:
        return False
    try:
        from django.db.models import F
        from django.utils import timezone

        from .models_translations import TraductionManquante

        maintenant = timezone.now()
        touchees = TraductionManquante.objects.filter(
            company=company, langue=langue, cle=cle).update(
                occurrences=F('occurrences') + 1, updated_at=maintenant)
        if not touchees:
            TraductionManquante.objects.get_or_create(
                company=company, langue=langue, cle=cle,
                defaults={'occurrences': 1})
        return True
    except Exception:  # noqa: BLE001 — jamais bloquant pour un affichage
        logger.debug('enregistrer_repli: compteur i18n indisponible',
                     exc_info=True)
        return False


def cles_a_notifier(company, limite=10):
    """Clés manquantes NON ENCORE rapportées, la plus fréquente en tête.

    Le classement porte sur le DELTA de la période (``occurrences`` moins
    ``occurrences_notifiees``), pas sur le total cumulé : une clé signalée le
    mois dernier et appelée deux fois cette semaine ne doit pas devancer une
    clé toute neuve appelée cinquante fois.
    """
    from django.db.models import F

    from .models_translations import TraductionManquante

    if company is None:
        return []
    qs = (TraductionManquante.objects
          .filter(company=company,
                  occurrences__gt=F('occurrences_notifiees'))
          .annotate(nouvelles=F('occurrences') - F('occurrences_notifiees'))
          .order_by('-nouvelles', 'langue', 'cle'))
    return list(qs[:limite])


def marquer_notifiees(lignes):
    """Aligne ``occurrences_notifiees`` sur ``occurrences`` pour ``lignes``.

    Relu depuis la base au moment de l'écriture (jamais la valeur mémorisée
    avant l'envoi) : les occurrences arrivées PENDANT l'envoi restent donc à
    rapporter la semaine suivante au lieu d'être perdues.
    """
    from django.db.models import F

    from .models_translations import TraductionManquante

    ids = [ligne.pk for ligne in lignes]
    if not ids:
        return 0
    return TraductionManquante.objects.filter(id__in=ids).update(
        occurrences_notifiees=F('occurrences'))
