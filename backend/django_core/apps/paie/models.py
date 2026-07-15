"""Modèles de la Paie marocaine (module `apps.paie`).

Socle des paramètres de paie conformes au cadre social marocain :

* ``ParametrePaie`` (PAIE2) — constantes sociales VERSIONNÉES par société et par
  ``date_effet`` : SMIG/SMAG, plafond CNSS, taux CNSS/AMO salarial & patronal,
  taux de la taxe de formation professionnelle. Un nouveau jeu de constantes
  s'ajoute à chaque évolution réglementaire (on ne modifie pas l'historique).
* ``BaremeIR`` / ``TrancheIR`` (PAIE4) — barème de l'Impôt sur le Revenu
  VERSIONNÉ par société et par ``date_effet`` : chaque barème porte ses tranches
  (borne min/max, taux, somme à déduire) ordonnées.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Aucun comportement existant n'est modifié — ce
module est entièrement additif.
"""
from decimal import Decimal

from django.db import models

from core.crypto_fields import EncryptedCharField


# ── PAIE2 — Paramètres sociaux versionnés ──────────────────────────────────

class ParametrePaie(models.Model):
    """Constantes sociales d'une société à une ``date_effet`` donnée.

    Versionné : un jeu par date d'effet (SMIG/SMAG, plafond & taux CNSS/AMO,
    taux de formation professionnelle, frais professionnels et — PAIE5 —
    déduction pour charges de famille). L'historique est immuable — un nouveau
    barème réglementaire crée une nouvelle ligne, jamais une modification.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_parametres',
        verbose_name='Société',
    )
    date_effet = models.DateField(verbose_name="Date d'effet")
    smig = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='SMIG')
    smag = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='SMAG')
    plafond_cnss = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('6000'),
        verbose_name='Plafond CNSS')
    taux_cnss_salarial = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('4.48'),
        verbose_name='Taux CNSS salarial')
    taux_cnss_patronal = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('8.98'),
        verbose_name='Taux CNSS patronal')
    taux_amo_salarial = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('2.26'),
        verbose_name='Taux AMO salarial')
    taux_amo_patronal = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('2.26'),
        verbose_name='Taux AMO patronal')
    # PAIE23 — Allocations familiales (prestations familiales CNSS) : charge
    # PATRONALE NON PLAFONNÉE sur le brut, ~6,4 % au cadre marocain. C'est un
    # coût employeur informatif — il n'est JAMAIS déduit du net du salarié.
    # Valeur éditable par société.
    taux_allocations_familiales = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('6.4'),
        verbose_name='Taux allocations familiales (patronal)')
    taux_formation_pro = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('1.6'),
        verbose_name='Taux formation professionnelle')
    # Frais professionnels (déduction IR) — barème 2026 : 35 % plafonné à
    # 2 500 MAD/mois quand le brut imposable n'excède pas 6 500 MAD/mois,
    # sinon 25 % plafonné à 2 916,67 MAD/mois.
    taux_frais_pro_bas = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('35'),
        verbose_name='Taux frais professionnels (brut ≤ seuil)')
    plafond_frais_pro_bas = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('2500'),
        verbose_name='Plafond frais professionnels (brut ≤ seuil)')
    taux_frais_pro_haut = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('25'),
        verbose_name='Taux frais professionnels (brut > seuil)')
    plafond_frais_pro_haut = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('2916.67'),
        verbose_name='Plafond frais professionnels (brut > seuil)')
    seuil_frais_pro = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('6500'),
        verbose_name='Seuil brut frais professionnels')
    # PAIE5 — Déduction pour charges de famille (déduction sur l'IR).
    # Cadre social marocain : un montant fixe par personne à charge et par mois,
    # plafonné à un nombre maximal de personnes (barème courant ≈ 30 MAD/mois et
    # par personne, plafond 6 → 360 MAD/mois). Valeurs ÉDITABLES par le fondateur.
    deduction_par_personne_a_charge = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('30'),
        verbose_name='Déduction mensuelle par personne à charge')
    plafond_personnes_a_charge = models.PositiveIntegerField(
        default=6,
        verbose_name='Plafond du nombre de personnes à charge')
    # PAIE14 — Taux de majoration des heures supplémentaires (cadre marocain).
    # 25 % : HS de jour (semaine normale) ; 50 % : HS de nuit ;
    # 100 % : HS de jour férié ou dimanche.
    # Valeurs réglementaires marocaines ; éditables par société.
    taux_hs_jour = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('25'),
        verbose_name='Majoration HS jour (%)')
    taux_hs_nuit = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('50'),
        verbose_name='Majoration HS nuit (%)')
    taux_hs_ferie = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('100'),
        verbose_name='Majoration HS férié/dimanche (%)')
    # PAIE15 — Barème d'ancienneté (prime d'ancienneté marocaine).
    # Barème standard : 5 % après 2 ans, 10 % après 5 ans, 15 % après 12 ans,
    # 20 % après 20 ans, 25 % après 25 ans. Exprimés en années (seuils)
    # et en pourcentage (taux). Éditables par société.
    anciennete_seuil_1 = models.PositiveSmallIntegerField(
        default=2, verbose_name="Ancienneté seuil 1 (années)")
    anciennete_taux_1 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('5'),
        verbose_name="Taux ancienneté seuil 1 (%)")
    anciennete_seuil_2 = models.PositiveSmallIntegerField(
        default=5, verbose_name="Ancienneté seuil 2 (années)")
    anciennete_taux_2 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('10'),
        verbose_name="Taux ancienneté seuil 2 (%)")
    anciennete_seuil_3 = models.PositiveSmallIntegerField(
        default=12, verbose_name="Ancienneté seuil 3 (années)")
    anciennete_taux_3 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('15'),
        verbose_name="Taux ancienneté seuil 3 (%)")
    anciennete_seuil_4 = models.PositiveSmallIntegerField(
        default=20, verbose_name="Ancienneté seuil 4 (années)")
    anciennete_taux_4 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('20'),
        verbose_name="Taux ancienneté seuil 4 (%)")
    anciennete_seuil_5 = models.PositiveSmallIntegerField(
        default=25, verbose_name="Ancienneté seuil 5 (années)")
    anciennete_taux_5 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('25'),
        verbose_name="Taux ancienneté seuil 5 (%)")
    # XPAI1 — Solde de tout compte (STC) : plafond d'exonération IR de
    # l'indemnité légale de licenciement/départ (barème art. 53 du Code du
    # travail). Valeur ÉDITABLE par société ; défaut LF courant 1 000 000 MAD.
    plafond_exoneration_ir_indemnite_licenciement = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('1000000'),
        verbose_name="Plafond exonération IR indemnité de licenciement")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # PAIE3 — Validation fondateur des valeurs légales par défaut. Les valeurs
    # 2026 sont préremplies par le seed mais restent ÉDITABLES ; tant que le
    # fondateur ne les a pas confirmées, ce drapeau reste False.
    valide_par_fondateur = models.BooleanField(
        default=False, verbose_name='Validé par le fondateur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Paramètre de paie'
        verbose_name_plural = 'Paramètres de paie'
        ordering = ['-date_effet']
        unique_together = [('company', 'date_effet')]

    def __str__(self):
        return f'Paramètres paie {self.date_effet}'


# ── PAIE4 — Barème IR versionné ────────────────────────────────────────────

class BaremeIR(models.Model):
    """Barème de l'Impôt sur le Revenu d'une société à une ``date_effet``.

    Versionné : chaque barème porte ses ``TrancheIR`` (cf. ``tranches``). Le
    barème en vigueur est celui dont la ``date_effet`` est la plus récente et
    qui couvre la période de paie.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_baremes_ir',
        verbose_name='Société',
    )
    libelle = models.CharField(
        max_length=120, default='Barème IR', verbose_name='Libellé')
    date_effet = models.DateField(verbose_name="Date d'effet")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # PAIE3 — barème officiel 2026 préprovisionné par le seed, éditable, en
    # attente de confirmation explicite du fondateur.
    valide_par_fondateur = models.BooleanField(
        default=False, verbose_name='Validé par le fondateur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Barème IR'
        verbose_name_plural = 'Barèmes IR'
        ordering = ['-date_effet']
        unique_together = [('company', 'date_effet')]

    def __str__(self):
        return f'{self.libelle} {self.date_effet}'


# ── PAIE6 — Rubrique de paie paramétrable ──────────────────────────────────

class Rubrique(models.Model):
    """Ligne de bulletin de paie PARAMÉTRABLE (catalogue, scopé société).

    Chaque rubrique est une ligne configurable du bulletin : un ``code`` court,
    un ``libelle``, un ``type`` (gain / retenue / cotisation) et les drapeaux
    fiscaux/sociaux qui pilotent l'assiette de calcul :

    * ``imposable`` — entre dans la base de l'IR ;
    * ``soumis_cnss`` — entre dans l'assiette CNSS ;
    * ``soumis_amo`` — entre dans l'assiette AMO ;
    * ``soumis_cimr`` — entre dans l'assiette CIMR.

    Le mode de calcul est laissé ouvert : soit un ``montant_fixe`` (montant
    constant), soit un couple ``base``/``taux`` (assiette × taux %). ``compte``
    est le code de compte comptable optionnel pour l'imputation. ``ordre`` fixe
    l'ordre d'affichage sur le bulletin ; ``actif`` permet d'archiver une
    rubrique sans la supprimer.

    Multi-société : ``company`` est posée côté serveur. Le couple
    ``(company, code)`` est unique. Modèle purement additif : aucun calcul de
    paie existant n'en dépend encore.
    """
    TYPE_GAIN = 'gain'
    TYPE_RETENUE = 'retenue'
    TYPE_COTISATION = 'cotisation'
    TYPE_CHOICES = [
        (TYPE_GAIN, 'Gain'),
        (TYPE_RETENUE, 'Retenue'),
        (TYPE_COTISATION, 'Cotisation'),
    ]

    BASE_BRUT = 'brut'
    BASE_BRUT_IMPOSABLE = 'brut_imposable'
    BASE_NET_IMPOSABLE = 'net_imposable'
    BASE_PLAFONNEE_CNSS = 'plafonnee_cnss'
    BASE_AUTRE = 'autre'
    BASE_CHOICES = [
        (BASE_BRUT, 'Brut'),
        (BASE_BRUT_IMPOSABLE, 'Brut imposable'),
        (BASE_NET_IMPOSABLE, 'Net imposable'),
        (BASE_PLAFONNEE_CNSS, 'Assiette plafonnée CNSS'),
        (BASE_AUTRE, 'Autre / manuelle'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_rubriques',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    type = models.CharField(
        max_length=12, choices=TYPE_CHOICES, default=TYPE_GAIN,
        verbose_name='Type')
    imposable = models.BooleanField(
        default=False, verbose_name='Imposable (IR)')
    soumis_cnss = models.BooleanField(
        default=False, verbose_name='Soumis CNSS')
    soumis_amo = models.BooleanField(
        default=False, verbose_name='Soumis AMO')
    soumis_cimr = models.BooleanField(
        default=False, verbose_name='Soumis CIMR')
    # PAIE16 — Avantages en nature & indemnités : imposable vs non-imposable
    # dans la limite d'un plafond. Beaucoup d'indemnités/avantages marocains
    # (transport, panier, déplacement, logement, voiture de fonction…) sont
    # EXONÉRÉS d'IR (et souvent de CNSS/AMO) tant que leur montant mensuel reste
    # SOUS un plafond réglementaire ; la fraction qui EXCÈDE le plafond est
    # réintégrée dans la base imposable (et dans l'assiette CNSS/AMO si la
    # rubrique est soumise). ``avantage_nature`` distingue un avantage en nature
    # (logé/nourri/voiture) d'une indemnité en numéraire — purement informatif.
    avantage_nature = models.BooleanField(
        default=False, verbose_name='Avantage en nature')
    # Plafond mensuel d'exonération. ``None`` (défaut) = pas de plafond
    # spécifique : la rubrique est entièrement imposable ou entièrement exonérée
    # selon son drapeau ``imposable`` (comportement historique inchangé). Une
    # valeur renseignée active le régime « exonéré jusqu'au plafond, excédent
    # imposable ».
    plafond_exoneration = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name="Plafond mensuel d'exonération")
    compte = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Compte comptable')
    # Mode de calcul : montant fixe OU base × taux. Les deux peuvent rester nuls
    # (rubrique à saisie manuelle sur le bulletin).
    base = models.CharField(
        max_length=20, choices=BASE_CHOICES, default=BASE_BRUT,
        verbose_name='Assiette')
    taux = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name='Taux (%)')
    montant_fixe = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant fixe')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # ZPAI3 — pilote l'inclusion de cette rubrique de COTISATION PATRONALE
    # dans le rapport « coût employeur » consolidé (``services.cout_employeur``).
    # Par défaut vrai pour une cotisation (comportement historique inchangé :
    # toutes les cotisations patronales connues entrent dans le total) ; un
    # gain/une retenue n'entre jamais dans ce total (le drapeau est ignoré
    # pour ces types). Dé-flagger une rubrique la sort de l'agrégat SANS
    # toucher au calcul du bulletin lui-même (jamais client-facing).
    apparait_cout_employeur = models.BooleanField(
        default=True, verbose_name='Apparaît au coût employeur')
    # ZPAI8 — Règle d'arrondi des jours/heures pour une rubrique d'ABSENCE
    # (façon Odoo « Display in Payslip » : pas d'arrondi / demi-journée /
    # journée). Ignoré pour toute rubrique qui n'est pas rattachée à un
    # ``ElementVariable`` de type ``absence``. ``aucun`` (défaut) = comportement
    # historique inchangé (quantité brute, sans arrondi).
    ARRONDI_AUCUN = 'aucun'
    ARRONDI_DEMI_JOURNEE = 'demi_journee'
    ARRONDI_JOURNEE = 'journee'
    ARRONDI_CHOICES = [
        (ARRONDI_AUCUN, 'Aucun'),
        (ARRONDI_DEMI_JOURNEE, 'Demi-journée'),
        (ARRONDI_JOURNEE, 'Journée'),
    ]
    SENS_SUP = 'sup'
    SENS_INF = 'inf'
    SENS_CHOICES = [
        (SENS_SUP, 'Arrondi supérieur'),
        (SENS_INF, 'Arrondi inférieur'),
    ]
    arrondi = models.CharField(
        max_length=13, choices=ARRONDI_CHOICES, default=ARRONDI_AUCUN,
        blank=True, verbose_name="Arrondi (jours d'absence)")
    sens_arrondi = models.CharField(
        max_length=3, choices=SENS_CHOICES, default=SENS_SUP,
        blank=True, verbose_name='Sens de l\'arrondi')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rubrique de paie'
        verbose_name_plural = 'Rubriques de paie'
        ordering = ['ordre', 'code']
        unique_together = [('company', 'code')]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class TrancheIR(models.Model):
    """Tranche d'un ``BaremeIR`` : intervalle de revenu, taux, somme à déduire.

    Le barème mensuel se calcule par tranche : pour un revenu net imposable, on
    applique le ``taux`` de la tranche couvrante puis on retranche
    ``somme_a_deduire`` (formule par tranche du barème marocain).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_tranches_ir',
        verbose_name='Société',
    )
    bareme = models.ForeignKey(
        BaremeIR,
        on_delete=models.CASCADE,
        related_name='tranches',
        verbose_name='Barème',
    )
    borne_min = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Borne minimale')
    borne_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Borne maximale')
    taux = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0'),
        verbose_name='Taux')
    somme_a_deduire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Somme à déduire')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = "Tranche IR"
        verbose_name_plural = "Tranches IR"
        ordering = ['ordre']

    def __str__(self):
        return f'{self.borne_min}–{self.borne_max} @ {self.taux}%'


# ── PAIE8 — Profil de paie de l'employé ────────────────────────────────────

class ProfilPaie(models.Model):
    """Profil de paie d'un employé (PAIE8) — ``OneToOne`` vers le dossier RH.

    Porte les paramètres de paie propres à un collaborateur, distincts de sa
    fiche RH : le ``type_remuneration`` (mensuel / journalier / forfait /
    horaire), le ``salaire_base`` (selon le type), les affiliations sociales
    (CNSS / AMO / CIMR avec leurs numéros) et le ``rib`` de virement.

    Relié au dossier RH par une chaîne de FK (``rh.DossierEmploye``) — la paie
    ne lit JAMAIS les modèles de ``rh`` directement ; le rapprochement passe par
    ``apps.rh.selectors``. ``OneToOne`` : un employé n'a qu'un profil de paie.

    Multi-société : ``company`` posée côté serveur. Le ``salaire_base`` est une
    donnée SENSIBLE (palier paie), jamais exposée côté client.
    """
    TYPE_MENSUEL = 'mensuel'
    TYPE_JOURNALIER = 'journalier'
    TYPE_FORFAIT = 'forfait'
    TYPE_HORAIRE = 'horaire'
    TYPE_REMUNERATION_CHOICES = [
        (TYPE_MENSUEL, 'Mensuel'),
        (TYPE_JOURNALIER, 'Journalier'),
        (TYPE_FORFAIT, 'Forfait'),
        (TYPE_HORAIRE, 'Horaire'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_profils',
        verbose_name='Société',
    )
    employe = models.OneToOneField(
        'rh.DossierEmploye',
        on_delete=models.CASCADE,
        related_name='profil_paie',
        verbose_name='Dossier employé',
    )
    type_remuneration = models.CharField(
        max_length=12, choices=TYPE_REMUNERATION_CHOICES, default=TYPE_MENSUEL,
        verbose_name='Type de rémunération')
    salaire_base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Salaire de base')
    # Affiliations sociales (Maroc).
    affilie_cnss = models.BooleanField(
        default=True, verbose_name='Affilié CNSS')
    affilie_amo = models.BooleanField(
        default=True, verbose_name='Affilié AMO')
    affilie_cimr = models.BooleanField(
        default=False, verbose_name='Affilié CIMR')
    taux_cimr_salarial = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal('0'),
        verbose_name='Taux CIMR salarial')
    numero_cnss = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='N° CNSS')
    numero_amo = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='N° AMO')
    numero_cimr = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='N° CIMR')
    # PAIE13 — Normes de travail du profil, utilisées pour la proration.
    # Pour le type JOURNALIER : salaire_base est le taux journalier ; le brut
    # est taux × jours effectivement travaillés (ElementVariable.TYPE_HEURES /
    # TYPE_ABSENCE sont convertis en jours). Pour le type HORAIRE : salaire_base
    # est le taux horaire ; le brut est taux × heures effectivement travaillées.
    # Pour MENSUEL et FORFAIT : salaire_base est utilisé tel quel (mensuel peut
    # néanmoins être proraté quand l'employé ne couvre pas le mois complet — la
    # proratisation compare les jours travaillés aux jours contractuels du mois).
    # Ces normes sont éditables par employé ; les défauts 26 j / 191 h
    # correspondent au cadre marocain standard (169 h réglementaires ≈ 191 h
    # pratiques entreprise ; 26 jours ouvrables par mois en moyenne).
    jours_travail_mensuel = models.PositiveSmallIntegerField(
        default=26, verbose_name='Jours de travail par mois (norme)')
    heures_travail_mensuel = models.PositiveSmallIntegerField(
        default=191, verbose_name='Heures de travail par mois (norme)')
    rib = EncryptedCharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    banque = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Banque')
    # XPAI9 — Mode de paiement du salarié. ``virement`` (défaut, comportement
    # historique — seul mode couvert jusqu'ici) entre dans l'ordre de
    # virement (PAIE30) ; ``cheque``/``especes`` en sont EXCLUS (listés à
    # part) — un profil espèces/chèque est réglé hors virement.
    MODE_PAIEMENT_VIREMENT = 'virement'
    MODE_PAIEMENT_CHEQUE = 'cheque'
    MODE_PAIEMENT_ESPECES = 'especes'
    MODE_PAIEMENT_CHOICES = [
        (MODE_PAIEMENT_VIREMENT, 'Virement'),
        (MODE_PAIEMENT_CHEQUE, 'Chèque'),
        (MODE_PAIEMENT_ESPECES, 'Espèces'),
    ]
    mode_paiement = models.CharField(
        max_length=10, choices=MODE_PAIEMENT_CHOICES,
        default=MODE_PAIEMENT_VIREMENT, verbose_name='Mode de paiement')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # XPAI24 — Structure de paie appliquée à la création (gabarit de
    # rubriques par catégorie). Informatif : aucun lien vivant après
    # application, les rubriques copiées restent modifiables librement.
    structure = models.ForeignKey(
        'StructurePaie',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='profils',
        verbose_name='Structure de paie appliquée',
    )
    # XPAI18 — Régime d'exonération IR (stagiaire / ANAPEC / TAHFIZ), fenêtre
    # d'éligibilité et plafond mensuel exonéré. ``REGIME_AUCUN`` (défaut) =
    # comportement historique inchangé (aucune exonération). La bascule
    # automatique au régime normal à l'expiration est faite par
    # ``services.expirer_regimes_echus`` (jamais en lecture — un cron/action).
    REGIME_AUCUN = 'aucun'
    REGIME_STAGIAIRE = 'stagiaire'
    REGIME_ANAPEC = 'anapec'
    REGIME_TAHFIZ = 'tahfiz'
    REGIME_EXONERATION_CHOICES = [
        (REGIME_AUCUN, 'Aucun'),
        (REGIME_STAGIAIRE, 'Stagiaire'),
        (REGIME_ANAPEC, 'ANAPEC'),
        (REGIME_TAHFIZ, 'TAHFIZ'),
    ]
    regime_exoneration = models.CharField(
        max_length=10, choices=REGIME_EXONERATION_CHOICES,
        default=REGIME_AUCUN, verbose_name="Régime d'exonération IR")
    regime_date_debut = models.DateField(
        null=True, blank=True, verbose_name="Régime — date de début")
    regime_date_fin = models.DateField(
        null=True, blank=True, verbose_name="Régime — date de fin (fenêtre)")
    regime_plafond_mensuel = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('6000'),
        verbose_name="Régime — plafond mensuel exonéré")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Profil de paie'
        verbose_name_plural = 'Profils de paie'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Profil paie #{self.employe_id} ({self.type_remuneration})'


# ── XPAI3 — Mutuelle / prévoyance / assurance groupe ────────────────────────

class RegimeMutuelle(models.Model):
    """Régime de mutuelle/prévoyance/assurance groupe (XPAI3), company-scoped.

    Catalogue des régimes proposés par l'employeur (AMO complémentaire,
    prévoyance, assurance groupe…) : part salariale et part patronale — en
    POURCENTAGE (d'une base, typiquement le brut) ou en MONTANT FIXE — un
    palier CÉLIBATAIRE ou FAMILLE, et le drapeau ``deductible_net_imposable``
    qui pilote si la part salariale se déduit du net imposable AVANT IR
    (cadre marocain : les cotisations de prévoyance/mutuelle complémentaire
    collective sont déductibles sous conditions).

    Multi-société : ``company`` posée côté serveur.
    """
    MODE_POURCENTAGE = 'pourcentage'
    MODE_FIXE = 'fixe'
    MODE_CHOICES = [
        (MODE_POURCENTAGE, 'Pourcentage'),
        (MODE_FIXE, 'Montant fixe'),
    ]

    PALIER_CELIBATAIRE = 'celibataire'
    PALIER_FAMILLE = 'famille'
    PALIER_CHOICES = [
        (PALIER_CELIBATAIRE, 'Célibataire'),
        (PALIER_FAMILLE, 'Famille'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_regimes_mutuelle',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    mode = models.CharField(
        max_length=12, choices=MODE_CHOICES, default=MODE_POURCENTAGE,
        verbose_name='Mode de calcul')
    palier = models.CharField(
        max_length=12, choices=PALIER_CHOICES, default=PALIER_CELIBATAIRE,
        verbose_name='Palier')
    part_salariale = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0'),
        verbose_name='Part salariale (% ou montant)')
    part_patronale = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0'),
        verbose_name='Part patronale (% ou montant)')
    deductible_net_imposable = models.BooleanField(
        default=True,
        verbose_name='Déductible du net imposable (part salariale)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Régime de mutuelle'
        verbose_name_plural = 'Régimes de mutuelle'
        ordering = ['libelle']

    def __str__(self):
        return f'{self.libelle} ({self.get_palier_display()})'


class AdhesionMutuelle(models.Model):
    """Adhésion d'un ``ProfilPaie`` à un ``RegimeMutuelle`` (XPAI3).

    ``OneToOne`` vers ``ProfilPaie`` : un employé n'a qu'une adhésion active à
    la fois (changer de régime remplace l'adhésion, jamais de cumul). Porte la
    ``date_debut`` d'affiliation. Multi-société : ``company`` posée côté
    serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_adhesions_mutuelle',
        verbose_name='Société',
    )
    profil = models.OneToOneField(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='adhesion_mutuelle',
        verbose_name='Profil de paie',
    )
    regime = models.ForeignKey(
        RegimeMutuelle,
        on_delete=models.PROTECT,
        related_name='adhesions',
        verbose_name='Régime',
    )
    date_debut = models.DateField(verbose_name="Date d'adhésion")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Adhésion mutuelle'
        verbose_name_plural = 'Adhésions mutuelle'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.regime.libelle} → profil #{self.profil_id}'


