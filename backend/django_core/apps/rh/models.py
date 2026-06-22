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
