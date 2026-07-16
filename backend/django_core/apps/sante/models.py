"""Modèles de l'app santé (``apps.sante``) — cabinets/cliniques.

Vertical NTSAN : gestion administrative d'un cabinet/clinique (agenda
multi-praticiens, admission, nomenclature d'actes, facturation patient/tiers
payant). Multi-société : chaque modèle hérite de ``core.models.TenantModel``
(FK ``company`` posée côté serveur, jamais lue du corps de requête).

DONNÉES SENSIBLES (CNDP/(DECISION), note founder du groupe NTSAN) : ce module
ne stocke QUE des données ADMINISTRATIVES (identité, RDV, facturation) —
explicitement AUCUNE donnée médicale clinique. Toute donnée personnelle de
santé future devra suivre le pattern YHARD (chiffrement au repos) + une
(DECISION) explicite du founder avant d'être ajoutée.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class Praticien(TenantModel):
    """NTSAN1 — praticien exerçant dans le cabinet/clinique."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sante_praticiens',
        verbose_name='Utilisateur lié',
    )
    nom = models.CharField(max_length=255, verbose_name='Nom')
    specialite = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Spécialité')
    numero_ordre = models.CharField(
        max_length=50, blank=True, default='', verbose_name="Numéro d'ordre")
    couleur_agenda = models.CharField(
        max_length=20, blank=True, default='#2563eb',
        verbose_name='Couleur agenda')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Praticien'
        verbose_name_plural = 'Praticiens'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Salle(TenantModel):
    """NTSAN2 — salle/ressource (consultation, bloc, imagerie, labo).

    Réservation croisée praticien+salle dans l'agenda : une salle ne peut pas
    être double-réservée sur le même créneau. La contrainte applicative vit
    dans ``services.py`` (``verifier_disponibilite_salle``) et n'est
    exerçable qu'une fois le modèle ``RendezVous`` posé (NTSAN4) — c'est
    l'unique consommateur d'un créneau de salle ; elle est implémentée et
    testée dans la même passe que NTSAN4.
    """

    class Type(models.TextChoices):
        CONSULTATION = 'consultation', 'Consultation'
        BLOC = 'bloc', 'Bloc opératoire'
        IMAGERIE = 'imagerie', 'Imagerie'
        LABO = 'labo', 'Laboratoire'

    nom = models.CharField(max_length=150, verbose_name='Nom')
    type = models.CharField(
        max_length=15, choices=Type.choices, default=Type.CONSULTATION,
        verbose_name='Type')
    capacite = models.PositiveIntegerField(default=1, verbose_name='Capacité')
    equipements = models.TextField(
        blank=True, default='', verbose_name='Équipements')

    class Meta:
        verbose_name = 'Salle'
        verbose_name_plural = 'Salles'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Patient(TenantModel):
    """NTSAN3 — dossier ADMINISTRATIF patient (aucune donnée médicale
    clinique). ``client`` référence ``crm.Client`` par FK À CHAÎNE (jamais
    d'import direct de ``apps.crm.models``) ; la résolution/rattachement se
    fait via ``services.resoudre_client_pour_patient`` (import local par
    l'appelant).

    ``convention``/``numero_affiliation`` sont posés par NTSAN9 (nécessitent
    le modèle ``Convention``, qui n'existe pas encore à ce stade).
    """

    class Sexe(models.TextChoices):
        M = 'M', 'Masculin'
        F = 'F', 'Féminin'

    nom = models.CharField(max_length=255, verbose_name='Nom')
    prenom = models.CharField(max_length=255, blank=True, default='', verbose_name='Prénom')
    cin = models.CharField(max_length=30, blank=True, default='', verbose_name='CIN')
    date_naissance = models.DateField(
        null=True, blank=True, verbose_name='Date de naissance')
    sexe = models.CharField(
        max_length=1, choices=Sexe.choices, blank=True, default='',
        verbose_name='Sexe')
    telephone = models.CharField(max_length=20, blank=True, default='', verbose_name='Téléphone')
    whatsapp = models.CharField(max_length=20, blank=True, default='', verbose_name='WhatsApp')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    numero_dossier = models.CharField(
        max_length=30, blank=True, default='', db_index=True,
        verbose_name='Numéro de dossier')
    contact_urgence = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Contact d'urgence")
    # NTSAN3 — jamais d'import direct de crm.models : FK par chaîne.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patients_sante', verbose_name='Client CRM lié')

    class Meta:
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        ordering = ['nom', 'prenom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'numero_dossier'],
                condition=~models.Q(numero_dossier=''),
                name='sante_patient_unique_dossier_par_societe'),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()
