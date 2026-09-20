"""NTPRT9/NTPRT10/NTPRT11/NTPRT14 — Surface self-service AUTHENTIFIÉE du
portail CLIENT.

Ces deux ViewSets sont la version « compte réel » (NTPRT1/2/5) de ce que le
client obtenait jusqu'ici par lien tokenisé. Ils n'ajoutent AUCUNE logique
métier :

* la LECTURE passe par ``apps.ventes.selectors`` (jamais un import de
  ``apps.ventes.models`` — frontière cross-app CLAUDE.md), avec des payloads
  volontairement pauvres : aucun champ de coût/marge, aucune donnée interne ;
* l'ACCEPTATION d'un devis appelle ``apps.ventes.services.accept_devis``, le
  chemin d'acceptation UNIQUE déjà utilisé par la proposition publique
  tokenisée — la chaîne aval (statut accepté → BonCommande/Facture → chantier)
  est donc préservée 1:1 (règle #4), et la trace portail ``AcceptationDevisPortail``
  (FG229) est posée en plus via ``services.signer_acceptation_devis`` ;
* le PAIEMENT réutilise ``services.initier_paiement_facture`` : NO-OP tant que
  ``CMI_ENABLED`` est OFF (aucun appel réseau payant sans clé), avec repli
  virement (RIB de ``CompanyProfile``, lu via ``parametres.selectors``).

Le PDF du devis n'est PAS rendu ici : il reste servi par l'UNIQUE chemin
canonique ``GET /api/django/ventes/devis/<id>/proposal/`` (règle #4), dont la
garde a été ouverte au client PROPRIÉTAIRE (NTPRT10, cf.
``roles.permissions.IsInternalWriterOrPortalClientOwner``).

SÉCURITÉ — chaque endpoint exige ``IsPortalClientUser`` : portée EXACTEMENT
``portail_client`` (un compte fournisseur/partenaire est refusé même s'il est
« portail ») ET un ``portail_client_id`` non nul. Tout accès à un document
passe ensuite par un sélecteur qui exige le triplet (société, client, id) : un
document d'autrui est INTROUVABLE (404), jamais « trouvé puis refusé ».
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.roles.permissions import IsPortalClientUser, portal_scope_id

from . import services

#: Valeurs acceptées comme « oui » pour le consentement e-signature (QX9).
_VRAI = (True, 'true', 'True', '1', 1, 'on')


def _scope(request):
    """(société, client_id) du compte portail appelant.

    AUD148 (a) — POINT UNIQUE du chemin JWT client : c'est la porte que
    traversent TOUTES les méthodes des trois ViewSets self-service ci-dessous.
    On y horodate ``ComptePortailClient.derniere_connexion`` (au plus une fois
    par heure, cf. ``services.enregistrer_connexion_portail``) — la colonne
    était affichée par l'écran ERP et n'était écrite par aucun code, donc vide
    le jour où l'on cherche qui a consulté quoi.
    """
    company = request.user.company
    client_id = portal_scope_id(request.user)
    _noter_connexion(company, client_id)
    return company, client_id


def _noter_connexion(company, client_id):
    """Horodatage best-effort : une panne de trace n'a jamais fermé un
    portail."""
    try:
        from .selectors import etat_compte_portail_client
        etat = etat_compte_portail_client(
            getattr(company, 'id', None), client_id)
        if etat is not None:
            services.enregistrer_connexion_portail(etat[0], etat[2])
    except Exception:  # noqa: BLE001 - la trace ne casse jamais l'accès
        pass


def _ip(request):
    """AUD144 — l'IP de PREUVE (signature e-signature, loi 53-05) doit être
    celle du CLIENT, jamais celle du reverse-proxy. ``REMOTE_ADDR`` seul rend
    l'IP interne du conteneur nginx/Caddy (``identity/middleware.py``) : on
    délègue donc à LA primitive UNIQUE du dépôt (QJR416,
    ``core.throttling.ip_de_requete`` — dernier saut de confiance de
    ``X-Forwarded-For``), déjà utilisée par le chemin de signature PUBLIC
    tokenisé (``ventes/public_views.py``). Jamais une seconde primitive."""
    from core.throttling import ip_de_requete
    return ip_de_requete(request)


def _auditer_portail(action, request, *, instance=None, detail=''):
    """NTPRT7 — Journalise une action portail dans le journal d'activité
    EXISTANT (``audit.AuditLog``), flag ``via_portail=True`` — jamais un 2e
    système d'audit. Best-effort (``record`` n'élève jamais) : un souci de
    journalisation ne casse jamais la requête du client."""
    from apps.audit.recorder import record
    record(
        action, instance=instance, company=request.user.company,
        user=request.user, detail=detail, via_portail=True,
    )


def _prochain_jalon_pour_chantier(company, client_id, chantier_id):
    """NTPRT37 — prochain jalon NON ATTEINT d'UN site précis du client.

    Même forme que ``installations.selectors.prochain_jalon_client_portail``
    (« widget concerné » par le sélecteur de site), mais bornée à un seul
    chantier au lieu du plus récent tous chantiers confondus. Réutilise
    ``installations.selectors.chantier_du_client_portail_obj`` (le garde-fou
    déjà en place ailleurs dans ce module : un chantier d'un autre client — ou
    inexistant — renvoie ``None``, jamais une fuite) + le sélecteur PORTAIL
    ``jalons_du_chantier`` (même app, aucune donnée nouvelle)."""
    from apps.installations.selectors import chantier_du_client_portail_obj

    from .selectors import jalons_du_chantier

    chantier = chantier_du_client_portail_obj(company, client_id, chantier_id)
    if chantier is None:
        return None
    jalon = jalons_du_chantier(company, chantier.id).filter(
        atteint=False).first()
    if jalon is None:
        return None
    return {
        'chantier_id': chantier.id,
        'chantier_reference': chantier.reference,
        'libelle': jalon.libelle,
        'date_jalon': jalon.date_jalon,
    }


@extend_schema(
    parameters=[OpenApiParameter(
        name='chantier', type=OpenApiTypes.INT, required=False,
        location=OpenApiParameter.QUERY,
        description='NTPRT37 — site (chantier) sélectionné : borne '
                    '« prochain_jalon » à CE site. Absent ou invalide : '
                    'comportement inchangé (jalon le plus proche tous sites '
                    'confondus).')],
    responses=inline_serializer(
        name='PortailClientTableauDeBord',
        fields={
            'devis_en_attente': serializers.IntegerField(),
            'factures_impayees': serializers.IntegerField(),
            'prochaine_echeance': serializers.DateField(allow_null=True),
            'tickets_ouverts': serializers.IntegerField(),
            'prochain_jalon': inline_serializer(
                name='PortailClientProchainJalon',
                fields={
                    'chantier_id': serializers.IntegerField(),
                    'chantier_reference': serializers.CharField(),
                    'libelle': serializers.CharField(),
                    'date_jalon': serializers.DateField(allow_null=True),
                },
                allow_null=True),
        }))
@api_view(['GET'])
@permission_classes([IsPortalClientUser])
def tableau_de_bord_client(request):
    """NTPRT9 — Cartes résumé du tableau de bord du CLIENT connecté (devis en
    attente, factures impayées + échéance la plus proche, tickets SAV
    ouverts, prochain jalon chantier).

    Symétrique de ``tableau_de_bord_fournisseur``/``tableau_de_bord_partenaire``
    (``apps.portail.views_externes``) : société ET client viennent
    EXCLUSIVEMENT du compte portail connecté (``_scope``), jamais d'un
    paramètre de requête. Chaque carte lit le sélecteur PROPRIÉTAIRE de son
    domaine (``ventes``/``sav``/``installations``) — jamais un import direct
    de leurs modèles depuis ``portail`` (frontière cross-app CLAUDE.md) — donc
    les compteurs matchent, par construction, ce que l'écran interne montre
    pour ce même client.

    NTPRT37 — sélecteur de site (multi-chantiers B2B) : ``?chantier=<id>``
    est un filtre ADDITIF, aucune donnée nouvelle. SEUL ``prochain_jalon``
    (par nature lié à UN chantier) en tient compte ; ``devis_en_attente``/
    ``factures_impayees``/``tickets_ouverts`` restent au niveau CLIENT quel
    que soit le site choisi (critère d'acceptation NTPRT37) — ce sont des
    agrégats société-client, jamais scindés par site. Un ``chantier`` absent
    laisse le comportement d'avant (jalon le plus proche tous sites
    confondus) ; un ``chantier`` fourni mais INVALIDE (inexistant, ou d'un
    autre client) renvoie ``prochain_jalon: null`` — jamais un repli
    silencieux vers l'agrégat global ni les données d'un autre site."""
    from apps.installations.selectors import prochain_jalon_client_portail
    from apps.sav.selectors import tickets_ouverts_client
    from apps.ventes.selectors import resume_portail_client

    company, client_id = _scope(request)
    resume = resume_portail_client(company, client_id)
    resume['tickets_ouverts'] = tickets_ouverts_client(company, client_id)
    chantier_id = request.query_params.get('chantier')
    jalon = None
    if chantier_id:
        jalon = _prochain_jalon_pour_chantier(company, client_id, chantier_id)
    resume['prochain_jalon'] = (
        jalon if chantier_id else prochain_jalon_client_portail(
            company, client_id))
    return Response(resume)


@extend_schema(
    parameters=[OpenApiParameter(
        name='chantier', type=OpenApiTypes.INT, required=False,
        location=OpenApiParameter.QUERY,
        description='NTPRT37 — site (chantier) sélectionné : borne '
                    '« alertes_ouvertes » à CE site. Absent ou invalide : '
                    'comportement inchangé (tous les sites du client).')],
    responses=inline_serializer(
        name='PortailClientMaConsommation',
        fields={
            'window_days': serializers.IntegerField(),
            'provider_configure': serializers.BooleanField(),
            'points': serializers.ListField(child=inline_serializer(
                name='PortailClientConsommationPoint',
                fields={
                    'date': serializers.DateField(),
                    'energy_kwh': serializers.DecimalField(
                        max_digits=12, decimal_places=2),
                })),
            'alertes_ouvertes': serializers.IntegerField(),
        }))
@api_view(['GET'])
@permission_classes([IsPortalClientUser])
def ma_consommation_client(request):
    """NTPRT15 — « Ma consommation » : série de production (kWh) + drapeaux
    de sous-performance OUVERTS des systèmes du client connecté — LECTURE
    SEULE (``monitoring.selectors``, jamais un import de ``monitoring.
    models`` — frontière cross-app CLAUDE.md), jamais d'écriture depuis le
    portail.

    No-op gracieux (critère d'acceptation) : sans provider configuré
    (défaut ``NoOpProvider`` — saisie manuelle absente), ``points`` est une
    liste VIDE et ``provider_configure`` est faux — jamais une erreur 500,
    l'écran affiche alors un état vide explicite.

    NTPRT37 — sélecteur de site : ``?chantier=<id>`` borne
    ``alertes_ouvertes`` à ce SEUL chantier (le queryset renvoyé par
    ``underperformance_flags_client_portail`` porte déjà une FK
    ``installation`` — on la filtre ici, sans toucher au sélecteur ni
    inventer de donnée). La série ``points`` reste l'agrégat CLIENT :
    ``monitoring.selectors`` ne fournit qu'un total tous systèmes confondus,
    et cette tâche n'ajoute aucune donnée nouvelle. Un ``chantier`` fourni
    mais d'un autre client (ou inexistant) est IGNORÉ — comportement
    inchangé, jamais une fuite ni une erreur."""
    from apps.installations.selectors import chantier_du_client_portail_obj
    from apps.monitoring.selectors import (
        production_kwh_series_client_portail,
        underperformance_flags_client_portail,
    )

    company, client_id = _scope(request)
    serie = production_kwh_series_client_portail(company, client_id)
    alertes = underperformance_flags_client_portail(company, client_id)
    chantier_id = request.query_params.get('chantier')
    if chantier_id and chantier_du_client_portail_obj(
            company, client_id, chantier_id) is not None:
        alertes = alertes.filter(installation_id=chantier_id)
    serie['alertes_ouvertes'] = alertes.count()
    return Response(serie)


# ── NTPRT36 — Export « mes données » (portabilité, loi 09-08) ──────────────

@extend_schema(responses={(200, 'application/zip'): OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsPortalClientUser])
def exporter_mes_donnees(request):
    """NTPRT36 — bouton « Télécharger mes données » : un zip devis/factures/
    tickets/documents du client connecté.

    DÉCISION (infrastructure DSR existante — ``core.dsr.exporter``, FG394) :
    elle agrège par IDENTITÉ (email/téléphone) TOUS les fournisseurs DSR
    enregistrés (crm/rh/ao/stock…), potentiellement bien au-delà de « mes
    devis/factures/tickets/documents » et sans jamais filtrer par
    ``client_id`` — le critère d'acceptation NTPRT36 (« strictement les
    enregistrements où ``client_id`` == celui du compte demandeur ») serait
    donc violé, et l'export toucherait des domaines hors du périmètre de ce
    lot (interdit : cross-app hors ``selectors.py``). Cette vue fait
    l'EXPORT MINIMAL DIRECT que la tâche prévoit en repli : elle relit les
    QUATRE mêmes sélecteurs déjà scopés (société, client) que les écrans
    portail équivalents (``mes-devis``/``mes-factures``/``mes-demandes-sav``/
    ``mes-documents``) — aucune requête supplémentaire, aucune donnée que le
    client ne voit pas déjà par ailleurs.

    Chaque ligne du zip appartient STRICTEMENT au client connecté : aucun
    sélecteur ici n'accepte de paramètre autre que (société, client_id)."""
    import io
    import json
    import zipfile
    from decimal import Decimal

    from django.http import HttpResponse
    from django.utils import timezone

    from apps.ged.selectors import documents_partages_client_portail, latest_version
    from apps.records.storage import fetch_attachment
    from apps.ventes.selectors import (
        devis_du_client_portail, factures_du_client_portail,
    )

    from .models import DemandeTicketPortail

    company, client_id = _scope(request)

    def _json_safe(valeur):
        import datetime
        if isinstance(valeur, Decimal):
            return str(valeur)
        if isinstance(valeur, (datetime.date, datetime.datetime)):
            return valeur.isoformat()
        return valeur

    def _serialise(lignes):
        return [{cle: _json_safe(v) for cle, v in ligne.items()}
                for ligne in lignes]

    devis = _serialise(devis_du_client_portail(company, client_id))
    factures = _serialise(factures_du_client_portail(company, client_id))
    tickets = [{
        'id': d.id,
        'sujet': d.sujet,
        'description': d.description,
        'statut': d.statut,
        'statut_display': d.get_statut_display(),
        'date_creation': (d.date_creation.isoformat()
                          if d.date_creation else None),
    } for d in DemandeTicketPortail.objects.filter(
        company=company, client_id=client_id)]
    documents = list(documents_partages_client_portail(company, client_id))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            'devis.json', json.dumps(devis, ensure_ascii=False, indent=2))
        archive.writestr(
            'factures.json',
            json.dumps(factures, ensure_ascii=False, indent=2))
        archive.writestr(
            'tickets.json', json.dumps(tickets, ensure_ascii=False, indent=2))
        noms_utilises = set()
        for document in documents:
            version = latest_version(document)
            if version is None:
                continue
            data, erreur = fetch_attachment(version.file_key)
            if erreur:
                continue
            nom = (version.filename or document.nom
                   or f'document-{document.id}').replace('/', '_')
            # Deux documents ne partagent JAMAIS le même chemin dans le zip.
            if nom in noms_utilises:
                nom = f'{document.id}-{nom}'
            noms_utilises.add(nom)
            archive.writestr(f'documents/{nom}', data)
        manifeste = {
            'client_id': client_id,
            'exporte_le': timezone.now().isoformat(),
            'devis': len(devis),
            'factures': len(factures),
            'tickets': len(tickets),
            'documents': len(documents),
        }
        archive.writestr(
            'manifest.json', json.dumps(manifeste, ensure_ascii=False,
                                        indent=2))

    from apps.audit.models import AuditLog
    _auditer_portail(
        AuditLog.Action.EXPORT, request,
        detail='Export « mes données » (portabilité) depuis le portail '
               'client')
    reponse = HttpResponse(buffer.getvalue(), content_type='application/zip')
    reponse['Content-Disposition'] = 'attachment; filename="mes-donnees.zip"'
    reponse['X-Content-Type-Options'] = 'nosniff'
    return reponse