# ── PAIE9 — Rubriques récurrentes par employé ──────────────────────────────

class RubriqueEmploye(models.Model):
    """Rubrique RÉCURRENTE rattachée à un profil de paie (PAIE9).

    Une rubrique du catalogue (``Rubrique``) appliquée systématiquement à un
    employé chaque mois : prime de transport, indemnité de panier, prime
    d'ancienneté, etc. Porte une surcharge optionnelle du ``montant`` ou du
    ``taux`` (sinon le calcul retombe sur la définition de la rubrique).

    ``actif`` permet de suspendre une rubrique récurrente sans la supprimer ;
    ``date_debut`` / ``date_fin`` bornent sa période d'application (facultatif).
    Multi-société : ``company`` posée côté serveur. Le couple
    ``(profil, rubrique)`` est unique — une rubrique n'est rattachée qu'une fois
    par employé.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_rubriques_employe',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='rubriques',
        verbose_name='Profil de paie',
    )
    rubrique = models.ForeignKey(
        Rubrique,
        on_delete=models.PROTECT,
        related_name='rattachements',
        verbose_name='Rubrique',
    )
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant (surcharge)')
    taux = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name='Taux % (surcharge)')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rubrique employé'
        verbose_name_plural = 'Rubriques employé'
        ordering = ['rubrique__ordre', 'id']
        unique_together = [('profil', 'rubrique')]

    def __str__(self):
        return f'{self.rubrique.code} → profil #{self.profil_id}'


# ── PAIE10 — Période de paie (run mensuel) ─────────────────────────────────

class PeriodePaie(models.Model):
    """Run de paie d'un mois donné (PAIE10) — cycle de statuts.

    Une période est un couple ``(annee, mois)`` par société, qui passe par les
    statuts :

    * ``brouillon`` — ouverte, éléments variables saisissables ;
    * ``calculee`` — bulletins calculés (snapshot) ;
    * ``validee`` — validée par le responsable paie ;
    * ``cloturee`` — figée définitivement (plus aucune modification).

    Le cycle est strictement progressif (``services.changer_statut`` interdit un
    retour en arrière). Multi-société : ``company`` posée côté serveur. Le couple
    ``(company, annee, mois)`` est unique.
    """
    STATUT_BROUILLON = 'brouillon'
    STATUT_CALCULEE = 'calculee'
    STATUT_VALIDEE = 'validee'
    STATUT_CLOTUREE = 'cloturee'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_CALCULEE, 'Calculée'),
        (STATUT_VALIDEE, 'Validée'),
        (STATUT_CLOTUREE, 'Clôturée'),
    ]
    # Ordre du cycle — un statut ne peut qu'AVANCER.
    ORDRE_STATUTS = [
        STATUT_BROUILLON, STATUT_CALCULEE, STATUT_VALIDEE, STATUT_CLOTUREE,
    ]

    # XPAI4 — Nature du run. ``mensuel`` (défaut, comportement historique) est
    # le cycle mensuel normal ; ``hors_cycle`` est un run INDÉPENDANT du mois
    # calendaire (13e mois/gratification, rappel de masse…) : peut coexister
    # avec le run mensuel du même (année, mois) — le couple unique
    # ``(company, annee, mois)`` ci-dessous est donc étendu à ``type_run``.
    TYPE_RUN_MENSUEL = 'mensuel'
    TYPE_RUN_HORS_CYCLE = 'hors_cycle'
    TYPE_RUN_CHOICES = [
        (TYPE_RUN_MENSUEL, 'Mensuel'),
        (TYPE_RUN_HORS_CYCLE, 'Hors-cycle (prime/rappel)'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_periodes',
        verbose_name='Société',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois')
    type_run = models.CharField(
        max_length=12, choices=TYPE_RUN_CHOICES, default=TYPE_RUN_MENSUEL,
        verbose_name='Type de run')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    statut = models.CharField(
        max_length=12, choices=STATUT_CHOICES, default=STATUT_BROUILLON,
        verbose_name='Statut')
    date_paiement = models.DateField(
        null=True, blank=True, verbose_name='Date de paiement')
    date_cloture = models.DateTimeField(
        null=True, blank=True, verbose_name='Clôturée le')
    # ZPAI12 — Marqueur d'idempotence de l'alerte de clôture en retard (façon
    # ``EcheanceDeclarative.date_notification``, XPAI6) : posé UNE SEULE FOIS
    # par ``services.notifier_cloture_en_retard`` — un re-run le lendemain ne
    # renotifie jamais la même période.
    date_alerte_cloture_retard = models.DateTimeField(
        null=True, blank=True, verbose_name='Alerte de clôture en retard envoyée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Période de paie'
        verbose_name_plural = 'Périodes de paie'
        ordering = ['-annee', '-mois']
        # XPAI4 — ``type_run`` étend l'unicité : un run hors-cycle (13e mois)
        # peut coexister avec le run mensuel du même (année, mois).
        unique_together = [('company', 'annee', 'mois', 'type_run')]

    def __str__(self):
        return f'Paie {self.mois:02d}/{self.annee} ({self.statut})'


# ── PAIE11 — Éléments variables du mois ────────────────────────────────────

class ElementVariable(models.Model):
    """Élément variable d'un employé pour une période (PAIE11).

    Saisie mensuelle qui varie d'un mois à l'autre : heures travaillées, heures
    supplémentaires, jours d'absence, primes ponctuelles, retenues. Importable
    depuis RH (heures/HS/absences) via ``services.importer_elements_rh`` — la
    paie ne lit jamais ``rh.models`` directement, le rapprochement passe par
    ``apps.rh.selectors``.

    Rattaché à une ``PeriodePaie`` et à un ``ProfilPaie``. ``type`` qualifie la
    nature de l'élément (heures, HS, absence, prime, retenue) ; ``rubrique`` est
    la rubrique catalogue associée (facultatif). ``quantite`` et ``montant``
    portent la valeur. ``source`` trace l'origine (saisie manuelle ou import RH).

    Multi-société : ``company`` posée côté serveur.
    """
    TYPE_HEURES = 'heures'
    TYPE_HS = 'heures_sup'
    TYPE_ABSENCE = 'absence'
    TYPE_PRIME = 'prime'
    TYPE_RETENUE = 'retenue'
    TYPE_CHOICES = [
        (TYPE_HEURES, 'Heures travaillées'),
        (TYPE_HS, 'Heures supplémentaires'),
        (TYPE_ABSENCE, 'Absence'),
        (TYPE_PRIME, 'Prime'),
        (TYPE_RETENUE, 'Retenue'),
    ]

    # PAIE14 — Catégorie des heures supplémentaires (utilisée uniquement quand
    # ``type == TYPE_HS``). Détermine le taux de majoration applicable.
    HS_JOUR = 'jour'      # Heures sup de jour (semaine) → +25 %
    HS_NUIT = 'nuit'      # Heures sup de nuit → +50 %
    HS_FERIE = 'ferie'    # Heures sup jour férié ou dimanche → +100 %
    HS_CATEGORIE_CHOICES = [
        (HS_JOUR, 'Heures sup de jour (25 %)'),
        (HS_NUIT, 'Heures sup de nuit (50 %)'),
        (HS_FERIE, 'Heures sup férié/dimanche (100 %)'),
    ]

    SOURCE_MANUEL = 'manuel'
    SOURCE_RH = 'rh'
    SOURCE_CHOICES = [
        (SOURCE_MANUEL, 'Saisie manuelle'),
        (SOURCE_RH, 'Import RH'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_elements_variables',
        verbose_name='Société',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='elements_variables',
        verbose_name='Période',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='elements_variables',
        verbose_name='Profil de paie',
    )
    type = models.CharField(
        max_length=12, choices=TYPE_CHOICES, default=TYPE_PRIME,
        verbose_name='Type')
    rubrique = models.ForeignKey(
        Rubrique,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='elements_variables',
        verbose_name='Rubrique',
    )
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    quantite = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Quantité')
    # PAIE14 — Catégorie HS : ``jour`` (25 %), ``nuit`` (50 %),
    # ``ferie`` (100 %). Ignoré si ``type != TYPE_HS``.
    # Blank/null = jour par défaut (la majoration s'applique quand même,
    # avec le taux « jour » du ParametrePaie de la société).
    categorie_hs = models.CharField(
        max_length=6,
        choices=HS_CATEGORIE_CHOICES,
        default=HS_JOUR,
        blank=True,
        verbose_name='Catégorie HS')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    # PAIE26 — Paiement & décompte des congés/absences. Pour un élément
    # ``TYPE_ABSENCE``, ``remunere`` distingue un congé PAYÉ (congé payé,
    # maladie indemnisée…) d'une absence NON rémunérée (sans solde, absence
    # injustifiée). Une absence rémunérée n'est NI déduite du salaire de base
    # proraté, NI portée en retenue : le salarié est payé comme s'il était
    # présent. Une absence non rémunérée (défaut) est décomptée comme aujourd'hui.
    # Ignoré pour les autres types d'élément.
    remunere = models.BooleanField(
        default=False, verbose_name='Absence rémunérée')
    # PAIE26 — Décompte du solde de congés. ``deduit_solde`` reprend la règle du
    # TypeAbsence RH (FG164) : si vrai, la quantité de jours est retranchée du
    # compteur de congés payés (informatif côté paie ; le décompte effectif du
    # solde reste géré par RH). Ignoré hors absence.
    deduit_solde = models.BooleanField(
        default=False, verbose_name='Déduit du solde de congés')
    # XPAI14 — Catégorie d'un arrêt CNSS (utilisée uniquement quand
    # ``type == TYPE_ABSENCE``). ``aucune`` (défaut) = absence ordinaire
    # (comportement historique inchangé). ``maladie``/``maternite`` marquent
    # un arrêt indemnisé par la CNSS : les jours sont neutralisés côté
    # salaire ET cotisations (comme toute absence ``remunere=False`` déduite
    # du salaire proraté), et déclenchent l'attestation de salaire CNSS
    # (dossier IJ, ``builders.render_attestation_ij_cnss_pdf``).
    ABSENCE_AUCUNE = 'aucune'
    ABSENCE_MALADIE_CNSS = 'maladie'
    ABSENCE_MATERNITE_CNSS = 'maternite'
    CATEGORIE_ABSENCE_CHOICES = [
        (ABSENCE_AUCUNE, 'Absence ordinaire'),
        (ABSENCE_MALADIE_CNSS, 'Arrêt CNSS — maladie'),
        (ABSENCE_MATERNITE_CNSS, 'Arrêt CNSS — maternité'),
    ]
    categorie_absence = models.CharField(
        max_length=10, choices=CATEGORIE_ABSENCE_CHOICES,
        default=ABSENCE_AUCUNE, blank=True,
        verbose_name='Catégorie d\'absence')
    # ZPAI9 — Type d'entrée ponctuelle du catalogue (facultatif). NULL
    # (défaut) = comportement historique inchangé, piloté uniquement par
    # ``type``/``categorie_hs``/``categorie_absence`` ci-dessus. Renseigné,
    # les drapeaux fiscaux/sociaux du type catalogue (``imposable``/
    # ``soumis_cnss``/``soumis_amo``) priment sur l'assiette par défaut de
    # cet élément dans ``calculer_bulletin``.
    type_entree = models.ForeignKey(
        'TypeEntreePonctuelle',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='elements_variables',
        verbose_name="Type d'entrée ponctuelle (catalogue)",
    )
    # ZPAI11 — Reconduction automatique vers la période suivante (défaut
    # False = comportement historique inchangé : ressaisie chaque mois). Un
    # élément ponctuel-mais-répétitif (ex. prime de transport saisie chaque
    # mois) marqué ``reconduire=True`` est copié UNE fois vers M+1 par
    # ``services.reporter_elements_periode`` — jamais automatiquement à la
    # création de l'élément lui-même.
    reconduire = models.BooleanField(
        default=False, verbose_name='Reconduire vers la période suivante')
    # ZPAI11 — Trace de reconduction : posé UNIQUEMENT sur la copie créée par
    # ``services.reporter_elements_periode`` (jamais sur l'original saisi à la
    # main). Sert de clé d'IDEMPOTENCE : un re-run de la reconduction ne
    # duplique jamais la copie d'un même élément d'origine vers la même
    # période cible (``unique_together`` ci-dessous).
    reconduit_depuis = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconductions',
        verbose_name='Reconduit depuis (élément M-1)',
    )
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUEL,
        verbose_name='Source')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Élément variable'
        verbose_name_plural = 'Éléments variables'
        ordering = ['periode', 'profil', 'id']
        # ZPAI11 — une même origine ne peut être reconduite qu'UNE fois vers
        # une période cible donnée (NULL ``reconduit_depuis`` = saisie
        # normale, jamais concerné par cette contrainte).
        unique_together = [('periode', 'reconduit_depuis')]

    def __str__(self):
        return f'{self.get_type_display()} {self.quantite} → profil #{self.profil_id}'


# ── PAIE17 — Bulletin de paie (snapshot immuable une fois validé) ───────────

class BulletinPaie(models.Model):
    """Bulletin de paie d'un employé pour une période (PAIE17).

    SNAPSHOT figé du calcul (``services.calculer_bulletin``) : tous les montants
    sont MATÉRIALISÉS au moment de la génération (brut, cotisations salariales &
    patronales, frais pro, net imposable, IR, net à payer…). Le détail des lignes
    vit dans ``LigneBulletin`` (cf. ``lignes``).

    IMMUTABILITÉ — une fois ``statut == 'valide'``, le bulletin et ses lignes sont
    GELÉS : aucune modification de montant n'est plus possible, et le bulletin ne
    peut être ni supprimé ni recalculé. Tant qu'il est ``'brouillon'``, il peut
    être recalculé (régénéré) librement. Le passage ``brouillon → valide`` est la
    seule transition autorisée (irréversible). Cette garde est posée dans
    ``save``/``delete`` ci-dessous ET dans ``services`` — elle ne dépend donc pas
    de la couche API.

    Multi-société : ``company`` posée côté serveur. Le couple
    ``(periode, profil)`` est unique — un seul bulletin par employé et par
    période. Donnée SENSIBLE (salaires) — usage interne paie uniquement.
    """
    STATUT_BROUILLON = 'brouillon'
    STATUT_VALIDE = 'valide'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_VALIDE, 'Validé'),
    ]

    # PAIE36 — Nature du bulletin : normal, RECTIFICATIF (corrige un bulletin
    # déjà validé/clôturé, qui reste figé) ou RAPPEL (régularisation/rattrapage
    # d'un mois antérieur sur un mois courant).
    # XPAI1 — STC (solde de tout compte) : bulletin de sortie d'un employé,
    # calculé une seule fois (dernier salaire proraté + indemnités de
    # licenciement/préavis/congés non pris − avances/saisies en cours).
    TYPE_NORMAL = 'normal'
    TYPE_RECTIFICATIF = 'rectificatif'
    TYPE_RAPPEL = 'rappel'
    TYPE_STC = 'stc'
    # XPAI4 — Bulletin de run hors-cycle (13e mois / prime de bilan), généré
    # sur une ``PeriodePaie`` de ``type_run == TYPE_RUN_HORS_CYCLE``.
    TYPE_GRATIFICATION = 'gratification'
    # ZPAI4 — Bulletin d'ANNULATION (refund payslip) : contrepartie à montants
    # NÉGATIFS d'un bulletin déjà traité, distincte du RECTIFICATIF qui
    # remplace. Sert à extourner proprement un bulletin (cumul annuel/9421).
    TYPE_ANNULATION = 'annulation'
    TYPE_BULLETIN_CHOICES = [
        (TYPE_NORMAL, 'Normal'),
        (TYPE_RECTIFICATIF, 'Rectificatif'),
        (TYPE_RAPPEL, 'Rappel'),
        (TYPE_STC, 'Solde de tout compte'),
        (TYPE_GRATIFICATION, '13e mois / gratification'),
        (TYPE_ANNULATION, "Annulation (extourne)"),
    ]

    # Champs de montant figés au moment du calcul (snapshot). Modifiables tant
    # que le bulletin est en brouillon, gelés dès la validation.
    SNAPSHOT_FIELDS = [
        'brut', 'brut_imposable', 'cnss_salariale', 'cnss_patronale',
        'amo_salariale', 'amo_patronale', 'allocations_familiales',
        'formation_professionnelle',
        'cimr_salariale', 'frais_professionnels', 'net_imposable', 'ir',
        'retenues', 'prime_anciennete', 'charges_patronales', 'net_a_payer',
        'personnes_a_charge', 'provision_conges', 'montant_exonere_regime',
    ]

    class BulletinVerrouille(Exception):
        """Tentative de modification/suppression d'un bulletin validé (figé)."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_bulletins',
        verbose_name='Société',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='bulletins',
        verbose_name='Période',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='bulletins',
        verbose_name='Profil de paie',
    )
    statut = models.CharField(
        max_length=12, choices=STATUT_CHOICES, default=STATUT_BROUILLON,
        verbose_name='Statut')
    # PAIE36 — Nature du bulletin + lien vers le bulletin d'origine corrigé.
    type_bulletin = models.CharField(
        max_length=14, choices=TYPE_BULLETIN_CHOICES, default=TYPE_NORMAL,
        verbose_name='Nature du bulletin')
    rectifie = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rectifications',
        verbose_name="Bulletin d'origine corrigé",
    )
    motif = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Motif (rectificatif / rappel)')
    personnes_a_charge = models.PositiveSmallIntegerField(
        default=0, verbose_name='Personnes à charge')
    # ── Snapshot des montants (Decimal au centime) ─────────────────────────
    brut = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Brut')
    brut_imposable = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Brut imposable')
    cnss_salariale = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='CNSS salariale')
    cnss_patronale = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='CNSS patronale')
    amo_salariale = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='AMO salariale')
    amo_patronale = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='AMO patronale')
    # PAIE23 — Allocations familiales (charge patronale, informative — jamais
    # déduite du net du salarié).
    allocations_familiales = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Allocations familiales (patronal)')
    # PAIE24 — Taxe de formation professionnelle (1,6 % patronal, collectée avec
    # la CNSS) : charge employeur informative — jamais déduite du net du salarié.
    formation_professionnelle = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Formation professionnelle (patronal)')
    # PAIE25 — Provision pour congés payés : charge PATRONALE informative
    # (engagement social) constituée chaque mois sur la base des jours de CP
    # acquis dans le mois × le taux journalier du salarié. N'est JAMAIS déduite
    # du net du salarié — c'est une provision comptable employeur.
    provision_conges = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Provision congés payés (patronal)')
    cimr_salariale = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='CIMR salariale')
    frais_professionnels = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Frais professionnels')
    net_imposable = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Net imposable')
    ir = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='IR')
    # XPAI18 — Montant EXONÉRÉ d'IR au titre du régime stagiaire/ANAPEC/TAHFIZ
    # du profil (fraction du net imposable sous le plafond mensuel, dans la
    # fenêtre d'éligibilité). 0 par défaut (régime normal). Tracé pour le 9421.
    montant_exonere_regime = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name="Montant exonéré (régime stagiaire/ANAPEC/TAHFIZ)")
    retenues = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Retenues')
    prime_anciennete = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name="Prime d'ancienneté")
    charges_patronales = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Charges patronales')
    net_a_payer = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Net à payer')
    date_validation = models.DateTimeField(
        null=True, blank=True, verbose_name='Validé le')
    # XPAI9 — Statut de décompte du paiement, horodaté. Distinct de
    # ``statut`` (brouillon/valide — le CALCUL) : ``paye`` trace que le
    # salarié a EFFECTIVEMENT reçu son net (virement exécuté, chèque remis,
    # espèces décomptées) — jamais posé automatiquement par le calcul.
    paye = models.BooleanField(default=False, verbose_name='Payé')
    date_paiement = models.DateTimeField(
        null=True, blank=True, verbose_name='Payé le')
    # XPAI21 — Accusé de lecture (coffre-fort employé, PAIE35) : horodate la
    # PREMIÈRE consultation du bulletin par le salarié. Posé une seule fois
    # (jamais réécrit — cf. ``_CHAMPS_AUTORISES_APRES_VALIDATION`` ci-dessous
    # et la garde côté service ``marquer_bulletin_lu``).
    lu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Lu le (accusé de lecture)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bulletin de paie'
        verbose_name_plural = 'Bulletins de paie'
        ordering = ['-date_creation']
        unique_together = [('periode', 'profil')]

    def __str__(self):
        return f'Bulletin #{self.profil_id} {self.periode} ({self.statut})'

    @property
    def est_valide(self):
        """Vrai quand le bulletin est figé (validé)."""
        return self.statut == self.STATUT_VALIDE

    # Champs dont l'écriture reste autorisée sur un bulletin déjà VALIDÉ
    # (PAIE17) : la transition de validation elle-même (statut/
    # date_validation) et le suivi de paiement (XPAI9 — un bulletin est
    # toujours validé AVANT d'être payé, donc ``paye``/``date_paiement``
    # se posent forcément APRÈS le gel). ``lu_le`` (XPAI21) se pose de la
    # même façon, après coup, à la première consultation employé. Les
    # montants/lignes de paie restent, eux, strictement figés.
    _CHAMPS_AUTORISES_APRES_VALIDATION = frozenset(
        {'statut', 'date_validation', 'paye', 'date_paiement', 'lu_le'})

    def save(self, *args, **kwargs):
        """Garde d'immuabilité (PAIE17).

        Un bulletin déjà ``valide`` en base est FIGÉ pour ses montants/lignes :
        seules restent autorisées la transition de validation elle-même
        (``brouillon → valide``, qui pose ``date_validation``) et le suivi de
        paiement (``paye``/``date_paiement``, posés après coup par
        ``marquer_bulletin_paye``). Toute autre écriture sur un bulletin
        validé lève ``BulletinVerrouille``. Tant que le bulletin est
        brouillon, ``save`` est libre (recalcul/régénération).
        """
        if self.pk:
            ancien = (
                BulletinPaie.objects
                .filter(pk=self.pk)
                .values('statut')
                .first()
            )
            if ancien and ancien['statut'] == self.STATUT_VALIDE:
                # Déjà validé en base → figé (hors statut/date_validation/
                # paiement).
                update_fields = kwargs.get('update_fields')
                autorise = (
                    update_fields is not None
                    and set(update_fields)
                    <= self._CHAMPS_AUTORISES_APRES_VALIDATION
                    and self.statut == self.STATUT_VALIDE
                )
                if not autorise:
                    raise BulletinPaie.BulletinVerrouille(
                        'Bulletin validé : modification interdite (figé).')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Interdit la suppression d'un bulletin validé (snapshot conservé)."""
        if self.est_valide:
            raise BulletinPaie.BulletinVerrouille(
                'Bulletin validé : suppression interdite.')
        return super().delete(*args, **kwargs)


