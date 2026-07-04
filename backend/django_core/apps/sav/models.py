"""
Après-vente — parc d'équipements (n° de série + horloges de garantie) et
tickets SAV (service après-vente).

Deux objets de première classe, queryables, accrochés au chantier
(Installation) :

  * Equipement : UNE ligne = UN appareil physique posé chez un client. Permet
    de répondre à « quels clients ont l'onduleur modèle X, et est-il encore
    sous garantie constructeur ». Les dates de fin de garantie sont CALCULÉES
    à partir de la durée structurée du produit (Produit.garantie_mois /
    garantie_production_mois) et de la date de pose — jamais inventées.

  * Ticket : une demande de SAV. Son cycle de vie est une liste FERMÉE, en
    ordre d'entonnoir, INDÉPENDANTE des étapes du lead (STAGES.py) et des
    statuts de document devis/facture. « Annulé » n'est PAS une étape : c'est
    un drapeau avec motif, comme « Perdu » sur un lead.

Le ticket sait si l'équipement qu'il concerne est sous garantie : quand un
équipement est lié, `sous_garantie_calcule` compare la date du jour à sa fin
de garantie ; sinon, la valeur manuelle (oui/non/à déterminer) est utilisée.

FG81 — SLA par ticket : horloge de première réponse + délai cible par société
(SavSlaSettings) + drapeaux sla_breach / sla_due_at calculés.
FG82 — Checklist de visite de maintenance (MaintenanceChecklistTemplate /
        Item) + TicketChecklistItem par ticket.
FG83 — Réclamation garantie fournisseur (WarrantyClaim, flux RMA).
FG85 — Jeton QR EQUIP:<id> sur Equipement + action étiquettes.
FG87 — Base de connaissances SAV (KbArticle).
FG90 — nb_tickets_12m (équipement « citron ») — computed, pas de colonne DB.
"""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .services import add_months


# ── FG81 — Réglages SLA par société ──────────────────────────────────────────

class SavSlaSettings(models.Model):
    """Délais SLA par société pour les tickets SAV (FG81).

    `sla_response_days` — délai de première réponse en jours calendaires
    (défaut 1). `sla_resolution_days` — délai de résolution cible (défaut 7).
    `sla_par_priorite` JSON optionnel : {"urgente": {"response": 0,
    "resolution": 1}, "haute": {...}} pour affiner par priorité.

    `sla_breach_enabled` : tant que False, aucune notification n'est émise —
    comportement d'aujourd'hui inchangé.
    """
    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='sav_sla_settings')
    sla_response_days = models.PositiveIntegerField(default=1)
    sla_resolution_days = models.PositiveIntegerField(default=7)
    sla_par_priorite = models.JSONField(null=True, blank=True)
    sla_breach_enabled = models.BooleanField(default=False)
    # XSAV4 — notifications client aux transitions du ticket (reçu / planifié /
    # résolu). Défaut OFF : comportement actuel inchangé tant que la société ne
    # l'active pas explicitement.
    notifications_client_sav = models.BooleanField(default=False)
    # XSAV5 — échéance SLA calculée en JOURS OUVRÉS (via core/calendar.py :
    # jours ouvrés + fériés marocains) plutôt qu'en jours calendaires. Défaut
    # OFF : comportement actuel (calendaire) inchangé tant que la société ne
    # l'active pas explicitement.
    sla_jours_ouvres = models.BooleanField(default=False)
    # ── XSAV6 — pré-alerte SLA (J-x) + escalade à la violation ──────────────
    # Nombre de jours AVANT sla_due_at où une pré-alerte est émise au
    # technicien assigné. 0 = pré-alerte désactivée (défaut : comportement
    # actuel inchangé, aucune pré-alerte n'a jamais existé).
    sla_warning_days = models.PositiveIntegerField(default=0)
    # Escalade au tier responsable/direction à la violation (en plus de la
    # notification technicien existante — FG81/scan_sla_breaches). OFF par
    # défaut : comportement actuel inchangé.
    escalade_activee = models.BooleanField(default=False)
    # XSAV9 — affectation automatique des tickets à la création (round-robin /
    # équilibrage de charge). Défaut OFF : comportement actuel inchangé (tout
    # ticket reste affecté à la main tant que la société ne l'active pas).
    affectation_auto_sav = models.BooleanField(default=False)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réglage SLA SAV'
        verbose_name_plural = 'Réglages SLA SAV'

    def __str__(self):
        return f'SLA SAV (société {self.company_id})'

    @classmethod
    def get(cls, company):
        obj, _ = cls.objects.get_or_create(company=company)
        return obj

    def days_for(self, priorite):
        """Renvoie (response_days, resolution_days) pour une priorité donnée."""
        par = self.sla_par_priorite or {}
        p = par.get(priorite, {})
        return (
            p.get('response', self.sla_response_days),
            p.get('resolution', self.sla_resolution_days),
        )


# ── FG82 — Checklist de visite de maintenance ─────────────────────────────────

