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
from django.utils import timezone


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

    # ── XQHS2 — Disposition (que devient le produit/travail non conforme ?) ──
    class Disposition(models.TextChoices):
        REBUT = 'rebut', 'Rebut'
        RETOUCHE = 'retouche', 'Retouche'
        RETOUR_FOURNISSEUR = 'retour_fournisseur', 'Retour fournisseur'
        ACCEPTE_EN_ETAT = 'accepte_en_etat', "Accepté en l'état"
        TRI_RECONTROLE = 'tri_recontrole', 'Tri / recontrôle'

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
    # XMFG13 — pont Contrôle qualité d'assemblage (installations.OrdreAssemblage)
    # → NCR. Lien optionnel via FK chaîne de caractères (jamais un import
    # cross-app de modèle) : un item de checklist QC en échec peut ouvrir une
    # non-conformité liée à l'ordre.
    ordre_assemblage = models.ForeignKey(
        'installations.OrdreAssemblage',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr',
        verbose_name="Ordre d'assemblage d'origine",
    )
    # XQHS23 — pont SAV → NCR (boucle défaillances terrain/garantie). Lien
    # optionnel via FK-chaîne (jamais un import cross-app de modèle, pattern
    # QHSE11/XMFG13) : une NCR peut naître d'un ticket SAV (panne/garantie).
    ticket_sav = models.ForeignKey(
        'sav.Ticket',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr',
        verbose_name="Ticket SAV d'origine",
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
    # ── XQHS2 — Disposition tracée (qui/quand) + coût interne ────────────────
    disposition = models.CharField(
        max_length=20, choices=Disposition.choices,
        blank=True, default='', verbose_name='Disposition')
    disposition_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr_dispositions',
        verbose_name='Disposition posée par',
    )
    disposition_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Disposition posée le')
    # Coût interne de la disposition — JAMAIS client-facing (même règle que
    # `stock.Produit.prix_achat`).
    cout_disposition = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True, verbose_name='Coût de la disposition (interne)')
    # Référence LÂCHE au fournisseur (stock.Fournisseur) — FK-chaîne, jamais un
    # import cross-app de modèle. Posée quand disposition = retour_fournisseur.
    fournisseur = models.ForeignKey(
        'stock.Fournisseur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_ncr_retours',
        verbose_name='Fournisseur (retour)',
    )
    # XQHS4 — code de défaut normalisé (remplace/complète `origine` texte
    # libre pour permettre le Pareto). Nullable/additif.
    code_defaut = models.ForeignKey(
        'CodeDefaut',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='non_conformites',
        verbose_name='Code de défaut',
    )
    # ── XQHS22 — Coût de la non-qualité (CoQ), INTERNE uniquement ───────────
    # JAMAIS dans un PDF ni une sortie client — même règle que `prix_achat`.
    # Distinct de `cout_disposition` (XQHS2, coût de la disposition précise) :
    # ``cout_estime``/``cout_reel`` couvrent le coût GLOBAL de la NCR.
    cout_estime = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True, verbose_name='Coût estimé (interne)')
    cout_reel = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True, verbose_name='Coût réel (interne)')
    # XQHS22 — pas ``auto_now_add`` : le rollup mensuel (cout_non_qualite)
    # ventile par ``date_creation`` et doit pouvoir dater un NCR rétroactivement
    # (backfill/tests) ; l'API garde le champ read-only (auto au moment du
    # ``create`` via le default), donc le comportement client est inchangé.
    date_creation = models.DateTimeField(
        default=timezone.now, verbose_name='Créé le')

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
    # XQHS22 — coût interne de l'action (JAMAIS client-facing).
    cout = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True, verbose_name='Coût (interne)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Action corrective / préventive'
        verbose_name_plural = 'Actions correctives / préventives'
        ordering = ['-id']

    def __str__(self):
        return f'{self.get_type_action_display()} — {self.description[:40]}'


# ── XQHS2 — Dérogation (acceptation en l'état bornée) ───────────────────────

class Derogation(models.Model):
    """Acceptation en l'état bornée (dérogation) liée à une NCR (XQHS2).

    Une disposition ``accepte_en_etat`` peut nécessiter une dérogation formelle
    bornée dans le temps OU en quantité : justification, évaluation du risque,
    approbateur, et une ``date_expiration`` avec relance à échéance (même
    pattern que ``ConformiteEnvironnementale.prealerte_jours`` — QHSE38).

    Le ``statut_calcule(today)`` dérive l'état réel : ``expiree`` si l'échéance
    est dépassée, sinon le ``statut`` enregistré. Multi-société via ``company``
    posée côté serveur. Entièrement additif.
    """
    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIREE = 'expiree', 'Expirée'
        CLOTUREE = 'cloturee', 'Clôturée'

    PREALERTE_JOURS_DEFAUT = 15

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_derogations',
        verbose_name='Société',
    )
    non_conformite = models.ForeignKey(
        NonConformite,
        on_delete=models.CASCADE,
        related_name='derogations',
        verbose_name='Non-conformité',
    )
    justification = models.TextField(
        blank=True, default='', verbose_name='Justification')
    evaluation_risque = models.TextField(
        blank=True, default='', verbose_name='Évaluation du risque')
    # Bornage : période ET/OU quantité (les deux facultatifs, au moins un
    # attendu côté UI — non forcé côté modèle pour rester additif/souple).
    quantite_max = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Quantité maximale couverte')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    prealerte_jours = models.PositiveIntegerField(
        default=PREALERTE_JOURS_DEFAUT, verbose_name='Préalerte (jours)')
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_derogations_approuvees',
        verbose_name='Approbateur',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.ACTIVE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dérogation'
        verbose_name_plural = 'Dérogations'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_derog_co_statut',
            ),
            models.Index(
                fields=['company', 'date_expiration'],
                name='qhse_derog_co_exp',
            ),
        ]

    def statut_calcule(self, today=None):
        """État réel : clôturée figée, sinon expirée si l'échéance est
        dépassée, sinon le statut enregistré. Lecture seule."""
        from django.utils import timezone
        if self.statut == self.Statut.CLOTUREE:
            return self.Statut.CLOTUREE
        if today is None:
            today = timezone.localdate()
        if self.date_expiration is not None and self.date_expiration < today:
            return self.Statut.EXPIREE
        return self.statut

    def save(self, *args, **kwargs):
        # Le statut n'est auto-basculé sur EXPIREE que s'il n'a pas déjà été
        # clôturé manuellement — la clôture reste une action explicite.
        if self.statut != self.Statut.CLOTUREE:
            self.statut = self.statut_calcule()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Dérogation NCR#{self.non_conformite_id} — {self.get_statut_display()}'


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
    # XQHS4 — code de défaut normalisé posé sur un relevé en ÉCHEC
    # (``conforme=False``). Nullable/additif.
    code_defaut = models.ForeignKey(
        'CodeDefaut',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='releves_controle',
        verbose_name='Code de défaut',
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
    # XQHS11 — mapping clause ISO multi-référentiel (nullable, additif). Ex.
    # clause="9001:8.5.1", referentiel="9001". Sert à la heatmap
    # constats-par-clause et au readiness étendu (14001/45001).
    clause = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Clause ISO')
    referentiel = models.CharField(
        max_length=15, blank=True, default='',
        choices=[
            ('9001', 'ISO 9001'), ('14001', 'ISO 14001'),
            ('45001', 'ISO 45001'), ('nm', 'NM'), ('autre', 'Autre'),
        ],
        verbose_name='Référentiel')
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
    # WIR128 — valideur/délivreur tracés par FK utilisateur (auditable), à
    # l'image des modèles voisins (ActionCorrectivePreventive.verifiee_par,
    # ConsignationLoto) — plus de texte libre non traçable.
    delivre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_permis_delivres',
        verbose_name='Délivré par')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_permis_valides',
        verbose_name='Validé par')
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
    # XQHS18 — fréquence cible des exercices d'urgence (drills) pour ce plan.
    # Additif/nullable, défaut 12 mois (annuel) : ne change rien aux plans
    # existants au-delà d'ajouter la cadence de relance.
    frequence_mois = models.PositiveIntegerField(
        default=12, verbose_name="Fréquence cible des exercices (mois)")
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
        # XQHS19 — incident environnemental (déversement/rejet non conforme).
        ENVIRONNEMENT = 'environnement', 'Environnement'

    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clos'

    # ── XQHS19 — Milieu touché par un incident environnemental ──────────────
    class MilieuTouche(models.TextChoices):
        SOL = 'sol', 'Sol'
        EAU = 'eau', 'Eau'
        AIR = 'air', 'Air'

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
    # XQHS4 — code de défaut normalisé posé sur un incident. Nullable/additif.
    code_defaut = models.ForeignKey(
        'CodeDefaut',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='incidents',
        verbose_name='Code de défaut',
    )
    # ── XQHS19 — Incidents environnementaux (déversement/rejet) ─────────────
    # Tous nullable/blank par défaut : additif, aucune valeur sur les
    # incidents existants (accident/presqu_accident/incident classiques).
    substance = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Substance')
    quantite_estimee = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        verbose_name='Quantité estimée')
    quantite_unite = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Unité')
    milieu_touche = models.CharField(
        max_length=10, choices=MilieuTouche.choices,
        blank=True, default='', verbose_name='Milieu touché')
    notification_requise = models.BooleanField(
        default=False, verbose_name='Notification à autorité requise')
    autorite_notifiee = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Autorité notifiée')
    date_notification = models.DateField(
        null=True, blank=True, verbose_name='Date de notification')
    date_limite_notification = models.DateField(
        null=True, blank=True, verbose_name='Date limite de notification')
    # XQHS22 — coût interne de l'incident (JAMAIS client-facing).
    cout = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True, verbose_name='Coût (interne)')
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

    @property
    def notification_en_retard(self):
        """XQHS19 — True si une notification requise n'a pas encore été faite
        et que la date limite est dépassée. Sans échéance/non requise :
        toujours False (rien à relancer)."""
        from django.utils import timezone

        if not self.notification_requise or self.date_notification:
            return False
        if self.date_limite_notification is None:
            return False
        return timezone.localdate() > self.date_limite_notification

    def peut_cloturer(self):
        """XQHS19 — la clôture exige la notification si elle est requise
        (analogue au gate CAPA de ``NonConformite``, QHSE13)."""
        return not (self.notification_requise and not self.date_notification)


# ── QHSE30 — Déclaration CNSS de l'accident du travail (échéance légale) ─────

class DeclarationCnss(models.Model):
    """Suivi de la déclaration CNSS d'un accident du travail + échéance légale (QHSE30).

    Au Maroc, l'employeur doit déclarer tout accident du travail à la CNSS dans
    un délai légal court (quelques jours après l'accident). Ce modèle PILOTE ce
    suivi côté QHSE : pour un accident du travail donné, il calcule la
    ``date_limite`` (= ``date_accident`` + ``delai_jours``), enregistre la
    déclaration effective (``date_declaration`` + ``numero_declaration``) et
    expose un ``statut`` (à déclarer / déclaré / hors délai) afin de faire
    remonter les déclarations qui approchent de l'échéance ou la dépassent.

    L'accident lui-même vit dans ``rh`` (``rh.AccidentTravail``, FG181) et n'est
    référencé QUE par FK-CHAÎNE (``'rh.AccidentTravail'``) — jamais par import du
    modèle ``rh`` (cf. ``InductionSecurite.employe``). Le détail blessure /
    salarié / CNSS-côté-RH reste dans ``rh`` ; cette couche QHSE est le PILOTAGE
    de l'échéance réglementaire, séparé et additif.

    La ``date_accident`` est COPIÉE / saisie à la création (base du calcul de
    l'échéance) : on ne lit pas en boucle l'accident RH pour ne pas coupler les
    deux apps. Le ``delai_jours`` est paramétrable (défaut ``DELAI_LEGAL_JOURS``)
    pour absorber une évolution réglementaire sans migration.

    ``statut_calcule(today)`` dérive l'état réel à une date donnée : ``declare``
    si une déclaration est enregistrée, sinon ``hors_delai`` si l'échéance est
    dépassée, sinon ``a_declarer``. Le ``statut`` stocké est rafraîchi côté
    serveur (``save``) à partir de ce calcul tant qu'aucune déclaration n'a été
    saisie — une fois déclaré, l'état est figé sur ``declare``.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps de
    requête). Une seule déclaration par (société, accident) — ``unique_together``.

    RUNTIME-SAFETY (leçon FG136) : les codes bornés ``statut`` ≤ 20 ;
    ``numero_declaration`` plafonné ; les notes, potentiellement longues, sont un
    ``TextField`` (aucune limite à dépasser).
    """

    # Délai légal CNSS par défaut (jours) — paramétrable par déclaration.
    DELAI_LEGAL_JOURS = 2

    class Statut(models.TextChoices):
        A_DECLARER = 'a_declarer', 'À déclarer'
        DECLARE = 'declare', 'Déclaré'
        HORS_DELAI = 'hors_delai', 'Hors délai'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_declarations_cnss',
        verbose_name='Société',
    )
    # FK-CHAÎNE cross-app vers l'accident du travail (rh.AccidentTravail, FG181) :
    # jamais un import du modèle rh.
    accident_travail = models.ForeignKey(
        'rh.AccidentTravail',
        on_delete=models.CASCADE,
        related_name='qhse_declarations_cnss',
        verbose_name='Accident du travail',
    )
    # Base du calcul de l'échéance : copiée / saisie à la création (pas de lecture
    # en boucle de l'accident RH).
    date_accident = models.DateField(verbose_name="Date de l'accident")
    # Délai légal CNSS (jours) — paramétrable pour absorber une évolution
    # réglementaire sans migration.
    delai_jours = models.PositiveSmallIntegerField(
        default=DELAI_LEGAL_JOURS, verbose_name='Délai légal (jours)')
    # Échéance calculée côté serveur (= date_accident + delai_jours) — jamais lue
    # du corps de requête.
    date_limite = models.DateField(
        null=True, blank=True, verbose_name='Date limite de déclaration')
    # Déclaration effective : date + référence CNSS (vides tant que non déclaré).
    date_declaration = models.DateField(
        null=True, blank=True, verbose_name='Date de déclaration')
    numero_declaration = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='N° / référence de déclaration')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.A_DECLARER, verbose_name='Statut')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    # ── XQHS1 — jours d'ITT + certificat/consolidation/conciliation ─────────
    # ``jours_itt`` est SAISI/COPIÉ à la création comme ``date_accident`` : la
    # source RH vivante reste ``rh.AccidentTravail.nb_jours_arret`` (pas de
    # double saisie synchronisée en continu, juste un instantané au moment de
    # la déclaration QHSE).
    jours_itt = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Jours d'incapacité temporaire de travail (ITT)")
    date_certificat_initial = models.DateField(
        null=True, blank=True,
        verbose_name='Date du certificat médical initial')
    date_consolidation = models.DateField(
        null=True, blank=True,
        verbose_name='Date de consolidation / guérison')

    class ConciliationStatut(models.TextChoices):
        NON_REQUISE = 'non_requise', 'Non requise'
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        FAITE = 'faite', 'Faite'

    conciliation_statut = models.CharField(
        max_length=15, choices=ConciliationStatut.choices,
        default=ConciliationStatut.NON_REQUISE,
        verbose_name='Statut de la conciliation préalable')
    # ── XQHS1 — volet maladie professionnelle (MP) ───────────────────────────
    # Réutilise la même mécanique d'échéances ; ``est_maladie_professionnelle``
    # gate l'affichage du volet MP côté UI sans dupliquer le modèle.
    est_maladie_professionnelle = models.BooleanField(
        default=False, verbose_name='Maladie professionnelle')
    type_maladie_professionnelle = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Type MP (tableau marocain)')
    exposition_mp = models.TextField(
        blank=True, default='', verbose_name="Exposition (agent, durée, poste)")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Déclaration CNSS d'accident du travail"
        verbose_name_plural = "Déclarations CNSS d'accident du travail"
        ordering = ['-id']
        unique_together = [('company', 'accident_travail')]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_declcnss_co_statut',
            ),
            models.Index(
                fields=['company', 'date_limite'],
                name='qhse_declcnss_co_limite',
            ),
        ]

    def calcul_date_limite(self):
        """Échéance légale = ``date_accident`` + ``delai_jours`` (ou None)."""
        from datetime import timedelta
        if self.date_accident is None:
            return None
        return self.date_accident + timedelta(days=self.delai_jours or 0)

    def statut_calcule(self, today=None):
        """État réel de la déclaration à une date donnée.

        * ``declare`` — une déclaration est enregistrée (``date_declaration``
          renseignée) ; l'état est alors figé, indépendamment de l'échéance ;
        * ``hors_delai`` — pas (encore) déclaré ET ``date_limite`` strictement
          dépassée (``< today``) ;
        * ``a_declarer`` — pas déclaré et l'échéance n'est pas (encore) dépassée.

        Lecture seule, aucune mutation.
        """
        from django.utils import timezone
        if self.date_declaration is not None:
            return self.Statut.DECLARE
        if today is None:
            today = timezone.localdate()
        limite = self.date_limite or self.calcul_date_limite()
        if limite is not None and limite < today:
            return self.Statut.HORS_DELAI
        return self.Statut.A_DECLARER

    def save(self, *args, **kwargs):
        """Recalcule l'échéance et rafraîchit le statut côté serveur.

        La ``date_limite`` est TOUJOURS dérivée de ``date_accident`` +
        ``delai_jours`` (jamais lue du corps). Le ``statut`` est aligné sur
        ``statut_calcule()`` — déclaré si une déclaration existe, sinon hors
        délai/à déclarer selon l'échéance.
        """
        self.date_limite = self.calcul_date_limite()
        self.statut = self.statut_calcule()
        super().save(*args, **kwargs)

    def __str__(self):
        return (f'Décl. CNSS accident#{self.accident_travail_id} — '
                f'{self.get_statut_display()}')


