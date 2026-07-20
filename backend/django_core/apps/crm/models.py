import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import SoftDeleteModel, TenantModel

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

    # N93 — langue des documents client-facing (facture / devis). Sert à marquer,
    # par client, la langue dans laquelle ses PDF doivent être produits. Le RENDU
    # Arabe du PDF (RTL + police arabe dans le moteur premium) est un chantier de
    # suivi distinct ; ce champ ne fait que porter la préférence. FR par défaut.
    class LangueDocument(models.TextChoices):
        FR = 'fr', 'Français'
        AR = 'ar', 'العربية'

    langue_document = models.CharField(
        max_length=2,
        choices=LangueDocument.choices,
        default=LangueDocument.FR,
        verbose_name='Langue des documents',
        help_text='Langue des factures / devis générés pour ce client.',
    )

    # XSAL1 — Liste de prix négociée (string-FK additive vers
    # ventes.ListePrix — jamais d'import direct de apps.ventes.models ici).
    # Vide = comportement historique inchangé (le client reste au
    # `Produit.prix_vente` standard, résolu par
    # `apps.ventes.services.prix_applicable`).
    liste_prix = models.ForeignKey(
        'ventes.ListePrix',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        verbose_name='Liste de prix',
        help_text="Tarif négocié pour ce client. Vide = prix de vente standard.",
    )

    # XFAC25 — envoi programmé (mensuel) du relevé de compte. Défaut OFF :
    # le relevé reste disponible uniquement à la demande (comportement actuel
    # inchangé). ON + email renseigné + encours non nul → un relevé PDF est
    # envoyé automatiquement le 1er du mois (job beat idempotent, voir
    # apps.ventes.scheduled.releve_mensuel_reminders).
    releve_mensuel_auto = models.BooleanField(
        default=False,
        verbose_name='Envoi mensuel automatique du relevé',
        help_text="Envoie automatiquement le relevé de compte PDF le 1er du "
                  "mois si l'encours n'est pas nul. Désactivé par défaut.",
    )
    # XFAC23 — conditions de paiement négociées par client (délai en jours,
    # ex. 30/60/90 — omniprésent en B2B marocain) + report facultatif en fin
    # de mois. NULL = pas de réglage → comportement actuel inchangé (fallback
    # +30 j dans apps.ventes.scheduled._echeance_effective).
    delai_paiement_jours = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Délai de paiement (jours)',
        help_text='Vide = comportement par défaut (+30 j depuis émission).',
    )
    fin_de_mois = models.BooleanField(
        default=False,
        verbose_name='Échéance reportée en fin de mois',
        help_text=(
            "Si coché, l'échéance calculée depuis le délai est reportée au "
            "dernier jour de son mois (ex. « 60 jours fin de mois »)."
        ),
    )

    # ── XSAL9 — Hiérarchie de comptes (société mère / filiales) ──
    # Self-FK nullable, additif : un groupe (ex. holding agricole à 3 fermes)
    # peut lier ses fiches Client sans fusionner leurs données. `clean()`
    # garde contre un cycle ; la même société uniquement (jamais cross-tenant).
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='filiales',
        verbose_name='Société mère',
        help_text="Rattache ce client à une société mère (consolidation "
                  "CA groupe). Même société uniquement ; jamais de cycle.")

    # ── QX35 — Code de parrainage DÉTERMINISTE (additif) ──
    # Dérivé du pk (ex. « TQ-1042 ») dès la première sauvegarde — jamais un
    # UUID aléatoire : un code stable, lisible, copiable dans un lien
    # `?utm_source=parrainage&utm_campaign=<code>` (parrainage.astro). Unique
    # par construction (dérivé du pk) ; nullable pour les lignes existantes
    # tant qu'elles ne sont pas resauvegardées (comportement inchangé).
    code_parrainage = models.CharField(
        max_length=20, blank=True, null=True, unique=True,
        verbose_name='Code de parrainage',
        help_text="Code stable partagé par ce client pour parrainer un "
                  "prospect (lien /devis/mon-toit?utm_source=parrainage&"
                  "utm_campaign=<code>).",
    )
    # ── ARC18 — Pont additif vers le répertoire unifié Tiers ──
    # FK nullable (string-FK — jamais d'import de apps.tiers.models ici, crm
    # reste découplé de la couche fondation par référence string). L'identité
    # reste MAÎTRE ici ; ``tiers`` n'en est qu'un MIROIR one-way, réversible,
    # posé par le hook de sauvegarde (voir apps/crm/tiers_bridge.py) et
    # backfillé par la commande ``backfill_tiers``. Vide = pas encore relié
    # (comportement API historique strictement inchangé).
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clients',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié des parties prenantes reflétant "
                  "ce client. Renseignée automatiquement (miroir).")
    # ── ZSAL9 — Avertissement de vente (« sale warnings » façon Odoo) ──
    # Message optionnel affiché quand ce client est sélectionné dans le
    # générateur de devis (ex. « client à traiter au comptant »). Si
    # ``avertissement_bloquant`` est True, une garde serveur refuse
    # l'acceptation / la génération de facture d'un devis pour ce client SAUF
    # override responsable/admin journalisé (patron XFAC28). Vide (défaut) =
    # comportement historique strictement inchangé. Jamais de prix d'achat ici.
    avertissement_vente = models.TextField(
        blank=True, default='',
        verbose_name='Avertissement de vente',
        help_text="Message affiché au devis quand ce client est sélectionné.")
    avertissement_bloquant = models.BooleanField(
        default=False,
        verbose_name='Avertissement bloquant',
        help_text="Si activé, empêche l'acceptation/facturation sans override "
                  "responsable/admin.")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        unique_together = [('company', 'email')]

    def __str__(self):
        return f"{self.nom} {self.prenom if self.prenom else ''}"

    def save(self, *args, **kwargs):
        # QX35 — génère le code de parrainage APRÈS la première sauvegarde
        # (a besoin du pk pour rester déterministe et unique sans collision) —
        # patron standard Django « dérivé du pk », deuxième save() ciblé sur
        # le seul champ concerné (jamais de boucle : ne s'exécute qu'une
        # fois, quand code_parrainage est encore vide).
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.code_parrainage:
            self.code_parrainage = f'TQ-{self.pk}'
            # QX35 — écrire via QuerySet.update() plutôt qu'un 2ᵉ save() : un
            # second save() re-déclenche le post_save (le miroir tiers ARC18
            # créerait alors un DOUBLON pour un client sans clé). .update() pose
            # le champ en base sans signal ; l'instance le porte déjà.
            type(self).objects.filter(pk=self.pk).update(
                code_parrainage=self.code_parrainage)

    def clean(self):
        super().clean()
        # XSAL9 — anti-cycle : `parent` ne peut jamais créer une boucle
        # (A→B→A) ni se référencer lui-même, et doit rester dans la MÊME
        # société (jamais de hiérarchie cross-tenant).
        if self.parent_id is None:
            return
        if self.parent_id == self.pk:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {'parent': "Un client ne peut pas être sa propre société mère."})
        if self.company_id and self.parent.company_id != self.company_id:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {'parent': 'La société mère doit appartenir à la même société.'})
        seen = {self.pk} if self.pk else set()
        current = self.parent
        depth = 0
        while current is not None:
            if current.pk in seen or depth > 100:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {'parent': 'Cette hiérarchie créerait un cycle.'})
            seen.add(current.pk)
            current = current.parent
            depth += 1


