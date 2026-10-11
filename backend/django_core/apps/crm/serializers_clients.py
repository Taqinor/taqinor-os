"""SPL76 — sérialiseurs du sous-parcours clients (salle de vente,
apporteurs, deals, défis, T-TRACE, partenaires), déplacés de
``serializers.py`` à l'identique (move only). Dépendance à sens unique : ce
module importe ``.serializers``, jamais l'inverse.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    AppareilEquipe, Apporteur, Client, DealEnregistre, Defi, Partenaire, SalleVente,
    SalleVenteItem, VisiteExterne,
)
from .serializers import (
    _CompanyScopedRelationsMixin, _CurrentCompanyDefault, _LeadEnPorteeMixin,
)


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

    @extend_schema_field(serializers.CharField())
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


class DealEnregistreSerializer(_LeadEnPorteeMixin,
                               _CompanyScopedRelationsMixin,
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


class VisiteExterneSerializer(serializers.ModelSerializer):
    """T-TRACE — UNE trace de visite externe, lecture seule (voir
    ``apps/crm/visites.py`` pour tout ce que la finalité anti-fraude couvre).
    ``lead_nom`` est en lecture seule pour l'écran de revue."""
    point_display = serializers.CharField(
        source='get_point_display', read_only=True)
    lead_nom = serializers.CharField(
        source='lead.nom', read_only=True, default=None,
        allow_null=True)

    class Meta:
        model = VisiteExterne
        fields = [
            'id', 'point', 'point_display', 'contexte', 'token_suffixe',
            'ip', 'user_agent', 'langue', 'appareil_id', 'duree_s',
            'terminee', 'lead', 'lead_nom', 'created_at',
        ]
        read_only_fields = fields


class AppareilEquipeSerializer(serializers.ModelSerializer):
    """QJ-EQUIPE-2 — un appareil ÉQUIPE, exclu du traçage anti-fraude.

    La société et ``cree_par`` sont posés côté serveur (jamais lus du corps de
    requête, multi-tenant) ; voir ``crm.services.enregistrer_appareil_equipe``,
    l'unique chemin d'écriture du registre (``create`` et ``ce_navigateur``).
    """
    company = serializers.HiddenField(default=_CurrentCompanyDefault())
    cree_par = serializers.PrimaryKeyRelatedField(read_only=True)
    cree_par_nom = serializers.CharField(
        source='cree_par.get_full_name', read_only=True, default=None,
        allow_null=True)

    class Meta:
        model = AppareilEquipe
        fields = [
            'id', 'company', 'appareil_id', 'libelle',
            'cree_par', 'cree_par_nom', 'created_at',
        ]
        read_only_fields = ['created_at']
        # Pas de UniqueTogetherValidator auto (company, appareil_id) : la vue
        # rend le POST idempotent (re-marquer met à jour le libellé, jamais un
        # 400) — la contrainte DB reste le filet contre une vraie course.
        validators = []