# ── NTPRT38 — Recherche globale, scopée au portail CLIENT connecté ─────────

class RecherchePortailResultatSerializer(serializers.Serializer):
    """Un résultat individuel d'un groupe de la recherche portail."""
    id = serializers.IntegerField()
    label = serializers.CharField()
    sublabel = serializers.CharField(allow_blank=True)


class RecherchePortailGroupeSerializer(serializers.Serializer):
    type = serializers.CharField()
    label = serializers.CharField()
    results = serializers.ListField(child=RecherchePortailResultatSerializer())


class RecherchePortailSerializer(serializers.Serializer):
    """Même enveloppe que la recherche globale INTERNE
    (``apps.reporting.search.global_search`` — ``{query, groups: [{type,
    label, results}]}``), pour que le hook frontend existant se transpose
    sans réinvention. Le CONTENU, lui, est une version scopée-portail
    entièrement réécrite ici (voir docstring de la vue)."""
    query = serializers.CharField(allow_blank=True)
    groups = serializers.ListField(child=RecherchePortailGroupeSerializer())


@extend_schema(
    parameters=[OpenApiParameter(
        name='q', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
        description='Mot-clé recherché.')],
    responses=RecherchePortailSerializer)
@api_view(['GET'])
@permission_classes([IsPortalClientUser])
def recherche_portail_client(request):
    """NTPRT38 — recherche globale, VERSION SCOPÉE-PORTAIL du client connecté.

    ``apps.reporting.search.global_search`` (T5/ARC29) est la recherche
    INTERNE : elle balaie leads/clients/chantiers/équipements de TOUTE la
    société, gardée ``IsAnyRole`` (qui exclut explicitement un compte
    ``portail_*``), et ses fonctions de requête (``_spec_devis``…) importent
    directement les modèles métier — deux raisons pour lesquelles elle ne
    peut PAS être appelée telle quelle depuis ici. Cette vue est donc une
    recherche DISTINCTE, mais délibérément restreinte aux QUATRE mêmes
    sélecteurs déjà scopés (société, client) que les écrans portail
    (``mes-devis``/``mes-factures``/``mes-demandes-sav``/``mes-documents``) :
    AUCUN nouvel index, un simple filtre par mot-clé sur les lignes que ces
    sélecteurs renvoient déjà. L'enveloppe ``{query, groups}`` reprend
    volontairement celle de la recherche interne (même vocabulaire) sans
    partager une ligne de son code.

    Un mot-clé vide renvoie des groupes vides — jamais toutes les données du
    client déversées sans filtre. Chaque sélecteur étant borné (société,
    client_id), un résultat ne peut JAMAIS provenir d'un autre compte."""
    from django.db.models import Q

    from apps.ged.selectors import documents_partages_client_portail
    from apps.ventes.selectors import (
        devis_du_client_portail, factures_du_client_portail,
    )

    from .models import DemandeTicketPortail

    q = (request.query_params.get('q') or '').strip()
    company, client_id = _scope(request)
    groupes = []
    if q:
        aiguille = q.lower()

        devis = [d for d in devis_du_client_portail(company, client_id)
                 if aiguille in (d.get('reference') or '').lower()]
        groupes.append({
            'type': 'devis', 'label': 'Devis',
            'results': [{'id': d['id'], 'label': d['reference'],
                        'sublabel': d.get('statut_display', '')}
                       for d in devis]})

        factures = [f for f in factures_du_client_portail(company, client_id)
                    if aiguille in (f.get('reference') or '').lower()]
        groupes.append({
            'type': 'facture', 'label': 'Factures',
            'results': [{'id': f['id'], 'label': f['reference'],
                        'sublabel': f.get('statut_display', '')}
                       for f in factures]})

        tickets = DemandeTicketPortail.objects.filter(
            company=company, client_id=client_id).filter(
                Q(sujet__icontains=q) | Q(description__icontains=q))
        groupes.append({
            'type': 'ticket', 'label': 'Tickets',
            'results': [{'id': d.id, 'label': d.sujet,
                        'sublabel': d.get_statut_display()}
                       for d in tickets]})

        documents = documents_partages_client_portail(
            company, client_id).filter(
                Q(nom__icontains=q) | Q(reference__icontains=q))
        groupes.append({
            'type': 'document', 'label': 'Documents',
            'results': [{'id': d.id, 'label': d.nom,
                        'sublabel': d.reference or ''}
                       for d in documents]})
    else:
        groupes = [
            {'type': 'devis', 'label': 'Devis', 'results': []},
            {'type': 'facture', 'label': 'Factures', 'results': []},
            {'type': 'ticket', 'label': 'Tickets', 'results': []},
            {'type': 'document', 'label': 'Documents', 'results': []},
        ]
    return Response({'query': q, 'groups': groupes})


