from decimal import Decimal

from django.db import models
from django.conf import settings


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

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom


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

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        unique_together = [('company', 'sku')]

    def __str__(self):
        return self.nom


class MouvementStock(models.Model):
    """Entrées / Sorties / Transferts de stock avec traçabilité complète."""

    class TypeMouvement(models.TextChoices):
        ENTREE = 'entree', 'Entrée'
        SORTIE = 'sortie', 'Sortie'
        TRANSFERT = 'transfert', 'Transfert'
        AJUSTEMENT = 'ajustement', 'Ajustement'

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


class RetourFournisseur(models.Model):
    """N19 — retour fournisseur (articles défectueux / erronés).

    À la validation, le stock est DÉCRÉMENTÉ via MouvementStock (type SORTIE),
    exactement comme partout ailleurs. Peut être lié au bon de commande
    fournisseur d'origine. Usage INTERNE (prix d'achat jamais client-facing).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='retours_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT, related_name='retours')
    bon_commande = models.ForeignKey(
        'BonCommandeFournisseur', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='retours')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='retours_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retour fournisseur'
        verbose_name_plural = 'Retours fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class LigneRetourFournisseur(models.Model):
    """Ligne d'un retour fournisseur : SKU, quantité retournée, motif."""
    retour = models.ForeignKey(
        RetourFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_retour_fournisseur')
    quantite = models.IntegerField()
    motif = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = 'Ligne de retour fournisseur'
        verbose_name_plural = 'Lignes de retour fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'


class PrixFournisseur(models.Model):
    """N17 — prix d'achat d'un produit chez un fournisseur donné.

    Un produit peut avoir plusieurs fournisseurs avec des prix différents ;
    on garde le prix d'achat (INTERNE — jamais client-facing) et la date du
    dernier achat. Sert à proposer le fournisseur le moins cher au moment de
    rédiger un bon de commande. La date du dernier achat est mise à jour
    automatiquement à la réception d'un BCF. Additif."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='prix_fournisseurs')
    produit = models.ForeignKey(
        Produit, on_delete=models.CASCADE, related_name='prix_fournisseurs')
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.CASCADE, related_name='prix_produits')
    # Prix d'ACHAT — donnée INTERNE, jamais sur un document client.
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_dernier_achat = models.DateField(null=True, blank=True)
    # XPUR7 — délai de livraison (jours) constaté/annoncé pour ce couple
    # produit×fournisseur. Alimente la suggestion `date_livraison_prevue`
    # d'un BCF. Null = pas de délai connu (comportement historique).
    delai_livraison_jours = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Prix fournisseur"
        verbose_name_plural = "Prix fournisseurs"
        unique_together = [('produit', 'fournisseur')]
        ordering = ['prix_achat']

    def __str__(self):
        return f'{self.produit_id} @ {self.fournisseur_id} = {self.prix_achat}'


# XPUR3 — devises d'achat courantes (imports panneaux/onduleurs). MAD reste le
# défaut partout : un document sans devise saisie garde le comportement
# historique (contre-valeur = montant, taux = 1) puisque tout est déjà en MAD.
class DeviseAchat(models.TextChoices):
    MAD = 'MAD', 'Dirham marocain (MAD)'
    EUR = 'EUR', 'Euro (EUR)'
    USD = 'USD', 'Dollar américain (USD)'
    CNY = 'CNY', 'Yuan chinois (CNY)'


class BonCommandeFournisseur(models.Model):
    """Bon de commande FOURNISSEUR (achat / approvisionnement) — N12.

    À NE PAS confondre avec `ventes.BonCommande`, qui est un bon de commande
    CLIENT lié à un devis. Celui-ci est un document d'ACHAT : il liste les
    références (SKU) commandées à un fournisseur, avec leurs PRIX D'ACHAT
    (INTERNES — jamais exposés sur un document client).

    À la réception (totale ou partielle), le stock est INCRÉMENTÉ exactement
    comme partout ailleurs : via `MouvementStock` (type ENTREE). Aucun
    mécanisme parallèle.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ENVOYE = 'envoye', 'Envoyé'
        RECU = 'recu', 'Reçu'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bons_commande_fournisseur',
    )
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name='bons_commande',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )
    date_commande = models.DateField(null=True, blank=True)
    # XPUR3 — devise du document (défaut MAD, comportement historique
    # inchangé) + taux de change saisi à la date du document (aucun appel
    # externe). Les LIGNES portent le prix d'achat unitaire EN CETTE DEVISE ;
    # la contre-valeur MAD (utilisée PARTOUT en interne : coût moyen pondéré,
    # balance âgée, payment run, comparatif fournisseurs) est calculée par
    # `LigneBonCommandeFournisseur.prix_achat_unitaire_mad`.
    devise = models.CharField(
        max_length=3, choices=DeviseAchat.choices, default=DeviseAchat.MAD)
    taux_change = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text='Taux de change devise → MAD à la date du document '
                  '(saisie manuelle, aucun appel externe).')
    # ── XPUR7 — dates de livraison prévues, accusé fournisseur, OTD réel ────
    # Pré-calculée (date_commande + délai de PrixFournisseur) à la création,
    # reste modifiable ensuite. Null = pas de date prévue (comportement
    # historique, aucun délai connu).
    date_livraison_prevue = models.DateField(null=True, blank=True)
    # Accusé de commande du fournisseur : date qu'IL confirme (distincte de
    # la date demandée ci-dessus, jamais écrasée — préserve l'OTD promis-vs-
    # reçu) + son numéro de confirmation.
    date_confirmee_fournisseur = models.DateField(null=True, blank=True)
    numero_confirmation_fournisseur = models.CharField(
        max_length=100, blank=True, default='')
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bons_commande_fournisseur',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bon de commande fournisseur'
        verbose_name_plural = 'Bons de commande fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_achat(self):
        """Total HT d'achat (INTERNE — jamais sur un document client)."""
        return sum((ligne.total_achat for ligne in self.lignes.all()), 0)

    @property
    def est_entierement_recu(self):
        lignes = list(self.lignes.all())
        return bool(lignes) and all(
            ligne.quantite_recue >= ligne.quantite for ligne in lignes
        )


