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
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .services import add_months


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

    class Meta:
        verbose_name = 'Équipement'
        verbose_name_plural = 'Équipements'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'produit']),
            models.Index(fields=['company', 'date_fin_garantie']),
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
    # Le chantier concerné.
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='tickets',
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

    # Sous garantie : CALCULÉ depuis l'équipement lié quand il y en a un ;
    # sinon, valeur manuelle (oui/non/à déterminer) posée par l'utilisateur.
    sous_garantie = models.CharField(
        max_length=12, choices=SousGarantie.choices,
        default=SousGarantie.A_DETERMINER)
    # Coût interne (jamais affiché côté client).
    cout = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    # ── Annulation : un DRAPEAU avec motif, pas une étape (comme « Perdu »). ──
    annule = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=255, blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='tickets_crees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ticket SAV'
        verbose_name_plural = 'Tickets SAV'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return self.reference

    @property
    def sous_garantie_calcule(self):
        """Garantie effective du ticket.

        Si un équipement est lié et porte une date de fin de garantie, on
        compare à aujourd'hui ('oui'/'non'). Sinon, la valeur manuelle stockée
        ('oui'/'non'/'a_determiner') fait foi.
        """
        eq = self.equipement
        if eq is not None and eq.date_fin_garantie:
            today = timezone.localdate()
            return (self.SousGarantie.OUI if today < eq.date_fin_garantie
                    else self.SousGarantie.NON)
        return self.sous_garantie