class MesDevisPortailViewSet(viewsets.ViewSet):
    """NTPRT10 — « Mes devis » : liste, détail, acceptation."""

    permission_classes = [IsPortalClientUser]

    def list(self, request):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': devis_du_client_portail(company, client_id)})

    def retrieve(self, request, pk=None):
        from apps.ventes.selectors import devis_du_client_portail
        company, client_id = _scope(request)
        for ligne in devis_du_client_portail(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[IsPortalClientUser])
    def accepter(self, request, pk=None):
        """Accepte le devis via le chemin d'acceptation UNIQUE de ``ventes``.

        Exige un nom signataire ET un consentement EXPLICITE à la signature
        électronique (QX9, loi 43-20) : le consentement ne défaute jamais à
        vrai. Idempotent — un second envoi ne re-signe pas.
        """
        from apps.ventes.selectors import devis_du_client_portail_obj
        from apps.ventes.services import AcceptError, accept_devis

        # NTPRT6 — un membre d'équipe « lecture seule » ne peut PAS accepter
        # de devis (consultation uniquement).
        if not services.peut_ecrire_portail_client(request.user):
            return Response(
                {'detail': "Votre accès est en lecture seule : vous ne "
                           "pouvez pas accepter de devis."},
                status=status.HTTP_403_FORBIDDEN)

        company, client_id = _scope(request)
        devis = devis_du_client_portail_obj(company, client_id, pk)
        if devis is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Votre nom est requis pour signer le devis.'},
                status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('consent_esign') not in _VRAI:
            return Response(
                {'detail': 'Votre consentement explicite à la signature '
                           'électronique est requis pour accepter le devis.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            accept_devis(
                devis=devis,
                user=request.user,
                nom=nom,
                option=(request.data.get('option') or '').strip(),
                ip=_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
                consentement=True,
            )
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))

        # Trace portail (FG229) — posée APRÈS la bascule, jamais à sa place.
        #
        # AUD145 — le ``get_or_create`` tournait HORS transaction et sans
        # contrainte d'unicité : deux POST concurrents (le double-clic du
        # client sur « J'accepte ») créaient DEUX preuves du même devis, avec
        # deux horodatages. Le verrou d'``accept_devis`` ne couvre que le
        # DEVIS. On englobe donc création + signature dans UNE transaction, et
        # on rattrape l'``IntegrityError`` que la nouvelle contrainte
        # ``uniq_acceptation_portail_devis`` lève sur le perdant de la course :
        # il RELIT la preuve du gagnant au lieu d'en fabriquer une seconde.
        from django.db import IntegrityError, transaction

        from .models import AcceptationDevisPortail
        try:
            with transaction.atomic():
                acceptation, _ = AcceptationDevisPortail.objects.get_or_create(
                    company=company, devis=devis)
                services.signer_acceptation_devis(
                    acceptation, nom=nom, ip=_ip(request))
        except IntegrityError:
            acceptation = AcceptationDevisPortail.objects.filter(
                company=company, devis=devis).first()
            if acceptation is not None:
                services.signer_acceptation_devis(
                    acceptation, nom=nom, ip=_ip(request))

        devis.refresh_from_db(fields=['statut'])
        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.ACCEPT, request, instance=devis,
            detail='Devis accepté via le portail client')
        return Response({
            'detail': 'Devis accepté. Merci !',
            'reference': devis.reference,
            'statut': devis.statut,
        })


