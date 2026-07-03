"""Vues de la Paie marocaine (toutes scopées société, admin-gated).

La paie est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``).
Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur.
"""
import csv
import io

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import builders

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
)
from .services import (
    TransitionPeriodeInterdite,
    calculer_bulletin,
    changer_statut,
    cloturer_periode_paie,
    creer_bulletin_rectificatif,
    declaration_cnss,
    emettre_ordre_virement,
    ensure_defaults,
    ensure_rubriques_defaut,
    ensure_rubriques_standard,
    etat_des_charges,
    etat_ir_9421,
    etat_ir_9421_annuel,
    fichier_damancom_cnss,
    fichier_virement_paie,
    fichier_virement_paie_simt,
    generer_bulletin,
    generer_bulletin_stc,
    generer_echeances_periode,
    generer_ordre_virement,
    generer_run_gratification,
    importer_elements_rh,
    journal_de_paie,
    livre_de_paie,
    marquer_bulletin_paye,
    notifier_echeances_en_retard,
    profils_hors_virement,
    rapprochement_paie_gl,
    recalculer_cumul_annuel,
    reemettre_ligne_virement,
    rejeter_ligne_virement,
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

    @action(detail=True, methods=['get'], url_path='attestation')
    def attestation(self, request, pk=None):
        """Attestation salaire/travail/domiciliation au format PDF (PAIE34).

        Paramètre de requête ``type`` ∈ {salaire, travail, domiciliation}
        (défaut ``travail``). L'attestation de salaire s'appuie sur le dernier
        bulletin VALIDÉ du profil.
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
        try:
            pdf = builders.render_attestation_pdf(
                type_att, profil, bulletin=bulletin)
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


class RubriqueEmployeViewSet(_PaieBaseViewSet):
    """Rubriques récurrentes par employé (PAIE9) — société scopée."""
    queryset = RubriqueEmploye.objects.select_related(
        'profil', 'rubrique').all()
    serializer_class = RubriqueEmployeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'id']


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

    @action(detail=True, methods=['get'], url_path='fichier-damancom')
    def fichier_damancom(self, request, pk=None):
        """Fichier de télédéclaration CNSS au format DAMANCOM (PAIE31)."""
        periode = self.get_object()
        return Response(
            fichier_damancom_cnss(periode), status=status.HTTP_200_OK)

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

    @action(detail=True, methods=['get'], url_path='hors-virement')
    def hors_virement(self, request, pk=None):
        """Profils réglés hors virement (espèces/chèque) de la période (XPAI9)."""
        periode = self.get_object()
        return Response(
            profils_hors_virement(periode), status=status.HTTP_200_OK)

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

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        """PDF du bulletin de l'employé (self-service, PAIE35)."""
        bulletin = self.get_object()  # déjà scopé à l'utilisateur
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


class EcheanceDeclarativeViewSet(_PaieVoirOuGerer, TenantMixin,
                                 viewsets.ModelViewSet):
    """Échéances déclaratives paie (XPAI6) — générées automatiquement.

    Lecture + modification du ``statut`` uniquement (progression manuelle du
    traitement réel d'une déclaration : générée → déposée → payée). Les
    champs ``periode``/``type_echeance``/``date_limite`` sont posés par le
    générateur (``services.generer_echeances_periode``) et restent en
    lecture seule côté API. ``paie_voir``/``paie_gerer`` (XPAI7).
    """
    permission_classes = [IsResponsableOrAdmin]  # repli si get_permissions absent
    queryset = EcheanceDeclarative.objects.select_related('periode').all()
    serializer_class = EcheanceDeclarativeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_limite', 'periode', 'id']
    http_method_names = ['get', 'patch', 'head', 'options']
