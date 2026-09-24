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

CALX368 — ``calepinage.simule`` : UNE SIMULATION VIENT D'ABOUTIR
-----------------------------------------------------------------
Le service d'orchestration (``apps.calepinage.services.simulation``, le seul
chemin qui lance une simulation) émet ``core.events.calepinage_simule`` APRÈS
avoir fusionné le résultat dans ``Calepinage.resultat`` — jamais pour un « déjà
calculé », un refus ou un calcul à blanc. Ce module s'y abonne et livre le
webhook ``calepinage.simule``. Le modèle émetteur est résolu PAR LE REGISTRE
(il sert de ``sender``) : toujours aucun import ``apps.calepinage`` ->
``apps.publicapi``, et une installation sans le module calepinage ne branche
rien du tout.

La charge utile (:func:`charge_utile_simulation`) reprend UNIQUEMENT des clés
déjà publiées par ``PublicCalepinageSerializer`` (CAL214), plus ``p50_kwh`` et
``performance_ratio`` lus du résultat RÉELLEMENT calculé
(``production.total`` du contrat ``calepinage_simulation.json``) — ``null``
tant que rien n'est calculé, jamais ``0``. Ni géométrie, ni coût.

POURQUOI UN POST SIGNÉ, ET PAS LE GET D'AURORA
-----------------------------------------------
Aurora livre ses webhooks en requêtes GET sans corps : selon sa propre
checklist d'intégration CRM
(https://help.aurorasolar.com/hc/en-us/articles/17426531448083-CRM-Checklist-for-Aurora-API-Integrations),
« the UUIDs and values are included in the query string of the URL
template ». Nous ne le suivons PAS : une valeur portée par la chaîne de
requête finit dans les journaux d'accès, les proxys et les historiques de
tous les intermédiaires ; il n'y a aucun corps à signer, donc rien ne prouve
au receveur que les valeurs n'ont pas été altérées ni rejouées. La livraison
passe donc par le socle existant (``delivery.dispatch_event`` →
``tasks.deliver_webhook`` → ``delivery._send``) : un POST JSON dont le corps
est signé HMAC-SHA256 avec son horodatage (``X-Taqinor-Signature-V2:
t=<epoch>,v1=<hex>`` et ``X-Taqinor-Timestamp``), l'URL de l'abonné restant
EXACTEMENT celle qu'il a déclarée — aucune valeur n'y est ajoutée.
"""
import logging

from django.db.models.signals import post_save, pre_save

from .constants import EVENT_CALEPINAGE_SIMULE, EVENT_CALEPINAGE_VALIDE

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


# ── CALX368 — calepinage.simule ─────────────────────────────────────────────

#: Les clés de la charge utile ``calepinage.simule``. Toutes, sauf les deux
#: dernières, sont des champs DÉJÀ publiés par ``PublicCalepinageSerializer``
#: (``apps/publicapi/public_serializers.py``) ; les deux dernières sont lues
#: dans ``resultat['production']['total']``. ``liens`` n'y est pas : un lien
#: présigné d'une heure n'a rien à faire dans un message qui peut être rejoué
#: plus tard, et le calculer ferait appeler le stockage depuis un signal.
CLES_CHARGE_SIMULE = (
    'id', 'titre', 'statut', 'lead_id', 'client_id', 'devis_id',
    'appel_offre_id', 'layout_hash', 'version_moteur', 'kwc', 'modules',
    'p50_kwh', 'performance_ratio',
)


def _calepinage_model():
    """Le modèle ÉMETTEUR, par le REGISTRE — ``None`` sans le module."""
    from django.apps import apps as django_apps
    try:
        return django_apps.get_model('calepinage', 'Calepinage')
    except LookupError:
        return None


def _total_de_production(resultat):
    """``resultat['production']['total']``, TOUJOURS un dict."""
    production = resultat.get('production')
    total = production.get('total') if isinstance(production, dict) else None
    return total if isinstance(total, dict) else {}


def charge_utile_simulation(calepinage):
    """La charge utile de ``calepinage.simule`` — testée clé par clé.

    ``kwc``/``modules`` sont lus EXACTEMENT comme ``PublicCalepinageSerializer``
    les lit (clés ``kwc``/``total_modules`` du résultat du moteur) ;
    ``p50_kwh``/``performance_ratio`` viennent de ``production.total`` écrit
    par la simulation. Tout ce qui n'est pas un nombre réel vaut ``None``.
    """
    resultat = getattr(calepinage, 'resultat', None)
    resultat = resultat if isinstance(resultat, dict) else {}
    total = _total_de_production(resultat)
    return {
        'id': getattr(calepinage, 'pk', None),
        'titre': getattr(calepinage, 'titre', '') or '',
        'statut': getattr(calepinage, 'statut', '') or '',
        'lead_id': getattr(calepinage, 'lead_id', None),
        'client_id': getattr(calepinage, 'client_id', None),
        'devis_id': getattr(calepinage, 'devis_id', None),
        'appel_offre_id': getattr(calepinage, 'appel_offre_id', None),
        'layout_hash': getattr(calepinage, 'layout_hash', '') or '',
        'version_moteur': getattr(calepinage, 'version_moteur', '') or '',
        'kwc': _nombre(resultat.get('kwc')),
        'modules': _entier(resultat.get('total_modules')),
        'p50_kwh': _nombre(total.get('p50_kwh')),
        'performance_ratio': _nombre(total.get('performance_ratio')),
    }


def calepinage_simule_recu(sender, calepinage=None, company_id=None,
                           **kwargs):
    """Abonné de ``core.events.calepinage_simule`` : livre le webhook."""
    if calepinage is None:
        return
    company_id = company_id or getattr(calepinage, 'company_id', None)
    if not company_id:
        return
    from . import delivery
    try:
        delivery.dispatch_event(company_id, EVENT_CALEPINAGE_SIMULE,
                                charge_utile_simulation(calepinage))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception('%s: dispatch webhook échoué (calepinage %s)',
                         EVENT_CALEPINAGE_SIMULE,
                         getattr(calepinage, 'pk', None))


def connecter_simulation():
    """Branche ``calepinage.simule`` — rien si le module est absent."""
    modele = _calepinage_model()
    if modele is None:
        return False
    from core import events
    events.calepinage_simule.connect(
        calepinage_simule_recu, sender=modele,
        dispatch_uid='publicapi_calepinage_simule')
    return True


def connect():
    """Branche le récepteur calepinage. Appelé depuis ``PublicApiConfig.ready()``."""
    modele = _variante_model()
    if modele is None:
        return
    pre_save.connect(variante_pre_save, sender=modele,
                     dispatch_uid='publicapi_calepinage_variante_pre')
    post_save.connect(variante_post_save, sender=modele,
                      dispatch_uid='publicapi_calepinage_valide')
    # CALX368 — la simulation aboutie, sur le bus `core.events`.
    connecter_simulation()
