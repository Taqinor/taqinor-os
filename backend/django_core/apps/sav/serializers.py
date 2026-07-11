from datetime import timedelta

from rest_framework import serializers
from django.utils import timezone

from .models import (
    Equipement, Ticket, TicketActivity, PieceConsommee,
    SavSlaSettings, MaintenanceChecklistTemplate, MaintenanceChecklistItem,
    TicketChecklistItem, WarrantyClaim, KbArticle, AlarmeOnduleur,
    TicketSatisfaction, CauseDefaillance, RemedeDefaillance,
    EquipementDowntime, ReleveCompteurEquipement, ReponseType,
    CompatibilitePiece, PieceRetiree, PretEquipement, CategorieTicket,
    EquipeMaintenance, CategorieEquipement, TicketActiviteAFaire,
    WorksheetMaintenanceModele, TicketWorksheet,
)

# Fenêtre « garantie expirant bientôt » (jours).
EXPIRING_SOON_DAYS = 90


class EquipementSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True, default=None)
    produit_marque = serializers.CharField(source='produit.marque', read_only=True, default=None)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True, default=None)
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    client_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    garantie_etat = serializers.SerializerMethodField()
    garantie_jours_restants = serializers.SerializerMethodField()
    # L632 — qui/quand : nom du créateur (les dates sont déjà sérialisées).
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)
    # L629 — référence du ticket SAV qui a remplacé l'appareil (statut remplacé).
    remplace_par_ticket_reference = serializers.CharField(
        source='remplace_par_ticket.reference', read_only=True, default=None)
    # L624 — nombre de tickets SAV ouverts liés à cet équipement.
    nb_tickets_ouverts = serializers.SerializerMethodField()
    # FG90 — nombre de tickets correctifs sur les 12 derniers mois (citron).
    nb_tickets_12m = serializers.SerializerMethodField()
    # XSAV13 — garantie légale de conformité (loi 31-08), calculée.
    date_fin_garantie_legale = serializers.DateField(read_only=True)
    date_fin_garantie_effective = serializers.DateField(read_only=True)
    sous_garantie_legale_seule = serializers.BooleanField(read_only=True)
    # ZMFG2 — catégorie de parc (libellé lecture).
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)

    class Meta:
        model = Equipement
        fields = '__all__'
        # company / dates de garantie / created_by posés côté serveur — jamais
        # depuis le corps. Les dates de garantie sont CALCULÉES (read-only).
        read_only_fields = [
            'company', 'created_by', 'equipement_token', 'public_token',
            'date_fin_garantie', 'date_fin_garantie_production',
            'date_creation', 'date_modification',
        ]
        # L636 — l'unicité (company, numero_serie) est CONDITIONNELLE (séries
        # vides exclues). On désactive le UniqueTogetherValidator auto de DRF
        # (qui rendrait numero_serie obligatoire et casserait une série omise)
        # et on s'appuie sur validate_numero_serie + la contrainte DB.
        validators = []

    def validate_numero_serie(self, value):
        """L636 — unicité du n° de série par société (les vides sont permis).

        Filet au niveau serializer en plus de la contrainte d'unicité DB
        conditionnelle, pour un message FR clair même si la contrainte est
        absente (collision avec des lignes existantes au déploiement)."""
        serie = (value or '').strip()
        if not serie:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        qs = Equipement.objects.filter(
            company=company, numero_serie=serie)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Ce numéro de série existe déjà dans votre société.')
        return value

    def get_nb_tickets_ouverts(self, obj):
        return obj.tickets.filter(
            statut__in=Ticket.OPEN_STATUTS, annule=False).count()

    def get_nb_tickets_12m(self, obj):
        """FG90 — compte les tickets correctifs des 12 derniers mois."""
        since = timezone.localdate() - timedelta(days=365)
        return obj.tickets.filter(
            type=Ticket.Type.CORRECTIF,
            date_creation__date__gte=since,
        ).count()

    def get_client_nom(self, obj):
        # XPOS9 — un équipement vendu au comptoir (sans chantier) porte son
        # client directement via `client_vente` ; sinon dérivé du chantier.
        c = getattr(obj.installation, 'client', None) or obj.client_vente
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_garantie_jours_restants(self, obj):
        if not obj.date_fin_garantie:
            return None
        return (obj.date_fin_garantie - timezone.localdate()).days

    def get_garantie_etat(self, obj):
        """État de garantie : non_renseignee / sous_garantie / expire_bientot /
        hors_garantie. Sert d'indicateur clair côté écran."""
        if not obj.date_fin_garantie:
            return 'non_renseignee'
        jours = (obj.date_fin_garantie - timezone.localdate()).days
        if jours < 0:
            return 'hors_garantie'
        if jours <= EXPIRING_SOON_DAYS:
            return 'expire_bientot'
        return 'sous_garantie'


class TicketActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = TicketActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


# ── ZSAV3 — Activités planifiées à échéance sur le ticket ────────────────────

class TicketActiviteAFaireSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    assigne_nom = serializers.CharField(
        source='assigne.username', read_only=True, default=None)
    en_retard = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketActiviteAFaire
        fields = [
            'id', 'ticket', 'type', 'type_display', 'titre', 'echeance',
            'assigne', 'assigne_nom', 'fait', 'fait_le', 'en_retard',
            'date_creation',
        ]
        read_only_fields = [
            'id', 'ticket', 'fait', 'fait_le', 'date_creation',
        ]


class PieceRetireeSerializer(serializers.ModelSerializer):
    """XMFG10 — pièce retirée (lecture). Aucun prix d'achat exposé côté client."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True, default=None)
    produit_sku = serializers.CharField(
        source='produit.sku', read_only=True, default=None)
    destination_display = serializers.CharField(
        source='get_destination_display', read_only=True)
    # ZMFG8 — typage opérationnel explicite (ajout/retrait/recyclage).
    operation_display = serializers.CharField(
        source='get_operation_display', read_only=True)

    class Meta:
        model = PieceRetiree
        fields = [
            'id', 'produit', 'produit_nom', 'produit_marque', 'produit_sku',
            'quantite', 'numero_serie', 'destination', 'destination_display',
            'operation', 'operation_display',
            'restockee', 'warranty_claim', 'equipement_remplace',
            'date_creation',
        ]
        read_only_fields = [
            'restockee', 'warranty_claim', 'equipement_remplace',
            'date_creation',
        ]


class PretEquipementSerializer(serializers.ModelSerializer):
    """XSAV27 — prêt d'équipement (loaner). Statut/mouvements posés par les
    actions dédiées du service (jamais en écriture directe du corps)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    en_retard = serializers.BooleanField(read_only=True)

    class Meta:
        model = PretEquipement
        fields = [
            'id', 'ticket', 'produit', 'produit_nom', 'produit_marque',
            'numero_serie', 'statut', 'statut_display', 'date_sortie',
            'date_retour_prevue', 'date_retour_reelle', 'stock_sorti',
            'stock_reintegre', 'en_retard', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'date_sortie', 'date_retour_reelle', 'stock_sorti',
            'stock_reintegre', 'date_creation',
        ]