# ── XQHS1 — Checklist des étapes légales AT/MP (loi 18-12) ──────────────────

class EtapeDeclarationAt(models.Model):
    """Étape légale datée de la chaîne de déclaration AT/MP (loi 18-12, XQHS1).

    La loi 18-12 impose une CHAÎNE d'étapes (pas une échéance unique) :

    * ``avis_employeur`` — avis à l'employeur/assureur sous 48 h ;
    * ``dossier_assureur`` — dossier de déclaration à l'assureur AT sous 5 j ;
    * ``information_inspection`` — information de l'inspection du travail dans
      le même délai (5 j) ;
    * ``certificat_medical`` — certificat médical initial (en 3 exemplaires) ;
    * ``suivi_itt`` — suivi des jours d'ITT ;
    * ``certificat_guerison`` — certificat de guérison / consolidation ;
    * ``conciliation`` — étape de conciliation préalable obligatoire.

    Chaque étape porte une ``echeance`` CALCULÉE côté serveur (jamais lue du
    corps de requête) à partir de ``declaration.date_accident`` + un délai en
    heures/jours propre au type d'étape (cf. ``services.instancier_etapes_at``),
    un statut (``a_faire``/``fait``/``hors_delai``) et une date de réalisation.
    Une pièce jointe peut être rattachée via ``records.Attachment`` (ContentType
    générique, comme ``ReleveControle``/``NonConformite``).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class TypeEtape(models.TextChoices):
        AVIS_EMPLOYEUR = 'avis_employeur', 'Avis à l\'employeur/assureur (48 h)'
        DOSSIER_ASSUREUR = 'dossier_assureur', \
            "Dossier de déclaration à l'assureur AT (5 j)"
        INFORMATION_INSPECTION = 'information_inspection', \
            "Information de l'inspection du travail (5 j)"
        CERTIFICAT_MEDICAL = 'certificat_medical', \
            'Certificat médical initial (3 exemplaires)'
        SUIVI_ITT = 'suivi_itt', "Suivi des jours d'ITT"
        CERTIFICAT_GUERISON = 'certificat_guerison', \
            'Certificat de guérison / consolidation'
        CONCILIATION = 'conciliation', 'Conciliation préalable obligatoire'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        FAIT = 'fait', 'Fait'
        HORS_DELAI = 'hors_delai', 'Hors délai'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_etapes_declaration_at',
        verbose_name='Société',
    )
    declaration = models.ForeignKey(
        DeclarationCnss,
        on_delete=models.CASCADE,
        related_name='etapes',
        verbose_name='Déclaration CNSS',
    )
    type_etape = models.CharField(
        max_length=25, choices=TypeEtape.choices, verbose_name="Type d'étape")
    # Échéance calculée côté serveur (cf. services.instancier_etapes_at) —
    # jamais lue du corps de requête.
    echeance = models.DateTimeField(
        null=True, blank=True, verbose_name='Échéance')
    fait_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Fait le')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.A_FAIRE, verbose_name='Statut')
    notes = models.TextField(blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Étape de déclaration AT/MP'
        verbose_name_plural = 'Étapes de déclaration AT/MP'
        ordering = ['declaration', 'echeance', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['declaration', 'type_etape'],
                name='qhse_etapeat_decl_type_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_etapeat_co_statut',
            ),
            models.Index(
                fields=['company', 'echeance'],
                name='qhse_etapeat_co_echeance',
            ),
        ]

    def statut_calcule(self, now=None):
        """État réel de l'étape : fait / hors délai / à faire.

        ``fait`` si ``fait_le`` est renseigné (figé, indépendant de l'échéance) ;
        sinon ``hors_delai`` si l'échéance est strictement dépassée ; sinon
        ``a_faire``. Lecture seule.
        """
        from django.utils import timezone
        if self.fait_le is not None:
            return self.Statut.FAIT
        if now is None:
            now = timezone.now()
        if self.echeance is not None and self.echeance < now:
            return self.Statut.HORS_DELAI
        return self.Statut.A_FAIRE

    def save(self, *args, **kwargs):
        self.statut = self.statut_calcule()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_type_etape_display()} — {self.get_statut_display()}'


# ── QHSE31 — Analyse d'incident (arbre des causes) → CAPA ───────────────────

class AnalyseIncident(models.Model):
    """Analyse des causes d'un ``Incident`` (arbre des causes) → CAPA (QHSE31).

    Pour un incident HSE (``Incident``, QHSE29), conduit une analyse de causes
    racines : la ``methode`` employée (cinq M / arbre des causes / cinq
    pourquoi), une ``description`` du déroulé et une ``synthese`` des
    enseignements, son ``analyste`` et son cycle de vie (``statut`` : en cours →
    clos).

    L'arbre des causes lui-même vit dans ``CauseIncident`` (relation 1-N
    auto-référencée pour la hiérarchie faits → causes immédiates → causes
    profondes → cause racine). Les actions correctives générées sont des
    ``ActionCorrectivePreventive`` (CAPA) du même module : conformément au
    modèle existant (la CAPA porte un FK NON nul vers ``NonConformite``), le
    service ``generer_capa_depuis_analyse`` crée d'abord une NCR-pont depuis
    l'incident puis la CAPA dessus, et rattache cette NCR à l'analyse via
    ``non_conformite`` — on réutilise le modèle CAPA tel quel, sans linkage
    divergent (cf. ``lever_ncr_audit``).

    Une seule analyse par incident (contrainte d'unicité ``OneToOne`` logique).
    Multi-société via ``company`` posée côté serveur (jamais lue du corps).
    Entièrement additif.
    """
    class Methode(models.TextChoices):
        CINQ_M = '5m', 'Cinq M (Ishikawa)'
        ARBRE_DES_CAUSES = 'arbre_des_causes', 'Arbre des causes'
        CINQ_POURQUOI = '5pourquoi', 'Cinq pourquoi'

    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_analyses_incident',
        verbose_name='Société',
    )
    incident = models.OneToOneField(
        Incident,
        on_delete=models.CASCADE,
        related_name='analyse',
        verbose_name='Incident',
    )
    methode = models.CharField(
        max_length=20, choices=Methode.choices,
        default=Methode.ARBRE_DES_CAUSES, verbose_name="Méthode d'analyse")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    synthese = models.TextField(
        blank=True, default='', verbose_name='Synthèse')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.EN_COURS, verbose_name='Statut')
    date_analyse = models.DateField(
        null=True, blank=True, verbose_name="Date de l'analyse")
    analyste = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_analyses_incident',
        verbose_name='Analyste',
    )
    # NCR-pont (QHSE31) : la CAPA existante porte un FK NON nul vers
    # ``NonConformite`` ; le service crée donc une NCR depuis l'incident et la
    # rattache ici pour relier l'analyse à ses CAPA — réutilisation du modèle
    # CAPA tel quel (jamais un linkage divergent).
    non_conformite = models.ForeignKey(
        NonConformite,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='analyses_incident',
        verbose_name='Non-conformité liée',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Analyse d'incident"
        verbose_name_plural = "Analyses d'incident"
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_analyse_co_statut',
            ),
        ]

    def __str__(self):
        return f'Analyse incident#{self.incident_id} ({self.get_methode_display()})'


class CauseIncident(models.Model):
    """Nœud de l'arbre des causes d'une ``AnalyseIncident`` (QHSE31).

    Chaque cause porte son ``type_cause`` (fait / cause immédiate / cause
    profonde / cause racine), un ``libelle`` et un ``parent`` optionnel
    (auto-référencé, même analyse) qui construit la HIÉRARCHIE de l'arbre : un
    fait peut enfanter une cause immédiate, qui enfante une cause profonde, qui
    remonte à la cause racine. ``ordre`` ordonne les frères.

    Multi-société via ``company`` posée côté serveur. Le FK ``analyse`` et le FK
    ``parent`` restent intra-app (même module QHSE) — additif.
    """
    class TypeCause(models.TextChoices):
        FAIT = 'fait', 'Fait'
        CAUSE_IMMEDIATE = 'cause_immediate', 'Cause immédiate'
        CAUSE_PROFONDE = 'cause_profonde', 'Cause profonde'
        CAUSE_RACINE = 'cause_racine', 'Cause racine'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_causes_incident',
        verbose_name='Société',
    )
    analyse = models.ForeignKey(
        AnalyseIncident,
        on_delete=models.CASCADE,
        related_name='causes',
        verbose_name='Analyse',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='enfants',
        verbose_name='Cause parente',
    )
    type_cause = models.CharField(
        max_length=20, choices=TypeCause.choices,
        default=TypeCause.FAIT, verbose_name='Type de cause')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Cause d'incident"
        verbose_name_plural = "Causes d'incident"
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(
                fields=['analyse', 'parent'],
                name='qhse_cause_analyse_par',
            ),
        ]

    def __str__(self):
        return f'{self.get_type_cause_display()} — {self.libelle[:40]}'


# ── QHSE33 — Inspection sécurité planifiée (→ NCR) ─────────────────────────

class InspectionSecurite(models.Model):
    """Inspection sécurité planifiée d'un chantier / site (QHSE33).

    Une inspection sécurité (ronde / visite HSE) est PLANIFIÉE à une date
    (``date_prevue``), réalisée (``date_realisee``) puis conclue ``conforme`` ou
    ``non_conforme``. Quand l'inspection est jugée non conforme, elle peut
    LEVER une non-conformité (NCR) via le service ``lever_ncr_inspection``
    (idempotent : une seule NCR par inspection), lien tracé par ``ncr``.

    Le rattachement au chantier se fait par référence LÂCHE (``chantier_id`` —
    jamais un import cross-app du modèle ``installations.Chantier``). La NCR
    générée est intra-app (FK ``qhse.NonConformite``).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). La ``reference`` est attribuée côté serveur via
    ``create_with_reference`` (plus haut numéro utilisé + 1, race-safe — jamais
    count()+1). Entièrement additif.
    """
    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        REALISEE = 'realisee', 'Réalisée'
        ANNULEE = 'annulee', 'Annulée'

    class Resultat(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        CONFORME = 'conforme', 'Conforme'
        NON_CONFORME = 'non_conforme', 'Non conforme'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_inspections_securite',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    titre = models.CharField(max_length=255, verbose_name='Titre')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PLANIFIEE, verbose_name='Statut')
    resultat = models.CharField(
        max_length=15, choices=Resultat.choices,
        default=Resultat.EN_ATTENTE, verbose_name='Résultat')
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    date_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date prévue')
    date_realisee = models.DateField(
        null=True, blank=True, verbose_name='Date réalisée')
    inspecteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_inspections_securite',
        verbose_name='Inspecteur',
    )
    observations = models.TextField(
        blank=True, default='', verbose_name='Observations')
    # NCR levée par cette inspection (QHSE33) — lien intra-app, idempotent.
    ncr = models.ForeignKey(
        NonConformite,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inspections_securite',
        verbose_name='Non-conformité levée',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Inspection sécurité'
        verbose_name_plural = 'Inspections sécurité'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_inspsec_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_inspsec_co_statut',
            ),
            models.Index(
                fields=['company', 'date_prevue'],
                name='qhse_inspsec_co_prevue',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_inspsec_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "INSP"} — {self.titre}'


# ── QHSE36 — Déchets + bordereau de suivi (BSD, loi 28-00) ─────────────────

class Dechet(models.Model):
    """Type de déchet géré par la société (QHSE36, loi 28-00).

    Référentiel des déchets produits sur les chantiers solaires : emballages,
    chutes de câble, panneaux HS, batteries (DANGEREUX), huiles, etc. Chaque
    entrée porte sa ``categorie`` (dangereux / non dangereux / inerte), un
    ``code`` (catalogue marocain des déchets, optionnel), une ``unite`` de
    quantité et la filière d'élimination prévue (``mode_traitement``).

    La loi 28-00 (gestion des déchets et leur élimination) impose un suivi
    formalisé des déchets DANGEREUX via un bordereau (cf.
    ``BordereauSuiviDechet``). ``dangereux`` est dérivé de la catégorie.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Categorie(models.TextChoices):
        DANGEREUX = 'dangereux', 'Dangereux'
        NON_DANGEREUX = 'non_dangereux', 'Non dangereux'
        INERTE = 'inerte', 'Inerte'

    class ModeTraitement(models.TextChoices):
        RECYCLAGE = 'recyclage', 'Recyclage / valorisation'
        ENFOUISSEMENT = 'enfouissement', 'Enfouissement'
        INCINERATION = 'incineration', 'Incinération'
        TRAITEMENT_SPECIALISE = 'traitement_specialise', \
            'Traitement spécialisé'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_dechets',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    code = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Code déchet')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices,
        default=Categorie.NON_DANGEREUX, verbose_name='Catégorie')
    unite = models.CharField(
        max_length=20, blank=True, default='kg', verbose_name='Unité')
    mode_traitement = models.CharField(
        max_length=25, choices=ModeTraitement.choices,
        default=ModeTraitement.RECYCLAGE, verbose_name='Mode de traitement')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Déchet'
        verbose_name_plural = 'Déchets'
        ordering = ['libelle', 'id']
        indexes = [
            models.Index(
                fields=['company', 'categorie'],
                name='qhse_dechet_co_cat',
            ),
        ]

    @property
    def dangereux(self):
        """Vrai si le déchet est de catégorie dangereuse (suivi BSD requis)."""
        return self.categorie == self.Categorie.DANGEREUX

    def __str__(self):
        return f'{self.libelle} ({self.get_categorie_display()})'


