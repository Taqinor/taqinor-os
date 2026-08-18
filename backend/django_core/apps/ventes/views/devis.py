from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from drf_spectacular.utils import extend_schema  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
    DevisActionRequiseSerializer,  # PACT17 — forme déclarée de l'agrégat
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
)
# NTPRT10 — garde du chemin canonique /proposal ouverte au client PROPRIÉTAIRE
# depuis son portail (``apps.roles`` est une app FONDATION, pas un domaine).
from apps.roles.permissions import (  # noqa: F401
    IsInternalWriterOrPortalClientOwner, is_portal_user, portal_scope_id,
)
from core.viewsets import CompanyScopedModelViewSet  # noqa: F401  ARC5
# PV84 — builder UNIQUE du chemin proposition (nom-client inclus dans l'URL) ;
# jamais de f'/proposition/{token}' en dur ailleurs dans ce fichier.
from ..utils.client_links import chemin_proposition  # noqa: F401
from core.entite_scoping import EntiteScopeMixin  # noqa: F401  NTADM2
from core.idempotency import IdempotentCreateMixin  # noqa: F401  YAPIC9
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _gamme_envoi_payload(devis):
    """GAMME — bloc « envoi à la carte » pour la modale d'envoi de l'ERP.

    ``None`` quand le devis n'appartient pas à une paire de gammes : la modale
    d'envoi reste alors strictement celle d'aujourd'hui. Sinon : le libellé de
    CHAQUE gamme, laquelle est recommandée et le mode d'envoi courant (défaut
    « les_deux » — décision fondateur)."""
    from ..services import gamme_envoi, gamme_info, gamme_soeur
    soeur = gamme_soeur(devis)
    if soeur is None:
        return None
    ici, la_soeur = gamme_info(devis), gamme_info(soeur)
    recommandee = (la_soeur.get('nom') if la_soeur.get('recommandee')
                   else ici.get('nom'))
    return {
        'envoi': gamme_envoi(devis),
        'nom': ici.get('nom') or '',
        'soeur_nom': la_soeur.get('nom') or '',
        'soeur_reference': soeur.reference,
        'recommandee': recommandee or '',
    }


def _appliquer_gamme_envoi(devis, mode):
    """GAMME — applique le mode d'envoi demandé (no-op hors paire de gammes)."""
    from ..services import regler_envoi_gamme
    return regler_envoi_gamme(devis, mode)


