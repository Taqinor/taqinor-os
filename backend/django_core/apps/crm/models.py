import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    date_creation = models.DateTimeField(auto_now_add=True)
    # Traçabilité (additif) : qui a créé le client (forcé côté serveur) et
    # date de dernière modification. created_by est nullable (clients importés /
    # créés depuis un lead sans utilisateur courant) et SET_NULL pour ne jamais
    # perdre un client si l'utilisateur est supprimé.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_crees',
    )
    date_modification = models.DateTimeField(auto_now=True)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)
    # FG41 — plafond d'encours client (soft warning, jamais un blocage dur).
    # NULL = pas de limite définie (comportement actuel inchangé).
    # Quand défini, un devis/facture ajouté qui pousse l'encours TTC total
    # des factures ouvertes au-delà déclenche un avertissement API + UI.
    plafond_credit = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        verbose_name='Plafond de crédit (MAD TTC)',
        help_text='Seuil d\'encours client. Vide = pas de limite.',
    )
    # FG26 — RGPD : un client anonymisé (droit à l'effacement) a ses PII
    # scrubées tout en préservant l'intégrité comptable (devis/factures gardés).
    # Le drapeau bloque toute ré-identification accidentelle et marque la ligne.
    is_anonymized = models.BooleanField(default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)

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
        # Additif (toiture-3D intake) : le prospect ne connaît pas toujours son
        # type de raccordement — choix tolérant qui ne fausse pas l'existant.
        INCONNU = 'inconnu', 'Je ne sais pas'

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

    # Langue préférée du contact pour les messages (ex. WhatsApp). Nullable :
    # tant qu'elle n'est pas renseignée, le message retombe sur le FR. Les clés
    # sont identiques à celles attendues par le constructeur WhatsApp
    # (apps.ventes.utils.whatsapp : langue ∈ {'fr','darija'}).
    class LanguePreferee(models.TextChoices):
        FR = 'fr', 'Français'
        DARIJA = 'darija', 'Darija'

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
    # Langue préférée du contact (FR/Darija) — pré-sélectionne la langue du
    # message WhatsApp. Nullable : non renseignée → retombe sur le FR.
    langue_preferee = models.CharField(
        max_length=10, choices=LanguePreferee.choices, blank=True, null=True)
    # Bornes géographiques : latitude ∈ [-90, 90], longitude ∈ [-180, 180].
    # Les validateurs s'appliquent à full_clean()/serializers ; le DecimalField
    # max_digits=9/decimal_places=6 autorise déjà ±999.999999, d'où ces gardes.
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])

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
    # ── Q2 — Toiture 3D : pin + contour BRUTS du client (additif, optionnels) ──
    # Le client POINTE simplement son bâtiment (il n'est PAS obligé de dessiner) :
    # roof_point = {lat, lng} de l'épingle ; roof_outline = polygone rough
    # OPTIONNEL [[lat,lng], …], le plus souvent vide. Distinct du layout
    # FINALISÉ (panneaux placés) qui vit sur Devis.roof_layout et seul atteint la
    # proposition. bill_kwh = conso mensuelle estimée (kWh) saisie au diagnostic.
    roof_point = models.JSONField(null=True, blank=True)
    roof_outline = models.JSONField(null=True, blank=True)
    bill_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Jeton imprévisible par lead pour le lien de hand-off Meriem (conception
    # privée) ET, en aval, la proposition web tokenisée. Toujours posé côté
    # serveur, jamais lu d'un corps de requête.
    token = models.UUIDField(default=uuid.uuid4, editable=False,
                             unique=True, db_index=True)
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

    # FG28 — Horodatage de la PREMIÈRE prise de contact (set server-side dès
    # que le stage sort de NEW ou qu'une note de contact est enregistrée).
    # Nullable : NULL = jamais contacté. Permet le calcul du délai de réponse
    # et l'alerte SLA « non contacté > Xh » (filtre kanban + badge rouge).
    first_contacted_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Premier contact à',
    )

    # ── Archivage réversible (2026-06-13) — additif ──
    # Un lead archivé disparaît des vues par défaut (kanban/liste/calendrier/
    # graphique) mais reste filtrable (« Archivés ») et restaurable. La
    # suppression définitive reste un geste admin distinct (destroy).
    is_archived = models.BooleanField(default=False)
    # Champs personnalisés (T11) — valeurs indexées par CustomFieldDef.code.
    custom_data = models.JSONField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads_archives',
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # QJ6 — Score de qualité calculé (0–100) et persisté pour un tri
    # pagination-safe. Recalculé à chaque création/mise à jour du lead
    # (services.recompute_lead_score). NULL sur les leads importés avant la
    # migration (backfill optionnel au premier accès).
    score = models.IntegerField(
        null=True, blank=True,
        verbose_name='Score de qualité',
        help_text='Score 0–100 calculé automatiquement (voir scoring.py).',
    )

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'source']),
            models.Index(fields=['company', 'stage']),
            models.Index(fields=['company', 'score'], name='crm_lead_company_score_idx'),
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
        # FG30 — Interactions de communication typées
        APPEL = 'appel', 'Appel'
        EMAIL = 'email', 'E-mail'

    # FG30 — Résultat optionnel d'un appel ou e-mail (affiché dans le chatter).
    OUTCOMES = [
        ('',        '—'),
        ('joint',   'Joint'),
        ('non_joint', 'Non joint'),
        ('rappel',  'À rappeler'),
        ('refuse',  'Refus'),
        ('interesse', 'Intéressé'),
    ]
    outcome = models.CharField(
        max_length=20, blank=True, default='',
        choices=OUTCOMES,
        verbose_name="Résultat de l'interaction",
    )

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
    # Marque une entrée issue d'une action « en masse » (édition groupée de
    # plusieurs leads) — l'Historique l'affiche avec un badge « en masse ».
    bulk = models.BooleanField(default=False)
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


