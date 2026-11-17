"""Projets, étapes, modèles et revue (reference/api.md §3.3, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class ProjetsVue(IdempotentCreateMixin, APIView):
    """GET projets/ (liste paginée + constat) · POST projets/ (créer)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class ProjetVue(APIView):
    """GET (PROJET) · PATCH (verrou 409) · DELETE (avec ses tâches) projets/{id}/."""

    permission_classes = PERMISSIONS

    def get(self, request, id):
        raise PasEncore()

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class ProjetReordonnerVue(APIView):
    """POST projets/{id}/reordonner/ — ordre manuel, « Mettre en haut »."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TrierParPrioriteVue(APIView):
    """POST projets/trier-par-priorite/ — ordre par priorité, une fois."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class ProjetAffichageVue(APIView):
    """GET projets/{id}/vue/ — sections, ITEM, avancement, santé, jalon, burn-up."""

    permission_classes = PERMISSIONS

    def get(self, request, id):
        raise PasEncore()


class PlanificationApercuVue(APIView):
    """POST projets/{id}/planification/apercu/ — lire une liste, rien n'est écrit."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class PlanificationVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/planification/ — tout créer, priorité comprise (verrou 409)."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class DecalerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/decaler/ — `{"delta_jours","apercu"}`."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class ProjetTerminerVue(APIView):
    """POST projets/{id}/terminer/ — clôture."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class ProjetRouvrirVue(APIView):
    """POST projets/{id}/rouvrir/ — réouverture."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class ProjetRestaurerVue(APIView):
    """POST projets/{id}/restaurer/ — le projet et les tâches supprimées avec lui."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class DupliquerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/dupliquer/ — `{"nom","date_debut","apercu"}`."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class EnregistrerModeleVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/enregistrer-modele/ — `{"nom","inclure_notes"}`."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class SectionsVue(APIView):
    """POST sections/ — `{"projet_id","nom","date_debut"?,"date_fin"?}`."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class SectionVue(APIView):
    """PATCH (renommer, dates) · DELETE (tâches « Sans étape ») sections/{id}/."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class SectionReordonnerVue(APIView):
    """POST sections/{id}/reordonner/."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class ModelesVue(APIView):
    """GET modeles/ — liste paginée."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class ModeleVue(APIView):
    """GET · PATCH `{"nom"}` · DELETE modeles/{id}/."""

    permission_classes = PERMISSIONS

    def get(self, request, id):
        raise PasEncore()

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class ModeleInstancierVue(IdempotentCreateMixin, APIView):
    """POST modeles/{id}/instancier/ — `{"nom","date_lancement","apercu"}`."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class RevueProjetsVue(APIView):
    """GET revue/projets/ — bilan de la semaine (ou Semaine courte) et cartes."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class RevueDecisionVue(APIView):
    """PUT revue/projets/{projet_id}/ — la décision d'une carte de revue."""

    permission_classes = PERMISSIONS

    def put(self, request, projet_id):
        raise PasEncore()
