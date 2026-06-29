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
from .models_installation import Installation  # noqa: F401
from .models_intervention import Intervention

# NOTE: découpage de l'ancien models.py monolithe (un fichier par
# domaine). app_label, noms de table et Meta inchangés : models.py
# ré-exporte toutes les classes pour la découverte Django + migrations.


class InterventionPreparation(models.Model):
    """F5 — liste de préparation PROPRE à une intervention (une seule par
    intervention). Le matériel provient de la nomenclature gelée du chantier
    (`Installation.bom`, copiée du devis) ; les outils proviennent du kit
    d'outillage sélectionné. La confirmation « Tout est chargé » (`tout_charge`)
    est requise AVANT que l'intervention puisse quitter « À préparer ». Additif —
    company-scopé, posé côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='intervention_preparations')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='preparation')
    # Kit d'outillage sélectionné (apps.outillage.KitOutillage). SET_NULL : si le
    # kit est supprimé, la préparation et ses lignes outils restent.
    kit = models.ForeignKey(
        'outillage.KitOutillage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparations')
    # F5 — confirmation « Tout est chargé ». Garde la transition de statut.
    tout_charge = models.BooleanField(default=False)
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparations_confirmees')
    confirme_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Préparation d'intervention"
        verbose_name_plural = "Préparations d'intervention"
        ordering = ['intervention_id']

    def __str__(self):
        return f'Préparation · intervention {self.intervention_id}'


class PreparationMaterielLigne(models.Model):
    """F5 — une ligne MATÉRIEL de la préparation : quantité requise (issue de la
    nomenclature gelée du chantier) + une case « chargé ». `manquant` lie le
    flux Besoin matériel / brouillon de bon de commande existant (un manque =
    une rupture sur le disponible du SKU). Le produit catalogue est optionnel
    (les lignes libres restent traçables par désignation)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='preparation_materiel_lignes')
    preparation = models.ForeignKey(
        InterventionPreparation, on_delete=models.CASCADE,
        related_name='materiel')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparation_lignes')
    designation = models.CharField(max_length=255)
    quantite_requise = models.PositiveIntegerField(default=0)
    charge = models.BooleanField(default=False)
    # F5 — drapeau de pénurie au moment de la préparation (disponible < requis).
    manquant = models.BooleanField(default=False)
    quantite_manquante = models.PositiveIntegerField(default=0)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne matériel de préparation'
        verbose_name_plural = 'Lignes matériel de préparation'

    def __str__(self):
        return f'{self.designation} × {self.quantite_requise}'


class PreparationOutilLigne(models.Model):
    """F5 — une ligne OUTIL de la préparation : un outil du kit sélectionné, avec
    une case « coché » (chargé dans la camionnette). Référence un outil du
    catalogue Outillage (SET_NULL si l'outil est retiré du parc)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='preparation_outil_lignes')
    preparation = models.ForeignKey(
        InterventionPreparation, on_delete=models.CASCADE,
        related_name='outils')
    outil = models.ForeignKey(
        'outillage.Outillage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='preparation_lignes')
    libelle = models.CharField(max_length=255)
    coche = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Ligne outil de préparation'
        verbose_name_plural = 'Lignes outil de préparation'

    def __str__(self):
        return f'{self.libelle} · {"✓" if self.coche else "—"}'


# ── F9 — Saisie de n° de série par composant (étapes Pendant/Après) ──────────
class ComponentSerial(models.Model):
    """F9 — n° de série d'un composant relevé pendant une intervention, avec une
    photo OPTIONNELLE de la plaque signalétique (via la pièce jointe générique)
    et une éventuelle extraction OCR (interface SWAPPABLE, no-op par défaut).

    Le n° de série PEUT être vide : la saisie ne bloque JAMAIS la complétion
    d'une étape ni de l'intervention. À la validation, ces relevés alimentent le
    parc installé (sav.Equipement), exactement comme la checklist chantier (N9).
    Additif — company-scopé, posé côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='component_serials')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='serials')
    # Produit catalogue concerné (onduleur, panneau…). Optionnel : un composant
    # hors catalogue reste traçable par sa désignation libre.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='component_serials')
    designation = models.CharField(max_length=255, blank=True, default='')
    # Le créneau de shot list / l'étape où la plaque est photographiée (clé).
    slot_cle = models.CharField(max_length=40, blank=True, default='')
    numero_serie = models.CharField(max_length=120, blank=True, default='')
    # Photo de la plaque (records.Attachment) — clé MinIO, jamais commitée.
    plaque_attachment = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    # True si le n° de série a été proposé par l'OCR (sinon saisie manuelle).
    serie_ocr = models.BooleanField(default=False)
    # True une fois ce relevé poussé vers le parc installé (sav.Equipement),
    # pour ne jamais créer deux fois le même équipement.
    pousse_parc = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'N° de série de composant'
        verbose_name_plural = 'N° de série de composants'
        ordering = ['intervention_id', 'id']

    def __str__(self):
        return f'{self.designation or self.produit_id} · {self.numero_serie or "—"}'