class BordereauSuiviDechet(models.Model):
    """Bordereau de suivi des déchets (BSD, QHSE36, loi 28-00).

    Pièce réglementaire qui trace le PARCOURS d'un lot de déchets dangereux du
    producteur (la société) jusqu'à son élimination finale, en passant par le
    transporteur et l'éliminateur. La loi 28-00 impose ce suivi pour les déchets
    dangereux : ``Dechet.dangereux`` doit être vrai (garde-fou côté service).

    Cycle : ``emis`` (créé par le producteur) → ``enleve`` (pris en charge par le
    transporteur) → ``traite`` (éliminé / valorisé, bordereau soldé). Le
    rattachement au chantier producteur se fait par référence LÂCHE
    (``chantier_id`` — jamais un import cross-app de ``installations``).

    Multi-société via ``company`` posée côté serveur. La ``reference`` est
    attribuée côté serveur via ``create_with_reference`` (plus haut numéro
    utilisé + 1, race-safe — jamais count()+1). Entièrement additif.
    """
    class Statut(models.TextChoices):
        EMIS = 'emis', 'Émis'
        ENLEVE = 'enleve', 'Enlevé'
        TRAITE = 'traite', 'Traité'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_bsd',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    dechet = models.ForeignKey(
        Dechet,
        on_delete=models.PROTECT,
        related_name='bordereaux',
        verbose_name='Déchet',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.EMIS, verbose_name='Statut')
    # Référence LÂCHE au chantier producteur (installations.Chantier) par id.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier producteur')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=3,
        null=True, blank=True, verbose_name='Quantité')
    producteur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Producteur')
    transporteur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Transporteur')
    eliminateur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Éliminateur')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    date_enlevement = models.DateField(
        null=True, blank=True, verbose_name="Date d'enlèvement")
    date_traitement = models.DateField(
        null=True, blank=True, verbose_name='Date de traitement')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bordereau de suivi des déchets'
        verbose_name_plural = 'Bordereaux de suivi des déchets'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_bsd_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_bsd_co_statut',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_bsd_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "BSD"} — {self.dechet_id}'


# ── QHSE37 — Recyclage des modules PV (fin de vie) ─────────────────────────

class RecyclageModule(models.Model):
    """Fin de vie / recyclage d'un lot de modules photovoltaïques (QHSE37).

    Trace l'envoi en filière de recyclage de modules PV en fin de vie (casse,
    déclassement, rénovation) : marque/modèle, nombre de modules, masse estimée,
    motif de mise au rebut, filière/repreneur et cycle de vie
    (``collecte`` → ``transporte`` → ``recycle``). Un panneau PV est un déchet
    spécifique (verre + silicium + cadre alu + connectique) dont la valorisation
    matière est encadrée : ce modèle est le pendant « modules » du BSD (QHSE36)
    et peut citer un ``BordereauSuiviDechet`` quand le lot transite par un BSD.

    Le rattachement au chantier d'origine se fait par référence LÂCHE
    (``chantier_id`` — jamais un import cross-app de ``installations``). Le FK
    ``bordereau`` reste intra-app (QHSE).

    Multi-société via ``company`` posée côté serveur. La ``reference`` est
    attribuée côté serveur via ``create_with_reference`` (plus haut numéro
    utilisé + 1, race-safe — jamais count()+1). Entièrement additif.
    """
    class Motif(models.TextChoices):
        CASSE = 'casse', 'Casse / bris'
        DECLASSEMENT = 'declassement', 'Déclassement (performance)'
        RENOVATION = 'renovation', 'Rénovation / remplacement'
        FIN_DE_VIE = 'fin_de_vie', 'Fin de vie'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        COLLECTE = 'collecte', 'Collecté'
        TRANSPORTE = 'transporte', 'Transporté'
        RECYCLE = 'recycle', 'Recyclé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_recyclage_modules',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    marque = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Marque')
    modele = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Modèle')
    nombre_modules = models.PositiveIntegerField(
        default=0, verbose_name='Nombre de modules')
    masse_kg = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True, verbose_name='Masse estimée (kg)')
    motif = models.CharField(
        max_length=15, choices=Motif.choices,
        default=Motif.FIN_DE_VIE, verbose_name='Motif')
    statut = models.CharField(
        max_length=12, choices=Statut.choices,
        default=Statut.COLLECTE, verbose_name='Statut')
    filiere = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Filière / repreneur')
    # Référence LÂCHE au chantier d'origine (installations.Chantier) par id.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID du chantier d'origine")
    # Lien optionnel vers le bordereau de suivi (QHSE36) — intra-app.
    bordereau = models.ForeignKey(
        BordereauSuiviDechet,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recyclages_modules',
        verbose_name='Bordereau de suivi',
    )
    date_collecte = models.DateField(
        null=True, blank=True, verbose_name='Date de collecte')
    date_recyclage = models.DateField(
        null=True, blank=True, verbose_name='Date de recyclage')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Recyclage de modules PV'
        verbose_name_plural = 'Recyclages de modules PV'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='qhse_recyc_co_ref_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_recyc_co_statut',
            ),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_recyc_co_chant',
            ),
        ]

    def __str__(self):
        return f'{self.reference or "REC"} — {self.nombre_modules} module(s)'


# ── QHSE38 — Conformité environnementale + relances ────────────────────────

class ConformiteEnvironnementale(models.Model):
    """Obligation de conformité environnementale + échéance de renouvellement (QHSE38).

    Suit les autorisations / obligations réglementaires environnementales d'une
    société : autorisation environnementale, étude d'impact (EIE), enregistrement
    déchets (loi 28-00), conformité rejets/eau/air, autre. Chaque entrée porte un
    ``type_conformite``, l'``autorite`` qui la délivre, sa fenêtre de validité
    (``date_obtention`` → ``date_expiration``) et un cycle de vie (``conforme`` /
    ``a_renouveler`` / ``non_conforme`` / ``expire``).

    Le ``statut_calcule(today)`` dérive l'état réel à une date : ``expire`` si
    l'échéance est passée, ``a_renouveler`` si elle approche (dans
    ``prealerte_jours``), sinon le ``statut`` enregistré. Le sélecteur
    ``conformites_a_relancer`` (QHSE38) et le service ``relancer_conformites``
    s'appuient dessus pour notifier les renouvellements à préparer.

    Le rattachement éventuel au chantier se fait par référence LÂCHE
    (``chantier_id`` — jamais un import cross-app de ``installations``).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    PREALERTE_JOURS_DEFAUT = 60

    class TypeConformite(models.TextChoices):
        AUTORISATION = 'autorisation', 'Autorisation environnementale'
        ETUDE_IMPACT = 'etude_impact', "Étude d'impact (EIE)"
        ENREGISTREMENT_DECHETS = 'enregistrement_dechets', \
            'Enregistrement déchets (loi 28-00)'
        REJETS = 'rejets', 'Conformité rejets (eau / air)'
        # XQHS8 — généralisation du registre à toutes les thématiques ISO
        # 45001/9001 (sécurité, travail, urbanisme, technique).
        COMMISSION_LOCALE = 'commission_locale', 'Commission locale (sécurité)'
        VERIFICATION_ELECTRIQUE = (
            'verification_electrique', 'Vérification électrique périodique')
        REGLEMENT_INTERIEUR = 'reglement_interieur', 'Règlement intérieur'
        CSH = 'csh', 'CSH (comité sécurité et hygiène)'
        URBANISME = 'urbanisme', 'Urbanisme / autorisation chantier'
        ASSURANCE = 'assurance', 'Assurance obligatoire'
        AUTRE = 'autre', 'Autre'

    class Thematique(models.TextChoices):
        ENVIRONNEMENT = 'environnement', 'Environnement'
        SECURITE = 'securite', 'Sécurité'
        TRAVAIL = 'travail', 'Travail'
        TECHNIQUE = 'technique', 'Technique'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        CONFORME = 'conforme', 'Conforme'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        NON_CONFORME = 'non_conforme', 'Non conforme'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_conformites_env',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    type_conformite = models.CharField(
        max_length=25, choices=TypeConformite.choices,
        default=TypeConformite.AUTORISATION, verbose_name='Type')
    # XQHS8 — thématique du registre généralisé (environnement reste le
    # défaut pour ne rien changer aux lignes existantes QHSE38).
    thematique = models.CharField(
        max_length=15, choices=Thematique.choices,
        default=Thematique.ENVIRONNEMENT, verbose_name='Thématique')
    # XQHS8 — dernière évaluation périodique de conformité (ISO 45001/9001).
    date_derniere_evaluation = models.DateField(
        null=True, blank=True, verbose_name='Date de la dernière évaluation')
    resultat_derniere_evaluation = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Résultat de la dernière évaluation')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.CONFORME, verbose_name='Statut')
    autorite = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Autorité de tutelle')
    reference_dossier = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Référence du dossier')
    # Référence LÂCHE au chantier (installations.Chantier) par id.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    date_obtention = models.DateField(
        null=True, blank=True, verbose_name="Date d'obtention")
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    prealerte_jours = models.PositiveIntegerField(
        default=PREALERTE_JOURS_DEFAUT,
        verbose_name='Préalerte (jours)')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_conformites_env',
        verbose_name='Responsable',
    )
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Conformité environnementale'
        verbose_name_plural = 'Conformités environnementales'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_confenv_co_statut',
            ),
            models.Index(
                fields=['company', 'date_expiration'],
                name='qhse_confenv_co_exp',
            ),
        ]

    def statut_calcule(self, today=None):
        """État réel à une date : expiré / à renouveler / statut enregistré.

        ``expire`` si l'échéance est passée ; ``a_renouveler`` si elle tombe dans
        la fenêtre de préalerte ; sinon le ``statut`` enregistré. Sans échéance,
        renvoie le ``statut`` enregistré tel quel.
        """
        from datetime import timedelta

        from django.utils import timezone

        if today is None:
            today = timezone.localdate()
        if self.date_expiration is None:
            return self.statut
        if self.date_expiration < today:
            return self.Statut.EXPIRE
        limite = today + timedelta(days=self.prealerte_jours or 0)
        if self.date_expiration <= limite:
            return self.Statut.A_RENOUVELER
        return self.statut

    def __str__(self):
        return f'{self.intitule} ({self.get_type_conformite_display()})'


# ── QHSE39 — Bilan carbone interne (scopes 1 / 2 / 3) ──────────────────────

class BilanCarbone(models.Model):
    """Bilan carbone interne d'une société sur une période (QHSE39).

    Inventaire des émissions de gaz à effet de serre (GES) de la société, agrégé
    par les trois SCOPES du GHG Protocol :

    * scope 1 — émissions directes (combustion carburant des véhicules, groupes
      électrogènes, etc.) ;
    * scope 2 — émissions indirectes liées à l'énergie achetée (électricité du
      réseau) ;
    * scope 3 — autres émissions indirectes (achats, transport amont/aval,
      déplacements, déchets…).

    Le bilan porte une ``annee`` (et un libellé), un ``statut`` (brouillon /
    validé / archivé) et agrège ses lignes (``LigneBilanCarbone``) en totaux par
    scope + total global (``total_tco2e`` / ``total_scope_*``), tous calculés à la
    volée à partir des lignes — aucun champ dérivé stocké.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_bilans_carbone',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    annee = models.PositiveIntegerField(verbose_name='Année')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    perimetre = models.TextField(
        blank=True, default='', verbose_name='Périmètre')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bilan carbone'
        verbose_name_plural = 'Bilans carbone'
        ordering = ['-annee', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'annee', 'libelle'],
                name='qhse_bilan_co_an_lib_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'annee'],
                name='qhse_bilan_co_annee',
            ),
        ]

    def _total(self, scope=None):
        from decimal import Decimal
        qs = self.lignes.all()
        if scope is not None:
            qs = qs.filter(scope=scope)
        # tco2e est dérivé (quantite × facteur_emission) : on somme en Python
        # pour réutiliser la propriété ``tco2e`` de chaque ligne.
        return sum((ligne.tco2e for ligne in qs), Decimal('0'))

    @property
    def total_scope_1(self):
        return self._total(LigneBilanCarbone.Scope.SCOPE_1)

    @property
    def total_scope_2(self):
        return self._total(LigneBilanCarbone.Scope.SCOPE_2)

    @property
    def total_scope_3(self):
        return self._total(LigneBilanCarbone.Scope.SCOPE_3)

    @property
    def total_tco2e(self):
        return self._total()

    def __str__(self):
        return f'{self.libelle} ({self.annee})'


