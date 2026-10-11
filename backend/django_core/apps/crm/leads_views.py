"""SPL77 — intake des leads : actions doublons / fusion / scan de carte /
questionnaire / ROI / premier contact / SLA / points de contact de
LeadViewSet (``LeadIntakeActionsMixin``), le rapport d'attribution et
PointContactViewSet, déplacés de ``views.py`` à l'identique (move only).

Règle d'import : ce module n'importe JAMAIS ``views.py``.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from core.viewsets import CompanyScopedModelViewSet
from .models import Lead, PointContact
from .serializers import LeadSerializer, PointContactSerializer, masquer_pii_dict
from .actions_crud import READ_ACTIONS, _PorteeEnfantsMixin
from . import activity
from . import schema_docs as sd
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, HasPermissionOrLegacy


@extend_schema(parameters=[sd.P_DEBUT, sd.P_FIN], responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def rapport_attribution(request):
    """ZSAL6 — Rapport d'attribution des leads par commercial + par source,
    croisé avec le résultat (conversion, CA signé). ?debut=&fin= (YYYY-MM-DD,
    optionnels) filtrent la période. Lecture seule."""
    user = request.user
    if not user.company_id:
        return Response({'par_commercial': [], 'par_source': []})
    from django.utils.dateparse import parse_date
    debut = parse_date(request.query_params.get('debut') or '') or None
    fin = parse_date(request.query_params.get('fin') or '') or None
    from .selectors import attribution_leads
    return Response(attribution_leads(user.company, debut=debut, fin=fin))


@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD]))
class PointContactViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """FG204 — journal multi-touch des points de contact d'un lead.

    Au-delà du first-touch (``Lead.canal``), on consigne chaque point de contact
    du parcours (Meta → site → WhatsApp → signature) pour une attribution
    multi-touch.

    Routes :
      GET/POST  /crm/points-contact/                    (filtre ?lead=<id>)
      GET/PATCH /crm/points-contact/{id}/
      DELETE    /crm/points-contact/{id}/
      GET       /crm/points-contact/attribution/?lead=  (résumé first/last-touch)

    Lecture tout rôle, écriture responsable/admin. Toujours scopé par société
    (TenantMixin) : la société et ``saisi_par`` sont posés côté serveur depuis
    l'utilisateur actif — jamais lus du corps de requête (multi-tenant).
    """
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
    serializer_class = PointContactSerializer
    queryset = PointContact.objects.select_related(
        'lead', 'company', 'saisi_par').all()
    filterset_fields = ['lead', 'canal']
    ordering_fields = ['ordre', 'date_contact', 'saisi_le', 'cout']
    ordering = ['ordre', 'date_contact', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Société et saisi_par toujours posés côté serveur ; date par défaut
        et ordre auto-incrémenté quand non fourni ; trace chatter."""
        from django.utils import timezone
        from django.db.models import Max
        lead = serializer.validated_data.get('lead')
        # date_contact par défaut : maintenant (le journal pose l'horodatage).
        date_contact = serializer.validated_data.get('date_contact')
        save_kwargs = {
            'company': self.request.user.company,
            'saisi_par': self.request.user,
        }
        if date_contact is None:
            save_kwargs['date_contact'] = timezone.now()
        # Ordre auto : si le client n'a pas posé d'ordre (>0), prend le max+1 du
        # journal de ce lead (chaque point de contact suit le précédent).
        ordre = serializer.validated_data.get('ordre') or 0
        if ordre == 0 and lead is not None:
            current_max = (
                PointContact.objects.filter(
                    company=self.request.user.company, lead=lead)
                .aggregate(m=Max('ordre'))['m'] or 0
            )
            save_kwargs['ordre'] = current_max + 1
        obj = serializer.save(**save_kwargs)
        # Trace dans le chatter du lead (best-effort, ne casse jamais la création).
        try:
            from . import activity
            activity.log_note(
                obj.lead, self.request.user,
                f"Point de contact ajouté : {obj.get_canal_display()}"
                + (f" ({obj.source})" if obj.source else "")
                + ".",
            )
        except Exception:
            pass


