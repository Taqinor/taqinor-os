from decimal import Decimal

from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder


class Categorie(models.Model):
    # Tag de TYPE d'équipement optionnel et additif (L579) : permet de filtrer
    # un emplacement (slot) d'équipement de chantier par TYPE indépendamment du
    # libellé free-text de la catégorie (qu'une société peut renommer). Les
    # catégories existantes restent NON typées (None) → comportement inchangé.
    class TypeEquipement(models.TextChoices):
        PANNEAU = 'panneau', 'Panneau'
        ONDULEUR = 'onduleur', 'Onduleur'
        BATTERIE = 'batterie', 'Batterie'
        STRUCTURE = 'structure', 'Structure'
        CABLE = 'cable', 'Câble'
        PROTECTION = 'protection', 'Protection'
        POMPE = 'pompe', 'Pompe'
        VARIATEUR = 'variateur', 'Variateur'
        COMPTEUR = 'compteur', 'Compteur'
        ACCESSOIRE = 'accessoire', 'Accessoire'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories',
    )
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    ordre = models.PositiveSmallIntegerField(
        default=100,
        help_text="Ordre d'affichage délibéré (plus petit = plus haut).")
    type_equipement = models.CharField(
        max_length=20,
        choices=TypeEquipement.choices,
        null=True,
        blank=True,
        help_text="Type d'équipement (optionnel) pour filtrer les slots de "
                  "chantier par TYPE, quel que soit le libellé de la "
                  "catégorie. Vide = non typée (comportement historique).")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        unique_together = [('company', 'nom')]
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom


class Fournisseur(models.Model):
    # DC34 — un SEUL référentiel tiers-fournisseur couvre le matériel ET la
    # prestation (sous-traitance). Le `type` ventile la nature du fournisseur ;
    # les données propres au sous-traitant (métier, archivage) vivent sur le
    # satellite OneToOne `SousTraitantProfile`. Il n'existe plus de référentiel
    # sous-traitant parallèle (l'ancien installations.SousTraitant est fondu ici).
    class Type(models.TextChoices):
        MATERIEL = 'materiel', 'Matériel'
        SERVICE = 'service', 'Service / sous-traitance'
        MIXTE = 'mixte', 'Mixte (matériel + service)'

    # XPUR4 — statut fournisseur (défaut actif = comportement historique
    # inchangé). Enforcé à la CRÉATION d'un BCF (bloque_commandes/total) et
    # d'un PaiementFournisseur (bloque_paiements/total).
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        BLOQUE_COMMANDES = 'bloque_commandes', 'Bloqué (commandes)'
        BLOQUE_PAIEMENTS = 'bloque_paiements', 'Bloqué (paiements)'
        BLOQUE_TOTAL = 'bloque_total', 'Bloqué (total)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fournisseurs',
    )
    nom = models.CharField(max_length=255)
    # DC34 — nature du fournisseur. Par défaut « matériel » (compat ascendante :
    # tout fournisseur existant reste matériel). Un sous-traitant est « service ».
    type = models.CharField(
        max_length=10, choices=Type.choices, default=Type.MATERIEL,
        help_text="Nature du fournisseur : matériel, service (sous-traitance) "
                  "ou mixte.")
    contact_personne = models.CharField(
        max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)

    # ── DC15 — Identité légale du fournisseur (saisie une seule fois) ─────────
    # ICE / IF / RC / RIB sont les identifiants légaux marocains du fournisseur.
    # Saisis ici une fois, ils sont CONSOMMÉS par les comptes auxiliaires de la
    # comptabilité (DC30), les parties au contrat (DC31), les PDF de facture
    # fournisseur (AP) et les profils sous-traitant — sans jamais re-saisir
    # l'identité ailleurs. Tous optionnels (compat ascendante : aucun
    # fournisseur existant n'est impacté). Aucun montant / prix d'achat ici.
    ice = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="Identifiant Commun de l'Entreprise (ICE).")
    identifiant_fiscal = models.CharField(
        max_length=20, blank=True, null=True,
        help_text='Identifiant Fiscal (IF).')
    rc = models.CharField(
        max_length=40, blank=True, null=True,
        help_text='Numéro du Registre du Commerce (RC).')
    rib = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='RIB / IBAN du fournisseur (règlements AP).')
    # XPLT14 — champs personnalisés (apps.customfields, module='fournisseur').
    custom_data = models.JSONField(null=True, blank=True)

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.ACTIF,
        help_text='Statut fournisseur : actif, bloqué commandes, bloqué '
                  'paiements ou bloqué total.')
    motif_blocage = models.TextField(blank=True, null=True)

    # ── XPUR5 — fiche fournisseur enrichie ──────────────────────────────────
    categorie = models.ForeignKey(
        'CategorieFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='fournisseurs')
    # Préremplit XPUR3 (devise du BCF) / le BCF (incoterm).
    devise_defaut = models.CharField(
        max_length=3, blank=True, default='',
        help_text='Devise par défaut pour les BCF de ce fournisseur '
                  "(vide = MAD, comportement historique).")
    incoterm = models.CharField(
        max_length=10, blank=True, default='',
        help_text="Incoterm par défaut (EXW, FOB, CIF…). Vide = non défini.")

    # ── XPUR6 — conditions de paiement fournisseur ──────────────────────────
    # Délai en jours (0 = comptant, comportement historique : date_echeance
    # reste saisie à la main). fin_de_mois arrondit l'échéance à la fin du
    # mois calendaire suivant l'ajout du délai (« 60 j fin de mois »).
    delai_paiement_jours = models.PositiveIntegerField(default=0)
    fin_de_mois = models.BooleanField(default=False)
    # Escompte paiement anticipé (type 2/10 net 30) : escompte_pct % si réglé
    # dans les escompte_jours suivant la date de facture. 0 = pas d'escompte
    # (comportement historique).
    escompte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    escompte_jours = models.PositiveIntegerField(default=0)

    # ── ARC24 — référentiel des conditions de paiement (additif, optionnel) ──
    # FK nullable (string-FK — jamais d'import de apps.parametres.models ici)
    # vers parametres.ConditionPaiement : MIROIR des trois champs numériques
    # ci-dessus (delai_paiement_jours/fin_de_mois/escompte_pct restent MAÎTRES).
    # Backfillée depuis les triplets distincts par la commande
    # ``backfill_conditions_paiement``. Vide = comportement historique inchangé.
    condition_paiement_ref = models.ForeignKey(
        'parametres.ConditionPaiement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fournisseurs',
        verbose_name='Condition de paiement (référentiel)',
        help_text="Condition du référentiel Paramètres reflétant le délai/"
                  "escompte de ce fournisseur (miroir).")

    # ── ARC18 — Pont additif vers le répertoire unifié Tiers ──
    # FK nullable (string-FK — jamais d'import de apps.tiers.models ici, stock
    # reste découplé de la couche fondation par référence string). L'identité
    # reste MAÎTRE ici ; ``tiers`` n'en est qu'un MIROIR one-way, réversible,
    # posé par le hook de sauvegarde (voir apps/stock/tiers_bridge.py) et
    # backfillé par la commande ``backfill_tiers``. Vide = pas encore relié
    # (comportement API historique strictement inchangé).
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='fournisseurs',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié des parties prenantes reflétant "
                  "ce fournisseur. Renseignée automatiquement (miroir).")

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom


def _default_portail_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_portail_expiry():
    from datetime import timedelta
    from django.utils import timezone
    return timezone.now() + timedelta(days=90)