class LigneBulletin(models.Model):
    """Ligne d'un ``BulletinPaie`` (PAIE17) — snapshot d'une ligne de paie.

    Détail figé d'un bulletin : ``code``, ``libelle``, ``type`` (gain / retenue /
    cotisation) et ``montant``, dans l'ordre d'affichage (``ordre``). Issu du
    moteur ``calculer_bulletin`` (clé ``lignes``).

    IMMUTABILITÉ — une ligne dont le bulletin parent est ``valide`` est GELÉE :
    ni création, ni modification, ni suppression. La garde est posée dans
    ``save``/``delete`` (et dans ``services``). Multi-société : ``company`` posée
    côté serveur (héritée du bulletin).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_lignes_bulletin',
        verbose_name='Société',
    )
    bulletin = models.ForeignKey(
        BulletinPaie,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Bulletin',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    type = models.CharField(
        max_length=12, choices=Rubrique.TYPE_CHOICES,
        default=Rubrique.TYPE_GAIN, verbose_name='Type')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Ligne de bulletin'
        verbose_name_plural = 'Lignes de bulletin'
        ordering = ['bulletin', 'ordre', 'id']

    def __str__(self):
        return f'{self.code} {self.montant} (bulletin #{self.bulletin_id})'

    def _bulletin_fige(self):
        statut = (
            BulletinPaie.objects
            .filter(pk=self.bulletin_id)
            .values_list('statut', flat=True)
            .first()
        )
        return statut == BulletinPaie.STATUT_VALIDE

    def save(self, *args, **kwargs):
        """Interdit toute écriture si le bulletin parent est validé (figé)."""
        if self.bulletin_id and self._bulletin_fige():
            raise BulletinPaie.BulletinVerrouille(
                'Bulletin validé : lignes figées (écriture interdite).')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Interdit la suppression d'une ligne d'un bulletin validé."""
        if self.bulletin_id and self._bulletin_fige():
            raise BulletinPaie.BulletinVerrouille(
                'Bulletin validé : lignes figées (suppression interdite).')
        return super().delete(*args, **kwargs)


