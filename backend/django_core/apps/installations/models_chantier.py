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


class ChecklistTemplate(models.Model):
    """N74 — modèle NOMMÉ de checklist d'onboarding/chantier, configurable dans
    Paramètres. Un template regroupe des étapes ordonnées (ChecklistEtapeModele)
    et peut être rattaché à un `type_installation` : à la création d'un chantier,
    le template dont le type correspond est sélectionné automatiquement ; sinon
    on retombe sur le template « Défaut » (type_installation vide).

    Le template « Défaut » est protégé et porte EXACTEMENT les étapes appliquées
    aujourd'hui — un chantier sans type spécifique reçoit donc la même checklist
    qu'avant (comportement préservé). Additif — aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_templates')
    nom = models.CharField(max_length=120)
    # Type d'installation qui auto-sélectionne ce template (résidentiel /
    # industriel / agricole). Vide = template « Défaut » (repli générique).
    type_installation = models.CharField(
        max_length=20, choices=Installation.TypeInstallation.choices,
        blank=True, null=True)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    # `protege` verrouille le template « Défaut » système contre la suppression.
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Modèle de checklist chantier"
        verbose_name_plural = "Modèles de checklist chantier"

    def __str__(self):
        return self.nom


class ChecklistEtapeModele(models.Model):
    """N4 — étape MODÈLE de la checklist d'exécution chantier, éditable dans
    Paramètres (libellé + ordre + activation). `capture_serie` marque les
    étapes où l'on saisit des numéros de série (N9 : panneaux/onduleur).
    `protege` verrouille une étape système contre la suppression. Additif.

    N74 — chaque étape appartient à un `template` (nullable : les étapes
    historiques sans template sont rattachées au template « Défaut » par la
    migration de données / l'amorçage paresseux)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_etapes')
    # N74 — template propriétaire (nullable pour la compat ; les étapes
    # orphelines sont migrées vers le template « Défaut »).
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.CASCADE,
        null=True, blank=True, related_name='etapes')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    # FG76 — une photo est REQUISE pour valider cette étape (gate identique à
    # F8 pour les créneaux de la shot list d'intervention). Défaut False : les
    # étapes existantes ne sont pas bloquées rétroactivement.
    photo_obligatoire = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        # N74 — la clé est unique PAR template (même cle réutilisable d'un
        # template à l'autre). Les étapes historiques (template=NULL) gardent
        # l'unicité par société jusqu'à leur rattachement au template « Défaut ».
        unique_together = [('company', 'template', 'cle')]
        verbose_name = "Étape de checklist chantier"
        verbose_name_plural = "Étapes de checklist chantier"

    def __str__(self):
        return self.libelle


