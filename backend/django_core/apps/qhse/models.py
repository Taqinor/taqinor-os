"""Modèles QHSE (Qualité / Hygiène / Sécurité / Environnement).

Socle du module QHSE :

* ``NonConformite`` (NCR) — fiche de non-conformité (qualité, sécurité,
  environnement) avec gravité, origine et cycle de vie (ouverte → en
  traitement → résolue → clôturée). Peut être rattachée à un chantier
  (référence lâche) et signalée par un utilisateur.
* ``ActionCorrectivePreventive`` (CAPA) — action corrective ou préventive
  rattachée à une non-conformité, avec cause racine, responsable, échéance et
  statut d'avancement.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Entièrement additif.
"""
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models


# ── QHSE1 / QHSE9 — Non-conformités (NCR) ──────────────────────────────────

class NonConformite(models.Model):
    """Fiche de non-conformité (NCR) d'une société.

    Trace un écart qualité/sécurité/environnement : sa ``gravite``, son
    ``origine``, l'éventuel chantier concerné (référence lâche par id, jamais un
    import cross-app de modèle) et son cycle de vie via ``statut``.
    """
    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        EN_TRAITEMENT = 'en_traitement', 'En traitement'
        RESOLUE = 'resolue', 'Résolue'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_ncr',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices,
        default=Gravite.MINEURE, verbose_name='Gravité')
    origine = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Origine')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.OUVERTE, verbose_name='Statut')
    # Référence lâche au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    signale_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr_signalees',
        verbose_name='Signalé par',
    )
    date_detection = models.DateField(
        null=True, blank=True, verbose_name='Date de détection')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Non-conformité'
        verbose_name_plural = 'Non-conformités'
        ordering = ['-id']

    def __str__(self):
        return f'{self.titre} ({self.get_gravite_display()})'


# ── QHSE10 — Actions correctives / préventives (CAPA) ──────────────────────

class ActionCorrectivePreventive(models.Model):
    """Action corrective ou préventive (CAPA) rattachée à une non-conformité.

    Décrit le traitement d'un écart : ``type_action`` (corrective/préventive),
    cause racine, responsable, échéance et avancement (``statut``).
    """
    class Type(models.TextChoices):
        CORRECTIVE = 'corrective', 'Corrective'
        PREVENTIVE = 'preventive', 'Préventive'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        REALISEE = 'realisee', 'Réalisée'
        VERIFIEE = 'verifiee', 'Vérifiée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_capa',
        verbose_name='Société',
    )
    non_conformite = models.ForeignKey(
        NonConformite,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name='Non-conformité',
    )
    type_action = models.CharField(
        max_length=12, choices=Type.choices,
        default=Type.CORRECTIVE, verbose_name="Type d'action")
    description = models.TextField(verbose_name='Description')
    cause_racine = models.TextField(
        blank=True, default='', verbose_name='Cause racine')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_capa_responsable',
        verbose_name='Responsable',
    )
    echeance = models.DateField(
        null=True, blank=True, verbose_name='Échéance')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.A_FAIRE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Action corrective / préventive'
        verbose_name_plural = 'Actions correctives / préventives'
        ordering = ['-id']

    def __str__(self):
        return f'{self.get_type_action_display()} — {self.description[:40]}'


# ── QHSE2 — ITP (Inspection & Test Plan) ───────────────────────────────────

