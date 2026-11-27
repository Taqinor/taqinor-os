import functools  # AGQ23 — enveloppe d'idempotence d'une action

from drf_spectacular.utils import extend_schema_view
from ..openapi_params import (
    ENTITE, choix_requete, entier_requete, qint, qstr,
)
from drf_spectacular.utils import extend_schema
from . import openapi_docs as D
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.parsers import JSONParser
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..models import Devis
from ..serializers import (
    DevisListeSerializer,
    DevisSerializer,
    DevisWriteSerializer,
)
from ..selectors_listes import (  # T4-X4-005 — liste paginée par le serveur
    STATUTS_EFFECTIFS, filtrer_liste_devis, synthese_liste_devis,
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
    DroitDeLaGrille, droits_de_la_grille, is_portal_user, portal_scope_id,
)
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..gardes_lecture import LectureVentes  # ADVS23
from core.pagination import OrdreTotalMixin  # ERR-FACTURES-LISTE-ORDRE-INSTABLE
# AUD403 — brique UNIQUE du dépôt pour qu'un ``get_permissions()`` par action
# ne jette pas en silence la garde qu'une ``@action`` déclare elle-même.
from core.permissions import declared_action_permissions
# PV84 — builder UNIQUE du chemin proposition (nom-client inclus dans l'URL) ;
# jamais de f'/proposition/{token}' en dur ailleurs dans ce fichier.
from ..utils.client_links import chemin_proposition
from core.entite_scoping import EntiteScopeMixin  # NTADM2
from core.idempotency import IdempotentCreateMixin  # YAPIC9
from ..utils.company_settings import create_numbered
from .devis_edition import DevisEditionActionsMixin  # SPL135
from .devis_cycle import DevisCycleActionsMixin  # SPL136
from .devis_etudes import DevisEtudesActionsMixin  # SPL137
from .devis_envoi import DevisEnvoiActionsMixin  # SPL138
from .devis_pdf import DevisPdfActionsMixin  # SPL139
from .devis_calepinage import DevisCalepinageActionsMixin  # SPL140
from .devis_facturation import DevisFacturationActionsMixin  # SPL141
from .devis_cadence import DevisCadenceActionsMixin  # SPL142
from .assistant import DevisAssistantActionsMixin  # copilote vague 2 (VAD)
from authentication.scoping import visible_user_ids
import logging

logger = logging.getLogger(__name__)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


CONCEVABLE = ['1', 'true']
#: T4-X4-005 — ``?forme=complete`` : la forme COMPLÈTE en liste (lignes,
#: étude, calepinage), demandée par le seul dialogue « Signé » d'un lead.
FORMES_LISTE = ['complete']
ACTIFS = ['1']
#: T4-X4-005 — paramètres de la liste paginée par le serveur (DevisList.jsx).
PARAMS_LISTE = [
    qstr('forme', enum=FORMES_LISTE,
         desc="« complete » : lignes, étude et calepinage dans chaque ligne "
              "(par défaut, la forme légère de la liste)."),
    qstr('q', desc='Recherche dans la référence ou le nom du client.'),
    qstr('statut_effectif', enum=list(STATUTS_EFFECTIFS),
         desc="Statut affiché (un devis en attente dont la validité est "
              "passée se lit « expire »)."),
    qstr('actifs', enum=ACTIFS, desc='« 1 » : masque les versions remplacées.'),
    qstr('auteurs', desc="Identifiants des auteurs, séparés par des virgules."),
]


def _auteurs_requete(request):
    """``?auteurs=1,2,3`` → liste d'entiers ; vide → ``None`` ; autre → 400."""
    from rest_framework.exceptions import ValidationError
    brut = (request.query_params.get('auteurs') or '').strip()
    if not brut:
        return None
    morceaux = [m.strip() for m in brut.split(',') if m.strip()]
    if len(morceaux) > 500 or not all(m.isdigit() for m in morceaux):
        raise ValidationError({'auteurs': [
            "« auteurs » attend des identifiants séparés par des virgules."]})
    return [int(m) for m in morceaux]


