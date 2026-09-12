"""Vues de la Paie marocaine (toutes scopées société, admin-gated).

La paie est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur.
"""
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import (
    FormParser, JSONParser, MultiPartParser,
)
from rest_framework.response import Response

from . import builders
from . import selectors as paie_selectors

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import (
    AdhesionMutuelle,
    AvanceSalarie,
    BaremeIR,
    BulletinPaie,
    CumulAnnuel,
    EcheanceDeclarative,
    ElementVariable,
    LigneVirement,
    OrdreVirement,
    ParametrePaie,
    PaysPaie,
    PeriodePaie,
    ProfilPaie,
    RegimeMutuelle,
    Rubrique,
    RubriqueEmploye,
    SaisieArret,
    SchemaComptablePaie,
    StructurePaie,
    ProvisionPaieMensuelle,
    TypeEntreePonctuelle,
)
from .serializers import (
    AdhesionMutuelleSerializer,
    AvanceSalarieSerializer,
    BaremeIRSerializer,
    BulletinPaieSerializer,
    CumulAnnuelSerializer,
    DepotDeclaratifSerializer,
    EcheanceDeclarativeSerializer,
    ElementVariableSerializer,
    LigneVirementSerializer,
    ParametrePaieSerializer,
    PaysPaieSerializer,
    PeriodePaieSerializer,
    OrdreVirementSerializer,
    ProfilPaieSerializer,
    RegimeMutuelleSerializer,
    RubriqueEmployeSerializer,
    RubriqueSerializer,
    SaisieArretSerializer,
    SchemaComptablePaieSerializer,
    StructurePaieSerializer,
    TypeEntreePonctuelleSerializer,
)
from .services import (
    TransitionPeriodeInterdite,
    annuler_saisie_arret,
    appliquer_rappel_retroactif,
    appliquer_regularisation_ir,
    appliquer_structure_a_profil,
    attestation_salaire_ij_cnss,
    bareme_en_vigueur,
    bordereau_paiement_cnss,
    brut_pour_net_cible,
    avertissements_parametre_paie,
    avertissements_periode,
    calculer_bulletin,
    changer_statut,
    checklist_cloture,
    cloturer_periode_paie,
    commit_reprise_cumuls,
    controle_completude,
    controle_ecarts,
    cout_employeur,
    cout_global_par_profil,
    creer_bulletin_annulation,
    creer_bulletin_rectificatif,
    creer_saisies_arret_lot,
    declaration_cimr,
    declaration_cnss,
    detecter_periodes_impactees,
    deposer_bds_complementaire,
    deposer_bds_principal,
    dry_run_reprise_cumuls,
    emettre_ordre_virement,
    enregistrer_depot_declaratif,
    ensure_defaults,
    ensure_pays_paie_standard,
    ensure_types_entree_ponctuelle_standard,
    ensure_rubriques_defaut,
    ensure_rubriques_standard,
    ensure_schema_comptable_standard,
    ensure_structures_standard,
    etat_charges as etat_charges_detaille,
    etat_des_charges,
    expirer_regimes_echus,
    etat_ir_9421,
    etat_ir_9421_annuel,
    export_xml_simpl_ir_9421,
    fichier_cimr,
    fichier_damancom_cnss,
    fichier_damancom_strict,
    fichier_telepaiement_cnss,
    fichier_virement_paie,
    fichier_virement_paie_simt,
    generer_bulletin,
    generer_bulletin_stc,
    generer_echeances_periode,
    generer_ordre_virement,
    generer_run_gratification,
    historique_carriere,
    importer_avantages_nature_flotte,
    importer_elements_rh,
    journal_de_paie,
    journal_de_paie_ventile,
    livre_de_paie,
    marquer_bulletin_lu,
    marquer_bulletin_paye,
    mouvements_cnss_periode,
    notifier_echeances_en_retard,
    parametre_en_vigueur,
    payer_ordre_virement,
    payer_organismes,
    profils_hors_virement,
    rapprochement_paie_gl,
    rapprocher_affebds,
    rattacher_bulletins,
    recalculer_cumul_annuel,
    reemettre_ligne_virement,
    registre_conges,
    reinitialiser_schema_comptable,
    reporter_elements_periode,
    rejeter_ligne_virement,
    saisies_arret_du_bulletin,
    simuler_bulletin,
    simuler_cout_embauche,
    synchroniser_salaire,
    valider_bulletin,
    verifier_cloture_autorisee,
)


def _pdf_response(pdf_bytes, filename):
    """Réponse HTTP de téléchargement PDF (pièce jointe)."""
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


class _PaieVoirOuGerer:
    """XPAI7 — ``paie_voir``/``paie_gerer`` selon la méthode HTTP (fine-grained).

    Un compte AVEC rôle fin est jugé par ``has_erp_permission`` : lecture
    (``GET``/``HEAD``/``OPTIONS``, y compris les actions custom en ``GET``
    comme ``bulletin``/``declaration-cnss``/``etat-charges``) exige
    ``paie_voir`` ; toute écriture (POST/PUT/PATCH/DELETE, y compris les
    actions custom comme ``changer-statut``/``cloturer``/``valider``) exige
    ``paie_gerer``. Repli legacy : un compte SANS rôle fin garde l'accès
    Responsable/Admin d'avant (aucune régression). Mixin réutilisé par TOUS
    les viewsets paie (y compris ceux qui n'héritent pas de
    ``_PaieBaseViewSet``) — le coffre-fort employé (scopé utilisateur) reste
    à part, hors périmètre.
    """
    def get_permissions(self):
        from rest_framework.permissions import SAFE_METHODS

        from authentication.permissions import HasPermissionOrLegacy

        code = 'paie_voir' if self.request.method in SAFE_METHODS \
            else 'paie_gerer'
        return [HasPermissionOrLegacy(code)()]


