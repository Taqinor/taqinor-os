"""CAL215 — abonné ``apps.publicapi`` à la VALIDATION d'un calepinage :
retenir une variante (``CalepinageVariante.retenue`` passe à vrai) livre le
webhook sortant ``calepinage.valide`` (``delivery.dispatch_event``, MÊME
transport signé que tous les autres webhooks, aucun nouveau mécanisme).

POURQUOI UN RÉCEPTEUR, ET DANS CE SENS-LÀ
------------------------------------------
Le module calepinage ne connaît pas l'API publique et ne doit pas
l'apprendre : il n'y a donc AUCUN import ``apps.calepinage`` ->
``apps.publicapi``. C'est ``publicapi`` qui écoute, exactement comme
``signals.py`` écoute déjà lead/devis/facture/chantier/ticket, et comme
``btp_event_receivers``/``scm_event_receivers`` écoutent le bus
``core.events``. Le modèle écouté est résolu PAR LE REGISTRE
(``apps.get_model``), pas par un import statique : la frontière inter-apps
(lecture d'``apps.calepinage`` par son ``selectors.py``) reste entière, et une
installation sans le module calepinage ne branche simplement rien.

CE QUI EST LIVRÉ — ET CE QUI NE L'EST JAMAIS
---------------------------------------------
La charge utile dit QUELLE variante a été retenue et CE QU'ELLE PÈSE
(``kwc``/``modules``, lus du résultat réellement calculé par le moteur —
``null`` tant que rien n'a été calculé, jamais ``0``). Elle ne porte NI
géométrie brute (``roof_layout``, plans/rangées) NI aucun coût interne :
mêmes limites que ``PublicCalepinageSerializer`` (CAL214).

QUAND — UNE TRANSITION, PAS UNE COPIE
--------------------------------------
L'évènement marque le GESTE « cette variante-là est la bonne » : une variante
existante qui passe à retenue. Une variante CRÉÉE déjà retenue est une copie
(``services.variantes.dupliquer`` recopie le drapeau de l'original) — le choix
a été fait ailleurs, et un duplicata ne re-notifie donc pas l'intégration.
``creer_variante(retenir=True)`` reste couvert : il crée à faux puis bascule
par le service, ce qui EST la transition.
"""
import logging

from django.db.models.signals import post_save, pre_save

from .constants import EVENT_CALEPINAGE_VALIDE

logger = logging.getLogger(__name__)

# Attribut transitoire portant l'ancienne valeur de `retenue` entre pre_save et
# post_save (même patron que `_OLD_STATUT_ATTR` dans `signals.py`).
_OLD_RETENUE_ATTR = '_publicapi_old_retenue'


def _variante_model():
    """Le modèle écouté, par le REGISTRE — jamais un import statique.

    Renvoie ``None`` si le module calepinage n'est pas installé : il n'y a
    alors rien à brancher, et surtout aucun ``ImportError`` au démarrage.
    """
    from django.apps import apps as django_apps
    try:
        return django_apps.get_model('calepinage', 'CalepinageVariante')
    except LookupError:
        return None


def variante_pre_save(sender, instance, **kwargs):
    """Mémorise sur l'instance la valeur de ``retenue`` actuellement en base."""
    if not instance.pk:
        setattr(instance, _OLD_RETENUE_ATTR, None)
        return
    try:
        ancienne = sender.objects.filter(pk=instance.pk).values_list(
            'retenue', flat=True).first()
    except Exception:  # noqa: BLE001 — jamais bloquant pour la sauvegarde
        ancienne = None
    setattr(instance, _OLD_RETENUE_ATTR, ancienne)


def variante_post_save(sender, instance, created=False, **kwargs):
    if created or not getattr(instance, 'retenue', False):
        return
    if getattr(instance, _OLD_RETENUE_ATTR, None) is True:
        return  # déjà retenue avant cette sauvegarde : aucune transition
    _livrer(instance)


def _livrer(variante):
    """Livraison best-effort : un webhook ne casse jamais le geste métier."""
    company_id = getattr(variante, 'company_id', None)
    if not company_id:
        return
    from . import delivery
    try:
        delivery.dispatch_event(company_id, EVENT_CALEPINAGE_VALIDE,
                                charge_utile(variante))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception('%s: dispatch webhook échoué (variante %s)',
                         EVENT_CALEPINAGE_VALIDE, getattr(variante, 'pk', None))


def charge_utile(variante):
    """La charge utile publiée — testée clé par clé (`tests_cal215_…`)."""
    resultat = getattr(variante, 'resultat', None)
    resultat = resultat if isinstance(resultat, dict) else {}
    return {
        'calepinage_id': getattr(variante, 'calepinage_id', None),
        'variante_id': getattr(variante, 'pk', None),
        'nom': getattr(variante, 'nom', '') or '',
        'layout_hash': getattr(variante, 'layout_hash', '') or '',
        'kwc': _nombre(resultat.get('kwc')),
        'modules': _entier(resultat.get('total_modules')),
    }


def _nombre(valeur):
    """Un nombre RÉEL, ou ``None`` — jamais une valeur inventée, jamais 0."""
    if valeur is None or isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return None


def _entier(valeur):
    nombre = _nombre(valeur)
    return int(nombre) if nombre is not None else None


def connect():
    """Branche le récepteur calepinage. Appelé depuis ``PublicApiConfig.ready()``."""
    modele = _variante_model()
    if modele is None:
        return
    pre_save.connect(variante_pre_save, sender=modele,
                     dispatch_uid='publicapi_calepinage_variante_pre')
    post_save.connect(variante_post_save, sender=modele,
                      dispatch_uid='publicapi_calepinage_valide')
