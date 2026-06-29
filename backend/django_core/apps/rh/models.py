"""Modèles des Ressources humaines (module `apps.rh`).

Socle du dossier employé (DC29) : référentiel unique des collaborateurs d'une
société, rattaché optionnellement à un compte utilisateur.

* ``Departement`` — découpage organisationnel (production, commercial, atelier…).
* ``DossierEmploye`` — fiche employé maître (source de vérité unique) : identité,
  contact, poste, contrat, statut et données de paie internes.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Le ``cout_horaire`` est une donnée INTERNE qui
n'apparaît jamais dans une sortie client. Ce module est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Departement(models.Model):
    """Département d'une société (regroupe des ``DossierEmploye``)."""
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_departements',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    code = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Code')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Département'
        verbose_name_plural = 'Départements'
        unique_together = [('company', 'nom')]
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Poste(models.Model):
    """Référentiel des postes/fonctions (FG160) — remplace le ``poste`` texte
    libre de ``DossierEmploye``.

    Un ``Poste`` est une fonction normalisée de la société (ex. « Technicien
    pose », « Chef de chantier », « Commercial ») rattachable optionnellement à
    un ``Departement``. Il sert de socle aux grilles/habilitations et à
    l'organigramme : un employé pointe désormais vers un ``Poste`` (FK) au lieu
    d'une chaîne saisie à la main. Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_postes',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=120, verbose_name='Intitulé')
    code = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Code')
    departement = models.ForeignKey(
        'Departement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='postes',
        verbose_name='Département',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Poste'
        verbose_name_plural = 'Postes'
        unique_together = [('company', 'intitule')]
        ordering = ['intitule']

    def __str__(self):
        return self.intitule


class DossierEmploye(models.Model):
    """Fiche employé maître (DC29) — source de vérité unique du collaborateur.

    Peut être reliée à un compte utilisateur (``user``) mais reste autonome :
    un employé sans accès applicatif a quand même son dossier. Le ``cout_horaire``
    est strictement INTERNE et n'apparaît dans aucune sortie client.
    """
    class TypeContrat(models.TextChoices):
        CDI = 'cdi', 'CDI'
        CDD = 'cdd', 'CDD'
        ANAPEC = 'anapec', 'ANAPEC'
        STAGE = 'stage', 'Stage'
        INTERIM = 'interim', 'Intérim'

    class Statut(models.TextChoices):
        # FG161 — cycle de vie : embauché (avant prise de poste) → actif →
        # (suspendu) → sorti. Le statut SORTI déclenche l'offboarding.
        EMBAUCHE = 'embauche', 'Embauché'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        SORTI = 'sorti', 'Sorti'

    class MotifSortie(models.TextChoices):
        DEMISSION = 'demission', 'Démission'
        LICENCIEMENT = 'licenciement', 'Licenciement'
        FIN_CONTRAT = 'fin_contrat', 'Fin de contrat'
        RETRAITE = 'retraite', 'Retraite'
        RUPTURE_PERIODE_ESSAI = 'rupture_essai', "Rupture période d'essai"
        AUTRE = 'autre', 'Autre'

    class SituationFamiliale(models.TextChoices):
        CELIBATAIRE = 'celibataire', 'Célibataire'
        MARIE = 'marie', 'Marié(e)'
        DIVORCE = 'divorce', 'Divorcé(e)'
        VEUF = 'veuf', 'Veuf(ve)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_dossiers',
        verbose_name='Société',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossier_employe',
        verbose_name='Compte utilisateur',
    )
    matricule = models.CharField(max_length=30, verbose_name='Matricule')
    nom = models.CharField(max_length=120, verbose_name='Nom')
    prenom = models.CharField(max_length=120, verbose_name='Prénom')
    cin = models.CharField(
        max_length=20, blank=True, default='', verbose_name='CIN')
    # Numéros légaux paie (Maroc) — facultatifs ; pas d'unicité ici (à étudier
    # en suivi : unicité par société sans piège AddField(unique, default)).
    cnss = models.CharField(
        max_length=20, blank=True, default='', verbose_name='N° CNSS')
    cimr = models.CharField(
        max_length=20, blank=True, default='', verbose_name='N° CIMR')
    amo = models.CharField(
        max_length=20, blank=True, default='', verbose_name='N° AMO')
    situation_familiale = models.CharField(
        max_length=12, choices=SituationFamiliale.choices,
        blank=True, default='', verbose_name='Situation familiale')
    nombre_enfants = models.PositiveIntegerField(
        default=0, verbose_name="Nombre d'enfants")
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    email = models.EmailField(blank=True, default='', verbose_name='E-mail')
    # FG160 — référentiel : ``poste_ref`` (FK Poste) remplace le ``poste`` texte
    # libre, conservé en transition pour migrer/dédupliquer les chaînes existantes.
    poste = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Poste (libre)')
    poste_ref = models.ForeignKey(
        'Poste',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employes',
        verbose_name='Poste',
    )
    departement = models.ForeignKey(
        Departement,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employes',
        verbose_name='Département',
    )
    date_embauche = models.DateField(
        null=True, blank=True, verbose_name="Date d'embauche")
    type_contrat = models.CharField(
        max_length=10, choices=TypeContrat.choices,
        default=TypeContrat.CDI, verbose_name='Type de contrat')
    contrat_date_debut = models.DateField(
        null=True, blank=True, verbose_name='Début de contrat')
    contrat_date_fin = models.DateField(
        null=True, blank=True, verbose_name='Fin de contrat')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.ACTIF, verbose_name='Statut')
    # FG161 — offboarding : date + motif de sortie (renseignés quand SORTI).
    date_sortie = models.DateField(
        null=True, blank=True, verbose_name='Date de sortie')
    motif_sortie = models.CharField(
        max_length=20, choices=MotifSortie.choices,
        blank=True, default='', verbose_name='Motif de sortie')
    # FG158 — Coordonnées personnelles étendues (facultatives) : utiles RH/paie,
    # restent INTERNES au dossier (accès Administrateur/Responsable uniquement).
    adresse_perso = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Adresse personnelle')
    telephone_perso = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Téléphone personnel')
    email_perso = models.EmailField(
        blank=True, default='', verbose_name='E-mail personnel')
    # FG158 — Contact d'urgence (personne à prévenir) — utile chantier/accident.
    urgence_nom = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Personne à prévenir — nom')
    urgence_lien = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Personne à prévenir — lien')
    urgence_telephone = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Personne à prévenir — téléphone')
    # FG158 — Donnée MÉDICALE sensible (utile chantier/accident) : ne quitte
    # jamais l'API RH interne, soumise au même contrôle d'accès que le dossier.
    groupe_sanguin = models.CharField(
        max_length=3, blank=True, default='', verbose_name='Groupe sanguin')
    # Coût horaire INTERNE (paie/marge) — ne JAMAIS exposer côté client.
    cout_horaire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût horaire')
    rib = models.CharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Dossier employé'
        verbose_name_plural = 'Dossiers employés'
        unique_together = [('company', 'matricule')]
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f'{self.matricule} — {self.nom} {self.prenom}'


class Remuneration(models.Model):
    """Rémunération de base d'un employé (FG157) — donnée paie SENSIBLE.

    Chaque changement de salaire crée une NOUVELLE ligne : la dernière (par
    ``date_effet`` décroissante) est la rémunération en vigueur, les précédentes
    forment l'historique conservé. L'accès en lecture ET en écriture est réservé
    aux porteurs de la permission ``salaires_voir`` (palier RH) ; ces montants ne
    quittent jamais une sortie client.
    """
    class Periodicite(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        HORAIRE = 'horaire', 'Horaire'
        JOURNALIER = 'journalier', 'Journalier'
        ANNUEL = 'annuel', 'Annuel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_remunerations',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='remunerations',
        verbose_name='Employé',
    )
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Montant')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    periodicite = models.CharField(
        max_length=12, choices=Periodicite.choices,
        default=Periodicite.MENSUEL, verbose_name='Périodicité')
    date_effet = models.DateField(verbose_name="Date d'effet")
    motif = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Motif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Rémunération'
        verbose_name_plural = 'Rémunérations'
        # Historique : la plus récente d'abord ; ligne courante = première.
        ordering = ['-date_effet', '-date_creation']

    def __str__(self):
        return (f'{self.employe.matricule} — {self.montant} {self.devise} '
                f'({self.get_periodicite_display()})')


class DocumentEmploye(models.Model):
    """Coffre documents employé (FG159) — pièces administratives d'un dossier.

    Chaque document RÉUTILISE le stockage objet existant de ``records.Attachment``
    (MinIO, bucket ``erp-uploads``) : ce modèle est une simple couche de
    QUALIFICATION (type de document + expiration optionnelle) au-dessus d'une
    pièce jointe — il ne stocke aucun fichier lui-même. ``records`` est une app
    socle : la référencer par FK est autorisé, on n'importe pas ses vues. Le
    fichier transite par ``records.storage.store_attachment`` exactement comme
    les autres pièces jointes ; rien n'est commité dans le dépôt.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps), et
    l'accès suit le même verrou que le dossier (Administrateur/Responsable). La
    ``date_expiration`` est facultative (NULL = document sans échéance) ; un
    sélecteur liste les documents qui expirent bientôt.
    """
    class TypeDocument(models.TextChoices):
        CONTRAT = 'contrat', 'Contrat'
        CIN = 'cin', 'CIN'
        RIB = 'rib', 'RIB'
        DIPLOME = 'diplome', 'Diplôme'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_documents',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Employé',
    )
    # Réutilise le stockage MinIO existant : on ne construit AUCUN nouveau
    # stockage de fichier. La suppression du document supprime sa pièce jointe.
    attachment = models.OneToOneField(
        'records.Attachment',
        on_delete=models.CASCADE,
        related_name='document_employe',
        verbose_name='Pièce jointe',
    )
    type_document = models.CharField(
        max_length=10, choices=TypeDocument.choices,
        default=TypeDocument.AUTRE, verbose_name='Type de document')
    # Facultative : NULL = document sans date d'expiration (ex. diplôme).
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Document employé'
        verbose_name_plural = 'Documents employés'
        ordering = ['type_document', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'employe']),
            models.Index(fields=['company', 'date_expiration']),
        ]

    def __str__(self):
        return f'{self.employe.matricule} — {self.get_type_document_display()}'


class ElementSortie(models.Model):
    """Checklist d'offboarding (FG161) — un élément à récupérer au départ.

    À la sortie d'un employé (``DossierEmploye.statut = SORTI``) on suit la
    restitution du matériel et la clôture des accès : EPI, outils, badge, clés,
    véhicule, téléphone… Chaque ligne porte un libellé, un type normalisé et un
    drapeau ``recupere`` (avec date). Multi-société : ``company`` posée côté
    serveur, jamais lue du corps de requête.
    """
    class TypeElement(models.TextChoices):
        EPI = 'epi', 'EPI'
        OUTIL = 'outil', 'Outil'
        BADGE = 'badge', 'Badge'
        CLES = 'cles', 'Clés'
        VEHICULE = 'vehicule', 'Véhicule'
        TELEPHONE = 'telephone', 'Téléphone'
        ORDINATEUR = 'ordinateur', 'Ordinateur'
        ACCES_SI = 'acces_si', 'Accès informatiques'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_elements_sortie',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='elements_sortie',
        verbose_name='Employé',
    )
    libelle = models.CharField(max_length=160, verbose_name='Libellé')
    type_element = models.CharField(
        max_length=12, choices=TypeElement.choices,
        default=TypeElement.AUTRE, verbose_name='Type')
    recupere = models.BooleanField(default=False, verbose_name='Récupéré')
    date_recuperation = models.DateField(
        null=True, blank=True, verbose_name='Date de récupération')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Élément de sortie'
        verbose_name_plural = 'Éléments de sortie'
        ordering = ['type_element', 'libelle']
        indexes = [models.Index(fields=['company', 'employe'])]

    def __str__(self):
        return f'{self.employe.matricule} — {self.libelle}'


class TypeAbsence(models.Model):
    """Typologie d'absences (FG164) — catégorie de congé/absence + règle de
    décompte.

    Chaque société dispose d'un référentiel de types : congé payé (CP), maladie,
    sans solde, exceptionnel, accident du travail (AT)… Deux règles pilotent le
    décompte d'une demande de congé (FG163) :

    * ``decompte_jours_ouvres`` — si vrai, seuls les jours ouvrés (hors week-end
      et jours fériés) entre les deux dates comptent ; sinon on compte les jours
      calendaires.
    * ``deduit_solde`` — si vrai, la durée est retranchée du solde de congés de
      l'employé (FG162) ; un congé sans solde ou la maladie ne déduisent pas le
      compteur CP.

    ``code`` est unique par société pour servir de clé stable (CP, MAL, SS…).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_types_absence',
        verbose_name='Société',
    )
    code = models.CharField(max_length=20, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    decompte_jours_ouvres = models.BooleanField(
        default=True, verbose_name='Décompte en jours ouvrés')
    deduit_solde = models.BooleanField(
        default=True, verbose_name='Déduit du solde de congés')
    remunere = models.BooleanField(default=True, verbose_name='Rémunéré')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Type d'absence"
        verbose_name_plural = "Types d'absence"
        unique_together = [('company', 'code')]
        ordering = ['libelle']

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class SoldeConge(models.Model):
    """Compteur annuel de congés payés d'un employé (FG162) — droits Maroc.

    Un solde par employé et par ``annee``. Le droit légal marocain s'acquiert à
    raison d'environ 1,5 jour ouvrable par mois de service (18 jours/an), majoré
    de l'ancienneté (1,5 jour supplémentaire par tranche de 5 ans). Le modèle
    stocke :

    * ``acquis`` — jours acquis sur l'année (acquisition mensuelle, voir
      ``services.acquisition_mensuelle``) ;
    * ``report`` — solde reporté de l'année précédente ;
    * ``pris`` — jours déjà consommés par des demandes validées.

    Le ``disponible`` = report + acquis − pris est calculé (non stocké). Tout est
    multi-société (``company`` posée côté serveur).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_soldes_conge',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='soldes_conge',
        verbose_name='Employé',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    acquis = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Jours acquis')
    report = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Report année précédente')
    pris = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Jours pris')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Solde de congés'
        verbose_name_plural = 'Soldes de congés'
        unique_together = [('company', 'employe', 'annee')]
        ordering = ['-annee', 'employe']

    @property
    def disponible(self):
        """Jours encore disponibles = report + acquis − pris."""
        return (self.report or Decimal('0')) + \
            (self.acquis or Decimal('0')) - (self.pris or Decimal('0'))

    def __str__(self):
        return f'{self.employe.matricule} — {self.annee} : {self.disponible} j'


class Pointage(models.Model):
    """Pointage journalier (FG166) — arrivée/départ d'un employé avec géoloc.

    Chaque enregistrement trace un événement d'entrée (ARRIVEE) ou de sortie
    (DEPART) d'un employé, optionnellement accompagné de coordonnées GPS
    (``gps_lat`` / ``gps_lng``) saisies côté mobile. La durée travaillée entre
    une arrivée et un départ se calcule dynamiquement (propriété
    ``duree_minutes``).

    Convention : un pointage ARRIVEE a un ``pointage_le`` posé côté serveur et
    des coordonnées GPS facultatives. Un pointage DEPART référence
    optionnellement l'ARRIVEE du même jour via ``arrivee`` (FK auto-résolu côté
    service). Les deux peuvent aussi rester indépendants (pointage simplifié :
    ``heure_arrivee`` + ``heure_depart`` sur la même ligne).

    Design minimal choisi : une seule ligne par session travaillée (arrivée +
    départ), pour simplifier le calcul des heures. Le champ ``type_pointage``
    reste pour les cas d'entrées partielles (ex. saisie mobile purement
    arrivée, départ saisi plus tard via PATCH).

    Multi-société : ``company`` posée côté serveur (jamais lue du corps). Le
    ``DossierEmploye`` doit appartenir à la même société.
    """
    class TypePointage(models.TextChoices):
        ARRIVEE = 'arrivee', 'Arrivée'
        DEPART = 'depart', 'Départ'
        COMPLET = 'complet', 'Complet (arrivée + départ)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_pointages',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='pointages',
        verbose_name='Employé',
    )
    type_pointage = models.CharField(
        max_length=10, choices=TypePointage.choices,
        default=TypePointage.ARRIVEE, verbose_name='Type')
    # Heure d'arrivée (pointée côté serveur à la création si type=ARRIVEE).
    heure_arrivee = models.DateTimeField(
        null=True, blank=True, verbose_name="Heure d'arrivée")
    # Heure de départ (mise à jour via PATCH ou @action depart).
    heure_depart = models.DateTimeField(
        null=True, blank=True, verbose_name='Heure de départ')
    # Géolocalisation arrivée (mobile, facultative).
    arrivee_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS arrivée — latitude')
    arrivee_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS arrivée — longitude')
    # Géolocalisation départ (mobile, facultative).
    depart_gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS départ — latitude')
    depart_gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS départ — longitude')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        ordering = ['-heure_arrivee', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_pointage_comp_employe_idx'),
            models.Index(
                fields=['company', 'heure_arrivee'],
                name='rh_pointage_comp_arrivee_idx'),
        ]

    @property
    def duree_minutes(self):
        """Durée travaillée en minutes (None si arrivée ou départ absent)."""
        if self.heure_arrivee and self.heure_depart:
            delta = self.heure_depart - self.heure_arrivee
            return max(0, int(delta.total_seconds() // 60))
        return None

    def __str__(self):
        return (f'{self.employe.matricule} — '
                f'{self.heure_arrivee} ({self.get_type_pointage_display()})')


class FeuilleTemps(models.Model):
    """Feuille de temps par chantier (FG167) — heures imputées à une Installation.

    Distinct du ``Pointage`` (clock-in/out brut) : ici on IMPUTE des heures de
    main-d'œuvre à un chantier (``installations.Installation``) pour le calcul
    du coût réel en job-costing. Optionnellement lié à une intervention SAV
    (``intervention_id``, string FK lazy — on ne veut pas importer sav.models).

    Champs :
    * ``employe`` — technicien dont les heures sont imputées.
    * ``installation_id`` — FK string vers ``installations.Installation`` (jamais
      importé directement — cross-app boundary via string FK).
    * ``intervention_id`` — FK string facultative vers ``sav.Intervention`` (même
      règle).
    * ``date`` — journée d'imputation.
    * ``heures`` — durée imputée en heures décimales (ex. 7,5).
    * ``taux_horaire`` — taux appliqué (copié du ``cout_horaire`` au moment de la
      saisie ; INTERNE, jamais exposé côté client). NULL = pas encore valorisé.
    * ``cout_calcule`` — heures × taux_horaire (propriété calculée, non stockée).
    * ``description`` — nature du travail (pose, câblage, test…).

    Le ``cout_horaire`` est strictement INTERNE (jamais dans une réponse client) ;
    seul un accès Administrateur/Responsable peut lire ce champ.

    Multi-société : ``company`` posée côté serveur (jamais lue du corps de requête).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_feuilles_temps',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='feuilles_temps',
        verbose_name='Employé',
    )
    # String FK cross-app — jamais importer installations.models directement.
    installation_id = models.PositiveIntegerField(
        verbose_name="Installation (ID)")
    # Référence optionnelle à une intervention SAV (cross-app string FK).
    intervention_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Intervention (ID, optionnel)')
    date = models.DateField(verbose_name="Date d'imputation")
    heures = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Heures imputées')
    # Taux horaire INTERNE (copié du dossier employé au moment de la saisie).
    # NULL = non valorisé (pas de coût disponible).
    taux_horaire = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Taux horaire (interne)')
    description = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Nature du travail')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Feuille de temps'
        verbose_name_plural = 'Feuilles de temps'
        ordering = ['-date', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'employe']),
            models.Index(fields=['company', 'installation_id']),
            models.Index(fields=['company', 'date']),
        ]

    @property
    def cout_calcule(self):
        """Coût de main-d'œuvre = heures × taux_horaire (None si non valorisé)."""
        if self.heures is not None and self.taux_horaire is not None:
            return self.heures * self.taux_horaire
        return None

    def __str__(self):
        return (f'{self.employe.matricule} — installation#{self.installation_id}'
                f' {self.date} : {self.heures}h')