class Lead(SoftDeleteModel):
    """A sales lead / opportunity — distinct from a Client (customer) record.

    Leads carry a pipeline stage (canonical from STAGES.py) and a source/origin
    so imported test leads are distinguishable from leads created natively in the
    OS. Pipeline stage lives HERE, never on the Client/contact table.

    VX96 — ``Lead`` est le PREMIER adoptant du soft-delete partagé
    (``core.SoftDeleteModel``, FG388). La suppression n'est plus définitive :
    ``LeadViewSet.destroy()`` appelle ``lead.soft_delete(user)``, qui masque le
    lead des querysets par défaut (``Lead.objects`` = vivants) et journalise une
    entrée de corbeille (``DeletionRecord``) restaurable pendant 30 min via le
    ``TrashViewSet`` (``/core/corbeille/``). ``Lead.all_objects`` atteint aussi
    les supprimés. (On ne construit AUCUN écran corbeille ici — NTUX7.)
    """

    class Source(models.TextChoices):
        OS_NATIVE = 'os_native', 'Créé dans TAQINOR'
        ODOO_IMPORT_TEST = 'odoo_import_test', 'Import test Odoo'
        SITE_WEB = 'site_web', 'Site web'
        # XMKT32 — lead créé depuis un formulaire Meta Lead Ads (Facebook/
        # Instagram), via l'API officielle (jamais de scraping).
        META_LEAD_ADS = 'meta_lead_ads', 'Meta Lead Ads'

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

    # QW2 — Mode PROFESSIONNEL du site (WJ68) : type de site + nombre de sites.
    # Vocabulaire identique à `apps/web/src/lib/lead.ts` (FACILITY_TYPES /
    # SITE_COUNTS) — additifs, optionnels, jamais redemandés au commercial.
    class FacilityType(models.TextChoices):
        BUREAU = 'bureau', 'Bureau'
        ENTREPOT = 'entrepot', 'Entrepôt'
        USINE = 'usine', 'Usine'
        COMMERCE = 'commerce', 'Commerce'
        AGRICOLE = 'agricole', 'Agricole'
        AUTRE = 'autre', 'Autre'

    class SiteCount(models.TextChoices):
        UN = '1', '1 site'
        DEUX_A_CINQ = '2-5', '2 à 5 sites'
        SIX_PLUS = '6+', '6 sites ou plus'

    # QW2 — Créneau de visite technique préféré (W353), STATIQUE — jamais une
    # réservation confirmée (le RDV réel reste QJ20 Appointment).
    class VisitWindowPart(models.TextChoices):
        MATIN = 'matin', 'Matin'
        APRES_MIDI = 'apres_midi', 'Après-midi'

    class VisitWindowWeek(models.TextChoices):
        CETTE_SEMAINE = 'cette_semaine', 'Cette semaine'
        SEMAINE_PROCHAINE = 'semaine_prochaine', 'Semaine prochaine'

    # QW3 — Préférence de contact EXPLICITE du prospect (lead.ts
    # CONTACT_PREFERENCES), DISTINCTE de `whatsapp_opt_in` (consentement
    # marketing WhatsApp) et de `Canal` (canal marketing d'ORIGINE) : ceci est
    # « comment voulez-vous qu'on vous recontacte », une question posée UNE
    # FOIS au client, jamais déduite ni écrasée par le canal marketing.
    class ContactPreference(models.TextChoices):
        WHATSAPP_ONLY = 'whatsapp_only', 'WhatsApp uniquement'
        PHONE_OK = 'phone_ok', 'Rappel téléphonique OK'

    # Langue préférée du contact pour les messages (ex. WhatsApp). Nullable :
    # tant qu'elle n'est pas renseignée, le message retombe sur le FR. Les clés
    # sont identiques à celles attendues par le constructeur WhatsApp
    # (apps.ventes.utils.whatsapp : langue ∈ {'fr','darija'}).
    class LanguePreferee(models.TextChoices):
        FR = 'fr', 'Français'
        DARIJA = 'darija', 'Darija'

    # ── QK1 — Qualification captée par le site (tous additifs, optionnels) ──
    # Distributeur d'électricité du prospect (détermine la tranche tarifaire).
    class Distributeur(models.TextChoices):
        ONEE = 'onee', 'ONEE'
        LYDEC = 'lydec', 'Lydec'
        REDAL = 'redal', 'Redal'
        AUTRE = 'autre', 'Autre'

    # Statut d'occupation du bâtiment (un locataire ne décide pas des travaux).
    class Ownership(models.TextChoices):
        PROPRIETAIRE = 'proprietaire', 'Propriétaire'
        LOCATAIRE = 'locataire', 'Locataire'
        AUTRE = 'autre', 'Autre'

    # Horizon du projet déclaré par le prospect.
    class ProjectTimeline(models.TextChoices):
        IMMEDIAT = 'immediat', 'Dès que possible'
        MOINS_3_MOIS = '3_mois', 'Moins de 3 mois'
        MOINS_6_MOIS = '6_mois', '3 à 6 mois'
        PLUS_TARD = 'plus_tard', 'Plus tard / je me renseigne'

    # Intention de financement déclarée.
    class FinancingIntent(models.TextChoices):
        CASH = 'cash', 'Comptant'
        CREDIT = 'credit', 'Crédit / financement'
        INDECIS = 'indecis', 'Pas encore décidé'

    # Charges futures prévues (clés autorisées de `futures_charges`).
    FUTURES_CHARGES_KEYS = ('clim', 've', 'pompe')

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

    # ── ARC56 — Pont additif vers le répertoire unifié Tiers (stade amont) ──
    # FK nullable (string-FK ``'tiers.Tiers'``) : le lead porte l'identité
    # PRÉ-CONVERSION (avant qu'un Client structuré existe), donc le recoupement
    # « qui est ce tiers ? » (ARC20) doit aussi couvrir ce stade. Rattaché au
    # MÊME Tiers que le Client résolu (via resolve_client_for_lead + le miroir
    # crm.Client → Tiers d'ARC18) ; jamais un 2ᵉ Tiers pour le même acteur.
    # ATTENTION QW7 : ce pont ne touche AUCUN champ de nom du lead.
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié reflétant ce prospect "
                  "(stade amont). Renseignée automatiquement (miroir).")

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

    # ── XSAL7 — Pipeline pondéré PRÉ-devis (additif, nullable) ──
    # Un lead chaud SANS devis pèse zéro dans le forecast pipeline
    # aujourd'hui ; ces deux champs, saisis librement en amont d'un devis,
    # lui donnent un poids (montant_estime × win_probability, voir
    # apps/reporting/pipeline.py) UNIQUEMENT quand le lead n'a aucun devis
    # actif (jamais de double comptage avec la valeur du devis).
    montant_estime = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant estimé (MAD)',
        help_text="Estimation libre du commercial avant devis — contribue "
                  "au forecast pondéré tant qu'aucun devis actif n'existe.")
    date_cloture_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date de clôture prévue')

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
    # QW3 — préférence de contact EXPLICITE, distincte de `whatsapp_opt_in`
    # (consentement marketing) et de `canal` (canal marketing d'origine).
    # NULL = non renseignée (comportement historique inchangé).
    contact_preference = models.CharField(
        max_length=16, choices=ContactPreference.choices, blank=True, null=True,
        verbose_name='Préférence de contact')
    # QX15 — horodatage de la POSE de `contact_preference` (distinct de
    # `date_creation` du lead). Le SLA rappel doit mesurer depuis QUAND le
    # rappel a été demandé, pas depuis quand le lead a été créé — un vieux
    # lead dont la préférence est posée MAINTENANT ne doit pas apparaître
    # instantanément « SLA rompu ». NULL = jamais posé (ou posé avant ce
    # champ) ; le sélecteur retombe sur `date_creation` dans ce cas
    # (comportement historique inchangé pour les leads déjà en base).
    contact_preference_set_at = models.DateTimeField(null=True, blank=True)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    # Attribution publicitaire (capture first-touch du site)
    fbclid = models.CharField(max_length=500, blank=True, null=True)
    utm_source = models.CharField(max_length=300, blank=True, null=True)
    utm_medium = models.CharField(max_length=300, blank=True, null=True)
    utm_campaign = models.CharField(max_length=300, blank=True, null=True)
    utm_content = models.CharField(max_length=300, blank=True, null=True)
    utm_term = models.CharField(max_length=300, blank=True, null=True)

    # ── ADSENG1 — Identifiants Meta natifs des leads Lead Ads (additifs,
    # nullable). Meta ne pousse JAMAIS campaign_name/adset_name dans le webhook
    # leadgen ; il pousse ad_id/adgroup_id/form_id (+ leadgen_id). On les
    # capture ici comme CLÉS DE JOINTURE STABLES vers les miroirs adsengine
    # (AdMirror.meta_id / AdSetMirror.meta_id / AdCampaignMirror.meta_id), là où
    # les utm_* (chaînes saisies) ne sont bons que pour l'affichage. Vides pour
    # tout lead non-Meta (site/appel/DM). L'attribution PAR VARIANTE (ADSENG6)
    # joint sur meta_ad_id.
    meta_ad_id = models.CharField(max_length=64, blank=True, null=True)
    meta_adset_id = models.CharField(max_length=64, blank=True, null=True)
    meta_campaign_id = models.CharField(max_length=64, blank=True, null=True)
    meta_form_id = models.CharField(max_length=64, blank=True, null=True)

    # ── QK1 — Qualification captée par le site (additifs, nullable) ──
    # Le site collecte ces signaux au moment de la capture ; ils ne doivent
    # jamais être re-demandés au prospect par le commercial.
    distributeur = models.CharField(
        max_length=12, choices=Distributeur.choices, blank=True, null=True,
        verbose_name="Distributeur d'électricité")
    # Âge de la toiture en années (numérique simple ; NULL = inconnu).
    roof_age = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Âge de la toiture (ans)')
    ownership = models.CharField(
        max_length=12, choices=Ownership.choices, blank=True, null=True,
        verbose_name="Statut d'occupation")
    project_timeline = models.CharField(
        max_length=12, choices=ProjectTimeline.choices, blank=True, null=True,
        verbose_name='Horizon du projet')
    financing_intent = models.CharField(
        max_length=12, choices=FinancingIntent.choices, blank=True, null=True,
        verbose_name='Financement envisagé')
    # Charges futures prévues — liste de clés parmi FUTURES_CHARGES_KEYS
    # (clim / véhicule électrique / pompe). NULL = non renseigné.
    futures_charges = models.JSONField(
        null=True, blank=True,
        verbose_name='Charges futures prévues',
        help_text="Liste parmi 'clim', 've', 'pompe'.")

    # ── QW2 — Champs du site sans colonne d'accueil (additifs, nullable) ──
    # NOTE : `raisonSociale` du site RÉUTILISE `societe` (models.py ci-dessus)
    # — pas de colonne dédiée (consigne founder explicite).
    facility_type = models.CharField(
        max_length=12, choices=FacilityType.choices, blank=True, null=True,
        verbose_name='Type de site (pro)')
    site_count = models.CharField(
        max_length=4, choices=SiteCount.choices, blank=True, null=True,
        verbose_name='Nombre de sites (pro)')
    # Créneau de visite technique PRÉFÉRÉ (statique, jamais un RDV confirmé —
    # le rendez-vous réel reste QJ20 Appointment).
    visit_window_part = models.CharField(
        max_length=12, choices=VisitWindowPart.choices, blank=True, null=True,
        verbose_name='Créneau de visite préféré')
    visit_window_week = models.CharField(
        max_length=20, choices=VisitWindowWeek.choices, blank=True, null=True,
        verbose_name='Semaine de visite préférée')
    # Référence courte générée CÔTÉ CLIENT (aucune garantie d'unicité globale —
    # sert de corrélation best-effort avec une conversation WhatsApp/support,
    # jamais une clé d'unicité serveur).
    client_ref = models.CharField(
        max_length=24, blank=True, null=True,
        verbose_name='Référence client (générée navigateur)')
    # Diaspora/MRE : `phoneE164` étranger (indicatif ≠ 212) — une motion
    # commerciale distincte, badge-worthy (jamais utilisé pour qualifiesForCrm).
    phone_is_foreign = models.BooleanField(
        null=True, blank=True, verbose_name='Numéro étranger (diaspora/MRE)')
    # Première page de landing vue (first-touch) — protégé comme l'UTM :
    # jamais écrasé sur un visiteur revenant (voir `_FIRST_TOUCH_FIELDS`,
    # apps/crm/webhooks.py).
    page = models.CharField(
        max_length=300, blank=True, null=True,
        verbose_name='Page de landing (first-touch)')

    # ── Questionnaire quote-journey du site (pro/agricole) — additif ──
    # Réponses de dimensionnement SANS colonne d'accueil, clés snake_case
    # alignées sur le vocabulaire etude_params du générateur (water_source,
    # irrigation, besoin_m3j, tension_raccordement, puissance_kva…). Les
    # réponses qui ONT déjà une colonne (HMT/débit/CV pompe → pompe_*,
    # kWh/MAD pro → bill_kwh/facture_hiver) sont mappées sur ces colonnes
    # par le webhook (apps/crm/webhooks.py) et ne sont PAS dupliquées ici.
    web_questionnaire = models.JSONField(
        default=dict, blank=True,
        verbose_name='Questionnaire web (quote-journey)')
    # Chiffres MONTRÉS au visiteur au moment de la capture (kwc, prodKwh,
    # ecoMad*, paybackLabel, pompeCv, champKwc, m3Jour…) — snapshot verbatim
    # re-whitelisté CÔTÉ SERVEUR (webhooks._clean_estimate_shown), jamais
    # recalculé : c'est la promesse vue par le prospect, pas une étude.
    web_estimate = models.JSONField(
        default=dict, blank=True,
        verbose_name='Estimation montrée (web)')

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

    # VX98 — dernier auteur d'une modification (posé server-side dans
    # perform_update, jamais accepté du corps de requête). Alimente la puce de
    # fraîcheur « modifié par X il y a N min » (silencieuse si NULL ou si c'est
    # l'utilisateur courant). Pattern identique à archived_by ; date_modification
    # (auto_now) porte l'horodatage.
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads_modifies',
    )

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

    # XMKT21 — horodatage de l'assignation automatique MQL (franchissement du
    # seuil de score société). NULL tant que le lead n'a jamais franchi le
    # seuil : marqueur d'idempotence (une seule assignation+notification par
    # lead), jamais réinitialisé si le score redescend puis remonte.
    mql_assigned_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Assigné MQL le',
        help_text='Horodatage de la première assignation automatique '
                  'déclenchée par le franchissement du seuil MQL (XMKT21).',
    )

    # ── QW10 — Colonnes de dédup NORMALISÉES + indexées (additif) ──
    # `find_duplicates_by_contact` itérait TOUS les leads d'une société en
    # Python à chaque webhook (O(N), cible d'amplification sur un endpoint à
    # secret statique). Ces colonnes sont maintenues en écriture (voir
    # `save()`) à partir des mêmes normaliseurs (`services.normalize_phone` /
    # `normalize_email`) : la recherche devient une requête indexée, pas un
    # scan. Vide ('') plutôt que NULL pour rester indexable simplement (une
    # valeur vide n'est jamais un doublon — filtrée côté requête).
    phone_normalise = models.CharField(
        max_length=20, blank=True, default='', db_index=True,
        verbose_name='Téléphone normalisé (dédup)')
    email_normalise = models.CharField(
        max_length=254, blank=True, default='', db_index=True,
        verbose_name='Email normalisé (dédup)')

    def save(self, *args, **kwargs):
        # QW10 — maintient les colonnes de dédup normalisées à chaque save,
        # quelle que soit la voie d'écriture (webhook, admin, API, import) —
        # source unique de vérité : `apps.crm.services` (jamais dupliquée ici).
        from . import services as _crm_services
        self.phone_normalise = _crm_services.normalize_phone(self.telephone) or ''
        self.email_normalise = _crm_services.normalize_email(self.email) or ''
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['company', 'source']),
            models.Index(fields=['company', 'stage']),
            models.Index(fields=['company', 'score'], name='crm_lead_company_score_idx'),
            # QW10 — dédup indexée (téléphone/email normalisés), remplace le
            # scan Python complet de `find_duplicates_by_contact`.
            models.Index(fields=['company', 'phone_normalise'],
                         name='crm_lead_phone_norm_idx'),
            models.Index(fields=['company', 'email_normalise'],
                         name='crm_lead_email_norm_idx'),
            # ADSENG1/ADSENG6 — jointure d'attribution PAR VARIANTE : on
            # regroupe les leads d'une société par leur ad Meta (meta_ad_id).
            models.Index(fields=['company', 'meta_ad_id'],
                         name='crm_lead_meta_ad_idx'),
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
    # VX111 — pièce jointe optionnelle sur une note manuelle (kind='note'),
    # ex. photo prise depuis mobile pendant une visite. RÉUTILISE le magasin
    # `records.Attachment` existant (déjà whitelisté ('crm','lead')) — jamais
    # un second magasin de fichiers. SET_NULL : la note reste lisible même si
    # la pièce jointe est supprimée indépendamment (ex. depuis AttachmentsPanel).
    attachment = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lead_notes',
        verbose_name='Pièce jointe',
    )
    # Marque une entrée issue d'une action « en masse » (édition groupée de
    # plusieurs leads) — l'Historique l'affiche avec un badge « en masse ».
    bulk = models.BooleanField(default=False)
    # LW28 — note épinglée : mise en avant hors chronologie en tête de
    # l'Historique (`historique/` trie `(-pinned, -created_at)`). Additif,
    # défaut False → comportement historique strictement inchangé.
    pinned = models.BooleanField(default=False, verbose_name='Épinglée')
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
    un texte libre ; cette liste sert de choix proposés. Additif.

    PUB28 — ``est_junk`` distingue un motif de perte JUNK (numéro invalide,
    spam/bot, hors zone, jamais répondu — le lead n'était jamais un prospect
    réel) d'un motif RÉEL (prix, concurrent, reporté — un vrai prospect perdu
    pour une raison commerciale). Sert le signal qualité manquant au veto de
    divergence : le taux de junk PAR AD (``apps.adsengine.attribution``)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='motifs_perte')
    nom = models.CharField(max_length=150)
    archived = models.BooleanField(default=False)
    est_junk = models.BooleanField(
        default=False, verbose_name='Motif junk (pas un vrai prospect)',
        help_text='Numéro invalide, spam/bot, hors zone, jamais répondu — '
                  'distinct d\'un motif de perte commercial réel.')

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

    def render(self, prenom='', ville='', lien='', lien_rdv='') -> str:
        """Substitue les variables dans le corps du modèle.

        XSAL17 — ``lien_rdv`` (lien de réservation de visite) est résolu par
        l'APPELANT (``services.resoudre_lien_rdv`` — nécessite le lead pour
        créer/retrouver le ``BookingLink``) ; ce modèle reste une simple
        substitution de chaîne. Un template SANS ``{lien_rdv}`` est rendu
        strictement inchangé (aucun paramètre supplémentaire n'y change rien)."""
        return (self.corps
                .replace('{prenom}', prenom or '')
                .replace('{ville}', ville or '')
                .replace('{lien}', lien or '')
                .replace('{lien_rdv}', lien_rdv or ''))


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

    @property
    def filleul_display_nom(self) -> str:
        """DC14 — nom du filleul affiché, le FK étant la source prioritaire.

        ``filleul_nom`` (texte libre) peut diverger du FK lié. Quand un
        ``filleul_client`` ou ``filleul_lead`` est présent, on affiche SON nom
        (source de vérité) ; sinon on retombe sur le texte libre saisi.
        """
        if self.filleul_client_id and self.filleul_client:
            return self.filleul_client.nom
        if self.filleul_lead_id and self.filleul_lead:
            return self.filleul_lead.nom
        return self.filleul_nom or ''


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
        # PUB37 — additif, DISTINCT d'ANNULE : le prospect ne s'est jamais
        # présenté (vs un RDV annulé À L'AVANCE). Une annonce qui génère des
        # RDV fantômes coûte cher avant que le coût-par-signature ne le
        # montre — signal qualité intermédiaire par variante (adsengine).
        NO_SHOW = 'no_show', 'Absent (no-show)'

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


