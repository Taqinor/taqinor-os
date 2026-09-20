"""Les sous-ressources ÉLECTRIQUES du calepinage — CAL125 (+ CAL128).

UNE SEULE FORME D'URL (CAL233) : ces vues ne sont PAS une nouvelle famille
d'URL. Elles sont un MIXIN d'``@action`` monté sur le viewset pivot, donc
servies sous ``/api/django/calepinage/calepinages/<pk>/…`` comme tout le reste
de l'objet métier. Le mixin existe pour que la lane électrique n'écrive pas
dans le fichier du viewset (lanes réellement file-disjointes) — pas pour
ouvrir une seconde porte.

CE QUE CHAQUE ACTION GARANTIT
-----------------------------
* la SOCIÉTÉ vient du serveur : ``get_object()`` est borné par le queryset du
  viewset (``CompanyScopedModelViewSet``), donc un calepinage d'une autre
  société est INTROUVABLE (404) et jamais « interdit » ;
* chaque action déclare SA garde (``PeutVoirCalepinage`` /
  ``PeutGererCalepinage``) — le cliquet ``core.tests.test_action_permissions``
  refuse une action gardée seulement au niveau classe ;
* un refus métier est rendu 400 EN NOMMANT le champ fautif (règle fondateur du
  08/09/2026 : jamais un « non enregistré » générique) ;
* AUCUN prix, AUCUN ``prix_achat`` : le résultat électrique ne publie que des
  grandeurs électriques et des quantités.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..services.electrique import (
    EntreeInvalide, TemperaturesInvalides, enregistrer_entree,
    evaluation_electrique, resultat_calepinage,
)

__all__ = ['ElectriqueActionsMixin']


class ElectriqueActionsMixin:
    """Les ``@action`` électriques du viewset pivot."""

    @action(detail=True, methods=['get'], url_path='resultat',
            permission_classes=[PeutVoirCalepinage])
    def resultat(self, request, pk=None):
        """CAL125 — le ``resultat`` du calepinage, affectation comprise.

        Forme EXACTE du contrat committé
        ``contract_samples/calepinage_resultat.json`` (CAL244, publié seul sur
        ``main`` AVANT cette tâche — PACT10) : toutes les clés sont toujours
        présentes, et ce qui n'a pas été calculé vaut ``null`` (jamais ``0``).

        ``electrique.affectation`` donne, module par module, sa chaîne ET son
        entrée MPPT : c'est la table que l'écran teinte (CAL126). Sans elle,
        l'écran recalculerait une partition — donc une AUTRE partition que
        celle qui a été dimensionnée.

        Lecture PURE : rien n'est écrit, aucun statut n'est touché.
        """
        calepinage = self.get_object()
        try:
            return Response(resultat_calepinage(calepinage))
        except TemperaturesInvalides as refus:
            return Response({refus.champ or 'temperatures': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='entree-electrique',
            permission_classes=[PeutGererCalepinage])
    def entree_electrique(self, request, pk=None):
        """CAL125 — enregistre l'ENTRÉE du calcul électrique, puis republie.

        Le matériel est DÉSIGNÉ (identifiants produit, résolus par le
        sélecteur du stock et bornés société), les longueurs et les
        températures sont SAISIES : rien n'est deviné depuis le devis ni
        depuis un catalogue « par défaut ». La réponse est le ``resultat``
        recalculé — l'appelant n'a pas à enchaîner un second appel.
        """
        calepinage = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        try:
            enregistrer_entree(calepinage, corps)
            return Response(resultat_calepinage(calepinage))
        except (EntreeInvalide, TemperaturesInvalides) as refus:
            return Response({refus.champ or 'entree_electrique': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='evaluer-electrique',
            permission_classes=[PeutVoirCalepinage])
    def evaluer_electrique(self, request, pk=None):
        """CAL128 — le verdict onduleur À CHAUD, pendant la conception.

        L'atelier l'appelle après anti-rebond avec le dessin EN COURS
        (``layout`` dans le corps) : l'utilisateur est averti PENDANT qu'il
        dessine, pas au moment de chiffrer. Rien n'est écrit — ni conception,
        ni statut, ni résultat : c'est une évaluation, pas un enregistrement
        (d'où la garde en LECTURE).

        Le message NOMME la contrainte (Isc / MPPT / V_max), le pan et la
        chaîne fautifs. Une fiche technique incomplète rend
        ``verdict: 'indetermine'`` et AUCUN bloquant : le silence, jamais un
        faux vert.
        """
        calepinage = self.get_object()
        corps = request.data if isinstance(request.data, dict) else {}
        layout = corps.get('layout')
        if layout is not None and not isinstance(layout, dict):
            return Response(
                {'layout': "La conception envoyée doit être un objet "
                           "(reçu : %s)." % type(layout).__name__},
                status=status.HTTP_400_BAD_REQUEST)
        entree = corps.get('entree_electrique')
        if entree is not None and not isinstance(entree, dict):
            return Response(
                {'entree_electrique': "L'entrée électrique doit être un "
                                      "objet."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(evaluation_electrique(
                calepinage, entree=entree, layout=layout))
        except (EntreeInvalide, TemperaturesInvalides) as refus:
            return Response({refus.champ or 'entree_electrique': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
