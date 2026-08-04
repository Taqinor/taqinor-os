"""Portée « entité » (Groupe NTADM) — filtre d'affichage optionnel.

NTADM2 — filtre de CONFORT (``?entite=<id>``) : un paramètre de requête
OPTIONNEL qui restreint une liste à une entité (``apps.entites``). Il
n'accorde ni ne retire aucun droit ; absent, la liste est STRICTEMENT celle
d'aujourd'hui. Le périmètre de DONNÉES par rôle (NTADM3) est une couche
séparée, posée plus tard dans ce même module.

``core`` reste une couche de FONDATION : ce module n'importe aucune app.
"""

__all__ = [
    'entite_id_demandee',
    'filtre_entite_demandee',
    'EntiteScopeMixin',
]


def entite_id_demandee(request):
    """``?entite=<id>`` normalisé en entier, ou ``None``.

    Une valeur absente, vide ou non numérique vaut « pas de filtre » — jamais
    une erreur 500 ni une liste vide surprise.
    """
    if request is None:
        return None
    params = getattr(request, 'query_params', None)
    if params is None:
        return None
    brut = params.get('entite')
    if brut in (None, ''):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


def filtre_entite_demandee(qs, request, champ='entite'):
    """NTADM2 — applique le filtre OPTIONNEL ``?entite=<id>`` sur ``qs``.

    Additif : sans le paramètre, ``qs`` est renvoyé INCHANGÉ. La société est
    déjà filtrée en amont (``TenantMixin``) — on n'ajoute jamais un
    re-filtrage société ici.
    """
    entite_id = entite_id_demandee(request)
    if entite_id is None:
        return qs
    return qs.filter(**{f'{champ}_id': entite_id})


class EntiteScopeMixin:
    """Mixin de ViewSet : filtre optionnel ``?entite=`` (NTADM2).

    À poser AVANT la base scopée société dans les bases de la classe ::

        class DevisViewSet(EntiteScopeMixin, CompanyScopedModelViewSet):

    ``get_queryset`` compose avec ``super()`` : le scoping société reste en
    amont et INCHANGÉ. Sans ``?entite=`` dans la requête, le queryset rendu
    est byte-identique à celui d'avant.
    """

    #: nom du champ FK vers ``entites.Entite`` sur le modèle du viewset.
    entite_field = 'entite'

    def get_queryset(self):
        qs = super().get_queryset()
        request = getattr(self, 'request', None)
        if request is None:
            return qs
        return filtre_entite_demandee(qs, request, self.entite_field)
