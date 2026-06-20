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


class ChecklistTemplate(models.Model):
    """N74 — modèle NOMMÉ de checklist d'onboarding/chantier, configurable dans
    Paramètres. Un template regroupe des étapes ordonnées (ChecklistEtapeModele)
    et peut être rattaché à un `type_installation` : à la création d'un chantier,
    le template dont le type correspond est sélectionné automatiquement ; sinon
    on retombe sur le template « Défaut » (type_installation vide).

    Le template « Défaut » est protégé et porte EXACTEMENT les étapes appliquées
    aujourd'hui — un chantier sans type spécifique reçoit donc la même checklist
    qu'avant (comportement préservé). Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_templates')
    nom = models.CharField(max_length=120)
    # Type d'installation qui auto-sélectionne ce template (résidentiel /
    # industriel / agricole). Vide = template « Défaut » (repli générique).
    type_installation = models.CharField(
        max_length=20, choices=Installation.TypeInstallation.choices,
        blank=True, null=True)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    # `protege` verrouille le template « Défaut » système contre la suppression.
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Modèle de checklist chantier"
        verbose_name_plural = "Modèles de checklist chantier"

    def __str__(self):
        return self.nom


class ChecklistEtapeModele(models.Model):
    """N4 — étape MODÈLE de la checklist d'exécution chantier, éditable dans
    Paramètres (libellé + ordre + activation). `capture_serie` marque les
    étapes où l'on saisit des numéros de série (N9 : panneaux/onduleur).
    `protege` verrouille une étape système contre la suppression. Additif.

    N74 — chaque étape appartient à un `template` (nullable : les étapes
    historiques sans template sont rattachées au template « Défaut » par la
    migration de données / l'amorçage paresseux)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_etapes')
    # N74 — template propriétaire (nullable pour la compat ; les étapes
    # orphelines sont migrées vers le template « Défaut »).
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.CASCADE,
        null=True, blank=True, related_name='etapes')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        # N74 — la clé est unique PAR template (même cle réutilisable d'un
        # template à l'autre). Les étapes historiques (template=NULL) gardent
        # l'unicité par société jusqu'à leur rattachement au template « Défaut ».
        unique_together = [('company', 'template', 'cle')]
        verbose_name = "Étape de checklist chantier"
        verbose_name_plural = "Étapes de checklist chantier"

    def __str__(self):
        return self.libelle


class StockReservation(models.Model):
    """N14 — réservation de stock d'un chantier sur un SKU (produit catalogue).

    À la création d'un chantier, on RÉSERVE auprès du stock les quantités
    requises issues de la nomenclature GELÉE du devis lié (`Installation.bom`),
    une ligne par produit. La réservation ENGAGE le stock sans le décrémenter :
    le « disponible » d'un produit = `quantite_stock` − somme des réservations
    actives non encore consommées (les vues stock + alertes de stock bas en
    tiennent compte). Au passage du chantier à « Installé », la réservation est
    CONSOMMÉE : un seul MouvementStock SORTIE par SKU, idempotent (le drapeau
    `consomme` garantit qu'un re-passage par « Installé » ne re-décrémente
    jamais). À l'annulation/clôture du chantier, la réservation NON consommée
    est LIBÉRÉE (`active=False`) — le disponible revient.

    Entièrement additif ; multi-tenant (société posée côté serveur).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stock_reservations')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='reservations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='reservations')
    quantite = models.PositiveIntegerField(default=0)
    # Réservation engagée tant que `active` ET non `consomme` : elle pèse alors
    # sur le « disponible ». Libérée (annulation/clôture) ⇒ active=False.
    active = models.BooleanField(default=True)
    # Consommée au passage « Installé » : le stock A été décrémenté. Le drapeau
    # est le verrou d'idempotence (jamais deux SORTIE pour la même réservation).
    consomme = models.BooleanField(default=False)
    date_consommation = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réservation de stock'
        verbose_name_plural = 'Réservations de stock'
        ordering = ['installation_id', 'id']
        # Une seule réservation par (chantier, produit) — le réamorçage est
        # idempotent (on met à jour la quantité plutôt que d'empiler).
        unique_together = [('installation', 'produit')]
        indexes = [
            models.Index(fields=['produit', 'active', 'consomme']),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.produit_id} × {self.quantite}'


class ChantierChecklistItem(models.Model):
    """N4 — état d'une étape de checklist POUR un chantier donné : fait / par
    qui / quand. Le pourcentage d'avancement du chantier en dérive. Créés
    paresseusement depuis les étapes modèle à la première consultation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_items')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='checklist')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_items_faits')
    fait_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('installation', 'cle')]
        verbose_name = "Étape de checklist (chantier)"
        verbose_name_plural = "Étapes de checklist (chantier)"

    def __str__(self):
        return f"{self.installation_id} · {self.libelle} · {'✓' if self.fait else '—'}"


# ── F7/F8 — Shot list (modèle de prises de vue guidées) ──────────────────────
class ShotListSlot(models.Model):
    """F7/F8 — emplacement (créneau) d'une SHOT LIST de documentation terrain,
    configurable dans Paramètres. Chaque créneau définit une vue attendue lors
    d'une intervention, groupée par PHASE (avant/pendant/après). `obligatoire`
    pilote l'application F8 : une intervention ne peut passer à « Terminée » tant
    qu'un créneau obligatoire n'a pas au moins une photo.

    Les défauts sont semés au standard de documentation d'un chantier solaire.
    `protege` verrouille un créneau système contre la suppression. Additif —
    company-scopé, aucune migration destructive."""

    class Phase(models.TextChoices):
        AVANT = 'avant', 'Avant'
        PENDANT = 'pendant', 'Pendant'
        APRES = 'apres', 'Après'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shotlist_slots')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    phase = models.CharField(
        max_length=8, choices=Phase.choices, default=Phase.AVANT)
    # F8 — une photo de ce créneau est requise pour terminer l'intervention.
    obligatoire = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Créneau de shot list'
        verbose_name_plural = 'Créneaux de shot list'

    def __str__(self):
        return f'{self.get_phase_display()} · {self.libelle}'


# ── F5 — Liste de préparation d'une intervention ─────────────────────────────