class MaintenanceChecklistTemplate(models.Model):
    """Modèle de checklist pour les visites de maintenance préventive (FG82).

    Configurable dans Paramètres ; un modèle « Défaut » est semé
    automatiquement. Additif — aucune migration destructive.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='maintenance_checklist_templates')
    nom = models.CharField(max_length=120)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)  # Template système protégé.

    class Meta:
        ordering = ['nom']
        verbose_name = 'Modèle de checklist maintenance'
        verbose_name_plural = 'Modèles de checklist maintenance'

    def __str__(self):
        return self.nom


class MaintenanceChecklistItem(models.Model):
    """Étape d'un modèle de checklist de maintenance (FG82)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='maintenance_checklist_items')
    template = models.ForeignKey(
        MaintenanceChecklistTemplate, on_delete=models.CASCADE,
        related_name='items')
    cle = models.CharField(max_length=60)
    libelle = models.CharField(max_length=180)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'template', 'cle')]
        verbose_name = 'Étape de checklist maintenance'
        verbose_name_plural = 'Étapes de checklist maintenance'

    def __str__(self):
        return self.libelle


# ── Modèle Équipement ──────────────────────────────────────────────────────────

class Equipement(models.Model):
    class Statut(models.TextChoices):
        EN_SERVICE = 'en_service', 'En service'
        REMPLACE = 'remplace', 'Remplacé'
        HORS_SERVICE = 'hors_service', 'Hors service'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='equipements',
    )
    # Le modèle catalogue dont c'est une unité. PROTECT : on ne supprime pas un
    # produit encore référencé par du matériel posé.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT, related_name='equipements',
    )
    numero_serie = models.CharField(max_length=120, blank=True, null=True)
    # FG85 — jeton QR stable encodé sur l'étiquette (EQUIP:<id>).
    # Calculé à la création, jamais modifié.
    equipement_token = models.CharField(
        max_length=30, blank=True, default='',
        help_text="Jeton QR pour le scan de l'équipement (EQUIP:<id>).")
    # XSAV19 — jeton public opaque pour la page « Signaler un problème » sans
    # login (`/e/<public_token>`). DISTINCT de `equipement_token` (EQUIP:<id>
    # est devinable — jamais exposé sur une page publique). Généré LAZILY
    # via `ensure_public_token()` — nullable/blank : NULL tant que l'étiquette
    # publique n'a jamais été demandée (comportement actuel inchangé).
    public_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text=('Jeton public (XSAV19) pour la page de signalement sans '
                   'login. Généré via ensure_public_token().'))
    # Le chantier auquel l'appareil appartient (objet pivot de l'après-vente).
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='equipements',
    )
    date_pose = models.DateField(null=True, blank=True)

    # ── Horloges de garantie — CALCULÉES (date_pose + durée du produit). ──
    date_fin_garantie = models.DateField(null=True, blank=True)
    date_fin_garantie_production = models.DateField(null=True, blank=True)

    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.EN_SERVICE)
    note = models.TextField(blank=True, null=True)
    # Quand statut = « remplacé », lien optionnel vers le ticket qui a remplacé
    # l'appareil. SET_NULL : la suppression d'un ticket ne casse pas le parc.
    remplace_par_ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipements_remplaces',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='equipements_crees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # ── XSAV17 — entretien conditionnel à l'usage (heures/kWh) ──────────────
    # Seuil d'usage (heures de pompage OU kWh produits, selon le type de
    # relevé courant de l'équipement) entre deux entretiens préventifs. NULL
    # (défaut) = comportement actuel inchangé : l'entretien reste déclenché
    # UNIQUEMENT par le temps (ContratMaintenance).
    entretien_toutes_les_heures = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text=('Seuil de compteur (heures ou kWh) entre deux entretiens '
                   "préventifs. Vide = entretien déclenché par le temps "
                   "uniquement (comportement actuel)."))
    # Valeur du compteur au dernier entretien préventif généré par
    # franchissement de seuil (XSAV17) — sert de référence pour détecter le
    # PROCHAIN franchissement (anti-doublon, même esprit que
    # ContratMaintenance.derniere_visite / UnderperformanceFlag.is_open).
    dernier_entretien_compteur_valeur = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Équipement'
        verbose_name_plural = 'Équipements'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'produit']),
            models.Index(fields=['company', 'date_fin_garantie']),
        ]
        constraints = [
            # L636 — un n° de série est unique par société. Conditionnel : les
            # séries vides/NULL sont permises (un appareil peut être saisi sans
            # série) et n'entrent pas dans la contrainte.
            models.UniqueConstraint(
                fields=['company', 'numero_serie'],
                condition=models.Q(numero_serie__isnull=False)
                & ~models.Q(numero_serie=''),
                name='uniq_equipement_serie_par_societe',
            ),
        ]

    def __str__(self):
        return f"{self.numero_serie or '—'} ({self.produit_id})"

    def recompute_garanties(self):
        """Recalcule les deux dates de fin de garantie depuis date_pose + la
        durée structurée du produit. Laisse à None si la donnée manque — d'où
        « garantie non renseignée » côté affichage."""
        produit = self.produit
        gm = getattr(produit, 'garantie_mois', None)
        gpm = getattr(produit, 'garantie_production_mois', None)
        self.date_fin_garantie = (
            add_months(self.date_pose, gm)
            if (self.date_pose and gm) else None
        )
        self.date_fin_garantie_production = (
            add_months(self.date_pose, gpm)
            if (self.date_pose and gpm) else None
        )

    # ── XSAV13 — garantie légale de conformité (loi 31-08, biens meubles) ──
    # Durée légale marocaine, impérative et non négociable : 12 mois à
    # compter de la pose. CALCULÉE (comme les autres horloges), jamais
    # stockée — recalculée à la lecture depuis `date_pose`, cohérente avec
    # `recompute_garanties` pour la garantie commerciale.
    GARANTIE_LEGALE_MOIS = 12

    @property
    def date_fin_garantie_legale(self):
        """Fin de la garantie légale de conformité (loi 31-08) : date_pose +
        12 mois. None si `date_pose` n'est pas renseignée."""
        if not self.date_pose:
            return None
        return add_months(self.date_pose, self.GARANTIE_LEGALE_MOIS)

    @property
    def date_fin_garantie_effective(self):
        """XSAV13 — Fin de garantie EFFECTIVE = le MAX entre la garantie
        légale (loi 31-08) et la garantie commerciale constructeur — la plus
        favorable au client s'applique. None si aucune des deux n'est
        calculable (ni date_pose, ni durée constructeur renseignée)."""
        candidates = [
            d for d in (self.date_fin_garantie_legale, self.date_fin_garantie)
            if d is not None
        ]
        return max(candidates) if candidates else None

    @property
    def sous_garantie_legale_seule(self):
        """XSAV13 — True si SEULE la garantie légale (loi 31-08) couvre
        encore l'équipement — la garantie commerciale est absente ou déjà
        expirée. Sert à afficher la mention dédiée sur la fiche/PDF."""
        legale = self.date_fin_garantie_legale
        if legale is None:
            return False
        today = timezone.localdate()
        legale_active = today < legale
        commerciale_active = bool(
            self.date_fin_garantie and today < self.date_fin_garantie)
        return legale_active and not commerciale_active

    def set_token(self):
        """FG85 — pose le jeton EQUIP:<id> après la première sauvegarde."""
        token = f'EQUIP:{self.pk}'
        if self.equipement_token != token:
            self.equipement_token = token
            self.save(update_fields=['equipement_token'])

    def ensure_public_token(self):
        """XSAV19 — Génère (lazily) et renvoie le jeton public opaque.

        Idempotent : si déjà présent, le renvoie tel quel sans écriture.
        ``secrets.token_urlsafe(32)`` — espace de collision négligeable
        (2^192), même patron que ``Ticket.ensure_share_token`` (FG86)."""
        if self.public_token:
            return self.public_token
        token = secrets.token_urlsafe(32)
        self.public_token = token
        self.save(update_fields=['public_token'])
        return self.public_token


