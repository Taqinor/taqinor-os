"""SPL76 — sérialiseurs du sous-parcours clients (salle de vente,
apporteurs, deals, défis, T-TRACE, partenaires), déplacés de
``serializers.py`` à l'identique (move only). Dépendance à sens unique : ce
module importe ``.serializers``, jamais l'inverse.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    AppareilEquipe, Apporteur, DealEnregistre, Defi, Partenaire, SalleVente,
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
