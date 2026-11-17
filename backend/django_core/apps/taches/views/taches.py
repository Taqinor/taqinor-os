"""Tâches, À trier, fiche et ce qui s'y rattache (reference/api.md §3.1-§3.2, §4) : recherche, listes,
fiche, actions d'une tâche, lot, rappels, récurrences, check-list, étiquettes, vues enregistrées,
supprimées récemment, derniers gestes.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class RechercheVue(APIView):
    """GET recherche/ — projets et tâches par mots."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class TachesVue(IdempotentCreateMixin, APIView):
    """GET taches/ (listes paginées) · POST taches/ (une LIGNE)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class TacheVue(APIView):
    """GET (TACHE, lien revérifié) · PATCH (verrou 409) · DELETE taches/{id}/."""

    permission_classes = PERMISSIONS

    def get(self, request, id):
        raise PasEncore()

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class TachePlanifierVue(APIView):
    """POST taches/{id}/planifier/ — seul chemin du jour, de l'heure et du moment."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheTerminerVue(APIView):
    """POST taches/{id}/terminer/ — cocher."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheRouvrirVue(APIView):
    """POST taches/{id}/rouvrir/ — décocher."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheTrancherVue(APIView):
    """POST taches/{id}/trancher/ — aujourdhui, garder, jour, un_jour, abandonner."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheSauterVue(APIView):
    """POST taches/{id}/sauter/ — sauter une occurrence."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheAttendreVue(APIView):
    """POST taches/{id}/attendre/ — « En attente de… »."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheRecuVue(APIView):
    """POST taches/{id}/recu/ — reçu."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheReordonnerVue(APIView):
    """POST taches/{id}/reordonner/ — `{"liste","avant_id","apres_id"}`."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheRestaurerVue(APIView):
    """POST taches/{id}/restaurer/ — restaurer une tâche supprimée."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheRappelsVue(APIView):
    """POST taches/{id}/rappels/ — poser un rappel."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class TacheChangementApercuVue(APIView):
    """POST taches/{id}/changement/apercu/ — écho d'un renommage, abandon ou suppression."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class LotVue(IdempotentCreateMixin, APIView):
    """POST taches/lot/ — une action sur une sélection (≤ 200)."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class RappelVue(APIView):
    """DELETE rappels/{id}/ — retirer un rappel."""

    permission_classes = PERMISSIONS

    def delete(self, request, id):
        raise PasEncore()


class RappelRepeterVue(APIView):
    """POST rappels/{id}/repeter/ — « Encore 10 min · 1 h · Demain 9 h »."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class RecurrenceVue(APIView):
    """PATCH recurrences/{id}/ — modifier ou arrêter (`actif:false`) une récurrence."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()


class ChecklistVue(APIView):
    """POST checklist/ — ajouter un point `{"tache_id","libelle"}`."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class ElementChecklistVue(APIView):
    """PATCH · DELETE checklist/{id}/."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class ElementChecklistReordonnerVue(APIView):
    """POST checklist/{id}/reordonner/."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class EtiquettesVue(APIView):
    """GET etiquettes/ (liste paginée) · POST etiquettes/ `{"nom","couleur"}`."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class EtiquetteVue(APIView):
    """PATCH · DELETE etiquettes/{id}/."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class VuesVue(APIView):
    """GET vues/ (≤ 30, non paginé) · POST vues/ `{"nom","filtres","rang"}`."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class VueEnregistreeVue(APIView):
    """PATCH · DELETE vues/{id}/."""

    permission_classes = PERMISSIONS

    def patch(self, request, id):
        raise PasEncore()

    def delete(self, request, id):
        raise PasEncore()


class SupprimeesVue(APIView):
    """GET supprimees/ — Supprimées récemment (un projet = une ligne)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class GestesVue(APIView):
    """GET gestes/ — derniers gestes (7 jours)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()


class GesteAnnulerVue(APIView):
    """POST gestes/{id}/annuler/ — Annuler (200 partiel)."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()
