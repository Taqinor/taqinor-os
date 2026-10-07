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

from ..permissions import (
    PeutApprouverCalepinage, PeutLireOuEcrireCalepinage, PeutVoirCalepinage,
)
from ..services.electrique import (
    CLE_PUBLICATION, EntreeInvalide, TemperaturesInvalides, enregistrer_entree,
    entree_electrique_servie, entree_stockee, evaluation_electrique,
    resultat_calepinage, verdict_publiable,
)
from ..services.protections import DecisionInvalide
from ..services.terre import TerreInvalide

__all__ = ['ElectriqueActionsMixin']

#: ACAL150 — les refus qui DOIVENT rester des 400 nommés (jamais un 500) :
#: températures, décision de check-list, décision de terre. La lecture du
#: résultat les tolère déjà ; la vue les attrape quand même, par sûreté.
_REFUS_DE_LECTURE = (TemperaturesInvalides, DecisionInvalide, TerreInvalide)


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
        # ACAL172 — ``?variante=<id>`` : le résultat (verdict électrique
        # compris) calculé sur le ``roof_layout`` de CETTE variante du même
        # calepinage ; rien n'est écrit. Variante étrangère ⇒ 404.
        variante = None
        brut = request.query_params.get('variante')
        if brut not in (None, ''):
            from .. import selectors

            variante = (selectors.variantes(calepinage).filter(pk=brut).first()
                        if str(brut).isdigit() else None)
            if variante is None:
                return Response({'variante': 'Variante introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            if not isinstance(variante.roof_layout, dict) \
                    or not variante.roof_layout:
                # Lot 2 critique #17 — jamais le résultat du calepinage sous
                # l'étiquette d'une variante sans conception.
                return Response(
                    {'variante': "La variante n'a pas de conception : "
                                 "dessinez-la avant de l'évaluer."},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            if variante is None:
                return Response(resultat_calepinage(calepinage))
            # Lot 2 critique #17 — la simulation servie est celle de LA
            # variante (ACAL112 l'écrit sur ``variante.resultat``).
            servi = resultat_calepinage(
                calepinage, layout=variante.roof_layout,
                porteur_simulation=variante)
            servi['variante'] = {'id': variante.pk, 'nom': variante.nom}
            return Response(servi)
        except _REFUS_DE_LECTURE as refus:
            return Response({refus.champ or 'temperatures': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], url_path='entree-electrique',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def entree_electrique(self, request, pk=None):
        """CAL125 — enregistre l'ENTRÉE du calcul électrique, puis republie.

        ACAL56 — ``GET`` relit l'entrée STOCKÉE clé par clé, avec le matériel
        RÉSOLU et sa provenance (désignation explicite, sinon lignes du devis
        lié — D-ACAL-10), les rôles absents et les candidats du catalogue de
        la société (contrat ``calepinage_entree_electrique.json``). Lecture
        PURE, garde de LECTURE ; ``POST`` reste gardé en écriture.

        Le matériel est DÉSIGNÉ (identifiants produit, résolus par le
        sélecteur du stock et bornés société) ou, à défaut, celui du devis
        lié ; les longueurs et les températures sont SAISIES : rien n'est
        tiré d'un catalogue « par défaut ». La réponse du ``POST`` est le
        ``resultat`` recalculé — l'appelant n'a pas à enchaîner un second
        appel.

        CALX215 — ``derogations`` (``[{code, motif}]``) passe outre des
        ALERTES nommées par leur code : l'AUTEUR est l'utilisateur de la
        requête (jamais un nom envoyé dans le corps) et l'instant est posé
        par le serveur.
        """
        calepinage = self.get_object()
        if request.method.lower() == 'get':
            return Response(entree_electrique_servie(
                calepinage, entree_stockee(calepinage)))
        corps = request.data if isinstance(request.data, dict) else {}
        if corps.get('derogations') and not PeutApprouverCalepinage() \
                .has_permission(request, self):
            # ACAL283 / D-ACAL-9 — toute dérogation électrique exige
            # ``calepinage_approuver`` ; refus NOMMÉ, rien n'est écrit.
            return Response(
                {'derogations': "Passer outre une alerte électrique exige le "
                                "droit « calepinage_approuver » : demandez à "
                                "un approbateur de poser la dérogation."},
                status=status.HTTP_403_FORBIDDEN)
        try:
            enregistrer_entree(calepinage, corps, user=request.user)
            return Response(resultat_calepinage(calepinage))
        except (EntreeInvalide, *_REFUS_DE_LECTURE) as refus:
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

        CALX248 — la clé ``publication`` porte le verdict PUBLIABLE complet
        (``{publiable, motifs}``) : norme omise, raccordement, équilibrage,
        terre et tronçons non calculables, tout ce qui empêche de publier au
        MÊME endroit. Il se prononce sur la conception ENREGISTRÉE — on
        publie ce qui est enregistré, pas ce qui est en cours de dessin — et
        il est donc omis quand l'appel porte un dessin à chaud.
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
            evaluation = evaluation_electrique(
                calepinage, entree=entree, layout=layout)
            # La clé est TOUJOURS présente : ``None`` quand l'appel porte un
            # dessin ou une entrée à chaud, pour que l'écran n'ait jamais à
            # deviner si elle manque ou si elle est vide.
            evaluation[CLE_PUBLICATION] = (
                None if (layout is not None or entree is not None)
                else verdict_publiable(calepinage))
            return Response(evaluation)
        except (EntreeInvalide, *_REFUS_DE_LECTURE) as refus:
            return Response({refus.champ or 'entree_electrique': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)
