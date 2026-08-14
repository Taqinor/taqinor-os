"""AOF61/AOF62 — sérialiseurs de l'API de calepinage.

Ces sérialiseurs ne portent AUCUNE règle métier : ils valident la FORME d'une
demande et nomment le champ fautif. Un payload invalide doit produire un 400
qui dit LEQUEL des champs est en cause — « 400 Bad Request » nu oblige à
deviner, et c'est ce qui transforme une erreur de saisie en ticket.

``company`` n'apparaît dans AUCUN champ d'entrée : elle est toujours résolue
côté serveur depuis ``request.user.company`` (règle multi-tenant du dépôt).
"""
from __future__ import annotations

from rest_framework import serializers

__all__ = [
    'DemandeCalepinageSerializer', 'DemandeJobCalepinageSerializer',
    'ResultatCalepinageSerializer', 'JobCalepinageSerializer',
    'ComparaisonVariantesSerializer', 'PreuveCalepinageSerializer',
    'MargesCalepinageSerializer', 'TiroirsCalepinageSerializer',
    'SuggestionCalepinageSerializer',
]


class DemandeCalepinageSerializer(serializers.Serializer):
    """Une demande de calcul : PAR TOITURE, ou par document d'entrée brut.

    Les deux portes existent parce qu'elles servent deux usages réels :
    ``toiture`` est le chemin produit (l'atelier recalcule la toiture ouverte)
    ; ``entree`` est le chemin expert (rejouer un document du contrat AOF57
    tel quel, par exemple un golden). Elles s'excluent : accepter les deux à
    la fois obligerait à choisir en silence laquelle gagne.
    """

    toiture = serializers.IntegerField(
        required=False, allow_null=True,
        help_text="Identifiant de la toiture à calepiner.")
    params = serializers.JSONField(
        required=False,
        help_text="Paramètres de calepinage (défaut : ceux de la toiture).")
    entree = serializers.JSONField(
        required=False,
        help_text="Document d'entrée du contrat de calepinage (mode expert).")

    def validate(self, attrs):
        toiture = attrs.get('toiture')
        entree = attrs.get('entree')
        if toiture is None and entree is None:
            raise serializers.ValidationError({'toiture': (
                "Indiquez une toiture à calepiner, ou fournissez un document "
                "d'entrée complet dans « entree »."
            )})
        if toiture is not None and entree is not None:
            raise serializers.ValidationError({'entree': (
                "« toiture » et « entree » s'excluent : fournissez l'un OU "
                "l'autre, jamais les deux."
            )})
        if entree is not None and not isinstance(entree, dict):
            raise serializers.ValidationError({'entree': (
                "Le document d'entrée doit être un objet JSON."
            )})
        if attrs.get('params') is not None and \
                not isinstance(attrs['params'], dict):
            raise serializers.ValidationError({'params': (
                "Les paramètres de calepinage doivent être un objet JSON."
            )})
        return attrs


class DemandeJobCalepinageSerializer(DemandeCalepinageSerializer):
    """Même demande, lancée en TÂCHE DE FOND (``core.jobs``)."""

    persister = serializers.BooleanField(
        default=False,
        help_text="Écrire le résultat dans une variante de calepinage.")
    nom = serializers.CharField(required=False, allow_blank=True,
                                max_length=255)
    role = serializers.CharField(required=False, allow_blank=True,
                                 max_length=12)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get('persister') and attrs.get('toiture') is None:
            raise serializers.ValidationError({'persister': (
                "Persister un résultat exige une toiture : un document brut "
                "n'appartient à aucune toiture."
            )})
        return attrs