# ── XSAV17 — Relevés compteur (heures / kWh) ──────────────────────────────────

class ReleveCompteurEquipement(models.Model):
    """XSAV17 — Relevé de compteur d'usage d'un équipement client, saisi
    manuellement (heures de pompage ou kWh produits — décisif pour pompes et
    onduleurs, contrairement au parc entreprise FG341 qui a son propre
    compteur horaire machine).

    La valeur est CROISSANTE (compteur cumulatif, jamais un delta) : un
    relevé inférieur au dernier relevé enregistré pour le même équipement
    est refusé (protection contre une saisie erronée qui ferait « reculer »
    le compteur et fausserait la détection de franchissement de seuil)."""
    class Type(models.TextChoices):
        HEURES = 'heures', 'Heures'
        KWH = 'kwh', 'kWh'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='releves_compteur_equipement')
    equipement = models.ForeignKey(
        'sav.Equipement', on_delete=models.CASCADE,
        related_name='releves_compteur')
    type = models.CharField(max_length=10, choices=Type.choices)
    valeur = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Relevé compteur équipement'
        verbose_name_plural = 'Relevés compteur équipement'
        ordering = ['-date', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'equipement'],
                         name='sav_releve_co_equip_idx'),
        ]

    def __str__(self):
        return f'{self.equipement_id} — {self.valeur} {self.type}'


# ── Modèle Ticket ─────────────────────────────────────────────────────────────