class LigneBilanCarbone(models.Model):
    """Ligne d'émission d'un bilan carbone, rattachée à un scope (QHSE39).

    Chaque ligne décrit une SOURCE d'émission : sa ``categorie`` (carburant,
    électricité, déplacements…), son ``scope`` (1 / 2 / 3), une ``quantite``
    d'activité dans son ``unite`` et un ``facteur_emission`` (tCO₂e par unité).
    Les émissions de la ligne (``tco2e``) sont DÉRIVÉES : ``quantite ×
    facteur_emission`` — jamais stockées.

    Le FK ``bilan`` reste intra-app (même module QHSE). ``company`` posée côté
    serveur. Entièrement additif.
    """
    class Scope(models.TextChoices):
        SCOPE_1 = 'scope_1', 'Scope 1 — émissions directes'
        SCOPE_2 = 'scope_2', 'Scope 2 — énergie achetée'
        SCOPE_3 = 'scope_3', 'Scope 3 — autres indirectes'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_lignes_bilan_carbone',
        verbose_name='Société',
    )
    bilan = models.ForeignKey(
        BilanCarbone,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Bilan',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    scope = models.CharField(
        max_length=10, choices=Scope.choices,
        default=Scope.SCOPE_1, verbose_name='Scope')
    categorie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Catégorie')
    quantite = models.DecimalField(
        max_digits=14, decimal_places=3,
        default=0, verbose_name="Quantité d'activité")
    unite = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Unité')
    facteur_emission = models.DecimalField(
        max_digits=14, decimal_places=6,
        default=0, verbose_name="Facteur d'émission (tCO₂e/unité)")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de bilan carbone'
        verbose_name_plural = 'Lignes de bilan carbone'
        ordering = ['scope', 'id']
        indexes = [
            models.Index(
                fields=['bilan', 'scope'],
                name='qhse_lbilan_bilan_scope',
            ),
        ]

    @property
    def tco2e(self):
        """Émissions de la ligne (tCO₂e) = quantité × facteur d'émission."""
        from decimal import Decimal
        q = self.quantite or Decimal('0')
        f = self.facteur_emission or Decimal('0')
        return (q * f).quantize(Decimal('0.001'))

    def __str__(self):
        return f'{self.libelle} ({self.get_scope_display()})'


# ── QHSE40 — Indicateur ESG + export reporting ─────────────────────────────

class IndicateurESG(models.Model):
    """Indicateur ESG (Environnement / Social / Gouvernance) (QHSE40).

    Mesure un indicateur extra-financier d'une société pour une période donnée,
    classé par ``pilier`` ESG. Chaque indicateur porte un ``code`` (libre, ex.
    ``E1`` / ``S2``), une ``valeur`` mesurée, une ``cible`` optionnelle, une
    ``unite`` et une période (``annee`` + ``periode`` libre, ex. ``T1`` ou
    ``2026``). ``atteinte_cible`` indique si la cible est tenue.

    Le sélecteur ``export_esg`` (QHSE40) agrège ces indicateurs par pilier pour
    le reporting (CSRD-like) ; un export plat est exposé côté vue. Le
    rattachement éventuel au bilan carbone (QHSE39) reste un FK intra-app
    optionnel.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Pilier(models.TextChoices):
        ENVIRONNEMENT = 'environnement', 'Environnement'
        SOCIAL = 'social', 'Social'
        GOUVERNANCE = 'gouvernance', 'Gouvernance'

    class Tendance(models.TextChoices):
        HAUSSE_FAVORABLE = 'hausse_favorable', 'Hausse favorable'
        BAISSE_FAVORABLE = 'baisse_favorable', 'Baisse favorable'
        NEUTRE = 'neutre', 'Neutre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_indicateurs_esg',
        verbose_name='Société',
    )
    code = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Code')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    pilier = models.CharField(
        max_length=15, choices=Pilier.choices,
        default=Pilier.ENVIRONNEMENT, verbose_name='Pilier ESG')
    valeur = models.DecimalField(
        max_digits=18, decimal_places=4,
        null=True, blank=True, verbose_name='Valeur')
    cible = models.DecimalField(
        max_digits=18, decimal_places=4,
        null=True, blank=True, verbose_name='Cible')
    unite = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Unité')
    annee = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Année')
    periode = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Période')
    tendance_souhaitee = models.CharField(
        max_length=20, choices=Tendance.choices,
        default=Tendance.NEUTRE, verbose_name='Tendance souhaitée')
    # Lien optionnel vers un bilan carbone (QHSE39) — intra-app.
    bilan_carbone = models.ForeignKey(
        BilanCarbone,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='indicateurs_esg',
        verbose_name='Bilan carbone lié',
    )
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Indicateur ESG'
        verbose_name_plural = 'Indicateurs ESG'
        ordering = ['pilier', 'code', 'id']
        indexes = [
            models.Index(
                fields=['company', 'pilier'],
                name='qhse_esg_co_pilier',
            ),
            models.Index(
                fields=['company', 'annee'],
                name='qhse_esg_co_annee',
            ),
        ]

    @property
    def atteinte_cible(self):
        """Cible atteinte ? ``None`` si valeur ou cible manquante.

        Le sens dépend de la tendance souhaitée : pour une baisse favorable
        (ex. accidents, émissions) la cible est tenue quand ``valeur <= cible`` ;
        sinon (hausse favorable / neutre) quand ``valeur >= cible``.
        """
        if self.valeur is None or self.cible is None:
            return None
        if self.tendance_souhaitee == self.Tendance.BAISSE_FAVORABLE:
            return self.valeur <= self.cible
        return self.valeur >= self.cible

    def __str__(self):
        return f'{self.code or self.libelle} ({self.get_pilier_display()})'


# ── XQHS3 — Contrôle qualité à la réception fournisseur + quarantaine ───────

class PlanControleReception(models.Model):
    """Plan de contrôle qualité à la réception fournisseur (XQHS3).

    Défini par produit OU par catégorie (au moins l'un des deux — non forcé
    côté modèle) : quand une ``stock.ReceptionFournisseur`` est confirmée
    (événement ``core.events.reception_fournisseur_confirmee``), tout produit
    couvert par un plan actif déclenche un ``ControleReception``. Le
    ``taux_echantillonnage`` (%) indique la part à contrôler ; les points de
    contrôle vivent dans ``PointControleReception`` (relation 1-N, réutilise le
    pattern ``PointControleModele``).

    Références FK-CHAÎNE vers ``stock`` (jamais un import de modèle).
    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_plans_controle_reception',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=255, verbose_name='Nom')
    # Référence LÂCHE au produit (stock.Produit) — FK-chaîne.
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='qhse_plans_controle_reception',
        verbose_name='Produit',
    )
    # Référence LÂCHE à la catégorie (stock.Categorie) — FK-chaîne.
    categorie = models.ForeignKey(
        'stock.Categorie',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='qhse_plans_controle_reception',
        verbose_name='Catégorie',
    )
    taux_echantillonnage = models.PositiveSmallIntegerField(
        default=100, verbose_name="Taux d'échantillonnage (%)")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Plan de contrôle réception'
        verbose_name_plural = 'Plans de contrôle réception'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'produit'],
                name='qhse_plancr_co_produit',
            ),
            models.Index(
                fields=['company', 'categorie'],
                name='qhse_plancr_co_categ',
            ),
        ]

    def __str__(self):
        return self.nom


class PointControleReception(models.Model):
    """Point de contrôle d'un ``PlanControleReception`` (XQHS3).

    Mirroir de ``PointControleModele`` (ITP) : décrit un point à vérifier à la
    réception (visuel/mesure/document/essai), sans point d'arrêt (pas de
    blocage bloquant côté modèle — l'advisory se fait au niveau du sélecteur).
    """
    class TypeReleve(models.TextChoices):
        MESURE = 'mesure', 'Mesure'
        VISUEL = 'visuel', 'Visuel'
        DOCUMENT = 'document', 'Document'
        ESSAI = 'essai', 'Essai'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_points_controle_reception',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanControleReception,
        on_delete=models.CASCADE,
        related_name='points',
        verbose_name='Plan de contrôle réception',
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    type_releve = models.CharField(
        max_length=10, choices=TypeReleve.choices,
        default=TypeReleve.VISUEL, verbose_name='Type de relevé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Point de contrôle réception'
        verbose_name_plural = 'Points de contrôle réception'
        ordering = ['plan', 'ordre', 'id']

    def __str__(self):
        return self.intitule


class ControleReception(models.Model):
    """Contrôle qualité exécuté à la réception d'un produit sous plan (XQHS3).

    Une ``ControleReception`` matérialise l'exécution d'un
    ``PlanControleReception`` pour UNE réception fournisseur donnée
    (``reception_id`` — FK-CHAÎNE vers ``stock.ReceptionFournisseur``, jamais
    un import de modèle). Le ``verdict`` (accepté / refusé / quarantaine) est
    posé par le contrôleur ; un verdict ``refuse`` crée automatiquement une
    ``NonConformite`` pré-remplie (disposition XQHS2) via
    ``services.lever_ncr_controle_reception``.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Verdict(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        ACCEPTE = 'accepte', 'Accepté'
        REFUSE = 'refuse', 'Refusé'
        QUARANTAINE = 'quarantaine', 'Quarantaine'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_controles_reception',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanControleReception,
        on_delete=models.PROTECT,
        related_name='controles',
        verbose_name='Plan de contrôle réception',
    )
    # Référence LÂCHE à la réception fournisseur (stock.ReceptionFournisseur).
    reception_id = models.PositiveIntegerField(
        verbose_name='ID de la réception fournisseur')
    # Référence LÂCHE au produit contrôlé (stock.Produit).
    produit_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du produit')
    verdict = models.CharField(
        max_length=15, choices=Verdict.choices,
        default=Verdict.EN_ATTENTE, verbose_name='Verdict')
    controleur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_controles_reception',
        verbose_name='Contrôleur',
    )
    notes = models.TextField(blank=True, default='', verbose_name='Notes')
    # Pont vers la NCR créée automatiquement sur un verdict REFUSE (XQHS2).
    non_conformite = models.ForeignKey(
        NonConformite,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_controles_reception',
        verbose_name='Non-conformité liée',
    )
    date_controle = models.DateTimeField(
        null=True, blank=True, verbose_name='Contrôlé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Contrôle réception'
        verbose_name_plural = 'Contrôles réception'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reception_id', 'plan'],
                name='qhse_ctrlrecep_co_recep_plan_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'verdict'],
                name='qhse_ctrlrecep_co_verdict',
            ),
            models.Index(
                fields=['company', 'reception_id'],
                name='qhse_ctrlrecep_co_recep',
            ),
        ]

    def __str__(self):
        return f'Contrôle réception#{self.reception_id} — {self.get_verdict_display()}'

    @property
    def ouvert(self):
        """Contrôle non encore statué (advisory pour ``stock``)."""
        return self.verdict == self.Verdict.EN_ATTENTE


# ── XQHS4 — Catalogue de codes de défauts + Pareto qualité ──────────────────

class CodeDefaut(models.Model):
    """Code de défaut normalisé (référentiel company-scoped, XQHS4).

    Remplace le texte libre ``NonConformite.origine`` pour permettre
    l'agrégation des causes (Pareto). Chaque code porte un ``code`` court, un
    ``libelle`` et une ``famille`` (regroupement de haut niveau : produit / pose
    DC / pose AC / structure / document / fournisseur…). Seedable via
    ``manage.py seed_codes_defaut_solaire`` (idempotent).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Famille(models.TextChoices):
        PRODUIT = 'produit', 'Produit'
        POSE_DC = 'pose_dc', 'Pose DC'
        POSE_AC = 'pose_ac', 'Pose AC'
        STRUCTURE = 'structure', 'Structure'
        DOCUMENT = 'document', 'Document'
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_codes_defaut',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    famille = models.CharField(
        max_length=15, choices=Famille.choices,
        default=Famille.AUTRE, verbose_name='Famille')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Code de défaut'
        verbose_name_plural = 'Codes de défaut'
        ordering = ['famille', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='qhse_codedefaut_co_code_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'famille'],
                name='qhse_codedefaut_co_famille',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


# ── XFSM14 — Thermographie IR : points chauds classés + baseline/suivi ─────

class ReleveThermographie(models.Model):
    """Relevé de thermographie infrarouge (IEC 62446-3) d'un équipement.

    Chaque relevé capture une image IR (via ``records.Attachment``, référence
    LÂCHE par id — jamais un import cross-app de modèle) d'un ``equipement_ref``
    texte libre, le ``delta_t`` mesuré (écart de température °C) et une
    ``classe_severite`` dérivée automatiquement du seuillage société (méthode
    ``classer_severite``). Deux ``campagne`` : ``recette`` (baseline initiale) et
    ``suivi`` (contrôle périodique) permettent la comparaison dans le temps pour
    un même ``equipement_ref``.

    Rattachement chantier par référence LÂCHE (``chantier_id``). Multi-société
    via ``company`` posée côté serveur. Entièrement additif.
    """
    class Campagne(models.TextChoices):
        RECETTE = 'recette', 'Recette (baseline)'
        SUIVI = 'suivi', 'Suivi périodique'

    class Severite(models.TextChoices):
        OBSERVATION = 'observation', 'Observation'
        A_SURVEILLER = 'a_surveiller', 'À surveiller'
        INTERVENTION_REQUISE = 'intervention_requise', 'Intervention requise'

    # Seuils par défaut ΔT (°C) — classement IEC 62446-3, paramétrable par
    # société via les champs seuil_* ci-dessous.
    SEUIL_A_SURVEILLER_DEFAUT = 5
    SEUIL_INTERVENTION_DEFAUT = 15

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_releves_thermo',
        verbose_name='Société',
    )
    # Référence LÂCHE au chantier (installations.Chantier) par id.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    equipement_ref = models.CharField(
        max_length=255, verbose_name='Référence équipement')
    # Référence LÂCHE à la pièce jointe (records.Attachment) par id.
    attachment_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la pièce jointe (image IR)')
    campagne = models.CharField(
        max_length=10, choices=Campagne.choices,
        default=Campagne.SUIVI, verbose_name='Campagne')
    delta_t = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True, verbose_name='ΔT mesuré (°C)')
    seuil_a_surveiller = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=SEUIL_A_SURVEILLER_DEFAUT,
        verbose_name='Seuil « à surveiller » (°C)')
    seuil_intervention = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=SEUIL_INTERVENTION_DEFAUT,
        verbose_name='Seuil « intervention requise » (°C)')
    classe_severite = models.CharField(
        max_length=25, choices=Severite.choices,
        default=Severite.OBSERVATION, verbose_name='Classe de sévérité')
    date_releve = models.DateField(
        null=True, blank=True, verbose_name='Date du relevé')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    # Lien lâche vers la NCR auto-créée en cas de sévérité maximale.
    ncr = models.ForeignKey(
        NonConformite,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='releves_thermo',
        verbose_name='NCR levée',
    )
    releve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_releves_thermo',
        verbose_name='Relevé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Relevé de thermographie'
        verbose_name_plural = 'Relevés de thermographie'
        ordering = ['-date_releve', '-id']
        indexes = [
            models.Index(
                fields=['company', 'equipement_ref'],
                name='qhse_thermo_co_equip',
            ),
        ]

    def classer_severite(self):
        """Dérive la classe de sévérité depuis ``delta_t`` et les seuils.

        ``intervention_requise`` si ΔT ≥ seuil_intervention, ``a_surveiller``
        si ΔT ≥ seuil_a_surveiller, sinon ``observation``. Sans ΔT mesuré,
        renvoie ``observation`` (rien à classer).
        """
        if self.delta_t is None:
            return self.Severite.OBSERVATION
        if self.delta_t >= self.seuil_intervention:
            return self.Severite.INTERVENTION_REQUISE
        if self.delta_t >= self.seuil_a_surveiller:
            return self.Severite.A_SURVEILLER
        return self.Severite.OBSERVATION

    def save(self, *args, **kwargs):
        self.classe_severite = self.classer_severite()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.equipement_ref} — ΔT {self.delta_t}°C'


