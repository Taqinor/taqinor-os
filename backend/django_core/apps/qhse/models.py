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
    # QHSE11 — pont Réserve (installations.Reserve) → NCR. Lien optionnel via
    # FK chaîne de caractères (jamais un import cross-app de modèle) : une
    # non-conformité peut naître d'une réserve de fin de chantier.
    reserve = models.ForeignKey(
        'installations.Reserve',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr',
        verbose_name="Réserve d'origine",
    )
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
    # QHSE13 — vérification d'efficacité : une CAPA réalisée n'est VÉRIFIÉE
    # (et donc clôturable au niveau NCR) que si son efficacité a été contrôlée
    # et jugée concluante (``efficace=True``). ``efficace`` null = pas encore
    # vérifiée, True = efficace, False = inefficace (rouvre le traitement).
    efficace = models.BooleanField(
        null=True, blank=True, verbose_name='Efficace')
    commentaire_verification = models.TextField(
        blank=True, default='', verbose_name="Commentaire de vérification")
    date_verification = models.DateTimeField(
        null=True, blank=True, verbose_name='Vérifiée le')
    verifiee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_capa_verifiees',
        verbose_name='Vérifiée par',
    )
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


# ── QHSE7 — Relevé courbe I-V par string (mise en service PV) ───────────────

