"""Le viewset PIVOT du module Calepinage — CAL16.

UNE SEULE FORME D'URL (CAL233) : tout l'objet métier est servi sous
``/api/django/calepinage/calepinages/<pk>/…``, les sous-ressources en
``@action`` du routeur DRF. Aucune seconde famille d'URL n'est ouverte ici.

CE QUI EST GARANTI PAR LE SOCLE, ET PAS RECODÉ
-----------------------------------------------
* ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) : le queryset est filtré
  sur ``request.user.company`` et la société est POSÉE côté serveur — un
  ``company`` envoyé dans le corps n'existe pas pour le sérialiseur, donc il
  est ignoré, et un calepinage d'une autre société est INTROUVABLE (404),
  jamais « interdit » (un 403 confirmerait son existence) ;
* ``core.permissions.ScopedPermission`` + ``read_permission``/
  ``write_permission`` : lecture gardée par ``calepinage_voir``, écriture par
  ``calepinage_gerer`` (codes lus de ``apps/calepinage/permissions.py``, jamais
  écrits en littéral ici) ;
* chaque ``@action`` déclare EN PLUS sa propre garde (``PeutVoirCalepinage`` /
  ``PeutGererCalepinage``). ``get_permissions`` CUMULE les deux (patron
  ``apps/ao/viewsets.py``) : la garde déclarée par l'action est un plafond
  supplémentaire, jamais une substitution qui jetterait la garde du domaine.

LES FILTRES SONT RÉELLEMENT SERVIS (leçon PV22)
------------------------------------------------
``?lead=`` ``?client=`` ``?statut=`` ``?depuis=`` ``?q=`` passent par
``selectors.appliquer_filtres_liste`` — la MÊME fonction que le sélecteur
public. Un filtre ILLISIBLE (statut inconnu, date invalide) est REFUSÉ 400 en
nommant le champ, jamais avalé en silence : un filtre ignoré fait ouvrir le
mauvais objet (``LeadWorkspace.jsx`` l'a montré).
"""
from __future__ import annotations

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import filters
from rest_framework.exceptions import ValidationError as DrfValidationError

from core.permissions import ScopedPermission, declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet

from .. import selectors
from ..models import Calepinage
from ..permissions import CAL_GERER, CAL_VOIR
from ..serializers import CalepinageSerializer

__all__ = ['CalepinageViewSet']


class CalepinageViewSet(CompanyScopedModelViewSet):
    """CRUD du pivot ``Calepinage`` + ses sous-ressources en ``@action``."""

    queryset = Calepinage.objects.select_related('client', 'devis').all()
    serializer_class = CalepinageSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at', 'statut', 'titre']

    read_permission = CAL_VOIR
    write_permission = CAL_GERER

    def get_permissions(self):
        """``ScopedPermission`` TOUJOURS, + la garde déclarée par l'action.

        Cumul et jamais substitution : sans ``declared_action_permissions``,
        le ``permission_classes=`` d'une ``@action`` serait complètement
        inopérant (cf. ``core.permissions``).
        """
        permissions = [ScopedPermission()]
        declared = declared_action_permissions(self)
        if declared is not None:
            permissions.extend(declared)
        return permissions

    # ── Liste : des filtres qui filtrent VRAIMENT ──────────────────────────
    def get_queryset(self):
        params = getattr(self.request, 'query_params', {}) or {}
        return selectors.appliquer_filtres_liste(
            super().get_queryset(),
            lead_id=_entier(params.get('lead'), 'lead'),
            client_id=_entier(params.get('client'), 'client'),
            statut=_statut(params.get('statut')),
            depuis=_moment(params.get('depuis')),
            q=params.get('q'))

    def perform_create(self, serializer):
        """Société ET auteur posés côté serveur — jamais lus du corps."""
        serializer.save(company=self.request.user.company,
                        cree_par=self.request.user)


# ── Lecture des paramètres de requête : refusée en NOMMANT le champ ────────

def _entier(valeur, champ):
    """Un identifiant entier, ou ``None`` quand le filtre est absent."""
    if valeur in (None, ''):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        raise DrfValidationError({
            champ: (f"Le filtre « {champ} » attend un identifiant "
                    f"(reçu : {valeur!r})."),
        })


def _statut(valeur):
    """Un statut du vocabulaire du serveur, ou ``None``.

    Un statut INCONNU est refusé : l'avaler rendrait la liste ENTIÈRE là où
    l'écran croit lire un sous-ensemble — exactement le mode de panne PV22.
    """
    if valeur in (None, ''):
        return None
    admis = [choix for choix, _ in Calepinage.Statut.choices]
    if valeur not in admis:
        raise DrfValidationError({
            'statut': (f"Statut inconnu : « {valeur} ». Statuts admis : "
                       f"{', '.join(admis)}."),
        })
    return valeur


def _moment(valeur):
    """Une date (ou un horodatage ISO), ou ``None`` — jamais une date devinée."""
    if valeur in (None, ''):
        return None
    moment = parse_datetime(valeur) or parse_date(valeur)
    if moment is None:
        raise DrfValidationError({
            'depuis': (f"Date illisible : « {valeur} ». Format attendu : "
                       "AAAA-MM-JJ (ou un horodatage ISO 8601)."),
        })
    return moment
