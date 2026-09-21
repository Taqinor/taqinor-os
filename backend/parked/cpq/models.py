"""Modèles CPQ (Configure-Price-Quote enterprise).

Toutes les liaisons vers les autres apps DOMAINE (``stock``, ``ventes``,
``crm``) sont des string-FK (M3 : aucun import de leurs ``models``). Chaque
modèle porte un FK ``company`` (multi-tenant) posé côté serveur.
"""
import uuid

from django.conf import settings
from django.db import models

from core.models import TenantModel


class OptionProduit(TenantModel):
    """NTCPQ1 — Option de configuration d'un produit.

    Regroupe des produits par ``groupe_option`` (ex. « Onduleur », « Batterie »)
    et marque si le groupe est obligatoire dans une configuration. String-FK
    vers ``stock.Produit`` (aucun import cross-app).

    ARC1 — hérite de ``core.models.TenantModel`` (FK ``company`` + timestamps).
    ``company`` est REDÉCLARÉ ci-dessous à l'identique pour préserver
    l'accesseur inverse historique (``company.cpq_options_produit``)."""
    # Redéclaré à l'identique (ARC1) : conserve le related_name historique.
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_options_produit')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: option sans objet si produit supprimé
        related_name='cpq_options')
    groupe_option = models.CharField(
        max_length=100,
        help_text="Groupe de l'option (ex. « Onduleur », « Batterie »).")
    obligatoire = models.BooleanField(
        default=False,
        help_text='Le groupe doit être renseigné dans la configuration.')

    class Meta:
        verbose_name = 'Option produit'
        verbose_name_plural = 'Options produit'
        ordering = ['groupe_option', 'id']
        indexes = [
            models.Index(fields=['company', 'groupe_option'],
                         name='cpq_optprod_co_grp'),
        ]

    def __str__(self):
        return f'{self.groupe_option} · produit {self.produit_id}'


class ContrainteCompatibilite(TenantModel):
    """NTCPQ1 — Contrainte de compatibilité entre deux produits.

    ``INCOMPATIBLE`` : les deux produits ne peuvent coexister (violation
    bloquante). ``REQUIERT`` : si ``produit_a`` est présent, ``produit_b`` doit
    l'être aussi (bloquant). ``RECOMMANDE`` : suggestion (avertissement seul).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    class TypeContrainte(models.TextChoices):
        INCOMPATIBLE = 'INCOMPATIBLE', 'Incompatible'
        REQUIERT = 'REQUIERT', 'Requiert'
        RECOMMANDE = 'RECOMMANDE', 'Recommandé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_contraintes_compatibilite')
    produit_a = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: contrainte sans objet si produit supprimé
        related_name='cpq_contraintes_a')
    produit_b = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: contrainte sans objet si produit supprimé
        related_name='cpq_contraintes_b')
    type = models.CharField(
        max_length=20, choices=TypeContrainte.choices)
    message_utilisateur = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Message affiché à l'utilisateur quand la contrainte joue.")

    class Meta:
        verbose_name = 'Contrainte de compatibilité'
        verbose_name_plural = 'Contraintes de compatibilité'
        ordering = ['id']
        indexes = [
            models.Index(fields=['company', 'type'],
                         name='cpq_contr_co_type'),
            models.Index(fields=['company', 'produit_a'],
                         name='cpq_contr_co_pa'),
        ]

    def __str__(self):
        return f'{self.produit_a_id} {self.type} {self.produit_b_id}'

    @property
    def bloquante(self):
        """``INCOMPATIBLE`` et ``REQUIERT`` sont bloquantes ; ``RECOMMANDE``
        est un simple avertissement."""
        return self.type in (
            self.TypeContrainte.INCOMPATIBLE, self.TypeContrainte.REQUIERT)


class RegleProduitCPQ(TenantModel):
    """NTCPQ2 — Règle produit data-driven réutilisant ``core.rules``.

    ``condition_group`` est un arbre de conditions ET/OU/NON évalué par
    ``core.rules.evaluate_condition_group`` (le moteur GÉNÉRIQUE existant, jamais
    réécrit). ``actions`` est une liste libre de dicts (ex.
    ``[{"type": "exiger_option", "valeur": "triphase"}]``) renvoyée quand la
    règle se déclenche. Aucune action n'est exécutée par le modèle : le
    déclenchement est purement déclaratif (l'appelant décide de la suite).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_regles_produit')
    nom = models.CharField(max_length=150)
    condition_group = models.JSONField(
        default=dict, blank=True,
        help_text="Arbre de conditions ET/OU/NON (core.rules).")
    actions = models.JSONField(
        default=list, blank=True,
        help_text='Liste d\'actions déclenchées quand la règle est vraie.')
    # NTCPQ21 — une règle déclenchée est par défaut un AVERTISSEMENT (badge
    # rouge, jamais un blocage). Marquée bloquante, elle rend la configuration
    # invalide de façon bloquante. Défaut False ⇒ comportement inchangé.
    bloquante = models.BooleanField(
        default=False,
        help_text='Règle bloquante (et non simple avertissement) quand elle '
                  'se déclenche.')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Règle produit CPQ'
        verbose_name_plural = 'Règles produit CPQ'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_regle_co_actif'),
        ]

    def __str__(self):
        return self.nom


