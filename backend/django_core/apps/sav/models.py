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
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Contrat de maintenance'
        verbose_name_plural = 'Contrats de maintenance'

    def __str__(self):
        return f'Contrat #{self.pk} — {self.client_id}'

    def prochaine_visite(self):
        """Date de la prochaine visite (dernière visite ou début + période)."""
        from datetime import date
        base = self.derniere_visite or self.date_debut
        m = self.MONTHS.get(self.periodicite, 12)
        # Avance de m mois sans dépendance externe.
        y, mo = base.year, base.month + m
        y += (mo - 1) // 12
        mo = ((mo - 1) % 12) + 1
        day = min(base.day, 28)
        return date(y, mo, day)

    def is_due(self, today=None):
        from datetime import date
        return self.actif and (today or date.today()) >= self.prochaine_visite()
