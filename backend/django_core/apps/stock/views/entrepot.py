"""Groupe NTWMS (vague 3) — vues de PILOTAGE d'entrepôt (lecture seule).

Cockpit entrepôt (NTWMS29), simulateur de capacité what-if (NTWMS33),
suggestion de tâche retour / interleaving (NTWMS36), alertes de sur-capacité
par zone (NTWMS42).

PÉRIMÈTRE. Les tâches du plan situaient l'endpoint cockpit et l'endpoint
d'alertes dans ``apps/reporting`` ; cette lane ne possède que ``apps/stock``,
donc ils vivent ici — exactement comme ``entrepot/productivite/`` (NTWMS18) et
``entrepot/pertes/`` (NTWMS24) livrés à la vague précédente. La donnée, sa
garde et son test restent au même endroit.

Toutes les vues sont en LECTURE : aucune n'écrit, aucune ne réserve.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin


def _int_param(value, defaut=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return defaut


@extend_schema(responses={
    200: inline_serializer('StockEntrepotCockpit', {
        'date': serializers.CharField(),
        'zones': serializers.ListField(child=serializers.DictField()),
        'zones_en_surcapacite': serializers.ListField(
            child=serializers.DictField()),
        'vagues': serializers.ListField(child=serializers.DictField()),
        'vagues_en_retard': serializers.IntegerField(),
        'comptages_dus': serializers.ListField(child=serializers.DictField()),
        'expeditions_du_jour': serializers.ListField(
            child=serializers.DictField()),
        'lots_peremption': serializers.ListField(
            child=serializers.DictField()),
        'horizon_peremption_jours': serializers.IntegerField(),
    }),
})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def entrepot_cockpit_view(request):
    """NTWMS29 — tableau de bord entrepôt, tout en une requête.

    Remplissage par zone, vagues de prélèvement en cours + EN RETARD,
    comptages tournants dus, expéditions du jour par transporteur et lots
    proches de péremption (FEFO) : le responsable voit d'un coup d'œil ce qui
    dérape sans naviguer entre cinq écrans.

    Paramètres facultatifs : ``?emplacement=``, ``?horizon_peremption=``
    (jours), ``?retard_heures=``.
    """
    from ..selectors_entrepot import cockpit_entrepot

    return Response(cockpit_entrepot(
        request.user.company,
        emplacement_id=_int_param(request.query_params.get('emplacement')),
        horizon_peremption_jours=_int_param(
            request.query_params.get('horizon_peremption'), 30),
        retard_vague_heures=_int_param(
            request.query_params.get('retard_heures'), 24),
    ))


@extend_schema(responses={
    200: inline_serializer('StockSimulationCapacite', {
        'zone': serializers.CharField(),
        'produit': serializers.IntegerField(allow_null=True),
        'capacite': serializers.IntegerField(allow_null=True),
        'occupe_actuel': serializers.IntegerField(),
        'taux_actuel_pct': serializers.CharField(allow_null=True),
        'quantite_ajoutee': serializers.IntegerField(),
        'occupe_projete': serializers.IntegerField(),
        'taux_projete_pct': serializers.CharField(allow_null=True),
        'depassement': serializers.BooleanField(),
        'unites_en_trop': serializers.IntegerField(),
        'avertissement': serializers.CharField(allow_blank=True),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def simuler_capacite_view(request):
    """NTWMS33 — what-if de capacité :
    ``?zone=A&quantite=200[&produit=&emplacement=]``.

    Projette le taux de remplissage d'une zone SI on y ajoutait la quantité
    demandée — pour décider où stocker une grosse réception AVANT qu'elle
    n'arrive. Aucune écriture, aucune réservation.
    """
    from ..selectors_entrepot import simuler_capacite

    try:
        resultat = simuler_capacite(
            request.user.company,
            zone=request.query_params.get('zone'),
            quantite_supplementaire=_int_param(
                request.query_params.get('quantite'), 0),
            produit_id=_int_param(request.query_params.get('produit')),
            emplacement_id=_int_param(request.query_params.get('emplacement')),
        )
    except ValueError as exc:
        return Response({'detail': str(exc)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(resultat)


@extend_schema(responses={
    200: inline_serializer('StockZonesSurcapacite', {
        'seuil_pct': serializers.CharField(),
        'zones': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def zones_surcapacite_view(request):
    """NTWMS42 — zones qui franchissent le seuil de remplissage
    (``?seuil=95``). Alerte PASSIVE : la tâche planifiée
    ``stock.alerter_surcapacite_zones`` notifie sur le même sélecteur."""
    from ..selectors_entrepot import (
        SEUIL_SURCAPACITE_PCT, _fmt_dec, zones_en_surcapacite,
    )

    seuil = request.query_params.get('seuil')
    zones = zones_en_surcapacite(
        request.user.company, seuil_pct=seuil,
        emplacement_id=_int_param(request.query_params.get('emplacement')))
    return Response({
        'seuil_pct': (zones[0]['seuil_pct'] if zones
                      else _fmt_dec(seuil or SEUIL_SURCAPACITE_PCT)),
        'zones': zones,
    })


@extend_schema(responses={
    200: inline_serializer('StockHistoriqueCasier', {
        'bin': serializers.IntegerField(),
        'bin_code': serializers.CharField(allow_blank=True),
        'lignes': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def historique_casier_view(request, bin_id):
    """NTWMS39 — journal d'un casier : qui a changé quoi, et quand.

    Création, modification d'un champ structurant (code/zone/allée/casier/
    ordre/catégorie de stockage), archivage et réactivation. Lecture seule,
    scopée société — le casier d'une autre société renvoie une liste vide,
    jamais son historique.
    """
    from ..models import HistoriqueCasier

    company = request.user.company
    lignes = (HistoriqueCasier.objects
              .filter(company=company, bin_id=bin_id)
              .select_related('auteur', 'bin')
              .order_by('-created_at', '-id'))
    lignes = list(lignes[:200])
    return Response({
        'bin': int(bin_id),
        'bin_code': (lignes[0].bin.code if lignes else ''),
        'lignes': [{
            'id': ligne.id,
            'action': ligne.action,
            'champ': ligne.champ,
            'ancienne_valeur': ligne.ancienne_valeur,
            'nouvelle_valeur': ligne.nouvelle_valeur,
            'auteur': (getattr(ligne.auteur, 'username', '')
                       if ligne.auteur_id else ''),
            'date': ligne.created_at.isoformat(),
        } for ligne in lignes],
    })


@extend_schema(responses={
    200: inline_serializer('StockTacheRetour', {
        'zone_courante': serializers.CharField(allow_blank=True),
        'suggestions': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def tache_retour_view(request):
    """NTWMS36 — interleaving : ``?zone=C[&limite=1]``.

    Après un rangement en zone C, propose la ligne de prélèvement en attente
    la plus proche du trajet RETOUR (même zone d'abord, sinon la plus proche
    de la sortie) — au lieu de renvoyer l'opérateur à vide au quai.
    """
    from ..selectors_entrepot import suggerer_tache_retour

    zone = request.query_params.get('zone') or ''
    return Response({
        'zone_courante': zone,
        'suggestions': suggerer_tache_retour(
            request.user.company, zone_courante=zone,
            operateur=request.user,
            limite=_int_param(request.query_params.get('limite'), 1)),
    })