class OffreGroupee(TenantModel):
    """NTCPQ3 — Bundle produit à prix cascadé.

    ``prix_total`` (optionnel) : quand il est renseigné et que les lignes sont
    en mode ``FIXE``, le total du bundle PRIME et est réparti au prorata du prix
    catalogue sur les lignes lors de l'application au devis. Sinon chaque ligne
    est valorisée selon son propre ``mode_prix``.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_offres_groupees')
    nom = models.CharField(max_length=150)
    prix_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Prix fixe du bundle (mode FIXE) réparti au prorata.')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Offre groupée'
        verbose_name_plural = 'Offres groupées'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_offre_co_actif'),
        ]

    def __str__(self):
        return self.nom


class LigneOffreGroupee(models.Model):
    """NTCPQ3 — Composant d'une offre groupée.

    ``mode_prix`` : ``FIXE`` (le total du bundle prime, réparti au prorata),
    ``REMISE_PCT`` (prix catalogue moins ``valeur`` %), ``PRIX_COMPOSANT``
    (prix imposé = ``valeur``)."""
    class ModePrix(models.TextChoices):
        FIXE = 'FIXE', 'Prix fixe (bundle)'
        REMISE_PCT = 'REMISE_PCT', 'Remise %'
        PRIX_COMPOSANT = 'PRIX_COMPOSANT', 'Prix composant imposé'

    offre = models.ForeignKey(
        OffreGroupee, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — la ligne porte un prix imposé / une remise négociée (valeur) ; refuser la suppression du produit plutôt que perdre la tarification convenue du bundle
        related_name='cpq_lignes_offre')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=1)
    mode_prix = models.CharField(
        max_length=20, choices=ModePrix.choices, default=ModePrix.FIXE)
    valeur = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='% de remise (REMISE_PCT) ou prix imposé (PRIX_COMPOSANT).')

    class Meta:
        verbose_name = 'Ligne offre groupée'
        verbose_name_plural = 'Lignes offre groupée'
        ordering = ['offre_id', 'id']

    def __str__(self):
        return f'{self.offre_id} · produit {self.produit_id} × {self.quantite}'


class PrixContractuel(TenantModel):
    """NTCPQ5 — Prix négocié par contrat nommé pour un couple client/produit.

    Prime sur TOUTE liste de prix générique (segment, assignée…) pour ce couple
    client/produit tant qu'il est dans sa fenêtre de validité (priorité 1 dans
    ``ventes.services.prix_applicable``). Liaisons string-FK (aucun import des
    modèles crm/stock).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_prix_contractuels')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.CASCADE,  # on_delete: prix sans objet si client supprimé
        related_name='cpq_prix_contractuels')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.PROTECT,  # on_delete: PROTECT — prix contractuel NÉGOCIÉ client×produit (donnée réelle) ; refuser la suppression du produit plutôt que d'effacer l'accord tarifaire
        related_name='cpq_prix_contractuels')
    prix_ht = models.DecimalField(max_digits=12, decimal_places=2)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    motif = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cpq_prix_contractuels_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prix contractuel'
        verbose_name_plural = 'Prix contractuels'
        ordering = ['-date_creation', 'id']
        indexes = [
            models.Index(fields=['company', 'client', 'produit'],
                         name='cpq_prixctr_co_cl_pr'),
        ]

    def __str__(self):
        return f'{self.client_id}/{self.produit_id} @ {self.prix_ht}'

    @property
    def est_actif(self):
        """Dans sa fenêtre de validité (bornes optionnelles, ouvertes si
        non renseignées)."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.date_debut and today < self.date_debut:
            return False
        if self.date_fin and today > self.date_fin:
            return False
        return True


class SeuilMargeFamille(TenantModel):
    """NTCPQ6 — Garde-fou de marge minimale par famille (catégorie) produit.

    INTERNE only : sert au check serveur qui pose ``marge_sous_seuil`` sur le
    détail devis (staff). N'apparaît JAMAIS dans un PDF/proposition client
    (règle #4). String-FK vers ``stock.Categorie``.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_seuils_marge')
    categorie = models.ForeignKey(
        'stock.Categorie', on_delete=models.CASCADE,  # on_delete: seuil sans objet si catégorie supprimée
        related_name='cpq_seuils_marge')
    marge_min_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text='Marge minimale attendue (%) pour cette famille.')

    class Meta:
        verbose_name = 'Seuil de marge par famille'
        verbose_name_plural = 'Seuils de marge par famille'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'categorie'],
                name='cpq_seuilmarge_unique_co_cat'),
        ]

    def __str__(self):
        return f'{self.categorie_id} ≥ {self.marge_min_pct}%'


