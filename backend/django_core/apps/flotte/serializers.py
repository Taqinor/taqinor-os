"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant).
"""
from rest_framework import serializers

from .models import (
    ActifFlotte,
    AffectationConducteur,
    CarteCarburant,
    Conducteur,
    EnginRoulant,
    EtatDesLieux,
    PleinCarburant,
    ReferentielFlotte,
    ReservationVehicule,
    Vehicule,
)


class VehiculeSerializer(serializers.ModelSerializer):
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # FLOTTE3 — libellé en lecture de l'emplacement de stock lié (résolu via le
    # sélecteur de `apps.stock`, dégrade sur l'id nu).
    emplacement_stock_label = serializers.SerializerMethodField()

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'modele', 'energie',
            'energie_display', 'kilometrage', 'valeur', 'statut',
            'statut_display', 'categorie_permis_requise',
            'emplacement_stock_id', 'emplacement_stock_label',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_emplacement_stock_label(self, obj):
        from .selectors import emplacement_stock_label
        return emplacement_stock_label(
            obj.company, obj.emplacement_stock_id)

    def validate_emplacement_stock_id(self, value):
        """FLOTTE3 — Valide (best-effort) que l'id pointe un EmplacementStock de
        la MÊME société, via le sélecteur de `apps.stock` (import local, jamais
        `apps.stock.models`). Si le sélecteur est indisponible, dégrade : on
        stocke l'id sans valider (comportement de la lane PROJ2)."""
        if value in (None, ''):
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        try:
            from apps.stock import selectors as stock_selectors
        except Exception:
            return value
        getter = getattr(stock_selectors, 'get_emplacement_scoped', None)
        if getter is None:
            # Le stock n'expose pas de sélecteur adapté : on dégrade (store-only).
            return value
        if getter(company, value) is None:
            raise serializers.ValidationError(
                "Emplacement de stock introuvable pour cette société.")
        return value