class Canal(models.Model):
    """Canal / source de lead géré (Paramètres → CRM). Le champ Lead.canal reste
    une clé texte ; cette liste pilote le sélecteur et les libellés. Additif.

    `cle` = clé stockée sur Lead.canal (ex. 'site_web'). `protege` verrouille un
    canal critique contre le renommage/la suppression : 'site_web' est utilisé
    par le webhook du site web — le supprimer/renommer casserait le pipeline."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='canaux')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=80)
    ordre = models.PositiveIntegerField(default=0)
    protege = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Canal de lead'
        verbose_name_plural = 'Canaux de lead'

    def __str__(self):
        return self.libelle


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


class MessageTemplate(models.Model):
    """FG36 — Modèles de messages WhatsApp/SMS réutilisables en CRM.

    Chaque modèle porte un nom, une langue, un corps avec des variables
    substituables ({prenom}, {ville}, {lien}) et un flag d'archivage.
    Scoped par société ; éditable uniquement par l'admin.
    """

    class Langue(models.TextChoices):
        FR = 'fr', 'Français'
        DARIJA = 'darija', 'Darija'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='crm_message_templates',
    )
    nom = models.CharField(max_length=150, verbose_name='Nom du modèle')
    langue = models.CharField(
        max_length=10, choices=Langue.choices, default=Langue.FR,
        verbose_name='Langue')
    # Variables disponibles : {prenom}, {ville}, {lien} (lien devis)
    corps = models.TextField(verbose_name='Corps du message')
    archived = models.BooleanField(default=False, verbose_name='Archivé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Modèle de message'
        verbose_name_plural = 'Modèles de messages'

    def __str__(self):
        return f"{self.nom} ({self.get_langue_display()})"

    def render(self, prenom='', ville='', lien='') -> str:
        """Substitue les variables dans le corps du modèle."""
        return (self.corps
                .replace('{prenom}', prenom or '')
                .replace('{ville}', ville or '')
                .replace('{lien}', lien or ''))


class Parrainage(models.Model):
    """N98 — parrainage : un client (parrain) recommande un prospect (filleul).

    Le filleul peut être un lead non encore converti et/ou un client. La
    récompense (configurable, défaut en Paramètres) est versée une fois le
    parrainage « converti ». Additif, borné société.
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        CONVERTI = 'converti', 'Converti'
        RECOMPENSE_VERSEE = 'recompense_versee', 'Récompense versée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='parrainages')
    parrain = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='parrainages_donnes')
    filleul_lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='parrainages')
    filleul_client = models.ForeignKey(
        'crm.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='parrainages_recus')
    filleul_nom = models.CharField(max_length=200, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    recompense = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Parrainage'

    def __str__(self):
        return f'Parrainage #{self.pk} (parrain {self.parrain_id})'


class ObjectifCommercial(models.Model):
    """FG39 — Objectif commercial / KPI target (objectif vs réalisé).

    Chaque objectif porte une métrique, une période et une cible (Decimal).
    Le « réalisé » est calculé à la demande (endpoint attainment) depuis les
    données du domaine CRM — pas stocké, pour rester toujours à jour.

    Métriques CRM-only (pas d'import ventes) :
      - nb_leads    : leads créés dans la période
      - nb_contacts : leads passés en CONTACTED+ dans la période
      - nb_devis    : placeholder (réalisé = 0 sans données ventes)
      - ca_signe    : placeholder (réalisé = 0 sans données ventes)
      - nb_rdv      : rendez-vous effectués dans la période

    Les métriques ``nb_devis`` et ``ca_signe`` sont exposées pour permettre
    au fondateur de saisir des cibles maintenant ; le réalisé sera branché
    quand la couche service ventes sera exposée via un sélecteur cross-app.
    (Aucun import de ``apps.ventes.models`` ici — règle import-linter.)
    """

    class PeriodType(models.TextChoices):
        MONTH = 'month', 'Mensuel'
        QUARTER = 'quarter', 'Trimestriel'
        YEAR = 'year', 'Annuel'

    class Metric(models.TextChoices):
        NB_LEADS = 'nb_leads', 'Nombre de leads'
        NB_CONTACTS = 'nb_contacts', 'Leads contactés'
        NB_DEVIS = 'nb_devis', 'Nombre de devis'
        CA_SIGNE = 'ca_signe', 'CA signé (MAD TTC)'
        NB_RDV = 'nb_rdv', 'Rendez-vous effectués'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='objectifs_commerciaux',
    )
    # Responsable optionnel — NULL = objectif d'équipe global.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='crm_objectifs',
        verbose_name='Responsable',
    )
    metric = models.CharField(
        max_length=20,
        choices=Metric.choices,
        verbose_name='Métrique',
    )
    period_type = models.CharField(
        max_length=10,
        choices=PeriodType.choices,
        default=PeriodType.MONTH,
        verbose_name='Périodicité',
    )
    # Année du début de la période (ex. 2026). Pour un trimestre : trimestre
    # 1 = mois 1–3 de cette année. Pour un mois : period_month (1–12).
    period_year = models.PositiveSmallIntegerField(verbose_name='Année')
    # Pour les objectifs mensuels (1–12) ; ignoré pour les trimestriels/annuels.
    period_month = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Mois (1–12)',
        help_text='Uniquement pour les objectifs mensuels.',
    )
    # Pour les objectifs trimestriels (1–4) ; ignoré sinon.
    period_quarter = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Trimestre (1–4)',
        help_text='Uniquement pour les objectifs trimestriels.',
    )
    cible = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Cible',
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='crm_objectifs_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objectif commercial'
        verbose_name_plural = 'Objectifs commerciaux'
        ordering = ['-period_year', '-period_month', 'metric']
        # Contraintes nommées (pas d'Index sans nom — règle CI-enforced).
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_month'],
                name='crm_obj_uniq_month',
                condition=models.Q(period_type='month'),
            ),
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year', 'period_quarter'],
                name='crm_obj_uniq_quarter',
                condition=models.Q(period_type='quarter'),
            ),
            models.UniqueConstraint(
                fields=['company', 'owner', 'metric',
                        'period_type', 'period_year'],
                name='crm_obj_uniq_year',
                condition=models.Q(period_type='year'),
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_metric_display()} — {self.period_type} '
            f'{self.period_year} (cible {self.cible})'
        )


