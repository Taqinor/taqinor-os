"""Sérialiseurs de la Gestion des contrats.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est également posé côté
serveur.
"""
from rest_framework import serializers

from .models import (
    Clause,
    ClauseContrat,
    Contrat,
    ContratLien,
    ModeleContrat,
    ModeleContratClause,
    PartieContrat,
)


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

    class Meta:
        model = Contrat
        fields = [
            'id', 'reference', 'type_contrat', 'type_contrat_display',
            'objet', 'statut', 'statut_display', 'client_id',
            'sav_contrat_maintenance_id', 'date_debut',
            'date_fin', 'montant', 'devise',
            'confidentialite', 'confidentialite_display',
            'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']


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


class InstancierContratSerializer(serializers.Serializer):
    """Corps de la requête POST /modeles/<id>/instancier/.

    Permet de surcharger les valeurs par défaut du gabarit au moment de
    l'instanciation. Tous les champs sont facultatifs : les valeurs manquantes
    sont héritées du gabarit.
    """
    objet = serializers.CharField(max_length=255, required=False, allow_blank=True)
    reference = serializers.CharField(max_length=50, required=False, allow_blank=True)