class Ticket(models.Model):
    class Statut(models.TextChoices):
        NOUVEAU = 'nouveau', 'Nouveau'
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        RESOLU = 'resolu', 'Résolu'
        CLOTURE = 'cloture', 'Clôturé'

    # Ordre d'entonnoir (pour le tri des vues — JAMAIS alphabétique).
    STATUT_ORDER = [
        Statut.NOUVEAU,
        Statut.PLANIFIE,
        Statut.EN_COURS,
        Statut.RESOLU,
        Statut.CLOTURE,
    ]
    # Statuts considérés « ouverts » (file de service par défaut).
    OPEN_STATUTS = [Statut.NOUVEAU, Statut.PLANIFIE, Statut.EN_COURS]

    class Type(models.TextChoices):
        CORRECTIF = 'correctif', 'Correctif'
        PREVENTIF = 'preventif', 'Préventif'

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE = 'haute', 'Haute'
        URGENTE = 'urgente', 'Urgente'

    class SousGarantie(models.TextChoices):
        OUI = 'oui', 'Oui'
        NON = 'non', 'Non'
        A_DETERMINER = 'a_determiner', 'À déterminer'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tickets_sav',
    )
    reference = models.CharField(max_length=50)

    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT, related_name='tickets_sav',
    )
    # Le chantier concerné (optionnel : un ticket de maintenance préventive
    # peut être lié au seul client quand aucun chantier précis n'est ciblé).
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tickets',
    )
    # L'appareil précis, si connu. SET_NULL : pas de perte du ticket.
    equipement = models.ForeignKey(
        'sav.Equipement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tickets',
    )

    type = models.CharField(
        max_length=12, choices=Type.choices, default=Type.CORRECTIF)
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.NOUVEAU)
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    description = models.TextField(blank=True, null=True)
    technicien_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tickets_techniques',
    )
    date_ouverture = models.DateField(null=True, blank=True)
    date_resolution = models.DateField(null=True, blank=True)
    # FG88 — Date de tournée planifiée (jour de la visite préventive groupée).
    # Posée par l'action de planification de tournée (bulk-assign date +
    # technicien), distincte de date_ouverture qui reste la date d'ouverture du
    # ticket. NULL = visite non encore planifiée.
    date_tournee = models.DateField(null=True, blank=True)

    # Sous garantie : CALCULÉ depuis l'équipement lié quand il y en a un ;
    # sinon, valeur manuelle (oui/non/à déterminer) posée par l'utilisateur.
    sous_garantie = models.CharField(
        max_length=12, choices=SousGarantie.choices,
        default=SousGarantie.A_DETERMINER)
    # Coût interne (jamais affiché côté client).
    cout = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    # ── XSAV14 — taxonomie panne / cause / remède (codifiés à la résolution) ──
    # Optionnels : NULL tant qu'un technicien ne les a pas saisis (comportement
    # actuel inchangé). SET_NULL : la suppression d'un référentiel ne casse pas
    # l'historique des tickets déjà codifiés.
    cause = models.ForeignKey(
        'sav.CauseDefaillance', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tickets')
    remede = models.ForeignKey(
        'sav.RemedeDefaillance', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tickets')

    # ── Annulation : un DRAPEAU avec motif, pas une étape (comme « Perdu »). ──
    annule = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=255, blank=True, null=True)

    # ── FG81 — SLA (horloge de première réponse + drapeaux) ──────────────────
    # date_premiere_reponse : posée manuellement (ou via action) quand
    # l'équipe contacte le client pour la première fois. NULL = pas encore.
    date_premiere_reponse = models.DateTimeField(null=True, blank=True)
    # Échéance cible pour la RÉSOLUTION (calculée à la création depuis le SLA
    # société). NULL quand le réglage SLA n'est pas activé.
    sla_due_at = models.DateField(null=True, blank=True)
    # True quand sla_due_at est dépassé et le ticket toujours ouvert.
    # Mis à jour par le scan journalier + à chaque changement de statut.
    sla_breach = models.BooleanField(default=False)

    # ── XSAV5 — pause « en attente client » (l'horloge SLA ignore ce temps) ──
    en_attente_client = models.BooleanField(default=False)
    attente_depuis = models.DateField(null=True, blank=True)
    # Cumul de jours déjà passés en pause (mis à jour à la REPRISE, pas en
    # continu) — sert à décaler l'échéance affichée sans perdre l'historique
    # des pauses précédentes.
    jours_pause = models.PositiveIntegerField(default=0)

    # ── XSAV6 — idempotence pré-alerte / escalade (un niveau notifié une
    # seule fois, jamais chaque jour au re-passage du sweep). Remis à False
    # quand sla_due_at est recalculée (nouvelle échéance = nouveau cycle).
    sla_pre_alert_notifiee = models.BooleanField(default=False)
    sla_escalade_notifiee = models.BooleanField(default=False)

    # ── XSAV11 — suivi des réouvertures ──────────────────────────────────────
    # Incrémenté CÔTÉ SERVEUR à chaque transition résolu/clôturé → statut
    # ouvert (jamais décrémenté). 0 = jamais réouvert (comportement actuel).
    reopen_count = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='tickets_crees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    # FG100 — champs personnalisés (additif, jamais destructif).
    # Les définitions viennent de apps.customfields (module='ticket').
    custom_data = models.JSONField(null=True, blank=True)
    # FG86 — Jeton de partage public (lecture seule) pour le lien client.
    # Nullable + blank : jamais un seul default pour toutes les lignes existantes
    # (évite la violation d'unicité sur une DB peuplée). Généré lazily via
    # ensure_share_token(). Unique : chaque ticket a son propre jeton.
    share_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="Jeton public du lien client (FG86). Généré via ensure_share_token().")

    # ── XSAV3 — Devis de réparation hors garantie créé depuis ce ticket ──────
    # Référence par ID externe (jamais un FK vers apps.ventes.Devis — règle de
    # modularité CLAUDE.md, cross-app write via ventes.services). Pattern
    # identique à WarrantyClaim.fournisseur_id_ext. NULL = aucun devis créé.
    devis_id_ext = models.IntegerField(
        null=True, blank=True,
        help_text='ID du Devis ventes créé depuis ce ticket (XSAV3).')

    class Meta:
        verbose_name = 'Ticket SAV'
        verbose_name_plural = 'Tickets SAV'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['company', 'sla_breach']),
        ]

    def __str__(self):
        return self.reference

    @property
    def sous_garantie_calcule(self):
        """Garantie effective du ticket.

        Si un équipement est lié et porte une date de fin de garantie, on
        compare à aujourd'hui ('oui'/'non'). Sinon, la valeur manuelle stockée
        ('oui'/'non'/'a_determiner') fait foi.

        XSAV13 — la comparaison utilise ``date_fin_garantie_effective``
        (MAX entre la garantie légale de conformité loi 31-08 et la garantie
        commerciale constructeur) : un équipement de 8 mois sans garantie
        constructeur reste sous garantie (légale, impérative)."""
        eq = self.equipement
        if eq is not None and eq.date_fin_garantie_effective:
            today = timezone.localdate()
            return (self.SousGarantie.OUI
                    if today < eq.date_fin_garantie_effective
                    else self.SousGarantie.NON)
        return self.sous_garantie

    def recompute_sla_breach(self):
        """Recalcule sla_breach : True si sla_due_at dépassé + ticket ouvert.

        XSAV5 — l'échéance affichée (donc le calcul de dépassement) ignore le
        temps déjà passé en pause « en attente client » : on décale la
        comparaison de ``jours_pause`` jours (+ la pause EN COURS, si active,
        comptée jusqu'à aujourd'hui). Un ticket qui n'a jamais été mis en
        pause (jours_pause=0, en_attente_client=False) est comparé tel quel —
        byte-identique au comportement d'avant XSAV5.
        """
        if not self.sla_due_at:
            self.sla_breach = False
            return
        if self.statut not in self.OPEN_STATUTS or self.annule:
            self.sla_breach = False
            return
        today = timezone.localdate()
        due = self.sla_due_at_effectif(today=today)
        self.sla_breach = today > due

    def _pause_en_cours_jours(self, today=None):
        """XSAV5 — jours déjà écoulés dans la pause EN COURS (0 si aucune)."""
        if not self.en_attente_client or not self.attente_depuis:
            return 0
        today = today or timezone.localdate()
        return max(0, (today - self.attente_depuis).days)

    def sla_due_at_effectif(self, today=None):
        """XSAV5 — échéance SLA décalée du temps déjà passé en pause.

        ``sla_due_at`` reste la valeur brute posée à la création (jamais
        réécrite) ; cette méthode ajoute ``jours_pause`` (pauses déjà closes)
        + la pause en cours (si active) pour obtenir l'échéance EFFECTIVE.
        Sans jamais avoir été mis en pause, renvoie ``sla_due_at`` inchangé.
        """
        if not self.sla_due_at:
            return self.sla_due_at
        total_pause = self.jours_pause + self._pause_en_cours_jours(today=today)
        if total_pause <= 0:
            return self.sla_due_at
        return self.sla_due_at + timezone.timedelta(days=total_pause)

    def mettre_en_attente_client(self, today=None):
        """XSAV5 — démarre la pause « en attente client » (idempotent)."""
        if self.en_attente_client:
            return
        self.en_attente_client = True
        self.attente_depuis = today or timezone.localdate()

    def reprendre_apres_attente(self, today=None):
        """XSAV5 — clôt la pause en cours et cumule sa durée dans
        ``jours_pause`` (idempotent : sans pause active, ne fait rien)."""
        if not self.en_attente_client:
            return
        self.jours_pause += self._pause_en_cours_jours(today=today)
        self.en_attente_client = False
        self.attente_depuis = None

    def ensure_share_token(self):
        """FG86 — Génère (lazily) et renvoie le jeton de partage public.

        Idempotent : si le jeton existe déjà, le retourne tel quel sans écriture.
        Si le jeton est absent, génère un secrets.token_urlsafe(32) (43 chars URL-safe),
        l'enregistre avec update_fields pour ne pas déclencher auto_now sur d'autres
        champs, et le renvoie.  La collision est théoriquement possible mais
        négligeable (espace de 2^192).
        """
        if self.share_token:
            return self.share_token
        token = secrets.token_urlsafe(32)
        self.share_token = token
        self.save(update_fields=['share_token'])
        return self.share_token


