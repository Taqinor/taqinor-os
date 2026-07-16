"""
FG310 — Demande d'achat (réquisition) → approbation.

``DemandeAchat`` est la RÉQUISITION interne d'achat émise par le terrain
(« il me faut 12 panneaux pour le chantier X »), qui doit être APPROUVÉE avant de
devenir un bon de commande fournisseur (``stock.BonCommandeFournisseur``). Elle
vit dans l'app installations (réalisation chantier), se rattache à un chantier
(``Installation``, même app) et/ou un programme (``Projet``, même app), et liste
les articles souhaités (``DemandeAchatLigne`` → ``stock.Produit`` en string-FK).

Le fournisseur final n'est PAS décidé ici (c'est la RFQ FG311 + le BCF qui
tranchent). On peut indiquer un fournisseur SUGGÉRÉ (``stock.Fournisseur``,
string-FK, optionnel). Cross-app : on référence ``stock`` par STRING-FK
uniquement — aucune importation du modèle ``stock`` au chargement.

Cycle de vie PROPRE (brouillon → soumise → approuvée → refusée → commandée),
distinct des autres couches de statut de l'OS. Additif & multi-tenant : FK
``company`` posée côté serveur, jamais lue du corps.

SCA36 — pilote 3 du kit ``core.documents`` (Groupe SCA) : DÉGRADATION GRACIEUSE
SANS TOTAUX. ``DemandeAchat`` hérite de ``core.documents.DocumentMetier``
(socle ARC1 ``TenantModel`` + contrat statut/transitions) mais volontairement
PAS de ``TotauxDocumentMixin`` — le pilote qui prouve que le kit est
COMPOSABLE, pas une uniformité forcée : une demande d'achat est un document
d'APPROBATION, pas une pièce monétaire (le prix ne devient contractuel qu'au
BCF généré, YPROC5). AUCUN champ ``montant_ht``/``montant_tva``/``montant_ttc``
n'est ajouté ; ``montant_estime`` reste la property INTERNE historique
(Σ lignes, non figée) et ``DemandeAchatLigne`` reste telle quelle (pas de
conversion vers ``LigneDocumentMetier`` — pas de remise/TVA sur une
réquisition). Le flux d'approbation
(``soumettre``/``approuver``/``refuser``/``marquer_commandee``) reste sur son
moteur PROPRE (chemin ARC10 nommé — cf. docstring ``core.documents`` : le
cycle d'approbation multi-étapes est ``core.WorkflowDefinition``, jamais
dupliqué par le kit) : les actions de vue sont INCHANGÉES.

Conversion MIXTE (même principe que SCA34/OrdreSousTraitance) :
  * ``company`` — REDÉCLARÉE à l'identique (``null=True, blank=True``,
    ``related_name`` historique) : colonne DB inchangée pour ce champ ;
  * ``created_at``/``updated_at`` — NOUVEAUX champs additifs (``AddField``) ;
    ``date_creation``/``date_modification`` historiques CONSERVÉS tels quels ;
  * ``statut`` — hérité du kit (``max_length`` 20→32, élargissement pur via
    ``AlterField``) ; ``choices``/``default`` bit-identiques (5 valeurs,
    défaut ``brouillon``, adossés par ``__init_subclass__``) ;
  * ``TRANSITIONS`` — table déclarative documentaire (miroir des gardes de
    vue, hors ré-application idempotente du même statut) ; les actions de vue
    restent le point d'écriture.

Référence ``DA-YYYYMM-NNNN`` INCHANGÉE (même numéroteur anti-collision ARC6) :
non-régression de format + reprise du compteur dans
``tests_sca36_kit_demande_achat.py``.
"""
from django.conf import settings
from django.db import models

from core.documents import DocumentMetier