def _resume_devis_auto(devis):
    """ALEA51 — le RETOUR du devis automatique pour la bannière de succès :
    ``total_ttc``, ``economie_an_1_ht``, ``retour_ans`` (``None`` quand
    l'investissement est incomplet ou sans étude C&I) et ``postes_apres_visite``
    (désignations « à chiffrer après la visite »). Tout est LU du devis créé
    (``etude_params.etude_ci`` stocké ; la valorisation et le retour sont ceux
    que lit déjà le document, ``economie_ci_pour_devis``) : rien n'est
    recalculé ici et aucun statut n'est touché. Jamais bloquant."""
    total = devis.total_ttc
    resume = {'total_ttc': float(total) if total is not None else None,
              'economie_an_1_ht': None, 'retour_ans': None,
              'economie_an_1_ht_avec': None, 'retour_ans_avec': None, 'kwc_avec': None,
              'postes_apres_visite': []}
    etude = (devis.etude_params or {}).get('etude_ci')
    if not isinstance(etude, dict):
        return resume
    # Fondateur 17/11/2026 — un devis à deux options DIT les deux : l'économie
    # et le retour de l'option « avec batterie » sont ceux que l'étude a
    # stockés (``option_avec``, les mêmes que lit le PDF), jamais recalculés.
    avec = etude.get('option_avec')
    if isinstance(avec, dict) and (avec.get('economie_annuelle_mad') or 0) > 0:
        resume.update(economie_an_1_ht_avec=avec.get('economie_annuelle_mad'),
                      retour_ans_avec=avec.get('retour_simple_ans'), kwc_avec=avec.get('kwc'))
    composition = etude.get('composition') or {}
    resume['postes_apres_visite'] = list(composition.get('a_chiffrer_visite') or [])
    try:
        from ..economie_ci import economie_ci_pour_devis
        bloc = economie_ci_pour_devis(devis, devis.company) or {}
        resume['economie_an_1_ht'] = (bloc.get('economie_annee1') or {}).get('total_mad')
        resume['retour_ans'] = (bloc.get('indicateurs') or {}).get('retour_ans')
        # CE2E3 — le retour au dixième que le PDF imprime (CPDF7), même calcul.
        from ..domain.regles_calcul import REGLES_CORRIGEES_2710, regles_au_moins
        from ..quote_engine.ci.couverture import retour_dixieme
        if regles_au_moins(devis, REGLES_CORRIGEES_2710):
            resume['retour_ans'] = retour_dixieme(bloc, resume['retour_ans'])
    except Exception:  # lecture seule : la bannière se passe de ces chiffres
        logger.warning('devis/auto : résumé économique indisponible (dégradé)',
                       exc_info=True)
    return resume


def _option_unique(devis, decide_par_la_requete=False):
    """T4-V2-013/015 — un devis à UNE option (scénario mono déclaré) :
    ``{batterie, souhait_fiche}`` = l'option porte-t-elle la batterie, et
    est-ce le souhait « batterie » de la fiche du lead qui l'a décidé ;
    ``None`` sur un devis à deux options (``options`` les nomme). Lecture pure.
    Relecture m2 — ``souhait_fiche`` est faux quand la REQUÊTE a imposé
    l'option (``scenario`` ou composition imposée), même si la fiche dit pareil."""
    from ..utils.options import (
        AVEC_BATTERIE, deux_options_declarees, option_du_scenario_mono,
        scenario_declare)
    if deux_options_declarees(devis):
        return None
    option = option_du_scenario_mono(scenario_declare(devis))
    if not option:
        return None
    batterie = option == AVEC_BATTERIE
    souhait = (getattr(devis.lead, 'batterie_souhaitee', '') or '').strip() if devis.lead_id else ''
    return {'batterie': batterie,
            'souhait_fiche': not decide_par_la_requete
            and souhait == ('avec' if batterie else 'sans')}


def _reponse_devis_auto(devis, alertes, decide_par_la_requete=False):
    """COP2-V3 — LA réponse de ``POST devis/auto/`` (création 201 ET rejeu
    d'idempotence 200) : la bannière (ALEA51) + la carte ``devis_cree`` de
    l'assistant — ``devis_id`` (alias de ``id``), ``lead_id`` et
    ``composition`` (lignes TTC du devis créé, jamais un prix d'achat).
    Contrat : ``contract_samples/assistant_devis_cree.json``."""
    from ..models import ShareLink
    from ..domain.composition_imposee import lignes_ttc
    from ..selectors_assistant import options_du_devis
    link = ShareLink.for_devis(devis)
    resume = _resume_devis_auto(devis)
    return {
        'id': devis.id,
        'devis_id': devis.id,
        'lead_id': devis.lead_id,
        'reference': devis.reference,
        'statut': devis.statut,
        'kwc': (devis.etude_params or {}).get('puissance_kwc'),
        'nb_lignes': devis.lignes.count(),
        'proposal_token': link.token,
        'proposal_path': chemin_proposition(devis, link.token),
        'alertes': list(alertes or []),
        'total_ttc': resume['total_ttc'],
        'economie_an_1_ht': resume['economie_an_1_ht'],
        'retour_ans': resume['retour_ans'],
        'economie_an_1_ht_avec': resume['economie_an_1_ht_avec'],
        'retour_ans_avec': resume['retour_ans_avec'],
        'kwc_avec': resume['kwc_avec'],
        'postes_apres_visite': resume['postes_apres_visite'],
        'composition': lignes_ttc(devis),
        # 20/11/2026 (DEV-202611-0090) — chaque option avec SES chiffres :
        # ``total_ttc`` (gardé) ne dit pas à quelle option il correspond.
        'options': options_du_devis(devis),
        # T4-V2-015 — l'option unique et sa raison (souhait de la fiche).
        'option_unique': _option_unique(devis, decide_par_la_requete),
    }