class ReleveCourbeIV(models.Model):
    """Relevé de courbe I-V (courant-tension) d'un string PV à la mise en service.

    Mesure de commissioning d'un string photovoltaïque : pour un chantier
    (référence lâche par ``chantier_id`` — jamais un import cross-app de
    ``installations``) et/ou un ``PlanInspectionChantier`` (ITP appliqué), on
    consigne les grandeurs caractéristiques relevées au traceur de courbe :
    ``voc`` (tension circuit ouvert), ``isc`` (courant court-circuit), ``vmpp``,
    ``impp``, ``pmpp`` (point de puissance maximale), ainsi que les conditions
    de mesure ``irradiance`` (W/m²) et ``temperature_module`` (°C). La courbe
    mesurée complète peut être stockée en JSON (liste de points ``{v, i}``).

    Le facteur de forme ``FF = Pmpp / (Voc · Isc)`` est calculé à la volée par
    :meth:`fill_factor` quand les valeurs nécessaires sont présentes.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_courbes_iv',
        verbose_name='Société',
    )
    # Référence lâche au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    # Rattachement lâche optionnel à un ITP appliqué (même app QHSE).
    plan_chantier = models.ForeignKey(
        PlanInspectionChantier,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='courbes_iv',
        verbose_name="Plan d'inspection chantier",
    )
    string_id = models.CharField(
        max_length=120, verbose_name='Identifiant du string')
    voc = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Voc — tension circuit ouvert (V)')
    isc = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Isc — courant court-circuit (A)')
    vmpp = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Vmpp — tension au point de puissance max (V)')
    impp = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Impp — courant au point de puissance max (A)')
    pmpp = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Pmpp — puissance au point max (W)')
    irradiance = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Irradiance (W/m²)')
    temperature_module = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Température module (°C)')
    # Courbe mesurée : liste de points ``[{"v": <float>, "i": <float>}, ...]``.
    courbe_points = models.JSONField(
        default=list, blank=True, verbose_name='Points de la courbe (v, i)')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_releve = models.DateTimeField(
        null=True, blank=True, verbose_name='Date du relevé')
    releve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_courbes_iv_relevees',
        verbose_name='Relevé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Relevé courbe I-V'
        verbose_name_plural = 'Relevés courbe I-V'
        ordering = ['-id']

    def __str__(self):
        return f'String {self.string_id} — chantier {self.chantier_id}'

    def fill_factor(self):
        """Facteur de forme ``FF = Pmpp / (Voc · Isc)``, sinon ``None``.

        Calculé uniquement quand ``pmpp``, ``voc`` et ``isc`` sont présents et
        que le dénominateur ``Voc · Isc`` est non nul. Renvoie un ``Decimal``
        (rapport sans unité, typiquement ≈ 0,7–0,85 pour un string sain) arrondi
        à 4 décimales ; ``None`` quand le calcul n'est pas possible.
        """
        if self.pmpp is None or self.voc is None or self.isc is None:
            return None
        denom = self.voc * self.isc
        if denom == 0:
            return None
        return (self.pmpp / denom).quantize(Decimal('0.0001'))


# ── QHSE14 — Chatter QHSE (NCR / CAPA / Incident / Audit) ──────────────────

class QhseChatterEntry(models.Model):
    """Entrée d'historique « chatter » (style Odoo) d'un objet QHSE.

    Rattachée à une entité QHSE par couple ``(cible_type, cible_id)`` — une
    référence lâche stable qui couvre déjà la non-conformité (NCR) et l'action
    corrective/préventive (CAPA) et reste ouverte aux futures entités Incident
    et Audit, sans coupler ces modèles ni dépendre de ContentType.

    Deux familles d'entrées, comme le chatter CRM :

    * automatiques (``CREATION`` / ``MODIFICATION``) — log d'un champ suivi
      (``field`` / ``field_label`` / ``old_value`` / ``new_value``), écrit côté
      serveur, jamais par le navigateur ;
    * manuelles (``NOTE``) — note libre saisie par un utilisateur.

    L'utilisateur acteur (``user``) et la société (``company``) sont TOUJOURS
    posés côté serveur. Entièrement additif.
    """
    class Cible(models.TextChoices):
        NCR = 'ncr', 'Non-conformité'
        CAPA = 'capa', 'Action corrective/préventive'
        INCIDENT = 'incident', 'Incident'
        AUDIT = 'audit', 'Audit'

    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_chatter',
        verbose_name='Société',
    )
    cible_type = models.CharField(
        max_length=10, choices=Cible.choices, verbose_name='Type de cible')
    cible_id = models.PositiveIntegerField(verbose_name="ID de l'objet ciblé")
    kind = models.CharField(
        max_length=15, choices=Kind.choices, verbose_name="Type d'entrée")
    field = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Champ')
    field_label = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Libellé du champ')
    old_value = models.TextField(
        blank=True, default='', verbose_name='Ancienne valeur')
    new_value = models.TextField(
        blank=True, default='', verbose_name='Nouvelle valeur')
    body = models.TextField(blank=True, default='', verbose_name='Note')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_chatter',
        verbose_name='Auteur',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Le')

    class Meta:
        verbose_name = 'Entrée de chatter QHSE'
        verbose_name_plural = 'Entrées de chatter QHSE'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'cible_type', 'cible_id']),
        ]

    def __str__(self):
        return f'{self.cible_type}#{self.cible_id} {self.kind}'


# ── QHSE15 — Grille d'audit + critères pondérés ────────────────────────────

class GrilleAudit(models.Model):
    """Grille d'audit réutilisable (gabarit de notation pondérée).

    Modèle de grille que l'on instancie lors d'un audit (à venir, QHSE16) :
    porte un ``nom``/``code``, une description, un ``type_audit`` (chantier /
    sécurité / qualité / environnement) et un drapeau ``actif``. Ses critères
    pondérés vivent dans ``CritereAudit`` (relation 1-N). Multi-société via le FK
    ``company`` posé côté serveur. Entièrement additif.
    """
    class TypeAudit(models.TextChoices):
        CHANTIER = 'chantier', 'Chantier'
        SECURITE = 'securite', 'Sécurité'
        QUALITE = 'qualite', 'Qualité'
        ENVIRONNEMENT = 'environnement', 'Environnement'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_grilles_audit',
        verbose_name='Société',
    )
    code = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Code')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    type_audit = models.CharField(
        max_length=15, choices=TypeAudit.choices,
        default=TypeAudit.CHANTIER, verbose_name="Type d'audit")
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Grille d'audit"
        verbose_name_plural = "Grilles d'audit"
        ordering = ['-id']

    def __str__(self):
        return self.nom

    def poids_total(self):
        """Somme des poids des critères de la grille (0 si aucun)."""
        agg = self.criteres.aggregate(total=models.Sum('poids'))
        return agg['total'] or 0


class CritereAudit(models.Model):
    """Critère pondéré d'une ``GrilleAudit``.

    Décrit un point à noter au sein d'une grille : son ``intitule``, une
    ``categorie`` (regroupement libre), un ``poids`` (pondération relative dans
    le score) et un ``ordre`` d'affichage. La note se fera sur une échelle
    ``note_max`` (défaut 5). Multi-société via ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_criteres_audit',
        verbose_name='Société',
    )
    grille = models.ForeignKey(
        GrilleAudit,
        on_delete=models.CASCADE,
        related_name='criteres',
        verbose_name="Grille d'audit",
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    categorie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Catégorie')
    poids = models.PositiveIntegerField(default=1, verbose_name='Poids')
    note_max = models.PositiveIntegerField(
        default=5, verbose_name='Note maximale')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Critère d'audit"
        verbose_name_plural = "Critères d'audit"
        ordering = ['grille', 'ordre', 'id']

    def __str__(self):
        return f'{self.intitule} (poids {self.poids})'


# ── QHSE16 — Exécution d'audit : Audit + ReponseCritere ────────────────────

class Audit(models.Model):
    """Exécution d'un audit contre une ``GrilleAudit`` (template).

    Un ``Audit`` représente la session de notation concrète : on choisit une
    ``GrilleAudit`` (gabarit), on renseigne l'auditeur, la date, et le système
    calcule un ``score`` (% pondéré des critères conformes) à la clôture via le
    service ``calculer_score_audit``. Chaque critère de la grille reçoit une
    ``ReponseCritere`` (conforme / non-conforme / NA). Les critères non-conformes
    peuvent lever une ``NonConformite`` (NCR) via ``lever_ncr_audit``.

    Cycle de vie : ``brouillon`` → ``en_cours`` → ``clos``.
    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_audits',
        verbose_name='Société',
    )
    grille = models.ForeignKey(
        GrilleAudit,
        on_delete=models.PROTECT,
        related_name='qhse_audits',
        verbose_name="Grille d'audit",
    )
    date_audit = models.DateField(
        null=True, blank=True, verbose_name="Date de l'audit")
    auditeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_audits_conduits',
        verbose_name='Auditeur',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Score calculé à la clôture (% pondéré des critères conformes, 0-100,
    # arrondi à 2 décimales). Null = pas encore calculé.
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True, verbose_name='Score (%)')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    # Référence lâche au chantier (installations.Chantier) par id — jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Audit'
        verbose_name_plural = 'Audits'
        ordering = ['-id']

    def __str__(self):
        return f'Audit {self.grille.nom} — {self.date_audit or "sans date"}'


class ReponseCritere(models.Model):
    """Réponse à un critère d'audit dans le cadre d'un ``Audit``.

    Pour chaque ``CritereAudit`` de la grille, l'auditeur coche ``CONFORME``,
    ``NON_CONFORME`` ou ``NA`` (non applicable — exclu du calcul du score) et
    peut ajouter une note. Une ``ReponseCritere`` non conforme peut générer une
    ``NonConformite`` (NCR) via le service ``lever_ncr_audit`` (lien lâche par
    ``ncr_id`` — jamais un FK fort pour éviter le couplage fort intra-app).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """

    class Resultat(models.TextChoices):
        CONFORME = 'conforme', 'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'
        NA = 'na', 'Non applicable'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_reponses_critere',
        verbose_name='Société',
    )
    audit = models.ForeignKey(
        Audit,
        on_delete=models.CASCADE,
        related_name='qhse_reponses',
        verbose_name='Audit',
    )
    critere = models.ForeignKey(
        CritereAudit,
        on_delete=models.PROTECT,
        related_name='qhse_reponses',
        verbose_name="Critère d'audit",
    )
    resultat = models.CharField(
        max_length=12, choices=Resultat.choices,
        default=Resultat.NA, verbose_name='Résultat')
    note = models.TextField(
        blank=True, default='', verbose_name='Note / observation')
    # Lien lâche vers la NonConformite levée pour cette réponse (même app, mais
    # on garde un IntegerField pour éviter les suppressions en cascade non voulues
    # et garder un couplage minimal).
    ncr_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la non-conformité levée')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Réponse à critère"
        verbose_name_plural = "Réponses à critères"
        ordering = ['audit', 'critere__ordre', 'critere__id']
        # Un seul enregistrement par (audit, critère).
        constraints = [
            models.UniqueConstraint(
                fields=['audit', 'critere'],
                name='qhse_reponsecritere_audit_critere_uniq',
            )
        ]

    def __str__(self):
        return (
            f'{self.critere.intitule} → {self.get_resultat_display()}'
            f' (audit {self.audit_id})'
        )


# ── QHSE17 — Grille de notation fin de chantier (gate clôture) ──────────────

class NotationFinChantier(models.Model):
    """Grille de notation de fin de chantier (gate de clôture).

    Évalue la qualité d'un chantier solaire avant sa clôture sur une rubrique
    pondérée : sécurité, qualité de pose, nettoyage, documents remis, satisfaction
    client. Le ``score`` (0–100, % pondéré des items conformes) est calculé à la
    création / mise à jour via le service ``calculer_score_notation`` ; le
    ``verdict`` (``passe`` / ``echec``) est dérivé automatiquement du seuil de la
    rubrique (``seuil_passage``, défaut 70). Le sélecteur
    ``chantier_peut_cloturer`` consulte cette porte avant la clôture — il ne
    bloque rien par lui-même ; le câblage dans ``installations`` est un suivi
    futur (QHSE17 advisory gate).

    Référence lâche au chantier (``chantier_id``) — jamais un import cross-app de
    ``installations.models``. Multi-société via ``company`` posée côté serveur.
    Entièrement additif.
    """

    # Seuil de passage par défaut (pourcentage de score minimal pour que le
    # chantier soit autorisé à clôturer).
    SEUIL_PASSAGE_DEFAUT = 70

    class Verdict(models.TextChoices):
        PASSE = 'passe', 'Passé'
        ECHEC = 'echec', 'Échec'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_notations_fin_chantier',
        verbose_name='Société',
    )
    # Référence lâche au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(verbose_name='ID du chantier')
    date_notation = models.DateField(
        null=True, blank=True, verbose_name='Date de notation')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_notations_fin_chantier',
        verbose_name='Auteur',
    )
    # Score calculé (% pondéré, 0–100, 2 décimales). Null = non encore calculé.
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True, verbose_name='Score (%)')
    # Seuil de passage paramétrable (%, entier). Score ≥ seuil → PASSE.
    seuil_passage = models.PositiveIntegerField(
        default=SEUIL_PASSAGE_DEFAUT, verbose_name='Seuil de passage (%)')
    # Verdict dérivé du score vs seuil. Null = pas encore calculé.
    verdict = models.CharField(
        max_length=6, choices=Verdict.choices,
        null=True, blank=True, verbose_name='Verdict')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Notation fin de chantier'
        verbose_name_plural = 'Notations fin de chantier'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_notation_co_chantier',
            ),
        ]

    def __str__(self):
        score_str = f'{self.score}%' if self.score is not None else '—'
        return f"Notation chantier {self.chantier_id} — {score_str}"


class ItemNotation(models.Model):
    """Item de notation fin de chantier (rubrique pondérée).

    Représente un critère de la grille de fin de chantier (ex. « sécurité du
    chantier », « qualité de câblage », « nettoyage », « documents remis »,
    « satisfaction client »). Chaque item porte un ``intitule``, un ``poids``
    (pondération relative) et un résultat : ``conforme`` (True/False/null).

    Le service ``calculer_score_notation`` agrège les items conformes pondérés de
    la notation parente pour calculer le ``score`` et le ``verdict``. Multi-société
    via ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_items_notation',
        verbose_name='Société',
    )
    notation = models.ForeignKey(
        NotationFinChantier,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Notation fin de chantier',
    )
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    categorie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Catégorie')
    poids = models.PositiveIntegerField(default=1, verbose_name='Poids')
    conforme = models.BooleanField(
        null=True, blank=True, verbose_name='Conforme')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Item de notation fin de chantier'
        verbose_name_plural = 'Items de notation fin de chantier'
        ordering = ['notation', 'ordre', 'id']

    def __str__(self):
        etat = 'conforme' if self.conforme else ('NC' if self.conforme is False else '?')
        return f'{self.intitule} [{etat}] (poids {self.poids})'


