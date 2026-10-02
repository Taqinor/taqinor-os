import logging

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from ..models import Devis, BonCommande
from ..serializers import (
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    FactureSerializer,
    DevisActivitySerializer,
    DevisActionRequiseSerializer,  # PACT17 — forme déclarée de l'agrégat
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
    HasPermissionOrLegacy,
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
# QJR73 — L'ÉCRIVAIN UNIQUE DES LIGNES N'EST PLUS UNE MÉTHODE DE CE VIEWSET.
# `_replace_lines_atomic` vivait ici, donc hors d'atteinte de tout autre
# appelant, alors que les tests le décrivent comme « le SEUL chemin d'écriture »
# des lignes. Son corps est parti TEL QUEL dans `domain/lignes.remplacer_lignes`
# (dédenté, `self` retiré, pas une ligne de logique touchée).
# QJR93 (M5, bascule 1/5) — CE FICHIER N'APPELLE PLUS `remplacer_lignes`.
# `atomic` et `replace-lines` recopiaient la MÊME paire de gestes (écrire les
# lignes sous transaction, puis rafraîchir les quatre études hors transaction),
# chacun avec son propre commentaire de dix lignes expliquant l'autre. Les deux
# passent désormais par `domain/pipeline.appliquer` — le mode `ecrire` pour la
# première moitié, le mode `rafraichir` pour la seconde — donc par LE MÊME
# écrivain et LE MÊME ordonnancement que les quatre autres origines de devis.
# Les frontières de transaction n'ont pas bougé d'une ligne : les réponses des
# endpoints sont inchangées à l'octet.
from ..domain.pipeline import (
    MODE_ECRIRE, MODE_RAFRAICHIR, ORIGINE_ECRAN, IntentionDevis, appliquer,
)

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


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


def _refus_modifiabilite(devis, geste):
    """QJR516 — la garde d'édition UNIQUE des vues : ``True`` si le geste
    est REFUSÉ sur ce devis (prédicat ``domain/modifiabilite``). L'appelant
    répond alors ``_reponse_non_modifiable`` (409). Lit le statut, ne
    l'écrit jamais (règle #4)."""
    from ..domain.modifiabilite import est_modifiable
    return not est_modifiable(devis, geste)


def _reponse_non_modifiable(devis, geste, message_statut=None):
    """QJR516 — la réponse 409 ``{detail, statut, revision_possible}`` d'un
    geste refusé. ``message_statut`` (avec ``%s`` = statut affiché) conserve
    le texte historique d'une garde existante pour un devis ACTIF ; un devis
    remplacé ou archivé reçoit la raison du prédicat."""
    from ..domain.modifiabilite import verdict
    v = verdict(devis, geste)
    if message_statut and devis.is_active:
        detail = message_statut % devis.get_statut_display()
    else:
        detail = v['raison_non_modifiable']
    return Response(
        {'detail': detail, 'statut': devis.statut,
         'revision_possible': v['revision_possible']},
        status=status.HTTP_409_CONFLICT)


class _RemiseEnvoiRefusee(APIException):
    """QJR539 — 400 ``{detail}`` : garde de remise T17 d'un envoi."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'remise_non_approuvee'


def _exiger_remise_envoi(devis, user, *, enregistrer=True):
    """QJR539 — garde de remise T17 d'un VRAI envoi (lien client, courriel,
    aperçu/commit WhatsApp), appelée AVANT tout effet de bord ; lève
    ``_RemiseEnvoiRefusee`` (400 ``{detail}``). Ne juge que les devis encore
    envoyables (brouillon, envoyé). ``enregistrer=False`` : un aperçu n'écrit
    pas l'approbation implicite d'un admin."""
    from ..services import RemiseNonApprouvee, exiger_approbation_remise
    if devis.statut not in ('brouillon', 'envoye'):
        return
    try:
        exiger_approbation_remise(devis, user, enregistrer=enregistrer)
    except RemiseNonApprouvee as erreur:
        raise _RemiseEnvoiRefusee(erreur.message)


def _valider_etude_ecran(etude_in):
    """QJR544 — pré-validation des CHOIX d'écran (``etude_params`` clés
    ECRAN) avant toute écriture, partagée par ``/atomic`` et
    ``replace-lines`` : un refus pointe ``etude_params`` et n'écrit rien."""
    from rest_framework.exceptions import ValidationError
    from ..domain.etude_schema import ECRAN, fusionner
    if etude_in is None:
        return
    if not isinstance(etude_in, dict):
        raise ValidationError({'etude_params': "Objet {clé: valeur} attendu."})
    try:
        fusionner({}, proprietaire=ECRAN, **etude_in)
    except (ValueError, TypeError) as exc:
        raise ValidationError({'etude_params': str(exc)})


def _gardes_mise_a_jour(instance, validated_data, user, *, t17=True):
    """QJR544 — les gardes d'une mise à jour d'en-tête, en UN point (PATCH
    ``perform_update`` et ``replace-lines`` avec ``entete``) :

    * QJR521 — un devis remplacé / archivé ne se réactive jamais ;
    * QJR516 — prédicat de modifiabilité (geste ENTETE), 400 {'statut'} et
      l'exception « désactivation seule » conservés ;
    * ERR8 — lead / client d'une autre société refusés ;
    * QJR539 (``t17``) — correction d'un ENVOYÉ : une remise globale ENTRANTE
      plus profonde au-dessus du seuil n'est plus couverte par l'approbation
      d'avant (400 {'statut'}). ``replace-lines`` passe ``t17=False`` et juge
      APRÈS l'écriture des lignes, dans sa transaction.

    Lit le statut, ne l'écrit jamais (règle #4)."""
    from rest_framework.exceptions import ValidationError
    if (instance.is_active is False
            and validated_data.get('is_active') is True):
        raise ValidationError({
            'is_active': 'Un devis remplacé ou archivé ne se réactive pas.'})
    from ..domain.modifiabilite import ENTETE, verdict
    if not verdict(instance, ENTETE)['modifiable']:
        nouveau_is_active = validated_data.get(
            'is_active', instance.is_active)
        only_deactivation = (
            nouveau_is_active is False and instance.is_active is True
            and set(validated_data.keys()) <= {'is_active'}
        )
        if not only_deactivation:
            raise ValidationError({
                'statut': 'Devis figé — révisez-le (reviser) pour le '
                          'modifier.'})
    company = getattr(user, 'company', None)
    if company is not None:
        lead = validated_data.get('lead')
        client = validated_data.get('client')
        if lead is not None and lead.company_id != company.id:
            raise ValidationError({'lead': 'Lead inconnu.'})
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
    if t17 and instance.statut == 'envoye':
        from ..services import (
            RemiseNonApprouvee, reverifier_remise_apres_correction)
        from ..domain.tarification import profondeur_remise_effective
        try:
            reverifier_remise_apres_correction(
                instance, user, avant=profondeur_remise_effective(instance),
                remise_globale=validated_data.get(
                    'remise_globale', instance.remise_globale))
        except RemiseNonApprouvee as erreur:
            raise ValidationError({'statut': erreur.message})


class _DevisModifie(APIException):
    """QJR545 — 409 ``{code: 'devis_modifie', detail, updated_at,
    updated_by_nom}`` : le devis a bougé depuis l'ouverture (verrou
    optimiste, contrat ``devis_verrou_edition.json``)."""
    status_code = status.HTTP_409_CONFLICT
    default_code = 'devis_modifie'


def _refus_verrou(devis, request):
    """QJR545 — ``Response`` 409 si ``expected_updated_at`` est fourni et
    diffère du jeton en base ; ``None`` sinon (champ absent ⇒ inchangé)."""
    from ..domain.verrou_devis import verifier_jeton
    charge = verifier_jeton(devis, request.data)
    if charge is None:
        return None
    return Response(charge, status=status.HTTP_409_CONFLICT)


def _jeton(devis):
    """QJR545 — le jeton d'édition à renvoyer dans une réponse 2xx."""
    valeur = getattr(devis, 'updated_at', None)
    # Même représentation que le GET (DateTimeField de DRF) : le jeton
    # renvoyé est comparable, à l'octet, à celui que sert la fiche.
    return serializers.DateTimeField().to_representation(valeur) if valeur else None


