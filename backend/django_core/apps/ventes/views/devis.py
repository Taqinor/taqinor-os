from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis
from ..serializers import (
    DevisSerializer,
    DevisWriteSerializer,
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
# NTPRT10 — garde du chemin canonique /proposal ouverte au client PROPRIÉTAIRE
# depuis son portail (``apps.roles`` est une app FONDATION, pas un domaine).
from apps.roles.permissions import (
    is_portal_user, portal_scope_id,
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
from ..utils.company_settings import create_numbered
from .devis_gardes import _pourcentage_saisi  # ACAL278
from .devis_edition import DevisEditionActionsMixin  # SPL135
from .devis_cycle import DevisCycleActionsMixin  # SPL136
from .devis_etudes import DevisEtudesActionsMixin  # SPL137
from .devis_envoi import DevisEnvoiActionsMixin  # SPL138
from .devis_pdf import DevisPdfActionsMixin  # SPL139
from .devis_calepinage import DevisCalepinageActionsMixin  # SPL140
from .devis_facturation import DevisFacturationActionsMixin  # SPL141
from .devis_cadence import DevisCadenceActionsMixin  # SPL142

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import visible_user_ids  # noqa: E402


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class DevisViewSet(DevisEditionActionsMixin,
                   DevisCycleActionsMixin,
                   DevisEtudesActionsMixin,
                   DevisEnvoiActionsMixin,
                   DevisPdfActionsMixin,
                   DevisCalepinageActionsMixin,
                   DevisFacturationActionsMixin,
                   DevisCadenceActionsMixin,
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
        # Règle fondateur (08/10/2026) : le RESPONSABLE d'un lead voit TOUJOURS
        # tous les devis de SON lead, quel qu'en soit l'auteur (sinon le
        # dialogue « Signé » ne propose pas le devis d'un collègue). Seuls ses
        # propres leads sont ouverts ; la société reste bornée en amont.
        visibles = visible_user_ids(user)
        if visibles is not None:
            from django.db.models import Q
            from apps.crm.selectors import lead_ids_du_responsable
            qs = qs.filter(
                Q(created_by__in=visibles)
                | Q(lead_id__in=lead_ids_du_responsable(user)))
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
        from decimal import Decimal
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

        # ACAL278 — UNE règle de module (fini, 0..100, 2 décimales) au lieu
        # d'un ``_dec`` imbriqué sans borne : 400 NOMMÉ, jamais l'IntegrityError
        # de ck_devis_remise_globale_0_100 (500).
        taux_tva, erreur = _pourcentage_saisi(
            request.data, 'taux_tva', Decimal('20'))
        remise, erreur_remise = _pourcentage_saisi(
            request.data, 'remise_globale', Decimal('0'))
        erreur = erreur or erreur_remise
        if erreur:
            return Response(
                dict(erreur, detail=next(iter(erreur.values()))),
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
        # AGR124 — le devis automatique AGRICOLE dépose ici ses alertes
        # (étude pompage + articles « prix à renseigner » omis), rendues à
        # l'écran (``alertes``) ; les autres marchés n'y écrivent rien.
        journal = {}
        try:
            devis = build_devis_auto(
                lead=lead_obj, user=request.user, company=company,
                taux_tva=taux_tva, remise_globale=remise,
                target_kwc=request.data.get('target_kwc'),
                scenario=request.data.get('scenario'),
                etude_extra=etude_extra, journal_auto=journal)
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
                'alertes': list(journal.get('alertes') or []),
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

    @action(detail=True, methods=['post'], url_path='revoquer-lien-public',
            permission_classes=[IsResponsableOrAdmin])
    def revoquer_lien_public(self, request, pk=None):
        """ADOC131 (D-ADOC-4) — « Révoquer le lien client » : coupe
        immédiatement le lien public du devis (proposition ET suivi, même
        jeton) en posant ``ShareLink.revoque_le``. Devis d'une autre société →
        404 (``get_object`` borné à la société). Aucun statut écrit."""
        from ..domain.suivi import revoquer_liens_publics
        devis = self.get_object()
        nombre, quand = revoquer_liens_publics(devis)
        return Response({'revoques': nombre, 'revoque_le': quand})

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