# ── F10 — Annotation d'une photo (dessin + légende pour signaler un défaut) ───
class PhotoAnnotation(models.Model):
    """F10 — annotation d'une photo d'intervention : un calque de dessin simple
    (tracés vectoriels JSON) + une légende texte, pour signaler un problème. Fait
    partie de l'enregistrement de la photo (lié à records.Attachment). Le calque
    est stocké en JSON (lignes/flèches/rectangles relatifs) — aucune nouvelle
    dépendance d'image. Additif — company-scopé."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='photo_annotations')
    attachment = models.OneToOneField(
        'records.Attachment', on_delete=models.CASCADE,
        related_name='annotation')
    # Calque de dessin : liste d'objets {type, points/coords, couleur}. Vide =
    # pas de dessin (seule la légende compte).
    drawing = models.JSONField(default=list, blank=True)
    caption = models.TextField(blank=True, default='')
    # F10 — drapeau « problème signalé » (une annotation peut juste légender).
    probleme = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Annotation de photo'
        verbose_name_plural = 'Annotations de photo'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Annotation · pièce {self.attachment_id}'


# ── F11/F12 — Réconciliation du matériel consommé ────────────────────────────
class MaterielConsommation(models.Model):
    """F11 — réconciliation du matériel consommé d'une intervention (une par
    intervention). Liste chaque ligne de la nomenclature (prévu) face au
    réellement utilisé, autorise des lignes hors-nomenclature, et exige une
    justification dès qu'utilisé ≠ prévu. À la validation, la consommation
    RÉELLE (et non l'estimation du devis) pilote les mouvements de stock du
    chantier et la marge job-costing. Les prix d'achat restent internes."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='materiel_consommations')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='consommation')
    valide = models.BooleanField(default=False)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    valide_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réconciliation matériel consommé'
        verbose_name_plural = 'Réconciliations matériel consommé'
        ordering = ['intervention_id']

    def __str__(self):
        return f'Consommation · intervention {self.intervention_id}'


class ConsommationLigne(models.Model):
    """F11 — une ligne de la réconciliation : prévu (nomenclature) vs utilisé.
    `hors_nomenclature` marque une ligne ajoutée sur le terrain (câble, vis,
    MC4…). La justification (texte OU mémo vocal) est requise quand utilisé ≠
    prévu — vérifié au service, pas au modèle. La consommation réelle de cette
    ligne (sur SKU catalogue) pilote le mouvement de stock à la validation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='consommation_lignes')
    consommation = models.ForeignKey(
        MaterielConsommation, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consommation_lignes')
    designation = models.CharField(max_length=255)
    quantite_prevue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    quantite_utilisee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    hors_nomenclature = models.BooleanField(default=False)
    justification = models.TextField(blank=True, default='')
    # Mémo vocal de justification (F13) — lien optionnel vers un VoiceMemo.
    justification_memo = models.ForeignKey(
        'installations.VoiceMemo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    # True une fois la consommation réelle de cette ligne portée au stock, pour
    # garantir l'idempotence (jamais deux mouvements pour la même ligne).
    stock_applique = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de consommation'
        verbose_name_plural = 'Lignes de consommation'
        ordering = ['ordre', 'id']

    def __str__(self):
        return f'{self.designation} · {self.quantite_utilisee}/{self.quantite_prevue}'

    @property
    def variance(self):
        """Écart utilisé − prévu (Decimal)."""
        return (self.quantite_utilisee or 0) - (self.quantite_prevue or 0)


# ── F13/F14 — Mémo vocal + transcription (interface swappable, no-op) ─────────
class VoiceMemo(models.Model):
    """F13 — mémo vocal enregistré sur le terrain, stocké via la pièce jointe
    générique (records.Attachment → MinIO, jamais commité). Rattachable n'importe
    où sur une intervention : note générale, note sur une photo, justification de
    variance, ou note sur une réserve (via `cible`). F14 — la transcription est
    posée par l'interface SWAPPABLE : tant qu'aucun fournisseur n'est configuré,
    `transcript` = « Non transcrit — service non configuré » et `transcrit`=False.
    L'audio reste la source de vérité ; le transcript est éditable."""
    class Cible(models.TextChoices):
        GENERAL = 'general', 'Note générale'
        PHOTO = 'photo', 'Note sur photo'
        VARIANCE = 'variance', 'Justification de variance'
        RESERVE = 'reserve', 'Note sur réserve'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='voice_memos')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='voice_memos')
    cible = models.CharField(
        max_length=12, choices=Cible.choices, default=Cible.GENERAL)
    # Audio stocké (records.Attachment) — clé MinIO. SET_NULL : la suppression
    # de la pièce jointe ne perd pas l'historique de transcription.
    audio = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    transcript = models.TextField(blank=True, default='')
    # F14 — True seulement si un fournisseur a réellement transcrit. Le no-op
    # laisse False et le libellé « Non transcrit — service non configuré ».
    transcrit = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mémo vocal'
        verbose_name_plural = 'Mémos vocaux'
        ordering = ['-date_creation', 'id']

    def __str__(self):
        return f'Mémo · intervention {self.intervention_id} ({self.cible})'