# ── FG82 — Checklist par ticket ───────────────────────────────────────────────

class TicketChecklistItem(models.Model):
    """Item de checklist de maintenance coché sur un ticket (FG82).

    Rendu dans le PDF de rapport d'intervention (maintenance). Miroir de
    l'Item du template, mais copié au niveau du ticket pour historisation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ticket_checklist_items')
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='checklist_items')
    # Clé de l'étape (depuis le template, pour identification stable).
    cle = models.CharField(max_length=60)
    libelle = models.CharField(max_length=180)
    ordre = models.PositiveIntegerField(default=0)
    coche = models.BooleanField(default=False)
    note = models.TextField(blank=True, default='')
    coche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_coche = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'cle']
        unique_together = [('ticket', 'cle')]
        verbose_name = 'Item checklist ticket'
        verbose_name_plural = 'Items checklist ticket'

    def __str__(self):
        return f'{self.libelle} (ticket {self.ticket_id})'


class TicketActivity(models.Model):
    """Historique « chatter » d'un ticket — même modèle que LeadActivity /
    InstallationActivity. Entrées automatiques (création + changements de
    champs suivis, dont le statut) et notes manuelles. Utilisateur et société
    posés côté serveur, jamais lus du corps de la requête."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ticket_activities',
    )
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ticket_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité ticket'
        verbose_name_plural = 'Activités ticket'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['ticket', '-created_at'])]

    def __str__(self):
        return f"{self.ticket_id} {self.kind} {self.field or ''}".strip()


# ── FG83 — Réclamation garantie fournisseur (RMA) ─────────────────────────────