class PartenaireSerializer(serializers.ModelSerializer):
    """Partenaires commerciaux (apporteurs/sous-revendeurs/installateurs,
    FG234/FG237) + couche certification NTMIG26.

    SOLMVP10/SOLMVP30b — ce serializer vivait dans ``apps.compta`` (shim
    ODX13, réexporté ici) ; compta est désormais une coquille parquée sans
    aucune url (``core.parked``), donc ``crm.Partenaire`` — qui n'a jamais
    quitté cette app — reprend nativement sa propre surface API. Aucun champ
    n'a changé : seule la maison a bougé.
    """
    certification_expiree = serializers.BooleanField(read_only=True)
    rang_certification = serializers.IntegerField(read_only=True)
    specialites = serializers.ListField(
        child=serializers.CharField(), required=False)

    class Meta:
        model = Partenaire
        fields = [
            'id', 'nom', 'type_partenaire', 'email', 'telephone',
            'taux_commission', 'token_acces', 'actif',
            'statut_onboarding', 'numero_agrement', 'zone', 'date_activation',
            'niveau_certification', 'date_certification',
            'date_expiration_certification', 'specialites',
            'nb_deploiements_reussis', 'certification_expiree',
            'rang_certification',
            'date_creation',
        ]
        read_only_fields = [
            'token_acces', 'date_activation', 'date_creation',
            # NTMIG26 — le compteur de déploiements est de l'HISTORIQUE : il
            # s'alimente par l'enregistrement d'un déploiement (NTMIG28), pas
            # par un PATCH qui permettrait de gonfler son propre score.
            'nb_deploiements_reussis', 'certification_expiree',
            'rang_certification',
        ]

    def validate_specialites(self, value):
        """NTMIG26 — spécialités prises dans la liste FERMÉE du référentiel.

        Une valeur libre rendrait l'annuaire des certifiés infiltrable :
        « Compta », « compta » et « COMPTA » seraient trois spécialités
        distinctes qu'aucun filtre ne retrouverait ensemble.
        """
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'Les spécialités doivent être une liste de clés de module.')
        connues_cles = Partenaire.SPECIALITES_CLES
        inconnues = [str(v) for v in value if str(v) not in connues_cles]
        if inconnues:
            connues = ', '.join(connues_cles)
            raise serializers.ValidationError(
                f"Spécialité(s) inconnue(s) : {', '.join(inconnues)}. "
                f'Valeurs acceptées : {connues}.')
        # Dédoublonne en préservant l'ordre de saisie.
        vues, propres = set(), []
        for v in value:
            if str(v) in vues:
                continue
            vues.add(str(v))
            propres.append(str(v))
        return propres

    def validate(self, attrs):
        """NTMIG26 — une échéance de certification antérieure à sa date de
        délivrance décrirait une certification née expirée."""
        attrs = super().validate(attrs)
        instance = getattr(self, 'instance', None)
        debut = attrs.get(
            'date_certification', getattr(instance, 'date_certification', None))
        fin = attrs.get(
            'date_expiration_certification',
            getattr(instance, 'date_expiration_certification', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({
                'date_expiration_certification': (
                    "L'expiration ne peut pas précéder la date de "
                    'certification.')})
        return attrs


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
    created_by = serializers.PrimaryKeyRelatedField(
        read_only=True, allow_null=True)
    created_by_nom = serializers.SerializerMethodField()
    # CIQ402 (contrat CIQ8 ``client_entreprise.json``, D-CIQ-11) — ce qui
    # manque à l'identité légale d'un client entreprise et ce que chaque
    # étape exige (rien ne bloque un devis). Pur, sans requête.
    identite_entreprise = serializers.SerializerMethodField()

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

    def validate_ice(self, value):
        # NTI18N19 — validateur MA formalisé (framework extensible par
        # pack_pays, NTI18N16 — pas encore construit, GATED-founder : en
        # attendant, 'MA' est passé en dur, comportement historique puisque
        # toute société actuelle EST marocaine). Jamais bloquant pour un
        # champ vide (optionnel côté modèle).
        from apps.parametres.tax_id_validators import validate_tax_id
        resultat = validate_tax_id('MA', 'ice', value)
        if not resultat['valide']:
            raise serializers.ValidationError(resultat['message'])
        return value

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

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_created_by_nom(self, obj):
        return getattr(obj.created_by, 'username', None)

    @extend_schema_field(serializers.DictField())
    def get_identite_entreprise(self, obj):
        from .models import identite_entreprise
        return identite_entreprise(
            entreprise=obj.type_client == Client.TypeClient.ENTREPRISE,
            raison_sociale=obj.nom,
            raison_a_confirmer=obj.raison_sociale_a_confirmer,
            ice=obj.ice, rc=obj.rc, if_fiscal=obj.if_fiscal,
            adresse_siege=obj.adresse_siege, adresse=obj.adresse)

    @extend_schema_field(serializers.IntegerField())
    def get_devis_count(self, obj):
        return obj.devis.count()

    @extend_schema_field(serializers.CharField())
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

    @extend_schema_field(serializers.CharField())
    def get_total_paye(self, obj):
        """Total ENCAISSÉ du client (somme des montant_paye des factures)."""
        from decimal import Decimal
        total = Decimal('0')
        for f in obj.factures.all():
            if f.statut != 'annulee':
                total += f.montant_paye
        return str(total)