class _LotCreationSerializer(serializers.Serializer):
    """QJR648 — le corps de ``POST /devis/<id>/lots/`` : ``nom_lot`` requis,
    ``adresse_site`` facultative, ``ordre`` entier ≥ 0 facultatif, ``lignes``
    liste d'entiers facultative. Une entrée invalide répond 400, jamais 500."""

    nom_lot = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True,
        error_messages={'max_length': 'Nom de lot trop long (150 max).'})
    adresse_site = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True)
    ordre = serializers.IntegerField(
        min_value=0, required=False, allow_null=True,
        error_messages={'invalid': 'Ordre : entier positif attendu.',
                        'min_value': 'Ordre : entier positif attendu.'})
    lignes = serializers.ListField(
        child=serializers.IntegerField(
            error_messages={'invalid': 'Lignes : identifiants entiers '
                                       'attendus.'}),
        required=False, allow_null=True)

    def validate_nom_lot(self, valeur):
        nom = (valeur or '').strip()
        if not nom:
            raise serializers.ValidationError('Nom de lot requis.')
        return nom

    def validate(self, attrs):
        if not (attrs.get('nom_lot') or '').strip():
            raise serializers.ValidationError(
                {'nom_lot': 'Nom de lot requis.'})
        return attrs


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
        # ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les CHOIX de l'écran
        # (``scenario``, ``recommended_option``, ``nombre_proprietes``)
        # décident de l'option que suit l'argent (``utils/options.py``
        # ``deux_options_declarees``). Ils arrivaient APRÈS la création (PATCH
        # ``etude-params``) : la réponse de création totalisait alors TOUTES
        # les lignes (les deux onduleurs compris) et l'écran « Devis
        # enregistré » annonçait un prix qu'aucun document ne porte. Ils sont
        # désormais écrits par l'unique écrivain (``etude_schema.ecrire``)
        # sous la MÊME transaction. Validés AVANT : un refus pointe le champ
        # ``etude_params`` et ne crée rien. Absents ⇒ comportement d'hier.
        from ..domain.etude_schema import ECRAN, ecrire
        etude_in = head.pop('etude_params', None)
        _valider_etude_ecran(etude_in)
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

        # QJR563 — même devise par défaut de la société que POST /devis/ ;
        # une devise fournie dans le corps est respectée.
        devise_kwargs = {}
        if 'devise' not in serializer.validated_data:
            from ..domain.creation import devise_par_defaut
            devise_kwargs['devise'] = devise_par_defaut(company)
        try:
            with transaction.atomic():
                def _save(ref):
                    devis = serializer.save(
                        reference=ref, client=client,
                        created_by=request.user, company=company,
                        **devise_kwargs)
                    if etude_in:
                        ecrire(devis, proprietaire=ECRAN, **etude_in)
                    # QJR93 — l'ÉTAPE 5 du pipeline, sous la MÊME transaction :
                    # la composition est celle que l'écran a arrêtée, le
                    # pipeline ne la recompose pas (recomposer détruirait les
                    # prix et quantités tapés par le commercial).
                    # QJR550 — ``user`` : l'auteur de l'instantané du
                    # geste, jamais lu du corps.
                    appliquer(devis, IntentionDevis(
                        origine=ORIGINE_ECRAN, mode=MODE_ECRIRE,
                        company=company, user=request.user,
                        composition=lignes_in))
                    return devis
                create_numbered(Devis, company, 'devis', _save)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Enregistrement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)

        devis = serializer.instance
        # QJR554 — la marge interne (QX23be) et le kWc sont posés par le mode
        # RAFRAICHIR du pipeline ci-dessous (``finaliser_caches``) : plus de
        # rattrapage manuel ici.
        # L-QA1 (24/08/2026) — MÊME rafraîchissement que ``replace_lines``
        # ci-dessous : ``atomic`` EST le chemin de création du générateur
        # (devis + lignes en un seul commit) et, avant ce correctif, ne posait
        # ni le bloc horaire ni le tableau de dimensionnement — un devis créé
        # ici gardait ``etude_params`` sans ``etude_horaire``/``dimensionnement``
        # tant qu'aucune édition ultérieure (``replace-lines``) ne les
        # déclenchait. HORS de la transaction ci-dessus, best-effort (voir la
        # docstring des deux fonctions) : un devis correctement créé ne doit
        # jamais être annulé par une étude.
        # L-1V (24/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE : la liste
        # recopiée ici (et une deuxième fois dans ``replace_lines``, et une
        # TROISIÈME, incomplète, dans ``LigneDevisViewSet``) vit maintenant
        # dans ``services.rafraichir_etudes_du_devis``. Une étude ajoutée
        # demain part sur les trois chemins d'écriture, ou sur aucun.
        # QJR47 — ``force=True`` RETIRÉ : il protégeait contre un cache posé
        # sur la simple PRÉSENCE de la clé. Depuis QJR43/QJR44 c'est
        # l'EMPREINTE des entrées (et, pour le bloc horaire, la composition)
        # qui décide — un devis qui vient d'être créé n'a aucun bloc, donc les
        # quatre études se calculent de toute façon.
        # QJR93 — l'ÉTAPE 7 du pipeline. Elle RELIT l'instance avant les
        # études (QJR20) : sur un devis qui vient d'être créé la relecture ne
        # change rien, mais le contrat cesse d'être « espéré » selon le chemin.
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR, company=company))
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
        # QJR516 — le prédicat UNIQUE (geste LIGNES) ; texte et code 409
        # {'detail'} CONSERVÉS.
        if _refus_modifiabilite(devis, 'LIGNES'):
            return _reponse_non_modifiable(
                devis, 'LIGNES',
                'Devis « %s » : ses lignes ne peuvent plus être '
                'remplacées. Utilisez « Réviser » pour en créer une '
                'nouvelle version.')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        lignes_in = request.data.get('lignes')
        if not isinstance(lignes_in, list):
            return Response({'detail': 'Champ « lignes » requis (liste).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # QJR204 — ALIGNÉ SUR ``/atomic``, QUI REFUSE DÉJÀ L'ENSEMBLE VIDE.
        # Cet endpoint SUPPRIME puis recrée : une liste VIDE effaçait toutes
        # les lignes d'un devis brouillon/envoyé et répondait 200. Vérifié
        # avant d'en faire un refus : aucun flux légitime de « tout vider »
        # n'existe (``ventesApi.replaceLignesDevis`` est l'unique appelant de
        # production et l'écran n'offre aucun geste de ce genre). L'écrivain
        # unique du domaine porte la même garde, pour les chemins non-HTTP.
        if not lignes_in:
            from ..domain.lignes import MSG_REMPLACEMENT_VIDE
            return Response({'detail': MSG_REMPLACEMENT_VIDE},
                            status=status.HTTP_400_BAD_REQUEST)
        # QJR544 (contrat QJR504, devis_replace_lines_entete.json) — UNE
        # transaction pour l'édition entière : en-tête + lignes + choix
        # d'écran. ``entete`` et ``etude_params`` sont OPTIONNELS : sans eux,
        # comportement identique à l'octet. ``statut`` dans l'en-tête est
        # IGNORÉ (QJR541). Tout est VALIDÉ avant la première écriture.
        from rest_framework.exceptions import ValidationError
        entete_in = request.data.get('entete')
        etude_in = request.data.get('etude_params')
        entete_ser = None
        if entete_in is not None:
            if not isinstance(entete_in, dict):
                return Response({'detail': 'Champ « entete » : objet attendu.'},
                                status=status.HTTP_400_BAD_REQUEST)
            entete = {k: v for k, v in entete_in.items()
                      if k not in ('statut', 'company')}
            entete_ser = DevisWriteSerializer(devis, data=entete, partial=True)
            entete_ser.is_valid(raise_exception=True)
            _gardes_mise_a_jour(devis, entete_ser.validated_data,
                                request.user, t17=False)
        _valider_etude_ecran(etude_in)
        from ..services import (
            RemiseNonApprouvee, reverifier_remise_apres_correction)
        from ..domain.tarification import profondeur_remise_effective
        # QJR539 — correction d'un ENVOYÉ : profondeur de remise AVANT le geste.
        envoye = devis.statut == 'envoye'
        remise_avant = profondeur_remise_effective(devis) if envoye else None
        geste_complet = entete_ser is not None or bool(etude_in)
        try:
            with transaction.atomic():
                # QJR544 — avec un en-tête, la trace QJR518 encadre le geste
                # ENTIER : UNE ligne de chatter et UN instantané par clic.
                avant_geste = None
                if geste_complet:
                    from ..domain.modifiabilite import debut_de_geste_devis
                    avant_geste = debut_de_geste_devis(devis, request.user)
                if entete_ser is not None:
                    entete_ser.save(updated_by=request.user)
                if etude_in:
                    from ..domain.etude_schema import ECRAN, ecrire
                    ecrire(devis, proprietaire=ECRAN, **etude_in)
                # QJR93 — l'ÉTAPE 5 du pipeline, sous la MÊME transaction
                # qu'hier : un échec préserve les lignes d'origine.
                # QJR518 — ``user`` : l'auteur d'une correction après envoi
                # (chatter + instantané), jamais lu du corps.
                appliquer(devis, IntentionDevis(
                    origine=ORIGINE_ECRAN, mode=MODE_ECRIRE,
                    company=devis.company, user=request.user,
                    composition=lignes_in,
                    tracer_correction=not geste_complet))
                # QJR539 — remise plus profonde au-dessus du seuil sur un
                # envoyé : la garde T17 s'applique, un refus annule le geste.
                if envoye:
                    reverifier_remise_apres_correction(
                        devis, request.user, avant=remise_avant)
                if avant_geste is not None:
                    from ..domain.modifiabilite import fin_de_geste_devis
                    fin_de_geste_devis(devis, request.user, avant=avant_geste,
                                       objet='lignes')
        except RemiseNonApprouvee as erreur:
            return Response({'detail': erreur.message},
                            status=status.HTTP_400_BAD_REQUEST)
        except ValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — rollback : lignes d'origine
            return Response({'detail': f'Remplacement échoué : {exc}'},
                            status=status.HTTP_400_BAD_REQUEST)
        # CJ2b — C'EST LE CHEMIN D'ENREGISTREMENT DU GÉNÉRATEUR. L'écran de
        # devis sauvegarde une édition en deux appels : ``PATCH /devis/<id>/``
        # puis CE remplacement atomique de TOUTES les lignes. Sans ce
        # rafraîchissement, la composition qui vient d'être posée (panneaux,
        # onduleur, batterie) ne serait jamais celle que le bloc horaire décrit,
        # et le devis retomberait sur le modèle forfaitaire alors qu'un calcul
        # heure par heure exact est possible.
        # HORS de la transaction ci-dessus, et best-effort : un devis
        # correctement remplacé ne doit jamais être annulé par une étude.
        # L-1V (24/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE (bloc horaire,
        # dimensionnement, profils comparatifs, conception électrique) : voir
        # ``services.rafraichir_etudes_du_devis``. La composition vient de
        # changer, les quatre études doivent décrire les lignes COURANTES.
        # QJR47 — ``force=True`` RETIRÉ. Il couvrait le cas « les lignes ET
        # ``etude_params`` ont changé dans le même enregistrement » : les DEUX
        # entrent désormais dans l'empreinte (la composition pour le bloc
        # horaire et les profils, le profil client pour l'empreinte des
        # entrées), donc un vrai changement recalcule et un faux ne coûte plus
        # trois balayages complets.
        # QJR93 — l'ÉTAPE 7 du pipeline, HORS de la transaction ci-dessus,
        # comme hier. La relecture (QJR20) est ce que ce chemin faisait déjà
        # implicitement : ``remplacer_lignes`` supprime la relation préchargée
        # par le queryset, ce qui vide son cache de résultats — le contrat est
        # désormais EXPLICITE plutôt que dépendant de ce détail de Django.
        # QJR544 — un en-tête / une étude changés dans ce geste sont des
        # grandeurs invisibles depuis les lignes : ``force_etudes`` (comme le
        # PATCH d'en-tête). Sans eux, comportement d'hier.
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR,
            company=devis.company, force_etudes=geste_complet))
        # QJR545 — le jeton d'édition avance (lignes sauvées hors Devis.save)
        # et la réponse porte celui réellement en base.
        from ..domain.verrou_devis import toucher
        toucher(devis)
        return Response(DevisSerializer(
            devis, context={'request': request}).data)

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

    @action(detail=True, methods=['post'], url_path='share-link',
            permission_classes=[IsResponsableOrAdmin])
    def share_link(self, request, pk=None):
        """B2 — frappe (ou réutilise) un lien public de proposition pour ce
        devis. Permet au site de (re)générer le lien de proposition d'un devis
        existant lors de la livraison. Le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (autre société → 404).

        L-NIV (24/08/2026) — ``niveau`` (« standard » | « confiance ») et
        ``otp_lecture`` (bool) sont optionnels dans le corps : le commercial
        RÉVOQUE ou change le niveau d'un lien EXISTANT sans jamais régénérer
        le jeton (le lien déjà envoyé au client continue de fonctionner).
        Absents du corps → valeurs du lien inchangées (déjà posées, ou les
        défauts du modèle sur un lien fraîchement créé).

        L-SECT (24/08/2026) — ``sections`` (dict {clé: bool}) dit CE QUE le
        client reçoit sur sa page devis, choisi dans le dialogue « Envoyer au
        client ». Mêmes garanties : optionnel, révocable, jeton inchangé.

        QJ-FUNNEL (fondateur 09/09/2026 — « le lead reste en Contacté, il ne
        passe jamais à Devis envoyé ») — ``envoi: true`` (optionnel) dit que
        CE POST est un ENVOI au client (copier le lien pour l'envoyer,
        WhatsApp par devis) et non un aperçu interne ni un simple réglage
        niveau/OTP/sections : le devis passe alors brouillon → « envoyé » via
        ``mark_devis_sent`` — LE chemin unique U4/QJ14, déjà celui de l'email
        et de la barre WhatsApp multi-devis — dont l'événement ``devis_sent``
        avance le funnel du lead vers QUOTE_SENT et démarre la cadence
        après-devis. Idempotent (un devis déjà envoyé/accepté ne bouge pas) ;
        absent/false → comportement d'avant, byte-identique."""
        from ..models import ShareLink
        devis = self.get_object()
        # QJR539 — garde T17 AVANT tout effet d'un ENVOI (gamme, mint, statut).
        if request.data.get('envoi'):
            _exiger_remise_envoi(devis, request.user)
        # GAMME — le mode d'envoi (« seule » / « les_deux ») accompagne le lien
        # quand le vendeur le précise ; absent du corps → mode déjà posé.
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        # QJ-FUNNEL — AVANT le mint : si l'envoi est refusé, l'erreur nommée
        # part au commercial et aucun lien ne sort de ce POST.
        if request.data.get('envoi'):
            from ..services import mark_devis_sent
            mark_devis_sent(devis=devis, user=request.user)
        link = ShareLink.for_devis(devis)
        # L-NIV — ne touche jamais au jeton : simple mise à jour de champs sur
        # le lien déjà résolu (créé ou réutilisé) ci-dessus.
        champs_modifies = []
        niveau = request.data.get('niveau')
        if niveau is not None:
            if niveau not in dict(ShareLink.NIVEAU_CHOICES):
                return Response(
                    {'detail': "niveau invalide (attendu : 'standard' ou "
                               "'confiance')."},
                    status=status.HTTP_400_BAD_REQUEST)
            if link.niveau != niveau:
                link.niveau = niveau
                champs_modifies.append('niveau')
        if 'otp_lecture' in request.data:
            otp_lecture = bool(request.data.get('otp_lecture'))
            if link.otp_lecture != otp_lecture:
                link.otp_lecture = otp_lecture
                champs_modifies.append('otp_lecture')
        # L-SECT (24/08/2026) — sections servies au client, choisies dans le
        # dialogue « Envoyer au client ». Whitelist STRICTE de clés + valeurs
        # BOOLÉENNES seulement : rien d'autre n'entre en base. Absent du corps
        # → sections du lien inchangées (comportement d'aujourd'hui).
        if 'sections' in request.data:
            brut = request.data.get('sections')
            if not isinstance(brut, dict):
                return Response(
                    {'detail': 'sections invalide (objet attendu).'},
                    status=status.HTTP_400_BAD_REQUEST)
            inconnues = sorted(set(brut) - set(ShareLink.SECTIONS_CLES))
            if inconnues:
                return Response(
                    {'detail': 'sections invalide — clés inconnues : '
                               + ', '.join(inconnues) + '.'},
                    status=status.HTTP_400_BAD_REQUEST)
            non_bool = sorted(k for k, v in brut.items() if not isinstance(v, bool))
            if non_bool:
                return Response(
                    {'detail': 'sections invalide — valeurs booléennes '
                               'attendues : ' + ', '.join(non_bool) + '.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if (link.sections or {}) != brut:
                link.sections = brut
                champs_modifies.append('sections')
        if champs_modifies:
            link.save(update_fields=champs_modifies)
        # L-INTPREV (fondateur 25/08/2026) — second lien « aperçu interne » :
        # même page, même construction de chemin (``chemin_proposition``),
        # jeton différent. ``jeton_interne_effectif`` génère paresseusement
        # celui d'un très étroit lien préexistant qui aurait échappé au
        # backfill de la migration 0103 (garde défensive — le cas normal
        # porte déjà un jeton interne, posé par le default du champ ou par ce
        # backfill).
        token_interne = link.jeton_interne_effectif()
        return Response(
            {'token': link.token, 'path': chemin_proposition(devis, link.token),
             'token_interne': token_interne,
             'path_interne': chemin_proposition(devis, token_interne),
             'gamme': _gamme_envoi_payload(devis),
             'niveau': link.niveau, 'otp_lecture': link.otp_lecture,
             'sections': link.sections or {}},
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
        # QJR539 — garde T17 AVANT tout effet (gamme, PDF, lien, `_send`).
        _exiger_remise_envoi(devis, request.user)
        to_email = (request.data.get('to_email') or '').strip() or None
        sujet = (request.data.get('sujet') or '').strip() or None
        corps = (request.data.get('corps') or '').strip() or None
        pdf_mode = (request.data.get('pdf_mode') or 'full').strip()
        # GAMME — mode d'envoi « à la carte », réglé au moment de l'envoi.
        # UN PDF = UNE GAMME : la pièce jointe reste le PDF de CE devis, jamais
        # un PDF fusionné des deux gammes (chaque gamme a le sien).
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        # QJR668 — la pièce jointe est rendue AVANT ``mark_devis_sent`` : les
        # clauses/CGV de l'affaire sont gelées dès maintenant pour y figurer.
        if devis.statut == devis.Statut.BROUILLON:
            from ..domain.cycle_vie import figer_clauses_devis
            figer_clauses_devis(devis)

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

        # QJR519 — un email en ÉCHEC ne marque JAMAIS le devis envoyé (ni
        # date_envoi, ni devis_sent → funnel, ni cadence) : 502 explicite,
        # EmailLog ECHEC et note chatter ci-dessus conservés.
        if not ok:
            devis.refresh_from_db(fields=['statut'])
            return Response({
                'detail': f'Échec envoi email : {err}',
                'log_id': log.id,
                'email_statut': log.statut,
                'devis_statut': devis.statut,
            }, status=status.HTTP_502_BAD_GATEWAY)

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

    def _reponse_derive(self, request, devis, resultat):
        """QJR588 — la réponse 200 du contrat QJR505."""
        from ..domain.verrou_devis import toucher
        devis.refresh_from_db()
        toucher(devis)
        return Response({
            'devis': DevisSerializer(devis, context={'request': request}).data,
            'champs_repris': resultat.get('champs_repris', []),
            'corrige_apres_envoi': bool(resultat.get('corrige_apres_envoi')),
            'avertissements': resultat.get('avertissements', []),
        })

    @staticmethod
    def _refus_derive_fige(devis):
        """QJR588 — accepté / refusé / expiré / remplacé : 400
        ``{detail, code: 'devis_fige'}`` (garde QJR516, statut LU)."""
        from ..domain.modifiabilite import (
            LIGNES, DevisNonModifiable, exiger_modifiable)
        try:
            exiger_modifiable(devis, LIGNES)
        except DevisNonModifiable:
            return Response(
                {'detail': 'Devis figé — révisez-le (reviser) pour le '
                           'modifier.', 'code': 'devis_fige'},
                status=status.HTTP_400_BAD_REQUEST)
        return None

    @action(detail=True, methods=['post'], url_path='reappliquer-lead',
            permission_classes=[IsResponsableOrAdmin])
    def reappliquer_lead(self, request, pk=None):
        """QJR588 (contrat ``devis_reappliquer_lead.json``) — « Reprendre
        les valeurs du lead » : études recalculées depuis le lead courant,
        compte de panneaux réconcilié (prix négociés, lignes manuelles,
        sections et notes intacts), estampille reposée. Brouillon et envoyé
        sur place (envoyé : correction tracée) ; figé → 400 ``devis_fige``."""
        from ..domain.pipeline import reappliquer_lead
        devis = self.get_object()  # borné société
        refus = self._refus_derive_fige(devis)
        if refus is not None:
            return refus
        resultat = reappliquer_lead(devis, user=request.user,
                                    company=request.user.company)
        return self._reponse_derive(request, devis, resultat)

    @action(detail=True, methods=['post'], url_path='acquitter-derive',
            permission_classes=[IsResponsableOrAdmin])
    def acquitter_derive(self, request, pk=None):
        """QJR588 — « Garder les valeurs du devis » : l'estampille est
        reposée sur les valeurs COURANTES du lead, rien d'autre (lignes et
        études octet-identiques). Figé → 400 ``devis_fige``."""
        from ..domain.pipeline import restamper_provenance
        devis = self.get_object()
        refus = self._refus_derive_fige(devis)
        if refus is not None:
            return refus
        restamper_provenance(devis)
        return self._reponse_derive(request, devis, {
            'champs_repris': [], 'corrige_apres_envoi': False,
            'avertissements': []})

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
        # ── QJR407 (S5-1 / S5-2 / S5-4) — LE CLONEUR DU DOMAINE ─────────────
        # Cette boucle réimplémentait ``Devis.objects.create(...)`` et OMETTAIT
        # les sept champs que le cloneur porte depuis QJR146(a) : ``devise``,
        # ``taux_change``, ``echeancier``, ``acompte_pct``, ``acompte_montant``,
        # ``entite``, ``custom_data`` — une variante perdait l'échéancier
        # NÉGOCIÉ et l'acompte de l'original. Elle créait en outre le devis
        # HORS transaction avant de cloner ses lignes (S5-4). La
        # réimplémentation est SUPPRIMÉE (règle permanente 2).
        #
        # L'ÉCHELLE reste propre à cette vue — c'est la seule chose que ce
        # chemin a de particulier, et elle passe par ``remplacements``.
        # QJR84 conservé mot pour mot : ``quantite_manuelle`` NE se recopie
        # PAS — la quantité vient d'être mise à l'échelle, elle n'est plus
        # celle que le commercial avait tapée. QJR202 (purge des clés dérivées
        # + rafraîchissement FORCÉ des études sur la taille RÉELLE de la copie)
        # est porté par le cloneur, pour les quatre chemins à la fois.
        from ..domain.creation import cloner_devis

        for scale in scales:
            variant_note = _label_for(scale)

            def _echelle(ligne, _scale=scale):
                brute = ligne.quantite * Decimal(str(_scale))
                qty = brute.quantize(Decimal('0.01'),
                                     rounding=ROUND_HALF_UP)
                return {'quantite': max(qty, Decimal('0.01')),
                        'quantite_manuelle': False}

            nd = cloner_devis(
                source, user=request.user,
                note=(f'[Variante {variant_note}] '
                      + (source.note or '')).strip(),
                # Groupe : version_parent = racine, version incrémentée,
                # is_active=True (alternative, pas remplacement).
                version=source.version + len(created) + 1,
                version_parent=root,
                remplacements=_echelle)
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

    # api-only: TEMPORAIRE (QJR667) — aucun bouton « Dupliquer » du devis n'appelle
    # encore cette action ; retirer ce marqueur dès que l'écran la câble.
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
        # QJR521 — le corps inline (cloner_devis puis save HORS transaction :
        # fourche au double clic, v1 active à côté d'un brouillon orphelin)
        # est remplacé par LE service de domaine verrouillé. QJR407 (cloneur
        # unique, sept champs, lignes QJR224/QJR84) vit dans ``cloner_devis``,
        # appelé par ``reviser_devis``.
        from ..domain.cycle_vie import RevisionError, reviser_devis
        old = self.get_object()
        try:
            nd = reviser_devis(old, user=request.user)
        except RevisionError as exc:
            return Response({'detail': exc.message},
                            status=status.HTTP_409_CONFLICT)
        return Response(
            DevisSerializer(nd, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'],
            url_path='historique-configuration',
            permission_classes=[IsResponsableOrAdmin])
    def historique_configuration(self, request, pk=None):
        """NTCPQ20 — Historique FIN des configurations d'un devis brouillon
        ou ENVOYÉ (QJR552 : l'état vu par le client avant une correction après
        envoi, puis l'état corrigé — D-QJR5-1 / D-QJR5-7). Un instantané par
        geste d'enregistrement (QJR550), apparié par identité stable (QJR551).

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
            # QJR516 — rattacher des lignes à un lot est une édition de LIGNES.
            if _refus_modifiabilite(devis, 'LIGNES'):
                return _reponse_non_modifiable(devis, 'LIGNES')
            # QJR648 — l'entrée est VALIDÉE avant toute écriture (un « ordre »
            # ou des « lignes » non numériques répondaient 500) et la création
            # + le rattachement tiennent dans UNE transaction : jamais de lot
            # orphelin qu'un nouvel essai refuserait comme « déjà existant ».
            entree = _LotCreationSerializer(data=request.data)
            entree.is_valid(raise_exception=True)
            donnees = entree.validated_data
            nom = donnees['nom_lot']
            if devis.lots.filter(nom_lot=nom).exists():
                raise ValidationError(
                    {'nom_lot': 'Ce lot existe déjà sur ce devis.'})
            with transaction.atomic():
                lot = LotDevis.objects.create(
                    company=devis.company, devis=devis, nom_lot=nom,
                    adresse_site=(donnees.get('adresse_site') or '').strip(),
                    ordre=donnees.get('ordre') or 0)
                ids = donnees.get('lignes') or []
                if ids:
                    # Jamais une ligne d'un autre devis (donc d'une autre
                    # société).
                    devis.lignes.filter(id__in=ids).update(lot=lot)
        resultat = lots_totaux(devis)
        if resultat is None:
            resultat = {'lots': [], 'hors_lot': None,
                        'total_consolide': None}
        return Response(
            resultat,
            status=(status.HTTP_201_CREATED if request.method == 'POST'
                    else status.HTTP_200_OK))

    # api-only: TEMPORAIRE (QJR667) — aucun bouton « Renouveler » du devis n'appelle
    # encore cette action ; retirer ce marqueur dès que l'écran la câble.
    @action(detail=True, methods=['post'], url_path='renouveler',
            permission_classes=[IsResponsableOrAdmin])
    def renouveler(self, request, pk=None):
        """NTCPQ13 — Renouvelle un devis ACCEPTÉ (ou expiré) : nouveau brouillon
        reprenant les lignes actuelles aux PRIX CATALOGUE COURANTS, lié à son
        devis d'origine (``devis_origine``) et numéroté
        (``numero_renouvellement``). Le devis source reste intact — distinct de
        ``reviser`` (qui crée la V+1 d'un devis envoyé, accepté, refusé ou
        expiré — D-QJR5-2 ; un accepté révisé garde son chantier, QJR559)."""
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
            # QJR135 / ES4 — ON SÉRIALISE L'INSTANCE QUE LE SERVICE A ÉCRITE.
            # ``accept_devis`` REBIND son nom local sur la relecture VERROUILLÉE
            # (``select_for_update().get(...)``) : l'objet de l'appelant reste
            # celui d'AVANT, donc ``statut`` y valait encore « envoyé »,
            # ``option_acceptee`` '' et ``accepte_par_nom`` '' juste après une
            # acceptation réussie. On reprend donc sa VALEUR DE RETOUR — jamais
            # un second ``refresh_from_db`` qui redemanderait ce que le service
            # a déjà en main.
            devis = accept_devis(
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

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Chatter du devis (notes + acceptation)."""
        devis = self.get_object()
        return Response(
            DevisActivitySerializer(devis.activites.all(), many=True).data)

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

    @action(detail=True, methods=['get'], url_path='lecture-client',
            permission_classes=[IsResponsableOrAdmin])
    def lecture_client(self, request, pk=None):
        """ANALYT1 (audit item 64, 26/08/2026) — « Lecture par le client » :
        combien de VISITES DISTINCTES chaque section de la proposition
        publique a reçues, et l'alerte de friction si une section a été
        RELUE au-delà du seuil (``ShareLink.friction_alert``).

        Réservé responsable/admin (VX199 — voir ``get_permissions`` ci-
        dessus) : ce sont des analytics INTERNES (temps/visites du client sur
        sa propre proposition) — jamais montrées au client, jamais une
        promesse de conversion, juste un signal « ce client relit, un appel
        peut aider ». Lecture PURE sur le ``ShareLink`` le plus récent du
        devis, borné à sa société (déjà scopée par ``get_object()``).
        ``sections``/``friction`` vides ⇒ aucun beacon reçu pour ce devis."""
        from ..models import ShareLink

        devis = self.get_object()
        link = (ShareLink.objects
                .filter(devis=devis, company=devis.company)
                .order_by('-id').first())
        return Response({
            'sections': link.visites_par_section if link else {},
            'friction': link.friction_alert if link else None,
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
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )

        devis = self.get_object()
        # QJR539 — garde T17 : l'aperçu précède un envoi, il est refusé
        # d'emblée (sans écrire l'approbation implicite d'un admin).
        _exiger_remise_envoi(devis, request.user, enregistrer=False)
        phone = devis_recipient_phone(devis)
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
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
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )
        from ..services import mark_devis_sent

        devis = self.get_object()
        # QJR539 — garde T17 AVANT tout effet (gamme, lien, statut).
        _exiger_remise_envoi(devis, request.user)
        phone = devis_recipient_phone(devis)
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
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

    @action(detail=True, methods=['post'], url_path='pdf-partage',
            permission_classes=[IsResponsableOrAdmin])
    def pdf_partage(self, request, pk=None):
        """QJR659 (décision fondateur 01/10) — le PDF du devis a été partagé
        par la feuille de partage native (``navigator.share`` résolu) : cela
        vaut ENVOI, comme copier le lien client (D-QJR5-3).

        Ce n'est PAS un « marquer envoyé » nu : la garde de remise T17
        (QJR539) passe AVANT tout effet (400 ``{detail}``, le devis reste
        brouillon), puis ``mark_devis_sent`` — le seul chemin brouillon →
        envoyé (idempotent, ne régresse jamais un accepté/refusé/expiré,
        funnel via ``devis_sent``). Aucun lien client n'est minté. Le
        frontend ne l'appelle ni sur AbortError ni sur le repli
        téléchargement."""
        from ..services import mark_devis_sent
        from .. import activity

        devis = self.get_object()
        _exiger_remise_envoi(devis, request.user)
        etait_brouillon = devis.statut == Devis.Statut.BROUILLON
        mark_devis_sent(devis=devis, user=request.user)
        if etait_brouillon:
            activity.log_devis_note(
                devis, request.user,
                f'PDF du devis {devis.reference} partagé (feuille de partage).')
        return Response({'devis_statut': devis.statut})

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

    # ── TAILLES (ordre fondateur, 26/08/2026) — les trois tailles côté vendeur ─
    #
    # TROIS actions, et le découpage n'est pas cosmétique : ``get_permissions``
    # raisonne sur ``self.action``, donc une action qui porterait à la fois le
    # GET et le PATCH sous un seul nom forcerait la LECTURE au niveau de garde
    # de l'ÉCRITURE. Une action par verbe = une garde juste par verbe.
    #
    # PIÈGE VX199 : les trois sont inscrites dans la liste de ``get_permissions``
    # ci-dessus, ET déclarent la MÊME classe dans leur décorateur. Sans
    # l'inscription, elles tomberaient sur le repli ``IsAdminRole`` — le
    # décorateur ne serait jamais consulté et fermerait l'écran aux
    # responsables tout en AYANT L'AIR ouvert.

    def _offres_tailles_reponse(self, devis):
        """L'état COMPLET des trois tailles, tel que l'écran vendeur le lit.

        MÊME dérivation que la page client (``offres_tailles.deriver``) : le
        vendeur et le client ne peuvent pas voir deux jeux de chiffres. Seule
        différence, assumée : ici aucune taille n'est cachée sous le seuil de
        deux (c'est un écran d'édition, pas une comparaison), et un devis non
        dérivable répond ``editable: false`` avec sa raison EN CLAIR plutôt
        qu'une section muette.
        """
        from ..offres_tailles import deriver
        from ..quote_engine.builder import build_quote_data

        try:
            data = build_quote_data(devis, {'pdf_mode': 'full'})
            bloc = deriver(devis, data)
        except Exception:  # noqa: BLE001 — un écran d'édition ne tombe jamais
            logging.getLogger(__name__).warning(
                'offres_tailles indisponibles sur %s',
                getattr(devis, 'reference', '?'), exc_info=True)
            bloc = None
        if bloc is None:
            return {
                'offres_tailles': None,
                'editable': False,
                'raison_non_editable': (
                    'Ce devis ne permet pas encore de dériver des tailles : '
                    'il doit être résidentiel, porter un profil de '
                    'consommation réel et un tableau de dimensionnement.'
                ),
            }
        return {'offres_tailles': bloc, 'editable': True}

    # ── QJR58 — LE REGISTRE DE SURCHARGES (décision fondateur D12) ───────────

    @staticmethod
    def _overrides_reponse(devis, chemins_regeneres=()):
        """La forme du contrat PACT10 ``contract_samples/devis_overrides.json``.

        ``effectif`` est DÉRIVÉ À CHAQUE LECTURE, jamais stocké : la carte des
        valeurs ``auto`` est celle que le moteur rend AUJOURD'HUI.

        QJR216 — LA CARTE ``autos`` EST ENFIN ALIMENTÉE. Elle valait ``{}`` en
        dur depuis QJR58, si bien que **toute** réponse annonçait ``auto:
        null``, y compris sur les chemins dont le moteur a une valeur lisible :
        le bloc promettait « valeur posée vs valeur moteur, côte à côte » et ne
        portait que la première. Elle vient désormais de
        ``domain.overrides.autos_du_devis`` — les chemins que le moteur ne sait
        pas dériver restent OMIS, jamais remplis d'un défaut (règle Z2).

        ``chemins_regeneres`` — les chemins qui viennent de repasser en
        automatique (DELETE). Ils sont FORCÉS dans la vue pour que la réponse
        les porte avec leur valeur moteur : sortis du registre, ils
        disparaissaient purement et simplement de la réponse, alors que
        l'endpoint promet « retour à l'automatique ».

        QJR305 — ILS SONT FORCÉS DANS LA VUE, PAS DANS LA CARTE ``autos``. Les
        y insérer avec ``None`` (l'ancien ``setdefault``) faisait passer pour
        « valeur automatique nulle » un chemin dont le moteur n'a simplement
        AUCUNE valeur : ``vue_effective`` ne pouvait plus le marquer
        ``non_derivable`` et l'écran retombait sur le champ vide ambigu.

        ``lignes`` est une carte ``{id: {...}}`` — JAMAIS une liste indexée par
        position (une ligne supprimée déplacerait la surcharge sur une autre).
        """
        from ..domain import overrides as registre_overrides

        lignes = {}
        for ligne in devis.lignes.all():
            marques = {
                champ: bool(getattr(ligne, champ))
                for champ in ('quantite_manuelle', 'prix_manuel')
                if hasattr(ligne, champ)
            }
            if any(marques.values()):
                lignes[str(ligne.pk)] = marques
        autos = registre_overrides.autos_du_devis(devis)
        return {
            'overrides': registre_overrides.registre_du_devis(devis),
            'effectif': registre_overrides.vue_effective(
                devis, autos,
                chemins_supplementaires=tuple(chemins_regeneres)),
            'lignes': lignes,
        }

    @action(detail=True, methods=['get', 'patch', 'delete'],
            url_path='overrides',
            permission_classes=[IsResponsableOrAdmin])
    def overrides(self, request, pk=None):
        """GET / PATCH / DELETE du REGISTRE de surcharges de CE devis.

        * **GET** — le registre + le bloc ``effectif`` dérivé à la lecture.
        * **PATCH** — FUSIONNE le sous-ensemble de chemins reçu : envoyer
          ``{"taille.nb_panneaux": {"valeur": 14}}`` ne touche AUCUN autre
          chemin déjà posé. Un champ DÉRIVÉ, un chemin hors liste blanche D12
          ou une clé indexée par POSITION sont refusés en 400 avec un message
          FR qui NOMME le chemin — jamais un silence.
        * **DELETE ?chemin=<chemin>** — ``regenerer`` : SUPPRIME l'override de
          ce chemin (retour à l'automatique). Il ne le REMPLACE jamais dans le
          REGISTRE par une valeur calculée : reposer une valeur exige un
          nouveau PATCH explicite. QJR216 — la RÉPONSE, elle, porte le chemin
          régénéré avec la valeur que le moteur calcule : sans quoi « retour à
          l'automatique » rendait un trou au lieu de la valeur promise.

        L'ÉCRITURE PASSE PAR UN ``UPDATE`` D'UNE SEULE COLONNE
        (``domain.overrides.ecrire_colonne``) : ni ``updated_at`` ni le gel
        ``prix_par_kwc`` ne bougent — les deux effets de bord de ``Devis.save``
        sont faux pour une pose d'override. Aucune ligne, aucun total, aucun
        statut n'est touché (règle #4).

        QJR223 — LE CYCLE LIRE-FUSIONNER-ÉCRIRE EST VERROUILLÉ (``select_for_
        update``), PAS SEULEMENT L'ÉCRITURE. ``ecrire_colonne`` fait un
        ``UPDATE`` inconditionnel de la colonne entière : sans verrou, deux
        PATCH concurrents sur deux chemins DIFFÉRENTS relisent tous deux le
        MÊME registre de départ, fusionnent chacun sur cette même base, puis
        s'écrasent l'un l'autre au ``UPDATE`` — le perdant répond quand même
        200 comme si sa surcharge était stockée (``ecrire_colonne`` réécrit
        aussi ``devis.overrides`` EN MÉMOIRE avant que la course ne tranche).
        Le verrou de ligne (``domain.overrides.relire_verrouille``, jamais
        ``Devis.save()`` — ce serait réintroduire les deux effets de bord
        ci-dessus) SÉRIALISE les deux requêtes : la seconde relit alors le
        registre DÉJÀ enrichi par la première et fusionne par-dessus — les
        deux surcharges survivent.
        """
        from ..domain import overrides as registre_overrides
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        from ..serializers import OverridesSerializer

        devis = self.get_object()
        if request.method == 'GET':
            return Response(self._overrides_reponse(devis))
        # QJR516 — PATCH et DELETE gardés (geste ETUDE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        from ..domain.verrou_devis import toucher

        if request.method == 'DELETE':
            chemin = request.query_params.get('chemin') or ''
            if not chemin:
                return Response(
                    {'chemin': 'Paramètre requis : quel chemin régénérer ?'},
                    status=status.HTTP_400_BAD_REQUEST)
            if not registre_overrides.chemin_autorise(chemin):
                return Response(
                    {'chemin': registre_overrides.MSG_CHEMIN_INCONNU},
                    status=status.HTTP_400_BAD_REQUEST)
            avant_geste = debut_de_geste_devis(devis, request.user)
            with transaction.atomic():
                devis = registre_overrides.relire_verrouille(devis)
                registre_overrides.ecrire_colonne(
                    devis, registre_overrides.regenerer(devis, chemin))
            self._rafraichir_etudes_apres_surcharge(devis)
            fin_de_geste_devis(devis, request.user, avant=avant_geste,
                               objet='surcharges')
            toucher(devis)
            # QJR216 — le chemin régénéré REVIENT dans la réponse avec la
            # valeur du moteur (avant, il en disparaissait : « retour à
            # l'automatique » se soldait par un trou).
            reponse = self._overrides_reponse(
                devis, chemins_regeneres=(chemin,))
            reponse['updated_at'] = _jeton(devis)
            return Response(reponse)

        serializer = OverridesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        avant_geste = debut_de_geste_devis(devis, request.user)
        try:
            with transaction.atomic():
                devis = registre_overrides.relire_verrouille(devis)
                registre = registre_overrides.fusionner(
                    devis, serializer.validated_data, utilisateur=request.user)
                registre_overrides.ecrire_colonne(devis, registre)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        self._rafraichir_etudes_apres_surcharge(devis)
        fin_de_geste_devis(devis, request.user, avant=avant_geste,
                           objet='surcharges')
        toucher(devis)
        reponse = self._overrides_reponse(devis)
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)

    @staticmethod
    def _rafraichir_etudes_apres_surcharge(devis):
        """QJR564 — une surcharge posée ou régénérée (``etude.jour_reference``,
        ``taille.nb_panneaux``, ``taille.panel_watt``…) nourrit le moteur ; les
        études STOCKÉES (lues telles quelles par ``/proposal``) sont donc
        relancées APRÈS la transaction. Inconditionnel : les empreintes
        QJR43/QJR44 court-circuitent une étude dont les entrées n'ont pas
        bougé — aucune liste de chemins tenue à la main ici. Best-effort : une
        étude en échec n'annule jamais une surcharge enregistrée."""
        from ..services import rafraichir_etudes_du_devis
        try:
            rafraichir_etudes_du_devis(devis)
        except Exception:  # noqa: BLE001
            pass

    @action(detail=True, methods=['get', 'patch'], url_path='etude-params',
            permission_classes=[IsResponsableOrAdmin])
    def etude_params(self, request, pk=None):
        """QJR62 — GET / PATCH **FUSIONNANT** d'``etude_params``.

        LE TROU QUE CECI FERME. L'écran sauvegardait le devis en RECONSTRUISANT
        ``etude_params`` de zéro et en le PATCHant sur un sérialiseur
        permissif : chaque clé qu'il ne reconstruit pas lui-même —
        ``factures_mensuelles_reelles``, ``gamme``, et tout ce que les quatre
        rafraîchisseurs du serveur avaient écrit — DISPARAISSAIT à la
        sauvegarde suivante du vendeur.

        Ici, seules les clés REÇUES bougent ; les autres restent intouchées,
        bit à bit. Une clé inconnue du schéma ou d'un type impossible est
        refusée en 400 avec un message FR, jamais ignorée en silence ; une clé
        DÉRIVÉE dont l'écran n'est pas propriétaire (le bloc horaire, le
        tableau de dimensionnement, les profils comparatifs, la simulation)
        l'est aussi — c'est le moteur qui les calcule.

        Une valeur ``null`` RETIRE la clé (règle Z2 : une étude qui n'est plus
        calculable est retirée, jamais laissée périmée).

        Ce correctif est SERVEUR et ne dépend d'aucun changement d'écran.
        L'écriture est chirurgicale (``update_fields=['etude_params']``) :
        aucune ligne, aucun total, aucun statut ne bouge (règle #4).

        QJR66 / passe Fable pré-merge — LES ÉTUDES SUIVENT LEURS ENTRÉES.
        Depuis que l'écran écrit par ICI (et non plus dans le corps atomique du
        devis), ses factures réelles arrivent APRÈS le rafraîchissement des
        quatre études déclenché par l'écriture des lignes : le PDF servait
        alors des économies dérivées d'entrées PÉRIMÉES — une régression franche
        par rapport au chemin d'hier. On relance donc les études quand, et
        seulement quand, une clé qui NOURRIT le moteur vient de bouger. La
        liste vit dans le SCHÉMA (``entrees_du_moteur``), pas ici. L'appel est
        quasi gratuit quand rien n'a réellement changé : les empreintes
        QJR43/QJR44 court-circuitent chaque étude dont les entrées sont
        identiques — c'est exactement leur rôle.
        """
        from ..domain.etude_schema import ECRAN, ecrire, entrees_du_moteur

        devis = self.get_object()
        if request.method == 'GET':
            return Response({'etude_params': devis.etude_params or {}})
        # QJR516 — PATCH gardé (geste ETUDE).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel, retiré du corps : ce
        # n'est pas une clé d'étude). Réponse littérale : la forme du 409
        # reste lisible par check_api_shapes.
        from ..domain.verrou_devis import verifier_jeton
        charge = verifier_jeton(devis, request.data)
        if charge is not None:
            return Response(
                {'code': charge['code'], 'detail': charge['detail'],
                 'updated_at': charge['updated_at'],
                 'updated_by_nom': charge['updated_by_nom']},
                status=status.HTTP_409_CONFLICT)

        corps = request.data
        if isinstance(corps, dict) and 'expected_updated_at' in corps:
            corps = {k: v for k, v in corps.items()
                     if k != 'expected_updated_at'}
        if not isinstance(corps, dict) or not corps:
            return Response(
                {'detail': 'Corps invalide : un objet {clé: valeur} non vide '
                           'est attendu.'},
                status=status.HTTP_400_BAD_REQUEST)
        # QJR518 — l'option recommandée est IMPRIMÉE : sur un envoyé, sa
        # correction est tracée (instantané avant, trace après).
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        avant_geste = debut_de_geste_devis(devis, request.user)
        try:
            bloc = ecrire(devis, proprietaire=ECRAN, **corps)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        except TypeError:
            return Response(
                {'detail': "Clé d'étude invalide : les noms de clés doivent "
                           'être des identifiants simples.'},
                status=status.HTTP_400_BAD_REQUEST)
        if entrees_du_moteur(corps.keys()):
            # Best-effort, comme sur les trois autres chemins d'écriture : une
            # étude qui échoue ne doit JAMAIS annuler une entrée correctement
            # enregistrée.
            from ..services import rafraichir_etudes_du_devis
            try:
                rafraichir_etudes_du_devis(devis)
            except Exception:  # noqa: BLE001
                pass
        fin_de_geste_devis(devis, request.user, avant=avant_geste,
                           objet='étude')
        # La réponse reste LE BLOC FUSIONNÉ — ce que l'appelant vient de poser,
        # plus ce qui était déjà là. Délibéré : c'est le contrat de cet endpoint
        # (`contract_samples`), et y injecter les blocs dérivés fraîchement
        # recalculés en changerait la forme sans que personne les lise. Ils sont
        # en base, à leur place, pour le moteur PDF.
        # QJR545 — le jeton d'édition (avancé par ``ecrire``) accompagne le
        # bloc : clé ADDITIVE, la forme ``{etude_params}`` est inchangée.
        return Response({'etude_params': bloc, 'updated_at': _jeton(devis)})

    @action(detail=True, methods=['get'], url_path='offres-tailles',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles(self, request, pk=None):
        """LECTURE des trois tailles Éco / Recommandé / Max de ce devis."""
        return Response(self._offres_tailles_reponse(self.get_object()))

    @action(detail=True, methods=['patch'], url_path='offres-tailles/config',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_config(self, request, pk=None):
        """ÉCRITURE de la CONFIGURATION d'UNE taille — elle seule.

        Le sérialiseur refuse en 400 tout nombre dérivé : il n'existe aucun
        chemin par lequel un prix tapé à la main entre dans le stockage. Les
        deux autres tailles ne sont pas touchées, marqueur ``ajuste`` compris.
        Aucune ligne, aucun total, aucun statut du devis ne bouge (règle #4).
        """
        from ..offres_tailles import enregistrer_config
        from ..serializers import OffreTailleEcritureSerializer

        devis = self.get_object()
        # QJR516 — geste ETUDE (configuration d'exploration).
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        serializer = OffreTailleEcritureSerializer(
            data=request.data, context={'company': devis.company})
        serializer.is_valid(raise_exception=True)
        enregistrer_config(devis, serializer.validated_data['cle'],
                           serializer.validated_data['config'],
                           utilisateur=request.user)
        return Response(self._offres_tailles_reponse(devis))

    @action(detail=True, methods=['post'],
            url_path='offres-tailles/regenerer',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_regenerer(self, request, pk=None):
        """RÉGÉNÈRE UNE taille depuis le moteur — elle seule.

        Retire la configuration du vendeur pour CETTE taille (et donc son
        marqueur « ajustée ») : la dérivation moteur reprend la main. Les deux
        autres tailles restent intouchées, y compris leur propre marqueur.
        """
        from ..offres_tailles import regenerer_taille
        from ..serializers import OffreTailleRegenerationSerializer

        devis = self.get_object()
        # QJR516 — geste ETUDE.
        if _refus_modifiabilite(devis, 'ETUDE'):
            return _reponse_non_modifiable(devis, 'ETUDE')
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        serializer = OffreTailleRegenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        regenerer_taille(devis, serializer.validated_data['cle'])
        from ..domain.verrou_devis import toucher
        toucher(devis)
        reponse = self._offres_tailles_reponse(devis)
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)

    @action(detail=True, methods=['post'],
            url_path='offres-tailles/appliquer',
            permission_classes=[IsResponsableOrAdmin])
    def offres_tailles_appliquer(self, request, pk=None):
        """APPLIQUE la taille « Recommandé » AU DEVIS (lignes, totaux, études).

        LA DIFFÉRENCE AVEC ``offres-tailles/config``, ET C'EST TOUT LE SUJET.
        Le PATCH écrit une CONFIGURATION d'exploration : la carte change, le
        devis officiel ne bouge pas. Ce POST-ci fait l'inverse — il RECOMPOSE
        le devis lui-même sur la configuration ajustée de « Recommandé », par
        ``sync_devis_from_layout`` (l'unique machinerie de recomposition), si
        bien que le PDF, les totaux et la page client changent réellement.

        Le STATUT n'est jamais écrit (règle #4) : c'est la garde de
        ``sync_devis_from_layout`` qui décide, et un refus revient en 400 avec
        son motif EN FRANÇAIS (``revision_possible`` dit si « Réviser » est la
        bonne suite). Éco et Max sont refusées : ce sont des explorations.
        """
        from ..offres_tailles import ApplicationImpossible, appliquer_au_devis
        from ..serializers import OffreTailleRegenerationSerializer

        devis = self.get_object()
        # QJR545 — verrou optimiste (jeton optionnel).
        refus = _refus_verrou(devis, request)
        if refus is not None:
            return refus
        serializer = OffreTailleRegenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resume = appliquer_au_devis(devis, serializer.validated_data['cle'],
                                        utilisateur=request.user)
        except ApplicationImpossible as erreur:
            # PAS de ``ValidationError`` ICI, ET C'EST DÉLIBÉRÉ. DRF passe le
            # detail d'une ``ValidationError`` par ``_get_error_details``, qui
            # transforme TOUTE feuille en ``ErrorDetail`` (une chaîne) et
            # enveloppe les scalaires dans une liste : ``revision_possible``
            # partait donc en ``["True"]`` sur le fil. L'écran teste un BOOLÉEN
            # pour choisir entre « Réviser » et un refus sec — une chaîne
            # « True » et une chaîne « False » sont toutes deux vraies en JS,
            # et le bouton « Réviser » se serait affiché sur un devis clos.
            return Response(
                {'detail': erreur.detail,
                 'revision_possible': bool(erreur.revision_possible)},
                status=status.HTTP_400_BAD_REQUEST)
        from ..domain.verrou_devis import toucher
        toucher(devis)
        devis.refresh_from_db()
        reponse = self._offres_tailles_reponse(devis)
        reponse['applique'] = resume
        reponse['updated_at'] = _jeton(devis)
        return Response(reponse)

    def perform_update(self, serializer):
        # YDOCF2 / QJR516 / QJR521 / ERR8 / QJR539 — les gardes d'une mise à
        # jour d'en-tête vivent en UN point (``_gardes_mise_a_jour``), partagé
        # avec ``replace-lines`` (QJR544). QJR541 — ``statut`` est en lecture
        # seule : un PATCH ne fait plus passer un devis en « envoyé » ni
        # n'avance le funnel.
        # QJR545 — verrou optimiste (jeton optionnel, autres clients).
        from ..domain.verrou_devis import verifier_jeton
        charge = verifier_jeton(serializer.instance, self.request.data)
        if charge is not None:
            raise _DevisModifie(charge)
        _gardes_mise_a_jour(serializer.instance, serializer.validated_data,
                            self.request.user)
        company = self.request.user.company
        # QJR518 — état vu par le client capturé AVANT l'écriture (ENVOYÉ
        # seulement) ; trace posée en fin de geste si l'en-tête ou la note
        # visibles ont changé.
        from ..domain.modifiabilite import (
            debut_de_geste_devis, fin_de_geste_devis)
        avant_geste = debut_de_geste_devis(
            serializer.instance, self.request.user)
        super().perform_update(serializer)
        # QJR552 — l'instantané APRÈS le geste (brouillon ou envoyé : l'en-tête
        # corrigé, remise / échéancier, entre dans l'historique) ; dédoublonné.
        from ..domain.cycle_vie import instantane_de_geste
        instantane_de_geste(serializer.instance, user=self.request.user)
        # VX98 — dernier auteur de modification (server-side, jamais du corps) :
        # alimente la puce de fraîcheur. Pattern archived_by.
        serializer.instance.updated_by = self.request.user
        serializer.instance.save(update_fields=['updated_by'])
        # CJ2b — le bloc horaire canonique doit refléter le devis TEL QU'IL EST
        # APRÈS cette écriture (puissance, factures, profil ont pu changer) :
        # sans ce rafraîchissement, un devis résidentiel édité hors auto-devis
        # gardait un bloc PÉRIMÉ ou ABSENT et retombait sur le modèle
        # « facture »/forfait alors qu'un calcul heure par heure exact restait
        # possible. Best-effort, ne lève jamais (voir la docstring de la
        # fonction) : un rafraîchissement raté n'empêche jamais la sauvegarde.
        # ``force`` : une mise à jour de devis peut avoir changé les FACTURES
        # ou le profil dans ``etude_params`` — grandeurs invisibles depuis les
        # lignes, donc le court-circuit « composition inchangée » ne s'applique
        # pas ici.
        #
        # QJR94 (M5, bascule 2/5) — LES QUATRE ÉTUDES, PLUS DEUX.
        # Ce chemin n'appelait QUE deux des quatre rafraîchisseurs (le bloc
        # horaire et le dimensionnement), ce qui DÉFAISAIT la façade « les
        # quatre études en un seul geste » (L-1V) que les trois autres chemins
        # d'écriture respectent : après tout PATCH touchant ``etude_params``,
        # les PROFILS COMPARATIFS et la CONCEPTION ÉLECTRIQUE restaient ceux
        # d'avant. La conception électrique, seule des quatre à n'être jamais
        # recalculée à la lecture, PERSISTAIT alors un schéma unifilaire
        # décrivant une composition que le devis ne vend plus — et c'est ce
        # schéma-là que le client voit sur sa page proposition.
        # CHANGEMENT DE COMPORTEMENT ASSUMÉ (R4-C.5), porté au DONE LOG.
        # ``force=True`` est CONSERVÉ, et vaut désormais pour les quatre : la
        # raison qui l'imposait aux deux premiers (un PATCH change des
        # grandeurs qu'aucune lecture de lignes ne voit) vaut à l'identique
        # pour les deux autres.
        appliquer(serializer.instance, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR,
            company=company, force_etudes=True))
        fin_de_geste_devis(serializer.instance, self.request.user,
                           avant=avant_geste, objet='en-tête')
        # QJR545 — les écritures de fin de geste passent en ``update_fields`` :
        # le jeton servi par la réponse est réaligné sur la base.
        from ..domain.verrou_devis import toucher
        toucher(serializer.instance)

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
