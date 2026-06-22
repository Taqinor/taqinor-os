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
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        SORTI = 'sorti', 'Sorti'

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
    poste = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Poste')
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