# ── XFSM24 — Check-in travailleur isolé avec escalade ───────────────────────

class CheckinSecurite(models.Model):
    """Cycle check-in/check-out d'un technicien seul sur site à risque.

    Le technicien check-in au démarrage d'une intervention à risque (toiture,
    local HT…) avec une ``heure_checkout_prevue``. Si le check-out réel dépasse
    ce délai de plus de ``delai_escalade_min`` minutes sans check-out, la
    tâche périodique ``escalader_checkins_en_retard`` (service) déclenche UNE
    escalade (``escalade_declenchee`` — idempotent, jamais deux fois).

    Rattachement intervention par référence LÂCHE (``intervention_id`` —
    jamais un import cross-app de ``sav``/``installations``). Multi-société via
    ``company`` posée côté serveur. Entièrement additif.
    """
    DELAI_ESCALADE_MIN_DEFAUT = 30

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_checkins',
        verbose_name='Société',
    )
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='qhse_checkins',
        verbose_name='Technicien',
    )
    # Référence LÂCHE à l'intervention (sav.Ticket ou installations.*) par id.
    intervention_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'intervention")
    site_ref = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Site')
    heure_checkin = models.DateTimeField(
        null=True, blank=True, verbose_name='Heure de check-in')
    heure_checkout_prevue = models.DateTimeField(
        null=True, blank=True, verbose_name='Heure de check-out prévue')
    heure_checkout_reelle = models.DateTimeField(
        null=True, blank=True, verbose_name='Heure de check-out réelle')
    delai_escalade_min = models.PositiveIntegerField(
        default=DELAI_ESCALADE_MIN_DEFAUT,
        verbose_name="Délai avant escalade (min)")
    escalade_declenchee = models.BooleanField(
        default=False, verbose_name='Escalade déclenchée')
    escalade_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Escaladé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Check-in sécurité'
        verbose_name_plural = 'Check-ins sécurité'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'heure_checkout_prevue'],
                name='qhse_checkin_co_prevue',
            ),
        ]

    def en_retard(self, now=None):
        """True si le check-out réel manque et le délai d'escalade est dépassé."""
        from django.utils import timezone

        if self.heure_checkout_reelle is not None:
            return False
        if self.heure_checkout_prevue is None:
            return False
        if now is None:
            now = timezone.now()
        from datetime import timedelta
        limite = self.heure_checkout_prevue + timedelta(
            minutes=self.delai_escalade_min or 0)
        return now > limite

    def __str__(self):
        return f'Check-in {self.technicien} — {self.site_ref or "site"}'


# ── XQHS5 — Campagne de rappel / containment par produit-lot-série ─────────

class CampagneRappel(models.Model):
    """Campagne de rappel/containment sur un défaut fournisseur (produit-lot).

    Le ``produit`` est référencé en FK-CHAÎNE (``'stock.Produit'`` — jamais un
    import de modèle) ; la plage de séries/lot borne le peuplement des
    ``ElementRappel`` (lu depuis le parc réel via ``sav.selectors``, jamais un
    import de ``apps.sav.models``). Multi-société via ``company`` posée côté
    serveur. Entièrement additif.
    """
    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_COURS = 'en_cours', 'En cours'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_campagnes_rappel',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=255, verbose_name='Titre')
    # FK-chaîne — jamais un import cross-app de `apps.stock.models`.
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='qhse_campagnes_rappel',
        verbose_name='Produit concerné',
    )
    serie_debut = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Série début')
    serie_fin = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Série fin')
    lot = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Lot')
    motif = models.TextField(blank=True, default='', verbose_name='Motif')
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices,
        default=Gravite.MAJEURE, verbose_name='Gravité')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    date_verification_efficacite = models.DateField(
        null=True, blank=True, verbose_name="Vérification d'efficacité")
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_campagnes_rappel',
        verbose_name='Responsable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Campagne de rappel'
        verbose_name_plural = 'Campagnes de rappel'
        ordering = ['-id']

    def __str__(self):
        return self.titre


class ElementRappel(models.Model):
    """Équipement concerné par une ``CampagneRappel`` — cycle de traitement.

    Rattachement au parc/chantier/client par références LÂCHES
    (``equipement_id``, ``installation_id``, ``client_id`` — jamais un import
    cross-app de modèle) : peuplées depuis ``sav.selectors`` uniquement.
    """
    class Statut(models.TextChoices):
        A_NOTIFIER = 'a_notifier', 'À notifier'
        NOTIFIE = 'notifie', 'Notifié'
        PLANIFIE = 'planifie', 'Planifié'
        REMPLACE = 'remplace', 'Remplacé'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_elements_rappel',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        CampagneRappel,
        on_delete=models.CASCADE,
        related_name='elements',
        verbose_name='Campagne',
    )
    # Référence LÂCHE au parc (sav.Equipement) — jamais un import de modèle.
    equipement_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID équipement (parc)')
    numero_serie = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Numéro de série')
    # Référence LÂCHE au chantier (installations.Installation) par id.
    installation_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de l'installation")
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.A_NOTIFIER, verbose_name='Statut')
    # Ticket SAV créé pour le remplacement (référence LÂCHE — jamais un import
    # de `apps.sav.models`).
    ticket_sav_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID ticket SAV (remplacement)')
    notifie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Notifié le')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Élément de rappel'
        verbose_name_plural = 'Éléments de rappel'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['campagne', 'equipement_id'],
                name='qhse_elemrappel_campagne_equip_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_elemrappel_co_statut',
            ),
        ]

    def __str__(self):
        return f'{self.numero_serie or self.equipement_id} ({self.get_statut_display()})'


# ── XQHS6 — SCAR : demande d'action corrective fournisseur ─────────────────

class DemandeActionFournisseur(models.Model):
    """SCAR — demande d'action corrective adressée à un fournisseur.

    Se crée depuis une NCR d'origine fournisseur (réception refusée / NCR
    fournisseur) : le ``fournisseur`` est référencé en FK-CHAÎNE
    (``'stock.Fournisseur'`` — jamais un import cross-app de modèle). Le cycle
    de vie (``emise`` → ``repondue`` → ``verifiee`` → ``close``) trace la
    réponse fournisseur (cause racine / action / preuve en pièces jointes
    ``records.Attachment``, saisies EN INTERNE) et sa vérification d'efficacité
    (pattern QHSE13).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Statut(models.TextChoices):
        EMISE = 'emise', 'Émise'
        REPONDUE = 'repondue', 'Répondue'
        VERIFIEE = 'verifiee', 'Vérifiée'
        CLOSE = 'close', 'Close'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_scar',
        verbose_name='Société',
    )
    # FK-chaîne — jamais un import cross-app de `apps.stock.models`.
    fournisseur = models.ForeignKey(
        'stock.Fournisseur',
        on_delete=models.CASCADE,
        related_name='qhse_scar',
        verbose_name='Fournisseur',
    )
    ncr_source = models.ForeignKey(
        NonConformite,
        on_delete=models.CASCADE,
        related_name='scar',
        verbose_name='NCR source',
    )
    description_defaut = models.TextField(
        blank=True, default='', verbose_name='Description du défaut')
    echeance_reponse = models.DateField(
        null=True, blank=True, verbose_name='Échéance de réponse')
    cause_racine_fournisseur = models.TextField(
        blank=True, default='', verbose_name='Cause racine (fournisseur)')
    action_fournisseur = models.TextField(
        blank=True, default='', verbose_name='Action corrective (fournisseur)')
    # Références LÂCHES aux preuves (records.Attachment), saisies EN INTERNE
    # (jamais un import cross-app de modèle).
    preuve_attachment_ids = models.JSONField(
        default=list, blank=True, verbose_name='IDs pièces jointes preuve')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.EMISE, verbose_name='Statut')
    date_reponse = models.DateTimeField(
        null=True, blank=True, verbose_name='Répondue le')
    efficace = models.BooleanField(
        null=True, blank=True, verbose_name='Efficace (vérification)')
    date_verification = models.DateTimeField(
        null=True, blank=True, verbose_name='Vérifiée le')
    verifiee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_scar_verifiees',
        verbose_name='Vérifiée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Demande d'action corrective fournisseur (SCAR)"
        verbose_name_plural = "Demandes d'action corrective fournisseur (SCAR)"
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'fournisseur', 'statut'],
                name='qhse_scar_co_fourn_statut',
            ),
        ]

    def __str__(self):
        return f'SCAR #{self.pk} — {self.fournisseur_id} ({self.get_statut_display()})'


# ── XQHS7 — Analyse structurée 5-Pourquoi / 8D sur NCR ──────────────────────

class AnalyseNcr(models.Model):
    """Analyse structurée d'une NCR : chaîne 5-Pourquoi et/ou rapport 8D.

    ``cinq_pourquoi`` — liste ordonnée JSON de ``{'pourquoi': str, 'reponse':
    str}`` (bornée à 5 entrées par ``clean()``). ``huit_d`` — dict JSON des 8
    disciplines D1 à D8, chacune ``{'texte': str, 'statut': str}`` ; D5/D6
    réutilisent les CAPA existantes de la NCR (pas dupliquées ici, juste
    référencées par le texte/lien côté rendu PDF).

    Un seul enregistrement par NCR (OneToOne). Multi-société via ``company``
    posée côté serveur. Entièrement additif.
    """
    MAX_POURQUOI = 5
    DISCIPLINES = [
        'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8',
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_analyses_ncr',
        verbose_name='Société',
    )
    non_conformite = models.OneToOneField(
        NonConformite,
        on_delete=models.CASCADE,
        related_name='analyse',
        verbose_name='Non-conformité',
    )
    cinq_pourquoi = models.JSONField(
        default=list, blank=True, verbose_name='5-Pourquoi')
    huit_d = models.JSONField(
        default=dict, blank=True, verbose_name='8D')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Analyse NCR (5-Pourquoi / 8D)'
        verbose_name_plural = 'Analyses NCR (5-Pourquoi / 8D)'
        ordering = ['-id']

    def clean(self):
        from django.core.exceptions import ValidationError
        if isinstance(self.cinq_pourquoi, list) \
                and len(self.cinq_pourquoi) > self.MAX_POURQUOI:
            raise ValidationError(
                f'Le 5-Pourquoi ne peut dépasser {self.MAX_POURQUOI} entrées.')

    def __str__(self):
        return f'Analyse NCR #{self.non_conformite_id}'


# ── XQHS9 — Registre des certifications (ISO / IMANOR NM) + audits ─────────

class Certification(models.Model):
    """Certificat détenu par l'entreprise (ISO 9001/14001/45001, NM…).

    Suit le ``referentiel``, l'``organisme`` certificateur (IMANOR, AFNOR…),
    le numéro/périmètre et la fenêtre de validité (``date_emission`` →
    ``date_expiration``). Relance à échéance : pattern ``prealerte``
    (QHSE38/XQHS8), ``statut_calcule`` dérive l'état réel.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    PREALERTE_JOURS_DEFAUT = 60

    class Referentiel(models.TextChoices):
        ISO_9001 = 'iso_9001', 'ISO 9001'
        ISO_14001 = 'iso_14001', 'ISO 14001'
        ISO_45001 = 'iso_45001', 'ISO 45001'
        NM = 'nm', 'NM (norme marocaine)'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        VALIDE = 'valide', 'Valide'
        A_RENOUVELER = 'a_renouveler', 'À renouveler'
        EXPIRE = 'expire', 'Expiré'
        SUSPENDU = 'suspendu', 'Suspendu'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_certifications',
        verbose_name='Société',
    )
    referentiel = models.CharField(
        max_length=15, choices=Referentiel.choices,
        default=Referentiel.ISO_9001, verbose_name='Référentiel')
    organisme = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Organisme')
    numero_certificat = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Numéro de certificat')
    perimetre = models.TextField(
        blank=True, default='', verbose_name='Périmètre')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    prealerte_jours = models.PositiveIntegerField(
        default=PREALERTE_JOURS_DEFAUT, verbose_name='Préalerte (jours)')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.VALIDE, verbose_name='Statut')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_certifications',
        verbose_name='Responsable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Certification'
        verbose_name_plural = 'Certifications'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'date_expiration'],
                name='qhse_certif_co_exp',
            ),
        ]

    def statut_calcule(self, today=None):
        """État réel à une date — même logique que ``ConformiteEnvironnementale``."""
        from datetime import timedelta

        from django.utils import timezone

        if today is None:
            today = timezone.localdate()
        if self.statut == self.Statut.SUSPENDU:
            return self.statut
        if self.date_expiration is None:
            return self.statut
        if self.date_expiration < today:
            return self.Statut.EXPIRE
        limite = today + timedelta(days=self.prealerte_jours or 0)
        if self.date_expiration <= limite:
            return self.Statut.A_RENOUVELER
        return self.statut

    def __str__(self):
        return f'{self.get_referentiel_display()} — {self.numero_certificat or "sans n°"}'


