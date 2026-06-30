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


class Certification(models.Model):
    """Certification spécifique par employé (FG174) — hauteur/harnais/CACES/SST…

    Famille DISTINCTE des habilitations électriques (FG173, ``Habilitation``,
    norme NF C 18-510) : ici les certifications NON électriques exigées en
    chantier PV — travail en hauteur, port du harnais, CACES/conduite de
    nacelle, secourisme du travail (SST), conduite (permis/engins). Comme pour
    une habilitation, c'est un TITRE délivré par un organisme avec une DATE DE
    VALIDITÉ (expiration), mais on ne mélange pas les deux familles.

    Une ligne par certification détenue par un employé. ``valide`` est CALCULÉ
    (la certification est active ET sa date de validité n'est pas dépassée — une
    certification sans échéance reste valide tant qu'elle est ``actif``). Un
    sélecteur/endpoint liste les certifications qui expirent bientôt ou sont
    déjà expirées (``?expire_within=``).

    Multi-société : ``company`` posée côté serveur (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société.
    """
    class TypeCertification(models.TextChoices):
        TRAVAIL_HAUTEUR = 'travail_hauteur', 'Travail en hauteur'
        HARNAIS = 'harnais', 'Port du harnais / EPI antichute'
        CACES_NACELLE = 'caces_nacelle', 'CACES / nacelle (PEMP)'
        SECOURISME_SST = 'secourisme_sst', \
            'Secourisme du travail (SST)'
        CONDUITE = 'conduite', 'Conduite (permis / engins)'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_certifications',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='certifications',
        verbose_name='Employé',
    )
    type_certification = models.CharField(
        max_length=20, choices=TypeCertification.choices,
        default=TypeCertification.TRAVAIL_HAUTEUR,
        verbose_name='Type de certification')
    # Organisme délivrant le titre (centre de formation, organisme agréé…).
    organisme = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Organisme délivrant')
    date_obtention = models.DateField(
        null=True, blank=True, verbose_name="Date d'obtention")
    # Échéance du titre : NULL = sans date de validité (reste valide tant que
    # ``actif``). Une certification dont l'échéance est passée n'est plus
    # ``valide``.
    date_validite = models.DateField(
        null=True, blank=True, verbose_name='Date de validité (expiration)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Certification spécifique'
        verbose_name_plural = 'Certifications spécifiques'
        ordering = ['employe', 'type_certification']
        constraints = [
            # Un employé ne détient qu'UNE ligne par certification (on met à
            # jour la validité plutôt que d'empiler des doublons).
            models.UniqueConstraint(
                fields=['employe', 'type_certification'],
                name='rh_cert_emp_type_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_cert_comp_emp_idx'),
            models.Index(
                fields=['company', 'date_validite'],
                name='rh_cert_comp_valid_idx'),
        ]

    @property
    def valide(self):
        """Vrai si la certification est active ET non expirée.

        Une certification sans ``date_validite`` reste valide tant qu'elle est
        ``actif``. Sinon elle est valide jusqu'au jour de l'échéance inclus.
        """
        if not self.actif:
            return False
        if self.date_validite is None:
            return True
        from django.utils import timezone
        return self.date_validite >= timezone.localdate()

    def __str__(self):
        return (f'{self.employe.matricule} — '
                f'{self.get_type_certification_display()}')


class VisiteMedicale(models.Model):
    """Visite médicale du travail par employé (FG177) — aptitude + échéance.

    Famille DISTINCTE des habilitations électriques (FG173, ``Habilitation``)
    et des certifications (FG174, ``Certification``) : la visite médicale du
    travail est l'examen de la médecine du travail qui prononce l'APTITUDE du
    salarié à son poste — obligatoire pour le chantier (Code du travail
    marocain, médecine du travail). On enregistre la dernière visite
    (``date_visite``), la prochaine échéance (``prochaine_visite``, p. ex.
    annuelle), le VERDICT D'APTITUDE (apte / apte avec restrictions / inapte),
    le médecin/organisme et d'éventuelles restrictions de poste.

    Une ligne par visite (on garde l'historique des visites) ; ``a_jour`` est
    CALCULÉ : la visite est à jour si elle est active ET que la prochaine visite
    n'est pas dépassée (une visite sans prochaine échéance reste à jour tant
    qu'elle est ``actif``). Un sélecteur/endpoint liste les visites dont la
    prochaine échéance arrive bientôt ou est déjà dépassée (``?expire_within=``)
    — c'est l'alerte exigée avant toute affectation chantier.

    Multi-société : ``company`` posée côté serveur (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société.
    """
    class Aptitude(models.TextChoices):
        APTE = 'apte', 'Apte'
        APTE_AVEC_RESTRICTIONS = 'apte_avec_restrictions', \
            'Apte avec restrictions'
        INAPTE = 'inapte', 'Inapte'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_visites_medicales',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='visites_medicales',
        verbose_name='Employé',
    )
    date_visite = models.DateField(
        null=True, blank=True, verbose_name='Date de la visite')
    # Prochaine échéance : NULL = pas de prochaine visite planifiée (reste à
    # jour tant que ``actif``). Une visite dont la prochaine échéance est passée
    # n'est plus ``a_jour``.
    prochaine_visite = models.DateField(
        null=True, blank=True,
        verbose_name='Prochaine visite (échéance)')
    aptitude = models.CharField(
        max_length=24, choices=Aptitude.choices,
        default=Aptitude.APTE, verbose_name="Verdict d'aptitude")
    # Médecin du travail ayant prononcé l'aptitude.
    medecin = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Médecin du travail')
    # Organisme / service de médecine du travail.
    organisme = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Organisme / service de santé au travail')
    # Restrictions de poste prononcées (en cas d'aptitude avec restrictions).
    restrictions = models.TextField(
        blank=True, default='', verbose_name='Restrictions de poste')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Visite médicale du travail'
        verbose_name_plural = 'Visites médicales du travail'
        ordering = ['employe', '-date_visite']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_vismed_comp_emp_idx'),
            models.Index(
                fields=['company', 'prochaine_visite'],
                name='rh_vismed_comp_proch_idx'),
        ]

    @property
    def a_jour(self):
        """Vrai si la visite est active ET sa prochaine échéance non dépassée.

        Une visite sans ``prochaine_visite`` reste à jour tant qu'elle est
        ``actif``. Sinon elle est à jour jusqu'au jour de l'échéance inclus.
        """
        if not self.actif:
            return False
        if self.prochaine_visite is None:
            return True
        from django.utils import timezone
        return self.prochaine_visite >= timezone.localdate()

    def __str__(self):
        return (f'{self.employe.matricule} — '
                f'{self.get_aptitude_display()}')