class EnginRoulantSerializer(serializers.ModelSerializer):
    type_engin_display = serializers.CharField(
        source='get_type_engin_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = EnginRoulant
        fields = [
            'id', 'nom', 'type_engin', 'type_engin_display', 'marque',
            'modele', 'compteur_heures', 'valeur', 'statut', 'statut_display',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class ReferentielFlotteSerializer(serializers.ModelSerializer):
    """FLOTTE6 — entrée d'une liste de référence éditable du parc.

    ``company`` n'est jamais exposée en écriture : elle est posée côté serveur
    par le ``TenantMixin``. L'unicité ``(company, domaine, code)`` est validée
    par société (le scope société est appliqué dans le sérialiseur, jamais lu du
    corps de requête)."""

    domaine_display = serializers.CharField(
        source='get_domaine_display', read_only=True)

    class Meta:
        model = ReferentielFlotte
        fields = [
            'id', 'domaine', 'domaine_display', 'code', 'libelle', 'ordre',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Vérifie l'unicité (company, domaine, code) DANS la société courante.

        Le ``UniqueTogetherValidator`` par défaut inclut ``company``, absent des
        champs exposés ; on revalide donc explicitement avec la société du
        serveur pour renvoyer une 400 lisible plutôt qu'une 500 d'intégrité."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return attrs
        domaine = attrs.get('domaine', getattr(self.instance, 'domaine', None))
        code = attrs.get('code', getattr(self.instance, 'code', None))
        qs = ReferentielFlotte.objects.filter(
            company=company, domaine=domaine, code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'code': "Ce code existe déjà pour ce domaine."})
        return attrs


class ConducteurSerializer(serializers.ModelSerializer):
    """FLOTTE7 — conducteur / chauffeur avec informations de permis.

    ``company`` n'est JAMAIS exposée en écriture (posée côté serveur via
    ``TenantMixin``). ``user`` est facultatif : un conducteur externe sans
    compte ERP peut être enregistré sans liaison utilisateur.

    Champ lecture seule :
    - ``user_display`` : nom complet de l'utilisateur ERP lié, ou ``None``.
    """

    user_display = serializers.SerializerMethodField()

    class Meta:
        model = Conducteur
        fields = [
            'id', 'user', 'user_display', 'nom', 'telephone',
            'numero_permis', 'categorie_permis',
            'date_obtention', 'date_expiration',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_user_display(self, obj):
        if obj.user_id is None:
            return None
        user = obj.user
        full = (
            f'{user.first_name} {user.last_name}'.strip()
            or user.username
        )
        return full

    def validate_user(self, value):
        """Vérifie que l'utilisateur lié appartient à la même société."""
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Cet utilisateur n'appartient pas à votre société.")
        return value


class ActifFlotteSerializer(serializers.ModelSerializer):
    """FLOTTE5 — référence d'actif unifiée (Vehicule | EnginRoulant).

    ``company`` est posée côté serveur par le ``TenantMixin`` — jamais lue du
    corps de requête. Les champs ``vehicule`` et ``engin`` acceptent les ids
    des actifs de la MÊME société ; la validation (exactement l'un des deux)
    est déléguée au modèle (``full_clean`` dans ``save``).

    Champs lecture seule :
    - ``type_actif`` : 'vehicule' | 'engin'
    - ``label``      : désignation lisible de l'actif cible
    """

    type_actif = serializers.CharField(read_only=True)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = ActifFlotte
        fields = [
            'id', 'vehicule', 'engin', 'type_actif', 'label', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Vérifie que exactement un des deux FKs est fourni ET que l'actif
        cible appartient à la société courante."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        engin = attrs.get(
            'engin', getattr(self.instance, 'engin', None))

        has_vehicule = vehicule is not None
        has_engin = engin is not None

        if has_vehicule and has_engin:
            raise serializers.ValidationError(
                "Un actif ne peut pointer qu'un véhicule OU un engin, pas les "
                "deux.")
        if not has_vehicule and not has_engin:
            raise serializers.ValidationError(
                "Renseignez soit 'vehicule' soit 'engin'.")

        if company is not None:
            if has_vehicule and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule': "Ce véhicule n'appartient pas à votre société."})
            if has_engin and engin.company_id != company.id:
                raise serializers.ValidationError(
                    {'engin': "Cet engin n'appartient pas à votre société."})

        return attrs


class AffectationConducteurSerializer(serializers.ModelSerializer):
    """FLOTTE8 — Affectation datée conducteur ↔ véhicule.

    ``company`` est posée côté serveur par le ``TenantMixin`` (jamais lue du
    corps de requête). Les FKs ``conducteur`` et ``vehicule`` doivent appartenir
    à la même société que l'utilisateur courant. La validation garantit que
    ``date_fin >= date_debut`` quand ``date_fin`` est renseignée.

    FLOTTE9 — Contrôle « permis valide / catégorie » à l'affectation : par
    défaut, une affectation dont le conducteur n'a pas de permis valide (numéro/
    catégorie manquant, permis expiré, ou catégorie inadaptée au véhicule) est
    REJETÉE (400). Le drapeau écriture-seule ``force`` dégrade ce rejet en
    soft-warn : l'affectation est acceptée et l'avertissement est exposé en
    lecture via ``permis_avertissement``.

    Champs lecture seule :
    - ``conducteur_nom``       : nom complet du conducteur.
    - ``vehicule_label``       : immatriculation + marque/modèle du véhicule.
    - ``permis_avertissement`` : message du contrôle de permis quand
      l'affectation a été forcée malgré une non-conformité, sinon ``None``.
    """

    conducteur_nom = serializers.SerializerMethodField()
    vehicule_label = serializers.SerializerMethodField()
    # FLOTTE9 — drapeau écriture-seule : dégrade le rejet du contrôle de permis
    # en soft-warn (l'affectation est créée malgré la non-conformité).
    force = serializers.BooleanField(write_only=True, required=False,
                                     default=False)
    permis_avertissement = serializers.SerializerMethodField()

    class Meta:
        model = AffectationConducteur
        fields = [
            "id",
            "conducteur",
            "conducteur_nom",
            "vehicule",
            "vehicule_label",
            "date_debut",
            "date_fin",
            "notes",
            "actif",
            "force",
            "permis_avertissement",
            "date_creation",
        ]
        read_only_fields = ["date_creation"]

    def get_permis_avertissement(self, obj):
        """Avertissement de permis posé lors d'une affectation forcée
        (non-conformité acceptée volontairement)."""
        return getattr(obj, '_permis_avertissement', None)

    def get_conducteur_nom(self, obj):
        return str(obj.conducteur) if obj.conducteur_id else None

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def validate(self, attrs):
        """Valide la plage de dates et l'appartenance à la société courante."""
        request = self.context.get("request")
        company = getattr(getattr(request, "user", None), "company", None)

        conducteur = attrs.get(
            "conducteur", getattr(self.instance, "conducteur", None))
        vehicule = attrs.get(
            "vehicule", getattr(self.instance, "vehicule", None))
        date_debut = attrs.get(
            "date_debut", getattr(self.instance, "date_debut", None))
        date_fin = attrs.get(
            "date_fin", getattr(self.instance, "date_fin", None))

        # Plage de dates : date_fin >= date_debut quand fournie.
        if date_debut is not None and date_fin is not None:
            if date_fin < date_debut:
                raise serializers.ValidationError(
                    {"date_fin": "La date de fin doit être postérieure ou égale"
                     " à la date de début."})

        # Vérification de société sur les FKs.
        if company is not None:
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {"conducteur":
                     "Ce conducteur n'appartient pas à votre société."})
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {"vehicule":
                     "Ce véhicule n'appartient pas à votre société."})

        # FLOTTE9 — Contrôle « permis valide / catégorie » à l'affectation.
        # Par défaut : rejet (400) si le conducteur n'a pas un permis valide de
        # la bonne catégorie ; ``force=True`` dégrade en soft-warn.
        force = attrs.pop('force', False)
        self._permis_avertissement = None
        if conducteur is not None and vehicule is not None:
            from .services import controle_permis
            ok, _code, message = controle_permis(conducteur, vehicule)
            if not ok:
                if force:
                    self._permis_avertissement = message
                else:
                    raise serializers.ValidationError({"conducteur": message})

        return attrs

    def _attach_warning(self, instance):
        instance._permis_avertissement = getattr(
            self, '_permis_avertissement', None)
        return instance

    def create(self, validated_data):
        return self._attach_warning(super().create(validated_data))

    def update(self, instance, validated_data):
        return self._attach_warning(super().update(instance, validated_data))


# ── FLOTTE10 — Réservation de véhicule + détection de conflit ────────────────

class ReservationVehiculeSerializer(serializers.ModelSerializer):
    """FLOTTE10 — Réservation datée d'un véhicule avec détection de conflit.

    ``company`` est posée côté serveur par le ``TenantMixin`` (jamais lue du
    corps de requête). Les FKs ``vehicule`` et ``conducteur`` doivent appartenir
    à la société courante. La validation rejette (400) toute réservation active
    qui chevauche une autre réservation active du même véhicule (service
    ``reservations_en_conflit``).

    Champs lecture seule :
    - ``vehicule_label``   : immatriculation + marque/modèle.
    - ``conducteur_nom``   : nom du conducteur prévu, ou ``None``.
    - ``statut_display``   : libellé du statut.
    """

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    vehicule_label = serializers.SerializerMethodField()
    conducteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ReservationVehicule
        fields = [
            'id', 'vehicule', 'vehicule_label', 'conducteur', 'conducteur_nom',
            'debut', 'fin', 'motif', 'statut', 'statut_display', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_conducteur_nom(self, obj):
        return str(obj.conducteur) if obj.conducteur_id else None

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))
        debut = attrs.get('debut', getattr(self.instance, 'debut', None))
        fin = attrs.get('fin', getattr(self.instance, 'fin', None))
        statut = attrs.get(
            'statut',
            getattr(self.instance, 'statut',
                    ReservationVehicule.Statut.DEMANDEE))

        # Plage horaire : fin > debut.
        if debut is not None and fin is not None and fin <= debut:
            raise serializers.ValidationError(
                {'fin': "La date de fin doit être postérieure à la date de "
                        "début."})

        # Appartenance société.
        if company is not None:
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule':
                     "Ce véhicule n'appartient pas à votre société."})
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {'conducteur':
                     "Ce conducteur n'appartient pas à votre société."})

        # Détection de conflit — uniquement pour une réservation active.
        if company is not None and vehicule is not None \
                and debut is not None and fin is not None \
                and statut in ReservationVehicule.STATUTS_ACTIFS:
            from .services import reservations_en_conflit
            exclude_pk = self.instance.pk if self.instance is not None else None
            conflits = reservations_en_conflit(
                company, vehicule, debut, fin, exclude_pk=exclude_pk)
            premier = conflits.first()
            if premier is not None:
                raise serializers.ValidationError(
                    {'debut': "Ce véhicule est déjà réservé sur ce créneau "
                              f"(conflit avec la réservation #{premier.pk})."})

        return attrs