def _idempotente(suffixe):
    """AGQ23 (C-AGQ-022) — pose le contrat ``Idempotency-Key`` de
    ``core.idempotency`` (``IdempotentCreateMixin._avec_idempotence``, LA
    primitive, aucune seconde garde) autour d'une ACTION de création, sans
    toucher son corps (sa forme servie reste lisible par
    ``scripts/check_api_shapes.py``). Sans en-tête : appel inchangé."""
    def decorer(vue):
        @functools.wraps(vue)
        def enveloppe(self, request, *args, **kwargs):
            return self._avec_idempotence(
                request, lambda: vue(self, request, *args, **kwargs),
                suffixe=suffixe)
        return enveloppe
    return decorer


@extend_schema_view(list=extend_schema(parameters=[
    qint('lead'), qstr('concevable', enum=CONCEVABLE),
    qstr('statut', enum=Devis.Statut.values), ENTITE, *PARAMS_LISTE],
    responses=D.LignesDeListeDevis),
    create=extend_schema(extensions=D.CORPS_LEAD_OU_CLIENT))
class DevisViewSet(OrdreTotalMixin, DevisEditionActionsMixin,
                   DevisCycleActionsMixin,
                   DevisEtudesActionsMixin,
                   DevisEnvoiActionsMixin,
                   DevisPdfActionsMixin,
                   DevisCalepinageActionsMixin,
                   DevisFacturationActionsMixin,
                   DevisCadenceActionsMixin,
                   DevisAssistantActionsMixin,
                   IdempotentCreateMixin, EntiteScopeMixin,
                   CompanyScopedModelViewSet):
    # ENF17 / api-fuzz-full — ``DevisWriteSerializer`` porte ``IdInconnu404Mixin``
    # (``client``/``lead`` inconnus = 404) : ``entite`` répond pareil.
    entite_inconnue_404 = True
    parser_classes = [JSONParser]  # ENF11/D2 : aucun envoi de fichier
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
        # APRF4 (C-APRF-002) — `updated_by_nom` et la société (profil,
        # validité) lus PAR LIGNE de liste : un SELECT par devis sans eux.
        'updated_by', 'company',
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
        # APRF4 — la fiche technique de chaque produit (moteur d'affichage),
        # et ce que `solde_devis` lit par facture : affectations de paiement
        # (patron AUD157 de FactureViewSet), lignes de facture et d'avoir
        # (totaux non figés). Sans eux : une requête par facture active.
        'lignes__produit__fiche_technique',
        'factures', 'factures__paiements', 'factures__avoirs',
        'factures__affectations_paiement__paiement', 'factures__lignes',
        'factures__avoirs__lignes',
        # CI #890 — ``Facture.montant_du`` (lu par ``solde_devis``) passe par
        # ``decomposition_du`` (AFAC31) qui lit AUSSI ``notes_debit_total``
        # et ``retenues_subies_total`` : sans ces prefetch, DEUX SELECT par
        # facture active (``ventes_notedebit`` + ``ventes_retenuesubie``
        # WHERE facture_id = …) — N+1 sur chaque devis facturé de la liste.
        'factures__notes_debit', 'factures__notes_debit__lignes',
        'factures__retenues_subies', 'factures__retenues_subies__paiement',
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
        # CI #997 (2) — chaque paramètre publié est lu STRICTEMENT (400 nommé
        # hors type / hors énumération, jamais ignoré ni 500 au filtre).
        lead_id = entier_requete(self.request, 'lead')
        if lead_id is not None:
            qs = qs.filter(lead_id=lead_id)
        # QJR636 — ?concevable=1 : les devis dont la toiture se calepine
        # encore (choix « Conception 3D »), APRÈS les portées ci-dessus.
        if choix_requete(self.request, 'concevable', CONCEVABLE):
            from ..selectors import devis_concevables
            qs = devis_concevables(qs)
        # ?statut= (consolidation de factures : devis ACCEPTÉS) était publié
        # mais ignoré — la liste rendait tous les statuts.
        statut = choix_requete(self.request, 'statut', Devis.Statut.values)
        return qs.filter(statut=statut) if statut else qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DevisWriteSerializer
        # T4-X4-005 — la LISTE sert la forme légère, sauf ``?forme=complete``.
        if self.action == 'list' and not choix_requete(
                self.request, 'forme', FORMES_LISTE):
            return DevisListeSerializer
        return DevisSerializer

    def filter_queryset(self, queryset):
        """T4-X4-005 — recherche, statut effectif, versions remplacées et
        auteurs appliqués par le SERVEUR, sur la LISTE seule (les autres
        actions gardent leur portée inchangée)."""
        queryset = super().filter_queryset(queryset)
        if self.action != 'list':
            return queryset
        q = (self.request.query_params.get('q') or '').strip()[:100]
        return filtrer_liste_devis(
            queryset, getattr(self.request.user, 'company', None), q=q,
            statut_effectif=choix_requete(
                self.request, 'statut_effectif', list(STATUTS_EFFECTIFS)),
            actifs=bool(choix_requete(self.request, 'actifs', ACTIFS)),
            auteurs=_auteurs_requete(self.request))

    @extend_schema(responses=D.DevisSyntheseResponse)
    @action(pagination_class=None, detail=False, methods=['get'],
            url_path='synthese', permission_classes=[LectureVentes])
    def synthese(self, request):
        """T4-X4-005 — l'en-tête de la liste des devis (cartes par statut,
        devis à relancer, option batterie, versions remplacées, nombre total)
        calculé sur TOUTE la portée du rôle, puisque l'écran ne charge plus
        qu'une page. Contrat : ``contract_samples/devis_synthese.json``."""
        donnees = synthese_liste_devis(
            self.get_queryset(), getattr(request.user, 'company', None))
        return Response({
            'total': donnees['total'],
            'remplaces': donnees['remplaces'],
            'par_statut': donnees['par_statut'],
            'a_relancer': donnees['a_relancer'],
            'batterie': donnees['batterie'],
        })

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
        if self.action in ('list', 'retrieve'):
            # ADVS23 — bornée aux rôles du module Ventes, comme les factures.
            return [LectureVentes()]
        if self.action == 'variante_config':
            # La LECTURE est ouverte à tous ; l'ÉCRITURE (PUT) est re-vérifiée
            # DANS l'action.
            return [IsAnyRole()]
        if self.action in ('create', 'update', 'partial_update'):
            # ASEC71/ASEC74 — modifier / créer un devis exige ``ventes_modifier``
            # / ``ventes_creer`` (grille).
            modifier = [DroitDeLaGrille('ventes_modifier')]
            return [IsResponsableOrAdmin()] + droits_de_la_grille(
                self, update=modifier, partial_update=modifier,
                create=[DroitDeLaGrille('ventes_creer')])
        if self.action == 'destroy':
            # ASEC50 / D-ASEC-4 — supprimer un devis exige ``ventes_supprimer``
            # en plus du palier administrateur.
            return [IsAdminRole(), DroitDeLaGrille('ventes_supprimer')()]
        # toute future action non déclarée : fermé par défaut.
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        """QJR639 (D-QJR5-2) — un devis ACCEPTÉ ne se supprime pas : le DELETE
        effaçait en cascade sa signature électronique (DevisSignature), son
        lien client (ShareLink), ses lignes et son chatter, et orphelinait son
        BC. 409 sans rien effacer ; seule la révision reste ouverte (ASUP54 :
        la désactivation d'un accepté est refusée). Le statut est LU, jamais écrit (règle #4).

        QJR661 (décision fondateur 01/10 — archivage seul) : SEUL un brouillon
        se supprime. Un envoyé / refusé / expiré a un lien client (ShareLink)
        et un historique qui partiraient en cascade : même 409 « archivez-le »."""
        devis = self.get_object()
        if devis.statut == Devis.Statut.ACCEPTE:
            return Response(
                {'detail': 'Devis accepté : il ne se supprime pas — '
                           'révisez-le.'},  # ASUP54 — ne se désactive pas
                status=status.HTTP_409_CONFLICT)
        if devis.statut != Devis.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un brouillon se supprime : '
                           'archivez-le (désactivation) ou révisez-le.'},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """VNT55 (D-ADEV-1) — supprimer le brouillon de révision V2 réactive
        sa V1 (ADEV16 : quel qu'en soit le statut), dans la même transaction
        (le lien ``superseded_by`` est lu AVANT la suppression)."""
        from django.db import transaction
        from ..domain.revision import abandonner_revision
        with transaction.atomic():
            abandonner_revision(instance, self.request.user, retrait=True)
            super().perform_destroy(instance)

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
        if 'taux_tva' not in serializer.validated_data:
            # APAR81 (D-APAR-1) — le taux standard de la société, comme la devise.
            from ..utils.company_settings import tva_standard
            save_kwargs['taux_tva'] = tva_standard(company)

        # QJR541 — ``statut`` n'est plus écrivable : un devis créé par POST
        # est toujours un brouillon, le funnel n'avance que par les
        # événements devis_sent / devis_accepted (crm/receivers.py).
        create_numbered(
            Devis, company, 'devis',
            lambda ref: serializer.save(reference=ref, **save_kwargs),
        )

    @extend_schema(request=D.CompositionRequest,
                   responses={200: D.CompositionResponse,
                              409: D.ErreurComposition},
                   extensions=D.CORPS_KWC_OU_PANNEAUX)
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
        from decimal import Decimal
        from ..services import composer_devis_residentiel, AutoDevisError

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        # CI #997 fuzz — le corps est validé par le schéma PUBLIÉ lui-même
        # (``D.CompositionRequest``) : nombres JSON (plus ``"5"`` relu par
        # ``Decimal``), bornes, scénario énuméré, drapeau booléen strict,
        # ``dimensionnement_avec`` objet de nombres — un écart = 400 nommé.
        from ..utils.corps import valider_corps_schema
        corps = valider_corps_schema(request, D.CompositionRequest)

        def _nombre(cle, defaut=None):
            return (Decimal(str(corps[cle])) if corps.get(cle) is not None
                    else defaut)

        kwc = _nombre('kwc')
        nb_panneaux = _nombre('nb_panneaux', Decimal('0'))
        # D-ACAL-169 — sans puissance tapée : celle du panneau par défaut que la
        # composition accepte (et CE produit), sinon le 710 Wc d'aujourd'hui.
        from ..domain.panneau_defaut import panneau_auto_composition
        auto = panneau_auto_composition(company)
        panel_watt = _nombre('panel_watt', Decimal(str(auto.watt)))
        # APAR49 — défaut = taux STANDARD de la société, jamais 20 codé.
        from ..utils.company_settings import tva_standard
        taux_tva = _nombre('taux_tva', tva_standard(company))
        mppt_paires = _nombre('mppt_paires', Decimal('1'))
        # U3COMPOSE — ``{'nb_panneaux'?, 'kwc'?, 'batterie_kwh'?}`` en float
        # (vide = moteur muet sur l'axe batterie).
        dimensionnement_avec = {
            cle: float(valeur) for cle, valeur in (
                corps.get('dimensionnement_avec') or {}).items()
            if cle in ('nb_panneaux', 'kwc', 'batterie_kwh')} or None

        structure = corps.get('structure_type') or 'acier'
        # STKCAT1/STKCAT7 — l'id du produit de structure CHOISI ; le scoping
        # société est celui du CATALOGUE, posé côté composition (un id d'une
        # autre société n'y résout simplement rien).
        structure_produit_id = corps.get('structure_produit_id')
        structure_produit_id = (int(structure_produit_id)
                                if structure_produit_id is not None else None)
        # QJR-OFFGRID — drapeau ADDITIF et optionnel : le site est ISOLÉ
        # (onduleur autonome + batterie, option unique). Absent ⇒ dry-run
        # strictement inchangé. Cet endpoint n'a AUCUN lead en portée (il est
        # piloté par les nombres tapés à l'écran) : le repli « raccordement du
        # lead = aucun » vit là où le lead existe, dans ``build_devis_auto``.
        hors_reseau = bool(corps.get('hors_reseau'))
        # QJR604 — la ville du barème transport vient d'un LEAD de la société
        # (404 sinon), résolue côté serveur ; plus jamais d'un texte libre.
        ville = ''
        if corps.get('lead') is not None:
            from apps.crm.selectors import leads_visibles
            from ..domain.transport import ville_du_lead
            # ADVS24 — borné à la portée du rôle, pas à la seule société.
            lead_obj = leads_visibles(request.user, company).filter(
                pk=int(corps['lead'])).first()
            if lead_obj is None:
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
            ville = ville_du_lead(lead_obj)
        else:
            lead_obj = None
        # COP2-V3 — composition IMPOSÉE : même résolution et mêmes contrôles
        # que ``POST devis/auto/`` (règle U3), rien n'est écrit.
        from ..domain.composition_imposee import (
            imposition_du_corps, preparer_imposition)
        # ``nb_panneaux`` seul reste l'entrée NON imposée historique du dry-run.
        imposes = imposition_du_corps(corps, nb_panneaux_seul_impose=False)
        impose = {}
        alertes_imposees = []
        try:
            if imposes:
                if corps.get('kwc') is not None:
                    raise AutoDevisError(
                        'Composition imposée : la puissance (kwc) ne se '
                        'combine pas avec un nombre de panneaux imposé.',
                        field='kwc')
                imposition, alertes_imposees, phase, hors_reseau = (
                    preparer_imposition(
                        company=company, lead=lead_obj, imposes=imposes,
                        scenario=corps.get('scenario'), user=request.user,
                        hors_reseau=hors_reseau))
                nb_panneaux = Decimal(imposition.nb_panneaux)
                panel_watt = Decimal(str(imposition.panel_watt))
                impose = {
                    'scenario': imposition.scenario, 'phase': phase,
                    'modeles': [{'produit_id': imposition.panneau_id,
                                 'watt': imposition.panel_watt,
                                 'count': imposition.nb_panneaux}],
                    'onduleur_impose': imposition.onduleur_impose,
                    'batterie_imposee': imposition.batterie_imposee}
            resultat = composer_devis_residentiel(
                company=company,
                kwc=float(kwc) if kwc is not None else 0,
                nb_panneaux=int(nb_panneaux),
                panel_watt=float(panel_watt),
                scenario=impose.pop('scenario', corps.get('scenario')),
                structure_type=str(structure),
                structure_produit_id=structure_produit_id,
                taux_tva=taux_tva,
                mppt_paires=int(mppt_paires),
                dimensionnement_avec=dimensionnement_avec,
                hors_reseau=hors_reseau,
                ville=ville,
                panneau_prefere_id=None if impose else auto.prefere(panel_watt),
                **impose,
            )
        except AutoDevisError as exc:
            # CI #1003 fuzz — corps conforme au schéma : catalogue ou réglage
            # de la société qui s'y oppose (aucun onduleur autonome tarifé,
            # marque épinglée absente…) = refus d'ÉTAT, 409 — comme
            # ``/devis/auto/`` ; le message FRANÇAIS reste lu tel quel.
            # COP2-V3 — ``choix`` quand un élément imposé est ambigu.
            refus = {'detail': exc.message, 'field': exc.field}
            if getattr(exc, 'choix', None) is not None:
                refus['choix'] = exc.choix
            return Response(refus, status=status.HTTP_409_CONFLICT)
        # D-ACAL-169 — le motif (désigné mais inutilisable) n'est dit que si la
        # puissance n'a pas été tapée ; la clé ``panneau_par_defaut`` sert l'écran.
        for alerte in alertes_imposees:
            resultat['avertissements'].append(alerte['message'])
        if auto.motif and corps.get('panel_watt') is None and not impose:
            resultat['avertissements'].append(auto.motif)
        return Response(dict(resultat, panneau_par_defaut=auto.resume()), status=status.HTTP_200_OK)

    @extend_schema(request=D.AutoDevisRequest,
                   responses={201: D.AutoDevisResponse,
                              200: D.AutoDevisResponse,
                              409: D.ErreurDevisAuto},
                   extensions=D.CORPS_LEAD_OU_CLIENT)
    @action(detail=False, methods=['post'], url_path='auto',  # ASEC87 — grille « Créer »
            permission_classes=[IsResponsableOrAdmin, DroitDeLaGrille('ventes_creer')])
    @_idempotente('auto')  # AGQ23 — rejoue le 1ᵉʳ devis d'une même clé
    def auto(self, request):
        """Copilote — crée un devis automatiquement dimensionné à partir de la
        fiche lead, pour les QUATRE marchés : résidentiel, agricole (pompage,
        AGR124), commercial et industriel (moteur C&I, CIQ120) — JAMAIS un
        brouillon vide. C'est le seul chemin de création de devis offert à
        l'agent.

        Corps : ``{lead}`` (ou ``{client}``, dont on remonte au lead le plus
        récent) + ``taux_tva?`` / ``remise_globale?``. La société est TOUJOURS
        celle du user ; le lead est borné à sa portée (404 sinon). 409 si les
        données de dimensionnement manquent (le refus nomme le champ du lead
        ``field``), si un poste fixe C&I n'a pas de prix (« Prix à renseigner »,
        ALEA50) ou si rien ne se compose — l'agent demande alors la donnée /
        oriente vers le générateur. La réponse porte de quoi dire le succès :
        ``total_ttc``, ``economie_an_1_ht``, ``retour_ans`` (null si
        l'investissement est incomplet) et ``postes_apres_visite`` (ALEA51).
        Aucun statut n'est touché : le service renvoie un brouillon (règle #4).

        AGQ23 (C-AGQ-022) — IDEMPOTENTE (``_idempotente``) : une
        ``Idempotency-Key`` (une par ouverture du panneau lead) rejoue le
        PREMIER devis créé pour cette clé au lieu d'en créer un second (2ᵉ
        clic après un délai dépassé côté écran alors que le serveur a fini la
        création) ; corps différent → 409. Sans en-tête : inchangé."""
        from decimal import Decimal
        from ..services import build_devis_auto, AutoDevisError
        from ..domain.composition_imposee import (
            build_devis_auto_impose, imposition_du_corps)
        from apps.crm.selectors import (
            get_company_client, get_latest_lead_for_client, leads_visibles,
        )

        company = request.user.company
        if company is None:
            return Response(
                {'detail': 'Utilisateur sans société.'},
                status=status.HTTP_400_BAD_REQUEST)

        # CI #997 fuzz — corps validé par le sérialiseur PUBLIÉ (types JSON
        # stricts, pourcentages 0-100 en chaîne ou nombre) : 400 nommé.
        from ..utils.corps import valider_corps
        corps = valider_corps(request, D.AutoDevisRequest)
        lead_obj = None
        lead_id = corps.get('lead')
        client_id = corps.get('client')
        # ADVS24 — portée du rôle : le lead d'un collègue = lead inconnu.
        visibles = leads_visibles(request.user, company)
        if lead_id:
            lead_obj = visibles.filter(pk=lead_id).first()
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
                    # CI #997 fuzz — l'ÉTAT de la fiche s'oppose : 409.
                    status=status.HTTP_409_CONFLICT)
            if not visibles.filter(pk=lead_obj.pk).exists():
                return Response({'detail': 'Lead inconnu.'},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(
                {'detail': 'Un lead (ou un client) est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        # ACAL278 — UNE règle (fini, 0..100, 2 décimales), désormais PUBLIÉE
        # par le sérialiseur (CI #997 fuzz) ; APAR49 — défaut = taux STANDARD
        # de la société (``tva_standard``).
        from ..utils.company_settings import tva_standard
        taux_tva = corps.get('taux_tva')
        if taux_tva is None:
            taux_tva = tva_standard(company)
        remise = corps.get('remise_globale')
        if remise is None:
            remise = Decimal('0')

        # U3 — trois réglages POUR CE DEVIS-LÀ, qui ne réécrivent JAMAIS la
        # fiche du lead : la puissance cible saisie par le commercial (EZ5), le
        # scénario batterie demandé, et les clés d'étude que l'écran a déjà
        # calculées (factures mensuelles réelles du contrat PACT10). La
        # COMPOSITION, elle, est entièrement serveur : l'appelant n'envoie
        # aucune ligne, aucun prix, aucune marque.
        # CI #997 fuzz (24/10) : JSON libre rangé en jsonb -> nul / demi-substituts
        # normalisés (DataError 500 sinon).
        from ..utils.corps import nettoyer_json
        etude_extra = nettoyer_json(corps.get('etude_params'))
        # COP2-V3 — les champs de composition IMPOSÉE présents (corps validé).
        imposes = imposition_du_corps(corps)
        # Relecture m2 — l'option unique a-t-elle été décidée par la REQUÊTE
        # (scénario demandé ou composition imposée) plutôt que par la fiche ?
        par_requete = bool(imposes) or bool(str(corps.get('scenario') or '').strip())
        # AGR124 — le devis automatique AGRICOLE dépose ici ses alertes
        # (étude pompage + articles « prix à renseigner » omis), rendues à
        # l'écran (``alertes``) ; les autres marchés n'y écrivent rien.
        journal = {}

        # ADEV80 (C-ACI-009) — idempotence : deux clics rapides ne créent
        # JAMAIS deux brouillons. (1) REJEU : même utilisateur, même lead,
        # corps identique, < 120 s -> 200 avec le MÊME brouillon (forme du
        # 201). La trace vit dans le cache (clé = hachage du corps canonique,
        # TTL 120 s) : aucune migration. (2) VERROU par lead : ``cache.add``
        # testé ``is False`` UNIQUEMENT — un cache en panne (django_redis
        # fail-soft, NTPLT24) répond ``None`` : pas de verrou, jamais un 409
        # pour tous. Jamais ``select_for_update`` sur le lead.
        import hashlib
        import json
        from django.core.cache import cache
        corps_canonique = json.dumps(
            {k: v for k, v in dict(request.data).items()
             if k not in ('lead', 'client')},
            sort_keys=True, default=str, separators=(',', ':'))
        cle_rejeu = 'devis-auto:replay:%s:%s:%s:%s' % (
            company.id, lead_obj.id, request.user.id,
            hashlib.sha1(corps_canonique.encode('utf-8'), usedforsecurity=False).hexdigest())
        try:
            trace = cache.get(cle_rejeu)
        except Exception:  # cache indisponible : pas de rejeu
            logger.warning('devis/auto : cache indisponible — étape ignorée (mode dégradé)', exc_info=True)
            trace = None
        if isinstance(trace, dict) and trace.get('id'):
            deja = Devis.objects.filter(
                pk=trace['id'], company=company, lead=lead_obj,
                created_by=request.user).first()
            if deja is not None:
                # COP2-V3 — le rejeu porte la MÊME forme que la création
                # (composition, devis_id, lead_id compris).
                return Response(
                    _reponse_devis_auto(deja, trace.get('alertes'), par_requete),
                    status=status.HTTP_200_OK)

        cle_verrou = 'devis-auto:%s:%s' % (company.id, lead_obj.id)
        try:
            pose = cache.add(cle_verrou, 1, 180)
        except Exception:  # cache indisponible : pas de verrou
            logger.warning('devis/auto : cache indisponible — étape ignorée (mode dégradé)', exc_info=True)
            pose = None
        if pose is False:
            return Response(
                {'detail': 'Un devis automatique est déjà en cours pour '
                           'ce lead.'},
                status=status.HTTP_409_CONFLICT)
        try:
            if imposes:
                # COP2-V3 — composition IMPOSÉE (résidentiel) : champs lus du
                # corps VALIDÉ, résolus par le résolveur catalogue unique.
                devis = build_devis_auto_impose(
                    lead=lead_obj, user=request.user, company=company,
                    imposes=imposes, taux_tva=taux_tva,
                    remise_globale=remise, scenario=corps.get('scenario'),
                    target_kwc=corps.get('target_kwc'),
                    etude_extra=etude_extra, journal_auto=journal)
            else:
                devis = build_devis_auto(
                    lead=lead_obj, user=request.user, company=company,
                    taux_tva=taux_tva, remise_globale=remise,
                    target_kwc=request.data.get('target_kwc'),
                    scenario=request.data.get('scenario'),
                    etude_extra=etude_extra, journal_auto=journal)
        except AutoDevisError as exc:
            # CI #997 fuzz — corps valide : donnée de la fiche manquante,
            # marché ou catalogue qui s'y oppose = refus d'ÉTAT, 409 (le
            # message FRANÇAIS du serveur reste lu tel quel par les écrans).
            # COP2-V3 — un élément imposé à zéro ou plusieurs candidats porte
            # ``choix`` (les produits nommés) : le serveur ne choisit jamais.
            refus = {'detail': exc.message, 'field': exc.field}
            if getattr(exc, 'choix', None) is not None:
                refus['choix'] = exc.choix
            return Response(refus, status=status.HTTP_409_CONFLICT)
        finally:
            if pose is True:
                try:
                    cache.delete(cle_verrou)
                except Exception:
                    logger.warning('devis/auto : cache indisponible — étape ignorée (mode dégradé)', exc_info=True)

        alertes = list(journal.get('alertes') or [])
        try:
            cache.set(cle_rejeu, {'id': devis.id, 'alertes': alertes}, 120)
        except Exception:
            logger.warning('devis/auto : cache indisponible — étape ignorée (mode dégradé)', exc_info=True)
        return Response(_reponse_devis_auto(devis, alertes, par_requete),
                        status=status.HTTP_201_CREATED)

    # api-only: lue par l'assistant (action `ventes.devis.lignes`), aucun écran ne l'appelle.
    @extend_schema(request=None,
                   responses={200: D.LignesAssistantResponse,
                              404: D.ErreurDetail})
    @action(detail=True, methods=['get'], url_path='lignes-assistant',
            permission_classes=[LectureVentes])
    def lignes_assistant(self, request, pk=None):
        """COP2-V5 — les lignes d'UN devis pour l'assistant : ``ligne_id`` (que
        ``ventes.devis.ligne_modifier`` / ``ligne_supprimer`` demandent),
        ``produit_id``, quantité et prix TTC. Portée = ``get_object`` (société
        + visibilité du rôle, celle de la liste). Jamais de prix d'achat ni de
        marge. Contrat : ``contract_samples/assistant_devis_lignes.json``."""
        from decimal import Decimal
        from ..domain.composition_imposee import lignes_ttc
        from ..selectors_assistant import options_du_devis
        devis = self.get_object()
        total = devis.total_ttc
        return Response({
            'devis_id': devis.id,
            'reference': devis.reference,
            'statut': devis.statut,
            'total_ttc': (str(Decimal(total).quantize(Decimal('0.01')))
                          if total is not None else None),
            'lignes': lignes_ttc(devis, avec_ids=True),
            # D-COP-5 — « le total option par option » : même calcul que les
            # réponses de devis/auto et des gestes de lignes.
            'options': options_du_devis(devis),
        })

    @extend_schema(methods=['GET'], responses=D.VarianteConfigResponse)
    @extend_schema(methods=['PUT'], request=D.VarianteConfigRequest,
                   responses={200: D.VarianteConfigResponse,
                              400: D.ErreurDetail, 403: D.ErreurDetail})
    @action(detail=False, methods=['get', 'put'], url_path='variante-config')
    def variante_config(self, request):
        """QG9 — Lit (GET) ou règle (PUT) le pourcentage des variantes de devis.

        Le pourcentage vit sur ``CompanyProfile.variante_pct`` (défaut 20),
        scopé à la société de l'utilisateur (jamais lu du corps). La LECTURE est
        ouverte à tous les rôles ; l'ÉCRITURE exige ``parametres_modifier``
        (ADRG11, 403 sinon). Corps PUT : ``variante_pct`` (0–100,
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

        # PUT — ADRG11 (D-ADRG-5) : réglage société, droit ``parametres_modifier``
        # (jamais un nom de rôle codé en dur).
        user = request.user
        if not HasPermissionOrLegacy('parametres_modifier')().has_permission(request, self):
            return Response(
                {'detail': 'Droit « Modifier les paramètres » requis pour ce pourcentage.'},
                status=status.HTTP_403_FORBIDDEN)
        from decimal import Decimal, InvalidOperation
        # ENF11 — corps non objet (null, liste, texte) : 400 qui nomme le champ.
        if not isinstance(request.data, dict):
            return Response(
                {'detail': 'variante_pct : corps JSON objet attendu.'},
                status=status.HTTP_400_BAD_REQUEST)
        raw = request.data.get('variante_pct')
        try:
            pct = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            pct = None
        # ENF11 — NaN passait ``Decimal(...)`` puis levait InvalidOperation à
        # la comparaison ci-dessous (500) : non fini = invalide.
        if pct is None or not pct.is_finite():
            return Response(
                {'detail': 'variante_pct invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not (Decimal('0') < pct < Decimal('100')):
            return Response(
                {'detail': 'Le pourcentage doit être strictement entre 0 et 100.'},
                status=status.HTTP_400_BAD_REQUEST)
        if pct != pct.quantize(Decimal('0.01')):
            return Response(
                {'detail': 'variante_pct : deux décimales au plus.'},
                status=status.HTTP_400_BAD_REQUEST)
        ancien = profile.variante_pct
        profile.variante_pct = pct
        profile.save(update_fields=['variante_pct'])
        # APAR60 (C-APAR-039) — journal avant/après, comme l'écran Profil
        # (même champ, même libellé, section « profil »).
        from apps.parametres.models import SettingsAuditLog
        if ancien != profile.variante_pct:
            SettingsAuditLog.log_change(
                company, user, 'profil', 'variante_pct',
                'Pourcentage des variantes de devis', ancien,
                profile.variante_pct)
        return Response({'variante_pct': str(profile.variante_pct)})

    @extend_schema(request=None, responses=D.RevoquerLienPublicResponse)
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

    @extend_schema(
        parameters=[OpenApiParameter('client', OpenApiTypes.INT, required=True)],
        responses=D.PrefillSiteResponse)
    @action(detail=False, methods=['get'], url_path='prefill-site',
            permission_classes=[LectureVentes])
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
