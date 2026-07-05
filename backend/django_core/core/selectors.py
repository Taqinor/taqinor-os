"""Sélecteurs transverses de la couche fondation ``core`` (YRBAC11).

``TenantMixin`` scope automatiquement le queryset générique d'un
``ModelViewSet`` (liste + ``get_object`` du détail), mais les vues
FONCTIONNELLES (``@api_view``) et les ``@action`` qui chargent un objet « à la
main » via ``Model.objects.get(pk=…)``/``get_object_or_404(Model, pk=…)``
peuvent oublier de re-borner à la société de l'appelant — un ID d'une AUTRE
société serait alors accessible (fuite cross-tenant).

``get_company_object`` est le remplacement canonique : filtre TOUJOURS par
``company`` (+ une portée additionnelle optionnelle, ex.
``core.scoping.visible_user_ids``) et renvoie un 404 INDISTINCT de « l'objet
n'existe pas » — jamais un signal différent pour « existe mais pas à toi »
(l'existence d'un enregistrement d'une autre société est elle-même sensible).

``core`` reste FONDATION : aucun import d'app métier au niveau module (le
seul couplage est le paramètre ``model`` passé par l'appelant).
"""
from __future__ import annotations

from django.http import Http404


def get_company_object(model_or_queryset, pk, user, extra_scope=None,
                       **extra_filters):
    """Renvoie l'instance scopée à la société de ``user`` d'id ``pk``, ou lève
    ``Http404`` — INDISTINCTEMENT d'un ``pk`` inexistant.

    Args:
        model_or_queryset: une classe de modèle Django (doit porter un champ
            ``company``), OU un queryset déjà construit (ex. avec
            ``select_related``/``prefetch_related`` pour éviter le N+1) — les
            DEUX sont acceptés, le filtrage société/portée s'applique dessus.
        pk: la clé primaire demandée (brute, non validée par l'appelant).
        user: ``request.user``. Sans société (et sans superuser), renvoie
            TOUJOURS 404 (jamais de fuite implicite).
        extra_scope: callable optionnel ``qs, user -> qs`` appliqué APRÈS le
            filtre société (ex. ``core.scoping.scope_queryset`` pour borner en
            plus à la portée d'équipe/sous-arbre d'un rôle narrowed). Ignoré
            (aucun narrowing) si ``None`` — comportement historique.
        **extra_filters: filtres additionnels appliqués tels quels (ex.
            ``confidentialite='public'``).

    Un superuser SANS société voit tout (comportement plateforme historique,
    identique à ``TenantMixin``) ; un superuser AVEC société reste scopé à
    cette société (usage ERP normal).
    """
    qs = (
        model_or_queryset.objects.all()
        if hasattr(model_or_queryset, 'objects')
        else model_or_queryset
    )
    company_id = getattr(user, 'company_id', None)
    if company_id:
        qs = qs.filter(company_id=company_id)
    elif not getattr(user, 'is_superuser', False):
        qs = qs.none()
    if extra_filters:
        qs = qs.filter(**extra_filters)
    if extra_scope is not None:
        qs = extra_scope(qs, user)
    obj = qs.filter(pk=pk).first()
    if obj is None:
        # Message générique — jamais « appartient à une autre société » :
        # l'existence d'un enregistrement hors-société est elle-même une
        # fuite (IDOR par énumération).
        raise Http404('Introuvable.')
    return obj
