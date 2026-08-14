"""Modèles de l'app `mrp` (Groupe NTMFG — Production / MRP II).

Moteur générique de production : postes de charge, gammes opératoires, ordres
de fabrication capacitaires. Distinct du kitting boutique déjà livré côté
`installations.Kit`/`KitComposant`/`OrdreAssemblage` (assemblage léger
magasin) — jamais reconstruit ici. `mrp` référence `stock`/`installations`
UNIQUEMENT par string-FK (jamais d'import de leurs modules `models`).
"""
from django.db import models

from core.models import TenantModel


class PosteDeCharge(TenantModel):
    """NTMFG1 — poste de charge (work center) : machine, ligne ou poste
    manuel, avec sa capacité journalière et son coût horaire INTERNE (jamais
    client-facing — comme `Produit.prix_achat`, DC28)."""

    class TypePoste(models.TextChoices):
        MACHINE = 'machine', 'Machine'
        LIGNE = 'ligne', 'Ligne'
        MANUEL = 'manuel', 'Poste manuel'
        # NTMFG10 — poste de sous-traitance (opération confiée à un tiers).
        SOUS_TRAITE = 'sous_traite', 'Sous-traité'

    code = models.CharField(max_length=40, verbose_name='Code')
    nom = models.CharField(max_length=200, verbose_name='Nom')
    type_poste = models.CharField(
        max_length=16, choices=TypePoste.choices,
        default=TypePoste.MACHINE, verbose_name='Type de poste')
    capacite_heures_jour = models.DecimalField(
        max_digits=5, decimal_places=2, default=8,
        verbose_name='Capacité (h/jour)')
    # Coût horaire INTERNE (main-d'œuvre + amortissement) — jamais dans un
    # document client-facing (même règle que `Produit.prix_achat`, DC28).
    cout_horaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Coût horaire (interne)')
    # Calendrier de travail simple : jours ouvrés + horaires, ex.
    # {"jours_ouvres": [0,1,2,3,4], "heure_debut": "08:00", "heure_fin": "17:00"}
    # (0=lundi). Défaut = semaine standard marocaine (lun-ven).
    calendrier_travail = models.JSONField(
        default=dict, blank=True, verbose_name='Calendrier de travail')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Poste de charge'
        verbose_name_plural = 'Postes de charge'
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='mrp_poste_co_code_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='mrp_poste_co_actif_idx'),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'


class Gamme(TenantModel):
    """NTMFG2 — gamme opératoire généraliste (routing) : la SÉQUENCE
    d'opérations avec poste de charge + temps standard pour fabriquer un
    produit, réutilisable par plusieurs Ordres de Fabrication (NTMFG3).

    Distincte de `installations.EtapeAssemblage` (checklist légère d'un Kit
    atelier-boutique, sans poste ni temps réglé séparé du temps de
    préparation) — une `Gamme` PEUT référencer un produit qui EST un
    `stock.KitProduit` (le composite vendable), mais porte sa propre
    industrialisation (postes, temps, capacité)."""

    nom = models.CharField(max_length=200, verbose_name='Nom')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='mrp_gammes', verbose_name='Produit fabriqué')
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # NTMFG4 — nomenclature (BOM) SOURCE de cette gamme, réutilisée en
    # LECTURE SEULE via `stock.services.exploser_kit_par_id` (jamais d'import
    # du modèle `stock.KitProduit`) pour le backflush (consommation
    # composants / production composite) à la clôture d'un OF SANS
    # `kit_ordre_assemblage` lié. Optionnel : une gamme sans nomenclature ne
    # mouvemente aucun stock à la clôture (OF de suivi pur).
    kit_source = models.ForeignKey(
        'stock.KitProduit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mrp_gammes_source',
        verbose_name='Nomenclature source (kit)')

    class Meta:
        verbose_name = 'Gamme opératoire'
        verbose_name_plural = 'Gammes opératoires'
        ordering = ['produit_id', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit', 'version'],
                name='mrp_gamme_co_produit_version_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'produit', 'actif'],
                         name='mrp_gamme_co_produit_actif_idx'),
        ]

    def __str__(self):
        return f'{self.nom} (v{self.version})'