# ── QHSE18 — Procédure qualité versionnée (docs qualité GED) ────────────────

class ProcedureQualite(models.Model):
    """Procédure qualité VERSIONNÉE (document du système qualité, type ISO 9001).

    Chaque enregistrement est UNE version d'une procédure identifiée par sa
    ``reference`` (ex. ``PRO-QUAL-001``). À la manière de ``ged.DocumentVersion``,
    on conserve l'historique complet : créer une nouvelle version n'écrase rien,
    elle ajoute une ligne avec ``version = max(version de la référence) + 1`` (cf.
    ``services.nouvelle_version_procedure``). Le sélecteur
    ``procedure_qualite_courante`` renvoie la version en vigueur (ou, à défaut, la
    plus haute) d'une référence.

    Cycle de vie d'une version via ``statut`` : ``brouillon`` → ``en_vigueur`` →
    ``obsolete``. Le contenu peut vivre en texte libre (``contenu``) et/ou être
    rattaché à un document GED par référence lâche (``document_id`` — jamais un
    import cross-app de ``ged.models`` ; la lecture passe par
    ``apps.ged.selectors``). Multi-société via ``company`` posée côté serveur.
    Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_VIGUEUR = 'en_vigueur', 'En vigueur'
        OBSOLETE = 'obsolete', 'Obsolète'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_procedures_qualite',
        verbose_name='Société',
    )
    reference = models.CharField(max_length=80, verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    contenu = models.TextField(
        blank=True, default='', verbose_name='Contenu')
    # Référence lâche au document GED (ged.Document) par id : jamais un import
    # cross-app de modèle. La lecture passe par apps.ged.selectors.
    document_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du document GED')
    date_application = models.DateField(
        null=True, blank=True, verbose_name="Date d'entrée en vigueur")
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_procedures_qualite',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Procédure qualité'
        verbose_name_plural = 'Procédures qualité'
        ordering = ['reference', '-version', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference', 'version'],
                name='qhse_procqual_ref_version_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'reference'],
                name='qhse_procqual_co_ref',
            ),
        ]

    def __str__(self):
        return f'{self.reference} v{self.version} — {self.titre}'


# ── QHSE19 — Retour client qualité (satisfaction) ──────────────────────────

class RetourClientQualite(models.Model):
    """Retour client de satisfaction qualité (enquête post-chantier / SAV).

    Chaque enregistrement capture l'avis d'un client sur la qualité d'une
    prestation : une ``note_satisfaction`` de 1 (très insatisfait) à 5 (très
    satisfait), un ``commentaire`` libre, la ``date_retour``, le ``canal`` par
    lequel l'avis est arrivé (téléphone, email, WhatsApp, formulaire…) et un
    drapeau ``traite`` indiquant que le retour a été traité côté qualité.

    Le retour peut être rattaché — par référence LÂCHE — à un chantier
    (``chantier_id``, cf. ``installations.Chantier``) et/ou à un client
    (``client_id``, cf. ``crm`` / ``ventes``) : jamais un import cross-app de
    leurs modèles, exactement comme les autres liens QHSE (``NonConformite``,
    ``NotationFinChantier``). La lecture cross-app passe par les sélecteurs de
    l'app cible.

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). Le sélecteur ``satisfaction_moyenne`` agrège la note moyenne
    d'une société (optionnellement par chantier). Entièrement additif.
    """
    class Canal(models.TextChoices):
        TELEPHONE = 'telephone', 'Téléphone'
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        FORMULAIRE = 'formulaire', 'Formulaire'
        VISITE = 'visite', 'Visite sur site'
        AUTRE = 'autre', 'Autre'

    NOTE_MIN = 1
    NOTE_MAX = 5

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_retours_client',
        verbose_name='Société',
    )
    # Références LÂCHES par id : jamais un import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    note_satisfaction = models.PositiveSmallIntegerField(
        verbose_name='Note de satisfaction (1–5)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    date_retour = models.DateField(verbose_name='Date du retour')
    canal = models.CharField(
        max_length=12, choices=Canal.choices,
        blank=True, default='', verbose_name='Canal')
    traite = models.BooleanField(default=False, verbose_name='Traité')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Retour client qualité'
        verbose_name_plural = 'Retours client qualité'
        ordering = ['-date_retour', '-id']
        indexes = [
            models.Index(
                fields=['company', 'date_retour'],
                name='qhse_retcli_co_date',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_retcli_co_chant',
            ),
        ]

    def __str__(self):
        return f'Retour client {self.note_satisfaction}/5 — {self.date_retour}'


# ── QHSE21 — Évaluation des risques (document unique) ───────────────────────

class EvaluationRisque(models.Model):
    """Évaluation des risques professionnels — « document unique » (QHSE21).

    Document unique d'évaluation des risques (DUERP) / plan de prévention : un
    parent ``EvaluationRisque`` regroupe une série de ``LigneEvaluationRisque``,
    chaque ligne décrivant un risque par poste/activité avec sa ``gravite`` et sa
    ``probabilite`` (1–5), sa ``criticite`` calculée (gravité × probabilité) et
    les mesures de prévention associées.

    Cycle de vie : ``brouillon`` → ``validee`` → ``archivee``. Le rattachement
    optionnel à un chantier se fait par référence LÂCHE (``chantier_id`` —
    jamais un import cross-app du modèle ``installations.Chantier``). La lecture
    cross-app passe par les sélecteurs de l'app cible.

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, jamais count()+1).
    Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDEE = 'validee', 'Validée'
        ARCHIVEE = 'archivee', 'Archivée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_evaluations_risque',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    date_evaluation = models.DateField(
        null=True, blank=True, verbose_name="Date d'évaluation")
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    evaluateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_evaluations_risque',
        verbose_name='Évaluateur',
    )
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Évaluation des risques'
        verbose_name_plural = 'Évaluations des risques'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_evalrisque_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_evalrisque_co_statut',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_evalrisque_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "DUERP"} — {self.titre}'