class TicketPiece(models.Model):
    """Pièce consommée sur un ticket SAV (N46).

    Enregistre additivement une pièce (produit catalogue) utilisée lors d'une
    intervention de dépannage, avec sa quantité. À l'enregistrement, le stock
    PEUT être décrémenté (réutilise EXACTEMENT le patron MouvementStock SORTIE
    du reste de l'OS — voir services.decrementer_stock_piece). Les pièces
    apparaissent sur le rapport d'intervention (N45) — JAMAIS le prix d'achat.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ticket_pieces',
    )
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='pieces')
    # PROTECT : on ne supprime pas un produit référencé par une pièce posée.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT, related_name='ticket_pieces',
    )
    quantite = models.PositiveIntegerField(default=1)
    # Trace : le stock a-t-il été décrémenté lors de l'enregistrement ?
    stock_decremente = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='ticket_pieces_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pièce ticket'
        verbose_name_plural = 'Pièces ticket'
        ordering = ['-date_creation']
        indexes = [models.Index(fields=['company', 'ticket'])]

    def __str__(self):
        return f"{self.quantite} × {self.produit_id} (ticket {self.ticket_id})"


class ReclamationGarantie(models.Model):
    """Réclamation de garantie contre un composant (N48).

    Trace auditable d'une demande de prise en charge sous garantie d'un
    équipement, avec sa description et son résultat (accordée / refusée / en
    cours). Scopée à la société ; acteur posé côté serveur.
    """
    class Resultat(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        ACCORDEE = 'accordee', 'Accordée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reclamations_garantie',
    )
    equipement = models.ForeignKey(
        'sav.Equipement', on_delete=models.CASCADE,
        related_name='reclamations_garantie',
    )
    date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    resultat = models.CharField(
        max_length=12, choices=Resultat.choices, default=Resultat.EN_COURS)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='reclamations_garantie_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réclamation de garantie'
        verbose_name_plural = 'Réclamations de garantie'
        ordering = ['-date_creation']
        indexes = [models.Index(fields=['company', 'equipement'])]

    def __str__(self):
        return f"Réclamation #{self.pk} ({self.equipement_id})"


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


# Fenêtre « visite à venir bientôt » (jours) — une visite due dans cet horizon
# remonte dans la vue « à venir ».
UPCOMING_SOON_DAYS = 30

# Fenêtre « renouvellement proche » (jours) — un contrat dont la date de fin
# tombe dans cet horizon remonte dans la vue « à renouveler » (N47).
RENEWAL_SOON_DAYS = 60


class ContratMaintenance(models.Model):
    """Contrat de maintenance préventive — un abonnement de visites récurrentes
    accroché à un chantier (et donc à un client). Quand une visite arrive à
    échéance, le contrat GÉNÈRE un ticket SAV préventif. La détection d'échéance
    est CALCULÉE à la lecture (next_visite = dernière visite / début + intervalle)
    — aucun planificateur, cron ou tâche de fond, comme partout dans l'OS.

    La génération est déclenchée À LA DEMANDE (ouverture de la vue « à venir »
    ou clic « générer les tickets dus ») et reste idempotente : un seul ticket
    par échéance grâce à `derniere_echeance_traitee`.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='contrats_maintenance',
    )
    # Le chantier couvert (objet pivot de l'après-vente).
    installation = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='contrats_maintenance',
    )
    # Client — résolu côté serveur depuis le chantier ; jamais lu du corps.
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='contrats_maintenance',
    )

    libelle = models.CharField(max_length=150, blank=True, null=True)
    # Nombre de mois entre deux visites préventives.
    intervalle_mois = models.PositiveSmallIntegerField(default=12)
    date_debut = models.DateField()
    # ── Renouvellement (N47) — ADDITIF. Date de fin du contrat et/ou durée en
    #    mois. Le drapeau « à renouveler » est CALCULÉ à la lecture (date_fin
    #    dans l'horizon RENEWAL_SOON_DAYS), jamais stocké. ──
    date_fin = models.DateField(null=True, blank=True)
    duree_mois = models.PositiveSmallIntegerField(null=True, blank=True)
    # Date de la dernière visite réalisée/générée (None = jamais encore visité).
    derniere_visite = models.DateField(null=True, blank=True)
    # Échéance déjà matérialisée par un ticket — garde-fou d'idempotence.
    derniere_echeance_traitee = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='contrats_maintenance_crees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrat de maintenance'
        verbose_name_plural = 'Contrats de maintenance'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'actif']),
            models.Index(fields=['company', 'installation']),
        ]

    def __str__(self):
        return self.libelle or f"Contrat #{self.pk}"

    @property
    def prochaine_visite(self):
        """Date de la prochaine visite préventive — CALCULÉE à la lecture.

        base = dernière visite si elle existe, sinon date de début ; on ajoute
        l'intervalle. Si aucune visite n'a eu lieu, la première échéance est la
        date de début elle-même (la visite de mise en route)."""
        if not self.derniere_visite:
            return self.date_debut
        return add_months(self.derniere_visite, self.intervalle_mois)

    def est_due(self, today=None):
        """Vrai si une visite est due (prochaine échéance <= aujourd'hui)."""
        if not self.actif:
            return False
        today = today or timezone.localdate()
        prochaine = self.prochaine_visite
        return prochaine is not None and prochaine <= today

    def est_a_venir(self, today=None, horizon_jours=UPCOMING_SOON_DAYS):
        """Vrai si une visite est due OU due dans l'horizon proche."""
        if not self.actif:
            return False
        today = today or timezone.localdate()
        prochaine = self.prochaine_visite
        if prochaine is None:
            return False
        return prochaine <= today + timedelta(days=horizon_jours)

    @property
    def date_fin_effective(self):
        """Date de fin du contrat — CALCULÉE à la lecture (N47).

        date_fin explicite si elle existe ; sinon date_debut + duree_mois ;
        sinon None (« non renseignée »). Aucune date inventée."""
        if self.date_fin:
            return self.date_fin
        if self.duree_mois:
            return add_months(self.date_debut, self.duree_mois)
        return None

    def jours_avant_fin(self, today=None):
        fin = self.date_fin_effective
        if fin is None:
            return None
        today = today or timezone.localdate()
        return (fin - today).days

    def a_renouveler(self, today=None, horizon_jours=RENEWAL_SOON_DAYS):
        """Vrai si le contrat approche de son renouvellement — CALCULÉ.

        Drapeau levé quand la date de fin tombe dans l'horizon (passée ou à
        venir dans `horizon_jours`). Un contrat inactif n'est jamais signalé."""
        if not self.actif:
            return False
        jours = self.jours_avant_fin(today)
        if jours is None:
            return False
        return jours <= horizon_jours
