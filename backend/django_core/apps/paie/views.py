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

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
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
    PeriodePaie,
    ProfilPaie,
    RegimeMutuelle,
    Rubrique,
    RubriqueEmploye,
    SaisieArret,
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
    EcheanceDeclarativeSerializer,
    ElementVariableSerializer,
    LigneVirementSerializer,
    ParametrePaieSerializer,
    PeriodePaieSerializer,
    OrdreVirementSerializer,
    ProfilPaieSerializer,
    RegimeMutuelleSerializer,
    RubriqueEmployeSerializer,
    RubriqueSerializer,
    SaisieArretSerializer,
    StructurePaieSerializer,
    TypeEntreePonctuelleSerializer,
)
from .services import (
    TransitionPeriodeInterdite,
    annuler_saisie_arret,
    appliquer_structure_a_profil,
    attestation_salaire_ij_cnss,
    bareme_en_vigueur,
    brut_pour_net_cible,
    avertissements_periode,
    calculer_bulletin,
    changer_statut,
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
    deposer_bds_complementaire,
    deposer_bds_principal,
    dry_run_reprise_cumuls,
    emettre_ordre_virement,
    ensure_defaults,
    ensure_types_entree_ponctuelle_standard,
    ensure_rubriques_defaut,
    ensure_rubriques_standard,
    ensure_structures_standard,
    etat_des_charges,
    expirer_regimes_echus,
    etat_ir_9421,
    etat_ir_9421_annuel,
    export_xml_simpl_ir_9421,
    fichier_cimr,
    fichier_damancom_cnss,
    fichier_damancom_strict,
    fichier_virement_paie,
    fichier_virement_paie_simt,
    generer_bulletin,
    generer_bulletin_stc,
    generer_echeances_periode,
    generer_ordre_virement,
    generer_run_gratification,
    historique_carriere,
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
    rejeter_ligne_virement,
    saisies_arret_du_bulletin,
    simuler_bulletin,
    synchroniser_salaire,
    valider_bulletin,
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


class ParametrePaieViewSet(_PaieBaseViewSet):
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


class BaremeIRViewSet(_PaieBaseViewSet):
    """Barèmes IR versionnés et leurs tranches (PAIE4)."""
    queryset = BaremeIR.objects.prefetch_related('tranches').all()
    serializer_class = BaremeIRSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['date_effet', 'id']


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

    ``OneToOne`` vers ``rh.DossierEmploye`` ; le salaire de base est SENSIBLE
    (jamais exposé côté client). ``company`` posée côté serveur.
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

    @action(detail=True, methods=['get'], url_path='stc-pdf')
    def stc_pdf(self, request, pk=None):
        """Reçu pour solde de tout compte au format PDF (XPAI1).

        Sert le dernier bulletin STC du profil (peu importe son statut —
        brouillon consultable avant validation, comme un aperçu).
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
        try:
            pdf = builders.render_stc_pdf(bulletin)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return _pdf_response(pdf, f'stc_{profil.id}.pdf')

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
        try:
            cloturer_periode_paie(
                periode, valider_brouillons=bool(valider))
        except TransitionPeriodeInterdite as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(periode).data, status=status.HTTP_200_OK)

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
        """État consolidé des charges sociales par organisme (XPAI5).

        ``?export=csv`` renvoie le fichier CSV au lieu du JSON.
        """
        periode = self.get_object()
        data = etat_des_charges(periode)
        if request.query_params.get('export') == 'csv':
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
        """Passe l'écriture du journal de paie AVEC ventilation analytique (XPAI17)."""
        periode = self.get_object()
        ecriture = journal_de_paie_ventile(periode, created_by=request.user)
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
        """Valide le bulletin → fige le snapshot (immuable, PAIE17)."""
        bulletin = self.get_object()
        valider_bulletin(bulletin)
        return Response(
            self.get_serializer(bulletin).data, status=status.HTTP_200_OK)

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
        """Bulletin de paie au format PDF conforme (PAIE34)."""
        bulletin = self.get_object()
        try:
            pdf = builders.render_bulletin_pdf(bulletin)
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
            pdf = builders.render_bulletin_pdf(bulletin)
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
        return Response(
            self.get_serializer(ordre).data, status=status.HTTP_200_OK)

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
        try:
            saisies = creer_saisies_arret_lot(
                request.user.company, profils,
                type_saisie=request.data.get('type'),
                montant_total=request.data.get('montant_total'),
                montant_echeance=request.data.get('montant_echeance'),
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
