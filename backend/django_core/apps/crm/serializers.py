from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.serializers import (
    model_is_company_scoped,
    request_company_id,
    scope_related_field,
)
from .models import (
    Apporteur, Appointment, Client, ConcurrentPerte, DealEnregistre, Defi,
    EquipeCommerciale,
    EtapePlanActivite, ForecastEntry, ForecastSnapshot, Lead, LeadActivity,
    LeadPlaybookProgress, MessageTemplate, ObjectifCommercial, Parrainage,
    PlanActivite, PlanCompte, Playbook, PlaybookEtape,
    PlaybookTache, PointContact, RelanceEtape, RevueCompte, SalleVente,
    SalleVenteItem, SavedView, SiteProfile, WebsiteLeadPayload,
)
from .devis_auto import champs_manquants, message_manquants
from .scoring import compute_score, score_label, score_reasons

# ODX13 — ré-export TRANSITOIRE des serializers partenaires/territoires
# (FG234–237) qui vivent encore dans ``apps.compta.serializers``. Ce module
# expose ``apps.crm.serializers`` pour les ViewSets ré-exportés dans
# ``apps/crm/views.py`` et les nouvelles routes ``/api/django/crm/…`` ;
# ODX22 re-logera leur corps ici.
from apps.compta.serializers import (  # noqa: F401,E402
    CommissionPartenaireSerializer,
    PartenaireSerializer,
    SoumissionLeadPartenaireSerializer,
    TerritoireCommercialSerializer,
)


# ── LW29/CRX19 — PII du lead : une SEULE liste, un SEUL masquage ────────────
#
# ``LeadSerializer`` masque déjà ces six champs pour un rôle sans
# ``client_pii_voir``… mais le CHATTER les recopiait en clair dans
# ``old_value``/``new_value`` : « telephone : 0612345678 → 0698765432 » restait
# lisible par tout le monde. Le masquage vit donc AU NIVEAU DU SÉRIALISEUR
# d'activité, donc PAR CONSTRUCTION sur les trois surfaces qui servent le
# chatter (action ``historique``, ``chatter_recent`` embarqué au retrieve, et
# l'enveloppe uniforme ARC9).
LEAD_PII_FIELDS = ('telephone', 'email', 'adresse', 'whatsapp',
                   'gps_lat', 'gps_lng')

#: Remplacement affiché à la place d'une valeur PII masquée.
PII_MASQUE = '•••'


def pii_masquee_pour(user) -> bool:
    """Condition UNIQUE du masquage PII (LW29) : ``user`` connu et privé de
    ``client_pii_voir``. Sans utilisateur (rendu serveur/interne, tâche de
    fond), rien n'est masqué — comportement historique."""
    return user is not None and not getattr(user, 'can_view_client_pii', True)


def masquer_valeurs_chatter(field, old_value, new_value, user):
    """Renvoie ``(old_value, new_value)`` masqués si ``field`` est une PII du
    lead et que ``user`` n'a pas le droit de la voir.

    Fonction PARTAGÉE par ``LeadActivitySerializer`` et par l'enveloppe
    uniforme (``selectors.lead_chatter_envelope``) : une seule règle, jamais
    deux implémentations qui divergent.
    """
    if not pii_masquee_pour(user):
        return old_value, new_value
    if (field or '') not in LEAD_PII_FIELDS:
        return old_value, new_value
    return (PII_MASQUE if old_value else old_value,
            PII_MASQUE if new_value else new_value)


class LeadActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()
    # VX111 — pièce jointe optionnelle sur une note (photo prise depuis
    # mobile). Même forme d'URL que AttachmentSerializer.get_url (proxy
    # Django même origine, jamais MinIO direct) — pas de sérialiseur imbriqué
    # pour rester compatible avec la structure plate consommée par
    # ChatterTimeline côté frontend.
    attachment_url = serializers.SerializerMethodField()
    attachment_filename = serializers.SerializerMethodField()
    attachment_mime = serializers.SerializerMethodField()

    class Meta:
        model = LeadActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'outcome', 'bulk', 'pinned', 'user_nom', 'created_at',
            'attachment_url', 'attachment_filename', 'attachment_mime',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)

    def get_attachment_url(self, obj):
        if not obj.attachment_id:
            return None
        return f'/api/django/records/attachments/{obj.attachment_id}/download/'

    def get_attachment_filename(self, obj):
        return getattr(obj.attachment, 'filename', None)

    def get_attachment_mime(self, obj):
        return getattr(obj.attachment, 'mime', None)

    def to_representation(self, instance):
        """CRX19 — masque ``old_value``/``new_value`` quand l'entrée porte sur
        une PII du lead et que l'utilisateur n'a pas ``client_pii_voir``.

        Ici et NULLE PART AILLEURS : les trois surfaces qui servent le chatter
        (``historique``, ``chatter_recent``, enveloppe ARC9) héritent donc du
        masquage par construction. Sans ``context['request']`` (rendu interne),
        rien n'est masqué — comportement historique."""
        data = super().to_representation(instance)
        request = self.context.get('request') if hasattr(self, 'context') \
            else None
        user = getattr(request, 'user', None) if request is not None else None
        data['old_value'], data['new_value'] = masquer_valeurs_chatter(
            data.get('field'), data.get('old_value'), data.get('new_value'),
            user)
        return data


class RelanceEtapeSerializer(serializers.ModelSerializer):
    """RELANCE FOUNDATION — étape du plan de relance structuré d'un lead, pour
    le panneau « Relances du jour ». Plate (jamais de sérialiseur Lead
    imbriqué) — même convention que ``LeadActivitySerializer`` ci-dessus."""

    lead_nom = serializers.SerializerMethodField()
    lead_owner_nom = serializers.SerializerMethodField()
    overdue = serializers.SerializerMethodField()

    class Meta:
        model = RelanceEtape
        fields = [
            'id', 'lead', 'lead_nom', 'lead_owner_nom', 'ordre', 'due_date',
            'canal', 'libelle', 'statut', 'note', 'overdue',
        ]
        read_only_fields = [
            'id', 'lead', 'ordre', 'due_date', 'canal', 'libelle',
        ]

    def get_lead_nom(self, obj) -> str:
        return f'{obj.lead.nom} {obj.lead.prenom or ""}'.strip()

    def get_lead_owner_nom(self, obj) -> str | None:
        return getattr(obj.lead.owner, 'username', None)

    def get_overdue(self, obj) -> bool:
        from core.dates import aujourd_hui_local
        return obj.due_date < aujourd_hui_local()


class _CurrentCompanyDefault:
    """Société du user courant, injectée CÔTÉ SERVEUR (jamais lue du corps
    de la requête). Satisfait le validateur d'unicité (company, email) qui,
    sinon, exigeait `company` dans le payload — cassait « Nouveau client »."""
    requires_context = True

    def __call__(self, serializer_field):
        return serializer_field.context['request'].user.company


# ── CRX13 — relations NUES re-scopées société (primitive CRX12) ──────────────
#
# Treize relations d'``apps/crm`` étaient déclarées (ou auto-construites) avec
# un queryset NON scopé : un POST/PATCH pouvait donc rattacher l'objet à une
# ligne d'une AUTRE société, et l'erreur renvoyée servait d'ORACLE d'existence.
# Le re-scope se fait par PROMOTION du champ déjà construit
# (``core.serializers.scope_related_field``) plutôt que par re-déclaration :
# les arguments d'origine (``required``, ``allow_null``, ``source``, messages)
# sont conservés à l'identique — seule la résolution de l'id change. Un champ
# déjà en lecture seule, ou dont la cible n'a pas de ``company``, est ignoré.