class LigneEvaluationRisque(models.Model):
    """Ligne d'une ``EvaluationRisque`` : un risque par poste/activité (QHSE21).

    Chaque ligne décrit un ``danger`` rattaché à un ``poste``/``activite``,
    noté par sa ``gravite`` et sa ``probabilite`` (1–5). La ``criticite`` est
    calculée et STOCKÉE côté serveur (gravité × probabilité, 1–25) à chaque
    sauvegarde — jamais lue du corps. Les ``mesures_prevention`` et le
    ``risque_residuel`` (texte libre) complètent la fiche.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    NIVEAU_MIN = 1
    NIVEAU_MAX = 5

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_lignes_evaluation_risque',
        verbose_name='Société',
    )
    evaluation = models.ForeignKey(
        EvaluationRisque,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Évaluation des risques',
    )
    poste = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Poste')
    activite = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Activité')
    danger = models.CharField(max_length=255, verbose_name='Danger / risque')
    gravite = models.PositiveSmallIntegerField(
        default=1, verbose_name='Gravité (1–5)')
    probabilite = models.PositiveSmallIntegerField(
        default=1, verbose_name='Probabilité (1–5)')
    # Criticité = gravité × probabilité (1–25), calculée et stockée côté serveur.
    criticite = models.PositiveSmallIntegerField(
        default=1, verbose_name='Criticité (gravité × probabilité)')
    mesures_prevention = models.TextField(
        blank=True, default='', verbose_name='Mesures de prévention')
    risque_residuel = models.TextField(
        blank=True, default='', verbose_name='Risque résiduel')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Ligne d'évaluation des risques"
        verbose_name_plural = "Lignes d'évaluation des risques"
        ordering = ['evaluation', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['company', 'evaluation'],
                name='qhse_ligneer_co_eval',
            ),
        ]

    def save(self, *args, **kwargs):
        # La criticité est TOUJOURS recalculée côté serveur : produit
        # gravité × probabilité, jamais une valeur reçue du corps de requête.
        self.criticite = (self.gravite or 0) * (self.probabilite or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.danger} (criticité {self.criticite})'


class PermisTravail(models.Model):
    """Permis de travail QHSE — autorisation préalable à un travail à risque (QHSE23).

    Couvre les permis spécifiques exigés avant une opération dangereuse sur un
    chantier : travail en hauteur, consignation électrique, point chaud (soudure
    / meulage / flamme nue), espace confiné, ou autre. Le permis fixe une fenêtre
    de validité (``date_debut`` → ``date_fin``), les mesures de prévention à
    appliquer, qui l'a délivré et qui l'a validé.

    Cycle de vie : ``brouillon`` → ``valide`` → ``cloture`` (ou ``expire`` une
    fois la fenêtre de validité passée). Le rattachement au chantier se fait par
    référence LÂCHE (``chantier_id`` — jamais un import cross-app du modèle
    ``installations.Chantier``).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Entièrement additif.
    """
    class TypePermis(models.TextChoices):
        HAUTEUR = 'hauteur', 'Travail en hauteur'
        CONSIGNATION_ELEC = 'consignation_elec', 'Consignation électrique'
        POINT_CHAUD = 'point_chaud', 'Point chaud (soudure / flamme)'
        ESPACE_CONFINE = 'espace_confine', 'Espace confiné'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        CLOTURE = 'cloture', 'Clôturé'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_permis_travail',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    type_permis = models.CharField(
        max_length=20, choices=TypePermis.choices,
        default=TypePermis.HAUTEUR, verbose_name='Type de permis')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Début de validité')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Fin de validité')
    delivre_par = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Délivré par')
    valide_par = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Validé par')
    mesures_prevention = models.TextField(
        blank=True, default='', verbose_name='Mesures de prévention')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Permis de travail'
        verbose_name_plural = 'Permis de travail'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_permis_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_permis_co_statut',
            ),
            models.Index(
                fields=['company', 'type_permis'],
                name='qhse_permis_co_type',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_permis_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "PT"} — {self.titre}'


class ConsignationLoto(models.Model):
    """Consignation électrique (LOTO) rattachée à un permis de travail (QHSE24).

    Trace le verrouillage / étiquetage (lockout-tagout, « LOTO ») d'une source
    d'énergie électrique avant une intervention : quel équipement / point de
    consignation est mis hors tension, qui l'a consigné (``consignateur``),
    quand (``date_consignation``), avec quel cadenas (``cadenas_pose``) et quelle
    étiquette (``etiquette``), et si l'absence de tension a été vérifiée (VAT).

    Une consignation est toujours rattachée à un ``PermisTravail`` (typiquement
    de type ``consignation_elec``). Cycle de vie : ``consignee`` →
    ``deconsignee`` (la déconsignation enregistre ``date_deconsignation`` et
    bascule le ``statut``).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Entièrement additif.
    """
    class Statut(models.TextChoices):
        CONSIGNEE = 'consignee', 'Consignée'
        DECONSIGNEE = 'deconsignee', 'Déconsignée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_consignations_loto',
        verbose_name='Société',
    )
    permis = models.ForeignKey(
        'qhse.PermisTravail',
        on_delete=models.CASCADE,
        related_name='consignations_loto',
        verbose_name='Permis de travail',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    equipement = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Équipement')
    point_consignation = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Point de consignation')
    consignateur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Consignateur')
    date_consignation = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de consignation')
    date_deconsignation = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de déconsignation')
    cadenas_pose = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Cadenas posé')
    etiquette = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Étiquette')
    verifie_absence_tension = models.BooleanField(
        default=False, verbose_name="Absence de tension vérifiée (VAT)")
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.CONSIGNEE, verbose_name='Statut')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Consignation électrique (LOTO)'
        verbose_name_plural = 'Consignations électriques (LOTO)'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_consigloto_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'permis'],
                name='qhse_consigloto_co_permis',
            ),
            models.Index(
                fields=['company', 'statut'],
                name='qhse_consigloto_co_statut',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "LOTO"} — {self.equipement or self.permis_id}'


class InductionSecurite(models.Model):
    """Accueil / induction sécurité préalable à l'accès au chantier (QHSE26).

    Trace une session d'accueil sécurité donnée à une personne AVANT qu'elle
    n'accède au site : le chantier concerné, la personne accueillie (un salarié
    OU un sous-traitant externe — d'où ``personne_nom`` libre + ``est_sous_traitant``
    et ``entreprise_externe`` puisqu'un externe n'est pas un salarié), la date,
    qui a animé l'accueil (``anime_par``), les thèmes couverts (``themes``) et
    l'acquittement / signature de la personne (``acquittement`` + son horodatage
    ``acquittement_le``). Une fenêtre de validité optionnelle (``validite_jours``)
    permet d'exiger un nouvel accueil après N jours.

    Le rattachement au chantier se fait par référence LÂCHE (``chantier_id`` —
    jamais un import cross-app du modèle ``installations.Chantier``). Le lien vers
    un salarié interne est optionnel et exprimé par FK-chaîne nullable vers
    ``rh.DossierEmploye`` (jamais d'import de modèle cross-app).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_inductions_securite',
        verbose_name='Société',
    )
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    # La personne accueillie : nom libre (couvre les externes qui ne sont pas
    # des salariés). Si c'est un salarié interne, on relie en plus le dossier.
    personne_nom = models.CharField(
        max_length=255, verbose_name='Personne accueillie')
    est_sous_traitant = models.BooleanField(
        default=False, verbose_name='Sous-traitant externe')
    entreprise_externe = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Entreprise externe')
    # Salarié interne optionnel : FK-chaîne nullable, jamais un import de modèle.
    employe = models.ForeignKey(
        'rh.DossierEmploye',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_inductions_securite',
        verbose_name='Salarié (dossier RH)',
    )
    date_induction = models.DateField(
        null=True, blank=True, verbose_name="Date de l'accueil")
    anime_par = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Animé par')
    themes = models.TextField(
        blank=True, default='', verbose_name='Thèmes couverts')
    acquittement = models.BooleanField(
        default=False, verbose_name='Acquittement / signature')
    acquittement_le = models.DateTimeField(
        null=True, blank=True, verbose_name="Acquitté le")
    # Fenêtre de validité optionnelle : nombre de jours avant un nouvel accueil.
    validite_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Validité (jours)')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Accueil sécurité (induction)'
        verbose_name_plural = 'Accueils sécurité (inductions)'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_induc_co_chant',
            ),
            models.Index(
                fields=['company', 'est_sous_traitant'],
                name='qhse_induc_co_stt',
            ),
            models.Index(
                fields=['company', 'date_induction'],
                name='qhse_induc_co_date',
            ),
        ]

    def __str__(self):
        return f'Accueil sécurité — {self.personne_nom}'