class StageModele(models.Model):
    """CH1 — étape/gate CONFIGURABLE du cycle de vie chantier, par société.

    Étend le motif ChecklistTemplate/ChecklistEtapeModele : une liste ordonnée
    d'étapes (« stages ») éditable dans Paramètres (Directeur uniquement),
    amorcée au cycle de vie PV international (étude de site → conception →
    autorisations/82-21 → approvisionnement → montage mécanique → installation
    électrique → mise en service IEC 62446-1 → inspection/raccordement →
    remise client → O&M).

    Chaque étape est un GATE : `bloquant` rend son franchissement OBLIGATOIREMENT
    conditionné aux exigences cochées (`exige_*` — checklist faite, photos,
    n° de série, essais de mise en service, matériel disponible, dossier 82-21,
    pièces de remise) — plus les points d'arrêt QHSE (toujours vérifiés pour un
    gate bloquant, cf. CH2). Une étape non bloquante reste PUREMENT consultative.

    `statut_legacy` rabat l'étape sur l'entonnoir HISTORIQUE à 7 statuts de
    `Installation.statut` (JAMAIS supprimé) : l'arrivée sur une étape synchronise
    le statut hérité, ce qui préserve 1:1 les effets de bord existants
    (consommation du stock à « Installé », remise de garantie/parc à
    « Réceptionné » — FG70/N14) et toutes les vues/filtres actuels.
    Additif — company-scopée, aucune migration destructive."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stages_chantier')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    # Gate BLOQUANT : le franchissement exige les éléments requis ci-dessous
    # + la levée des points d'arrêt QHSE. Non bloquant = consultatif.
    bloquant = models.BooleanField(default=False)
    # ── Éléments REQUIS pour franchir le gate (si bloquant) ──
    exige_checklist = models.BooleanField(default=False)
    exige_photos = models.BooleanField(default=False)
    exige_series = models.BooleanField(default=False)
    exige_tests = models.BooleanField(default=False)
    exige_materiel = models.BooleanField(default=False)
    exige_dossier = models.BooleanField(default=False)
    exige_pack = models.BooleanField(default=False)
    # Statut HÉRITÉ (enum 7 étapes, jamais supprimé) que porte un chantier
    # arrivé sur cette étape — c'est le pont qui fait tirer les effets de bord
    # existants (stock/garantie) sur les gates mappés.
    statut_legacy = models.CharField(
        max_length=20, choices=Installation.Statut.choices,
        null=True, blank=True)
    actif = models.BooleanField(default=True)
    # `protege` verrouille une étape système contre la suppression (comme les
    # étapes de checklist) ; elle reste désactivable/réordonnable.
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('company', 'cle')]
        verbose_name = 'Étape de chantier (gate)'
        verbose_name_plural = 'Étapes de chantier (gates)'

    def __str__(self):
        return f'{self.ordre} · {self.libelle}'


class CommissioningRecord(models.Model):
    """CH3 — fiche de RECETTE structurée d'un chantier selon IEC 62446-1
    (essais de mise en service des systèmes PV raccordés au réseau).

    Première classe côté ``installations`` : remplace la saisie libre historique
    (``Installation.mes_pv_notes`` / ``mes_production_test`` / ``mes_tension``,
    CONSERVÉS lisibles — aucune donnée détruite) par un jeu d'essais discret :

      * documentation (dossier as-built / schéma / datasheets présents) ;
      * inspection visuelle (structure, câblage, mise à la terre) ;
      * essais électriques : continuité de terre, polarité, Voc/Isc par string
        (relevés I-V — cf. ``CommissioningIVReading``, miroir de FG275), mesure
        de résistance d'isolement ;
      * vérification de performance (production d'essai vs attendu) ;
      * sécurité (dispositifs de coupure, signalisation).

    Une fiche PASSÉE (``resultat`` = conforme / conforme avec réserves) est
    REQUISE pour franchir le gate « Mise en service » (CH2). Un chantier ↔ une
    fiche (unicité). Additif — company posée côté serveur ; aucun statut de
    devis touché (règle #4)."""

    class Resultat(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CONFORME = 'conforme', 'Conforme'
        RESERVES = 'reserves', 'Conforme avec réserves'
        NON_CONFORME = 'non_conforme', 'Non conforme'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='commissioning_records')
    installation = models.OneToOneField(
        Installation, on_delete=models.CASCADE,
        related_name='commissioning_record')
    date_essai = models.DateField(null=True, blank=True)
    technicien = models.CharField(max_length=120, blank=True, null=True)
    # ── XFSM12 — instrument de mesure utilisé (traçabilité d'étalonnage,
    #    exigée par l'IEC 62446-1). String-FK vers ``outillage.Outillage`` (par
    #    id, jamais un import du modèle pour la RELATION — l'app lit déjà
    #    ``apps.outillage.models`` ailleurs, cf. field_services.py) : nullable,
    #    additif, aucune fiche existante n'est affectée. ──
    instrument_id = models.PositiveIntegerField(null=True, blank=True)
    # ── Documentation (IEC 62446-1 §4) ──
    doc_dossier_ok = models.BooleanField(null=True, blank=True)
    doc_schema_ok = models.BooleanField(null=True, blank=True)
    doc_datasheets_ok = models.BooleanField(null=True, blank=True)
    # ── Inspection visuelle (§5) ──
    visuel_structure_ok = models.BooleanField(null=True, blank=True)
    visuel_cablage_ok = models.BooleanField(null=True, blank=True)
    visuel_terre_ok = models.BooleanField(null=True, blank=True)
    # ── Essais électriques (§6) ──
    continuite_terre_ok = models.BooleanField(null=True, blank=True)
    continuite_terre_ohm = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True)
    polarite_ok = models.BooleanField(null=True, blank=True)
    # Résistance d'isolement (MΩ) ; seuil usuel ≥ 1 MΩ.
    isolement_mohm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    isolement_ok = models.BooleanField(null=True, blank=True)
    # ── Vérification de performance (§7) ──
    production_test_kw = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    production_attendue_kw = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    performance_ok = models.BooleanField(null=True, blank=True)
    # ── Sécurité ──
    securite_coupure_ok = models.BooleanField(null=True, blank=True)
    securite_signalisation_ok = models.BooleanField(null=True, blank=True)
    resultat = models.CharField(
        max_length=14, choices=Resultat.choices, default=Resultat.EN_COURS)
    observations = models.TextField(blank=True, null=True)
    # FG275 — lien LÂCHE (par id, jamais un import du modèle ventes) vers une
    # fiche de recette ventes existante dont on réutilise les courbes I-V déjà
    # saisies ; les relevés propres à cette fiche vivent dans
    # ``CommissioningIVReading``.
    ventes_recette_id = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='commissioning_records_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Fiche de recette (IEC 62446-1)'
        verbose_name_plural = 'Fiches de recette (IEC 62446-1)'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Recette {self.resultat} — chantier {self.installation_id}'

    @property
    def passe(self):
        """La fiche est PASSÉE (débloque le gate) si conforme ou conforme
        avec réserves."""
        return self.resultat in (self.Resultat.CONFORME, self.Resultat.RESERVES)

    @property
    def instrument(self):
        """XFSM12 — instrument de mesure référencé (résolu par id, jamais un
        import au niveau module — ``apps.outillage.models`` reste une lecture
        locale à la fonction, cf. le patron déjà en place dans
        ``field_services.py``). None si ``instrument_id`` est vide ou pointe
        vers un outil supprimé."""
        if not self.instrument_id:
            return None
        from apps.outillage.models import Outillage
        return Outillage.objects.filter(pk=self.instrument_id).first()

    @property
    def instrument_etalonnage_expire(self):
        """XFSM12 — True si l'instrument référencé a un étalonnage FG80 EXPIRÉ
        (intervalle défini ET date de prochaine calibration dépassée ou jamais
        calibré). None si aucun instrument n'est référencé, ou si l'instrument
        n'est pas soumis à calibration périodique (intervalle = 0)."""
        instrument = self.instrument
        if instrument is None or not instrument.intervalle_calibration_mois:
            return None
        if instrument.date_prochaine_calibration is None:
            return True
        import datetime
        return instrument.date_prochaine_calibration <= datetime.date.today()


class CommissioningIVReading(models.Model):
    """CH3/FG275 — relevé I-V par string d'une fiche de recette : Voc/Isc/Pmax
    mesurés confrontés aux valeurs attendues (datasheet × modules en série).

    Miroir, côté ``installations``, de la capture I-V ventes (FG275) : la fiche
    de recette peut aussi référencer une fiche ventes existante
    (``CommissioningRecord.ventes_recette_id``) pour réutiliser des courbes déjà
    saisies. Additif — company posée côté serveur."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='commissioning_iv_readings')
    record = models.ForeignKey(
        CommissioningRecord, on_delete=models.CASCADE,
        related_name='iv_readings')
    string_label = models.CharField(max_length=60)
    n_modules_serie = models.PositiveSmallIntegerField(null=True, blank=True)
    voc_mesure_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    isc_mesure_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    pmax_mesure_w = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    voc_attendu_v = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    isc_attendu_a = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    pmax_attendu_w = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ecart_pmax_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    defaut_detecte = models.BooleanField(default=False)
    observations = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Relevé I-V (recette chantier)'
        verbose_name_plural = 'Relevés I-V (recette chantier)'
        ordering = ['record', 'string_label']

    def __str__(self):
        return f'I-V {self.string_label} (recette {self.record_id})'


class ReverificationMesure(models.Model):
    """XFSM13 — re-vérification périodique IEC 62446-2 : reprend les points
    électriques de la RECETTE (``CommissioningRecord`` : Riso, continuité de
    terre, Voc par string via ``CommissioningIVReading``) et calcule
    automatiquement l'écart (dérive %) vs cette baseline du chantier.

    Rattachée à une ``Intervention`` de type
    ``Intervention.Type.REVERIFICATION_62446`` (string-FK par id — le modèle
    ``Intervention`` n'est jamais importé ici pour éviter tout couplage inutile
    entre les deux modules de ``models_*``, cf. le même patron déjà en place
    pour ``StageModele``/``Installation.etape``). Un dépassement du seuil de
    dérive (paramétrable, défaut 20 %) crée automatiquement une ``Reserve``
    sur l'intervention (service `services.py`, jamais ici — modèle = données
    pures). Additif — company posée côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reverifications')
    intervention_id = models.PositiveIntegerField()
    record_baseline = models.ForeignKey(
        CommissioningRecord, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reverifications')
    # ── Points électriques repris de la recette (IEC 62446-1 §6) ──
    isolement_mohm = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    continuite_terre_ohm = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True)
    # ── Résultat de la comparaison, calculé côté serveur ──
    # {"string_label": ..., "voc_baseline_v": ..., "voc_mesure_v": ...,
    #  "ecart_pct": ...} par string.
    voc_comparaison = models.JSONField(default=list, blank=True)
    isolement_ecart_pct = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    seuil_alerte_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)
    depassement_detecte = models.BooleanField(default=False)
    reserve_id = models.PositiveIntegerField(null=True, blank=True)
    observations = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reverifications_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Re-vérification IEC 62446-2'
        verbose_name_plural = 'Re-vérifications IEC 62446-2'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Re-vérification #{self.intervention_id}'