class LigneBonCommandeFournisseur(models.Model):
    """Ligne d'un bon de commande fournisseur : SKU, quantité, prix d'achat
    unitaire (INTERNE) et quantité déjà reçue (réceptions partielles)."""

    bon_commande = models.ForeignKey(
        BonCommandeFournisseur,
        on_delete=models.CASCADE,
        related_name='lignes',
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        related_name='lignes_bon_commande_fournisseur',
    )
    quantite = models.IntegerField()
    # Prix d'ACHAT unitaire — donnée INTERNE, TOUJOURS en contre-valeur MAD
    # (utilisée PARTOUT en interne : coût moyen pondéré/landed cost, balance
    # âgée, payment run, comparatif fournisseurs — XPUR3). N'apparaît JAMAIS
    # sur un document destiné au client (devis, facture, BC client).
    prix_achat_unitaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    # XPUR3 — prix d'achat unitaire saisi dans la DEVISE du document (BCF.
    # devise/taux_change). Null = document en MAD (comportement historique) :
    # `prix_achat_unitaire` reste alors l'unique source de vérité. Quand
    # renseigné, `prix_achat_unitaire` DOIT être sa contre-valeur MAD
    # (prix_achat_unitaire_devise × bon_commande.taux_change) — recalculée
    # côté service à la saisie, jamais divergente.
    prix_achat_unitaire_devise = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Prix d'achat unitaire dans la devise du document "
                  '(optionnel — null = document en MAD).')
    # ── FG67 / DC38 — Coût débarqué (landed cost) ────────────────────────────
    # Frais annexes TOTAUX de la LIGNE (fret + douane + TVA import + transit),
    # à répartir sur les unités de la ligne. Le coût de revient débarqué
    # unitaire = prix_achat_unitaire + frais_annexes / quantité. Replié dans le
    # coût moyen pondéré (average_cost_with_source). INTERNE, jamais
    # client-facing. Optionnel (0 = comportement historique inchangé).
    frais_annexes = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Frais annexes TOTAUX de la ligne (fret/douane/TVA import/'
                  'transit), répartis sur les unités. INTERNE.')
    quantite_recue = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Ligne de bon de commande fournisseur'
        verbose_name_plural = 'Lignes de bon de commande fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'

    @property
    def quantite_restante(self):
        return max(self.quantite - self.quantite_recue, 0)

    @property
    def total_achat(self):
        return self.quantite * self.prix_achat_unitaire

    @property
    def cout_unitaire_debarque(self):
        """FG67/DC38 — coût de revient débarqué unitaire = prix d'achat unitaire
        + frais annexes répartis sur la quantité de la ligne. INTERNE."""
        from decimal import Decimal
        pu = self.prix_achat_unitaire or Decimal('0')
        frais = self.frais_annexes or Decimal('0')
        qte = self.quantite or 0
        if qte and frais:
            return pu + (frais / Decimal(str(qte)))
        return pu