class Appointment(models.Model):
    """QJ20 — Rendez-vous (visite commerciale/technique) planifié sur un lead.

    Modèle additif. Un lead peut avoir plusieurs rendez-vous ; le statut suit
    le cycle de vie (planifié → confirmé → effectué / annulé). Company scopé :
    un rendez-vous appartient à la société du lead. La date planifiée est
    stockée en UTC (convention Django) ; l'UI affiche l'heure locale marocaine
    (Africa/Casablanca).

    RAMADAN-AWARE PACING (``ramadan_pacing``): champ booléen sur la société
    (voir ``Appointment.RAMADAN_AVOID_HOURS``) — quand activé, les rappels
    ne sont PAS envoyés pendant la plage horaire iftar-sensible (défaut :
    18 h – 21 h Casablanca). Le service de rappel consulte ce drapeau avant
    d'envoyer. Aucune dépendance externe : le drapeau est simplement posé par
    l'utilisateur dans les réglages, et la logique est documentée ici.
    """

    # Heures (locales Casablanca) à éviter quand le drapeau Ramadan est actif.
    # Plage iftar-sensible (simplifié : 18h–21h). Documenté ici pour référence.
    RAMADAN_AVOID_START_H = 18
    RAMADAN_AVOID_END_H = 21

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        CONFIRME = 'confirme', 'Confirmé'
        EFFECTUE = 'effectue', 'Effectué'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='appointments',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='appointments',
        verbose_name='Lead',
    )
    scheduled_at = models.DateTimeField(
        verbose_name='Date et heure planifiées',
        help_text='Heure UTC ; affichée en Africa/Casablanca dans l\'UI.',
    )
    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.PLANIFIE,
        verbose_name='Statut',
    )
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='Notes de visite',
    )
    # Whether a reminder has already been dispatched (idempotency guard for
    # the beat job — prevents double-sending if the job fires twice).
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name='Rappel envoyé',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['company', 'scheduled_at'],
                         name='crm_appt_co_sched_idx'),
            models.Index(fields=['lead', 'statut'],
                         name='crm_appt_lead_stat_idx'),
        ]

    def __str__(self):
        return (
            f'RDV #{self.pk} — lead {self.lead_id} '
            f'le {self.scheduled_at:%Y-%m-%d %H:%M} ({self.statut})'
        )


