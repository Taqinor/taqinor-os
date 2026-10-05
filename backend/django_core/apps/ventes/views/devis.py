from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..models import Devis, BonCommande
from ..serializers import (
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    FactureSerializer,
    DevisActionRequiseSerializer,  # PACT17 — forme déclarée de l'agrégat
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
# NTPRT10 — garde du chemin canonique /proposal ouverte au client PROPRIÉTAIRE
# depuis son portail (``apps.roles`` est une app FONDATION, pas un domaine).
from apps.roles.permissions import (
    IsInternalWriterOrPortalClientOwner, is_portal_user, portal_scope_id,
)
from core.viewsets import CompanyScopedModelViewSet  # ARC5
# AUD403 — brique UNIQUE du dépôt pour qu'un ``get_permissions()`` par action
# ne jette pas en silence la garde qu'une ``@action`` déclare elle-même.
from core.permissions import declared_action_permissions
# PV84 — builder UNIQUE du chemin proposition (nom-client inclus dans l'URL) ;
# jamais de f'/proposition/{token}' en dur ailleurs dans ce fichier.
from ..utils.client_links import chemin_proposition
from core.entite_scoping import EntiteScopeMixin  # NTADM2
from core.idempotency import IdempotentCreateMixin  # YAPIC9
from ..utils.references import create_with_reference
from ..utils.company_settings import create_numbered
# SPL134 — les 3 gardes partagées vivent dans leur module (les mixins
# d'actions ``views/devis_*.py`` les lisent sans importer ce fichier).
from .devis_gardes import (
    _refus_modifiabilite, _reponse_non_modifiable,
)
from .devis_edition import DevisEditionActionsMixin  # SPL135
from .devis_cycle import DevisCycleActionsMixin  # SPL136
from .devis_etudes import DevisEtudesActionsMixin  # SPL137
from .devis_envoi import DevisEnvoiActionsMixin  # SPL138

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402


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


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class DevisViewSet(DevisEditionActionsMixin,
                   DevisCycleActionsMixin,
                   DevisEtudesActionsMixin,
                   DevisEnvoiActionsMixin,
                   IdempotentCreateMixin, EntiteScopeMixin,
                   CompanyScopedModelViewSet):
    # YAPIC9 — pilote de core.idempotency.IdempotentCreateMixin : sans
    # en-tête `Idempotency-Key`, comportement inchangé (le mixin ne fait que
    # déléguer à super().create()). AVEC l'en-tête, un rejeu à corps
    # identique renvoie le devis initial (pas de doublon) ; corps différent
    # -> 409. perform_create ci-dessous reste la SEULE logique métier de
    # création — le mixin ne touche jamais à la sémantique devis/statuts.
    # ARC5 — sweep TenantMixin : base transverse unique (CompanyScopedModelViewSet
    # = TenantMixin + ModelViewSet). get_queryset (portée de visibilité +
    # company_qs) / perform_create / perform_update / get_permissions SURCHARGENT
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
        qs = super().get_queryset()
        # WIR225 — indicateur « ce devis EST la racine d'un groupe de
        # variantes ». La liste ne savait le dire que du CÔTÉ ENFANT
        # (`version`, `version_parent_ref`, `superseded_by_ref`) : sur la
        # racine, les trois sont vides, donc son entrée « Voir les versions »
        # disparaissait au premier rechargement — la comparaison n'était plus
        # atteignable que juste après la création. Annotation `Exists` : UNE
        # sous-requête pour toute la page, jamais un N+1.
        from django.db.models import Exists, OuterRef
        qs = qs.annotate(a_variantes_annote=Exists(
            Devis.objects.filter(version_parent=OuterRef('pk'), is_active=True)))
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
            # AUD143 — même exclusion que le sélecteur portail
            # (ventes.selectors.devis_du_client_portail) : un devis BROUILLON
            # n'a jamais été montré au client (fuite de travail en cours). Le
            # chemin PDF canonique `/proposal` (règle #4) passe par
            # ``self.get_object()`` -> ``get_queryset()`` et ne contrôlait
            # jusqu'ici AUCUN statut ; un brouillon devient donc INTROUVABLE
            # (404) pour TOUTE action portail, jamais 403 (qui confirmerait
            # son existence).
            return qs.filter(client_id=scope).exclude(
                statut=Devis.Statut.BROUILLON)
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # devis qu'il a créés / son équipe. 'all' → inchangé.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        # Filtre optionnel ?lead=<id> — utilisé par le dialogue « Signé » (A2)
        # pour lister les devis d'un lead. Borné à la société par company_qs.
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        # QJR636 — ?concevable=1 : les devis dont la toiture se calepine
        # encore (choix « Conception 3D »), APRÈS les portées ci-dessus.
        if self.request.query_params.get('concevable') in ('1', 'true'):
            from ..selectors import devis_concevables
            qs = devis_concevables(qs)
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DevisWriteSerializer
        return DevisSerializer

    def get_permissions(self):
        # AUD403 — la garde DÉCLARÉE par l'@action PRIME (``core.permissions.
        # declared_action_permissions`` : les kwargs du décorateur font
        # autorité). QJR649 — toutes les @action de ce viewset déclarent leur
        # ``permission_classes`` sauf ``variante_config`` : l'ancienne chaîne
        # elif d'une soixantaine de noms était inatteignable pour chacune et a
        # été réduite à la vraie table ci-dessous (matrice action × rôle
        # figée par ``tests/test_devis_matrice_permissions.py``).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        if self.action in ('list', 'retrieve', 'variante_config'):
            # variante_config : la LECTURE est ouverte à tous ; l'ÉCRITURE
            # (PUT) est re-vérifiée DANS l'action.
            return [IsAnyRole()]
        if self.action in ('create', 'update', 'partial_update'):
            return [IsResponsableOrAdmin()]
        # destroy, et toute future action non déclarée : fermé par défaut.
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        """QJR639 (D-QJR5-2) — un devis ACCEPTÉ ne se supprime pas : le DELETE
        effaçait en cascade sa signature électronique (DevisSignature), son
        lien client (ShareLink), ses lignes et son chatter, et orphelinait son
        BC. 409 sans rien effacer ; l'archivage (PATCH ``is_active=False``) ou
        la révision restent ouverts. Le statut est LU, jamais écrit (règle #4).

        QJR661 (décision fondateur 01/10 — archivage seul) : SEUL un brouillon
        se supprime. Un envoyé / refusé / expiré a un lien client (ShareLink)
        et un historique qui partiraient en cascade : même 409 « archivez-le »."""
        devis = self.get_object()
        if devis.statut == Devis.Statut.ACCEPTE:
            return Response(
                {'detail': 'Devis accepté : il ne se supprime pas — '
                           'archivez-le (désactivation) ou révisez-le.'},
                status=status.HTTP_409_CONFLICT)
        if devis.statut != Devis.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un brouillon se supprime : '
                           'archivez-le (désactivation) ou révisez-le.'},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

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
            # QJR563 — UN helper, partagé avec /devis/atomic/.
            from ..domain.creation import devise_par_defaut
            save_kwargs['devise'] = devise_par_defaut(company)

        # QJR541 — ``statut`` n'est plus écrivable : un devis créé par POST
        # est toujours un brouillon, le funnel n'avance que par les
        # événements devis_sent / devis_accepted (crm/receivers.py).
        create_numbered(
            Devis, company, 'devis',
            lambda ref: serializer.save(reference=ref, **save_kwargs),
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
        # CAL185 — DEUXIÈME ENTRÉE, MÊME CHEMIN. Le commercial compare ses
        # options DANS le calepinage, en retient une… et rien ne partait de
        # cette variante retenue. `{"calepinage": <id>}` (sans `layout`) fait
        # lire sa conception par `apps.calepinage.selectors` — jamais ses
        # modèles — et la fait chiffrer par CE service, qui délègue lui-même à
        # `build_devis_from_layout` : aucun second chemin de création de
        # lignes. Un corps qui porte un `layout` explicite est inchangé.
        calepinage_id = request.data.get('calepinage')
        nomenclature = None
        if (not isinstance(layout, dict) or not layout) and calepinage_id:
            from apps.calepinage.selectors import nomenclature_variante_retenue
            nomenclature = nomenclature_variante_retenue(
                calepinage_id, company)
            if nomenclature is None:
                return Response(
                    {'detail': "Aucune variante retenue à chiffrer sur ce "
                               "calepinage : comparez vos options, retenez-en "
                               "une, puis relancez.",
                     'champ': 'calepinage'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            layout = nomenclature['layout']
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

        # STKCAT8 — le chemin 3D était MUET sur la structure : il ne
        # transmettait NI l'id du produit choisi NI le type, donc tout devis né
        # du calepinage était composé en ACIER par défaut, quoi qu'ait choisi le
        # commercial. Valeur non numérique ⇒ ignorée (repli sur le type), jamais
        # un 500 ; l'id est résolu dans le catalogue DÉJÀ scopé société, côté
        # composition (un id d'une autre société n'y désigne rien).
        _brut_structure_id = request.data.get('structure_produit_id')
        try:
            structure_produit_id = (
                int(_brut_structure_id)
                if _brut_structure_id not in (None, '') else None)
        except (TypeError, ValueError):
            structure_produit_id = None
        # STKCAT9 bis — absent = None : la création 3D retombe alors sur la
        # structure du LEAD (produit épinglé, puis préférence), comme /auto/.
        structure_type = request.data.get('structure_type') or None

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

        # L-TRI (fondateur 24/08/2026 : « cette erreur ne doit pas se
        # répéter ») — le chemin 3D ne transmettait PAS la phase du lead :
        # un client triphasé pouvait encore recevoir un onduleur mono par
        # ICI alors que l'auto-devis (services.py, PVCOMPAT) la passait déjà.
        from apps.ventes.compatibilites import normaliser_phase
        _composition = dict(
            taux_tva=taux_tva, remise_globale=remise,
            structure_produit_id=structure_produit_id,
            structure_type=(str(structure_type) if structure_type else None),
            phase=normaliser_phase(getattr(lead_obj, 'raccordement', None)))
        # CAL185 — le rapport « à renseigner » n'existe que sur l'entrée
        # calepinage ; l'entrée historique est byte-identique.
        rapport = None
        if nomenclature is not None:
            from ..services import build_devis_depuis_calepinage_retenu
            devis, rapport = build_devis_depuis_calepinage_retenu(
                calepinage_id=calepinage_id, user=request.user,
                company=company, lead=lead_obj, client=client_obj,
                **_composition)
        else:
            devis = build_devis_from_layout(
                layout=layout, user=request.user, company=company,
                lead=lead_obj, client=client_obj, **_composition)

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
        corps = {
            'id': devis.id,
            'reference': devis.reference,
            'statut': devis.statut,
            'proposal_token': link.token,
            'proposal_path': chemin_proposition(devis, link.token),
        }
        # CAL185 — clés AJOUTÉES seulement sur l'entrée calepinage : la
        # réponse de l'entrée historique ne bouge pas d'un octet.
        if rapport is not None:
            corps['calepinage'] = rapport['calepinage']
            corps['variante'] = rapport['variante']
            corps['a_renseigner'] = rapport['a_renseigner']
        return Response(corps, status=status.HTTP_201_CREATED)

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
        STATUT n'est jamais écrit (règle #4) : un devis « envoyé » est CORRIGÉ
        SUR PLACE (200, QJR557 — chatter « corrigé après envoi : calepinage »,
        marqueur ``resync_apres_envoi``, statut inchangé) ; un devis accepté
        répond 409 avec ``revision_possible: true`` (le bon geste est
        « Réviser ») ; refusé/expiré, 409 avec ``revision_possible: false``.
        Renvoyer le MÊME layout ne fait aucune écriture
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
            # CJ2b / L-1V — les lignes viennent d'être resynchronisées
            # (quantités de panneaux, batterie, onduleur) : les QUATRE études
            # doivent repartir de cette composition COURANTE — pas seulement le
            # bloc horaire, sans quoi le schéma unifilaire de la page client
            # décrirait la composition d'avant (best-effort, jamais bloquant —
            # voir ``services.rafraichir_etudes_du_devis``).
            # QJR20 — « composition COURANTE » est désormais GARANTI et non
            # espéré : ``sync_devis_from_layout`` recale l'instance qu'on lui a
            # passée sur la ligne qu'il a verrouillée et écrite
            # (``_resynchroniser_instance_appelante``). Sans ce recalage,
            # ``devis`` gardait les lignes PRÉCHARGÉES en début de requête
            # (``prefetch_related('lignes')`` du queryset) et les quatre études
            # se recalculaient — puis se PERSISTAIENT — sur la composition
            # d'AVANT la resynchro.
            from ..services import rafraichir_etudes_du_devis
            rafraichir_etudes_du_devis(devis)
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
        ``longueur_chaine_forcee``, ``plafond_kwc_par_onduleur``,
        ``inclure_prise_terre`` — toute autre clé est ignorée). Les DEUX
        rendent EXACTEMENT la même forme, celle du
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
        # QJR516 — le prédicat UNIQUE (domain/modifiabilite, geste BOQ) ;
        # texte et code 409 {'detail'} CONSERVÉS.
        if _refus_modifiabilite(devis, 'BOQ'):
            return _reponse_non_modifiable(
                devis, 'BOQ',
                'Devis « %s » : on ne peut plus y ajouter de lignes. '
                'Utilisez « Réviser » pour en créer une nouvelle version.')
        design = getattr(devis, 'electrical_design', None)
        if not isinstance(design, dict) or not design.get('bom'):
            return Response(
                {'detail': "Ce devis n'a pas encore de conception électrique : "
                           'lancez d\'abord « Conception électrique ».'},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = ajouter_lignes_boq_electrique(devis, request.user)
        return Response(resultat)

    @action(detail=False, methods=['post'], url_path='composition',
            permission_classes=[IsResponsableOrAdmin])
    def composition(self, request):
        """U3 (fondateur 20/08/2026) — DRY-RUN de la composition résidentielle.

        Compose le kit et rend les lignes SANS RIEN CRÉER : aucun devis, aucune
        ligne, aucun statut (règle #4). C'est la moitié « à blanc » de la
        source de vérité unique — même catalogue, même fonction pure, mêmes
        règles de gamme que ``POST /ventes/devis/auto/`` qui, lui, compose ET
        crée. L'écran générateur s'en sert pour préremplir ses lignes éditables
        au lieu de recomposer le kit en JavaScript de son côté ; c'est ce qui
        fait qu'il n'existe plus « deux sortes de devis ».

        Corps : ``{kwc | nb_panneaux}`` + ``panel_watt?`` / ``scenario?`` /
        ``structure_produit_id?`` / ``structure_type?`` / ``taux_tva?`` /
        ``mppt_paires?`` / ``dimensionnement_avec?``. STKCAT1 —
        ``structure_produit_id`` (id ``stock.Produit``) est PRIORITAIRE sur
        ``structure_type``, devenu un ALIAS DÉPRÉCIÉ ; le produit est résolu
        dans le catalogue DÉJÀ scopé société, donc l'id d'une autre société ne
        désigne rien. La société est TOUJOURS celle du user (le
        catalogue d'une autre société ne fuite jamais) ; les marques épinglées
        et l'ordre des lignes sont lus SERVEUR-SIDE dans les réglages Gammes,
        jamais acceptés du corps.
        Forme de la réponse : ``contract_samples/devis_composition.json``.

        U3COMPOSE (26/08/2026) — ``dimensionnement_avec`` (optionnel) est
        l'objet ``{nb_panneaux?, kwc?, batterie_kwh?}`` de l'optimum AXE
        BATTERIE (moteur calibré, ``dimensionnement.choisir_recommandation_avec``
        côté écran) : sans lui le dry-run composait TOUJOURS les DEUX options
        sur le MÊME champ (celui optimisé SANS batterie) — ``composer_devis_
        residentiel`` accepte ce paramètre depuis L-2OPT, la vue ne le lisait
        simplement pas encore — alors que le devis créé
        (``POST /ventes/devis/auto/``) fusionne bien deux champs distincts
        quand ils divergent. Wiré ici pour que l'aperçu écran et la création
        composent EXACTEMENT le même kit — la source de vérité unique promise
        par cet endpoint (U3) vaut aussi pour les deux optimiseurs (L-2OPT).
        """
        from decimal import Decimal, InvalidOperation
        from ..services import composer_devis_residentiel, AutoDevisError

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        def _nombre(cle, defaut=None):
            brut = request.data.get(cle)
            if brut in (None, ''):
                return defaut
            try:
                return Decimal(str(brut))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError(cle)

        def _dimensionnement_avec(brut):
            """``None`` | ``{'nb_panneaux'?, 'kwc'?, 'batterie_kwh'?}`` en
            ``float`` — miroir de ce que ``composer_devis_residentiel``
            attend. Un corps qui n'est pas un objet, ou vide, vaut « moteur
            muet sur l'axe batterie » (repli historique, jamais une erreur)."""
            if not isinstance(brut, dict):
                return None
            valeurs = {}
            for cle in ('nb_panneaux', 'kwc', 'batterie_kwh'):
                item = brut.get(cle)
                if item in (None, ''):
                    continue
                try:
                    valeurs[cle] = float(item)
                except (TypeError, ValueError):
                    raise ValueError('dimensionnement_avec.%s' % cle)
            return valeurs or None

        try:
            kwc = _nombre('kwc')
            nb_panneaux = _nombre('nb_panneaux', Decimal('0'))
            from ..domain.taille import _AUTO_PANEL_WATT
            panel_watt = _nombre('panel_watt', Decimal(_AUTO_PANEL_WATT))
            taux_tva = _nombre('taux_tva', Decimal('20'))
            mppt_paires = _nombre('mppt_paires', Decimal('1'))
            dimensionnement_avec = _dimensionnement_avec(
                request.data.get('dimensionnement_avec'))
        except ValueError as exc:
            return Response(
                {'detail': 'Valeur numérique invalide : %s.' % exc},
                status=status.HTTP_400_BAD_REQUEST)

        if (kwc is None or kwc <= 0) and nb_panneaux <= 0:
            return Response(
                {'detail': 'Renseignez une puissance (kwc) ou un nombre de '
                           'panneaux (nb_panneaux).'},
                status=status.HTTP_400_BAD_REQUEST)

        structure = request.data.get('structure_type') or 'acier'
        # STKCAT1/STKCAT7 — l'id du produit de structure CHOISI. Une valeur non
        # numérique est IGNORÉE (repli sur le toggle), jamais un 500 ; le
        # scoping société est celui du CATALOGUE, posé côté composition (un id
        # d'une autre société n'y résout simplement rien).
        _brut_structure_id = request.data.get('structure_produit_id')
        try:
            structure_produit_id = (
                int(_brut_structure_id)
                if _brut_structure_id not in (None, '') else None)
        except (TypeError, ValueError):
            structure_produit_id = None
        # QJR-OFFGRID — drapeau ADDITIF et optionnel : le site est ISOLÉ
        # (onduleur autonome + batterie, option unique). Absent ⇒ dry-run
        # strictement inchangé. Cet endpoint n'a AUCUN lead en portée (il est
        # piloté par les nombres tapés à l'écran) : le repli « raccordement du
        # lead = aucun » vit là où le lead existe, dans ``build_devis_auto``.
        _brut_hors_reseau = request.data.get('hors_reseau')
        hors_reseau = (str(_brut_hors_reseau).strip().lower()
                       in ('1', 'true', 'oui', 'yes')
                       if _brut_hors_reseau is not None else False)
        # QJR604 — la ville du barème transport vient d'un LEAD de la société
        # (404 sinon), résolue côté serveur ; plus jamais d'un texte libre.
        ville = ''
        if request.data.get('lead') not in (None, ''):
            from apps.crm.selectors import get_company_lead
            from ..domain.transport import ville_du_lead
            try:
                lead_obj = get_company_lead(
                    company, int(request.data.get('lead')))
            except (TypeError, ValueError):
                lead_obj = None
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
            ville = ville_du_lead(lead_obj)
        try:
            resultat = composer_devis_residentiel(
                company=company,
                kwc=float(kwc) if kwc is not None else 0,
                nb_panneaux=int(nb_panneaux),
                panel_watt=float(panel_watt),
                scenario=request.data.get('scenario'),
                structure_type=str(structure),
                structure_produit_id=structure_produit_id,
                taux_tva=taux_tva,
                mppt_paires=int(mppt_paires),
                dimensionnement_avec=dimensionnement_avec,
                hors_reseau=hors_reseau,
                ville=ville,
            )
        except AutoDevisError as exc:
            return Response(
                {'detail': exc.message, 'field': exc.field},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(resultat, status=status.HTTP_200_OK)

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

        # U3 — trois réglages POUR CE DEVIS-LÀ, qui ne réécrivent JAMAIS la
        # fiche du lead : la puissance cible saisie par le commercial (EZ5), le
        # scénario batterie demandé, et les clés d'étude que l'écran a déjà
        # calculées (factures mensuelles réelles du contrat PACT10). La
        # COMPOSITION, elle, est entièrement serveur : l'appelant n'envoie
        # aucune ligne, aucun prix, aucune marque.
        etude_extra = request.data.get('etude_params')
        if etude_extra is not None and not isinstance(etude_extra, dict):
            return Response(
                {'detail': 'etude_params doit être un objet.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            devis = build_devis_auto(
                lead=lead_obj, user=request.user, company=company,
                taux_tva=taux_tva, remise_globale=remise,
                target_kwc=request.data.get('target_kwc'),
                scenario=request.data.get('scenario'),
                etude_extra=etude_extra)
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

    @extend_schema(responses=DevisActionRequiseSerializer)
    @action(detail=False, methods=['get'], url_path='action-requise',
            permission_classes=[IsAnyRole])
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

        CAD115 (SIG9) — le tableau est désormais ouvert au rôle qui relance
        réellement (nav ``['normal','responsable','admin']``), et chaque
        ligne publie ``prochaine_touche_crm`` pour arbitrer avec la file
        calendaire du CRM.

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

    @action(
        detail=True,
        methods=['post'],
        url_path='generer-pdf',
        permission_classes=[IsResponsableOrAdmin],
    )
    def generer_pdf(self, request, pk=None):
        devis = self.get_object()
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
        # WIR217 — une nouvelle demande efface l'échec consigné : sinon un
        # « Réessayer » repartirait déjà marqué en échec.
        from ..tasks import oublier_echec_pdf_devis
        oublier_echec_pdf_devis(devis.id)
        return Response(
            {'task_id': task.id, 'detail': 'Génération PDF lancée.'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=True,
        methods=['get'],
        url_path='etat-pdf',
        # Même garde que la LECTURE d'un devis (cf. get_permissions) : c'est un
        # état de rendu, pas une donnée métier de plus.
        permission_classes=[IsAnyRole],
    )
    def etat_pdf(self, request, pk=None):
        """WIR217 — état de la génération du PDF : prêt / en cours / ÉCHEC.

        Le sondage du frontend ne lisait que ``fichier_pdf`` : un échec
        DÉFINITIF de ``task_generate_devis_pdf`` (retries épuisés) était donc
        invisible et le sondage tournait sans fin. Cet endpoint expose l'état
        consigné par la tâche (patron EXPORT_JOB, cache scopé société).

        ``erreur``/``date`` ne sont renseignés QUE sur l'état ``echec`` ; un
        rendu déjà prêt l'emporte toujours sur un échec plus ancien.
        """
        from django.core.cache import cache
        from ..tasks import pdf_job_cache_key

        devis = self.get_object()  # scoping société (404 hors société)
        job = cache.get(pdf_job_cache_key(devis.pk)) or {}
        # Défense en profondeur : jamais l'état d'une AUTRE société, même si
        # une clé de cache venait à collisionner.
        if job.get('company_id') not in (None, devis.company_id):
            job = {}
        pret = bool(devis.fichier_pdf)
        if pret:
            statut = 'pret'
        elif job.get('status') == 'error':
            statut = 'echec'
        else:
            statut = 'en_cours'
        return Response({
            'devis': devis.pk,
            'statut': statut,
            'fichier_pdf': pret,
            'erreur': job.get('error') if statut == 'echec' else None,
            'date': job.get('at') if statut == 'echec' else None,
        })

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
            }
            if 'show_monthly' in request.query_params:
                raw['show_monthly'] = request.query_params['show_monthly'] not in ('0', 'false')
            if 'devis_final' in request.query_params:
                raw['devis_final'] = request.query_params['devis_final'] in ('1', 'true')
            # Page « Étude » (4e page premium) — dégrade proprement à 3 pages
            # si le devis n'a pas de données d'étude (géré par le moteur).
            if 'include_etude' in request.query_params:
                raw['include_etude'] = request.query_params['include_etude'] in ('1', 'true')
            # CAL183 — page « Calepinage » (planche cotée). Le défaut est AUTO
            # (présente dès que le devis porte un calepinage dessinable) : le
            # paramètre n'existe donc QUE pour trancher explicitement, et son
            # absence laisse l'AUTO décider. `?include_calepinage=0` est
            # l'opt-out ; toute autre valeur vaut « oui » — même lecture que
            # `include_etude` juste au-dessus, jamais une seconde convention.
            if 'include_calepinage' in request.query_params:
                raw['include_calepinage'] = (
                    request.query_params['include_calepinage'] in ('1', 'true'))
            # NTI18N4 — langue de sortie du document, INDÉPENDANTE de la
            # langue d'interface de qui génère le PDF. `?langue=` écrase la
            # résolution auto (priorité : explicite > Client.langue_document
            # > repli société [NTI18N34, pas encore construit] > FR). Le
            # moteur reçoit toujours une valeur DÉJÀ résolue — jamais un
            # second moteur, jamais de logique de langue dupliquée ici.
            from apps.parametres.i18n_resolver import resolve_langue_sortie
            raw['langue_sortie'] = resolve_langue_sortie(
                langue_explicite=request.query_params.get('langue'),
                client=devis.client, company=devis.company)
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
        404). Seuls ``roof_layout`` et ``layout_hash`` sont touchés ; aucun
        statut ne bouge (préservation des statuts, règle #4).

        CAL39 — CE CHEMIN ÉTAIT MUET. Il n'émettait AUCUN événement et ne
        posait même pas ``layout_hash``, alors que ``from-layout`` et
        ``sync-layout`` font les deux. Conséquences : la dédup au clic suivant
        ne pouvait pas le reconnaître, et tout abonné au bus (le miroir de
        calepinage, la note au chatter du lead) ignorait cet enregistrement —
        un calepinage créé depuis la fiche lead restait gelé pendant que le
        devis, lui, était redessiné ici. Il émet désormais le MÊME événement
        que les deux autres, et pose la MÊME empreinte. AUCUNE ligne d'écran
        ne change : le geste, la route et la réponse sont identiques."""
        from ..services import layout_hash, poser_layout_hash

        devis = self.get_object()
        if request.method == 'GET':
            return Response({'roof_layout': devis.roof_layout})
        # QJR516 — POST gardé (geste ETUDE : le layout brut, pas la
        # resynchronisation des lignes, qui reste CALEPINAGE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # POST — le corps entier est le layout (on accepte aussi un wrapper
        # {"roof_layout": …} pour rester souple côté front).
        payload = request.data
        if isinstance(payload, dict) and set(payload.keys()) == {'roof_layout'}:
            payload = payload['roof_layout']
        devis.roof_layout = payload
        devis.save(update_fields=['roof_layout'])
        # La MÊME empreinte que les deux autres chemins (écriture ciblée, aucun
        # statut touché) — puis la MÊME annonce.
        poser_layout_hash(devis, layout_hash(payload))
        _emettre_layout_finalise(devis, request.user)
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

        # QJR516 — garde (geste ETUDE) AVANT l'upload MinIO : un devis
        # accepté ne reçoit plus de rendu, et aucun objet n'est écrit.
        devis_garde = self.get_object()
        if _refus_modifiabilite(devis_garde, 'ETUDE'):
            return _reponse_non_modifiable(devis_garde, 'ETUDE')
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
            # PVFRESH — ce bouton livrait les octets du DERNIER rendu, quelle
            # que soit l'ancienneté de ce rendu : « Générer PDF », puis on
            # corrige une quantité, puis « Télécharger » → le commercial
            # repartait avec le PDF d'AVANT la correction et l'envoyait au
            # client, pendant que la page /proposition (qui, elle, re-rend à
            # chaque appel) montrait les chiffres à jour. C'est exactement la
            # divergence page/PDF signalée le 18/08/2026. On compare donc
            # l'empreinte des données à celle du fichier stocké : identiques →
            # aucun re-rendu (le cache garde tout son intérêt), différentes →
            # re-rendu dans LE MÊME format avant de servir.
            #
            # DÉGRADATION : si le rafraîchissement lui-même échoue (moteur ou
            # stockage momentanément indisponible), on retombe sur le fichier
            # stocké plutôt que de refuser le téléchargement — ce bouton
            # fonctionnait avant PVFRESH, il doit continuer de fonctionner.
            from ..quote_engine import cle_pdf_a_jour
            try:
                cle = cle_pdf_a_jour(devis)
            except Exception:  # noqa: BLE001
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    'PVFRESH: rafraîchissement impossible pour %s — le fichier '
                    'stocké est servi tel quel', devis.reference,
                    exc_info=True)
                cle = devis.fichier_pdf
            pdf_bytes = download_pdf(cle)
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
        statuts/GL/numérotation des vraies factures. Trace au chatter.

        QJR19 (décision fondateur D1 du 29/08/2026 — l'endpoint est CONSERVÉ) :
        LE RENDU D'ABORD, LE DOCUMENT ENSUITE. Le ``ProformaDocument`` et sa
        référence ``PF-`` étaient créés AVANT le rendu : un gabarit qui plantait
        (ligne de section/note, XSAL14) consommait quand même le numéro, et la
        séquence de la société avançait pour un document qui n'a jamais existé.
        Le rendu se fait donc À L'INTÉRIEUR de la fabrique passée à
        ``create_with_reference`` — ce qui garantit AUSSI que le numéro IMPRIMÉ
        sur le PDF est exactement celui qui est enregistré, même en cas de
        course sur la référence.
        """
        from ..models import ProformaDocument
        from ..utils.pdf import generate_proforma_pdf

        devis = self.get_object()
        company = request.user.company
        rendu = {}

        def _rendre_puis_creer(ref):
            rendu['pdf'] = generate_proforma_pdf(devis, ref)
            return ProformaDocument.objects.create(
                company=company, devis=devis, reference=ref,
                created_by=request.user,
            )

        try:
            proforma = create_with_reference(
                ProformaDocument, 'PF', company, _rendre_puis_creer,
                period='monthly')
        except Exception as exc:
            return Response({'detail': f'PDF indisponible : {exc}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        pdf_bytes = rendu['pdf']

        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            f'Facture pro-forma {proforma.reference} générée par '
            f'{getattr(request.user, "username", "?")}.')

        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="{proforma.reference}.pdf"')
        return resp