class PreuveCalepinageSerializer(serializers.Serializer):
    """La PREUVE publiée — vocabulaire verrouillé d'AOF44."""

    total_retenu = serializers.IntegerField(read_only=True)
    total_optimal = serializers.IntegerField(read_only=True, allow_null=True)
    methode = serializers.CharField(read_only=True)
    methode_exacte = serializers.BooleanField(read_only=True)
    optimal = serializers.BooleanField(read_only=True)
    libelle = serializers.CharField(read_only=True)
    pas_cm = serializers.FloatField(read_only=True)
    nb_optima = serializers.IntegerField(read_only=True, allow_null=True)
    borne_superieure = serializers.IntegerField(read_only=True,
                                                allow_null=True)
    marge_troncon_min = serializers.FloatField(read_only=True,
                                               allow_null=True)
    marge_bande_min = serializers.FloatField(read_only=True, allow_null=True)
    rangee_critique = serializers.CharField(read_only=True)
    obstacle_critique = serializers.CharField(read_only=True)
    controles = serializers.ListField(child=serializers.CharField(),
                                      read_only=True)
    version_moteur = serializers.CharField(read_only=True)


class MargesCalepinageSerializer(serializers.Serializer):
    """PV49 — les marges MESURÉES par la passe de robustesse, en centimètres.

    Les deux grandeurs sont ``allow_null`` et c'est le cœur du contrat : une
    marge NON MESURÉE vaut ``null``, jamais ``0`` — un ``0`` ferait lire « au
    ras » là où rien n'a été mesuré (une toiture sans obstacle n'a AUCUNE marge
    de bande). Le repère fautif dit lequel des deux cas s'applique : il est
    vide quand rien n'a été mesuré.
    """

    troncon_min_cm = serializers.FloatField(read_only=True, allow_null=True)
    bande_min_cm = serializers.FloatField(read_only=True, allow_null=True)
    rangee_critique = serializers.CharField(read_only=True, allow_blank=True)
    obstacle_critique = serializers.CharField(read_only=True, allow_blank=True)


# ── PV49 — les 5 tiroirs de l'atelier ────────────────────────────────────────
# PACT7 : ces sérialiseurs sont le MIROIR du dictionnaire que
# ``calepinage_io.tiroirs_vers_json`` construit. Un « type: object » sans
# propriété ne contredit rien — c'est exactement ce qui a laissé passer
# l'incident du 03/08/2026. Chaque clé publiée est donc NOMMÉE ici, et les
# feuilles (listes d'options, points de graphe) restent des objets JSON parce
# qu'elles portent des clés optionnelles que le moteur n'émet que lorsqu'il a
# réellement mesuré quelque chose.

class _DonneesKitsSerializer(serializers.Serializer):
    kits = serializers.ListField(child=serializers.JSONField(),
                                 read_only=True)
    granularites = serializers.ListField(child=serializers.JSONField(),
                                         read_only=True)
    approvisionnement = serializers.JSONField(read_only=True)
    recommandation = serializers.JSONField(read_only=True, required=False)
    composition = serializers.JSONField(read_only=True, required=False)
    contre_epreuve = serializers.ListField(child=serializers.JSONField(),
                                           read_only=True, required=False)


class _DonneesAlleesSerializer(serializers.Serializer):
    presets = serializers.ListField(child=serializers.JSONField(),
                                    read_only=True)
    graphe = serializers.JSONField(read_only=True, required=False)


class _DonneesRivesSerializer(serializers.Serializer):
    champs = serializers.ListField(child=serializers.JSONField(),
                                   read_only=True)
    variante_conservatrice = serializers.JSONField(read_only=True,
                                                   required=False)


class _DonneesOrientationSerializer(serializers.Serializer):
    sens_rangees = serializers.ListField(child=serializers.JSONField(),
                                         read_only=True)
    orientations_tables = serializers.ListField(child=serializers.JSONField(),
                                                read_only=True)
    segmentations = serializers.ListField(child=serializers.JSONField(),
                                          read_only=True)
    formes_l = serializers.ListField(child=serializers.JSONField(),
                                     read_only=True)


# Chaque tiroir a sa PROPRE classe nommée — pas une fabrique qui rendrait cinq
# classes de même nom : drf-spectacular nomme ses composants d'après la classe,
# et cinq homonymes se recouvriraient dans le schéma publié.
#
# ``donnees`` est TOUJOURS ``allow_null`` : un tiroir dégradé garde sa clé et
# rend ``null``, si bien que l'écran teste l'absence de DONNÉES et jamais
# l'absence de clé. ``valeurs`` porte la sélection courante à préremplir.

