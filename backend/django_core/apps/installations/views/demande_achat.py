"""Vues FG310 — demande d'achat (réquisition) → approbation.

``DemandeAchatViewSet`` : CRUD des réquisitions d'achat chantier + cycle de vie
(``soumettre`` / ``approuver`` / ``refuser`` / ``marquer_commandee``).
``DemandeAchatLigneViewSet`` : CRUD des lignes (produit catalogue OU désignation
libre). Lecture tout rôle, écriture responsable/admin ; APPROBATION réservée
responsable/admin (FG310 : la réquisition doit être approuvée avant de devenir un
BCF). Multi-tenant via ``TenantMixin`` : référence/société/created_by posés côté
serveur ; les FK liées (chantier/programme/fournisseur_suggere) sont validées
tenant. Cross-app : ``stock.Fournisseur`` / ``stock.Produit`` en string-FK.

SCA36 — pilote 3 du kit ``core.documents`` (dégradation gracieuse sans totaux).
Le viewset gagne le chatter générique ARC8 (``ChatterViewSetMixin`` :
``chatter/historique`` GET tout rôle + ``chatter/noter`` POST
responsable/admin) ; la numérotation passe EXPLICITEMENT par la primitive du
kit ``core.numbering`` (le shim ``apps.ventes.utils.references`` en était déjà
le ré-export bit-identique — format ``DA-YYYYMM-NNNN`` inchangé). Les actions
d'approbation et leurs gardes restent STRICTEMENT inchangées (moteur propre,
chemin ARC10 nommé) ; aucun PDF (document d'approbation interne).
"""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.numbering import create_with_reference
from core.viewsets import CompanyScopedModelViewSet

from apps.records.views import ChatterViewSetMixin

from ..models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)
from ..serializers import (
    DemandeAchatSerializer, DemandeAchatLigneSerializer,
    EtapeApprobationAchatSerializer, RegleApprobationAchatSerializer,
)

# SCA36 — 'chatter_historique' est une lecture (patron flotte : le
# get_permissions maison prime sur les permission_classes d'@action du mixin).
READ_ACTIONS = ['list', 'retrieve', 'chatter_historique',
                'etapes_approbation']


def _check_tenant(serializer, company, field):
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


def _notifier_demandeur_decision(da, approuvee):
    """VX213 (c) — bord RETOUR : notifie le DEMANDEUR (``created_by``) de la
    décision d'approbation de sa réquisition (motif inclus si refus).

    Best-effort (ne lève jamais) : émettre la notification ne doit jamais
    casser la transition d'approbation. No-op si aucun demandeur. Le corps
    reste CLIENT-SAFE — aucun montant (jamais dérivé de ``prix_achat``) : la
    décision porte sur la référence + l'objet, pas sur un prix d'achat interne.
    La société est celle de la DA (jamais issue d'une requête)."""
    demandeur = getattr(da, 'created_by', None)
    if demandeur is None or not getattr(demandeur, 'pk', None):
        return
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        if approuvee:
            titre = f"Demande d'achat approuvée — {da.reference}"
            corps = f"Votre demande « {da.objet} » ({da.reference}) a été approuvée."
        else:
            titre = f"Demande d'achat refusée — {da.reference}"
            corps = f"Votre demande « {da.objet} » ({da.reference}) a été refusée."
            if da.motif_refus:
                corps += f" Motif : {da.motif_refus}"
        notify(
            demandeur, EventType.DA_DECIDEE, titre, body=corps,
            link=f'/installations/demandes-achat?demande={da.pk}',
            company=da.company)
    except Exception:  # pragma: no cover - défensif
        pass


class DemandeAchatViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """FG310 — réquisitions d'achat. Lecture tout rôle, écriture
    responsable/admin. Référence anti-collision + société + `created_by` posés
    serveur ; chantier/programme/fournisseur_suggere validés tenant. Filtrable
    par `statut`, `chantier`, `programme`. Cycle de vie via les actions.
    SCA36 — chatter générique (`chatter/historique`, `chatter/noter`) via le
    kit ; approbations inchangées."""
    queryset = DemandeAchat.objects.select_related(
        'chantier', 'programme', 'fournisseur_suggere',
        'approuvee_par', 'created_by').prefetch_related('lignes').all()
    serializer_class = DemandeAchatSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('statut', 'statut'),
                         ('chantier', 'chantier_id'),
                         ('programme', 'programme_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs

    def _check_all_tenant(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'chantier')
        _check_tenant(serializer, company, 'programme')
        _check_tenant(serializer, company, 'fournisseur_suggere')

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_all_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(DemandeAchat, 'DA', company, _save)

    def perform_update(self, serializer):
        self._check_all_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        """FG310 — soumet la demande pour approbation (brouillon → soumise).

        NTP2P2 — instancie en outre le plan d'approbation (N étapes
        séquentielles) si une ``RegleApprobationAchat`` active couvre le
        montant estimé. Sans règle : aucune étape, comportement historique.

        NTP2P4 — contrôle budgétaire départemental AVANT tout changement
        d'état : si le budget restant du département du demandeur ne couvre
        pas la demande, la soumission est refusée (400) — sauf dérogation
        autorisée par la règle d'approbation. Inactif par défaut."""
        from .. import services

        da = self.get_object()
        if da.statut not in (DemandeAchat.Statut.BROUILLON,
                             DemandeAchat.Statut.SOUMISE):
            return Response(
                {'detail': "Seule une demande brouillon peut être soumise."},
                status=status.HTTP_400_BAD_REQUEST)
        regle = services.resoudre_regle_approbation_achat(da)
        try:
            services.controler_budget_demande_achat(da, regle=regle)
        except services.BudgetAchatError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save(update_fields=['statut', 'date_modification'])
        services.lancer_workflow_approbation_achat(da, regle=regle)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['get'], url_path='etapes-approbation')
    def etapes_approbation(self, request, pk=None):
        """NTP2P2 — plan d'approbation de la demande (étapes séquentielles)."""
        da = self.get_object()
        etapes = da.etapes_approbation.select_related(
            'approbateur', 'regle').order_by('niveau', 'id')
        return Response(EtapeApprobationAchatSerializer(etapes, many=True).data)

    @action(detail=True, methods=['post'], url_path='approuver-etape')
    def approuver_etape(self, request, pk=None):
        """NTP2P2 — approuve l'étape courante du plan d'approbation. Quand la
        DERNIÈRE étape est validée, la demande bascule ``approuvee``."""
        from .. import services
        return self._decider_etape(request, services.approuver_etape_achat)

    @action(detail=True, methods=['post'], url_path='rejeter-etape')
    def rejeter_etape(self, request, pk=None):
        """NTP2P2 — rejette l'étape courante : la demande bascule ``refusee``
        et les étapes restantes sont annulées."""
        from .. import services
        return self._decider_etape(request, services.rejeter_etape_achat)

    def _decider_etape(self, request, operation):
        """Résout l'étape visée (corps ``etape``, sinon la prochaine en
        attente), SCOPÉE à la demande courante, puis applique la décision."""
        from .. import services

        da = self.get_object()
        etape_id = request.data.get('etape')
        if etape_id:
            etape = da.etapes_approbation.filter(pk=etape_id).first()
            if etape is None:
                return Response(
                    {'detail': 'Étape inconnue pour cette demande.'},
                    status=status.HTTP_404_NOT_FOUND)
        else:
            etape = services.prochaine_etape_approbation_achat(da)
            if etape is None:
                return Response(
                    {'detail': "Aucune étape d'approbation en attente."},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            operation(etape, approbateur=request.user,
                      commentaire=request.data.get('commentaire') or '')
        except services.ApprobationAchatError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        da.refresh_from_db()
        if da.statut in (DemandeAchat.Statut.APPROUVEE,
                         DemandeAchat.Statut.REFUSEE):
            _notifier_demandeur_decision(
                da, approuvee=da.statut == DemandeAchat.Statut.APPROUVEE)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        """FG310 — approuve la demande (soumise → approuvée), prérequis avant
        transformation en BCF. Trace l'approbateur + la date.

        NTP2P2 — refusée tant qu'une étape du plan d'approbation reste en
        attente : la demande ne passe ``approuvee`` que quand TOUTES les étapes
        requises sont validées (via ``approuver-etape``)."""
        from .. import services

        da = self.get_object()
        if da.statut != DemandeAchat.Statut.SOUMISE:
            return Response(
                {'detail': "Seule une demande soumise peut être approuvée."},
                status=status.HTTP_400_BAD_REQUEST)
        if services.workflow_approbation_achat_actif(da):
            return Response(
                {'detail': "Un plan d'approbation est en cours : validez les "
                           "étapes via « approuver-etape »."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.APPROUVEE
        da.approuvee_par = request.user
        da.date_decision = timezone.now()
        da.motif_refus = None
        da.save(update_fields=['statut', 'approuvee_par', 'date_decision',
                               'motif_refus', 'date_modification'])
        _notifier_demandeur_decision(da, approuvee=True)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """FG310 — refuse la demande (soumise → refusée) avec un motif."""
        from .. import services

        da = self.get_object()
        if da.statut != DemandeAchat.Statut.SOUMISE:
            return Response(
                {'detail': "Seule une demande soumise peut être refusée."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.REFUSEE
        da.approuvee_par = request.user
        da.date_decision = timezone.now()
        da.motif_refus = (request.data.get('motif_refus') or '').strip() or None
        da.save(update_fields=['statut', 'approuvee_par', 'date_decision',
                               'motif_refus', 'date_modification'])
        # NTP2P2 — un refus direct annule les étapes encore en attente (pas
        # de plan d'approbation orphelin sur une demande refusée).
        da.etapes_approbation.filter(
            statut=EtapeApprobationAchat.Statut.EN_ATTENTE
        ).update(statut=EtapeApprobationAchat.Statut.REJETE,
                 decision_le=timezone.now())
        # NTP2P4 — l'enveloppe budgétaire engagée est rendue.
        services.liberer_budget_demande_achat(da)
        _notifier_demandeur_decision(da, approuvee=False)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'])
    def marquer_commandee(self, request, pk=None):
        """FG310 — marque la demande comme commandée (approuvée → commandée),
        une fois le BCF émis. Garde : seule une demande APPROUVÉE peut l'être."""
        da = self.get_object()
        if da.statut != DemandeAchat.Statut.APPROUVEE:
            return Response(
                {'detail': "Seule une demande approuvée peut être marquée "
                           "commandée."},
                status=status.HTTP_400_BAD_REQUEST)
        da.statut = DemandeAchat.Statut.COMMANDEE
        da.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'], url_path='generer-bcf')
    def generer_bcf(self, request, pk=None):
        """YPROC5 — convertit les lignes de la DA APPROUVÉE en BCF brouillon
        chez le fournisseur choisi (corps, défaut `fournisseur_suggere`).
        Idempotent : une DA déjà commandée avec un BCF lié est refusée."""
        from django.apps import apps as django_apps
        from apps.stock.services import creer_bcf_depuis_lignes

        da = self.get_object()
        if da.statut != DemandeAchat.Statut.APPROUVEE:
            return Response(
                {'detail': "Seule une demande approuvée peut générer un BCF."},
                status=status.HTTP_400_BAD_REQUEST)
        if da.bon_commande_id:
            return Response(
                {'detail': 'Cette demande a déjà un BCF lié.'},
                status=status.HTTP_400_BAD_REQUEST)

        fournisseur_id = request.data.get('fournisseur') or (
            da.fournisseur_suggere_id)
        if not fournisseur_id:
            return Response(
                {'detail': 'Aucun fournisseur (ni suggéré, ni fourni).'},
                status=status.HTTP_400_BAD_REQUEST)
        fournisseur_model = django_apps.get_model('stock', 'Fournisseur')
        fournisseur = fournisseur_model.objects.filter(
            id=fournisseur_id, company=request.user.company).first()
        if fournisseur is None:
            return Response(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'},
                status=status.HTTP_400_BAD_REQUEST)

        lignes_source = list(da.lignes.select_related('produit').all())
        # XPUR16 — les lignes sans produit catalogue sont reportées en
        # désignation libre (jamais ignorées : couverture complète de la DA).
        lignes = [
            (ligne.produit_id, ligne.designation or
             (ligne.produit.nom if ligne.produit_id else ''),
             ligne.quantite, ligne.prix_estime)
            for ligne in lignes_source
        ]
        if not lignes:
            return Response(
                {'detail': 'Cette demande ne contient aucune ligne.'},
                status=status.HTTP_400_BAD_REQUEST)

        bon = creer_bcf_depuis_lignes(
            company=request.user.company, user=request.user,
            fournisseur=fournisseur, lignes=lignes,
            note=f'Généré depuis {da.reference}')
        da.bon_commande = bon
        da.statut = DemandeAchat.Statut.COMMANDEE
        da.save(update_fields=['bon_commande', 'statut', 'date_modification'])
        # NTP2P4 — l'engagement devient RÉALISÉ (le BCF est passé).
        from .. import services
        services.consommer_budget_demande_achat(da, bon_commande_id=bon.pk)
        return Response(self.get_serializer(da).data)

    @action(detail=True, methods=['post'], url_path='importer-lignes-csv')
    def importer_lignes_csv(self, request, pk=None):
        """NTP2P40 — Import CSV en masse de ``DemandeAchatLigne``.

        Corps multipart : fichier ``fichier`` (ou ``csv``). Colonnes
        attendues (en-tête, ordre libre) : ``designation``, ``sku``
        (optionnel — résout un produit catalogue de la société),
        ``quantite``, ``prix_estime``. Chaque ligne est validée
        INDÉPENDAMMENT — une ligne invalide est reportée dans ``erreurs``
        SANS bloquer les autres (rapport ligne par ligne, jamais tout ou
        rien). Seule une DA BROUILLON/SOUMISE accepte un import (une DA déjà
        décidée reste figée)."""
        import csv
        import io

        da = self.get_object()
        if da.statut not in (DemandeAchat.Statut.BROUILLON,
                             DemandeAchat.Statut.SOUMISE):
            return Response(
                {'detail': 'Seule une demande brouillon ou soumise accepte '
                           'un import de lignes.'},
                status=status.HTTP_400_BAD_REQUEST)

        fichier = request.FILES.get('fichier') or request.FILES.get('csv')
        if fichier is None:
            return Response(
                {'fichier': "Le fichier 'fichier' est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            texte = fichier.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response(
                {'fichier': 'Encodage invalide (UTF-8 attendu).'},
                status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(texte))
        if reader.fieldnames is None:
            return Response(
                {'fichier': 'Fichier CSV vide ou sans en-tête.'},
                status=status.HTTP_400_BAD_REQUEST)
        entetes = {(h or '').strip().lower(): h for h in reader.fieldnames}

        from django.apps import apps as django_apps
        produit_model = django_apps.get_model('stock', 'Produit')
        company = request.user.company

        creees = []
        erreurs = []
        for numero, row in enumerate(reader, start=2):  # 1 = en-tête
            def _val(cle):
                col = entetes.get(cle)
                return (row.get(col) or '').strip() if col else ''

            designation = _val('designation')
            sku = _val('sku')
            quantite_brute = _val('quantite')
            prix_brut = _val('prix_estime')

            produit = None
            if sku:
                produit = produit_model.objects.filter(
                    company=company, sku=sku).first()
                if produit is None:
                    erreurs.append(
                        {'ligne': numero,
                         'erreur': f"SKU inconnu pour cette société : {sku}"})
                    continue
            if not designation and produit is None:
                erreurs.append(
                    {'ligne': numero,
                     'erreur': 'Ni désignation ni SKU renseigné.'})
                continue
            try:
                quantite = Decimal(quantite_brute or '0')
                prix_estime = Decimal(prix_brut or '0')
            except InvalidOperation:
                erreurs.append(
                    {'ligne': numero,
                     'erreur': 'Quantité ou prix estimé invalide.'})
                continue
            if quantite <= 0:
                erreurs.append(
                    {'ligne': numero, 'erreur': 'Quantité doit être > 0.'})
                continue

            ligne = DemandeAchatLigne.objects.create(
                demande=da, produit=produit,
                designation=designation or None,
                quantite=quantite, prix_estime=prix_estime)
            creees.append(ligne.id)

        return Response({
            'importees': len(creees),
            'lignes_creees': creees,
            'erreurs': erreurs,
        }, status=status.HTTP_201_CREATED if creees else status.HTTP_200_OK)


class RegleApprobationAchatViewSet(CompanyScopedModelViewSet):
    """NTP2P2 — CRUD des règles d'approbation d'achat (seuil de montant +
    périmètre chantier/programme optionnel). Lecture tout rôle, écriture
    responsable/admin. Société posée serveur ; chantier/programme validés
    tenant. Filtrable par `actif`, `chantier`, `programme`."""
    queryset = RegleApprobationAchat.objects.select_related(
        'chantier', 'programme').all()
    serializer_class = RegleApprobationAchatSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        actif = params.get('actif')
        if actif in ('0', 'false', 'False'):
            qs = qs.filter(actif=False)
        elif actif in ('1', 'true', 'True'):
            qs = qs.filter(actif=True)
        for key, col in (('chantier', 'chantier_id'),
                         ('programme', 'programme_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs

    def _check_all_tenant(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'chantier')
        _check_tenant(serializer, company, 'programme')

    def perform_create(self, serializer):
        self._check_all_tenant(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_all_tenant(serializer)
        super().perform_update(serializer)


class DemandeAchatLigneViewSet(viewsets.ModelViewSet):
    """FG310 — lignes de demande d'achat. La ligne n'a pas de `company` propre :
    le scope société passe par la demande parente (`demande__company`).
    Filtrable par `demande`. Lecture tout rôle, écriture responsable/admin."""
    queryset = DemandeAchatLigne.objects.select_related(
        'demande', 'produit').all()
    serializer_class = DemandeAchatLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(demande__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        demande = self.request.query_params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        demande = serializer.validated_data.get('demande')
        if demande is not None and getattr(
                demande, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'demande': 'Demande inconnue pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