# ── PAIE27 — Cumul annuel par employé (brut/net imposable/IR/CNSS/congés) ────

class CumulAnnuel(models.Model):
    """Cumul annuel de paie d'un employé (PAIE27) — totaux d'une année civile.

    Agrégat MATÉRIALISÉ des montants clés d'un salarié sur une année :
    brut, brut imposable, net imposable, IR, CNSS/AMO/CIMR salariales, frais
    professionnels, net à payer, charges patronales, provision congés, et le
    cumul de jours de congés acquis/pris (alimenté côté RH). Sert de base aux
    déclarations annuelles (état IR 9421, attestations) et au contrôle de
    cohérence mensuelle.

    Recalculé (idempotent) à partir des bulletins VALIDÉS de l'année par
    ``services.recalculer_cumul_annuel`` : un cumul n'est jamais saisi à la main.
    Multi-société : ``company`` posée côté serveur. Le couple
    ``(company, profil, annee)`` est unique — un seul cumul par employé et par
    année.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_cumuls_annuels',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='cumuls_annuels',
        verbose_name='Profil de paie',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    brut = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul brut')
    brut_imposable = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul brut imposable')
    net_imposable = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul net imposable')
    ir = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul IR')
    cnss_salariale = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul CNSS salariale')
    amo_salariale = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul AMO salariale')
    cimr_salariale = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul CIMR salariale')
    frais_professionnels = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul frais professionnels')
    net_a_payer = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul net à payer')
    charges_patronales = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul charges patronales')
    provision_conges = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Cumul provision congés payés')
    # Compteur de congés (alimenté côté RH, informatif).
    conges_acquis = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'),
        verbose_name='Congés acquis (jours)')
    conges_pris = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'),
        verbose_name='Congés pris (jours)')
    nombre_bulletins = models.PositiveIntegerField(
        default=0, verbose_name='Nombre de bulletins cumulés')
    date_calcul = models.DateTimeField(
        null=True, blank=True, verbose_name='Recalculé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Cumul annuel'
        verbose_name_plural = 'Cumuls annuels'
        ordering = ['-annee', 'profil']
        unique_together = [('company', 'profil', 'annee')]

    def __str__(self):
        return f'Cumul {self.annee} profil #{self.profil_id}'


# ── PAIE28 — Avance / prêt salarié + déduction mensuelle ────────────────────

class AvanceSalarie(models.Model):
    """Avance ou prêt accordé à un salarié, remboursé par retenue (PAIE28).

    Couvre l'avance PONCTUELLE (``nombre_echeances=1``) comme le PRÊT étalé sur
    plusieurs mois (``nombre_echeances>1``). Chaque mois ouvré, une ÉCHÉANCE
    (``montant_echeance``) est retenue sur le bulletin tant que le solde restant
    n'est pas épuisé. Le ``montant_echeance`` est calculé à la création
    (``montant_total / nombre_echeances``) mais reste éditable.

    Le suivi du remboursement se fait par ``montant_rembourse`` (cumul retenu) :
    le SOLDE restant = ``montant_total − montant_rembourse``. Une avance est
    ACTIVE tant qu'elle n'est pas soldée (``solde > 0``) et que ``actif`` est vrai
    et que la ``date_debut`` est atteinte. Multi-société : ``company`` posée côté
    serveur. ``profil`` (FK ``ProfilPaie``) rattache l'avance à l'employé.
    """
    TYPE_AVANCE = 'avance'
    TYPE_PRET = 'pret'
    TYPE_CHOICES = [
        (TYPE_AVANCE, 'Avance sur salaire'),
        (TYPE_PRET, 'Prêt salarié'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_avances',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='avances',
        verbose_name='Profil de paie',
    )
    type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_AVANCE,
        verbose_name='Type')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant total accordé')
    montant_echeance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant de l\'échéance mensuelle')
    nombre_echeances = models.PositiveSmallIntegerField(
        default=1, verbose_name='Nombre d\'échéances')
    montant_rembourse = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant déjà remboursé')
    date_debut = models.DateField(verbose_name='Date de début de retenue')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Avance / prêt salarié'
        verbose_name_plural = 'Avances / prêts salariés'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.get_type_display()} {self.montant_total} → profil #{self.profil_id}'

    @property
    def solde_restant(self):
        """Solde encore dû = montant total − montant déjà remboursé (>= 0)."""
        solde = (self.montant_total or Decimal('0')) \
            - (self.montant_rembourse or Decimal('0'))
        return solde if solde > 0 else Decimal('0')

    @property
    def soldee(self):
        """Vrai quand l'avance est entièrement remboursée."""
        return self.solde_restant <= 0