class PortailFournisseurToken(models.Model):
    """XPUR22 — jeton public, révocable/expirant, du portail fournisseur en
    lecture seule (auto-généré depuis la fiche fournisseur). Mêmes garanties
    que ``ventes.ShareLink``/``sav.Ticket.share_token`` : imprévisible, jamais
    exposé côté client, isolation stricte au SEUL fournisseur porteur du
    jeton (jamais les documents d'un autre fournisseur, jamais de marge)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='portail_fournisseur_tokens')
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.CASCADE,
        related_name='portail_tokens')
    token = models.CharField(
        max_length=64, unique=True, default=_default_portail_token,
        editable=False)
    expires_at = models.DateTimeField(default=_default_portail_expiry)
    revoked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='portail_fournisseur_tokens_crees')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Jeton portail fournisseur'
        verbose_name_plural = 'Jetons portail fournisseur'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token'], name='stock_pftoken_token_idx')]

    def __str__(self):
        return f'Portail {self.fournisseur_id} · {self.token[:8]}…'

    @property
    def est_valide(self):
        from django.utils import timezone
        return not self.revoked and self.expires_at > timezone.now()


class CategorieFournisseur(models.Model):
    """XPUR5 — référentiel léger de catégories fournisseur (type ``Marque``),
    filtrable dans la liste. Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='categories_fournisseur')
    nom = models.CharField(max_length=100)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Catégorie fournisseur'
        verbose_name_plural = 'Catégories fournisseur'

    def __str__(self):
        return self.nom


class ContactFournisseur(models.Model):
    """XPUR5 — contact secondaire d'un fournisseur (N contacts par
    fournisseur ; ``Fournisseur.contact_personne`` reste le contact
    principal, comportement historique inchangé)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='contacts_fournisseur')
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.CASCADE, related_name='contacts')
    nom = models.CharField(max_length=255)
    fonction = models.CharField(max_length=120, blank=True, default='')
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = 'Contact fournisseur'
        verbose_name_plural = 'Contacts fournisseur'
        ordering = ['fournisseur_id', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.fournisseur_id})'


class SousTraitantProfile(models.Model):
    """DC34 — satellite OneToOne portant les champs PROPRES au sous-traitant sur
    un ``Fournisseur`` de type « service ».

    Le tiers lui-même (raison sociale, contact, ICE/IF/RC/RIB, adresse) vit sur
    le ``Fournisseur`` (source unique d'identité, DC15) : on ne re-stocke rien
    ici. Ce satellite n'ajoute que ce qui est SPÉCIFIQUE à la sous-traitance :
    le corps de métier et le drapeau d'archivage. Il remplace l'ancien modèle
    parallèle ``installations.SousTraitant`` (fondu dans Fournisseur par DC34).

    Multi-tenant : ``company`` posée côté serveur ; elle DOIT rester égale à la
    société du fournisseur porteur (garanti côté service). Couche INDÉPENDANTE
    des statuts de l'OS — un sous-traitant n'a qu'un drapeau ``actif``."""

    class Metier(models.TextChoices):
        TERRASSEMENT = 'terrassement', 'Terrassement'
        GENIE_CIVIL = 'genie_civil', 'Génie civil'
        ELECTRICITE = 'electricite', 'Électricité'
        LEVAGE = 'levage', 'Levage'
        TRANSPORT = 'transport', 'Transport'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='sous_traitant_profils')
    fournisseur = models.OneToOneField(
        Fournisseur, on_delete=models.CASCADE,
        related_name='profil_sous_traitant')
    # max_length=20 couvre le plus long code de Metier ('terrassement' = 12).
    metier = models.CharField(
        max_length=20, choices=Metier.choices, default=Metier.AUTRE)
    actif = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sous_traitant_profils_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil sous-traitant'
        verbose_name_plural = 'Profils sous-traitant'
        ordering = ['fournisseur__nom']
        indexes = [
            # Noms d'index ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'metier'],
                         name='idx_stp_co_metier'),
            models.Index(fields=['company', 'actif'],
                         name='idx_stp_co_actif'),
        ]

    def __str__(self):
        return f'{self.fournisseur.nom} · {self.get_metier_display()}'


class AchatsParametres(models.Model):
    """XPUR1 — paramètres achats/fournisseurs PAR SOCIÉTÉ (un seul par
    company, créé paresseusement via ``get_or_create``). Regroupe les
    interrupteurs fins que les tâches XPUR ajoutent au fil de l'eau
    (blocage paiement sur conformité expirée XPUR1, RAS-TVA XPUR2,
    tolérances 3-voies XPUR10…) SANS toucher à ``apps.parametres`` (foundation
    app hors périmètre de ce lot) ni dupliquer un référentiel par tâche.
    Défauts = comportement actuel inchangé (tout OFF / tolérances à 0)."""

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='achats_parametres')
    # XPUR1 — quand actif, un PaiementFournisseur est refusé si le
    # fournisseur a un document de conformité OBLIGATOIRE manquant/expiré.
    bloquer_paiement_conformite_expiree = models.BooleanField(default=False)
    # XPUR2 — quand actif, la RAS-TVA (LF 2024) est calculée et retenue à
    # chaque PaiementFournisseur. OFF par défaut = comportement historique
    # (paiement intégral, aucune retenue).
    ras_tva_actif = models.BooleanField(default=False)
    # ── XPUR10 — tolérances par défaut du rapprochement 3 voies (FG131) ────
    # Pré-remplissent `creer_rapprochement_3voies` (compta) : écart prix % +
    # absolu MAD, écart quantité %. 0 = comportement historique inchangé
    # (tolérance nulle, déjà le défaut actuel de FG131).
    tolerance_prix_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    tolerance_prix_absolu_mad = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    tolerance_quantite_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0)
    # XPUR13 — écart % (par rapport au dernier prix / prix moyen d'achat)
    # au-delà duquel une ligne de BCF lève un warning « prix hors norme ».
    # 0 = comportement historique inchangé (aucun seuil, pas de warning
    # d'écart — seul le dépassement du prix CONTRACTUEL est alors signalé).
    seuil_deviation_prix_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Écart %% (vs dernier prix/prix moyen) déclenchant un '
                  'warning sur une ligne de BCF. 0 = désactivé.')
    # XPUR26 — préparation mandat e-facturation DGI 2026 (ENTRANT). Quand
    # actif, l'import d'un fichier UBL 2.1 crée une FactureFournisseur
    # BROUILLON pré-remplie. OFF par défaut = total no-op, aucun appel
    # externe (la validation plateforme DGI réelle attendra le mandat).
    einvoicing_entrant_actif = models.BooleanField(default=False)
    # XSTK6 — bloque la sortie d'un LOT périmé (registre `LotEntrepot`). ON
    # par défaut (garde de sécurité), contournable avec motif tracé via
    # `sortir_lot_entrepot(..., forcer=True, motif=...)`.
    bloquer_stock_perime = models.BooleanField(default=True)
    # XSTK8 — refuse par défaut toute écriture qui ferait passer
    # `Produit.quantite_stock`/`StockEmplacement.quantite` sous zéro (sorties
    # chantier/assemblage, retours fournisseur…). False = comportement
    # historique inchangé (aucun garde, comme avant XSTK8) si activé
    # explicitement par la société.
    stock_negatif_autorise = models.BooleanField(default=False)
    # ZPUR7 — quand actif, la tâche beat `stock.relancer_bcf_en_retard`
    # PROPOSE un brouillon de relance (WhatsApp/email, jamais envoyé sans
    # clic) pour les BCF ENVOYE en retard. OFF par défaut = no-op total (la
    # tâche autodécouverte tourne mais ne fait rien tant que la société ne
    # l'active pas).
    relance_bcf_actif = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paramètres achats'
        verbose_name_plural = 'Paramètres achats'

    def __str__(self):
        return f'Paramètres achats · {self.company_id}'

    @classmethod
    def for_company(cls, company):
        """Renvoie (en le créant si besoin) le réglage de la société. Défauts
        = comportement historique inchangé."""
        obj, _created = cls.objects.get_or_create(company=company)
        return obj