class _CompanyScopedRelationsMixin:
    """Re-scope société les relations nommées dans ``scoped_relations``.

    Posé en PREMIÈRE base du sérialiseur : un ``get_fields`` propre au
    sérialiseur (ClientSerializer, LeadSerializer) reste prioritaire et appelle
    ``super()``, donc la promotion s'applique dans tous les cas.
    """

    #: Noms de champs de relation à re-scoper sur ``request.user.company``.
    scoped_relations: tuple = ()

    def get_fields(self):
        fields = super().get_fields()
        for name in self.scoped_relations:
            field = fields.get(name)
            if field is not None:
                scope_related_field(field)
        return fields


class _CompanyScopedUniqueValidator(UniqueValidator):
    """``UniqueValidator`` dont le queryset est re-scopé société.

    Le validateur d'unicité auto-généré par DRF pour un champ ``unique``
    interroge TOUTES les sociétés : répondre « déjà utilisé » sur un id qui
    n'appartient pas au demandeur révèle l'existence d'une ligne voisine. On
    restreint donc la recherche à la société de la requête. Sans requête (rendu
    interne) ou pour un acteur sans société, le comportement d'origine est
    conservé à l'identique.
    """

    def __call__(self, value, serializer_field):
        company_id = request_company_id(serializer_field.context)
        if company_id is not None and model_is_company_scoped(
                self.queryset.model):
            scoped = UniqueValidator(
                queryset=self.queryset.filter(company_id=company_id),
                message=self.message, lookup=self.lookup)
            return scoped(value, serializer_field)
        return super().__call__(value, serializer_field)


def _scope_unique_validators(field):
    """Remplace les ``UniqueValidator`` d'un champ par leur version scopée."""
    if field is None:
        return
    validators = getattr(field, 'validators', None)
    if not validators:
        return
    field.validators = [
        _CompanyScopedUniqueValidator(
            queryset=v.queryset, message=v.message, lookup=v.lookup)
        if type(v) is UniqueValidator else v
        for v in validators
    ]


class ClientSerializer(_CompanyScopedRelationsMixin,
                       serializers.ModelSerializer):
    # CRX13 — la liste de prix négociée et la fiche du répertoire unifié sont
    # deux relations SORTANTES (ventes/tiers) : sans re-scope, un PATCH pouvait
    # rattacher le client au tarif d'une autre société.
    scoped_relations = ('liste_prix', 'tiers')

    devis_count = serializers.SerializerMethodField()
    total_facture_ttc = serializers.SerializerMethodField()
    total_paye = serializers.SerializerMethodField()
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    # Traçabilité (L16) : qui a créé le client + dernière modification.
    # created_by est forcé côté serveur (perform_create) — jamais lu du corps.
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    created_by_nom = serializers.SerializerMethodField()

    # FG20 — coordonnées personnelles masquées quand le rôle n'a pas
    # ``client_pii_voir``. Source unique des champs PII partagée avec le Lead.
    PII_FIELDS = ('telephone', 'email', 'adresse')

    def validate(self, attrs):
        # Champs personnalisés (T11, L808) : valider/nettoyer le custom_data du
        # client contre les définitions du module « client », même chemin que
        # Lead. À la création on valide toujours (champs obligatoires) ; en
        # mise à jour, uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'client', company, attrs.get('custom_data'))
        return attrs

    def validate_parent(self, value):
        # XSAL9 — anti-cycle + même société, appliqué ici car DRF n'invoque
        # PAS Model.clean() automatiquement à l'écriture API (seul
        # full_clean() le ferait — jamais appelé sur ce chemin).
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'La société mère doit appartenir à la même société.')
        if self.instance is not None:
            if value.pk == self.instance.pk:
                raise serializers.ValidationError(
                    "Un client ne peut pas être sa propre société mère.")
            seen = {self.instance.pk}
            current = value
            depth = 0
            while current is not None:
                if current.pk in seen or depth > 100:
                    raise serializers.ValidationError(
                        'Cette hiérarchie créerait un cycle.')
                seen.add(current.pk)
                current = current.parent
                depth += 1
        return value

    def get_fields(self):
        fields = super().get_fields()
        # FG20 — masque la PII en LECTURE pour les rôles non autorisés. On rend
        # les champs lecture-seule (plutôt que de les retirer) afin de ne jamais
        # casser une écriture légitime, et on les vide à la sérialisation.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'can_view_client_pii', True):
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

    class Meta:
        model = Client
        fields = '__all__'
        read_only_fields = ['date_modification']

    def get_created_by_nom(self, obj):
        return getattr(obj.created_by, 'username', None)

    def get_devis_count(self, obj):
        return obj.devis.count()

    def get_total_facture_ttc(self, obj):
        """Valeur cumulée FACTURÉE (TTC) du client : somme des factures non
        annulées. total_ttc est une propriété calculée → agrégation en Python.
        Aucun prix d'achat ni marge n'intervient (totaux client-facing)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.total_ttc
        return str(total)

    def get_total_paye(self, obj):
        """Total ENCAISSÉ du client (somme des montant_paye des factures)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.montant_paye
        return str(total)


