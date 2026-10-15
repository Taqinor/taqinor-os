"""T9 — export Excel générique pour les listes restantes (devis, factures,
chantiers, équipements, tickets SAV). Lecture seule, borné à la société.
Leads/clients/produits ont leurs propres exports dédiés."""
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes)
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.champs_stricts import EntierStrict
from core.parseurs import PARSEURS_JSON, corps_valide
from apps.crm.exports import build_xlsx_response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers


def _co_qs(model, user, company_id=None):
    """Queryset borné à UNE société — jamais « toutes » (AUD315).

    La branche superutilisateur renvoyait auparavant le queryset NON filtré :
    un export lancé par un superutilisateur sans société mélangeait
    silencieusement toutes les sociétés dans un seul fichier. Désormais ce
    profil doit DÉSIGNER la société exportée (``company`` dans le corps) ;
    sans sélecteur explicite, on ne renvoie rien (fail-closed).
    """
    qs = model.objects.all()
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        if not company_id:
            return qs.none()
        return qs.filter(company_id=company_id)
    return qs.none()


def _devis_rows(user, ids, company_id=None):
    from apps.ventes.models import Devis
    from apps.ventes.selectors import devis_avec_totaux
    # APRF15 (C-APRF-004) — ``total_ttc`` lu sur des devis préchargés par LE
    # préchargement unique des totaux (``devis_avec_totaux`` :
    # ``lignes__produit``) + la société (réglages lus par le calcul) : le
    # nombre de requêtes ne dépend plus du nombre de devis exportés.
    qs = devis_avec_totaux(
        _co_qs(Devis, user, company_id).select_related('client', 'company'))
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Statut', 'Total TTC', 'Créé le', 'Validité']
    rows = [[
        d.reference, getattr(d.client, 'nom', '') or '', d.get_statut_display(),
        str(d.total_ttc or 0),
        d.date_creation.strftime('%Y-%m-%d') if d.date_creation else '',
        d.date_validite.isoformat() if d.date_validite else '',
    ] for d in qs.order_by('-id')]
    return 'devis.xlsx', headers, rows, 'Devis'


def _factures_rows(user, ids, company_id=None):
    from apps.ventes.models import Facture
    qs = _co_qs(Facture, user, company_id).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    # ``Facture`` n'a pas de ``date_creation`` (AttributeError → 500 dès qu'une
    # facture existait) : sa date de référence est ``date_emission``.
    headers = ['Référence', 'Client', 'Statut', 'Échéance', 'Émise le']
    rows = [[
        f.reference, getattr(f.client, 'nom', '') or '', f.get_statut_display(),
        f.date_echeance.isoformat() if f.date_echeance else '',
        f.date_emission.strftime('%Y-%m-%d') if f.date_emission else '',
    ] for f in qs.order_by('-id')]
    return 'factures.xlsx', headers, rows, 'Factures'


def _chantiers_rows(user, ids, company_id=None):
    from apps.installations.models import Installation
    qs = _co_qs(Installation, user, company_id).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Statut', 'Pose prévue', 'Mise en service']
    rows = [[
        i.reference, getattr(i.client, 'nom', '') or '', i.get_statut_display(),
        i.date_pose_prevue.isoformat() if i.date_pose_prevue else '',
        i.date_mise_en_service.isoformat() if i.date_mise_en_service else '',
    ] for i in qs.order_by('-id')]
    return 'chantiers.xlsx', headers, rows, 'Chantiers'


def _equipements_rows(user, ids, company_id=None):
    from apps.sav.models import Equipement
    qs = _co_qs(Equipement, user, company_id).select_related('produit')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['N° série', 'Produit', 'Pose', 'Fin garantie', 'Statut']
    rows = [[
        e.numero_serie or '', getattr(e.produit, 'nom', '') or '',
        e.date_pose.isoformat() if e.date_pose else '',
        e.date_fin_garantie.isoformat() if e.date_fin_garantie else '',
        e.get_statut_display() if hasattr(e, 'get_statut_display') else e.statut,
    ] for e in qs.order_by('-id')]
    return 'equipements.xlsx', headers, rows, 'Équipements'


