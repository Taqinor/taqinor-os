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
        # XFSM13 — re-vérification périodique IEC 62446-2 : reprend les points
        # électriques de la recette (Riso, continuité, Voc/string) et compare
        # à la baseline du chantier. Additif — n'affecte aucun type existant.
        REVERIFICATION_62446 = 'reverification_62446', 'Re-vérification IEC 62446-2'

    class Priorite(models.TextChoices):
        # XFSM4 — priorité pilotant le tri dispatch (kanban F4, calendrier
        # FG68, « Ma journée » F22). Sans lien avec STAGES.py ni le statut
        # chantier/intervention. Défaut NORMALE = comportement actuel inchangé.
        URGENTE = 'urgente', 'Urgente'
        HAUTE = 'haute', 'Haute'
        NORMALE = 'normale', 'Normale'

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
    # XFSM4 — priorité (héritée du ticket SAV lié quand il existe, sinon
    # NORMALE) : pilote le tri dans le kanban F4, le calendrier FG68 et « Ma
    # journée » F22. Additif — ne touche ni le statut chantier ni STAGES.py.
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
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
    # DC40 — équipe terrain CANONIQUE assignée (FK nullable vers ``Equipe``).
    # ADDITIF : l'ancien M2M ``equipe`` ci-dessus reste intact (rien ne casse).
    # Quand ``equipe_ref`` est posée, les membres de l'intervention se résolvent
    # via l'équipe canonique (``selectors.membres_intervention``) ; sinon on
    # retombe sur le M2M ad-hoc historique. Une seule DÉFINITION d'équipe.
    equipe_ref = models.ForeignKey(
        'installations.Equipe', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
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
    # ── XFSM7 — position GPS optionnelle au départ (posée par l'action
    #    ``depart-depot`` quand le navigateur la fournit). Sert UNIQUEMENT à
    #    calculer l'ETA affichée sur le lien public « technicien en route » ;
    #    n'affecte aucune logique F6 existante (distance-au-site reste basée
    #    sur l'arrivée). Nullable — un départ sans GPS garde le comportement
    #    actuel (ETA simplement absente du payload public). ──
    depart_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    depart_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    # ── FG69 — signature client sur le compte-rendu / PV ─────────────────────
    # Data-URL PNG (ou SVG strokes JSON) de la signature. Stocké en base car
    # la taille d'une signature PNG compressée est typiquement < 20 Ko.
    signature_client = models.TextField(blank=True, null=True)
    signataire_nom = models.CharField(max_length=120, blank=True, null=True)
    signe_le = models.DateTimeField(null=True, blank=True)

    # ── FG78 — RDV confirmation + historique reschedule ───────────────────────
    # Métadonnées RDV, orthogonales à la machine à états statut.
    rdv_confirme = models.BooleanField(default=False)
    rdv_confirme_le = models.DateTimeField(null=True, blank=True)
    rdv_reschedule_count = models.PositiveIntegerField(default=0)

    # ── XFSM5 — fenêtre de RDV promise (ex. 8h–10h) + ponctualité ────────────
    # Affichées sur la confirmation client et « Ma journée » F22. Nullable :
    # une intervention sans fenêtre garde le comportement actuel (heure exacte
    # implicite, pas de mesure de ponctualité). `arrivee_dans_fenetre` est
    # dérivé au check-in GPS (F6) : True/False une fois calculé, None tant que
    # l'arrivée n'a pas eu lieu ou qu'aucune fenêtre n'est promise.
    fenetre_debut = models.TimeField(null=True, blank=True)
    fenetre_fin = models.TimeField(null=True, blank=True)
    arrivee_dans_fenetre = models.BooleanField(null=True, blank=True)

    # ── XFSM7 — lien public « technicien en route » (suivi de visite) ───────
    # Jeton de partage public (même patron que ``sav.Ticket.share_token``
    # FG86) : nullable/blank, généré lazily via ``ensure_lien_client_token``,
    # unique par intervention. Expire à ``date_prevue`` + 1 jour (au-delà, la
    # visite du jour est passée — pas de sens de suivre "en route" plus tard).
    lien_client_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="Jeton public du lien « technicien en route » (XFSM7).")

    # ── ZFSM2 — lien public tokenisé du compte-rendu signé ───────────────────
    # Jeton DISTINCT du lien « en route » (XFSM7 ci-dessus) : XFSM7 ne couvre
    # QUE le suivi de visite, jamais le compte-rendu final (F19). Même patron
    # (secrets.token_urlsafe(32), lazy, unique). Généré à la validation de
    # l'intervention (statut « Validée ») — n'expire jamais par date (le
    # compte-rendu d'une intervention ancienne reste consultable), mais reste
    # révocable en vidant le champ.
    lien_rapport_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="Jeton public du lien compte-rendu signé (ZFSM2).")

    # ── XFSM21 — météo sur le planning (travaux toiture) ─────────────────────
    # Prévision J+3 (Open-Meteo, gratuit, sans clé) récupérée par la tâche Beat
    # quotidienne pour les interventions POSE planifiées. None = pas encore
    # évalué (ou hors fenêtre J+3) ; True = pluie/vent au-delà des seuils
    # paramétrables ; False = prévision OK. Additif, jamais bloquant.
    meteo_risque = models.BooleanField(null=True, blank=True)
    meteo_verifie_le = models.DateTimeField(null=True, blank=True)

    # ── YSERV6 — annulation de chantier : solder les interventions ─────────
    # Drapeau ORTHOGONAL à `statut` (F3 STATUT_ORDER reste INTACT) : une
    # intervention non terminée d'un chantier annulé passe `annulee=True`
    # (jamais un statut supplémentaire dans la state machine). Exclue des vues
    # kanban/calendrier/charge ; une nouvelle intervention est refusée sur un
    # chantier annulé. `reactiver()` lève ce drapeau UNIQUEMENT pour les
    # interventions qu'il a lui-même annulées (tracé dans `motif_annulation`).
    annulee = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=255, blank=True, null=True)

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

    def ensure_lien_client_token(self):
        """XFSM7 — génère (lazily) et renvoie le jeton public du lien client.

        Idempotent : si le jeton existe déjà, le retourne tel quel sans
        écriture. Sinon génère un ``secrets.token_urlsafe(32)`` (même patron
        que ``sav.Ticket.ensure_share_token``, FG86)."""
        if self.lien_client_token:
            return self.lien_client_token
        import secrets
        token = secrets.token_urlsafe(32)
        self.lien_client_token = token
        self.save(update_fields=['lien_client_token'])
        return self.lien_client_token

    @property
    def lien_client_expire(self):
        """XFSM7 — le lien expire le lendemain de la date prévue (une visite
        d'un jour passé n'a plus de sens à suivre « en route »). Sans date
        prévue, le lien n'expire jamais par cette règle (couvert par le
        statut : une intervention VALIDEE/TERMINEE cesse d'avoir un ETA)."""
        if not self.date_prevue:
            return False
        from datetime import timedelta

        from django.utils import timezone
        # Comparaison sur la DATE seule (évite tout souci de fuseau horaire) :
        # expiré si aujourd'hui > date_prevue + 1 jour.
        return timezone.localdate() > (self.date_prevue + timedelta(days=1))

    def ensure_lien_rapport_token(self):
        """ZFSM2 — génère (lazily) et renvoie le jeton public du lien
        compte-rendu signé. Idempotent : si le jeton existe déjà, le retourne
        tel quel sans écriture. Même patron que ``ensure_lien_client_token``
        (XFSM7) / ``sav.Ticket.ensure_share_token`` (FG86) — un jeton
        DISTINCT, car XFSM7 ne couvre que le suivi « en route »."""
        if self.lien_rapport_token:
            return self.lien_rapport_token
        import secrets
        token = secrets.token_urlsafe(32)
        self.lien_rapport_token = token
        self.save(update_fields=['lien_rapport_token'])
        return self.lien_rapport_token


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


