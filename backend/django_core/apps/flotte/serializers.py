"""Sérialiseurs du module Gestion de flotte.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par le
``TenantMixin`` (``perform_create``). Aucune valeur de société du corps de requête
n'est jamais acceptée (multi-tenant).
"""
from rest_framework import serializers

from .models import (
    ActifFlotte,
    AffectationConducteur,
    AssuranceVehicule,
    BaremeVignette,
    CarteCarburant,
    CarteGriseVehicule,
    Conducteur,
    ContratVehicule,
    CoutVehicule,
    DemandeVehicule,
    EcheanceEntretien,
    EcheanceReglementaire,
    EnginRoulant,
    EtatDesLieux,
    Garage,
    Infraction,
    OrdreReparation,
    PieceFlotte,
    PlanEntretien,
    Pneumatique,
    PleinCarburant,
    ReferentielFlotte,
    ReleveTelematique,
    ReservationVehicule,
    Sinistre,
    TrajetChantier,
    TrajetTelematique,
    Vehicule,
    VisiteTechnique,
)


class VehiculeSerializer(serializers.ModelSerializer):
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_fiscal_display = serializers.CharField(
        source='get_type_fiscal_display', read_only=True)
    # FLOTTE3 — libellé en lecture de l'emplacement de stock lié (résolu via le
    # sélecteur de `apps.stock`, dégrade sur l'id nu).
    emplacement_stock_label = serializers.SerializerMethodField()
    # XFLT4 — checklist de mise en service, exposée en lecture calculée.
    checklist_mise_en_service_ok = serializers.SerializerMethodField()
    # XFLT12 — libellé du modèle de référence (catalogue), lecture seule.
    modele_ref_label = serializers.SerializerMethodField()

    class Meta:
        model = Vehicule
        fields = [
            'id', 'immatriculation', 'marque', 'modele', 'energie',
            'energie_display', 'kilometrage', 'puissance_fiscale', 'valeur',
            'statut', 'statut_display', 'categorie_permis_requise',
            'emplacement_stock_id', 'emplacement_stock_label',
            'vin', 'annee', 'date_acquisition', 'type_fiscal',
            'type_fiscal_display', 'tags', 'checklist_mise_en_service',
            'checklist_mise_en_service_ok', 'modele_ref', 'modele_ref_label',
            'carte_mobilite', 'valeur_residuelle',
            'pct_charges_non_deductibles',
            'date_cession', 'prix_cession', 'acheteur', 'date_creation',
            'custom_data',
        ]
        # XFLT16 — la cession passe UNIQUEMENT par l'action ``ceder/`` (calcule
        # le gain/perte, délègue à compta si immobilisé) — jamais un PATCH direct.
        read_only_fields = [
            'date_creation', 'date_cession', 'prix_cession', 'acheteur']

    def validate(self, attrs):
        # ARC14 — champs personnalisés (pilote) : valider/nettoyer
        # custom_data contre les définitions du module « vehicule », même
        # chemin que Lead/Client/Produit. Création → toujours validé (champs
        # obligatoires) ; mise à jour → uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'vehicule', company, attrs.get('custom_data'))
        return attrs

    def get_modele_ref_label(self, obj):
        return str(obj.modele_ref) if obj.modele_ref_id else None

    def validate_pct_charges_non_deductibles(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                "Le % de charges non déductibles doit être compris entre "
                "0 et 100.")
        return value

    def get_checklist_mise_en_service_ok(self, obj):
        return obj.checklist_mise_en_service_ok()

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


class JournalStatutVehiculeSerializer(serializers.ModelSerializer):
    """XFLT4 — Entrée du journal des changements de statut véhicule.

    Lecture seule côté API (créé uniquement par
    ``services.changer_statut_vehicule``, jamais via un POST direct)."""

    user_nom = serializers.SerializerMethodField()

    class Meta:
        from .models import JournalStatutVehicule
        model = JournalStatutVehicule
        fields = [
            'id', 'vehicule', 'ancien_statut', 'nouveau_statut', 'user',
            'user_nom', 'horodatage',
        ]
        read_only_fields = fields

    def get_user_nom(self, obj):
        return obj.user.get_username() if obj.user_id else None


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
            'id', 'user', 'user_display', 'employe_id', 'nom', 'telephone',
            'numero_permis', 'categorie_permis',
            'date_obtention', 'date_expiration',
            # XFLT27 — conformité transport lourd (> 3,5 t) : carte de
            # conducteur professionnel + formation continue NARSA.
            'carte_conducteur_pro_numero', 'carte_conducteur_pro_expiration',
            'formation_continue_narsa_date', 'formation_continue_narsa_validite',
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
    # XFLT17 — avertissement non bloquant (charte véhicule non accusée),
    # calculé à la CRÉATION uniquement (première affectation).
    charte_avertissement = serializers.SerializerMethodField()
    # XFLT20 — avertissement non bloquant (accessoires non rendus), calculé
    # quand ``date_fin`` est posée (fin d'affectation).
    accessoires_avertissement = serializers.SerializerMethodField()

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
            "charte_avertissement",
            "accessoires_avertissement",
            "date_creation",
        ]
        read_only_fields = ["date_creation"]

    def get_permis_avertissement(self, obj):
        """Avertissement de permis posé lors d'une affectation forcée
        (non-conformité acceptée volontairement)."""
        return getattr(obj, '_permis_avertissement', None)

    def get_charte_avertissement(self, obj):
        """XFLT17 — Message si la charte véhicule courante n'a pas été
        accusée par le conducteur (posé à la création seulement)."""
        return getattr(obj, '_charte_avertissement', None)

    def get_accessoires_avertissement(self, obj):
        """XFLT20 — Message si des accessoires restent non rendus (posé à
        la mise à jour, quand ``date_fin`` clôture l'affectation)."""
        return getattr(obj, '_accessoires_avertissement', None)

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
        instance._charte_avertissement = getattr(
            self, '_charte_avertissement', None)
        instance._accessoires_avertissement = getattr(
            self, '_accessoires_avertissement', None)
        return instance

    def create(self, validated_data):
        instance = super().create(validated_data)
        # XFLT17 — Avertissement charte véhicule, à la CRÉATION seulement
        # (première affectation) — jamais recalculé à la mise à jour.
        from .services import accuse_charte_manquant, charte_courante

        self._charte_avertissement = None
        if instance.conducteur_id is not None \
                and accuse_charte_manquant(instance.conducteur):
            charte = charte_courante(instance.company)
            self._charte_avertissement = (
                f"Charte véhicule non accusée par le conducteur "
                f"(version courante : v{charte.version}).")
        return self._attach_warning(instance)

    def update(self, instance, validated_data):
        # XFLT21 — Journal d'audit : capture l'état AVANT modification pour
        # journaliser chaque changement RÉEL (conducteur/date_fin/actif).
        from .services import journaliser_diff_affectation

        avant = {
            'conducteur_id': instance.conducteur_id,
            'date_fin': instance.date_fin,
            'actif': instance.actif,
        }
        company = instance.company
        vehicule = instance.vehicule

        instance = super().update(instance, validated_data)

        request = self.context.get('request')
        user = getattr(request, 'user', None)
        apres = {
            'company': company,
            'vehicule': vehicule,
            'instance': instance,
            'conducteur_id': instance.conducteur_id,
            'date_fin': instance.date_fin,
            'actif': instance.actif,
        }
        journaliser_diff_affectation(avant, apres, user=user)

        # XFLT20 — Warning accessoires non rendus, calculé QUAND la mise à
        # jour clôture l'affectation (date_fin renseignée).
        from .services import avertissement_accessoires_non_rendus

        self._accessoires_avertissement = None
        if 'date_fin' in validated_data and validated_data['date_fin'] \
                is not None:
            self._accessoires_avertissement = \
                avertissement_accessoires_non_rendus(instance)
        return self._attach_warning(instance)


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
            'points', 'photos', 'nb_photos', 'accessoires',
            'signature_conducteur', 'signature_conducteur_horodatage',
            'signature_responsable', 'signature_responsable_horodatage',
            'commentaire', 'date_creation',
        ]
        # XFLT17 — les signatures passent UNIQUEMENT par l'action ``signer/``
        # (nom saisi + horodatage serveur, e-signature loi 53-05) — jamais un
        # PATCH direct sur ces champs.
        read_only_fields = [
            'date_creation', 'signature_conducteur',
            'signature_conducteur_horodatage', 'signature_responsable',
            'signature_responsable_horodatage']

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

    XFLT8 — ``tva_recuperable`` est CALCULÉ par défaut à la création depuis
    ``Vehicule.type_fiscal`` (``services.classifier_tva_recuperable``) si non
    fourni explicitement au body — reste éditable (override founder).
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
            'tva_recuperable', 'montant_tva', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_prix_unitaire(self, obj):
        return obj.prix_unitaire

    def create(self, validated_data):
        # XFLT8 — 'tva_recuperable' non fourni explicitement → classification
        # par défaut depuis le type fiscal du véhicule.
        if 'tva_recuperable' not in self.initial_data:
            from .services import classifier_tva_recuperable
            vehicule = validated_data.get('vehicule')
            if vehicule is not None:
                validated_data['tva_recuperable'] = \
                    classifier_tva_recuperable(vehicule)
        return super().create(validated_data)

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