class HeuresSupp(models.Model):
    """Heures supplémentaires & calcul majoré (FG168) — entrée de paie.

    Détecte les heures supplémentaires d'un employé sur une journée (au-delà du
    seuil légal) et leur applique le taux de majoration marocain. Le droit du
    travail marocain (code du travail, art. 196 & 201) fixe la durée normale à
    44 h/semaine (≈ 8 h/jour) et majore les heures effectuées au-delà :

    * **+25 %** — heures sup. de JOUR (entre 6 h et 21 h) un jour ouvrable ;
    * **+50 %** — heures sup. de NUIT (entre 21 h et 6 h) un jour ouvrable ;
    * **+50 %** — heures sup. de JOUR un jour de repos hebdomadaire ou férié ;
    * **+100 %** — heures sup. de NUIT un jour de repos hebdomadaire ou férié.

    Modèle de saisie (journalier) : on enregistre, pour une ``date`` donnée, les
    heures travaillées (``heures_travaillees``) au-delà desquelles on dépasse le
    ``seuil_journalier`` (défaut 8 h), avec la part effectuée de NUIT
    (``heures_nuit``) et un drapeau ``jour_repos_ferie`` (jour de repos ou férié).
    À partir de ces entrées, ``services.calculer_majoration`` répartit les heures
    supplémentaires dans les quatre tranches de taux et calcule le montant majoré
    consommable par la paie (via le ``cout_horaire`` interne du dossier).

    Les quatre décomptes (``hs_25``, ``hs_50``, ``hs_100`` + heures normales) et
    le ``montant_majore`` sont CALCULÉS et STOCKÉS côté serveur à la saisie pour
    rester stables (la paie les relit tels quels). Multi-société : ``company``
    posée côté serveur (jamais lue du corps). Le ``cout_horaire`` reste INTERNE :
    il n'apparaît dans aucune sortie client.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_heures_supp',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='heures_supp',
        verbose_name='Employé',
    )
    date = models.DateField(verbose_name='Date')
    heures_travaillees = models.DecimalField(
        max_digits=6, decimal_places=2,
        verbose_name='Heures travaillées')
    # Part des heures effectuée de NUIT (21 h–6 h). Bornée aux heures sup.
    heures_nuit = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Heures de nuit')
    # Seuil journalier au-delà duquel les heures deviennent supplémentaires.
    seuil_journalier = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('8'),
        verbose_name='Seuil journalier')
    # Jour de repos hebdomadaire OU jour férié → tranche 50 %/100 %.
    jour_repos_ferie = models.BooleanField(
        default=False, verbose_name='Jour de repos / férié')
    # Décomptes répartis (calculés à la saisie, relus tels quels par la paie).
    heures_normales = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Heures normales')
    hs_25 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='HS majorées 25 %')
    hs_50 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='HS majorées 50 %')
    hs_100 = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='HS majorées 100 %')
    # Taux horaire INTERNE (copié du dossier au moment de la saisie ; NULL = non
    # valorisé). Le montant majoré en découle ; jamais exposé côté client.
    taux_horaire = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Taux horaire (interne)')
    montant_majore = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        verbose_name='Montant majoré (interne)')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Heures supplémentaires'
        verbose_name_plural = 'Heures supplémentaires'
        ordering = ['-date', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_hsupp_comp_employe_idx'),
            models.Index(
                fields=['company', 'date'],
                name='rh_hsupp_comp_date_idx'),
        ]

    @property
    def total_hs(self):
        """Total des heures supplémentaires (toutes tranches confondues)."""
        return (self.hs_25 or Decimal('0')) + (self.hs_50 or Decimal('0')) \
            + (self.hs_100 or Decimal('0'))

    def __str__(self):
        return (f'{self.employe.matricule} — {self.date} : '
                f'{self.total_hs} HS')


class DemandeConge(models.Model):
    """Demande & validation de congés (FG163) — workflow employé → superviseur/RH.

    Un employé soumet une demande (type d'absence + dates) ; un superviseur/RH la
    valide ou la refuse. Le nombre de jours décomptés est calculé à la soumission
    (``services.calculer_jours_demande``) : jours OUVRÉS (hors week-end et jours
    fériés, cf. FG5 / ``working_days``) si le type le requiert, sinon jours
    calendaires. À la validation, si le type ``deduit_solde``, la durée est
    ajoutée au compteur ``pris`` du ``SoldeConge`` de l'année. Multi-société :
    ``company`` posée côté serveur ; ``employe`` et ``type_absence`` doivent
    appartenir à la même société.
    """
    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        VALIDEE = 'validee', 'Validée'
        REFUSEE = 'refusee', 'Refusée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_demandes_conge',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='demandes_conge',
        verbose_name='Employé',
    )
    type_absence = models.ForeignKey(
        TypeAbsence,
        on_delete=models.PROTECT,
        related_name='demandes',
        verbose_name="Type d'absence",
    )
    date_debut = models.DateField(verbose_name='Du')
    date_fin = models.DateField(verbose_name='Au')
    jours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Jours décomptés')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.SOUMISE, verbose_name='Statut')
    # Décision (validation/refus) : qui et quand, côté serveur.
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_demandes_decidees',
        verbose_name='Décidé par',
    )
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de décision')
    motif_refus = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de refus')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Demande de congés'
        verbose_name_plural = 'Demandes de congés'
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            models.Index(fields=['company', 'employe']),
            models.Index(fields=['company', 'statut']),
            models.Index(fields=['company', 'date_debut', 'date_fin']),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — {self.type_absence.code} '
                f'{self.date_debut}→{self.date_fin} ({self.get_statut_display()})')


class AffectationRoster(models.Model):
    """Planning d'équipes / roster (FG169) — affectation hebdomadaire d'un
    technicien à une équipe et, optionnellement, à une camionnette.

    Une ligne de roster affecte UN employé (``employe``) à UNE journée
    (``date``) au sein d'une ``equipe`` (libellé normalisé d'équipe terrain,
    p. ex. « Équipe Nord », « Pose A ») et, facultativement, à une camionnette
    du parc (``vehicule_id`` — STRING-FK vers ``flotte.Vehicule`` : on ne
    référence jamais ``flotte.models`` directement, exactement comme
    ``FeuilleTemps.installation_id``). Le roster se construit semaine par semaine
    (sept lignes/jour par technicien) ; ``semaine_du`` mémorise le lundi de la
    semaine pour grouper l'affichage et les requêtes hebdomadaires.

    DÉTECTION DE CONFLIT DE CONGÉS : un technicien ayant une demande de congé
    VALIDÉE couvrant la journée d'affectation ne devrait PAS y être affecté.
    Le champ ``conflit_conge`` matérialise ce conflit (calculé côté serveur à la
    création/màj via ``services.detecter_conflit_conge`` qui réutilise le
    sélecteur congés ``employe_absent_le``). Il n'est jamais lu du corps.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Une seule affectation par
    (société, employé, jour) — un technicien n'est pas sur deux équipes le même
    jour (``unique_together``).
    """
    class Creneau(models.TextChoices):
        JOURNEE = 'journee', 'Journée'
        MATIN = 'matin', 'Matin'
        APRES_MIDI = 'apres_midi', 'Après-midi'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_affectations_roster',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='affectations_roster',
        verbose_name='Employé',
    )
    equipe = models.CharField(max_length=120, verbose_name='Équipe')
    # String FK cross-app vers flotte.Vehicule — jamais importer flotte.models.
    vehicule_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Camionnette (ID, optionnel)')
    date = models.DateField(verbose_name="Date d'affectation")
    # Lundi de la semaine concernée (posé côté serveur à partir de ``date``).
    semaine_du = models.DateField(
        null=True, blank=True, verbose_name='Semaine du (lundi)')
    creneau = models.CharField(
        max_length=10, choices=Creneau.choices,
        default=Creneau.JOURNEE, verbose_name='Créneau')
    # Conflit de congé : vrai si l'employé est en congé VALIDÉ ce jour-là.
    # Calculé côté serveur (jamais lu du corps de requête).
    conflit_conge = models.BooleanField(
        default=False, verbose_name='Conflit de congé')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Affectation roster"
        verbose_name_plural = "Affectations roster"
        unique_together = [('company', 'employe', 'date')]
        ordering = ['-date', 'equipe', 'employe']
        indexes = [
            models.Index(
                fields=['company', 'semaine_du'],
                name='rh_roster_comp_semaine_idx'),
            models.Index(
                fields=['company', 'equipe'],
                name='rh_roster_comp_equipe_idx'),
            models.Index(
                fields=['company', 'date'],
                name='rh_roster_comp_date_idx'),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — {self.equipe} '
                f'{self.date} ({self.get_creneau_display()})')


class PresenceChantier(models.Model):
    """Registre de présence chantier journalier / émargement (FG170).

    Trace QUI était présent sur QUEL chantier (``installation_id`` — STRING-FK
    vers ``installations.Installation``, jamais ``installations.models``, comme
    ``FeuilleTemps``) un jour donné. Sert de preuve en cas de litige et de base
    de facturation main-d'œuvre. Une ligne par (société, employé, installation,
    jour).

    ÉMARGEMENT : ``emarge`` matérialise la signature/confirmation de présence
    (avec ``emarge_le`` et ``emarge_par`` posés côté serveur via l'action
    ``emarger``). Le ``statut`` distingue présent / absent / retard / parti tôt
    (utile au croisement litiges/facturation). ``heure_arrivee``/``heure_depart``
    sont des heures saisies sur site (facultatives, distinctes du clock-in/out
    brut ``Pointage``). Multi-société : ``company`` posée côté serveur, jamais lue
    du corps de requête ; ``employe`` doit appartenir à la même société.
    """
    class Statut(models.TextChoices):
        PRESENT = 'present', 'Présent'
        ABSENT = 'absent', 'Absent'
        RETARD = 'retard', 'En retard'
        PARTI_TOT = 'parti_tot', 'Parti tôt'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_presences_chantier',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='presences_chantier',
        verbose_name='Employé',
    )
    # String FK cross-app vers installations.Installation — jamais d'import.
    installation_id = models.PositiveIntegerField(
        verbose_name="Installation (ID)")
    date = models.DateField(verbose_name='Date')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PRESENT, verbose_name='Statut')
    heure_arrivee = models.TimeField(
        null=True, blank=True, verbose_name="Heure d'arrivée")
    heure_depart = models.TimeField(
        null=True, blank=True, verbose_name='Heure de départ')
    # Émargement : signature/confirmation de présence (posée via l'action).
    emarge = models.BooleanField(default=False, verbose_name='Émargé')
    emarge_le = models.DateTimeField(
        null=True, blank=True, verbose_name="Émargé le")
    emarge_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_presences_emargees',
        verbose_name='Émargé par',
    )
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Présence chantier'
        verbose_name_plural = 'Présences chantier'
        unique_together = [('company', 'employe', 'installation_id', 'date')]
        ordering = ['-date', 'installation_id', 'employe']
        indexes = [
            models.Index(
                fields=['company', 'installation_id', 'date'],
                name='rh_presence_inst_date_idx'),
            models.Index(
                fields=['company', 'employe', 'date'],
                name='rh_presence_emp_date_idx'),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — installation#{self.installation_id}'
                f' {self.date} ({self.get_statut_display()})')


class IncidentPresence(models.Model):
    """Retards & absences injustifiées (FG171) — marquage + base de comptage.

    Chaque ligne marque UN incident de présence d'un employé : un RETARD (avec
    ``minutes_retard``) ou une ABSENCE INJUSTIFIÉE sur une ``date``. Sert de
    socle disciplinaire et de pilotage : un compteur par employé/période se
    calcule par agrégation (``selectors.compteur_incidents``) — on ne stocke pas
    le total, on le dérive.

    Un incident peut être RÉGULARISÉ a posteriori (``justifie=True`` + ``motif``
    + ``justifie_par``/``justifie_le`` posés côté serveur) : un retard couvert
    par un justificatif ou une absence finalement justifiée sort du décompte
    disciplinaire sans perdre la trace. Multi-société : ``company`` posée côté
    serveur (jamais lue du corps) ; ``employe`` doit appartenir à la même société.
    """
    class TypeIncident(models.TextChoices):
        RETARD = 'retard', 'Retard'
        ABSENCE_INJUSTIFIEE = 'absence_injustifiee', 'Absence injustifiée'
        DEPART_ANTICIPE = 'depart_anticipe', 'Départ anticipé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_incidents_presence',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='incidents_presence',
        verbose_name='Employé',
    )
    type_incident = models.CharField(
        max_length=20, choices=TypeIncident.choices,
        default=TypeIncident.RETARD, verbose_name="Type d'incident")
    date = models.DateField(verbose_name='Date')
    # Retard/départ anticipé : nombre de minutes (0 pour une absence).
    minutes_retard = models.PositiveIntegerField(
        default=0, verbose_name='Minutes de retard')
    # Régularisation : un incident justifié sort du décompte disciplinaire.
    justifie = models.BooleanField(default=False, verbose_name='Justifié')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    justifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_incidents_justifies',
        verbose_name='Justifié par',
    )
    justifie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Justifié le')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Incident de présence'
        verbose_name_plural = 'Incidents de présence'
        ordering = ['-date', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe', 'date'],
                name='rh_incident_emp_date_idx'),
            models.Index(
                fields=['company', 'type_incident'],
                name='rh_incident_comp_type_idx'),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — '
                f'{self.get_type_incident_display()} {self.date}')


class Competence(models.Model):
    """Référentiel de compétences métier (FG172) — catalogue par société.

    Catalogue des savoir-faire techniques évalués chez les équipes terrain :
    pose structure, raccordement DC/AC, MES onduleur, pompage, soudure… Chaque
    compétence porte un ``domaine`` (regroupement métier) et un ``libelle``
    libre. Le niveau d'un employé sur une compétence vit dans
    ``CompetenceEmploye`` (la matrice). Multi-société : ``company`` posée côté
    serveur (jamais lue du corps). Le couple (société, code) est unique.
    """
    class Domaine(models.TextChoices):
        POSE_STRUCTURE = 'pose_structure', 'Pose structure'
        RACCORDEMENT_DC = 'raccordement_dc', 'Raccordement DC'
        RACCORDEMENT_AC = 'raccordement_ac', 'Raccordement AC'
        MES_ONDULEUR = 'mes_onduleur', 'MES onduleur'
        POMPAGE = 'pompage', 'Pompage'
        SOUDURE = 'soudure', 'Soudure'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_competences',
        verbose_name='Société',
    )
    code = models.CharField(max_length=40, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    domaine = models.CharField(
        max_length=20, choices=Domaine.choices,
        default=Domaine.AUTRE, verbose_name='Domaine')
    description = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Description')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Compétence'
        verbose_name_plural = 'Compétences'
        ordering = ['domaine', 'libelle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='rh_competence_uniq_code'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'domaine'],
                name='rh_competence_dom_idx'),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class CompetenceEmploye(models.Model):
    """Matrice de compétences — niveau d'un employé sur une compétence (FG172).

    Une ligne par (société, employé, compétence) : le ``niveau`` situe l'employé
    sur l'échelle (0 non acquis → 4 expert). Le couple (employé, compétence) est
    unique : on met à jour la ligne plutôt que d'en empiler. ``evalue_le`` /
    ``evalue_par`` tracent la dernière évaluation côté serveur. Multi-société :
    ``company`` posée côté serveur (jamais lue du corps) ; ``employe`` et
    ``competence`` doivent appartenir à la même société.
    """
    class Niveau(models.IntegerChoices):
        NON_ACQUIS = 0, 'Non acquis'
        DEBUTANT = 1, 'Débutant'
        INTERMEDIAIRE = 2, 'Intermédiaire'
        CONFIRME = 3, 'Confirmé'
        EXPERT = 4, 'Expert'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_competences_employe',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='competences',
        verbose_name='Employé',
    )
    competence = models.ForeignKey(
        Competence,
        on_delete=models.CASCADE,
        related_name='niveaux_employes',
        verbose_name='Compétence',
    )
    niveau = models.PositiveSmallIntegerField(
        choices=Niveau.choices, default=Niveau.NON_ACQUIS,
        verbose_name='Niveau')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    evalue_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Évalué le')
    evalue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_competences_evaluees',
        verbose_name='Évalué par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Niveau de compétence'
        verbose_name_plural = 'Niveaux de compétence'
        ordering = ['competence', '-niveau']
        constraints = [
            models.UniqueConstraint(
                fields=['employe', 'competence'],
                name='rh_competence_emp_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'competence', 'niveau'],
                name='rh_comp_emp_lvl_idx'),
            models.Index(
                fields=['company', 'employe'],
                name='rh_comp_emp_idx'),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — {self.competence.code} '
                f'({self.get_niveau_display()})')


class Habilitation(models.Model):
    """Habilitation électrique par employé (FG173) — titre + validité/organisme.

    Concept DISTINCT de la matrice de compétences (FG172,
    ``Competence``/``CompetenceEmploye``) : une compétence situe un niveau de
    savoir-faire ; une HABILITATION électrique est un TITRE réglementaire,
    délivré par un organisme, avec une DATE DE VALIDITÉ (échéance) — exigé sur
    tout chantier PV (norme NF C 18-510 : B0/H0 non-électricien, B1V/B2V
    exécutant/chargé de travaux en BT, BR intervention BT générale, BC
    consignation, H0/H1V/H2V/HC pour la HT…).

    Une ligne par titre détenu par un employé. ``valide`` est CALCULÉ (le titre
    est actif ET sa date de validité n'est pas dépassée — un titre sans échéance
    reste valide tant qu'il est ``actif``). Un sélecteur/endpoint liste les
    habilitations qui expirent bientôt ou sont déjà expirées (``?expire_within=``).

    Multi-société : ``company`` posée côté serveur (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société.
    """
    class TypeHabilitation(models.TextChoices):
        # Norme NF C 18-510 — basse tension (B) puis haute tension (H).
        B0 = 'b0', "B0 — Non-électricien (travaux d'ordre non électrique BT)"
        H0 = 'h0', 'H0 — Non-électricien (zone HT)'
        H0V = 'h0v', 'H0V — Non-électricien (voisinage HT)'
        B1 = 'b1', 'B1 — Exécutant électricien BT'
        B1V = 'b1v', 'B1V — Exécutant électricien BT (voisinage)'
        B2 = 'b2', 'B2 — Chargé de travaux BT'
        B2V = 'b2v', 'B2V — Chargé de travaux BT (voisinage)'
        BR = 'br', "BR — Chargé d'intervention générale BT"
        BC = 'bc', 'BC — Chargé de consignation BT'
        BE = 'be', "BE — Chargé d'opérations spécifiques BT"
        H1 = 'h1', 'H1 — Exécutant électricien HT'
        H1V = 'h1v', 'H1V — Exécutant électricien HT (voisinage)'
        H2 = 'h2', 'H2 — Chargé de travaux HT'
        H2V = 'h2v', 'H2V — Chargé de travaux HT (voisinage)'
        HC = 'hc', 'HC — Chargé de consignation HT'
        BP = 'bp', 'BP — Photovoltaïque (opérations sur installation PV)'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_habilitations',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='habilitations',
        verbose_name='Employé',
    )
    type_habilitation = models.CharField(
        max_length=10, choices=TypeHabilitation.choices,
        default=TypeHabilitation.B1V, verbose_name="Titre d'habilitation")
    # Organisme délivrant le titre (centre de formation, employeur habilité…).
    organisme = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Organisme délivrant')
    date_obtention = models.DateField(
        null=True, blank=True, verbose_name="Date d'obtention")
    # Échéance du titre : NULL = sans date de validité (rare ; reste valide tant
    # que ``actif``). Un titre dont l'échéance est passée n'est plus ``valide``.
    date_validite = models.DateField(
        null=True, blank=True, verbose_name='Date de validité (échéance)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Habilitation électrique'
        verbose_name_plural = 'Habilitations électriques'
        ordering = ['employe', 'type_habilitation']
        constraints = [
            # Un employé ne détient qu'UNE ligne par titre (on met à jour la
            # validité plutôt que d'empiler des doublons).
            models.UniqueConstraint(
                fields=['employe', 'type_habilitation'],
                name='rh_habil_emp_type_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_habil_comp_emp_idx'),
            models.Index(
                fields=['company', 'date_validite'],
                name='rh_habil_comp_valid_idx'),
        ]

    @property
    def valide(self):
        """Vrai si le titre est actif ET non expiré.

        Un titre sans ``date_validite`` reste valide tant qu'il est ``actif``.
        Sinon il est valide jusqu'au jour de l'échéance inclus.
        """
        if not self.actif:
            return False
        if self.date_validite is None:
            return True
        from django.utils import timezone
        return self.date_validite >= timezone.localdate()

    def __str__(self):
        return (f'{self.employe.matricule} — '
                f'{self.get_type_habilitation_display()}')