# ── F16 — Réserves (punch-list) d'une intervention ───────────────────────────
class Reserve(models.Model):
    """F16 — réserve (point de finition à reprendre) d'une intervention :
    description, photo optionnelle, mémo vocal optionnel, assigné, résolution.
    Peut faire naître une intervention de suivi OU un ticket SAV (liens
    optionnels). Additif — company-scopé."""
    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        RESOLUE = 'resolue', 'Résolue'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reserves')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='reserves')
    description = models.TextField(blank=True, default='')
    photo = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    memo = models.ForeignKey(
        'installations.VoiceMemo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves_assignees')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE)
    resolution = models.TextField(blank=True, default='')
    resolue_le = models.DateTimeField(null=True, blank=True)
    # F16 — suivi engendré (optionnel) : intervention de suivi et/ou ticket SAV.
    suivi_intervention = models.ForeignKey(
        Intervention, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves_origine')
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reserves')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réserve'
        verbose_name_plural = 'Réserves'
        ordering = ['statut', '-date_creation']

    def __str__(self):
        return f'Réserve · intervention {self.intervention_id} ({self.statut})'


# ── F17 — Réconciliation du retour d'outillage ───────────────────────────────
class ToolReturn(models.Model):
    """F17 — état du retour d'un outil du kit à la clôture d'une intervention :
    rendu (oui/non) + emplacement de retour. À la confirmation, met à jour le
    statut + l'emplacement de l'outil dans le catalogue Outillage. Un outil non
    rendu est signalé (statut maintenu « En intervention »)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tool_returns')
    intervention = models.ForeignKey(
        Intervention, on_delete=models.CASCADE, related_name='tool_returns')
    outil = models.ForeignKey(
        'outillage.Outillage', on_delete=models.CASCADE,
        related_name='tool_returns')
    rendu = models.BooleanField(default=False)
    emplacement_retour = models.ForeignKey(
        'stock.EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    note = models.CharField(max_length=255, blank=True, default='')
    confirme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    confirme_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Retour d\'outil'
        verbose_name_plural = 'Retours d\'outils'
        ordering = ['intervention_id', 'id']
        unique_together = [('intervention', 'outil')]

    def __str__(self):
        return f'{self.outil_id} · {"rendu" if self.rendu else "non rendu"}'


# ── F18 — Consignes de sécurité (checklist configurable + sign-off) ──────────
class SafetyChecklistSlot(models.Model):
    """F18 — point d'une checklist de consignes de sécurité, éditable dans
    Paramètres. Défauts semés (EPI portés, consignation électrique).
    `protege` verrouille un point système. Additif — company-scopé."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_slots')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Consigne de sécurité'
        verbose_name_plural = 'Consignes de sécurité'

    def __str__(self):
        return self.libelle


class SafetySignoff(models.Model):
    """F18 — sign-off des consignes de sécurité pour une intervention (un par
    intervention). Coche chaque point de la checklist, avec qui + quand (patron
    d'audit existant)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_signoffs')
    intervention = models.OneToOneField(
        Intervention, on_delete=models.CASCADE, related_name='safety_signoff')
    signe = models.BooleanField(default=False)
    signe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    signe_le = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sign-off sécurité'
        verbose_name_plural = 'Sign-offs sécurité'
        ordering = ['intervention_id']

    def __str__(self):
        return f'Sécurité · intervention {self.intervention_id}'


class SafetyCheckItem(models.Model):
    """F18 — état d'un point de consigne de sécurité pour une intervention :
    coché / par qui / quand. Matérialisé depuis les points actifs à la première
    consultation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='safety_check_items')
    signoff = models.ForeignKey(
        SafetySignoff, on_delete=models.CASCADE, related_name='items')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=0)
    coche = models.BooleanField(default=False)
    coche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    coche_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('signoff', 'cle')]
        verbose_name = 'Point de consigne (intervention)'
        verbose_name_plural = 'Points de consigne (intervention)'

    def __str__(self):
        return f'{self.libelle} · {"✓" if self.coche else "—"}'