class AuditCertification(models.Model):
    """Audit d'un organisme certificateur sur une ``Certification``.

    ``type_etape`` (étape 1 / étape 2 / surveillance / renouvellement),
    l'auditeur externe et les constats. Un constat MAJEUR peut ouvrir une NCR
    liée via le service ``lever_ncr`` existant (réutilise
    ``lever_ncr_audit``-style : lien lâche ``ncr_id``).
    """
    class TypeEtape(models.TextChoices):
        ETAPE_1 = 'etape_1', 'Étape 1'
        ETAPE_2 = 'etape_2', 'Étape 2'
        SURVEILLANCE = 'surveillance', 'Surveillance'
        RENOUVELLEMENT = 'renouvellement', 'Renouvellement'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_audits_certification',
        verbose_name='Société',
    )
    certification = models.ForeignKey(
        Certification,
        on_delete=models.CASCADE,
        related_name='audits',
        verbose_name='Certification',
    )
    type_etape = models.CharField(
        max_length=15, choices=TypeEtape.choices,
        default=TypeEtape.SURVEILLANCE, verbose_name='Type')
    date_audit = models.DateField(
        null=True, blank=True, verbose_name="Date de l'audit")
    auditeur_externe = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Auditeur externe')
    constats = models.TextField(
        blank=True, default='', verbose_name='Constats')
    constat_majeur = models.BooleanField(
        default=False, verbose_name='Constat majeur')
    # Lien lâche vers la NCR levée pour un constat majeur (même app, IntegerField
    # pour garder un couplage minimal — pattern ReponseCritere.ncr_id).
    ncr_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la NCR levée')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Audit de certification'
        verbose_name_plural = 'Audits de certification'
        ordering = ['-id']

    def __str__(self):
        return f'{self.get_type_etape_display()} — {self.certification}'


# ── XQHS10 — Programme d'audit interne annuel ───────────────────────────────

class ProgrammeAudit(models.Model):
    """Programme d'audit interne annuel.

    Regroupe les ``AuditPlanifie`` d'une ``annee`` civile pour une société.
    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        CLOS = 'clos', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_programmes_audit',
        verbose_name='Société',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Programme d'audit"
        verbose_name_plural = "Programmes d'audit"
        ordering = ['-annee']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'annee'],
                name='qhse_programmeaudit_co_annee_uniq',
            ),
        ]

    def __str__(self):
        return f'Programme audit {self.annee}'


class AuditPlanifie(models.Model):
    """Audit planifié au sein d'un ``ProgrammeAudit`` (avant instanciation).

    ``responsable_domaine`` sert de GARDE D'INDÉPENDANCE ADVISORY : si
    ``auditeur == responsable_domaine``, ``independance_ok`` renvoie ``False``
    (avertissement, jamais un blocage dur). L'instanciation en ``Audit`` réel se
    fait via le service ``instancier_audit_planifie`` (garde le lien via
    ``audit`` — idempotent).
    """
    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        REALISE = 'realise', 'Réalisé'
        EN_RETARD = 'en_retard', 'En retard'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_audits_planifies',
        verbose_name='Société',
    )
    programme = models.ForeignKey(
        ProgrammeAudit,
        on_delete=models.CASCADE,
        related_name='audits_planifies',
        verbose_name='Programme',
    )
    processus_domaine = models.CharField(
        max_length=255, verbose_name='Processus / domaine audité')
    grille = models.ForeignKey(
        GrilleAudit,
        on_delete=models.PROTECT,
        related_name='qhse_audits_planifies',
        verbose_name="Grille d'audit",
    )
    date_cible = models.DateField(
        null=True, blank=True, verbose_name='Date cible')
    auditeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_audits_planifies_conduits',
        verbose_name='Auditeur assigné',
    )
    responsable_domaine = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_audits_planifies_domaines',
        verbose_name='Responsable du domaine',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PLANIFIE, verbose_name='Statut')
    # Lien vers l'Audit réel une fois instancié (QHSE16) — idempotence.
    audit = models.OneToOneField(
        Audit,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_planifie',
        verbose_name='Audit instancié',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Audit planifié'
        verbose_name_plural = 'Audits planifiés'
        ordering = ['date_cible', 'id']

    def independance_ok(self):
        """Garde d'indépendance ADVISORY : ``False`` si l'auditeur est aussi le
        responsable du domaine audité (avertissement, jamais bloquant)."""
        if self.auditeur_id is None or self.responsable_domaine_id is None:
            return True
        return self.auditeur_id != self.responsable_domaine_id

    def __str__(self):
        return f'{self.processus_domaine} — {self.date_cible or "sans date"}'


# ── XQHS11 — Référentiel de clauses ISO multi-norme (seedable) ─────────────

class ClauseNorme(models.Model):
    """Clause d'un référentiel ISO (9001/14001/45001/NM), seedable.

    Structure HLS partagée (High Level Structure — commune aux normes de
    management ISO récentes) : une même clause numérotée (ex. « 8.5.1 ») peut
    exister sous plusieurs référentiels pour qu'une même preuve serve
    plusieurs normes. Company-scopé pour rester cohérent avec le reste de
    l'app (pas de référentiel global partagé entre sociétés).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_clauses_norme',
        verbose_name='Société',
    )
    referentiel = models.CharField(
        max_length=15,
        choices=[
            ('9001', 'ISO 9001'), ('14001', 'ISO 14001'),
            ('45001', 'ISO 45001'), ('nm', 'NM'), ('autre', 'Autre'),
        ],
        verbose_name='Référentiel')
    numero = models.CharField(max_length=20, verbose_name='Numéro de clause')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Clause de norme'
        verbose_name_plural = 'Clauses de norme'
        ordering = ['referentiel', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'referentiel', 'numero'],
                name='qhse_clausenorme_co_ref_num_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.referentiel}:{self.numero} — {self.intitule}'


# ── XQHS12 — Revue de direction + comité de sécurité et d'hygiène ──────────

class ReunionQhse(models.Model):
    """Réunion QHSE structurée : revue de direction / CSH / réunion HSE.

    ``participants`` — liste JSON de références LÂCHES aux employés (ids
    ``rh.DossierEmploye``, jamais un import cross-app de modèle) OU des noms
    texte libres. ``checklist_revue_direction`` — pour ``revue_direction``
    uniquement : entrées obligatoires ISO 9.3 (booléens « couvert »), exigées
    avant de pouvoir clore (cf. ``services.cloturer_reunion_qhse``).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class TypeReunion(models.TextChoices):
        REVUE_DIRECTION = 'revue_direction', 'Revue de direction'
        COMITE_HYGIENE_SECURITE = (
            'comite_hygiene_securite', "Comité d'hygiène et de sécurité")
        REUNION_HSE = 'reunion_hse', 'Réunion HSE'

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        TENUE = 'tenue', 'Tenue'
        CLOTUREE = 'cloturee', 'Clôturée'

    # Checklist des entrées obligatoires ISO 9.3 pour une revue de direction.
    CHECKLIST_REVUE_DIRECTION_CLES = [
        'resultats_audits', 'kpi', 'retours_clients', 'statut_capa',
        'ressources',
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_reunions',
        verbose_name='Société',
    )
    type_reunion = models.CharField(
        max_length=25, choices=TypeReunion.choices,
        default=TypeReunion.REUNION_HSE, verbose_name='Type')
    date_reunion = models.DateField(
        null=True, blank=True, verbose_name='Date')
    participants = models.JSONField(
        default=list, blank=True, verbose_name='Participants')
    ordre_du_jour = models.TextField(
        blank=True, default='', verbose_name='Ordre du jour')
    pv = models.TextField(blank=True, default='', verbose_name='PV / minutes')
    # Références LÂCHES aux pièces jointes (records.Attachment).
    attachment_ids = models.JSONField(
        default=list, blank=True, verbose_name='IDs pièces jointes')
    # ISO 9.3 — checklist des entrées obligatoires (revue_direction only).
    # dict {cle: bool} — clés = CHECKLIST_REVUE_DIRECTION_CLES.
    checklist_revue_direction = models.JSONField(
        default=dict, blank=True, verbose_name='Checklist ISO 9.3')
    # CSH — rapport annuel (obligations Code du travail ≥50 salariés).
    rapport_annuel = models.TextField(
        blank=True, default='', verbose_name='Rapport annuel (CSH)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PLANIFIEE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réunion QHSE'
        verbose_name_plural = 'Réunions QHSE'
        ordering = ['-date_reunion', '-id']
        indexes = [
            models.Index(
                fields=['company', 'type_reunion'],
                name='qhse_reunion_co_type',
            ),
        ]

    def checklist_9_3_complete(self):
        """True si toutes les entrées obligatoires ISO 9.3 sont cochées
        « couvert ». N'a de sens que pour ``revue_direction``."""
        checklist = self.checklist_revue_direction or {}
        return all(
            checklist.get(cle) is True
            for cle in self.CHECKLIST_REVUE_DIRECTION_CLES)

    def __str__(self):
        return f'{self.get_type_reunion_display()} — {self.date_reunion or "sans date"}'


class DecisionReunion(models.Model):
    """Décision prise lors d'une ``ReunionQhse``.

    Une décision peut « spawner » une CAPA liée via le service existant
    (``creer_capa_depuis_decision`` — réutilise ``ActionCorrectivePreventive``,
    rattachée à une NCR de convenance créée à cet effet OU laissée sans CAPA
    si l'appelant ne le demande pas).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_decisions_reunion',
        verbose_name='Société',
    )
    reunion = models.ForeignKey(
        ReunionQhse,
        on_delete=models.CASCADE,
        related_name='decisions',
        verbose_name='Réunion',
    )
    texte = models.TextField(verbose_name='Décision')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_decisions_reunion',
        verbose_name='Responsable',
    )
    # Lien lâche vers la CAPA créée depuis cette décision (même app,
    # IntegerField pour couplage minimal — pattern ReponseCritere.ncr_id).
    capa_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la CAPA créée')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Décision de réunion'
        verbose_name_plural = 'Décisions de réunion'
        ordering = ['-id']

    def __str__(self):
        return self.texte[:80]


# ── XQHS13 — Objectifs & cibles QHSE/ESG avec revues périodiques ───────────

class ObjectifQhse(models.Model):
    """Objectif chiffré QHSE/ESG avec baseline, cible et échéance (ISO 6.2).

    ``indicateur_esg`` — lien optionnel vers un ``IndicateurESG`` existant
    (même app) pour réutiliser sa mesure ; sinon ``indicateur_libre`` texte.
    ``sens_amelioration`` détermine si « mieux » = valeur qui monte ou qui
    descend (ex. accidents → baisse, taux de satisfaction → hausse).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Domaine(models.TextChoices):
        QUALITE = 'qualite', 'Qualité'
        SECURITE = 'securite', 'Sécurité'
        ENVIRONNEMENT = 'environnement', 'Environnement'
        ESG = 'esg', 'ESG'

    class SensAmelioration(models.TextChoices):
        HAUSSE = 'hausse', 'Hausse souhaitée'
        BAISSE = 'baisse', 'Baisse souhaitée'

    class Frequence(models.TextChoices):
        MENSUELLE = 'mensuelle', 'Mensuelle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        SEMESTRIELLE = 'semestrielle', 'Semestrielle'
        ANNUELLE = 'annuelle', 'Annuelle'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_objectifs',
        verbose_name='Société',
    )
    domaine = models.CharField(
        max_length=15, choices=Domaine.choices,
        default=Domaine.QUALITE, verbose_name='Domaine')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    indicateur_libre = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Indicateur (libre)')
    indicateur_esg = models.ForeignKey(
        IndicateurESG,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='objectifs',
        verbose_name='Indicateur ESG lié',
    )
    valeur_baseline = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True, verbose_name='Valeur de référence (baseline)')
    annee_baseline = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Année de base')
    valeur_cible = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True, verbose_name='Valeur cible')
    echeance = models.DateField(
        null=True, blank=True, verbose_name='Échéance')
    sens_amelioration = models.CharField(
        max_length=10, choices=SensAmelioration.choices,
        default=SensAmelioration.HAUSSE, verbose_name="Sens d'amélioration")
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_objectifs',
        verbose_name='Responsable',
    )
    frequence_revue = models.CharField(
        max_length=15, choices=Frequence.choices,
        default=Frequence.TRIMESTRIELLE, verbose_name='Fréquence de revue')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Objectif QHSE'
        verbose_name_plural = 'Objectifs QHSE'
        ordering = ['-id']

    def __str__(self):
        return self.intitule


class RevueObjectif(models.Model):
    """Revue périodique d'un ``ObjectifQhse`` : valeur constatée + verdict.

    ``atteint`` est dérivé automatiquement au ``save()`` depuis
    ``valeur_constatee`` vs ``objectif.valeur_cible`` et
    ``objectif.sens_amelioration`` (``None`` sans cible/valeur — pas encore
    calculable).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_revues_objectif',
        verbose_name='Société',
    )
    objectif = models.ForeignKey(
        ObjectifQhse,
        on_delete=models.CASCADE,
        related_name='revues',
        verbose_name='Objectif',
    )
    periode = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Période')
    date_revue = models.DateField(
        null=True, blank=True, verbose_name='Date de revue')
    valeur_constatee = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True, verbose_name='Valeur constatée')
    atteint = models.BooleanField(
        null=True, blank=True, verbose_name='Atteint')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Revue d'objectif"
        verbose_name_plural = "Revues d'objectif"
        ordering = ['-date_revue', '-id']

    def calculer_atteint(self):
        """``True``/``False``/``None`` selon la valeur constatée vs la cible et
        le sens d'amélioration de l'objectif parent."""
        cible = self.objectif.valeur_cible
        if cible is None or self.valeur_constatee is None:
            return None
        if self.objectif.sens_amelioration == \
                ObjectifQhse.SensAmelioration.BAISSE:
            return self.valeur_constatee <= cible
        return self.valeur_constatee >= cible

    def save(self, *args, **kwargs):
        self.atteint = self.calculer_atteint()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.objectif.intitule} — {self.periode or "sans période"}'


# ── XQHS14 — Registre des risques & opportunités SMQ + contexte (clause 4) ──

class RisqueOpportunite(models.Model):
    """Risque ou opportunité niveau ENTREPRISE/processus (ISO 6.1).

    Distinct du document unique opérationnel chantier (``EvaluationRisque``) :
    ce registre couvre le niveau SMQ (management system) — processus,
    fournisseurs, marché… Cotation ``probabilite × gravite`` sur la même
    échelle 1–5 que le document unique, à la fois INHÉRENTE (avant traitement)
    et RÉSIDUELLE (après traitement) pour tracer l'effet des actions.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    NIVEAU_MIN = 1
    NIVEAU_MAX = 5

    class Type(models.TextChoices):
        RISQUE = 'risque', 'Risque'
        OPPORTUNITE = 'opportunite', 'Opportunité'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_risques_opportunites',
        verbose_name='Société',
    )
    type_ro = models.CharField(
        max_length=15, choices=Type.choices,
        default=Type.RISQUE, verbose_name='Type')
    processus = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Processus concerné')
    description = models.TextField(verbose_name='Description')
    probabilite_inherente = models.PositiveSmallIntegerField(
        default=1, verbose_name='Probabilité inhérente (1–5)')
    gravite_inherente = models.PositiveSmallIntegerField(
        default=1, verbose_name='Gravité inhérente (1–5)')
    criticite_inherente = models.PositiveSmallIntegerField(
        default=1, verbose_name='Criticité inhérente')
    probabilite_residuelle = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Probabilité résiduelle (1–5)')
    gravite_residuelle = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Gravité résiduelle (1–5)')
    criticite_residuelle = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Criticité résiduelle')
    actions_traitement = models.TextField(
        blank=True, default='', verbose_name='Actions de traitement')
    date_revue = models.DateField(
        null=True, blank=True, verbose_name='Date de revue')
    frequence_revue_jours = models.PositiveIntegerField(
        default=180, verbose_name='Fréquence de revue (jours)')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_risques_opportunites',
        verbose_name='Responsable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Risque / opportunité'
        verbose_name_plural = 'Risques / opportunités'
        ordering = ['-id']

    def save(self, *args, **kwargs):
        self.criticite_inherente = (
            (self.probabilite_inherente or 1) * (self.gravite_inherente or 1))
        if self.probabilite_residuelle is not None \
                and self.gravite_residuelle is not None:
            self.criticite_residuelle = (
                self.probabilite_residuelle * self.gravite_residuelle)
        else:
            self.criticite_residuelle = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_type_ro_display()} — {self.description[:60]}'


