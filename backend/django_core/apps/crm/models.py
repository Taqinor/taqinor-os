from django.conf import settings
from django.db import models

from .stages import STAGE_CHOICES, NEW


class Client(models.Model):
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='clients',
    )

    class TypeClient(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        ENTREPRISE = 'entreprise', 'Entreprise'

    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    # Optionnel depuis 2026-06 : un client peut être créé depuis un lead sans
    # email (l'unicité (company, email) reste garantie quand l'email existe).
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    # ── Type + identifiants légaux marocains (2026-06) — additif ──
    # Particulier → CIN ; Entreprise → ICE / IF / RC. Le formulaire montre le
    # bon jeu de champs selon le type. Migration de données : un client qui
    # porte déjà un ICE devient « Entreprise », sinon « Particulier ».
    type_client = models.CharField(
        max_length=12, choices=TypeClient.choices,
        default=TypeClient.PARTICULIER)
    cin = models.CharField(max_length=30, blank=True, null=True)
    # Identifiant Commun de l'Entreprise (clients professionnels marocains).
    # Optionnel : affiché sur les PDF uniquement quand renseigné.
    ice = models.CharField(max_length=30, blank=True, null=True)
    if_fiscal = models.CharField(max_length=30, blank=True, null=True)
    rc = models.CharField(max_length=30, blank=True, null=True)
    # Valeurs des champs personnalisés définis par la société (module 'client').
    # Additif : map {field_key: value} validée par customfields. Jamais null en
    # base (défaut {}), scopé société via les définitions.
    custom_fields = models.JSONField(default=dict, blank=True, null=True)
    # Marqueur d'origine : non nul = fiche issue d'un import CSV/Excel (à
    # distinguer des fiches saisies à la main et de la migration Odoo). Additif.
    import_batch = models.ForeignKey(
        'imports.ImportBatch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='clients')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        unique_together = [('company', 'email')]

    def __str__(self):
        return f"{self.nom} {self.prenom if self.prenom else ''}"


class Lead(models.Model):
    """A sales lead / opportunity — distinct from a Client (customer) record.

    Leads carry a pipeline stage (canonical from STAGES.py) and a source/origin
    so imported test leads are distinguishable from leads created natively in the
    OS. Pipeline stage lives HERE, never on the Client/contact table.
    """

    class Source(models.TextChoices):
        OS_NATIVE = 'os_native', 'Créé dans TAQINOR'
        ODOO_IMPORT_TEST = 'odoo_import_test', 'Import test Odoo'
        SITE_WEB = 'site_web', 'Site web'

    # Tranches de facture du diagnostic du site public — les CLÉS sont
    # strictement identiques aux ids émis par taqinor.ma (billRange.ts).
    class BillRangeBucket(models.TextChoices):
        LT800 = 'lt800', 'Moins de 800 MAD'
        B800_1000 = '800-1000', '800 – 1 000 MAD'
        B1000_1500 = '1000-1500', '1 000 – 1 500 MAD'
        B1500_3000 = '1500-3000', '1 500 – 3 000 MAD'
        B3000_5000 = '3000-5000', '3 000 – 5 000 MAD'
        B5000_10000 = '5000-10000', '5 000 – 10 000 MAD'
        GT10000 = 'gt10000', 'Plus de 10 000 MAD'

    # Canal marketing d'origine (différent de `source`, qui marque la
    # provenance technique de la donnée : natif vs import).
    class Canal(models.TextChoices):
        META_ADS = 'meta_ads', 'Publicité Meta'
        WHATSAPP_CTWA = 'whatsapp_ctwa', 'WhatsApp/CTWA'
        SITE_WEB = 'site_web', 'Site web'
        REFERENCE = 'reference', 'Référence'
        TELEPHONE = 'telephone', 'Téléphone'
        WALK_IN = 'walk_in', 'Visite/Walk-in'
        AUTRE = 'autre', 'Autre'

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        NORMALE = 'normale', 'Normale'
        HAUTE = 'haute', 'Haute'

    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        COMMERCIAL = 'commercial', 'Commercial'
        INDUSTRIEL = 'industriel', 'Industriel'
        AGRICOLE = 'agricole', 'Agricole'

    class Raccordement(models.TextChoices):
        MONOPHASE = 'monophase', 'Monophasé'
        TRIPHASE = 'triphase', 'Triphasé'

    class TypeToiture(models.TextChoices):
        TERRASSE_BETON = 'terrasse_beton', 'Terrasse béton'
        TOLE_METAL = 'tole_metal', 'Tôle/Métal'
        TUILES = 'tuiles', 'Tuiles'
        BAC_ACIER = 'bac_acier', 'Bac acier'
        FIBROCIMENT = 'fibrociment', 'Fibrociment'
        AUTRE = 'autre', 'Autre'

    class Orientation(models.TextChoices):
        SUD = 'sud', 'Sud'
        SUD_EST = 'sud_est', 'Sud-Est'
        SUD_OUEST = 'sud_ouest', 'Sud-Ouest'
        EST = 'est', 'Est'
        OUEST = 'ouest', 'Ouest'
        AUTRE = 'autre', 'Autre'

    class Ombrage(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        PARTIEL = 'partiel', 'Partiel'
        IMPORTANT = 'important', 'Important'

    class StructurePref(models.TextChoices):
        ACIER = 'acier', 'Acier'
        ALUMINIUM = 'aluminium', 'Aluminium'

    class BatterieSouhaitee(models.TextChoices):
        SANS = 'sans', 'Sans batterie'
        AVEC = 'avec', 'Avec batterie'
        LES_DEUX = 'les_deux', 'Les deux options'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='leads',
    )
    # Contact identity (a lead may not yet be a structured client).
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255, blank=True, null=True)
    societe = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    ville = models.CharField(max_length=120, blank=True, null=True)

    # Client (fiche structurée) résolu depuis ce lead — rempli au premier devis
    # ou manuellement ; la résolution évite les doublons (voir services.py).
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
    )

    # Facture électrique du lead (MAD/mois). Si l'été ne diffère pas de
    # l'hiver, facture_hiver vaut pour les deux (ete_differente = False).
    facture_hiver = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    facture_ete = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ete_differente = models.BooleanField(default=False)

    # ── Contact & localisation (extension CRM solaire 2026-06) ──
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    # ── Pipeline / CRM ──
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leads_assignes')
    canal = models.CharField(
        max_length=20, choices=Canal.choices, blank=True, null=True)
    priorite = models.CharField(
        max_length=10, choices=Priorite.choices, default=Priorite.NORMALE)
    # Tags libres, séparés par des virgules (ex. "Régularisation 82-21, VIP")
    tags = models.CharField(max_length=500, blank=True, null=True)
    # Drapeau « Perdu » — indépendant de l'étape (voir STAGES.py : « Perdu »
    # n'est PAS une étape, c'est un lost-flag qui se pose depuis N'IMPORTE
    # quelle étape, avec sa raison dans motif_perte). Un lead Froid n'est pas
    # forcément perdu ; un lead à « Devis envoyé » peut l'être.
    perdu = models.BooleanField(default=False)
    motif_perte = models.CharField(max_length=255, blank=True, null=True)
    relance_date = models.DateField(null=True, blank=True)
    type_installation = models.CharField(
        max_length=20, choices=TypeInstallation.choices, blank=True, null=True)

    # ── Profil énergétique ──
    conso_mensuelle_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    tranche_onee = models.CharField(max_length=100, blank=True, null=True)
    raccordement = models.CharField(
        max_length=12, choices=Raccordement.choices, blank=True, null=True)
    # Installation existante à régulariser ? (Loi 82-21)
    regularisation_8221 = models.BooleanField(default=False)

    # ── Pompage solaire (leads Agricole) — mêmes entrées que le générateur ──
    pompe_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    pompe_hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    pompe_debit_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)

    # ── Toiture & site ──
    type_toiture = models.CharField(
        max_length=20, choices=TypeToiture.choices, blank=True, null=True)
    surface_toiture_m2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    orientation = models.CharField(
        max_length=12, choices=Orientation.choices, blank=True, null=True)
    inclinaison_deg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    ombrage = models.CharField(
        max_length=12, choices=Ombrage.choices, blank=True, null=True)
    ombrage_notes = models.TextField(blank=True, null=True)
    nb_etages = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    structure_pref = models.CharField(
        max_length=12, choices=StructurePref.choices, blank=True, null=True)
    taille_souhaitee_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    batterie_souhaitee = models.CharField(
        max_length=12, choices=BatterieSouhaitee.choices, blank=True, null=True)

    # ── Visite technique (légère) ──
    visite_prevue_le = models.DateField(null=True, blank=True)
    visite_effectuee = models.BooleanField(default=False)
    visite_notes = models.TextField(blank=True, null=True)

    # Pipeline stage — canonical keys from STAGES.py (default Nouveau / NEW).
    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default=NEW,
    )
    # Origin marker: native vs imported test data.
    source = models.CharField(
        max_length=32,
        choices=Source.choices,
        default=Source.OS_NATIVE,
    )
    # Traceability for imported records (e.g. Odoo lead id) — never written back.
    external_system = models.CharField(max_length=50, blank=True, null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)

    # ── Intake site web (taqinor.ma) — tous additifs et optionnels ──
    # Tranche du diagnostic (clés identiques au site) ; distinct de
    # facture_hiver (montant exact saisi au CRM).
    bill_range_bucket = models.CharField(
        max_length=20, choices=BillRangeBucket.choices, blank=True, null=True)
    # Type de toiture TEL QU'ÉMIS par le site (villa/hangar/toit_plat/autre) —
    # volontairement distinct de type_toiture (taxonomie technique CRM).
    roof_type = models.CharField(max_length=30, blank=True, null=True)
    # Bande ROI préliminaire affichée au prospect (ex. « 5 à 9 kWc · 4 à 6 ans »)
    roi_band = models.CharField(max_length=200, blank=True, null=True)
    whatsapp_opt_in = models.BooleanField(null=True, blank=True)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    # Attribution publicitaire (capture first-touch du site)
    fbclid = models.CharField(max_length=500, blank=True, null=True)
    utm_source = models.CharField(max_length=300, blank=True, null=True)
    utm_medium = models.CharField(max_length=300, blank=True, null=True)
    utm_campaign = models.CharField(max_length=300, blank=True, null=True)
    utm_content = models.CharField(max_length=300, blank=True, null=True)
    utm_term = models.CharField(max_length=300, blank=True, null=True)

    note = models.TextField(blank=True, null=True)

    # ── Archivage réversible (2026-06-13) — additif ──
    # Un lead archivé disparaît des vues par défaut (kanban/liste/calendrier/
    # graphique) mais reste filtrable (« Archivés ») et restaurable. La
    # suppression définitive reste un geste admin distinct (destroy).
    is_archived = models.BooleanField(default=False)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads_archives',
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    # Valeurs des champs personnalisés (module 'lead') — voir app customfields.
    custom_fields = models.JSONField(default=dict, blank=True, null=True)

    # Marqueur d'origine : non nul = lead issu d'un import CSV/Excel. Séparé du
    # champ `source` (Odoo/site/natif) et de la migration Odoo ponctuelle.
    import_batch = models.ForeignKey(
        'imports.ImportBatch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leads')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'source']),
            models.Index(fields=['company', 'stage']),
        ]
        constraints = [
            # An imported record is unique per (company, system, external id) so
            # a re-run of the import does not create duplicates.
            models.UniqueConstraint(
                fields=['company', 'external_system', 'external_id'],
                name='uniq_lead_external_ref',
                condition=models.Q(external_id__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenom or ''} [{self.stage}]".strip()


class WebsiteLeadPayload(models.Model):
    """Charge utile BRUTE reçue du site web — stockée AVANT tout mapping.

    Garantie « jamais perdre un lead » : même si le mapping vers Lead échoue
    (payload inattendu, bug), la donnée d'origine est conservée telle quelle
    et rejouable. Aucune logique métier ici.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='website_lead_payloads',
    )
    payload = models.JSONField()
    remote_addr = models.CharField(max_length=64, blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True, null=True)
    lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='website_payloads')

    class Meta:
        verbose_name = 'Payload lead site web'
        verbose_name_plural = 'Payloads leads site web'
        ordering = ['-received_at']

    def __str__(self):
        return f"payload #{self.pk} ({'ok' if self.processed else 'brut'})"


class LeadActivity(models.Model):
    """Historique « chatter » d'un lead (style Odoo), modèle maison.

    Deux familles d'entrées :
      - automatiques : création du lead et changements de champs suivis
        (champ, ancienne valeur, nouvelle valeur, utilisateur, horodatage) —
        écrites côté serveur au niveau de l'API, jamais par le navigateur ;
      - manuelles : notes libres (appel passé, commentaire…).
    """

    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='lead_activities',
    )
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lead_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité lead'
        verbose_name_plural = 'Activités lead'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['lead', '-created_at'])]

    def __str__(self):
        return f"{self.lead_id} {self.kind} {self.field or ''}".strip()


class LeadTag(models.Model):
    """Étiquette de lead gérée (Paramètres → CRM). Le champ Lead.tags reste un
    texte libre ; cette liste sert de suggestions + couleurs. Additif."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='lead_tags')
    nom = models.CharField(max_length=80)
    couleur = models.CharField(max_length=7, blank=True, default='')
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Étiquette de lead'

    def __str__(self):
        return self.nom


class MotifPerte(models.Model):
    """Motif de perte géré (Paramètres → CRM). Le champ Lead.motif_perte reste
    un texte libre ; cette liste sert de choix proposés. Additif."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='motifs_perte')
    nom = models.CharField(max_length=150)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Motif de perte'

    def __str__(self):
        return self.nom


# Clé du canal « Site web » — protégée : utilisée par le webhook du site public
# (webhooks.py). Elle ne peut être ni renommée ni supprimée.
CANAL_SITE_WEB_KEY = 'site_web'


class CanalSource(models.Model):
    """Canal / source d'origine d'un lead, géré (Paramètres → CRM).

    Promotion de l'ancien enum Lead.Canal (texte libre stocké dans
    Lead.canal) vers une liste de référence éditable, scopée par société :
    ajout / renommage / réordonnancement. Le champ `Lead.canal` reste un
    CharField : cette liste fournit le libellé + l'ordre ; aucune valeur de
    lead existante ne change. Additif.

    La clé `site_web` (CANAL_SITE_WEB_KEY) est PROTÉGÉE — le webhook du site
    public écrit cette valeur. Elle ne peut être ni renommée ni supprimée.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='canaux_sources')
    # Clé stable (anglais/slug) stockée dans Lead.canal — jamais renommée.
    key = models.CharField(max_length=40)
    # Libellé affiché (français), librement modifiable.
    label = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=100)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'label']
        unique_together = [('company', 'key')]
        verbose_name = 'Canal / source de lead'
        verbose_name_plural = 'Canaux / sources de lead'

    def __str__(self):
        return self.label

    @property
    def is_protected(self):
        """Canal système non supprimable / non renommable (clé)."""
        return self.key == CANAL_SITE_WEB_KEY