class PlanInspectionModele(models.Model):
    """Modèle réutilisable de plan d'inspection (ITP — Inspection & Test Plan).

    Gabarit de plan d'inspection et d'essais qu'on instancie sur un chantier :
    porte un ``nom``/``code``, une description et un drapeau ``actif``. Ses
    points de contrôle vivent dans ``PointControleModele`` (relation 1-N). Tout
    est scopé société via le FK ``company`` posé côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_plans_inspection',
        verbose_name='Société',
    )
    code = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Code')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Modèle de plan d'inspection"
        verbose_name_plural = "Modèles de plan d'inspection"
        ordering = ['-id']

    def __str__(self):
        return self.nom


class PointControleModele(models.Model):
    """Point de contrôle d'un modèle de plan d'inspection (ITP).

    Décrit un contrôle à exécuter au sein d'un ``PlanInspectionModele`` : la
    ``phase`` de travaux concernée, le ``type_releve`` (nature du
    relevé — mesure/visuel/document/essai) et, surtout, un drapeau
    ``hold_point`` : un point d'arrêt obligatoire où les travaux ne peuvent pas
    se poursuivre tant qu'il n'est pas levé/signé. ``ordre`` ordonne les points
    au sein d'un plan.
    """
    class TypeReleve(models.TextChoices):
        MESURE = 'mesure', 'Mesure'
        VISUEL = 'visuel', 'Visuel'
        DOCUMENT = 'document', 'Document'
        ESSAI = 'essai', 'Essai'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_points_controle',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanInspectionModele,
        on_delete=models.CASCADE,
        related_name='points',
        verbose_name="Plan d'inspection",
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    phase = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Phase')
    type_releve = models.CharField(
        max_length=10, choices=TypeReleve.choices,
        default=TypeReleve.VISUEL, verbose_name='Type de relevé')
    # Plage attendue d'un relevé MESURÉ (QHSE5) : quand au moins l'une des deux
    # bornes est renseignée, la conformité d'un ``ReleveControle`` à valeur
    # numérique est calculée automatiquement (min ≤ valeur ≤ max). Laissées
    # nulles → aucune auto-conformité (la conformité reste manuelle).
    valeur_min = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name='Valeur min attendue')
    valeur_max = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        verbose_name='Valeur max attendue')
    hold_point = models.BooleanField(
        default=False, verbose_name="Point d'arrêt")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Point de contrôle (modèle)'
        verbose_name_plural = 'Points de contrôle (modèle)'
        ordering = ['plan', 'ordre', 'id']

    def __str__(self):
        return f'{self.intitule} ({self.get_type_releve_display()})'


# ── QHSE4 — ITP appliqué : plan chantier + relevés de contrôle ─────────────

class PlanInspectionChantier(models.Model):
    """Instance APPLIQUÉE d'un modèle ITP (``PlanInspectionModele``) sur un
    chantier précis.

    C'est l'ouverture concrète d'un plan d'inspection : on copie un gabarit
    (``modele``) sur un chantier (référence lâche par ``chantier_id`` — jamais
    un import cross-app de ``installations``) et chaque point du modèle devient
    un ``ReleveControle`` à renseigner. Cycle de vie via ``statut``
    (en_cours → clôturé). Multi-société via ``company`` posée côté serveur.
    """
    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CLOTURE = 'cloture', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_plans_chantier',
        verbose_name='Société',
    )
    modele = models.ForeignKey(
        PlanInspectionModele,
        on_delete=models.PROTECT,
        related_name='instances_chantier',
        verbose_name="Modèle d'ITP",
    )
    # Référence lâche au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(verbose_name='ID du chantier')
    date_ouverture = models.DateField(
        null=True, blank=True, verbose_name="Date d'ouverture")
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.EN_COURS, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Plan d'inspection chantier"
        verbose_name_plural = "Plans d'inspection chantier"
        ordering = ['-id']

    def __str__(self):
        return f'{self.modele.nom} — chantier {self.chantier_id}'


class ReleveControle(models.Model):
    """Relevé d'un point de contrôle au sein d'un ``PlanInspectionChantier``.

    Né de la copie d'un ``PointControleModele`` du gabarit (on conserve un FK
    ``point`` vers la source pour l'intitulé/phase/hold_point) et porte le
    relevé réel : ``valeur`` (texte libre — mesure, doc, observation),
    ``conforme`` (null = pas encore relevé, True/False), une éventuelle
    ``photo_key`` (clé objet MinIO, convention ``records.storage``), et la
    traçabilité (``date_releve`` / ``releve_par``). Multi-société via
    ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_releves',
        verbose_name='Société',
    )
    plan_chantier = models.ForeignKey(
        PlanInspectionChantier,
        on_delete=models.CASCADE,
        related_name='releves',
        verbose_name="Plan d'inspection chantier",
    )
    point = models.ForeignKey(
        PointControleModele,
        on_delete=models.PROTECT,
        related_name='releves',
        verbose_name='Point de contrôle (modèle)',
    )
    valeur = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Valeur relevée')
    conforme = models.BooleanField(
        null=True, blank=True, verbose_name='Conforme')
    # Clé objet MinIO (bucket erp-uploads) — le fichier ne quitte jamais le
    # stockage objet ; rien n'est commité dans le dépôt.
    photo_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Clé photo')
    date_releve = models.DateTimeField(
        null=True, blank=True, verbose_name='Date du relevé')
    releve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_releves_effectues',
        verbose_name='Relevé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Relevé de contrôle'
        verbose_name_plural = 'Relevés de contrôle'
        ordering = ['plan_chantier', 'point__ordre', 'id']

    def __str__(self):
        return f'{self.point.intitule} — {self.plan_chantier_id}'

    def valeur_numerique(self):
        """Extrait le premier nombre signé de ``valeur`` (texte libre).

        La ``valeur`` est saisie librement (ex. ``"24.5 N.m"`` ou ``"24,5"``).
        On lit le premier token numérique (virgule décimale tolérée) et on le
        renvoie en ``Decimal`` ; ``None`` si rien d'exploitable n'est trouvé.
        """
        if not self.valeur:
            return None
        match = re.search(r'[-+]?\d+(?:[.,]\d+)?', self.valeur)
        if not match:
            return None
        try:
            return Decimal(match.group(0).replace(',', '.'))
        except (InvalidOperation, ValueError):
            return None

    def conformite_auto(self):
        """Conformité auto-calculée vs la plage attendue du point, sinon ``None``.

        Renvoie ``True``/``False`` UNIQUEMENT quand le point de contrôle définit
        une plage numérique (au moins ``valeur_min`` ou ``valeur_max``) ET que
        la valeur relevée est numérique ; sinon ``None`` (la conformité reste
        celle posée manuellement). Bornes inclusives.
        """
        point = self.point
        vmin = point.valeur_min
        vmax = point.valeur_max
        if vmin is None and vmax is None:
            return None
        valeur = self.valeur_numerique()
        if valeur is None:
            return None
        if vmin is not None and valeur < vmin:
            return False
        if vmax is not None and valeur > vmax:
            return False
        return True

    def save(self, *args, **kwargs):
        """Auto-conformité (QHSE5) avant l'enregistrement.

        Quand le point porte une plage attendue et que la valeur est numérique,
        ``conforme`` est dérivé automatiquement (min ≤ valeur ≤ max, inclusif).
        En l'absence de plage ou de valeur numérique, ``conforme`` n'est pas
        touché : il reste celui défini manuellement.
        """
        auto = self.conformite_auto()
        if auto is not None:
            self.conforme = auto
        super().save(*args, **kwargs)