class RisqueOpportuniteCapa(models.Model):
    """Lien (M2M explicite) entre un ``RisqueOpportunite`` et une CAPA
    (traitement lié — un même risque peut avoir plusieurs actions)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_risque_capa',
        verbose_name='Société',
    )
    risque_opportunite = models.ForeignKey(
        RisqueOpportunite,
        on_delete=models.CASCADE,
        related_name='capa_liees',
        verbose_name='Risque / opportunité',
    )
    capa = models.ForeignKey(
        ActionCorrectivePreventive,
        on_delete=models.CASCADE,
        related_name='risques_opportunites_liees',
        verbose_name='CAPA',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'CAPA liée à un risque/opportunité'
        verbose_name_plural = 'CAPA liées à des risques/opportunités'
        constraints = [
            models.UniqueConstraint(
                fields=['risque_opportunite', 'capa'],
                name='qhse_risque_capa_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.risque_opportunite_id} ↔ CAPA {self.capa_id}'


class PartieInteressee(models.Model):
    """Partie intéressée pertinente pour le SMQ (clause 4.2 ISO).

    ``partie`` (ex. « Client », « Fournisseur », « Autorité locale »),
    ``attentes`` et une ``pertinence`` qualitative.
    """
    class Pertinence(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        FORTE = 'forte', 'Forte'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_parties_interessees',
        verbose_name='Société',
    )
    partie = models.CharField(max_length=255, verbose_name='Partie')
    attentes = models.TextField(
        blank=True, default='', verbose_name='Attentes / exigences')
    pertinence = models.CharField(
        max_length=10, choices=Pertinence.choices,
        default=Pertinence.MOYENNE, verbose_name='Pertinence SMQ')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Partie intéressée'
        verbose_name_plural = 'Parties intéressées'
        ordering = ['-id']

    def __str__(self):
        return self.partie


class ContexteOrganisation(models.Model):
    """Contexte/enjeux de l'organisation (clause 4.1 ISO) — 1 par société.

    ``swot`` — texte structuré (forces/faiblesses/opportunités/menaces) ;
    ``perimetre_smq`` — périmètre du système de management inclus.
    """
    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_contexte_organisation',
        verbose_name='Société',
    )
    swot = models.TextField(blank=True, default='', verbose_name='SWOT')
    perimetre_smq = models.TextField(
        blank=True, default='', verbose_name='Périmètre du SMQ')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Contexte de l'organisation"
        verbose_name_plural = "Contextes de l'organisation"

    def __str__(self):
        return f'Contexte — {self.company_id}'


# ── XQHS15 — Diffusion & accusé de lecture des procédures qualité ──────────

class DiffusionProcedure(models.Model):
    """Diffusion d'une version de ``ProcedureQualite`` à une population cible.

    ``population_cible`` — JSON, soit une liste d'ids utilisateur, soit un
    rôle (ex. ``{'role': 'technicien'}``) — reste texte/JSON libre pour rester
    additif sans dépendre d'un modèle de rôle particulier. Chaque diffusion
    matérialise ses ``AccuseLecture`` via le service
    ``diffuser_procedure``/``ajouter_lecteurs``.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_diffusions_procedure',
        verbose_name='Société',
    )
    procedure = models.ForeignKey(
        ProcedureQualite,
        on_delete=models.CASCADE,
        related_name='diffusions',
        verbose_name='Procédure (version)',
    )
    population_cible = models.JSONField(
        default=dict, blank=True, verbose_name='Population cible')
    date_diffusion = models.DateTimeField(
        auto_now_add=True, verbose_name='Diffusée le')

    class Meta:
        verbose_name = 'Diffusion de procédure'
        verbose_name_plural = 'Diffusions de procédure'
        ordering = ['-id']

    def __str__(self):
        return f'Diffusion {self.procedure} — {self.date_diffusion}'


class AccuseLecture(models.Model):
    """Accusé de lecture d'un utilisateur pour une ``DiffusionProcedure``.

    ``lu_le`` = « signature » : confirmation datée SERVEUR (jamais une date
    saisie par le client). Unique ``(diffusion, user)`` — un utilisateur ne
    peut accuser lecture qu'une fois par diffusion (idempotent).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_accuses_lecture',
        verbose_name='Société',
    )
    diffusion = models.ForeignKey(
        DiffusionProcedure,
        on_delete=models.CASCADE,
        related_name='accuses_lecture',
        verbose_name='Diffusion',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='qhse_accuses_lecture',
        verbose_name='Utilisateur',
    )
    lu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Lu le (signature serveur)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Accusé de lecture'
        verbose_name_plural = 'Accusés de lecture'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['diffusion', 'user'],
                name='qhse_accuselecture_diffusion_user_uniq',
            ),
        ]

    def __str__(self):
        statut = 'lu' if self.lu_le else 'en attente'
        return f'{self.user_id} — {statut}'


# ── XQHS16 — Signalement QR public sans compte (danger/incident chantier) ──

def _default_qr_token():
    import secrets
    return secrets.token_urlsafe(24)


class LienSignalementPublic(models.Model):
    """Lien public tokenisé (QR) par chantier pour un signalement anonyme
    (danger/incident) SANS compte ERP (XQHS16).

    Pattern des liens publics tokenisés déjà en place (``ventes.ShareLink``,
    ``ged`` partage/dépôt) : le jeton (long, imprévisible) est l'UNIQUE secret
    d'accès — la société et le chantier sont résolus DEPUIS le jeton, JAMAIS
    depuis le corps de requête. Révocable (``actif=False``) ; pas d'expiration
    fixe (un QR imprimé reste valable tant que le chantier est actif) sauf si
    l'utilisateur le révoque manuellement.

    ``responsable_hse`` optionnel : notifié (best-effort) à chaque
    signalement reçu via ce lien.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_liens_signalement',
        verbose_name='Société',
    )
    # Référence LÂCHE au chantier (installations.Chantier) par id : jamais un
    # import cross-app de modèle.
    chantier_id = models.PositiveIntegerField(
        verbose_name='ID du chantier')
    token = models.CharField(
        max_length=64, unique=True, default=_default_qr_token,
        editable=False, verbose_name='Jeton')
    libelle = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Libellé (ex. nom du chantier)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    responsable_hse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_liens_signalement_responsable',
        verbose_name='Responsable HSE à notifier',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_liens_signalement_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Lien de signalement public (QR)'
        verbose_name_plural = 'Liens de signalement public (QR)'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['token'], name='qhse_liensig_token'),
            models.Index(
                fields=['company', 'chantier_id'],
                name='qhse_liensig_co_chant',
            ),
        ]

    def __str__(self):
        return f'Lien signalement — {self.libelle or self.chantier_id}'


class SignalementPublic(models.Model):
    """Signalement reçu via un ``LienSignalementPublic`` (XQHS16).

    Créé par un tiers SANS compte ERP (sous-traitant, riverain). L'auteur est
    facultatif (``nom``/``telephone`` vides = anonyme). ``source`` reste
    toujours ``qr_public`` pour distinguer ces entrées des signalements
    internes classiques (registre ``Incident``).

    Multi-société via ``company`` posée côté serveur (résolue depuis le lien,
    jamais depuis le corps de requête). Entièrement additif.
    """
    class Type(models.TextChoices):
        DANGER = 'danger', 'Danger'
        INCIDENT = 'incident', 'Incident'

    class Source(models.TextChoices):
        QR_PUBLIC = 'qr_public', 'QR public'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_signalements_publics',
        verbose_name='Société',
    )
    lien = models.ForeignKey(
        LienSignalementPublic,
        on_delete=models.CASCADE,
        related_name='signalements',
        verbose_name='Lien',
    )
    type_signalement = models.CharField(
        max_length=10, choices=Type.choices,
        default=Type.DANGER, verbose_name='Type')
    description = models.TextField(verbose_name='Description')
    photo_url = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Photo (URL)')
    nom = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Nom (facultatif)')
    telephone = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Téléphone (facultatif)')
    source = models.CharField(
        max_length=15, choices=Source.choices,
        default=Source.QR_PUBLIC, verbose_name='Source')
    # Référence lâche : l'incident QHSE créé à partir de ce signalement, une
    # fois traité côté HSE (intra-app, FK directe possible).
    incident = models.ForeignKey(
        'Incident',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='signalements_publics',
        verbose_name='Incident lié',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Signalement public (QR)'
        verbose_name_plural = 'Signalements publics (QR)'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'type_signalement'],
                name='qhse_sigpub_co_type',
            ),
        ]

    @property
    def anonyme(self):
        return not self.nom and not self.telephone

    def __str__(self):
        return f'Signalement {self.get_type_signalement_display()} ({self.lien_id})'


# ── XQHS17 — Observations sécurité comportementales (BBS) ──────────────────

class ObservationSecurite(models.Model):
    """Observation comportementale sécurité (Behavior-Based Safety, XQHS17).

    Saisie rapide (mobile-friendly) d'une observation TERRAIN — sûre ou à
    risque — distincte du presqu'accident (``rh.PresquAccident``, RH) et du
    registre d'incident (``qhse.Incident``, événement déjà survenu). La BBS
    alimente la prévention EN AMONT, avant tout événement.

    ``categorie`` réutilise les familles ``CodeDefaut`` là où c'est pertinent
    (EPI/hauteur/électrique/manutention/environnement/autre) pour rester
    cohérent avec le Pareto qualité existant, sans dépendre d'un FK vers
    ``CodeDefaut`` (catégorie fixe, pas un référentiel éditable ici).

    Une observation À RISQUE peut être convertie en un clic en CAPA (liée à
    une NCR minimale créée pour l'occasion) ou en NCR directe — voir
    ``services.convertir_observation_en_capa`` /
    ``convertir_observation_en_ncr``.

    Le rattachement au chantier se fait par référence LÂCHE (``chantier_id``).
    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Categorie(models.TextChoices):
        EPI = 'epi', 'EPI'
        HAUTEUR = 'hauteur', 'Travail en hauteur'
        ELECTRIQUE = 'electrique', 'Électrique'
        MANUTENTION = 'manutention', 'Manutention'
        ENVIRONNEMENT = 'environnement', 'Environnement'
        AUTRE = 'autre', 'Autre'

    class TypeObservation(models.TextChoices):
        SUR = 'sur', 'Sûr'
        A_RISQUE = 'a_risque', 'À risque'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_observations_securite',
        verbose_name='Société',
    )
    date_observation = models.DateField(
        null=True, blank=True, verbose_name="Date de l'observation")
    # Référence LÂCHE au chantier (installations.Chantier) par id.
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du chantier')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices,
        default=Categorie.AUTRE, verbose_name='Catégorie')
    type_observation = models.CharField(
        max_length=10, choices=TypeObservation.choices,
        default=TypeObservation.SUR, verbose_name="Type d'observation")
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    feedback_donne = models.BooleanField(
        default=False, verbose_name='Feedback donné sur place')
    observateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_observations_securite',
        verbose_name='Observateur',
    )
    # Conversion en un clic — trace vers l'action/NCR née de cette observation
    # (intra-app, FK directe). NULL tant qu'aucune conversion n'a eu lieu.
    action_liee = models.ForeignKey(
        'ActionCorrectivePreventive',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='observations_origine',
        verbose_name='CAPA liée',
    )
    non_conformite_liee = models.ForeignKey(
        'NonConformite',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='observations_origine',
        verbose_name='NCR liée',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Observation sécurité (BBS)'
        verbose_name_plural = 'Observations sécurité (BBS)'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'type_observation'],
                name='qhse_obssec_co_type',
            ),
            models.Index(
                fields=['company', 'observateur'],
                name='qhse_obssec_co_observ',
            ),
        ]

    def __str__(self):
        return f'{self.get_type_observation_display()} — {self.get_categorie_display()}'


# ── XQHS18 — Exercices d'urgence (drills) rattachés aux plans d'urgence ─────

class ExerciceUrgence(models.Model):
    """Exercice d'urgence (évacuation/incendie/déversement) rattaché à un
    ``PlanUrgence`` (XQHS18, exigence ISO 45001 8.2).

    Trace la planification (``date_prevue``) puis la réalisation
    (``date_realisee``, ``duree_evacuation_secondes`` chronométrée,
    participants, observations/écarts). Un écart constaté peut créer une CAPA
    liée (voir ``services.creer_capa_depuis_ecart_exercice``).

    ``frequence_mois`` sur le plan lui-même détermine la cadence cible ; le
    sélecteur ``exercices_dus`` (pattern QHSE38/QHSE12) identifie les plans en
    retard de leur prochain exercice.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Type(models.TextChoices):
        EVACUATION = 'evacuation', 'Évacuation'
        INCENDIE = 'incendie', 'Incendie'
        DEVERSEMENT = 'deversement', 'Déversement'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        REALISE = 'realise', 'Réalisé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_exercices_urgence',
        verbose_name='Société',
    )
    plan = models.ForeignKey(
        PlanUrgence,
        on_delete=models.CASCADE,
        related_name='exercices',
        verbose_name="Plan d'urgence",
    )
    type_exercice = models.CharField(
        max_length=15, choices=Type.choices,
        default=Type.EVACUATION, verbose_name="Type d'exercice")
    date_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date prévue')
    date_realisee = models.DateField(
        null=True, blank=True, verbose_name='Date réalisée')
    duree_evacuation_secondes = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Durée d'évacuation chronométrée (secondes)")
    nb_participants = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Nombre de participants')
    participants_libre = models.TextField(
        blank=True, default='', verbose_name='Participants (liste libre)')
    observations = models.TextField(
        blank=True, default='', verbose_name='Observations / écarts')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PLANIFIE, verbose_name='Statut')
    # Écart → CAPA liée (intra-app, FK directe). NULL tant qu'aucune CAPA
    # n'a été créée à partir de cet exercice.
    capa_liee = models.ForeignKey(
        'ActionCorrectivePreventive',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='exercices_urgence_origine',
        verbose_name='CAPA liée',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Exercice d'urgence"
        verbose_name_plural = "Exercices d'urgence"
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'plan'],
                name='qhse_exeurg_co_plan',
            ),
            models.Index(
                fields=['company', 'statut'],
                name='qhse_exeurg_co_statut',
            ),
        ]

    def __str__(self):
        return f'{self.get_type_exercice_display()} — {self.plan.titre}'