class SiteProfile(models.Model):
    """DC12 — profil site/énergie RÉUTILISABLE, attaché au client.

    Aujourd'hui le profil énergétique et toiture est re-saisi à chaque devis
    (surtout pour les devis SANS lead, qui n'ont nulle part où puiser ces
    valeurs). Ce modèle est la SOURCE UNIQUE par client : saisi une fois, le
    générateur de devis le pré-remplit ensuite (consommé via
    ``selectors.site_profile_for_client``).

    Les taxonomies (raccordement, type de toiture, orientation, ombrage…) sont
    RÉUTILISÉES depuis ``Lead`` — jamais redéclarées ici — pour éviter une
    seconde liste de choix divergente. Borné société ; un seul profil par
    client (OneToOne). Tous les champs sont optionnels et additifs.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='site_profiles',
    )
    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='site_profile',
        verbose_name='Client',
    )

    # ── Profil énergétique (mêmes champs que Lead) ──
    facture_hiver = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    facture_ete = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    ete_differente = models.BooleanField(default=False)
    conso_mensuelle_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    tranche_onee = models.CharField(max_length=100, blank=True, null=True)
    raccordement = models.CharField(
        max_length=12, choices=Lead.Raccordement.choices,
        blank=True, null=True)
    regularisation_8221 = models.BooleanField(default=False)
    type_installation = models.CharField(
        max_length=20, choices=Lead.TypeInstallation.choices,
        blank=True, null=True)

    # ── Pompage solaire (clients Agricole) ──
    pompe_cv = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    pompe_hmt_m = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)
    pompe_debit_m3h = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)

    # ── Toiture & site ──
    type_toiture = models.CharField(
        max_length=20, choices=Lead.TypeToiture.choices,
        blank=True, null=True)
    surface_toiture_m2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    orientation = models.CharField(
        max_length=12, choices=Lead.Orientation.choices,
        blank=True, null=True)
    inclinaison_deg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    ombrage = models.CharField(
        max_length=12, choices=Lead.Ombrage.choices, blank=True, null=True)
    ombrage_notes = models.TextField(blank=True, null=True)

    # ── Localisation du site (pour devis sans lead) ──
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])

    # Traçabilité (forcée côté serveur).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil site'
        verbose_name_plural = 'Profils site'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Profil site (client {self.client_id})'


def _default_chat_token():
    return uuid.uuid4().hex


class ChatSessionPublique(models.Model):
    """XMKT37 — Session de livechat d'un VISITEUR anonyme du site public.

    Même modèle de confiance que le webhook ``webhooks/website-leads/`` :
    la ``company`` est résolue CÔTÉ SERVEUR (le token identifie la SESSION,
    jamais la société — la société est posée à la création, jamais reçue du
    corps de requête). Le transcript est un JSON horodaté ; aucune donnée
    interne (prix_achat/marges) n'y transite jamais — la réponse IA passe
    par ``core.ai`` dont le prompt XMKT37 exclut ce type de donnée par
    construction (aucun accès aux modèles métier).
    """

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        QUALIFIEE = 'qualifiee', 'Qualifiée'
        FERMEE = 'fermee', 'Fermée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='chat_sessions_publiques')
    token = models.CharField(
        max_length=64, unique=True, default=_default_chat_token,
        editable=False)
    # Transcript horodaté : liste de {auteur: 'visiteur'|'assistant'|'system',
    # texte: str, date: iso8601}. Jamais de champ interne (prix_achat/marge).
    transcript = models.JSONField(default=list, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE)
    # Lead créé dès que nom + téléphone/email sont capturés (XMKT37).
    lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chat_sessions_publiques')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Session livechat publique'
        verbose_name_plural = 'Sessions livechat publiques'
        ordering = ['-last_message_at']

    def __str__(self):
        return f'Session livechat #{self.pk} ({self.statut})'


class PlanActivite(models.Model):
    """ZSAL2 — Plan d'activité (Odoo « Activity Plans ») : séquence de tâches
    pré-définies applicable à un lead d'un clic (ex. « Nouveau lead solaire »
    = J0 appeler, J1 email étude, J3 visite technique, J7 relance devis).

    Distinct des séquences marketing XMKT (email/SMS automatisés côté
    marketing) : ceci est une CHECKLIST d'activités internes du commercial,
    matérialisée en ``records.Activity`` sur le lead cible.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='plans_activite')
    nom = models.CharField(max_length=120)
    actif = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan d'activité"
        verbose_name_plural = "Plans d'activité"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class EtapePlanActivite(models.Model):
    """ZSAL2 — Une étape d'un :class:`PlanActivite` : un type d'activité à
    créer, ``delai_jours`` après la date d'application du plan (0 = le jour
    même), avec un résumé par défaut et un assigné par défaut optionnel
    (owner du lead si vide, sinon un utilisateur fixe)."""
    plan = models.ForeignKey(
        PlanActivite, on_delete=models.CASCADE, related_name='etapes')
    ordre = models.PositiveIntegerField(default=0)
    activity_type = models.ForeignKey(
        'records.ActivityType', on_delete=models.PROTECT,
        related_name='etapes_plan_activite')
    delai_jours = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de jours après l'application du plan (0 = le jour même).")
    resume_defaut = models.CharField(max_length=255, blank=True, default='')
    # NULL = assigné par défaut = owner du lead ciblé (résolu à l'application).
    assigne_par_defaut = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapes_plan_activite_assignees')

    class Meta:
        verbose_name = "Étape de plan d'activité"
        verbose_name_plural = "Étapes de plan d'activité"
        ordering = ['plan', 'ordre', 'delai_jours']

    def __str__(self):
        return f'{self.plan.nom} — J{self.delai_jours} {self.resume_defaut}'.strip()