class DocumentConformiteFournisseur(models.Model):
    """XPUR1 — pièce de conformité fiscale/administrative d'un FOURNISSEUR
    (matériel ET service — DC34 a fondu les deux populations dans le même
    ``Fournisseur``, donc ce modèle sert les deux sans dupliquer FG307).

    Miroir de ``installations.AttestationSousTraitant`` (FG307) mais posé côté
    ``apps.stock`` puisque ``Fournisseur`` y vit désormais. Une pièce expirée
    (ou manquante quand ``obligatoire``) déclenche un WARNING à la création
    d'un BCF et peut bloquer le ``PaiementFournisseur`` (paramétrable par
    société via ``CompanyProfile.bloquer_paiement_conformite_expiree`` —
    XPUR1). Additif, multi-tenant (company posée côté serveur)."""

    class Type(models.TextChoices):
        ARF = 'arf', 'Attestation de régularité fiscale (ARF)'
        CNSS = 'cnss', 'Attestation CNSS'
        RC = 'rc', 'Registre du commerce (RC)'
        ASSURANCE = 'assurance', 'Assurance'
        AUTRE = 'autre', 'Autre pièce'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='documents_conformite_fournisseur')
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.CASCADE,
        related_name='documents_conformite')
    type_document = models.CharField(
        max_length=20, choices=Type.choices, default=Type.AUTRE)
    reference = models.CharField(max_length=120, blank=True, null=True)
    date_emission = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True)
    obligatoire = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documents_conformite_fournisseur_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document de conformité fournisseur'
        verbose_name_plural = 'Documents de conformité fournisseur'
        ordering = ['fournisseur_id', 'type_document']
        indexes = [
            models.Index(fields=['company', 'fournisseur'],
                         name='idx_docf_co_fourn'),
            models.Index(fields=['company', 'date_expiration'],
                         name='idx_docf_co_expir'),
        ]

    def __str__(self):
        return f'{self.get_type_document_display()} · {self.fournisseur_id}'

    def est_valide(self, a_la_date=None):
        """Vrai si la pièce est encore valide à la date donnée (aujourd'hui
        par défaut). Sans date d'expiration = considérée valide (pièce sans
        échéance)."""
        from django.utils import timezone
        if self.date_expiration is None:
            return True
        ref = a_la_date or timezone.now().date()
        return self.date_expiration >= ref