# ── N91/F21 — Journal d'idempotence de la capture terrain hors-ligne ──────────
class FieldOp(models.Model):
    """N91/F21 — une opération de capture terrain rejouée depuis l'outbox du
    terminal (hors-ligne → en ligne).

    Quand le réseau est mauvais, l'app file localement chaque action de la
    capture terrain (checklist chantier, photos*, n° de série, mémo vocal*,
    matériel consommé, réserves, sign-off sécurité, check-in GPS, signature PV)
    avec une **clé d'idempotence générée côté client** (`client_op_id`, un UUID).
    À la reconnexion, l'outbox POST le lot au point de synchro. Cette ligne est
    le JOURNAL de dédup : la première application enregistre le résultat ; un
    REJEU de la même clé renvoie le résultat mémorisé SANS ré-appliquer l'effet
    (no-op idempotent, last-write-wins déjà absorbé côté handler).

    La clé est **scopée par société + utilisateur** : un locataire ne peut
    jamais rejouer l'opération d'un autre. La société est posée côté serveur,
    JAMAIS lue du corps de requête. Additif — aucune table métier modifiée."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_field_ops')
    # Clé d'idempotence générée par le terminal (UUID). Unique par société.
    client_op_id = models.CharField(max_length=64, db_index=True)
    # Type d'opération (ex. « intervention.checkin »), pour router le rejeu et
    # tracer l'historique. Liste ouverte côté service (FIELD_OP_HANDLERS).
    op_type = models.CharField(max_length=60)
    # Cible logique (« intervention » / « chantier ») + son id, pour l'audit.
    target_type = models.CharField(max_length=20, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)
    # Résultat mémorisé renvoyé tel quel au rejeu (no-op idempotent).
    result = models.JSONField(default=dict, blank=True)
    # True si l'opération a réussi (un échec n'est PAS mémorisé comme succès —
    # le terminal pourra la rejouer après correction).
    ok = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    applied_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Opération de capture terrain (idempotence)'
        verbose_name_plural = 'Opérations de capture terrain (idempotence)'
        ordering = ['-applied_le', 'id']
        # Idempotence scopée société : la même clé d'un même locataire ne
        # s'applique qu'UNE fois ; deux sociétés peuvent réutiliser une valeur
        # de clé sans collision. Nom d'index ≤30 car.
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'client_op_id'],
                name='uniq_fieldop_company_opid'),
        ]

    def __str__(self):
        return f'{self.op_type} · {self.client_op_id[:8]}'