class LeadSerializer(_CompanyScopedRelationsMixin,
                     serializers.ModelSerializer):
    # CRX13 — ``deleted_by`` (auto-construit depuis ``__all__``) désignait
    # n'importe quel utilisateur, toutes sociétés confondues. CRX15 l'a depuis
    # verrouillé en LECTURE SEULE (cf. ``Meta.read_only_fields``) : la
    # promotion est alors un no-op, conservée comme filet si le champ
    # redevenait un jour inscriptible.
    scoped_relations = ('deleted_by',)

    stage_label = serializers.CharField(source='get_stage_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    client_nom = serializers.SerializerMethodField()
    devis = serializers.SerializerMethodField()
    owner_nom = serializers.SerializerMethodField()
    owner_poste = serializers.SerializerMethodField()
    owner_avatar = serializers.SerializerMethodField()
    devis_auto = serializers.SerializerMethodField()
    next_activity = serializers.SerializerMethodField()
    # FG27 — Score de qualité du lead (lecture seule, calculé à la volée).
    score = serializers.SerializerMethodField()
    score_label = serializers.SerializerMethodField()
    # VX221 — décomposition « pourquoi ce score » (facteurs + points), pour le
    # tooltip du badge. Pure exposition des composantes déjà calculées.
    score_reasons = serializers.SerializerMethodField()
    # FG29 — Âge dans l'étape courante (jours depuis le dernier changement d'étape).
    stage_since_days = serializers.SerializerMethodField()
    # VX98 — auteur de la dernière modification (puce de fraîcheur). Lecture seule.
    updated_by_nom = serializers.CharField(
        source='updated_by.username', read_only=True, default=None)
    # VX243(a) — confiance au niveau du DOSSIER : « archivé par X le … ». Les
    # champs archived_by/archived_at sont posés côté serveur (jamais rendus
    # avant) — on expose ici le NOM de l'archiviste en lecture seule pour que
    # la ligne archivée le montre. Silencieux si le lead n'est pas archivé.
    archived_by_nom = serializers.CharField(
        source='archived_by.username', read_only=True, default=None)
    # LW29 — masquage PII rendu VISIBLE (au lieu de silencieux) : le front
    # peut afficher les champs PII_FIELDS verrouillés-cadenas plutôt que de
    # laisser croire à une édition qui sera jetée (drop silencieux au PATCH).
    # Même condition EXACTE que get_fields()/to_representation() ci-dessous
    # — source unique, jamais une seconde règle qui pourrait diverger.
    pii_masked = serializers.SerializerMethodField()
    # LW30 — 50 dernières LeadActivity embarquées sur le RETRIEVE seulement
    # (jamais list() — payload) : voir get_fields() plus bas.
    chatter_recent = serializers.SerializerMethodField()
    # PV78 — conception 3D du lead {kwc, image_url}. RETRIEVE SEULEMENT, même
    # porte que chatter_recent : ce bloc coûte une requête devis + une URL
    # pré-signée PAR LEAD, ce qui serait un N+1 franc sur une liste de 50
    # cartes. Voir get_fields() plus bas.
    conception = serializers.SerializerMethodField()
    # LB39 — marqueur d'ANNULATION du dernier changement d'étape. Champ HORS
    # MODÈLE, write-only, jamais persisté (retiré dans validate()) : à lui
    # seul il n'autorise RIEN — il déclenche seulement la vérification
    # serveur `_undo_of_last_stage_change` (le chatter doit porter le
    # mouvement inverse exact, daté de moins de UNDO_WINDOW_SECONDS). La
    # garde funnel reste intégralement en place pour tout autre recul.
    undo = serializers.BooleanField(write_only=True, required=False)
    # Fenêtre d'annulation, alignée sur la durée d'affichage du toast
    # « Annuler » côté client (VX95) avec une marge confortable.
    UNDO_WINDOW_SECONDS = 300
    # ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN
    # ARRIÈRE d'étape, avec une confirmation avant ». Même patron que ``undo``
    # (champ HORS MODÈLE, write-only, retiré dans validate(), jamais persisté),
    # mais une sémantique différente et volontairement plus large :
    #   • ``undo`` = annulation MACHINE du dernier mouvement, revérifiée contre
    #     le chatter et bornée dans le temps — l'utilisatrice n'affirme rien ;
    #   • ``confirme_recul`` = décision HUMAINE explicite. Le client a montré
    #     une boîte de confirmation nommant le lead et les deux étapes, et
    #     l'utilisatrice a dit oui. Il n'y a donc rien à revérifier contre
    #     l'historique : un recul volontaire est un fait métier légitime (un
    #     devis retombe en relance, un « signé » se dénoue), pas un accident.
    # Ce qu'il n'ouvre PAS : le verrou du lead perdu (vérifié AVANT, comme pour
    # ``undo``) et les actions en MASSE (voir la garde funnel plus bas).
    confirme_recul = serializers.BooleanField(write_only=True, required=False)

    @staticmethod
    def _canonical_phone(value):
        """Forme canonique '212XXXXXXXXX' d'un numéro marocain saisi librement
        (06 12-34 56 78, +212612…, 00212…). Source unique : le normaliseur des
        ventes (apps.ventes.utils.phone) — pas de logique dupliquée ici. Vide
        ou non normalisable → on conserve la valeur saisie telle quelle (jamais
        de rejet : le formulaire est volontairement permissif).

        25/08/2026 — LANE NUMÉROS INTERNATIONAUX : cette garde ne réécrit la
        saisie QUE quand `normalize_ma_phone` reconnaît un numéro marocain ;
        avant cette date, `normalize_ma_phone` forçait quand même un préfixe
        '212' sur presque tout le reste (le `or value` ci-dessous ne se
        déclenchait donc presque jamais), ce qui CORROMPAIT silencieusement un
        numéro étranger saisi (ex. +33612345678 → '21233612345678') plutôt que
        de le conserver tel quel. `normalize_ma_phone` renvoie désormais None
        pour tout ce qui n'est pas reconnaissable comme marocain, donc un +33
        posté ici relit exactement +33 (voir test_lead_foreign_phone_survives_
        api_write, apps/crm/tests)."""
        if value in (None, ''):
            return value
        from apps.ventes.utils.phone import normalize_ma_phone
        return normalize_ma_phone(value) or value

    def validate_telephone(self, value):
        return self._canonical_phone(value)

    def validate_whatsapp(self, value):
        return self._canonical_phone(value)

    def get_devis_auto(self, obj):
        """Prêt pour le devis automatique ? Même règle que l'endpoint
        POST /leads/<id>/devis-auto/ (source unique : devis_auto.py)."""
        manquants = champs_manquants(obj)
        return {
            'pret': not manquants,
            'manquants': manquants,
            'message': message_manquants(manquants) if manquants else None,
        }

    def get_next_activity(self, obj):
        """Activité ouverte la plus proche (pour la pastille horloge de la
        carte kanban) : {state: overdue/today/upcoming, due_date, summary}.

        YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge une carte
        {lead_id: Activity} en UNE requête pour toute la page et la pose dans
        le contexte (``next_activity_map``) : on la préfère quand elle existe
        pour éviter une requête PAR LIGNE (N+1). Sans contexte (ex. detail
        unique, ou appel serializer hors vue), on retombe sur la requête
        individuelle — comportement inchangé."""
        try:
            next_activity_map = self.context.get('next_activity_map')
            if next_activity_map is not None:
                act = next_activity_map.get(obj.id)
            else:
                from django.contrib.contenttypes.models import ContentType
                from apps.records.models import Activity
                ct = ContentType.objects.get_for_model(obj.__class__)
                act = (Activity.objects
                       .filter(content_type=ct, object_id=obj.id, done=False,
                               due_date__isnull=False)
                       .order_by('due_date').first())
            if act is None:
                return None
            from apps.records.serializers import activity_state
            return {
                'state': activity_state(act.due_date, False),
                'due_date': act.due_date.isoformat(),
                'summary': act.summary or act.activity_type.nom,
            }
        except Exception:
            return None

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_owner_poste(self, obj):
        return getattr(obj.owner, 'poste', None) or None

    def get_owner_avatar(self, obj):
        """URL présignée de la photo du responsable (avatar Odoo)."""
        if not obj.owner_id:
            return None
        from authentication.avatars import presign_avatar
        return presign_avatar(getattr(obj.owner, 'avatar_key', ''))

    # FG27 — Score de qualité (lecture seule)
    def get_score(self, obj):
        """CRX22 — sert la colonne PERSISTÉE ``Lead.score``.

        Avant, le badge recalculait le score À LA VOLÉE pour chaque ligne
        alors que le TRI (``ordering_fields``) et « Ma file »
        (``selectors.leads_chauds_non_contactes``, ``score__gte``) filtrent sur
        la COLONNE : deux valeurs différentes pour le même lead, donc une
        liste triée « par score » dont les badges n'étaient pas dans l'ordre.
        Une seule valeur fait foi maintenant — celle que
        ``services.recompute_lead_score`` écrit à chaque édition et que le job
        beat quotidien rafraîchit sur les leads non touchés.

        Repli sur le calcul UNIQUEMENT quand la colonne est encore NULL (leads
        importés avant la migration QJ6, jamais réenregistrés) : le badge ne
        doit pas afficher un trou.
        """
        if obj.score is not None:
            return obj.score
        return compute_score(obj)

    def get_score_label(self, obj):
        return score_label(self.get_score(obj))

    def get_score_reasons(self, obj):
        # VX221 — liste [{facteur, label, points}] triée par points décroissants.
        return score_reasons(obj)

    # FG29 — Âge dans l'étape courante
    def get_stage_since_days(self, obj):
        """Nombre de jours depuis le dernier changement d'étape de ce lead.

        Source : dernière entrée LeadActivity de type MODIFICATION sur le champ
        'stage'. Si aucune → âge depuis la création du lead (première entrée).
        Renvoie None si indétectable.
        """
        try:
            from django.utils import timezone
            # YOPSB13/perf_n1 — sur une LISTE, LeadViewSet.list() précharge une
            # carte {lead_id: dernière date de changement d'étape} en UNE requête
            # (stage_since_map) : sinon c'était 1 requête LeadActivity PAR LIGNE
            # (N+1). Hors contexte (détail) → requête individuelle inchangée.
            stage_since_map = self.context.get('stage_since_map')
            if stage_since_map is not None:
                ref = stage_since_map.get(obj.id) or obj.date_creation
            else:
                from .models import LeadActivity
                last_change = (
                    LeadActivity.objects
                    .filter(lead=obj, kind=LeadActivity.Kind.MODIFICATION,
                            field='stage')
                    .order_by('-created_at')
                    .first()
                )
                ref = last_change.created_at if last_change else obj.date_creation
            if ref is None:
                return None
            now = timezone.now()
            if hasattr(ref, 'tzinfo') and ref.tzinfo is None:
                from django.utils.timezone import make_aware
                ref = make_aware(ref)
            return (now - ref).days
        except Exception:
            return None

    def validate_owner(self, value):
        # Le responsable assigné doit appartenir à la même société.
        request = self.context.get('request')
        if value and request and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Utilisateur inconnu.')
        return value

    def validate_canal(self, value):
        """Le canal doit appartenir aux canaux GÉRÉS de la société (Paramètres →
        CRM) en plus des choices figés du modèle. Vide accepté. Source unique :
        le référentiel Canal — un PATCH avec une clé inconnue est rejeté 400."""
        if value in (None, ''):
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        from .models import Canal as CanalModel
        existe = CanalModel.objects.filter(
            company=company, cle=value, archived=False).exists()
        # Le référentiel peut ne pas être amorcé (lazy seed) : on tolère alors
        # les clés du modèle pour ne pas casser un import/création légitime.
        if not existe and CanalModel.objects.filter(company=company).exists():
            raise serializers.ValidationError('Canal inconnu.')
        return value

    def _undo_of_last_stage_change(self, current, target):
        """LB39 — le PATCH demandé est-il l'ANNULATION du dernier changement
        d'étape de CE lead, dans la fenêtre courte ?

        Vérification côté SERVEUR uniquement : le marqueur ``undo`` du client
        n'est jamais cru sur parole. La dernière entrée de chatter
        ``LeadActivity`` field='stage' doit avoir enregistré EXACTEMENT le
        mouvement inverse (``old_value`` = l'étape demandée, ``new_value`` =
        l'étape actuelle) et dater de moins de ``UNDO_WINDOW_SECONDS``. Toute
        autre marche arrière reste refusée par la garde funnel — on n'ouvre
        donc jamais un recul manuel, seulement le retour en arrière de sa
        PROPRE action, tant que le toast « Annuler » est à l'écran.
        """
        from django.utils import timezone
        from . import stages as stage_mod

        last = (LeadActivity.objects
                .filter(lead=self.instance,
                        kind=LeadActivity.Kind.MODIFICATION,
                        field='stage')
                .order_by('-created_at', '-id')
                .first())
        if last is None or last.created_at is None:
            return False
        age = (timezone.now() - last.created_at).total_seconds()
        if age < 0 or age > self.UNDO_WINDOW_SECONDS:
            return False
        # Le chatter stocke le LIBELLÉ FR (activity._display) ; d'anciennes
        # écritures peuvent porter la clé brute — les deux sont acceptées, la
        # comparaison reste exacte dans les deux cas.
        labels = stage_mod.STAGE_LABELS

        def _is(stored, key):
            return stored is not None and stored in (labels.get(key), key)

        return _is(last.old_value, target) and _is(last.new_value, current)

    def validate(self, attrs):
        # LB39 — marqueur d'annulation : jamais persisté (champ hors modèle),
        # retiré ici pour ne jamais atteindre ``.save()``.
        undo = bool(attrs.pop('undo', False))
        # Ordre fondateur 2026-08-01 : confirmation humaine d'un recul. Jamais
        # persisté non plus (champ hors modèle) — retiré ici comme ``undo``.
        confirme_recul = bool(attrs.pop('confirme_recul', False))
        # Garde funnel côté serveur (aligné sur la règle bulk _bulk_stage_allowed):
        # en MISE À JOUR, un lead perdu ne change pas d'étape, et un recul dans
        # l'entonnoir doit être EXPLICITEMENT assumé (Froid = parking, jamais
        # une régression : _bulk_stage_allowed l'autorise déjà des deux côtés).
        if self.instance is not None and 'stage' in attrs:
            from .services import _bulk_stage_allowed
            current = self.instance.stage
            target = attrs['stage']
            if target != current:
                # Verrou du lead perdu : il PRÉCÈDE toute échappatoire — ni
                # ``undo`` ni ``confirme_recul`` ne le déverrouillent.
                if self.instance.perdu:
                    raise serializers.ValidationError(
                        {'stage': 'Lead perdu — étape non modifiable.'})
                if not _bulk_stage_allowed(current, target):
                    # DEUX échappatoires, et deux seulement :
                    # LB39 — l'annulation, validée serveur, du dernier
                    # changement d'étape de ce lead (le toast « Annuler » de
                    # VX95 PATCHait en arrière et se prenait un 400
                    # systématique — l'undo était mort en production) ;
                    # ordre fondateur 2026-08-01 — la confirmation humaine
                    # explicite d'un recul volontaire (le client a montré une
                    # boîte nommant le lead et les deux étapes). Sans l'un des
                    # deux, un recul nu reste un 400 : le refus par défaut est
                    # inchangé, c'est la seule manière d'empêcher un
                    # glisser-déposer maladroit de défaire un pipeline.
                    if not (confirme_recul
                            or (undo and self._undo_of_last_stage_change(current, target))):
                        raise serializers.ValidationError(
                            {'stage': "On ne recule pas une étape."})
        # ORDRE FONDATEUR (24/08/2026) — le GPS ne doit JAMAIS être écrasé ni
        # supplanté par l'adresse. Le Lead Workspace (LW9, draftCore.js) ne
        # PATCH déjà que les clés réellement modifiées (dirty keys) — éditer
        # l'adresse seule n'envoie donc jamais gps_lat/gps_lng. Ce garde est
        # une DÉFENSE EN PROFONDEUR pour tout AUTRE appelant (import, script,
        # futur écran) : une mise à jour qui n'apporte pas de nouvelles
        # coordonnées EXPLICITES (vide/nulle) ne doit jamais effacer un GPS
        # déjà posé sur ce lead.
        if self.instance is not None:
            for gps_field in ('gps_lat', 'gps_lng'):
                if (gps_field in attrs and attrs[gps_field] in (None, '')
                        and getattr(self.instance, gps_field) is not None):
                    attrs.pop(gps_field)
        # Champs personnalisés (T11) : valider/nettoyer contre les définitions
        # du module « lead ». À la création on valide toujours (champs
        # obligatoires) ; en mise à jour, uniquement si custom_data est fourni
        # (pour ne pas bloquer un PATCH d'un autre champ / édition en place).
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'lead', company, attrs.get('custom_data'))
        return attrs

    class Meta:
        model = Lead
        fields = '__all__'
        # company/source/external refs are set server-side, never trusted from
        # input. The lead→client link is resolved server-side too (no-duplicate
        # rules in services.py), never accepted from the browser.
        # L'archivage se pilote par les actions archiver/restaurer, jamais par
        # un PATCH direct du corps.
        read_only_fields = [
            'company', 'external_system', 'external_id', 'client',
            'is_archived', 'archived_by', 'archived_at',
            # CRX15 — triplet de soft-delete VERROUILLÉ, par parité exacte avec
            # `is_archived` juste au-dessus : il ne se pilote que par la
            # suppression (`SoftDeleteModel.soft_delete`/`restore`), jamais par
            # un PATCH direct du corps. Écrivable, `is_deleted: true` faisait
            # DISPARAÎTRE le lead des listes sans écrire de `DeletionRecord`
            # (donc sans corbeille ni undo) et en contournant la garde 409 qui
            # refuse la suppression d'un lead porteur de devis.
            'is_deleted', 'deleted_at', 'deleted_by',
            'first_contacted_at',  # FG28 — posé server-side uniquement
            'updated_by',  # VX98 — posé server-side (perform_update) uniquement
            # B3 — toiture 3D : pin/contour bruts + conso saisis par le client
            # (webhook site, posés server-side). Exposés en LECTURE SEULE sur la
            # fiche lead pour que la page de conception authentifiée réhydrate la
            # toiture épinglée du client ; jamais réécrits via un PATCH du corps.
            'roof_point', 'roof_outline', 'bill_kwh',
        ]

    # FG20 — coordonnées personnelles masquées sans ``client_pii_voir``.
    # CRX19 — SOURCE UNIQUE (module) partagée avec le masquage du chatter :
    # deux listes divergentes, c'est un champ masqué sur la fiche et lisible
    # dans son historique.
    PII_FIELDS = LEAD_PII_FIELDS

    def _pii_masked(self):
        """LW29 — condition UNIQUE de masquage PII, réutilisée par
        get_fields()/to_representation() ET par le champ calculé
        ``pii_masked`` — jamais une seconde règle qui pourrait diverger."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return user is not None and not getattr(user, 'can_view_client_pii', True)

    def get_fields(self):
        fields = super().get_fields()
        if self._pii_masked():
            for name in self.PII_FIELDS:
                if name in fields:
                    fields[name].read_only = True
        # LW30 — chatter_recent n'est embarqué que sur le RETRIEVE (flag de
        # contexte posé par LeadViewSet.retrieve() uniquement) ; ABSENT du
        # payload list() — jamais juste null, la clé elle-même disparaît.
        if not self.context.get('include_chatter_recent'):
            fields.pop('chatter_recent', None)
            # PV78 — même porte : ``include_chatter_recent`` est le marqueur
            # « vue DÉTAIL » du dépôt (posé UNIQUEMENT par
            # ``LeadViewSet.retrieve``). On le RÉUTILISE plutôt que d'ajouter
            # un second drapeau qu'il faudrait poser au même endroit — et la
            # conception, qui coûte une requête + une URL pré-signée par lead,
            # ne descend donc jamais dans une liste.
            fields.pop('conception', None)
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self._pii_masked():
            for name in self.PII_FIELDS:
                if name in data:
                    data[name] = None
        return data

    def get_pii_masked(self, obj):
        """LW29 — expose EXPLICITEMENT si les champs PII_FIELDS sont
        masqués pour l'utilisateur courant, pour que le front les rende
        verrouillés-cadenas au lieu de laisser croire à une édition qui
        sera jetée (drop silencieux au PATCH)."""
        return self._pii_masked()

    def get_conception(self, obj):
        """PV78 — ``{kwc, image_url}`` de la conception 3D du lead.

        Lecture cross-app par le SÉLECTEUR de l'app cible
        (``crm.selectors.conception_3d_du_lead`` → ``ventes.selectors``), jamais
        par un import des modèles ventes. Company-scopée côté ventes. Les deux
        clés sont TOUJOURS là : un lead sans devis calepiné vaut deux valeurs
        vides, jamais une clé absente.
        """
        from .selectors import conception_3d_du_lead
        return conception_3d_du_lead(obj)

    def get_chatter_recent(self, obj):
        """LW30 — 50 dernières LeadActivity (auto + notes), épingle-d'abord
        (tri LW28), ``select_related('user','attachment')`` pour éviter tout
        N+1 (même garde que LW8). Calculée uniquement quand get_fields() a
        gardé le champ (RETRIEVE) — jamais appelée sur une liste.

        CRX19 — le CONTEXTE est propagé : sans lui, le sérialiseur d'activité
        ne connaît pas l'utilisateur et le masquage PII du chatter ne
        s'appliquerait pas sur cette surface."""
        rows = (
            obj.activites
            .select_related('user', 'attachment')
            .order_by('-pinned', '-created_at')[:50]
        )
        return LeadActivitySerializer(
            rows, many=True, context=self.context).data

    def get_client_nom(self, obj):
        if not obj.client_id:
            return None
        c = obj.client
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_devis(self, obj):
        # Devis « empilés » sur le lead, du plus récent au plus ancien.
        # A4 — on expose le chantier lié (s'il existe) et l'option acceptée pour
        # que la fiche lead propose en ligne « Générer la facture » et « Créer le
        # chantier » (sans doublon) après acceptation.
        # YOPSB13 — sur une LISTE, ``LeadViewSet.list()`` précharge les
        # chantiers de TOUS les devis de la page en UNE requête et la pose
        # dans le contexte (``chantier_map``), pour éviter une requête
        # Installation PAR LIGNE (N+1). Sans contexte, on retombe sur l'appel
        # individuel — comportement inchangé.
        # YOPSB13/perf_n1 — ``obj.devis.order_by(...)`` clone le manager et
        # IGNORE le cache prefetch (``prefetch_related('devis')`` posé par
        # ``LeadViewSet``), ré-exécutant une requête PAR ligne (N+1). On lit le
        # cache via ``.all()`` puis on trie en Python (ordre identique), sans
        # importer le modèle ``ventes`` (frontière inter-app respectée).
        rows = sorted(
            obj.devis.all(),
            key=lambda d: (d.date_creation is not None, d.date_creation),
            reverse=True,
        )
        chantier_map = self.context.get('chantier_map')
        if chantier_map is not None:
            chantiers = {d.id: chantier_map.get(d.id) for d in rows}
        else:
            from apps.installations.selectors import (
                installation_summaries_for_devis,
            )
            chantiers = installation_summaries_for_devis(rows)
        # L-NIV-UI (24/08/2026) — niveau/otp_lecture du ShareLink DÉJÀ EXISTANT
        # (jamais un mint) : sans ça, l'onglet Devis (DevisTab.jsx) n'affichait
        # le badge de niveau qu'après un premier clic sur le sélecteur/case,
        # car son état `linkMeta` ne se remplissait qu'à partir de la réponse
        # d'un POST share-link explicite. Lecture cross-app via
        # `apps.ventes.selectors` (jamais `apps.ventes.models`).
        # YOPSB13 — MÊME garde N+1 que ``chantier_map`` : sur une LISTE,
        # ``LeadViewSet.list()`` précharge les ShareLink de TOUS les devis de
        # la page en UNE requête (``share_link_map`` dans le contexte). Sans
        # ce préchargement (retrieve, usage direct du serializer), on retombe
        # sur l'appel pour ce lead seul — comportement identique.
        share_link_map = self.context.get('share_link_map')
        if share_link_map is not None:
            niveau_map = share_link_map
        else:
            from apps.ventes.selectors import share_link_niveau_map
            niveau_map = share_link_niveau_map([d.id for d in rows])
        return [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': d.statut,
                'total_ttc': str(d.total_ttc),
                'date_creation': d.date_creation.isoformat(),
                'option_acceptee': d.option_acceptee,
                'chantier': chantiers.get(d.id),
                'share_link': niveau_map.get(d.id),
            }
            for d in rows
        ]