class Marque(models.Model):
    """Marque produit gérée (Paramètres → Stock). `Produit.marque` reste un
    texte libre (compat ascendante) ; cette liste sert de référentiel + ajout
    libre dans le formulaire produit. Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='marques')
    nom = models.CharField(max_length=100)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Marque'

    def __str__(self):
        return self.nom


class Produit(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='produits',
    )
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    sku = models.CharField(max_length=50, blank=True, null=True)
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_stock = models.IntegerField(default=0)
    seuil_alerte = models.IntegerField(default=0)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits'
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='produits'
    )
    tva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    # ── Fiche commerciale (devis PDF riches, 2026-06) — tout optionnel ──
    marque = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(
        blank=True, null=True,
        help_text='Lignes descriptives affichées sous la désignation dans les PDF (une par ligne).')
    garantie = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Texte garantie constructeur / performance.')

    # ── Durée de garantie structurée (alimente les horloges de garantie du
    #    parc d'équipements). Numérique, en MOIS, optionnelle : un produit sans
    #    durée renseignée donne « garantie non renseignée » sur son équipement
    #    (même logique que les pompes sans prix). Le texte `garantie` ci-dessus
    #    reste en place et inchangé. Aucune durée n'est inventée par le code. ──
    garantie_mois = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Garantie équipement en mois (laisser vide si non renseignée).')
    garantie_production_mois = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Garantie production (panneaux) en mois — souvent 300 à 360.')

    # ── Spécifications pompage solaire (mode Agricole) ──
    pompe_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance pompe en chevaux (CV).')
    hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Hauteur manométrique totale max (m).')
    debit_m3j = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Débit max indicatif (m³/jour).')
    pompe_kw = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Puissance nominale (kW) — pompes ET variateurs.')
    tension_v = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Tension nominale (V) : 220 ou 380.')
    courbe_pompe = models.JSONField(
        null=True, blank=True,
        help_text="Courbe de performance constructeur : "
                  '{"debits_m3h": [0, 12, ...], "hmt_m": [91, 85, ...]} '
                  '(HMT délivrée à chaque débit).')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)

    # ── FG54 — Réapprovisionnement auto ──────────────────────────────────────
    # Quantité cible à recomander quand le stock passe sous seuil_alerte.
    # Si non renseignée, la suggestion de réappro propose seuil_alerte × 2
    # (comportement conservateur par défaut). INTERNE — jamais client-facing.
    quantite_reappro_cible = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Quantité cible à commander lors d\'un réapprovisionnement '
                  '(facultatif ; défaut = seuil_alerte × 2).')

    # ── XCTR17 — Location de matériel SORTANTE (aux clients) — fondation ────
    # `louable` = ce produit peut faire l'objet d'un `contrats.OrdreLocation`.
    # Faux par défaut : AUCUN produit existant ne devient louable tant que
    # cette case n'est pas cochée explicitement (comportement inchangé). Les
    # tarifs sont OPTIONNELS et purement indicatifs (l'ordre de location peut
    # les surcharger) ; aucun n'est requis pour cocher `louable`.
    louable = models.BooleanField(
        default=False, verbose_name='Louable aux clients',
        help_text="Peut faire l'objet d'un ordre de location client "
                  '(groupe électrogène, pompe, nacelle…).')
    tarif_location_jour = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Tarif location / jour')
    tarif_location_semaine = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Tarif location / semaine')
    tarif_location_mois = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Tarif location / mois')

    # ── XPOS9 — Capture n° de série à la vente → garantie SAV automatique ───
    # Flag additif : off par défaut, rien ne change pour un produit existant.
    # Quand actif, la vente comptoir (apps.pos) invite à saisir/scanner le(s)
    # n° de série vendu(s) et crée automatiquement l'Equipement SAV garanti
    # (apps.sav.services.creer_equipement_depuis_vente_pos).
    suivi_serie = models.BooleanField(
        default=False, verbose_name='Suivi par n° de série',
        help_text="Active la saisie du n° de série à la vente comptoir et "
                  "la création automatique de l'équipement SAV garanti "
                  '(onduleur, batterie…).')

    # ── XSTK3 — code-barres FABRICANT (EAN/UPC/GTIN) ────────────────────────
    # Distinct du jeton interne `PRODUIT:<id>` (N20/labels.py, imprimé PAR
    # nous) : celui-ci est imprimé PAR LE FABRICANT sur l'emballage. Nullable
    # — un produit sans code-barres garde le comportement historique (scan
    # uniquement via le jeton interne). Unicité PAR SOCIÉTÉ quand renseigné.
    code_barres = models.CharField(
        max_length=64, blank=True, null=True,
        verbose_name='Code-barres fabricant (EAN/UPC/GTIN)',
        help_text='Code-barres imprimé par le fabricant (EAN-13, UPC, '
                  'GTIN…) — distinct du jeton interne de scan.')

    # ── XSTK15 — Unité de mesure du stock ───────────────────────────────────
    # Défaut « unité » = comportement historique inchangé (tout produit
    # existant reste compté en entiers sans unité). Le câble solaire
    # s'achète en touret de 100 m et se vend au mètre : le STOCK reste
    # stocké dans UNE SEULE unité (jamais de double comptage) — les
    # conditionnements d'achat (`ConditionnementProduit`) convertissent VERS
    # cette unité à l'écriture du mouvement.
    unite_stock = models.CharField(
        max_length=20, default='unité',
        verbose_name='Unité de stock',
        help_text="Unité dans laquelle le stock est compté (unité/m/kg…).")
    # ── ARC27 — référentiel des unités de mesure (additif, optionnel) ──
    # FK nullable (string-FK — jamais d'import de apps.parametres.models ici)
    # vers parametres.UniteMesure : MIROIR de ``unite_stock`` (qui reste MAÎTRE).
    # Backfillée depuis les codes distincts par la commande
    # ``backfill_unites_mesure``. Vide = comportement historique inchangé.
    unite = models.ForeignKey(
        'parametres.UniteMesure',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='produits',
        verbose_name='Unité (référentiel)',
        help_text="Unité du référentiel Paramètres reflétant ``unite_stock`` "
                  "(miroir — source du libellé affiché).")

    # ── XSTK19 — Code SH (HS) + pays d'origine → dossier d'import (ADII) ────
    # Nullables : un produit sans ces champs garde le comportement historique
    # (saisie manuelle du dossier d'import). Pré-remplit les lignes du
    # dossier d'import (`installations.DossierImport`) depuis le BCF lié.
    code_sh = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Code SH (HS)',
        help_text="Code du Système Harmonisé (nomenclature douanière) — "
                  'utilisé pour pré-remplir le dossier d\'import ADII.')
    pays_origine = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Pays d'origine",
        help_text="Pays d'origine du produit — utilisé pour pré-remplir le "
                  'dossier d\'import ADII.')

    # ── ZPUR1 — Politique de facturation d'achat (parité « Bill Control »
    # Odoo : Ordered vs Received quantities) ───────────────────────────────
    # Défaut `sur_reception` = comportement HISTORIQUE inchangé (FG56 :
    # `receptions-fournisseur/{id}/facturer/` reste l'unique chemin). Un
    # produit `sur_commande` peut en plus être facturé DIRECTEMENT depuis un
    # BCF (`bons-commande-fournisseur/{id}/facturer/`, ZPUR1) sans exiger de
    # réception au préalable — utile pour un import payé à la commande.
    class PolitiqueFacturationAchat(models.TextChoices):
        SUR_RECEPTION = 'sur_reception', 'Sur réception'
        SUR_COMMANDE = 'sur_commande', 'Sur commande'

    politique_facturation_achat = models.CharField(
        max_length=20, choices=PolitiqueFacturationAchat.choices,
        default=PolitiqueFacturationAchat.SUR_RECEPTION,
        verbose_name="Politique de facturation d'achat",
        help_text='« Sur réception » = comportement historique (FG56, '
                  'facturé depuis la réception). « Sur commande » = peut '
                  "être facturé directement depuis le BCF, sans exiger de "
                  'réception préalable (ZPUR1).')

    # ── XCTR1 — Produit récurrent (abonnement) → conversion auto en contrat de
    # maintenance à l'acceptation d'un devis. `est_recurrent` = False par
    # défaut : AUCUN produit existant ne devient récurrent tant que cette case
    # n'est pas cochée (comportement inchangé). `periodicite_defaut` est
    # NULLABLE — vide = pas de préconisation de périodicité (le receiver
    # retombe sur ContratMaintenance.Periodicite.ANNUEL).
    class PeriodiciteDefaut(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'
        SEMESTRIEL = 'semestriel', 'Semestriel'
        ANNUEL = 'annuel', 'Annuel'

    est_recurrent = models.BooleanField(
        default=False, verbose_name='Produit récurrent (abonnement)',
        help_text='Prestation d\'abonnement (maintenance, monitoring…) : une '
                  'ligne de ce produit sur un devis accepté crée '
                  'automatiquement un contrat de maintenance SAV.')
    periodicite_defaut = models.CharField(
        max_length=15, choices=PeriodiciteDefaut.choices,
        null=True, blank=True,
        verbose_name='Périodicité par défaut',
        help_text='Périodicité proposée au contrat de maintenance créé '
                  '(vide = annuel).')
    # ── ZSAL9 — Avertissement de vente (« sale warnings » façon Odoo) ──
    # Message optionnel affiché quand ce produit est ajouté à un devis (ex.
    # « produit en rupture prolongée »). Si ``avertissement_bloquant`` est True,
    # une garde serveur refuse l'acceptation / la génération de facture d'un
    # devis contenant ce produit SAUF override responsable/admin journalisé
    # (patron XFAC28). Vide (défaut) = comportement historique inchangé. Jamais
    # de prix d'achat exposé via ce champ.
    avertissement_vente = models.TextField(
        blank=True, default='',
        verbose_name='Avertissement de vente',
        help_text="Message affiché au devis quand ce produit est ajouté.")
    avertissement_bloquant = models.BooleanField(
        default=False,
        verbose_name='Avertissement bloquant',
        help_text="Si activé, empêche l'acceptation/facturation sans override "
                  "responsable/admin.")

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        unique_together = [('company', 'sku')]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code_barres'],
                condition=~models.Q(
                    code_barres__isnull=True) & ~models.Q(code_barres=''),
                name='stock_produit_company_code_barres_uniq'),
        ]

    def __str__(self):
        return self.nom

    def _sync_unite_ref(self):
        """WIR97 / ARC27 — maintient la FK ``unite`` alignée sur le code MAÎTRE
        ``unite_stock``.

        Relie le produit à l'unité ACTIVE du référentiel Paramètres
        (``parametres.UniteMesure``) de même code, ou délie (``None``) si aucune
        ne correspond. Rend la FK EFFECTIVEMENT la source du libellé lu par
        ``ProduitSerializer.unite_stock_display`` — au lieu d'un miroir figé par
        un backfill ponctuel. Purement additif : ``unite_stock`` reste MAÎTRE ;
        sans société ou sans unité de référence correspondante, on retombe sur
        le code brut (comportement historique, aucune régression)."""
        if not self.company_id:
            return
        # parametres est une app de FONDATION (import descendant autorisé,
        # cf. CLAUDE.md) — jamais un import cross-app d'une app métier.
        from apps.parametres.models import UniteMesure
        code = (self.unite_stock or '').strip()
        match = None
        if code:
            match = UniteMesure.objects.filter(
                company_id=self.company_id, code=code, actif=True).first()
        self.unite = match

    def save(self, *args, **kwargs):
        # Ne resynchronise la FK unité que sur un save COMPLET ou une MAJ
        # touchant ``unite_stock`` — jamais quand le backfill pose ``unite``
        # seule (``update_fields=['unite']``), pour rester idempotent avec lui.
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'unite_stock' in update_fields:
            self._sync_unite_ref()
            if update_fields is not None and 'unite' not in update_fields:
                kwargs['update_fields'] = list(update_fields) + ['unite']
        super().save(*args, **kwargs)


# ── XSTK15 — Conditionnements d'achat (touret/carton…) ───────────────────────

class ConditionnementProduit(models.Model):
    """XSTK15 — un conditionnement d'ACHAT d'un produit (« Touret 100 m »,
    « Carton 50 ») avec son facteur de conversion VERS l'unité de stock du
    produit (`Produit.unite_stock`). Le stock reste stocké dans UNE SEULE
    unité (jamais de double comptage) : recevoir « 2 tourets de 100 m »
    incrémente 200 m via ``facteur``. Code-barres optionnel (résolution par
    scan, XSTK3)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='conditionnements_produit')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='conditionnements')
    nom = models.CharField(
        max_length=100,
        help_text='Ex. « Touret 100 m », « Carton 50 ».')
    facteur = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Combien d'unités de stock ce conditionnement représente "
                  '(ex. 100 pour un touret de 100 m).')
    code_barres = models.CharField(
        max_length=64, blank=True, null=True,
        help_text='Code-barres du conditionnement (optionnel, résolution '
                  'par scan).')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conditionnement produit'
        verbose_name_plural = 'Conditionnements produit'
        ordering = ['produit__nom', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code_barres'],
                condition=~models.Q(
                    code_barres__isnull=True) & ~models.Q(code_barres=''),
                name='stock_conditionnement_company_code_barres_uniq'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.produit.nom})'