class RegleApprobationRemise(TenantModel):
    """NTCPQ7 — Règle d'approbation par PROFONDEUR de remise (calquée sur
    ``contrats.RegleApprobation``, mais par intervalle de remise % au lieu de
    montant).

    Le résolveur (``services.resoudre_regle_remise``) retient, parmi les règles
    actives de la société, la plus SPÉCIFIQUE (intervalle le plus étroit, puis
    ``priorite``, puis id récent) couvrant la remise réelle du devis.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""

    class NiveauApprobation(models.TextChoices):
        RESPONSABLE = 'responsable', 'Responsable'
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        DIRECTION = 'direction', 'Direction'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_regles_approbation_remise')
    libelle = models.CharField(max_length=200, blank=True, default='')
    remise_min_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    remise_max_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    niveau_approbation = models.CharField(
        max_length=20, choices=NiveauApprobation.choices,
        default=NiveauApprobation.RESPONSABLE)
    nombre_approbateurs = models.PositiveIntegerField(default=1)
    priorite = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Règle d'approbation de remise"
        verbose_name_plural = "Règles d'approbation de remise"
        ordering = ['-priorite', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_regleremise_co_act'),
        ]

    def __str__(self):
        return self.libelle or f'Règle remise #{self.pk}'

    def couvre(self, remise):
        """La remise (%) tombe-t-elle dans ``[remise_min_pct, remise_max_pct]``
        (bornes incluses ; borne NULL = ouverte de ce côté) ?"""
        from decimal import Decimal
        if remise is None:
            return self.remise_min_pct is None and self.remise_max_pct is None
        remise = Decimal(str(remise))
        if self.remise_min_pct is not None and remise < self.remise_min_pct:
            return False
        if self.remise_max_pct is not None and remise > self.remise_max_pct:
            return False
        return True

    def largeur_intervalle(self):
        """Largeur de l'intervalle (None = ouvert → moins spécifique)."""
        if self.remise_min_pct is None or self.remise_max_pct is None:
            return None
        return self.remise_max_pct - self.remise_min_pct


