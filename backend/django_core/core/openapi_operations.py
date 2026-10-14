"""ENF11 — operationId DISTINCTS sans jamais figer une chaîne d'identifiant.

POURQUOI PAS ``@extend_schema(operation_id=...)``
-------------------------------------------------
``erp_agentique/urls.py`` monte la même liste de routes sous ``api/django/`` ET
sous ``api/v1/`` : drf-spectacular dérive donc pour chaque vue DEUX operationId,
``django_X`` et ``v1_X``. Un ``operation_id`` écrit en dur vaut la même chaîne
sur les deux montages — il CRÉE une collision au lieu d'en retirer une, et le
raccourci WOW-CI3 (``erp_agentique/openapi_check.py``) refuse tout operationId
qui ne commence pas par ``django_``.

Le cas rencontré est toujours le même : deux routes dont les jetons de chemin
sont identiques une fois les variables retirées (``…/mes-devis/`` et
``…/mes-devis/{id}/`` ; ``…/run/`` et ``…/{id}/run/``). drf-spectacular les
baptise toutes deux ``…_retrieve`` (ou ``…_create``) puis les départage par un
suffixe numérique (``_2``) — un nom qui dépend de l'ordre des routes.

CE QUE FAIT CE MODULE
---------------------
``mots_operation(**mots)`` rend un ``AutoSchema`` à poser en attribut
``schema`` de la vue : l'operationId AUTO (préfixe de montage compris) garde
tous ses jetons et seul son DERNIER mot (``retrieve``/``create``…) est remplacé
pour les actions nommées. Clé = l'action du ViewSet (``list``, ``run_adhoc``…)
ou, pour une ``APIView``, la méthode HTTP en minuscules.
Déclaration de schéma UNIQUEMENT : aucune route, aucune réponse servie ne change.
"""
from drf_spectacular.openapi import AutoSchema


class SchemaMotsOperation(AutoSchema):
    """AutoSchema dont le mot final de l'operationId est remplacé par action."""

    #: {action du ViewSet | méthode HTTP en minuscules : nouveau mot final}
    mots: dict = {}

    def get_operation_id(self) -> str:
        operation_id = super().get_operation_id()
        cle = getattr(self.view, 'action', None) or self.method.lower()
        mot = self.mots.get(cle)
        if not mot:
            return operation_id
        if self.method == 'GET' and self._is_list_view():
            ancien = 'list'
        else:
            ancien = self.method_mapping[self.method.lower()]
        suffixe = f'_{ancien}'
        if not operation_id.endswith(suffixe):
            raise ValueError(
                f'ENF11 : operationId {operation_id!r} ne finit pas par '
                f'{suffixe!r} — OPERATION_ID_METHOD_POSITION a changé ?')
        return f'{operation_id[:-len(suffixe)]}_{mot}'


def mots_operation(**mots) -> SchemaMotsOperation:
    """``schema = mots_operation(list='list')`` sur la vue (voir l'en-tête)."""
    return type('SchemaMotsOperation', (SchemaMotsOperation,), {'mots': mots})()