def _emettre_layout_finalise(devis, user):
    """PV79 — annonce que la conception 3D d'un devis est finalisée.

    Passe par le bus ``core.events`` (M6) plutôt que par un appel direct à
    ``crm`` : les deux apps restent découplées, et un futur abonné (chantier,
    notifications…) se branche sans toucher ce fichier. Ne change AUCUN statut
    et n'écrit rien lui-même (règle #4).

    Jamais bloquant : un abonné en échec ne doit pas faire échouer la
    finalisation d'un calepinage déjà enregistré. L'erreur est journalisée.
    """
    from core.events import layout_finalise
    try:
        layout_finalise.send(sender='ventes.views.devis', devis=devis,
                             user=user)
    except Exception:  # noqa: BLE001 — un abonné cassé ne casse pas le devis
        import logging as _logging
        _logging.getLogger(__name__).exception(
            'PV79 : abonné en échec sur layout_finalise (devis %s)', devis.pk)


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class DevisViewSet(IdempotentCreateMixin, EntiteScopeMixin,
                   CompanyScopedModelViewSet):
    # YAPIC9 — pilote de core.idempotency.IdempotentCreateMixin : sans
    # en-tête `Idempotency-Key`, comportement inchangé (le mixin ne fait que
    # déléguer à super().create()). AVEC l'en-tête, un rejeu à corps
    # identique renvoie le devis initial (pas de doublon) ; corps différent
    # -> 409. perform_create ci-dessous reste la SEULE logique métier de
    # création — le mixin ne touche jamais à la sémantique devis/statuts.
    # ARC5 — sweep TenantMixin : base transverse unique (CompanyScopedModelViewSet
    # = TenantMixin + ModelViewSet). get_queryset (portée de visibilité +
    # _company_qs) / perform_create / perform_update / get_permissions SURCHARGENT
    # la base : scoping société et matrice 401/403/404 INCHANGÉS.
    #   Règle #4 : ce sweep ne touche NI le statut NI la sérialisation Devis. Le
    #   moteur ne change jamais les statuts. L'@action `proposal` (chemin canonique
    #   du PDF client, IsResponsableOrAdmin) reste une LECTURE AUTHENTIFIÉE scopée
    #   société : `self.get_object()` passe par get_queryset (devis d'une autre
    #   société → 404). Elle N'EST PAS un endpoint public — l'accès CLIENT au PDF
    #   passe par les vues tokenisées ShareLink de `public_views.py`
    #   (AllowAny, hors périmètre de ce sweep), qui restent inchangées.
    queryset = Devis.objects.select_related(
        'client', 'created_by', 'lead', 'bon_commande', 'signature',
        'superseded_by', 'version_parent',
    ).prefetch_related(
        # YOPSB13 — paiements/avoirs imbriqués préchargés : DevisSerializer.
        # get_solde (via solde_devis) itère f.paiements/f.avoirs PAR facture ;
        # sans ces prefetch c'était un N+1 imbriqué sur la liste.
        # SCA43 — `lignes__produit` (pas seulement `lignes`) : DevisSerializer.
        # _display appelle build_quote_data PAR DEVIS pour le total d'affichage,
        # et `_line_to_item` y lit `ligne.produit` (marque/description/garantie)
        # PAR LIGNE. Sans ce prefetch c'était un produit-par-ligne → N+1 qui
        # grandit avec le nombre de devis (même prefetch que
        # generate_premium_devis_pdf). Rend le total de liste O(1).
        'lignes', 'lignes__produit',
        'factures', 'factures__paiements', 'factures__avoirs',
        'share_links',
        # YOPSB13 — évite le N+1 de DevisSerializer.get_chantier (avant :
        # une requête Installation par devis via le sélecteur
        # installations.selectors.installation_for_devis appelé par ligne de
        # liste). String-FK cross-app (Installation.devis, related_name=
        # 'installations') — jamais d'import de apps.installations.models ici.
        'installations',
    ).all()

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # NTPRT10 — un compte PORTAIL externe ne voit QUE les devis de SON
        # client, sur TOUTE action. Appliqué AVANT la portée interne (qui
        # raisonne sur `created_by`, notion sans objet pour un externe) : un
        # devis d'autrui répond alors 404, jamais 403 — aucun oracle
        # d'existence. Un compte portail sans rattachement, ou d'une portée
        # autre que « client », ne voit RIEN (jamais tout).
        user = self.request.user
        if is_portal_user(user):
            scope = portal_scope_id(user)
            if (getattr(user, 'portee', None) != 'portail_client'
                    or scope is None):
                return qs.none()
            return qs.filter(client_id=scope)
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # devis qu'il a créés / son équipe. 'all' → inchangé.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        # Filtre optionnel ?lead=<id> — utilisé par le dialogue « Signé » (A2)
        # pour lister les devis d'un lead. Borné à la société par _company_qs.
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DevisWriteSerializer
        return DevisSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + [
            'historique', 'variante_config', 'superior_contact_status',
            # WIR96/WIR99 — deux LECTURES pures ouvertes à tout rôle (le
            # `permission_classes` de l'@action ne suffit PAS : get_permissions
            # PRIME et son repli est IsAdminRole).
            'suivi_partage', 'prefill_site',
        ]:
            # variante_config : la LECTURE est ouverte à tous ; l'ÉCRITURE (PUT)
            # est re-vérifiée dans l'action (Directeur / Commercial responsable).
            return [IsAnyRole()]
        elif self.action in ('accepter', 'refuser'):
            # VX199 — validation/refus de devis : permission ERP FINE
            # (ventes_valider), pas le grossier IsResponsableOrAdmin (qui passe
            # pour tout rôle portant une écriture). get_permissions PRIME sur le
            # permission_classes de l'@action, donc la garde fine doit être ICI.
            return [HasPermissionOrLegacy('ventes_valider')()]
        elif self.action == 'action_requise':
            # PACT17 — « Relances du jour » est une LECTURE agrégée réservée au
            # même périmètre que son entrée de menu (features/ventes/
            # module.config.jsx : roles responsable + admin), exactement comme
            # son miroir SAV `/sav/tickets/file-action/` (ZSAV6). La garde doit
            # être ICI : get_permissions PRIME sur le `permission_classes` de
            # l'@action (son repli est IsAdminRole, qui fermerait l'écran aux
            # responsables) — l'@action déclare donc la MÊME classe pour ne
            # jamais mentir sur la garde effective.
            return [IsResponsableOrAdmin()]
        elif self.action == 'proposal':
            # NTPRT10 — ``/proposal`` reste l'UNIQUE chemin PDF client (règle
            # #4) : plutôt qu'un second rendu pour le portail, on OUVRE ce
            # chemin au client PROPRIÉTAIRE. La garde reste
            # ``IsResponsableOrAdmin`` à l'identique côté INTERNE ; côté
            # portail elle exige la portée ``portail_client``, une méthode SÛRE
            # et — au niveau OBJET — ``devis.client_id == portail_client_id``
            # (le queryset ci-dessus borne déjà à ce même client).
            # NB : cette surcharge de ``get_permissions`` PRIME volontairement
            # sur le ``permission_classes`` de l'@action (cf. ``accepter``/
            # ``refuser``, VX199) — les deux déclarent donc la MÊME classe pour
            # ne jamais mentir sur la garde effective.
            return [IsInternalWriterOrPortalClientOwner()]
        elif self.action in WRITE_ACTIONS + [
            'generer_pdf', 'telecharger_pdf', 'convertir_en_bc',
            'generer_facture', 'reviser', 'noter',
            'layout', 'roof_image', 'from_layout', 'auto', 'share_link',
            'envoyer_email', 'dupliquer_variante', 'variantes', 'dupliquer',
            # GAMMES — création de la SŒUR « gamme ». Déclare la MÊME classe
            # que le permission_classes de l'@action (cette surcharge PRIME
            # sur lui — cf. le commentaire VX199 ci-dessus).
            'dupliquer_variante_gamme',
            'save_preset', 'apply_preset', 'contacter_superieur',
            'whatsapp', 'proforma_pdf',
            # QX21be — atomic create + replace-lines (self.action is the
            # Python method name, not url_path: 'replace-lines' → 'replace_lines').
            'atomic', 'replace_lines',
            # QX22be — WhatsApp preview (read-only, no status change).
            'whatsapp_preview',
            # NTCPQ8 — approbation de remise (lecture + décisions).
            'approbation', 'approuver_etape', 'rejeter_etape',
            # NTCPQ13 — renouvellement d'un devis accepté/expiré. Déclare la
            # MÊME classe que le permission_classes de l'@action (cette
            # surcharge PRIME sur lui — cf. le commentaire VX199 ci-dessus).
            'renouveler',
            # NTCPQ14 — avenants d'un devis accepté (lecture + application).
            'avenants',
            # NTCPQ18 — lots multi-sites (lecture + création).
            'lots',
            # NTCPQ20 — historique fin de configuration (lecture seule).
            'historique_configuration',
            # PV17 — contexte de l'écran de conception 3D. LECTURE, mais
            # réservée au même périmètre que le générateur de devis
            # (responsable + admin), pas ouverte à tout rôle. La garde doit
            # être ICI : get_permissions PRIME sur le ``permission_classes``
            # de l'@action (son repli est IsAdminRole) — l'@action déclare
            # donc la MÊME classe pour ne jamais mentir sur la garde
            # effective.
            'design_context',
            # PV18 — resynchronisation des lignes sur un nouveau calepinage
            # (écriture chirurgicale, jamais le statut).
            'sync_layout',
            # PV47 — report OPT-IN du bordereau électrique en lignes de devis.
            'ajouter_boq_electrique',
            # PV41 — étude électrique du devis (GET affiche, POST recalcule).
            # Même périmètre que le générateur (responsable + admin) : la garde
            # doit être ICI, get_permissions PRIME sur le
            # ``permission_classes`` de l'@action — qui déclare donc la MÊME
            # classe pour ne jamais mentir sur la garde effective.
            'conception_electrique',
            # PV74 — étude bankable asynchrone : lancement (202) et suivi du
            # job. Même périmètre que le générateur (responsable + admin) ; la
            # garde vit ICI car get_permissions PRIME sur le
            # ``permission_classes`` de l'@action, qui déclare la MÊME classe.
            'simuler', 'simulation_status',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from apps.crm.services import resolve_client_for_lead

        company = self.request.user.company
        lead = serializer.validated_data.get('lead')
        client = serializer.validated_data.get('client')

        # Tenant safety: lead and client must belong to the user's company.
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})

        # Lead-primary: when no client is given, resolve it from the lead
        # (reuses the linked/matching client, else creates one — no duplicates).
        if client is None:
            if lead is None:
                raise ValidationError(
                    {'client': 'Un client ou un lead est requis.'})
            client = resolve_client_for_lead(lead)

        # FG52 — devise : si le corps n'en fournit pas, appliquer la devise par
        # défaut de la société (CompanyProfile.devise_defaut), repli MAD.
        save_kwargs = dict(
            client=client,
            created_by=self.request.user,
            company=company,
        )
        if 'devise' not in serializer.validated_data:
            from apps.parametres.models import CompanyProfile
            save_kwargs['devise'] = (
                getattr(CompanyProfile.get(company=company), 'devise_defaut', '')
                or 'MAD')

        create_numbered(
            Devis, company, 'devis',
            lambda ref: serializer.save(reference=ref, **save_kwargs),
        )

        # Mouvement automatique du funnel CRM : un devis créé directement en
        # « envoyé »/« accepté » avance le lead (ancien statut ≡ brouillon).
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, Devis.Statut.BROUILLON,
            serializer.instance.statut, self.request.user,
        )

    @action(detail=False, methods=['post'], url_path='from-layout',
            permission_classes=[IsResponsableOrAdmin])
    def from_layout(self, request):
        """Q3/B1 — transforme un layout toiture 3D FINALISÉ en Devis brouillon,
        puis frappe un lien public de proposition.

        Corps : ``{layout, lead, client, taux_tva?, remise_globale?}``. Le
        ``layout`` est le JSON sérialisé tel que stocké par l'action ``layout``
        (AreaRecord[] + result + renderPlan). La société est TOUJOURS celle du
        user (jamais lue du corps) ; lead et client sont résolus bornés à cette
        société (404/400 si une autre société). Au moins un lead OU un client est
        requis. Aucun statut n'est touché : le service renvoie un brouillon
        (préservation des statuts, règle #4) et la numérotation anti-collision
        est gérée par le service.

        QJ17 — idempotency: if a brouillon devis with the same lead + layout hash
        already exists for this company, it is returned (HTTP 200) instead of
        creating a duplicate.  A pre-flight composition check validates the
        catalogue before building and returns HTTP 422 with inline French guidance
        on failure (instead of a PDF error at render time).
        """
        from decimal import Decimal, InvalidOperation
        from ..services import build_devis_from_layout, layout_hash, validate_composition_for_layout
        from ..models import ShareLink

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        layout = request.data.get('layout')
        if not isinstance(layout, dict) or not layout:
            return Response(
                {'detail': 'Layout manquant ou invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Résolution bornée société du lead et du client. On passe par les
        # sélecteurs/services crm (jamais d'import direct des models crm depuis
        # ventes) ; un id d'une autre société → 404 (introuvable dans la portée).
        lead_obj = None
        client_obj = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            from apps.crm.selectors import get_company_lead
            lead_obj = get_company_lead(company, lead_id)
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if client_id:
            from apps.crm.selectors import get_company_client
            client_obj = get_company_client(company, client_id)
            if client_obj is None:
                return Response({'detail': 'Client inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        if lead_obj is None and client_obj is None:
            return Response(
                {'detail': 'Un client ou un lead est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _dec(raw, default):
            if raw in (None, ''):
                return default
            try:
                return Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                return None

        taux_tva = _dec(request.data.get('taux_tva'), Decimal('20'))
        remise = _dec(request.data.get('remise_globale'), Decimal('0'))
        if taux_tva is None or remise is None:
            return Response(
                {'detail': 'taux_tva / remise_globale invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        # QJ17 — pre-flight composition check: validate catalogue before building.
        composition_errors = validate_composition_for_layout(layout, company)
        if composition_errors:
            return Response(
                {'detail': composition_errors[0], 'errors': composition_errors},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # QJ17 — idempotency: dedupe by lead + layout hash.
        # Re-clicking « Générer » returns the existing brouillon, not a duplicate.
        lhash = layout_hash(layout)
        existing = None
        if lead_obj is not None and lhash:
            existing = (
                Devis.objects.filter(
                    company=company,
                    lead=lead_obj,
                    statut=Devis.Statut.BROUILLON,
                    layout_hash=lhash,
                )
                .order_by('-date_creation')
                .first()
            )
        if existing is not None:
            link = ShareLink.for_devis(existing)
            import logging as _logging
            _logging.getLogger(__name__).info(
                'QJ17: dedup hit — returning existing brouillon %s (hash %s…)',
                existing.reference, lhash[:8])
            return Response(
                {
                    'id': existing.id,
                    'reference': existing.reference,
                    'statut': existing.statut,
                    'proposal_token': link.token,
                    'proposal_path': chemin_proposition(existing, link.token),
                    'deduplicated': True,
                },
                status=status.HTTP_200_OK)

        devis = build_devis_from_layout(
            layout=layout, user=request.user, company=company,
            lead=lead_obj, client=client_obj,
            taux_tva=taux_tva, remise_globale=remise)

        # QJ17 — persist the layout hash on the newly-created devis so future
        # duplicate requests are caught in O(1).
        if lhash:
            Devis.objects.filter(pk=devis.pk).update(layout_hash=lhash)
            devis.layout_hash = lhash

        # PV79 — la conception 3D est FINALISÉE. Aucun statut ne bouge : on
        # ANNONCE seulement le fait, et les abonnés (crm : note au chatter du
        # lead) réagissent — ventes n'importe donc jamais crm.
        _emettre_layout_finalise(devis, request.user)

        link = ShareLink.for_devis(devis)
        return Response(
            {
                'id': devis.id,
                'reference': devis.reference,
                'statut': devis.statut,
                'proposal_token': link.token,
                'proposal_path': chemin_proposition(devis, link.token),
            },
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='design-context',
            permission_classes=[IsResponsableOrAdmin])
    def design_context(self, request, pk=None):
        """PV17 — TOUT ce que l'écran de conception 3D doit savoir d'un devis,
        en UN SEUL appel et sous UNE SEULE forme.

        Renvoie ``{devis, geometrie, cible, carte, modifiable,
        raison_lecture_seule, avertissements}`` — toutes les clés TOUJOURS
        présentes (contrat ``contract_samples/devis_design_context.json``) : un
        panier vide vaut ``[]``, une valeur inconnue ``None``/``''``, jamais
        une clé absente. L'écran n'a donc rien à deviner et ne peut pas
        ``.map()`` sur ``undefined``.

        LECTURE PURE, scopée société par ``get_queryset`` (un devis d'une autre
        société → 404) : aucun statut, aucune ligne, aucun layout n'est écrit
        (règle #4)."""
        from ..selectors import contexte_conception_devis

        devis = self.get_object()  # borné société par get_queryset
        contexte = contexte_conception_devis(devis, request.user.company)
        if contexte is None:
            return Response({'detail': 'Devis inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(contexte)

    @action(detail=True, methods=['post'], url_path='sync-layout',
            permission_classes=[IsResponsableOrAdmin])
    def sync_layout(self, request, pk=None):
        """PV18 — resynchronise les LIGNES du devis sur un nouveau calepinage.

        Corps : le layout sérialisé (on accepte aussi les enveloppes
        ``{"layout": …}`` / ``{"roof_layout": …}``, comme l'action ``layout``).

        Mise à jour CHIRURGICALE d'un brouillon : quantités de panneaux,
        présence de la batterie et onduleur accordé au scénario — prix
        négociés, remises, sections, notes, ordre et groupes multi-villa
        restent intacts. PVHEAL — le KIT MANQUANT (structures, socles,
        accessoires, tableau AC/DC, installation, transport…) est en plus
        AJOUTÉ quand il manque, jamais re-tarifé quand il est là ; un
        composant introuvable ou non tarifé est sauté et DIT dans
        ``avertissements``, et ``lignes_ajoutees`` compte les ajouts. Le
        STATUT n'est jamais écrit (règle #4) : un devis « envoyé » répond 409
        avec ``revision_possible: true`` (le bon geste est « Réviser ») ; un
        devis accepté/refusé/expiré répond 409 avec ``revision_possible:
        false``. Renvoyer le MÊME layout ne fait aucune écriture
        (``inchange: true``). Devis d'une autre société → 404 (get_queryset)."""
        from ..services import sync_devis_from_layout, SyncLayoutError

        devis = self.get_object()  # borné société par get_queryset
        payload = request.data
        if isinstance(payload, dict):
            for enveloppe in ('layout', 'roof_layout'):
                if set(payload.keys()) == {enveloppe}:
                    payload = payload[enveloppe]
                    break
        if not isinstance(payload, dict) or not payload:
            return Response({'detail': 'Layout manquant ou invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = sync_devis_from_layout(devis, payload, request.user)
        except SyncLayoutError as exc:
            return Response(
                {'detail': exc.detail,
                 'revision_possible': exc.revision_possible},
                status=status.HTTP_409_CONFLICT)
        # PV79 — même annonce qu'à la création : la toiture vient d'être
        # redessinée et les lignes suivent. Un renvoi du MÊME layout
        # (``inchange``) n'annonce rien : il ne s'est rien passé.
        if not (isinstance(resultat, dict) and resultat.get('inchange')):
            _emettre_layout_finalise(devis, request.user)
        return Response(resultat)

    @action(detail=True, methods=['get', 'post'],
            url_path='conception-electrique',
            permission_classes=[IsResponsableOrAdmin])
    def conception_electrique(self, request, pk=None):
        """PV41 — l'ÉTUDE ÉLECTRIQUE du devis, en UN SEUL appel.

        ``GET`` renvoie l'étude rangée sur le devis, et la calcule si elle
        n'existe pas encore. ``POST`` la RECALCULE en appliquant les
        surcharges du corps (``dc_m``, ``ac_m``, ``phases``, ``regime``,
        ``batterie``, ``zone_keraunique``, ``temp_froid_c``, ``temp_chaud_c``,
        ``longueur_chaine_forcee``, ``plafond_kwc_par_onduleur`` — toute autre
        clé est ignorée). Les DEUX rendent EXACTEMENT la même forme, celle du
        contrat partagé ``contract_samples/conception_electrique.json``
        (``chaines``, ``conformite``, ``ratio_dc_ac``, ``ratio_ac_dc``,
        ``protections``, ``cables``, ``bom``, ``note``, ``parametres``) —
        toutes les clés TOUJOURS présentes, une liste vide valant ``[]``.

        Recalculer aux mêmes entrées n'écrit RIEN (empreinte identique,
        idempotence QJ17). Aucun statut, aucune ligne, aucun prix n'est touché
        — l'étude est une pièce technique et le moteur ne connaît aucun montant
        (règle #4 : ``/proposal`` reste le seul chemin du PDF client). Scopé
        société par ``get_queryset`` : un devis d'une autre société → 404.
        """
        from ..electrical_service import (
            build_electrical_design, conception_electrique_stockee)

        devis = self.get_object()  # borné société par get_queryset
        if request.method == 'GET':
            stockee = conception_electrique_stockee(devis)
            if stockee is not None:
                return Response(stockee)
            return Response(build_electrical_design(devis))
        surcharges = request.data if isinstance(request.data, dict) else {}
        return Response(build_electrical_design(devis, overrides=surcharges))

    @action(detail=True, methods=['post'], url_path='simuler',
            permission_classes=[IsResponsableOrAdmin])
    def simuler(self, request, pk=None):
        """PV74 — lance l'ÉTUDE BANKABLE du devis en tâche de fond → 202.

        L'étude interroge PVGIS par pan de toiture : la faire dans la requête
        bloquerait un slot serveur pendant des secondes et casserait au premier
        hoquet réseau. On répond donc immédiatement ``202`` avec un jeton et
        l'URL à interroger, exactement comme l'export asynchrone de cette app
        (SCA41) :

            {detail, job_id, status: 'pending', zones, status_url}

        Corps : ``{"force_refresh": true}`` pour ignorer le cache PVGIS (PV73)
        et refaire les appels réseau ; absent/false → un second calcul du même
        toit ne recoûte aucun aller-retour.

        Un devis SANS calepinage exploitable répond ``400`` plutôt que de
        lancer une étude vide. Le STATUT du devis n'est jamais écrit (règle #4 :
        la tâche ne pose que ``etude_params['simulation']``). Scopé société par
        ``get_queryset`` : un devis d'une autre société → 404.
        """
        import uuid

        from django.core.cache import cache

        from ..tasks import (
            SIMULATION_JOB_CACHE_TTL, simulation_job_cache_key,
            task_simulate_bankable_study, zones_etude_du_devis,
        )

        devis = self.get_object()  # borné société par get_queryset
        zones = zones_etude_du_devis(devis)
        if not zones:
            return Response(
                {'detail': ('Ce devis ne porte aucun pan de toiture '
                            'exploitable : dessinez le calepinage 3D avant de '
                            'lancer la simulation.')},
                status=status.HTTP_400_BAD_REQUEST)

        corps = request.data if isinstance(request.data, dict) else {}
        force_refresh = bool(corps.get('force_refresh'))

        token = uuid.uuid4().hex
        company = request.user.company
        # État initial en cache AVANT dispatch, scopé société — le endpoint de
        # statut vérifie cette société avant tout accès (jamais inter-tenant).
        cache.set(simulation_job_cache_key(token), {
            'company_id': company.id,
            'devis_id': devis.pk,
            'status': 'pending',
        }, SIMULATION_JOB_CACHE_TTL)
        task_simulate_bankable_study.apply_async(
            args=[devis.pk, company.id, token],
            kwargs={'force_refresh': force_refresh},
            queue='interactive')

        return Response({
            'detail': 'Simulation lancée en arrière-plan.',
            'job_id': token,
            'status': 'pending',
            'zones': len(zones),
            'status_url': ('/api/django/ventes/devis/%s/simulation-status/%s/'
                           % (devis.pk, token)),
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'],
            url_path=r'simulation-status/(?P<token>[0-9a-f]{32})',
            permission_classes=[IsResponsableOrAdmin])
    def simulation_status(self, request, pk=None, token=None):
        """PV74 — état d'une simulation lancée par ``simuler``.

        ``202 {status: 'pending'}`` tant qu'elle tourne, ``200 {status:
        'ready', simulation: {...}}`` quand elle est rangée, ``500 {status:
        'error'}`` si le calcul a échoué. Un jeton inconnu — ou appartenant à
        une AUTRE société — répond ``404`` indistinct : on ne révèle pas
        l'existence d'un job qui n'est pas le sien (même discipline que
        ``export_status``, SCA41).

        La charge ``simulation`` est relue sur le DEVIS
        (``etude_params['simulation']``), jamais recopiée depuis le cache : le
        document reste l'unique source de vérité. LECTURE PURE."""
        from django.core.cache import cache

        from ..tasks import simulation_job_cache_key

        devis = self.get_object()  # borné société par get_queryset
        job = cache.get(simulation_job_cache_key(token))
        if (not job or job.get('company_id') != request.user.company_id
                or job.get('devis_id') != devis.pk):
            return Response({'detail': 'Simulation introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        etat = job.get('status')
        if etat == 'ready':
            simulation = (devis.etude_params or {}).get('simulation')
            return Response({'status': 'ready', 'simulation': simulation})
        if etat == 'error':
            return Response(
                {'status': 'error', 'detail': 'La simulation a échoué.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': 'pending'},
                        status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'],
            url_path='ajouter-boq-electrique',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_boq_electrique(self, request, pk=None):
        """PV47 — reporte le BORDEREAU électrique (PV41) en lignes de devis.

        Geste EXPLICITE et jamais silencieux : la conception électrique se
        recalcule à chaque changement de disposition, et si elle réécrivait les
        lignes toute seule, le prix d'un devis bougerait sous les yeux du
        client. Ces lignes n'apparaissent donc QUE sur cet appel.

        Deux issues par ligne de bordereau : un produit du catalogue
        correspond (ligne produit à SON prix — 0 et « à chiffrer » tant que le
        fondateur ne l'a pas renseigné), ou aucun ne correspond (ligne de NOTE
        « à chiffrer », sans prix, et la ligne remonte dans ``manques``).
        Aucun prix n'est JAMAIS inventé.

        GARDE DE STATUT (patron PV15) : seuls « brouillon » et « envoyé »
        acceptent l'ajout ; au-delà, 409 avec le statut NOMMÉ (le bon geste est
        « Réviser »). Cette garde LIT le statut, elle ne l'écrit jamais
        (règle #4). Devis d'une autre société → 404 (get_queryset).
        """
        from ..services import ajouter_lignes_boq_electrique

        devis = self.get_object()  # borné société par get_queryset
        _MODIFIABLES = (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE)
        if devis.statut not in _MODIFIABLES:
            return Response(
                {'detail': (
                    'Devis « %s » : on ne peut plus y ajouter de lignes. '
                    'Utilisez « Réviser » pour en créer une nouvelle version.'
                    % devis.get_statut_display())},
                status=status.HTTP_409_CONFLICT)
        design = getattr(devis, 'electrical_design', None)
        if not isinstance(design, dict) or not design.get('bom'):
            return Response(
                {'detail': "Ce devis n'a pas encore de conception électrique : "
                           'lancez d\'abord « Conception électrique ».'},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = ajouter_lignes_boq_electrique(devis, request.user)
        return Response(resultat)

    @action(detail=False, methods=['post'], url_path='atomic',
            permission_classes=[IsResponsableOrAdmin])
    def atomic(self, request):
        """QX21be — création TRANSACTIONNELLE d'un devis + ses lignes en UN
        SEUL commit. Remplace les 1+N allers-retours non gardés du générateur
        (qui laissaient des brouillons orphelins/partiels qu'un vendeur pouvait
        ensuite envoyer). Couper la connexion en cours de route laisse soit
        RIEN, soit un devis complet.

        Corps : les champs de devis (statut/taux_tva/remise_globale/lead/
        client/mode_installation/etude_params…) + ``lignes`` : liste de
        ``{produit, designation, quantite, prix_unitaire, remise?, taux_tva?}``.
        La société est TOUJOURS forcée côté serveur. Aucun ``prix_achat``.
        """
        from django.db import transaction
        from rest_framework.exceptions import ValidationError
        from apps.crm.services import resolve_client_for_lead

        company = request.user.company
        if company is None:
            return Response({'detail': 'Utilisateur sans société.'},
                            status=status.HTTP_400_BAD_REQUEST)

        lignes_in = request.data.get('lignes')
        if not isinstance(lignes_in, list) or not lignes_in:
            return Response({'detail': 'Au moins une ligne est requise.'},
                            status=status.HTTP_400_BAD_REQUEST)

        head = {k: v for k, v in request.data.items() if k != 'lignes'}
        head.pop('company', None)  # jamais accepté du corps
        serializer = DevisWriteSerializer(data=head)
        serializer.is_valid(raise_exception=True)

        lead = serializer.validated_data.get('lead')
        client = serializer.validated_data.get('client')
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if client is None:
            if lead is None:
                raise ValidationError(
                    {'client': 'Un client ou un lead est requis.'})
            client = resolve_client_for_lead(lead)

        try:
            with transaction.atomic():
                def _save(ref):
                    devis = serializer.save(
                        reference=ref, client=client,
                        created_by=request.user, company=company)
                    self._replace_lines_atomic(devis, lignes_in, company)
                    return devis
                create_numbered(Devis, company, 'devis', _save)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Enregistrement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)

        devis = serializer.instance
        # QX23be — fige la marge interne à la création (manager-only).
        try:
            from ..services import refresh_marge_snapshot
            refresh_marge_snapshot(devis)
        except Exception:  # noqa: BLE001
            pass
        return Response(DevisSerializer(
            devis, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='replace-lines',
            permission_classes=[IsResponsableOrAdmin])
    def replace_lines(self, request, pk=None):
        """QX21be — remplace ATOMIQUEMENT toutes les lignes d'un devis en un
        seul commit (édition). Remplace le delete-all-puis-recréer à erreurs
        avalées du générateur, qui pouvait laisser un devis avec moins/aucune
        ligne. Un échec préserve les lignes d'origine (rollback complet).

        PV15 — GARDE DE STATUT. Cet endpoint SUPPRIME puis recrée toutes les
        lignes : sans garde, un appel sur un devis ACCEPTÉ (ou refusé/expiré)
        effaçait le contenu d'un document déjà engagé, dont la chaîne
        BonCommande/Facture dépend. Seuls « brouillon » et « envoyé » restent
        modifiables ; au-delà, 409 avec le statut NOMMÉ (le bon geste est
        « Réviser », qui crée une nouvelle version). Cette garde ne CHANGE
        jamais le statut — elle le LIT (règle #4)."""
        from django.db import transaction
        devis = self.get_object()  # borné société par get_queryset
        _MODIFIABLES = (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE)
        if devis.statut not in _MODIFIABLES:
            return Response(
                {'detail': (
                    'Devis « %s » : ses lignes ne peuvent plus être '
                    'remplacées. Utilisez « Réviser » pour en créer une '
                    'nouvelle version.' % devis.get_statut_display())},
                status=status.HTTP_409_CONFLICT)
        lignes_in = request.data.get('lignes')
        if not isinstance(lignes_in, list):
            return Response({'detail': 'Champ « lignes » requis (liste).'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                self._replace_lines_atomic(devis, lignes_in, devis.company)
        except Exception as exc:  # noqa: BLE001 — rollback : lignes d'origine
            return Response({'detail': f'Remplacement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(DevisSerializer(
            devis, context={'request': request}).data)

    def _replace_lines_atomic(self, devis, lignes_in, company):
        """QX21be — supprime puis recrée les lignes du devis (appelé SOUS une
        transaction par l'appelant). Produits bornés à la société de
        l'utilisateur OU au catalogue global (PV15, même portée que
        ``services._pick_product``) ; jamais de ``prix_achat`` accepté du corps.

        XSAL5 — ``optionnelle`` (add-on hors total) est persistée.
        XSAL14 — ``type_ligne`` (produit [défaut] / section / note) + ``ordre`` :
        une ligne section/note ne porte NI produit NI prix (jamais comptée dans
        les totaux). ``ordre`` par défaut = position dans la liste envoyée."""
        from decimal import Decimal, InvalidOperation
        from django.db.models import Q
        from ..models import LigneDevis
        from apps.stock.models import Produit
        _VALID_TYPES = {c.value for c in LigneDevis.TypeLigne}
        devis.lignes.all().delete()
        for idx, li in enumerate(lignes_in):
            if not isinstance(li, dict):
                continue
            type_ligne = str(li.get('type_ligne') or 'produit')
            if type_ligne not in _VALID_TYPES:
                type_ligne = 'produit'
            try:
                ordre = int(li.get('ordre', idx))
            except (TypeError, ValueError):
                ordre = idx
            # XSAL14 — ligne de SECTION/NOTE : intertitre/texte sans prix.
            if type_ligne in ('section', 'note'):
                designation = (li.get('designation') or '').strip()
                if not designation:
                    raise ValueError(
                        'Une ligne de section/note doit porter un intitulé.')
                LigneDevis.objects.create(
                    devis=devis, produit=None,
                    designation=designation[:255],
                    quantite=None, prix_unitaire=None, remise=Decimal('0'),
                    taux_tva=None, type_ligne=type_ligne, ordre=ordre)
                continue
            # Ligne PRODUIT (chemin historique + XSAL5 optionnelle + ordre).
            try:
                produit_id = int(li.get('produit'))
            except (TypeError, ValueError):
                raise ValueError('Ligne sans produit valide.')
            # PV15 — le catalogue GLOBAL (``company IS NULL``) est quotable :
            # c'est exactement la portée que ``services._pick_product`` retient
            # pour composer un devis. Le filtre société-stricte d'origine
            # REFUSAIT ici des produits que l'auto-composition venait de poser
            # sur le même devis (« Produit N inconnu » sur un simple
            # ré-enregistrement). La portée reste bornée : société de
            # l'utilisateur OU catalogue global — jamais celui d'un autre
            # tenant.
            produit = Produit.objects.filter(
                Q(company=company) | Q(company__isnull=True),
                id=produit_id).first()
            if produit is None:
                raise ValueError(f'Produit {produit_id} inconnu.')
            try:
                qte = Decimal(str(li.get('quantite', 1)))
                pu = Decimal(str(li.get('prix_unitaire', produit.prix_vente)))
                remise = Decimal(str(li.get('remise', 0)))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError('Quantité/prix/remise invalide.')
            taux = li.get('taux_tva')
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation=(li.get('designation') or produit.nom)[:255],
                quantite=qte, prix_unitaire=pu, remise=remise,
                taux_tva=Decimal(str(taux)) if taux is not None else None,
                optionnelle=bool(li.get('optionnelle', False)),
                type_ligne='produit', ordre=ordre)

    @action(detail=False, methods=['post'], url_path='auto',
            permission_classes=[IsResponsableOrAdmin])
    def auto(self, request):
        """Copilote — crée un devis RÉSIDENTIEL automatiquement dimensionné à
        partir de la fiche lead (JAMAIS un brouillon vide). C'est le seul chemin
        de création de devis offert à l'agent.

        Corps : ``{lead}`` (ou ``{client}``, dont on remonte au lead le plus
        récent) + ``taux_tva?`` / ``remise_globale?``. La société est TOUJOURS
        celle du user ; le lead est borné à cette société (404 sinon). 422 si les
        données de dimensionnement manquent ou si le marché n'est pas résidentiel
        — l'agent demande alors la donnée / oriente vers le générateur. Aucun
        statut n'est touché : le service renvoie un brouillon (règle #4)."""
        from decimal import Decimal, InvalidOperation
        from ..services import build_devis_auto, AutoDevisError
        from ..models import ShareLink
        from apps.crm.selectors import (
            get_company_lead, get_company_client, get_latest_lead_for_client,
        )

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        lead_obj = None
        lead_id = request.data.get('lead')
        client_id = request.data.get('client')
        if lead_id:
            lead_obj = get_company_lead(company, lead_id)
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        elif client_id:
            if get_company_client(company, client_id) is None:
                return Response({'detail': 'Client inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
            lead_obj = get_latest_lead_for_client(company, client_id)
            if lead_obj is None:
                return Response(
                    {'detail': "Ce client n'a pas de fiche lead avec profil "
                     "énergétique. Complétez le lead (facture d'hiver ou taille "
                     "souhaitée) pour générer l'auto-devis."},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        else:
            return Response(
                {'detail': 'Un lead (ou un client) est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _dec(raw, default):
            if raw in (None, ''):
                return default
            try:
                return Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                return None

        taux_tva = _dec(request.data.get('taux_tva'), Decimal('20'))
        remise = _dec(request.data.get('remise_globale'), Decimal('0'))
        if taux_tva is None or remise is None:
            return Response(
                {'detail': 'taux_tva / remise_globale invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            devis = build_devis_auto(
                lead=lead_obj, user=request.user, company=company,
                taux_tva=taux_tva, remise_globale=remise)
        except AutoDevisError as exc:
            return Response(
                {'detail': exc.message, 'field': exc.field},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        link = ShareLink.for_devis(devis)
        return Response(
            {
                'id': devis.id,
                'reference': devis.reference,
                'statut': devis.statut,
                'kwc': (devis.etude_params or {}).get('puissance_kwc'),
                'nb_lignes': devis.lignes.count(),
                'proposal_token': link.token,
                'proposal_path': chemin_proposition(devis, link.token),
            },
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='share-link',
            permission_classes=[IsResponsableOrAdmin])
    def share_link(self, request, pk=None):
        """B2 — frappe (ou réutilise) un lien public de proposition pour ce
        devis. Permet au site de (re)générer le lien de proposition d'un devis
        existant lors de la livraison. Le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (autre société → 404)."""
        from ..models import ShareLink
        devis = self.get_object()
        # GAMME — le mode d'envoi (« seule » / « les_deux ») accompagne le lien
        # quand le vendeur le précise ; absent du corps → mode déjà posé.
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        link = ShareLink.for_devis(devis)
        return Response(
            {'token': link.token, 'path': chemin_proposition(devis, link.token),
             'gamme': _gamme_envoi_payload(devis)},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        """QJ14 — Envoie la proposition (PDF premium + lien tokenisé) au client
        par email, consigne l'envoi dans EmailLog et marque le devis « envoyé »
        via mark_devis_sent (règle #4 — seul chemin de transition brouillon→envoyé).

        Body (tous optionnels) :
          - ``to_email``  : adresse destinataire (défaut : client.email)
          - ``sujet``     : objet de l'email (défaut : modèle FR)
          - ``corps``     : corps de l'email (défaut : modèle FR)
          - ``pdf_mode``  : « full » | « onepage » (défaut : « full »)

        Idempotent : un devis déjà « envoyé » (ou plus avancé) ne régresse pas
        — l'email est tout de même envoyé mais mark_devis_sent ne re-stampe pas.

        Retourne l'EmailLog id + statut + le statut courant du devis.
        """
        from ..models import ShareLink
        from ..services import mark_devis_sent
        from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
        from ..utils.pdf import download_pdf

        devis = self.get_object()
        to_email = (request.data.get('to_email') or '').strip() or None
        sujet = (request.data.get('sujet') or '').strip() or None
        corps = (request.data.get('corps') or '').strip() or None
        pdf_mode = (request.data.get('pdf_mode') or 'full').strip()
        # GAMME — mode d'envoi « à la carte », réglé au moment de l'envoi.
        # UN PDF = UNE GAMME : la pièce jointe reste le PDF de CE devis, jamais
        # un PDF fusionné des deux gammes (chaque gamme a le sien).
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))

        # Génère le PDF premium (persist=False — rendu à la volée, pas de
        # remplacement du fichier stocké : le moteur rend seulement).
        attachment = None
        attachment_name = None
        try:
            opts = clean_pdf_options({'pdf_mode': pdf_mode})
            key = generate_premium_devis_pdf(devis.id, opts, persist=False)
            attachment = download_pdf(key)
            attachment_name = f'Devis_{devis.reference}.pdf'
        except Exception:  # noqa: BLE001 — PDF indisponible n'empêche pas l'envoi
            pass

        # Ajoute le lien de proposition tokenisé dans le corps si fourni.
        link = ShareLink.for_devis(devis)
        proposal_url = chemin_proposition(devis, link.token)
        # ZSAL5 — gabarit ``envoi_devis`` (EmailTemplate) : sujet/corps
        # explicitement fournis dans le corps de requête restent prioritaires
        # (comportement historique) ; sinon on rend le gabarit effectif de la
        # société (défaut = texte historique byte-identique tant que non édité).
        if not sujet or not corps:
            from apps.parametres.models_email import EmailTemplate
            client = devis.client
            nom_client = ''
            civilite = ''
            if client:
                nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
                civilite = getattr(client, 'civilite', '') or ''
            # ``{nom}`` porte le salut complet ("Bonjour X," / "Bonjour,")
            # pour préserver EXACTEMENT le rendu historique par défaut.
            salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
            # XSAL17 — {lien_rdv} : résolu paresseusement, jamais de
            # BookingLink créé si le gabarit effectif ne référence pas le
            # placeholder (évite un jeton inutile à chaque envoi de devis).
            lien_rdv = ''
            if devis.lead_id and '{lien_rdv}' in EmailTemplate.get_template(
                    devis.company, 'envoi_devis')['corps']:
                try:
                    from apps.crm.services import public_booking_url
                    lien_rdv = public_booking_url(devis.lead, request=request)
                except Exception:  # noqa: BLE001 — jamais bloquer l'envoi
                    lien_rdv = ''
            rendu = EmailTemplate.render(
                devis.company, 'envoi_devis',
                civilite=civilite, nom=salut,
                reference=devis.reference or '', lien=proposal_url,
                validite=(devis.date_validite.strftime('%d/%m/%Y')
                          if devis.date_validite else ''),
                lien_rdv=lien_rdv,
            )
            sujet = sujet or rendu['sujet']
            corps = corps or rendu['corps']

        # Envoi + EmailLog via le service centralisé. attach_pdf=False car on
        # a déjà le contenu — on passe attachment/attachment_name directement.
        from ..email_service import _send, _from_email, _chatter_note
        from ..models import EmailLog  # noqa: F811 — local import shadows class-level

        client = devis.client
        dest = (to_email or (getattr(client, 'email', '') or '')).strip()
        reference = devis.reference or ''
        if not sujet:
            sujet = f'Votre devis {reference}'

        log = EmailLog(
            company=devis.company,
            direction=EmailLog.Direction.SORTANT,
            client=client,
            devis=devis,
            to_email=dest, from_email=_from_email(),
            sujet=(sujet or '')[:300], corps=corps,
            reference=reference[:80],
            piece_jointe=(attachment_name or '')[:255],
            created_by=request.user if getattr(request.user, 'is_authenticated', False) else None,
        )

        if not dest:
            log.statut = EmailLog.Statut.ECHEC
            log.erreur = 'Aucune adresse email destinataire.'
            log.save()
            return Response(
                {'detail': log.erreur, 'log_id': log.id, 'statut': 'echec'},
                status=status.HTTP_400_BAD_REQUEST)

        ok, err = _send(dest, sujet, corps, attachment, attachment_name)
        log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
        log.erreur = err
        log.save()

        etat = 'envoyé' if ok else "échec d'envoi"
        _chatter_note(devis, f"Email du devis {reference} — {etat} (à {dest}).", request.user)

        # Marque le devis « envoyé » via le seul chemin autorisé (règle #4).
        # Idempotent : un devis déjà envoyé/accepté/refusé n'est pas régressé.
        mark_devis_sent(devis=devis, user=request.user)

        # ZSAL5 — reflet de l'envoi dans le chatter du LEAD lié (best-effort,
        # jamais un import des models crm depuis ventes).
        if ok and devis.lead_id:
            try:
                from apps.crm.services import noter_devis_envoye
                noter_devis_envoye(reference, devis.lead)
            except Exception:  # noqa: BLE001 — best-effort, ne bloque jamais l'envoi
                pass

        return Response({
            'detail': f'Email envoyé à {dest}.' if ok else f'Échec envoi email : {err}',
            'log_id': log.id,
            'email_statut': log.statut,
            'devis_statut': devis.statut,
            'proposal_path': proposal_url,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='save-preset',
            permission_classes=[IsResponsableOrAdmin])
    def save_preset(self, request, pk=None):
        """QJ16-wiring — Enregistre le devis courant comme preset (modèle de devis).

        Body (tous optionnels sauf ``nom``) :
          - ``nom``         : nom du modèle (obligatoire, max 150 caractères)
          - ``description`` : note libre (optionnel)

        La company est TOUJOURS forcée depuis ``devis.company`` — jamais du corps.
        Retourne le preset créé (id, nom, mode_installation, lignes_snapshot…).
        """
        from ..services import save_devis_as_preset
        from ..serializers import DevisPresetSerializer
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'detail': 'Le nom du modèle est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        description = (request.data.get('description') or '').strip()
        try:
            preset = save_devis_as_preset(
                devis, nom, description, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DevisPresetSerializer(preset).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='apply-preset',
            permission_classes=[IsResponsableOrAdmin])
    def apply_preset(self, request, pk=None):
        """QJ16-wiring — Applique un preset à ce devis (brouillon uniquement).

        Body :
          - ``preset_id`` : id du DevisPreset à appliquer (obligatoire)

        La company du preset DOIT correspondre à celle du devis (vérifiée
        par ``apply_preset_to_devis`` — cross-company → 400).
        RULE #4 : n'affecte jamais Devis.statut.
        Retourne le décompte de lignes créées.
        """
        from ..services import apply_preset_to_devis
        from ..models import DevisPreset
        devis = self.get_object()
        preset_id = request.data.get('preset_id')
        if not preset_id:
            return Response(
                {'detail': 'preset_id est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            preset = DevisPreset.objects.get(
                pk=preset_id, company=devis.company)
        except DevisPreset.DoesNotExist:
            return Response(
                {'detail': 'Modèle introuvable pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            created = apply_preset_to_devis(preset, devis)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'detail': f'{len(created)} ligne(s) ajoutée(s) depuis le modèle.',
            'lignes_created': len(created),
            'skipped_priceless': len(preset.lignes_snapshot) - len(created),
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='dupliquer-variante',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer_variante(self, request, pk=None):
        """QJ15 — Crée 2–3 variantes de taille du devis pour comparaison
        côte-à-côte.

        Chaque variante est un devis brouillon indépendant partageable :
          - même client / lead / mode / TVA / remise que l'original ;
          - lignes clonées avec quantités ajustées selon le facteur de
            dimensionnement (``scale``) passé dans le corps — ou déduit
            automatiquement : ×0.8 (−20 %) / ×1.0 (identique) / ×1.25 (+25 %) ;
          - ``version_parent`` positionné sur l'original (ou son propre parent)
            pour grouper les variantes sans créer une revision :
            ``is_active=True`` sur toutes → ce sont des alternatives, pas des
            remplacements ;
          - aucun changement de statut (règle #4) ;
          - numéros de référence séquentiels via ``create_numbered``.

        Corps optionnel :
          ``scales`` : liste de flottants explicites, ex. [0.8, 1.0, 1.25]
                       (override par requête, max 3 éléments) ;
          ``variante_pct`` : pourcentage p → échelles symétriques
                       [1−p, 1.0, 1+p] (override par requête).

        QG9 — Sans override, le pourcentage vient de
        ``CompanyProfile.variante_pct`` (défaut 20 → échelles 0.8 / 1.0 / 1.2),
        scopé société. Retourne la liste des devis créés.
        """
        source = self.get_object()
        company = source.company
        root = source.version_parent or source

        # QG9 — échelles depuis un pourcentage : override requête ``scales``
        # (rétro-compat) > override requête ``variante_pct`` > config société
        # ``CompanyProfile.variante_pct`` (défaut 20). Symétrique : [1−p, 1, 1+p].
        def _scales_from_pct(pct):
            try:
                p = float(pct) / 100.0
            except (TypeError, ValueError):
                return None
            if not (0 < p < 1):
                return None
            return [round(1 - p, 4), 1.0, round(1 + p, 4)]

        scales = None
        raw_scales = request.data.get('scales')
        if raw_scales:
            try:
                scales = [float(s) for s in raw_scales][:3]
            except (TypeError, ValueError):
                scales = None
        if scales is None:
            pct = request.data.get('variante_pct')
            if pct is None:
                from apps.parametres.models import CompanyProfile
                pct = getattr(CompanyProfile.get(company=company),
                              'variante_pct', 20)
            scales = _scales_from_pct(pct) or [0.8, 1.0, 1.25]
        if not scales:
            scales = [0.8, 1.0, 1.25]

        # Labels FR dérivés de l'échelle : « −X % » / « Standard » / « +X % ».
        def _label_for(scale):
            if abs(scale - 1.0) < 1e-9:
                return 'Standard'
            pct = round((scale - 1.0) * 100)
            sign = '+' if pct > 0 else '−'
            return f'{sign}{abs(pct)} %'

        created = []
        from decimal import Decimal, ROUND_HALF_UP

        for scale in scales:
            variant_note = _label_for(scale)
            holder = {}

            def _save(ref, _scale=scale, _note=variant_note):
                obj = Devis.objects.create(
                    company=company, reference=ref,
                    client=source.client, lead=source.lead,
                    statut=Devis.Statut.BROUILLON,
                    taux_tva=source.taux_tva,
                    remise_globale=source.remise_globale,
                    note=(f'[Variante {_note}] ' + (source.note or '')).strip(),
                    mode_installation=source.mode_installation,
                    etude_params=source.etude_params,
                    prix_cible_kwc=source.prix_cible_kwc,
                    created_by=request.user,
                    # Groupe : version_parent = racine, version incrémentée,
                    # is_active=True (alternative, pas remplacement).
                    version=source.version + len(created) + 1,
                    version_parent=root,
                    is_active=True,
                )
                holder['obj'] = obj
                return obj

            create_numbered(Devis, company, 'devis', _save)
            nd = holder['obj']

            for ligne in source.lignes.all():
                raw_qty = ligne.quantite * Decimal(str(scale))
                qty = raw_qty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                qty = max(qty, Decimal('0.01'))
                LigneDevis.objects.create(
                    devis=nd,
                    produit=ligne.produit,
                    designation=ligne.designation,
                    quantite=qty,
                    prix_unitaire=ligne.prix_unitaire,
                    remise=ligne.remise,
                    taux_tva=ligne.taux_tva,
                )
            created.append(nd)

        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in created],
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='dupliquer-variante-gamme',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer_variante_gamme(self, request, pk=None):
        """GAMME (fondateur 2026-08-18) — crée la SŒUR « gamme » de ce devis.

        Une gamme = une VARIANTE de devis (même mécanique QJ15 : devis frère
        complet groupé par ``version_parent``, composition et prix PROPRES).
        Le libellé est une DONNÉE libre — aucune marque codée en dur : il est
        stocké dans ``etude_params['gamme']`` (aucun changement de modèle).

        Corps :
          ``nom``            : libellé de la gamme créée (défaut « Premium ») ;
          ``nom_source``     : libellé de la gamme du devis courant
                               (défaut « Essentielle », ou celui déjà posé) ;
          ``recommandee``    : ``true`` pour que la NOUVELLE gamme porte le
                               badge « Recommandé » (défaut : la source le
                               garde — le devis porteur est la recommandée).

        Aucun statut n'est touché (règle #4). Renvoie les DEUX devis."""
        from ..services import (
            GAMME_NOMS_DEFAUT, creer_variante_gamme, gamme_info,
        )
        source = self.get_object()
        nom = (str(request.data.get('nom') or '').strip()
               or GAMME_NOMS_DEFAUT[1])
        nom_source = (str(request.data.get('nom_source') or '').strip()
                      or None)
        recommandee = request.data.get('recommandee') in (
            True, 'true', 'True', '1', 1, 'on')
        try:
            soeur = creer_variante_gamme(
                source, nom, user=request.user,
                nom_gamme_source=nom_source, recommandee=recommandee)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        source.refresh_from_db(fields=['etude_params'])
        ctx = {'request': request}
        return Response(
            {
                'source': DevisSerializer(source, context=ctx).data,
                'gamme': DevisSerializer(soeur, context=ctx).data,
                'gammes': [gamme_info(source), gamme_info(soeur)],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get', 'put'], url_path='variante-config')
    def variante_config(self, request):
        """QG9 — Lit (GET) ou règle (PUT) le pourcentage des variantes de devis.

        Le pourcentage vit sur ``CompanyProfile.variante_pct`` (défaut 20),
        scopé à la société de l'utilisateur (jamais lu du corps). La LECTURE est
        ouverte à tous les rôles ; l'ÉCRITURE est réservée au Directeur et au
        Commercial responsable (403 sinon). Corps PUT : ``variante_pct`` (0–100,
        exclusif). Le générateur applique alors les échelles [1−p, 1, 1+p]
        (override par requête toujours possible sur ``dupliquer-variante``)."""
        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=company)

        if request.method == 'GET':
            return Response({'variante_pct': str(profile.variante_pct)})

        # PUT — réservé Directeur / Commercial responsable.
        user = request.user
        role_nom = getattr(getattr(user, 'role', None), 'nom', '')
        autorise = (
            getattr(user, 'is_superuser', False)
            or getattr(user, 'is_admin_role', False)
            or role_nom in ('Directeur', 'Commercial responsable')
        )
        if not autorise:
            return Response(
                {'detail': ('Seuls le Directeur et le Commercial responsable '
                            'peuvent modifier ce pourcentage.')},
                status=status.HTTP_403_FORBIDDEN)
        from decimal import Decimal, InvalidOperation
        raw = request.data.get('variante_pct')
        try:
            pct = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {'detail': 'variante_pct invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not (Decimal('0') < pct < Decimal('100')):
            return Response(
                {'detail': 'Le pourcentage doit être strictement entre 0 et 100.'},
                status=status.HTTP_400_BAD_REQUEST)
        profile.variante_pct = pct
        profile.save(update_fields=['variante_pct'])
        return Response({'variante_pct': str(profile.variante_pct)})

    @action(detail=True, methods=['get'], url_path='variantes',
            permission_classes=[IsResponsableOrAdmin])
    def variantes(self, request, pk=None):
        """QJ15 — Liste les variantes liées à ce devis (même version_parent,
        toutes actives). Utilisé par la proposal côte-à-côte."""
        devis = self.get_object()
        root = devis.version_parent or devis
        siblings = (
            Devis.objects
            .filter(company=devis.company, version_parent=root, is_active=True)
            .select_related('client')
            .order_by('version', 'id')
        )
        # An isolated devis (no version_parent and no child variants) is not
        # part of any variant group → return an empty comparison set.
        if devis.version_parent_id is None and not siblings.exists():
            return Response([])
        # Include root itself in the comparison set.
        root_devis = Devis.objects.filter(
            pk=root.pk, company=devis.company, is_active=True).first()
        results = []
        if root_devis:
            results.append(root_devis)
        for s in siblings:
            if s.pk not in {r.pk for r in results}:
                results.append(s)
        return Response(
            [DevisSerializer(v, context={'request': request}).data
             for v in results],
        )

    @action(detail=True, methods=['post'], url_path='dupliquer',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer(self, request, pk=None):
        """NTUX13 — Duplication INDÉPENDANTE (à ne pas confondre avec
        ``dupliquer-variante``, QJ15, qui groupe ses copies via
        ``version_parent`` pour une comparaison côte-à-côte). Le duplicata
        repart TOUJOURS en ``brouillon`` avec un nouveau numéro, quel que
        soit le statut de la source (jamais une copie de statut ``accepte``/
        ``envoye``), et ne porte aucun lien vers le chantier/BonCommande/
        Facture de l'original (ces objets naissent en aval d'une acceptation
        et ne sont référencés nulle part sur ``Devis`` — rien à copier)."""
        source = self.get_object()
        from ..services import dupliquer_devis
        copie = dupliquer_devis(source, user=request.user)
        return Response(
            DevisSerializer(copie, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approuver-remise',
            permission_classes=[IsAdminRole])
    def approuver_remise(self, request, pk=None):
        """Approbation admin de la remise (T17) — débloque l'envoi du devis."""
        devis = self.get_object()
        devis.remise_approuvee = True
        devis.remise_approuvee_par = request.user
        devis.save(update_fields=['remise_approuvee', 'remise_approuvee_par'])
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='reviser',
            permission_classes=[IsResponsableOrAdmin])
    def reviser(self, request, pk=None):
        """Révise un devis en une NOUVELLE version (v2, v3…). La nouvelle version
        clone les lignes et repart en brouillon ; l'ancienne devient inactive et
        pointe vers sa remplaçante (lecture seule côté UI). Les liens lead/client
        et le schéma de numérotation sont préservés. Additif, sans perte."""
        old = self.get_object()
        company = old.company
        root = old.version_parent or old
        new_devis = {}

        def _save(ref):
            new_devis['obj'] = Devis.objects.create(
                company=company, reference=ref, client=old.client, lead=old.lead,
                statut=Devis.Statut.BROUILLON, taux_tva=old.taux_tva,
                remise_globale=old.remise_globale, note=old.note,
                mode_installation=old.mode_installation,
                etude_params=old.etude_params, prix_cible_kwc=old.prix_cible_kwc,
                created_by=request.user, version=old.version + 1,
                version_parent=root, is_active=True)
            return new_devis['obj']

        create_numbered(Devis, company, 'devis', _save)
        nd = new_devis['obj']
        for ligne in old.lignes.all():
            LigneDevis.objects.create(
                devis=nd, produit=ligne.produit, designation=ligne.designation,
                quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
                remise=ligne.remise, taux_tva=ligne.taux_tva)
        old.is_active = False
        old.superseded_by = nd
        old.save(update_fields=['is_active', 'superseded_by'])
        return Response(
            DevisSerializer(nd, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'],
            url_path='historique-configuration',
            permission_classes=[IsResponsableOrAdmin])
    def historique_configuration(self, request, pk=None):
        """NTCPQ20 — Historique FIN des configurations d'un devis brouillon.

        GET : la liste des instantanés (id, horodatage, auteur, nombre de
        lignes, contenu). ``?a=<id>&b=<id>`` renvoie EN PLUS le diff des lignes
        entre deux instantanés (ajoutées / retirées / modifiées). Lecture
        seule : ne crée ni ne modifie aucun instantané."""
        from ..services import diff_configurations_devis
        devis = self.get_object()
        snapshots = list(devis.config_snapshots.select_related('auteur').all())
        payload = {
            'snapshots': [{
                'id': s.id,
                'date': s.date_creation.isoformat(),
                'auteur': (getattr(s.auteur, 'username', None)
                           if s.auteur_id else None),
                'nb_lignes': len((s.contenu or {}).get('lignes') or []),
                'contenu': s.contenu,
            } for s in snapshots],
        }
        a_id = request.query_params.get('a')
        b_id = request.query_params.get('b')
        if a_id and b_id:
            index = {str(s.id): s for s in snapshots}
            a = index.get(str(a_id))
            b = index.get(str(b_id))
            if a is None or b is None:
                return Response({'detail': 'Instantané introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            payload['diff'] = diff_configurations_devis(a, b)
        return Response(payload)

    @action(detail=True, methods=['get', 'post'], url_path='lots',
            permission_classes=[IsResponsableOrAdmin])
    def lots(self, request, pk=None):
        """NTCPQ18 — Lots (sites/bâtiments) d'un devis multi-sites.

        GET : sous-total HT par lot + total consolidé (chaîne canonique, donc
        cohérent au centime avec le total du devis). Devis sans lot →
        ``{'lots': [], 'total_consolide': None}`` (comportement mono-site
        inchangé).
        POST : crée un lot — corps ``{nom_lot, adresse_site?, ordre?,
        lignes?: [ligne_id, ...]}`` ; les lignes citées lui sont rattachées."""
        from rest_framework.exceptions import ValidationError
        from ..models import LotDevis
        from ..selectors import lots_totaux
        devis = self.get_object()
        if request.method == 'POST':
            nom = (request.data.get('nom_lot') or '').strip()
            if not nom:
                raise ValidationError({'nom_lot': 'Nom de lot requis.'})
            if devis.lots.filter(nom_lot=nom).exists():
                raise ValidationError(
                    {'nom_lot': 'Ce lot existe déjà sur ce devis.'})
            lot = LotDevis.objects.create(
                company=devis.company, devis=devis, nom_lot=nom,
                adresse_site=(request.data.get('adresse_site') or '').strip(),
                ordre=int(request.data.get('ordre') or 0))
            ids = request.data.get('lignes') or []
            if ids:
                # Jamais une ligne d'un autre devis (donc d'une autre société).
                devis.lignes.filter(id__in=ids).update(lot=lot)
        resultat = lots_totaux(devis)
        if resultat is None:
            resultat = {'lots': [], 'hors_lot': None,
                        'total_consolide': None}
        return Response(
            resultat,
            status=(status.HTTP_201_CREATED if request.method == 'POST'
                    else status.HTTP_200_OK))

    @action(detail=True, methods=['get', 'post'], url_path='avenants',
            permission_classes=[IsResponsableOrAdmin])
    def avenants(self, request, pk=None):
        """NTCPQ14 — Avenants d'un devis ACCEPTÉ.

        GET : liste des avenants (les plus récents d'abord).
        POST : applique un avenant — corps ``{lignes_ajoutees: [...],
        lignes_retirees: [id, ...], motif}``. Les totaux sont recalculés et
        l'approbation NTCPQ7 n'est redéclenchée que si le NOUVEAU taux de
        remise global dépasse le seuil configuré."""
        from ..serializers import AvenantDevisSerializer
        devis = self.get_object()
        if request.method == 'GET':
            return Response(AvenantDevisSerializer(
                devis.avenants.all(), many=True).data)
        from apps.cpq.services import appliquer_avenant_devis
        avenant = appliquer_avenant_devis(
            devis,
            lignes_ajoutees=request.data.get('lignes_ajoutees') or [],
            lignes_retirees=request.data.get('lignes_retirees') or [],
            motif=(request.data.get('motif') or '').strip(),
            user=request.user)
        return Response(AvenantDevisSerializer(avenant).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='renouveler',
            permission_classes=[IsResponsableOrAdmin])
    def renouveler(self, request, pk=None):
        """NTCPQ13 — Renouvelle un devis ACCEPTÉ (ou expiré) : nouveau brouillon
        reprenant les lignes actuelles aux PRIX CATALOGUE COURANTS, lié à son
        devis d'origine (``devis_origine``) et numéroté
        (``numero_renouvellement``). Le devis source reste intact — distinct de
        ``reviser`` (qui corrige un devis non encore accepté)."""
        from ..services import renouveler_devis
        nouveau = renouveler_devis(self.get_object(), user=request.user)
        return Response(
            DevisSerializer(nouveau, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='accepter',
            permission_classes=[HasPermissionOrLegacy('ventes_valider')])
    def accepter(self, request, pk=None):
        """N25 — marque le devis « accepté » à une date choisie, en capturant le
        nom de la personne qui accepte ; l'acceptation est consignée dans le
        chatter du devis et avance le funnel CRM (→ SIGNED). C'est le
        déclencheur explicite de la création d'un chantier."""
        from datetime import date as _date
        from ..services import (
            accept_devis, AcceptError, verifier_credit_hold, CreditHoldError,
            verifier_sale_warnings, SaleWarningError,
        )
        devis = self.get_object()
        nom = (request.data.get('nom') or '').strip()
        date_str = (request.data.get('date') or '').strip()
        try:
            date_acc = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # XFAC28 — blocage crédit dur (étend FG41). Flag OFF (défaut) → no-op,
        # comportement FG41 intact (avertissement seul). Flag ON et client en
        # dépassement → 403, sauf override explicite responsable/admin
        # (journalisé chatter + audit).
        if devis.client_id is not None:
            override = bool(request.data.get('override_credit'))
            try:
                verifier_credit_hold(
                    devis.client, override=override, user=request.user,
                    chatter_target=devis, contexte='acceptation devis')
            except CreditHoldError as exc:
                return Response(
                    {'detail': (
                        'Client en blocage crédit : '
                        f'{exc.motif}. Un responsable/admin peut passer '
                        'outre avec `override_credit: true`.'),
                     'credit_hold': True},
                    status=status.HTTP_403_FORBIDDEN)
        # ZSAL9 — avertissement de vente BLOQUANT (produit/client). Vide (défaut)
        # → no-op. Bloquant → 403, sauf override responsable/admin journalisé.
        try:
            verifier_sale_warnings(
                devis, override=bool(request.data.get('override_avertissement')),
                user=request.user, chatter_target=devis)
        except SaleWarningError as exc:
            return Response(
                {'detail': (
                    f'Avertissement de vente bloquant : {exc.motif}. '
                    'Un responsable/admin peut passer outre avec '
                    '`override_avertissement: true`.'),
                 'sale_warning': True},
                status=status.HTTP_403_FORBIDDEN)
        # A1 — option retenue (« Sans batterie » / « Avec batterie »). La
        # résolution (deux options → choix explicite obligatoire ; mono-option
        # → déduit du scénario) et le tampon d'acceptation passent désormais
        # par le service unique accept_devis (réutilisé par la proposition web
        # tokenisée Q7), préservant 1:1 la chaîne bon-commande/facture (règle #4).
        option = (request.data.get('option') or '').strip()
        try:
            accept_devis(
                devis=devis, user=request.user, nom=nom,
                date_acceptation=date_acc, option=option,
                idempotent_reaccept=False)
        except AcceptError as exc:
            return Response(
                {'detail': exc.message},
                status=(status.HTTP_409_CONFLICT if exc.conflict
                        else status.HTTP_400_BAD_REQUEST))
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @staticmethod
    def _resolve_accepted_option(devis, data):
        """A1 — détermine l'option retenue à l'acceptation.

        Renvoie ``(option, None)`` en cas de succès ou ``('', message)`` en cas
        d'erreur. Un devis à deux options exige un choix explicite et valide ;
        un devis à option unique déduit l'option de son scénario (jamais
        d'échec : une liste libre / un pompage retombe sur « sans_batterie »).
        """
        valid = {c.value for c in Devis.OptionAcceptee}
        option = (data.get('option') or '').strip()
        if option and option not in valid:
            return '', ("Option invalide (attendu « sans_batterie » ou "
                        "« avec_batterie »).")
        try:
            from ..quote_engine.builder import build_quote_data
            qd = build_quote_data(devis, {'pdf_mode': 'onepage'})
            nb_options = qd.get('nb_options', 1)
            scenario = qd.get('scenario', '')
        except Exception:  # noqa: BLE001 — l'acceptation ne doit jamais casser
            nb_options, scenario = 1, ''
        if nb_options == 2 and not option:
            return '', ("Ce devis comporte deux options — précisez celle "
                        "choisie par le client (« sans_batterie » ou "
                        "« avec_batterie »).")
        if not option:
            option = (Devis.OptionAcceptee.AVEC_BATTERIE
                      if scenario == 'Avec batterie'
                      else Devis.OptionAcceptee.SANS_BATTERIE)
        return option, None

    @action(detail=True, methods=['post'], url_path='refuser',
            permission_classes=[HasPermissionOrLegacy('ventes_valider')])
    def refuser(self, request, pk=None):
        """FG44 — marque le devis « refusé » avec date + motif + chatter.

        Symétrique à « accepter » : consigne le refus dans l'historique du devis.
        Body optionnel :
          - ``motif``  : raison du refus (libre, max 255 caractères)
          - ``date``   : date ISO AAAA-MM-JJ (défaut = aujourd'hui)
          - ``marquer_lead_perdu`` : true → émet devis_refused → CRM marque
                                     le lead associé perdu (si lead_id présent)
        """
        from datetime import date as _date
        from .. import activity
        from core.events import devis_refused

        devis = self.get_object()
        if devis.statut not in (
            Devis.Statut.BROUILLON, Devis.Statut.ENVOYE,
        ):
            return Response(
                {'detail': (
                    'Seul un devis en cours (brouillon ou envoyé) peut être '
                    f'refusé ; statut actuel : '
                    f'« {devis.get_statut_display()} ».'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        motif = (request.data.get('motif') or '').strip()[:255]
        date_str = (request.data.get('date') or '').strip()
        try:
            date_ref = _date.fromisoformat(date_str) if date_str \
                else timezone.now().date()
        except ValueError:
            return Response({'detail': 'Date invalide (attendu AAAA-MM-JJ).'},
                            status=status.HTTP_400_BAD_REQUEST)
        marquer_lead_perdu = bool(
            request.data.get('marquer_lead_perdu', False))

        devis.statut = Devis.Statut.REFUSE
        devis.date_refus = date_ref
        devis.motif_refus = motif
        devis.save(update_fields=['statut', 'date_refus', 'motif_refus'])
        activity.log_devis_refusal(devis, request.user, motif, date_ref)

        # M6 — événement découplé : ventes émet, crm réagit
        # (marque le lead perdu si demandé et lead_id présent).
        devis_refused.send(
            sender=Devis, devis=devis, user=request.user,
            motif_refus=motif,
            marquer_lead_perdu=marquer_lead_perdu,
        )
        return Response(
            DevisSerializer(devis, context={'request': request}).data)

    @action(detail=True, methods=['get'], url_path='approbation',
            permission_classes=[IsResponsableOrAdmin])
    def approbation(self, request, pk=None):
        """NTCPQ8 — Liste les étapes d'approbation de remise du devis."""
        devis = self.get_object()
        from apps.cpq.selectors import etapes_approbation_devis
        return Response(etapes_approbation_devis(devis))

    @action(detail=True, methods=['post'], url_path='approuver-etape',
            permission_classes=[HasPermissionOrLegacy('cpq_approbation_approuver')])
    def approuver_etape(self, request, pk=None):
        """NTCPQ8 — Approuve l'étape courante d'approbation de remise."""
        devis = self.get_object()
        from apps.cpq.services import approuver_etape_devis
        commentaire = (request.data.get('commentaire') or '').strip()
        etape, toutes_approuvees = approuver_etape_devis(
            devis, user=request.user, commentaire=commentaire)
        return Response({
            'detail': 'Étape approuvée.',
            'etape_id': etape.id,
            'toutes_approuvees': toutes_approuvees,
        })

    @action(detail=True, methods=['post'], url_path='rejeter-etape',
            permission_classes=[HasPermissionOrLegacy('cpq_approbation_approuver')])
    def rejeter_etape(self, request, pk=None):
        """NTCPQ8 — Rejette l'étape courante : renvoie le devis en brouillon."""
        devis = self.get_object()
        from apps.cpq.services import rejeter_etape_devis
        motif = (request.data.get('motif') or '').strip()
        etape = rejeter_etape_devis(devis, user=request.user, motif=motif)
        return Response({'detail': 'Étape rejetée.', 'etape_id': etape.id})

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter du devis (notes + acceptation)."""
        devis = self.get_object()
        return Response(
            DevisActivitySerializer(devis.activites.all(), many=True).data)

    @extend_schema(responses=DevisActionRequiseSerializer)
    @action(detail=False, methods=['get'], url_path='action-requise',
            permission_classes=[IsResponsableOrAdmin])
    def action_requise(self, request):
        """PACT17 (QX29/QX30) — « Relances du jour » : les devis nécessitant
        une action, groupés par MOTIF.

        L'écran ``DevisActionBoardPage`` appelait cet agrégat depuis sa
        création et l'entrée de menu était publiée aux rôles responsable/admin
        — mais la moitié serveur n'avait jamais été construite : le chemin
        retombait sur la route de DÉTAIL du routeur (``devis/<pk>/`` accepte
        n'importe quel segment), donc un 404, donc un écran mort. Cette action
        est cette moitié manquante, miroir de ``/sav/tickets/file-action/``
        (ZSAV6).

        Lecture PURE via ``selectors.devis_action_requise``, bornée à
        ``request.user.company`` — jamais de devis d'une autre société. RÈGLE
        #4 : aucune écriture, aucun statut touché.

        Renvoie ``{'buckets': {clé: {'count', 'ids'}, …}, 'wa_drafts':
        {id: message}}`` — forme déclarée par ``DevisActionRequiseSerializer``
        (PACT7 : jamais ``response=dict``).
        """
        from ..selectors import devis_action_requise
        return Response(devis_action_requise(request.user.company))

    @action(detail=False, methods=['get'], url_path='prefill-site',
            permission_classes=[IsAnyRole])
    def prefill_site(self, request):
        """WIR99 — pré-remplissage du générateur pour un devis SANS LEAD.

        ``crm.SiteProfile`` (DC12) est la source unique par client du profil
        énergie / toiture / pompage : son docstring promettait ce
        pré-remplissage, qui n'existait nulle part (aucun appelant de
        ``crm.selectors.site_profile_for_client``). Ce point d'entrée le
        branche : ``GET /ventes/devis/prefill-site/?client=<id>``.

        Lecture PURE via ``apps.crm.selectors`` (jamais un import des modèles
        crm), bornée à ``request.user.company`` — un profil d'une autre société
        n'est jamais renvoyé. Renvoie ``{'client': <id>, 'profil': {...}|null}``
        (``profil`` à ``null`` quand le client n'a pas encore de SiteProfile).
        """
        from apps.crm.selectors import site_profile_for_client

        client_id = request.query_params.get('client')
        if not client_id:
            return Response(
                {'detail': 'Paramètre `client` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            client_id = int(client_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Paramètre `client` invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        profil = site_profile_for_client(client_id, request.user.company)
        return Response({'client': client_id, 'profil': profil})

    @action(detail=True, methods=['get'], url_path='suivi-partage',
            permission_classes=[IsAnyRole])
    def suivi_partage(self, request, pk=None):
        """WIR96 — suivi marketing du devis : ouverture du lien de partage
        (« vu le … ») + relances de devis abandonné consignées.

        Lecture PURE via ``apps.marketing.selectors`` (jamais un import des
        modèles marketing). Bornée à la société du devis, elle-même déjà
        scopée par ``get_object()``. Renvoie ``{'ouverture': {...}|null,
        'relances': [...]}``."""
        from apps.marketing.selectors import (
            ouverture_partage_pour_token, relances_devis_abandonne)
        from ..models import ShareLink

        devis = self.get_object()
        ouverture = None
        link = (ShareLink.objects
                .filter(devis=devis, company=devis.company)
                .order_by('-id').first())
        if link is not None:
            ouverture = ouverture_partage_pour_token(devis.company, link.token)
        return Response({
            'ouverture': ouverture,
            'relances': relances_devis_abandonne(devis.company, devis.pk),
        })

    @action(detail=True, methods=['post'], url_path='whatsapp-preview',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_preview(self, request, pk=None):
        """QX22be — PRÉVISUALISATION WhatsApp (lecture seule) : construit le lien
        wa.me + le message SANS marquer le devis « envoyé ».

        Le vendeur ouvre la modale d'envoi (aperçu) puis clique le lien wa.me
        pour VRAIMENT envoyer (l'action ``whatsapp`` marque alors « envoyé »).
        Ouvrir puis fermer la modale ne doit JAMAIS créer un devis fantôme
        « envoyé » dont l'horloge de validité a démarré. Aucune transition de
        statut, aucune écriture (hormis le ShareLink réutilisé, idempotent)."""
        from ..utils.phone import normalize_ma_phone
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )

        devis = self.get_object()
        phone = devis_recipient_phone(devis)
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        langue = request.data.get('langue')
        if langue is None:
            lead = getattr(devis, 'lead', None)
            langue = (getattr(lead, 'langue_preferee', None) or 'fr'
                      if lead is not None else 'fr')
        message, link = build_single_devis_whatsapp(request, devis, langue)
        # PAS de mark_devis_sent, PAS de chatter : simple aperçu.
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
            'devis_statut': devis.statut,  # inchangé
            'preview': True,
            # GAMME — de quoi afficher le choix « envoyer cette gamme seule /
            # envoyer les deux » dans la modale d'envoi. ``None`` quand le
            # devis n'a pas de gamme sœur (modale inchangée).
            'gamme': _gamme_envoi_payload(devis),
        })

    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """QG8 — « Envoyer » un devis = le flux WhatsApp des leads.

        Miroir de ``crm.LeadViewSet.whatsapp_devis`` au niveau du devis :
          * construit un lien wa.me PRÊT à envoyer (n'envoie rien — le commercial
            appuie lui-même sur Envoyer) ;
          * le {lien} est un lien public tokenisé (30 j) vers le PDF CLIENT du
            devis — jamais de prix d'achat ni de marge (règle #4 : le moteur ne
            fait que rendre) ;
          * marque le devis « envoyé » via ``mark_devis_sent`` (U4 — le SEUL
            chemin de transition brouillon→envoyé) et fait avancer le funnel
            (→ QUOTE_SENT) via l'événement domaine ``devis_sent`` ;
          * idempotent, ne dégrade JAMAIS un devis accepté/refusé/expiré.

        Le destinataire vient du client, sinon du lead (WhatsApp puis
        téléphone). Body optionnel : ``langue`` (défaut : langue du lead, sinon
        « fr »). La société est déjà bornée par ``get_queryset``.
        """
        from ..utils.phone import normalize_ma_phone
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )
        from ..services import mark_devis_sent

        devis = self.get_object()
        phone = devis_recipient_phone(devis)
        if not normalize_ma_phone(phone):
            return Response(
                {'detail': 'Aucun numéro de téléphone.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        langue = request.data.get('langue')
        if langue is None:
            lead = getattr(devis, 'lead', None)
            langue = (getattr(lead, 'langue_preferee', None) or 'fr'
                      if lead is not None else 'fr')
        # GAMME — le MODE D'ENVOI est réglé À L'ENVOI et vit sur le devis
        # (``etude_params['gamme']['envoi']``), des deux côtés de la paire.
        # Absent du corps → le mode déjà posé (défaut « les_deux »).
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        message, link = build_single_devis_whatsapp(request, devis, langue)

        # U4 — partager le devis le marque « envoyé » (idempotent, jamais de
        # régression accepté/refusé/expiré). Le funnel avance via devis_sent.
        mark_devis_sent(devis=devis, user=request.user)

        # Trace l'action au chatter du devis (même app — autorisé). L'audit
        # transverse passe par le bus core.events (contrat d'import M4 : ventes
        # n'importe jamais apps.audit directement), jamais par un appel direct.
        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            f'Lien WhatsApp du devis {devis.reference} préparé.')

        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
            'devis_statut': devis.statut,
        })

    @action(detail=True, methods=['post'], url_path='contacter-superieur',
            permission_classes=[IsResponsableOrAdmin])
    def contacter_superieur(self, request, pk=None):
        """QJ28 — « Contacter mon supérieur » : notifie le SUPÉRIEUR du vendeur
        sur ce devis (action MANUELLE — un bouton, jamais automatique).

        Destinataires : le ``supervisor`` du créateur du devis (repli : le
        vendeur courant), sinon les managers de repli de la société
        (« Commercial responsable » / « Directeur ») — jamais le vendeur
        lui-même. La notification passe par ``notify()`` (event
        ``devis_superior_contact_requested``) et porte un lien vers le devis.
        Aucun statut n'est touché (règle #4). La société vient TOUJOURS du
        devis (déjà borné à la société du user par ``get_queryset``).

        Body optionnel : ``message`` (max 500 caractères).
        """
        devis = self.get_object()
        handler = devis.created_by or request.user
        from apps.crm.services import user_and_superior_recipients
        recipients = [
            u for u in user_and_superior_recipients(handler, devis.company)
            if u.pk not in {handler.pk, request.user.pk}
        ]
        if not recipients:
            return Response(
                {'detail': (
                    'Aucun supérieur à notifier : définissez un superviseur '
                    'dans Paramètres → Équipe, ou un rôle « Commercial '
                    'responsable » / « Directeur ».')},
                status=status.HTTP_400_BAD_REQUEST)

        message = (str(request.data.get('message') or '')).strip()[:500]
        client_nom = str(devis.client) if devis.client_id else ''
        body_parts = [
            f'{request.user.username} demande votre avis sur le devis '
            f'{devis.reference}'
            + (f' (client : {client_nom})' if client_nom else '') + '.']
        if message:
            body_parts.append(f'Message : « {message} »')

        from apps.notifications.services import notify_many
        notify_many(
            recipients,
            'devis_superior_contact_requested',
            f'Avis demandé — devis {devis.reference}',
            body='\n'.join(body_parts),
            link=f'/ventes/devis?devis={devis.pk}',
            company=devis.company,
        )
        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            'Supérieur notifié pour avis sur ce devis.'
            + (f' Message : « {message} »' if message else ''))
        return Response({
            'detail': 'Votre supérieur a été notifié.',
            'recipients': [u.username for u in recipients],
        })

    @action(detail=True, methods=['get'],
            url_path='superior-contact-status',
            permission_classes=[IsAnyRole])
    def superior_contact_status(self, request, pk=None):
        """VX215 — boucle de retour « pris en charge » (version lecture
        seule) : après « Contacter mon supérieur » (ci-dessus), l'ÉMETTEUR
        voit si sa demande a été VUE — sans jamais lire le CONTENU des
        notifications d'autrui, seulement l'état `read`/lecteur de CETTE
        demande précise (scopée à ce devis + cet événement). Zéro nouveau
        modèle : relit directement les `Notification` déjà créées par
        `contacter_superieur` (même société, même `link`)."""
        devis = self.get_object()
        from apps.notifications.selectors import superior_contact_status
        link = f'/ventes/devis?devis={devis.pk}'
        return Response(superior_contact_status(devis.company, link))

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """Ajoute une note manuelle au chatter du devis."""
        from .. import activity
        devis = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'detail': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_devis_note(devis, request.user, body)
        return Response(DevisActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)

    def _guard_discount_approval(self, devis, ancien, nouveau, remise):
        """T17 — bloque le passage en « envoyé » si la remise dépasse le seuil
        société sans approbation. Seuil non renseigné = désactivé (défaut).
        Un admin/propriétaire approuve implicitement en envoyant."""
        from rest_framework.exceptions import ValidationError
        if nouveau != 'envoye' or ancien == 'envoye':
            return
        from apps.parametres.models import CompanyProfile
        seuil = CompanyProfile.get(devis.company).discount_approval_threshold
        if seuil is None:
            return
        if (remise or 0) <= seuil or devis.remise_approuvee:
            return
        if getattr(self.request.user, 'is_admin_role', False):
            devis.remise_approuvee = True
            devis.remise_approuvee_par = self.request.user
            devis.save(update_fields=['remise_approuvee', 'remise_approuvee_par'])
            return
        raise ValidationError({'statut': (
            f'Remise de {remise} % supérieure au seuil de {seuil} % : '
            "l'approbation d'un administrateur est requise avant l'envoi.")})

    def _guard_matrix_approval(self, devis):
        """NTCPQ7/8 — instancie les étapes d'approbation par palier de remise
        pour ce devis puis bloque l'envoi tant qu'une étape est en attente. Un
        devis sans remise qualifiante ne crée aucune étape (envoi libre)."""
        from apps.cpq.services import (
            lancer_approbation_devis, verifier_compatibilite_envoyable,
        )
        from ..services import verifier_devis_envoyable
        lancer_approbation_devis(devis)
        verifier_devis_envoyable(devis)
        # NTCPQ31 — mode compatibilité « BLOQUANT » de la société : empêche
        # l'envoi tant qu'une violation bloquante (NTCPQ1) subsiste. No-op en
        # AVERTISSEMENT (défaut, comportement historique inchangé).
        verifier_compatibilite_envoyable(devis)
        # NTCPQ11 — l'envoi est autorisé : fige les clauses/CGV dynamiques
        # (write-once, jamais recalculé après envoi).
        from ..services import figer_clauses_devis
        figer_clauses_devis(devis)

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        # YDOCF2 — un devis figé (accepté/refusé/expiré) ne doit plus être
        # librement édité : le BC/Facture/BoM chantier aval sont déjà générés
        # depuis son contenu figé. Seule exception : le désactiver (révision
        # « superseded », is_active=False) — la voie de modification reste
        # `reviser` (clone en V+1 éditable), jamais un PATCH direct.
        instance = serializer.instance
        FROZEN = {Devis.Statut.ACCEPTE, Devis.Statut.REFUSE, Devis.Statut.EXPIRE}
        if instance.statut in FROZEN:
            nouveau_is_active = serializer.validated_data.get(
                'is_active', instance.is_active)
            only_deactivation = (
                nouveau_is_active is False and instance.is_active is True
                and set(serializer.validated_data.keys()) <= {'is_active'}
            )
            if not only_deactivation:
                raise ValidationError({
                    'statut': 'Devis figé — révisez-le (reviser) pour le '
                              'modifier.'})
        # ERR8 — un PATCH/PUT ne doit pas re-pointer le devis vers le client/lead
        # d'une autre société (mass-assignment). perform_create valide déjà ces
        # FK ; on applique la même garde à la mise à jour.
        company = self.request.user.company
        if company is not None:
            lead = serializer.validated_data.get('lead')
            client = serializer.validated_data.get('client')
            if lead is not None and lead.company_id != company.id:
                raise ValidationError({'lead': 'Lead inconnu.'})
            if client is not None and client.company_id != company.id:
                raise ValidationError({'client': 'Client inconnu.'})
        # Snapshot du statut AVANT écriture, puis mouvement automatique du
        # funnel CRM (envoye → QUOTE_SENT, accepte → SIGNED). Import local
        # pour éviter les cycles, comme dans perform_create.
        ancien_statut = serializer.instance.statut
        nouveau_statut = serializer.validated_data.get('statut', ancien_statut)
        remise = serializer.validated_data.get(
            'remise_globale', serializer.instance.remise_globale)
        self._guard_discount_approval(
            serializer.instance, ancien_statut, nouveau_statut, remise)
        # NTCPQ7/8 — matrice d'approbation par paliers de remise : à la
        # tentative d'envoi, instancie les étapes requises et bloque tant
        # qu'une étape est en attente (en plus du seuil unique T17 ci-dessus).
        if nouveau_statut == Devis.Statut.ENVOYE and ancien_statut != Devis.Statut.ENVOYE:  # noqa: E501
            self._guard_matrix_approval(serializer.instance)
        super().perform_update(serializer)
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern archived_by.
        serializer.instance.updated_by = self.request.user
        serializer.instance.save(update_fields=['updated_by'])
        from apps.crm.services import avancer_stage_pour_devis
        avancer_stage_pour_devis(
            serializer.instance, ancien_statut,
            serializer.instance.statut, self.request.user,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
        # NTCPQ7/8 — bloque la génération PDF tant qu'une étape d'approbation de
        # remise reste en attente (aucune étape → comportement inchangé).
        from ..services import verifier_devis_envoyable
        verifier_devis_envoyable(devis)
        from ..quote_engine import clean_pdf_options
        from ..tasks import task_generate_devis_pdf
        # Format options (simulator parity) — whitelisted server-side.
        pdf_options = clean_pdf_options(request.data)
        task = task_generate_devis_pdf.delay(devis.id, pdf_options)
        # M4 — événement découplé : ventes émet, le satellite audit journalise
        # (AuditLog.Action.PDF). ventes n'importe plus apps.audit ; le signal
        # est synchrone (même requête), donc l'acteur/société restent identiques.
        from core.events import document_pdf_generated
        document_pdf_generated.send(
            sender=Devis, instance=devis, kind='devis')
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='proposal',
        # NTPRT10 — MÊME classe que la branche `proposal` de get_permissions
        # ci-dessus (qui prime) : la déclaration de l'@action ne doit jamais
        # annoncer une garde différente de la garde effective.
        permission_classes=[IsInternalWriterOrPortalClientOwner],
    )
    def proposal(self, request, pk=None):
        """Canonical client-facing quote PDF path (CLAUDE.md rule #4).

        Renders the premium quote PDF for this devis (synchronously, via the
        vendored quote engine), stores it in MinIO and streams it inline.
        """
        devis = self.get_object()
        try:
            from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
            from ..utils.pdf import download_pdf
            # Format via query params, e.g. ?pdf_mode=onepage&devis_final=1
            raw = {
                'pdf_mode': request.query_params.get('pdf_mode'),
                'payment_mode': request.query_params.get('payment_mode'),
                'custom_acompte': request.query_params.get('custom_acompte'),
            }
            if 'show_monthly' in request.query_params:
                raw['show_monthly'] = request.query_params['show_monthly'] not in ('0', 'false')
            if 'devis_final' in request.query_params:
                raw['devis_final'] = request.query_params['devis_final'] in ('1', 'true')
            # Page « Étude » (4e page premium) — dégrade proprement à 3 pages
            # si le devis n'a pas de données d'étude (géré par le moteur).
            if 'include_etude' in request.query_params:
                raw['include_etude'] = request.query_params['include_etude'] in ('1', 'true')
            # ERR74 — /proposal is a safe GET: render + stream, but do NOT
            # persist fichier_pdf on every call (persist=False). The single
            # engine picks the residential (redesigned) or legacy renderer.
            key = generate_premium_devis_pdf(
                devis.id, clean_pdf_options(raw), persist=False)
            pdf_bytes = download_pdf(key)
        except Exception as exc:
            return Response(
                {'detail': f'Génération de la proposition échouée : {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Proposition', devis.reference,
            client=devis.client if devis.client_id else None,
            company=devis.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='layout',
        permission_classes=[IsResponsableOrAdmin],
    )
    def layout(self, request, pk=None):
        """Q1 — lit (GET) ou enregistre (POST) le layout 3D FINALISÉ du devis.

        Le corps POST EST le layout sérialisé (AreaRecord[] + result +
        renderPlan) tel que le produit l'outil roofPro11. La société n'est
        jamais lue du corps : le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (un devis d'une autre société →
        404). Seul ``roof_layout`` est touché ; aucun statut ne bouge
        (préservation des statuts, règle #4)."""
        devis = self.get_object()
        if request.method == 'GET':
            return Response({'roof_layout': devis.roof_layout})
        # POST — le corps entier est le layout (on accepte aussi un wrapper
        # {"roof_layout": …} pour rester souple côté front).
        payload = request.data
        if isinstance(payload, dict) and set(payload.keys()) == {'roof_layout'}:
            payload = payload['roof_layout']
        devis.roof_layout = payload
        devis.save(update_fields=['roof_layout'])
        return Response({'roof_layout': devis.roof_layout})

    @action(
        detail=True,
        methods=['post'],
        url_path='roof-image',
        permission_classes=[IsResponsableOrAdmin],
    )
    def roof_image(self, request, pk=None):
        """Q4 — réceptionne le snapshot PNG 3D et le stocke dans MinIO.

        L'image part dans le bucket PDF existant sous une clé scopée société
        (``roofs/<company>/<reference>.png``) et la clé est mémorisée sur
        ``devis.roof_image``. La société est forcée côté serveur (clé dérivée
        du devis, lui-même borné à la société par ``get_queryset``) ; rien
        n'est lu du corps hors le fichier. Aucun statut ne bouge (règle #4).
        Renvoie l'URL pré-signée de relecture (lecture seule, 1 h)."""
        from ..utils.pdf import upload_roof_image, roof_image_signed_url
        from ..quote_engine.builder import _ensure_pdf_bucket

        upload = request.FILES.get('image') or request.FILES.get('file')
        if upload is None:
            return Response(
                {'detail': "Fichier image manquant (champ « image »)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = upload.read()
        # Validation magic-bytes : PNG (\x89PNG) ou JPEG (\xff\xd8\xff).
        is_png = data[:8] == b'\x89PNG\r\n\x1a\n'
        is_jpeg = data[:3] == b'\xff\xd8\xff'
        if not (is_png or is_jpeg):
            return Response(
                {'detail': 'Image invalide (PNG ou JPEG attendu).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        devis = self.get_object()
        ext = 'png' if is_png else 'jpg'
        ctype = 'image/png' if is_png else 'image/jpeg'
        company_id = getattr(devis, 'company_id', None) or '0'
        key = f'roofs/{company_id}/{devis.reference}.{ext}'
        _ensure_pdf_bucket()
        upload_roof_image(data, key, content_type=ctype)
        devis.roof_image = key
        devis.save(update_fields=['roof_image'])
        return Response(
            {'roof_image': key, 'url': roof_image_signed_url(key)},
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='telecharger-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def telecharger_pdf(self, request, pk=None):
        devis = self.get_object()
        if not devis.fichier_pdf:
            return Response(
                {'detail': (
                    'PDF non disponible. '
                    'Cliquez d\'abord sur « Générer PDF ».'
                )},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from ..utils.pdf import download_pdf
            pdf_bytes = download_pdf(devis.fichier_pdf)
        except Exception:
            return Response(
                {'detail': 'Fichier introuvable. Régénérez le PDF.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Devis', devis.reference,
            client=devis.client if devis.client_id else None,
            company=devis.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"'
        )
        return response

    @action(
        detail=True,
        methods=['post'],
        url_path='convertir-bc',
        permission_classes=[IsResponsableOrAdmin],
    )
    def convertir_en_bc(self, request, pk=None):
        devis = self.get_object()
        if devis.statut != Devis.Statut.ACCEPTE:
            return Response(
                {'detail': (
                    'Le devis doit être au statut '
                    '« Accepté » pour être converti.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if BonCommande.objects.filter(devis=devis).exists():
            return Response(
                {'detail': 'Un bon de commande existe déjà pour ce devis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = request.user.company
        bc = create_numbered(
            BonCommande, company, 'bon_commande',
            lambda ref: BonCommande.objects.create(
                reference=ref,
                devis=devis,
                client=devis.client,
                statut=BonCommande.Statut.EN_ATTENTE,
                company=company,
            ),
        )
        # YEVNT6 — événement documentaire (best-effort).
        from core.events import bon_commande_cree
        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=company)
        serializer = BonCommandeSerializer(bc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-facture',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_facture(self, request, pk=None):
        """Génère la PROCHAINE facture de tranche de l'échéancier du devis.

        1er appel → facture d'acompte (30 % ou 50 % selon le mode) ; appels
        suivants → tranche matériel puis solde. Chaque facture est numérotée
        sans collision et créée « Émise » (postée). L'échéancier vient de
        l'unique mapping PAYMENT_TERMS_BY_MODE.
        """
        devis = self.get_object()
        from ..utils.echeancier import creer_facture_tranche
        from ..services import (
            reserver_stock_devis_facture, StockInsuffisantError,
            verifier_credit_hold, CreditHoldError,
            verifier_sale_warnings, SaleWarningError,
        )
        company = request.user.company
        # XFAC28 — blocage crédit dur (étend FG41). Flag OFF (défaut) → no-op.
        if devis.client_id is not None:
            override = bool(request.data.get('override_credit'))
            try:
                verifier_credit_hold(
                    devis.client, override=override, user=request.user,
                    chatter_target=devis, contexte='génération facture')
            except CreditHoldError as exc:
                return Response(
                    {'detail': (
                        'Client en blocage crédit : '
                        f'{exc.motif}. Un responsable/admin peut passer '
                        'outre avec `override_credit: true`.'),
                     'credit_hold': True},
                    status=status.HTTP_403_FORBIDDEN)
        # ZSAL9 — avertissement de vente BLOQUANT (produit/client). Vide → no-op.
        try:
            verifier_sale_warnings(
                devis, override=bool(request.data.get('override_avertissement')),
                user=request.user, chatter_target=devis)
        except SaleWarningError as exc:
            return Response(
                {'detail': (
                    f'Avertissement de vente bloquant : {exc.motif}. '
                    'Un responsable/admin peut passer outre avec '
                    '`override_avertissement: true`.'),
                 'sale_warning': True},
                status=status.HTTP_403_FORBIDDEN)
        try:
            # U9 — la facturation directe par échéancier court-circuite le bon
            # de commande : on réserve/consomme ici le stock matériel du devis,
            # comme le ferait la livraison d'un BC, dans la MÊME transaction que
            # la facture (rollback atomique si la réservation échoue). La garde
            # anti-double-comptage du service évite de re-décompter quand un BC
            # livré existe déjà ou qu'une tranche antérieure a déjà réservé.
            with transaction.atomic():
                reserver_stock_devis_facture(
                    devis=devis, user=request.user, company=company)
                facture = creer_facture_tranche(
                    devis, request.user, company,
                    create_with_reference,
                )
        except StockInsuffisantError as exc:
            return Response(
                {'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            FactureSerializer(facture).data, status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='proforma-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def proforma_pdf(self, request, pk=None):
        """XFAC10 — facture PRO-FORMA NON comptabilisée : layout facture
        legacy filigrané « PRO-FORMA — ne constitue pas une facture »,
        numérotation propre PF- (utils/references.py), AUCUN impact sur les
        statuts/GL/numérotation des vraies factures. Trace au chatter."""
        from ..models import ProformaDocument
        from ..utils.pdf import generate_proforma_pdf

        devis = self.get_object()
        company = request.user.company

        def _create(ref):
            return ProformaDocument.objects.create(
                company=company, devis=devis, reference=ref,
                created_by=request.user,
            )

        proforma = create_with_reference(
            ProformaDocument, 'PF', company, _create, period='monthly')

        try:
            pdf_bytes = generate_proforma_pdf(devis, proforma.reference)
        except Exception as exc:
            return Response({'detail': f'PDF indisponible : {exc}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            f'Facture pro-forma {proforma.reference} générée par '
            f'{getattr(request.user, "username", "?")}.')

        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="{proforma.reference}.pdf"')
        return resp