def _ajouter_mois(date_depart, mois):
    """Ajoute ``mois`` mois à ``date_depart`` (clamp fin de mois).

    Brique d'arithmétique de dates pour la péremption/le recontrôle des EPI
    (FG179), SANS dépendance externe (pas de ``dateutil``). Le jour est borné au
    dernier jour du mois cible — ainsi le 31 janvier + 1 mois = 28/29 février.
    Renvoie ``None`` si ``date_depart`` ou ``mois`` est absent/None.
    """
    import datetime as _dt

    if date_depart is None or mois is None:
        return None
    mois = int(mois)
    total = (date_depart.month - 1) + mois
    annee = date_depart.year + total // 12
    mois_cible = total % 12 + 1
    # Dernier jour du mois cible (jour 1 du mois suivant - 1 jour).
    if mois_cible == 12:
        dernier_jour = 31
    else:
        premier_mois_suivant = _dt.date(annee, mois_cible + 1, 1)
        dernier_jour = (premier_mois_suivant - _dt.timedelta(days=1)).day
    jour = min(date_depart.day, dernier_jour)
    return _dt.date(annee, mois_cible, jour)


class EpiCatalogue(models.Model):
    """Catalogue des EPI de la société (FG178) — équipement de protection.

    Référentiel des équipements de protection individuelle (EPI) que la société
    attribue à ses équipes chantier : casque, harnais antichute, gants isolants,
    chaussures de sécurité, lunettes… Une ligne par modèle/référence d'EPI ; la
    DOTATION nominative (qui porte quel EPI, en quelle taille, depuis quelle
    date) est portée par ``DotationEpi``.

    Famille DISTINCTE des habilitations (FG173), certifications (FG174) et
    visites médicales (FG177) : ici c'est le MATÉRIEL de protection attribué, pas
    un titre réglementaire. Le ``type_epi`` regroupe les dotations par famille
    d'équipement.

    Multi-société : ``company`` posée côté serveur (jamais lue du corps).
    """
    class TypeEpi(models.TextChoices):
        CASQUE = 'casque', 'Casque'
        HARNAIS = 'harnais', 'Harnais antichute'
        GANTS_ISOLANTS = 'gants_isolants', 'Gants isolants'
        CHAUSSURES = 'chaussures', 'Chaussures de sécurité'
        LUNETTES = 'lunettes', 'Lunettes de protection'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_epi_catalogue',
        verbose_name='Société',
    )
    type_epi = models.CharField(
        max_length=20, choices=TypeEpi.choices,
        default=TypeEpi.CASQUE, verbose_name="Type d'EPI")
    # Désignation lisible du modèle/référence (marque, norme…).
    designation = models.CharField(
        max_length=160, verbose_name='Désignation')
    # Durée de vie réglementaire en MOIS (FG179) : certains EPI sont à durée
    # de vie limitée (harnais antichute, longes…). NULL = pas de péremption
    # programmée. À la dotation, ``DotationEpi.date_peremption`` se dérive de
    # ``date_dotation + duree_vie_mois``.
    duree_vie_mois = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durée de vie (mois)')
    # Intervalle de recontrôle/vérification périodique en MOIS (FG179) : p. ex.
    # un harnais ou des gants isolants se recontrôlent tous les N mois. NULL =
    # pas de recontrôle programmé. À la dotation,
    # ``DotationEpi.date_prochain_controle`` se dérive de
    # ``date_dotation + intervalle_controle_mois``.
    intervalle_controle_mois = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Intervalle de contrôle (mois)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'EPI (catalogue)'
        verbose_name_plural = 'EPI (catalogue)'
        ordering = ['type_epi', 'designation']
        indexes = [
            models.Index(
                fields=['company', 'type_epi'],
                name='rh_epicat_comp_type_idx'),
        ]

    def __str__(self):
        return f'{self.get_type_epi_display()} — {self.designation}'


