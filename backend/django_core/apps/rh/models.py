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
