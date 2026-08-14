"""NTEXT6 — registre FERMÉ des sources de liste itérables par une boucle.

Une étape ``FOR_EACH`` ne peut PAS désigner un modèle arbitraire : elle nomme
une **clé de source** de ce registre, et seule une source déclarée ici sait
produire une liste. C'est la garde qui empêche une règle éditée depuis l'admin
de transformer le moteur d'automatisation en lecteur universel de la base
(traversée de FK arbitraire, fuite inter-app, fuite de prix d'achat).

Chaque source est une fonction ``(instance, company, argument, context)`` qui
renvoie une **liste de dicts LECTURE SEULE** (jamais des instances de modèle :
une sous-action ne doit pas pouvoir écrire dans l'objet itéré). Les lectures
cross-app passent EXCLUSIVEMENT par les ``selectors.py`` de l'app propriétaire
(CLAUDE.md), jamais par un import de ses ``models``.

Syntaxe de ``source`` : ``'<clé>'`` ou ``'<clé>:<argument>'``
  - ``contexte:<clé>``       → une liste déjà posée dans le contexte par
                               l'émetteur (aucun accès base).
  - ``devis.lignes``         → les lignes du devis déclencheur, via
                               ``ventes.selectors.devis_pour_projet``.
  - ``objet_custom:<code>``  → les enregistrements d'un objet personnalisé de
                               la société (``customfields``, app foundation).
"""
import logging

logger = logging.getLogger(__name__)

#: Borne dure anti-DoS : une boucle n'itère JAMAIS plus que ça, quelle que
#: soit la taille réelle de la liste (la troncature est journalisée).
MAX_ITERATIONS = 200

__all__ = ['MAX_ITERATIONS', 'resolve_list', 'source_keys']


def _source_contexte(instance, company, argument, context):
    """Liste déjà présente dans le contexte (``contexte:lignes``)."""
    if not argument:
        return []
    valeur = (context or {}).get(argument)
    if not isinstance(valeur, (list, tuple)):
        return []
    return [
        item if isinstance(item, dict) else {'valeur': item}
        for item in valeur
    ]


def _source_devis_lignes(instance, company, argument, context):
    """Lignes du devis déclencheur — via le selector ventes, jamais ses modèles.

    ``lignes_devis_pour_automatisation`` ne renvoie que des dicts (désignation,
    quantité, produit lié, total HT) et n'expose AUCUN prix d'achat ni marge.
    Sans devis résolvable, la boucle itère zéro élément (no-op propre) au lieu
    de lever.
    """
    devis_id = argument or getattr(instance, 'pk', None)
    if not devis_id or company is None:
        return []
    try:
        from apps.ventes.selectors import lignes_devis_pour_automatisation
        return lignes_devis_pour_automatisation(
            devis_id, company, limite=MAX_ITERATIONS + 1)
    except Exception:  # pragma: no cover - défensif (app absente/erreur)
        logger.debug('automation: source devis.lignes indisponible',
                     exc_info=True)
        return []


def _source_objet_custom(instance, company, argument, context):
    """Enregistrements d'un objet personnalisé de la société (scopé company)."""
    code = (argument or '').strip()
    if not code or company is None:
        return []
    from apps.customfields.models import CustomObjectDef, CustomRecord
    objet = CustomObjectDef.objects.filter(
        company=company, code=code, actif=True).first()
    if objet is None:
        return []
    records = (CustomRecord.objects
               .filter(company=company, objet=objet)
               .order_by('id')[:MAX_ITERATIONS + 1])
    return [
        {'id': rec.pk, **(rec.data if isinstance(rec.data, dict) else {})}
        for rec in records
    ]


#: Registre FERMÉ (whitelist). Ajouter une source = ajouter une entrée ICI.
SOURCES = {
    'contexte': _source_contexte,
    'devis.lignes': _source_devis_lignes,
    'objet_custom': _source_objet_custom,
}


def source_keys():
    """Clés de source autorisées (pour la validation côté serializer/UI)."""
    return sorted(SOURCES)


def resolve_list(source, instance, company, context=None):
    """Résout ``source`` en ``(liste, tronquee, erreur)``.

    - ``liste``    : au plus :data:`MAX_ITERATIONS` dicts lecture seule ;
    - ``tronquee`` : vrai si la source contenait davantage d'éléments ;
    - ``erreur``   : message FR quand la clé n'est pas whitelistée (la boucle
      est alors journalisée sans effet), sinon ``None``.

    Ne lève jamais : une source en échec renvoie une liste vide.
    """
    raw = (source or '').strip()
    if not raw:
        return [], False, 'Aucune source de liste configurée.'
    cle, _, argument = raw.partition(':')
    cle = cle.strip()
    handler = SOURCES.get(cle)
    if handler is None:
        return [], False, (
            f'Source de liste « {cle} » non autorisée : '
            f'sources permises = {", ".join(source_keys())}.')
    try:
        items = handler(instance, company, argument.strip(), context or {})
    except Exception:  # pragma: no cover - filet de sécurité
        logger.exception('automation: source de liste %s en échec', cle)
        return [], False, None
    items = list(items or [])
    tronquee = len(items) > MAX_ITERATIONS
    return items[:MAX_ITERATIONS], tronquee, None