def _tickets_rows(user, ids, company_id=None):
    from apps.sav.models import Ticket
    qs = _co_qs(Ticket, user, company_id).select_related('client')
    if ids:
        qs = qs.filter(id__in=ids)
    headers = ['Référence', 'Client', 'Type', 'Statut', 'Ouverture', 'Résolution']
    rows = [[
        t.reference, getattr(t.client, 'nom', '') or '',
        t.get_type_display() if hasattr(t, 'get_type_display') else t.type,
        t.get_statut_display(),
        t.date_ouverture.isoformat() if t.date_ouverture else '',
        t.date_resolution.isoformat() if t.date_resolution else '',
    ] for t in qs.order_by('-id')]
    return 'tickets.xlsx', headers, rows, 'Tickets SAV'


_BUILDERS = {
    'devis': _devis_rows, 'factures': _factures_rows, 'chantiers': _chantiers_rows,
    'equipements': _equipements_rows, 'tickets': _tickets_rows,
}


#: Corps de ``POST export/<entity>/`` : LE prédicat publié ET appliqué. Les
#: identifiants sont bornés à l'entier 32 bits des clés primaires (un entier
#: plus grand n'existe pas) ; un corps non objet répond 400 (``.get`` sur une
#: liste levait AttributeError → 500).
_ID_MAX = 2147483647
_EXPORT_LISTE_REQUETE = inline_serializer('ExportListeRequete', {
    'ids': serializers.ListField(
        child=EntierStrict(min_value=1, max_value=_ID_MAX), required=False),
    'company': EntierStrict(min_value=1, max_value=_ID_MAX, required=False)})


@extend_schema(
    parameters=[OpenApiParameter(
        'entity', OpenApiTypes.STR, OpenApiParameter.PATH,
        enum=sorted(_BUILDERS))],
    request=_EXPORT_LISTE_REQUETE,
    responses={(200, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): OpenApiTypes.BINARY})
@api_view(['POST'])
@permission_classes([IsAnyRole])
@parser_classes(PARSEURS_JSON)
def export_list(request, entity):
    """POST /imports/export/<entity>/ {ids?: [...]} → .xlsx (société courante).

    AUD315 — un superutilisateur SANS société doit joindre ``company`` (id de
    la société à exporter) : sans ce sélecteur, la requête est refusée en 400
    au lieu de produire un fichier mélangeant tous les tenants. Pour tout autre
    compte, la société reste celle de l'utilisateur et ``company`` est ignoré.
    """
    builder = _BUILDERS.get(entity)
    if builder is None:
        return Response({'detail': 'Entité inconnue.'}, status=400)
    corps = corps_valide(request, _EXPORT_LISTE_REQUETE)
    company_id = None
    if not request.user.company_id and request.user.is_superuser:
        company_id = corps.get('company')
        if not company_id:
            return Response(
                {'company': 'Sélecteur de société obligatoire : un compte sans '
                            'société doit désigner la société à exporter.'},
                status=400)
    ids = corps.get('ids') or []
    # APRF15 (C-APRF-028) — comme le jumeau leads (``export-xlsx``), l'export
    # des devis exporte une SÉLECTION : ``ids`` vide n'exporte plus toute la
    # société (aucune borne) mais répond 400. Les autres entités sont
    # inchangées ici (garde APRF28). ENF11 (api-fuzz) : la règle dépend de
    # l'entité du chemin, que le schéma d'un corps partagé ne sait pas dire —
    # c'est un refus d'ÉTAT de la sélection (409), plus une requête malformée.
    if entity == 'devis' and not ids:
        return Response(
            {'detail': 'Sélection requise : sélectionnez au moins un devis '
                       'à exporter.'},
            status=409)
    filename, headers, rows, title = builder(request.user, ids, company_id)
    return build_xlsx_response(filename, headers, rows, sheet_title=title)
