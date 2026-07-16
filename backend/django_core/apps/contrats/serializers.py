"""Sérialiseurs de la Gestion des contrats.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est également posé côté
serveur.
"""
from rest_framework import serializers

from .models import (
    AlerteContrat,
    Avenant,
    Caution,
    Clause,
    ClauseContrat,
    Contrat,
    ContratActivity,
    ContratLien,
    CycleFacturationLog,
    EcheancierContrat,
    EngagementSLA,
    EtapeApprobation,
    IndexationPrix,
    JalonContrat,
    LigneEcheance,
    ModeleContrat,
    ModeleContratClause,
    MotifResiliation,
    Obligation,
    OrdreLocation,
    ParametresLocation,
    PartieContrat,
    PieceConformite,
    PlanRecurrent,
    RegleApprobation,
    Resiliation,
    RetenueGarantie,
    SignatureContrat,
    VersionContrat,
)


class ContratActivitySerializer(serializers.ModelSerializer):
    """Entrée du chatter d'un contrat (transition automatique ou note manuelle).

    Tous les champs sont en LECTURE SEULE côté API : les entrées sont créées
    exclusivement côté serveur (transitions auditées, action ``noter``). La
    société et l'auteur ne sont jamais lus du corps de requête (CONTRAT15).
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ContratActivity
        fields = [
            'id', 'contrat', 'type', 'type_display', 'field', 'old_value',
            'new_value', 'message', 'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)


class NoterContratSerializer(serializers.Serializer):
    """Corps de l'action ``noter`` : une note manuelle libre (non vide)."""
    message = serializers.CharField()

    def validate_message(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Note vide.')
        return value


class ContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'un ``Contrat``.

    ``sav_contrat_maintenance_id`` est un lien LÂCHE (id seul) vers un contrat
    de maintenance SAV (``sav.ContratMaintenance``) — jamais un FK dur ni un
    import de ``apps.sav.models``. Depuis XCTR13, l'ÉCRITURE de ce champ est
    VALIDÉE via le sélecteur cross-app ``sav.selectors.contrat_maintenance_
    existe`` (frontière cross-app, CLAUDE.md) : un id inexistant OU d'une
    AUTRE société est refusé (400). ``None``/vide reste toujours accepté
    (aucun contrat de maintenance rattaché).
    """
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    confidentialite_display = serializers.CharField(
        source='get_confidentialite_display', read_only=True)
    # CONTRAT20 — dates clés calculées (lecture seule) : la date limite de
    # préavis (``date_fin − preavis_jours``) et le nombre de jours restants
    # jusque-là (négatif = échéance dépassée). ``None`` si non calculable.
    echeance_preavis = serializers.SerializerMethodField()
    jours_avant_preavis = serializers.SerializerMethodField()
    # CONTRAT21 — nombre de jours restants jusqu'à la FIN du contrat
    # (``date_fin``). Distinct de ``jours_avant_preavis`` (échéance de préavis).
    # Négatif = échéance dépassée ; ``None`` si ``date_fin`` non renseignée.
    jours_avant_echeance = serializers.SerializerMethodField()

    class Meta:
        model = Contrat
        fields = [
            'id', 'reference', 'type_contrat', 'type_contrat_display',
            'objet', 'statut', 'statut_display', 'client_id',
            'sav_contrat_maintenance_id', 'modele', 'date_debut',
            'date_fin', 'preavis_jours', 'tacite_reconduction',
            'duree_reconduction_mois', 'preavis_traite',
            # CONTRAT23 — audit du renouvellement (posés côté serveur).
            'date_dernier_renouvellement', 'nb_renouvellements',
            'echeance_preavis', 'jours_avant_preavis',
            'jours_avant_echeance',
            'montant', 'devise', 'plan_recurrent',
            'confidentialite', 'confidentialite_display',
            'responsable', 'responsable_nom',
            'created_by', 'date_creation', 'custom_data',
        ]
        read_only_fields = [
            'created_by', 'date_creation',
            'date_dernier_renouvellement', 'nb_renouvellements',
        ]

    responsable_nom = serializers.SerializerMethodField()

    def validate(self, attrs):
        # ARC14 — champs personnalisés (pilote) : valider/nettoyer
        # custom_data contre les définitions du module « contrat », même
        # chemin que Lead/Client/Produit. Création → toujours validé (champs
        # obligatoires) ; mise à jour → uniquement si custom_data est fourni.
        is_create = self.instance is None
        if is_create or 'custom_data' in attrs:
            from apps.customfields.serializers import validate_custom_data
            request = self.context.get('request')
            company = getattr(getattr(request, 'user', None), 'company', None)
            if company is not None:
                attrs['custom_data'] = validate_custom_data(
                    'contrat', company, attrs.get('custom_data'))
        return attrs

    def get_responsable_nom(self, obj):
        return getattr(obj.responsable, 'username', None)

    def get_echeance_preavis(self, obj):
        echeance = obj.echeance_preavis()
        return echeance.isoformat() if echeance is not None else None

    def get_jours_avant_preavis(self, obj):
        return obj.jours_avant_preavis()

    def get_jours_avant_echeance(self, obj):
        return obj.jours_avant_echeance()

    def validate_modele(self, modele):
        """Le gabarit source (optionnel) doit appartenir à la société."""
        if modele is None:
            return modele
        request = self.context.get('request')
        if request is not None and modele.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce modèle n'appartient pas à votre société.")
        return modele

    def validate_plan_recurrent(self, plan):
        """Le plan de facturation récurrente (optionnel) doit appartenir à la
        société — ZCTR1."""
        if plan is None:
            return plan
        request = self.context.get('request')
        if request is not None and plan.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce plan de facturation récurrente n'appartient pas à "
                "votre société.")
        return plan

    def validate_responsable(self, responsable):
        """Le responsable (optionnel) doit appartenir à la société — XCTR10."""
        if responsable is None:
            return responsable
        request = self.context.get('request')
        if request is not None and \
                responsable.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce responsable n'appartient pas à votre société.")
        return responsable

    def validate_sav_contrat_maintenance_id(self, pk):
        """L'id, s'il est fourni, doit exister DANS la société — XCTR13.

        Frontière cross-app : délègue à ``sav.selectors.contrat_maintenance_
        existe`` (import fonction-local, jamais ``sav.models``). ``None``
        reste toujours accepté (aucun rattachement).
        """
        if not pk:
            return pk
        request = self.context.get('request')
        company = getattr(request, 'user', None) and request.user.company \
            if request is not None else None
        if company is None:
            return pk
        from apps.sav.selectors import contrat_maintenance_existe

        if not contrat_maintenance_existe(pk, company):
            raise serializers.ValidationError(
                "Ce contrat de maintenance SAV est introuvable dans votre "
                "société.")
        return pk


class PartieContratSerializer(serializers.ModelSerializer):
    type_partie_display = serializers.CharField(
        source='get_type_partie_display', read_only=True)

    class Meta:
        model = PartieContrat
        fields = [
            'id', 'contrat', 'type_partie', 'type_partie_display', 'nom',
            'fonction', 'email', 'telephone', 'ordre',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur.

        Empêche d'attacher une partie à un contrat d'une autre société (la
        société de la partie elle-même est posée côté serveur par le
        ``TenantMixin``).
        """
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class AlerteContratSerializer(serializers.ModelSerializer):
    """Alerte/rappel planifié sur un contrat (CONTRAT22).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé comme appartenant à la société de
    l'utilisateur. ``statut`` / ``date_envoi`` / ``cree_par`` sont en lecture
    seule (posés côté serveur lors de la création ou du dispatch).
    """
    type_alerte_display = serializers.CharField(
        source='get_type_alerte_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AlerteContrat
        fields = [
            'id', 'contrat', 'type_alerte', 'type_alerte_display',
            'date_declenchement', 'message', 'statut', 'statut_display',
            'date_envoi', 'cree_par', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'statut_display', 'date_envoi', 'cree_par',
            'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class SemerAlertesSerializer(serializers.Serializer):
    """Corps de l'action ``semer-echeances`` : fenêtre de jours (optionnelle)."""
    within = serializers.IntegerField(required=False, min_value=0, default=30)


class ContratLienSerializer(serializers.ModelSerializer):
    """Lien contrat → document métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le
    ``contrat`` reçu est validé comme appartenant à la société de l'utilisateur.
    """
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = ContratLien
        fields = [
            'id', 'contrat', 'type_cible', 'type_cible_display', 'cible_id',
            'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class ModeleContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'un ``ModeleContrat`` (bibliothèque de gabarits — CONTRAT7).

    ``company`` n'est jamais exposée en écriture : elle est posée côté serveur.
    Champs d'affichage (_display) sont en lecture seule.
    """
    type_contrat_defaut_display = serializers.CharField(
        source='get_type_contrat_defaut_display', read_only=True)
    confidentialite_defaut_display = serializers.CharField(
        source='get_confidentialite_defaut_display', read_only=True)

    class Meta:
        model = ModeleContrat
        fields = [
            'id', 'nom', 'categorie',
            'type_contrat_defaut', 'type_contrat_defaut_display',
            'corps', 'clauses',
            'devise_defaut',
            'confidentialite_defaut', 'confidentialite_defaut_display',
            'actif', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class ClauseSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``Clause`` (bibliothèque de clauses — CONTRAT8).

    ``company`` n'est jamais exposée en écriture : posée côté serveur.
    ``type_clause_display`` est en lecture seule.
    """

    type_clause_display = serializers.CharField(
        source="get_type_clause_display", read_only=True
    )
    # YHARD4 — variantes localisées (repli FR, cf. core/i18n_content.py) :
    # cible via ``?locale=`` sur la requête, additif, jamais requis.
    titre_localise = serializers.SerializerMethodField()
    corps_localise = serializers.SerializerMethodField()

    class Meta:
        model = Clause
        fields = [
            "id",
            "titre",
            "titre_localise",
            "categorie",
            "type_clause",
            "type_clause_display",
            "corps",
            "corps_localise",
            "ordre",
            "actif",
            "date_creation",
        ]
        read_only_fields = ["date_creation"]

    def _target_locale(self):
        request = self.context.get('request')
        locale = self.context.get('locale')
        if not locale and request is not None:
            locale = request.query_params.get('locale') if hasattr(
                request, 'query_params') else request.GET.get('locale')
        if locale and len(locale) <= 5:
            return locale
        return None

    def get_titre_localise(self, obj):
        from core.i18n_content import translated_value
        return translated_value(obj, 'titre', self._target_locale())

    def get_corps_localise(self, obj):
        from core.i18n_content import translated_value
        return translated_value(obj, 'corps', self._target_locale())


class ModeleContratClauseSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une liaison ``ModeleContratClause`` (CONTRAT8).

    Permet de rattacher / ordonner des ``Clause`` sur un ``ModeleContrat``.
    ``company`` est posée côté serveur ; ``modele`` et ``clause`` sont validés
    comme appartenant à la même société que l'utilisateur.
    """

    class Meta:
        model = ModeleContratClause
        fields = ["id", "modele", "clause", "ordre"]

    def _validate_tenant(self, obj, field_name):
        """Vérifie que l'objet appartient à la société de l'utilisateur."""
        request = self.context.get("request")
        if request is not None and obj.company_id != request.user.company_id:
            raise serializers.ValidationError(
                f"Ce {field_name} n'appartient pas à votre société."
            )
        return obj

    def validate_modele(self, modele):
        return self._validate_tenant(modele, "modèle de contrat")

    def validate_clause(self, clause):
        return self._validate_tenant(clause, "clause")


class ClauseContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``ClauseContrat`` — clause résolue d'un contrat (CONTRAT9).

    ``company`` n'est jamais exposée : posée côté serveur. Le ``contrat`` et la
    ``clause`` (source, optionnelle) reçus sont validés comme appartenant à la
    société de l'utilisateur.

    Résolution & surcharge :
    - À la CRÉATION, si une ``clause`` source est fournie et que ``titre`` /
      ``corps`` ne le sont pas, ils sont matérialisés depuis la clause-source
      (``resoudre_depuis_clause``). Fournir explicitement ``titre``/``corps``
      en présence d'une source les surcharge → ``surchargee=True``.
    - À la MISE À JOUR, modifier ``titre`` ou ``corps`` d'une clause issue d'une
      source positionne ``surchargee=True``. ``surchargee`` est en lecture
      seule (jamais piloté depuis le corps de requête).
    """

    # ``clause`` (source) est optionnelle : NULL = clause ad hoc. On la déclare
    # explicitement ``required=False`` car un FK déclaré via ``fields`` n'hérite
    # pas toujours du ``required=False`` attendu.
    clause = serializers.PrimaryKeyRelatedField(
        queryset=Clause.objects.all(),
        required=False, allow_null=True,
    )
    clause_titre = serializers.CharField(
        source="clause.titre", read_only=True, default=None
    )

    class Meta:
        model = ClauseContrat
        fields = [
            "id", "contrat", "clause", "clause_titre",
            "titre", "corps", "ordre", "surchargee", "date_creation",
        ]
        read_only_fields = ["surchargee", "date_creation"]
        # ``titre``/``corps`` peuvent être omis quand une clause-source est
        # fournie : ils sont alors résolus côté serveur.
        extra_kwargs = {
            "titre": {"required": False, "allow_blank": True},
            "corps": {"required": False, "allow_blank": True},
        }
        # On NEUTRALISE le ``UniqueTogetherValidator`` auto-généré par la
        # contrainte d'unicité conditionnelle ``(contrat, clause)`` : DRF
        # rendrait ``clause`` OBLIGATOIRE, cassant les clauses ad hoc
        # (``clause=NULL``). L'unicité reste garantie par la contrainte DB
        # (partielle) et est vérifiée proprement dans ``validate`` ci-dessous.
        validators = []

    def _validate_tenant(self, obj, field_name):
        request = self.context.get("request")
        if request is not None and obj.company_id != request.user.company_id:
            raise serializers.ValidationError(
                f"Ce {field_name} n'appartient pas à votre société."
            )
        return obj

    def validate_contrat(self, contrat):
        return self._validate_tenant(contrat, "contrat")

    def validate_clause(self, clause):
        if clause is None:
            return clause
        return self._validate_tenant(clause, "clause")

    def validate(self, attrs):
        """Résout depuis la clause-source et calcule l'état de surcharge.

        À la création : si une source est fournie et le texte manque, on le
        matérialise depuis la source ; un texte fourni explicitement (différent
        de la source) marque ``surchargee=True``. Sans source, ``titre`` et
        ``corps`` sont obligatoires (clause ad hoc). À la mise à jour, toute
        modification du ``titre``/``corps`` d'une clause sourcée la surcharge.
        """
        clause = attrs.get("clause", getattr(self.instance, "clause", None))
        contrat = attrs.get("contrat", getattr(self.instance, "contrat", None))
        titre = attrs.get("titre", getattr(self.instance, "titre", ""))
        corps = attrs.get("corps", getattr(self.instance, "corps", ""))

        # Unicité (contrat, clause) pour les clauses SOURCÉES uniquement — les
        # clauses ad hoc (clause=NULL) ne sont pas contraintes. On la vérifie
        # ici plutôt qu'avec le validateur auto (qui rendrait ``clause``
        # obligatoire). La contrainte DB partielle reste le filet de sécurité.
        if clause is not None and contrat is not None:
            dup = ClauseContrat.objects.filter(contrat=contrat, clause=clause)
            if self.instance is not None:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError(
                    "Cette clause source est déjà rattachée à ce contrat."
                )

        if clause is not None:
            # Matérialise le texte manquant depuis la clause-source.
            if not titre:
                titre = clause.titre
                attrs["titre"] = titre
            if not corps:
                corps = clause.corps
                attrs["corps"] = corps
            # Surcharge dès que le texte résolu diffère de la source ; sinon
            # remise à False (vaut aussi quand on remet le texte d'origine).
            attrs["surchargee"] = (
                titre != clause.titre or corps != clause.corps
            )
        else:
            # Clause ad hoc : titre et corps sont obligatoires.
            if not titre:
                raise serializers.ValidationError(
                    {"titre": "Ce champ est obligatoire sans clause source."}
                )
            if not corps:
                raise serializers.ValidationError(
                    {"corps": "Ce champ est obligatoire sans clause source."}
                )
        return attrs


class RendreContratSerializer(serializers.Serializer):
    """Corps optionnel de POST /contrats/<id>/rendre/ (CONTRAT10).

    ``gabarit`` permet de fournir un corps-modèle ad hoc à fusionner ; s'il est
    omis, le rendu utilise le corps du ``ModeleContrat`` lié (ou un gabarit par
    défaut). Tous les champs sont facultatifs.
    """
    gabarit = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False)


class ChangerStatutSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/changer-statut/ (CONTRAT12).

    ``statut`` est le statut cible de la transition gardée.
    """
    statut = serializers.ChoiceField(choices=Contrat.Statut.choices)


class RenouvelerContratSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/renouveler/ (CONTRAT23).

    Détermine la nouvelle période de renouvellement. Les deux champs sont
    optionnels mais l'UN au moins (ou une ``duree_reconduction_mois`` déjà posée
    sur le contrat) est nécessaire pour calculer la nouvelle fin :

    - ``nouvelle_date_fin`` : date de fin explicite (prioritaire) ;
    - ``duree_mois``        : nombre de mois à ajouter à la fin courante.

    L'auteur, la société et l'horodatage du renouvellement sont posés CÔTÉ
    SERVEUR — jamais lus du corps de requête.
    """
    nouvelle_date_fin = serializers.DateField(required=False, allow_null=True)
    duree_mois = serializers.IntegerField(
        required=False, allow_null=True, min_value=1)


class InstancierContratSerializer(serializers.Serializer):
    """Corps de la requête POST /modeles/<id>/instancier/.

    Permet de surcharger les valeurs par défaut du gabarit au moment de
    l'instanciation. Tous les champs sont facultatifs : les valeurs manquantes
    sont héritées du gabarit.
    """
    objet = serializers.CharField(max_length=255, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=50, required=False, allow_blank=True)


class RegleApprobationSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``RegleApprobation`` (règle d'approbation — CONTRAT13).

    ``company`` n'est jamais exposée en écriture : posée côté serveur par le
    ``TenantMixin``. Les champs ``_display`` sont en lecture seule. La cohérence
    des bornes de montant est validée (min ≤ max).
    """
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    niveau_approbation_display = serializers.CharField(
        source='get_niveau_approbation_display', read_only=True)

    class Meta:
        model = RegleApprobation
        fields = [
            'id', 'libelle', 'type_contrat', 'type_contrat_display',
            'montant_min', 'montant_max',
            'niveau_approbation', 'niveau_approbation_display',
            'nombre_approbateurs', 'priorite', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """Borne min ≤ max quand les deux sont fixées (sinon borne ouverte)."""
        montant_min = attrs.get(
            'montant_min', getattr(self.instance, 'montant_min', None))
        montant_max = attrs.get(
            'montant_max', getattr(self.instance, 'montant_max', None))
        if (
            montant_min is not None
            and montant_max is not None
            and montant_min > montant_max
        ):
            raise serializers.ValidationError(
                'Le montant minimum ne peut pas dépasser le montant maximum.')
        return attrs


class ResoudreRegleApprobationSerializer(serializers.Serializer):
    """Paramètres de GET /regles-approbation/resoudre/ (CONTRAT13).

    ``montant`` est requis ; ``type_contrat`` est optionnel (vide = aucun type).
    """
    montant = serializers.DecimalField(max_digits=14, decimal_places=2)
    type_contrat = serializers.ChoiceField(
        choices=Contrat.TypeContrat.choices, required=False, allow_blank=True)


class EtapeApprobationSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``EtapeApprobation`` (étape de workflow — CONTRAT14).

    Lecture seule côté API : les étapes sont créées par le service de lancement
    du workflow et décidées via les actions ``approuver`` / ``rejeter`` du
    contrat — jamais en POST direct. ``company``, ``contrat``, ``regle``,
    ``approbateur``, ``statut`` et ``decision_le`` sont posés côté serveur.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    niveau_approbation_display = serializers.CharField(
        source='get_niveau_approbation_display', read_only=True)

    class Meta:
        model = EtapeApprobation
        fields = [
            'id', 'contrat', 'regle', 'niveau',
            'niveau_approbation', 'niveau_approbation_display',
            'approbateur', 'statut', 'statut_display',
            'decision_le', 'commentaire', 'date_creation',
        ]
        read_only_fields = fields


class DeciderEtapeSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/approuver-etape|rejeter-etape/ (CONTRAT14).

    ``etape`` désigne l'étape (id) à décider ; ``commentaire`` est optionnel.
    L'approbateur est l'utilisateur courant (posé côté serveur).
    """
    etape = serializers.IntegerField(min_value=1)
    commentaire = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False)


class SignatureContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``SignatureContrat`` (signature e-sign IN-APP — CONTRAT16).

    Lecture seule côté API : les signatures sont créées exclusivement par
    l'action ``signer`` du contrat (jamais en POST direct). ``company``,
    ``contrat``, ``signataire`` (utilisateur agissant), les preuves
    (``ip_adresse`` / ``user_agent``) et ``date_signature`` sont posés côté
    serveur — jamais lus du corps de requête.
    """
    role_signataire_display = serializers.CharField(
        source='get_role_signataire_display', read_only=True)
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    signataire_username = serializers.SerializerMethodField()

    class Meta:
        model = SignatureContrat
        fields = [
            'id', 'contrat', 'signataire_nom',
            'signataire', 'signataire_username',
            'role_signataire', 'role_signataire_display',
            'date_signature', 'ip_adresse', 'user_agent',
            'methode', 'methode_display',
        ]
        read_only_fields = fields

    def get_signataire_username(self, obj):
        return getattr(obj.signataire, 'username', None)


class SignerContratSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/signer/ (CONTRAT16).

    Loi 53-05 : un ``signataire_nom`` dactylographié consenti vaut signature.
    L'utilisateur agissant, la société et les preuves (IP, user agent) sont
    posés côté serveur — jamais lus du corps de requête. ``methode`` est
    optionnelle (``typed`` par défaut).
    """
    signataire_nom = serializers.CharField(max_length=255)
    role_signataire = serializers.ChoiceField(
        choices=SignatureContrat.RoleSignataire.choices)
    methode = serializers.ChoiceField(
        choices=SignatureContrat.Methode.choices, required=False)

    def validate_signataire_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'Le nom du signataire est requis (loi 53-05).')
        return value


class VersionContratSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``VersionContrat`` (version immuable d'un rendu — CONTRAT18).

    Lecture seule côté API : les versions sont créées exclusivement par l'action
    ``creer-version`` du contrat (jamais en POST direct sur cette ressource), et
    ne sont JAMAIS modifiées ni supprimées une fois figées. ``company``,
    ``contrat``, ``version``, ``cree_par`` et ``cree_le`` sont posés côté serveur
    — jamais lus du corps de requête.
    """
    cree_par_username = serializers.SerializerMethodField()

    class Meta:
        model = VersionContrat
        fields = [
            'id', 'contrat', 'version', 'contenu', 'fichier_key',
            'motif', 'cree_par', 'cree_par_username', 'cree_le',
        ]
        read_only_fields = fields

    def get_cree_par_username(self, obj):
        return getattr(obj.cree_par, 'username', None)


class CreerVersionSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/creer-version/ (CONTRAT18).

    ``motif`` et ``fichier_key`` sont optionnels. Le ``contenu`` est figé côté
    serveur (rendu par fusion du contrat) — jamais lu du corps : on ne laisse pas
    le client falsifier l'instantané immuable. ``version``, ``company`` et
    ``cree_par`` sont posés côté serveur.
    """
    motif = serializers.CharField(
        max_length=255, required=False, allow_blank=True)
    fichier_key = serializers.CharField(
        max_length=512, required=False, allow_blank=True)


class AvenantSerializer(serializers.ModelSerializer):
    """Sérialiseur d'un ``Avenant`` (amendement de contrat — CONTRAT24).

    Lecture seule côté API : les avenants sont créés exclusivement par l'action
    ``creer-avenant`` du contrat (jamais en POST direct sur cette ressource).
    ``company``, ``contrat``, ``numero``, ``version_creee``, ``cree_par`` et
    ``date_creation`` sont posés côté serveur — jamais lus du corps de requête.
    """
    cree_par_username = serializers.SerializerMethodField()

    class Meta:
        model = Avenant
        fields = [
            'id', 'contrat', 'numero', 'objet', 'description',
            'date_effet', 'montant_delta', 'version_creee',
            'cree_par', 'cree_par_username', 'date_creation',
        ]
        read_only_fields = fields

    def get_cree_par_username(self, obj):
        return getattr(obj.cree_par, 'username', None)


class CreerAvenantSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/creer-avenant/ (CONTRAT24).

    ``objet`` (titre court de l'amendement) est requis ; ``description``,
    ``date_effet`` et ``montant_delta`` sont optionnels. Quand ``montant_delta``
    est fourni, il est AJOUTÉ à ``Contrat.montant`` côté serveur. Le ``numero``,
    la société, ``version_creee`` et ``cree_par`` sont posés côté serveur — jamais
    lus du corps de requête.
    """
    objet = serializers.CharField(max_length=255)
    description = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False)
    date_effet = serializers.DateField(required=False, allow_null=True)
    montant_delta = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True)

    def validate_objet(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                "L'objet de l'avenant est requis.")
        return value


class ResiliationSerializer(serializers.ModelSerializer):
    """Sérialiseur d'une ``Resiliation`` (résiliation de contrat — CONTRAT25).

    Lecture seule côté API : les résiliations sont créées exclusivement par
    l'action ``resilier`` du contrat (jamais en POST direct sur cette ressource).
    ``company``, ``contrat``, ``statut``, ``date_demande``, ``version_creee``,
    ``cree_par`` et ``date_creation`` sont posés côté serveur — jamais lus du
    corps de requête.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    cree_par_username = serializers.SerializerMethodField()
    motif_ref_libelle = serializers.CharField(
        source='motif_ref.libelle', read_only=True, default=None)

    class Meta:
        model = Resiliation
        fields = [
            'id', 'contrat', 'motif', 'motif_ref', 'motif_ref_libelle',
            'date_demande', 'date_effet',
            'preavis_jours', 'solde', 'statut', 'statut_display',
            'version_creee', 'cree_par', 'cree_par_username', 'date_creation',
        ]
        read_only_fields = fields

    def get_cree_par_username(self, obj):
        return getattr(obj.cree_par, 'username', None)


class ResilierContratSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/resilier/ (CONTRAT25).

    Enregistre la résiliation et fait basculer le contrat vers ``resilie`` via la
    machine d'états gardée (jamais un funnel STAGES.py). Tous les champs sont
    optionnels :

    - ``motif``         : motif/justification de la résiliation (texte libre) ;
    - ``motif_ref``     : ZCTR3 — id d'un ``MotifResiliation`` normalisé, EN
      PLUS du texte libre (jamais en remplacement) ; doit appartenir à la
      société du contrat, sinon 400 ;
    - ``date_effet``    : date de prise d'effet (après préavis) ;
    - ``preavis_jours`` : préavis observé, en jours ;
    - ``solde``         : solde de tout compte / indemnité.

    Le ``statut`` de la résiliation, sa ``date_demande``, la société,
    ``version_creee`` et ``cree_par`` sont posés CÔTÉ SERVEUR — jamais lus du
    corps de requête.
    """
    motif = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False)
    motif_ref = serializers.PrimaryKeyRelatedField(
        required=False, allow_null=True,
        queryset=MotifResiliation.objects.all())
    date_effet = serializers.DateField(required=False, allow_null=True)
    preavis_jours = serializers.IntegerField(
        required=False, allow_null=True, min_value=0)
    solde = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True)


class GenererDevisRenouvellementSerializer(serializers.Serializer):
    """Corps de POST /contrats/<id>/generer-devis-renouvellement/ (XCTR12).

    ``valeur_indice`` (optionnel) : valeur COURANTE de l'indice de référence
    de la première ``IndexationPrix`` active du contrat — si fournie, le
    montant proposé est révisé par la formule d'indexation (CONTRAT32) ; sinon
    le montant courant du contrat est repris tel quel.
    """
    valeur_indice = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, allow_null=True,
        min_value=0)


class JalonContratSerializer(serializers.ModelSerializer):
    """Jalon / étape clé d'un contrat (CONTRAT26).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. ``numero``,
    ``statut``, ``date_atteinte`` et ``date_creation`` sont posés côté serveur
    (le jalon est créé via l'action ``creer-jalon`` ou marqué via
    ``marquer-atteint``).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = JalonContrat
        fields = [
            'id', 'contrat', 'numero', 'intitule', 'description', 'date_cible',
            'statut', 'statut_display', 'date_atteinte', 'date_creation',
        ]
        read_only_fields = [
            'numero', 'statut', 'statut_display', 'date_atteinte',
            'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class ObligationSerializer(serializers.ModelSerializer):
    """Obligation / livrable contractuel (CONTRAT26).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` et le ``jalon`` (optionnel) sont validés
    même-société. ``date_realisation`` est posée côté serveur (action
    ``marquer-faite``) et reste en lecture seule.
    """
    redevable_display = serializers.CharField(
        source='get_redevable_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Obligation
        fields = [
            'id', 'contrat', 'jalon', 'intitule', 'description', 'redevable',
            'redevable_display', 'date_echeance', 'statut', 'statut_display',
            'date_realisation', 'ordre', 'date_creation',
        ]
        read_only_fields = [
            'date_realisation', 'redevable_display', 'statut_display',
            'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat

    def validate_jalon(self, jalon):
        """Le jalon rattaché (optionnel) doit appartenir à la même société."""
        if jalon is None:
            return jalon
        request = self.context.get('request')
        if request is not None and jalon.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce jalon n'appartient pas à votre société.")
        return jalon


class EngagementSLASerializer(serializers.ModelSerializer):
    """Engagement de niveau de service (SLA) & pénalités (CONTRAT27).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. La validation des
    bornes (taux cible ∈ [0,100], pénalité ≥ 0…) est relayée depuis
    ``EngagementSLA.clean``.
    """
    mode_penalite_display = serializers.CharField(
        source='get_mode_penalite_display', read_only=True)

    class Meta:
        model = EngagementSLA
        fields = [
            'id', 'contrat', 'libelle', 'taux_cible', 'unite',
            'mode_penalite', 'mode_penalite_display', 'valeur_penalite',
            'penalite_max', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat

    def validate(self, attrs):
        """Relaie la validation des bornes du modèle (``clean``).

        Construit un objet de contrôle avec les valeurs courantes (instance en
        update) surchargées par les valeurs entrantes, et appelle ``clean``.
        """
        from django.core.exceptions import ValidationError as DjangoVE

        controle = EngagementSLA()
        for field in ('taux_cible', 'valeur_penalite', 'mode_penalite'):
            valeur = attrs.get(
                field, getattr(self.instance, field, None)
                if self.instance is not None else None)
            if valeur is not None:
                setattr(controle, field, valeur)
        try:
            controle.clean()
        except DjangoVE as exc:
            raise serializers.ValidationError(
                exc.messages if hasattr(exc, 'messages') else str(exc))
        return attrs


class LigneEcheanceSerializer(serializers.ModelSerializer):
    """Ligne (échéance) d'un échéancier — lecture seule (CONTRAT30).

    Les lignes sont créées via l'action ``ajouter-ligne`` de l'échéancier
    (numéro = max+1 côté serveur). ``date_paiement`` est posée côté serveur au
    pointage (``pointer-paiement``). ``company``, ``numero`` et ``date_paiement``
    ne sont jamais lus du corps de requête.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = LigneEcheance
        fields = [
            'id', 'echeancier', 'numero', 'libelle', 'date_echeance',
            'montant', 'statut', 'statut_display', 'date_paiement',
            'facture_id', 'date_creation',
        ]
        read_only_fields = fields


class EcheancierContratSerializer(serializers.ModelSerializer):
    """Échéancier de paiement d'un contrat (en-tête) — CONTRAT30.

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. ``montant_total`` est
    CALCULÉ côté serveur (somme des lignes) et reste en lecture seule. Les lignes
    sont sérialisées en lecture seule (``lignes``).
    """
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    lignes = LigneEcheanceSerializer(many=True, read_only=True)

    class Meta:
        model = EcheancierContrat
        fields = [
            'id', 'contrat', 'libelle', 'periodicite', 'periodicite_display',
            'montant_total', 'devise', 'statut', 'statut_display',
            'facturation_active', 'lignes', 'date_creation',
        ]
        read_only_fields = [
            'montant_total', 'periodicite_display', 'statut_display',
            'lignes', 'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class AjouterLigneEcheanceSerializer(serializers.Serializer):
    """Corps de POST /echeanciers/<id>/ajouter-ligne/ (CONTRAT30).

    ``date_echeance`` requise ; ``montant`` et ``libelle`` optionnels. Le
    ``numero``, la société et le statut sont posés CÔTÉ SERVEUR.
    """
    date_echeance = serializers.DateField()
    montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True,
        min_value=0)
    libelle = serializers.CharField(
        required=False, allow_blank=True, max_length=200)


class IndexationPrixSerializer(serializers.ModelSerializer):
    """Règle d'indexation / révision de prix d'un contrat (CONTRAT32).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. ``date_derniere_revision``
    est posée côté serveur (action ``appliquer``) et reste en lecture seule. La
    validation des bornes (valeur de base > 0, part fixe ∈ [0,1]) est relayée
    depuis ``IndexationPrix.clean``.
    """
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)

    class Meta:
        model = IndexationPrix
        fields = [
            'id', 'contrat', 'libelle', 'indice', 'valeur_base', 'part_fixe',
            'periodicite', 'periodicite_display', 'date_derniere_revision',
            'actif', 'date_creation',
        ]
        read_only_fields = [
            'periodicite_display', 'date_derniere_revision', 'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat

    def validate(self, attrs):
        """Relaie la validation des bornes du modèle (``clean``)."""
        from django.core.exceptions import ValidationError as DjangoVE

        controle = IndexationPrix()
        for field in ('valeur_base', 'part_fixe'):
            valeur = attrs.get(
                field, getattr(self.instance, field, None)
                if self.instance is not None else None)
            if valeur is not None:
                setattr(controle, field, valeur)
        try:
            controle.clean()
        except DjangoVE as exc:
            raise serializers.ValidationError(
                exc.messages if hasattr(exc, 'messages') else str(exc))
        return attrs


class IndexationActionSerializer(serializers.Serializer):
    """Corps des actions simuler/appliquer d'une indexation (CONTRAT32).

    ``valeur_actuelle`` (requis) : valeur courante de l'indice de référence.
    ``prix_base`` (optionnel, simulation seulement) : base de calcul si différente
    du montant du contrat.
    """
    valeur_actuelle = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=0)
    prix_base = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True,
        min_value=0)


class CampagneRevisionSerializer(serializers.Serializer):
    """Corps de POST /contrats/campagne-revision/ (XCTR11).

    ``filtres`` (optionnel) : ``{type_contrat, statut, responsable_id}``.
    ``pct`` (requis) : pourcentage de révision (ex. 5 = +5 %, -3 = -3 %).
    ``date_effet`` (optionnel, application seulement) : défaut aujourd'hui.
    ``preview`` (défaut ``True``) : aucune écriture tant que ``False`` n'est
    pas explicitement passé.
    """
    filtres = serializers.DictField(required=False, allow_null=True)
    pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    date_effet = serializers.DateField(required=False, allow_null=True)
    preview = serializers.BooleanField(required=False, default=True)


class RollbackCampagneRevisionSerializer(serializers.Serializer):
    """Corps de POST /contrats/campagne-revision-rollback/ (XCTR11).

    ``avenant_ids`` : liste des ids d'avenants à compenser (retournés par
    l'application de la campagne — ``rollback_ids``).
    """
    avenant_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False)


class PenaliteSLASerializer(serializers.Serializer):
    """Corps de POST /sla/<id>/penalite/ (CONTRAT27).

    ``taux_realise`` (optionnel) : taux de service effectivement réalisé en %.
    Quand il atteint le taux cible, aucune pénalité n'est due. ``montant_contrat``
    (optionnel) : montant de base pour le mode pourcentage (défaut = montant du
    contrat). Lecture seule : ne crée aucune écriture.
    """
    taux_realise = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True,
        min_value=0)
    montant_contrat = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True,
        min_value=0)


class RetenueGarantieSerializer(serializers.ModelSerializer):
    """Retenue de garantie & suivi de libération (CONTRAT28).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. ``montant_retenu``
    est CALCULÉ côté serveur (= base × taux %) et reste en lecture seule ; le
    ``statut`` et ``date_liberation_effective`` sont posés côté serveur (action
    ``liberer``) — un POST ne peut pas forcer une retenue « libérée ».
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RetenueGarantie
        fields = [
            'id', 'contrat', 'montant_base', 'taux', 'montant_retenu',
            'date_retenue', 'date_liberation_prevue',
            'date_liberation_effective', 'statut', 'statut_display', 'note',
            'date_creation',
        ]
        read_only_fields = [
            'montant_retenu', 'date_liberation_effective', 'statut',
            'statut_display', 'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat

    def validate_taux(self, value):
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(
                'Le taux de retenue doit être compris entre 0 et 100.')
        return value


class CautionSerializer(serializers.ModelSerializer):
    """Caution / garantie liée à un contrat — registre (CONTRAT29).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. Le ``statut`` est un
    simple champ de registre (éditable) — il ne pilote AUCUNE machine d'états du
    contrat (CONTRAT12).
    """
    type_caution_display = serializers.CharField(
        source='get_type_caution_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Caution
        fields = [
            'id', 'contrat', 'type_caution', 'type_caution_display', 'garant',
            'reference', 'montant', 'devise', 'date_emission',
            'date_expiration', 'statut', 'statut_display', 'note',
            'date_creation',
        ]
        read_only_fields = [
            'type_caution_display', 'statut_display', 'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class PieceConformiteSerializer(serializers.ModelSerializer):
    """Pièce de conformité / attestation obligatoire d'un contrat (CONTRAT34).

    ``company`` n'est jamais exposée : elle est posée côté serveur (déduite du
    contrat). Le ``contrat`` reçu est validé même-société. ``date_fourniture``
    est posée côté serveur (action ``marquer-fournie``) et reste en lecture seule.
    """
    type_piece_display = serializers.CharField(
        source='get_type_piece_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PieceConformite
        fields = [
            'id', 'contrat', 'type_piece', 'type_piece_display', 'libelle',
            'obligatoire', 'statut', 'statut_display', 'ged_document_id',
            'date_fourniture', 'date_expiration', 'note', 'date_creation',
        ]
        read_only_fields = [
            'type_piece_display', 'statut_display', 'date_fourniture',
            'date_creation',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class MarquerPieceFournieSerializer(serializers.Serializer):
    """Corps de POST /pieces-conformite/<id>/marquer-fournie/ (CONTRAT34).

    Tous les champs sont optionnels : ``ged_document_id`` (lien LÂCHE vers un
    document GED), ``date_expiration``. Le ``statut`` et ``date_fourniture`` sont
    posés CÔTÉ SERVEUR.
    """
    ged_document_id = serializers.IntegerField(
        required=False, allow_null=True, min_value=1)
    date_expiration = serializers.DateField(required=False, allow_null=True)


class CycleFacturationLogSerializer(serializers.ModelSerializer):
    """Entrée du journal de facturation récurrente — XCTR5.

    TOUS les champs sont en LECTURE SEULE côté API : les entrées sont créées
    exclusivement côté serveur par les services de facturation récurrente
    (``services.enregistrer_cycle``). ``company`` n'est jamais lue du corps de
    requête.
    """
    source_type_display = serializers.CharField(
        source='get_source_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = CycleFacturationLog
        fields = [
            'id', 'source_type', 'source_type_display', 'source_id',
            'periode', 'statut', 'statut_display', 'motif', 'facture_id',
            'nb_tentatives', 'date_creation',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# XCTR17 — Location de matériel SORTANTE (aux clients)
# ---------------------------------------------------------------------------


class OrdreLocationSerializer(serializers.ModelSerializer):
    """``OrdreLocation`` (XCTR17). ``company`` posée côté serveur ; le produit
    doit être ``louable`` (vérifié en vue, jamais ici, pour garder ce
    sérialiseur réutilisable en lecture comme en écriture)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True)

    caution_statut_display = serializers.CharField(
        source='get_caution_statut_display', read_only=True)

    class Meta:
        model = OrdreLocation
        fields = [
            'id', 'client_id', 'produit', 'produit_nom', 'numero_serie',
            'devis_id', 'devis_ligne_id',
            'date_reservation', 'date_enlevement_prevue',
            'date_retour_prevue', 'date_enlevement_reelle',
            'date_retour_reelle', 'statut', 'statut_display', 'tarif_jour',
            'montant_estime', 'note', 'date_creation',
            'caution_montant', 'caution_statut', 'caution_statut_display',
            'caution_retenue', 'caution_motif_retenue',
            'frais_retard_jour', 'frais_retard_montant',
            'frais_retard_facture_id', 'inspection_checklist',
            'inspection_releve_compteur', 'inspection_dommages_montant',
            'inspection_facture_id', 'inspection_ticket_sav_id',
            'inspection_date', 'facturation_recurrente_active',
            'facturation_periodicite', 'facturation_moment',
            'derniere_facturation',
        ]
        read_only_fields = [
            'id', 'statut', 'date_enlevement_reelle', 'date_retour_reelle',
            'montant_estime', 'date_creation', 'devis_id', 'devis_ligne_id',
            'caution_montant', 'caution_statut', 'caution_retenue',
            'caution_motif_retenue',
            'frais_retard_montant', 'frais_retard_facture_id',
            'inspection_dommages_montant', 'inspection_facture_id',
            'inspection_ticket_sav_id', 'inspection_date',
            'derniere_facturation',
        ]


class ChangerStatutOrdreLocationSerializer(serializers.Serializer):
    """Corps de POST /ordres-location/<id>/changer-statut/ (XCTR17)."""
    statut = serializers.ChoiceField(choices=OrdreLocation.Statut.choices)


class ProlongerOrdreLocationSerializer(serializers.Serializer):
    """Corps de POST /ordres-location/<id>/prolonger/ (XCTR20)."""
    nouvelle_date_retour = serializers.DateField()


class EcourterOrdreLocationSerializer(serializers.Serializer):
    """Corps de POST /ordres-location/<id>/ecourter/ (XCTR20)."""
    nouvelle_date_retour = serializers.DateField()


class PlanRecurrentSerializer(serializers.ModelSerializer):
    """Plan de facturation récurrente réutilisable (nommé) — ZCTR1.

    ``company`` n'est jamais exposée en écriture (posée côté serveur par le
    ``TenantMixin``). ``intervalle`` doit être ≥ 1.
    """
    unite_display = serializers.CharField(
        source='get_unite_display', read_only=True)

    class Meta:
        model = PlanRecurrent
        fields = [
            'id', 'nom', 'unite', 'unite_display', 'intervalle',
            'delai_cloture_auto_jours', 'aligner_debut_periode', 'actif',
            'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']

    def validate_intervalle(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "L'intervalle doit être un entier positif (≥ 1).")
        return value


class MotifResiliationSerializer(serializers.ModelSerializer):
    """Référentiel éditable des motifs de résiliation (close reasons) — ZCTR3.

    ``company`` n'est jamais exposée en écriture (posée côté serveur par le
    ``TenantMixin``).
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = MotifResiliation
        fields = [
            'id', 'code', 'libelle', 'ordre', 'actif', 'categorie',
            'categorie_display', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']


class ParametresLocationSerializer(serializers.ModelSerializer):
    """Réglages de location, singleton par société — ZCTR4.

    ``company`` n'est jamais exposée en écriture (posée côté serveur par le
    viewset, qui garantit une seule ligne par société — ``get_or_create``).
    Toutes les valeurs NULL/0 laissent le comportement XCTR17/19 inchangé.
    """

    class Meta:
        model = ParametresLocation
        fields = [
            'id', 'duree_minimale_jours', 'temps_securite_heures',
            'frais_retard_jour_defaut', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']
