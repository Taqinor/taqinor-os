"""
Module Chantiers / Installations — l'objet pivot de l'après-vente.

Le chantier (Installation) est créé une fois le devis signé/accepté. C'est le
dossier de réalisation auquel tout l'après-vente (interventions, mise en
service, et plus tard parc équipements / garanties / SAV) viendra s'attacher.

Trois couches de statuts INDÉPENDANTES coexistent dans l'OS, à ne jamais
mélanger :
  1. l'étape du lead (STAGES.py — l'entonnoir commercial) ;
  2. le statut du document devis/facture (ventes) ;
  3. le statut du CHANTIER ci-dessous (réalisation physique).

Cet enum est une liste FERMÉE, en ordre d'entonnoir. « annulé » n'est PAS une
étape : c'est un drapeau (avec motif), comme « Perdu » sur un lead.
"""
from django.conf import settings
from django.db import models
from .models_installation import Installation

# NOTE: découpage de l'ancien models.py monolithe (un fichier par
# domaine). app_label, noms de table et Meta inchangés : models.py
# ré-exporte toutes les classes pour la découverte Django + migrations.


class TypeIntervention(models.Model):
    """Type d'intervention géré (Paramètres → Chantiers). `Intervention.type`
    reste une clé texte ; cette liste pilote le sélecteur et les libellés.
    `protege` verrouille un type système contre le renommage/la suppression.
    Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='types_intervention')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=80)
    ordre = models.PositiveIntegerField(default=0)
    protege = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = "Type d'intervention"
        verbose_name_plural = "Types d'intervention"

    def __str__(self):
        return self.libelle


class Intervention(models.Model):
    class Type(models.TextChoices):
        POSE = 'pose', 'Pose'
        RACCORDEMENT = 'raccordement', 'Raccordement'
        MISE_EN_SERVICE = 'mise_en_service', 'Mise en service'
        CONTROLE = 'controle', 'Contrôle'
        DEPANNAGE = 'depannage', 'Dépannage'

    class Statut(models.TextChoices):
        # F3 — machine à états PROPRE à l'intervention (sortie chantier).
        # TOTALEMENT séparée du statut chantier (Installation.Statut) et du
        # contrat STAGES.py : changer ce statut ne touche JAMAIS le chantier.
        A_PREPARER = 'a_preparer', 'À préparer'
        PRETE = 'prete', 'Prête'
        EN_ROUTE = 'en_route', 'En route'
        SUR_SITE = 'sur_site', 'Sur site'
        TERMINEE = 'terminee', 'Terminée'
        VALIDEE = 'validee', 'Validée'

    # Ordre de progression du statut intervention (pour un tri non-alphabétique
    # et le kanban). Ne pilote AUCUNE logique chantier.
    STATUT_ORDER = [
        Statut.A_PREPARER, Statut.PRETE, Statut.EN_ROUTE,
        Statut.SUR_SITE, Statut.TERMINEE, Statut.VALIDEE,
    ]

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='interventions',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='interventions',
    )
    # Lien OPTIONNEL vers un ticket SAV : résoudre un ticket peut enregistrer
    # une ou plusieurs interventions (visites terrain) contre lui, sans créer
    # de concept « visite » parallèle. Additif, nullable — le comportement
    # chantier→intervention existant reste intact.
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    type_intervention = models.CharField(max_length=20, choices=Type.choices)
    # F3 — statut PROPRE de l'intervention. Défaut « À préparer » ⇒ toute
    # intervention existante migrée prend ce statut (additif, non destructif).
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_PREPARER)
    date_prevue = models.DateField(null=True, blank=True)
    date_realisee = models.DateField(null=True, blank=True)
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    # F3 — équipe assignée (un+ employés). Défaut = l'installateur du chantier,
    # posé côté serveur à la création quand l'équipe est laissée vide.
    equipe = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='interventions_equipe',
    )
    # F3 — camionnette assignée : un emplacement de stock (dépôt/camionnette).
    camionnette = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    compte_rendu = models.TextField(blank=True, null=True)

    # ── F6 — horodatage du trajet & arrivée sur site (géolocalisation
    #    navigateur, AUCUN service externe). Tout est ADDITIF et nullable :
    #    une intervention existante n'est pas affectée. Le check-in pose une
    #    position GPS d'arrivée (≠ GPS du chantier, qui reste la cible) ; on en
    #    dérive une distance-au-site indicative côté API. Le départ-dépôt et le
    #    retour bornent le temps de trajet. ──
    depart_depot_le = models.DateTimeField(null=True, blank=True)
    arrivee_site_le = models.DateTimeField(null=True, blank=True)
    arrivee_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    arrivee_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    retour_depot_le = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='interventions_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Intervention"
        verbose_name_plural = "Interventions"
        ordering = ['-date_prevue', '-date_creation']

    def __str__(self):
        return f"{self.get_type_intervention_display()} — {self.installation_id}"


class InterventionActivity(models.Model):
    """Historique « chatter » d'une intervention — même patron que
    InstallationActivity / LeadActivity. Entrées automatiques (création +
    changements de champs suivis, dont le statut) et notes manuelles.
    L'utilisateur et la société sont toujours posés côté serveur."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='intervention_activities',
    )
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='intervention_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité intervention'
        verbose_name_plural = 'Activités intervention'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['intervention', '-created_at'])]

    def __str__(self):
        return f"{self.intervention_id} {self.kind} {self.field or ''}".strip()


class InstallationActivity(models.Model):
    """Historique « chatter » d'un chantier — même modèle que LeadActivity.

    Entrées automatiques (création + changements de champs suivis, dont le
    statut) et notes manuelles. L'utilisateur et la société sont toujours
    posés côté serveur, jamais lus du corps de la requête.
    """
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installation_activities',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installation_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité chantier'
        verbose_name_plural = 'Activités chantier'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['installation', '-created_at'])]

    def __str__(self):
        return f"{self.installation_id} {self.kind} {self.field or ''}".strip()