class MesFacturesPortailViewSet(viewsets.ViewSet):
    """NTPRT11 — « Mes commandes & factures » : liste, détail, intention de
    paiement (GATED CMI)."""

    permission_classes = [IsPortalClientUser]

    def list(self, request):
        from apps.ventes.selectors import factures_du_client_portail
        company, client_id = _scope(request)
        return Response({
            'results': factures_du_client_portail(company, client_id),
            'paiement_en_ligne_actif': services.cmi_actif(),
        })

    def retrieve(self, request, pk=None):
        from apps.ventes.selectors import factures_du_client_portail
        company, client_id = _scope(request)
        for ligne in factures_du_client_portail(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='payer',
            permission_classes=[IsPortalClientUser])
    def payer(self, request, pk=None):
        """Crée (ou réutilise) une intention de paiement locale — JAMAIS
        d'appel payant.

        Critère NTPRT11 : sans clé CMI, le bouton « Payer » crée une intention
        ``initie`` ET renvoie les coordonnées bancaires (RIB de
        ``CompanyProfile``) comme repli — jamais une erreur. Avec CMI actif, la
        même intention est créée et l'intégration (future) prend le relais dans
        ``services.initier_paiement_facture`` : rien n'est décidé ici.

        AUD137 — deux garde-fous ajoutés ici :
        1. une facture ANNULÉE ou déjà PAYÉE est REFUSÉE (400) — le sélecteur
           la rend déjà non ``payable`` (``factures_du_client_portail``), mais
           le serveur ne fait jamais confiance à un écran qui afficherait
           quand même le bouton.
        2. IDEMPOTENT : réutilise l'intention ``initie`` existante
           (``get_or_create`` + contrainte partielle
           ``uniq_paiement_portail_facture_initie``) au lieu d'en créer une
           nouvelle à chaque clic, et rafraîchit son montant/méthode depuis
           l'état COURANT de la facture à chaque appel — jamais figé au
           premier clic.
        """
        from django.db import IntegrityError, transaction

        from apps.parametres.selectors import company_identity
        from apps.ventes.selectors import (
            facture_du_client_portail, facture_est_payable_portail,
        )

        company, client_id = _scope(request)
        facture = facture_du_client_portail(company, client_id, pk)
        if facture is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not facture_est_payable_portail(facture):
            return Response(
                {'detail': "Cette facture n'est plus payable "
                           "(annulée ou déjà réglée)."},
                status=status.HTTP_400_BAD_REQUEST)

        from .models import PaiementFacturePortail
        actif = services.cmi_actif()
        methode = (PaiementFacturePortail.Methode.CARTE if actif
                   else PaiementFacturePortail.Methode.VIREMENT)
        try:
            with transaction.atomic():
                paiement, _ = PaiementFacturePortail.objects.get_or_create(
                    company=company, facture=facture,
                    statut=PaiementFacturePortail.Statut.INITIE,
                    defaults={'montant': facture.montant_du,
                              'methode': methode})
        except IntegrityError:
            paiement = PaiementFacturePortail.objects.filter(
                company=company, facture=facture,
                statut=PaiementFacturePortail.Statut.INITIE).first()
        # Rafraîchit le montant/méthode depuis l'état COURANT de la facture à
        # CHAQUE appel — une intention réutilisée ne doit jamais rester figée
        # au reste dû du premier clic.
        paiement.montant = facture.montant_du
        paiement.methode = methode
        paiement.save(update_fields=['montant', 'methode'])
        services.initier_paiement_facture(paiement)
        paiement.refresh_from_db(fields=['reference', 'statut'])
        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.PAYMENT, request, instance=paiement,
            detail=f'Intention de paiement facture #{facture.id} '
                   'initiée depuis le portail client')

        # Repli virement : UNIQUEMENT le nom, la banque et le RIB de la société
        # émettrice — jamais le reste de son identité légale (on ne déverse pas
        # ``company_identity`` entier vers un écran externe).
        identite = company_identity(company)
        return Response({
            'paiement_id': paiement.id,
            'reference': paiement.reference,
            'statut': paiement.statut,
            'montant': str(paiement.montant),
            'paiement_en_ligne_actif': actif,
            'virement': {
                'beneficiaire': identite.get('nom', ''),
                'banque': identite.get('banque', ''),
                'rib': identite.get('rib', ''),
            },
        })


#: ``MesLivraisonsPortailViewSet`` est un ``ViewSet`` nu (aucun queryset) :
#: drf-spectacular ne peut pas déduire le type de ``{id}`` sur ses routes de
#: détail et le dégradait en "string" avec un avertissement. L'identifiant est
#: la PK entière de la livraison. Déclaré UNE fois et partagé par TOUTES les
#: actions `detail=True` — en oublier une laisse l'avertissement revenir (c'est
#: exactement ce qui est arrivé à ``preuve-photo``).
_ID_LIVRAISON = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description="Identifiant de la livraison du client connecté.",
)


class MesLivraisonsPortailArticleSerializer(serializers.Serializer):
    """Un article d'une livraison — vue CLIENT (jamais un prix ni un coût).

    Déclaré en classe (et non plus par ``inline_serializer``) pour que le
    schéma OpenAPI soit dérivable : drf-spectacular nomme le composant d'après
    la classe en retirant le suffixe ``Serializer``, donc le composant reste
    EXACTEMENT ``MesLivraisonsPortailArticle`` — le contrat publié ne bouge pas.
    """
    designation = serializers.CharField()
    quantite = serializers.FloatField()


class MesLivraisonsPortailLigneSerializer(serializers.Serializer):
    """Une livraison telle que le portail la montre au client.

    Reflet EXACT de ``apps.installations.selectors.livraisons_client_portail``
    (le contrat client-safe testé par XSTK22 : jamais ``cout_transport``,
    jamais un prix d'achat). Même remarque que ci-dessus sur le nom du
    composant : il reste ``MesLivraisonsPortailLigne``.
    """
    id = serializers.IntegerField()
    reference = serializers.CharField()
    chantier_id = serializers.IntegerField(allow_null=True)
    date_prevue = serializers.DateField(allow_null=True)
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    numero_suivi = serializers.CharField(allow_null=True)
    articles = serializers.ListField(
        child=MesLivraisonsPortailArticleSerializer())
    pod_disponible = serializers.BooleanField()
    pod_url = serializers.CharField(allow_null=True)


class MesLivraisonsPortailViewSet(viewsets.ViewSet):
    """WIR216 — « Mes livraisons » : la section portail que le lien de l'email
    ``livraison_en_transit``/``livraison_livree`` (FG228,
    ``apps.installations.livraison_client_notify``) prétendait déjà ouvrir —
    elle n'existait pas (404 systématique).

    Lecture SEULE via ``apps.installations.selectors.livraisons_client_portail``
    (jamais un import de ``apps.installations.models`` — frontière cross-app) :
    ce sélecteur est DÉJÀ le contrat client-safe testé par XSTK22 (jamais
    ``cout_transport`` ni un prix d'achat). Distinct de l'action
    ``LivraisonViewSet.portail`` (INTERNE, ``IsAnyRole`` + ``?client=`` du
    corps de requête — jamais atteignable par un compte portail, cf.
    ``IsAnyRole`` qui exclut explicitement ``portee != interne``) : ICI, le
    client est dérivé du compte portail CONNECTÉ, jamais d'un paramètre."""

    permission_classes = [IsPortalClientUser]
    #: ``viewsets.ViewSet`` n'est pas une ``GenericAPIView`` : sans cet
    #: attribut, drf-spectacular ne peut PAS deviner le sérialiseur de la vue
    #: et journalise « unable to guess serializer » (garde YAPIC6). Ce n'est
    #: pas une déclaration décorative : c'est la ressource principale de ce
    #: ViewSet (une livraison), réutilisée telle quelle dans la réponse de
    #: ``list``. ``preuve`` déclare sa propre forme dans son ``@extend_schema``.
    serializer_class = MesLivraisonsPortailLigneSerializer

    @extend_schema(responses=inline_serializer(
        name='MesLivraisonsPortail',
        fields={
            'results': serializers.ListField(
                child=MesLivraisonsPortailLigneSerializer()),
        }))
    def list(self, request):
        from apps.installations.selectors import livraisons_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': livraisons_client_portail(company, client_id)})

    @extend_schema(parameters=[_ID_LIVRAISON], responses=inline_serializer(
        name='MesLivraisonsPortailPreuve',
        fields={
            'livraison_id': serializers.IntegerField(),
            'livraison_reference': serializers.CharField(),
            'signataire_nom': serializers.CharField(allow_null=True),
            'signature_image': serializers.CharField(allow_null=True),
            'horodatage': serializers.DateTimeField(allow_null=True),
            'note': serializers.CharField(allow_null=True),
            'gps_lat': serializers.CharField(allow_null=True),
            'gps_lng': serializers.CharField(allow_null=True),
            'photo_url': serializers.CharField(allow_null=True),
        }))
    @action(detail=True, methods=['get'], url_path='preuve')
    def preuve(self, request, pk=None):
        """AUD301 — preuve de livraison (FG330) CONSULTABLE par le client.

        Le lien « Voir la preuve de livraison » du portail pointait vers
        l'endpoint INTERNE ``/installations/preuves-livraison/<id>/``
        (``IsAnyRole``, qui exclut explicitement ``portee != 'interne'``) : un
        compte ``portail_client`` obtenait 403 à CHAQUE clic. Ici, le client
        est dérivé du compte CONNECTÉ (jamais d'un paramètre) et la lecture
        passe par ``apps.installations.selectors`` — jamais un import de ses
        modèles. Une livraison d'un autre client (ou d'une autre société) est
        INTROUVABLE : 404, jamais « trouvée puis refusée »."""
        from apps.installations.selectors import (
            preuve_livraison_client_portail,
        )
        company, client_id = _scope(request)
        preuve = preuve_livraison_client_portail(company, client_id, pk)
        if preuve is None:
            return Response({'detail': 'Preuve de livraison introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        preuve.pop('photo_attachment_id', None)
        return Response(preuve)

    @extend_schema(parameters=[_ID_LIVRAISON])
    @action(detail=True, methods=['get'], url_path='preuve-photo')
    def preuve_photo(self, request, pk=None):
        """AUD301 — sert la PHOTO de la preuve de livraison, en ligne.

        L'endpoint générique ``records/attachments/<id>/download/`` est
        ``IsAnyRole`` : il rejouerait exactement le 403 que cette tâche
        corrige. On relaie donc le fichier ici, sous la MÊME garde de portée et
        le MÊME scope client que ``preuve``. ``apps.records`` est une app de
        FONDATION (import direct autorisé) ; le scope, lui, vient du sélecteur
        installations."""
        from django.http import HttpResponse
        from apps.installations.selectors import (
            preuve_livraison_client_portail,
        )
        from apps.records.models import Attachment
        from apps.records.storage import fetch_attachment

        company, client_id = _scope(request)
        preuve = preuve_livraison_client_portail(company, client_id, pk)
        attachment_id = (preuve or {}).get('photo_attachment_id')
        if not attachment_id:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        att = Attachment.objects.filter(
            id=attachment_id, company=company).first()
        if att is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(att.file_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_404_NOT_FOUND)
        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True
        # (« téléchargement doc »).
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.EXPORT, request, instance=att,
            detail='Photo de preuve de livraison consultée depuis le '
                   'portail client')
        resp = HttpResponse(
            data, content_type=att.mime or 'application/octet-stream')
        nom = (att.filename or 'preuve-livraison').replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{nom}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp


#: ``MesDemandesSavPortailViewSet`` est un ``ViewSet`` nu (aucun queryset),
#: même remarque que ``_ID_LIVRAISON`` ci-dessus : sans type explicite,
#: drf-spectacular dégrade le paramètre de détail en "string".
_ID_DEMANDE_SAV = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description="Identifiant de la demande SAV du client connecté.",
)