class EquipeCommerciale(models.Model):
    """ZSAL3 — Équipe commerciale (Odoo « Sales Teams / My Teams »).

    PAS un pipeline/étapes propre à l'équipe (règle #2 — STAGES.py reste
    l'unique source des étapes) : juste un regroupement de commerciaux pour
    agréger un tableau de bord d'équipe (pipeline ouvert, valeur pondérée,
    activités en retard, avancement vs objectif). ``responsable`` est le
    manager d'équipe (peut ne pas être membre lui-même) ; ``membres`` est un
    M2M additif — n'importe quel utilisateur peut appartenir à 0 ou 1+ équipe
    (comportement historique inchangé : un commercial sans équipe reste visible
    partout ailleurs, seul le dashboard « Mes équipes » l'ignore).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='equipes_commerciales')
    nom = models.CharField(max_length=120)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='equipes_dirigees')
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='equipes_commerciales')
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Équipe commerciale'
        verbose_name_plural = 'Équipes commerciales'
        ordering = ['nom']

    def __str__(self):
        return self.nom


# XSAL17 — Lien de réservation de RDV, tokenisé par lead + expirant.
# Même patron que ``ventes.ShareLink`` (jeton long/imprévisible, expiration
# par défaut), gardé DANS crm (pas d'import de ventes.models) : le placeholder
# {lien_rdv} des messages/templates CRM résout vers un lien de CE type,
# jamais vers un ShareLink devis/facture (domaines distincts).
BOOKING_LINK_TTL_DAYS = 14


def _default_booking_token():
    import secrets
    return secrets.token_urlsafe(32)


def _default_booking_expiry():
    from datetime import timedelta

    from django.utils import timezone as _timezone
    return _timezone.now() + timedelta(days=BOOKING_LINK_TTL_DAYS)


class BookingLink(models.Model):
    """XSAL17 — Lien PUBLIC, tokenisé et expirant (14 j), permettant à un
    prospect de réserver un créneau de visite rattaché à SON lead sans
    login. Résolu au moment de l'ENVOI d'un message contenant le placeholder
    ``{lien_rdv}`` (voir ``services.resoudre_lien_rdv``) — jamais généré à
    l'avance/en masse. Une réservation via ce lien crée un ``Appointment``
    via le service ``book_appointment`` existant (même logique métier que la
    création interne)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='booking_links')
    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.CASCADE, related_name='booking_links')
    token = models.CharField(
        max_length=64, unique=True, default=_default_booking_token,
        editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_booking_expiry)
    # Posé dès qu'un Appointment a été créé via ce lien — un lien déjà
    # utilisé reste résolvable (affiche « déjà réservé ») mais ne recrée
    # jamais un second rendez-vous (idempotence).
    used_at = models.DateTimeField(null=True, blank=True)
    appointment = models.ForeignKey(
        'crm.Appointment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='booking_link_origine')

    class Meta:
        verbose_name = 'Lien de réservation RDV'
        verbose_name_plural = 'Liens de réservation RDV'
        ordering = ['-created_at']

    def __str__(self):
        return f'BookingLink lead#{self.lead_id} ({self.token[:8]}…)'

    @property
    def is_expired(self):
        from django.utils import timezone as _timezone
        return _timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None


# ── FG234–237 — Partenaires & territoires commerciaux (ODX13, rapatriés de
# compta : leur foyer Odoo naturel CRM/resellers) ──────────────────────────
# ``db_table`` figé sur le nom historique (``compta_<model>``) — SORTIE
# state-only de compta (migration ``crm.0059_odx13_partenaires_split`` +
# ``compta.0109_odx13_partenaires_split``), aucune donnée déplacée. Les
# anciennes routes ``/api/django/compta/…`` restent servies à l'identique
# (les ViewSets/serializers restent physiquement dans l'app compta — voir
# ``apps/crm/views.py``/``apps/crm/serializers.py`` pour le ré-export
# transitoire des nouvelles routes ``/api/django/crm/…``).

class Partenaire(models.Model):
    """Partenaire commercial : apporteur d'affaires ou sous-revendeur (FG234).

    Fiche minimale ici (compte + accès tokenisé + taux de commission). FG237
    enrichit la fiche (statut d'agrément, zone, onboarding). Un partenaire
    soumet des leads via le portail (``SoumissionLeadPartenaire``) et suit leur
    statut. Scopé société ; le token d'accès est posé côté serveur.
    """
    class Type(models.TextChoices):
        APPORTEUR = 'apporteur', "Apporteur d'affaires"
        SOUS_REVENDEUR = 'sous_revendeur', 'Sous-revendeur'
        INSTALLATEUR = 'installateur', 'Installateur'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='partenaires',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom / raison sociale')
    type_partenaire = models.CharField(
        max_length=16, choices=Type.choices, default=Type.APPORTEUR,
        verbose_name='Type de partenaire')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    taux_commission = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)')
    token_acces = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="Token d'accès")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # FG237 — Annuaire & onboarding installateurs partenaires.
    statut_onboarding = models.CharField(
        max_length=12,
        choices=[
            ('prospect', 'Prospect'),
            ('en_cours', "En cours d'agrément"),
            ('agree', 'Agréé (activé)'),
            ('suspendu', 'Suspendu'),
        ],
        default='prospect',
        verbose_name="Statut d'onboarding")
    numero_agrement = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name="Numéro d'agrément")
    zone = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Zone géographique')
    date_activation = models.DateField(
        null=True, blank=True, verbose_name="Date d'activation")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    # ── ARC19 — Pont additif vers le répertoire unifié Tiers ──
    # FK nullable (string-FK ``'tiers.Tiers'`` — jamais d'import de
    # apps.tiers.models ici). L'identité reste MAÎTRE côté Partenaire ; ``tiers``
    # n'en est qu'un MIROIR one-way réversible, posé par le hook de sauvegarde
    # (apps/compta/tiers_bridge.py, sender re-pointé sur ``crm.Partenaire`` par
    # ODX13) et backfillé par ``backfill_tiers`` (source re-pointée pareil).
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='partenaires',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié des parties prenantes reflétant "
                  "ce partenaire. Renseignée automatiquement (miroir).")

    class Meta:
        verbose_name = 'Partenaire commercial'
        verbose_name_plural = 'Partenaires commerciaux'
        db_table = 'compta_partenaire'
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.get_type_partenaire_display()})'