def _tag_en_usage(company, nom):
    """Nombre de leads dont le champ texte ``tags`` référence ce libellé.

    ``Lead.tags`` est un texte libre séparé par des virgules ; on compte les
    leads qui portent ce libellé comme jeton (insensible à la casse)."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    cible = nom.casefold()
    n = 0
    for raw in Lead.objects.filter(
            company=company, tags__icontains=nom).values_list('tags', flat=True):
        if any((t or '').strip().casefold() == cible
               for t in (raw or '').split(',')):
            n += 1
    return n


def _motif_en_usage(company, nom):
    """Nombre de leads dont ``motif_perte`` (texte libre) vaut ce libellé."""
    from .models import Lead
    nom = (nom or '').strip()
    if not nom:
        return 0
    return Lead.objects.filter(
        company=company, motif_perte__iexact=nom).count()


class LeadTagSerializer(serializers.ModelSerializer):
    # Nombre de leads référençant cette étiquette — l'UI désactive la
    # suppression et propose l'archivage si > 0 (L780).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import LeadTag
        model = LeadTag
        fields = ['id', 'nom', 'couleur', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return _tag_en_usage(obj.company, obj.nom)


class MotifPerteSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce motif de perte (L779).
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import MotifPerte
        model = MotifPerte
        # PUB28 — est_junk distingue un motif JUNK (numéro invalide, spam/bot…)
        # d'un motif de perte commercial réel (prix, concurrent…).
        fields = ['id', 'nom', 'archived', 'est_junk', 'en_usage']

    def get_en_usage(self, obj):
        return _motif_en_usage(obj.company, obj.nom)


class CanalSerializer(serializers.ModelSerializer):
    # Nombre de leads utilisant ce canal — l'UI désactive la suppression si > 0.
    en_usage = serializers.SerializerMethodField()

    class Meta:
        from .models import Canal
        model = Canal
        fields = ['id', 'cle', 'libelle', 'ordre', 'protege', 'archived', 'en_usage']
        read_only_fields = ['protege']

    def get_en_usage(self, obj):
        from .models import Lead
        return Lead.objects.filter(company=obj.company, canal=obj.cle).count()

    def validate_cle(self, value):
        # La clé d'un canal protégé (ex. 'site_web') ne peut pas être renommée :
        # le webhook du site web en dépend.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'un canal protégé ne peut pas être modifiée.")
        return value


class WebsiteLeadPayloadSerializer(serializers.ModelSerializer):
    """QX16 — surface LECTURE SEULE des payloads bruts d'intake, pour que
    « jamais perdre un lead » (webhooks.py) soit vérifiable/actionnable, pas
    juste une promesse en commentaire. Le rejeu s'effectue via l'action
    ``replay`` du viewset (jamais depuis ce sérialiseur, jamais un champ
    modifiable ici).

    CRX2 — ``source``/``source_display`` disent de quel intake vient la ligne
    (site web ou Meta Lead Ads) : sans eux, l'écran ne pourrait pas expliquer
    ce qu'un rejeu va faire."""
    lead_nom = serializers.CharField(source='lead.nom', read_only=True, default=None)
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)

    class Meta:
        model = WebsiteLeadPayload
        fields = [
            'id', 'company', 'source', 'source_display', 'payload',
            'remote_addr', 'received_at', 'processed', 'error', 'lead',
            'lead_nom',
        ]
        read_only_fields = fields