class ReceptionFournisseur(models.Model):
    """G5 — Réception fournisseur (goods-in / entrée de marchandises).

    Trace une réception (totale ou partielle) des articles d'un bon de commande
    fournisseur. À la CONFIRMATION (statut « confirmé »), chaque ligne reçue
    crée un `MouvementStock` ENTREE — exactement comme l'action `recevoir` du
    BCF, jamais un mécanisme parallèle — et avance le statut du BCF selon ses
    quantités reçues existantes (`quantite_recue`/`est_entierement_recu`). La
    confirmation est IDEMPOTENTE : une réception déjà confirmée ne re-crée
    jamais de mouvement. Numérotation sans trou (préfixe REC). Usage INTERNE.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        CONFIRME = 'confirme', 'Confirmé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='receptions_fournisseur')
    reference = models.CharField(max_length=50)
    bon_commande = models.ForeignKey(
        BonCommandeFournisseur, on_delete=models.PROTECT,
        related_name='receptions')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    date_reception = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    # Qui a réceptionné la marchandise.
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receptions_fournisseur')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receptions_fournisseur_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réception fournisseur'
        verbose_name_plural = 'Réceptions fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_recu(self):
        """Nombre total d'articles reçus sur cette réception."""
        return sum((ligne.quantite for ligne in self.lignes.all()), 0)


class LigneReceptionFournisseur(models.Model):
    """Ligne d'une réception fournisseur : la ligne de BCF concernée, le produit
    et la quantité effectivement reçue lors de cette réception."""

    reception = models.ForeignKey(
        ReceptionFournisseur, on_delete=models.CASCADE, related_name='lignes')
    ligne_commande = models.ForeignKey(
        LigneBonCommandeFournisseur, on_delete=models.PROTECT,
        related_name='lignes_reception')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT,
        related_name='lignes_reception_fournisseur')
    quantite = models.IntegerField()

    # ── FG61 — Numéros de série à la réception ────────────────────────────
    # Sériaux capturés à l'entrée en stock (pour réconciliation avec
    # sav.Equipement lors de l'installation). Optionnel ; liste de chaînes.
    numeros_serie = models.JSONField(
        null=True, blank=True,
        help_text='Numéros de série reçus lors de cette ligne (liste de '
                  'chaînes). Optionnel ; aucune série = null.')

    # ── FG64 — Traçabilité lot / date de péremption ───────────────────────
    # Batteries, produits d'étanchéité, etc. Optionnel : un produit sans
    # date de péremption n'apparaît jamais dans le rapport d'expiry.
    numero_lot = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Numéro de lot ou batch (optionnel).')
    date_peremption = models.DateField(
        null=True, blank=True,
        help_text='Date de péremption / fin de vie (optionnel).')

    class Meta:
        verbose_name = 'Ligne de réception fournisseur'
        verbose_name_plural = 'Lignes de réception fournisseur'

    def __str__(self):
        return f'{self.produit_id} × {self.quantite}'


