"""Sérialiseurs des Ressources humaines.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    AffectationRoster,
    Competence,
    CompetenceEmploye,
    DemandeConge,
    Departement,
    DocumentEmploye,
    DossierEmploye,
    ElementSortie,
    FeuilleTemps,
    HeuresSupp,
    IncidentPresence,
    Pointage,
    Poste,
    PresenceChantier,
    Remuneration,
    SoldeConge,
    TypeAbsence,
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
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_departement(self, value):
        return _meme_societe(self, value, 'Département')

    def validate_poste_ref(self, value):
        return _meme_societe(self, value, 'Poste')


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


class TypeAbsenceSerializer(serializers.ModelSerializer):
    """Typologie d'absence (FG164) — règle de décompte par catégorie."""

    class Meta:
        model = TypeAbsence
        fields = [
            'id', 'code', 'libelle', 'decompte_jours_ouvres', 'deduit_solde',
            'remunere', 'actif', 'date_creation',
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
            'date_debut', 'date_fin', 'jours', 'motif',
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
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'emarge', 'emarge_le', 'emarge_par',
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