# ── XQHS20 — Registre des aspects & impacts environnementaux (ISO 14001) ──

class AspectEnvironnemental(models.Model):
    """Aspect environnemental d'une activité + cotation de significativité
    (XQHS20, ISO 14001 6.1.2).

    Chaque entrée décrit une ``activite`` (transport, pose, stockage
    batteries, déchets chantier…), son ``aspect`` (ce qui interagit avec
    l'environnement) et son ``impact`` (la conséquence). La cotation
    ``frequence`` × ``gravite`` (1 à 5 chacune) donne ``criticite`` (dérivée,
    jamais stockée) ; ``significatif`` est calculé côté serveur au-delà du
    ``seuil_significativite`` configurable par société (défaut 12).

    Lien optionnel vers une ``ProcedureQualite`` (contrôle opérationnel
    documenté) et vers un ``ObjectifQhse`` (XQHS13, objectif de réduction).
    ``date_revue`` + relance suivent le pattern QHSE38/QHSE12.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    SEUIL_SIGNIFICATIVITE_DEFAUT = 12

    class Condition(models.TextChoices):
        NORMALE = 'normale', 'Normale'
        ANORMALE = 'anormale', 'Anormale'
        URGENCE = 'urgence', "Urgence"

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_aspects_environnementaux',
        verbose_name='Société',
    )
    activite = models.CharField(max_length=255, verbose_name='Activité')
    aspect = models.CharField(max_length=255, verbose_name='Aspect')
    impact = models.CharField(max_length=255, verbose_name='Impact')
    condition = models.CharField(
        max_length=10, choices=Condition.choices,
        default=Condition.NORMALE, verbose_name='Condition')
    frequence = models.PositiveSmallIntegerField(
        default=1, verbose_name='Fréquence (1-5)')
    gravite = models.PositiveSmallIntegerField(
        default=1, verbose_name='Gravité (1-5)')
    seuil_significativite = models.PositiveIntegerField(
        default=SEUIL_SIGNIFICATIVITE_DEFAUT,
        verbose_name='Seuil de significativité')
    controles_existants = models.TextField(
        blank=True, default='',
        verbose_name='Contrôles opérationnels existants')
    procedure = models.ForeignKey(
        'ProcedureQualite',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='aspects_environnementaux',
        verbose_name='Procédure liée',
    )
    objectif = models.ForeignKey(
        'ObjectifQhse',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='aspects_environnementaux',
        verbose_name='Objectif QHSE lié',
    )
    date_revue = models.DateField(
        null=True, blank=True, verbose_name='Date de revue')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Aspect environnemental'
        verbose_name_plural = 'Aspects environnementaux'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'condition'],
                name='qhse_aspenv_co_cond',
            ),
        ]

    @property
    def criticite(self):
        return (self.frequence or 0) * (self.gravite or 0)

    @property
    def significatif(self):
        return self.criticite >= (
            self.seuil_significativite or self.SEUIL_SIGNIFICATIVITE_DEFAUT)

    def __str__(self):
        return f'{self.activite} — {self.aspect}'


# ── XQHS21 — Relevés de consommation par site (élec/eau/carburant) ─────────

class ReleveConsommation(models.Model):
    """Relevé périodique de consommation d'un site (XQHS21).

    Capture la consommation MENSUELLE d'un site/groupe électrogène :
    électricité (kWh), gasoil/essence (L, groupes électrogènes de site — le
    carburant des VÉHICULES existe déjà dans ``flotte.PleinCarburant`` et est
    agrégé via le sélecteur ``flotte.selectors.consommation_annuelle_flotte``,
    jamais re-saisi ici), eau (m³).

    ``services.generer_lignes_bilan`` agrège les relevés d'une année (+ le
    carburant flotte) en ``LigneBilanCarbone`` pré-remplies, idempotent.

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class TypeEnergie(models.TextChoices):
        ELECTRICITE = 'electricite', 'Électricité (kWh)'
        GASOIL = 'gasoil', 'Gasoil (L)'
        ESSENCE = 'essence', 'Essence (L)'
        EAU = 'eau', 'Eau (m³)'

    class Source(models.TextChoices):
        FACTURE = 'facture', 'Facture'
        COMPTEUR = 'compteur', 'Compteur'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_releves_consommation',
        verbose_name='Société',
    )
    site_libelle = models.CharField(
        max_length=255, verbose_name='Site / libellé')
    type_energie = models.CharField(
        max_length=15, choices=TypeEnergie.choices,
        default=TypeEnergie.ELECTRICITE, verbose_name="Type d'énergie")
    # Mois-année de la période couverte (premier jour du mois par convention).
    periode = models.DateField(verbose_name='Période (mois)')
    quantite = models.DecimalField(
        max_digits=14, decimal_places=3, default=0, verbose_name='Quantité')
    source = models.CharField(
        max_length=15, choices=Source.choices,
        default=Source.FACTURE, verbose_name='Source')
    piece_jointe_url = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Pièce jointe (URL)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Relevé de consommation'
        verbose_name_plural = 'Relevés de consommation'
        ordering = ['-periode', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'site_libelle', 'type_energie', 'periode'],
                name='qhse_relconso_co_site_type_periode_uniq',
            )
        ]
        indexes = [
            models.Index(
                fields=['company', 'periode'],
                name='qhse_relconso_co_periode',
            ),
        ]

    def __str__(self):
        return (f'{self.site_libelle} — {self.get_type_energie_display()} '
                f'({self.periode:%Y-%m})')


# ── XQHS24 — Gestion du changement (MOC léger) ──────────────────────────────

class DemandeChangement(models.Model):
    """Demande de gestion du changement (MOC — Management Of Change léger,
    XQHS24) : trace un changement de procédé/équipement/organisation/document
    AVEC revue des risques avant mise en œuvre.

    Cycle de vie : ``brouillon`` → ``en_revue`` → ``approuve`` → ``deploye`` /
    (``clos`` | ``annule``). Un changement TEMPORAIRE porte
    ``date_expiration`` + relance de réversion (pattern
    ``Derogation``/``ConformiteEnvironnementale`` QHSE38). Les actions de mise
    en œuvre = CAPA liées (voir ``services.creer_capa_mise_en_oeuvre_moc``).

    Multi-société via ``company`` posée côté serveur. Entièrement additif.
    """
    class Type(models.TextChoices):
        PROCEDE = 'procede', 'Procédé'
        EQUIPEMENT = 'equipement', 'Équipement'
        ORGANISATION = 'organisation', 'Organisation'
        DOCUMENT = 'document', 'Document'

    class Impact(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYEN = 'moyen', 'Moyen'
        FORT = 'fort', 'Fort'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_REVUE = 'en_revue', 'En revue'
        APPROUVE = 'approuve', 'Approuvé'
        DEPLOYE = 'deploye', 'Déployé'
        CLOS = 'clos', 'Clos'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_demandes_changement',
        verbose_name='Société',
    )
    type_changement = models.CharField(
        max_length=15, choices=Type.choices,
        default=Type.PROCEDE, verbose_name='Type de changement')
    description = models.TextField(verbose_name='Description')
    justification = models.TextField(
        blank=True, default='', verbose_name='Justification')
    classification_impact = models.CharField(
        max_length=10, choices=Impact.choices,
        default=Impact.FAIBLE, verbose_name="Classification d'impact")
    # Revue des risques : texte libre + lien optionnel vers un DUERP existant
    # (même app, FK directe).
    revue_risques = models.TextField(
        blank=True, default='', verbose_name='Revue des risques')
    evaluation_risque = models.ForeignKey(
        'EvaluationRisque',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='demandes_changement',
        verbose_name='Évaluation des risques liée',
    )
    documents_formations_impactes = models.TextField(
        blank=True, default='', verbose_name='Documents/formations impactés')
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_demandes_changement_approuvees',
        verbose_name='Approbateur',
    )
    date_approbation = models.DateTimeField(
        null=True, blank=True, verbose_name="Date d'approbation")
    checklist_verification = models.TextField(
        blank=True, default='',
        verbose_name='Checklist de vérification avant déploiement')
    statut = models.CharField(
        max_length=15, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Changement TEMPORAIRE : date de retour à l'état antérieur + relance
    # (pattern Derogation/ConformiteEnvironnementale, QHSE38). NULL = permanent.
    est_temporaire = models.BooleanField(
        default=False, verbose_name='Changement temporaire')
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name='Date de réversion prévue')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Demande de changement (MOC)'
        verbose_name_plural = 'Demandes de changement (MOC)'
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='qhse_demchang_co_statut',
            ),
        ]

    def __str__(self):
        return f'{self.get_type_changement_display()} — {self.description[:40]}'


class DemandeChangementCapa(models.Model):
    """Lien (M2M explicite) entre une ``DemandeChangement`` et une CAPA
    (action de mise en œuvre — un même changement peut avoir plusieurs
    actions, pattern ``RisqueOpportuniteCapa``)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_demande_changement_capa',
        verbose_name='Société',
    )
    demande_changement = models.ForeignKey(
        DemandeChangement,
        on_delete=models.CASCADE,
        related_name='capa_liees',
        verbose_name='Demande de changement',
    )
    capa = models.ForeignKey(
        'ActionCorrectivePreventive',
        on_delete=models.CASCADE,
        related_name='demandes_changement_liees',
        verbose_name='CAPA',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'CAPA liée à une demande de changement'
        verbose_name_plural = 'CAPA liées à une demande de changement'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['demande_changement', 'capa'],
                name='qhse_demchangcapa_dem_capa_uniq',
            )
        ]

    def __str__(self):
        return f'{self.demande_changement_id} ↔ CAPA {self.capa_id}'


# ── XQHS26 — Veille réglementaire QHSE Maroc (revue périodique assistée) ────
# DECISION (utilité vs charge à valider par le fondateur). Version SOBRE sans
# dépendance externe : AUCUN scraping de source (règle CLAUDE.md #5 — ToS) ;
# les textes suivis sont saisis manuellement, seule la CADENCE de revue est
# automatisée (génération des revues dues, pas de collecte de contenu).

class VeilleReglementaire(models.Model):
    """Texte réglementaire QHSE suivi, avec cadence de revue périodique.

    Chaque texte suivi (loi, décret, arrêté, norme…) porte sa ``source``
    (Bulletin Officiel / ministère / organisme), une cadence de revue
    (``cadence_jours`` — 90 jours = trimestrielle par défaut) et une
    ``date_prochaine_revue`` qui avance à chaque revue conclue
    (``qhse.services.conclure_revue_veille``). Le ``responsable`` (HSE) est
    celui à qui la revue est assignée.

    Le lien optionnel ``registre_conformite`` rattache ce texte à une entrée du
    registre des exigences légales généralisé (XQHS8,
    ``ConformiteEnvironnementale``) : une revue conclut l'applicabilité et peut
    créer cette entrée si absente (``qhse.services.conclure_revue_veille``).

    Multi-société via ``company`` posée côté serveur (jamais lue du corps de
    requête). Entièrement additif.
    """
    CADENCE_JOURS_DEFAUT = 90  # trimestrielle

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_veilles_reglementaires',
        verbose_name='Société',
    )
    texte_suivi = models.CharField(
        max_length=255, verbose_name='Texte réglementaire suivi')
    source = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Source (BO / ministère)')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    cadence_jours = models.PositiveIntegerField(
        default=CADENCE_JOURS_DEFAUT, verbose_name='Cadence de revue (jours)')
    date_derniere_revue = models.DateField(
        null=True, blank=True, verbose_name='Dernière revue')
    date_prochaine_revue = models.DateField(
        null=True, blank=True, verbose_name='Prochaine revue')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='qhse_veilles_reglementaires',
        verbose_name='Responsable HSE',
    )
    # Lien optionnel vers le registre légal généralisé (XQHS8). Nullable : posé
    # par le service lors de la première revue applicable.
    registre_conformite = models.ForeignKey(
        ConformiteEnvironnementale,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='veilles_reglementaires',
        verbose_name='Entrée du registre légal liée',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Veille réglementaire'
        verbose_name_plural = 'Veilles réglementaires'
        ordering = ['date_prochaine_revue', '-id']
        indexes = [
            models.Index(
                fields=['company', 'date_prochaine_revue'],
                name='qhse_veille_co_prochaine',
            ),
        ]

    def __str__(self):
        return self.texte_suivi


class RevueVeilleReglementaire(models.Model):
    """Une revue périodique (occurrence) d'une ``VeilleReglementaire``.

    Générée automatiquement quand la revue est due
    (``qhse.services.generer_revues_veille_dues`` — idempotent : une seule
    revue ``a_faire`` ouverte à la fois par veille). Conclue via
    ``qhse.services.conclure_revue_veille`` : fixe ``conclusion``
    (applicable / non_applicable), avance ``date_prochaine_revue`` du parent,
    et lie/instancie le registre légal (XQHS8) si ``applicable``.
    """
    class Conclusion(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        APPLICABLE = 'applicable', 'Applicable'
        NON_APPLICABLE = 'non_applicable', 'Non applicable'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='qhse_revues_veille',
        verbose_name='Société',
    )
    veille = models.ForeignKey(
        VeilleReglementaire,
        on_delete=models.CASCADE,
        related_name='revues',
        verbose_name='Veille réglementaire',
    )
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name='Échéance de la revue')
    date_revue = models.DateField(
        null=True, blank=True, verbose_name='Date de revue effective')
    conclusion = models.CharField(
        max_length=15, choices=Conclusion.choices,
        default=Conclusion.A_FAIRE, verbose_name='Conclusion')
    impact_evalue = models.TextField(
        blank=True, default='', verbose_name='Impact évalué')
    resume_ia = models.TextField(
        blank=True, default='',
        verbose_name='Résumé IA du changement (XQHS25, optionnel)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Revue de veille réglementaire'
        verbose_name_plural = 'Revues de veille réglementaire'
        ordering = ['-date_echeance', '-id']
        indexes = [
            models.Index(
                fields=['company', 'conclusion'],
                name='qhse_revveille_co_concl',
            ),
        ]

    def __str__(self):
        return f'{self.veille.texte_suivi} — {self.get_conclusion_display()}'