# ── PAIE29 — Saisie-arrêt / cession sur salaire (quotité saisissable) ───────

class SaisieArret(models.Model):
    """Saisie-arrêt ou cession sur salaire d'un employé (PAIE29).

    Retenue judiciaire (saisie-arrêt) ou volontaire (cession) opérée sur le
    salaire au profit d'un créancier (pension alimentaire, dette…), DANS LA
    LIMITE de la quotité saisissable (la part du salaire légalement saisissable
    selon un barème progressif par tranche de revenu — cf.
    ``services.quotite_saisissable``). La fraction insaisissable reste toujours
    versée au salarié.

    Une saisie est ACTIVE tant que ``actif`` est vrai et que le montant dû
    (``montant_total − montant_retenu``) n'est pas épuisé. Le ``montant_retenu``
    est cumulé par le service à la validation des bulletins (jamais saisi à la
    main). Une saisie PRIORITAIRE (``prioritaire=True``, p. ex. pension
    alimentaire) est servie avant les autres dans la limite de la quotité.

    Multi-société : ``company`` posée côté serveur. ``profil`` rattache la saisie
    à l'employé.
    """
    TYPE_SAISIE = 'saisie'
    TYPE_CESSION = 'cession'
    TYPE_CHOICES = [
        (TYPE_SAISIE, 'Saisie-arrêt (judiciaire)'),
        (TYPE_CESSION, 'Cession volontaire'),
    ]

    # ZPAI6 — Cycle de vie explicite (façon Odoo Running/Completed/Cancelled) :
    # ``en_cours`` (défaut, sert encore des retenues), ``soldee`` (posée
    # automatiquement quand ``solde_restant<=0`` à l'application d'une
    # retenue), ``annulee`` (arrêt manuel des retenues futures, sans jamais
    # effacer l'historique déjà retenu).
    STATUT_EN_COURS = 'en_cours'
    STATUT_SOLDEE = 'soldee'
    STATUT_ANNULEE = 'annulee'
    STATUT_CHOICES = [
        (STATUT_EN_COURS, 'En cours'),
        (STATUT_SOLDEE, 'Soldée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_saisies',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='saisies',
        verbose_name='Profil de paie',
    )
    type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_SAISIE,
        verbose_name='Type')
    creancier = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Créancier')
    reference = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Référence (jugement/acte)')
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant total à recouvrer')
    montant_echeance = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Échéance mensuelle souhaitée')
    montant_retenu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant déjà retenu')
    prioritaire = models.BooleanField(
        default=False, verbose_name='Prioritaire (ex. pension alimentaire)')
    date_debut = models.DateField(verbose_name='Date de début de retenue')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    # ZPAI6 — statut explicite du cycle de vie, en plus du booléen ``actif``
    # historique (conservé, inchangé, pour compat rétro : ``actif`` continue
    # de piloter ``retenues_saisies_periode``/``appliquer_saisies``).
    statut = models.CharField(
        max_length=10, choices=STATUT_CHOICES, default=STATUT_EN_COURS,
        verbose_name='Statut')
    date_annulation = models.DateTimeField(
        null=True, blank=True, verbose_name='Annulée le')
    motif_annulation = models.CharField(
        max_length=200, blank=True, default='', verbose_name="Motif d'annulation")
    # ZPAI7 — Clé de lot (facultative) : posée quand la saisie est créée par
    # ``services.creer_saisies_arret_lot`` (éclatement multi-employés). Sert
    # UNIQUEMENT à l'IDEMPOTENCE d'un re-run (même clé → aucune re-création),
    # jamais affichée comme référence légale (distincte de ``reference``).
    lot_reference = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Référence de lot (idempotence)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Saisie-arrêt / cession'
        verbose_name_plural = 'Saisies-arrêts / cessions'
        # Saisies prioritaires d'abord, puis les plus anciennes.
        ordering = ['-prioritaire', 'date_debut', 'id']
        indexes = [
            models.Index(
                fields=['company', 'lot_reference'],
                name='paie_saisie_lot_idx'),
        ]

    def __str__(self):
        return f'{self.get_type_display()} {self.montant_total} → profil #{self.profil_id}'

    @property
    def solde_restant(self):
        """Reste à recouvrer = montant total − montant déjà retenu (>= 0)."""
        solde = (self.montant_total or Decimal('0')) \
            - (self.montant_retenu or Decimal('0'))
        return solde if solde > 0 else Decimal('0')

    @property
    def soldee(self):
        """Vrai quand la saisie est entièrement recouvrée."""
        return self.solde_restant <= 0


