"""ENF1b — réponse ``OPTIONS`` qui ne plante jamais (api-fuzz du 09/10).

``SimpleMetadata.determine_actions`` (DRF) décrit les champs acceptés en
``PUT``/``POST`` : pour ``PUT`` il appelle ``view.get_object()``, puis
``view.get_serializer()``. Sur une action de LISTE (``detail=False``) qui
accepte ``PUT``/``PATCH`` (``…/bulk/``, ``…/courant/``, ``…/favoris/``…),
``get_object()`` lève l'``AssertionError`` « Expected view … to be called
with a URL keyword argument named "pk" » ; sur une vue sans
``serializer_class`` (``GabaritDossierViewSet``), ``get_serializer()`` lève
« should either include a `serializer_class` attribute ». DRF n'attrape que
``APIException``/``PermissionDenied``/``Http404`` : 8 opérations ``OPTIONS``
répondaient 500.

Ces assertions décrivent une limite de la DESCRIPTION automatique, pas une
erreur de la requête : la méthode concernée est simplement omise du bloc
``actions`` (exactement comme DRF le fait déjà quand la permission manque).
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.metadata import SimpleMetadata
from rest_framework.request import clone_request


class TaqinorMetadata(SimpleMetadata):
    """``DEFAULT_METADATA_CLASS`` — ``SimpleMetadata`` sans 500 sur OPTIONS."""

    def determine_actions(self, request, view):
        actions = {}
        for method in {'PUT', 'POST'} & set(view.allowed_methods):
            view.request = clone_request(request, method)
            try:
                if hasattr(view, 'check_permissions'):
                    view.check_permissions(view.request)
                if method == 'PUT' and hasattr(view, 'get_object'):
                    view.get_object()
                serializer = view.get_serializer()
            except (exceptions.APIException, PermissionDenied, Http404,
                    AssertionError):
                continue
            finally:
                view.request = request
            actions[method] = self.get_serializer_info(serializer)
        return actions