class EtapeApprobationDevis(TenantModel):
    """NTCPQ7 — Étape séquentielle d'approbation de remise d'un devis (même
    schéma que ``contrats.EtapeApprobation``).

    Statut LOCAL (``en_attente`` → ``approuve``/``rejete``), sans lien avec le
    funnel STAGES.py ni le statut du devis. ``devis`` est une string-FK vers
    ``ventes.Devis`` (aucun import cross-app des modèles).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_etapes_approbation_devis')
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.CASCADE,  # on_delete: étape sans objet si devis supprimé
        related_name='cpq_etapes_approbation')
    regle = models.ForeignKey(
        RegleApprobationRemise, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapes')
    niveau = models.PositiveIntegerField(default=1)
    niveau_approbation = models.CharField(
        max_length=20, choices=RegleApprobationRemise.NiveauApprobation.choices,
        default=RegleApprobationRemise.NiveauApprobation.RESPONSABLE)
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cpq_etapes_devis_decidees')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    decision_le = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)
    # NTCPQ33 — horodatage de la DERNIÈRE relance automatique envoyée à
    # l'approbateur (job planifié) ; NULL = jamais relancée. Empêche plus
    # d'une relance par 24h par étape (idempotence du job).
    derniere_relance_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Étape d'approbation de devis"
        verbose_name_plural = "Étapes d'approbation de devis"
        ordering = ['devis_id', 'niveau', 'id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='cpq_etapedev_co_sta'),
            models.Index(fields=['devis', 'niveau'],
                         name='cpq_etapedev_dv_niv'),
        ]

    def __str__(self):
        return f'Devis {self.devis_id} · étape {self.niveau} · {self.statut}'


class QuestionConfigurateur(TenantModel):
    """NTCPQ9 — Question du configurateur guidé (backend pour FG211).

    ``options`` (JSON) porte les choix proposés et, par convention, une clé
    ``champ`` : le nom du champ de contexte utilisé pour évaluer les règles
    produit (NTCPQ2). Ex. ``{"champ": "kwc", "choices": [...]}``. Sans ``champ``,
    la clé de contexte est ``q<id>``.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    class TypeQuestion(models.TextChoices):
        CHOIX_UNIQUE = 'CHOIX_UNIQUE', 'Choix unique'
        CHOIX_MULTIPLE = 'CHOIX_MULTIPLE', 'Choix multiple'
        NUMERIQUE = 'NUMERIQUE', 'Numérique'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_questions_configurateur')
    ordre = models.PositiveIntegerField(default=0)
    texte = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20, choices=TypeQuestion.choices,
        default=TypeQuestion.CHOIX_UNIQUE)
    options = models.JSONField(default=dict, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Question configurateur'
        verbose_name_plural = 'Questions configurateur'
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_question_co_act'),
        ]

    def __str__(self):
        return self.texte

    @property
    def champ(self):
        """Clé de contexte pour l'évaluation des règles (défaut ``q<id>``)."""
        opts = self.options if isinstance(self.options, dict) else {}
        return opts.get('champ') or f'q{self.pk}'