class FactureFournisseur(models.Model):
    """G5 — Facture fournisseur / comptabilité fournisseur (AP).

    Document d'ACHAT reçu d'un fournisseur, éventuellement rattaché à un bon de
    commande fournisseur. Porte les montants HT/TVA/TTC et un statut de
    règlement. Le solde dû = TTC − Σ paiements. Usage INTERNE (les montants
    d'achat ne sont jamais client-facing).
    """

    class Statut(models.TextChoices):
        A_PAYER = 'a_payer', 'À payer'
        PARTIELLEMENT_PAYEE = 'partiellement_payee', 'Partiellement payée'
        PAYEE = 'payee', 'Payée'

    # XPUR2 — nature de l'achat pour la RAS-TVA (LF 2024) : biens & travaux
    # (retenue 100 % de la TVA SI le fournisseur n'a pas d'ARF valide, sinon
    # rien) vs prestations de services (75 % avec ARF valide / 100 % sans).
    # Défaut 'biens' — comportement historique inchangé tant que la RAS-TVA
    # est désactivée (AchatsParametres.ras_tva_actif = False par défaut).
    class TypeAchat(models.TextChoices):
        BIENS = 'biens', 'Biens & travaux'
        SERVICES = 'services', 'Prestations de services'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='factures_fournisseur')
    reference = models.CharField(max_length=50)
    fournisseur = models.ForeignKey(
        Fournisseur, on_delete=models.PROTECT,
        related_name='factures_fournisseur')
    bon_commande = models.ForeignKey(
        BonCommandeFournisseur, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='factures_fournisseur')
    # Référence du document chez le fournisseur (numéro de sa facture).
    ref_fournisseur = models.CharField(max_length=100, blank=True, null=True)
    type_achat = models.CharField(
        max_length=10, choices=TypeAchat.choices, default=TypeAchat.BIENS,
        help_text="Nature de l'achat (RAS-TVA LF 2024) : biens & travaux ou "
                  'prestations de services.')
    date_facture = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    # XPUR3 — devise + taux de change (mêmes règles que le BCF : défaut MAD,
    # taux 1, saisi à la date du document, aucun appel externe). Les montants
    # HT/TVA/TTC ci-dessous restent TOUJOURS la contre-valeur MAD (utilisée
    # partout en interne : balance âgée FG132, payment run FG133) ; les
    # montants en devise natifs sont ajoutés séparément pour l'affichage.
    devise = models.CharField(
        max_length=3, choices=DeviseAchat.choices, default=DeviseAchat.MAD)
    taux_change = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text='Taux de change devise → MAD à la date du document '
                  '(saisie manuelle, aucun appel externe).')
    montant_ttc_devise = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Montant TTC dans la devise du document (optionnel — '
                  'null = document en MAD).')
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    montant_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, default=0)
    statut = models.CharField(
        max_length=24, choices=Statut.choices, default=Statut.A_PAYER)

    # ── XPUR10 — file d'exceptions du rapprochement 3 voies (FG131) ────────
    # Une facture HORS tolérance société (XPUR10) passe en `exception` : la
    # CRÉATION d'un PaiementFournisseur est refusée tant qu'elle n'est pas
    # résolue par un responsable/admin. Défaut 'normale' = comportement
    # historique inchangé (jamais bloquée).
    class StatutControle(models.TextChoices):
        NORMALE = 'normale', 'Normale'
        EXCEPTION = 'exception', 'En exception'
        RESOLUE = 'resolue', 'Résolue'

    statut_controle = models.CharField(
        max_length=12, choices=StatutControle.choices,
        default=StatutControle.NORMALE)
    motif_ecart = models.TextField(blank=True, null=True)
    resolu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='factures_fournisseur_resolues')
    resolu_le = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='factures_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture fournisseur'
        verbose_name_plural = 'Factures fournisseur'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    @property
    def total_paye(self):
        """Somme des paiements enregistrés sur cette facture."""
        return sum((p.montant for p in self.paiements.all()), Decimal('0'))

    @property
    def total_acomptes_imputes(self):
        """XPUR8 — somme des acomptes fournisseur imputés sur CETTE facture
        (0 si aucun — comportement historique inchangé)."""
        return sum(
            (a.montant for a in self.acomptes_imputes.all()), Decimal('0'))

    @property
    def total_avoirs_imputes(self):
        """XPUR9 — somme des avoirs fournisseur imputés sur CETTE facture
        (0 si aucun — comportement historique inchangé)."""
        return sum(
            (i.montant for i in self.avoirs_imputes.all()), Decimal('0'))

    @property
    def solde_du(self):
        """Solde dû = TTC − Σ paiements − Σ acomptes imputés − Σ avoirs
        imputés (jamais négatif)."""
        solde = ((self.montant_ttc or Decimal('0')) - self.total_paye
                 - self.total_acomptes_imputes - self.total_avoirs_imputes)
        return max(solde, Decimal('0'))