class PlanUrgence(models.Model):
    """Plan d'urgence / premiers secours par chantier/site (QHSE28).

    Regroupe pour un chantier/site donné les informations à afficher en cas
    d'urgence : le ``point_rassemblement`` (point de rassemblement), l'hôpital
    le plus proche optionnel (``hopital_proche`` + ``hopital_distance_km`` +
    ``hopital_telephone``), une ``date_revision`` (dernière revue du plan) et un
    ``statut`` de cycle de vie (``brouillon`` → ``actif`` → ``archive``). Les
    contacts d'urgence (pompiers/SAMU/police + contacts internes) et les
    secouristes désignés sont portés par les enfants ``ContactUrgence`` et
    ``Secouriste``.

    Le rattachement au chantier se fait par référence LÂCHE (``chantier_id`` —
    jamais un import cross-app du modèle ``installations.Chantier``). La lecture
    cross-app passe par les sélecteurs de l'app cible.

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_plans_urgence',
        verbose_name='Société',
    )
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    point_rassemblement = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Point de rassemblement')
    point_rassemblement_details = models.TextField(
        blank=True, default='',
        verbose_name='Point de rassemblement (détails)')
    # Hôpital le plus proche — optionnel.
    hopital_proche = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Hôpital le plus proche')
    hopital_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Distance hôpital (km)')
    hopital_telephone = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Téléphone hôpital')
    date_revision = models.DateField(
        null=True, blank=True, verbose_name='Date de révision')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Plan d'urgence / premiers secours"
        verbose_name_plural = "Plans d'urgence / premiers secours"
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_planurg_co_chant',
            ),
            models.Index(
                fields=['company', 'statut'],
                name='qhse_planurg_co_statut',
            ),
        ]

    def __str__(self):
        return f'Plan d\'urgence — {self.titre}'


class ContactUrgence(models.Model):
    """Contact d'urgence d'un ``PlanUrgence`` (QHSE28).

    Un numéro à appeler en cas d'urgence : services externes (pompiers/SAMU/
    police) ou contacts internes (chef de chantier, HSE…). ``type_contact``
    classe la nature du contact ; ``nom`` et ``telephone`` portent l'essentiel.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class TypeContact(models.TextChoices):
        POMPIERS = 'pompiers', 'Pompiers'
        SAMU = 'samu', 'SAMU / urgences médicales'
        POLICE = 'police', 'Police / gendarmerie'
        INTERNE = 'interne', 'Contact interne'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_contacts_urgence',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanUrgence,
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name="Plan d'urgence",
    )
    type_contact = models.CharField(
        max_length=10, choices=TypeContact.choices,
        default=TypeContact.AUTRE, verbose_name='Type de contact')
    nom = models.CharField(max_length=255, verbose_name='Nom / service')
    telephone = models.CharField(max_length=40, verbose_name='Téléphone')
    notes = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Notes')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Contact d'urgence"
        verbose_name_plural = "Contacts d'urgence"
        ordering = ['plan', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['company', 'plan'],
                name='qhse_conturg_co_plan',
            ),
        ]

    def __str__(self):
        return f'{self.nom} ({self.telephone})'