class SessionConfigurateur(TenantModel):
    """NTCPQ9 — Session du configurateur (anonyme ou liée à un devis brouillon).

    ``token`` identifie la session côté API. ``devis`` (string-FK) est renseigné
    quand la session a généré un devis (NTCPQ10) — sert aussi à la purge
    NTCPQ34 (une session sans devis inactive > 30 j est purgeable).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique). ``created_at``/``updated_at``
    hérités de TenantModel (à l'identique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_sessions_configurateur')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cpq_sessions_configurateur')

    class Meta:
        verbose_name = 'Session configurateur'
        verbose_name_plural = 'Sessions configurateur'
        ordering = ['-created_at', 'id']
        indexes = [
            models.Index(fields=['company', 'updated_at'],
                         name='cpq_session_co_upd'),
        ]

    def __str__(self):
        return str(self.token)


class ReponseConfigurateur(models.Model):
    """NTCPQ9 — Réponse à une question dans une session de configurateur."""
    session = models.ForeignKey(
        SessionConfigurateur, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='reponses')
    question = models.ForeignKey(
        QuestionConfigurateur, on_delete=models.CASCADE,  # on_delete: réponse sans objet si question supprimée
        related_name='reponses')
    valeur = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'Réponse configurateur'
        verbose_name_plural = 'Réponses configurateur'
        ordering = ['session_id', 'question_id']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'question'],
                name='cpq_reponse_unique_sess_q'),
        ]

    def __str__(self):
        return f'{self.session_id}/{self.question_id}={self.valeur}'


class ProduitEquivalent(TenantModel):
    """NTCPQ16 — Règle de substitution produit par tier (moteur de variantes).

    ``produit_source`` peut être remplacé par ``produit_substitut`` dans la
    variante du tier donné (économique / standard / premium). Générique
    multi-métiers — distinct du couple solaire Sans-batterie/Avec-batterie déjà
    en production, qui reste un cas spécifique.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name explicite)."""
    class Tier(models.TextChoices):
        ECONOMIQUE = 'economique', 'Économique'
        STANDARD = 'standard', 'Standard'
        PREMIUM = 'premium', 'Premium'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_produits_equivalents')
    produit_source = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: règle sans objet si produit supprimé
        related_name='cpq_equivalents_source')
    produit_substitut = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,  # on_delete: règle sans objet si substitut supprimé
        related_name='cpq_equivalents_substitut')
    tier = models.CharField(
        max_length=20, choices=Tier.choices, default=Tier.STANDARD)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Produit équivalent'
        verbose_name_plural = 'Produits équivalents'
        ordering = ['produit_source_id', 'tier', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit_source', 'produit_substitut',
                        'tier'],
                name='cpq_equiv_unique_co_src_sub_tier'),
        ]
        indexes = [
            models.Index(fields=['company', 'produit_source', 'tier'],
                         name='cpq_equiv_co_src_tier'),
        ]

    def __str__(self):
        return (f'{self.produit_source_id} → {self.produit_substitut_id} '
                f'({self.tier})')


class ParametresCPQ(TenantModel):
    """NTCPQ30 — Réglages CPQ, SINGLETON par société (pattern
    ``contrats.ParametresLocation``/ZCTR4).

    Toutes les valeurs par défaut préservent le comportement historique :
    une société sans ligne créée (``get_or_create`` côté vue) se comporte
    exactement comme avant NTCPQ30. ``approbation_active=False`` fait passer
    ``envoyer``/``generer-pdf`` en direct SANS blocage NTCPQ7 pour CETTE
    société uniquement (lu par ``services.lancer_approbation_devis``), sans
    affecter les autres sociétés.

    ARC1/SCA4 — hérite de ``core.models.TenantModel`` (FK ``company`` +
    ``created_at``/``updated_at``) comme tous les autres modèles de cette app,
    au lieu de re-hand-roller la paire multi-société. ``company`` est REDÉCLARÉ
    ci-dessous À L'IDENTIQUE : le socle fournit un ``ForeignKey``, or ce modèle
    est un SINGLETON par société — le ``OneToOneField`` (contrainte d'unicité)
    et le ``related_name`` historique ``company.cpq_parametres`` sont conservés
    tels quels. ``date_creation``/``date_modification`` restent également en
    place : ils sont exposés par ``ParametresCPQSerializer`` (contrat d'API).
    """
    # Redéclaré à l'identique (ARC1) : OneToOne singleton + related_name
    # historique — aucun changement de schéma sur la colonne company_id.
    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_parametres')
    marge_min_defaut_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Marge minimale par défaut (%) — repli quand aucun '
                  'SeuilMargeFamille ne couvre la catégorie.')
    approbation_active = models.BooleanField(
        default=True,
        help_text="Désactivé : envoyer/generer-pdf ne sont plus bloqués "
                  "par une approbation de remise en attente (NTCPQ7).")
    variantes_auto_generees = models.BooleanField(
        default=False,
        help_text='Générer automatiquement les variantes (NTCPQ16) à la '
                  'création du devis.')
    duree_validite_prix_contractuel_jours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Durée de validité par défaut d'un PrixContractuel sans "
                  "date_fin explicite (NULL = pas de limite, comportement "
                  "historique inchangé).")

    class ModeCompatibilite(models.TextChoices):
        BLOQUANT = 'BLOQUANT', 'Bloquant'
        AVERTISSEMENT = 'AVERTISSEMENT', 'Avertissement'

    # NTCPQ31 — AVERTISSEMENT par défaut : ne casse rien sur les tenants
    # existants (une violation INCOMPATIBLE/REQUIERT reste un badge NTCPQ21,
    # jamais un blocage, tant qu'une société ne bascule pas explicitement en
    # BLOQUANT).
    compatibilite_mode = models.CharField(
        max_length=20, choices=ModeCompatibilite.choices,
        default=ModeCompatibilite.AVERTISSEMENT,
        help_text='BLOQUANT empêche envoyer/generer-pdf tant qu’une '
                  'violation de compatibilité bloquante (NTCPQ1) subsiste.')
    # NTCPQ33 — nombre de jours d'attente avant relance automatique d'une
    # étape d'approbation encore en_attente (job planifié, apps/cpq/scheduled.py).
    delai_relance_approbation_jours = models.PositiveIntegerField(default=2)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres CPQ'
        verbose_name_plural = 'Paramètres CPQ'

    def __str__(self):
        return f'Paramètres CPQ — {self.company_id}'

    @classmethod
    def get_or_default(cls, company):
        """Renvoie les réglages de ``company`` SANS écrire en base (repli
        sur une instance non sauvegardée aux valeurs par défaut) — utile aux
        lectures fréquentes (ex. ``lancer_approbation_devis``) qui ne
        veulent pas créer une ligne pour chaque société lue."""
        obj = cls.objects.filter(company=company).first()
        return obj if obj is not None else cls(company=company)


class ClauseCGV(TenantModel):
    """NTCPQ11 — Clause / CGV dynamique appliquée selon le type de deal.

    ``applicable_si`` est un arbre de conditions ET/OU/NON évalué par
    ``core.rules.evaluate_condition_group`` contre le contexte du devis
    (``type_deal``, ``montant``, ``total_ht``, ``remise_globale``…). Vide =
    toujours applicable (seul ``type_deal`` filtre alors).

    ``type_deal`` est un référentiel LIBRE (texte) : vide = tous les types.
    Le snapshot des clauses retenues est figé sur
    ``ventes.Devis.clauses_appliquees`` au moment de l'envoi, jamais recalculé
    ensuite.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name explicite)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cpq_clauses_cgv')
    nom = models.CharField(max_length=150)
    corps_texte = models.TextField(
        blank=True, default='',
        help_text="Texte de la clause tel qu'il apparaîtra sur le document.")
    type_deal = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Référentiel libre (ex. « industriel »). Vide = tous types.')
    applicable_si = models.JSONField(
        default=dict, blank=True,
        help_text='Arbre de conditions ET/OU/NON (core.rules). Vide = toujours.')
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Clause / CGV'
        verbose_name_plural = 'Clauses / CGV'
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='cpq_clause_co_actif'),
        ]

    def __str__(self):
        return self.nom