# ── PAIE30 — Ordre de virement + fichier de virement banque ────────────────

class OrdreVirement(models.Model):
    """Ordre de virement des salaires d'une période (PAIE30).

    Regroupe en UN ordre l'ensemble des bulletins VALIDÉS d'une ``PeriodePaie``
    à payer par virement bancaire : chaque salarié devient une ``LigneVirement``
    (RIB + net à payer). Sert à générer le fichier de virement remis à la banque
    (``services.fichier_virement_paie``).

    Cycle : ``brouillon`` (lignes éditables) → ``emis`` (transmis à la banque,
    figé). Multi-société : ``company`` posée côté serveur. Le couple
    ``(company, periode)`` est unique — un seul ordre de virement par période.
    """
    STATUT_BROUILLON = 'brouillon'
    STATUT_EMIS = 'emis'
    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_EMIS, 'Émis'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_ordres_virement',
        verbose_name='Société',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='ordres_virement',
        verbose_name='Période',
    )
    # DC39 — référence unique générée par ``references.create_with_reference``
    # (``OV-YYYYMM-NNNN``, plus-haut-utilisé+1 par société/mois, race-safe),
    # JAMAIS ``count()+1``. Posée à la première création de l'ordre.
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    statut = models.CharField(
        max_length=12, choices=STATUT_CHOICES, default=STATUT_BROUILLON,
        verbose_name='Statut')
    date_execution = models.DateField(
        null=True, blank=True, verbose_name="Date d'exécution souhaitée")
    # DC20 — UN référentiel `compta.CompteTresorerie` est la source unique du
    # compte bancaire émetteur (RIB/IBAN/BIC/devise saisis UNE fois). Quand il
    # est renseigné, ``rib_emetteur``/``devise`` sont dérivés de lui à la
    # génération (cf. ``services.generer_ordre_virement``) ; ``rib_emetteur``
    # reste un repli texte libre pour l'historique / les sociétés sans
    # référentiel câblé. Référence par string-FK (jamais d'import de
    # ``compta.models``) — la trésorerie reste propriété de l'app compta.
    compte_emetteur = models.ForeignKey(
        'compta.CompteTresorerie',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordres_virement_paie',
        verbose_name='Compte émetteur (trésorerie)',
    )
    rib_emetteur = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB émetteur')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    total = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0'),
        verbose_name='Total à virer')
    nombre_lignes = models.PositiveIntegerField(
        default=0, verbose_name='Nombre de lignes')
    date_emission = models.DateTimeField(
        null=True, blank=True, verbose_name='Émis le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # YLEDG7 — écriture de règlement (débit 4432 / crédit trésorerie) postée
    # par ``services.payer_ordre_virement``. String-ref vers
    # ``compta.EcritureComptable`` (jamais d'import de compta.models depuis
    # paie) : posée une seule fois, garantit l'idempotence du paiement de
    # l'ordre.
    ecriture_reglement_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Écriture de règlement (compta)')
    date_reglement = models.DateTimeField(
        null=True, blank=True, verbose_name='Réglé le')

    class Meta:
        verbose_name = 'Ordre de virement'
        verbose_name_plural = 'Ordres de virement'
        ordering = ['-date_creation']
        unique_together = [('company', 'periode')]
        constraints = [
            # DC39 — la référence générée est unique par société (arbitre final
            # des courses de numérotation) ; les ordres pré-référence (blanc)
            # sont exclus.
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=models.Q(reference__isnull=False)
                & ~models.Q(reference=''),
                name='uniq_ordrevirement_ref_par_societe',
            ),
        ]

    def __str__(self):
        return f'Ordre virement {self.periode} ({self.statut})'

    @property
    def est_emis(self):
        return self.statut == self.STATUT_EMIS