class ParrainageSerializer(serializers.ModelSerializer):
    """N98 — parrainage. Société posée côté serveur ; parrain/filleul vérifiés
    appartenir à la même société (multi-tenant)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    parrain_nom = serializers.CharField(
        source='parrain.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # DC14 — nom du filleul à afficher : le FK lié prime sur le texte libre
    # (``filleul_nom`` peut diverger du client/lead réellement référencé).
    filleul_display_nom = serializers.CharField(read_only=True)

    class Meta:
        model = Parrainage
        fields = [
            'id', 'company', 'parrain', 'parrain_nom', 'filleul_lead',
            'filleul_client', 'filleul_nom', 'filleul_display_nom',
            'statut', 'statut_display',
            'recompense', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def _same_company(self, obj):
        req = self.context.get('request')
        return not (obj and req and obj.company_id != req.user.company_id)

    def validate_parrain(self, value):
        if not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_client(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Client inconnu.')
        return value

    def validate_filleul_lead(self, value):
        if value and not self._same_company(value):
            raise serializers.ValidationError('Lead inconnu.')
        return value


# DC12 — Profil site/énergie réutilisable par client ─────────────────────────

class SiteProfileSerializer(serializers.ModelSerializer):
    """DC12 — profil site/énergie réutilisable, attaché au client.

    Société posée CÔTÉ SERVEUR (HiddenField — jamais lue du corps de requête,
    multi-tenant). Le client référencé doit appartenir à la même société
    (validate_client). Une seule fiche par client (OneToOne)."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = SiteProfile
        fields = [
            'id', 'company', 'client',
            'facture_hiver', 'facture_ete', 'ete_differente',
            'conso_mensuelle_kwh', 'tranche_onee', 'raccordement',
            'regularisation_8221', 'type_installation',
            'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
            'type_toiture', 'surface_toiture_m2', 'orientation',
            'inclinaison_deg', 'ombrage', 'ombrage_notes',
            'gps_lat', 'gps_lng',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_client(self, value):
        req = self.context.get('request')
        if req and value and value.company_id != req.user.company_id:
            raise serializers.ValidationError('Client inconnu.')
        return value


# FG36 — Modèles de messages WhatsApp/SMS ─────────────────────────────────────

class MessageTemplateSerializer(serializers.ModelSerializer):
    """Modèle de message CRM (WhatsApp/SMS). Lecture tout rôle, écriture admin."""
    langue_display = serializers.CharField(
        source='get_langue_display', read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'nom', 'langue', 'langue_display', 'corps',
            'archived', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# QJ20 — Rendez-vous (visites commerciales/techniques) ───────────────────────

class AppointmentSerializer(serializers.ModelSerializer):
    """QJ20 — Rendez-vous sur un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lu du corps de requête). Le lead doit appartenir à la
    même société (validate_lead).
    ``statut_display`` et ``lead_nom`` sont en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'scheduled_at', 'statut', 'statut_display',
            'notes', 'reminder_sent', 'created_by',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['reminder_sent', 'created_by',
                            'date_creation', 'date_modification']

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value


# ── FG39 — ObjectifCommercial / KPI Target ────────────────────────────────────

class ObjectifCommercialSerializer(_CompanyScopedRelationsMixin,
                                   serializers.ModelSerializer):
    """Sérialise un objectif commercial + champs lecture optionnels."""

    # CRX13 — le porteur de l'objectif doit être un utilisateur de la société.
    scoped_relations = ('owner',)

    owner_nom = serializers.SerializerMethodField()
    metric_display = serializers.SerializerMethodField()
    period_type_display = serializers.SerializerMethodField()

    class Meta:
        model = ObjectifCommercial
        fields = [
            'id', 'company', 'owner', 'owner_nom',
            'metric', 'metric_display',
            'period_type', 'period_type_display',
            'period_year', 'period_month', 'period_quarter',
            'cible', 'notes',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification',
        ]

    def get_owner_nom(self, obj):
        return getattr(obj.owner, 'username', None)

    def get_metric_display(self, obj):
        return obj.get_metric_display()

    def get_period_type_display(self, obj):
        return obj.get_period_type_display()

    def validate(self, attrs):
        pt = attrs.get('period_type', getattr(self.instance, 'period_type', None))
        if pt == 'month' and not attrs.get(
                'period_month', getattr(self.instance, 'period_month', None)):
            raise serializers.ValidationError(
                {'period_month': 'Requis pour un objectif mensuel.'}
            )
        if pt == 'quarter' and not attrs.get(
                'period_quarter', getattr(self.instance, 'period_quarter', None)):
            raise serializers.ValidationError(
                {'period_quarter': 'Requis pour un objectif trimestriel.'}
            )
        month = attrs.get('period_month', getattr(self.instance, 'period_month', None))
        if month is not None and not (1 <= month <= 12):
            raise serializers.ValidationError(
                {'period_month': 'Doit être entre 1 et 12.'}
            )
        quarter = attrs.get('period_quarter', getattr(self.instance, 'period_quarter', None))
        if quarter is not None and not (1 <= quarter <= 4):
            raise serializers.ValidationError(
                {'period_quarter': 'Doit être entre 1 et 4.'}
            )
        return attrs


class ObjectifAttainmentSerializer(serializers.Serializer):
    """Lecture seule — objectif + réalisé + taux d'atteinte."""
    id = serializers.IntegerField()
    metric = serializers.CharField()
    metric_display = serializers.CharField()
    period_type = serializers.CharField()
    period_year = serializers.IntegerField()
    period_month = serializers.IntegerField(allow_null=True)
    period_quarter = serializers.IntegerField(allow_null=True)
    cible = serializers.DecimalField(max_digits=14, decimal_places=2)
    owner = serializers.IntegerField(allow_null=True)
    owner_nom = serializers.CharField(allow_null=True)
    realise = serializers.DecimalField(max_digits=14, decimal_places=2)
    taux = serializers.FloatField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()


# ── FG242 — Suivi des concurrents sur deals perdus ────────────────────────────

class ConcurrentPerteSerializer(serializers.ModelSerializer):
    """FG242 — concurrent gagnant + prix saisis sur un lead perdu.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``lead_nom`` est en lecture seule pour l'UI.
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)

    class Meta:
        model = ConcurrentPerte
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'concurrent_nom', 'concurrent_prix', 'devise', 'motif', 'notes',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_concurrent_prix(self, value):
        # Prix optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le prix du concurrent ne peut pas être négatif.')
        return value

    def validate_concurrent_nom(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le nom du concurrent est obligatoire.')
        return value


class PointContactSerializer(serializers.ModelSerializer):
    """FG204 — point de contact du parcours multi-touch d'un lead.

    La société est posée côté serveur (HiddenField depuis l'utilisateur courant
    — multi-tenant, jamais lue du corps de requête) ; ``saisi_par`` est forcé
    dans ``perform_create``. Le lead doit appartenir à la même société
    (validate_lead). ``date_contact`` est optionnel à la saisie (défaut : now).
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    saisi_par = serializers.PrimaryKeyRelatedField(read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()
    canal_libelle = serializers.CharField(
        source='get_canal_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None)
    date_contact = serializers.DateTimeField(required=False)

    class Meta:
        model = PointContact
        fields = [
            'id', 'company', 'lead', 'lead_nom',
            'canal', 'canal_libelle', 'source', 'date_contact', 'ordre',
            'detail', 'cout',
            'saisi_par', 'saisi_par_nom', 'saisi_le', 'date_modification',
        ]
        read_only_fields = [
            'saisi_par', 'saisi_le', 'date_modification',
        ]

    def get_saisi_par_nom(self, obj):
        return getattr(obj.saisi_par, 'username', None)

    def validate_lead(self, value):
        req = self.context.get('request')
        if req and value.company_id != getattr(req.user, 'company_id', None):
            raise serializers.ValidationError('Lead inconnu.')
        return value

    def validate_cout(self, value):
        # Coût optionnel mais jamais négatif (garde Decimal explicite en plus du
        # validateur modèle, pour un message clair côté API).
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le coût ne peut pas être négatif.')
        return value

    def validate_date_contact(self, value):
        # Si non fourni, retombe sur maintenant (le champ a un default côté
        # serveur via perform_create ; ici on accepte simplement la valeur).
        return value


# ── ZSAL2 — Plans d'activité ─────────────────────────────────────────────────

class EtapePlanActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtapePlanActivite
        fields = [
            'id', 'plan', 'ordre', 'activity_type', 'delai_jours',
            'resume_defaut', 'assigne_par_defaut',
        ]


class PlanActiviteSerializer(serializers.ModelSerializer):
    etapes = EtapePlanActiviteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanActivite
        fields = ['id', 'company', 'nom', 'actif', 'date_creation', 'etapes']
        read_only_fields = ['company', 'date_creation']


# ── ZSAL3 — Équipes commerciales (admin CRUD ; le dashboard « Mes équipes »
# lit stats_equipe() séparément, voir views.equipes_statistiques) ────────────

class EquipeCommercialeSerializer(_CompanyScopedRelationsMixin,
                                  serializers.ModelSerializer):
    # CRX13 — responsable ET membres (M2M) : le ``ManyRelatedField`` délègue à
    # son ``child_relation``, promu lui aussi.
    scoped_relations = ('responsable', 'membres')

    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    nb_membres = serializers.IntegerField(source='membres.count', read_only=True)

    class Meta:
        model = EquipeCommerciale
        fields = [
            'id', 'company', 'nom', 'responsable', 'responsable_nom',
            'membres', 'nb_membres', 'actif', 'date_creation',
        ]
        read_only_fields = ['company', 'date_creation']


# ── NTCRM4 — Catégories de forecast ──────────────────────────────────────────

class ForecastEntrySerializer(_CompanyScopedRelationsMixin,
                              serializers.ModelSerializer):
    # CRX13 — ``lead`` est un OneToOne : DRF lui greffe automatiquement un
    # ``UniqueValidator`` sur TOUTES les sociétés. Le champ est re-scopé ET son
    # validateur d'unicité aussi, sinon « déjà utilisé » sur un lead voisin
    # resterait un oracle d'existence.
    scoped_relations = ('lead',)

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    montant_effectif = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    owner_id = serializers.IntegerField(source='lead.owner_id', read_only=True)

    class Meta:
        model = ForecastEntry
        fields = [
            'id', 'lead', 'categorie', 'categorie_display', 'montant_prevu',
            'montant_effectif', 'owner_id', 'commentaire',
            'mis_a_jour_par', 'mis_a_jour_le',
        ]
        read_only_fields = ['mis_a_jour_par', 'mis_a_jour_le']

    def get_fields(self):
        fields = super().get_fields()
        _scope_unique_validators(fields.get('lead'))
        return fields


class ForecastSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForecastSnapshot
        fields = [
            'id', 'semaine_iso', 'categorie', 'montant_total', 'nb_leads',
            'owner', 'created_at',
        ]
        read_only_fields = fields


# ── NTCRM10 — Plan de compte ─────────────────────────────────────────────────
# ARC8 — l'historique (chatter) d'un PlanCompte est sérialisé par
# records.serializers.ChatterActivitySerializer (records.Activity), plus aucun
# serializer *Activity maison ici.


class RevueCompteSerializer(_CompanyScopedRelationsMixin,
                            serializers.ModelSerializer):
    # CRX13 — ``plan`` est la SEULE frontière société de ce modèle (RevueCompte
    # n'a pas de ``company`` propre) : sans re-scope, une revue pouvait être
    # accrochée au plan de compte d'une autre société.
    scoped_relations = ('plan',)

    class Meta:
        model = RevueCompte
        fields = [
            'id', 'plan', 'date_revue', 'participants', 'decisions',
            'prochaine_action', 'prochaine_action_date', 'created_by',
            'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']


class PlanCompteSerializer(_CompanyScopedRelationsMixin,
                           serializers.ModelSerializer):
    # CRX13 — le client du plan de compte, à la CRÉATION comme au PATCH.
    scoped_relations = ('client',)

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    revues = RevueCompteSerializer(many=True, read_only=True)

    class Meta:
        model = PlanCompte
        fields = [
            'id', 'client', 'objectifs_strategiques', 'potentiel_estime',
            'concurrents_presents', 'swot_forces', 'swot_faiblesses',
            'swot_opportunites', 'swot_menaces', 'prochaine_revue', 'statut',
            'statut_display', 'created_by', 'mis_a_jour_par', 'revues',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'mis_a_jour_par', 'date_creation', 'date_modification',
        ]


# ── NTCRM12 — Playbooks de vente par étape ───────────────────────────────────

class PlaybookTacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookTache
        fields = ['id', 'etape', 'libelle', 'obligatoire', 'ordre']


class PlaybookEtapeSerializer(serializers.ModelSerializer):
    stage_display = serializers.SerializerMethodField()
    taches = PlaybookTacheSerializer(many=True, read_only=True)

    class Meta:
        model = PlaybookEtape
        fields = ['id', 'playbook', 'stage', 'stage_display', 'ordre', 'taches']

    def get_stage_display(self, obj):
        from . import stages
        return stages.STAGE_LABELS.get(obj.stage, obj.stage)


class PlaybookSerializer(serializers.ModelSerializer):
    etapes = PlaybookEtapeSerializer(many=True, read_only=True)

    class Meta:
        model = Playbook
        # CRX35 — 'bloquant' retiré : le champ n'existe plus (rien ne le lisait).
        fields = ['id', 'nom', 'actif', 'condition', 'etapes', 'date_creation']
        read_only_fields = ['date_creation']


class LeadPlaybookProgressSerializer(serializers.ModelSerializer):
    tache_libelle = serializers.CharField(source='tache.libelle', read_only=True)
    tache_obligatoire = serializers.BooleanField(
        source='tache.obligatoire', read_only=True)
    etape_stage = serializers.CharField(source='tache.etape.stage', read_only=True)
    fait_par_nom = serializers.CharField(
        source='fait_par.username', read_only=True, default=None)

    class Meta:
        model = LeadPlaybookProgress
        fields = [
            'id', 'lead', 'tache', 'tache_libelle', 'tache_obligatoire',
            'etape_stage', 'fait', 'fait_par', 'fait_par_nom', 'fait_le',
            'created_at',
        ]
        read_only_fields = ['fait_par', 'fait_le', 'created_at']


# ── LB48 — Vues enregistrées par compte ────────────────────────────────────

class SavedViewSerializer(serializers.ModelSerializer):
    """LB48 — vue enregistrée personnelle (filtres + disposition d'une page).

    ``company`` n'est PAS exposé : toujours posé côté serveur
    (``SavedViewViewSet.perform_create`` — jamais lu du corps de requête),
    comme ``MessageTemplateSerializer``. ``user`` est un ``HiddenField``
    (jamais lisible/écrivable par le client — ``write_only`` implicite) posé
    depuis l'utilisateur courant : nécessaire pour que le validateur
    d'unicité auto-généré par DRF sur la contrainte ``(user, page, name)``
    s'active (DRF n'ajoute le ``UniqueTogetherValidator`` que si TOUS les
    champs de la contrainte sont représentés dans le serializer — sans ce
    champ cachée, un doublon lèverait une ``IntegrityError`` (500) au lieu
    d'un 400 propre).
    """
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = SavedView
        fields = ['id', 'page', 'name', 'rank', 'payload', 'created_at', 'user']
        read_only_fields = ['created_at']


class SalleVenteItemSerializer(serializers.ModelSerializer):
    """NTCRM17 — un élément (devis/document/lien vidéo/note) d'une salle de vente."""

    class Meta:
        model = SalleVenteItem
        fields = ['id', 'salle', 'type', 'reference', 'titre', 'ordre', 'created_at']
        read_only_fields = ['created_at']


class SalleVenteSerializer(_CompanyScopedRelationsMixin,
                           serializers.ModelSerializer):
    """NTCRM17 — salle de vente digitale (écran interne, authentifié).

    ``company`` est TOUJOURS posé côté serveur (jamais lu du corps).
    ``token``/``password_hash`` ne sont jamais exposés en écriture ; un mot
    de passe est posé via le champ ``write_only`` ``mot_de_passe`` (haché
    côté serveur, jamais stocké en clair). ``has_password`` expose
    seulement un booléen — jamais le hash."""

    # CRX13 — la salle référence exactement un lead OU un client : les deux
    # relations sont re-scopées société.
    scoped_relations = ('lead', 'client')

    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    items = SalleVenteItemSerializer(many=True, read_only=True)
    has_password = serializers.BooleanField(read_only=True)
    lien_public = serializers.SerializerMethodField()
    mot_de_passe = serializers.CharField(
        write_only=True, required=False, allow_blank=True)

    class Meta:
        model = SalleVente
        fields = [
            'id', 'company', 'lead', 'client', 'titre', 'token', 'expires_at',
            'actif', 'has_password', 'mot_de_passe', 'lien_public', 'items',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['token', 'created_by', 'created_at', 'updated_at']

    def get_lien_public(self, obj):
        return f'/salle-vente/{obj.token}'

    def validate(self, attrs):
        # NTCRM17 — piège DRF/HTML : `BooleanField.default_empty_html` vaut
        # False, donc un `actif` ABSENT d'un POST/PUT en form-data (une case
        # décochée n'est pas envoyée par un navigateur) arrive ici à False et
        # créait une salle immédiatement RÉVOQUÉE (lien public en 410). Une
        # requête qui ne parle pas d'`actif` ne doit jamais le modifier : on
        # retombe sur le défaut du modèle (création) ou sur la valeur en base
        # (mise à jour). Un `actif: false` EXPLICITE reste évidemment honoré.
        if 'actif' in attrs and 'actif' not in getattr(self, 'initial_data', {}):
            attrs.pop('actif')
        lead = attrs.get('lead', getattr(self.instance, 'lead', None))
        client = attrs.get('client', getattr(self.instance, 'client', None))
        if bool(lead) == bool(client):
            raise serializers.ValidationError(
                'Une salle de vente doit référencer exactement un lead OU un '
                'client (jamais les deux, jamais ni l\'un ni l\'autre).')
        return attrs

    def create(self, validated_data):
        mot_de_passe = validated_data.pop('mot_de_passe', '')
        instance = SalleVente(**validated_data)
        instance.set_password(mot_de_passe)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if 'mot_de_passe' in validated_data:
            instance.set_password(validated_data.pop('mot_de_passe'))
        return super().update(instance, validated_data)


class ApporteurSerializer(serializers.ModelSerializer):
    """NTCRM20 — apporteur d'affaires. ``company`` posé côté serveur."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())

    class Meta:
        model = Apporteur
        fields = [
            'id', 'company', 'nom', 'type_apporteur', 'contact_email',
            'contact_telephone', 'taux_commission_pct', 'actif', 'rib',
            'created_at', 'token_acces',
        ]
        read_only_fields = ['created_at', 'token_acces']


class DealEnregistreSerializer(_CompanyScopedRelationsMixin,
                               serializers.ModelSerializer):
    """NTCRM20 — deal enregistré par un apporteur. La fenêtre de protection
    (``clean()`` du modèle) est appliquée via ``full_clean()`` explicite
    (DRF n'invoque jamais la validation modèle automatiquement)."""

    # CRX13 — l'apporteur et le lead protégé doivent être de la société.
    scoped_relations = ('apporteur', 'lead')

    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    apporteur_nom = serializers.CharField(source='apporteur.nom', read_only=True)
    lead_nom = serializers.CharField(source='lead.nom', read_only=True)

    class Meta:
        model = DealEnregistre
        fields = [
            'id', 'company', 'apporteur', 'apporteur_nom', 'lead', 'lead_nom',
            'date_enregistrement', 'statut', 'expire_le',
            'montant_commission_estime', 'montant_commission_du',
        ]
        read_only_fields = [
            'date_enregistrement', 'statut', 'expire_le',
            'montant_commission_estime', 'montant_commission_du',
        ]

    def validate(self, attrs):
        instance = DealEnregistre(**{**attrs, 'pk': getattr(self.instance, 'pk', None)})
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else str(exc))
        return attrs


class DefiSerializer(serializers.ModelSerializer):
    """NTCRM23 — défi d'équipe. ``company`` posé côté serveur."""
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    metrique_display = serializers.CharField(
        source='get_metrique_display', read_only=True)

    class Meta:
        model = Defi
        fields = [
            'id', 'company', 'nom', 'periode_debut', 'periode_fin',
            'metrique', 'metrique_display', 'cible_equipe', 'recompense',
            'actif', 'created_at',
        ]
        read_only_fields = ['created_at']
