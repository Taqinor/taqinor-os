"""Beats de l'app ``parametres`` — hygiène des données de traduction.

Autodécouvert par ``erp_agentique.celery`` : le nom de module ``scheduled``
fait partie des ``related_name`` explicitement ré-explorés depuis l'incident
prod du 14/09/2026 (une tâche planifiée hors ``tasks.py`` n'était jamais
importée par le worker). Chaque tâche ajoutée ici doit donc AUSSI recevoir son
entrée ``beat_schedule`` et sa route ``scheduled`` — la garde
``core/tests/test_celery_task_routes.py`` refuse toute divergence.

NTI18N38 — purge mensuelle des traductions de CONTENU orphelines.

``core.models.ContentTranslation`` (YHARD4) désigne sa cible par
``content_type`` + ``object_id`` (contenttypes), PAS par une ForeignKey : la
suppression de l'objet source n'emporte donc RIEN. Une désignation produit
traduite en arabe survit indéfiniment à la suppression du produit — volume
mort, et surtout une donnée de contenu (texte saisi par un humain) conservée
au-delà de la vie de son objet, ce que la rétention ne couvre pas.

``parametres.TranslationOverride`` (N94) est hors de cette purge, et ce n'est
pas un oubli : ce modèle ne porte AUCUN pointeur d'objet — ses colonnes sont
``(company, locale, key, value)`` et ``key`` est une clé i18n d'INTERFACE
(``nav.stock``) dont le catalogue vit côté frontend, où le serveur n'impose
volontairement aucune liste blanche (cf. la docstring de
``models_translations``). Il n'existe donc pas de « source supprimée » à
détecter pour ces lignes ; les supprimer sur un autre critère effacerait du
texte saisi par le tenant. Un test garde cette frontière explicitement.

Multi-tenant : boucle par société active (jamais une company lue d'un corps de
requête). Best-effort de bout en bout — une société ou un content type en
échec n'empêche jamais les suivants.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _ids_existants(model, ids_bruts):
    """Sous-ensemble de ``ids_bruts`` (chaînes) qui désigne une ligne VIVANTE.

    ``ContentTranslation.object_id`` est une ``CharField`` : un id qui ne se
    convertit pas au type de la clé primaire du modèle cible ne peut désigner
    aucune ligne (il est donc orphelin), mais il ne doit jamais faire échouer
    la requête d'existence — on l'écarte avant le filtre.
    """
    champ_pk = model._meta.pk
    convertibles = {}
    for brut in ids_bruts:
        try:
            convertibles[champ_pk.to_python(brut)] = brut
        except Exception:  # noqa: BLE001 — id non convertible = orphelin
            continue
    if not convertibles:
        return set()
    vivants = model._default_manager.filter(
        pk__in=list(convertibles.keys())).values_list('pk', flat=True)
    return {convertibles[pk] for pk in vivants if pk in convertibles}


def _orphelines_de_la_societe(company):
    """Pks des ``ContentTranslation`` de ``company`` dont la cible a disparu.

    Un seul parcours par content type (jamais une requête par ligne) : les
    ids distincts du content type sont testés en UN filtre d'existence. Un
    content type dont le MODÈLE n'existe plus dans le code (app retirée) rend
    toutes ses lignes orphelines.
    """
    from django.contrib.contenttypes.models import ContentType

    from core.models import ContentTranslation

    lignes = ContentTranslation.objects.filter(company=company).values_list(
        'id', 'content_type_id', 'object_id')
    par_content_type = {}
    for pk, ct_id, object_id in lignes:
        par_content_type.setdefault(ct_id, {}).setdefault(
            object_id, []).append(pk)

    orphelines = []
    for ct_id, par_objet in par_content_type.items():
        try:
            modele = ContentType.objects.get_for_id(ct_id).model_class()
        except Exception:  # noqa: BLE001 — content type introuvable
            modele = None
        if modele is None:
            for pks in par_objet.values():
                orphelines.extend(pks)
            continue
        try:
            vivants = _ids_existants(modele, par_objet.keys())
        except Exception:  # noqa: BLE001 — jamais bloquant pour les suivants
            logger.warning(
                'purger_traductions_orphelines: content type %s illisible '
                'pour la société %s', ct_id, getattr(company, 'id', None),
                exc_info=True)
            continue
        for object_id, pks in par_objet.items():
            if object_id not in vivants:
                orphelines.extend(pks)
    return orphelines


def _journaliser(company, supprimees):
    """Trace la purge dans le journal d'activité (``audit.AuditLog``).

    Action système (``user=None``) : le purgeur n'a pas d'acteur humain.
    Best-effort — ``recorder.record`` ne lève jamais.
    """
    from apps.audit.models import AuditLog
    from apps.audit.recorder import record

    record(
        AuditLog.Action.DELETE,
        company=company,
        user=None,
        actor_username='beat',
        object_repr='Traductions de contenu orphelines',
        detail=f'NTI18N38 — {supprimees} traduction(s) de contenu '
               'orpheline(s) purgée(s) (objet source supprimé).',
    )


@shared_task(name='parametres.purger_traductions_orphelines')
def purger_traductions_orphelines():
    """NTI18N38 — supprime les ``ContentTranslation`` sans objet source.

    Renvoie ``{'societes': n, 'supprimees': m}``. Aucune société n'est
    journalisée quand elle n'avait rien à purger (pas de ligne d'audit vide
    chaque mois).
    """
    from authentication.selectors import active_companies

    from core.models import ContentTranslation

    societes = 0
    total = 0
    for company in active_companies():
        societes += 1
        try:
            pks = _orphelines_de_la_societe(company)
        except Exception:  # noqa: BLE001 — une société en échec n'arrête rien
            logger.warning(
                'purger_traductions_orphelines: société %s ignorée',
                getattr(company, 'id', None), exc_info=True)
            continue
        if not pks:
            continue
        supprimees = ContentTranslation.objects.filter(id__in=pks).delete()[0]
        total += supprimees
        if supprimees:
            _journaliser(company, supprimees)
    return {'societes': societes, 'supprimees': total}