class LigneFactureFournisseur(models.Model):
    """Ligne (optionnelle) d'une facture fournisseur : désignation libre,
    quantité et prix d'achat unitaire HT. Permet de ventiler une facture par
    article. INTERNE."""

    facture = models.ForeignKey(
        FactureFournisseur, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(
        Produit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_facture_fournisseur')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1)
    prix_unitaire_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Ligne de facture fournisseur'
        verbose_name_plural = 'Lignes de facture fournisseur'

    def __str__(self):
        return f'{self.designation} × {self.quantite}'

    @property
    def total_ht(self):
        return (self.quantite or Decimal('0')) * (
            self.prix_unitaire_ht or Decimal('0'))


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
        FactureFournisseur, on_delete=models.CASCADE,
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


class PaiementFournisseur(models.Model):
    """G5 — Paiement (règlement) d'une facture fournisseur. Chaque paiement
    réduit le solde dû de la facture. INTERNE."""

    class Mode(models.TextChoices):
        VIREMENT = 'virement', 'Virement'
        CHEQUE = 'cheque', 'Chèque'
        ESPECES = 'especes', 'Espèces'
        CARTE = 'carte', 'Carte'
        EFFET = 'effet', 'Effet / traite'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='paiements_fournisseur')
    facture = models.ForeignKey(
        FactureFournisseur, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    date_paiement = models.DateField(null=True, blank=True)
    mode = models.CharField(
        max_length=20, choices=Mode.choices, default=Mode.VIREMENT)
    note = models.TextField(blank=True, null=True)
    # ── XPUR2 — RAS-TVA fournisseurs (LF 2024, en vigueur 01/07/2024) ───────
    # Montant retenu à la source sur la TVA facturée + le taux appliqué
    # (0/75/100 %), calculés selon FactureFournisseur.type_achat + la
    # validité ARF du fournisseur (XPUR1). 0 par défaut = comportement
    # historique inchangé tant que AchatsParametres.ras_tva_actif est OFF.
    montant_ras_tva = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Montant de la retenue à la source sur la TVA (LF 2024).')
    taux_ras = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Taux de RAS-TVA appliqué (0/75/100 %).')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='paiements_fournisseur')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement fournisseur'
        verbose_name_plural = 'Paiements fournisseur'
        ordering = ['-date_paiement', '-date_creation']

    def __str__(self):
        return f'{self.facture_id} — {self.montant}'

    @property
    def montant_net_paye(self):
        """XPUR2 — net réellement décaissé = montant − RAS-TVA retenue."""
        return (self.montant or Decimal('0')) - (
            self.montant_ras_tva or Decimal('0'))


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
        'BonCommandeFournisseur', on_delete=models.CASCADE,
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
        'FactureFournisseur', on_delete=models.SET_NULL, null=True,
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
        FactureFournisseur, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='avoirs_origine')
    retour = models.ForeignKey(
        RetourFournisseur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='avoirs')
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
        FactureFournisseur, on_delete=models.CASCADE,
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
    """Composant d'un kit (FG66/DC36) : un produit du catalogue + une quantité.

    DC36 — le prix / la marque / la TVA ne sont JAMAIS recopiés ici : ils sont
    lus sur le ``Produit`` lié au moment de l'explosion. On ne stocke que le FK
    produit et la quantité dans le bundle."""

    kit = models.ForeignKey(
        KitProduit, on_delete=models.CASCADE, related_name='composants')
    produit = models.ForeignKey(
        Produit, on_delete=models.PROTECT, related_name='composants_kit')
    quantite = models.DecimalField(
        max_digits=12, decimal_places=2, default=1,
        help_text='Quantité de ce produit dans une unité de kit.')

    class Meta:
        verbose_name = 'Composant de kit'
        verbose_name_plural = 'Composants de kit'
        unique_together = [('kit', 'produit')]
        ordering = ['id']

    def __str__(self):
        return f'{self.kit_id}: {self.produit_id} × {self.quantite}'


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