class OperationGamme(models.Model):
    """NTMFG2 — une opération de la gamme : poste de charge + temps standard
    (prépa/unitaire/par-lot, style routing Odoo). Pas de `company` propre —
    scopée via `gamme.company` (même convention que
    `installations.KitComposant`)."""

    gamme = models.ForeignKey(
        Gamme, on_delete=models.CASCADE, related_name='operations')
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    poste_charge = models.ForeignKey(
        PosteDeCharge, on_delete=models.PROTECT,
        related_name='operations_gamme', verbose_name='Poste de charge')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    temps_prepa_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps de préparation (min)')
    temps_unitaire_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps unitaire (min/pièce)')
    temps_min_par_lot = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps minimum par lot (min)')

    class Meta:
        verbose_name = 'Opération de gamme'
        verbose_name_plural = 'Opérations de gamme'
        ordering = ['gamme_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['gamme'], name='mrp_opgamme_gamme_idx'),
            models.Index(fields=['poste_charge'], name='mrp_opgamme_poste_idx'),
        ]

    def __str__(self):
        return f'{self.gamme_id} · {self.ordre}. {self.libelle}'


class OrdreFabrication(TenantModel):
    """NTMFG3 — Ordre de Fabrication (OF) capacitaire, lié à une gamme et des
    postes. ÉTEND `installations.OrdreAssemblage` (qui reste l'ordre
    « kitting boutique » léger, sans poste ni temps par opération) — ne le
    duplique JAMAIS. `kit_ordre_assemblage` est un lien OPTIONNEL (string-FK)
    vers cet ordre existant pour les OF qui restent gérés côté kitting
    boutique : dans ce cas le mouvement matière reste porté par lui (XMFG1,
    jamais de double mouvement)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PLANIFIE = 'planifie', 'Planifié'
        LANCE = 'lance', 'Lancé'
        TERMINE = 'termine', 'Terminé'
        ANNULE = 'annule', 'Annulé'

    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='mrp_ordres_fabrication', verbose_name='Produit fabriqué')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1, verbose_name='Quantité')
    gamme = models.ForeignKey(
        Gamme, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordres_fabrication', verbose_name='Gamme')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_debut_planifiee = models.DateTimeField(
        null=True, blank=True, verbose_name='Début prévu')
    date_fin_planifiee = models.DateTimeField(
        null=True, blank=True, verbose_name='Fin prévue')
    priorite = models.PositiveSmallIntegerField(
        default=3, verbose_name='Priorité')
    # Lien optionnel string-FK vers un ordre d'assemblage kitting boutique
    # EXISTANT (`installations.OrdreAssemblage`) — quand présent, XMFG1 porte
    # le mouvement de stock, NTMFG4 ne mouvemente rien pour cet OF.
    kit_ordre_assemblage = models.ForeignKey(
        'installations.OrdreAssemblage', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mrp_ordres_fabrication',
        verbose_name="Ordre d'assemblage kitting lié")
    # NTMFG4 — idempotence du backflush (même garde que XMFG1
    # `stock_mouvemente`) : True dès que CET OF a produit son mouvement de
    # stock (consommation composants + production composite), pour ne
    # jamais le rejouer sur une clôture répétée.
    stock_mouvemente = models.BooleanField(
        default=False, verbose_name='Stock mouvementé')

    class Meta:
        verbose_name = 'Ordre de fabrication'
        verbose_name_plural = 'Ordres de fabrication'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='mrp_of_co_statut_idx'),
            models.Index(fields=['company', 'produit'],
                         name='mrp_of_co_produit_idx'),
        ]

    def __str__(self):
        return f'OF-{self.id} · {self.produit_id} × {self.quantite}'


class OperationOF(models.Model):
    """NTMFG3 — opération d'un OF, instanciée depuis la gamme à la
    confirmation de l'OF. Pas de `company` propre — scopée via
    `ordre_fabrication.company`."""

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        # NTMFG8 — terminal atelier MES : pause explicite, distincte d'un
        # simple retour à `a_faire`.
        EN_PAUSE = 'en_pause', 'En pause'
        TERMINEE = 'terminee', 'Terminée'

    class MotifRebut(models.TextChoices):
        """NTMFG8 — mêmes valeurs que `stock.MouvementStock.MotifRebut`
        (jamais d'import du modèle stock : ce sont des CHAÎNES littérales
        partagées par convention, XMFG11)."""
        CASSE = 'casse', 'Casse'
        DEFAUT = 'defaut', 'Défaut'
        ERREUR = 'erreur', 'Erreur'
        AUTRE = 'autre', 'Autre'

    ordre_fabrication = models.ForeignKey(
        OrdreFabrication, on_delete=models.CASCADE, related_name='operations')
    operation_gamme = models.ForeignKey(
        OperationGamme, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operations_of')
    poste_charge = models.ForeignKey(
        PosteDeCharge, on_delete=models.PROTECT, related_name='operations_of')
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    # NTMFG7 — jour où l'opération est planifiée sur son poste (day-bucket
    # scheduler à capacité finie, `services.planifier_of`).
    date_planifiee = models.DateField(
        null=True, blank=True, verbose_name='Jour planifié')
    # NTMFG8 — horodatages MES (démarrage/fin) ; le temps actif RÉEL =
    # (terminee_le - demarree_le) MOINS la somme des pauses (`PauseOperationOF`).
    demarree_le = models.DateTimeField(null=True, blank=True)
    terminee_le = models.DateTimeField(null=True, blank=True)
    temps_reel_min = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Temps réel (min)')
    quantite_bonne = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Quantité bonne')
    quantite_rebut = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Quantité rebut')
    motif_rebut = models.CharField(
        max_length=10, choices=MotifRebut.choices, blank=True, default='')

    class Meta:
        verbose_name = "Opération d'OF"
        verbose_name_plural = "Opérations d'OF"
        ordering = ['ordre_fabrication_id', 'ordre', 'id']
        indexes = [
            models.Index(fields=['ordre_fabrication'],
                         name='mrp_opof_of_idx'),
            models.Index(fields=['poste_charge', 'date_planifiee'],
                         name='mrp_opof_poste_date_idx'),
        ]

    def __str__(self):
        return f'{self.ordre_fabrication_id} · {self.ordre}. {self.libelle}'


class PauseOperationOF(models.Model):
    """NTMFG8 — intervalle de pause d'une `OperationOF` (terminal MES). Pas
    de `company` propre — scopée via `operation.ordre_fabrication.company`.
    `fin=None` = pause en cours."""

    operation = models.ForeignKey(
        OperationOF, on_delete=models.CASCADE, related_name='pauses')
    debut = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Pause d'opération"
        verbose_name_plural = "Pauses d'opération"
        ordering = ['operation_id', 'debut']
        indexes = [
            models.Index(fields=['operation'], name='mrp_pauseof_op_idx'),
        ]

    def __str__(self):
        return f'{self.operation_id} · pause {self.debut}'


class ReservationOF(models.Model):
    """NTMFG6 — réservation de composant sur un OF (miroir de
    `installations.ReservationAssemblage`, mais au niveau
    `mrp.OrdreFabrication`). Pas de `company` propre — scopée via
    `ordre_fabrication.company`. Bookkeeping MRP interne : n'affecte PAS le
    disponible cross-app (`stock.services.available_quantity`, qui reste
    dérivé des seules réservations `installations`) — visible uniquement sur
    l'écran de l'OF via `selectors.disponibilite_par_ligne_of`."""

    ordre_fabrication = models.ForeignKey(
        OrdreFabrication, on_delete=models.CASCADE, related_name='reservations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,
        related_name='mrp_reservations_of')
    quantite = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    consomme = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réservation d'OF"
        verbose_name_plural = "Réservations d'OF"
        ordering = ['ordre_fabrication_id', 'id']
        indexes = [
            models.Index(fields=['ordre_fabrication'],
                         name='mrp_resof_of_idx'),
            models.Index(fields=['produit'], name='mrp_resof_produit_idx'),
        ]

    def __str__(self):
        return f'{self.ordre_fabrication_id} · {self.produit_id} × {self.quantite}'