class LigneVirement(models.Model):
    """Ligne d'un ``OrdreVirement`` (PAIE30) — un bénéficiaire / un net à virer.

    Issue d'un ``BulletinPaie`` validé : bénéficiaire (nom du salarié), RIB,
    montant (net à payer du bulletin) et référence. Multi-société : ``company``
    posée côté serveur (héritée de l'ordre).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_lignes_virement',
        verbose_name='Société',
    )
    ordre = models.ForeignKey(
        OrdreVirement,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Ordre de virement',
    )
    bulletin = models.ForeignKey(
        BulletinPaie,
        on_delete=models.PROTECT,
        related_name='lignes_virement',
        verbose_name='Bulletin',
    )
    beneficiaire = models.CharField(
        max_length=160, verbose_name='Bénéficiaire')
    rib = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    reference = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Référence')
    # XPAI9 — Suivi des rejets de virement (RIB invalide). Une ligne rejetée
    # n'est JAMAIS supprimée (trace comptable/audit) ; ``ligne_correction``
    # référence la ligne RÉÉMISE avec le RIB corrigé (nouvelle ligne, même
    # bulletin) — chaîne d'audit complète.
    rejetee = models.BooleanField(default=False, verbose_name='Rejetée')
    motif_rejet = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Motif du rejet')
    date_rejet = models.DateTimeField(
        null=True, blank=True, verbose_name='Rejetée le')
    ligne_correction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='corrige',
        verbose_name='Ligne de correction (réémission)',
    )

    class Meta:
        verbose_name = 'Ligne de virement'
        verbose_name_plural = 'Lignes de virement'
        ordering = ['ordre', 'beneficiaire', 'id']

    def __str__(self):
        return f'{self.beneficiaire} {self.montant} (ordre #{self.ordre_id})'


# ── XPAI6 — Échéancier déclaratif paie ──────────────────────────────────────

class EcheanceDeclarative(models.Model):
    """Échéance de conformité déclarative d'une période de paie (XPAI6).

    Calendrier des déclarations dues par organisme : BDS mensuelle (CNSS,
    avant le 10 du mois suivant), IR mensuel (retenue à la source, versée à
    l'État), 9421 (état annuel des traitements & salaires, fin février de
    l'année suivante), CIMR (cotisation retraite). Générée AUTOMATIQUEMENT à
    la création d'une ``PeriodePaie`` (``services.generer_echeances_periode``,
    idempotent) — jamais saisie à la main. ``statut`` progresse
    manuellement (à_générer → générée → déposée → payée) au fil du traitement
    réel de la déclaration.

    Multi-société : ``company`` posée côté serveur.
    """
    TYPE_BDS = 'bds'
    TYPE_IR_MENSUEL = 'ir_mensuel'
    TYPE_9421 = 'etat_9421'
    TYPE_CIMR = 'cimr'
    TYPE_CHOICES = [
        (TYPE_BDS, 'BDS (CNSS)'),
        (TYPE_IR_MENSUEL, 'IR mensuel'),
        (TYPE_9421, 'État 9421 (annuel)'),
        (TYPE_CIMR, 'CIMR'),
    ]

    STATUT_A_GENERER = 'a_generer'
    STATUT_GENEREE = 'generee'
    STATUT_DEPOSEE = 'deposee'
    STATUT_PAYEE = 'payee'
    STATUT_CHOICES = [
        (STATUT_A_GENERER, 'À générer'),
        (STATUT_GENEREE, 'Générée'),
        (STATUT_DEPOSEE, 'Déposée'),
        (STATUT_PAYEE, 'Payée'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_echeances_declaratives',
        verbose_name='Société',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='echeances_declaratives',
        verbose_name='Période',
    )
    type_echeance = models.CharField(
        max_length=12, choices=TYPE_CHOICES, verbose_name='Type')
    date_limite = models.DateField(verbose_name='Date limite')
    statut = models.CharField(
        max_length=10, choices=STATUT_CHOICES, default=STATUT_A_GENERER,
        verbose_name='Statut')
    date_notification = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Rappel envoyé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # YLEDG7 — écriture de règlement (débit 4441/4452/4443 / crédit
    # trésorerie) postée par ``services.payer_organismes`` au règlement
    # effectif de la déclaration. String-ref vers
    # ``compta.EcritureComptable`` : posée une seule fois (idempotence).
    ecriture_reglement_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Écriture de règlement (compta)')

    class Meta:
        verbose_name = 'Échéance déclarative'
        verbose_name_plural = 'Échéances déclaratives'
        ordering = ['date_limite', 'type_echeance']
        unique_together = [('periode', 'type_echeance')]

    def __str__(self):
        return f'{self.get_type_echeance_display()} — {self.date_limite} ({self.statut})'

    @property
    def en_retard(self):
        """Vrai si la date limite est dépassée sans dépôt (déposée/payée)."""
        from django.utils import timezone
        if self.statut in (self.STATUT_DEPOSEE, self.STATUT_PAYEE):
            return False
        return timezone.localdate() > self.date_limite


# ── XPAI12 — BDS complémentaire/rectificative + trace des dépôts DAMANCOM ───

class DepotBDS(models.Model):
    """Trace un DÉPÔT de BDS (CNSS) pour une période (XPAI12).

    Un dépôt PRINCIPAL couvre l'ensemble des salariés déclarés au format
    DAMANCOM (``fichier_damancom_cnss``, PAIE31). Un dépôt COMPLÉMENTAIRE
    corrige un dépôt principal déjà déposé — salariés omis/corrections — et
    référence son dépôt principal via ``depot_principal`` : son contenu ne
    contient QUE le delta (jamais l'ensemble des salariés à nouveau). Une
    période ne peut avoir qu'UN dépôt principal, mais PLUSIEURS
    complémentaires (corrections successives).

    Multi-société : ``company`` posée côté serveur.
    """
    TYPE_PRINCIPAL = 'principal'
    TYPE_COMPLEMENTAIRE = 'complementaire'
    TYPE_CHOICES = [
        (TYPE_PRINCIPAL, 'Principal'),
        (TYPE_COMPLEMENTAIRE, 'Complémentaire'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_depots_bds',
        verbose_name='Société',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='depots_bds',
        verbose_name='Période',
    )
    type_depot = models.CharField(
        max_length=14, choices=TYPE_CHOICES, default=TYPE_PRINCIPAL,
        verbose_name='Type de dépôt')
    depot_principal = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='complements',
        verbose_name='Dépôt principal référencé',
    )
    # Salariés couverts par CE dépôt (liste d'ids de ProfilPaie) — pour un
    # complémentaire, uniquement le delta (omis/corrigés).
    profils_couverts = models.JSONField(
        default=list, blank=True, verbose_name='Profils couverts')
    date_depot = models.DateTimeField(
        auto_now_add=True, verbose_name='Déposé le')

    class Meta:
        verbose_name = 'Dépôt BDS'
        verbose_name_plural = 'Dépôts BDS'
        ordering = ['-date_depot']

    def __str__(self):
        return f'Dépôt BDS {self.get_type_depot_display()} — {self.periode}'


# ── XPAI24 — Structures de paie par catégorie (modèles de rubriques) ───────

class StructurePaie(models.Model):
    """Modèle de rubriques par catégorie de personnel (XPAI24), company-scoped.

    Un jeu de ``Rubrique`` par défaut (cadre/employé/ouvrier/technicien
    chantier…) appliqué en une fois à un ``ProfilPaie`` à sa création : au lieu
    d'affecter les rubriques récurrentes une à une (``RubriqueEmploye``), on
    choisit une structure et ses rubriques sont copiées (chacune reste
    modifiable individuellement ensuite — la structure n'est qu'un GABARIT,
    aucun lien n'est conservé après application).

    Multi-société : ``company`` posée côté serveur. Le couple ``(company,
    code)`` est unique.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_structures',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    description = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Structure de paie'
        verbose_name_plural = 'Structures de paie'
        ordering = ['libelle']
        unique_together = [('company', 'code')]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class StructurePaieRubrique(models.Model):
    """Rubrique DÉFAUT d'une ``StructurePaie`` (XPAI24) — ligne du gabarit.

    Porte une surcharge optionnelle du ``montant``/``taux`` (mêmes champs que
    ``RubriqueEmploye``, dont la ligne sera la copie lors de l'application).
    Multi-société : ``company`` posée côté serveur. Le couple ``(structure,
    rubrique)`` est unique.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_structure_rubriques',
        verbose_name='Société',
    )
    structure = models.ForeignKey(
        StructurePaie,
        on_delete=models.CASCADE,
        related_name='rubriques_defaut',
        verbose_name='Structure',
    )
    rubrique = models.ForeignKey(
        Rubrique,
        on_delete=models.PROTECT,
        related_name='structures_defaut',
        verbose_name='Rubrique',
    )
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant (surcharge)')
    taux = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name='Taux % (surcharge)')

    class Meta:
        verbose_name = 'Rubrique de structure'
        verbose_name_plural = 'Rubriques de structure'
        ordering = ['rubrique__ordre', 'id']
        unique_together = [('structure', 'rubrique')]

    def __str__(self):
        return f'{self.rubrique.code} → {self.structure.code}'


# ── XPAI17 — Ventilation analytique de la masse salariale ──────────────────

class VentilationAnalytiquePaie(models.Model):
    """Clé de ventilation analytique FIXE par profil (XPAI17), company-scoped.

    Repli quand aucune heure ``rh.FeuilleTemps`` n'est disponible pour la
    période : répartit le coût employeur du profil sur un ``centre_cout``
    (``compta.CentreCout``, référencé en STRING-FK — la paie n'importe jamais
    ``compta.models``) au ``pourcentage`` indiqué. Plusieurs clés peuvent
    coexister pour un même profil (ex. 60 % chantier A / 40 % chantier B) ;
    aucune contrainte de somme à 100 % n'est imposée en base (validée côté
    service au moment de l'usage — un total ≠ 100 % laisse un reliquat non
    ventilé, jamais une erreur bloquante).

    Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_ventilations_analytiques',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='ventilations_analytiques',
        verbose_name='Profil de paie',
    )
    # STRING-FK cross-app vers compta.CentreCout — jamais compta.models direct.
    centre_cout_id = models.PositiveIntegerField(
        verbose_name='Centre de coût (ID, compta.CentreCout)')
    pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100'),
        verbose_name='Pourcentage')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Ventilation analytique (clé fixe)'
        verbose_name_plural = 'Ventilations analytiques (clés fixes)'
        ordering = ['profil', 'id']

    def __str__(self):
        return (f'Profil #{self.profil_id} → '
                f'centre#{self.centre_cout_id} ({self.pourcentage}%)')