class LotEntrepot(models.Model):
    """XSTK6 — registre de LOTS en entrepôt (miroir d'
    ``installations.SerieEntrepot`` FG323, mais pour du stock non sérialisé
    suivi PAR LOT : batteries, produits d'étanchéité, tout ce qui porte
    ``numero_lot``/``date_peremption`` — FG64). Alimenté à la CONFIRMATION
    d'une réception (une ligne dont ``numero_lot`` est renseigné) ;
    décrémenté à la sortie (FEFO — péremption la plus proche d'abord).

    ``quantite_restante`` == 0 signifie « lot épuisé » (conservé pour
    l'historique/traçabilité, jamais supprimé). Multi-tenant : ``company``
    posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='lots_entrepot')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='lots_entrepot')
    numero_lot = models.CharField(max_length=100)
    date_peremption = models.DateField(null=True, blank=True)
    # Référence par nom de classe (chaîne) : `EmplacementStock` est défini
    # PLUS BAS dans ce fichier (ordre historique des classes inchangé).
    emplacement = models.ForeignKey(
        'EmplacementStock', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_entrepot')
    quantite_recue = models.IntegerField(default=0)
    quantite_restante = models.IntegerField(default=0)
    reference_reception = models.CharField(
        max_length=80, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lots_entrepot_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lot en entrepôt'
        verbose_name_plural = 'Lots en entrepôt'
        ordering = ['date_peremption', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'produit'],
                         name='idx_lotent_co_produit'),
            models.Index(fields=['company', 'date_peremption'],
                         name='idx_lotent_co_peremption'),
        ]

    def __str__(self):
        return f'{self.numero_lot} ({self.produit_id}) — {self.quantite_restante}'

    @property
    def est_perime(self):
        """Vrai si la date de péremption est dépassée (jamais pour un lot
        sans date — comportement historique inchangé)."""
        if not self.date_peremption:
            return False
        from django.utils import timezone
        return self.date_peremption < timezone.now().date()


class MouvementStock(models.Model):
    """Entrées / Sorties / Transferts de stock avec traçabilité complète."""

    class TypeMouvement(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'
        TRANSFERT = 'transfert', 'Transfert'
        AJUSTEMENT = 'ajustement', 'Ajustement'
        # XMFG11 — rebut de production (casse/défaut/erreur), distinct d'un
        # simple ajustement anonyme : toujours motivé + rattaché à un document
        # source (ex. un ordre d'assemblage) via `reference`.
        REBUT = 'rebut', 'Rebut'

    class MotifRebut(models.TextChoices):
        CASSE = 'casse', 'Casse'
        DEFAUT = 'defaut', 'Défaut'
        ERREUR = 'erreur', 'Erreur'
        # XSTK10 — motifs additionnels pour la mise au rebut manuelle
        # (`produits/{id}/rebuter/`), en plus des motifs XMFG11 existants.
        OBSOLETE = 'obsolete', 'Obsolète'
        PERIME = 'perime', 'Périmé'
        VOL = 'vol', 'Vol'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mouvements_stock',
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name='mouvements'
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TypeMouvement.choices,
    )
    quantite = models.IntegerField()
    quantite_avant = models.IntegerField()
    quantite_apres = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    # XMFG11 — motif du rebut (uniquement pour type_mouvement=REBUT). NULL
    # pour tous les autres types de mouvement — comportement historique inchangé.
    motif_rebut = models.CharField(
        max_length=10, choices=MotifRebut.choices, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mouvements_stock'
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de Stock"
        verbose_name_plural = "Mouvements de Stock"
        ordering = ['-date']

    def __str__(self):
        return f"{self.type_mouvement} | {self.produit.nom} | {self.quantite}"


class EmplacementStock(models.Model):
    """N15 — Emplacement de stock (dépôt principal, camionnette, dépôt secondaire…).

    Le stock TOTAL d'un produit reste `Produit.quantite_stock` (canonique,
    inchangé : réceptions, ventes, inventaire continuent de l'alimenter). Cette
    couche se contente de VENTILER ce total entre emplacements. L'emplacement
    PRINCIPAL détient le reste (total − somme des autres emplacements), si bien
    que tout le stock existant est par défaut au dépôt principal et que le
    comportement actuel est strictement inchangé. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='emplacements_stock')
    nom = models.CharField(max_length=100)
    is_principal = models.BooleanField(
        default=False,
        help_text='Le dépôt principal détient le stock non ventilé (un seul '
                  'par société).')
    ordre = models.PositiveSmallIntegerField(default=100)
    archived = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Emplacement de stock'
        verbose_name_plural = 'Emplacements de stock'
        unique_together = [('company', 'nom')]
        ordering = ['-is_principal', 'ordre', 'nom']

    def __str__(self):
        return self.nom


class StockEmplacement(models.Model):
    """Quantité d'un produit dans un emplacement NON principal.

    La quantité de l'emplacement principal n'est jamais stockée : elle est
    DÉRIVÉE (total − somme des emplacements non principaux) pour que le total
    canonique et la ventilation ne puissent pas diverger.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stocks_emplacement')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='stocks_emplacement')
    emplacement = models.ForeignKey(
        EmplacementStock, on_delete=models.CASCADE, related_name='stocks')
    quantite = models.IntegerField(default=0)

    # ── FG62 — Seuils min/max par emplacement ────────────────────────────
    # Permettent de signaler qu'un emplacement non-principal (ex: camionnette)
    # est sous son seuil propre, indépendamment du seuil global du produit.
    # Optionnels : null = pas de seuil défini sur cet emplacement.
    seuil_min = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Seuil minimum de stock pour cet emplacement (optionnel).')
    seuil_max = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Seuil maximum de stock pour cet emplacement (optionnel).')

    class Meta:
        verbose_name = "Stock par emplacement"
        verbose_name_plural = "Stocks par emplacement"
        # ERR93 — `company` ajouté à la contrainte d'unicité (convention
        # company-in-constraint) ; la quantité ventilée ne peut jamais être
        # négative (CheckConstraint additive, sûre sur les données existantes
        # car les gardes de transfert plafonnent déjà au stock disponible).
        unique_together = [('company', 'produit', 'emplacement')]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantite__gte=0),
                name='stockemplacement_quantite_non_negative'),
        ]

    def __str__(self):
        return f'{self.produit_id} @ {self.emplacement_id} = {self.quantite}'


class ProfilSaisonnier(models.Model):
    """XSTK17 — profil saisonnier de seuils min/max/cible, PAR PRODUIT ou PAR
    CATÉGORIE (l'un des deux, jamais les deux — validé en base). Pendant sa
    fenêtre (``mois_debut``..``mois_fin``, mois calendaires 1-12, la fenêtre
    peut « boucler » l'année ex. 11→2), les sélecteurs de réappro (FG54, FG65,
    FG326) lisent CE seuil en PRIORITÉ sur le seuil statique
    (``Produit.seuil_alerte``). Hors saison ou sans profil actif : repli
    STRICTEMENT inchangé sur le seuil statique existant (comportement
    historique). Deux profils de la MÊME cible (produit ou catégorie) ne
    peuvent pas se chevaucher (validé côté service, pas en DB — le
    chevauchement calendaire n'est pas exprimable en CheckConstraint
    portable)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='profils_saisonniers')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, null=True, blank=True,
        related_name='profils_saisonniers')
    categorie = models.ForeignKey(
        Categorie, on_delete=models.CASCADE, null=True, blank=True,
        related_name='profils_saisonniers')
    nom = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Libellé libre (ex. « Saison pompage »).')
    mois_debut = models.PositiveSmallIntegerField(
        help_text='Mois de début de la saison (1-12).')
    mois_fin = models.PositiveSmallIntegerField(
        help_text='Mois de fin de la saison (1-12, inclus). Peut être < '
                  'mois_debut (fenêtre à cheval sur le nouvel an).')
    seuil_min = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Seuil minimum de saison (remplace seuil_alerte pendant '
                  'la fenêtre).')
    seuil_max = models.PositiveIntegerField(null=True, blank=True)
    quantite_cible = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Quantité cible de remplacement pendant la saison '
                  '(remplace quantite_reappro_cible).')
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='profils_saisonniers_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil saisonnier'
        verbose_name_plural = 'Profils saisonniers'
        ordering = ['mois_debut']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(produit__isnull=False, categorie__isnull=True)
                    | models.Q(produit__isnull=True, categorie__isnull=False)
                ),
                name='stock_profilsaisonnier_produit_xor_categorie'),
        ]

    def __str__(self):
        cible = f'produit={self.produit_id}' if self.produit_id \
            else f'categorie={self.categorie_id}'
        return f'{self.nom or "Profil"} ({cible}, {self.mois_debut}→{self.mois_fin})'

    def couvre_mois(self, mois):
        """Vrai si ``mois`` (1-12) tombe dans la fenêtre, y compris quand
        elle boucle l'année (ex. mois_debut=11, mois_fin=2)."""
        if self.mois_debut <= self.mois_fin:
            return self.mois_debut <= mois <= self.mois_fin
        return mois >= self.mois_debut or mois <= self.mois_fin