class SoumissionLeadPartenaire(models.Model):
    """Lead soumis par un partenaire via le portail (FG234).

    Le partenaire renseigne les coordonnées d'un prospect ; on enregistre la
    soumission scopée société. Après qualification, le lead réel est créé dans
    ``crm`` (via son service, jamais importé ici) et référencé par ``lead_id``.
    Le partenaire suit le statut de sa soumission.
    """
    class Statut(models.TextChoices):
        SOUMIS = 'soumis', 'Soumis'
        QUALIFIE = 'qualifie', 'Qualifié'
        CONVERTI = 'converti', 'Converti'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='soumissions_lead_partenaire',
        verbose_name='Société',
    )
    partenaire = models.ForeignKey(
        Partenaire,
        on_delete=models.CASCADE,
        related_name='soumissions',
        verbose_name='Partenaire',
    )
    nom_prospect = models.CharField(
        max_length=200, verbose_name='Nom du prospect')
    telephone_prospect = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Téléphone du prospect')
    email_prospect = models.EmailField(
        blank=True, default='', verbose_name='Email du prospect')
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.SOUMIS,
        verbose_name='Statut')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead créé')
    date_soumission = models.DateTimeField(
        auto_now_add=True, verbose_name='Soumis le')

    class Meta:
        verbose_name = 'Soumission de lead (partenaire)'
        verbose_name_plural = 'Soumissions de lead (partenaire)'
        db_table = 'compta_soumissionleadpartenaire'
        ordering = ['-date_soumission']

    def __str__(self):
        return f'{self.nom_prospect} — {self.partenaire.nom}'


