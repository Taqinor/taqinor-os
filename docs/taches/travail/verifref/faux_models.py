# Transcription partielle de reference/donnees.md §2 (jetable, jamais importée par Django).
from django.conf import settings
from django.db import models
from django.db.models import Q
from core.models import TenantModel, SoftDeleteModel
from core.champs_plateforme import VerrouOptimisteMixin


class Projet(TenantModel, SoftDeleteModel, VerrouOptimisteMixin):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    nom = models.CharField(max_length=120)
    nom_cle = models.CharField(max_length=120, editable=False)
    date_debut = models.DateField(null=True)
    echeance = models.DateField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['company', 'proprietaire', 'nom_cle'], condition=Q(is_deleted=False), name='taches_projet_nom_uniq')]


class Tache(TenantModel, SoftDeleteModel, VerrouOptimisteMixin):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, null=True)  # on_delete: composition
    section = models.ForeignKey('Section', on_delete=models.SET_NULL, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name='enfants')  # on_delete: composition
    bloquee_par = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='bloque')
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.SET_NULL, null=True)
    activite_origine = models.ForeignKey('records.Activity', on_delete=models.SET_NULL, null=True)
    recurrence = models.ForeignKey('RegleRecurrence', on_delete=models.SET_NULL, null=True)
    client_id = models.CharField(max_length=64, null=True)
    jour_prevu = models.DateField(null=True)
    premier_jour_prevu = models.DateField(null=True)
    occurrence_du = models.DateField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'proprietaire', 'client_id'], condition=Q(client_id__isnull=False, is_deleted=False), name='taches_tache_cli_uniq'),
            models.UniqueConstraint(fields=['company', 'activite_origine'], condition=Q(activite_origine__isnull=False, is_deleted=False), name='taches_tache_act_uniq'),
            models.UniqueConstraint(fields=['company', 'recurrence', 'occurrence_du'], condition=Q(recurrence__isnull=False, occurrence_du__isnull=False, is_deleted=False), name='taches_tache_occ_uniq'),
        ]


class ReglagesRythme(TenantModel):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    bloc_debut = models.DateField(null=True)
    echec_le = models.DateField(null=True)
    tenir_fixee_le = models.DateField(null=True)
    tenir_silence_jusquau = models.DateField(null=True)


class IncitationCoach(TenantModel):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    jour = models.DateField()
    expire_le = models.DateField(null=True)


class RevueProjet(TenantModel):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)  # on_delete: composition
    prochaine_action = models.ForeignKey(Tache, on_delete=models.SET_NULL, null=True)
    semaine = models.DateField()


class JetonAcces(TenantModel):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: suit le compte
    jeton_hash = models.CharField(max_length=64, unique=True)


class Rappel(TenantModel):
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # on_delete: données personnelles
    tache = models.ForeignKey(Tache, on_delete=models.CASCADE)  # on_delete: composition
    jour = models.DateField()
    envoye_le = models.DateTimeField(null=True)