class TransfertStock(models.Model):
    """Le « transfer record » de N15 : déplace une quantité d'un produit d'un
    emplacement source vers un emplacement destination.

    Ne modifie JAMAIS le total `Produit.quantite_stock` — seule la ventilation
    par emplacement change. Tracé complet (qui / quand)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='transferts_stock')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT, related_name='transferts')
    source = models.ForeignKey(
        EmplacementStock, on_delete=models.PROTECT,
        related_name='transferts_sortants')
    destination = models.ForeignKey(
        EmplacementStock, on_delete=models.PROTECT,
        related_name='transferts_entrants')
    quantite = models.PositiveIntegerField()
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transferts_stock')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transfert de stock'
        verbose_name_plural = 'Transferts de stock'
        ordering = ['-date']

    def __str__(self):
        return (f'{self.produit_id}: {self.quantite} '
                f'{self.source_id}→{self.destination_id}')


# ── ODX19 — RetourFournisseur, LigneRetourFournisseur, PrixFournisseur ─────
# déplacés vers apps.achats (state-only, SeparateDatabaseAndState, tables
# stock_* inchangées). Voir le shim de ré-export en fin de fichier.


class PalierPrixFournisseur(models.Model):
    """XPUR14 — palier de prix par quantité minimale d'un tarif fournisseur.

    Un ``PrixFournisseur`` peut porter plusieurs paliers (ex. 1-9 unités au
    prix catalogue, 10-49 à un prix réduit, 50+ à un prix encore plus bas).
    Le palier applicable pour une quantité commandée est celui dont
    ``qte_min`` est le plus élevé sans dépasser la quantité. Additif : un
    ``PrixFournisseur`` sans palier garde le comportement historique
    (``prix_achat`` du tarif de base)."""
    prix_fournisseur = models.ForeignKey(
        'achats.PrixFournisseur', on_delete=models.CASCADE,
        related_name='paliers')
    qte_min = models.PositiveIntegerField()
    prix = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Palier de prix fournisseur'
        verbose_name_plural = 'Paliers de prix fournisseur'
        ordering = ['qte_min']
        unique_together = [('prix_fournisseur', 'qte_min')]

    def __str__(self):
        return f'{self.prix_fournisseur_id} · {self.qte_min}+ → {self.prix}'


# ---- ODX19 -- DeviseAchat, BonCommandeFournisseur, LigneBonCommandeFournisseur,
# ReceptionFournisseur, LigneReceptionFournisseur, FactureFournisseur,
# LigneFactureFournisseur deplaces vers apps.achats (state-only,
# SeparateDatabaseAndState, tables stock_* inchangees). Voir le shim de
# re-export en fin de fichier.


class EcheanceFactureFournisseur(models.Model):
    """XPUR6 — tranche d'échéancier d'une facture fournisseur (ex. 30 %
    avance / 70 % livraison). Additif — une facture sans échéancier explicite
    garde une échéance UNIQUE (``FactureFournisseur.date_echeance``,
    comportement historique) ; le payment run (FG133) et la balance âgée
    (FG132) lisent les tranches quand elles existent."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='echeances_facture_fournisseur')
    facture = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.CASCADE,
        related_name='echeances')
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Pourcentage du TTC de cette tranche (ex. 30.00).')
    montant = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    date_echeance = models.DateField()
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Échéance de facture fournisseur'
        verbose_name_plural = 'Échéances de facture fournisseur'
        ordering = ['date_echeance', 'id']

    def __str__(self):
        return f'{self.facture_id} — {self.montant} @ {self.date_echeance}'


# ---- ODX19 -- PaiementFournisseur deplace vers apps.achats (state-only,
# SeparateDatabaseAndState, table stock_paiementfournisseur inchangee). Voir
# le shim de re-export en fin de fichier.


class AcompteFournisseur(models.Model):
    """XPUR8 — acompte / avance versée à un fournisseur sur un BCF (pratique
    d'import 30 % à la commande / 70 % à l'expédition). Pattern
    ``PaiementFournisseur`` mais rattaché au BON DE COMMANDE (avant toute
    facture). Imputé automatiquement sur la première ``FactureFournisseur``
    du BCF (``consommer_acomptes_bcf``) : ``montant_consomme`` suit
    l'imputation, jamais négative, jamais imputée deux fois."""

    class Mode(models.TextChoices):
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        ESPECES = 'especes', 'Espèces'
        CARTE = 'carte', 'Carte'
        EFFET = 'effet', 'Effet / traite'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='acomptes_fournisseur')
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.CASCADE,
        related_name='acomptes')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    date_versement = models.DateField(null=True, blank=True)
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT)
    # Portion déjà imputée sur une facture — jamais > montant, jamais
    # décrémentée (imputation idempotente, un acompte ne s'impute qu'une
    # fois sur SA facture cible).
    montant_consomme = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    facture_imputee = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='acomptes_imputes')
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acomptes_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Acompte fournisseur'
        verbose_name_plural = 'Acomptes fournisseur'
        ordering = ['-date_versement', '-date_creation']

    def __str__(self):
        return f'{self.bon_commande_id} — {self.montant}'

    @property
    def montant_non_consomme(self):
        return max(
            (self.montant or Decimal('0'))
            - (self.montant_consomme or Decimal('0')), Decimal('0'))


class AvoirFournisseur(models.Model):
    """XPUR9 — avoir fournisseur (note de crédit AP). Matérialise la créance
    qu'un ``RetourFournisseur`` validé (qui ne fait que reverser le stock)
    laisse ouverte. Référencé via ``create_with_reference`` (préfixe AVF).
    Imputable sur une ou plusieurs ``FactureFournisseur`` du MÊME
    fournisseur ; les montants restent INTERNES (jamais client-facing)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        IMPUTE = 'impute', 'Imputé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='avoirs_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT, related_name='avoirs')
    facture_origine = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='avoirs_origine')
    retour = models.ForeignKey(
        'achats.RetourFournisseur', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='avoirs')
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    # Somme déjà imputée sur des factures — jamais > montant_ttc, jamais
    # décrémentée (l'imputation est cumulative, sur 1..N factures).
    montant_impute = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='avoirs_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Avoir fournisseur'
        verbose_name_plural = 'Avoirs fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def montant_disponible(self):
        """Solde de l'avoir NON encore imputé — jamais négatif."""
        return max(
            (self.montant_ttc or Decimal('0'))
            - (self.montant_impute or Decimal('0')), Decimal('0'))