# ── FG235 — Suivi des commissions partenaires ──────────────────────────────

class CommissionPartenaire(models.Model):
    """Commission due à un partenaire sur un devis signé/lead converti (FG235).

    Calculée sur une base HT × taux (%). Le devis est référencé par id
    (cross-app — jamais d'import ventes). Statut de règlement (due → payée). Le
    relevé par partenaire s'obtient en agrégeant ces lignes (action ``releve``).
    Scopée société.
    """
    class Statut(models.TextChoices):
        DUE = 'due', 'Due'
        PAYEE = 'payee', 'Payée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='commissions_partenaire',
        verbose_name='Société',
    )
    partenaire = models.ForeignKey(
        Partenaire,
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name='Partenaire',
    )
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du devis signé')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead')
    base_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Base HT (MAD)')
    taux = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant de commission (MAD)')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.DUE,
        verbose_name='Statut')
    paye_le = models.DateField(
        null=True, blank=True, verbose_name='Payée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Commission partenaire'
        verbose_name_plural = 'Commissions partenaire'
        db_table = 'compta_commissionpartenaire'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Commission {self.montant} — {self.partenaire.nom}'


# ── FG236 — Gestion des territoires / zones commerciales ───────────────────

class TerritoireCommercial(models.Model):
    """Zone commerciale : découpage géographique + affectation auto (FG236).

    Un territoire regroupe des villes/régions (liste de mots-clés en minuscules)
    et un commercial responsable (par id — ``owner_user_id``, jamais un import
    hors foundation). Le service ``affecter_territoire`` associe un lead à la
    zone qui matche sa ville, en respectant la priorité (plus haute d'abord).
    Scopé société.

    WIR81 — RELATION AVEC ``apps.territoires.Territoire`` (NTCRM1/2). Ces deux
    modèles « territoire » résolvent le même besoin sans référence croisée.
    Le moteur CANONIQUE d'assignation des leads est
    ``apps.territoires.Territoire`` : c'est LUI que
    ``crm.services.default_responsable_for`` consulte en premier (via
    ``territoires.services.resoudre_owner_pour_attrs``). ``TerritoireCommercial``
    est le référentiel LEGACY (FG236), conservé (jamais supprimé) car NTDST11
    prévoit une FK vers lui ; son ViewSet est exposé sous l'UNIQUE préfixe
    ``/api/django/compta/territoires-commerciaux/`` (le double montage ODX13 a
    été retiré ; le retrait complet ODX22 reste futur).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='territoires_commerciaux',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom du territoire')
    villes = models.JSONField(
        default=list, blank=True,
        verbose_name='Villes / régions (liste)')
    owner_user_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Commercial responsable (id)')
    priorite = models.IntegerField(
        default=0, verbose_name='Priorité (haute = prioritaire)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Territoire commercial'
        verbose_name_plural = 'Territoires commerciaux'
        db_table = 'compta_territoirecommercial'
        ordering = ['-priorite', 'nom']

    def __str__(self):
        return self.nom

    def matche_ville(self, ville):
        """True si ``ville`` correspond à l'une des villes/régions du zonage."""
        if not ville:
            return False
        cible = str(ville).strip().lower()
        for v in (self.villes or []):
            mot = str(v).strip().lower()
            if mot and (mot == cible or mot in cible or cible in mot):
                return True
        return False


class LeadActivityArchive(models.Model):
    """YOPSB11 — copie FROIDE d'une ``LeadActivity`` archivée.

    Table append-only à forte croissance (le chatter grossit sans borne) : la
    politique de rétention YOPSB11 déplace les lignes anciennes ici puis les
    supprime de la table vive. Schéma miroir SANS index chaud : les FK sont
    DÉNORMALISÉES en identifiants entiers (``company_id``/``lead_id``/…) — une
    archive ne doit dépendre du cycle de vie d'aucune table vive (pas de
    cascade si le lead/l'utilisateur est supprimé plus tard). Les comptages
    agrégés par société survivent via la colonne ``company_id`` conservée."""

    original_id = models.BigIntegerField(
        help_text="PK de la LeadActivity d'origine (table vive).")
    company_id = models.BigIntegerField(null=True, blank=True)
    lead_id = models.BigIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=15)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    outcome = models.CharField(max_length=20, blank=True, default='')
    attachment_id = models.BigIntegerField(null=True, blank=True)
    bulk = models.BooleanField(default=False)
    user_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité lead (archive)'
        verbose_name_plural = 'Activités lead (archive)'

    def __str__(self):
        return f'archive:{self.original_id}'