class TiroirKitsSerializer(serializers.Serializer):
    donnees = _DonneesKitsSerializer(read_only=True, allow_null=True)
    valeurs = serializers.JSONField(read_only=True)


class TiroirAlleesSerializer(serializers.Serializer):
    donnees = _DonneesAlleesSerializer(read_only=True, allow_null=True)
    valeurs = serializers.JSONField(read_only=True)


class TiroirRivesSerializer(serializers.Serializer):
    donnees = _DonneesRivesSerializer(read_only=True, allow_null=True)
    valeurs = serializers.JSONField(read_only=True)


class TiroirOrientationSerializer(serializers.Serializer):
    donnees = _DonneesOrientationSerializer(read_only=True, allow_null=True)
    valeurs = serializers.JSONField(read_only=True)


class _ChaineElectriqueSerializer(serializers.Serializer):
    libelle_taille = serializers.CharField(read_only=True, allow_blank=True)
    reste_texte = serializers.CharField(read_only=True, allow_blank=True)


class _OnduleursElectriqueSerializer(serializers.Serializer):
    nombre_texte = serializers.CharField(read_only=True, allow_blank=True)
    puissance_texte = serializers.CharField(read_only=True, allow_blank=True)
    plafond_texte = serializers.CharField(read_only=True, allow_blank=True)


class _RatioElectriqueSerializer(serializers.Serializer):
    texte = serializers.CharField(read_only=True, allow_blank=True)
    fourchette_texte = serializers.CharField(read_only=True, allow_blank=True)


class _ConformiteElectriqueSerializer(serializers.Serializer):
    conforme = serializers.BooleanField(read_only=True)
    bloquant = serializers.BooleanField(read_only=True)
    alerte = serializers.CharField(read_only=True, allow_blank=True)
    #: ``{texte, patch}`` ou ``null`` — le patch est REJOUABLE par
    #: ``majParametres`` (vocabulaire des paramètres), sinon la proposition est
    #: nulle : un bouton « appliquer » qui n'applique rien est pire que rien.
    repartition_proposee = serializers.JSONField(read_only=True,
                                                 allow_null=True)


class _DonneesElectriqueSerializer(serializers.Serializer):
    """PV44 — miroir EXACT de ``core.electrique.projeter_tiroirs``.

    Les quatre blocs sont ceux que ``TiroirElectrique.jsx`` lit, ni plus ni
    moins : une clé en trop est du code mort côté écran, une clé en moins est
    une ligne vide pour toujours.
    """

    chaine = _ChaineElectriqueSerializer(read_only=True)
    onduleurs = _OnduleursElectriqueSerializer(read_only=True)
    ratio_dc_ac = _RatioElectriqueSerializer(read_only=True)
    conformite = _ConformiteElectriqueSerializer(read_only=True)


class TiroirElectriqueSerializer(serializers.Serializer):
    """PV44 — le tiroir est ALIMENTÉ par ``core.electrique``.

    ``donnees`` reste ``allow_null`` : hors budget synchrone, le tiroir retombe
    sur sa forme dégradée, exactement comme les quatre autres.
    """

    donnees = _DonneesElectriqueSerializer(read_only=True, allow_null=True)
    valeurs = serializers.JSONField(read_only=True)


class TiroirsCalepinageSerializer(serializers.Serializer):
    """PV49 — les 5 tiroirs en UN SEUL bloc, chacun sous sa clé."""

    kits = TiroirKitsSerializer(read_only=True)
    allees = TiroirAlleesSerializer(read_only=True)
    rives = TiroirRivesSerializer(read_only=True)
    orientation = TiroirOrientationSerializer(read_only=True)
    electrique = TiroirElectriqueSerializer(read_only=True)