class Secouriste(models.Model):
    """Secouriste désigné rattaché à un ``PlanUrgence`` (QHSE28).

    Un sauveteur secouriste du travail (SST) désigné pour le site. Un salarié
    interne est relié par FK-chaîne nullable vers ``rh.DossierEmploye`` (jamais
    un import de modèle cross-app) ; pour un externe, ``nom`` libre suffit. La
    certification et sa validité (``certification`` + ``validite``) sont
    optionnelles.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_secouristes',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanUrgence,
        on_delete=models.CASCADE,
        related_name='secouristes',
        verbose_name="Plan d'urgence",
    )
    # Salarié interne optionnel : FK-chaîne nullable, jamais un import de modèle.
    secouriste = models.ForeignKey(
        'rh.DossierEmploye',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_secouristes',
        verbose_name='Salarié (dossier RH)',
    )
    # Nom libre : couvre les externes (non salariés) ; complète l'affichage pour
    # un salarié interne.
    nom = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Nom (si externe)')
    telephone = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Téléphone')
    certification = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Certification (SST…)')
    validite = models.DateField(
        null=True, blank=True, verbose_name='Validité certification')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Secouriste désigné'
        verbose_name_plural = 'Secouristes désignés'
        ordering = ['plan', 'ordre', 'id']
        indexes = [
            models.Index(
                fields=['company', 'plan'],
                name='qhse_secour_co_plan',
            ),
        ]

    def __str__(self):
        if self.secouriste_id:
            return f'Secouriste — {self.secouriste}'
        return f'Secouriste — {self.nom or "?"}'


# ── QHSE29 — Registre des incidents (HSE) ──────────────────────────────────

class Incident(models.Model):
    """Registre HSE unifié des incidents au niveau site (QHSE29).

    Capture, dans un registre unique côté QHSE, les événements de terrain :
    ``accident``, ``presqu_accident`` (near-miss) et ``incident``. Chaque entrée
    décrit son ``type_incident``, sa ``date_incident``, l'éventuel chantier
    concerné, sa ``gravite``, une ``description``, l'``action_immediate`` prise
    et son cycle de vie (``statut`` : ouvert → en cours → clos).

    DISTINCT du volet RH : ``rh`` tient ses propres modèles d'accident du travail
    (``AccidentTravail`` / ``PresquAccident``) avec le détail CNSS / blessure /
    salarié. Ce registre QHSE est le volet SÉCURITÉ DE SITE et ne référence
    JAMAIS ``rh`` par import — les deux couches restent séparées.

    Le rattachement au chantier se fait par référence LÂCHE (``chantier_id`` —
    jamais un import cross-app du modèle ``installations.Chantier``).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Entièrement additif.
    """
    class TypeIncident(models.TextChoices):
        ACCIDENT = 'accident', 'Accident'
        PRESQU_ACCIDENT = 'presqu_accident', 'Presqu’accident'
        INCIDENT = 'incident', 'Incident'

    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_incidents',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    type_incident = models.CharField(
        max_length=20, choices=TypeIncident.choices,
        default=TypeIncident.INCIDENT, verbose_name="Type d'événement")
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices,
        default=Gravite.MINEURE, verbose_name='Gravité')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    date_incident = models.DateField(
        null=True, blank=True, verbose_name="Date de l'événement")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    action_immediate = models.TextField(
        blank=True, default='', verbose_name='Action immédiate')
    declare_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_incidents_declares',
        verbose_name='Déclaré par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Incident HSE'
        verbose_name_plural = 'Incidents HSE'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_incident_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_incident_co_statut',
            ),
            models.Index(
                fields=['company', 'type_incident'],
                name='qhse_incident_co_type',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_incident_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "INC"} — {self.titre}'