class ImputationAvoirFournisseur(models.Model):
    """XPUR9 — trace UNE imputation d'un ``AvoirFournisseur`` sur UNE
    ``FactureFournisseur`` (un avoir peut être réparti sur plusieurs
    factures). Additif, INTERNE."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='imputations_avoir_fournisseur')
    avoir = models.ForeignKey(
        AvoirFournisseur, on_delete=models.CASCADE,
        related_name='imputations')
    facture = models.ForeignKey(
        'achats.FactureFournisseur', on_delete=models.CASCADE,
        related_name='avoirs_imputes')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Imputation d'avoir fournisseur"
        verbose_name_plural = "Imputations d'avoir fournisseur"
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.avoir_id} → {self.facture_id} : {self.montant}'


# ── FG63 — Session d'inventaire (comptage physique en brouillon) ──────────────

class InventaireSession(models.Model):
    """FG63 — Session de comptage physique du stock.

    Remplace l'action `inventaire` "one-shot" par un workflow draft / valider :
    le comptage est enregistré en mode brouillon (pouvant être corrigé) puis
    validé en une seule passe qui émet les ajustements (AJUSTEMENT) uniquement
    pour les lignes dont la quantité comptée diffère de la quantité théorique.
    La validation est IDEMPOTENTE : une session déjà validée ne peut pas être
    re-validée. INTERNE — admin uniquement.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inventaire_sessions')
    reference = models.CharField(max_length=50)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventaire_sessions')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session d\'inventaire'
        verbose_name_plural = 'Sessions d\'inventaire'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class LigneInventaire(models.Model):
    """Ligne d'une session d'inventaire : produit, quantité théorique
    (tirée du stock au moment de la création) et quantité comptée physiquement.
    L'écart est calculé lors de la validation de la session."""
    session = models.ForeignKey(
        InventaireSession, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_inventaire')
    quantite_theorique = models.IntegerField(
        help_text='Stock théorique au moment du comptage (snapshot).')
    quantite_comptee = models.IntegerField(
        help_text='Quantité réellement comptée physiquement.')

    class Meta:
        verbose_name = 'Ligne d\'inventaire'
        verbose_name_plural = 'Lignes d\'inventaire'

    def __str__(self):
        return f'{self.produit_id}: théo={self.quantite_theorique} compté={self.quantite_comptee}'

    @property
    def ecart(self):
        return self.quantite_comptee - self.quantite_theorique


# ── XSTK13 — Inventaire annuel légal (CGNC), figé et immuable ────────────────

class InventaireAnnuel(models.Model):
    """XSTK13 — snapshot IMMUABLE de la valorisation du stock au 31/12 d'un
    exercice comptable (CGNC : support du bilan, contrôle fiscal).

    ``donnees`` porte le snapshot complet (même forme que
    ``services.valorisation_a_date``) : une fois créé, un enregistrement
    n'est plus jamais modifié (le service refuse un second figement pour le
    même exercice+société). INTERNE — jamais client-facing."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inventaires_annuels')
    exercice = models.PositiveIntegerField(
        help_text='Année de l\'exercice comptable (ex. 2026).')
    date_reference = models.DateField(
        help_text='Date de référence du figement (31/12 de l\'exercice).')
    total_valeur = models.DecimalField(max_digits=16, decimal_places=2)
    nb_lignes = models.PositiveIntegerField(default=0)
    donnees = models.JSONField(
        encoder=DjangoJSONEncoder,
        help_text='Snapshot complet et immuable de la valorisation.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventaires_annuels_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Inventaire annuel'
        verbose_name_plural = 'Inventaires annuels'
        ordering = ['-exercice']
        unique_together = [('company', 'exercice')]

    def __str__(self):
        return f'Inventaire {self.exercice} ({self.company_id})'


# ── XSTK14 — Revalorisation manuelle du stock (document tracé) ──────────────

class RevalorisationStock(models.Model):
    """XSTK14 — corrige le COÛT MOYEN d'un produit (baisse mondiale du prix
    des panneaux, dépréciation) sans bidouiller les réceptions.

    À la VALIDATION, `nouveau_cout` devient la couche de départ du coût
    moyen (`services.average_cost_with_source` ne compte plus que les
    réceptions POSTÉRIEURES à `date_validation`) et le document est VERROUILLÉ
    (jamais modifié après validation). INTERNE, admin-only, jamais
    client-facing."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDEE = 'validee', 'Validée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='revalorisations_stock')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='revalorisations')
    ancien_cout = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Snapshot du coût moyen AVANT revalorisation.')
    nouveau_cout = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_snapshot = models.IntegerField(
        help_text='Quantité en stock au moment de la revalorisation.')
    delta_valeur = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='(nouveau_cout - ancien_cout) × quantite_snapshot.')
    motif = models.TextField(help_text='Motif obligatoire.')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='revalorisations_stock')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Revalorisation de stock'
        verbose_name_plural = 'Revalorisations de stock'
        ordering = ['-date_creation']

    def __str__(self):
        return (f'Revalo {self.produit_id}: {self.ancien_cout} -> '
                f'{self.nouveau_cout} ({self.statut})')


# ── FG66 / DC36 — Kit / nomenclature (BOM) vendable ───────────────────────────

class KitProduit(models.Model):
    """FG66 — Kit / nomenclature (BOM) : une configuration standard vendable
    (« Kit pompage 3CV », « Kit résidentiel 5 kWc ») composée de produits du
    catalogue.

    DC36 — un kit NE STOCKE AUCUN prix / marque / TVA propre : tout est dérivé
    de ses composants (``stock.Produit``) au moment de l'explosion. Le kit n'est
    qu'un en-tête + une liste de composants (``KitComposant``). À l'insertion
    dans un devis, le kit s'EXPLOSE en lignes composant (un SKU par ligne) pour
    une réservation de stock exacte du bundle — l'explosion vit dans
    ``services.exploser_kit`` (côté stock), consommée par ``ventes`` via la
    couche services/string-FK (jamais d'import direct du modèle stock).

    Multi-tenant : ``company`` toujours forcée côté serveur. Additif."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='kits_produit')
    nom = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kit / nomenclature'
        verbose_name_plural = 'Kits / nomenclatures'
        unique_together = [('company', 'sku')]
        ordering = ['nom']

    def __str__(self):
        return self.nom


class KitComposant(models.Model):
    """Composant d'un kit (FG66/DC36) : soit un produit du catalogue, soit
    (XMFG17) un SOUS-KIT (``composant_kit``) — jamais les deux (XOR imposé
    par une CheckConstraint additive, sûre sur les données existantes : tout
    composant déjà en base a ``produit`` renseigné et ``composant_kit`` NULL).

    DC36 — le prix / la marque / la TVA ne sont JAMAIS recopiés ici : ils sont
    lus sur le ``Produit`` (ou, pour un sous-kit, sur SES composants,
    récursivement) au moment de l'explosion."""

    kit = models.ForeignKey(
        KitProduit, on_delete=models.CASCADE, related_name='composants')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT, related_name='composants_kit',
        null=True, blank=True)
    # XMFG17 — sous-kit : nomenclature multi-niveaux. XOR avec `produit` (une
    # ligne de composition est soit un produit feuille, soit un sous-kit).
    composant_kit = models.ForeignKey(
        KitProduit, on_delete=models.PROTECT, null=True, blank=True,
        related_name='utilise_comme_sous_kit_dans',
        help_text='Sous-kit utilisé comme composant (XOR avec produit).')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1,
        help_text='Quantité de ce produit (ou sous-kit) dans une unité de kit.')
    # XMFG11 — taux de perte attendu (%) pour ce composant (casse, chutes...).
    # Défaut 0 = comportement historique inchangé. Gonfle le besoin/réservation
    # planifiés côté atelier (installations.KitComposant), pas la vente.
    taux_perte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Taux de perte attendu (%) — gonfle le besoin planifié.")

    class Meta:
        verbose_name = 'Composant de kit'
        verbose_name_plural = 'Composants de kit'
        unique_together = [('kit', 'produit'), ('kit', 'composant_kit')]
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(produit__isnull=False, composant_kit__isnull=True)
                    | models.Q(produit__isnull=True, composant_kit__isnull=False)
                ),
                name='kitcomposant_produit_xor_composant_kit',
            ),
        ]

    def __str__(self):
        cible = self.produit_id or f'kit:{self.composant_kit_id}'
        return f'{self.kit_id}: {cible} × {self.quantite}'