class PlanEntretienSerializer(serializers.ModelSerializer):
    """FLOTTE15 — Plan d'entretien préventif (km / date / heures).

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    ciblé (``actif_flotte``) doit appartenir à la société courante. Au moins un
    intervalle (km / jours / heures) est obligatoire — validé ici pour renvoyer
    une 400 lisible plutôt qu'une 500 d'intégrité.

    Champs lecture seule :
    - ``actif_label``   : désignation de l'actif ciblé (véhicule ou engin).
    - ``type_actif``    : 'vehicule' | 'engin'.
    """

    actif_label = serializers.SerializerMethodField()
    type_actif = serializers.SerializerMethodField()

    class Meta:
        model = PlanEntretien
        fields = [
            'id', 'actif_flotte', 'actif_label', 'type_actif',
            'type_entretien', 'intervalle_km', 'intervalle_jours',
            'intervalle_heures', 'dernier_km', 'derniere_date',
            'dernier_heures', 'seuil_alerte_km', 'seuil_alerte_jours',
            'seuil_alerte_heures', 'notes', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_type_actif(self, obj):
        return obj.actif_flotte.type_actif if obj.actif_flotte_id else None

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        def _get(field):
            return attrs.get(field, getattr(self.instance, field, None))

        if not any((_get('intervalle_km'), _get('intervalle_jours'),
                    _get('intervalle_heures'))):
            raise serializers.ValidationError(
                "Renseignez au moins un intervalle (km, jours ou heures).")

        return attrs


class EcheanceEntretienSerializer(serializers.ModelSerializer):
    """FLOTTE16 — Échéance d'entretien due (générée depuis un plan).

    Les échéances sont MATÉRIALISÉES côté serveur par
    ``services.generer_echeances_entretien`` — elles ne se créent pas via l'API.
    Le sérialiseur est donc en lecture ; seuls ``statut`` (pour avancer
    ``a_faire`` → ``planifie`` → ``fait``) et ``notes`` sont modifiables. Tous
    les champs dérivés de la génération (plan, actif, cibles, type, date de
    génération) sont en lecture seule.

    Champs lecture seule :
    - ``actif_label``   : désignation de l'actif ciblé (véhicule ou engin).
    - ``statut_display``: libellé du statut.
    - ``plan_type``     : type d'entretien du plan source.
    """

    actif_label = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    plan_type = serializers.SerializerMethodField()

    class Meta:
        model = EcheanceEntretien
        fields = [
            'id', 'plan', 'plan_type', 'actif_flotte', 'actif_label',
            'type_entretien', 'due_le', 'due_km', 'due_heures',
            'statut', 'statut_display', 'notes', 'genere_le',
        ]
        read_only_fields = [
            'plan', 'actif_flotte', 'type_entretien', 'due_le', 'due_km',
            'due_heures', 'genere_le',
        ]

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_plan_type(self, obj):
        return obj.plan.type_entretien if obj.plan_id else None


# ── FLOTTE17 — Garage / atelier + ordres de réparation (coûts) ────────────────

class GarageSerializer(serializers.ModelSerializer):
    """FLOTTE17 — Garage / atelier de réparation de la société.

    ``company`` est posée côté serveur (jamais lue du corps de requête).
    XFLT26 — ``ice``/``identifiant_fiscal`` optionnels, préparation de
    l'e-facturation DGI ; l'ICE doit comporter exactement 15 chiffres.
    """

    class Meta:
        model = Garage
        fields = [
            'id', 'nom', 'adresse', 'telephone', 'ice', 'identifiant_fiscal',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_ice(self, value):
        if value and (len(value) != 15 or not value.isdigit()):
            raise serializers.ValidationError(
                "L'ICE doit comporter exactement 15 chiffres.")
        return value


class OrdreReparationSerializer(serializers.ModelSerializer):
    """FLOTTE17 — Ordre de réparation d'un actif auprès d'un garage.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    (``actif_flotte``), le garage et l'échéance liés — quand fournis — doivent
    appartenir à la société courante. ``cout_total`` est en LECTURE SEULE : il
    est calculé côté modèle (``cout_main_oeuvre + cout_pieces``) à chaque save —
    jamais accepté du corps de requête.

    Champs lecture seule :
    - ``actif_label``      : désignation de l'actif ciblé (véhicule ou engin).
    - ``garage_nom``       : nom du garage (ou ``None``).
    - ``statut_display``   : libellé du statut.
    - ``cout_total``       : main d'œuvre + pièces (calculé).
    """

    actif_label = serializers.SerializerMethodField()
    garage_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # ZCTR10 — libellé du type de service (référentiel éditable), ou ``None``
    # si aucun type n'a été choisi (OR "non catégorisé").
    type_service_libelle = serializers.SerializerMethodField()

    class Meta:
        model = OrdreReparation
        fields = [
            'id', 'actif_flotte', 'actif_label', 'garage', 'garage_nom',
            'echeance', 'type_service', 'type_service_libelle', 'description',
            'date_ouverture', 'date_cloture',
            'statut', 'statut_display', 'cout_main_oeuvre', 'cout_pieces',
            'cout_total', 'sous_garantie', 'montant_devis', 'devis_fichier',
            'approuve_par', 'date_approbation', 'ecart_facture_devis_pct',
            'notes', 'date_creation',
        ]
        # cout_total est dérivé côté modèle, jamais saisi. sous_garantie et
        # ecart_facture_devis_pct sont posés automatiquement (XFLT14/XFLT19).
        # approuve_par/date_approbation passent UNIQUEMENT par l'action
        # ``approuver/`` — jamais un PATCH direct.
        read_only_fields = [
            'cout_total', 'sous_garantie', 'approuve_par', 'date_approbation',
            'ecart_facture_devis_pct', 'date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_garage_nom(self, obj):
        return obj.garage.nom if obj.garage_id else None

    def get_type_service_libelle(self, obj):
        return obj.type_service.libelle if obj.type_service_id else None

    def validate_cout_main_oeuvre(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût de main d'œuvre ne peut pas être négatif.")
        return value

    def validate_cout_pieces(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût des pièces ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        garage = attrs.get('garage', getattr(self.instance, 'garage', None))
        echeance = attrs.get(
            'echeance', getattr(self.instance, 'echeance', None))
        type_service = attrs.get(
            'type_service', getattr(self.instance, 'type_service', None))
        date_ouverture = attrs.get(
            'date_ouverture', getattr(self.instance, 'date_ouverture', None))
        date_cloture = attrs.get(
            'date_cloture', getattr(self.instance, 'date_cloture', None))

        if company is not None:
            if actif_flotte is not None \
                    and actif_flotte.company_id != company.id:
                raise serializers.ValidationError(
                    {'actif_flotte':
                     "Cet actif n'appartient pas à votre société."})
            if garage is not None and garage.company_id != company.id:
                raise serializers.ValidationError(
                    {'garage': "Ce garage n'appartient pas à votre société."})
            if echeance is not None and echeance.company_id != company.id:
                raise serializers.ValidationError(
                    {'echeance':
                     "Cette échéance n'appartient pas à votre société."})
            # ZCTR10 — le type de service doit appartenir à la société ET au
            # domaine TYPE_SERVICE du référentiel (jamais un domaine hardcodé).
            if type_service is not None:
                if type_service.company_id != company.id:
                    raise serializers.ValidationError(
                        {'type_service':
                         "Ce type de service n'appartient pas à votre "
                         "société."})
                if type_service.domaine != ReferentielFlotte.Domaine.TYPE_SERVICE:
                    raise serializers.ValidationError(
                        {'type_service':
                         "Ce type de service doit provenir du référentiel "
                         "« Type de service / entretien »."})

        if date_ouverture is not None and date_cloture is not None \
                and date_cloture < date_ouverture:
            raise serializers.ValidationError(
                {'date_cloture':
                 "La date de clôture ne peut pas précéder l'ouverture."})

        # XFLT19 — Un devis au-dessus du seuil d'approbation société ne peut
        # pas passer en « en_cours » sans être passé par l'action
        # ``approuver/`` au préalable (statut approuve).
        nouveau_statut = attrs.get('statut')
        if nouveau_statut is not None and self.instance is not None:
            from .services import transition_statut_or_autorisee

            # Simule l'instance avec le montant_devis à jour (peut être
            # modifié dans la même requête) pour le contrôle de seuil.
            montant_devis = attrs.get(
                'montant_devis', self.instance.montant_devis)
            statut_courant = self.instance.statut
            self.instance.montant_devis = montant_devis
            ok, message = transition_statut_or_autorisee(
                self.instance, nouveau_statut)
            self.instance.statut = statut_courant
            if not ok:
                raise serializers.ValidationError({'statut': message})

        return attrs


# ── FLOTTE18 — Pneumatiques + pièces détachées de la flotte ──────────────────

class PneumatiqueSerializer(serializers.ModelSerializer):
    """FLOTTE18 — Pneumatique monté à une position d'un véhicule.

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    véhicule lié doit appartenir à la société courante. Les dates et le coût
    sont cohérents (dépose ≥ montage, coût ≥ 0).

    Champs lecture seule :
    - ``vehicule_label``  : désignation du véhicule.
    - ``position_display``: libellé de la position.
    - ``statut_display``  : libellé du statut.
    """

    vehicule_label = serializers.SerializerMethodField()
    position_display = serializers.CharField(
        source='get_position_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Pneumatique
        fields = [
            'id', 'vehicule', 'vehicule_label', 'position', 'position_display',
            'marque', 'dimension', 'date_montage', 'km_montage', 'date_depose',
            'statut', 'statut_display', 'cout', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def validate_cout(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        date_montage = attrs.get(
            'date_montage', getattr(self.instance, 'date_montage', None))
        date_depose = attrs.get(
            'date_depose', getattr(self.instance, 'date_depose', None))

        if company is not None and vehicule is not None \
                and vehicule.company_id != company.id:
            raise serializers.ValidationError(
                {'vehicule': "Ce véhicule n'appartient pas à votre société."})

        if date_montage is not None and date_depose is not None \
                and date_depose < date_montage:
            raise serializers.ValidationError(
                {'date_depose':
                 "La date de dépose ne peut pas précéder le montage."})

        return attrs


class PieceFlotteSerializer(serializers.ModelSerializer):
    """FLOTTE18 — Pièce détachée posée sur un véhicule du parc.

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    véhicule et l'ordre de réparation liés (si fournis) doivent appartenir à la
    société courante. ``cout_total`` est en LECTURE SEULE (quantité × coût
    unitaire, calculé côté modèle).

    Champs lecture seule :
    - ``vehicule_label`` : désignation du véhicule.
    - ``cout_total``     : quantité × coût unitaire (calculé).
    """

    vehicule_label = serializers.SerializerMethodField()
    cout_total = serializers.SerializerMethodField()

    class Meta:
        model = PieceFlotte
        fields = [
            'id', 'vehicule', 'vehicule_label', 'ordre_reparation',
            'designation', 'reference', 'quantite', 'cout_unitaire',
            'cout_total', 'date_pose', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_cout_total(self, obj):
        return obj.cout_total

    def validate_cout_unitaire(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût unitaire ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        ordre = attrs.get(
            'ordre_reparation',
            getattr(self.instance, 'ordre_reparation', None))

        if company is not None:
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule':
                     "Ce véhicule n'appartient pas à votre société."})
            if ordre is not None and ordre.company_id != company.id:
                raise serializers.ValidationError(
                    {'ordre_reparation':
                     "Cet ordre de réparation n'appartient pas à votre "
                     "société."})

        return attrs


# ── FLOTTE19 — Échéances réglementaires (visite technique, assurance…) ─────────

class EcheanceReglementaireSerializer(serializers.ModelSerializer):
    """FLOTTE19 — Échéance réglementaire / administrative d'un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante. La cohérence
    des dates (échéance ≥ dernier renouvellement) et le coût (≥ 0) sont validés.

    Champs lecture seule :
    - ``actif_label``       : désignation de l'actif (véhicule ou engin).
    - ``type_echeance_display`` / ``statut_display`` : libellés.
    - ``statut_calcule``    : état RÉEL vs la date du jour
      (``a_jour`` | ``a_renouveler`` | ``expire``), calculé côté modèle.
    """

    actif_label = serializers.SerializerMethodField()
    type_echeance_display = serializers.CharField(
        source='get_type_echeance_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_calcule = serializers.SerializerMethodField()

    class Meta:
        model = EcheanceReglementaire
        fields = [
            'id', 'actif_flotte', 'actif_label', 'type_echeance',
            'type_echeance_display', 'date_echeance',
            'date_dernier_renouvellement', 'organisme', 'cout', 'alerte_jours',
            'statut', 'statut_display', 'statut_calcule', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_statut_calcule(self, obj):
        return obj.statut_calcule()

    def validate_cout(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        date_echeance = attrs.get(
            'date_echeance', getattr(self.instance, 'date_echeance', None))
        date_renouv = attrs.get(
            'date_dernier_renouvellement',
            getattr(self.instance, 'date_dernier_renouvellement', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        if date_echeance is not None and date_renouv is not None \
                and date_echeance < date_renouv:
            raise serializers.ValidationError(
                {'date_echeance':
                 "La date d'échéance ne peut pas précéder le dernier "
                 "renouvellement."})

        return attrs


class BaremeVignetteSerializer(serializers.ModelSerializer):
    """FLOTTE20 — Ligne de barème éditable de la vignette / TSAV.

    ``company`` est posée côté serveur (jamais lue du corps de requête). La
    tranche doit être cohérente (``cv_min ≤ cv_max``) et le montant positif.
    ``energie_display`` est exposé en lecture.
    """

    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)

    class Meta:
        model = BaremeVignette
        fields = [
            'id', 'energie', 'energie_display', 'cv_min', 'cv_max', 'montant',
            'annee', 'actif', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        cv_min = attrs.get('cv_min', getattr(self.instance, 'cv_min', None))
        cv_max = attrs.get('cv_max', getattr(self.instance, 'cv_max', None))
        if cv_min is not None and cv_max is not None and cv_min > cv_max:
            raise serializers.ValidationError(
                {'cv_min': "Le CV min ne peut pas dépasser le CV max."})
        return attrs


class AssuranceVehiculeSerializer(serializers.ModelSerializer):
    """FLOTTE21 — Police d'assurance d'un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante. La cohérence
    des dates (échéance ≥ début de couverture) et la franchise (≥ 0) sont
    validées.

    Champs lecture seule :
    - ``actif_label``    : désignation de l'actif (véhicule ou engin).
    - ``statut_display`` : libellé du statut stocké.
    - ``statut_calcule`` : état RÉEL vs la date du jour
      (``valide`` | ``a_renouveler`` | ``expiree``), calculé côté modèle.
    """

    actif_label = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_calcule = serializers.SerializerMethodField()

    class Meta:
        model = AssuranceVehicule
        fields = [
            'id', 'actif_flotte', 'actif_label', 'assureur', 'numero_police',
            'date_debut', 'date_echeance', 'franchise', 'attestation',
            'alerte_jours', 'statut', 'statut_display', 'statut_calcule',
            'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_statut_calcule(self, obj):
        return obj.statut_calcule()

    def validate_franchise(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La franchise ne peut pas être négative.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        date_echeance = attrs.get(
            'date_echeance', getattr(self.instance, 'date_echeance', None))
        date_debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        if date_echeance is not None and date_debut is not None \
                and date_echeance < date_debut:
            raise serializers.ValidationError(
                {'date_echeance':
                 "La date d'échéance ne peut pas précéder le début de "
                 "couverture."})

        return attrs


# ── FLOTTE22 — Visite technique (validité paramétrable) ────────────────────────

class VisiteTechniqueSerializer(serializers.ModelSerializer):
    """FLOTTE22 — Visite technique périodique d'un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante. La période de
    validité ``validite_mois`` est PARAMÉTRABLE (12 par défaut). Si
    ``date_prochaine`` n'est pas fournie, elle est calculée côté modèle depuis
    ``date_visite`` + ``validite_mois`` (``clean``) — ``date_prochaine`` est donc
    en lecture seule au sérialiseur.

    Champs lecture seule :
    - ``actif_label``     : désignation de l'actif (véhicule ou engin).
    - ``resultat_display``: libellé du résultat.
    - ``statut_display``  : libellé du statut stocké.
    - ``statut_calcule``  : état RÉEL vs la date du jour
      (``valide`` | ``a_renouveler`` | ``expiree``), calculé côté modèle.
    - ``date_prochaine``  : calculée (date_visite + validite_mois).
    """

    actif_label = serializers.SerializerMethodField()
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_calcule = serializers.SerializerMethodField()

    class Meta:
        model = VisiteTechnique
        fields = [
            'id', 'actif_flotte', 'actif_label', 'centre', 'date_visite',
            'resultat', 'resultat_display', 'validite_mois', 'date_prochaine',
            'cout', 'alerte_jours', 'statut', 'statut_display',
            'statut_calcule', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_prochaine', 'date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_statut_calcule(self, obj):
        return obj.statut_calcule()

    def validate_cout(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le coût ne peut pas être négatif.")
        return value

    def validate_validite_mois(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "La validité (mois) doit être strictement positive.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        return attrs


# ── FLOTTE23 — Carte grise & autorisation de circulation ───────────────────────

class CarteGriseVehiculeSerializer(serializers.ModelSerializer):
    """FLOTTE23 — Carte grise & autorisation de circulation d'un actif.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante. Stocke le
    numéro de carte grise, les dates d'immatriculation / de mise en circulation,
    l'autorisation de circulation (numéro + date de validité, facultatifs) et les
    deux documents scannés (``carte_grise_fichier``, ``autorisation_fichier``).

    Champs lecture seule :
    - ``actif_label``    : désignation de l'actif (véhicule ou engin).
    - ``statut_display`` : libellé du statut stocké.
    - ``statut_calcule`` : état RÉEL de l'autorisation vs la date du jour
      (``valide`` | ``a_renouveler`` | ``expiree``), calculé côté modèle.
    """

    actif_label = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_calcule = serializers.SerializerMethodField()

    class Meta:
        model = CarteGriseVehicule
        fields = [
            'id', 'actif_flotte', 'actif_label', 'numero_carte_grise',
            'date_immatriculation', 'date_mise_circulation',
            'autorisation_circulation_numero', 'autorisation_date_validite',
            'carte_grise_fichier', 'autorisation_fichier', 'alerte_jours',
            'statut', 'statut_display', 'statut_calcule', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_statut_calcule(self, obj):
        return obj.statut_calcule()

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        return attrs


# ── FLOTTE25 — Sinistres (accident / constat / assurance) ──────────────────────

class SinistreSerializer(serializers.ModelSerializer):
    """FLOTTE25 — Sinistre d'un actif de flotte (accident, vol, bris de glace…).

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) ET la police d'assurance liée (``assurance``, si
    renseignée) doivent appartenir à la société courante. Les montants
    (``montant_estime``, ``franchise``) doivent être ≥ 0.

    Champs lecture seule :
    - ``actif_label``           : désignation de l'actif (véhicule ou engin).
    - ``type_sinistre_display`` : libellé du type de sinistre.
    - ``statut_display``        : libellé du statut.
    """

    actif_label = serializers.SerializerMethodField()
    type_sinistre_display = serializers.CharField(
        source='get_type_sinistre_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Sinistre
        fields = [
            'id', 'actif_flotte', 'actif_label', 'assurance',
            'date_sinistre', 'type_sinistre', 'type_sinistre_display',
            'description', 'lieu', 'constat_fichier', 'numero_declaration',
            'montant_estime', 'franchise', 'statut', 'statut_display',
            'date_declaration', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def validate_montant_estime(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant estimé ne peut pas être négatif.")
        return value

    def validate_franchise(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La franchise ne peut pas être négative.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        assurance = attrs.get(
            'assurance', getattr(self.instance, 'assurance', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        if company is not None and assurance is not None \
                and assurance.company_id != company.id:
            raise serializers.ValidationError(
                {'assurance':
                 "Cette police d'assurance n'appartient pas à votre société."})

        return attrs


# ── FLOTTE26 — Infractions / PV de circulation ─────────────────────────────────

class InfractionSerializer(serializers.ModelSerializer):
    """FLOTTE26 — Infraction / PV de circulation contre un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) ET le conducteur lié (``conducteur``, si renseigné)
    doivent appartenir à la société courante. Le montant de l'amende
    (``montant_amende``) doit être ≥ 0.

    Champs lecture seule :
    - ``actif_label``             : désignation de l'actif (véhicule ou engin).
    - ``conducteur_nom``          : nom du conducteur responsable (ou None).
    - ``type_infraction_display`` : libellé du type d'infraction.
    - ``statut_display``          : libellé du statut.
    """

    actif_label = serializers.SerializerMethodField()
    conducteur_nom = serializers.SerializerMethodField()
    type_infraction_display = serializers.CharField(
        source='get_type_infraction_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Infraction
        fields = [
            'id', 'actif_flotte', 'actif_label', 'conducteur',
            'conducteur_nom', 'date_infraction', 'type_infraction',
            'type_infraction_display', 'lieu', 'reference_pv',
            'montant_amende', 'pv_fichier', 'statut', 'statut_display',
            'date_paiement', 'notes', 'imputation_auto',
            'date_limite_contestation', 'refacture_conducteur',
            'montant_retenu', 'date_creation',
        ]
        read_only_fields = ['date_creation', 'imputation_auto']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_conducteur_nom(self, obj):
        return obj.conducteur.nom if obj.conducteur_id else None

    def validate_montant_amende(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant de l'amende ne peut pas être négatif.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        if company is not None and conducteur is not None \
                and conducteur.company_id != company.id:
            raise serializers.ValidationError(
                {'conducteur':
                 "Ce conducteur n'appartient pas à votre société."})

        return attrs


class ReleveTelematiqueSerializer(serializers.ModelSerializer):
    """FLOTTE27 — Relevé télématique d'un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante. Les valeurs
    numériques sont bornées (odomètre / heures ≥ 0 ; carburant 0–100 %).

    Champs lecture seule :
    - ``actif_label``     : désignation de l'actif (véhicule ou engin).
    - ``source_display``  : libellé de la source du relevé.
    """

    actif_label = serializers.SerializerMethodField()
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)

    class Meta:
        model = ReleveTelematique
        fields = [
            'id', 'actif_flotte', 'actif_label', 'horodatage', 'odometre',
            'position_lat', 'position_lng', 'niveau_carburant',
            'heures_moteur', 'source', 'source_display', 'raw_payload',
            'codes_defaut', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def validate_odometre(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "L'odomètre ne peut pas être négatif.")
        return value

    def validate_heures_moteur(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Les heures moteur ne peuvent pas être négatives.")
        return value

    def validate_niveau_carburant(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                "Le niveau de carburant doit être compris entre 0 et 100 %.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        return attrs


# ── FLOTTE28 — Suivi de position & trajets télématiques ────────────────────────

class TrajetTelematiqueSerializer(serializers.ModelSerializer):
    """FLOTTE28 — Trajet télématique d'un actif de flotte.

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) ET les relevés liés (``releve_depart`` /
    ``releve_arrivee``, si renseignés) doivent appartenir à la société courante.
    La fin doit être >= au début ; la distance >= 0.
    """

    actif_label = serializers.SerializerMethodField()
    duree_minutes = serializers.ReadOnlyField()
    vitesse_moyenne_kmh = serializers.ReadOnlyField()

    class Meta:
        model = TrajetTelematique
        fields = [
            'id', 'actif_flotte', 'actif_label', 'debut', 'fin',
            'depart_lat', 'depart_lng', 'arrivee_lat', 'arrivee_lng',
            'distance_km', 'duree_minutes', 'vitesse_moyenne_kmh',
            'releve_depart', 'releve_arrivee', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def validate_distance_km(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La distance parcourue ne peut pas être négative.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        debut = attrs.get('debut', getattr(self.instance, 'debut', None))
        fin = attrs.get('fin', getattr(self.instance, 'fin', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        for champ in ('releve_depart', 'releve_arrivee'):
            releve = attrs.get(champ, getattr(self.instance, champ, None))
            if company is not None and releve is not None \
                    and releve.company_id != company.id:
                raise serializers.ValidationError(
                    {champ: "Ce relevé n'appartient pas à votre société."})

        if debut is not None and fin is not None and fin < debut:
            raise serializers.ValidationError(
                {'fin': "La fin du trajet ne peut pas précéder son début."})

        return attrs


# ── FLOTTE29 — Journal kilométrique & trajets imputés chantier ─────────────────

class TrajetChantierSerializer(serializers.ModelSerializer):
    """FLOTTE29 — Trajet d'un actif imputé à un chantier (journal kilométrique).

    ``company`` est posée côté serveur (jamais lue du corps de requête). L'actif
    lié (``actif_flotte``) doit appartenir à la société courante ; le chantier
    (``installation_id``, optionnel) est validé via
    ``installations.selectors.installation_scoped`` (même société). Le
    kilométrage d'arrivée doit être >= celui de départ ; la distance >= 0.
    """

    actif_label = serializers.SerializerMethodField()
    distance_calculee_km = serializers.ReadOnlyField()

    class Meta:
        model = TrajetChantier
        fields = [
            'id', 'actif_flotte', 'actif_label', 'installation_id',
            'date_trajet', 'motif', 'km_depart', 'km_arrivee', 'distance_km',
            'distance_calculee_km', 'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def validate_distance_km(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "La distance parcourue ne peut pas être négative.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif_flotte = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        km_depart = attrs.get(
            'km_depart', getattr(self.instance, 'km_depart', None))
        km_arrivee = attrs.get(
            'km_arrivee', getattr(self.instance, 'km_arrivee', None))
        installation_id = attrs.get(
            'installation_id',
            getattr(self.instance, 'installation_id', None))

        if company is not None and actif_flotte is not None \
                and actif_flotte.company_id != company.id:
            raise serializers.ValidationError(
                {'actif_flotte':
                 "Cet actif n'appartient pas à votre société."})

        if company is not None and installation_id is not None:
            from apps.installations.selectors import installation_scoped
            if installation_scoped(company, installation_id) is None:
                raise serializers.ValidationError(
                    {'installation_id':
                     "Ce chantier n'appartient pas à votre société."})

        if km_depart is not None and km_arrivee is not None \
                and km_arrivee < km_depart:
            raise serializers.ValidationError(
                {'km_arrivee':
                 "Le kilométrage d'arrivée ne peut pas être inférieur "
                 "au kilométrage de départ."})

        return attrs


# ── FLOTTE32 — Pool de véhicules & demandes ────────────────────────────────────

class DemandeVehiculeSerializer(serializers.ModelSerializer):
    """FLOTTE32 — Demande d'un véhicule du pool partagé.

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    demandeur (posé côté serveur à la création — l'utilisateur courant), le
    décideur et le véhicule attribué doivent appartenir à la société courante.
    La fin souhaitée doit être >= au début souhaité. L'approbation / le refus
    passent par les actions dédiées (``approuver`` / ``refuser``) — les champs
    de décision sont en lecture seule au sérialiseur.
    """

    demandeur_nom = serializers.SerializerMethodField()
    vehicule_label = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DemandeVehicule
        fields = [
            'id', 'demandeur', 'demandeur_nom', 'besoin',
            'date_debut_souhaitee', 'date_fin_souhaitee', 'statut',
            'statut_display', 'vehicule_attribue', 'vehicule_label',
            'decide_par', 'date_decision', 'motif_decision', 'notes',
            'date_creation',
        ]
        read_only_fields = [
            'demandeur', 'statut', 'vehicule_attribue', 'decide_par',
            'date_decision', 'motif_decision', 'date_creation',
        ]

    def get_demandeur_nom(self, obj):
        return obj.demandeur.get_username() if obj.demandeur_id else None

    def get_vehicule_label(self, obj):
        return obj.vehicule_attribue.immatriculation \
            if obj.vehicule_attribue_id else None

    def validate(self, attrs):
        debut = attrs.get(
            'date_debut_souhaitee',
            getattr(self.instance, 'date_debut_souhaitee', None))
        fin = attrs.get(
            'date_fin_souhaitee',
            getattr(self.instance, 'date_fin_souhaitee', None))
        if debut is not None and fin is not None and fin < debut:
            raise serializers.ValidationError(
                {'date_fin_souhaitee':
                 "La fin souhaitée ne peut pas précéder le début souhaité."})
        return attrs


class ContratVehiculeSerializer(serializers.ModelSerializer):
    """XFLT1 — Contrat véhicule (leasing/LLD/location/entretien).

    ``company`` est posée côté serveur (jamais lue du corps de requête). Le
    véhicule et le garage liés doivent appartenir à la société courante. La
    fin de contrat doit être >= au début (quand renseignée).

    Champs lecture seule :
    - ``vehicule_label``     : désignation du véhicule.
    - ``type_contrat_display`` / ``periodicite_display`` / ``statut_display``.
    - ``statut_calcule``     : état RÉEL vs la date du jour
      (``actif`` | ``expire``), calculé côté modèle.
    """

    vehicule_label = serializers.SerializerMethodField()
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_calcule = serializers.SerializerMethodField()

    class Meta:
        model = ContratVehicule
        fields = [
            'id', 'vehicule', 'vehicule_label', 'type_contrat',
            'type_contrat_display', 'fournisseur', 'garage', 'date_debut',
            'date_fin', 'montant_recurrent', 'periodicite',
            'periodicite_display', 'services_inclus', 'km_contractuel_an',
            'statut', 'statut_display', 'statut_calcule', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_vehicule_label(self, obj):
        return str(obj.vehicule) if obj.vehicule_id else None

    def get_statut_calcule(self, obj):
        return obj.statut_calcule()

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        vehicule = attrs.get(
            'vehicule', getattr(self.instance, 'vehicule', None))
        garage = attrs.get('garage', getattr(self.instance, 'garage', None))

        if company is not None:
            if vehicule is not None and vehicule.company_id != company.id:
                raise serializers.ValidationError(
                    {'vehicule':
                     "Ce véhicule n'appartient pas à votre société."})
            if garage is not None and garage.company_id != company.id:
                raise serializers.ValidationError(
                    {'garage':
                     "Ce garage n'appartient pas à votre société."})

        debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))
        fin = attrs.get(
            'date_fin', getattr(self.instance, 'date_fin', None))
        if debut is not None and fin is not None and fin < debut:
            raise serializers.ValidationError(
                {'date_fin':
                 "La fin du contrat ne peut pas précéder le début."})
        return attrs


class CoutVehiculeSerializer(serializers.ModelSerializer):
    """XFLT3 — Coût véhicule divers (péage, parking, lavage, contrat…).

    ``company`` est posée côté serveur (jamais lue du corps de requête).
    L'actif et le conducteur liés doivent appartenir à la société courante.

    XFLT26 — préparation e-facturation DGI : ``fournisseur_id_ref`` référence
    optionnellement un ``stock.Fournisseur`` de la société (id numérique,
    résolu en lecture via ``fournisseur_label`` sans importer les modèles de
    l'app stock) ; ``fournisseur`` (saisie libre) reste un repli pour un
    fournisseur ponctuel. Au-delà de ``CoutVehicule.SEUIL_REFERENCE_MAD``
    (5 000 MAD), une ``reference_piece`` absente déclenche un AVERTISSEMENT
    non bloquant (``reference_avertissement``) — jamais un rejet.

    Champs lecture seule :
    - ``actif_label``             : désignation de l'actif (véhicule/engin).
    - ``categorie_display``.
    - ``conducteur_nom``          : nom d'utilisateur du conducteur lié.
    - ``fournisseur_label``       : nom du fournisseur référencé, résolu par
      sélecteur cross-app (``apps.stock.selectors.get_fournisseur_by_id``).
    - ``reference_avertissement`` : message si le coût dépasse le seuil sans
      référence de pièce (``None`` sinon).
    """

    actif_label = serializers.SerializerMethodField()
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    conducteur_nom = serializers.SerializerMethodField()
    fournisseur_label = serializers.SerializerMethodField()
    reference_avertissement = serializers.SerializerMethodField()

    class Meta:
        model = CoutVehicule
        fields = [
            'id', 'actif_flotte', 'actif_label', 'categorie',
            'categorie_display', 'date', 'montant', 'fournisseur',
            'fournisseur_id_ref', 'fournisseur_label', 'reference_piece',
            'reference_avertissement', 'conducteur', 'conducteur_nom',
            'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_conducteur_nom(self, obj):
        return str(obj.conducteur) if obj.conducteur_id else None

    def get_fournisseur_label(self, obj):
        if not obj.fournisseur_id_ref:
            return None
        from apps.stock.selectors import get_fournisseur_by_id
        fournisseur = get_fournisseur_by_id(obj.company, obj.fournisseur_id_ref)
        return fournisseur.nom if fournisseur is not None else None

    def get_reference_avertissement(self, obj):
        seuil = CoutVehicule.SEUIL_REFERENCE_MAD
        if obj.montant is not None and obj.montant > seuil \
                and not obj.reference_piece:
            return (
                f'Coût de {obj.montant} MAD supérieur à {seuil} MAD sans '
                'référence de facture structurée — pensez à la renseigner '
                'pour la réconciliation comptable.'
            )
        return None

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant ne peut pas être négatif.")
        return value

    def validate_fournisseur_id_ref(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        from apps.stock.selectors import get_fournisseur_by_id
        if company is not None \
                and get_fournisseur_by_id(company, value) is None:
            raise serializers.ValidationError(
                "Ce fournisseur n'appartient pas à votre société.")
        return value


class SignalementVehiculeSerializer(serializers.ModelSerializer):
    """XFLT5 — Signalement d'anomalie véhicule déposé par un conducteur.

    ``company`` ET ``auteur`` sont posés côté serveur (jamais lus du corps de
    requête). L'actif et le conducteur liés doivent appartenir à la société
    courante.

    Champs lecture seule :
    - ``actif_label``      : désignation de l'actif (véhicule ou engin).
    - ``gravite_display`` / ``statut_display``.
    - ``auteur_nom``       : nom d'utilisateur de l'auteur.
    """

    actif_label = serializers.SerializerMethodField()
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        from .models import SignalementVehicule
        model = SignalementVehicule
        fields = [
            'id', 'actif_flotte', 'actif_label', 'conducteur', 'auteur',
            'auteur_nom', 'description', 'photo', 'gravite',
            'gravite_display', 'statut', 'statut_display',
            'ordre_reparation', 'date_creation',
        ]
        read_only_fields = ['auteur', 'ordre_reparation', 'date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_auteur_nom(self, obj):
        return obj.auteur.get_username() if obj.auteur_id else None


# ── XFLT12 — Catalogue de modèles véhicule ──────────────────────────────────────

class ModeleVehiculeSerializer(serializers.ModelSerializer):
    """XFLT12 — Modèle véhicule de référence (catalogue).

    ``company`` posée côté serveur (jamais lue du corps de requête).
    """

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    energie_display = serializers.CharField(
        source='get_energie_display', read_only=True)

    class Meta:
        from .models import ModeleVehicule
        model = ModeleVehicule
        fields = [
            'id', 'marque', 'modele', 'categorie', 'categorie_display',
            'energie', 'energie_display', 'co2_g_km', 'places',
            'puissance_fiscale', 'puissance_kw', 'valeur_catalogue',
            'capacite_reservoir_l', 'valeur_residuelle',
            'pct_charges_non_deductibles', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_pct_charges_non_deductibles(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                "Le % de charges non déductibles doit être compris entre "
                "0 et 100.")
        return value


# ── XFLT13 — Inspections périodiques paramétrables (check-lists DVIR) ──────────

class ModeleInspectionSerializer(serializers.ModelSerializer):
    """XFLT13 — Modèle de check-list d'inspection périodique.

    ``company`` posée côté serveur (jamais lue du corps de requête).
    """

    type_actif_cible_display = serializers.CharField(
        source='get_type_actif_cible_display', read_only=True)

    class Meta:
        from .models import ModeleInspection
        model = ModeleInspection
        fields = [
            'id', 'nom', 'type_actif_cible', 'type_actif_cible_display',
            'items', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class InspectionVehiculeSerializer(serializers.ModelSerializer):
    """XFLT13 — Inspection périodique réalisée sur un actif.

    ``company`` ET ``auteur`` posés côté serveur. Un item ``fail`` dans
    ``resultats`` crée automatiquement un ``SignalementVehicule`` lié (voir
    ``services.traiter_items_fail``, appelé côté vue à la création).

    Champs lecture seule :
    - ``actif_label``   : désignation de l'actif (véhicule ou engin).
    - ``modele_nom``    : nom du modèle d'inspection utilisé.
    - ``conducteur_nom``: nom du conducteur (ou None).
    - ``nb_items_fail`` : nombre d'items en échec, calculé.
    """

    actif_label = serializers.SerializerMethodField()
    modele_nom = serializers.SerializerMethodField()
    conducteur_nom = serializers.SerializerMethodField()
    nb_items_fail = serializers.SerializerMethodField()

    class Meta:
        from .models import InspectionVehicule
        model = InspectionVehicule
        fields = [
            'id', 'actif_flotte', 'actif_label', 'modele_inspection',
            'modele_nom', 'conducteur', 'conducteur_nom', 'auteur',
            'date_inspection', 'resultats', 'nb_items_fail',
            'signature_nom', 'signature_horodatage',
        ]
        read_only_fields = ['auteur', 'date_inspection']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_modele_nom(self, obj):
        return obj.modele_inspection.nom if obj.modele_inspection_id else None

    def get_conducteur_nom(self, obj):
        return obj.conducteur.nom if obj.conducteur_id else None

    def get_nb_items_fail(self, obj):
        return obj.nb_items_fail()


# ── XFLT14 — Garanties véhicule & pièces ────────────────────────────────────────

class GarantieFlotteSerializer(serializers.ModelSerializer):
    """XFLT14 — Garantie constructeur/fournisseur sur un actif ou composant.

    ``company`` posée côté serveur (jamais lue du corps de requête).
    """

    actif_label = serializers.SerializerMethodField()
    date_fin = serializers.SerializerMethodField()
    active = serializers.SerializerMethodField()

    class Meta:
        from .models import GarantieFlotte
        model = GarantieFlotte
        fields = [
            'id', 'actif_flotte', 'actif_label', 'composant', 'duree_mois',
            'duree_km', 'date_debut', 'date_fin', 'active', 'fournisseur',
            'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_date_fin(self, obj):
        date_fin = obj.date_fin()
        return date_fin.isoformat() if date_fin else None

    def get_active(self, obj):
        vehicule = getattr(obj.actif_flotte, 'vehicule', None)
        kilometrage = getattr(vehicule, 'kilometrage', None) if vehicule else None
        return obj.couvre(kilometrage=kilometrage)


# ── XFLT17 — Charte véhicule + accusé de lecture ────────────────────────────────

class CharteVehiculeSerializer(serializers.ModelSerializer):
    """XFLT17 — Charte véhicule versionnée. ``company`` posée côté serveur ;
    ``version`` est posée côté serveur (auto-incrémentée) — jamais du body."""

    class Meta:
        from .models import CharteVehicule
        model = CharteVehicule
        fields = ['id', 'version', 'document', 'date_publication']
        read_only_fields = ['version', 'date_publication']


class AccuseCharteSerializer(serializers.ModelSerializer):
    """XFLT17 — Accusé de lecture de la charte véhicule par un conducteur.

    ``company`` posée côté serveur. ``version`` est posée côté serveur
    (toujours la version courante au moment de l'accusé) — jamais du body.
    """

    conducteur_nom = serializers.SerializerMethodField()

    class Meta:
        from .models import AccuseCharte
        model = AccuseCharte
        fields = [
            'id', 'conducteur', 'conducteur_nom', 'version', 'date_accuse']
        read_only_fields = ['version', 'date_accuse']

    def get_conducteur_nom(self, obj):
        return obj.conducteur.nom if obj.conducteur_id else None


# ── XFLT18 — Budget flotte annuel vs réalisé ────────────────────────────────────

class BudgetFlotteSerializer(serializers.ModelSerializer):
    """XFLT18 — Ligne budgétaire annuelle par catégorie. ``company`` posée
    côté serveur. ``notifie_depassement`` est géré côté serveur (jamais du
    body — voir ``services.verifier_depassements_budget``)."""

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        from .models import BudgetFlotte
        model = BudgetFlotte
        fields = [
            'id', 'annee', 'categorie', 'categorie_display',
            'montant_budgete', 'notifie_depassement', 'date_creation',
        ]
        read_only_fields = ['notifie_depassement', 'date_creation']

    def validate_montant_budgete(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Le montant budgété ne peut pas être négatif.")
        return value


# ── XFLT20 — Registre de remise clés / carte / badge / tag Jawaz ───────────────

class RemiseAccessoireSerializer(serializers.ModelSerializer):
    """XFLT20 — Remise d'un accessoire (clé/carte/badge/tag Jawaz) à un
    conducteur. ``company`` posée côté serveur. L'actif et le conducteur
    liés doivent appartenir à la société courante.

    Champs lecture seule :
    - ``actif_label``          : désignation de l'actif.
    - ``conducteur_nom``       : nom du détenteur.
    - ``type_accessoire_display`` : libellé du type.
    """

    actif_label = serializers.SerializerMethodField()
    conducteur_nom = serializers.SerializerMethodField()
    type_accessoire_display = serializers.CharField(
        source='get_type_accessoire_display', read_only=True)

    class Meta:
        from .models import RemiseAccessoire
        model = RemiseAccessoire
        fields = [
            'id', 'actif_flotte', 'actif_label', 'type_accessoire',
            'type_accessoire_display', 'conducteur', 'conducteur_nom',
            'date_remise', 'date_retour', 'commentaire', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_actif_label(self, obj):
        return obj.actif_flotte.label if obj.actif_flotte_id else None

    def get_conducteur_nom(self, obj):
        return obj.conducteur.nom if obj.conducteur_id else None

    def validate(self, attrs):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)

        actif = attrs.get(
            'actif_flotte', getattr(self.instance, 'actif_flotte', None))
        conducteur = attrs.get(
            'conducteur', getattr(self.instance, 'conducteur', None))
        date_remise = attrs.get(
            'date_remise', getattr(self.instance, 'date_remise', None))
        date_retour = attrs.get(
            'date_retour', getattr(self.instance, 'date_retour', None))

        if company is not None:
            if actif is not None and actif.company_id != company.id:
                raise serializers.ValidationError(
                    {'actif_flotte':
                     "Cet actif n'appartient pas à votre société."})
            if conducteur is not None and conducteur.company_id != company.id:
                raise serializers.ValidationError(
                    {'conducteur':
                     "Ce conducteur n'appartient pas à votre société."})

        if date_remise is not None and date_retour is not None \
                and date_retour < date_remise:
            raise serializers.ValidationError(
                {'date_retour':
                 "La date de retour ne peut pas précéder la remise."})

        return attrs


# ── XFLT21 — Journal d'audit flotte ─────────────────────────────────────────────

class ActiviteFlotteSerializer(serializers.ModelSerializer):
    """XFLT21 — Entrée du journal d'audit flotte (lecture + création seules,
    IMMUABLE — jamais d'update/delete depuis l'API)."""

    type_objet_display = serializers.CharField(
        source='get_type_objet_display', read_only=True)
    user_nom = serializers.SerializerMethodField()

    class Meta:
        from .models import ActiviteFlotte
        model = ActiviteFlotte
        fields = [
            'id', 'vehicule', 'type_objet', 'type_objet_display', 'objet_id',
            'champ', 'ancienne_valeur', 'nouvelle_valeur', 'user', 'user_nom',
            'date_creation',
        ]
        read_only_fields = fields

    def get_user_nom(self, obj):
        return obj.user.get_username() if obj.user_id else None


# ── XFLT24 — Géofencing sur les données télématiques ────────────────────────────

class ZoneGeographiqueSerializer(serializers.ModelSerializer):
    """XFLT24 — Zone géographique circulaire de géofencing.

    ``company`` est posée côté serveur (jamais lue du corps de requête).
    """

    type_zone_display = serializers.CharField(
        source='get_type_zone_display', read_only=True)

    class Meta:
        from .models import ZoneGeographique
        model = ZoneGeographique
        fields = [
            'id', 'nom', 'type_zone', 'type_zone_display', 'centre_lat',
            'centre_lng', 'rayon_metres', 'heure_debut_autorisee',
            'heure_fin_autorisee', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_rayon_metres(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'Le rayon doit être strictement positif.')
        return value

    def validate(self, attrs):
        debut = attrs.get(
            'heure_debut_autorisee',
            getattr(self.instance, 'heure_debut_autorisee', None))
        fin = attrs.get(
            'heure_fin_autorisee',
            getattr(self.instance, 'heure_fin_autorisee', None))
        if debut is not None and fin is not None and fin <= debut:
            raise serializers.ValidationError(
                "L'heure de fin autorisée doit être postérieure à l'heure "
                'de début.')
        return attrs


# ── XFLT28 — Rappels constructeur (recall) ──────────────────────────────────────

class RappelConstructeurSerializer(serializers.ModelSerializer):
    """XFLT28 — Rappel constructeur (recall) rapproché contre les VIN du parc.

    ``company`` est posée côté serveur (jamais lue du corps de requête).
    """

    class Meta:
        from .models import RappelConstructeur
        model = RappelConstructeur
        fields = [
            'id', 'reference_campagne', 'constructeur', 'description',
            'vin_concernes', 'date_creation',
        ]
        read_only_fields = ['date_creation']