class PieceConsommeeSerializer(serializers.ModelSerializer):
    """N46 — pièce consommée (lecture). Aucun prix d'achat exposé côté client."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    produit_marque = serializers.CharField(
        source='produit.marque', read_only=True, default=None)
    produit_sku = serializers.CharField(
        source='produit.sku', read_only=True, default=None)

    class Meta:
        model = PieceConsommee
        fields = [
            'id', 'produit', 'produit_nom', 'produit_marque', 'produit_sku',
            'quantite', 'stock_decremente', 'date_creation',
        ]
        read_only_fields = ['stock_decremente', 'date_creation']


class TicketInterventionSerializer(serializers.Serializer):
    """Vue légère des interventions liées à un ticket (lecture seule)."""
    id = serializers.IntegerField()
    type_intervention = serializers.CharField()
    type_intervention_display = serializers.CharField(
        source='get_type_intervention_display')
    installation_id = serializers.IntegerField()
    date_prevue = serializers.DateField()
    date_realisee = serializers.DateField()
    compte_rendu = serializers.CharField()
    technicien_nom = serializers.SerializerMethodField()

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien, 'username', None)


class TicketChecklistItemSerializer(serializers.ModelSerializer):
    """FG82 — Item de checklist sur un ticket (coché/non coché)."""
    coche_par_nom = serializers.CharField(
        source='coche_par.username', read_only=True, default=None)

    class Meta:
        model = TicketChecklistItem
        fields = [
            'id', 'cle', 'libelle', 'ordre', 'coche', 'note',
            'coche_par_nom', 'date_coche',
        ]
        read_only_fields = ['cle', 'libelle', 'ordre', 'coche_par_nom', 'date_coche']


class TicketSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    priorite_display = serializers.CharField(
        source='get_priorite_display', read_only=True)
    statut_ordre = serializers.SerializerMethodField()
    client_nom = serializers.SerializerMethodField()
    # VX108 — tap-to-call : numéro du client du ticket (lecture seule).
    client_telephone = serializers.SerializerMethodField()
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    equipement_serie = serializers.CharField(
        source='equipement.numero_serie', read_only=True, default=None)
    equipement_produit = serializers.CharField(
        source='equipement.produit.nom', read_only=True, default=None)
    equipement_fin_garantie = serializers.DateField(
        source='equipement.date_fin_garantie', read_only=True, default=None)
    technicien_nom = serializers.SerializerMethodField()
    # Garantie effective : calculée depuis l'équipement lié, sinon manuelle.
    sous_garantie_effectif = serializers.SerializerMethodField()
    sous_garantie_effectif_display = serializers.SerializerMethodField()
    interventions = TicketInterventionSerializer(many=True, read_only=True)
    nb_interventions = serializers.SerializerMethodField()
    # FG81 — SLA : drapeaux calculés en lecture.
    sla_breach = serializers.BooleanField(read_only=True)
    sla_due_at = serializers.DateField(read_only=True)
    date_premiere_reponse = serializers.DateTimeField(read_only=True)
    # XSAV5 — échéance SLA EFFECTIVE (décalée du temps de pause), et pause.
    sla_due_at_effectif = serializers.SerializerMethodField()
    en_attente_client = serializers.BooleanField(read_only=True)
    attente_depuis = serializers.DateField(read_only=True)
    jours_pause = serializers.IntegerField(read_only=True)
    # XSAV11 — compteur de réouvertures (côté serveur uniquement).
    reopen_count = serializers.IntegerField(read_only=True)
    # XSAV14 — taxonomie panne / cause / remède (libellés lecture).
    cause_nom = serializers.CharField(
        source='cause.nom', read_only=True, default=None)
    remede_nom = serializers.CharField(
        source='remede.nom', read_only=True, default=None)
    # ZSAV2 — catégorie de ticket configurable (libellé lecture).
    categorie_nom = serializers.CharField(
        source='categorie.libelle', read_only=True, default=None)
    # ZMFG1 — équipe de maintenance assignée (libellé lecture).
    equipe_nom = serializers.CharField(
        source='equipe.nom', read_only=True, default=None)
    # ZMFG7 — catégorie d'équipement d'origine (libellé lecture, routage
    # par alias e-mail).
    categorie_equipement_nom = serializers.CharField(
        source='categorie_equipement.nom', read_only=True, default=None)
    # XCTR2 — couverture de l'équipement lié par le contrat de maintenance
    # ACTIF du client (registre XCTR2). None si aucun contrat/équipement.
    equipement_couvert = serializers.SerializerMethodField()
    # XCTR4 — routage de couverture PROPOSÉ (garantie/contrat/facturable),
    # calculé en lecture — distinct de `couverture` (valeur stockée).
    couverture_proposee = serializers.SerializerMethodField()
    # YSERV12 — canal de résolution PROPOSÉ (sur_site si intervention liée
    # terminée, sinon à_distance), distinct de `canal_resolution` (stocké).
    canal_resolution_propose = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # YOPSB13 — caches {client_id: ContratMaintenance|None} partagés pour
        # TOUTE la page sérialisée : avec ``many=True``, DRF réutilise UNE
        # seule instance enfant pour chaque ligne, donc un cache d'instance
        # survit d'un ticket à l'autre. Évite une requête ContratMaintenance
        # par ticket (N+1 réel) quand plusieurs tickets d'une liste partagent
        # le même client. DEUX caches distincts : get_equipement_couvert
        # (registre XCTR2 — n'importe quel contrat actif, priorité à celui
        # avec override SLA) et get_couverture_proposee/couverture_calculee
        # (XCTR4 — contrat actif le plus récent, sans condition d'override) —
        # des requêtes différentes, jamais interchangeables.
        self._contrat_actif_cache = {}
        self._contrat_recent_cache = {}

    def _contrat_actif_pour_client(self, client):
        from .models import ContratMaintenance
        if client is None:
            return None
        if client.id not in self._contrat_actif_cache:
            contrat = ContratMaintenance.actif_pour_client(client)
            if contrat is None:
                contrat = (ContratMaintenance.objects
                           .filter(client=client, actif=True)
                           .order_by('-date_creation').first())
            self._contrat_actif_cache[client.id] = contrat
        return self._contrat_actif_cache[client.id]

    class Meta:
        model = Ticket
        fields = '__all__'
        # company / reference / created_by posés côté serveur — jamais du corps.
        read_only_fields = [
            'company', 'reference', 'created_by',
            'date_creation', 'date_modification',
            'sla_breach', 'sla_due_at', 'date_premiere_reponse',
            # FG88 — date_tournee est posée par l'action de planification de
            # tournée (bulk-assign), jamais directement du corps de requête.
            'date_tournee',
            # XSAV5 — la pause se pilote via les actions dédiées, jamais en
            # écriture directe du corps de requête.
            'en_attente_client', 'attente_depuis', 'jours_pause',
            # XSAV11 — incrémenté côté serveur uniquement (perform_update).
            'reopen_count',
            # YDOCF1 — machine d'états GARDÉE : le statut ne se change plus
            # par un PATCH direct du corps de requête, seulement via les
            # actions guardées `planifier/demarrer/resoudre/cloturer`
            # (+ `annuler`/`reactiver` existants qui restent un DRAPEAU
            # séparé, jamais une valeur de `statut`).
            'statut',
        ]
        # client peut être déduit côté serveur d'un équipement lié (ticket
        # ouvert depuis le parc) ; sinon il reste exigé — voir
        # TicketViewSet.perform_create qui rejette un ticket sans client résolu.
        extra_kwargs = {'client': {'required': False}}

    def get_statut_ordre(self, obj):
        order = list(Ticket.STATUT_ORDER)
        try:
            return order.index(obj.statut)
        except ValueError:
            return len(order)

    def get_client_nom(self, obj):
        c = obj.client
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_client_telephone(self, obj):
        c = obj.client
        return c.telephone if c else None

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien_responsable, 'username', None)

    def get_sous_garantie_effectif(self, obj):
        return obj.sous_garantie_calcule

    def get_sous_garantie_effectif_display(self, obj):
        return dict(Ticket.SousGarantie.choices).get(
            obj.sous_garantie_calcule, obj.sous_garantie_calcule)

    def get_nb_interventions(self, obj):
        # Reuse the prefetch cache (interventions__technicien on
        # TicketViewSet.queryset) instead of .count(), which would re-query
        # per row and defeat the N+1 fix.
        return len(obj.interventions.all())

    def get_sla_due_at_effectif(self, obj):
        due = obj.sla_due_at_effectif()
        return due.isoformat() if due else None

    def get_equipement_couvert(self, obj):
        """XCTR2 — indicateur « couvert / non couvert » calculé sur le ticket :
        None si pas d'équipement lié ou pas de contrat actif du client, sinon
        True/False selon le registre `ContratMaintenance.equipements`.

        N+1 réel corrigé (YOPSB13) : réutilise le cache par client partagé
        avec ``get_couverture_proposee`` au lieu de requêter
        ``ContratMaintenance`` à chaque ticket."""
        if obj.equipement_id is None:
            return None
        contrat = self._contrat_actif_pour_client(obj.client)
        if contrat is None:
            return None
        return contrat.couvre_equipement(obj.equipement)

    def get_couverture_proposee(self, obj):
        # N+1 réel corrigé (YOPSB13) : partage le cache ContratMaintenance
        # (contrat actif le plus récent, sans condition d'override SLA — un
        # cache DISTINCT de get_equipement_couvert) par client sur toute la
        # page au lieu d'une requête par ticket.
        return obj.couverture_calculee(contrat_cache=self._contrat_recent_cache)

    def get_canal_resolution_propose(self, obj):
        return obj.canal_resolution_propose()


# ── FG81 — Réglages SLA ────────────────────────────────────────────────────────

class SavSlaSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavSlaSettings
        fields = [
            'id', 'sla_response_days', 'sla_resolution_days',
            'sla_par_priorite', 'sla_breach_enabled',
            'notifications_client_sav', 'sla_jours_ouvres',
            'sla_warning_days', 'escalade_activee', 'affectation_auto_sav',
            'auto_cloture_jours', 'recidive_fenetre_jours',
            # YSERV5 — génération automatique planifiée des visites.
            'generation_auto_visites', 'visites_avance_jours',
            # ZMFG6 — feuilles de maintenance (worksheets).
            'worksheets_maintenance_actifs',
            'date_modification',
        ]
        read_only_fields = ['date_modification']


# ── FG82 — Checklist templates ────────────────────────────────────────────────

class MaintenanceChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceChecklistItem
        fields = ['id', 'cle', 'libelle', 'ordre', 'actif']
        read_only_fields = ['id']


class MaintenanceChecklistTemplateSerializer(serializers.ModelSerializer):
    items = MaintenanceChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = MaintenanceChecklistTemplate
        fields = ['id', 'nom', 'actif', 'protege', 'items']
        read_only_fields = ['id']


# ── FG83 — Réclamation garantie fournisseur ───────────────────────────────────

class WarrantyClaimSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    resolution_display = serializers.CharField(
        source='get_resolution_display', read_only=True)
    equipement_serie = serializers.CharField(
        source='equipement.numero_serie', read_only=True, default=None)
    equipement_produit = serializers.CharField(
        source='equipement.produit.nom', read_only=True, default=None)

    class Meta:
        model = WarrantyClaim
        fields = '__all__'
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification',
        ]


# ── FG87 — Base de connaissances ──────────────────────────────────────────────

class KbArticleSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    created_by_nom = serializers.CharField(
        source='created_by.username', read_only=True, default=None)

    class Meta:
        model = KbArticle
        fields = '__all__'
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification',
        ]


# ── XSAV10 — Satisfaction (CSAT) ──────────────────────────────────────────────

class TicketSatisfactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketSatisfaction
        fields = ['id', 'ticket', 'note', 'commentaire', 'date_creation']
        read_only_fields = ['id', 'ticket', 'date_creation']


# ── FG280 — Alarmes / défauts onduleur ────────────────────────────────────────

class AlarmeOnduleurSerializer(serializers.ModelSerializer):
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    equipement_serie = serializers.CharField(
        source='equipement.numero_serie', read_only=True, default=None)
    equipement_produit = serializers.CharField(
        source='equipement.produit.nom', read_only=True, default=None)
    ticket_reference = serializers.CharField(
        source='ticket.reference', read_only=True, default=None)
    acquittee_par_nom = serializers.CharField(
        source='acquittee_par.username', read_only=True, default=None)

    class Meta:
        model = AlarmeOnduleur
        fields = '__all__'
        # Acquittement, escalade, société et créateur sont posés côté serveur —
        # jamais depuis le corps de la requête.
        read_only_fields = [
            'company', 'created_by', 'statut',
            'acquittee_par', 'date_acquittement', 'ticket',
            'date_creation', 'date_modification',
        ]


# ── XSAV14 — Taxonomie panne / cause / remède ─────────────────────────────────

class CauseDefaillanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CauseDefaillance
        fields = ['id', 'nom', 'ordre', 'archived']
        read_only_fields = ['id']


class RemedeDefaillanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemedeDefaillance
        fields = ['id', 'nom', 'ordre', 'archived']
        read_only_fields = ['id']


class CategorieTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorieTicket
        fields = ['id', 'libelle', 'ordre', 'actif']
        read_only_fields = ['id']


# ── ZMFG1 — Équipes de maintenance ────────────────────────────────────────────

class EquipeMaintenanceSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    membres_count = serializers.SerializerMethodField()

    class Meta:
        model = EquipeMaintenance
        fields = [
            'id', 'nom', 'membres', 'membres_count', 'responsable',
            'responsable_nom', 'actif', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']

    def get_membres_count(self, obj):
        return obj.membres.count()

    def _same_company(self, obj):
        req = self.context.get('request')
        return not (obj and req and req.user.company_id
                    and obj.company_id != req.user.company_id)

    def validate_responsable(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_membres(self, value):
        req = self.context.get('request')
        company_id = req.user.company_id if req else None
        for membre in value:
            if company_id and membre.company_id != company_id:
                raise serializers.ValidationError(
                    "Un membre doit appartenir à la même société.")
        return value


# ── ZMFG2 — Catégories d'équipement ───────────────────────────────────────────

class CategorieEquipementSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    # Compteur d'équipements par catégorie (smart-button façon Odoo).
    nb_equipements = serializers.SerializerMethodField()
    # ZMFG7 — équipe responsable (libellé lecture).
    equipe_responsable_nom = serializers.CharField(
        source='equipe_responsable.nom', read_only=True, default=None)

    class Meta:
        model = CategorieEquipement
        fields = [
            'id', 'nom', 'responsable', 'responsable_nom', 'commentaire',
            'nb_equipements',
            # ZMFG7 — alias e-mail → routage auto de demande.
            'alias_email', 'equipe_responsable', 'equipe_responsable_nom',
        ]
        read_only_fields = ['id']

    def get_nb_equipements(self, obj):
        return obj.equipements.count()

    def _same_company(self, obj):
        req = self.context.get('request')
        return not (obj and req and req.user.company_id
                    and obj.company_id != req.user.company_id)

    def validate_responsable(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value


# ── XSAV16 — Journal d'immobilisation (downtime) ──────────────────────────────

class EquipementDowntimeSerializer(serializers.ModelSerializer):
    ticket_reference = serializers.CharField(
        source='ticket.reference', read_only=True, default=None)
    en_cours = serializers.SerializerMethodField()

    class Meta:
        model = EquipementDowntime
        fields = [
            'id', 'equipement', 'debut', 'fin', 'ticket', 'ticket_reference',
            'motif', 'en_cours', 'date_creation',
        ]
        read_only_fields = [
            'id', 'company', 'created_by', 'date_creation',
        ]

    def get_en_cours(self, obj):
        return obj.fin is None


# ── XSAV17 — Relevés compteur (heures / kWh) ──────────────────────────────────

class ReleveCompteurEquipementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleveCompteurEquipement
        fields = ['id', 'equipement', 'type', 'valeur', 'date', 'date_creation']
        read_only_fields = ['id', 'company', 'created_by', 'date_creation']


# ── XSAV23 — Réponses types (macros) SAV ──────────────────────────────────────

class ReponseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReponseType
        fields = [
            'id', 'titre', 'corps', 'nouveau_statut', 'archived',
            'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


# ── XSAV25 — Compatibilité pièces ─────────────────────────────────────────────

class CompatibilitePieceSerializer(serializers.ModelSerializer):
    produit_equipement_nom = serializers.CharField(
        source='produit_equipement.nom', read_only=True, default=None)
    piece_nom = serializers.CharField(
        source='piece.nom', read_only=True, default=None)
    remplace_par_nom = serializers.CharField(
        source='remplace_par.nom', read_only=True, default=None)

    class Meta:
        model = CompatibilitePiece
        fields = [
            'id', 'produit_equipement', 'produit_equipement_nom',
            'piece', 'piece_nom', 'note', 'remplace_par',
            'remplace_par_nom', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


# ── ZMFG6 — Feuilles de maintenance (worksheets) ─────────────────────────────

class WorksheetMaintenanceModeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorksheetMaintenanceModele
        fields = [
            'id', 'nom', 'type_ticket_applicable', 'champs', 'actif',
            'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']


class TicketWorksheetSerializer(serializers.ModelSerializer):
    modele_nom = serializers.CharField(
        source='modele.nom', read_only=True, default=None)
    champs_requis_manquants = serializers.SerializerMethodField()

    class Meta:
        model = TicketWorksheet
        fields = [
            'id', 'ticket', 'modele', 'modele_nom', 'valeurs', 'complete',
            'complete_par', 'complete_le', 'champs_requis_manquants',
            'date_creation',
        ]
        read_only_fields = [
            'id', 'company', 'complete', 'complete_par', 'complete_le',
            'date_creation',
        ]

    def get_champs_requis_manquants(self, obj):
        return obj.champs_requis_manquants()