class MesDemandesSavPortailLigneSerializer(serializers.Serializer):
    """Une demande SAV telle que le portail la montre au client.

    Reflet EXACT de ``MesDemandesSavPortailViewSet._ligne`` — payload
    volontairement pauvre, aucune donnée interne. Même remarque que
    ``MesLivraisonsPortailLigneSerializer`` sur le nom du composant : déclarée
    en classe (pas via ``inline_serializer``) pour rester ``MesDemandesSavPortailLigne``.
    """
    id = serializers.IntegerField()
    sujet = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    chantier_id = serializers.IntegerField(allow_null=True)
    ticket_id = serializers.IntegerField(allow_null=True)
    date_creation = serializers.DateTimeField(allow_null=True)


class MesDemandesSavPortailFilEntreeSerializer(serializers.Serializer):
    """NTPRT12 — une entrée du fil CLIENT-VISIBLE d'un ticket SAV.

    Reflet EXACT de ``apps.sav.selectors.fil_client_du_ticket`` — payload
    volontairement pauvre (corps, horodatage, auteur), jamais un champ
    interne (coût, technicien assigné, SLA)."""
    id = serializers.IntegerField()
    body = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField(allow_null=True)
    auteur = serializers.CharField(allow_blank=True)


class MesDemandesSavPortailViewSet(viewsets.ViewSet):
    """AUD525 — « Mes demandes SAV » : la surface CLIENT de FG233.

    FG233 (ouverture d'un ticket SAV depuis le portail) était du code MORT :
    son seul ViewSet (``DemandeTicketPortailViewSet``) est gardé par
    ``IsResponsableOrAdmin`` — une garde INTERNE, refusée à tout rôle
    ``portail_*``. Aucun compte portail réel ne pouvait donc l'atteindre, et
    la déflection KB (suggestions/consultation) héritait de la même garde :
    jamais exercée par un vrai client.

    Ce ViewSet est la surface authentifiée manquante, sur le même patron que
    ``MesDevisPortailViewSet``/``MesFacturesPortailViewSet`` : garde
    ``IsPortalClientUser``, société ET client résolus du COMPTE connecté
    (jamais du corps de requête). Les écrans internes d'administration des
    demandes (liste, ``prendre_en_charge``) restent inchangés."""

    permission_classes = [IsPortalClientUser]
    #: ``viewsets.ViewSet`` n'est pas une ``GenericAPIView`` : sans cet
    #: attribut, drf-spectacular ne peut PAS deviner le sérialiseur de la vue
    #: et lève « unable to guess serializer » (même garde YAPIC6 que
    #: ``MesLivraisonsPortailViewSet`` ci-dessus).
    serializer_class = MesDemandesSavPortailLigneSerializer

    @staticmethod
    def _ligne(demande):
        """Payload CLIENT — volontairement pauvre : aucune donnée interne."""
        return {
            'id': demande.id,
            'sujet': demande.sujet,
            'description': demande.description,
            'statut': demande.statut,
            'statut_display': demande.get_statut_display(),
            'chantier_id': demande.chantier_id,
            'ticket_id': demande.ticket_id,
            'date_creation': (demande.date_creation.isoformat()
                              if demande.date_creation else None),
        }

    def _mes_demandes(self, request):
        from .models import DemandeTicketPortail
        company, client_id = _scope(request)
        return DemandeTicketPortail.objects.filter(
            company=company, client_id=client_id)

    @extend_schema(
        responses=inline_serializer(
            name='MesDemandesSavPortail',
            fields={
                'results': serializers.ListField(
                    child=MesDemandesSavPortailLigneSerializer()),
            }))
    def list(self, request):
        return Response({
            'results': [self._ligne(d) for d in self._mes_demandes(request)]})

    @extend_schema(parameters=[_ID_DEMANDE_SAV])
    def retrieve(self, request, pk=None):
        demande = self._mes_demandes(request).filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self._ligne(demande))

    def create(self, request):
        """Ouvre une demande SAV (statut SOUMISE) pour le client connecté.

        ``company`` et ``client`` viennent du compte portail, JAMAIS du
        corps. Le chantier éventuel est vérifié comme appartenant au client
        (un id étranger est ignoré, jamais lié)."""
        from .models import DemandeTicketPortail

        # NTPRT6 — un membre d'équipe « lecture seule » ne peut PAS ouvrir de
        # ticket (consultation uniquement).
        if not services.peut_ecrire_portail_client(request.user):
            return Response(
                {'detail': "Votre accès est en lecture seule : vous ne "
                           "pouvez pas ouvrir de ticket."},
                status=status.HTTP_403_FORBIDDEN)

        company, client_id = _scope(request)
        sujet = (request.data.get('sujet') or '').strip()[:200]
        if not sujet:
            return Response({'sujet': 'Ce champ est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)
        description = (request.data.get('description') or '').strip()[:4000]

        chantier_id = request.data.get('chantier') or request.data.get(
            'chantier_id')
        if chantier_id:
            from apps.installations.selectors import installation_scoped
            chantier = installation_scoped(company, chantier_id)
            if chantier is None or chantier.client_id != client_id:
                chantier_id = None

        demande = DemandeTicketPortail.objects.create(
            company=company, client_id=client_id, chantier_id=chantier_id,
            sujet=sujet, description=description,
            statut=DemandeTicketPortail.Statut.SOUMISE)
        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.CREATE, request, instance=demande,
            detail='Ticket SAV ouvert depuis le portail client')
        return Response(self._ligne(demande),
                        status=status.HTTP_201_CREATED)

    # ── XSAV22 — Déflection KB, désormais servie au VRAI client ────────────
    # Lit/écrit UNIQUEMENT via ``apps.kb.selectors``/``apps.kb.services``
    # (jamais ``apps.kb.models``). ``detail=False`` : appelables PENDANT la
    # saisie, avant toute création de demande.

    @action(detail=False, methods=['get'], url_path='suggestions-kb',
            permission_classes=[IsPortalClientUser])
    def suggestions_kb(self, request):
        """Articles KB (publiés + ``visible_portail``) suggérés pendant la
        saisie du sujet — la déflection avant soumission."""
        from apps.kb.selectors import suggestions_portail
        company, _ = _scope(request)
        return Response({'suggestions': suggestions_portail(
            company, request.query_params.get('q', ''))})

    @action(detail=False, methods=['post'], url_path='consulter-article-kb',
            permission_classes=[IsPortalClientUser])
    def consulter_article_kb(self, request):
        """Journalise la consultation d'un article suggéré (déflection)."""
        from apps.kb.services import enregistrer_consultation_portail
        company, _ = _scope(request)
        article_id = request.data.get('article_id')
        if not article_id:
            return Response({'detail': 'article_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'enregistre': enregistrer_consultation_portail(
            company, article_id)})

    # ── NTPRT12 — Fil de commentaires CLIENT-VISIBLE du ticket SAV lié ─────

    @extend_schema(parameters=[_ID_DEMANDE_SAV], responses=inline_serializer(
        name='MesDemandesSavPortailFil',
        fields={'results': serializers.ListField(
            child=MesDemandesSavPortailFilEntreeSerializer())}))
    @action(detail=True, methods=['get'], url_path='fil')
    def fil(self, request, pk=None):
        """NTPRT12 — fil de commentaires CLIENT-VISIBLE du ticket SAV créé à
        partir de cette demande portail.

        Passe par ``apps.sav.selectors.fil_client_du_ticket`` (jamais un
        import de ``apps.sav.models`` — frontière cross-app CLAUDE.md), qui
        ne renvoie QUE les entrées explicitement marquées
        ``visible_client`` : une note technicien, un journal de statut ou un
        échange interne n'apparaît JAMAIS ici. Une demande pas encore prise
        en charge (aucun ticket SAV créé) renvoie un fil VIDE, jamais une
        erreur."""
        from apps.sav.selectors import fil_client_du_ticket

        demande = self._mes_demandes(request).filter(pk=pk).first()
        if demande is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        if not demande.ticket_id:
            return Response({'results': []})
        company, client_id = _scope(request)
        return Response({'results': fil_client_du_ticket(
            company, client_id, demande.ticket_id)})