# ── FLOTTE11 — Check-list état des lieux départ / retour (photos) ────────────

class EtatDesLieuxSerializer(serializers.ModelSerializer):
    """FLOTTE11 — Check-list d'état des lieux d'un véhicule (photos).

    ``company`` est posée côté serveur (jamais lue du corps de requête). Les FKs
    (``vehicule``, ``reservation``, ``conducteur``) doivent appartenir à la
    société courante. ``points`` et ``photos`` sont des listes JSON.

    Champs lecture seule :
    - ``vehicule_label`` : désignation du véhicule.
    - ``moment_display`` / ``etat_general_display`` : libellés.
    - ``nb_photos``      : nombre de photos jointes.
    """

    moment_display = serializers.CharField(
        source='get_moment_display', read_only=True)
    etat_general_display = serializers.CharField(
        source='get_etat_general_display', read_only=True)
    vehicule_label = serializers.SerializerMethodField()
    nb_photos = serializers.IntegerField(read_only=True)

    class Meta:
        model = EtatDesLieux
        fields = [
            'id', 'vehicule', 'vehicule_label', 'reservation', 'conducteur',
            'moment', 'moment_display', 'date_constat', 'kilometrage',
            'niveau_carburant', 'etat_general', 'etat_general_display',
            'points', 'photos', 'nb_photos', 'commentaire', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def validate_niveau_carburant(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                "Le niveau de carburant doit être compris entre 0 et 100 %.")
        return value

    def validate_points(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Le champ 'points' doit être une liste.")
        return value

    def validate_photos(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Le champ 'photos' doit être une liste de clés.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return attrs

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        reservation = attrs.get(
            'reservation', getattr(self.instance, 'reservation', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))

        if vehicule is not None and vehicule.company_id != company.id:
            raise serializers.ValidationError(
                {'vehicule': "Ce véhicule n'appartient pas à votre société."})
        if reservation is not None and reservation.company_id != company.id:
            raise serializers.ValidationError(
                {'reservation':
                 "Cette réservation n'appartient pas à votre société."})
        if conducteur is not None and conducteur.company_id != company.id:
            raise serializers.ValidationError(
                {'conducteur':
                 "Ce conducteur n'appartient pas à votre société."})
        return attrs


# ── FLOTTE12 — Carnet de carburant (`PleinCarburant`) ────────────────────────

class PleinCarburantSerializer(serializers.ModelSerializer):
    """FLOTTE12 — Un plein de carburant au carnet d'un véhicule.

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    véhicule (et le conducteur si fourni) doivent appartenir à la société
    courante. La cohérence du kilométrage (compteur monotone croissant) est
    vérifiée via ``services.kilometrage_incoherent`` → 400 si le compteur recule.

    Champs lecture seule :
    - ``vehicule_label``  : désignation du véhicule.
    - ``unite_display``   : libellé de l'unité.
    - ``prix_unitaire``   : prix par litre / kWh (MAD), ``None`` si quantité nulle.
    """

    unite_display = serializers.CharField(
        source='get_unite_display', read_only=True)
    vehicule_label = serializers.SerializerMethodField()
    prix_unitaire = serializers.SerializerMethodField()

    class Meta:
        model = PleinCarburant
        fields = [
            'id', 'vehicule', 'vehicule_label', 'conducteur', 'date_plein',
            'kilometrage', 'quantite', 'unite', 'unite_display', 'prix_total',
            'prix_unitaire', 'plein_complet', 'station', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_prix_unitaire(self, obj):
        return obj.prix_unitaire

    def validate_quantite(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La quantité ne peut pas être négative.")
        return value

    def validate_prix_total(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le prix total ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))
        kilometrage = attrs.get(
            'kilometrage', getattr(self.instance, 'kilometrage', None))
        date_plein = attrs.get(
            'date_plein', getattr(self.instance, 'date_plein', None))

        if company is not None:
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule':
                     "Ce véhicule n'appartient pas à votre société."})
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {'conducteur':
                     "Ce conducteur n'appartient pas à votre société."})

            # Cohérence du kilométrage (compteur monotone croissant).
            if vehicule is not None and kilometrage is not None \
                    and date_plein is not None:
                from .services import kilometrage_incoherent
                exclude_pk = (
                    self.instance.pk if self.instance is not None else None)
                incoherent, message = kilometrage_incoherent(
                    company, vehicule, kilometrage, date_plein,
                    exclude_pk=exclude_pk)
                if incoherent:
                    raise serializers.ValidationError({'kilometrage': message})

        return attrs


class CarteCarburantSerializer(serializers.ModelSerializer):
    """FLOTTE14 — Carte carburant de la société.

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    véhicule et le conducteur attribués (si fournis) doivent appartenir à la
    société courante. Le plafond ne peut pas être négatif.

    Champs lecture seule :
    - ``vehicule_label``   : désignation du véhicule attribué (ou ``None``).
    - ``conducteur_label`` : nom du conducteur attribué (ou ``None``).
    """

    vehicule_label = serializers.SerializerMethodField()
    conducteur_label = serializers.SerializerMethodField()

    class Meta:
        model = CarteCarburant
        fields = [
            'id', 'numero', 'vehicule', 'vehicule_label', 'conducteur',
            'conducteur_label', 'plafond', 'actif', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_conducteur_label(self, obj):
        return str(obj.conducteur) if obj.conducteur_id else None

    def validate_plafond(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le plafond ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))

        if company is not None:
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule':
                     "Ce véhicule n'appartient pas à votre société."})
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {'conducteur':
                     "Ce conducteur n'appartient pas à votre société."})

        return attrs