class RevisionKit(models.Model):
    """XMFG18 — révision de nomenclature d'un kit (pattern RevisionDocument
    FG297) : snapshot JSON AUTO de la composition à chaque modification des
    composants, numéroté par kit. La révision la plus récente est la
    composition courante ; « composition au JJ/MM/AAAA » = la dernière
    révision à cette date. Jamais de prix d'achat dans le snapshot."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='revisions_kit_produit')
    kit = models.ForeignKey(
        KitProduit, on_delete=models.CASCADE, related_name='revisions')
    numero = models.PositiveIntegerField(default=1)
    composition = models.JSONField(
        default=list,
        help_text='Snapshot des composants : produit_id/composant_kit_id, '
                  'désignation, quantité, taux de perte.')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='revisions_kit_produit_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Révision de kit'
        verbose_name_plural = 'Révisions de kit'
        ordering = ['kit_id', '-numero']
        constraints = [
            models.UniqueConstraint(
                fields=['kit', 'numero'],
                name='stock_revkit_kit_numero_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'kit'],
                         name='stock_revkit_co_kit_idx'),
        ]

    def __str__(self):
        return f'Rev.{self.numero} — kit {self.kit_id}'


class FicheTechnique(models.Model):
    """DC35 / FG254 — Fiche technique (datasheet) d'un produit.

    Référence le ``Produit`` par FK et NE RE-STOCKE PAS l'identité ni les
    caractéristiques déjà portées par le produit : marque, garantie, courbe de
    pompe, description, prix, TVA vivent sur ``Produit`` et sont lus là-bas. La
    fiche ne porte QUE :

      • des paramètres ÉLECTRIQUES normalisés (Pmax / Voc / Isc / Vmp / Imp /
        rendement) qui n'existent pas encore sur ``Produit`` — utiles pour le
        dimensionnement / la comparaison sans dépendre du texte libre ;
      • le PDF constructeur d'origine.

    Un produit a au plus UNE fiche (OneToOne). Tout est optionnel : une fiche
    peut ne porter que le PDF, ou que des paramètres. Entièrement additif —
    aucun produit existant n'est impacté."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='fiches_techniques')
    produit = models.OneToOneField(
        Produit, on_delete=models.CASCADE, related_name='fiche_technique')

    # ── Paramètres électriques normalisés (Wc / V / A) — tous optionnels ──
    pmax_wc = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Puissance crête Pmax (Wc).')
    voc_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Tension circuit ouvert Voc (V).')
    isc_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Courant court-circuit Isc (A).')
    vmp_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Tension au point de puissance max Vmp (V).')
    imp_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Courant au point de puissance max Imp (A).')
    rendement_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Rendement du module (%).')

    # ── PDF constructeur d'origine (optionnel) ──
    pdf = models.FileField(
        upload_to='stock/fiches_techniques/%Y/%m/', null=True, blank=True,
        help_text='Fiche technique PDF du constructeur.')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche technique'
        verbose_name_plural = 'Fiches techniques'
        ordering = ['-date_mise_a_jour']

    def __str__(self):
        return f'Fiche technique — {self.produit_id}'


# ── ZPUR3 — Modèle de BCF réutilisable (purchase template) ──────────────────
# Odoo permet des « Purchase Templates » pré-remplissant produits/quantités
# pour des RFQ répétées. Chaque BCF de réappro récurrent (câble, MC4,
# visserie) se re-saisit aujourd'hui à la main — un modèle nommé matérialise
# un BCF BROUILLON pré-rempli en un clic.

class ModeleBonCommandeFournisseur(models.Model):
    """ZPUR3 — modèle de BCF réutilisable : un nom + un fournisseur optionnel
    + des lignes (produit + quantité par défaut). L'action `generer` (vue)
    matérialise un BCF BROUILLON pré-rempli à partir de ces lignes, éditable
    avant envoi. Le modèle lui-même ne bouge jamais aucun stock/mouvement."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='modeles_bcf')
    nom = models.CharField(max_length=150)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='modeles_bcf',
        help_text='Fournisseur par défaut du BCF généré (optionnel — peut '
                  "être choisi/changé à la génération si absent ici).")
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modeles_bcf_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modèle de bon de commande fournisseur'
        verbose_name_plural = 'Modèles de bon de commande fournisseur'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class ModeleBonCommandeFournisseurLigne(models.Model):
    """ZPUR3 — ligne d'un modèle de BCF : produit + quantité par défaut."""

    modele = models.ForeignKey(
        ModeleBonCommandeFournisseur, on_delete=models.CASCADE,
        related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE,
        related_name='lignes_modele_bcf')
    quantite = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Ligne de modèle de BCF'
        verbose_name_plural = 'Lignes de modèle de BCF'
        unique_together = [('modele', 'produit')]
        ordering = ['id']

    def __str__(self):
        return f'{self.modele_id}: {self.produit_id} × {self.quantite}'


class NomenclatureCodeBarres(models.Model):
    """ZSTK12 — nomenclature de code-barres (Odoo « Barcode Nomenclatures »),
    par société. XSTK4 parse GS1 en dur ; ceci permet à une société qui
    imprime ses PROPRES codes internes (préfixe magasin) de les faire router
    vers le bon type d'entité, sans toucher au parsing GS1/EAN existant.

    Repli : sans nomenclature ACTIVE, le résolveur de scan se comporte
    EXACTEMENT comme aujourd'hui (jetons internes puis GS1 puis EAN) —
    comportement historique inchangé."""

    class Type(models.TextChoices):
        DEFAULT = 'default', 'Défaut (EAN/UPC)'
        GS1 = 'gs1', 'GS1'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='nomenclatures_code_barres')
    nom = models.CharField(max_length=100)
    type_nomenclature = models.CharField(
        max_length=10, choices=Type.choices, default=Type.DEFAULT)
    actif = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nomenclature de code-barres'
        verbose_name_plural = 'Nomenclatures de code-barres'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class RegleCodeBarres(models.Model):
    """ZSTK12 — règle d'une nomenclature : un motif (regex ou préfixe simple)
    matché contre le code scanné route vers le type d'entité configuré
    (produit/lot/série/emplacement/quantité). Triées par ``priorite``
    (plus petit = évalué en premier)."""

    class Encode(models.TextChoices):
        PRODUIT = 'produit', 'Produit'
        LOT = 'lot', 'Lot'
        SERIE = 'serie', 'Série'
        EMPLACEMENT = 'emplacement', 'Emplacement'
        QUANTITE = 'quantite', 'Quantité'

    nomenclature = models.ForeignKey(
        NomenclatureCodeBarres, on_delete=models.CASCADE,
        related_name='regles')
    # Regex (compilée avec `re.match`) OU préfixe simple selon
    # `est_regex` — un préfixe simple `"22"` matche tout code commençant
    # par ces caractères (cas d'usage le plus fréquent, pas besoin de regex).
    motif = models.CharField(max_length=200)
    est_regex = models.BooleanField(default=False)
    encode = models.CharField(max_length=20, choices=Encode.choices)
    priorite = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = 'Règle de code-barres'
        verbose_name_plural = 'Règles de code-barres'
        ordering = ['priorite', 'id']

    def __str__(self):
        return f'{self.motif} → {self.encode}'

    def matches(self, code):
        if self.est_regex:
            import re
            try:
                return bool(re.match(self.motif, code))
            except re.error:
                return False
        return code.startswith(self.motif)


# ── ODX19 — MODULE ACHATS (déplacé) ────────────────────────────────────────
# PrixFournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
# ReceptionFournisseur, LigneReceptionFournisseur, FactureFournisseur,
# LigneFactureFournisseur, PaiementFournisseur, RetourFournisseur,
# LigneRetourFournisseur vivent désormais dans ``apps.achats`` (équivalent
# Odoo Purchase). ODX19 les a sortis de stock en préservant à l'IDENTIQUE
# leurs tables (``db_table = 'stock_<model>'``) via des migrations
# ``SeparateDatabaseAndState`` (state-only, zéro SQL). Ce ré-export garde le
# code/migrations historiques (``from apps.stock.models import
# BonCommandeFournisseur``, admin, tests) fonctionnels ; à retirer en ODX22
# une fois tous les appelants re-pointés sur ``apps.achats``.
from apps.achats.models import (  # noqa: E402,F401
    BonCommandeFournisseur,
    DeviseAchat,
    FactureFournisseur,
    LigneBonCommandeFournisseur,
    LigneFactureFournisseur,
    LigneReceptionFournisseur,
    LigneRetourFournisseur,
    PaiementFournisseur,
    PrixFournisseur,
    ReceptionFournisseur,
    RetourFournisseur,
)