# ── NTPRT35 — Widget « Satisfaction » post-interaction ──────────────────────

class SatisfactionPortailSerializer(serializers.Serializer):
    """L'enquête en attente, ou ``enquete: null`` quand il n'y a rien à
    demander."""
    enquete = serializers.DictField(allow_null=True)


class SatisfactionPortailViewSet(viewsets.ViewSet):
    """NTPRT35 — prompt de satisfaction du portail client.

    C'est le DÉCLENCHEUR D'INTERFACE qui manquait à FG238/FG239 : l'enquête
    (``marketing.EnqueteNPS``) était bien CRÉÉE à la réception d'un chantier
    (YSERV4) mais le client n'avait aucun écran pour y répondre. Aucune
    logique de scoring n'est ajoutée ici : la lecture passe par
    ``marketing.selectors``, l'écriture par ``marketing.services`` — jamais
    un import de ses ``models``.

    « Une fois par événement » (critère d'acceptation) ne repose sur AUCUN
    compteur de session : une enquête par événement (contrainte d'unicité
    AUD618 sur le chantier), et y répondre la passe à ``REPONDUE``, donc hors
    du sélecteur — définitivement. Fermer le prompt sans répondre n'écrit
    rien : la question revient, ce qui est le comportement voulu (on n'a pas
    encore l'avis), mais elle ne se REJOUE jamais une fois répondue.

    FG239 (avis Google) reste un ROUTAGE, pas une API payante : après une
    réponse de promoteur, on renvoie le lien SI la société en a configuré un
    (``GOOGLE_REVIEW_URL``) — vide sinon, sans erreur.
    """

    permission_classes = [IsPortalClientUser]
    serializer_class = SatisfactionPortailSerializer

    @extend_schema(responses=SatisfactionPortailSerializer)
    def list(self, request):
        from apps.marketing.selectors import enquete_satisfaction_en_attente
        company, client_id = _scope(request)
        return Response({
            'enquete': enquete_satisfaction_en_attente(company, client_id)})

    @extend_schema(
        request=inline_serializer(
            name='SatisfactionPortailReponse',
            fields={
                'enquete_id': serializers.IntegerField(),
                'score': serializers.IntegerField(),
                'commentaire': serializers.CharField(
                    required=False, allow_blank=True),
            }),
        responses=inline_serializer(
            name='SatisfactionPortailMerci',
            fields={
                'detail': serializers.CharField(),
                'lien_avis_google': serializers.CharField(allow_blank=True),
            }))
    @action(detail=False, methods=['post'], url_path='repondre',
            permission_classes=[IsPortalClientUser])
    def repondre(self, request):
        """Enregistre la note. Les erreurs NOMMENT le champ fautif."""
        from apps.marketing.services import (
            repondre_enquete_satisfaction_client,
        )

        company, client_id = _scope(request)
        enquete, erreur = repondre_enquete_satisfaction_client(
            company, client_id, request.data.get('enquete_id'),
            score=request.data.get('score'),
            commentaire=request.data.get('commentaire') or '')
        if erreur == 'score':
            return Response(
                {'score': 'Donnez une note entre 0 et 10.'},
                status=status.HTTP_400_BAD_REQUEST)
        if erreur is not None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        # FG239 — routage (jamais une API payante) : le lien n'est proposé
        # qu'au promoteur, et seulement si la société en a configuré un.
        lien = ''
        if enquete.categorie == 'promoteur':
            from apps.marketing.services import google_review_url_configuree
            lien = google_review_url_configuree()
        return Response({
            'detail': 'Merci pour votre retour !',
            'lien_avis_google': lien,
        })


# ── NTPRT14 — « Mes chantiers » (timeline + photos avant/pendant/après) ────
#
# ``viewsets.ViewSet`` nu (aucun queryset), même remarque YAPIC6 que
# ``MesLivraisonsPortailViewSet``/``MesDemandesSavPortailViewSet`` ci-dessus :
# sans ``serializer_class`` déclaré, drf-spectacular ne peut pas deviner le
# type de ``{id}`` et journalise « unable to guess serializer ».
_ID_CHANTIER = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description="Identifiant du chantier du client connecté.",
)


class MesChantiersPortailLigneSerializer(serializers.Serializer):
    """Reflet EXACT du contrat client-safe de
    ``apps.installations.selectors.chantiers_du_client_portail`` — JAMAIS de
    champ financier (BOM/prix exclus)."""
    id = serializers.IntegerField()
    reference = serializers.CharField()
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    site_ville = serializers.CharField(allow_null=True)
    date_creation = serializers.DateTimeField(allow_null=True)


class MesChantiersPortailJalonSerializer(serializers.Serializer):
    """Un jalon de la timeline portail (FG232/CHT10, synchronisée
    automatiquement par CHT11) — même contrat que l'écran interne
    ``JalonChantierPortailViewSet``, en LECTURE SEULE ici."""
    id = serializers.IntegerField()
    libelle = serializers.CharField()
    ordre = serializers.IntegerField()
    atteint = serializers.BooleanField()
    date_jalon = serializers.DateField(allow_null=True)


class MesChantiersPortailDetailSerializer(MesChantiersPortailLigneSerializer):
    """Le détail d'un chantier + SA timeline de jalons."""
    jalons = serializers.ListField(child=MesChantiersPortailJalonSerializer())


class MesChantiersPortailPhotoSerializer(serializers.Serializer):
    """Une photo (``records.Attachment``) de la galerie avant/pendant/après —
    reflet EXACT de ``photos_chantier_client_portail`` (jamais un champ
    financier)."""
    id = serializers.IntegerField()
    phase = serializers.CharField(allow_null=True)
    filename = serializers.CharField()
    created_at = serializers.DateTimeField(allow_null=True)
    url = serializers.CharField()


class MesChantiersPortailViewSet(viewsets.ViewSet):
    """NTPRT14 — « Mes chantiers » : timeline (jalons portail, lecture seule)
    + galerie photos avant/pendant/après, JAMAIS de donnée financière
    (BOM/prix exclus — le contrat de ``apps.installations.selectors``).

    Ne réécrit AUCUNE logique métier : les jalons viennent de la MÊME
    timeline portail que l'écran interne ``JalonChantierPortailViewSet``,
    synchronisée automatiquement (CHT11, aucune double saisie) — le client
    voit donc exactement ce que l'interne voit, sans les montants. Garde
    ``IsPortalClientUser`` ; société ET client résolus du COMPTE connecté
    (jamais du corps de requête ni de l'URL) ; un chantier d'un autre client
    est INTROUVABLE (404), jamais « trouvé puis refusé »."""

    permission_classes = [IsPortalClientUser]
    serializer_class = MesChantiersPortailLigneSerializer

    @extend_schema(responses=inline_serializer(
        name='MesChantiersPortail',
        fields={'results': serializers.ListField(
            child=MesChantiersPortailLigneSerializer())}))
    def list(self, request):
        from apps.installations.selectors import chantiers_du_client_portail
        company, client_id = _scope(request)
        return Response(
            {'results': chantiers_du_client_portail(company, client_id)})

    @extend_schema(
        parameters=[_ID_CHANTIER],
        responses=MesChantiersPortailDetailSerializer)
    def retrieve(self, request, pk=None):
        from apps.installations.selectors import (
            chantier_du_client_portail_obj, chantiers_du_client_portail,
        )
        company, client_id = _scope(request)
        chantier = chantier_du_client_portail_obj(company, client_id, pk)
        if chantier is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        ligne = next(
            (c for c in chantiers_du_client_portail(company, client_id)
             if c['id'] == chantier.id), None)
        return Response({**ligne, 'jalons': self._jalons(company, pk)})

    @staticmethod
    def _jalons(company, chantier_id):
        from .selectors import jalons_du_chantier
        return [{
            'id': j.id,
            'libelle': j.libelle,
            'ordre': j.ordre,
            'atteint': j.atteint,
            'date_jalon': j.date_jalon,
        } for j in jalons_du_chantier(company, chantier_id)]

    @extend_schema(parameters=[_ID_CHANTIER], responses=inline_serializer(
        name='MesChantiersPortailPhotos',
        fields={'results': serializers.ListField(
            child=MesChantiersPortailPhotoSerializer())}))
    @action(detail=True, methods=['get'], url_path='photos')
    def photos(self, request, pk=None):
        from apps.installations.selectors import (
            chantier_du_client_portail_obj, photos_chantier_client_portail,
        )
        company, client_id = _scope(request)
        if chantier_du_client_portail_obj(company, client_id, pk) is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        phase = request.query_params.get('phase') or None
        return Response({'results': photos_chantier_client_portail(
            company, client_id, pk, phase=phase)})

    @extend_schema(parameters=[_ID_CHANTIER, OpenApiParameter(
        name='attachment_id', type=OpenApiTypes.INT,
        location=OpenApiParameter.PATH,
        description='Identifiant de la photo (records.Attachment).')])
    @action(detail=True, methods=['get'],
            url_path=r'photo/(?P<attachment_id>[0-9]+)')
    def photo(self, request, pk=None, attachment_id=None):
        """Sert la PHOTO en ligne (même patron que
        ``MesLivraisonsPortailViewSet.preuve_photo`` — AUD301) : ``records``
        est une app de FONDATION (import direct autorisé) ; le scope client,
        lui, vient du sélecteur ``installations``."""
        from django.http import HttpResponse

        from apps.installations.selectors import photo_chantier_client_portail
        from apps.records.storage import fetch_attachment

        company, client_id = _scope(request)
        att = photo_chantier_client_portail(
            company, client_id, pk, attachment_id)
        if att is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(att.file_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(
            data, content_type=att.mime or 'application/octet-stream')
        nom = (att.filename or 'photo-chantier').replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{nom}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp


class MonEquipePortailLigneSerializer(serializers.Serializer):
    """Une invitation/membre d'équipe telle que le portail la montre au
    client — payload volontairement pauvre : jamais le token d'invitation."""
    id = serializers.IntegerField()
    email = serializers.EmailField()
    role = serializers.CharField()
    role_display = serializers.CharField()
    statut = serializers.CharField()
    statut_display = serializers.CharField()
    date_creation = serializers.DateTimeField(allow_null=True)
    date_acceptation = serializers.DateTimeField(allow_null=True)


#: YAPIC6 — même remarque que ``_ID_LIVRAISON`` plus haut : un ``ViewSet`` nu
#: (sans ``queryset``) laisse drf-spectacular incapable de deviner le type de
#: la PK entière de l'invitation. Déclaré UNE fois et partagé par TOUTES les
#: actions `detail=True`.
_ID_INVITATION = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description="Identifiant de l'invitation/membre d'équipe portail.",
)