class WarrantyClaim(models.Model):
    """Réclamation garantie fournisseur (flux RMA) pour un équipement défaillant
    sous garantie (FG83).

    Permet de tracer les échanges avec le fournisseur (Huawei / VEICHI /
    fabricant panneaux) depuis le signalement jusqu'à la résolution
    (remplacement ou avoir). Le fournisseur est lu via stock.selectors (jamais
    un import direct du modèle stock).
    """
    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        ENVOYE = 'envoye', 'Envoyé au fournisseur'
        EN_ATTENTE = 'en_attente', 'En attente de retour'
        RESOLU = 'resolu', 'Résolu'
        REFUSE = 'refuse', 'Refusé'

    class Resolution(models.TextChoices):
        REMPLACEMENT = 'remplacement', 'Remplacement'
        AVOIR = 'avoir', 'Avoir'
        REPARATION = 'reparation', 'Réparation'
        REFUSE = 'refuse', 'Refusé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='warranty_claims')
    equipement = models.ForeignKey(
        Equipement, on_delete=models.PROTECT, related_name='warranty_claims')
    ticket = models.ForeignKey(
        Ticket, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='warranty_claims')
    # Fournisseur — référence par ID (stock.Fournisseur) lu via selectors.
    # Stocké comme IntegerField pour ne pas importer le modèle stock.
    fournisseur_id_ext = models.IntegerField(
        null=True, blank=True,
        help_text='ID du fournisseur stock (sav.selectors.get_fournisseur).')
    fournisseur_nom_cache = models.CharField(
        max_length=120, blank=True, default='',
        help_text='Nom du fournisseur mis en cache (dénormalisation lecture).')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.OUVERT)
    # Référence RMA attribuée par le fournisseur.
    rma_ref = models.CharField(max_length=80, blank=True, default='')
    date_signalement = models.DateField(null=True, blank=True)
    date_envoi_fournisseur = models.DateField(null=True, blank=True)
    date_resolution = models.DateField(null=True, blank=True)
    resolution = models.CharField(
        max_length=15, choices=Resolution.choices, blank=True, default='')
    # Coût récupéré (avoir ou remplacement valorisé). Interne — jamais client.
    cout_recupere = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réclamation garantie fournisseur'
        verbose_name_plural = 'Réclamations garantie fournisseur'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['company', 'equipement']),
        ]

    def __str__(self):
        return f'RMA #{self.pk} — {self.equipement_id} ({self.statut})'


# ── FG87 — Base de connaissances SAV ─────────────────────────────────────────