# ── FG79 — Plan d'interventions standard par type d'installation ─────────────

class TypeInterventionPlan(models.Model):
    """FG79 — plan de la chaîne d'interventions STANDARD pour un type
    d'installation donné (résidentiel/industriel/agricole). Chaque ligne
    indique un type d'intervention (clé TypeIntervention), son ordre, et un
    libellé de contexte. L'action `creer-interventions-standard` matérialise
    ce plan en Interventions réelles sur le chantier (idempotent : ne recrée
    pas les types déjà présents). Additif — company-scopé."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='type_intervention_plans')
    # Type d'installation auquel ce plan s'applique.
    type_installation = models.CharField(
        max_length=20, choices=Installation.TypeInstallation.choices)
    # Clé du TypeIntervention (références texte : pas de FK rigide pour permettre
    # la création avant que les types d'intervention soient créés).
    type_intervention_cle = models.CharField(max_length=40)
    libelle_contexte = models.CharField(max_length=120, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['type_installation', 'ordre']
        unique_together = [('company', 'type_installation', 'type_intervention_cle')]
        verbose_name = "Plan d'intervention standard"
        verbose_name_plural = "Plans d'intervention standard"

    def __str__(self):
        return (f'{self.get_type_installation_display()} — '
                f'{self.type_intervention_cle} (#{self.ordre})')