class _PaieBaseViewSet(_PaieVoirOuGerer, TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + ``paie_voir``/``paie_gerer`` (XPAI7)."""
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent


class _RappelRetroactifMixin:
    """NTPAY1 — actions de rétroactivité d'un jeu versionné (paramètre/barème).

    Partagé par ``ParametrePaieViewSet`` et ``BaremeIRViewSet`` : la seule
    différence est le mot-clé passé aux services (``parametre=`` vs
    ``bareme=``), porté par ``_KWARG_RETRO``.

    * ``GET  <ressource>/<id>/periodes-impactees/`` — lecture seule, liste les
      périodes VALIDÉES/CLÔTURÉES que la publication rend périmées ;
    * ``POST <ressource>/<id>/rappel-retroactif/`` — corps
      ``{"periode_cible": <id>, "motif": "…"}`` : matérialise les bulletins de
      rappel sur la période cible. Les bulletins d'origine restent figés.
    """
    _KWARG_RETRO = 'parametre'

    def _periodes_impactees(self, request):
        objet = self.get_object()
        return detecter_periodes_impactees(
            request.user.company, **{self._KWARG_RETRO: objet})

    @action(detail=True, methods=['get'], url_path='periodes-impactees')
    def periodes_impactees(self, request, pk=None):
        """Périodes déjà figées que ce jeu versionné rend périmées (NTPAY1)."""
        periodes = self._periodes_impactees(request)
        return Response({
            'periodes': [
                {'id': p.id, 'annee': p.annee, 'mois': p.mois,
                 'statut': p.statut, 'type_run': p.type_run}
                for p in periodes
            ],
            'nombre': len(periodes),
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='rappel-retroactif')
    def rappel_retroactif(self, request, pk=None):
        """Génère les bulletins de rappel rétroactif (NTPAY1)."""
        periode_id = request.data.get('periode_cible')
        if not periode_id:
            raise DRFValidationError({
                'periode_cible': [
                    'Champ requis : indiquez la période OUVERTE qui portera '
                    'le rappel rétroactif.']})
        try:
            periode_cible = PeriodePaie.objects.get(
                company=request.user.company, pk=periode_id)
        except (PeriodePaie.DoesNotExist, ValueError, TypeError):
            raise DRFValidationError({
                'periode_cible': ['Période introuvable dans votre société.']})
        periodes = self._periodes_impactees(request)
        try:
            resultat = appliquer_rappel_retroactif(
                periode_cible, periodes,
                motif=(request.data.get('motif') or ''))
        except DjangoValidationError as exc:
            raise DRFValidationError({'periode_cible': exc.messages})
        return Response({
            'periode_cible': periode_cible.id,
            'periodes_regularisees': [p.id for p in resultat['periodes']],
            'bulletins': [b.id for b in resultat['bulletins']],
            'nombre_salaries': resultat['nombre_salaries'],
            'total_ecart_ir': str(resultat['total_ecart_ir']),
            'total_ecart_net': str(resultat['total_ecart_net']),
        }, status=status.HTTP_201_CREATED)


class ParametrePaieViewSet(_RappelRetroactifMixin, _PaieBaseViewSet):
    """Paramètres sociaux versionnés (PAIE2).

    PAIE3 — l'action ``seed-defaults`` provisionne (idempotent) les valeurs
    légales 2026 (paramètres + barème IR) pour la société de l'utilisateur,
    ``valide_par_fondateur=False``. La validation/surcharge se fait ensuite
    par un PATCH classique sur la ligne (``valide_par_fondateur`` et les taux
    sont en écriture).
    """
    queryset = ParametrePaie.objects.all()
    serializer_class = ParametrePaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_effet', 'id']

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Provisionne les valeurs légales 2026 pour la société (idempotent)."""
        created = ensure_defaults(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class BaremeIRViewSet(_RappelRetroactifMixin, _PaieBaseViewSet):
    """Barèmes IR versionnés et leurs tranches (PAIE4).

    NTPAY1 — ``periodes-impactees`` / ``rappel-retroactif`` (cf.
    ``_RappelRetroactifMixin``) rejouent les périodes déjà figées qu'un barème
    publié rétroactivement rend périmées.
    """
    _KWARG_RETRO = 'bareme'
    queryset = BaremeIR.objects.prefetch_related('tranches').all()
    serializer_class = BaremeIRSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['date_effet', 'id']

    # NTPAY21 — le jeton d'aperçu est SIGNÉ (pas de table, pas de migration) :
    # il prouve que l'étape « aperçu d'impact » a bien été jouée pour CE
    # barème, et il périme au bout d'une heure.
    _SEL_APERCU_BAREME = 'paie.wizard-publication-bareme'
    _DUREE_JETON_APERCU_S = 3600

    @staticmethod
    def _jeton_apercu(bareme):
        from django.core.signing import TimestampSigner

        signer = TimestampSigner(salt=BaremeIRViewSet._SEL_APERCU_BAREME)
        return signer.sign(f'{bareme.company_id}:{bareme.id}')

    @classmethod
    def _jeton_apercu_valide(cls, bareme, jeton):
        from django.core.signing import BadSignature, TimestampSigner

        if not jeton:
            return False
        signer = TimestampSigner(salt=cls._SEL_APERCU_BAREME)
        try:
            valeur = signer.unsign(jeton, max_age=cls._DUREE_JETON_APERCU_S)
        except BadSignature:
            # ``SignatureExpired`` hérite de ``BadSignature`` : un jeton
            # périmé comme un jeton forgé renvoient tous deux « invalide ».
            return False
        return valeur == f'{bareme.company_id}:{bareme.id}'

    @extend_schema(responses=inline_serializer('PaieWizardPublicationBareme', {
        'etape': serializers.CharField(),
        'bareme': serializers.DictField(),
        'impact': serializers.DictField(required=False),
        'periodes_impactees': serializers.ListField(
            child=serializers.DictField(), required=False),
        'jeton_apercu': serializers.CharField(required=False),
        'rappel': serializers.DictField(required=False, allow_null=True),
    }))
    @action(detail=True, methods=['post'], url_path='wizard-publication')
    def wizard_publication(self, request, pk=None):
        """Wizard guidé de publication d'un barème (NTPAY21).

        Enchaîne les briques existantes en UN parcours, dans cet ordre :

        1. ``etape='apercu'`` — comparateur d'impact (NTPAY17) + périodes déjà
           figées que la publication rend périmées (NTPAY1). Renvoie un
           ``jeton_apercu`` signé, valable une heure ;
        2. ``etape='publication'`` — exige ce jeton (sinon 400 : on ne publie
           pas un barème sans avoir vu son impact) ET
           ``valide_par_fondateur=True`` (la case est obligatoire avant
           activation). Option ``declencher_rappel`` + ``periode_cible`` :
           enchaîne le rappel rétroactif NTPAY1.

        Écriture → gate ``paie_gerer`` (mixin ``_PaieVoirOuGerer``).
        """
        bareme = self.get_object()
        etape = (request.data.get('etape') or 'apercu').strip()
        entete = {
            'id': bareme.id, 'libelle': bareme.libelle,
            'date_effet': bareme.date_effet,
            'valide_par_fondateur': bareme.valide_par_fondateur,
        }

        periodes = self._periodes_impactees(request)
        periodes_json = [
            {'id': p.id, 'annee': p.annee, 'mois': p.mois,
             'statut': p.statut, 'type_run': p.type_run}
            for p in periodes
        ]

        if etape == 'apercu':
            ancien = (
                BaremeIR.objects
                .filter(company=request.user.company, pays=bareme.pays,
                        date_effet__lt=bareme.date_effet)
                .order_by('-date_effet')
                .first()
            )
            impact = None
            if ancien is not None:
                impact = paie_selectors.comparer_baremes(
                    request.user.company, ancien, bareme)
            return Response({
                'etape': 'apercu',
                'bareme': entete,
                'impact': impact,
                'periodes_impactees': periodes_json,
                'jeton_apercu': self._jeton_apercu(bareme),
            }, status=status.HTTP_200_OK)

        if etape != 'publication':
            raise DRFValidationError({'etape': [
                "Étape inconnue : utilisez « apercu » puis « publication »."]})

        if not self._jeton_apercu_valide(
                bareme, request.data.get('jeton_apercu')):
            raise DRFValidationError({'jeton_apercu': [
                "Aperçu d'impact non joué (ou expiré) : rejouez l'étape "
                '« apercu » avant de publier ce barème.']})

        if not request.data.get('valide_par_fondateur'):
            raise DRFValidationError({'valide_par_fondateur': [
                'Validation du fondateur obligatoire : cochez la case avant '
                "d'activer ce barème."]})

        bareme.valide_par_fondateur = True
        bareme.save(update_fields=['valide_par_fondateur'])

        rappel = None
        if request.data.get('declencher_rappel'):
            periode_id = request.data.get('periode_cible')
            if not periode_id:
                raise DRFValidationError({'periode_cible': [
                    'Champ requis pour déclencher le rappel rétroactif : '
                    'indiquez la période OUVERTE qui le portera.']})
            try:
                periode_cible = PeriodePaie.objects.get(
                    company=request.user.company, pk=periode_id)
            except (PeriodePaie.DoesNotExist, ValueError, TypeError):
                raise DRFValidationError({'periode_cible': [
                    'Période introuvable dans votre société.']})
            try:
                resultat = appliquer_rappel_retroactif(
                    periode_cible, periodes,
                    motif=(request.data.get('motif') or ''))
            except DjangoValidationError as exc:
                raise DRFValidationError({'periode_cible': exc.messages})
            rappel = {
                'periode_cible': periode_cible.id,
                'periodes_regularisees': [p.id for p in resultat['periodes']],
                'bulletins': [b.id for b in resultat['bulletins']],
                'nombre_salaries': resultat['nombre_salaries'],
                'total_ecart_ir': str(resultat['total_ecart_ir']),
                'total_ecart_net': str(resultat['total_ecart_net']),
            }

        entete['valide_par_fondateur'] = True
        return Response({
            'etape': 'publication',
            'bareme': entete,
            'periodes_impactees': periodes_json,
            'rappel': rappel,
        }, status=status.HTTP_200_OK)

    @extend_schema(responses=inline_serializer('PaieComparaisonBaremes', {
        'ancien': serializers.DictField(allow_null=True),
        'nouveau': serializers.DictField(allow_null=True),
        'nombre_profils': serializers.IntegerField(),
        'lignes': serializers.ListField(child=serializers.DictField()),
        'totaux': serializers.DictField(),
    }))
    @action(detail=True, methods=['get'], url_path='comparer')
    def comparer(self, request, pk=None):
        """Aperçu d'IMPACT du barème avant publication (NTPAY17).

        Le barème de l'URL est le NOUVEAU jeu ; ``?ancien=<id>`` désigne celui
        auquel le comparer (défaut : le barème actif précédent, c'est-à-dire
        la plus récente date d'effet strictement antérieure, même pays).
        ``?profils=1,2,3`` restreint l'échantillon (défaut : les profils
        actifs, plafonnés). Aucune persistance — rien n'est publié ici.
        """
        nouveau = self.get_object()
        ancien_id = request.query_params.get('ancien')
        if ancien_id:
            ancien = BaremeIR.objects.filter(
                company=request.user.company, pk=ancien_id).first()
            if ancien is None:
                return Response(
                    {'detail': 'Barème « ancien » inconnu pour cette '
                     'société.'},
                    status=status.HTTP_404_NOT_FOUND)
        else:
            ancien = (
                BaremeIR.objects
                .filter(company=request.user.company, pays=nouveau.pays,
                        date_effet__lt=nouveau.date_effet)
                .order_by('-date_effet')
                .first()
            )
            if ancien is None:
                return Response(
                    {'detail': 'Aucun barème antérieur à comparer : '
                     'précisez « ancien ».'},
                    status=status.HTTP_400_BAD_REQUEST)

        profils = None
        brut_profils = request.query_params.get('profils')
        if brut_profils:
            try:
                profils = [int(x) for x in brut_profils.split(',') if x]
            except ValueError:
                return Response(
                    {'detail': 'Paramètre "profils" invalide (ids séparés '
                     'par des virgules).'},
                    status=status.HTTP_400_BAD_REQUEST)

        return Response(
            paie_selectors.comparer_baremes(
                request.user.company, ancien, nouveau,
                echantillon_profils=profils),
            status=status.HTTP_200_OK)


class RubriqueViewSet(_PaieBaseViewSet):
    """Catalogue des rubriques de paie paramétrables (PAIE6).

    Société scopée, accès Administrateur/Responsable. L'action
    ``seed-defaults`` provisionne (idempotent, additif) un jeu de rubriques
    standard (salaire de base, prime, heures sup, CNSS, AMO, IR, avance) pour
    la société, sans jamais écraser une rubrique déjà éditée.
    """
    queryset = Rubrique.objects.all()
    serializer_class = RubriqueSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['ordre', 'code', 'id']

    @action(detail=False, methods=['post'], url_path='seed-defaults')
    def seed_defaults(self, request):
        """Provisionne les rubriques de base pour la société (idempotent)."""
        created = ensure_rubriques_defaut(request.user.company)
        return Response(created, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """Provisionne le catalogue standard étendu (PAIE7) — idempotent.

        Sème les rubriques de base PLUS le catalogue standard (transport,
        panier, ancienneté, CIMR…), sans écraser une rubrique déjà éditée.
        """
        created = ensure_rubriques_standard(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class PaysPaieViewSet(_PaieBaseViewSet):
    """Pays de paie de la société (NTPAY7/NTPAY12) — activation & moteur.

    Société scopée, RBAC paie standard (``paie_voir`` lit, ``paie_gerer``
    édite). ``seed-standard`` provisionne le pays MAROC (idempotent) ; les
    packs FR/SN/CI restent gatés fondateur — un pays déclaré dont le moteur
    n'est pas livré est signalé par ``moteur_disponible: false`` et refusé à
    l'affectation d'un profil.
    """
    queryset = PaysPaie.objects.all()
    serializer_class = PaysPaieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code_iso', 'libelle']
    ordering_fields = ['code_iso', 'libelle', 'id']

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """Provisionne le pays de paie MAROC (idempotent)."""
        created = ensure_pays_paie_standard(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class SchemaComptablePaieViewSet(_PaieBaseViewSet):
    """Plan comptable paie — schéma de ventilation éditable (NTPAY3).

    Surface CRUD de ``SchemaComptablePaie`` (NTPAY2) : chaque ligne route un
    poste système OU une rubrique vers ses comptes de débit/crédit et sa
    section analytique. RBAC standard de la paie (``paie_voir`` lit,
    ``paie_gerer`` écrit — cf. ``_PaieVoirOuGerer``).

    * ``POST seed-standard/`` — sème (idempotent) le plan standard, qui
      reproduit à l'identique les comptes historiques ;
    * ``POST reinitialiser/`` — « Réinitialiser au plan standard » : rejoue le
      seed après avoir effacé les lignes de POSTE SYSTÈME (les lignes par
      rubrique, sans équivalent standard, sont conservées).
    """
    queryset = SchemaComptablePaie.objects.select_related('rubrique').all()
    serializer_class = SchemaComptablePaieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code_systeme', 'rubrique__code', 'rubrique__libelle',
                     'compte_debit', 'compte_credit']
    ordering_fields = ['ordre', 'code_systeme', 'id']

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """Provisionne le plan comptable paie standard (idempotent)."""
        created = ensure_schema_comptable_standard(request.user.company)
        return Response(created, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reinitialiser')
    def reinitialiser(self, request):
        """Réinitialise les postes système au plan standard (NTPAY3)."""
        resultat = reinitialiser_schema_comptable(request.user.company)
        return Response(resultat, status=status.HTTP_200_OK)


class TypeEntreePonctuelleViewSet(_PaieBaseViewSet):
    """Catalogue des types d'entrées ponctuelles (ZPAI9), société scopée.

    L'action ``seed-standard`` provisionne (idempotent, additif) les types
    courants (pourboire, remboursement de frais non imposable, déduction
    ponctuelle) sans jamais écraser un type déjà édité.
    """
    queryset = TypeEntreePonctuelle.objects.all()
    serializer_class = TypeEntreePonctuelleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['libelle', 'code', 'id']

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        """Provisionne le catalogue standard de types (idempotent)."""
        created = ensure_types_entree_ponctuelle_standard(request.user.company)
        return Response(created, status=status.HTTP_200_OK)


class ProfilPaieViewSet(_PaieBaseViewSet):
    """Profils de paie des employés (PAIE8) — société scopée, palier paie.

    ``OneToOne`` vers ``rh.DossierEmploye`` ; ``company`` posée côté serveur.

    AUD716 — le salaire de base est SENSIBLE : cette docstring l'affirmait déjà
    (« jamais exposé côté client ») alors que ``ProfilPaieSerializer`` le
    servait EN CLAIR et l'acceptait en écriture sous la seule permission
    ``paie_voir``/``paie_gerer``. Il est désormais gaté ``salaires_voir`` dans
    les deux sens PAR LE SERIALIZER (masqué en lecture, refusé en écriture) —
    et non par ``permission_classes``, pour que le reste du profil (affiliation
    CNSS/AMO, RIB, normes de travail, régime d'exonération) reste accessible au
    gestionnaire de paie, comme aujourd'hui.
    """
    queryset = ProfilPaie.objects.select_related('employe').all()
    serializer_class = ProfilPaieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employe__nom', 'employe__prenom', 'employe__matricule']
    ordering_fields = ['date_creation', 'id']

    def perform_create(self, serializer):
        """XPAI24 — un profil créé avec ``structure`` reçoit ses rubriques défaut."""
        profil = serializer.save(company=self.request.user.company)
        if profil.structure_id:
            appliquer_structure_a_profil(profil, profil.structure)

    @action(detail=False, methods=['post'], url_path='expirer-regimes')
    def expirer_regimes(self, request):
        """Bascule au régime normal les profils dont la fenêtre est expirée (XPAI18)."""
        bascules = expirer_regimes_echus(request.user.company)
        return Response(
            {'bascules': [p.id for p in bascules]}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='synchroniser-salaire')
    def synchroniser_salaire_action(self, request, pk=None):
        """Aligne le salaire du profil sur la rémunération RH en vigueur

        (YHIRE6). Gatée EXPLICITEMENT ``salaires_voir`` (donnée sensible,
        au-delà de ``paie_gerer``) : un compte sans cette permission fine
        obtient 403 même s'il gère la paie. Jamais de synchronisation
        silencieuse — appelée volontairement depuis l'écran de contrôle.
        """
        from authentication.permissions import HasPermission

        if not HasPermission('salaires_voir')().has_permission(
                request, self):
            return Response(
                {'detail': 'Permission "salaires_voir" requise.'},
                status=status.HTTP_403_FORBIDDEN)
        profil = self.get_object()
        synchroniser_salaire(profil)
        profil.refresh_from_db()
        return Response(
            self.get_serializer(profil).data, status=status.HTTP_200_OK)

    @extend_schema(responses=inline_serializer('PaieSimulationEmbauche', {
        'brut': serializers.DecimalField(max_digits=16, decimal_places=2),
        'net_a_payer': serializers.DecimalField(
            max_digits=16, decimal_places=2),
        'net_imposable': serializers.DecimalField(
            max_digits=16, decimal_places=2),
        'ir': serializers.DecimalField(max_digits=16, decimal_places=2),
        'charges_patronales': serializers.DecimalField(
            max_digits=16, decimal_places=2),
        'cout_total_employeur': serializers.DecimalField(
            max_digits=16, decimal_places=2),
        'devise': serializers.CharField(),
        'provisions': inline_serializer('PaieSimulationEmbaucheProvisions', {
            'gratification': serializers.DecimalField(
                max_digits=16, decimal_places=2),
            'conges_payes': serializers.DecimalField(
                max_digits=16, decimal_places=2),
            'ifc': serializers.DecimalField(max_digits=16, decimal_places=2),
            'total': serializers.DecimalField(
                max_digits=16, decimal_places=2),
        }),
        'lignes': inline_serializer(
            'PaieSimulationEmbaucheLigne', many=True, fields={
                'code': serializers.CharField(),
                'libelle': serializers.CharField(),
                'type': serializers.CharField(),
                'montant': serializers.DecimalField(
                    max_digits=16, decimal_places=2),
            }),
        'avertissements': serializers.ListField(
            child=serializers.CharField()),
    }))
    @action(detail=False, methods=['get'], url_path='simulation-embauche')
    def simulation_embauche(self, request):
        """Coût complet d'une EMBAUCHE FUTURE, sans aucun profil (NTPAY14).

        XPAI16 rejoue le moteur sur un profil EXISTANT ; ici rien n'existe
        encore. Paramètres de requête : ``brut`` **ou** ``net_cible``
        (exactement un des deux, requis), ``pays`` (id d'un ``PaysPaie`` de la
        société, facultatif), ``personnes_a_charge``, ``affilie_cnss`` /
        ``affilie_amo`` / ``affilie_cimr`` (booléens, défauts vrai/vrai/faux),
        ``taux_cimr``, ``regime_mutuelle`` (id d'un ``RegimeMutuelle`` de la
        société), ``regime_plafond_mensuel`` (plafond exonéré du régime
        stagiaire/ANAPEC/TAHFIZ), ``jours_travail_mensuel`` /
        ``heures_travail_mensuel``, ``anciennete_annees``, ``date`` (défaut
        aujourd'hui — fixe les barèmes en vigueur).

        Gatée EXPLICITEMENT ``salaires_voir`` (donnée sensible, au-delà de
        ``paie_voir`` — AUD716) : la simulation EXPOSE un brut et un net.
        Aucune écriture en base.
        """
        resultat, erreur = self._simulation_embauche_depuis_requete(request)
        if erreur is not None:
            return erreur
        return Response(resultat, status=status.HTTP_200_OK)

    def _simulation_embauche_depuis_requete(self, request):
        """NTPAY14 — simulation depuis les paramètres de requête.

        Renvoie ``(resultat, None)`` ou ``(None, reponse_erreur)``. Partagé
        par l'endpoint JSON et par la lettre d'offre NTPAY15, qui rejoue la
        MÊME simulation — jamais une seconde lecture des paramètres.
        """
        from authentication.permissions import HasPermission

        if not HasPermission('salaires_voir')().has_permission(request, self):
            return Response(
                {'detail': 'Permission "salaires_voir" requise.'},
                status=status.HTTP_403_FORBIDDEN)

        company = request.user.company
        params = request.query_params

        def _bool_param(nom, defaut):
            valeur = params.get(nom)
            if valeur is None:
                return defaut
            return valeur.lower() in ('1', 'true', 'vrai')

        def _decimal_param(nom, defaut=None):
            valeur = params.get(nom)
            if valeur in (None, ''):
                return defaut
            return Decimal(valeur)

        try:
            brut = _decimal_param('brut')
            net_cible = _decimal_param('net_cible')
            pac = int(params.get('personnes_a_charge', 0) or 0)
            taux_cimr = _decimal_param('taux_cimr', Decimal('0'))
            plafond_regime = _decimal_param(
                'regime_plafond_mensuel', Decimal('0'))
            anciennete = _decimal_param('anciennete_annees', Decimal('0'))
            jours = params.get('jours_travail_mensuel') or None
            heures = params.get('heures_travail_mensuel') or None
            jours = int(jours) if jours else None
            heures = int(heures) if heures else None
        except (InvalidOperation, ValueError, TypeError):
            return None, Response(
                {'detail': 'Paramètre numérique invalide.'},
                status=status.HTTP_400_BAD_REQUEST)

        le_jour = parse_date(params.get('date') or '') or None

        pays = None
        if params.get('pays'):
            pays = PaysPaie.objects.filter(
                company=company, pk=params.get('pays')).first()
            if pays is None:
                return None, Response(
                    {'detail': 'Pays de paie inconnu pour cette société.'},
                    status=status.HTTP_404_NOT_FOUND)

        regime_mutuelle = None
        if params.get('regime_mutuelle'):
            regime_mutuelle = RegimeMutuelle.objects.filter(
                company=company, pk=params.get('regime_mutuelle')).first()
            if regime_mutuelle is None:
                return None, Response(
                    {'detail': 'Régime de mutuelle inconnu pour cette '
                     'société.'},
                    status=status.HTTP_404_NOT_FOUND)

        try:
            resultat = simuler_cout_embauche(
                company, brut=brut, net_cible=net_cible, le_jour=le_jour,
                pays=pays, personnes_a_charge=pac,
                affilie_cnss=_bool_param('affilie_cnss', True),
                affilie_amo=_bool_param('affilie_amo', True),
                affilie_cimr=_bool_param('affilie_cimr', False),
                taux_cimr=taux_cimr, regime_mutuelle=regime_mutuelle,
                regime_plafond_mensuel=plafond_regime,
                jours_travail_mensuel=jours, heures_travail_mensuel=heures,
                anciennete_annees=anciennete)
        except ValueError as exc:
            return None, Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return resultat, None

    @action(detail=False, methods=['get'], url_path='lettre-offre')
    def lettre_offre(self, request):
        """Lettre d'offre / proposition d'embauche PDF (NTPAY15).

        Rejoue la simulation NTPAY14 (mêmes paramètres de requête) puis en
        tire un document RH-facing : intitulé du ``poste`` (requis),
        ``candidat``, ``avantages`` (séparés par ``;``), ``periode_essai``,
        ``date_prise_poste``. Le coût employeur (charges patronales,
        provisions, coût chargé) n'y figure JAMAIS.

        Gatée ``salaires_voir`` comme la simulation dont elle dérive.
        """
        from authentication.permissions import HasPermission

        if not HasPermission('salaires_voir')().has_permission(request, self):
            return Response(
                {'detail': 'Permission "salaires_voir" requise.'},
                status=status.HTTP_403_FORBIDDEN)

        poste = (request.query_params.get('poste') or '').strip()
        if not poste:
            return Response(
                {'detail': 'Paramètre "poste" requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        simulation, erreur = self._simulation_embauche_depuis_requete(request)
        if erreur is not None:
            return erreur

        avantages = [
            a.strip()
            for a in (request.query_params.get('avantages') or '').split(';')
            if a.strip()
        ]
        try:
            pdf = builders.render_lettre_offre_pdf(
                simulation, poste=poste,
                candidat=request.query_params.get('candidat', ''),
                avantages=avantages,
                periode_essai=request.query_params.get('periode_essai', ''),
                date_prise_poste=parse_date(
                    request.query_params.get('date_prise_poste') or ''),
                company=request.user.company)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return _pdf_response(pdf, 'lettre_offre.pdf')

    @action(detail=True, methods=['get'], url_path='attestation')
    def attestation(self, request, pk=None):
        """Attestation salaire/travail/domiciliation/IJ CNSS PDF (PAIE34).

        Paramètre de requête ``type`` ∈ {salaire, travail, domiciliation,
        attestation_ij_cnss} (défaut ``travail``). L'attestation de salaire
        s'appuie sur le dernier bulletin VALIDÉ du profil. XPAI14 —
        ``attestation_ij_cnss`` exige le paramètre ``periode`` (id) : agrège
        les arrêts CNSS de cette période.
        """
        profil = self.get_object()
        type_att = request.query_params.get('type', builders.TYPE_TRAVAIL)
        bulletin = (
            BulletinPaie.objects
            .filter(company=request.user.company, profil=profil,
                    statut=BulletinPaie.STATUT_VALIDE)
            .order_by('-periode__annee', '-periode__mois')
            .first()
        )
        arret_cnss = None
        if type_att == builders.TYPE_ATTESTATION_IJ_CNSS:
            periode_id = request.query_params.get('periode')
            if not periode_id:
                return Response(
                    {'detail': 'Paramètre "periode" requis pour '
                     'attestation_ij_cnss.'},
                    status=status.HTTP_400_BAD_REQUEST)
            try:
                periode = PeriodePaie.objects.get(
                    pk=periode_id, company=request.user.company)
            except (PeriodePaie.DoesNotExist, ValueError):
                return Response(
                    {'detail': 'Période inconnue.'},
                    status=status.HTTP_404_NOT_FOUND)
            arret_cnss = attestation_salaire_ij_cnss(profil, periode)
        try:
            pdf = builders.render_attestation_pdf(
                type_att, profil, bulletin=bulletin, arret_cnss=arret_cnss)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return _pdf_response(pdf, f'attestation_{type_att}_{profil.id}.pdf')

    @action(detail=True, methods=['post'], url_path='stc')
    def stc(self, request, pk=None):
        """Solde de tout compte (STC) — génère le bulletin de sortie (XPAI1).

        Corps : ``periode`` (id, requis — la période cible du STC) ;
        ``motif`` (facultatif, sinon repris du motif de sortie RH) ;
        ``mois_preavis`` (défaut 1) ; ``personnes_a_charge`` (défaut 0). Crée
        (ou recalcule tant que non validé) un bulletin de nature STC.
        """
        profil = self.get_object()
        periode_id = request.data.get('periode')
        if not periode_id:
            return Response(
                {'detail': 'Champ "periode" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            mois_preavis = int(request.data.get('mois_preavis', 1))
        except (TypeError, ValueError):
            mois_preavis = 1
        try:
            pac = int(request.data.get('personnes_a_charge', 0))
        except (TypeError, ValueError):
            pac = 0
        try:
            bulletin = generer_bulletin_stc(
                profil, periode, motif=request.data.get('motif', ''),
                mois_preavis=mois_preavis, personnes_a_charge=pac)
        except BulletinPaie.BulletinVerrouille as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BulletinPaieSerializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='certificat-travail')
    def certificat_travail(self, request, pk=None):
        """Certificat de travail de sortie, art. 72 (NTPAY6) — PDF.

        Pièce de sortie de l'assistant STC (XPAI1), distincte de
        l'attestation de travail générique (PAIE34) : elle porte les DATES
        EXACTES d'entrée/sortie, le(s) emploi(s) occupé(s) et la mention
        « libre de tout engagement ». Dates et poste sont lus via
        ``rh.selectors`` (jamais ``rh.models``). Sans date de sortie sur la
        fiche RH, l'édition est refusée en 400 en nommant ce qui manque.
        """
        from apps.rh import selectors as rh_selectors  # cross-app, lecture

        profil = self.get_object()
        identite = rh_selectors.fiche_identite_employe(
            request.user.company, profil.employe_id) or {}
        date_sortie, _motif = rh_selectors.sortie_employe(
            request.user.company, profil.employe_id)
        emplois = [identite.get('poste')] if identite.get('poste') else []
        try:
            pdf = builders.render_certificat_travail_pdf(
                profil,
                date_entree=identite.get('date_embauche'),
                date_sortie=date_sortie or identite.get('date_sortie'),
                emplois=emplois)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return _pdf_response(pdf, f'certificat_travail_{profil.id}.pdf')

    @action(detail=True, methods=['get'], url_path='stc-pdf')
    def stc_pdf(self, request, pk=None):
        """Reçu pour solde de tout compte au format PDF (XPAI1).

        Sert le dernier bulletin STC du profil. AUD702 — le reçu DÉFINITIF
        (clause de quittance signable + mentions protectrices + signatures)
        n'est rendu QUE depuis un bulletin VALIDÉ ; un bulletin en brouillon
        produit un PROJET filigrané, sans quittance ni bloc de signature.
        Tant que le bulletin est en brouillon, ``generer_bulletin_stc``
        supprime et recrée ses lignes à chaque appel : un reçu signé sur cette
        base pourrait ne plus correspondre à rien en base le lendemain.
        """
        profil = self.get_object()
        bulletin = (
            BulletinPaie.objects
            .filter(company=request.user.company, profil=profil,
                    type_bulletin=BulletinPaie.TYPE_STC)
            .order_by('-date_creation')
            .first()
        )
        if bulletin is None:
            return Response(
                {'detail': 'Aucun bulletin STC pour ce profil.'},
                status=status.HTTP_404_NOT_FOUND)
        definitif = builders.stc_est_definitif(bulletin)
        try:
            pdf = builders.render_stc_pdf(bulletin, definitif=definitif)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        nom = f'stc_{profil.id}.pdf' if definitif \
            else f'stc_projet_{profil.id}.pdf'
        return _pdf_response(pdf, nom)

    @action(detail=True, methods=['get'], url_path='simulation')
    def simulation(self, request, pk=None):
        """Simule un bulletin what-if SANS PERSISTANCE (XPAI16).

        Paramètres de requête : ``periode`` (id, requis — fixe les
        paramètres légaux en vigueur), ``salaire`` (facultatif, défaut le
        salaire réel du profil), ``prime`` (facultatif), ``personnes_a_charge``
        (facultatif). Ne crée aucun ``BulletinPaie``.
        """
        profil = self.get_object()
        periode_id = request.query_params.get('periode')
        if not periode_id:
            return Response(
                {'detail': 'Paramètre "periode" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            salaire = request.query_params.get('salaire')
            salaire = Decimal(salaire) if salaire is not None else None
            prime = Decimal(request.query_params.get('prime', '0') or '0')
            pac = int(request.query_params.get('personnes_a_charge', 0) or 0)
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'detail': 'Paramètre "salaire"/"prime"/'
                 '"personnes_a_charge" invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        resultat = simuler_bulletin(
            profil, periode, salaire=salaire, prime=prime,
            personnes_a_charge=pac)
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='registre-conges')
    def registre_conges_action(self, request):
        """Registre des congés annuel, par employé (XPAI26).

        Paramètre de requête ``annee`` requis. ``?export=pdf``/``?export=csv``
        renvoient le fichier au lieu du JSON. Lecture seule.
        """
        try:
            annee = int(request.query_params.get('annee'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Paramètre "annee" requis (et valide).'},
                status=status.HTTP_400_BAD_REQUEST)
        registre = registre_conges(request.user.company, annee)
        export = request.query_params.get('export')
        if export == 'pdf':
            try:
                pdf = builders.render_registre_conges_pdf(registre)
            except RuntimeError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return _pdf_response(pdf, f'registre_conges_{annee}.pdf')
        if export == 'csv':
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter=';')
            writer.writerow(['Matricule', 'Nom', 'Droits (j)', 'Pris (j)',
                             'Solde (j)'])
            for ligne in registre['lignes']:
                writer.writerow([
                    ligne['matricule'], ligne['nom'], ligne['droits'],
                    ligne['pris'], ligne['solde']])
            resp = HttpResponse(
                buffer.getvalue(), content_type='text/csv; charset=utf-8')
            resp['Content-Disposition'] = (
                f'attachment; filename="registre_conges_{annee}.csv"')
            return resp
        return Response(registre, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='historique-carriere')
    def historique_carriere_action(self, request, pk=None):
        """Fiche historique de carrière/salaire d'un profil (XPAI26).

        ``?export=pdf`` renvoie le PDF au lieu du JSON. Lecture seule,
        AUCUNE écriture.
        """
        profil = self.get_object()
        historique = historique_carriere(profil)
        if request.query_params.get('export') == 'pdf':
            try:
                pdf = builders.render_historique_carriere_pdf(historique)
            except RuntimeError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return _pdf_response(
                pdf, f'historique_carriere_{profil.id}.pdf')
        return Response(historique, status=status.HTTP_200_OK)


class RubriqueEmployeViewSet(_PaieBaseViewSet):
    """Rubriques récurrentes par employé (PAIE9) — société scopée."""
    queryset = RubriqueEmploye.objects.select_related(
        'profil', 'rubrique').all()
    serializer_class = RubriqueEmployeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']


class StructurePaieViewSet(_PaieBaseViewSet):
    """Structures de paie par catégorie (XPAI24) — gabarits de rubriques.

    ``ensure-standard`` sème (idempotent) les 3 structures standard
    (cadre/employé/ouvrier). ``appliquer`` rattache les rubriques d'une
    structure à un profil existant (corps : ``profil`` id) — la même
    application se produit automatiquement à la CRÉATION d'un profil dont
    ``structure`` est renseignée.
    """
    queryset = StructurePaie.objects.prefetch_related('rubriques_defaut').all()
    serializer_class = StructurePaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle', 'date_creation', 'id']

    @action(detail=False, methods=['post'], url_path='ensure-standard')
    def ensure_standard(self, request):
        """Sème (idempotent) les 3 structures standard (XPAI24)."""
        resultat = ensure_structures_standard(request.user.company)
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='appliquer')
    def appliquer(self, request, pk=None):
        """Applique cette structure à un profil existant (corps : ``profil``)."""
        structure = self.get_object()
        profil_id = request.data.get('profil')
        if not profil_id:
            return Response(
                {'detail': 'Champ "profil" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
        except (ProfilPaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Profil inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        nb = appliquer_structure_a_profil(profil, structure)
        return Response({'rattachees': nb}, status=status.HTTP_200_OK)


class RegimeMutuelleViewSet(_PaieBaseViewSet):
    """Catalogue des régimes de mutuelle/prévoyance (XPAI3) — société scopée."""
    queryset = RegimeMutuelle.objects.all()
    serializer_class = RegimeMutuelleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['libelle', 'id']


class AdhesionMutuelleViewSet(_PaieBaseViewSet):
    """Adhésions des profils aux régimes de mutuelle (XPAI3) — société scopée."""
    queryset = AdhesionMutuelle.objects.select_related('profil', 'regime').all()
    serializer_class = AdhesionMutuelleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']


class PeriodePaieViewSet(_PaieBaseViewSet):
    """Périodes de paie — run mensuel + cycle de statuts (PAIE10).

    Le ``statut`` n'avance que par l'action ``changer-statut`` (cycle progressif
    brouillon→calculée→validée→clôturée). L'action ``importer-elements-rh``
    (PAIE11) matérialise les éléments variables RH du mois.
    """
    queryset = PeriodePaie.objects.all()
    serializer_class = PeriodePaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'mois', 'date_creation', 'id']

    def perform_create(self, serializer):
        """Pose ``company`` puis génère (XPAI6) l'échéancier déclaratif."""
        periode = serializer.save(company=self.request.user.company)
        generer_echeances_periode(periode)

    @extend_schema(responses=inline_serializer('PaieConformite', {
        'today': serializers.DateField(),
        'conforme': serializers.BooleanField(),
        'echeances_en_retard': serializers.ListField(
            child=serializers.DictField()),
        'echeances_a_venir': serializers.ListField(
            child=serializers.DictField()),
        'depots_manquants': serializers.ListField(
            child=serializers.DictField()),
        'baremes_non_valides': serializers.ListField(
            child=serializers.DictField()),
        'periodes_en_retard': serializers.ListField(
            child=serializers.DictField()),
        'alertes_pre_run': serializers.ListField(
            child=serializers.DictField()),
    }))
    @extend_schema(responses=inline_serializer('PaieMasseSalariale', {
        'group_by': serializers.CharField(),
        'periode_debut': serializers.DictField(),
        'periode_fin': serializers.DictField(),
        'nombre_periodes': serializers.IntegerField(),
        'nombre_bulletins': serializers.IntegerField(),
        'groupes': serializers.ListField(child=serializers.DictField()),
        'totaux': serializers.DictField(),
    }))
    @action(detail=False, methods=['get'],
            url_path='rapports/masse-salariale')
    def rapport_masse_salariale_action(self, request):
        """Rapport de masse salariale par département ou par site (NTPAY19).

        Paramètres : ``debut`` et ``fin`` au format ``AAAA-MM`` (requis),
        ``group_by`` ∈ {``departement``, ``site``} (défaut ``departement``),
        ``export`` ∈ {``csv``, ``pdf``}. Lecture seule, bulletins VALIDÉS
        uniquement, gate ``paie_voir``.
        """
        debut = request.query_params.get('debut')
        fin = request.query_params.get('fin')
        if not debut or not fin:
            return Response(
                {'detail': 'Paramètres "debut" et "fin" requis '
                 '(format AAAA-MM).'},
                status=status.HTTP_400_BAD_REQUEST)
        group_by = request.query_params.get('group_by', 'departement')
        try:
            rapport = paie_selectors.rapport_masse_salariale(
                request.user.company, debut, fin, group_by=group_by)
        except (ValueError, TypeError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        export = request.query_params.get('export')
        if export == 'pdf':
            try:
                pdf = builders.render_masse_salariale_pdf(
                    rapport, company=request.user.company)
            except RuntimeError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return _pdf_response(pdf, f'masse_salariale_{debut}_{fin}.pdf')
        if export == 'csv':
            return self._export_masse_salariale_csv(rapport, debut, fin)
        return Response(rapport, status=status.HTTP_200_OK)

    @staticmethod
    def _export_masse_salariale_csv(rapport, debut, fin):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([f'Masse salariale {debut} - {fin}'])
        writer.writerow([])
        writer.writerow([
            'Groupe', 'Effectif', 'Brut', 'Charges patronales', 'Coût total'])
        for groupe in rapport['groupes']:
            writer.writerow([
                groupe['libelle'], groupe['effectif'], groupe['brut'],
                groupe['charges_patronales'], groupe['cout_total']])
        totaux = rapport['totaux']
        writer.writerow([])
        writer.writerow([
            'Total', totaux['effectif'], totaux['brut'],
            totaux['charges_patronales'], totaux['cout_total']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f'attachment; filename="masse_salariale_{debut}_{fin}.csv"')
        return resp

    @action(detail=False, methods=['get'], url_path='conformite')
    def conformite(self, request):
        """État de conformité paie de la société, en un seul écran (NTPAY16).

        Réunit les échéances déclaratives en retard/à venir (XPAI6), les
        preuves de dépôt manquantes (NTPAY5), les barèmes non validés par le
        fondateur, les périodes ouvertes en retard de clôture (ZPAI12) et les
        avertissements pré-run bloquants (ZPAI2). Lecture seule, gate
        ``paie_voir`` (méthode sûre → mixin ``_PaieVoirOuGerer``).
        """
        return Response(
            paie_selectors.cockpit_conformite_paie(request.user.company),
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='echeances')
    def echeances(self, request, pk=None):
        """Liste les échéances déclaratives de la période (XPAI6)."""
        periode = self.get_object()
        qs = periode.echeances_declaratives.all().order_by('date_limite')
        return Response(
            EcheanceDeclarativeSerializer(qs, many=True).data,
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='notifier-echeances-retard')
    def notifier_echeances_retard(self, request):
        """Notifie (best-effort) les échéances déclaratives en retard (XPAI6)."""
        notifiees = notifier_echeances_en_retard(request.user.company)
        return Response(
            {'notifiees': len(notifiees)}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """Fait avancer la période vers le ``statut`` demandé (PAIE10)."""
        periode = self.get_object()
        nouveau = request.data.get('statut')
        try:
            changer_statut(periode, nouveau)
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(periode).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """Clôture mensuelle + verrouillage de la période (PAIE36).

        Valide les bulletins encore en brouillon (sauf
        ``valider_brouillons=false`` dans le corps) puis fige la période
        (statut → clôturée). Aucun bulletin ne peut plus y être généré.
        """
        periode = self.get_object()
        valider = request.data.get('valider_brouillons', True)
        # NTPAY22 — checklist guidée : un point en ⚠️ exige un motif
        # d'acquittement EXPLICITE, jamais un simple clic.
        try:
            verifier_cloture_autorisee(
                periode,
                motif_acquittement=request.data.get(
                    'motif_acquittement', ''))
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message_dict)
        try:
            cloturer_periode_paie(
                periode, valider_brouillons=bool(valider))
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(periode).data, status=status.HTTP_200_OK)

    @extend_schema(responses=inline_serializer(
        'PaieChecklistCloture', many=True, fields={
            'code': serializers.CharField(),
            'libelle': serializers.CharField(),
            'statut': serializers.CharField(),
            'detail': serializers.CharField(),
        }))
    @action(detail=True, methods=['get'], url_path='checklist-cloture')
    def checklist_cloture_action(self, request, pk=None):
        """Points de contrôle avant clôture de la période (NTPAY22).

        Avances et saisies-arrêt du mois retenues, écarts M/M-1 sans anomalie,
        échéances déclaratives à jour, ordre de virement généré. Chaque point
        ressort ``ok`` ou ``alerte`` ; un point en alerte n'est franchissable
        qu'avec un ``motif_acquittement`` à la clôture. Lecture seule.
        """
        periode = self.get_object()
        return Response(
            checklist_cloture(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='run-gratification')
    def run_gratification(self, request, pk=None):
        """Génère les bulletins « 13e mois » de tous les profils actifs (XPAI4).

        La période cible doit être ``type_run == 'hors_cycle'``. Paramètre de
        corps ``annee_reference`` facultatif (défaut : l'année de la période).
        """
        periode = self.get_object()
        annee_reference = request.data.get('annee_reference') or None
        try:
            if annee_reference is not None:
                annee_reference = int(annee_reference)
            bulletins = generer_run_gratification(
                periode, annee_reference=annee_reference)
        except (ValueError, TypeError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except BulletinPaie.BulletinVerrouille as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'bulletins': [b.id for b in bulletins], 'nombre': len(bulletins)},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='importer-elements-rh')
    def importer_elements_rh(self, request, pk=None):
        """Importe les éléments variables RH du mois (PAIE11)."""
        periode = self.get_object()
        try:
            importes = importer_elements_rh(periode)
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'importes': importes}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'],
            url_path='importer-avantages-nature-flotte')
    def importer_avantages_nature_flotte_action(self, request, pk=None):
        """Importe les avantages en nature véhicule du mois (AUDV21/XFLT29).

        Lit ``apps.flotte.selectors.avantages_en_nature`` (cross-app, jamais
        ``flotte.models``) et matérialise la valeur mensuelle de chaque
        conducteur en usage privé en ``ElementVariable`` (rubrique
        ``AV_VOITURE``, ``source='flotte'``). Gatée ``paie_gerer`` comme toute
        écriture paie (élément variable = argent, jamais ``IsAnyRole``).
        """
        periode = self.get_object()
        try:
            importes = importer_avantages_nature_flotte(periode)
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'importes': importes}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reporter-elements')
    def reporter_elements(self, request, pk=None):
        """Reconduit les éléments récurrents de M-1 vers cette période (ZPAI11).

        Copie les ``ElementVariable`` marqués ``reconduire=True`` de la
        période calendaire précédente (même société/``type_run``) — no-op si
        aucune période précédente. Idempotent : un re-run ne duplique jamais
        une copie déjà faite.
        """
        periode = self.get_object()
        copies = reporter_elements_periode(periode)
        return Response(
            {'reconduits': [c.id for c in copies], 'nombre': len(copies)},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='bulletin')
    def bulletin(self, request, pk=None):
        """Calcule (sans persister) le bulletin d'un profil pour la période.

        PAIE12 — paramètre de requête ``profil`` (id) requis ;
        ``personnes_a_charge`` facultatif. Renvoie le détail du calcul. Donnée
        SENSIBLE : palier paie uniquement.
        """
        periode = self.get_object()
        profil_id = request.query_params.get('profil')
        if not profil_id:
            return Response(
                {'detail': 'Paramètre "profil" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
        except (ProfilPaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Profil inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pac = int(request.query_params.get('personnes_a_charge', 0))
        except (TypeError, ValueError):
            pac = 0
        resultat = calculer_bulletin(profil, periode, personnes_a_charge=pac)
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='declaration-cnss')
    def declaration_cnss(self, request, pk=None):
        """Bordereau de déclaration des salaires CNSS (BDS) de la période (PAIE31)."""
        periode = self.get_object()
        return Response(declaration_cnss(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='declaration-cimr')
    def declaration_cimr(self, request, pk=None):
        """Déclaration CIMR de la période — fichier préétabli e-CIMR (XPAI10)."""
        periode = self.get_object()
        return Response(declaration_cimr(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='fichier-cimr')
    def fichier_cimr(self, request, pk=None):
        """Fichier de télédéclaration CIMR — CSV documenté (XPAI10)."""
        periode = self.get_object()
        return Response(fichier_cimr(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='mouvements-cnss')
    def mouvements_cnss(self, request, pk=None):
        """Entrées/sorties CNSS de la période — alignée BDS (XPAI11)."""
        periode = self.get_object()
        return Response(
            mouvements_cnss_periode(periode), status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='affebds-rapprochement')
    def affebds_rapprochement(self, request):
        """Rapproche un fichier AFFEBDS importé contre les profils paie (XPAI11).

        Corps : ``contenu`` (texte du fichier AFFEBDS, CSV ``;`` — un numéro
        CNSS + nom par ligne). Aucun écrit sur les profils : pur rapport
        rapprochés/manquants/en trop.
        """
        contenu = request.data.get('contenu', '')
        rapport = rapprocher_affebds(request.user.company, contenu)
        return Response(rapport, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='bordereau-cnss')
    def bordereau_cnss(self, request, pk=None):
        """Bordereau de PAIEMENT des cotisations CNSS de la période (NTPAY4).

        JSON par défaut (montants par organisme, total, date limite, dépôt BDS
        lié). ``?export=pdf`` renvoie le bordereau imprimable,
        ``?export=fichier`` le fichier de télépaiement à longueurs fixes.
        Lecture seule — ne déclare ni ne règle rien.
        """
        periode = self.get_object()
        bordereau = bordereau_paiement_cnss(periode)
        export = (request.query_params.get('export') or '').lower()
        if export == 'pdf':
            try:
                pdf = builders.render_bordereau_cnss_pdf(
                    periode, bordereau=bordereau)
            except RuntimeError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return _pdf_response(
                pdf,
                f'bordereau_cnss_{periode.annee}_{periode.mois:02d}.pdf')
        if export == 'fichier':
            return Response(
                fichier_telepaiement_cnss(periode, bordereau=bordereau),
                status=status.HTTP_200_OK)
        return Response(bordereau, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='fichier-damancom')
    def fichier_damancom(self, request, pk=None):
        """Fichier de télédéclaration CNSS au format DAMANCOM (PAIE31)."""
        periode = self.get_object()
        return Response(
            fichier_damancom_cnss(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='fichier-damancom-strict')
    def fichier_damancom_strict_action(self, request, pk=None):
        """Fichier DAMANCOM au format eBDS STRICT — longueurs fixes (XPAI12)."""
        periode = self.get_object()
        return Response(
            fichier_damancom_strict(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='deposer-bds')
    def deposer_bds(self, request, pk=None):
        """Enregistre le dépôt PRINCIPAL de la BDS de la période (XPAI12)."""
        periode = self.get_object()
        depot = deposer_bds_principal(periode)
        return Response({
            'id': depot.id, 'type_depot': depot.type_depot,
            'profils_couverts': depot.profils_couverts,
            'date_depot': depot.date_depot,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='deposer-bds-complementaire')
    def deposer_bds_complementaire_action(self, request, pk=None):
        """Enregistre un dépôt BDS COMPLÉMENTAIRE — delta uniquement (XPAI12).

        Corps : ``profils_delta`` (liste des numéros CNSS/ids omis ou
        corrigés) requis.
        """
        periode = self.get_object()
        profils_delta = request.data.get('profils_delta') or []
        try:
            depot = deposer_bds_complementaire(periode, profils_delta)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'id': depot.id, 'type_depot': depot.type_depot,
            'depot_principal': depot.depot_principal_id,
            'profils_couverts': depot.profils_couverts,
            'date_depot': depot.date_depot,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='etat-ir')
    def etat_ir(self, request, pk=None):
        """État IR 9421 (retenues à la source) de la période (PAIE32)."""
        periode = self.get_object()
        return Response(etat_ir_9421(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='etat-charges')
    def etat_charges(self, request, pk=None):
        """État consolidé des charges sociales par organisme (XPAI5/NTPAY18).

        ``?export=csv`` renvoie le fichier CSV (forme XPAI5, inchangée).

        NTPAY18 — ``?detail=1`` renvoie l'état DÉTAILLÉ (5 organismes CNSS /
        AMO / IR / CIMR / mutuelle avec base, taux, parts salariale et
        patronale, plus les charges annexes recouvrées par la CNSS) et
        ``?export=pdf`` en imprime le document de synthèse. Le JSON par défaut
        reste celui d'XPAI5 — aucune régression pour ses appelants.
        """
        periode = self.get_object()
        export = request.query_params.get('export')
        detaille = request.query_params.get('detail') in ('1', 'true', 'vrai')

        if export == 'pdf' or detaille:
            etat = etat_charges_detaille(periode)
            if export == 'pdf':
                try:
                    pdf = builders.render_etat_charges_pdf(periode, etat=etat)
                except RuntimeError as exc:
                    return Response(
                        {'detail': str(exc)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
                return _pdf_response(
                    pdf,
                    f'etat_charges_{periode.annee}_{periode.mois:02d}.pdf')
            return Response(etat, status=status.HTTP_200_OK)

        data = etat_des_charges(periode)
        if export == 'csv':
            return self._export_etat_charges_csv(data)
        return Response(data, status=status.HTTP_200_OK)

    @staticmethod
    def _export_etat_charges_csv(data):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([f"État des charges sociales {data['mois']:02d}/{data['annee']}"])
        writer.writerow([])
        writer.writerow(['Organisme', 'Part salariale', 'Part patronale', 'Total'])
        for org in data['organismes']:
            writer.writerow([
                org['libelle'], org['salarial'], org['patronal'], org['total']])
        writer.writerow([])
        writer.writerow(['Total général', '', '', data['total_general']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f"attachment; filename=\"etat_charges_{data['annee']}_"
            f"{data['mois']:02d}.csv\"")
        return resp

    @action(detail=True, methods=['get'], url_path='rapprochement-gl')
    def rapprochement_gl(self, request, pk=None):
        """Rapproche le livre de paie au GL posté par le journal de paie (XPAI5)."""
        periode = self.get_object()
        return Response(
            rapprochement_paie_gl(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='livre-de-paie')
    def livre_de_paie(self, request, pk=None):
        """Livre de paie (registre récapitulatif) de la période (PAIE33)."""
        periode = self.get_object()
        return Response(livre_de_paie(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='cout-global')
    def cout_global(self, request, pk=None):
        """Coût global employeur PAR EMPLOYÉ de la période (XPAI17).

        Donnée INTERNE (jamais client-facing) : brut + charges patronales +
        provisions par employé, plus la ventilation analytique appliquée.
        """
        periode = self.get_object()
        return Response(
            cout_global_par_profil(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='cout-employeur')
    def cout_employeur_action(self, request, pk=None):
        """Rapport « coût employeur » CONSOLIDÉ de la période (ZPAI3).

        Total brut + charges patronales + provisions de tous les bulletins
        validés, ratio coût/net, coût moyen par tête. Distinct de
        ``cout-global`` (XPAI17, détail PAR employé). ``?export=csv``.
        Donnée INTERNE (jamais client-facing).
        """
        periode = self.get_object()
        data = cout_employeur(periode)
        if request.query_params.get('export') == 'csv':
            return self._export_cout_employeur_csv(data)
        return Response(data, status=status.HTTP_200_OK)

    @staticmethod
    def _export_cout_employeur_csv(data):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([
            f"Coût employeur {data['mois']:02d}/{data['annee']}"])
        writer.writerow([])
        writer.writerow(['Salariés', data['nombre_salaries']])
        writer.writerow(['Total brut', data['total_brut']])
        writer.writerow(
            ['Total charges patronales', data['total_charges_patronales']])
        writer.writerow(['Total provisions', data['total_provisions']])
        writer.writerow(['Total employeur', data['total_employeur']])
        writer.writerow(['Total net', data['total_net']])
        writer.writerow(['Ratio coût/net', data['ratio_cout_net']])
        writer.writerow(
            ['Coût moyen par tête', data['cout_moyen_par_tete']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = (
            f"attachment; filename=\"cout_employeur_{data['annee']}_"
            f"{data['mois']:02d}.csv\"")
        return resp

    @action(detail=True, methods=['post'], url_path='journal-ventile')
    def journal_ventile(self, request, pk=None):
        """Passe l'écriture du journal de paie AVEC ventilation analytique (XPAI17).

        AUD708 — traduit en 400 la ``ValidationError`` levée par le service
        (période comptable verrouillée, ou journal de paie déjà comptabilisé
        pour cette période) au lieu de laisser remonter un 500, exactement
        comme l'action ``journal-de-paie``.
        """
        periode = self.get_object()
        try:
            ecriture = journal_de_paie_ventile(periode, created_by=request.user)
        except DjangoValidationError as exc:
            return Response(
                {'detail': exc.messages if hasattr(exc, 'messages')
                 else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        if ecriture is None:
            return Response(
                {'detail': 'Aucun bulletin validé pour cette période.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'id': ecriture.id, 'reference': ecriture.reference},
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='provisions')
    def provisions(self, request, pk=None):
        """Provisions 13e mois / IFC de la période, par employé (XPAI20)."""
        periode = self.get_object()
        qs = (
            ProvisionPaieMensuelle.objects
            .filter(company=request.user.company, periode=periode)
            .select_related('profil', 'profil__employe'))
        data = [{
            'id': ligne.id,
            'profil_id': ligne.profil_id,
            'matricule': getattr(ligne.profil.employe, 'matricule', '')
            if ligne.profil.employe_id else '',
            'type_provision': ligne.type_provision,
            'montant': ligne.montant,
            'extournee': ligne.extournee,
        } for ligne in qs]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='hors-virement')
    def hors_virement(self, request, pk=None):
        """Profils réglés hors virement (espèces/chèque) de la période (XPAI9)."""
        periode = self.get_object()
        return Response(
            profils_hors_virement(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='brut-pour-net')
    def brut_pour_net(self, request, pk=None):
        """Calcul inverse « brut pour net cible » (XPAI16, lettres d'offre).

        Paramètres de requête : ``net_cible`` (requis), ``personnes_a_charge``
        (facultatif), ``affilie_cnss``/``affilie_amo``/``affilie_cimr``
        (booléens, défauts vrai/vrai/faux), ``taux_cimr`` (facultatif).
        Converge au centime — aucune persistance.
        """
        periode = self.get_object()
        le_jour = date(periode.annee, periode.mois, 1)
        parametre = parametre_en_vigueur(periode.company, le_jour)
        bareme = bareme_en_vigueur(periode.company, le_jour)
        try:
            net_cible = Decimal(request.query_params.get('net_cible'))
            pac = int(request.query_params.get('personnes_a_charge', 0) or 0)
            taux_cimr = Decimal(
                request.query_params.get('taux_cimr', '0') or '0')
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {'detail': 'Paramètre "net_cible" requis (et valide).'},
                status=status.HTTP_400_BAD_REQUEST)

        def _bool_param(name, defaut):
            valeur = request.query_params.get(name)
            if valeur is None:
                return defaut
            return valeur.lower() in ('1', 'true', 'vrai')

        try:
            resultat = brut_pour_net_cible(
                net_cible, parametre=parametre, bareme=bareme,
                personnes_a_charge=pac,
                affilie_cnss=_bool_param('affilie_cnss', True),
                affilie_amo=_bool_param('affilie_amo', True),
                affilie_cimr=_bool_param('affilie_cimr', False),
                taux_cimr=taux_cimr)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='controle-ecarts')
    def controle_ecarts_action(self, request, pk=None):
        """Contrôle des écarts avant validation, M vs M-1 (XPAI15).

        Paramètre de requête ``seuil_pct`` facultatif (défaut 20 %) —
        variation de net au-delà de laquelle un salarié est signalé.
        Avertissement uniquement, jamais un blocage.
        """
        periode = self.get_object()
        seuil_pct = request.query_params.get('seuil_pct')
        try:
            seuil_pct = Decimal(seuil_pct) if seuil_pct is not None else None
        except (InvalidOperation, ValueError):
            return Response(
                {'detail': 'Paramètre "seuil_pct" invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            controle_ecarts(periode, seuil_pct=seuil_pct),
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='controle-completude')
    def controle_completude_action(self, request, pk=None):
        """Contrôle de complétude pré-paie — trous structurels (YHIRE3).

        Distinct de ``controle-ecarts`` (XPAI15, comparaison M vs M-1) :
        liste les actifs sans profil de paie, les profils sans CNSS/RIB,
        les profils actifs dont le dossier RH n'est plus actif (sorti/
        embauché non pris de poste), et les CDD expirés avant la fin de la
        période. Lecture seule, affiché en tête du PaieRunWizard.
        """
        periode = self.get_object()
        return Response(
            controle_completude(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='avertissements')
    def avertissements(self, request, pk=None):
        """Panneau d'avertissements pré-run, façon Odoo (ZPAI2).

        Liste PLATE d'avertissements typés + gravité (RIB manquant en
        virement, CNSS manquant, salaire nul, profil sans dossier actif,
        CDD échu, actif sans profil de paie) — à afficher en tête du
        tableau de bord Paie avant de lancer le run.
        """
        periode = self.get_object()
        return Response(
            avertissements_periode(periode), status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='bulletins-pdf')
    def bulletins_pdf(self, request, pk=None):
        """Impression en lot des bulletins VALIDÉS de la période (ZPAI5).

        Fusionne (WeasyPrint + PyMuPDF) les PDF de tous les bulletins validés
        de la période en un seul document, ordonné par matricule/nom ; les
        brouillons sont exclus. 400 si aucun bulletin validé.
        """
        periode = self.get_object()
        try:
            pdf = builders.render_bulletins_periode_pdf(periode)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        nom = f'bulletins_{periode.annee}_{periode.mois:02d}.pdf'
        return _pdf_response(pdf, nom)

    @action(detail=True, methods=['post'], url_path='rattacher-bulletins')
    def rattacher_bulletins_action(self, request, pk=None):
        """Rattache des bulletins non affectés à cette période (ZPAI10).

        Corps : ``bulletins`` (liste d'ids de ``BulletinPaie`` NON clôturés,
        même société). Refuse si la période cible est clôturée, si un
        bulletin est d'une autre société, déjà validé, ou créerait un doublon
        ``(période, profil)``.
        """
        periode = self.get_object()
        bulletin_ids = request.data.get('bulletins') or []
        if not bulletin_ids:
            return Response(
                {'detail': 'Champ "bulletins" (liste d\'ids) requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            rattaches = rattacher_bulletins(periode, bulletin_ids)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BulletinPaieSerializer(rattaches, many=True).data,
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='journal-de-paie')
    def journal_de_paie(self, request, pk=None):
        """Passe l'écriture comptable du journal de paie (PAIE33).

        Agrège les bulletins validés et crée une écriture OD équilibrée via
        ``compta.services``. Renvoie l'id de l'écriture (ou 400 s'il n'y a aucun
        bulletin validé ou si la période comptable est verrouillée).
        """
        periode = self.get_object()
        try:
            ecriture = journal_de_paie(periode, created_by=request.user)
        except DjangoValidationError as exc:  # période comptable verrouillée…
            return Response(
                {'detail': exc.messages if hasattr(exc, 'messages')
                 else str(exc)},
                status=status.HTTP_400_BAD_REQUEST)
        if ecriture is None:
            return Response(
                {'detail': 'Aucun bulletin validé : rien à comptabiliser.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'ecriture_id': ecriture.id, 'reference': ecriture.reference},
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='etat-ir-annuel')
    def etat_ir_annuel(self, request):
        """État IR 9421 ANNUEL d'une société (PAIE32).

        Paramètre de requête ``annee`` requis : cumule l'IR retenu sur toutes
        les périodes de l'année.
        """
        try:
            annee = int(request.query_params.get('annee'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Paramètre "annee" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            etat_ir_9421_annuel(request.user.company, annee),
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='etat-ir-annuel-xml')
    def etat_ir_annuel_xml(self, request):
        """État IR 9421 ANNUEL — export XML EDI SIMPL-IR (XPAI13).

        Paramètre de requête ``annee`` requis. Renvoie le fichier XML
        téléchargeable, bien formé et validé contre le schéma embarqué.
        """
        try:
            annee = int(request.query_params.get('annee'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Paramètre "annee" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        xml = export_xml_simpl_ir_9421(request.user.company, annee)
        resp = HttpResponse(xml, content_type='application/xml; charset=utf-8')
        resp['Content-Disposition'] = (
            f'attachment; filename="etat_9421_{annee}.xml"')
        return resp


class ElementVariableViewSet(_PaieBaseViewSet):
    """Éléments variables du mois (PAIE11) — société scopée."""
    queryset = ElementVariable.objects.select_related(
        'periode', 'profil', 'rubrique').all()
    serializer_class = ElementVariableSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['periode', 'profil', 'id']

    def perform_destroy(self, instance):
        """AUD715 — la suppression suit la même garde de statut que l'écriture.

        Sans elle, un DELETE sur une période déjà CALCULÉE/VALIDÉE/CLÔTURÉE
        renvoyait 204 en retirant un élément qui n'influencerait plus jamais le
        bulletin déjà émis. La garde vit sur le modèle (admin, scripts inclus) ;
        ici on la traduit en 400 lisible plutôt qu'en 500.
        """
        try:
            instance.delete()
        except ElementVariable.PeriodeVerrouillee as exc:
            raise DRFValidationError({'periode': str(exc)})


class BulletinPaieViewSet(_PaieVoirOuGerer, TenantMixin,
                          viewsets.ReadOnlyModelViewSet):
    """Bulletins de paie matérialisés (PAIE17) — snapshot immuable.

    Lecture seule via l'API : un bulletin se crée/recalcule par l'action
    ``generer`` et se fige par l'action ``valider``. Les montants ne sont JAMAIS
    écrits directement (snapshot). Société scopée, ``paie_voir``/``paie_gerer``
    (XPAI7).
    """
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent
    queryset = BulletinPaie.objects.select_related(
        'periode', 'profil').prefetch_related('lignes').all()
    serializer_class = BulletinPaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'periode', 'profil', 'id']

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """Matérialise (ou recalcule) le bulletin d'un profil pour une période.

        Corps : ``periode`` (id), ``profil`` (id), ``personnes_a_charge``
        (facultatif). Un bulletin déjà VALIDÉ ne peut être régénéré (400).
        """
        periode_id = request.data.get('periode')
        profil_id = request.data.get('profil')
        if not periode_id or not profil_id:
            return Response(
                {'detail': 'Champs "periode" et "profil" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ProfilPaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période ou profil inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pac = int(request.data.get('personnes_a_charge', 0))
        except (TypeError, ValueError):
            pac = 0
        try:
            bulletin = generer_bulletin(profil, periode, personnes_a_charge=pac)
        except BulletinPaie.BulletinVerrouille as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide le bulletin → fige le snapshot (immuable, PAIE17).

        AUD705 — un refus métier (n° CNSS connu côté RH mais absent du profil
        de paie) est une erreur de saisie, pas une panne : il repart en 400
        avec son motif, jamais en 500.
        """
        bulletin = self.get_object()
        try:
            valider_bulletin(bulletin)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='regulariser-ir')
    def regulariser_ir(self, request, pk=None):
        """AUDV19 (DRAFT165-77, XPAI2) — applique la régularisation IR
        annuelle sur un bulletin BROUILLON. Ajoute (ou remplace) une ligne
        `IR-REGUL` (rappel si delta > 0, trop-perçu si delta < 0), met à
        jour `ir`/`net_a_payer`. AUD709 (prérequis de cette tâche) : le
        calcul respecte déjà l'exonération de régime (stagiaire/ANAPEC/
        TAHFIZ) — aucun rappel indu sur un profil protégé."""
        bulletin = self.get_object()
        try:
            delta = appliquer_regularisation_ir(bulletin)
        except BulletinPaie.BulletinVerrouille as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        bulletin.refresh_from_db()
        data = self.get_serializer(bulletin).data
        data['regularisation_ir_delta'] = str(delta)
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marquer-paye')
    def marquer_paye(self, request, pk=None):
        """Marque le bulletin comme payé (décompte espèces/chèque, XPAI9)."""
        bulletin = self.get_object()
        marquer_bulletin_paye(bulletin)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='analyse')
    def analyse(self, request):
        """Rapport d'analyse de paie pivot rubrique/département × mois (ZPAI1).

        Paramètres requis ``debut``/``fin`` au format ``YYYY-MM`` (fenêtre
        inclusive). ``?group_by=rubrique`` (défaut) ou ``?group_by=
        departement``. ``?export=csv`` renvoie le CSV (une colonne par mois)
        au lieu du JSON.
        """
        debut = request.query_params.get('debut', '')
        fin = request.query_params.get('fin', '')
        group_by = request.query_params.get('group_by', 'rubrique')
        try:
            annee_debut, mois_debut = (int(x) for x in debut.split('-'))
            annee_fin, mois_fin = (int(x) for x in fin.split('-'))
        except (ValueError, AttributeError):
            return Response(
                {'detail': 'Paramètres "debut"/"fin" requis (format '
                 'YYYY-MM).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            data = paie_selectors.analyse_paie(
                request.user.company, annee_debut, mois_debut,
                annee_fin, mois_fin, group_by=group_by)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if request.query_params.get('export') == 'csv':
            return self._export_analyse_csv(data)
        return Response(data, status=status.HTTP_200_OK)

    @staticmethod
    def _export_analyse_csv(data):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([data['group_by'].capitalize()] + data['mois'] + ['Total'])
        for ligne in data['lignes']:
            row = [ligne['libelle']]
            for mois_iso in data['mois']:
                row.append(ligne['totaux_par_mois'].get(mois_iso, ''))
            row.append(ligne['total'])
            writer.writerow(row)
        writer.writerow([])
        writer.writerow(['Total général', '', data['total_general']])
        resp = HttpResponse(
            buffer.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="analyse_paie.csv"'
        return resp

    @action(detail=True, methods=['post'], url_path='rectifier')
    def rectifier(self, request, pk=None):
        """Crée un bulletin RECTIFICATIF ou RAPPEL liant ce bulletin (PAIE36).

        Corps : ``periode_cible`` (id d'une période OUVERTE ≠ origine) requis ;
        ``type_bulletin`` ∈ {rectificatif, rappel} (défaut rectificatif) ;
        ``motif`` facultatif. Le bulletin d'origine reste FIGÉ ; un nouveau
        bulletin recalculé est émis sur la période cible.
        """
        origine = self.get_object()
        periode_id = request.data.get('periode_cible')
        if not periode_id:
            return Response(
                {'detail': 'Champ "periode_cible" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode_cible = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période cible inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            rectif = creer_bulletin_rectificatif(
                origine, periode_cible,
                type_bulletin=request.data.get('type_bulletin'),
                motif=request.data.get('motif', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(rectif).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """Crée un bulletin d'ANNULATION (refund payslip) de ce bulletin (ZPAI4).

        Corps : ``periode_cible`` (id d'une période OUVERTE, même société)
        requis. Recopie chaque ligne de ce bulletin à montant OPPOSÉ, sans
        toucher au bulletin d'origine (qui reste figé). Le bulletin
        d'annulation est renvoyé en brouillon (le valider fige/consolide dans
        le cumul annuel).
        """
        origine = self.get_object()
        periode_id = request.data.get('periode_cible')
        if not periode_id:
            return Response(
                {'detail': 'Champ "periode_cible" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode_cible = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période cible inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            annulation = creer_bulletin_annulation(origine, periode_cible)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(annulation).data,
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='saisies-arret')
    def saisies_arret(self, request, pk=None):
        """Saisies-arrêt/cessions servies par ce bulletin (ZPAI6).

        Lecture seule : relie les lignes ``SAISIE`` du bulletin figé à leur
        ``SaisieArret`` d'origine.
        """
        bulletin = self.get_object()
        resultats = saisies_arret_du_bulletin(bulletin)
        data = [
            {
                'saisie_id': r['saisie'].id if r['saisie'] else None,
                'creancier': r['ligne'].libelle,
                'montant': str(r['montant']),
            }
            for r in resultats
        ]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """Bulletin de paie au format PDF conforme (PAIE34).

        AUD703 — un bulletin VALIDÉ sert son ARCHIVE, jamais un re-rendu :
        l'identité imprimée (n° CNSS, RIB, date de paiement) reste modifiable
        après validation, un re-rendu pourrait donc différer du document
        réellement remis au salarié.
        """
        bulletin = self.get_object()
        try:
            pdf = builders.bulletin_pdf_a_servir(bulletin)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        nom = f'bulletin_{bulletin.periode.annee}_{bulletin.periode.mois:02d}_{bulletin.id}.pdf'
        return _pdf_response(pdf, nom)


class AvanceSalarieViewSet(_PaieBaseViewSet):
    """Avances / prêts salariés (PAIE28) — société scopée, palier paie.

    L'avance se rembourse automatiquement par retenue mensuelle sur le bulletin
    (calcul dans ``calculer_bulletin`` ; imputation effective à la validation du
    bulletin). ``montant_rembourse`` n'est jamais écrit via l'API.
    """
    queryset = AvanceSalarie.objects.select_related('profil').all()
    serializer_class = AvanceSalarieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation', 'id']


class CoffreFortBulletinViewSet(viewsets.ReadOnlyModelViewSet):
    """Coffre-fort des bulletins en self-service employé (PAIE35).

    Accessible à TOUT utilisateur authentifié, mais STRICTEMENT scopé à
    l'utilisateur : un salarié ne voit QUE ses propres bulletins VALIDÉS
    (rapprochés par ``profil.employe.user == request.user``). Il peut consulter
    la liste et télécharger le PDF de chacun, jamais ceux d'un collègue. Aucun
    accès en écriture. Donnée SENSIBLE — la garde est dans ``get_queryset``
    (jamais le ``company`` seul, sinon un employé verrait toute la société).
    """
    permission_classes = [IsAnyRole]
    serializer_class = BulletinPaieSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'periode', 'id']

    def get_queryset(self):
        user = self.request.user
        # Scopé à l'employé rattaché à CE compte utilisateur (OneToOne
        # rh.DossierEmploye.user), via la relation existante ProfilPaie.employe.
        # Seuls les bulletins VALIDÉS (figés) sont exposés au salarié.
        return (
            BulletinPaie.objects
            .filter(
                profil__employe__user=user,
                statut=BulletinPaie.STATUT_VALIDE,
            )
            .select_related('periode', 'profil')
            .prefetch_related('lignes')
        )

    def retrieve(self, request, *args, **kwargs):
        """XPAI21 — la consultation du détail pose l'accusé de lecture."""
        bulletin = self.get_object()
        marquer_bulletin_lu(bulletin)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """PDF du bulletin de l'employé (self-service, PAIE35).

        XPAI21 — le téléchargement pose aussi l'accusé de lecture (première
        consultation, jamais réécrit).
        """
        bulletin = self.get_object()  # déjà scopé à l'utilisateur
        marquer_bulletin_lu(bulletin)
        try:
            # AUD703 — le salarié retélécharge TOUJOURS l'archive de ce qui lui
            # a été remis, jamais un re-rendu (qui pourrait avoir changé).
            pdf = builders.bulletin_pdf_a_servir(bulletin)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        nom = f'bulletin_{bulletin.periode.annee}_{bulletin.periode.mois:02d}.pdf'
        return _pdf_response(pdf, nom)


class OrdreVirementViewSet(_PaieVoirOuGerer, TenantMixin,
                           viewsets.ReadOnlyModelViewSet):
    """Ordres de virement des salaires (PAIE30) — lecture seule + actions.

    L'ordre se construit/regénère par ``generer`` (depuis les bulletins validés
    d'une période), se fige par ``emettre``, et le fichier banque s'obtient par
    ``fichier``. Société scopée, ``paie_voir``/``paie_gerer`` (XPAI7).
    """
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent
    queryset = OrdreVirement.objects.select_related('periode').prefetch_related(
        'lignes').all()
    serializer_class = OrdreVirementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'periode', 'id']

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """Génère (ou régénère) l'ordre de virement d'une période (PAIE30).

        Corps : ``periode`` (id) requis ; ``date_execution`` / ``rib_emetteur``
        / ``compte_emetteur`` (id `compta.CompteTresorerie`, DC20) facultatifs.
        Un compte émetteur fourni dérive le RIB + la devise du référentiel
        trésorerie (source unique). Un ordre déjà ÉMIS ne peut être régénéré
        (400).
        """
        periode_id = request.data.get('periode')
        if not periode_id:
            return Response(
                {'detail': 'Champ "periode" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            periode = PeriodePaie.objects.get(
                pk=periode_id, company=request.user.company)
        except (PeriodePaie.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Période inconnue.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            ordre = generer_ordre_virement(
                periode,
                date_execution=request.data.get('date_execution') or None,
                rib_emetteur=request.data.get('rib_emetteur', ''),
                compte_emetteur=request.data.get('compte_emetteur') or None)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = self.get_serializer(ordre).data
        # AUD710 — remonte l'avertissement « paramètres sociaux non validés »
        # au client : l'ordre engage de l'argent réel.
        avertissements = avertissements_parametre_paie(
            periode.company, date(periode.annee, periode.mois, 1),
            contexte='Ordre de virement')
        if avertissements:
            data = {**data, 'avertissements': avertissements}
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='emettre')
    def emettre(self, request, pk=None):
        """Émet l'ordre de virement → fige l'ordre (PAIE30)."""
        ordre = self.get_object()
        emettre_ordre_virement(ordre)
        return Response(
            self.get_serializer(ordre).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='payer')
    def payer(self, request, pk=None):
        """Poste l'écriture de règlement de l'OV (débit 4432, YLEDG7).

        Corps : ``compte_tresorerie`` (id `compta.CompteTresorerie`,
        requis) ; ``date_reglement`` facultative (défaut aujourd'hui).
        Idempotent — rejouer renvoie la même écriture.
        """
        ordre = self.get_object()
        compte_id = request.data.get('compte_tresorerie')
        if not compte_id:
            return Response(
                {'detail': 'Champ "compte_tresorerie" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = payer_ordre_virement(
                ordre, compte_id,
                date_reglement=request.data.get('date_reglement') or None,
                created_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'ordre': self.get_serializer(ordre).data,
                'ecriture_id': ecriture.id if ecriture else None,
            },
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='fichier')
    def fichier(self, request, pk=None):
        """Renvoie le fichier de virement banque (lignes + total, PAIE30).

        XPAI8 — ``?format_banque=simt`` renvoie le format bancaire marocain
        SIMT (longueurs fixes) au lieu du CSV/JSON générique par défaut.
        """
        ordre = self.get_object()
        try:
            if request.query_params.get('format_banque') == 'simt':
                fichier = fichier_virement_paie_simt(ordre)
            else:
                fichier = fichier_virement_paie(ordre)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(fichier, status=status.HTTP_200_OK)


class LigneVirementViewSet(_PaieVoirOuGerer, TenantMixin,
                           viewsets.ReadOnlyModelViewSet):
    """Lignes d'ordre de virement (PAIE30) — suivi des rejets (XPAI9).

    Lecture seule + actions ``rejeter`` (marque un RIB invalide, jamais de
    suppression) et ``reemettre`` (crée une ligne corrigée liée via
    ``ligne_correction``). ``paie_voir``/``paie_gerer``.
    """
    queryset = LigneVirement.objects.select_related('ordre', 'bulletin').all()
    serializer_class = LigneVirementSerializer

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """Marque la ligne comme rejetée (RIB invalide, XPAI9)."""
        ligne = self.get_object()
        rejeter_ligne_virement(ligne, motif=request.data.get('motif', ''))
        return Response(
            self.get_serializer(ligne).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reemettre')
    def reemettre(self, request, pk=None):
        """Réémet une ligne rejetée avec un RIB corrigé (XPAI9)."""
        ligne = self.get_object()
        nouveau_rib = request.data.get('rib')
        try:
            nouvelle = reemettre_ligne_virement(
                ligne, nouveau_rib=nouveau_rib)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(nouvelle).data, status=status.HTTP_201_CREATED)


class SaisieArretViewSet(_PaieBaseViewSet):
    """Saisies-arrêts / cessions sur salaire (PAIE29) — société scopée, palier paie.

    La retenue est plafonnée à la quotité saisissable du net (calcul dans
    ``calculer_bulletin`` ; imputation effective à la validation du bulletin).
    ``montant_retenu`` n'est jamais écrit via l'API.
    """
    queryset = SaisieArret.objects.select_related('profil').all()
    serializer_class = SaisieArretSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'prioritaire', 'date_creation', 'id']

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """Annule la saisie — stoppe les retenues futures, historique intact (ZPAI6).

        Corps : ``motif`` facultatif. Refuse une saisie déjà soldée
        (``400``) ; annuler une saisie déjà annulée est un no-op.
        """
        saisie = self.get_object()
        try:
            saisie = annuler_saisie_arret(
                saisie, motif=request.data.get('motif', ''))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(saisie).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='creer-lot')
    def creer_lot(self, request):
        """Éclate une saisie en N fiches individuelles, une par profil (ZPAI7).

        Corps : ``profils`` (liste d'ids, même société), ``montant_total``,
        ``montant_echeance`` (facultatif), ``date_debut`` (YYYY-MM-DD),
        ``creancier``/``reference``/``type``/``prioritaire`` (facultatifs),
        ``cle_lot`` (requis — identifiant STABLE fourni par l'appelant pour
        l'idempotence : un re-run avec la même clé ne duplique rien).
        """
        profil_ids = request.data.get('profils') or []
        cle_lot = request.data.get('cle_lot')
        if not profil_ids or not cle_lot:
            return Response(
                {'detail': 'Champs "profils" (liste) et "cle_lot" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        profils = ProfilPaie.objects.filter(
            company=request.user.company, id__in=profil_ids)
        if profils.count() != len(set(profil_ids)):
            return Response(
                {'detail': "Un ou plusieurs profils sont introuvables ou "
                           "d'une autre société."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            date_debut = date.fromisoformat(request.data.get('date_debut'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Champ "date_debut" requis (format YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST)
        # ZPAI7 — le corps JSON envoie des montants en chaîne : converties en
        # Decimal ICI (jamais laissées telles quelles), sinon l'instance
        # créée porte un ``str`` en mémoire et les propriétés dérivées
        # (``solde_restant``) lèvent un TypeError str/Decimal à la
        # sérialisation de la réponse.
        try:
            montant_total = Decimal(str(request.data.get('montant_total')))
        except (InvalidOperation, TypeError):
            return Response(
                {'detail': 'Champ "montant_total" requis (nombre).'},
                status=status.HTTP_400_BAD_REQUEST)
        montant_echeance_brut = request.data.get('montant_echeance')
        try:
            montant_echeance = (
                Decimal(str(montant_echeance_brut))
                if montant_echeance_brut not in (None, '') else None)
        except InvalidOperation:
            return Response(
                {'detail': 'Champ "montant_echeance" invalide (nombre).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            saisies = creer_saisies_arret_lot(
                request.user.company, profils,
                type_saisie=request.data.get('type'),
                montant_total=montant_total,
                montant_echeance=montant_echeance,
                date_debut=date_debut,
                creancier=request.data.get('creancier', ''),
                reference=request.data.get('reference', ''),
                prioritaire=bool(request.data.get('prioritaire', False)),
                cle_lot=cle_lot,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(saisies, many=True).data,
            status=status.HTTP_200_OK)


class CumulAnnuelViewSet(_PaieVoirOuGerer, TenantMixin,
                         viewsets.ReadOnlyModelViewSet):
    """Cumuls annuels de paie par employé (PAIE27) — lecture seule.

    Le cumul est un agrégat MATÉRIALISÉ recalculé depuis les bulletins validés
    via l'action ``recalculer`` (corps : ``profil`` id, ``annee``). Jamais saisi
    directement. Société scopée, ``paie_voir``/``paie_gerer`` (XPAI7, donnée
    SENSIBLE).
    """
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent
    queryset = CumulAnnuel.objects.select_related('profil').all()
    serializer_class = CumulAnnuelSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['annee', 'profil', 'date_calcul', 'id']

    @extend_schema(responses=inline_serializer('PaieRegistreRemunerations', {
        'annee': serializers.IntegerField(),
        'nombre_salaries': serializers.IntegerField(),
        'lignes': serializers.ListField(child=serializers.DictField()),
        'totaux': serializers.DictField(),
    }))
    @action(detail=False, methods=['get'], url_path='registre-remunerations')
    def registre_remunerations(self, request):
        """Registre ANNUEL des rémunérations (NTPAY20, obligation légale).

        Paramètre ``annee`` requis. Une ligne par salarié rémunéré dans
        l'année, avec ses cumuls brut / CNSS / AMO / IR / net lus tels quels
        dans ``CumulAnnuel`` — jamais recalculés ici. ``?export=pdf`` imprime
        le document de contrôle (inspection du travail). Gate ``paie_voir``.
        """
        try:
            annee = int(request.query_params.get('annee'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Paramètre "annee" requis (et valide).'},
                status=status.HTTP_400_BAD_REQUEST)
        registre = builders.registre_remunerations_context(
            request.user.company, annee)
        if request.query_params.get('export') == 'pdf':
            try:
                pdf = builders.render_registre_remunerations_pdf(
                    request.user.company, annee, registre=registre)
            except RuntimeError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return _pdf_response(
                pdf, f'registre_remunerations_{annee}.pdf')
        return Response(registre, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='recalculer')
    def recalculer(self, request):
        """Recalcule le cumul annuel d'un profil pour une année (PAIE27).

        Corps : ``profil`` (id) et ``annee`` requis. Agrège les bulletins
        validés de l'année. Idempotent.
        """
        profil_id = request.data.get('profil')
        annee = request.data.get('annee')
        if not profil_id or not annee:
            return Response(
                {'detail': 'Champs "profil" et "annee" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            profil = ProfilPaie.objects.get(
                pk=profil_id, company=request.user.company)
            annee = int(annee)
        except (ProfilPaie.DoesNotExist, ValueError, TypeError):
            return Response(
                {'detail': 'Profil ou année invalide.'},
                status=status.HTTP_404_NOT_FOUND)
        cumul = recalculer_cumul_annuel(profil, annee)
        return Response(
            self.get_serializer(cumul).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reprise-dry-run',
            parser_classes=[MultiPartParser, FormParser])
    def reprise_dry_run(self, request):
        """Aperçu de l'import de reprise des cumuls (XPAI22, go-live).

        Corps multipart : ``file`` (CSV/XLSX). Signale les matricules
        inconnus AVANT tout commit. Ne modifie rien.
        """
        f = request.FILES.get('file')
        if f is None:
            return Response(
                {'detail': 'Aucun fichier fourni.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = dry_run_reprise_cumuls(
                f.read(), f.name, request.user.company)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reprise-commit',
            parser_classes=[MultiPartParser, FormParser])
    def reprise_commit(self, request):
        """Commit de l'import de reprise des cumuls (XPAI22, go-live).

        Corps multipart : ``file`` (CSV/XLSX). Crée/complète les cumuls sans
        JAMAIS écraser un cumul déjà calculé depuis de vrais bulletins
        validés.
        """
        f = request.FILES.get('file')
        if f is None:
            return Response(
                {'detail': 'Aucun fichier fourni.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            resultat = commit_reprise_cumuls(
                f.read(), f.name, request.user.company)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat, status=status.HTTP_200_OK)


class EcheanceDeclarativeViewSet(_PaieVoirOuGerer, TenantMixin,
                                 viewsets.ModelViewSet):
    """Échéances déclaratives paie (XPAI6) — générées automatiquement.

    Lecture + modification du ``statut`` uniquement (progression manuelle du
    traitement réel d'une déclaration : générée → déposée → payée). Les
    champs ``periode``/``type_echeance``/``date_limite`` sont posés par le
    générateur (``services.generer_echeances_periode``) et restent en
    lecture seule côté API. ``paie_voir``/``paie_gerer`` (XPAI7).

    L'action ``payer`` (YLEDG7) poste l'écriture de règlement de l'organisme
    (débit 4441/4452/4443, crédit trésorerie) et marque PAYÉES toutes les
    échéances du même organisme sur la période — un ``patch`` manuel de
    ``statut`` reste possible mais ne poste jamais d'écriture.
    """
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent
    queryset = EcheanceDeclarative.objects.select_related('periode').all()
    serializer_class = EcheanceDeclarativeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_limite', 'periode', 'id']
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    # Mappe ``type_echeance`` (modèle) au code ``organisme`` attendu par
    # ``services.payer_organismes`` (codes de ``_ORGANISMES_CHARGES``).
    _ORGANISME_PAR_TYPE = {
        EcheanceDeclarative.TYPE_BDS: 'cnss_amo',
        EcheanceDeclarative.TYPE_IR_MENSUEL: 'ir',
        EcheanceDeclarative.TYPE_CIMR: 'cimr',
    }

    @action(detail=True, methods=['post'], url_path='payer')
    def payer(self, request, pk=None):
        """Poste le règlement de l'organisme de cette échéance (YLEDG7).

        Corps : ``compte_tresorerie`` (id, requis), ``date_reglement``
        facultative. Solde 4441/4452/4443 pour TOUTES les échéances du même
        organisme sur la période (idempotent — déjà payée = ignorée).
        """
        echeance = self.get_object()
        organisme = self._ORGANISME_PAR_TYPE.get(echeance.type_echeance)
        if organisme is None:
            return Response(
                {'detail': (
                    "Cette échéance (état 9421 annuel) n'a pas de règlement "
                    "GL dédié.")},
                status=status.HTTP_400_BAD_REQUEST)
        compte_id = request.data.get('compte_tresorerie')
        if not compte_id:
            return Response(
                {'detail': 'Champ "compte_tresorerie" requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            ecriture = payer_organismes(
                echeance.periode, organisme, compte_id,
                date_reglement=request.data.get('date_reglement') or None,
                created_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        echeance.refresh_from_db()
        return Response(
            {
                'echeance': self.get_serializer(echeance).data,
                'ecriture_id': ecriture.id if ecriture else None,
            },
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['get', 'post'], url_path='depots',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def depots(self, request, pk=None):
        """Registre des dépôts déclaratifs de cette échéance (NTPAY5).

        ``GET`` liste les dépôts (preuves) déjà enregistrés.

        ``POST`` enregistre un dépôt et bascule l'échéance en « déposée » :
        ``reference_depot``, ``date_depot`` (défaut aujourd'hui),
        ``montant_declare``, ``statut`` (``depose``/``accepte``/``rejete``),
        ``motif_rejet`` (REQUIS si rejeté), et l'accusé lui-même soit en
        multipart (champ ``fichier``, PDF/PNG/JPEG/WebP), soit par une clé
        déjà stockée (``fichier_key``). Un dépôt REJETÉ n'avance jamais
        l'échéance.
        """
        echeance = self.get_object()
        if request.method == 'GET':
            return Response(
                DepotDeclaratifSerializer(
                    echeance.depots.all(), many=True).data,
                status=status.HTTP_200_OK)

        fichier_key = request.data.get('fichier_key') or ''
        fichier = request.FILES.get('fichier')
        if fichier is not None:
            from apps.records.storage import store_attachment  # app socle

            stocke, erreur = store_attachment(
                fichier, company=request.user.company)
            if erreur:
                raise DRFValidationError({'fichier': [erreur]})
            fichier_key = stocke['file_key']

        date_depot = request.data.get('date_depot') or None
        if date_depot:
            date_depot = parse_date(str(date_depot))
            if date_depot is None:
                raise DRFValidationError({'date_depot': [
                    'Date invalide : attendu AAAA-MM-JJ.']})
        montant = request.data.get('montant_declare')
        try:
            montant = Decimal(str(montant)) if montant not in (None, '') \
                else None
        except (InvalidOperation, ValueError):
            raise DRFValidationError({'montant_declare': [
                'Montant invalide.']})

        try:
            depot = enregistrer_depot_declaratif(
                echeance,
                date_depot=date_depot,
                reference_depot=request.data.get('reference_depot') or '',
                fichier_key=fichier_key,
                montant_declare=montant,
                statut=request.data.get('statut') or None,
                motif_rejet=request.data.get('motif_rejet') or '',
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, 'message_dict')
                else {'detail': exc.messages})
        echeance.refresh_from_db()
        return Response({
            'depot': DepotDeclaratifSerializer(depot).data,
            'echeance': self.get_serializer(echeance).data,
        }, status=status.HTTP_201_CREATED)
