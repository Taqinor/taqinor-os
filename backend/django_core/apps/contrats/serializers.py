"""Sérialiseurs de la Gestion des contrats.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est également posé côté
serveur.
"""
from rest_framework import serializers

from .models import (
    AlerteContrat,
    Avenant,
    Clause,
    ClauseContrat,
    Contrat,
    ContratActivity,
    ContratLien,
    EngagementSLA,
    EtapeApprobation,
    JalonContrat,
    ModeleContrat,
    ModeleContratClause,
    Obligation,
    PartieContrat,
    RegleApprobation,
    Resiliation,
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
    de maintenance SAV (``sav.ContratMaintenance``) : il est STOCKÉ tel quel,
    sans validation cross-app — l'app ``sav`` n'expose pas de ``selectors.py``
    aujourd'hui, donc on ne vérifie pas l'existence/la société de la cible et on
    n'importe JAMAIS ``apps.sav``. Quand un sélecteur SAV de lecture existera,
    l'enrichissement/validation pourra s'y brancher (même schéma que les
    ``ContratLien`` enrichis dans ``selectors.py``).
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
            'montant', 'devise',
            'confidentialite', 'confidentialite_display',
            'created_by', 'date_creation',
        ]
        read_only_fields = [
            'created_by', 'date_creation',
            'date_dernier_renouvellement', 'nb_renouvellements',
        ]

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

    class Meta:
        model = Clause
        fields = [
            "id",
            "titre",
            "categorie",
            "type_clause",
            "type_clause_display",
            "corps",
            "ordre",
            "actif",
            "date_creation",
        ]
        read_only_fields = ["date_creation"]


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

    class Meta:
        model = Resiliation
        fields = [
            'id', 'contrat', 'motif', 'date_demande', 'date_effet',
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

    - ``motif``         : motif/justification de la résiliation ;
    - ``date_effet``    : date de prise d'effet (après préavis) ;
    - ``preavis_jours`` : préavis observé, en jours ;
    - ``solde``         : solde de tout compte / indemnité.

    Le ``statut`` de la résiliation, sa ``date_demande``, la société,
    ``version_creee`` et ``cree_par`` sont posés CÔTÉ SERVEUR — jamais lus du
    corps de requête.
    """
    motif = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False)
    date_effet = serializers.DateField(required=False, allow_null=True)
    preavis_jours = serializers.IntegerField(
        required=False, allow_null=True, min_value=0)
    solde = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True)


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
