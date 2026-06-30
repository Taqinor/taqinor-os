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
    numero_cnss = models.CharField(
        max_length=20, blank=True, default='', verbose_name='N° CNSS')
    numero_amo = models.CharField(
        max_length=20, blank=True, default='', verbose_name='N° AMO')
    numero_cimr = models.CharField(
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
    rib = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    banque = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Banque')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Profil de paie'
        verbose_name_plural = 'Profils de paie'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Profil paie #{self.employe_id} ({self.type_remuneration})'


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

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paie_periodes',
        verbose_name='Société',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois')
    libelle = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    statut = models.CharField(
        max_length=12, choices=STATUT_CHOICES, default=STATUT_BROUILLON,
        verbose_name='Statut')
    date_paiement = models.DateField(
        null=True, blank=True, verbose_name='Date de paiement')
    date_cloture = models.DateTimeField(
        null=True, blank=True, verbose_name='Clôturée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Période de paie'
        verbose_name_plural = 'Périodes de paie'
        ordering = ['-annee', '-mois']
        unique_together = [('company', 'annee', 'mois')]

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
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUEL,
        verbose_name='Source')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Élément variable'
        verbose_name_plural = 'Éléments variables'
        ordering = ['periode', 'profil', 'id']

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

    # Champs de montant figés au moment du calcul (snapshot). Modifiables tant
    # que le bulletin est en brouillon, gelés dès la validation.
    SNAPSHOT_FIELDS = [
        'brut', 'brut_imposable', 'cnss_salariale', 'cnss_patronale',
        'amo_salariale', 'amo_patronale', 'allocations_familiales',
        'formation_professionnelle',
        'cimr_salariale', 'frais_professionnels', 'net_imposable', 'ir',
        'retenues', 'prime_anciennete', 'charges_patronales', 'net_a_payer',
        'personnes_a_charge', 'provision_conges',
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

    def save(self, *args, **kwargs):
        """Garde d'immuabilité (PAIE17).

        Un bulletin déjà ``valide`` en base est FIGÉ : seule reste autorisée la
        transition de validation elle-même (``brouillon → valide``, qui pose
        ``date_validation``). Toute autre écriture sur un bulletin validé lève
        ``BulletinVerrouille``. Tant que le bulletin est brouillon, ``save`` est
        libre (recalcul/régénération).
        """
        if self.pk:
            ancien = (
                BulletinPaie.objects
                .filter(pk=self.pk)
                .values('statut')
                .first()
            )
            if ancien and ancien['statut'] == self.STATUT_VALIDE:
                # Déjà validé en base → immuable.
                update_fields = kwargs.get('update_fields')
                autorise = (
                    update_fields is not None
                    and set(update_fields) <= {'statut', 'date_validation'}
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
