"""Profil entreprise (``CompanyProfile``).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``models.py`` monolithique sans le moindre changement de champ, de ``Meta`` ou
de nom de table — l'``app_label`` reste ``parametres`` et la table reste
``parametres_companyprofile`` (split sans migration)."""
from decimal import Decimal

from django.db import models


class CompanyProfile(models.Model):
    """
    Un profil par entreprise (utilisé dans les PDFs et paramètres).
    Pour la rétro-compatibilité, pk=1 reste l'instance par défaut
    lorsqu'aucune company n'est fournie.
    """
    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='profile',
    )
    nom = models.CharField(max_length=255, default='Mon Entreprise')
    adresse = models.TextField(blank=True, default='')
    email = models.EmailField(blank=True, default='')
    telephone = models.CharField(max_length=30, blank=True, default='')
    siret = models.CharField(max_length=20, blank=True, default='')
    tva_intra = models.CharField(max_length=20, blank=True, default='')
    # ── Identifiants légaux marocains (2026-06) — additif, tout optionnel ──
    # L'ICE du vendeur est légalement obligatoire sur une facture marocaine.
    # siret/tva_intra (style français) restent en place mais inutilisés ici.
    ice = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Identifiant Commun de l\'Entreprise (obligatoire sur facture).')
    identifiant_fiscal = models.CharField(
        max_length=30, blank=True, default='',
        help_text='IF — Identifiant Fiscal.')
    rc = models.CharField(
        max_length=30, blank=True, default='',
        help_text='RC — Registre de Commerce.')
    patente = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Patente / Taxe Professionnelle.')
    cnss = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Numéro d\'affiliation CNSS.')
    rib = models.CharField(max_length=50, blank=True, default='')
    banque = models.CharField(max_length=100, blank=True, default='')
    # ── SCA27 — site web de la société (identité/coordonnées) ──
    # Additif, VIDE par défaut. Pilote la ligne « site » du pied de page du PDF
    # résidentiel et la base des liens fiches produits : quand il est renseigné,
    # le moteur affiche CE site (et omet les fiches taqinor.ma du fondateur) ;
    # vide → le moteur garde ses littéraux historiques (taqinor.ma), donc un
    # devis sans profil enrichi reste rendu strictement à l'identique.
    site_web = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Site web de la société (ex. helios.ma), affiché sur le PDF '
                  'du devis. Vide = défaut historique.')
    # ── Bloc paiement & conditions sur la FACTURE (Feature B, 2026-06) ──
    # Trois réglages texte libre, additifs et VIDES par défaut : tant qu'ils ne
    # sont pas renseignés, le PDF facture est strictement identique (les blocs ne
    # s'affichent que si non-vides). Le RIB ci-dessus complète ce bloc. Ces
    # valeurs ne touchent JAMAIS le moteur premium des devis (pas de slot dédié).
    instructions_paiement = models.TextField(blank=True, default='')
    conditions_generales = models.TextField(blank=True, default='')
    couleur_principale = models.CharField(
        max_length=7, default='#2563EB'
    )
    logo_key = models.CharField(max_length=500, blank=True, default='')
    signature_key = models.CharField(
        max_length=500, blank=True, default=''
    )
    # Responsable assigné par défaut aux NOUVEAUX leads (site + manuel) quand
    # aucun responsable n'est choisi à la création. Initialisé sur le compte
    # « Meryem » par migration de données ; modifiable dans Paramètres.
    responsable_defaut_leads = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    # ── XSAL11 — Affectation round-robin équilibrée des leads entrants ──
    # OFF par défaut = comportement actuel inchangé (responsable par défaut /
    # round-robin déjà existant de QW6). ON : parmi les commerciaux actifs
    # (rôle « Commercial »), affecte au prochain dans la rotation en sautant
    # quiconque dépasse le plafond de leads OUVERTS (stage non SIGNED/COLD,
    # jamais perdu) ; fallback sur `responsable_defaut_leads` si tous saturés.
    round_robin_leads_actif = models.BooleanField(
        default=False,
        verbose_name='Affectation round-robin équilibrée des leads',
        help_text='OFF = comportement actuel (round-robin simple ou '
                  "responsable par défaut). ON = plafond de leads ouverts "
                  'par commercial appliqué avant rotation.')
    round_robin_plafond_leads_ouverts = models.PositiveIntegerField(
        default=20,
        verbose_name='Plafond de leads ouverts par commercial',
        help_text="Un commercial au-delà de ce nombre de leads OUVERTS "
                  "(stage non SIGNED/COLD, non perdu) est sauté dans la "
                  "rotation (XSAL11).")
    # N66 — installateur (technicien) assigné par défaut aux NOUVEAUX chantiers
    # quand aucun n'est choisi. NULL = comportement actuel (le créateur du
    # chantier en est le technicien responsable). Additif.
    default_installer = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    # ── Paramètres métier éditables (2026-06) — ADDITIFS ──
    # Chacun a pour défaut la valeur codée en dur aujourd'hui : tant que le
    # founder n'édite rien, le comportement est strictement identique.
    # Échéancier par mode : {mode: {acompte, materiel, solde}} en %. NULL =
    # repli sur PAYMENT_TERMS_BY_MODE (défaut historique 30/60/10 · 30/60/10 ·
    # 50/40/10).
    payment_terms = models.JSONField(null=True, blank=True)
    # Durée de validité du devis (jours). Défaut historique 30.
    quote_validity_days = models.PositiveIntegerField(default=30)
    # Heures de pompage effectives/jour par défaut (mode agricole). Défaut 7.
    agricole_pump_hours = models.DecimalField(
        max_digits=4, decimal_places=1, default=7)
    # Préfixes de numérotation des pièces : {devis,facture,avoir,bon_commande}.
    # NULL = repli sur les préfixes historiques (DEV/FAC/AVO/BC).
    doc_prefixes = models.JSONField(null=True, blank=True)
    # Numérotation par type de pièce (D3) : largeur de remplissage + période de
    # réinitialisation. Forme {key: {padding:int, reset:'monthly'|'yearly'|'none'}}.
    # NULL/clé absente = défaut historique (padding 4, reset mensuel) → la
    # numérotation reste strictement identique tant que rien n'est édité. Le
    # préfixe lui-même reste dans doc_prefixes (inchangé).
    doc_numbering = models.JSONField(null=True, blank=True)
    # Taux de TVA (réforme marocaine) — éditables, défauts historiques.
    tva_standard = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)
    tva_panneaux = models.DecimalField(
        max_digits=5, decimal_places=2, default=10)
    # ── Constantes ROI éditables (T6) — défauts = valeurs historiques codées
    # en dur dans le simulateur (solar.js). Tant qu'elles ne sont pas éditées,
    # le comportement reste identique ; le simulateur garde son repli interne.
    # Tarif ONEE moyen (MAD/kWh) — défaut 1.75 (solar.js KWH_PRICE).
    onee_tarif_kwh = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('1.75'))
    # Productible annuel moyen (kWh par kWc installé) — repère ROI éditable.
    productible_kwh_kwc = models.DecimalField(
        max_digits=7, decimal_places=1, default=Decimal('1600.0'))
    # ── Logique de devis éditable (D5) — défauts = constantes codées en dur du
    # simulateur (solar.js EFFICIENCY/estimerPanneaux). Tant qu'elles ne sont
    # pas éditées, le devis reste STRICTEMENT identique ; le simulateur garde
    # son repli interne (constantes par défaut).
    # Rendement global (productible appliqué à la production) — défaut 0.8.
    rendement_global = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal('0.8'))
    # Auto-remplir : nombre de panneaux par tranche de 900 MAD (facture hiver).
    panneaux_par_900mad = models.PositiveSmallIntegerField(default=8)
    # Prix cible /kWc par défaut (pré-remplit le générateur). NULL/vide = aucun
    # (comportement actuel : pas de prix cible pré-réglé).
    prix_cible_kwc_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Limite de remise (%) indicative dans le générateur. NULL/vide = aucune
    # limite (comportement actuel). Distinct du seuil d'APPROBATION (T17).
    remise_max_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    # Seuil d'approbation de remise (%) (T17). NULL/vide = désactivé (défaut) :
    # tant qu'il n'est pas renseigné, aucun devis n'exige d'approbation.
    discount_approval_threshold = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    # ── Seuils de régime loi 82-21 (N43) — kWc, éditables. Défauts = cadre
    # marocain standard : déclaration < 11 kWc, autorisation ANRE > 1 MW.
    seuil_regime_declaration_kwc = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('11'))
    seuil_regime_anre_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1000'))
    # ── Commission commerciale (N99) — additif, désactivé par défaut. Mode
    # 'off' (aucune commission, comportement inchangé), 'pct_devis' (% du HT
    # des devis signés) ou 'par_kwc' (MAD par kWc installé des chantiers issus
    # des devis signés). `commission_valeur` porte le % ou le montant/kWc selon
    # le mode. Donnée sensible : exposée aux seuls rôles autorisés (admin).
    commission_mode = models.CharField(max_length=10, default='off')
    commission_valeur = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # N98 — programme de parrainage : activation + récompense par défaut (pré-
    # remplit un nouveau parrainage). Désactivé par défaut → rien ne change.
    referral_enabled = models.BooleanField(default=False)
    referral_reward = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # ── FG52 — Devise par défaut de la société (multi-currency) ──
    # Préremplie sur les NOUVEAUX documents créés pour cette société. Défaut MAD
    # = comportement inchangé pour toutes les sociétés existantes. La devise est
    # uniquement informative / portée par le document (pas de conversion en base).
    devise_defaut = models.CharField(
        max_length=10, default='MAD',
        verbose_name='Devise par défaut',
        help_text='Code ISO 4217 appliqué par défaut aux nouveaux devis/factures '
                  '(ex. MAD, EUR, USD). Défaut MAD.',
    )

    # ── N105 — Capacité DGI LOCALE (interrupteur maître, défaut OFF) ──
    # Unique commutateur, par société, qui ARME la capacité DGI locale (export
    # UBL 2.1 conforme + validateur de conformité), atteignable UNIQUEMENT à la
    # demande / par programme (commande de gestion ou endpoint gardé). Tant
    # qu'il est False (défaut), la capacité est TOTALEMENT invisible et ne
    # change RIEN au comportement actuel : aucune pastille, aucun statut, aucune
    # colonne de liste, aucune modification du modèle Facture. Posé côté
    # serveur, jamais lu du corps d'une requête métier. HORS PÉRIMÈTRE (gatés
    # ailleurs) : transmission Simpl-TVA, signature électronique certifiée.
    dgi_export_actif = models.BooleanField(default=False)

    # ── XFAC29 — Transmission DGI SORTANTE (interrupteur maître, défaut OFF) ──
    # Distinct de `dgi_export_actif` (export local N105, jamais transmis) :
    # arme la couche de SIGNATURE + TRANSMISSION à une plateforme agréée
    # (apps/ventes/dgi/transmission.py). Tant qu'il est False (défaut), aucun
    # appel réseau n'est jamais tenté et `Facture.dgi_statut` reste à sa valeur
    # par défaut. `dgi_transmission_provider` nomme le fournisseur ('noop' par
    # défaut, 'mock' en tests) — swappable comme `payments/providers.py`.
    dgi_transmission_actif = models.BooleanField(default=False)
    dgi_transmission_provider = models.CharField(
        max_length=30, blank=True, default='noop')

    # ── YDOCF7 — Réservation de stock à la confirmation d'un BonCommande ──
    # Défaut OFF = comportement actuel intact (stock touché seulement à
    # `marquer-livre`). ON : `confirmer` réserve (StockReservation N14),
    # `annuler` libère, `marquer-livre` consomme la réservation au lieu d'un
    # second décrément direct.
    reserver_stock_bc = models.BooleanField(default=False)

    # ── Module d'exécution terrain (F9–F20) — interfaces SWAPPABLES ──
    # Chaque champ NOMME le fournisseur d'une capacité optionnelle. VIDE par
    # défaut = NO-OP total (aucun identifiant externe, aucun coût) : F9 retombe
    # sur la saisie manuelle, F14 étiquette « Non transcrit — service non
    # configuré », F20 ne signale rien. Aucun fournisseur n'est branché par ces
    # tâches ; renseigner ces champs est une décision opérateur faite ici.
    ocr_serie_provider = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Fournisseur OCR pour l'extraction des n° de série (F9). "
                  "Vide = saisie manuelle uniquement.")
    transcription_provider = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Fournisseur de transcription des mémos vocaux (F14). '
                  'Vide = mémos non transcrits.')
    photo_qa_provider = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Fournisseur de contrôle qualité IA des photos (F20). '
                  'Vide = aucun contrôle.')
    # F12 — seuil (%) de dépassement de consommation au-delà duquel une
    # intervention est signalée à la revue. Défaut 10 % ; éditable en Paramètres.
    overage_seuil_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10'),
        help_text="Pourcentage de dépassement de consommation déclenchant la "
                  "revue (F12).")
    # FG28 — Délai SLA de première prise de contact (heures). Un lead NEW ou
    # site_web non contacté au-delà de ce délai est signalé en rouge (badge
    # kanban + filtre « Non contactés > Xh »). Défaut 24 h. 0 = désactivé.
    lead_sla_hours = models.PositiveIntegerField(
        default=24,
        help_text='Délai maximum (en heures) avant première prise de contact '
                  'sur un nouveau lead. 0 = SLA désactivé.'
    )

    # ── FG22 — Politique de mot de passe & verrouillage de compte ──
    # Tous ADDITIFS et désactivés par défaut → comportement de connexion/
    # changement de mot de passe strictement inchangé tant que rien n'est édité.
    # Longueur minimale exigée (en plus des validateurs Django). Défaut 8 =
    # aligné sur le validateur Django standard (aucune exigence supplémentaire).
    password_min_length = models.PositiveSmallIntegerField(
        default=8,
        help_text='Longueur minimale du mot de passe (FG22).')
    # Exiger un mélange majuscule/minuscule + chiffre + caractère spécial.
    # False par défaut = aucune exigence de complexité supplémentaire.
    password_require_complexity = models.BooleanField(
        default=False,
        help_text='Exiger maj./min./chiffre/caractère spécial (FG22).')
    # Verrouillage après N échecs consécutifs. 0 = verrouillage désactivé
    # (défaut) → seul le throttle IP historique s'applique.
    lockout_max_attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Nombre d'échecs consécutifs avant verrouillage (0 = off).")
    # Durée du verrouillage en minutes (quand lockout_max_attempts > 0).
    lockout_duration_minutes = models.PositiveSmallIntegerField(
        default=15,
        help_text='Durée du verrouillage temporaire (minutes).')
    # Expiration du mot de passe (jours). 0 = jamais (défaut) → aucun compte
    # n'est jamais forcé de changer pour ancienneté.
    password_expiry_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="Expiration du mot de passe en jours (0 = jamais).")

    # ── NTSEC10 — Politique de session par société ──────────────────────────
    # Tous ADDITIFS et INERTES par défaut (0) → la durée de session/JWT actuelle
    # et le nombre de sessions concurrentes restent strictement inchangés tant
    # que la société ne fixe rien. Le câblage réel (refus de refresh JWT au-delà
    # de la durée absolue/inactivité, éviction de la session la plus ancienne à
    # la Nième) vit dans `apps/authentication` (couche cross-app) qui LIT ces
    # champs ; ce modèle n'en porte que la configuration.
    # Durée de vie absolue d'une session (heures) depuis sa création. 0 = durée
    # JWT actuelle (défaut) → aucun plafond absolu appliqué.
    session_absolute_hours = models.PositiveIntegerField(
        default=0,
        help_text="Durée de vie absolue d'une session (heures) depuis sa "
                  "création. 0 = durée JWT actuelle (défaut).")
    # Délai d'inactivité (minutes) au-delà duquel une session dormante ne peut
    # plus rafraîchir son jeton. 0 = désactivé (défaut).
    session_idle_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Délai d'inactivité (minutes) au-delà duquel une session "
                  "ne peut plus rafraîchir. 0 = désactivé (défaut).")
    # Nombre maximum de sessions actives simultanées par utilisateur. À la
    # Nième session, la plus ancienne est révoquée. 0 = illimité (défaut).
    max_concurrent_sessions = models.PositiveIntegerField(
        default=0,
        help_text="Nombre maximum de sessions concurrentes par utilisateur "
                  "(la plus ancienne est révoquée au-delà). 0 = illimité.")

    # ── NTSEC9 — MFA « step-up » par sensibilité d'action ──────────────────
    # Liste (JSON) des clés d'action que CETTE société considère sensibles et
    # pour lesquelles une ré-authentification MFA récente est exigée (paie run,
    # export SIEM, création IdP, break-glass…). VIDE par défaut = step-up
    # inactif → comportement strictement inchangé. Le contrôle runtime vit dans
    # `apps.identity.stepup.require_recent_mfa` (fondation réutilisable) ; ce
    # modèle n'en porte que la configuration par société.
    step_up_actions = models.JSONField(
        default=list, blank=True,
        help_text="Clés d'action exigeant une MFA récente (step-up). Liste "
                  "vide = inactif (défaut).")

    # ── NTSEC14 — appareils de confiance (« se souvenir de cet appareil ») ──
    # Quand True, un utilisateur peut, à la validation MFA, faire confiance à
    # son appareil pour sauter le second facteur jusqu'à expiration. False par
    # défaut = fonction inactive → la MFA reste toujours exigée (inchangé).
    allow_device_trust = models.BooleanField(
        default=False,
        help_text="Autoriser « se souvenir de cet appareil » pour sauter la "
                  "MFA sur un appareil de confiance. Défaut False.")

    # ── NTSEC28 — bannière / mention légale sur l'écran de connexion ────────
    # Texte affiché sur l'écran de login (SSO et local) exigeant un accusé avant
    # authentification (« accès autorisé uniquement… »). VIDE par défaut =
    # écran de login inchangé. L'accusé est journalisé best-effort (IP/UA).
    login_banner_text = models.TextField(
        blank=True, default='',
        help_text="Mention légale affichée avant authentification (accès "
                  "autorisé uniquement…). Vide = aucun bandeau (défaut).")

    # ── QG9 — pourcentage des variantes de devis (dupliquer-variante) ──
    # Pourcentage symétrique appliqué autour du devis d'origine pour produire
    # les variantes de taille : échelles [1−p, 1.0, 1+p]. Défaut 20 %
    # (échelles historiques ≈ 0.8 / 1.0 / 1.2). Éditable par Directeur /
    # Commercial responsable ; un override par requête reste possible. Additif :
    # une société existante utilise 20 tant que rien n'est changé.
    variante_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('20'),
        help_text='Pourcentage des variantes de devis (échelles 1−p / 1 / 1+p). '
                  'Défaut 20 %.')

    # ── FG26 — fenêtre de rétention du journal d'audit (RGPD) ──
    # Au-delà de N jours, les lignes du Journal d'activité peuvent être purgées
    # (commande/endpoint admin). 0 = conservation illimitée (défaut) → rien
    # n'est jamais purgé tant que la société ne fixe pas de fenêtre.
    audit_retention_days = models.PositiveIntegerField(
        default=0,
        help_text="Rétention du journal d'audit en jours (0 = illimité).")

    # ── NTSEC25 — comptes dormants : seuil de désactivation automatique ──
    # Un compte sans session (dernier ``UserSession.last_seen_at``) au-delà de
    # ``dormant_days`` jours est listé puis désactivé par la commande
    # ``desactiver_comptes_dormants``. 0 = désactivé (défaut) → jamais de
    # désactivation automatique ; réactivation manuelle toujours possible.
    dormant_days = models.PositiveIntegerField(
        default=0,
        help_text="Jours d'inactivité au-delà desquels un compte est désactivé "
                  "automatiquement (0 = jamais).")

    # ── XMKT21 — seuil de score MQL (Marketing Qualified Lead) ──
    # NULL/0 = désactivé (défaut) : aucune assignation automatique tant que la
    # société ne fixe pas de seuil — comportement actuel strictement inchangé.
    # Quand le score d'un lead (QJ6/FG27) franchit ce seuil, il est assigné
    # automatiquement (round-robin) + le responsable est notifié (XMKT21).
    seuil_mql = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Seuil de score MQL',
        help_text='Score (0–100) au-delà duquel un lead est automatiquement '
                  'assigné et le commercial notifié. Vide/0 = désactivé.')

    # ── YLEAD14 — recyclage des leads non travaillés (2e seuil, désassignation) ──
    # 0/NULL = désactivé (défaut) : un lead SLA-dépassé est escaladé (activité +
    # notification) mais JAMAIS désassigné tant que ce champ n'est pas fixé —
    # comportement actuel inchangé. Au-delà de ce délai (heures depuis la
    # création, complémentaire au SLA de premier contact), le owner est retiré
    # (owner→None) pour retourner le lead au pool.
    lead_sla_deassign_hours = models.PositiveIntegerField(
        default=0,
        help_text='Délai (heures) au-delà duquel un lead SLA-dépassé est '
                  'désassigné (rendu au pool). 0 = jamais désassigné (défaut).')
    # ── XFAC7 — rappel de courtoisie PRÉ-échéance (J-N avant échéance) ──
    # N jours AVANT date_echeance d'une facture émise, envoie un rappel amical
    # (prouvé pour réduire les retards — Chargebee/Odoo). Défaut 5, 0 = désactivé
    # → comportement historique inchangé tant que la société n'y touche pas.
    rappel_pre_echeance_jours = models.PositiveIntegerField(
        default=5,
        help_text="Jours avant échéance pour le rappel de courtoisie "
                  "(0 = désactivé).")

    # ── XFAC12 — escompte pour règlement anticipé (ex. 2/10 net 30) ──
    # Défauts PROPOSÉS à la création d'une facture (surchargeables par
    # facture) ; NULL = pas de proposition automatique (comportement actuel
    # inchangé — la société doit les activer explicitement).
    escompte_pct_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Taux d'escompte (%) proposé par défaut sur les "
                  "nouvelles factures.")
    escompte_jours_defaut = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Délai (jours) proposé par défaut pour l'escompte.")

    # ── XFAC13 — tolérance d'écart de règlement (abandon auto du résiduel) ──
    # Défaut 0 = comportement actuel inchangé (aucun abandon automatique). Un
    # résiduel (facture − paiement encaissé) strictement inférieur ou égal à ce
    # seuil (MAD) est proposé/soldé automatiquement à l'enregistrement du
    # paiement plutôt que de laisser la facture « en retard » indéfiniment.
    tolerance_ecart_reglement = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'),
        help_text='Résiduel (MAD) toléré, abandonné automatiquement à '
                  "l'encaissement. 0 = désactivé (défaut).")

    # ── XFAC18 — workflow de revue facture (ségrégation des tâches) ──
    # Défaut OFF = comportement actuel byte-identique (n'importe quel rôle qui
    # crée une facture peut l'émettre). ON : une facture créée par un
    # utilisateur du tier limité démarre « à valider » et l'émission exige un
    # valideur du tier responsable/admin DIFFÉRENT du créateur.
    revue_factures_active = models.BooleanField(
        default=False,
        help_text="Active le contrôle 4-yeux à l'émission des factures "
                  "(désactivé par défaut).")

    # ── XFAC24 — immutabilité de la facture émise (opt-in) ──
    # Défaut OFF = comportement actuel byte-identique (une facture émise reste
    # librement modifiable, hors verrou de PÉRIODE compta FG115). ON : les
    # champs financiers d'une facture non-brouillon deviennent en lecture
    # seule (correction par avoir + nouvelle facture uniquement) — prépare la
    # facturation électronique DGI (mandat 2026).
    factures_immuables = models.BooleanField(
        default=False,
        help_text="Interdit la modification des champs financiers d'une "
                  "facture non-brouillon (correction par avoir uniquement).")

    # ── XFAC28 — blocage crédit dur configurable (étend FG41) ──
    # Défaut OFF = comportement FG41 intact (avertissement seul, jamais de
    # blocage). ON : un client en dépassement de plafond (ou en retard au-delà
    # du seuil configuré) voit ``devis/{id}/accepter`` et
    # ``devis/{id}/generer-facture`` refusés (403), sauf override explicite
    # d'un responsable/admin. DECISION founder (2026) : seuils par défaut
    # prudents (0 jour = le critère retard est ignoré tant qu'il n'est pas
    # explicitement configuré ; le critère plafond utilise TOUJOURS
    # ``Client.plafond_credit`` déjà existant — FG41) ; le founder ajuste
    # ``credit_hold_retard_jours`` selon sa politique de recouvrement.
    credit_hold_actif = models.BooleanField(
        default=False,
        help_text="Bloque (403) les nouveaux devis acceptés/factures d'un "
                  "client en dépassement de crédit, au lieu du seul "
                  "avertissement FG41. Désactivé par défaut.")
    credit_hold_retard_jours = models.PositiveIntegerField(
        default=0,
        help_text="Jours de retard sur facture(s) ouvertes au-delà desquels "
                  "le hold s'applique aussi (indépendamment du plafond). "
                  "0 = ce critère est ignoré (seul le dépassement de "
                  "plafond FG41 déclenche le hold).")

    # ── XFSM1 — Facturation SAV hors garantie depuis le ticket ──────────────
    # Taux horaire main-d'œuvre (MAD/heure) utilisé par
    # ``sav.views.TicketViewSet.generer_facture`` pour chiffrer la ligne MO
    # d'un ticket SAV hors garantie. Vide = aucun taux configuré : la
    # génération de facture refuse la ligne MO tant que le founder n'a pas
    # renseigné ce taux (jamais de valeur inventée).
    taux_horaire_sav = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Taux horaire main-d\'œuvre SAV (MAD/heure), utilisé pour '
                  'facturer un ticket hors garantie depuis son temps passé.')

    # ── YSERV1 — Gate « acompte encaissé » avant planification (opt-in) ──────
    # Défaut OFF = comportement actuel byte-identique (aucun contrôle de
    # paiement à la planification). ON : passer un chantier à PLANIFIE est
    # refusé tant qu'aucune Facture de type 'acompte' du devis lié n'est
    # 'payee' — sauf override responsable/admin avec motif obligatoire
    # (journalisé au chatter).
    exiger_acompte_avant_planification = models.BooleanField(
        default=False,
        help_text="Bloque la planification d'un chantier (statut PLANIFIE) "
                  "tant que l'acompte du devis lié n'est pas encaissé. "
                  'Désactivé par défaut.')

    # ── YHIRE9 — garde d'habilitation à l'affectation d'intervention ─────────
    # Consomme `rh.selectors.verifier_habilitation_requise` (FG176) à
    # l'affectation/changement de technicien d'une intervention typée.
    # 'warn' (défaut) = un avertissement `avertissements[]` est renvoyé sans
    # bloquer (comportement quasi byte-identique — juste un champ en plus) ;
    # 'block' = l'affectation est refusée (400) tant que l'habilitation
    # requise n'est pas valide.
    class ModeGardeHabilitation(models.TextChoices):
        WARN = 'warn', 'Avertir seulement'
        BLOCK = 'block', 'Bloquer'

    mode_garde_habilitation = models.CharField(
        max_length=10, choices=ModeGardeHabilitation.choices,
        default=ModeGardeHabilitation.WARN,
        help_text="Comportement quand un technicien affecté n'a pas "
                  "l'habilitation requise pour le type d'intervention : "
                  "avertir (défaut) ou bloquer l'affectation.")

    # ── ZSTK11 — méthode de réservation du stock (Odoo "Reservation methods")
    # Défaut 'confirmation' = comportement actuel byte-identique : la création
    # d'un chantier (depuis un devis accepté) sème la réservation N14
    # automatiquement. 'manuelle' : le SEUL déclencheur devient conditionnel —
    # aucune réservation automatique à la création ; un bouton « Réserver le
    # stock » explicite appelle le même service `installations.services.
    # seed_reservations` (aucune logique de réservation dupliquée).
    class MethodeReservationStock(models.TextChoices):
        CONFIRMATION = 'confirmation', 'À la confirmation'
        MANUELLE = 'manuelle', 'Manuelle'

    methode_reservation_stock = models.CharField(
        max_length=20, choices=MethodeReservationStock.choices,
        default=MethodeReservationStock.CONFIRMATION,
        help_text="Réserver le stock automatiquement à la création du "
                  "chantier (défaut, comportement historique) ou "
                  "manuellement via un bouton explicite.")

    # ── ZSTK2 — fenêtre d'alerte de péremption (jours) pour la tâche beat
    # `stock.expiration_alerts` (Odoo "expiration alerts" scheduled action).
    # Défaut 30 — réutilise `produits_expirant_bientot` (FG64) tel quel, sans
    # dupliquer la logique d'expiry.
    jours_alerte_peremption = models.PositiveIntegerField(
        default=30,
        help_text='Fenêtre (jours) au-delà de laquelle un lot proche de sa '
                  'péremption déclenche une alerte automatique quotidienne.')

    # ── XMKT4 — consentement marketing (loi 09-08 / CNDP) ───────────────────
    # Numéro de déclaration CNDP, affiché dans le pied des emails marketing
    # (informatif, jamais obligatoire — vide = comportement actuel).
    numero_declaration_cndp = models.CharField(
        max_length=60, blank=True, default='',
        help_text="Numéro de déclaration CNDP (loi 09-08), affiché dans le "
                  "pied des emails marketing s'il est renseigné.")
    # Double opt-in des inscriptions publiques (FormulaireIntake) : OFF par
    # défaut (comportement actuel préservé — inscription immédiatement
    # consentante).
    double_optin_actif = models.BooleanField(
        default=False,
        help_text="Active le double opt-in (email de confirmation, "
                  "mailable seulement après clic) pour les inscriptions "
                  "publiques marketing. Désactivé par défaut.")

    # ── XMKT7 — pression marketing (throttling + fenêtres de silence) ───────
    # NULL/0 = comportement actuel (aucune limite), tous canaux confondus
    # (campagnes + séquences), sur la fenêtre glissante de
    # ``pression_marketing_periode_jours`` jours.
    pression_marketing_max_par_contact = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Nombre maximum de messages marketing (campagnes + "
                  "séquences, tous canaux) par contact sur la période. "
                  "Vide = aucune limite (comportement actuel).")
    pression_marketing_periode_jours = models.PositiveIntegerField(
        default=7,
        help_text="Fenêtre glissante (jours) sur laquelle le plafond de "
                  "pression marketing est évalué.")

    # ── XMKT22 — politique « sunset » d'engagement ──────────────────────────
    # NULL = fonctionnalité désactivée (comportement actuel, aucun contact
    # jamais marqué dormant). Valeur typique 90-180 jours.
    sunset_fenetre_jours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Fenêtre (jours, 90-180 typiquement) sans ouverture/clic "
                  "au-delà de laquelle un contact est marqué dormant et "
                  "sauté aux envois. Vide = désactivé (comportement actuel).")

    # ── XMKT23 — approbation avant envoi de masse ───────────────────────────
    seuil_approbation_envoi_masse = models.PositiveIntegerField(
        default=100,
        help_text="Au-delà de ce nombre de destinataires, l'envoi d'une "
                  "campagne exige l'approbation d'un Responsable/Directeur.")

    # ── ZFAC11 — arrondi de caisse sur règlements en ESPÈCES ────────────────
    # Le plus petit pas d'arrondi appliqué au reste à payer d'une facture
    # réglée EN ESPÈCES (0,05 / 0,20 / 1,00 MAD sont les pas typiques marocains ;
    # champ libre pour rester configurable). Défaut 0 = arrondi DÉSACTIVÉ →
    # comportement actuel strictement inchangé (aucun arrondi, aucun écart).
    # DÉCISION fondateur : pas d'arrondi configurable (défaut OFF) ; l'écart
    # d'arrondi est tracé comme un abandon de résiduel « Arrondi espèces »
    # (motif ZFAC11) — jamais silencieux — et suit l'écriture d'abandon de
    # créance existante (compte d'écart = 6585, celui de l'abandon FG135/XFAC13).
    # Ne s'applique QU'aux règlements en espèces ; virement/chèque/carte
    # l'ignorent totalement.
    arrondi_caisse = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Arrondi de caisse (espèces)',
        help_text="Plus petit pas d'arrondi (MAD) appliqué au reste à payer "
                  "d'une facture réglée en espèces (ex. 0,05 / 0,20 / 1,00). "
                  "0 = désactivé (comportement actuel).")

    # ── ZSTK13 — Réglages société stock (barcode / lots-séries / multi-
    # emplacements / colis) — surface de configuration unifiée. Ces capacités
    # existent déjà (multi-emplacements FG319, lots/séries FG61/64, colisage
    # FG322, scan FG384) et étaient TOUJOURS actives sans réglage société.
    # Défaut True = comportement actuel byte-identique pour toute société
    # existante ; passer un drapeau à False MASQUE l'affichage correspondant
    # côté frontend (aucune donnée détruite, aucun endpoint retiré — réversible).
    stock_lots_series_actif = models.BooleanField(
        default=True,
        verbose_name='Lots & numéros de série',
        help_text='Affiche les champs lot/série (réception, registre '
                  'd\'expiration, étiquettes). Désactiver masque ces champs '
                  'sans supprimer les données existantes.')
    stock_colisage_actif = models.BooleanField(
        default=True,
        verbose_name='Colisage',
        help_text="Affiche l'écran de colisage (préparation/contrôle des "
                  'colis avant expédition). Désactiver masque l\'écran sans '
                  'supprimer les colis existants.')
    stock_scan_actif = models.BooleanField(
        default=True,
        verbose_name='Scan code-barres',
        help_text='Affiche les panneaux de réception/scan code-barres. '
                  'Désactiver masque ces panneaux (la saisie manuelle reste '
                  'disponible).')

    # ── WIR24 — Écritures comptables automatiques (réglage PAR SOCIÉTÉ) ────
    # L'auto-passation des écritures ventes/achats (facture/paiement/avoir) est
    # câblée et idempotente sur ``core.events`` (apps/compta/receivers.py) mais
    # n'était gardée que par le réglage GLOBAL ``COMPTA_AUTO_ECRITURES`` (défaut
    # False) — aucun interrupteur in-app. Ce drapeau l'active pour CETTE société
    # sans toucher les autres. Défaut False = comportement historique inchangé
    # (rien n'est passé au grand livre tant que ni le global ni ce drapeau ne
    # sont actifs). Le réglage global reste un interrupteur MAÎTRE : s'il est
    # True, l'auto-génération est active pour toutes les sociétés (rétro-compat).
    comptabilite_auto_ecritures = models.BooleanField(
        default=False,
        verbose_name='Écritures comptables automatiques',
        help_text="Passe automatiquement au grand livre l'écriture de chaque "
                  'facture, paiement et avoir émis (partie double, idempotent). '
                  "Désactivé par défaut : aucune écriture n'est générée tant que "
                  "ce réglage n'est pas activé.")

    class Meta:
        verbose_name = 'Profil entreprise'

    def __str__(self):
        return self.nom

    @classmethod
    def get(cls, company=None):
        """
        Retourne (ou crée) le profil pour une company donnée.
        Sans company, retourne/crée l'instance pk=1 (rétro-compat).
        """
        if company is not None:
            obj, _ = cls.objects.get_or_create(
                company=company,
                defaults={'nom': company.nom},
            )
            return obj
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