class ActionSuggestionSerializer(serializers.Serializer):
    """PV50 — ce que l'écran DOIT proposer d'appliquer en un clic.

    L'action est DISCRIMINÉE par ``type`` : ``parametres`` porte un ``patch``
    du dict de paramètres de calepinage ; ``obstacle`` porte le repère visé et
    la ``provenance`` à lui donner. Les clés de l'autre famille sont alors
    absentes — d'où ``required=False`` sur les trois : un schéma qui les
    déclarerait toutes obligatoires décrirait une réponse que le serveur
    n'envoie jamais.
    """

    type = serializers.CharField(read_only=True)
    patch = serializers.JSONField(read_only=True, required=False)
    obstacle = serializers.CharField(read_only=True, required=False)
    provenance = serializers.CharField(read_only=True, required=False)


class SuggestionCalepinageSerializer(serializers.Serializer):
    """PV50 — une proposition APPLICABLE, à gain REJOUÉ par le moteur.

    ``gain_modules`` est SIGNÉ : un arbitrage d'obstacle peut coûter des
    modules, et le publier positif ferait passer une perte assumée pour un
    gain.
    """

    code = serializers.CharField(read_only=True)
    titre = serializers.CharField(read_only=True)
    gain_modules = serializers.IntegerField(read_only=True)
    gain_kwc = serializers.FloatField(read_only=True, required=False)
    confiance = serializers.CharField(read_only=True, required=False)
    question_a_poser = serializers.CharField(read_only=True, required=False,
                                             allow_blank=True)
    action = ActionSuggestionSerializer(read_only=True)


class ResultatCalepinageSerializer(serializers.Serializer):
    """Le résultat d'un calepinage — il porte TOUJOURS (hash, version)."""

    repere = serializers.CharField(read_only=True)
    hash_entree = serializers.CharField(read_only=True)
    version_moteur = serializers.CharField(read_only=True)
    schema_version = serializers.IntegerField(read_only=True)
    total_modules = serializers.IntegerField(read_only=True)
    kwc = serializers.FloatField(read_only=True)
    engageable = serializers.BooleanField(read_only=True)
    motifs_non_engageable = serializers.ListField(
        child=serializers.CharField(), read_only=True)
    engagement_modules = serializers.IntegerField(read_only=True,
                                                  allow_null=True)
    plans = serializers.ListField(child=serializers.JSONField(),
                                  read_only=True)
    rangees = serializers.ListField(child=serializers.JSONField(),
                                    read_only=True)
    preuve = PreuveCalepinageSerializer(read_only=True)
    #: PV49 — les deux blocs de l'atelier. Toujours PRÉSENTS : ``marges`` porte
    #: des ``null`` pour ce qui n'a pas été mesuré, ``tiroirs`` un jeu dégradé
    #: quand ils n'ont pas été produits.
    marges = MargesCalepinageSerializer(read_only=True)
    tiroirs = TiroirsCalepinageSerializer(read_only=True)
    #: PV50 — capées côté service ; une liste VIDE quand elles ne sont pas
    #: produites, jamais une clé absente.
    suggestions = SuggestionCalepinageSerializer(many=True, read_only=True)
    depuis_cache = serializers.BooleanField(read_only=True, required=False)


class JobCalepinageSerializer(serializers.Serializer):
    """L'état d'un calcul de fond + son résultat quand il est là."""

    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    statut = serializers.CharField(read_only=True)
    progress_pct = serializers.IntegerField(read_only=True)
    message_erreur = serializers.CharField(read_only=True)
    resultat = ResultatCalepinageSerializer(read_only=True,
                                            required=False,
                                            allow_null=True)
    variante = serializers.IntegerField(read_only=True, allow_null=True,
                                        required=False)


class ComparaisonVariantesSerializer(serializers.Serializer):
    """AOF62 — comparaison de N variantes en UN appel."""

    ids = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Identifiants de variantes séparés par des virgules.")

    def validate_ids(self, valeur):
        identifiants = []
        for brut in (valeur or '').replace(';', ',').split(','):
            brut = brut.strip()
            if not brut:
                continue
            if not brut.isdigit():
                raise serializers.ValidationError(
                    "« %s » n'est pas un identifiant de variante." % brut)
            identifiants.append(int(brut))
        if not identifiants:
            raise serializers.ValidationError(
                "Indiquez au moins un identifiant de variante à comparer.")
        return identifiants