class DemandeAchat(DocumentMetier):
    """FG310 — réquisition d'achat soumise à approbation avant transformation en
    BCF. Multi-tenant : la société est posée côté serveur. Référence
    ``DA-YYYYMM-NNNN`` anti-collision (jamais count()+1).

    SCA36 — socle ``core.documents.DocumentMetier`` SANS ``TotauxDocumentMixin``
    (document d'approbation : aucun champ monétaire ajouté)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMISE = 'soumise', 'Soumise'
        APPROUVEE = 'approuvee', 'Approuvée'
        REFUSEE = 'refusee', 'Refusée'
        COMMANDEE = 'commandee', 'Commandée'

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE = 'haute', 'Haute'
        URGENTE = 'urgente', 'Urgente'

    # SCA36 — table déclarative du graphe d'états (kit), miroir des gardes de
    # vue historiques (soumettre/approuver/refuser/marquer_commandee +
    # generer_bcf) hors ré-application idempotente du même statut. Documentaire :
    # les actions de vue restent le point d'écriture (approbation = moteur
    # propre, chemin ARC10 nommé).
    TRANSITIONS = {
        Statut.BROUILLON: {Statut.SOUMISE},
        Statut.SOUMISE: {Statut.APPROUVEE, Statut.REFUSEE},
        Statut.APPROUVEE: {Statut.COMMANDEE},
        Statut.REFUSEE: set(),
        Statut.COMMANDEE: set(),
    }

    # Redéclarée à l'identique (SCA36) : conserve le related_name + la
    # nullabilité historiques — colonne DB inchangée (state-only).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_demandes_achat')
    reference = models.CharField(max_length=50)
    objet = models.CharField(max_length=255)
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes_achat')
    programme = models.ForeignKey(
        'installations.Projet', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='demandes_achat')
    # Fournisseur SUGGÉRÉ (non contractuel) — string-FK vers stock.
    fournisseur_suggere = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_achat_suggerees')
    # YPROC5 — BCF généré depuis cette DA (traçabilité bidirectionnelle : la DA
    # montre son BCF, la vue BCF peut filtrer par demande). String-FK,
    # nullable = comportement historique inchangé (aucun BCF généré encore).
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_achat')
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    date_besoin = models.DateField(null=True, blank=True)
    # SCA36 — ``statut`` n'est PLUS redéclaré ici : hérité du kit
    # (``DocumentMetier.statut``, ``max_length=32``) et adossé aux ``choices``/
    # ``default`` de CETTE sous-classe par ``__init_subclass__`` (mêmes 5
    # valeurs, même défaut BROUILLON — seul ``max_length`` change, 20→32,
    # élargissement pur). Cf. docstring de tête.
    motif_refus = models.TextField(blank=True, null=True)
    approuvee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_achat_approuvees')
    date_decision = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demandes_achat_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande d'achat"
        verbose_name_plural = "Demandes d'achat"
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            # Noms d'index ≤ 30 caractères.
            models.Index(fields=['company', 'statut'],
                         name='idx_da_co_statut'),
            models.Index(fields=['company', 'chantier'],
                         name='idx_da_co_chantier'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.objet}'

    @property
    def montant_estime(self):
        """Σ (quantité × prix estimé) des lignes (INTERNE)."""
        from decimal import Decimal
        return sum((ligne.total_estime for ligne in self.lignes.all()),
                   Decimal('0'))


class DemandeAchatLigne(models.Model):
    """FG310 — ligne d'une demande d'achat : un produit (string-FK vers stock),
    une quantité et un prix unitaire ESTIMÉ (INTERNE, indicatif)."""

    demande = models.ForeignKey(
        DemandeAchat, on_delete=models.CASCADE, related_name='lignes')
    # Produit catalogue (string-FK vers stock). PROTECT côté DB pour ne pas
    # casser une demande si un produit est supprimé est inutile : on garde le
    # désignation libre en repli quand le produit n'est pas catalogué.
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_demande_achat_lignes')
    designation = models.CharField(max_length=255, blank=True, null=True)
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    prix_estime = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ligne de demande d'achat"
        verbose_name_plural = "Lignes de demande d'achat"

    def __str__(self):
        return f'{self.designation or self.produit_id} × {self.quantite}'

    @property
    def total_estime(self):
        return (self.quantite or 0) * (self.prix_estime or 0)