# ── NTCRM4 — Catégories de forecast (commit/best-case/pipeline/omis) ─────────
class ForecastEntry(TenantModel):
    """Catégorisation forecast d'UN lead, liée 1-1 pour ne pas alourdir
    ``Lead``. Un lead SANS ``ForecastEntry`` explicite est classé PIPELINE par
    défaut (voir ``montant_effectif``/le sélecteur ``forecast_rollup`` — aucune
    migration de données requise).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""

    class Categorie(models.TextChoices):
        COMMIT = 'commit', 'Commit'
        BEST_CASE = 'best_case', 'Best case'
        PIPELINE = 'pipeline', 'Pipeline'
        OMIS = 'omis', 'Omis'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='forecast_entries')
    lead = models.OneToOneField(
        Lead, on_delete=models.CASCADE,  # on_delete: entrée sans objet si lead supprimé
        related_name='forecast_entry')
    categorie = models.CharField(
        max_length=12, choices=Categorie.choices, default=Categorie.PIPELINE)
    # Vide = repli sur le devis actif le plus récent du lead, sinon
    # `Lead.montant_estime` (voir la propriété `montant_effectif`).
    montant_prevu = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant prévu (MAD)')
    commentaire = models.TextField(blank=True, default='')
    mis_a_jour_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='forecast_entries_maj')
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Entrée de forecast'
        verbose_name_plural = 'Entrées de forecast'
        ordering = ['-mis_a_jour_le']

    def __str__(self):
        return f'{self.lead_id} — {self.categorie}'

    @property
    def montant_effectif(self):
        """Montant retenu pour l'agrégation forecast : ``montant_prevu`` posé
        explicitement, sinon le devis ACTIF le plus récent du lead, sinon
        ``Lead.montant_estime`` (XSAL7), sinon zéro."""
        from decimal import Decimal
        if self.montant_prevu is not None:
            return self.montant_prevu
        try:
            devis = self.lead.devis.filter(is_active=True).order_by(
                '-date_creation').first()
            if devis is not None:
                return devis.total_ttc
        except Exception:
            pass
        return self.lead.montant_estime or Decimal('0')


# ── NTCRM6 — Snapshots hebdomadaires du forecast ──────────────────────────────
class ForecastSnapshot(TenantModel):
    """Photo hebdomadaire agrégée du forecast (glissement visible dans le
    temps) — créée par ``manage.py snapshot_forecast_hebdo`` (idempotente : un
    seul snapshot par semaine ISO + owner, upsert). ``owner`` nul = snapshot
    SOCIÉTÉ (tous commerciaux confondus) ; renseigné = snapshot individuel.

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique). ``created_at`` hérité de
    TenantModel (à l'identique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='forecast_snapshots')
    semaine_iso = models.CharField(
        max_length=8, verbose_name='Semaine ISO (ex. 2026-W29)')
    categorie = models.CharField(
        max_length=12, choices=ForecastEntry.Categorie.choices)
    montant_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    nb_leads = models.PositiveIntegerField(default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        # on_delete: snapshot individuel lié à l'utilisateur (CASCADE conservé
        # plutôt que SET_NULL pour ne pas risquer une collision avec le
        # snapshot société existant sous la même contrainte unique)
        null=True, blank=True, related_name='forecast_snapshots')

    class Meta:
        verbose_name = 'Snapshot de forecast'
        verbose_name_plural = 'Snapshots de forecast'
        ordering = ['-semaine_iso']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'semaine_iso', 'categorie', 'owner'],
                name='crm_forecast_snapshot_uniq_semaine_owner',
            ),
        ]

    def __str__(self):
        return f'{self.semaine_iso} {self.categorie} = {self.montant_total}'