class HandoverPack(models.Model):
    """CH4 — PACK DE REMISE client assemblé au franchissement du gate « Remise
    au client » (handover).

    Le pack RÉFÉRENCE (il ne stocke pas de binaire) les pièces du dossier remis
    au client + au vendeur : dossier as-built / schémas, fiches techniques
    (datasheets) des équipements, garanties (issues du parc SAV — FG70), le
    certificat de recette IEC 62446-1 (CH3), la référence du dossier
    réglementaire loi 82-21, et l'accès monitoring / application. La liste des
    pièces est un JSON `[{type, libelle, reference, present}]`, calculé côté
    serveur à partir de l'état réel du chantier — il DÉGRADE proprement quand
    une pièce manque (elle apparaît `present=False` plutôt que d'empêcher la
    génération).

    Un chantier ↔ un pack (unicité). Additif — company posée côté serveur ;
    aucun prix d'achat, aucun statut de devis touché (règle #4)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='handover_packs')
    installation = models.OneToOneField(
        Installation, on_delete=models.CASCADE,
        related_name='handover_pack')
    titre = models.CharField(max_length=160, blank=True, null=True)
    # Pièces assemblées : [{type, libelle, reference, present}].
    pieces = models.JSONField(default=list, blank=True)
    # Accès monitoring / application (URL ou identifiant de portail) remis au
    # client. Optionnel : dégrade proprement quand il n'est pas encore fourni.
    monitoring_acces = models.CharField(max_length=255, blank=True, null=True)
    # True dès que toutes les pièces OBLIGATOIRES sont présentes (calculé au
    # ré-assemblage) — c'est ce que le gate « Remise au client » exige.
    complet = models.BooleanField(default=False)
    date_generation = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='handover_packs_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pack de remise client'
        verbose_name_plural = 'Packs de remise client'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Pack de remise — chantier {self.installation_id}'


class StockReservation(models.Model):
    """N14 — réservation de stock d'un chantier sur un SKU (produit catalogue).

    À la création d'un chantier, on RÉSERVE auprès du stock les quantités
    requises issues de la nomenclature GELÉE du devis lié (`Installation.bom`),
    une ligne par produit. La réservation ENGAGE le stock sans le décrémenter :
    le « disponible » d'un produit = `quantite_stock` − somme des réservations
    actives non encore consommées (les vues stock + alertes de stock bas en
    tiennent compte). Au passage du chantier à « Installé », la réservation est
    CONSOMMÉE : un seul MouvementStock SORTIE par SKU, idempotent (le drapeau
    `consomme` garantit qu'un re-passage par « Installé » ne re-décrémente
    jamais). À l'annulation/clôture du chantier, la réservation NON consommée
    est LIBÉRÉE (`active=False`) — le disponible revient.

    Entièrement additif ; multi-tenant (société posée côté serveur).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='stock_reservations')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='reservations')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.CASCADE,
        related_name='reservations')
    quantite = models.PositiveIntegerField(default=0)
    # Réservation engagée tant que `active` ET non `consomme` : elle pèse alors
    # sur le « disponible ». Libérée (annulation/clôture) ⇒ active=False.
    active = models.BooleanField(default=True)
    # Consommée au passage « Installé » : le stock A été décrémenté. Le drapeau
    # est le verrou d'idempotence (jamais deux SORTIE pour la même réservation).
    consomme = models.BooleanField(default=False)
    date_consommation = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réservation de stock'
        verbose_name_plural = 'Réservations de stock'
        ordering = ['installation_id', 'id']
        # Une seule réservation par (chantier, produit) — le réamorçage est
        # idempotent (on met à jour la quantité plutôt que d'empiler).
        unique_together = [('installation', 'produit')]
        indexes = [
            models.Index(fields=['produit', 'active', 'consomme']),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.produit_id} × {self.quantite}'