class KbArticle(models.Model):
    """Article de la base de connaissances SAV (FG87).

    Les résolutions d'intervention évaporent comme du texte libre dans le
    chatter. KbArticle capitalise les playbooks de résolution : codes erreur
    onduleur, pannes de strings, problèmes terrain récurrents.

    Cherchable par texte libre + filtrable par produit/catégorie (aide à
    trouver le bon article depuis un ticket lié à un équipement précis).
    Aucun prix d'achat ni information sensible n'y figure.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='kb_articles')
    titre = models.CharField(max_length=200)
    corps = models.TextField()
    # Tags libres (liste JSON) — ex. ["onduleur", "E07", "Huawei"].
    tags = models.JSONField(default=list, blank=True)
    # Produit optionnel (lien vers le catalogue pour filtrage depuis ticket).
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='kb_articles')
    # Catégorie libre (ex. "Onduleur", "Câblage", "Pompage").
    categorie = models.CharField(max_length=80, blank=True, default='')
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Article KB SAV'
        verbose_name_plural = 'Articles KB SAV'
        ordering = ['-date_modification']
        indexes = [
            models.Index(fields=['company', 'actif']),
            models.Index(fields=['company', 'produit']),
        ]

    def __str__(self):
        return self.titre


class ContratMaintenance(models.Model):
    """T16 — contrat de maintenance préventive (abonnement de visites).

    Rattaché à un client (et optionnellement un chantier). La prochaine visite
    et le caractère « dû » sont calculés À LA LECTURE (pas de planificateur,
    cohérent avec l'expiration des devis T7). Quand une visite est due, un
    ticket SAV préventif est généré (idempotent) via le service dédié.
    """
    class Periodicite(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'
        SEMESTRIEL = 'semestriel', 'Semestriel'
        ANNUEL = 'annuel', 'Annuel'

    # Nombre de mois entre deux visites, par périodicité.
    MONTHS = {'mensuel': 1, 'trimestriel': 3, 'semestriel': 6, 'annuel': 12}

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='contrats_maintenance')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='contrats_maintenance')
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contrats_maintenance')
    periodicite = models.CharField(
        max_length=15, choices=Periodicite.choices,
        default=Periodicite.ANNUEL)
    date_debut = models.DateField()
    # Date de la dernière visite générée — avance à chaque génération.
    derniere_visite = models.DateField(null=True, blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    # N47 — durée du contrat (mois) + date de renouvellement explicite. Additif,
    # tout optionnel : NULL = comportement actuel (contrat sans échéance fixée).
    duree_mois = models.PositiveIntegerField(null=True, blank=True)
    date_renouvellement = models.DateField(null=True, blank=True)
    # ── Facturation récurrente (FG40) — additif, tout optionnel ──
    # `facturation_active` = False → le contrat génère des visites mais aucune
    # facture (comportement historique préservé — default False).
    # `derniere_facturation` = date du dernier cycle de facturation réussi.
    facturation_active = models.BooleanField(
        default=False,
        verbose_name='Facturation récurrente active',
        help_text='Si activé, `facturer` produit une Facture à chaque période.',
    )
    derniere_facturation = models.DateField(
        null=True, blank=True,
        verbose_name='Dernière facturation',
        help_text='Date du dernier cycle de facturation émis. Null = jamais facturé.',
    )
    # ── XSAV7 — SLA différencié par contrat (override optionnel) ────────────
    # NULL = pas d'override : le ticket retombe sur sla_par_priorite puis les
    # défauts société (comportement actuel inchangé). Un contrat premium peut
    # poser des délais plus stricts que le SLA société standard. On NE crée
    # PAS un second référentiel parallèle à `contrats.EngagementSLA` (qui
    # exprime un taux cible %, pas des délais en jours) — ce sont des overrides
    # simples, au même format que `SavSlaSettings`.
    sla_response_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='SLA — délai de première réponse (jours, override)',
        help_text='Vide = pas de override contrat (SLA société standard).',
    )
    sla_resolution_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='SLA — délai de résolution (jours, override)',
        help_text='Vide = pas de override contrat (SLA société standard).',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Contrat de maintenance'
        verbose_name_plural = 'Contrats de maintenance'

    def __str__(self):
        return f'Contrat #{self.pk} — {self.client_id}'

    @classmethod
    def actif_pour_client(cls, client):
        """XSAV7 — Contrat de maintenance ACTIF du client portant un override
        SLA, s'il en existe un. Renvoie None sinon (comportement actuel).

        Premier match gagne : le contrat le plus RÉCEMMENT créé parmi les
        actifs qui posent au moins un override (``sla_response_days`` ou
        ``sla_resolution_days`` non NULL)."""
        if client is None:
            return None
        return (cls.objects
                .filter(client=client, actif=True)
                .exclude(sla_response_days__isnull=True,
                         sla_resolution_days__isnull=True)
                .order_by('-date_creation')
                .first())

    def prochaine_visite(self):
        """Date de la prochaine visite (dernière visite ou début + période).

        DC19 — la date calculée est reportée au prochain JOUR OUVRÉ de la
        société (week-end/férié → jour ouvré suivant) via le référentiel
        calendrier partagé : une visite de maintenance n'est jamais planifiée
        un jour non ouvré. Repli silencieux sur la date brute si le calendrier
        est indisponible.
        """
        from datetime import date
        base = self.derniere_visite or self.date_debut
        m = self.MONTHS.get(self.periodicite, 12)
        # Avance de m mois sans dépendance externe.
        y, mo = base.year, base.month + m
        y += (mo - 1) // 12
        mo = ((mo - 1) % 12) + 1
        day = min(base.day, 28)
        cible = date(y, mo, day)
        try:
            from apps.notifications.calendar_utils import prochain_jour_ouvre
            return prochain_jour_ouvre(cible, self.company)
        except Exception:  # noqa: BLE001 — calendrier absent → date brute
            return cible

    def is_due(self, today=None):
        # Bucket « aujourd'hui » sur le fuseau de l'app (Africa/Casablanca) :
        # un date.today() naïf (UTC) décalait le « dû » d'un jour à minuit.
        return self.actif and (
            today or timezone.localdate()) >= self.prochaine_visite()

    def renouvellement_du(self, today=None):
        """True si la date de renouvellement est atteinte (contrat à renouveler)."""
        if not self.date_renouvellement:
            return False
        return self.actif and (
            today or timezone.localdate()) >= self.date_renouvellement

    def prochaine_facturation(self):
        """Date du prochain cycle de facturation (FG40).

        Basé sur `derniere_facturation` (si posé) ou `date_debut`.
        Utilise la même périodicité MONTHS que les visites.
        """
        from datetime import date as _date
        base = self.derniere_facturation or self.date_debut
        m = self.MONTHS.get(self.periodicite, 12)
        y, mo = base.year, base.month + m
        y += (mo - 1) // 12
        mo = ((mo - 1) % 12) + 1
        day = min(base.day, 28)
        return _date(y, mo, day)

    def facturation_due(self, today=None):
        """True si la facturation récurrente est due aujourd'hui ou passée."""
        if not self.facturation_active or not self.actif:
            return False
        return (today or timezone.localdate()) >= self.prochaine_facturation()


# ── FG280 — Alarmes / défauts onduleur ────────────────────────────────────────

class AlarmeOnduleur(models.Model):
    """FG280 — Alarme / défaut onduleur, DISTINCTE du ticket SAV.

    Un onduleur remonte des codes de défaut (E07, F12…) avec une gravité.
    Cet objet capture l'alarme telle qu'observée — code, gravité, équipement
    concerné — avec son propre cycle de vie d'acquittement/escalade, SÉPARÉ du
    cycle de vie du ticket SAV (`Ticket`). Acquitter = « j'ai vu » (utilisateur
    + horodatage côté serveur). Escalader = ouvrir/relier un ticket SAV pour
    traiter le défaut ; l'alarme reste l'enregistrement source.

    Multi-tenant : `company` posé côté serveur, jamais depuis le corps. Le lien
    `ticket` reste optionnel — une alarme peut vivre sans ticket (acquittée ou
    résolue sans intervention).
    """
    class Gravite(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Avertissement'
        CRITIQUE = 'critique', 'Critique'

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ACQUITTEE = 'acquittee', 'Acquittée'
        RESOLUE = 'resolue', 'Résolue'
        ESCALADEE = 'escaladee', 'Escaladée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='alarmes_onduleur')
    # L'appareil concerné, si connu. SET_NULL : pas de perte de l'alarme.
    equipement = models.ForeignKey(
        'sav.Equipement', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alarmes_onduleur')
    # Code remonté par l'onduleur (ex. "E07", "F12").
    code = models.CharField(max_length=60)
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices, default=Gravite.WARNING)
    libelle = models.CharField(max_length=180, blank=True, default='')
    description = models.TextField(blank=True, default='')
    date_detection = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.ACTIVE)

    # ── Acquittement (« j'ai vu ») — utilisateur + date posés côté serveur. ──
    acquittee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alarmes_onduleur_acquittees')
    date_acquittement = models.DateTimeField(null=True, blank=True)

    # ── Escalade — lien optionnel vers le ticket SAV qui traite le défaut. ──
    # SET_NULL : la suppression d'un ticket ne casse pas l'historique d'alarmes.
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alarmes_onduleur')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alarme onduleur'
        verbose_name_plural = 'Alarmes onduleur'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'statut'], name='sav_alarme_co_statut'),
            models.Index(
                fields=['company', 'gravite'], name='sav_alarme_co_gravite'),
        ]

    def __str__(self):
        return f'{self.code} ({self.gravite}) — {self.statut}'