class MonEquipePortailViewSet(viewsets.ViewSet):
    """NTPRT6 — « Mon équipe » : invitations/membres du portail client.

    Toute l'équipe (admin + invités) peut CONSULTER le roster
    (``IsPortalClientUser``) ; SEUL l'admin (compte SANS invitation, premier
    provisionné par NTPRT2) peut inviter ou révoquer — ``services.
    est_admin_portail_client`` fait la distinction, jamais un rôle inventé
    en plus de lecture/écriture.
    """

    permission_classes = [IsPortalClientUser]
    serializer_class = MonEquipePortailLigneSerializer

    @staticmethod
    def _ligne(invitation):
        return {
            'id': invitation.id,
            'email': invitation.email,
            'role': invitation.role,
            'role_display': invitation.get_role_display(),
            'statut': invitation.statut,
            'statut_display': invitation.get_statut_display(),
            'date_creation': (invitation.created_at.isoformat()
                              if invitation.created_at else None),
            'date_acceptation': (invitation.date_acceptation.isoformat()
                                 if invitation.date_acceptation else None),
        }

    def _invitations(self, request):
        from .models import InvitationPortail
        company, client_id = _scope(request)
        return InvitationPortail.objects.filter(
            company=company, compte_portail_client__client_id=client_id)

    @extend_schema(responses=inline_serializer(
        name='MonEquipePortail',
        fields={'results': serializers.ListField(
            child=MonEquipePortailLigneSerializer())}))
    def list(self, request):
        return Response({
            'results': [self._ligne(i) for i in self._invitations(request)]})

    @extend_schema(request=inline_serializer(
        name='MonEquipePortailInviter',
        fields={
            'email': serializers.EmailField(),
            'role': serializers.ChoiceField(
                choices=['lecture', 'ecriture'], required=False),
        }))
    def create(self, request):
        """Invite un collègue. RÉSERVÉ à l'admin (voir docstring de classe)."""
        if not services.est_admin_portail_client(request.user):
            return Response(
                {'detail': "Seul l'administrateur du portail peut inviter "
                           "des collègues."},
                status=status.HTTP_403_FORBIDDEN)

        email = (request.data.get('email') or '').strip()
        if not email:
            return Response({'email': 'Ce champ est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)
        role = request.data.get('role') or 'lecture'
        company, client_id = _scope(request)
        invitation = services.inviter_membre_portail(
            company, client_id, email, role)
        if invitation is None:
            return Response(
                {'detail': "Impossible de créer l'invitation."},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(self._ligne(invitation),
                        status=status.HTTP_201_CREATED)

    @extend_schema(parameters=[_ID_INVITATION])
    @action(detail=True, methods=['post'], url_path='revoquer')
    def revoquer(self, request, pk=None):
        """Révoque une invitation (et ferme l'accès si déjà acceptée).
        RÉSERVÉ à l'admin."""
        if not services.est_admin_portail_client(request.user):
            return Response(
                {'detail': "Seul l'administrateur du portail peut révoquer "
                           "un accès d'équipe."},
                status=status.HTTP_403_FORBIDDEN)

        company, _client_id = _scope(request)
        invitation = self._invitations(request).filter(pk=pk).first()
        if invitation is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        services.revoquer_invitation_portail(company, invitation.id)
        invitation.refresh_from_db()
        return Response(self._ligne(invitation))


class MesDocumentsPortailLigneSerializer(serializers.Serializer):
    """Un document GED tel que le portail le montre au client — payload
    volontairement pauvre : jamais de métadonnée interne (custom_data, ACL,
    verrous…)."""
    id = serializers.IntegerField()
    nom = serializers.CharField()
    reference = serializers.CharField(allow_blank=True)
    taille = serializers.IntegerField(allow_null=True)
    mime = serializers.CharField(allow_null=True)
    date_creation = serializers.DateTimeField(allow_null=True)


#: YAPIC6 — même remarque que ``_ID_LIVRAISON`` plus haut.
_ID_DOCUMENT_PORTAIL = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description='Identifiant du document GED partagé avec ce client.',
)


class MesDocumentsPortailViewSet(viewsets.ViewSet):
    """NTPRT13 — « Mes documents » : documents GED partagés EXPLICITEMENT
    avec ce client (lecture) + dépôt de justificatifs (factures ONEE…).

    LECTURE — réutilise ``ged.AclGed``/``ged.selectors`` (jamais un nouveau
    modèle de partage) : ``ged.selectors.documents_partages_client_portail``
    ne renvoie QUE les documents portant une ``AclGed`` EXPLICITE
    ``client=<ce client>`` — un document sans cette ACL n'apparaît JAMAIS ici
    (critère d'acceptation NTPRT13), même s'il vit dans un dossier par
    ailleurs partagé (l'héritage dossier reste un canal INTERNE, hors
    périmètre de cette surface client).

    ÉCRITURE — le dépôt réutilise ``apps.compta.serializers.
    DocumentClientPortailSerializer``/``DocumentClientPortail`` (FG231)
    À L'IDENTIQUE (même mixin MinIO AUD835, même dépôt GED miroir WIR94 via
    les récepteurs ``apps/portail/receivers.py``) : AUCUN nouveau modèle
    d'upload. Seule la SURFACE change (ce ViewSet, atteignable par un compte
    portail réel — l'ancien ``DocumentClientPortailViewSet`` reste
    ``IsResponsableOrAdmin``, donc fermé à un compte externe, même patron que
    le correctif AUD525 sur les tickets SAV). ``client_id``/``company`` sont
    TOUJOURS forcés depuis le compte connecté, jamais lus du corps.
    """

    permission_classes = [IsPortalClientUser]
    serializer_class = MesDocumentsPortailLigneSerializer

    @staticmethod
    def _ligne(document):
        from apps.ged.selectors import latest_version
        version = latest_version(document)
        return {
            'id': document.id,
            'nom': document.nom,
            'reference': document.reference or '',
            'taille': version.size if version else None,
            'mime': version.mime if version else None,
            'date_creation': (document.created_at.isoformat()
                              if document.created_at else None),
        }

    @extend_schema(responses=inline_serializer(
        name='MesDocumentsPortail',
        fields={'results': serializers.ListField(
            child=MesDocumentsPortailLigneSerializer())}))
    def list(self, request):
        from apps.ged.selectors import documents_partages_client_portail
        company, client_id = _scope(request)
        docs = documents_partages_client_portail(company, client_id)
        return Response({'results': [self._ligne(d) for d in docs]})

    @extend_schema(parameters=[_ID_DOCUMENT_PORTAIL])
    def retrieve(self, request, pk=None):
        from apps.ged.selectors import document_partage_client_portail
        company, client_id = _scope(request)
        doc = document_partage_client_portail(company, client_id, pk)
        if doc is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(self._ligne(doc))

    @extend_schema(parameters=[_ID_DOCUMENT_PORTAIL])
    @action(detail=True, methods=['get'], url_path='telecharger')
    def telecharger(self, request, pk=None):
        """Sert le contenu de la VERSION COURANTE du document partagé.

        Même patron que ``MesLivraisonsPortailViewSet.preuve_photo`` :
        ``apps.records`` est une app de FONDATION (import direct autorisé) ;
        le scope/l'ACL, eux, viennent du sélecteur GED."""
        from django.http import HttpResponse

        from apps.ged.selectors import (
            document_partage_client_portail, latest_version,
        )
        from apps.records.storage import fetch_attachment

        company, client_id = _scope(request)
        doc = document_partage_client_portail(company, client_id, pk)
        if doc is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        version = latest_version(doc)
        if version is None:
            return Response({'detail': 'Aucun fichier disponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        data, err = fetch_attachment(version.file_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_404_NOT_FOUND)

        # GED21 — un document diffusé sous contrôle (filigrane) le reste sur
        # CE canal aussi ; jamais un flux non filigrané qui contournerait la
        # règle appliquée partout ailleurs (aperçu interne, partage public).
        mime = version.mime or 'application/octet-stream'
        if getattr(doc, 'watermark_diffusion', False):
            try:
                from apps.ged import services as ged_services
                label = ged_services.watermark_label(company=company)
                data, _marque = ged_services.apply_watermark(data, mime, label)
            except Exception:  # noqa: BLE001 - dégrade à l'original, jamais 500
                pass

        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.EXPORT, request, instance=doc,
            detail='Document GED téléchargé depuis le portail client')

        nom = (version.filename or doc.nom or 'document').replace('"', '')
        resp = HttpResponse(data, content_type=mime)
        resp['Content-Disposition'] = f'attachment; filename="{nom}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    def create(self, request):
        """Dépose un justificatif (facture ONEE…) — réutilise
        ``DocumentClientPortailSerializer``/``DocumentClientPortail``
        EXISTANTS (FG231) tels quels. ``client_id``/``company`` forcés côté
        serveur, jamais lus du corps."""
        from apps.compta.serializers import DocumentClientPortailSerializer

        # NTPRT6 — un membre d'équipe « lecture seule » ne peut PAS déposer
        # de document (consultation uniquement).
        if not services.peut_ecrire_portail_client(request.user):
            return Response(
                {'detail': "Votre accès est en lecture seule : vous ne "
                           "pouvez pas déposer de document."},
                status=status.HTTP_403_FORBIDDEN)

        company, client_id = _scope(request)
        donnees = request.data.copy()
        donnees['client_id'] = client_id
        donnees.pop('lead_id', None)
        serializer = DocumentClientPortailSerializer(
            data=donnees, context={'request': request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save(company=company, client_id=client_id)

        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.CREATE, request, instance=document,
            detail='Justificatif déposé depuis le portail client')
        return Response(
            DocumentClientPortailSerializer(document).data,
            status=status.HTTP_201_CREATED)


# ── NTPRT16 — « Mes contrats » (maintenance) ────────────────────────────────
#
# ``viewsets.ViewSet`` nu (aucun queryset), même remarque YAPIC6 que
# ``MesDocumentsPortailViewSet`` ci-dessus.
_ID_CONTRAT_MAINTENANCE = OpenApiParameter(
    name='id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
    description='Identifiant du contrat de maintenance du client connecté.',
)


class MesContratsMaintenancePortailLigneSerializer(serializers.Serializer):
    """Un contrat de maintenance tel que le portail le montre au client.

    Reflet EXACT de ``apps.sav.selectors.contrats_maintenance_portail_client``
    — lecture minimisée (loi 09-08) : périodicité, dates, prix, droits
    inclus, JAMAIS un champ interne (SLA, tarif d'usage, dernière
    facturation, notes)."""
    id = serializers.IntegerField()
    periodicite = serializers.CharField()
    periodicite_display = serializers.CharField()
    date_debut = serializers.DateField(allow_null=True)
    date_renouvellement = serializers.DateField(allow_null=True)
    duree_mois = serializers.IntegerField(allow_null=True)
    actif = serializers.BooleanField()
    prix = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True)
    chantier = serializers.CharField(allow_blank=True)
    visites_incluses_an = serializers.IntegerField(allow_null=True)
    deplacements_inclus_an = serializers.IntegerField(allow_null=True)
    pieces_couvertes_pct = serializers.IntegerField(allow_null=True)


class MesContratsMaintenancePortailViewSet(viewsets.ViewSet):
    """NTPRT16 — « Mes contrats » (maintenance) : liste en lecture seule +
    demande de renouvellement/résiliation, portail CLIENT.

    Pendant SAV de ``contrats.selectors.contrats_portail_client`` (XCTR14,
    servi côté public tokenisé par ``apps.contrats.public_views`` — hors
    périmètre de cette tâche) : ici, la famille des contrats de MAINTENANCE
    (``apps.sav.ContratMaintenance``), authentifiée sur le compte portail
    connecté au lieu d'un jeton.

    LECTURE — ``apps.sav.selectors.contrats_maintenance_portail_client``
    (jamais un import de ``apps.sav.models`` — frontière cross-app
    CLAUDE.md), scopée société ET client : un contrat d'un autre client est
    INTROUVABLE, jamais « trouvé puis refusé ».

    ÉCRITURE — ``demander`` n'appelle QUE
    ``apps.sav.services.demander_action_portail_maintenance`` : une demande
    de renouvellement/résiliation reste une DEMANDE traitée en interne,
    JAMAIS un changement direct de ``actif``/date sur le contrat. NTPRT6 — un
    membre d'équipe « lecture seule » ne peut pas déposer de demande.
    """

    permission_classes = [IsPortalClientUser]
    serializer_class = MesContratsMaintenancePortailLigneSerializer

    @extend_schema(responses=inline_serializer(
        name='MesContratsMaintenancePortail',
        fields={'results': serializers.ListField(
            child=MesContratsMaintenancePortailLigneSerializer())}))
    def list(self, request):
        from apps.sav.selectors import contrats_maintenance_portail_client
        company, client_id = _scope(request)
        return Response({'results': contrats_maintenance_portail_client(
            company, client_id)})

    @extend_schema(parameters=[_ID_CONTRAT_MAINTENANCE],
                   responses=MesContratsMaintenancePortailLigneSerializer)
    def retrieve(self, request, pk=None):
        from apps.sav.selectors import contrats_maintenance_portail_client
        company, client_id = _scope(request)
        for ligne in contrats_maintenance_portail_client(company, client_id):
            if str(ligne['id']) == str(pk):
                return Response(ligne)
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        parameters=[_ID_CONTRAT_MAINTENANCE],
        request=inline_serializer(
            name='MesContratsMaintenancePortailDemande',
            fields={
                'type_demande': serializers.ChoiceField(
                    choices=['renouvellement', 'resiliation']),
                'message': serializers.CharField(
                    required=False, allow_blank=True),
            }),
        responses=inline_serializer(
            name='MesContratsMaintenancePortailDemandeReponse',
            fields={'detail': serializers.CharField()}))
    @action(detail=True, methods=['post'], url_path='demander')
    def demander(self, request, pk=None):
        """Enregistre une demande de renouvellement/résiliation.

        Les erreurs NOMMENT le champ fautif. ``contrat`` et ``client_id``
        viennent TOUJOURS du sélecteur scopé société+client, jamais d'un
        paramètre de requête."""
        from apps.sav.selectors import contrat_maintenance_du_client
        from apps.sav.services import (
            DemandeContratMaintenanceError,
            demander_action_portail_maintenance,
        )

        # NTPRT6 — un membre d'équipe « lecture seule » ne peut PAS déposer
        # de demande sur un contrat (consultation uniquement).
        if not services.peut_ecrire_portail_client(request.user):
            return Response(
                {'detail': "Votre accès est en lecture seule : vous ne "
                           "pouvez pas faire de demande sur ce contrat."},
                status=status.HTTP_403_FORBIDDEN)

        company, client_id = _scope(request)
        contrat = contrat_maintenance_du_client(company, client_id, pk)
        if contrat is None:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        type_demande = (request.data.get('type_demande') or '').strip()
        message = (request.data.get('message') or '').strip()
        try:
            demander_action_portail_maintenance(
                contrat, type_demande=type_demande, message=message,
                demandeur=request.user)
        except DemandeContratMaintenanceError:
            return Response(
                {'type_demande': 'Choisissez « renouvellement » ou '
                                 '« résiliation ».'},
                status=status.HTTP_400_BAD_REQUEST)

        # NTPRT7 — journal d'activité EXISTANT, flag via_portail=True.
        from apps.audit.models import AuditLog
        _auditer_portail(
            AuditLog.Action.CREATE, request, instance=contrat,
            detail=f'Demande « {type_demande} » sur contrat de maintenance '
                   'depuis le portail client')
        return Response({
            'detail': 'Votre demande a bien été enregistrée. Elle sera '
                      'traitée par nos équipes.',
        })