class ChantierChecklistItem(models.Model):
    """N4 — état d'une étape de checklist POUR un chantier donné : fait / par
    qui / quand. Le pourcentage d'avancement du chantier en dérive. Créés
    paresseusement depuis les étapes modèle à la première consultation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='checklist_items')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='checklist')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=0)
    capture_serie = models.BooleanField(default=False)
    # FG76 — copié depuis l'étape modèle ; gate le passage fait=True tant qu'une
    # photo de phase n'est pas disponible (miroir du comportement F8/shot list).
    photo_obligatoire = models.BooleanField(default=False)
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_items_faits')
    fait_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('installation', 'cle')]
        verbose_name = "Étape de checklist (chantier)"
        verbose_name_plural = "Étapes de checklist (chantier)"

    def __str__(self):
        return f"{self.installation_id} · {self.libelle} · {'✓' if self.fait else '—'}"


# ── F7/F8 — Shot list (modèle de prises de vue guidées) ──────────────────────
class ShotListSlot(models.Model):
    """F7/F8 — emplacement (créneau) d'une SHOT LIST de documentation terrain,
    configurable dans Paramètres. Chaque créneau définit une vue attendue lors
    d'une intervention, groupée par PHASE (avant/pendant/après). `obligatoire`
    pilote l'application F8 : une intervention ne peut passer à « Terminée » tant
    qu'un créneau obligatoire n'a pas au moins une photo.

    Les défauts sont semés au standard de documentation d'un chantier solaire.
    `protege` verrouille un créneau système contre la suppression. Additif —
    company-scopé, aucune migration destructive."""

    class Phase(models.TextChoices):
        AVANT = 'avant', 'Avant'
        PENDANT = 'pendant', 'Pendant'
        APRES = 'apres', 'Après'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shotlist_slots')
    cle = models.CharField(max_length=40)
    libelle = models.CharField(max_length=120)
    phase = models.CharField(
        max_length=8, choices=Phase.choices, default=Phase.AVANT)
    # F8 — une photo de ce créneau est requise pour terminer l'intervention.
    obligatoire = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)
    protege = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'libelle']
        unique_together = [('company', 'cle')]
        verbose_name = 'Créneau de shot list'
        verbose_name_plural = 'Créneaux de shot list'

    def __str__(self):
        return f'{self.get_phase_display()} · {self.libelle}'


# ── F5 — Liste de préparation d'une intervention ─────────────────────────────