# ── NTCRM10 — Plan de compte (Account Planning) formel ────────────────────────
class PlanCompte(TenantModel):
    """Plan de compte stratégique pour un client (création MANUELLE only —
    réservé aux comptes stratégiques, pas tous les clients).

    ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique). Les timestamps propres
    (``date_creation``/``date_modification``) restent distincts des
    ``created_at``/``updated_at`` hérités (noms différents, conservés)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        ARCHIVE = 'archive', 'Archivé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='plans_compte')
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE,  # on_delete: plan sans objet si client supprimé
        related_name='plan_compte')
    objectifs_strategiques = models.TextField(blank=True, default='')
    potentiel_estime = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Potentiel estimé (MAD)')
    # Distinct de ConcurrentPerte/FG242 (qui ne couvre que les deals PERDUS) —
    # ici, un texte libre sur les concurrents présents chez ce compte.
    concurrents_presents = models.TextField(blank=True, default='')
    swot_forces = models.JSONField(null=True, blank=True)
    swot_faiblesses = models.JSONField(null=True, blank=True)
    swot_opportunites = models.JSONField(null=True, blank=True)
    swot_menaces = models.JSONField(null=True, blank=True)
    prochaine_revue = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='plans_compte_crees')
    mis_a_jour_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='plans_compte_maj')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan de compte'
        verbose_name_plural = 'Plans de compte'
        ordering = ['-date_modification']

    def __str__(self):
        return f'Plan de compte — {self.client_id}'


# ARC8 — l'historique (chatter) d'un ``PlanCompte`` NE passe PLUS par un modèle
# ``*Activity`` maison : il converge sur ``records.Activity`` via
# ``records.services.log_activity`` / ``chatter_qs`` (voir ``PlanCompteViewSet``).


# ── NTCRM30 (préparé par NTCRM10/11) — Revue de compte ────────────────────────
class RevueCompte(models.Model):
    """Note de réunion structurée liée à un ``PlanCompte`` (même esprit que
    ``ReunionChantier``/FG296 côté commercial), affichée en timeline."""
    plan = models.ForeignKey(
        PlanCompte, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='revues')
    date_revue = models.DateField()
    participants = models.TextField(blank=True, default='')
    decisions = models.TextField(blank=True, default='')
    prochaine_action = models.CharField(max_length=255, blank=True, default='')
    prochaine_action_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='revues_compte_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Revue de compte'
        verbose_name_plural = 'Revues de compte'
        ordering = ['-date_revue']

    def __str__(self):
        return f'Revue {self.plan_id} — {self.date_revue}'


# ── NTCRM12 — Playbooks de vente par étape (STAGES.py — jamais codé en dur) ──
class Playbook(TenantModel):
    """ARC1 — hérite de ``core.models.TenantModel``; ``company`` redéclaré à
    l'identique (related_name historique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='playbooks')
    nom = models.CharField(max_length=150)
    actif = models.BooleanField(default=True)
    # Configuration STRICTE optionnelle : un changement de stage avec tâches
    # obligatoires non cochées reste TOUJOURS possible (avertissement
    # seulement) SAUF si ce playbook est marqué bloquant=True — cohérent avec
    # « never auto-move »/jamais un blocage dur par défaut.
    bloquant = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Playbook'
        verbose_name_plural = 'Playbooks'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class PlaybookEtape(models.Model):
    """Étape d'un playbook — la clé ``stage`` vient TOUJOURS de STAGES.py
    (``STAGE_CHOICES``), jamais codée en dur (règle #2)."""
    playbook = models.ForeignKey(
        Playbook, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='etapes')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Étape de playbook'
        verbose_name_plural = 'Étapes de playbook'
        ordering = ['ordre', 'id']
        unique_together = [('playbook', 'stage')]

    def __str__(self):
        return f'{self.playbook.nom} — {self.stage}'


class PlaybookTache(models.Model):
    etape = models.ForeignKey(
        PlaybookEtape, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='taches')
    libelle = models.CharField(max_length=255)
    obligatoire = models.BooleanField(default=False)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Tâche de playbook'
        verbose_name_plural = 'Tâches de playbook'
        ordering = ['ordre', 'id']

    def __str__(self):
        return self.libelle


class LeadPlaybookProgress(models.Model):
    """Progression d'UN lead sur UNE tâche de playbook — créée automatiquement
    (signal ``core.events.lead_stage_changed``, voir ``receivers.py``) quand le
    lead entre dans une étape portant un playbook actif. Cocher une tâche pose
    l'acteur + la date, jamais silencieux."""
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE,  # on_delete: progression sans objet si lead supprimé
        related_name='playbook_progress')
    tache = models.ForeignKey(
        PlaybookTache, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='progressions')
    fait = models.BooleanField(default=False)
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='playbook_taches_faites')
    fait_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Progression playbook du lead'
        verbose_name_plural = 'Progressions playbook des leads'
        ordering = ['tache__ordre', 'id']
        unique_together = [('lead', 'tache')]

    def __str__(self):
        return f'{self.lead_id} — {self.tache_id} ({"fait" if self.fait else "à faire"})'


# ── LB48 — Vues enregistrées par compte (filtres + disposition de page) ───────

class SavedView(TenantModel):
    """LB48 — vue enregistrée PERSONNELLE (un utilisateur, une page).

    Mémorise un jeu de filtres + une disposition de vue (ex. Kanban vs liste)
    pour une page donnée (``page`` = clé applicative libre, ex. ``crm.leads``),
    propre à l'utilisateur qui l'a créée — jamais partagée entre utilisateurs
    (contrairement à un futur « vues d'équipe »). Société ET utilisateur sont
    TOUJOURS posés côté serveur (jamais lus du corps de requête, cf.
    ``SavedViewViewSet``). ``rank`` ordonne les vues d'un utilisateur pour une
    page (0 = première/défaut) ; l'action ``reorder`` les réassigne en bloc.
    """
    # SCA4 — `company` + timestamps hérités de core.models.TenantModel
    # (accesseur inverse par défaut : company.crm_savedview_set).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: vue personnelle, sans objet sans son propriétaire
        related_name='crm_vues_enregistrees')
    page = models.CharField(
        max_length=64,
        help_text="Clé applicative de la page (ex. 'crm.leads').")
    name = models.CharField(max_length=80, verbose_name='Nom')
    rank = models.PositiveIntegerField(
        default=0, verbose_name='Rang',
        help_text='0 = première/vue par défaut.')
    payload = models.JSONField(
        default=dict, blank=True,
        help_text="Contenu de la vue : {filters, view}.")

    class Meta:
        verbose_name = 'Vue enregistrée'
        verbose_name_plural = 'Vues enregistrées'
        ordering = ['rank', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'page', 'name'],
                name='crm_sv_uniq_user_page_name',
            ),
        ]

    def __str__(self):
        return f'{self.page} — {self.name} ({self.user_id})'
