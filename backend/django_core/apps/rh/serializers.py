"""Sérialiseurs des Ressources humaines.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    AccidentTravail,
    AffectationRoster,
    AffectationVehicule,
    AnalyseRisquesChantier,
    AvanceSalaire,
    BesoinFormation,
    BulletinPaie,
    CampagneEvaluation,
    Candidature,
    CandidatureActivity,
    CauserieParticipant,
    CauserieSecurite,
    Certification,
    Competence,
    CompetenceEmploye,
    CompetenceRequise,
    CorrectionPointage,
    DemandeConge,
    DemandeRH,
    Departement,
    DeviceKiosque,
    DocumentEmploye,
    EmployeDeviceMap,
    EntretienRecrutement,
    GabaritEmailRecrutement,
    GrilleSalariale,
    NoteEntretien,
    PeriodeFermeture,
    PromesseEmbauche,
    ReglageRH,
    DossierActivity,
    DossierEmploye,
    DotationEpi,
    ElementIntegration,
    ElementIntegrationEmploye,
    ElementSortie,
    ElementsVariablesPaie,
    EmargementEpi,
    EvaluationEmploye,
    EpiCatalogue,
    FeuilleTemps,
    Habilitation,
    HeuresSupp,
    HoraireTravail,
    IncidentPresence,
    InscriptionFormation,
    LigneRisqueChantier,
    ModeleIntegration,
    NoteDeFrais,
    ObjectifIndividuel,
    OrdreMission,
    OuverturePoste,
    PermisConduire,
    Pointage,
    Poste,
    PresenceChantier,
    PresquAccident,
    PrimeAttribuee,
    Remuneration,
    Sanction,
    SessionFormation,
    SoldeConge,
    TypeAbsence,
    TypePrime,
    VisiteMedicale,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class DepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departement
        fields = ['id', 'nom', 'code', 'actif', 'date_creation']
        read_only_fields = ['date_creation']


class DossierEmployeSerializer(serializers.ModelSerializer):
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    situation_familiale_display = serializers.CharField(
        source='get_situation_familiale_display', read_only=True)
    motif_sortie_display = serializers.CharField(
        source='get_motif_sortie_display', read_only=True)

    class Meta:
        model = DossierEmploye
        fields = [
            'id', 'user', 'matricule', 'nom', 'prenom', 'cin',
            'cnss', 'cimr', 'amo', 'situation_familiale',
            'situation_familiale_display', 'nombre_enfants', 'telephone',
            'email', 'poste', 'poste_ref', 'departement', 'date_embauche',
            'type_contrat',
            'type_contrat_display', 'contrat_date_debut', 'contrat_date_fin',
            'statut', 'statut_display', 'cout_horaire',
            # FG161 — cycle de vie / offboarding.
            'date_sortie', 'motif_sortie', 'motif_sortie_display',
            'rib',
            # FG158 — coordonnées perso étendues + contact d'urgence (internes).
            'adresse_perso', 'telephone_perso', 'email_perso',
            'urgence_nom', 'urgence_lien', 'urgence_telephone',
            'groupe_sanguin',
            # XRH1 — période d'essai.
            'essai_date_fin', 'essai_renouvele',
            # XRH5 — déclaration d'entrée CNSS/AMO (statut posé côté serveur
            # via l'action ``marquer-declare`` ; en écriture directe reste
            # possible pour ``non_requis`` par un admin, mais jamais la date).
            'declaration_entree_statut', 'declaration_entree_date',
            # XRH8 — horaire de travail assigné.
            'horaire',
            'date_creation',
        ]
        read_only_fields = ['date_creation', 'declaration_entree_date']

    def validate_horaire(self, value):
        return _meme_societe(self, value, 'Horaire de travail')

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')

    def validate_poste_ref(self, value):
        return _meme_societe(self, value, 'Poste')


class HoraireTravailSerializer(serializers.ModelSerializer):
    """Gabarit d'horaire de travail (XRH8) — 44 h standard, Ramadan,
    saisonnier. ``date_debut``/``date_fin`` vides = permanent."""
    type_horaire_display = serializers.CharField(
        source='get_type_horaire_display', read_only=True)

    class Meta:
        model = HoraireTravail
        fields = [
            'id', 'nom', 'heures_semaine', 'heures_jour_defaut',
            'type_horaire', 'type_horaire_display',
            'date_debut', 'date_fin', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class DossierActivitySerializer(serializers.ModelSerializer):
    """Entrée de chatter d'un dossier employé (XRH6) — lecture seule (écrite
    uniquement côté serveur par la vue)."""
    auteur_username = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = DossierActivity
        fields = [
            'id', 'employe', 'type', 'field', 'old_value', 'new_value',
            'message', 'auteur', 'auteur_username', 'date_creation',
        ]
        read_only_fields = fields


class RemunerationSerializer(serializers.ModelSerializer):
    """Rémunération de base (FG157). ``employe`` doit appartenir à la société de
    l'utilisateur ; ``company`` est posée côté serveur."""
    periodicite_display = serializers.CharField(
        source='get_periodicite_display', read_only=True)

    class Meta:
        model = Remuneration
        fields = [
            'id', 'employe', 'montant', 'devise', 'periodicite',
            'periodicite_display', 'date_effet', 'motif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class DocumentEmployeSerializer(serializers.ModelSerializer):
    """Document du coffre employé (FG159) — qualifie une ``records.Attachment``.

    Lecture seule sur les métadonnées de la pièce jointe (nom/taille/mime/URL de
    téléchargement même origine) : le FICHIER lui-même reste dans MinIO via
    ``records.Attachment`` — ce sérialiseur n'expose que ce qui décrit le
    document. ``company`` et ``attachment`` sont posés côté serveur (jamais lus
    du corps) : la pièce jointe est créée par la vue à partir du fichier uploadé.
    """
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True)
    filename = serializers.CharField(
        source='attachment.filename', read_only=True)
    size = serializers.IntegerField(
        source='attachment.size', read_only=True)
    mime = serializers.CharField(
        source='attachment.mime', read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentEmploye
        fields = [
            'id', 'employe', 'type_document', 'type_document_display',
            'date_expiration', 'note',
            'filename', 'size', 'mime', 'url',
            'date_creation',
        ]
        read_only_fields = [
            'id', 'type_document_display', 'filename', 'size', 'mime', 'url',
            'date_creation',
        ]

    def get_url(self, obj):
        # Même proxy Django (même origine, authentifié par cookie) que toute
        # autre pièce jointe records — on ne sert jamais l'URL MinIO interne.
        if obj.attachment_id:
            return (f'/api/django/records/attachments/'
                    f'{obj.attachment_id}/download/')
        return None

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class PosteSerializer(serializers.ModelSerializer):
    """Référentiel poste (FG160). ``departement`` doit appartenir à la société."""
    departement_nom = serializers.CharField(
        source='departement.nom', read_only=True)

    class Meta:
        model = Poste
        fields = [
            'id', 'intitule', 'code', 'departement', 'departement_nom',
            'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')


class ElementSortieSerializer(serializers.ModelSerializer):
    """Élément de checklist d'offboarding (FG161). ``employe`` même société."""
    type_element_display = serializers.CharField(
        source='get_type_element_display', read_only=True)

    class Meta:
        model = ElementSortie
        fields = [
            'id', 'employe', 'libelle', 'type_element', 'type_element_display',
            'recupere', 'date_recuperation', 'note', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class ElementIntegrationSerializer(serializers.ModelSerializer):
    """Ligne gabarit d'un modèle d'intégration (XRH4)."""

    class Meta:
        model = ElementIntegration
        fields = ['id', 'modele', 'libelle', 'ordre', 'date_creation']
        read_only_fields = ['date_creation']

    def validate_modele(self, value):
        return _meme_societe(self, value, "Modèle d'intégration")


class ModeleIntegrationSerializer(serializers.ModelSerializer):
    """Gabarit de checklist d'intégration (XRH4), avec ses lignes imbriquées
    en lecture (``elements``)."""
    elements = ElementIntegrationSerializer(many=True, read_only=True)

    class Meta:
        model = ModeleIntegration
        fields = [
            'id', 'nom', 'poste_ref', 'departement', 'actif', 'elements',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_poste_ref(self, value):
        return _meme_societe(self, value, 'Poste')

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')


class ElementIntegrationEmployeSerializer(serializers.ModelSerializer):
    """Ligne de checklist d'intégration d'un employé (XRH4)."""

    class Meta:
        model = ElementIntegrationEmploye
        fields = [
            'id', 'employe', 'libelle', 'ordre', 'fait', 'fait_par', 'date',
            'date_creation',
        ]
        read_only_fields = ['fait_par', 'date', 'date_creation']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class TypeAbsenceSerializer(serializers.ModelSerializer):
    """Typologie d'absence (FG164) — règle de décompte par catégorie."""

    class Meta:
        model = TypeAbsence
        fields = [
            'id', 'code', 'libelle', 'decompte_jours_ouvres', 'deduit_solde',
            'remunere', 'actif', 'jours_legaux',
            'jours_max_sans_justificatif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class SoldeCongeSerializer(serializers.ModelSerializer):
    """Solde de congés annuel (FG162). ``disponible`` est calculé (lecture)."""
    disponible = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = SoldeConge
        fields = [
            'id', 'employe', 'annee', 'acquis', 'report', 'pris', 'disponible',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class DemandeCongeSerializer(serializers.ModelSerializer):
    """Demande de congés (FG163). ``employe`` et ``type_absence`` doivent
    appartenir à la société ; ``jours`` et le workflow de décision sont posés
    côté serveur (jamais lus du corps)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_absence_code = serializers.CharField(
        source='type_absence.code', read_only=True)

    class Meta:
        model = DemandeConge
        fields = [
            'id', 'employe', 'type_absence', 'type_absence_code',
            'date_debut', 'date_fin', 'jours',
            'demi_journee_debut', 'demi_journee_fin', 'justificatif',
            'motif',
            'statut', 'statut_display',
            'decide_par', 'date_decision', 'motif_refus', 'date_creation',
        ]
        # ``jours`` et tout l'état de décision sont calculés/posés côté serveur.
        read_only_fields = [
            'jours', 'statut', 'decide_par', 'date_decision', 'motif_refus',
            'date_creation',
        ]

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_type_absence(self, value):
        return _meme_societe(self, value, "Type d'absence")

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                {'date_fin': 'La date de fin précède la date de début.'})
        return attrs


class FeuilleTempsSerializer(serializers.ModelSerializer):
    """Feuille de temps par chantier (FG167) — heures imputées job-costing.

    ``company`` est posée côté serveur (jamais lue du corps). ``employe`` doit
    appartenir à la société de l'utilisateur. ``taux_horaire`` est un champ
    INTERNE : visible en API RH mais ne quitte jamais une sortie client. Le
    ``cout_calcule`` (heures × taux) est calculé en lecture, non stocké.
    """
    employe_nom = serializers.SerializerMethodField()
    cout_calcule = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = FeuilleTemps
        fields = [
            'id', 'employe', 'employe_nom',
            'installation_id', 'intervention_id',
            'date', 'heures', 'taux_horaire', 'cout_calcule',
            'description', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification', 'cout_calcule']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_heures(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'Les heures imputées doivent être positives.')
        return value


class HeuresSuppSerializer(serializers.ModelSerializer):
    """Heures supplémentaires majorées (FG168) — entrée de paie.

    Le client saisit ``employe``, ``date``, ``heures_travaillees``,
    ``heures_nuit``, ``seuil_journalier`` et ``jour_repos_ferie`` ; les
    décomptes répartis (``heures_normales``, ``hs_25``, ``hs_50``, ``hs_100``)
    ainsi que le ``taux_horaire`` interne et le ``montant_majore`` sont CALCULÉS
    et posés côté serveur (lecture seule). ``company`` est posée côté serveur ;
    ``employe`` doit appartenir à la société de l'utilisateur.
    """
    employe_nom = serializers.SerializerMethodField()
    total_hs = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True)

    class Meta:
        model = HeuresSupp
        fields = [
            'id', 'employe', 'employe_nom', 'date',
            'heures_travaillees', 'heures_nuit', 'seuil_journalier',
            'jour_repos_ferie',
            'heures_normales', 'hs_25', 'hs_50', 'hs_100', 'total_hs',
            'taux_horaire', 'montant_majore',
            'note', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'heures_normales', 'hs_25', 'hs_50', 'hs_100', 'total_hs',
            'taux_horaire', 'montant_majore',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_heures_travaillees(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Les heures travaillées ne peuvent pas être négatives.')
        return value

    def validate_heures_nuit(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Les heures de nuit ne peuvent pas être négatives.')
        return value


class PointageSerializer(serializers.ModelSerializer):
    """Pointage (FG166) — arrivée/départ avec géoloc.

    ``company`` et ``heure_arrivee`` (pour le type ARRIVEE) sont posés côté
    serveur. ``employe`` doit appartenir à la société de l'utilisateur.
    ``duree_minutes`` est calculée (lecture seule). ``heure_depart`` est
    facultative à la création ; elle est renseignée via l'action ``depart``
    ou par PATCH.
    """
    type_pointage_display = serializers.CharField(
        source='get_type_pointage_display', read_only=True)
    duree_minutes = serializers.IntegerField(read_only=True)
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = Pointage
        fields = [
            'id', 'employe', 'employe_nom',
            'type_pointage', 'type_pointage_display',
            'heure_arrivee', 'heure_depart',
            'arrivee_gps_lat', 'arrivee_gps_lng',
            'depart_gps_lat', 'depart_gps_lng',
            'duree_minutes', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification', 'duree_minutes']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        arrivee = attrs.get('heure_arrivee')
        depart = attrs.get('heure_depart')
        if arrivee and depart and depart < arrivee:
            raise serializers.ValidationError(
                {'heure_depart':
                 "L'heure de départ précède l'heure d'arrivée."})
        return attrs


class AffectationRosterSerializer(serializers.ModelSerializer):
    """Affectation roster (FG169) — affectation hebdo technicien↔équipe/camionnette.

    Le client saisit ``employe``, ``equipe``, ``date``, ``creneau`` et,
    facultativement, ``vehicule_id`` et ``note``. ``company`` est posée côté
    serveur (jamais lue du corps) ; ``employe`` doit appartenir à la société.
    ``semaine_du`` (lundi de la semaine) et ``conflit_conge`` (congé validé
    couvrant le jour) sont CALCULÉS et posés côté serveur — lecture seule.
    """
    creneau_display = serializers.CharField(
        source='get_creneau_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = AffectationRoster
        fields = [
            'id', 'employe', 'employe_nom', 'equipe', 'vehicule_id',
            'date', 'semaine_du', 'creneau', 'creneau_display',
            'conflit_conge', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'semaine_du', 'conflit_conge',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_equipe(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("L'équipe est obligatoire.")
        return value

    def validate(self, attrs):
        # Unicité (société, employé, jour) : ``company`` n'est pas un champ du
        # sérialiseur (posée côté serveur), donc DRF ne génère pas le validateur
        # automatiquement — on le vérifie ici contre la société de l'utilisateur.
        request = self.context.get('request')
        employe = attrs.get('employe') or getattr(self.instance, 'employe', None)
        jour = attrs.get('date') or getattr(self.instance, 'date', None)
        if request is not None and employe is not None and jour is not None:
            qs = AffectationRoster.objects.filter(
                company_id=request.user.company_id,
                employe=employe, date=jour)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'date': "Une affectation existe déjà pour cet employé "
                             "ce jour-là."})
        return attrs


class PresenceChantierSerializer(serializers.ModelSerializer):
    """Présence chantier / émargement (FG170) — qui était sur quel chantier.

    Le client saisit ``employe``, ``installation_id``, ``date``, ``statut`` et,
    facultativement, ``heure_arrivee``/``heure_depart``/``note``. ``company`` est
    posée côté serveur (jamais lue du corps) ; ``employe`` doit appartenir à la
    société. L'émargement (``emarge``/``emarge_le``/``emarge_par``) est posé côté
    serveur via l'action dédiée — lecture seule ici. Unicité (société, employé,
    installation, jour).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = PresenceChantier
        fields = [
            'id', 'employe', 'employe_nom', 'installation_id', 'date',
            'statut', 'statut_display',
            'heure_arrivee', 'heure_depart',
            'emarge', 'emarge_le', 'emarge_par', 'note',
            # XRH12 — géofence (posés côté serveur via l'action ``emarger``).
            'gps_lat', 'gps_lng', 'hors_zone',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'emarge', 'emarge_le', 'emarge_par',
            'gps_lat', 'gps_lng', 'hors_zone',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        # Garde-fou cohérence horaire.
        arrivee = attrs.get('heure_arrivee')
        depart = attrs.get('heure_depart')
        if arrivee and depart and depart < arrivee:
            raise serializers.ValidationError(
                {'heure_depart':
                 "L'heure de départ précède l'heure d'arrivée."})
        # Unicité (société, employé, installation, jour) — ``company`` posée côté
        # serveur n'est pas un champ du sérialiseur, donc on la vérifie ici.
        request = self.context.get('request')
        employe = attrs.get('employe') or getattr(self.instance, 'employe', None)
        installation_id = attrs.get('installation_id') \
            or getattr(self.instance, 'installation_id', None)
        jour = attrs.get('date') or getattr(self.instance, 'date', None)
        if request is not None and employe is not None \
                and installation_id is not None and jour is not None:
            qs = PresenceChantier.objects.filter(
                company_id=request.user.company_id, employe=employe,
                installation_id=installation_id, date=jour)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'date': "Une présence existe déjà pour cet employé sur "
                             "ce chantier ce jour-là."})
        return attrs


class IncidentPresenceSerializer(serializers.ModelSerializer):
    """Incident de présence (FG171) — retard / absence injustifiée + comptage.

    Le client saisit ``employe``, ``type_incident``, ``date``,
    ``minutes_retard`` (retard/départ anticipé) et ``motif``/``note``.
    ``company`` est posée côté serveur (jamais lue du corps) ; ``employe`` doit
    appartenir à la société. La régularisation (``justifie``/``justifie_par``/
    ``justifie_le``) est posée côté serveur via l'action dédiée — lecture seule.
    """
    type_incident_display = serializers.CharField(
        source='get_type_incident_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = IncidentPresence
        fields = [
            'id', 'employe', 'employe_nom',
            'type_incident', 'type_incident_display', 'date',
            'minutes_retard', 'justifie', 'motif',
            'justifie_par', 'justifie_le', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'justifie', 'justifie_par', 'justifie_le',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class CompetenceSerializer(serializers.ModelSerializer):
    """Référentiel de compétences (FG172) — catalogue par société.

    ``company`` est posée côté serveur (jamais lue du corps). Le couple
    (société, ``code``) est unique : un même code ne peut exister deux fois dans
    la même société.
    """
    domaine_display = serializers.CharField(
        source='get_domaine_display', read_only=True)

    class Meta:
        model = Competence
        fields = [
            'id', 'code', 'libelle', 'domaine', 'domaine_display',
            'description', 'actif', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_code(self, value):
        # Unicité (société, code) : ``company`` n'est pas un champ du
        # sérialiseur (posée côté serveur), donc on valide ici pour rendre
        # un 400 plutôt que de laisser remonter une IntegrityError 500.
        request = self.context.get('request')
        if request is not None:
            qs = Competence.objects.filter(
                company_id=request.user.company_id, code=value)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Une compétence avec ce code existe déjà.')
        return value


class CompetenceEmployeSerializer(serializers.ModelSerializer):
    """Matrice de compétences — niveau d'un employé sur une compétence (FG172).

    Le client saisit ``employe``, ``competence``, ``niveau`` et ``note``.
    ``company`` est posée côté serveur (jamais lue du corps) ; ``employe`` ET
    ``competence`` doivent appartenir à la société de l'utilisateur. L'évaluation
    (``evalue_par``/``evalue_le``) est posée côté serveur — lecture seule.
    """
    niveau_display = serializers.CharField(
        source='get_niveau_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()
    competence_code = serializers.CharField(
        source='competence.code', read_only=True)
    competence_libelle = serializers.CharField(
        source='competence.libelle', read_only=True)

    class Meta:
        model = CompetenceEmploye
        fields = [
            'id', 'employe', 'employe_nom',
            'competence', 'competence_code', 'competence_libelle',
            'niveau', 'niveau_display', 'note',
            'evalue_par', 'evalue_le',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'evalue_par', 'evalue_le',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_competence(self, value):
        return _meme_societe(self, value, 'Compétence')

    def validate(self, attrs):
        # Unicité (employé, compétence) : un employé n'a qu'une ligne par
        # compétence — on met à jour plutôt que d'empiler.
        employe = attrs.get('employe') \
            or getattr(self.instance, 'employe', None)
        competence = attrs.get('competence') \
            or getattr(self.instance, 'competence', None)
        if employe is not None and competence is not None:
            qs = CompetenceEmploye.objects.filter(
                employe=employe, competence=competence)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Un niveau existe déjà pour cet employé et cette '
                    'compétence.')
        return attrs


class HabilitationSerializer(serializers.ModelSerializer):
    """Habilitation électrique par employé (FG173) — titre + validité/organisme.

    Le client saisit ``employe``, ``type_habilitation``, ``organisme``,
    ``date_obtention``, ``date_validite`` (échéance), ``actif`` et ``note``.
    ``company`` est posée côté serveur (jamais lue du corps) ; ``employe`` doit
    appartenir à la société de l'utilisateur. ``valide`` (actif ET non expiré)
    est CALCULÉ — lecture seule. Une ligne par (employé, titre) : on met à jour
    la validité plutôt que d'empiler.
    """
    type_habilitation_display = serializers.CharField(
        source='get_type_habilitation_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()
    valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = Habilitation
        fields = [
            'id', 'employe', 'employe_nom',
            'type_habilitation', 'type_habilitation_display',
            'organisme', 'date_obtention', 'date_validite',
            'actif', 'valide', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification', 'valide']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        # Cohérence des dates : l'échéance ne précède pas l'obtention.
        obtention = attrs.get('date_obtention') \
            or getattr(self.instance, 'date_obtention', None)
        validite = attrs.get('date_validite') \
            or getattr(self.instance, 'date_validite', None)
        if obtention and validite and validite < obtention:
            raise serializers.ValidationError(
                {'date_validite':
                 "La date de validité précède la date d'obtention."})
        # Unicité (employé, titre) : ``company`` est posée côté serveur et n'est
        # pas un champ du sérialiseur, donc on valide ici pour rendre un 400
        # plutôt que de laisser remonter une IntegrityError 500.
        employe = attrs.get('employe') \
            or getattr(self.instance, 'employe', None)
        type_habil = attrs.get('type_habilitation') \
            or getattr(self.instance, 'type_habilitation', None)
        if employe is not None and type_habil is not None:
            qs = Habilitation.objects.filter(
                employe=employe, type_habilitation=type_habil)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Une habilitation de ce type existe déjà pour cet '
                    'employé.')
        return attrs


class CertificationSerializer(serializers.ModelSerializer):
    """Certification spécifique par employé (FG174) — hauteur/harnais/CACES/SST.

    Le client saisit ``employe``, ``type_certification``, ``organisme``,
    ``date_obtention``, ``date_validite`` (expiration), ``actif`` et ``note``.
    ``company`` est posée côté serveur (jamais lue du corps) ; ``employe`` doit
    appartenir à la société de l'utilisateur. ``valide`` (actif ET non expiré)
    est CALCULÉ — lecture seule. Une ligne par (employé, certification) : on met
    à jour la validité plutôt que d'empiler. Famille DISTINCTE des habilitations
    électriques (FG173).
    """
    type_certification_display = serializers.CharField(
        source='get_type_certification_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()
    valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = Certification
        fields = [
            'id', 'employe', 'employe_nom',
            'type_certification', 'type_certification_display',
            'organisme', 'date_obtention', 'date_validite',
            'actif', 'valide', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification', 'valide']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        # Cohérence des dates : l'expiration ne précède pas l'obtention.
        obtention = attrs.get('date_obtention') \
            or getattr(self.instance, 'date_obtention', None)
        validite = attrs.get('date_validite') \
            or getattr(self.instance, 'date_validite', None)
        if obtention and validite and validite < obtention:
            raise serializers.ValidationError(
                {'date_validite':
                 "La date de validité précède la date d'obtention."})
        # Unicité (employé, certification) : ``company`` est posée côté serveur
        # et n'est pas un champ du sérialiseur, donc on valide ici pour rendre
        # un 400 plutôt que de laisser remonter une IntegrityError 500.
        employe = attrs.get('employe') \
            or getattr(self.instance, 'employe', None)
        type_cert = attrs.get('type_certification') \
            or getattr(self.instance, 'type_certification', None)
        if employe is not None and type_cert is not None:
            qs = Certification.objects.filter(
                employe=employe, type_certification=type_cert)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Une certification de ce type existe déjà pour cet '
                    'employé.')
        return attrs


class VisiteMedicaleSerializer(serializers.ModelSerializer):
    """Visite médicale du travail par employé (FG177) — aptitude + échéance.

    Le client saisit ``employe``, ``date_visite``, ``prochaine_visite``
    (échéance), ``aptitude``, ``medecin``, ``organisme``, ``restrictions``,
    ``actif`` et ``note``. ``company`` est posée côté serveur (jamais lue du
    corps) ; ``employe`` doit appartenir à la société de l'utilisateur.
    ``a_jour`` (active ET prochaine visite non dépassée) est CALCULÉ — lecture
    seule. On garde l'historique des visites (pas d'unicité). Famille DISTINCTE
    des habilitations (FG173) et certifications (FG174).
    """
    aptitude_display = serializers.CharField(
        source='get_aptitude_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()
    a_jour = serializers.BooleanField(read_only=True)

    class Meta:
        model = VisiteMedicale
        fields = [
            'id', 'employe', 'employe_nom',
            'date_visite', 'prochaine_visite',
            'aptitude', 'aptitude_display',
            'medecin', 'organisme', 'restrictions',
            'actif', 'a_jour', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification', 'a_jour']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        # Cohérence des dates : la prochaine visite ne précède pas la visite.
        visite = attrs.get('date_visite') \
            or getattr(self.instance, 'date_visite', None)
        prochaine = attrs.get('prochaine_visite') \
            or getattr(self.instance, 'prochaine_visite', None)
        if visite and prochaine and prochaine < visite:
            raise serializers.ValidationError(
                {'prochaine_visite':
                 'La prochaine visite précède la date de la visite.'})
        return attrs


class EpiCatalogueSerializer(serializers.ModelSerializer):
    """Catalogue des EPI de la société (FG178) — type + désignation.

    Le client saisit ``type_epi``, ``designation`` et ``actif``. ``company`` est
    posée côté serveur (jamais lue du corps). Référentiel des équipements de
    protection ; la dotation nominative est portée par ``DotationEpi``.
    """
    type_epi_display = serializers.CharField(
        source='get_type_epi_display', read_only=True)

    class Meta:
        model = EpiCatalogue
        fields = [
            'id', 'type_epi', 'type_epi_display',
            'designation', 'duree_vie_mois', 'intervalle_controle_mois',
            'actif',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class DotationEpiSerializer(serializers.ModelSerializer):
    """Dotation nominative d'un EPI à un employé (FG178) — taille + date.

    Le client saisit ``employe``, ``epi`` (du catalogue), ``taille``,
    ``date_dotation``, ``date_renouvellement`` (échéance), ``quantite`` et
    ``note``. ``company`` est posée côté serveur (jamais lue du corps) ;
    ``employe`` et ``epi`` doivent appartenir à la société de l'utilisateur.
    Une échéance de renouvellement alimente le moteur d'échéances RH (FG175).
    """
    employe_nom = serializers.SerializerMethodField()
    epi_designation = serializers.CharField(
        source='epi.designation', read_only=True)
    type_epi = serializers.CharField(
        source='epi.type_epi', read_only=True)
    type_epi_display = serializers.CharField(
        source='epi.get_type_epi_display', read_only=True)
    # Échéances de cycle de vie DÉRIVÉES (FG179) : posées côté serveur à la
    # sauvegarde (date_dotation + durées du catalogue) ; jamais saisies.
    perime = serializers.SerializerMethodField()
    a_controler = serializers.SerializerMethodField()

    class Meta:
        model = DotationEpi
        fields = [
            'id', 'employe', 'employe_nom',
            'epi', 'epi_designation', 'type_epi', 'type_epi_display',
            'taille', 'date_dotation', 'date_renouvellement',
            'date_peremption', 'date_prochain_controle',
            'perime', 'a_controler',
            'quantite', 'note',
            'accuse_remise', 'date_accuse',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'date_peremption', 'date_prochain_controle',
            'accuse_remise', 'date_accuse',
            'date_creation', 'date_modification',
        ]

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def get_perime(self, obj):
        return obj.perime()

    def get_a_controler(self, obj):
        return obj.a_controler()

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_epi(self, value):
        return _meme_societe(self, value, 'EPI')

    def validate(self, attrs):
        # Cohérence des dates : le renouvellement ne précède pas la dotation.
        dotation = attrs.get('date_dotation') \
            or getattr(self.instance, 'date_dotation', None)
        renouvellement = attrs.get('date_renouvellement') \
            or getattr(self.instance, 'date_renouvellement', None)
        if dotation and renouvellement and renouvellement < dotation:
            raise serializers.ValidationError(
                {'date_renouvellement':
                 'La date de renouvellement précède la date de dotation.'})
        return attrs


class EmargementEpiSerializer(serializers.ModelSerializer):
    """Émargement de remise d'un EPI (FG180) — accusé signé, LECTURE seule.

    Sérialise la preuve d'un émargement déjà enregistré : nom dactylographié
    (fait foi — loi 53-05), rôle, méthode, date, mention et éléments de preuve
    (IP, user agent). La société, l'utilisateur agissant et les preuves sont
    posés CÔTÉ SERVEUR par le service ``emarger_dotation`` ; ce sérialiseur ne
    sert qu'à renvoyer l'émargement créé / lister l'historique d'une dotation.
    """
    role_signataire_display = serializers.CharField(
        source='get_role_signataire_display', read_only=True)
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)

    class Meta:
        model = EmargementEpi
        fields = [
            'id', 'dotation', 'signataire_nom', 'signataire',
            'role_signataire', 'role_signataire_display',
            'methode', 'methode_display', 'mention',
            'ip_adresse', 'user_agent', 'date_signature',
        ]
        read_only_fields = fields


class EmargerEpiSerializer(serializers.Serializer):
    """Corps de l'action ``emarger`` (FG180) — saisie de l'émargement.

    Le client saisit ``signataire_nom`` (nom dactylographié, requis — loi
    53-05), ``role_signataire`` (optionnel, ``employe`` par défaut), ``methode``
    (optionnel, ``typed`` par défaut) et ``mention`` (optionnelle). La société,
    l'utilisateur agissant et les preuves (IP, user agent) sont posés CÔTÉ
    SERVEUR — jamais lus du corps.
    """
    signataire_nom = serializers.CharField(max_length=255)
    role_signataire = serializers.ChoiceField(
        choices=EmargementEpi.RoleSignataire.choices,
        default=EmargementEpi.RoleSignataire.EMPLOYE)
    methode = serializers.ChoiceField(
        choices=EmargementEpi.Methode.choices,
        default=EmargementEpi.Methode.TYPED)
    mention = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default='')

    def validate_signataire_nom(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le nom du signataire est requis (loi 53-05).')
        return value.strip()


class AccidentTravailSerializer(serializers.ModelSerializer):
    """Accident du travail (FG181) — déclaration HSE + suivi CNSS.

    Le client saisit ``employe`` (le blessé), ``date_accident``, ``lieu``,
    ``gravite`` (léger / grave / mortel), ``description``, ``arret_travail``
    (+ ``nb_jours_arret``), ``photo_key`` (clé MinIO optionnelle), ``declare_cnss``
    (+ ``date_declaration_cnss``) et ``statut``. ``company`` ET ``reference``
    sont posées CÔTÉ SERVEUR (jamais lues du corps) ; ``employe`` doit appartenir
    à la société de l'utilisateur. ``reference`` est en lecture seule (générée
    race-safe à la création).
    """
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = AccidentTravail
        fields = [
            'id', 'reference', 'employe', 'employe_nom',
            'date_accident', 'lieu',
            'gravite', 'gravite_display', 'description',
            'arret_travail', 'nb_jours_arret', 'photo_key',
            'declare_cnss', 'date_declaration_cnss',
            'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate(self, attrs):
        # Cohérence : pas d'arrêt déclaré sans jours, et inversement un nombre
        # de jours implique un arrêt. On corrige le couple plutôt que d'empiler
        # une donnée incohérente (un arrêt à 0 jour ou des jours sans arrêt).
        arret = attrs.get('arret_travail')
        if arret is None:
            arret = getattr(self.instance, 'arret_travail', False)
        jours = attrs.get('nb_jours_arret')
        if jours is None:
            jours = getattr(self.instance, 'nb_jours_arret', 0)
        if not arret and jours:
            raise serializers.ValidationError(
                {'nb_jours_arret':
                 "Un nombre de jours d'arrêt implique un arrêt de travail."})
        return attrs


class PresquAccidentSerializer(serializers.ModelSerializer):
    """Presqu'accident / near-miss (FG182) — saisie rapide terrain.

    Le client saisit l'essentiel : ``date_constat``, ``lieu``, ``chantier_id``
    (référence chaîne optionnelle), ``description``, ``gravite_potentielle``
    (faible / moyenne / élevée), ``mesure_corrective``, ``photo_key`` (clé MinIO
    optionnelle) et ``statut`` (ouvert / traité). ``company``, ``reference`` ET
    ``declare_par`` sont posées CÔTÉ SERVEUR (jamais lues du corps).
    ``reference`` et ``declare_par`` sont en lecture seule (générées /
    renseignées côté serveur à la création).
    """
    gravite_potentielle_display = serializers.CharField(
        source='get_gravite_potentielle_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    declare_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = PresquAccident
        fields = [
            'id', 'reference',
            'date_constat', 'lieu', 'chantier_id',
            'description',
            'gravite_potentielle', 'gravite_potentielle_display',
            'mesure_corrective', 'photo_key',
            'declare_par', 'declare_par_nom',
            'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'declare_par',
            'date_creation', 'date_modification']

    def get_declare_par_nom(self, obj):
        if not obj.declare_par_id:
            return ''
        user = obj.declare_par
        full = user.get_full_name() if hasattr(user, 'get_full_name') else ''
        return full or getattr(user, 'username', '') or ''


class CauserieParticipantSerializer(serializers.ModelSerializer):
    """Participant + émargement d'une causerie sécurité (FG183).

    Le client saisit ``participant`` (un ``DossierEmploye`` de sa société) et,
    en option, ``present``. ``company`` et ``causerie`` sont posées CÔTÉ SERVEUR
    (jamais lues du corps) ; ``emarge`` / ``emarge_le`` sont en lecture seule
    (posées via l'action ``emarger`` de la causerie).
    """
    participant_nom = serializers.SerializerMethodField()

    class Meta:
        model = CauserieParticipant
        fields = [
            'id', 'participant', 'participant_nom',
            'present', 'emarge', 'emarge_le', 'date_creation',
        ]
        read_only_fields = ['emarge', 'emarge_le', 'date_creation']

    def get_participant_nom(self, obj):
        return f'{obj.participant.nom} {obj.participant.prenom}'

    def validate_participant(self, value):
        return _meme_societe(self, value, 'Participant')


class CauserieSecuriteSerializer(serializers.ModelSerializer):
    """Causerie sécurité / toolbox talk (FG183) — le quart d'heure sécurité.

    Le client saisit ``theme``, ``date_causerie``, ``chantier_id`` (référence
    chaîne optionnelle), ``animateur`` (un ``DossierEmploye`` de sa société),
    ``lieu`` et ``notes``, plus une liste imbriquée ``participants`` (chacun avec
    son ``participant``). ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``animateur`` et chaque ``participant`` doivent appartenir à la
    société de l'utilisateur. L'émargement de chaque participant se pose via
    l'action ``emarger`` — il est en lecture seule ici.
    """
    animateur_nom = serializers.SerializerMethodField()
    participants = CauserieParticipantSerializer(many=True, required=False)

    class Meta:
        model = CauserieSecurite
        fields = [
            'id', 'theme', 'date_causerie', 'chantier_id',
            'animateur', 'animateur_nom', 'lieu', 'notes',
            'participants',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_animateur_nom(self, obj):
        if not obj.animateur_id:
            return ''
        return f'{obj.animateur.nom} {obj.animateur.prenom}'

    def validate_animateur(self, value):
        return _meme_societe(self, value, 'Animateur')

    def validate_participants(self, value):
        # Chaque participant doit appartenir à la société de l'utilisateur, et
        # aucun doublon dans la même causerie (contrainte d'unicité au modèle).
        seen = set()
        for item in value:
            emp = item.get('participant')
            _meme_societe(self, emp, 'Participant')
            if emp is not None:
                if emp.id in seen:
                    raise serializers.ValidationError(
                        'Un participant ne peut figurer qu’une fois.')
                seen.add(emp.id)
        return value

    def create(self, validated_data):
        # ``company`` est injectée par le TenantMixin (perform_create) ; on la
        # propage aux participants enfants (jamais lue du corps).
        participants = validated_data.pop('participants', [])
        company = validated_data['company']
        causerie = CauserieSecurite.objects.create(**validated_data)
        for item in participants:
            CauserieParticipant.objects.create(
                company=company, causerie=causerie, **item)
        return causerie

    def update(self, instance, validated_data):
        # Mise à jour des champs de la causerie ; si ``participants`` est fourni,
        # on remplace la liste (les émargements existants sont réinitialisés —
        # une nouvelle liste = une nouvelle feuille d'émargement).
        participants = validated_data.pop('participants', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if participants is not None:
            instance.participants.all().delete()
            for item in participants:
                CauserieParticipant.objects.create(
                    company=instance.company, causerie=instance, **item)
        return instance


class LigneRisqueChantierSerializer(serializers.ModelSerializer):
    """Ligne de risque d'une analyse de risques chantier (FG184).

    Le client saisit ``danger``, ``description``, ``gravite``, ``probabilite``,
    ``niveau`` et ``mesure_prevention``. ``company`` et ``analyse`` sont posées
    CÔTÉ SERVEUR (jamais lues du corps) par le sérialiseur parent.
    """
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    probabilite_display = serializers.CharField(
        source='get_probabilite_display', read_only=True)
    niveau_display = serializers.CharField(
        source='get_niveau_display', read_only=True)

    class Meta:
        model = LigneRisqueChantier
        fields = [
            'id', 'danger', 'description',
            'gravite', 'gravite_display',
            'probabilite', 'probabilite_display',
            'niveau', 'niveau_display',
            'mesure_prevention', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class AnalyseRisquesChantierSerializer(serializers.ModelSerializer):
    """Analyse de risques chantier / plan de prévention (FG184) — AVANT travaux.

    Le client saisit ``chantier_id`` (référence chaîne optionnelle),
    ``date_analyse``, ``redacteur`` (un ``DossierEmploye`` de sa société),
    ``lieu``, ``statut``, ``notes`` et une liste imbriquée ``risques`` (chacun
    avec son danger / gravité / probabilité / niveau / mesure de prévention).
    ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ; ``redacteur``
    doit appartenir à la société de l'utilisateur, et ``company`` est propagée
    aux lignes de risque enfants.
    """
    redacteur_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    risques = LigneRisqueChantierSerializer(many=True, required=False)

    class Meta:
        model = AnalyseRisquesChantier
        fields = [
            'id', 'chantier_id', 'date_analyse',
            'redacteur', 'redacteur_nom',
            'lieu', 'statut', 'statut_display', 'notes',
            'risques',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_redacteur_nom(self, obj):
        if not obj.redacteur_id:
            return ''
        return f'{obj.redacteur.nom} {obj.redacteur.prenom}'

    def validate_redacteur(self, value):
        return _meme_societe(self, value, 'Rédacteur')

    def create(self, validated_data):
        # ``company`` est injectée par le TenantMixin (perform_create) ; on la
        # propage aux lignes de risque enfants (jamais lue du corps).
        risques = validated_data.pop('risques', [])
        company = validated_data['company']
        analyse = AnalyseRisquesChantier.objects.create(**validated_data)
        for item in risques:
            LigneRisqueChantier.objects.create(
                company=company, analyse=analyse, **item)
        return analyse

    def update(self, instance, validated_data):
        # Mise à jour des champs de l'analyse ; si ``risques`` est fourni, on
        # remplace la liste (une nouvelle analyse de risques = une nouvelle
        # liste).
        risques = validated_data.pop('risques', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if risques is not None:
            instance.risques.all().delete()
            for item in risques:
                LigneRisqueChantier.objects.create(
                    company=instance.company, analyse=instance, **item)
        return instance


class InscriptionFormationSerializer(serializers.ModelSerializer):
    """Inscription d'un employé à une session de formation (FG187).

    Le client saisit ``participant`` (un ``DossierEmploye`` de sa société),
    ``present``, ``resultat`` et ``note``. ``company`` et ``session`` sont
    posées CÔTÉ SERVEUR (jamais lues du corps) par le sérialiseur parent.
    """
    participant_nom = serializers.SerializerMethodField()
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)

    class Meta:
        model = InscriptionFormation
        fields = [
            'id', 'participant', 'participant_nom',
            'present', 'resultat', 'resultat_display', 'note',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_participant_nom(self, obj):
        if not obj.participant_id:
            return ''
        return f'{obj.participant.nom} {obj.participant.prenom}'

    def validate_participant(self, value):
        return _meme_societe(self, value, 'Participant')


class SessionFormationSerializer(serializers.ModelSerializer):
    """Session de formation (FG187) — gestion de la formation des équipes.

    Le client saisit ``intitule``, ``type`` (interne / externe),
    ``organisme``, ``date_debut`` / ``date_fin``, ``lieu``, ``cout``,
    ``competence_visee`` (une ``Competence`` de sa société), ``statut``,
    ``notes`` et une liste imbriquée ``inscriptions`` (chacune avec son
    participant / présence / résultat). ``company`` est posée CÔTÉ SERVEUR
    (jamais lue du corps) ; ``competence_visee`` et chaque ``participant``
    doivent appartenir à la société de l'utilisateur, et ``company`` est
    propagée aux inscriptions enfants.
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    competence_visee_libelle = serializers.SerializerMethodField()
    inscriptions = InscriptionFormationSerializer(many=True, required=False)

    class Meta:
        model = SessionFormation
        fields = [
            'id', 'intitule', 'type', 'type_display',
            'organisme', 'date_debut', 'date_fin', 'lieu', 'cout',
            'competence_visee', 'competence_visee_libelle',
            'statut', 'statut_display', 'notes',
            'inscriptions',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_competence_visee_libelle(self, obj):
        if not obj.competence_visee_id:
            return ''
        return obj.competence_visee.libelle

    def validate_competence_visee(self, value):
        return _meme_societe(self, value, 'Compétence visée')

    def create(self, validated_data):
        # ``company`` est injectée par le TenantMixin (perform_create) ; on la
        # propage aux inscriptions enfants (jamais lue du corps).
        inscriptions = validated_data.pop('inscriptions', [])
        company = validated_data['company']
        session = SessionFormation.objects.create(**validated_data)
        for item in inscriptions:
            InscriptionFormation.objects.create(
                company=company, session=session, **item)
        return session

    def update(self, instance, validated_data):
        # Mise à jour des champs de la session ; si ``inscriptions`` est
        # fourni, on remplace la liste.
        inscriptions = validated_data.pop('inscriptions', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if inscriptions is not None:
            instance.inscriptions.all().delete()
            for item in inscriptions:
                InscriptionFormation.objects.create(
                    company=instance.company, session=instance, **item)
        return instance


class BesoinFormationSerializer(serializers.ModelSerializer):
    """Besoin de formation (FG188) — plan de formation par employé.

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``theme``, ``priorite``, ``echeance``, ``obligation_reglementaire`` +
    ``type_obligation`` (OFPPT / CSF), ``statut``, une ``session_liee``
    (``SessionFormation`` de sa société) et des ``notes``. ``company`` est posée
    CÔTÉ SERVEUR (jamais lue du corps) ; ``employe`` et ``session_liee`` doivent
    appartenir à la société de l'utilisateur.
    """
    employe_nom = serializers.SerializerMethodField()
    priorite_display = serializers.CharField(
        source='get_priorite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_obligation_display = serializers.CharField(
        source='get_type_obligation_display', read_only=True)
    session_liee_intitule = serializers.SerializerMethodField()

    class Meta:
        model = BesoinFormation
        fields = [
            'id', 'employe', 'employe_nom', 'theme',
            'priorite', 'priorite_display',
            'echeance', 'obligation_reglementaire',
            'type_obligation', 'type_obligation_display',
            'statut', 'statut_display',
            'session_liee', 'session_liee_intitule',
            'notes', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def get_session_liee_intitule(self, obj):
        if not obj.session_liee_id:
            return ''
        return obj.session_liee.intitule

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_session_liee(self, value):
        return _meme_societe(self, value, 'Session liée')


class CandidatureSerializer(serializers.ModelSerializer):
    """Candidature à une ouverture de poste (FG189) — ATS-lite.

    Le client saisit ``ouverture`` (une ``OuverturePoste`` de sa société),
    ``nom``, ``email``, ``telephone``, ``cv_fichier``, ``source``, ``note`` et
    l'``etape`` du pipeline. ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``ouverture`` doit appartenir à la société de l'utilisateur.
    ``employe_cree`` est en lecture seule (posé par le service ``embaucher``).
    """
    etape_display = serializers.CharField(
        source='get_etape_display', read_only=True)
    ouverture_intitule = serializers.SerializerMethodField()
    employe_cree_nom = serializers.SerializerMethodField()

    class Meta:
        model = Candidature
        fields = [
            'id', 'ouverture', 'ouverture_intitule',
            'nom', 'email', 'telephone', 'cv_fichier', 'source', 'note',
            'etape', 'etape_display',
            'employe_cree', 'employe_cree_nom',
            # XRH19 (opt-out email auto), XRH21 (vivier / talent pool).
            'emails_auto', 'vivier', 'tags_vivier', 'vivier_origine',
            'date_candidature', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'employe_cree', 'vivier_origine',
            'date_creation', 'date_modification']

    def get_ouverture_intitule(self, obj):
        if not obj.ouverture_id:
            return ''
        return obj.ouverture.intitule

    def get_employe_cree_nom(self, obj):
        if not obj.employe_cree_id:
            return ''
        return f'{obj.employe_cree.nom} {obj.employe_cree.prenom}'

    def validate_ouverture(self, value):
        return _meme_societe(self, value, 'Ouverture')


class OuverturePosteSerializer(serializers.ModelSerializer):
    """Ouverture de poste / poste ouvert (FG189) — ATS-lite.

    Le client saisit ``intitule``, un ``poste_ref`` (référentiel ``rh.Poste``
    de sa société) et un ``departement`` optionnels, ``description``,
    ``nombre_postes``, ``statut``, ``date_ouverture`` / ``date_cible``. La liste
    imbriquée ``candidatures`` est en LECTURE SEULE (gérée via l'endpoint
    dédié). ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``poste_ref`` et ``departement`` doivent appartenir à la même société.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    poste_ref_intitule = serializers.SerializerMethodField()
    departement_nom = serializers.SerializerMethodField()
    candidatures = CandidatureSerializer(many=True, read_only=True)

    class Meta:
        model = OuverturePoste
        fields = [
            'id', 'intitule',
            'poste_ref', 'poste_ref_intitule',
            'departement', 'departement_nom',
            'description', 'nombre_postes',
            'statut', 'statut_display',
            'date_ouverture', 'date_cible',
            'candidatures',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_poste_ref_intitule(self, obj):
        if not obj.poste_ref_id:
            return ''
        return obj.poste_ref.intitule

    def get_departement_nom(self, obj):
        if not obj.departement_id:
            return ''
        return obj.departement.nom

    def validate_poste_ref(self, value):
        return _meme_societe(self, value, 'Poste')

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')


class EmbaucherSerializer(serializers.Serializer):
    """Entrée de l'action ``embaucher`` d'une candidature (FG189).

    Tous les champs sont optionnels : ``matricule`` (sinon dérivé ``CAND-<id>``)
    et quelques champs de dossier renseignables à l'embauche.
    """
    matricule = serializers.CharField(
        max_length=30, required=False, allow_blank=True)
    type_contrat = serializers.ChoiceField(
        choices=DossierEmploye.TypeContrat.choices, required=False)
    date_embauche = serializers.DateField(required=False)
    poste = serializers.CharField(
        max_length=120, required=False, allow_blank=True)


class ObjectifIndividuelSerializer(serializers.ModelSerializer):
    """Objectif individuel d'un entretien d'évaluation (FG190).

    Le client saisit ``libelle``, ``ponderation``, ``cible``, ``atteinte`` et
    ``note``. ``company`` et ``evaluation`` sont posées CÔTÉ SERVEUR (jamais
    lues du corps) par le sérialiseur parent.
    """

    class Meta:
        model = ObjectifIndividuel
        fields = [
            'id', 'libelle', 'ponderation', 'cible', 'atteinte', 'note',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class EvaluationEmployeSerializer(serializers.ModelSerializer):
    """Entretien annuel d'évaluation d'un collaborateur (FG190).

    Le client saisit ``campagne`` (une ``CampagneEvaluation`` de sa société),
    ``employe`` et ``evaluateur`` (des ``DossierEmploye`` de sa société),
    ``date_entretien``, ``note_globale``, ``synthese``, ``statut`` et une liste
    imbriquée ``objectifs``. ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``campagne`` / ``employe`` / ``evaluateur`` doivent appartenir à
    la société de l'utilisateur, et ``company`` est propagée aux objectifs
    enfants.
    """
    employe_nom = serializers.SerializerMethodField()
    evaluateur_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    objectifs = ObjectifIndividuelSerializer(many=True, required=False)

    class Meta:
        model = EvaluationEmploye
        fields = [
            'id', 'campagne', 'employe', 'employe_nom',
            'evaluateur', 'evaluateur_nom',
            'date_entretien', 'note_globale', 'synthese',
            'statut', 'statut_display',
            'objectifs',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def get_evaluateur_nom(self, obj):
        if not obj.evaluateur_id:
            return ''
        return f'{obj.evaluateur.nom} {obj.evaluateur.prenom}'

    def validate_campagne(self, value):
        return _meme_societe(self, value, 'Campagne')

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_evaluateur(self, value):
        return _meme_societe(self, value, 'Évaluateur')

    def create(self, validated_data):
        # ``company`` est injectée par le TenantMixin (perform_create) ; on la
        # propage aux objectifs enfants (jamais lue du corps).
        objectifs = validated_data.pop('objectifs', [])
        company = validated_data['company']
        evaluation = EvaluationEmploye.objects.create(**validated_data)
        for item in objectifs:
            ObjectifIndividuel.objects.create(
                company=company, evaluation=evaluation, **item)
        return evaluation

    def update(self, instance, validated_data):
        # Mise à jour des champs de l'entretien ; si ``objectifs`` est fourni,
        # on remplace la liste.
        objectifs = validated_data.pop('objectifs', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if objectifs is not None:
            instance.objectifs.all().delete()
            for item in objectifs:
                ObjectifIndividuel.objects.create(
                    company=instance.company, evaluation=instance, **item)
        return instance


class CampagneEvaluationSerializer(serializers.ModelSerializer):
    """Campagne d'appréciation annuelle (FG190) — entretiens & évaluations.

    Le client saisit ``intitule``, ``annee``, ``periode``, ``date_debut`` /
    ``date_fin``, ``statut`` et ``description``. La liste imbriquée
    ``evaluations`` est en LECTURE SEULE ici : les entretiens individuels se
    créent/modifient via leur propre endpoint. ``company`` est posée CÔTÉ
    SERVEUR (jamais lue du corps).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    evaluations = EvaluationEmployeSerializer(
        many=True, read_only=True)

    class Meta:
        model = CampagneEvaluation
        fields = [
            'id', 'intitule', 'annee', 'periode',
            'date_debut', 'date_fin',
            'statut', 'statut_display', 'description',
            'evaluations',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class SanctionSerializer(serializers.ModelSerializer):
    """Sanction disciplinaire d'un collaborateur (FG191).

    Le client saisit ``employe`` et ``auteur`` (des ``DossierEmploye`` de sa
    société), ``type_sanction``, ``date_faits``, ``date_notification``,
    ``duree_jours``, ``motif`` et ``statut``. ``company`` est posée CÔTÉ
    SERVEUR (jamais lue du corps) ; ``employe`` / ``auteur`` doivent appartenir
    à la société de l'utilisateur.
    """
    employe_nom = serializers.SerializerMethodField()
    type_sanction_display = serializers.CharField(
        source='get_type_sanction_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Sanction
        fields = [
            'id', 'employe', 'employe_nom', 'auteur',
            'type_sanction', 'type_sanction_display',
            'date_faits', 'date_notification', 'duree_jours',
            'motif', 'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_auteur(self, value):
        return _meme_societe(self, value, 'Auteur')


class ElementsVariablesPaieSerializer(serializers.ModelSerializer):
    """Bordereau mensuel d'éléments variables de paie (FG192).

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``annee``, ``mois``, les quantités (``heures_normales``, ``heures_supp``,
    ``jours_absence``, ``jours_conges``), les montants (``primes``,
    ``retenues``), un ``commentaire`` et le ``statut``. ``company`` et
    ``date_export`` sont posées CÔTÉ SERVEUR (jamais lues du corps).
    """
    employe_nom = serializers.SerializerMethodField()
    employe_matricule = serializers.CharField(
        source='employe.matricule', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ElementsVariablesPaie
        fields = [
            'id', 'employe', 'employe_nom', 'employe_matricule',
            'annee', 'mois',
            'heures_normales', 'heures_supp',
            'jours_absence', 'jours_conges',
            'primes', 'retenues', 'commentaire',
            'statut', 'statut_display', 'date_export',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_export', 'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_mois(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError(
                'Le mois doit être compris entre 1 et 12.')
        return value


class OrdreMissionSerializer(serializers.ModelSerializer):
    """Ordre de mission / déplacement chantier (FG194).

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``destination``, ``motif``, ``date_depart`` / ``date_retour``,
    ``moyen_transport``, ``vehicule_id``, ``per_diem`` et ``statut``.
    ``company`` et ``reference`` sont posées CÔTÉ SERVEUR (jamais lues du
    corps) ; ``employe`` doit appartenir à la société de l'utilisateur.
    """
    employe_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = OrdreMission
        fields = [
            'id', 'reference', 'employe', 'employe_nom',
            'destination', 'motif',
            'date_depart', 'date_retour', 'moyen_transport',
            'vehicule_id', 'per_diem', 'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['reference', 'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class AvanceSalaireSerializer(serializers.ModelSerializer):
    """Avance sur salaire (FG195) — demande/validation/déduction.

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``montant``, ``date_demande``, ``motif``, ``annee_deduction`` /
    ``mois_deduction`` (par défaut le mois suivant la demande, posé côté
    serveur si absent). ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``employe`` / ``valideur`` doivent appartenir à la société de
    l'utilisateur. ``statut`` et ``valideur`` évoluent via les actions dédiées.
    """
    employe_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AvanceSalaire
        fields = [
            'id', 'employe', 'employe_nom', 'valideur',
            'montant', 'date_demande', 'motif',
            'annee_deduction', 'mois_deduction',
            'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'valideur', 'statut', 'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_mois_deduction(self, value):
        if value is not None and not 1 <= value <= 12:
            raise serializers.ValidationError(
                'Le mois doit être compris entre 1 et 12.')
        return value


class BulletinPaieSerializer(serializers.ModelSerializer):
    """Bulletin de paie déposé en lecture seule (FG196).

    Lecture seule sur les métadonnées de la pièce jointe (nom/taille/mime/URL
    de téléchargement même origine) ; le FICHIER reste dans MinIO via
    ``records.Attachment``. Le client (vue) saisit ``employe``, ``annee``,
    ``mois``, ``note`` + le fichier en multipart ; ``company`` et
    ``attachment`` sont posés CÔTÉ SERVEUR (jamais lus du corps).
    """
    employe_nom = serializers.SerializerMethodField()
    filename = serializers.CharField(
        source='attachment.filename', read_only=True)
    size = serializers.IntegerField(
        source='attachment.size', read_only=True)
    mime = serializers.CharField(
        source='attachment.mime', read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = BulletinPaie
        fields = [
            'id', 'employe', 'employe_nom', 'annee', 'mois', 'note',
            'filename', 'size', 'mime', 'url', 'date_creation',
        ]
        read_only_fields = [
            'id', 'employe_nom', 'filename', 'size', 'mime', 'url',
            'date_creation',
        ]

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def get_url(self, obj):
        if obj.attachment_id:
            return (f'/api/django/records/attachments/'
                    f'{obj.attachment_id}/download/')
        return None

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_mois(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError(
                'Le mois doit être compris entre 1 et 12.')
        return value


class PermisConduireSerializer(serializers.ModelSerializer):
    """Permis de conduire & habilitation à conduire (FG197).

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``categorie``, ``numero``, ``date_delivrance``, ``date_expiration``,
    ``habilitation_conduite`` et ``note``. ``company`` est posée CÔTÉ SERVEUR
    (jamais lue du corps) ; ``employe`` doit appartenir à la société de
    l'utilisateur. Le couple (employe, categorie) est unique.
    """
    employe_nom = serializers.SerializerMethodField()
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    valide = serializers.SerializerMethodField()

    class Meta:
        model = PermisConduire
        fields = [
            'id', 'employe', 'employe_nom',
            'categorie', 'categorie_display', 'numero',
            'date_delivrance', 'date_expiration',
            'habilitation_conduite', 'valide', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'employe_nom', 'categorie_display', 'valide',
            'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def get_valide(self, obj):
        from django.utils import timezone
        if obj.date_expiration is None:
            return True
        return obj.date_expiration >= timezone.localdate()

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')


class AffectationVehiculeSerializer(serializers.ModelSerializer):
    """Affectation conducteur ↔ véhicule (FG198).

    Le client saisit ``employe`` (un ``DossierEmploye`` de sa société),
    ``vehicule_id`` (ID d'un ``flotte.Vehicule``), ``date_debut`` /
    ``date_fin``, ``statut`` et ``note``. ``company`` et ``permis_verifie``
    sont posées CÔTÉ SERVEUR (jamais lues du corps) ; ``employe`` doit
    appartenir à la société de l'utilisateur. La GARDE PERMIS (FG198) est
    appliquée côté serveur par la vue : pas de permis valide → 400.
    """
    employe_nom = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AffectationVehicule
        fields = [
            'id', 'employe', 'employe_nom', 'vehicule_id',
            'date_debut', 'date_fin', 'statut', 'statut_display',
            'permis_verifie', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'employe_nom', 'permis_verifie',
            'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Conducteur')


class NoteDeFraisSerializer(serializers.ModelSerializer):
    """Note de frais (FG199) — déclaration de frais par le collaborateur.

    Le client saisit ``categorie``, ``montant``, ``date_frais`` et ``libelle``.
    ``company``, ``employe`` et ``statut`` sont posés CÔTÉ SERVEUR : la note est
    rattachée au dossier du compte appelant par la vue self-service ; le statut
    suit le workflow d'approbation (soumise → approuvée → remboursée/refusée).
    """
    employe_nom = serializers.SerializerMethodField()
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = NoteDeFrais
        fields = [
            'id', 'employe', 'employe_nom',
            'categorie', 'categorie_display',
            'montant', 'date_frais', 'libelle',
            'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'employe', 'employe_nom', 'statut',
            'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'


class DemandeRHSerializer(serializers.ModelSerializer):
    """Demande RH self-service (XRH9) — guichet d'attestations à la demande.

    ``employe``, ``company`` et ``statut`` sont posés CÔTÉ SERVEUR par la vue
    self-service. ``attachment_url`` expose le lien de téléchargement du PDF
    une fois la demande traitée (vide sinon).
    """
    employe_nom = serializers.SerializerMethodField()
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    attachment_id = serializers.IntegerField(
        source='attachment.id', read_only=True, default=None)

    class Meta:
        model = DemandeRH
        fields = [
            'id', 'employe', 'employe_nom',
            'type', 'type_display', 'message',
            'statut', 'statut_display', 'motif_refus',
            'attachment_id', 'traite_par', 'traite_le',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'employe', 'employe_nom', 'statut', 'motif_refus',
            'attachment_id', 'traite_par', 'traite_le',
            'date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'


class CorrectionPointageSerializer(serializers.ModelSerializer):
    """Ligne d'audit immuable d'une correction de pointage (XRH11).

    Lecture seule — AUCUNE route update/delete n'existe pour ce modèle.
    """
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = CorrectionPointage
        fields = [
            'id', 'pointage', 'champ', 'ancienne_valeur', 'nouvelle_valeur',
            'motif', 'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', '') if obj.auteur_id else ''


class PromesseEmbaucheSerializer(serializers.ModelSerializer):
    """Promesse d'embauche (XRH20). ``company`` posée côté serveur ;
    ``salaire_propose`` gaté ``salaires_voir`` côté vue (le champ existe ici
    pour l'écran interne RH — le lien public candidat utilise sa propre vue
    dédiée)."""
    candidature_nom = serializers.CharField(
        source='candidature.nom', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PromesseEmbauche
        fields = [
            'id', 'candidature', 'candidature_nom', 'poste_propose',
            'type_contrat', 'date_debut_proposee', 'salaire_propose',
            'statut', 'statut_display', 'token', 'expires_at',
            'signataire_nom', 'date_signature', 'date_creation',
        ]
        read_only_fields = [
            'statut', 'token', 'signataire_nom', 'date_signature',
            'date_creation']


class GabaritEmailRecrutementSerializer(serializers.ModelSerializer):
    """Gabarit d'email automatique par étape (XRH19). ``company`` posée côté
    serveur."""
    etape_display = serializers.CharField(
        source='get_etape_display', read_only=True)

    class Meta:
        model = GabaritEmailRecrutement
        fields = [
            'id', 'etape', 'etape_display', 'objet', 'corps', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class CandidatureActivitySerializer(serializers.ModelSerializer):
    """Chatter d'une candidature (XRH18) — lecture seule côté client."""
    auteur_nom = serializers.SerializerMethodField()
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)

    class Meta:
        model = CandidatureActivity
        fields = [
            'id', 'candidature', 'type', 'type_display', 'field',
            'old_value', 'new_value', 'message', 'auteur', 'auteur_nom',
            'date_creation',
        ]
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', '') if obj.auteur_id else ''


class NoteEntretienSerializer(serializers.ModelSerializer):
    """Note d'entretien (XRH17) — une par évaluateur. ``evaluateur`` et
    ``company`` posés côté serveur."""
    evaluateur_nom = serializers.SerializerMethodField()
    moyenne_criteres = serializers.FloatField(read_only=True)

    class Meta:
        model = NoteEntretien
        fields = [
            'id', 'entretien', 'evaluateur', 'evaluateur_nom',
            'notes_criteres', 'commentaire', 'avis', 'moyenne_criteres',
            'date_creation',
        ]
        read_only_fields = ['evaluateur', 'evaluateur_nom', 'date_creation']

    def get_evaluateur_nom(self, obj):
        return getattr(obj.evaluateur, 'username', '')


class EntretienRecrutementSerializer(serializers.ModelSerializer):
    """Entretien de recrutement (XRH17). ``company`` posée côté serveur ;
    ``candidature`` doit appartenir à la société."""
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    notes = NoteEntretienSerializer(many=True, read_only=True)

    class Meta:
        model = EntretienRecrutement
        fields = [
            'id', 'candidature', 'date_heure', 'type', 'type_display',
            'evaluateurs', 'statut', 'statut_display', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class GrilleSalarialeSerializer(serializers.ModelSerializer):
    """Grille salariale par poste (XRH16) — donnée SENSIBLE (paie).
    ``company`` posée côté serveur. Jamais exposée hors du palier
    ``salaires_voir``."""
    poste_intitule = serializers.CharField(
        source='poste.intitule', read_only=True)

    class Meta:
        model = GrilleSalariale
        fields = [
            'id', 'poste', 'poste_intitule', 'echelon',
            'salaire_min', 'salaire_max', 'date_effet', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class CompetenceRequiseSerializer(serializers.ModelSerializer):
    """Profil de compétence requise par poste (XRH15). ``company`` posée côté
    serveur ; unicité (poste, compétence)."""
    competence_libelle = serializers.CharField(
        source='competence.libelle', read_only=True)
    niveau_requis_display = serializers.CharField(
        source='get_niveau_requis_display', read_only=True)

    class Meta:
        model = CompetenceRequise
        fields = [
            'id', 'poste', 'competence', 'competence_libelle',
            'niveau_requis', 'niveau_requis_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class PeriodeFermetureSerializer(serializers.ModelSerializer):
    """Fermeture collective / congé imposé (XRH14). ``company`` posée côté
    serveur ; ``appliquee``/``appliquee_le`` en lecture seule (posés par
    l'action ``appliquer``)."""
    type_absence_code = serializers.CharField(
        source='type_absence.code', read_only=True)

    class Meta:
        model = PeriodeFermeture
        fields = [
            'id', 'libelle', 'date_debut', 'date_fin', 'type_absence',
            'type_absence_code', 'departements', 'appliquee',
            'appliquee_le', 'date_creation',
        ]
        read_only_fields = ['appliquee', 'appliquee_le', 'date_creation']


class EmployeDeviceMapSerializer(serializers.ModelSerializer):
    """Mappage pointeuse externe → employé (XRH13). ``company`` posée côté
    serveur ; ``employe`` doit appartenir à la société."""
    employe_nom = serializers.SerializerMethodField()

    class Meta:
        model = EmployeDeviceMap
        fields = [
            'id', 'employe', 'employe_nom', 'device_user_id',
            'date_creation']
        read_only_fields = ['date_creation']

    def get_employe_nom(self, obj):
        return f'{obj.employe.nom} {obj.employe.prenom}'


class ReglageRHSerializer(serializers.ModelSerializer):
    """Réglages RH (XRH12) — géofence de pointage chantier. ``company``
    posée côté serveur (jamais lue du corps)."""
    class Meta:
        model = ReglageRH
        fields = ['id', 'geofence_metres', 'date_modification']
        read_only_fields = ['date_modification']


class DeviceKiosqueSerializer(serializers.ModelSerializer):
    """Device kiosque de pointage (XRH10) — administration.

    Le token en clair n'est JAMAIS exposé ici (seul ``token_hash`` en base) ;
    il n'apparaît que dans la réponse ponctuelle de l'action d'émission.
    """
    class Meta:
        model = DeviceKiosque
        fields = ['id', 'label', 'actif', 'date_creation',
                  'derniere_utilisation']
        read_only_fields = ['date_creation', 'derniere_utilisation']


class MesInfosSerializer(serializers.ModelSerializer):
    """Self-service employé (FG199) — fiche personnelle consultable/éditable.

    Le collaborateur consulte ses informations et ne peut MODIFIER que ses
    coordonnées personnelles et son contact d'urgence — JAMAIS son poste, son
    contrat, son statut, son matricule ni le ``cout_horaire`` (interne). Tous
    les champs sensibles sont en lecture seule.
    """
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DossierEmploye
        fields = [
            'id', 'matricule', 'nom', 'prenom', 'cin',
            'poste', 'type_contrat', 'type_contrat_display',
            'date_embauche', 'statut', 'statut_display',
            # Éditables par le collaborateur :
            'telephone', 'email',
            'adresse_perso', 'telephone_perso', 'email_perso',
            'urgence_nom', 'urgence_lien', 'urgence_telephone',
        ]
        read_only_fields = [
            'id', 'matricule', 'nom', 'prenom', 'cin', 'poste',
            'type_contrat', 'type_contrat_display',
            'date_embauche', 'statut', 'statut_display',
        ]


class TypePrimeSerializer(serializers.ModelSerializer):
    """Référentiel des primes & indemnités (FG193).

    Le client saisit ``code``, ``libelle``, ``nature``, ``montant_defaut``,
    ``imposable`` et ``actif``. ``company`` est posée CÔTÉ SERVEUR (jamais lue
    du corps) ; le couple (company, code) est unique.
    """
    nature_display = serializers.CharField(
        source='get_nature_display', read_only=True)

    class Meta:
        model = TypePrime
        fields = [
            'id', 'code', 'libelle', 'nature', 'nature_display',
            'montant_defaut', 'imposable', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class PrimeAttribueeSerializer(serializers.ModelSerializer):
    """Prime/indemnité attribuée à un employé pour une période (FG193).

    Le client saisit ``type_prime`` et ``employe`` (de sa société), ``annee``,
    ``mois``, ``montant``, ``motif`` et ``statut``. ``company`` est posée CÔTÉ
    SERVEUR (jamais lue du corps) ; ``type_prime`` / ``employe`` doivent
    appartenir à la société de l'utilisateur.
    """
    employe_nom = serializers.SerializerMethodField()
    type_prime_libelle = serializers.CharField(
        source='type_prime.libelle', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PrimeAttribuee
        fields = [
            'id', 'type_prime', 'type_prime_libelle',
            'employe', 'employe_nom', 'annee', 'mois',
            'montant', 'motif', 'statut', 'statut_display',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_employe_nom(self, obj):
        if not obj.employe_id:
            return ''
        return f'{obj.employe.nom} {obj.employe.prenom}'

    def validate_type_prime(self, value):
        return _meme_societe(self, value, 'Type de prime')

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Employé')

    def validate_mois(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError(
                'Le mois doit être compris entre 1 et 12.')
        return value