class DotationEpi(models.Model):
    """Dotation nominative d'un EPI à un employé (FG178) — taille + date.

    Attribue un EPI du catalogue (``EpiCatalogue``) à un employé, NOMINATIVEMENT,
    avec sa ``taille``, la ``date_dotation`` (remise) et une éventuelle
    ``date_renouvellement`` (échéance de remplacement — p. ex. un harnais
    antichute se renouvelle périodiquement). ``quantite`` permet de tracer
    plusieurs unités d'un même EPI.

    Si ``date_renouvellement`` est renseignée, la dotation alimente le moteur
    d'échéances RH (FG175) comme une alerte de remplacement à venir/dépassée.

    Multi-société : ``company`` posée côté serveur (jamais lue du corps) ;
    ``employe`` et ``epi`` doivent appartenir à la même société.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_dotations_epi',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='dotations_epi',
        verbose_name='Employé',
    )
    epi = models.ForeignKey(
        EpiCatalogue,
        on_delete=models.PROTECT,
        related_name='dotations',
        verbose_name='EPI',
    )
    # Taille attribuée (libre : « M », « 42 », « T9 »…).
    taille = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Taille')
    date_dotation = models.DateField(
        null=True, blank=True, verbose_name='Date de dotation')
    # Échéance de renouvellement : NULL = pas de renouvellement planifié. Une
    # dotation dont l'échéance est passée doit alerter (FG175).
    date_renouvellement = models.DateField(
        null=True, blank=True,
        verbose_name='Date de renouvellement (échéance)')
    # Date de péremption DÉRIVÉE (FG179) : ``date_dotation`` +
    # ``epi.duree_vie_mois``, calculée et stockée à la sauvegarde via
    # ``recalculer_echeances``. NULL = EPI sans durée de vie limitée (ou sans
    # date de dotation). Un EPI dont la péremption est passée doit alerter
    # (FG175, famille ``epi_peremption``).
    date_peremption = models.DateField(
        null=True, blank=True, verbose_name='Date de péremption')
    # Date de prochain recontrôle/vérification DÉRIVÉE (FG179) :
    # ``date_dotation`` + ``epi.intervalle_controle_mois``. NULL = pas de
    # recontrôle programmé. Un recontrôle dépassé doit alerter (FG175).
    date_prochain_controle = models.DateField(
        null=True, blank=True, verbose_name='Date de prochain contrôle')
    quantite = models.PositiveIntegerField(
        default=1, verbose_name='Quantité')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    # Accusé de remise (FG180) : marqueur posé côté serveur quand l'employé a
    # ÉMARGÉ la dotation (accusé de réception signé prouvant la remise de l'EPI,
    # exigible en cas de contrôle CNSS / accident du travail). La preuve
    # détaillée (nom dactylographié, IP, user agent, méthode) est portée par
    # ``EmargementEpi`` ; ce booléen est l'index rapide « cette dotation a-t-elle
    # un émargement valide ». Reste ``False`` tant que personne n'a émargé.
    accuse_remise = models.BooleanField(
        default=False, verbose_name='Remise émargée (accusée)')
    date_accuse = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Date de l'accusé de remise")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Dotation EPI'
        verbose_name_plural = 'Dotations EPI'
        ordering = ['employe', 'epi']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_dotepi_comp_emp_idx'),
            models.Index(
                fields=['company', 'date_renouvellement'],
                name='rh_dotepi_comp_renouv_idx'),
            models.Index(
                fields=['company', 'date_peremption'],
                name='rh_dotepi_comp_perem_idx'),
            models.Index(
                fields=['company', 'date_prochain_controle'],
                name='rh_dotepi_comp_ctrl_idx'),
        ]

    def recalculer_echeances(self):
        """Dérive ``date_peremption`` / ``date_prochain_controle`` (FG179).

        Calcule les deux échéances de cycle de vie à partir de la
        ``date_dotation`` et des durées portées par le catalogue
        (``epi.duree_vie_mois`` / ``epi.intervalle_controle_mois``). Sans date
        de dotation OU sans durée définie côté catalogue, l'échéance dérivée
        reste ``None``. N'effectue PAS de sauvegarde (appelée par ``save``).
        """
        epi = self.epi if self.epi_id else None
        duree = getattr(epi, 'duree_vie_mois', None) if epi else None
        intervalle = (
            getattr(epi, 'intervalle_controle_mois', None) if epi else None)
        self.date_peremption = _ajouter_mois(self.date_dotation, duree)
        self.date_prochain_controle = _ajouter_mois(
            self.date_dotation, intervalle)

    def save(self, *args, **kwargs):
        """Recalcule les échéances de cycle de vie avant chaque sauvegarde."""
        self.recalculer_echeances()
        super().save(*args, **kwargs)

    def perime(self, today=None):
        """Vrai si l'EPI a une date de péremption DÉPASSÉE (FG179).

        ``today`` injectable (par défaut ``timezone.localdate()``) rend le
        calcul déterministe/testable. Un EPI sans ``date_peremption`` n'est
        jamais périmé. Le jour de péremption inclus reste valide ; le lendemain
        est périmé.
        """
        if self.date_peremption is None:
            return False
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        return self.date_peremption < today

    def a_controler(self, today=None):
        """Vrai si le recontrôle périodique est échu/dépassé (FG179).

        ``today`` injectable (par défaut ``timezone.localdate()``). Un EPI sans
        ``date_prochain_controle`` n'est jamais à recontrôler. Le jour de
        contrôle inclus reste à jour ; le lendemain est à recontrôler.
        """
        if self.date_prochain_controle is None:
            return False
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        return self.date_prochain_controle < today

    def __str__(self):
        return f'{self.employe.matricule} — {self.epi}'


class EmargementEpi(models.Model):
    """Émargement de remise d'un EPI (FG180) — accusé signé de la dotation.

    Matérialise l'ACCUSÉ DE RÉCEPTION signé prouvant qu'un EPI (``DotationEpi``)
    a bien été REMIS à l'employé. C'est une pièce réglementaire : en cas de
    contrôle CNSS ou d'accident du travail, l'employeur doit pouvoir prouver
    qu'il a doté le salarié de l'équipement de protection — l'émargement signé
    en est la preuve.

    Signature électronique IN-APP, sur le modèle e-sign INTERNE de l'ERP
    (CONTRAT16) : AUCUN prestataire d'e-sign externe, AUCUNE dépendance tierce.
    La validité juridique repose sur la **loi marocaine 53-05** : un **nom
    dactylographié** (``signataire_nom``) consenti vaut signature. On enregistre
    QUI a émargé (le nom saisi + l'éventuel utilisateur agissant), à quel TITRE
    (``role_signataire`` : l'employé bénéficiaire, un témoin ou le responsable
    qui remet) et les ÉLÉMENTS DE PREUVE de l'acte (``ip_adresse``,
    ``user_agent``, ``date_signature``, ``methode``).

    Quand un émargement est enregistré, la dotation est marquée ACCUSÉE
    (``DotationEpi.accuse_remise = True`` + ``date_accuse``) par le service
    ``emarger_dotation``. C'est une couche distincte des échéances de cycle de
    vie (FG179) : ici on prouve la REMISE, pas la péremption.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps de
    requête) — celle de la dotation. ``signataire`` (l'utilisateur agissant)
    pointe vers ``AUTH_USER_MODEL`` (app foundation), FK autorisé et NULLABLE :
    un employé sans compte ERP émarge sur place (tablette du responsable) — seul
    son nom saisi et les preuves font foi.

    RUNTIME-SAFETY (leçon FG136) : ``ip_adresse`` ≤ 45 (IPv6 mappée) ;
    ``user_agent``, potentiellement très long, est un ``TextField`` (aucune
    limite à dépasser et lever) ; les codes bornés ``role_signataire`` /
    ``methode`` ≤ 20.
    """

    class RoleSignataire(models.TextChoices):
        # L'employé bénéficiaire qui reçoit l'EPI (accusé de réception).
        EMPLOYE = 'employe', 'Employé bénéficiaire'
        # Le responsable/encadrant qui remet l'EPI.
        REMETTANT = 'remettant', 'Remettant'
        # Un témoin de la remise.
        TEMOIN = 'temoin', 'Témoin'

    class Methode(models.TextChoices):
        # Saisie du nom dactylographié (loi 53-05) — méthode par défaut.
        TYPED = 'typed', 'Nom dactylographié'
        # Tracé manuscrit capturé (paraphe dessiné), évidence stockée ailleurs.
        DRAW = 'draw', 'Signature dessinée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_emargements_epi',
        verbose_name='Société',
    )
    dotation = models.ForeignKey(
        DotationEpi,
        on_delete=models.CASCADE,
        related_name='emargements',
        verbose_name='Dotation EPI',
    )
    # Nom dactylographié de celui qui émarge — fait foi (loi 53-05). Toujours
    # saisi.
    signataire_nom = models.CharField(
        max_length=255, verbose_name='Nom du signataire')
    # Utilisateur ERP ayant agi (NULL pour un employé sans compte qui émarge sur
    # place).
    signataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_emargements_epi',
        verbose_name='Utilisateur signataire',
    )
    role_signataire = models.CharField(
        max_length=20,
        choices=RoleSignataire.choices,
        default=RoleSignataire.EMPLOYE,
        verbose_name='Rôle du signataire',
    )
    date_signature = models.DateTimeField(
        auto_now_add=True, verbose_name='Émargé le')
    # Éléments de preuve. ``ip_adresse`` ≤ 45 (IPv6) ; ``user_agent`` en
    # TextField car potentiellement très long (leçon FG136).
    ip_adresse = models.CharField(
        max_length=45, blank=True, default='', verbose_name='Adresse IP')
    user_agent = models.TextField(
        blank=True, default='', verbose_name='User agent')
    methode = models.CharField(
        max_length=20,
        choices=Methode.choices,
        default=Methode.TYPED,
        verbose_name='Méthode de signature',
    )
    # Mention saisie au moment de l'émargement (« reçu en bon état », réserve…).
    mention = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Mention')

    class Meta:
        verbose_name = 'Émargement EPI'
        verbose_name_plural = 'Émargements EPI'
        ordering = ['-date_signature', 'id']
        indexes = [
            models.Index(
                fields=['company', 'dotation'],
                name='rh_emepi_comp_dot_idx'),
        ]

    def __str__(self):
        return f'{self.signataire_nom} — {self.dotation_id}'


class AccidentTravail(models.Model):
    """Registre HSE & accidents du travail (FG181) — déclaration + export CNSS.

    Matérialise la DÉCLARATION d'un accident du travail : qui (``employe``),
    quand (``date_accident``), où (``lieu``), la GRAVITÉ (léger / grave /
    mortel), la description des circonstances et l'éventuel ARRÊT DE TRAVAIL
    (``arret_travail`` + ``nb_jours_arret``). C'est une pièce réglementaire :
    au Maroc, l'employeur doit déclarer tout accident du travail (et de trajet)
    à la CNSS et à l'inspection du travail dans les délais légaux — ce registre
    en est le socle, et l'export ``?export=csv`` produit les champs d'une
    déclaration d'accident CNSS.

    Le suivi de la déclaration CNSS est porté par ``declare_cnss`` (la
    déclaration a-t-elle été transmise) + ``date_declaration_cnss``. Le
    ``statut`` (déclaré → clos) suit le cycle de vie du dossier d'accident.

    Numérotation : ``reference`` (``AT-YYYYMM-NNNN``) est posée CÔTÉ SERVEUR de
    façon race-safe via ``apps.ventes.utils.references.create_with_reference``
    (plus-haut-utilisé+1 par société/mois, savepoint + retry) — JAMAIS
    ``count()+1`` (qui collisionnait en production). Unique par société.

    Photos : ``photo_key`` référence un objet MinIO optionnel (preuve
    photographique des lieux/circonstances) — clé de stockage, pas un binaire.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps de
    requête) ; ``employe`` (le blessé) doit appartenir à la même société.

    RUNTIME-SAFETY (leçon FG136) : les codes bornés ``gravite`` / ``statut``
    ≤ 20 ; ``reference`` / ``lieu`` / ``photo_key`` plafonnés ; la description,
    potentiellement longue, est un ``TextField`` (aucune limite à dépasser).
    """

    class Gravite(models.TextChoices):
        LEGER = 'leger', 'Léger'
        GRAVE = 'grave', 'Grave'
        MORTEL = 'mortel', 'Mortel'

    class Statut(models.TextChoices):
        DECLARE = 'declare', 'Déclaré'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_accidents',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='rh_accidents',
        verbose_name='Employé blessé',
    )
    # Référence séquentielle posée côté serveur (AT-YYYYMM-NNNN), unique par
    # société. Race-safe (plus-haut-utilisé+1) — jamais count()+1.
    reference = models.CharField(
        max_length=30, verbose_name='Référence')
    date_accident = models.DateField(verbose_name="Date de l'accident")
    lieu = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Lieu')
    gravite = models.CharField(
        max_length=20, choices=Gravite.choices,
        default=Gravite.LEGER, verbose_name='Gravité')
    description = models.TextField(
        blank=True, default='', verbose_name='Description des circonstances')
    arret_travail = models.BooleanField(
        default=False, verbose_name='Arrêt de travail')
    nb_jours_arret = models.PositiveIntegerField(
        default=0, verbose_name="Nombre de jours d'arrêt")
    # Preuve photographique optionnelle (clé MinIO ; pas un binaire).
    photo_key = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Photo (clé)')
    # Suivi de la déclaration CNSS.
    declare_cnss = models.BooleanField(
        default=False, verbose_name='Déclaré à la CNSS')
    date_declaration_cnss = models.DateField(
        null=True, blank=True, verbose_name='Date de déclaration CNSS')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.DECLARE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Accident du travail'
        verbose_name_plural = 'Accidents du travail'
        ordering = ['-date_accident', '-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='rh_accident_ref_unique'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'date_accident'],
                name='rh_accident_comp_date_idx'),
            models.Index(
                fields=['company', 'gravite'],
                name='rh_accident_comp_grav_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_accident_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.reference} — {self.employe_id} ({self.gravite})'


class PresquAccident(models.Model):
    """Registre des presqu'accidents (near-miss, FG182) — pilotage HSE proactif.

    Un PRESQU'ACCIDENT (near-miss) est un événement qui aurait PU causer un
    accident mais ne l'a pas fait : aucun blessé, aucune déclaration CNSS. Le
    saisir vite sur le terrain est la base d'une prévention proactive — chaque
    presqu'accident remonté est un accident évité demain. C'est volontairement
    PLUS LÉGER que l'accident du travail (FG181, ``AccidentTravail``) : pas de
    personne blessée, pas d'arrêt de travail, pas de cycle de déclaration CNSS.

    On capture l'essentiel pour la saisie rapide : QUAND (``date_constat``), OÙ
    (``lieu`` + ``chantier_id`` optionnel, simple référence chaîne vers un
    chantier d'une autre app — pas de FK inter-app), CE QUI s'est passé
    (``description``), la GRAVITÉ POTENTIELLE (``gravite_potentielle`` : faible /
    moyenne / élevée — à quel point ça aurait pu mal tourner) et la MESURE
    CORRECTIVE prise ou à prendre (``mesure_corrective``). Le ``statut``
    (ouvert → traité) suit le traitement de l'action corrective.

    Traçabilité : ``declare_par`` (l'utilisateur qui remonte le presqu'accident)
    est posé CÔTÉ SERVEUR (jamais lu du corps de requête), nullable comme les
    autres champs d'acteur du module (cf. ``evalue_par``).

    Photos : ``photo_key`` référence un objet MinIO optionnel (preuve
    photographique de la situation dangereuse) — clé de stockage, pas un binaire.

    Numérotation : ``reference`` (``NM-YYYYMM-NNNN`` — *near-miss*) est posée
    CÔTÉ SERVEUR de façon race-safe via
    ``apps.ventes.utils.references.create_with_reference`` (plus-haut-utilisé+1
    par société/mois, savepoint + retry) — JAMAIS ``count()+1`` (qui
    collisionnait en production). Unique par société.

    Multi-société : ``company`` est posée côté serveur (jamais lue du corps).

    RUNTIME-SAFETY (leçon FG136) : les codes bornés ``gravite_potentielle`` /
    ``statut`` ≤ 20 ; ``reference`` / ``lieu`` / ``chantier_id`` / ``photo_key``
    plafonnés ; les descriptions, potentiellement longues, sont des
    ``TextField`` (aucune limite à dépasser).
    """

    class GravitePotentielle(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        ELEVEE = 'elevee', 'Élevée'

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        TRAITE = 'traite', 'Traité'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_presqu_accidents',
        verbose_name='Société',
    )
    # Référence séquentielle posée côté serveur (NM-YYYYMM-NNNN), unique par
    # société. Race-safe (plus-haut-utilisé+1) — jamais count()+1.
    reference = models.CharField(
        max_length=30, verbose_name='Référence')
    date_constat = models.DateField(verbose_name='Date du constat')
    lieu = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Lieu')
    # Référence chaîne optionnelle vers un chantier d'une autre app (pas de FK
    # inter-app) — saisie terrain libre.
    chantier_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Chantier (référence)')
    description = models.TextField(
        blank=True, default='',
        verbose_name='Description de la situation')
    gravite_potentielle = models.CharField(
        max_length=20, choices=GravitePotentielle.choices,
        default=GravitePotentielle.FAIBLE,
        verbose_name='Gravité potentielle')
    mesure_corrective = models.TextField(
        blank=True, default='', verbose_name='Mesure corrective')
    # Preuve photographique optionnelle (clé MinIO ; pas un binaire).
    photo_key = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Photo (clé)')
    # Qui a remonté le presqu'accident — posé côté serveur, jamais du corps.
    declare_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_presqu_accidents_declares',
        verbose_name='Déclaré par',
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.OUVERT, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Presqu'accident"
        verbose_name_plural = "Presqu'accidents"
        ordering = ['-date_constat', '-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='rh_presqaccident_ref_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'date_constat'],
                name='rh_presqacc_comp_date_idx'),
            models.Index(
                fields=['company', 'gravite_potentielle'],
                name='rh_presqacc_comp_grav_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_presqacc_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.reference} ({self.gravite_potentielle})'