class ConcurrentPerte(models.Model):
    """FG242 — Suivi des concurrents sur deals perdus.

    Sur un lead PERDU (drapeau ``Lead.perdu`` — voir STAGES.py : « Perdu » est un
    lost-flag, pas une étape), on saisit le concurrent qui a remporté l'affaire
    et son prix. Cette intelligence concurrentielle alimente l'analyse des
    pertes (qui nous bat, à quel prix, sur quel motif).

    Additif et borné société : un enregistrement appartient à la société du lead
    (posée côté serveur, jamais lue du corps de requête — multi-tenant). Le motif
    réutilise le vocabulaire ``Lead.motif_perte`` (texte libre alimenté par la
    liste gérée ``MotifPerte``), donc aucun nouveau jeu de valeurs n'est inventé.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='concurrents_perte',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='concurrents_perte',
        verbose_name='Lead perdu',
    )
    # Nom du concurrent gagnant (obligatoire — c'est le cœur de l'intel).
    concurrent_nom = models.CharField(
        max_length=200,
        verbose_name='Concurrent gagnant',
    )
    # Prix proposé par le concurrent (optionnel : pas toujours connu).
    concurrent_prix = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Prix du concurrent',
        help_text='Prix proposé par le concurrent. Vide si inconnu.',
    )
    # Devise du prix (défaut MAD) ; courte par convention ISO-ish.
    devise = models.CharField(
        max_length=8,
        default='MAD',
        blank=True,
        verbose_name='Devise',
    )
    # Motif de la perte — réutilise le vocabulaire de Lead.motif_perte (texte
    # libre alimenté par la liste gérée MotifPerte). Optionnel.
    motif = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='Motif de la perte',
    )
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')
    # Traçabilité : qui a saisi l'info (forcé côté serveur) + quand.
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='concurrents_perte_saisis',
        verbose_name='Saisi par',
    )
    saisi_le = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Concurrent (deal perdu)'
        verbose_name_plural = 'Concurrents (deals perdus)'
        ordering = ['-saisi_le']
        indexes = [
            # Nom d'index ≤ 30 chars (règle CI-enforced).
            models.Index(fields=['company', 'lead'],
                         name='crm_concperte_co_lead_idx'),
        ]

    def __str__(self):
        return (
            f'Concurrent {self.concurrent_nom} '
            f'(lead {self.lead_id})'
        )


class PointContact(models.Model):
    """FG204 — Tableau d'attribution multi-touch : journal des points de contact.

    Au-delà du first-touch (``Lead.canal``/``Lead.source``), on consigne CHAQUE
    point de contact du parcours d'un lead — publicité Meta → site web →
    WhatsApp → signature — pour une attribution multi-touch (qui a vraiment
    amené, puis converti, le lead).

    Additif et borné société : un enregistrement appartient à la société du lead
    (posée côté serveur, jamais lue du corps de requête — multi-tenant). Le
    ``canal`` réutilise le vocabulaire ``Lead.Canal`` (meta_ads/whatsapp_ctwa/
    site_web/reference/telephone/walk_in/autre), donc aucun nouveau jeu de
    valeurs n'est inventé. ``cout`` est optionnel (canaux payants : Meta Ads…).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='points_contact',
    )
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.CASCADE,
        related_name='points_contact',
        verbose_name='Lead',
    )
    # Canal du point de contact — réutilise STRICTEMENT le vocabulaire
    # Lead.Canal (max_length=20 couvre la plus longue clé, 'whatsapp_ctwa').
    canal = models.CharField(
        max_length=20,
        choices=Lead.Canal.choices,
        verbose_name='Canal',
    )
    # Source/détail libre du canal (ex. nom de la campagne Meta, page web).
    source = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name='Source',
    )
    # Date/heure du point de contact (défaut : maintenant à la création).
    date_contact = models.DateTimeField(
        verbose_name='Date du contact',
    )
    # Rang explicite dans le parcours (1, 2, 3…) — pose l'ordre du journal
    # même quand deux contacts partagent la même date.
    ordre = models.PositiveIntegerField(
        default=0,
        verbose_name='Ordre / séquence',
    )
    # Note libre sur ce point de contact.
    detail = models.TextField(blank=True, null=True, verbose_name='Détail')
    # Coût du point de contact pour les canaux payants (Meta Ads…). Optionnel.
    cout = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Coût',
        help_text='Coût du point de contact (canaux payants). Vide si gratuit.',
    )
    # Traçabilité : qui a saisi le point de contact (forcé côté serveur) + quand.
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='points_contact_saisis',
        verbose_name='Saisi par',
    )
    saisi_le = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Point de contact'
        verbose_name_plural = 'Points de contact'
        # Journal chronologique : par ordre explicite puis date de contact.
        ordering = ['ordre', 'date_contact', 'id']
        indexes = [
            # Nom d'index ≤ 30 chars (règle CI-enforced).
            models.Index(fields=['company', 'lead'],
                         name='crm_ptcontact_co_lead_idx'),
        ]

    def __str__(self):
        return (
            f'Point de contact {self.get_canal_display()} '
            f'(lead {self.lead_id})'
        )