class TicketSatisfaction(models.Model):
    """XSAV10 — Enquête de satisfaction (CSAT) à la clôture du ticket SAV.

    Saisie sur la page publique du lien client (share_token, FG86) une fois le
    ticket résolu/clôturé. UNE seule réponse par ticket (OneToOne) — un second
    POST public est refusé. Aucune donnée interne (cout, chatter) n'est jamais
    exposée sur la page publique ; seule la note + le commentaire libre sont
    collectés côté client.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ticket_satisfactions')
    ticket = models.OneToOneField(
        Ticket, on_delete=models.CASCADE, related_name='satisfaction')
    note = models.PositiveSmallIntegerField(
        help_text='Note de satisfaction 1 (très insatisfait) à 5 (très satisfait).')
    commentaire = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Satisfaction ticket SAV (CSAT)'
        verbose_name_plural = 'Satisfactions ticket SAV (CSAT)'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'date_creation']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(note__gte=1) & models.Q(note__lte=5),
                name='sav_ticketsatisfaction_note_1_5'),
        ]

    def __str__(self):
        return f'CSAT ticket {self.ticket_id} = {self.note}/5'


# ── XSAV14 — Taxonomie panne / cause / remède ────────────────────────────────

class CauseDefaillance(models.Model):
    """XSAV14 — Référentiel configurable des causes de panne (Paramètres SAV).

    Codifie la CAUSE d'une panne (ex. « Défaut composant », « Erreur
    d'installation », « Usure normale ») pour permettre l'analyse Pareto des
    modes de défaillance. Même patron que `crm.Canal`/`crm.MotifPerte` :
    liste plate, scopée société, éditable dans Paramètres, additive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='causes_defaillance')
    nom = models.CharField(max_length=150)
    ordre = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Cause de défaillance'
        verbose_name_plural = 'Causes de défaillance'

    def __str__(self):
        return self.nom


class RemedeDefaillance(models.Model):
    """XSAV14 — Référentiel configurable des remèdes appliqués (Paramètres SAV).

    Codifie le REMÈDE apporté à la résolution (ex. « Remplacement pièce »,
    « Reparamétrage », « Nettoyage »). Même patron que `CauseDefaillance`."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='remedes_defaillance')
    nom = models.CharField(max_length=150)
    ordre = models.PositiveIntegerField(default=0)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Remède de défaillance'
        verbose_name_plural = 'Remèdes de défaillance'

    def __str__(self):
        return self.nom


class PieceConsommee(models.Model):
    """N46 — pièce consommée sur un ticket SAV.

    Affichée sur le rapport d'intervention (via `ticket.pieces`) avec
    seulement désignation/marque/quantité — JAMAIS de prix d'achat ni de marge
    côté client. Le stock peut être décrémenté à l'enregistrement
    (MouvementStock SORTIE) ; `stock_decremente` évite tout double mouvement.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='pieces_sav')
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='pieces')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT, related_name='pieces_sav')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=1)
    stock_decremente = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pièce consommée'
        verbose_name_plural = 'Pièces consommées'
        ordering = ['id']

    def __str__(self):
        return f'{self.produit_id} ×{self.quantite} (ticket {self.ticket_id})'


# ── XSAV16 — Journal d'immobilisation (downtime) + disponibilité % ──────────

class EquipementDowntime(models.Model):
    """XSAV16 — Période d'immobilisation d'un équipement client.

    Ouverte depuis un ticket (panne bloquante) ou l'escalade d'une alarme
    onduleur critique (FG280) ; fermée à la résolution. ``fin`` NULL = encore
    en panne (immobilisation en cours). Le lien ``ticket`` est optionnel
    (SET_NULL) — l'historique de downtime survit à la suppression du ticket.

    Les fenêtres NE PEUVENT PAS se chevaucher pour un même équipement — la
    disponibilité % dérivée serait autrement faussée (double comptage). La
    garde anti-chevauchement est appliquée côté service (`services.py`), pas
    en contrainte DB (Django ne supporte pas nativement les contraintes
    d'exclusion de plage sans une extension Postgres dédiée)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='downtimes_equipement')
    equipement = models.ForeignKey(
        'sav.Equipement', on_delete=models.CASCADE, related_name='downtimes')
    debut = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='downtimes')
    motif = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Immobilisation équipement'
        verbose_name_plural = 'Immobilisations équipement'
        ordering = ['-debut']
        indexes = [
            models.Index(fields=['company', 'equipement'],
                         name='sav_eqdown_co_equip_idx'),
            models.Index(fields=['equipement', 'fin'],
                         name='sav_eqdown_equip_fin_idx'),
        ]

    def __str__(self):
        etat = 'en cours' if self.fin is None else 'clos'
        return f'Downtime équipement {self.equipement_id} ({etat})'

    def clore(self, fin=None):
        """Ferme l'immobilisation (idempotent : ne réécrit pas si déjà close)."""
        if self.fin is not None:
            return
        self.fin = fin or timezone.now()
        self.save(update_fields=['fin'])