# ── XPAI20 — Provisions gratifications (13e mois) & IFC ────────────────────

class ProvisionPaieMensuelle(models.Model):
    """Provision mensuelle 13e mois / IFC d'un profil (XPAI20), auditable.

    Une ligne PAR PROFIL et par mois de clôture, matérialisant le montant
    provisionné (1/12ᵉ du 13e mois pour ``TYPE_GRATIFICATION``, quote-part
    mensuelle de l'indemnité de fin de carrière — barème art. 53 — pour
    ``TYPE_IFC``). Postée en écriture réversible via ``compta.services``
    (même patron que la provision CP, PAIE25) — ``ecriture_id`` référence
    l'``EcritureComptable`` (STRING-FK, jamais ``compta.models`` direct).
    ``extournee`` passe à vrai quand le run 13e mois (XPAI4) ou la sortie
    (STC) reprend la provision. Multi-société : ``company`` posée côté
    serveur. Clé stable ``(company, profil, periode, type_provision)``.
    """
    TYPE_GRATIFICATION = 'gratification'
    TYPE_IFC = 'ifc'
    TYPE_CHOICES = [
        (TYPE_GRATIFICATION, '13e mois / prime de bilan'),
        (TYPE_IFC, 'Indemnité de fin de carrière'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_provisions_mensuelles',
        verbose_name='Société',
    )
    profil = models.ForeignKey(
        ProfilPaie,
        on_delete=models.CASCADE,
        related_name='provisions_mensuelles',
        verbose_name='Profil de paie',
    )
    periode = models.ForeignKey(
        PeriodePaie,
        on_delete=models.CASCADE,
        related_name='provisions_mensuelles',
        verbose_name='Période',
    )
    type_provision = models.CharField(
        max_length=14, choices=TYPE_CHOICES, verbose_name='Type de provision')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant provisionné')
    # STRING-FK cross-app vers compta.EcritureComptable — jamais
    # compta.models direct.
    ecriture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Écriture (ID, compta)')
    extournee = models.BooleanField(
        default=False, verbose_name='Extournée (reprise)')
    date_extourne = models.DateTimeField(
        null=True, blank=True, verbose_name='Extournée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Provision mensuelle (13e mois / IFC)'
        verbose_name_plural = 'Provisions mensuelles (13e mois / IFC)'
        ordering = ['-periode__annee', '-periode__mois', 'profil']
        unique_together = [('company', 'profil', 'periode', 'type_provision')]

    def __str__(self):
        return (f'{self.get_type_provision_display()} — profil #{self.profil_id} '
                f'({self.periode})')


# ── ZPAI9 — Catalogue de types d'entrées ponctuelles (Other Input Types) ───

class TypeEntreePonctuelle(models.Model):
    """Catalogue TYPÉ des entrées ponctuelles hors rubriques récurrentes (ZPAI9).

    Façon Odoo « Other Input Types » : au lieu du ``type`` fixe à 5 valeurs
    codées d'``ElementVariable`` (heures/HS/absence/prime/retenue), un
    catalogue company-scoped pour typer finement des entrées ponctuelles
    (pourboire, remboursement de frais non imposable, déduction ponctuelle…),
    chacune avec ses propres drapeaux fiscaux/sociaux. Un ``ElementVariable``
    peut référencer un type du catalogue via son FK nullable
    ``type_entree`` — NULL (défaut) préserve exactement le comportement
    historique piloté par ``ElementVariable.type`` seul.

    Multi-société : ``company`` posée côté serveur. Le couple
    ``(company, code)`` est unique.
    """
    SENS_GAIN = 'gain'
    SENS_RETENUE = 'retenue'
    SENS_CHOICES = [
        (SENS_GAIN, 'Gain'),
        (SENS_RETENUE, 'Retenue'),
    ]

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_types_entree_ponctuelle',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    sens = models.CharField(
        max_length=8, choices=SENS_CHOICES, default=SENS_GAIN,
        verbose_name='Sens')
    imposable = models.BooleanField(
        default=True, verbose_name='Imposable (IR)')
    soumis_cnss = models.BooleanField(
        default=True, verbose_name='Soumis CNSS')
    soumis_amo = models.BooleanField(
        default=True, verbose_name='Soumis AMO')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Type d'entrée ponctuelle"
        verbose_name_plural = "Types d'entrée ponctuelle"
        ordering = ['libelle', 'code']
        unique_together = [('company', 'code')]

    def __str__(self):
        return f'{self.code} — {self.libelle}'