class LeadIntakeActionsMixin:
    """SPL77 — actions d'intake de LeadViewSet (doublons, fusion, scan de
    carte, questionnaire, ROI, premier contact, SLA, points de contact),
    déplacées de ``views.py`` à corps inchangés.

    ``get_permissions`` coopératif (patron SPL75) : il ne garde QUE ses
    actions, sinon ``super()`` (la chaîne finit sur ``_RepliIsAdminMixin``).
    get_permissions() PRIME sur le ``permission_classes`` de l'@action (bug
    CI #25) : les gardes vivent donc ICI, avec leurs actions.
    """

    def get_permissions(self):
        if self.action in ('duplicates', 'check_duplicates', 'doublons',
                           'roi_sources', 'sla_breach',
                           # MRY19 — lecture ouverte à tout rôle, comme
                           # `sla_breach`.
                           'kpi_premier_contact',
                           'points_contact', 'scan_carte'):
            # VTA4 — la lecture des leads exige le code fin ``crm_voir``.
            return [HasPermissionOrLegacy('crm_voir')()]
        if self.action == 'merge':
            # VX199 — fusion de lead : permission ERP FINE (crm_modifier).
            return [HasPermissionOrLegacy('crm_modifier')()]
        if self.action == 'questionnaire_lien':
            # L-QUEST — sans cette garde, `questionnaire-lien` retomberait
            # sur le `[IsAdminRole()]` final et la Commerciale — qui envoie
            # justement le questionnaire — serait refusée.
            return [IsResponsableOrAdmin()]
        return super().get_permissions()

    @extend_schema(responses=sd.liste('CrmLeadDoublon'))
    @action(detail=True, methods=['get'], url_path='duplicates',
            permission_classes=[IsAnyRole])
    def duplicates(self, request, pk=None):
        """Doublons probables (même téléphone/email normalisé, même société).

        `match_fort` (ADDITIF au contrat existant) distingue le rapprochement
        ordinaire — même téléphone OU même e-mail — de l'« identité forte » :
        même e-mail ET même téléphone, c.-à-d. très probablement le même
        client. Depuis que le webhook du site crée SYSTÉMATIQUEMENT un nouveau
        lead (plus aucune fusion silencieuse), c'est ce bandeau qui porte le
        rapprochement, et la fusion reste manuelle."""
        from .leads_doublons import find_duplicate_leads, is_strong_identity_match
        lead = self.get_object()
        dups = find_duplicate_leads(lead, queryset=self._leads_en_portee())
        # ACRM4 — PII vidée pour un rôle sans ``client_pii_voir``
        # (``match_fort`` est calculé AVANT, sur les vraies valeurs).
        return Response([
            masquer_pii_dict({
                'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                'societe': d.societe, 'telephone': d.telephone,
                'email': d.email, 'stage': d.stage,
                'is_archived': d.is_archived,
                'nb_devis': d.devis.count(),
                'match_fort': is_strong_identity_match(
                    d, phone=lead.telephone, email=lead.email),
            }, request.user)
            for d in dups
        ])

    @extend_schema(parameters=[sd.param('telephone'), sd.param('phone'), sd.param('email'), sd.param('exclude', OpenApiTypes.INT)], responses=sd.liste('CrmLeadDoublonControle'))
    @action(detail=False, methods=['get'], url_path='check-duplicates',
            permission_classes=[IsAnyRole])
    def check_duplicates(self, request):
        """Contrôle PRÉ-CRÉATION (et édition) : un téléphone/email saisi
        correspond-il déjà à un lead de la société ? Avertissement NON bloquant
        côté formulaire — la société vient du serveur, jamais du corps. Saisie
        libre acceptée (mêmes normaliseurs que la détection de doublons).
        ?exclude=<id> retire le lead en cours d'édition de ses propres doublons.
        `match_fort` : même forme de ligne que l'action `duplicates` ci-dessus
        (les deux listes sont fusionnées par le même bandeau côté rail)."""
        from .leads_doublons import find_duplicates_by_contact, is_strong_identity_match
        phone = request.query_params.get('telephone') or \
            request.query_params.get('phone')
        email = request.query_params.get('email')
        exclude = request.query_params.get('exclude')
        exclude_pk = exclude if (exclude or '').isdigit() else None
        dups = find_duplicates_by_contact(
            request.user.company, phone=phone, email=email,
            exclude_pk=exclude_pk, queryset=self._leads_en_portee())
        # ACRM4 — PII vidée pour un rôle sans ``client_pii_voir``.
        return Response([
            masquer_pii_dict({
                'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                'societe': d.societe, 'telephone': d.telephone,
                'email': d.email, 'stage': d.stage,
                'is_archived': d.is_archived,
                'nb_devis': d.devis.count(),
                'match_fort': is_strong_identity_match(
                    d, phone=phone, email=email),
            }, request.user)
            for d in dups
        ])

    @extend_schema(request={'multipart/form-data': sd.corps('CrmScanCarteRequest', file=serializers.FileField())}, responses=sd.OBJ)
    @action(detail=False, methods=['post'], url_path='scan-carte',
            permission_classes=[IsAnyRole],
            parser_classes=[MultiPartParser],
            throttle_classes=[ScopedRateThrottle])
    def scan_carte(self, request):
        """XSAL8 — Scan de carte de visite (photo) → pré-remplissage du modal
        « Lead express ». NE CRÉE JAMAIS de lead — renvoie les champs
        reconnus + un pré-check de doublons ; l'utilisateur valide avant
        toute création. Sans clé OCR configurée : 503 douce, aucun appel
        réseau. Aucune image persistée au-delà du traitement (en mémoire)."""
        from .leads_intake import CarteVisiteScanUnavailable, scan_carte_visite

        upload = request.FILES.get('file')
        if not upload:
            return Response(
                {'detail': 'Aucune image fournie.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            content = upload.read()
        finally:
            upload.close()

        try:
            # ACRM7 (jumeau) — doublons cherchés dans la PORTÉE.
            result = scan_carte_visite(
                company=request.user.company, file_bytes=content,
                queryset=self._leads_en_portee())
        except CarteVisiteScanUnavailable as exc:
            message = str(exc)
            unavailable = 'configuré' in message
            return Response(
                {'detail': message},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE if unavailable
                        else status.HTTP_400_BAD_REQUEST))
        # ACRM4 (jumeau) — les doublons pré-vérifiés sont des leads EXISTANTS :
        # leur PII suit la règle unique du masquage (``client_pii_voir``).
        for doublon in result.get('doublons') or []:
            masquer_pii_dict(doublon, request.user)
        return Response(result)

    scan_carte.throttle_scope = 'crm_ocr_scan'

    @extend_schema(parameters=[sd.P_ARCHIVED_FLAG], responses=sd.liste('CrmGroupeDoublons'))
    @action(detail=False, methods=['get'], url_path='doublons',
            permission_classes=[IsAnyRole])
    def doublons(self, request):
        """Atelier doublons : scanne TOUS les leads de la société et renvoie les
        clusters de doublons probables (téléphone / email / nom normalisé, et
        depuis CAD93 adresse / point GPS pour le « même foyer »), avec pour
        chacun un survivant suggéré (le plus complet, puis le plus récent).

        SUGGESTION seulement : aucune fusion n'est faite ici, `match_keys` dit
        POURQUOI chaque groupe est rapproché et la décision reste humaine."""
        from .leads_doublons import (
            find_duplicate_clusters,
            _completeness,
            cluster_match_keys,
            _MERGE_FILL_FIELDS,
            _est_vide,
        )
        from .models import LeadActivity
        include_archived = request.query_params.get('archived') in ('1', 'true')
        clusters, _ = find_duplicate_clusters(
            request.user.company, include_archived=include_archived,
            queryset=self._leads_en_portee())
        # Libellés FR des champs comblés à la fusion (aperçu avant confirmation).
        field_labels = activity.TRACKED_FIELDS
        out = []
        for group in clusters:
            suggested = max(
                group, key=lambda le: (_completeness(le), le.date_creation))
            others = [d for d in group if d.id != suggested.id]
            # Aperçu de fusion : devis + activités migrés, et champs vides du
            # survivant que les absorbés viendraient combler.
            devis_migres = sum(d.devis.count() for d in others)
            activites_migrees = sum(
                LeadActivity.objects.filter(lead=d).count() for d in others)
            # CAD106 — l'aperçu annonçait devis, activités et champs comblés,
            # JAMAIS les relances : on confirmait une fusion sans savoir que
            # des touches ouvertes allaient quitter leur plan. Le compte vient
            # de la MÊME définition que la fusion (`relances_ouvertes_de`),
            # jamais d'un second filtre qui dériverait.
            from .leads_fusion import relances_ouvertes_de
            relances_reprises = sum(
                relances_ouvertes_de(d).count() for d in others)
            champs_combles = []
            for field in _MERGE_FILL_FIELDS:
                # ACRM13 — la MÊME règle « vide » que la fusion (un 0 saisi
                # n'est jamais annoncé comme « complété »).
                cur = getattr(suggested, field, None)
                if _est_vide(suggested, field, cur):
                    if any(not _est_vide(d, field, getattr(d, field, None))
                           for d in others):
                        champs_combles.append(field_labels.get(field, field))
            out.append({
                'suggested_survivor_id': suggested.id,
                'match_keys': cluster_match_keys(group),
                'merge_preview': {
                    'devis': devis_migres,
                    'activites': activites_migrees,
                    'fiches_archivees': len(others),
                    'champs_combles': champs_combles,
                    # CAD106 — combien de touches OUVERTES quittent leur plan.
                    'relances': relances_reprises,
                },
                # ACRM4 — PII vidée pour un rôle sans ``client_pii_voir``.
                'members': [
                    masquer_pii_dict({
                        'id': d.id, 'nom': d.nom, 'prenom': d.prenom,
                        'societe': d.societe, 'telephone': d.telephone,
                        'email': d.email, 'ville': d.ville, 'stage': d.stage,
                        'is_archived': d.is_archived,
                        'nb_devis': d.devis.count(),
                        'nb_activites': LeadActivity.objects.filter(lead=d).count(),
                        'completeness': _completeness(d),
                        'date_creation': d.date_creation.isoformat(),
                    }, request.user)
                    for d in group
                ],
            })
        return Response(out)

    @extend_schema(request=sd.corps('CrmLeadMergeRequest', others=sd.ids_requis()), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='merge',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def merge(self, request, pk=None):
        """Fusionne d'autres leads DANS celui-ci (survivant). Sans perte :
        devis, chantiers, activités, pièces jointes et historique sont déplacés ;
        les leads absorbés sont archivés (jamais supprimés)."""
        from .leads_fusion import merge_leads
        survivor = self.get_object()
        ids = request.data.get('others') or []
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Aucun lead à fusionner.'},
                            status=status.HTTP_400_BAD_REQUEST)
        others = list(self.get_queryset().filter(pk__in=ids).exclude(pk=survivor.pk))
        if not others:
            return Response({'detail': 'Leads à fusionner introuvables.'},
                            status=status.HTTP_400_BAD_REQUEST)
        merge_leads(survivor, others, request.user)
        survivor.refresh_from_db()
        data = dict(
            LeadSerializer(survivor, context={'request': request}).data)
        # ACRM40 — clé ADDITIVE : les fiches client distinctes (gardée en
        # tête), vide quand il n'y en avait qu'une.
        data['clients_distincts'] = getattr(
            survivor, '_clients_distincts', [])
        return Response(data)

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='points-contact',
            permission_classes=[IsAnyRole])
    def points_contact(self, request, pk=None):
        """FG204 — journal multi-touch ordonné + résumé d'attribution du lead
        (first-touch vs last-touch). get_object() borne déjà à la société."""
        from .selectors import lead_touchpoints_attribution
        lead = self.get_object()
        summary = lead_touchpoints_attribution(
            lead, company=request.user.company)
        return Response({
            'lead_id': summary['lead_id'],
            'count': summary['count'],
            'first_touch': summary['first_touch'],
            'last_touch': summary['last_touch'],
            'cout_total': summary['cout_total'],
            'timeline': PointContactSerializer(
                summary['timeline'], many=True).data,
        })

    # ── L-QUEST — Questionnaire envoyable au client ──────────────────────────
    @extend_schema(request=sd.corps('CrmQuestionnaireLienRequest', questions=serializers.ListField(child=serializers.CharField(), required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='questionnaire-lien',
            permission_classes=[IsResponsableOrAdmin])
    def questionnaire_lien(self, request, pk=None):
        """Crée (ou réutilise) le lien questionnaire d'un lead et renvoie de
        quoi l'envoyer au client.

        Le commercial choisit les questions via ``questions`` ({section:
        true/false}) ; sans corps, ce sont les informations MANQUANTES qui
        sont posées (ordre fondateur). Idempotent : un re-POST sur le même
        lead renvoie le MÊME lien tant qu'il n'a pas expiré, avec ses
        questions mises à jour — jamais un second jeton chez le client.

        La réponse porte DEUX URL : ``url`` (celle du client, la seule à
        envoyer) et ``url_interne`` (aperçu commercial, muet — il ne
        déclenche rien et n'écrit rien). Contrat :
        ``apps/crm/contract_samples/questionnaire_lead.json``."""
        from . import questionnaire as quest

        lead = self.get_object()
        try:
            questions = quest.valider_questions(
                request.data.get('questions'), lead)
        except quest.SectionInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        lien, change, cree = quest.mint_lien(
            lead, questions=questions, user=request.user)
        # AGR411 — le filtre de segment : un lien résidentiel reste
        # identique à l'octet, un lien agricole ne nomme que ses sections.
        sections_lead = quest.sections_du_lead(lead)
        posees = [cle for cle in sections_lead if lien.question_posee(cle)]
        if change:
            # Recalage fold 25/08 — jamais « envoyé » : le serveur n'observe
            # pas l'envoi WhatsApp. « créé » à la première ouverture du
            # dialogue, « mis à jour » quand le commercial change les
            # questions ; un re-POST identique ne laisse aucune trace.
            verbe = ('créé' if cree else 'mis à jour')
            activity.log_note(
                lead, request.user,
                f'Lien questionnaire {verbe} (sections : '
                + ', '.join(quest.LIBELLE_SECTION[c] for c in posees) + ')')
        return Response({
            # Les DEUX URL pointent sur le SITE PUBLIC (``PUBLIC_SITE_URL``),
            # jamais sur l'hôte de cette requête : la page questionnaire vit
            # dans ``apps/web``, pas sur l'API — un lien construit sur l'hôte
            # de l'API partait mort chez le client (finding #6).
            'url': quest.url_publique(lien.token),
            'url_interne': quest.url_publique(lien.token_interne),
            'token': lien.token,
            'expires_at': lien.expires_at.isoformat(),
            'questions': {cle: lien.question_posee(cle)
                          for cle in sections_lead},
            'manquantes': quest.manquantes(lead),
        })

    # ── FG34 — ROI par source / campagne ────────────────────────────────────
    @extend_schema(parameters=[sd.param('from', OpenApiTypes.DATE), sd.param('to', OpenApiTypes.DATE), sd.param('canal')], responses=sd.liste('CrmRoiSource'))
    @action(detail=False, methods=['get'], url_path='roi-sources',
            permission_classes=[IsAnyRole])
    def roi_sources(self, request):
        """Agrégation ROI par canal et par campagne UTM.

        Renvoie pour chaque groupe :
          canal, utm_campaign (optionnel), lead_count, signed_count,
          win_rate (%), signed_value_ttc (somme des devis acceptés TTC).
        Filtres : ?from=YYYY-MM-DD &to=YYYY-MM-DD &canal=<key>
        """
        import datetime

        qs = self.get_queryset().filter(is_archived=False)

        # Filtres date optionnels
        from_ = request.query_params.get('from')
        to_ = request.query_params.get('to')
        if from_:
            try:
                qs = qs.filter(date_creation__date__gte=datetime.date.fromisoformat(from_))
            except ValueError:
                pass
        if to_:
            try:
                qs = qs.filter(date_creation__date__lte=datetime.date.fromisoformat(to_))
            except ValueError:
                pass
        canal_filter = request.query_params.get('canal')
        if canal_filter:
            qs = qs.filter(canal=canal_filter)

        # APRF19 — AGRÉGATS : comptes par (canal, campagne) en UNE requête
        # (prédicat « signé » unique d'ACRM31, clé d'étape lue de STAGES.py),
        # valeur signée sur les devis retenus par ACRM10, préchargés AVEC
        # leurs totaux — nombre de requêtes indépendant du nombre de
        # campagnes et de leads signés.
        from django.db.models import Count
        from apps.reporting.pipeline import leads_avec_devis_totaux
        from .selectors import _devis_compte_comme_signe, lead_signe_q

        base = Lead.objects.filter(pk__in=qs.values('pk'))
        groupes = list(
            base.order_by().values('canal', 'utm_campaign')
            .annotate(lead_count=Count('pk', distinct=True),
                      signed_count=Count('pk', filter=lead_signe_q(),
                                         distinct=True))
            .order_by('canal', 'utm_campaign'))
        valeurs = {}
        for lead in leads_avec_devis_totaux(base.filter(lead_signe_q())):
            cle = (lead.canal, lead.utm_campaign)
            for d in lead.devis.all():
                # ACRM10 — la V2 seule d'une révision acceptée.
                if not _devis_compte_comme_signe(d):
                    continue
                try:
                    valeurs[cle] = valeurs.get(cle, 0) + float(d.total_ttc)
                except Exception:
                    pass
        result = []
        for grp in groupes:
            lead_count = grp['lead_count']
            signed_count = grp['signed_count']
            signed_value = valeurs.get((grp['canal'], grp['utm_campaign']), 0)
            result.append({
                'canal': grp['canal'],
                'utm_campaign': grp['utm_campaign'],
                'lead_count': lead_count,
                'signed_count': signed_count,
                'win_rate': round(signed_count / lead_count * 100, 1)
                if lead_count else 0,
                'signed_value_ttc': round(signed_value, 2),
            })
        return Response(result)

    # ── MRY19 — KPI « rappelé en moins de N minutes OUVRÉES » ────────────────
    # PACT7 — même raison que `kpi_cadences` ci-dessous : un agrégat déclare
    # sa forme, sinon le schéma la remplace par celle du ViewSet.
    @extend_schema(parameters=[sd.P_JOURS], responses=inline_serializer('CrmKpiPremierContact', {
        'objectif_minutes': serializers.IntegerField(),
        'nb_leads': serializers.IntegerField(),
        'nb_sous_objectif': serializers.IntegerField(allow_null=True),
        'pct_sous_objectif': serializers.FloatField(allow_null=True),
        'mediane_minutes_ouvrees': serializers.IntegerField(allow_null=True),
        # CAD88 — le délai CALENDAIRE réel, à côté de l'ouvré (jamais à sa
        # place) : un lead du vendredi soir traité lundi n'est plus « tenu ».
        'mediane_minutes_calendaires': serializers.IntegerField(
            allow_null=True),
        'nb_nuit_rappeles_avant_930': serializers.IntegerField(
            allow_null=True),
        'nb_nuit': serializers.IntegerField(),
    }))
    @action(detail=False, methods=['get'], url_path='kpi-premier-contact',
            permission_classes=[IsAnyRole])
    def kpi_premier_contact(self, request):
        """Forme `kpi_premier_contact` (contrat MRY25). ``?jours=`` (30).

        Minutes OUVRÉES, leads OS_NATIVE seulement, `null` partout sur zéro
        lead — jamais un 0 % fabriqué. Ne touche PAS à `sla-breach`, dont le
        contrat est consommé tel quel par `CrmInsightsPanel`."""
        try:
            jours = max(1, min(365, int(request.query_params.get('jours', 30))))
        except (TypeError, ValueError):
            jours = 30
        from .selectors import kpi_premier_contact as _kpi
        return Response(_kpi(request.user.company, jours=jours))

    # ── FG28 — Filtre SLA non contactés ──────────────────────────────────────
    @extend_schema(responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='sla-breach',
            permission_classes=[IsAnyRole])
    def sla_breach(self, request):
        """Leads NEW non contactés depuis plus de lead_sla_hours (filtre SLA).

        Retourne les leads dont first_contacted_at est NULL, stage=NEW,
        créés il y a plus de lead_sla_hours heures (selon le profil société).
        """
        from django.utils import timezone
        import datetime
        from .leads_premier_contact import lead_sla_hours as get_sla_hours
        sla = get_sla_hours(request.user.company)
        if sla == 0:
            return Response({'sla_hours': 0, 'count': 0, 'results': []})
        cutoff = timezone.now() - datetime.timedelta(hours=sla)
        qs = self.get_queryset().filter(
            is_archived=False,
            stage='NEW',
            first_contacted_at__isnull=True,
            date_creation__lte=cutoff,
        ).order_by('date_creation')
        # CAD133 (fix CI #713) — les signaux comportement/fraîcheur sont annotés en
        # sous-requêtes, comme dans get_queryset() : sans cela chaque lead relit ses
        # agrégats (16 requêtes par carte sur la file du jour).
        from .signaux import annotations_signaux
        qs = qs.annotate(**annotations_signaux())
        # APRF18 — sérialisation EN LOT (mêmes cartes que la liste).
        return Response({
            'sla_hours': sla,
            'count': qs.count(),
            'results': self._serialiser_leads_en_lot(qs),
        })
