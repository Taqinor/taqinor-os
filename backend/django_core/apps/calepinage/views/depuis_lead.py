"""CALX47 — ``POST /calepinages/depuis-lead/`` : la porte CRM du module.

LE CONSTAT
----------
``frontend/src/features/crm/workspace/IdentityRail.jsx`` offre « Concevoir la
toiture (3D) », qui ouvre l'ANCIEN atelier de devis ; un grep de
``frontend/src/features/crm`` ne trouvait AUCUN lien vers ``/calepinage/…``,
et ``module.config.jsx`` le dit noir sur blanc (« cette porte N'EXISTE PAS
aujourd'hui »). Le module autonome n'était donc joignable que par sa propre
liste — jamais depuis le dossier du client, là où le commercial travaille.

CE QUE CETTE PORTE FAIT, ET CE QU'ELLE NE FAIT PAS
----------------------------------------------------
* elle appelle ``services/creation.py::creer_pour_lead`` (CAL11), le chemin
  de création qui existe — aucun second chemin n'est écrit ;
* elle est **IDEMPOTENTE** : un lead qui a déjà un calepinage OUVERT reçoit
  CELUI-LÀ, jamais un second. « Ouvert » = non archivé, au sens exact de
  ``selectors.appliquer_filtres_liste`` (CAL208, ``inclure_archives=False``) :
  un calepinage mis à la corbeille ne bloque donc pas une nouvelle
  conception, et il n'est pas non plus ressuscité en silence ;
* la relecture se fait DANS la transaction, comme
  ``obtenir_ou_creer_pour_devis`` : deux clics simultanés sur le même lead
  ne produisent pas deux calepinages ;
* elle ne touche RIEN du geste existant « Concevoir la toiture (3D) », qui
  garde exactement sa sémantique (décision D2 du groupe CAL) ;
* le CRM n'est lu que par ``apps.crm.selectors`` — au travers du service de
  création, qui appelle ``get_company_lead`` (contrats import-linter).

La société vient TOUJOURS de ``request.user`` : un lead d'une autre société
est INTROUVABLE (refus nommé), jamais « interdit ».
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.creation import CreationRefusee, creer_pour_lead

__all__ = ['depuis_lead']


def _identifiant(brut):
    """Un identifiant entier, ou ``None`` — jamais une valeur devinée."""
    if brut in (None, ''):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


def _calepinage_ouvert(lead_id, company):
    """Le calepinage OUVERT le plus récent de ce lead, ou ``None``.

    Lecture bornée société par construction : ``company`` vient de
    l'appelant, jamais d'un corps de requête.
    """
    from ..models import Calepinage
    from ..selectors import appliquer_filtres_liste

    if company is None or not lead_id:
        return None
    return appliquer_filtres_liste(
        Calepinage.objects.filter(company=company), lead_id=lead_id).first()


def _reponse(calepinage, *, cree):
    from .calepinages import _reference

    return {
        'calepinage': calepinage.pk,
        'reference': _reference(calepinage),
        'nom': (calepinage.titre or '').strip() or str(calepinage),
        'lead': calepinage.lead_id,
        'cree': cree,
    }


@action(detail=False, methods=['post'], url_path='depuis-lead',
        permission_classes=[PeutGererCalepinage])
def depuis_lead(self, request):
    """CALX47 — le calepinage de ce lead : le MÊME à chaque appel."""
    from django.db import transaction

    corps = request.data if isinstance(request.data, dict) else {}
    company = getattr(request.user, 'company', None)
    lead_id = _identifiant(corps.get('lead'))
    if not lead_id:
        return Response(
            {'lead': "Aucun lead n'a été indiqué : choisissez le lead dont "
                     'vous concevez la toiture.'},
            status=status.HTTP_400_BAD_REQUEST)

    existant = _calepinage_ouvert(lead_id, company)
    if existant is not None:
        return Response(_reponse(existant, cree=False))

    try:
        with transaction.atomic():
            # Relecture DANS la transaction : deux clics simultanés sur
            # « Ouvrir dans le module Calepinage » ne créent pas deux objets.
            existant = _calepinage_ouvert(lead_id, company)
            if existant is not None:
                return Response(_reponse(existant, cree=False))
            calepinage = creer_pour_lead(lead_id, company, user=request.user,
                                         titre=str(corps.get('titre') or ''))
    except CreationRefusee as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response(_reponse(calepinage, cree=True),
                    status=status.HTTP_201_CREATED)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.depuis_lead = depuis_lead
