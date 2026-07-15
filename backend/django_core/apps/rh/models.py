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
import hashlib
import hmac
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.crypto_fields import EncryptedCharField


class Departement(models.Model):
    """Département d'une société (regroupe des ``DossierEmploye``).

    XRH27 — ``parent`` (FK self nullable) modélise la HIÉRARCHIE de
    départements (ex. Direction → Pôle technique → Équipes pose), auparavant
    plate. ``clean()`` protège contre les cycles (A→B→A) en remontant TOUTE
    la chaîne d'ancêtres, pas seulement le lien direct.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_departements',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    code = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Code')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='enfants',
        verbose_name='Département parent',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Département'
        verbose_name_plural = 'Départements'
        unique_together = [('company', 'nom')]
        ordering = ['nom']

    def clean(self):
        """XRH27 — rejette un cycle A→B→A en remontant TOUTE la chaîne de
        ``parent`` (pas seulement le lien direct)."""
        from django.core.exceptions import ValidationError

        if self.parent_id is None:
            return
        if self.pk is not None and self.parent_id == self.pk:
            raise ValidationError(
                'Un département ne peut pas être son propre parent.')

        vus = set()
        courant = self.parent
        while courant is not None:
            if self.pk is not None and courant.pk == self.pk:
                raise ValidationError(
                    'Cycle de hiérarchie détecté : ce département est déjà '
                    "un ancêtre du parent choisi.")
            if courant.pk in vus:
                break  # cycle préexistant ailleurs — n'empêche pas CETTE sauvegarde
            vus.add(courant.pk)
            courant = courant.parent

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


class HoraireTravail(models.Model):
    """Gabarit d'horaire de travail (XRH8) — 44 h standard, Ramadan, saisonnier.

    Le seuil HS journalier de ``HeuresSupp`` et le décompte présence supposent
    aujourd'hui un horaire implicite (8 h/j). Ce modèle rend l'horaire EXPLICITE
    et périodable : une société peut activer un horaire Ramadan (ex. 6 h/j) sur
    une fenêtre ``date_debut``→``date_fin``, avec retour automatique au standard
    une fois la fenêtre passée (aucune ligne active à cette date-là).

    ``heures_semaine``/``heures_jour_defaut`` bornent la durée normale ;
    ``heures_jour_defaut`` alimente directement le seuil HS via
    ``selectors.horaire_actif``. ``date_debut``/``date_fin`` NULL = horaire
    permanent (le cas standard 44 h) ; une fenêtre bornée cible un horaire
    temporaire (Ramadan, saison haute…).
    """
    class TypeHoraire(models.TextChoices):
        STANDARD_44H = 'standard_44h', 'Standard 44h'
        RAMADAN = 'ramadan', 'Ramadan'
        SAISONNIER = 'saisonnier', 'Saisonnier'
        TEMPS_PARTIEL = 'temps_partiel', 'Temps partiel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_horaires_travail',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    heures_semaine = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('44'),
        verbose_name='Heures / semaine')
    heures_jour_defaut = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('8'),
        verbose_name='Heures / jour (défaut)')
    type_horaire = models.CharField(
        max_length=15, choices=TypeHoraire.choices,
        default=TypeHoraire.STANDARD_44H, verbose_name="Type d'horaire")
    date_debut = models.DateField(
        null=True, blank=True,
        verbose_name='Début de validité (vide = permanent)')
    date_fin = models.DateField(
        null=True, blank=True,
        verbose_name='Fin de validité (vide = permanent)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Horaire de travail'
        verbose_name_plural = 'Horaires de travail'
        ordering = ['nom']
        indexes = [
            models.Index(
                fields=['company', 'date_debut', 'date_fin'],
                name='rh_horaire_comp_periode_idx'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.get_type_horaire_display()})'


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
    cin = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='CIN')
    # Numéros légaux paie (Maroc) — facultatifs ; pas d'unicité ici (à étudier
    # en suivi : unicité par société sans piège AddField(unique, default)).
    cnss = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='N° CNSS')
    cimr = EncryptedCharField(
        max_length=20, blank=True, default='', verbose_name='N° CIMR')
    amo = EncryptedCharField(
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
    # XRH8 — horaire de travail assigné (nullable : le seuil HS par défaut
    # 8 h/j s'applique tant qu'aucun horaire n'est assigné, cf.
    # ``selectors.horaire_actif``).
    horaire = models.ForeignKey(
        HoraireTravail,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employes',
        verbose_name='Horaire de travail',
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
    rib = EncryptedCharField(
        max_length=40, blank=True, default='', verbose_name='RIB')
    # XRH1 — période d'essai (Code du travail marocain : 3 mois cadres / 1,5
    # mois employés, renouvelable UNE fois). ``essai_date_fin`` borne la
    # période en cours (nullable : la plupart des dossiers n'ont pas d'essai
    # en cours) ; ``essai_renouvele`` mémorise qu'un renouvellement a déjà eu
    # lieu (le Code n'en autorise qu'un).
    essai_date_fin = models.DateField(
        null=True, blank=True, verbose_name="Fin de période d'essai")
    essai_renouvele = models.BooleanField(
        default=False, verbose_name="Période d'essai renouvelée")

    # XRH5 — suivi de conformité de la déclaration d'entrée CNSS/AMO. On ne
    # TRANSMET rien à Damancom ici — action manuelle du fondateur, on TRACE
    # seulement (statut + date). Défaut ``a_faire`` : tout nouvel embauché en
    # a besoin par défaut.
    class DeclarationEntreeStatut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        DECLAREE = 'declaree', 'Déclarée'
        NON_REQUIS = 'non_requis', 'Non requis'

    declaration_entree_statut = models.CharField(
        max_length=12, choices=DeclarationEntreeStatut.choices,
        default=DeclarationEntreeStatut.A_FAIRE,
        verbose_name="Déclaration d'entrée CNSS/AMO")
    declaration_entree_date = models.DateField(
        null=True, blank=True, verbose_name="Date de déclaration d'entrée")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # XPLT14 — champs personnalisés (apps.customfields, module='employe').
    custom_data = models.JSONField(null=True, blank=True)
    # XRH10 — PIN court du kiosque de pointage partagé (tablette dépôt).
    # Unique par société ; JAMAIS exposé en liste (lecture-seule server-side,
    # exclu des serializers de listing — seul le endpoint kiosque le compare).
    code_pointage = models.CharField(
        max_length=12, blank=True, default='', verbose_name='Code pointage (PIN)')
    # ZRH16 — localisation de télétravail par jour de semaine (« Remote Work »
    # Odoo). Map jour->lieu parmi bureau/domicile/terrain/autre, TOUS
    # optionnels (clé absente = bureau par défaut). Purement informatif,
    # aucun impact paie/pointage. Clés attendues : 'lundi'..'dimanche'.
    localisation_hebdo = models.JSONField(
        blank=True, default=dict, verbose_name='Localisation hebdomadaire')

    # ── ARC19 — Pont additif (INTERNE) vers le répertoire unifié Tiers ──
    # FK nullable (string-FK ``'tiers.Tiers'`` — jamais d'import de
    # apps.tiers.models ici). Le dossier employé est une partie prenante
    # INTERNE : le miroir ne pose AUCUN rôle client/fournisseur (drapeau dédié
    # côté Tiers réservé à un usage futur). Pas de fusion RIB ici (voir ARC25) :
    # le miroir n'écrit que l'identité (nom/prénom/CIN/contact), jamais le RIB
    # de paie. L'identité reste MAÎTRE côté dossier ; ``tiers`` n'en est qu'un
    # reflet réversible, posé par apps/rh/tiers_bridge.py.
    tiers = models.ForeignKey(
        'tiers.Tiers',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='dossiers_employe',
        verbose_name='Tiers (répertoire unifié)',
        help_text="Fiche du répertoire unifié reflétant ce collaborateur "
                  "(partie interne). Renseignée automatiquement (miroir).")

    class Meta:
        verbose_name = 'Dossier employé'
        verbose_name_plural = 'Dossiers employés'
        unique_together = [('company', 'matricule')]
        ordering = ['nom', 'prenom']
        constraints = [
            # XRH10 — PIN unique par société, mais SEULEMENT quand renseigné
            # (plusieurs dossiers peuvent avoir code_pointage='').
            models.UniqueConstraint(
                fields=['company', 'code_pointage'],
                condition=models.Q(~models.Q(code_pointage='')),
                name='rh_dossier_code_pointage_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.matricule} — {self.nom} {self.prenom}'


class DossierActivity(models.Model):
    """Chatter / journal d'un dossier employé (audit du parcours) — XRH6.

    Historique « chatter » à la Odoo d'un ``DossierEmploye``, modèle maison
    aligné sur ``contrats.ContratActivity`` / ``crm.LeadActivity``. Deux
    familles d'entrées :

      - automatiques (``type=log``) : audit des champs suivis (poste_ref,
        departement, statut, type_contrat, dates de contrat, manager si
        ajouté un jour) — champ touché (``field``) et son ancien → nouveau
        état (``old_value`` → ``new_value``), écrites CÔTÉ SERVEUR au niveau
        de l'API, jamais par le navigateur ;
      - manuelles (``type=note``) : notes libres via
        ``employes/{id}/noter``.

    La piste d'audit exigée pour l'inspection du travail : ``Remuneration``
    seule était historisée jusqu'ici (une nouvelle ligne par changement) — ce
    modèle couvre le RESTE du dossier (poste, statut, contrat…).

    Multi-tenant : ``company`` est posée côté serveur. ``employe`` est une
    référence interne à l'app ``rh`` (foundation du domaine), FK dur autorisé ;
    ``auteur`` pointe vers ``AUTH_USER_MODEL`` (app foundation), FK autorisé et
    nullable (un changement automatisé sans utilisateur reste journalisable).

    RUNTIME-SAFETY (leçon FG136) : les instantanés ``old_value``/``new_value``
    peuvent être longs — ils sont en ``TextField`` pour ne JAMAIS dépasser une
    longueur maximale et lever en base.
    """

    class Kind(models.TextChoices):
        LOG = 'log', 'Transition'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_dossier_activites',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        'DossierEmploye',
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Employé',
    )
    type = models.CharField(
        max_length=10, choices=Kind.choices, verbose_name='Type')
    # Champ concerné par une transition automatique (ex. ``poste_ref``,
    # ``departement``, ``statut``, ``type_contrat``). Vide pour une note.
    field = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Champ')
    old_value = models.TextField(
        blank=True, default='', verbose_name='Ancienne valeur')
    new_value = models.TextField(
        blank=True, default='', verbose_name='Nouvelle valeur')
    message = models.TextField(
        blank=True, default='', verbose_name='Message')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_dossier_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité dossier employé'
        verbose_name_plural = 'Activités dossier employé'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['employe', '-date_creation'],
                name='rh_dossier_act_emp_date_idx'),
        ]

    def __str__(self):
        return f'{self.employe_id} {self.type}'.strip()


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


class ModeleIntegration(models.Model):
    """Gabarit de checklist d'intégration/onboarding (XRH4).

    Symétrique de la checklist de SORTIE (``ElementSortie``, FG161) côté
    ENTRÉE : une société définit un ou plusieurs modèles d'intégration
    (contrat signé, CIN/RIB collectés, déclaration CNSS, dotation EPI,
    création compte, formation sécurité…) ciblés optionnellement par
    ``poste_ref``/``departement`` — le modèle le plus spécifique applicable
    est choisi à l'embauche (``services.embaucher``), sinon un modèle par
    défaut (``poste_ref`` et ``departement`` tous deux vides) si présent.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_modeles_integration',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=160, verbose_name='Nom')
    poste_ref = models.ForeignKey(
        'Poste',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='modeles_integration',
        verbose_name='Poste (optionnel)',
    )
    departement = models.ForeignKey(
        Departement,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='modeles_integration',
        verbose_name='Département (optionnel)',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Modèle d'intégration"
        verbose_name_plural = "Modèles d'intégration"
        ordering = ['nom']

    def __str__(self):
        return self.nom


class ElementIntegration(models.Model):
    """Ligne gabarit ordonnée d'un ``ModeleIntegration`` (XRH4).

    Ex. « Contrat signé », « CIN/RIB collectés », « Déclaration CNSS »,
    « Dotation EPI », « Création compte », « Formation sécurité »… L'ordre
    d'affichage/exécution est porté par ``ordre`` (croissant).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_elements_integration',
        verbose_name='Société',
    )
    modele = models.ForeignKey(
        ModeleIntegration,
        on_delete=models.CASCADE,
        related_name='elements',
        verbose_name="Modèle d'intégration",
    )
    libelle = models.CharField(max_length=160, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Élément d'intégration (gabarit)"
        verbose_name_plural = "Éléments d'intégration (gabarit)"
        ordering = ['ordre', 'libelle']
        indexes = [models.Index(fields=['company', 'modele'])]

    def __str__(self):
        return f'{self.modele.nom} — {self.libelle}'


class ElementIntegrationEmploye(models.Model):
    """Instance de checklist d'intégration pour UN employé (XRH4).

    Créée automatiquement à l'embauche (``services.embaucher``, FG189) à
    partir des lignes du ``ModeleIntegration`` applicable, ou manuellement via
    ``employes/{id}/instancier-integration``. ``fait``/``fait_par``/``date``
    tracent la coche (jamais lue du corps pour ``fait_par``/``date`` — posés
    côté serveur à la coche).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_elements_integration_employe',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='elements_integration',
        verbose_name='Employé',
    )
    libelle = models.CharField(max_length=160, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    fait = models.BooleanField(default=False, verbose_name='Fait')
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_elements_integration_coches',
        verbose_name='Fait par',
    )
    date = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de réalisation')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Élément d'intégration (employé)"
        verbose_name_plural = "Éléments d'intégration (employé)"
        ordering = ['ordre', 'libelle']
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
    # XRH2 — plafond légal informatif (ex. 14 semaines maternité, 3 j paternité).
    # Purement informatif : la VALIDATION ne bloque rien dessus (nullable).
    jours_legaux = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Plafond légal (jours, informatif)')
    # XRH3 — au Maroc un certificat médical est exigé sous 48 h pour les
    # absences dépassant ce seuil (maladie typiquement). ``None`` = jamais
    # exigé pour ce type (comportement historique, non bloquant).
    jours_max_sans_justificatif = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Jours max sans justificatif')
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
    # ZRH2 — garde d'idempotence de l'acquisition mensuelle automatique
    # (``accruer_conges``) : nombre de mois DÉJÀ crédités pour cette année,
    # jamais > 12. NULL/0 = comportement historique inchangé (acquisition
    # manuelle uniquement, comme avant ZRH2).
    mois_acquis = models.PositiveSmallIntegerField(
        default=0, verbose_name='Mois déjà crédités (acquisition auto)')
    # ZRH2 — le report janvier de N-1 vers N ne s'applique qu'une fois par
    # année (garde séparée du décompte des mois).
    report_applique = models.BooleanField(
        default=False, verbose_name='Report N-1 déjà appliqué')
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
    # ZRH5 — clôture automatique (« Automatic check-out » Odoo) : ``True`` si
    # ``heure_depart`` a été posée par ``manage.py clore_pointages_ouverts``
    # (jamais écrasé si le pointage était déjà fermé manuellement).
    depart_auto = models.BooleanField(
        default=False, verbose_name='Départ clôturé automatiquement')
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
    # XRH3 — demi-journée en début/fin de demande (décompte −0,5 j chacune via
    # ``services.calculer_jours_demande``). Une demande d'UN jour avec les deux
    # drapeaux à vrai reste 1 jour entier (les deux flags visent la même seule
    # journée dans ce cas — le service les traite indépendamment sur chaque
    # borne, ce qui a un sens dès que la plage dépasse 1 jour).
    demi_journee_debut = models.BooleanField(
        default=False, verbose_name='Demi-journée (début)')
    demi_journee_fin = models.BooleanField(
        default=False, verbose_name='Demi-journée (fin)')
    # XRH3 — justificatif (certificat médical…) exigé au-delà de
    # ``type_absence.jours_max_sans_justificatif`` (VALIDATION uniquement,
    # cf. ``services.valider_demande``).
    justificatif = models.FileField(
        upload_to='rh/demandes_conge/justificatifs/', null=True, blank=True,
        verbose_name='Justificatif')
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
    # XRH12 — géofence optionnelle : GPS capturé à l'émargement + drapeau si
    # hors du rayon configuré (jamais bloquant — le terrain a un GPS imprécis).
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS — latitude')
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='GPS — longitude')
    hors_zone = models.BooleanField(
        default=False, verbose_name='Hors zone (géofence)')
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
    # YHIRE13 — lien OPTIONNEL vers un produit du stock (référence STRING vers
    # ``stock.Produit``, jamais de FK cross-app : la frontière passe par
    # ``apps.stock.services``). NULL = comportement historique inchangé (aucun
    # effet stock). Quand renseigné, chaque ``DotationEpi`` décrémente ce
    # produit du stock à hauteur de sa ``quantite``.
    produit_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Produit stock lié (référence)')
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
    # YHIRE13 — restitution (sortie EPI récupéré) : quand l'EPI est lié à un
    # produit de stock, la restitution réintègre le stock. NULL/False par
    # défaut = comportement historique inchangé. Une dotation ne peut être
    # restituée qu'une fois (garde côté service).
    restituee = models.BooleanField(
        default=False, verbose_name='Restituée')
    date_restitution = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de restitution')
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


class CauserieSecurite(models.Model):
    """Causerie sécurité / toolbox talk (FG183) — le « quart d'heure sécurité ».

    Matérialise un BRIEFING SÉCURITÉ court tenu AVANT le démarrage d'un chantier
    (le « quart d'heure sécurité » / toolbox talk) : on rappelle un THÈME précis
    (port du harnais, consignation électrique, gestes et postures…) à l'équipe
    qui va intervenir. C'est une pierre angulaire de la prévention au quotidien
    et une pièce traçable : en cas de contrôle CNSS / inspection du travail ou
    après un accident, l'employeur prouve par l'émargement que l'équipe a bien
    été sensibilisée au risque ce jour-là.

    On capture l'essentiel : le THÈME (``theme``), la DATE (``date_causerie``),
    le CHANTIER concerné (``chantier_id`` — référence chaîne optionnelle vers un
    chantier d'une autre app, PAS de FK inter-app), l'ANIMATEUR qui a mené la
    causerie (``animateur`` → ``DossierEmploye``, même société) et un ``lieu`` /
    des ``notes`` libres. La liste des participants et leur émargement vit dans
    le modèle enfant ``CauserieParticipant``.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête) ; ``animateur`` doit appartenir à la même société.

    RUNTIME-SAFETY (leçon FG136) : ``theme`` / ``lieu`` / ``chantier_id``
    plafonnés ; les ``notes``, potentiellement longues, sont un ``TextField``
    (aucune limite à dépasser). Entièrement additif.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_causeries_securite',
        verbose_name='Société',
    )
    theme = models.CharField(max_length=255, verbose_name='Thème')
    date_causerie = models.DateField(verbose_name='Date')
    # Référence chaîne optionnelle vers un chantier d'une autre app (pas de FK
    # inter-app) — saisie terrain libre.
    chantier_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Chantier (référence)')
    # L'employé qui a animé la causerie (même société).
    animateur = models.ForeignKey(
        DossierEmploye,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_causeries_animees',
        verbose_name='Animateur',
    )
    lieu = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Lieu')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Causerie sécurité'
        verbose_name_plural = 'Causeries sécurité'
        ordering = ['-date_causerie', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'date_causerie'],
                name='rh_causerie_comp_date_idx'),
        ]

    def __str__(self):
        return f'{self.theme} ({self.date_causerie})'


class CauserieParticipant(models.Model):
    """Participant + émargement d'une causerie sécurité (FG183).

    Une ligne par personne PRÉSENTE à la causerie (``causerie`` → parent) avec
    son émargement individuel : ``present`` (a-t-elle assisté), ``emarge`` (a-t-
    elle signé l'accusé de présence) + ``emarge_le`` (horodatage posé CÔTÉ
    SERVEUR via l'action ``emarger``). Le participant est un ``DossierEmploye``
    de la même société.

    L'émargement matérialise l'accusé : « j'ai bien reçu le briefing sécurité du
    jour ». Posé via l'action dédiée, jamais déduit du corps brut.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps),
    celle de la causerie ; ``participant`` doit appartenir à la même société.
    Additif.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_causerie_participants',
        verbose_name='Société',
    )
    causerie = models.ForeignKey(
        CauserieSecurite,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name='Causerie',
    )
    participant = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='rh_causerie_participations',
        verbose_name='Participant',
    )
    present = models.BooleanField(default=True, verbose_name='Présent')
    # Émargement : signature/confirmation de présence (posée via l'action).
    emarge = models.BooleanField(default=False, verbose_name='Émargé')
    emarge_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Émargé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Participant causerie'
        verbose_name_plural = 'Participants causerie'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['causerie', 'participant'],
                name='rh_causerie_part_unique'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'causerie'],
                name='rh_causpart_comp_caus_idx'),
        ]

    def __str__(self):
        return f'{self.participant_id} @ {self.causerie_id}'


class AnalyseRisquesChantier(models.Model):
    """Analyse de risques chantier / plan de prévention (FG184) — AVANT travaux.

    Matérialise le PLAN DE PRÉVENTION d'un chantier : l'évaluation des risques
    réalisée AVANT le démarrage des travaux. C'est distinct de la check-list
    sécurité par intervention (F18, faite SUR le terrain au fil de l'eau) et de
    la causerie sécurité (FG183, le briefing du jour) : ici on identifie EN
    AMONT les dangers propres au chantier et les mesures de prévention à mettre
    en place avant que quiconque ne travaille. Réglementairement, l'employeur
    doit évaluer les risques et organiser la prévention sur chaque chantier ;
    ce plan en est le socle traçable.

    On capture l'essentiel : le CHANTIER concerné (``chantier_id`` — référence
    chaîne optionnelle vers un chantier d'une autre app, PAS de FK inter-app),
    la DATE de l'analyse (``date_analyse``), le RÉDACTEUR qui l'a menée
    (``redacteur`` → ``DossierEmploye``, même société), un ``lieu`` / des
    ``notes`` libres et le ``statut`` (brouillon → validé). La liste des risques
    identifiés vit dans le modèle enfant ``LigneRisqueChantier`` : chacun porte
    un danger, sa gravité × probabilité, un niveau de risque et la mesure de
    prévention associée.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête) ; ``redacteur`` doit appartenir à la même société.

    RUNTIME-SAFETY (leçon FG136) : le code borné ``statut`` ≤ 20 ; ``lieu`` /
    ``chantier_id`` plafonnés ; les ``notes``, potentiellement longues, sont un
    ``TextField`` (aucune limite à dépasser). Entièrement additif.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_analyses_risques_chantier',
        verbose_name='Société',
    )
    # Référence chaîne optionnelle vers un chantier d'une autre app (pas de FK
    # inter-app) — saisie terrain libre.
    chantier_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Chantier (référence)')
    date_analyse = models.DateField(verbose_name="Date de l'analyse")
    # L'employé qui a rédigé l'analyse de risques (même société).
    redacteur = models.ForeignKey(
        DossierEmploye,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_analyses_risques_redigees',
        verbose_name='Rédacteur',
    )
    lieu = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Lieu')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Analyse de risques chantier'
        verbose_name_plural = 'Analyses de risques chantier'
        ordering = ['-date_analyse', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'date_analyse'],
                name='rh_arc_comp_date_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_arc_comp_stat_idx'),
        ]

    def __str__(self):
        return f'Analyse risques {self.chantier_id or "—"} ' \
               f'({self.date_analyse})'


class LigneRisqueChantier(models.Model):
    """Risque identifié dans une analyse de risques chantier (FG184).

    Une ligne par RISQUE identifié sur le chantier (``analyse`` → parent) : le
    DANGER (``danger`` — la nature du risque, ex. « travail en hauteur »), une
    ``description`` détaillée, la GRAVITÉ (``gravite``) et la PROBABILITÉ
    (``probabilite``) estimées, le NIVEAU de risque qui en découle (``niveau`` —
    faible / moyen / élevé / critique) et la MESURE DE PRÉVENTION à appliquer
    (``mesure_prevention``).

    Le ``niveau`` est saisi (et non strictement calculé) pour laisser le
    rédacteur arbitrer : gravité × probabilité oriente, mais l'évaluateur
    tranche selon le contexte chantier.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps),
    celle de l'analyse parente. Additif.

    RUNTIME-SAFETY (leçon FG136) : les codes bornés ``gravite`` /
    ``probabilite`` / ``niveau`` ≤ 20 ; ``danger`` plafonné ; ``description`` /
    ``mesure_prevention``, potentiellement longues, sont des ``TextField``.
    """

    class Gravite(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        ELEVEE = 'elevee', 'Élevée'

    class Probabilite(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYENNE = 'moyenne', 'Moyenne'
        ELEVEE = 'elevee', 'Élevée'

    class Niveau(models.TextChoices):
        FAIBLE = 'faible', 'Faible'
        MOYEN = 'moyen', 'Moyen'
        ELEVE = 'eleve', 'Élevé'
        CRITIQUE = 'critique', 'Critique'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_lignes_risque_chantier',
        verbose_name='Société',
    )
    analyse = models.ForeignKey(
        AnalyseRisquesChantier,
        on_delete=models.CASCADE,
        related_name='risques',
        verbose_name='Analyse',
    )
    danger = models.CharField(max_length=255, verbose_name='Danger')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    gravite = models.CharField(
        max_length=20, choices=Gravite.choices,
        default=Gravite.MOYENNE, verbose_name='Gravité')
    probabilite = models.CharField(
        max_length=20, choices=Probabilite.choices,
        default=Probabilite.MOYENNE, verbose_name='Probabilité')
    niveau = models.CharField(
        max_length=20, choices=Niveau.choices,
        default=Niveau.MOYEN, verbose_name='Niveau de risque')
    mesure_prevention = models.TextField(
        blank=True, default='', verbose_name='Mesure de prévention')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Risque chantier'
        verbose_name_plural = 'Risques chantier'
        ordering = ['id']
        indexes = [
            models.Index(
                fields=['company', 'analyse'],
                name='rh_lrc_comp_analyse_idx'),
        ]

    def __str__(self):
        return f'{self.danger} ({self.niveau})'


class SessionFormation(models.Model):
    """Session de formation (FG187) — gestion de la formation des équipes.

    Matérialise une SESSION DE FORMATION organisée par la société :
    interne (formateur maison) ou externe (organisme), avec son ``intitule``,
    son ``type`` (interne / externe), l'``organisme`` éventuel, les dates
    (``date_debut`` / ``date_fin``), le ``lieu``, le ``cout`` total et un
    ``statut`` (planifiée → réalisée → annulée). La session peut viser une
    ``competence_visee`` du référentiel (FK même app ``rh.Competence``) :
    quand la session est marquée RÉALISÉE, le niveau de compétence des
    participants présents peut alors être enregistré/mis à jour dans la matrice
    (``CompetenceEmploye``) — c'est le lien formation → compétences.

    La liste des participants vit dans le modèle enfant
    ``InscriptionFormation`` (un par employé inscrit, avec présence et
    résultat). Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue
    du corps de requête) ; ``competence_visee`` doit appartenir à la même
    société. Entièrement additif.

    RUNTIME-SAFETY (leçon FG136) : le code borné ``type`` / ``statut`` ≤ 20 ;
    ``intitule`` / ``organisme`` / ``lieu`` plafonnés ; les ``notes``,
    potentiellement longues, sont un ``TextField``.
    """

    class TypeFormation(models.TextChoices):
        INTERNE = 'interne', 'Interne'
        EXTERNE = 'externe', 'Externe'

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        REALISEE = 'realisee', 'Réalisée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_sessions_formation',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=200, verbose_name='Intitulé')
    type = models.CharField(
        max_length=20, choices=TypeFormation.choices,
        default=TypeFormation.INTERNE, verbose_name='Type')
    organisme = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Organisme')
    date_debut = models.DateField(verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    lieu = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Lieu')
    cout = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Coût')
    # Compétence visée par la formation (même société) — alimente la matrice
    # quand la session est réalisée.
    competence_visee = models.ForeignKey(
        Competence,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions_formation',
        verbose_name='Compétence visée',
    )
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.PLANIFIEE, verbose_name='Statut')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Session de formation'
        verbose_name_plural = 'Sessions de formation'
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'date_debut'],
                name='rh_sf_comp_date_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_sf_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.intitule} ({self.date_debut})'


class InscriptionFormation(models.Model):
    """Inscription d'un employé à une session de formation (FG187).

    Une ligne par PARTICIPANT (``session`` → parent, ``participant`` →
    ``DossierEmploye`` de la même société) : la ``present`` trace la présence,
    ``resultat`` / ``note`` consignent l'issue (réussite, évaluation libre).
    Le couple (session, participant) est unique : on met à jour l'inscription
    plutôt que d'en empiler.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps),
    celle de la session parente ; ``participant`` doit appartenir à la même
    société. Additif.

    RUNTIME-SAFETY (leçon FG136) : le code borné ``resultat`` ≤ 20 ; ``note``,
    potentiellement longue, est un ``TextField``.
    """

    class Resultat(models.TextChoices):
        NON_EVALUE = 'non_evalue', 'Non évalué'
        REUSSI = 'reussi', 'Réussi'
        ECHEC = 'echec', 'Échec'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_inscriptions_formation',
        verbose_name='Société',
    )
    session = models.ForeignKey(
        SessionFormation,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name='Session',
    )
    participant = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='formations',
        verbose_name='Participant',
    )
    present = models.BooleanField(default=False, verbose_name='Présent')
    resultat = models.CharField(
        max_length=20, choices=Resultat.choices,
        default=Resultat.NON_EVALUE, verbose_name='Résultat')
    note = models.TextField(
        blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Inscription à une formation'
        verbose_name_plural = 'Inscriptions aux formations'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'participant'],
                name='rh_inscr_form_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'session'],
                name='rh_if_comp_sess_idx'),
        ]

    def __str__(self):
        return f'{self.participant} — {self.session}'


class BesoinFormation(models.Model):
    """Besoin de formation identifié pour un employé (FG188) — plan de formation.

    Matérialise un BESOIN DE FORMATION repéré pour un ``employe``
    (``DossierEmploye`` de la même société) : le ``theme`` à couvrir, sa
    ``priorite`` (basse / moyenne / haute), une ``echeance`` souhaitée
    (optionnelle), et un ``statut`` qui suit le besoin du repérage à sa
    satisfaction (identifié → planifié → satisfait). Quand le besoin répond à
    une OBLIGATION RÉGLEMENTAIRE marocaine (formations OFPPT / financement CSF),
    ``obligation_reglementaire`` est vrai et ``type_obligation`` précise le
    cadre (``ofppt`` / ``csf`` / autre). Le besoin peut être rattaché à une
    ``session_liee`` (FK même app ``rh.SessionFormation``) qui le couvre : si
    cette session est RÉALISÉE, le besoin peut basculer en ``satisfait``.

    C'est, avec le registre par employé (sélecteur ``registre_formation_employe``
    qui agrège ses ``InscriptionFormation``), le couple PLAN + REGISTRE de la
    formation : le registre = l'historique réalisé, le besoin = ce qui reste à
    planifier. Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du
    corps) ; ``employe`` et ``session_liee`` doivent appartenir à la même
    société. Entièrement additif.

    RUNTIME-SAFETY (leçon FG136) : codes bornés ``priorite`` / ``statut`` /
    ``type_obligation`` ≤ 20 ; ``theme`` plafonné ; ``notes`` en ``TextField`` ;
    index nommés explicitement (≤ 30 chars).
    """

    class Priorite(models.TextChoices):
        BASSE = 'basse', 'Basse'
        MOYENNE = 'moyenne', 'Moyenne'
        HAUTE = 'haute', 'Haute'

    class Statut(models.TextChoices):
        IDENTIFIE = 'identifie', 'Identifié'
        PLANIFIE = 'planifie', 'Planifié'
        SATISFAIT = 'satisfait', 'Satisfait'

    class TypeObligation(models.TextChoices):
        OFPPT = 'ofppt', 'OFPPT'
        CSF = 'csf', 'CSF (Contrats Spéciaux de Formation)'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_besoins_formation',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        'rh.DossierEmploye',
        on_delete=models.CASCADE,
        related_name='besoins_formation',
        verbose_name='Employé',
    )
    theme = models.CharField(max_length=200, verbose_name='Thème')
    priorite = models.CharField(
        max_length=20, choices=Priorite.choices,
        default=Priorite.MOYENNE, verbose_name='Priorité')
    echeance = models.DateField(
        null=True, blank=True, verbose_name='Échéance souhaitée')
    obligation_reglementaire = models.BooleanField(
        default=False, verbose_name='Obligation réglementaire')
    type_obligation = models.CharField(
        max_length=20, choices=TypeObligation.choices,
        blank=True, default='', verbose_name='Type d\'obligation')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.IDENTIFIE, verbose_name='Statut')
    # Session de formation qui couvre ce besoin (même société) — la
    # satisfaction du besoin peut découler de sa réalisation.
    session_liee = models.ForeignKey(
        'rh.SessionFormation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='besoins_couverts',
        verbose_name='Session liée',
    )
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Besoin de formation'
        verbose_name_plural = 'Besoins de formation'
        ordering = ['-priorite', 'echeance', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='rh_bf_comp_stat_idx'),
            models.Index(
                fields=['company', 'employe'],
                name='rh_bf_comp_emp_idx'),
        ]

    def __str__(self):
        return f'{self.theme} — {self.employe}'


class OuverturePoste(models.Model):
    """Ouverture de poste / poste ouvert au recrutement (FG189) — ATS-lite.

    Matérialise un POSTE OUVERT au recrutement : un ``intitule`` libre,
    rattachable optionnellement à un ``poste_ref`` (référentiel ``rh.Poste``,
    FG160) et à un ``departement`` (``rh.Departement``), une ``description`` du
    profil recherché, le ``nombre_postes`` à pourvoir (défaut 1) et un
    ``statut`` qui suit le cycle de vie de l'ouverture (ouvert → pourvu / clos /
    annulé). ``date_ouverture`` (défaut aujourd'hui) et ``date_cible``
    (échéance d'embauche souhaitée, optionnelle) bornent le besoin.

    Les CANDIDATURES (``Candidature``) sont rattachées à une ouverture ; quand
    le nombre de candidats EMBAUCHÉS atteint ``nombre_postes``, l'ouverture peut
    basculer en ``pourvu`` (service ``apps.rh.services.embaucher``). Multi-
    société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``poste_ref`` et ``departement`` doivent appartenir à la même société.
    Entièrement additif.

    RUNTIME-SAFETY (leçon FG136) : code borné ``statut`` ≤ 20 ; ``intitule``
    plafonné ; ``description`` en ``TextField`` ; index nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        # YHIRE14 — cycle amont d'approbation : une ouverture naît en
        # BROUILLON (défaut), passe par EN_APPROBATION à la soumission, puis
        # OUVERT une fois approuvée (SoD : approbateur ≠ demandeur). Les
        # ouvertures EXISTANTES avant YHIRE14 restent ``ouvert`` — seul le
        # DÉFAUT à la création change, aucune donnée existante n'est touchée.
        BROUILLON = 'brouillon', 'Brouillon'
        EN_APPROBATION = 'en_approbation', 'En approbation'
        OUVERT = 'ouvert', 'Ouvert'
        POURVU = 'pourvu', 'Pourvu'
        CLOS = 'clos', 'Clos'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_ouvertures_poste',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=200, verbose_name='Intitulé')
    poste_ref = models.ForeignKey(
        'rh.Poste',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ouvertures',
        verbose_name='Poste',
    )
    departement = models.ForeignKey(
        'rh.Departement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ouvertures',
        verbose_name='Département',
    )
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # XRH33 — ville affichée sur la page carrières publique (flag-gated).
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    # XRH33 — décision fondateur d'exposer (ou non) publiquement le
    # recrutement : une ouverture n'apparaît sur la page carrières QUE si
    # ``publiee=True`` ET ``CAREERS_ENABLED`` (défaut False, additif — les
    # ouvertures existantes restent NON publiées).
    publiee = models.BooleanField(
        default=False, verbose_name='Publiée (carrières)')
    nombre_postes = models.PositiveIntegerField(
        default=1, verbose_name='Nombre de postes')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # YHIRE14 — traçabilité SoD de l'approbation de réquisition (approbateur
    # ne peut jamais être le demandeur). NULL pour les ouvertures créées avant
    # YHIRE14 (comportement historique, restées ``ouvert``).
    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_ouvertures_demandees',
        verbose_name='Demandeur',
    )
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_ouvertures_approuvees',
        verbose_name='Approbateur',
    )
    date_soumission = models.DateTimeField(
        null=True, blank=True, verbose_name='Soumise le')
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidée le')
    motif_refus = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de refus')
    date_ouverture = models.DateField(
        null=True, blank=True, verbose_name="Date d'ouverture")
    date_cible = models.DateField(
        null=True, blank=True, verbose_name='Date cible')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Ouverture de poste'
        verbose_name_plural = 'Ouvertures de poste'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='rh_op_comp_stat_idx'),
        ]

    def __str__(self):
        return self.intitule


class Candidature(models.Model):
    """Candidature à une ouverture de poste (FG189) — ATS-lite.

    Représente un CANDIDAT postulant à une ``ouverture`` : son ``nom``,
    ``email`` / ``telephone``, un ``cv_fichier`` (optionnel), une ``source``
    (origine de la candidature : LinkedIn, ANAPEC, cooptation…), une ``note``
    libre, et son ``etape`` dans le pipeline de recrutement (reçu →
    présélection → entretien → offre → embauché / rejeté). ``date_candidature``
    (défaut aujourd'hui) horodate la réception.

    Quand le candidat atteint l'étape ``embauche`` via le service
    ``apps.rh.services.embaucher``, un ``DossierEmploye`` (même société) est
    créé et lié par ``employe_cree`` (``SET_NULL`` — conserve la candidature si
    le dossier est supprimé). L'opération est idempotente : un second appel ne
    recrée pas le dossier. Multi-société : ``company`` est posée CÔTÉ SERVEUR
    (jamais lue du corps), celle de l'ouverture parente ; ``ouverture`` et
    ``employe_cree`` appartiennent à la même société. Entièrement additif.

    RUNTIME-SAFETY (leçon FG136) : code borné ``etape`` ≤ 20 ; ``nom`` /
    ``telephone`` / ``source`` plafonnés ; ``note`` en ``TextField`` ; index
    nommés (≤ 30 chars).
    """

    class Etape(models.TextChoices):
        RECU = 'recu', 'Reçu'
        PRESELECTION = 'preselection', 'Présélection'
        ENTRETIEN = 'entretien', 'Entretien'
        OFFRE = 'offre', 'Offre'
        EMBAUCHE = 'embauche', 'Embauché'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_candidatures',
        verbose_name='Société',
    )
    ouverture = models.ForeignKey(
        OuverturePoste,
        on_delete=models.CASCADE,
        related_name='candidatures',
        verbose_name='Ouverture',
    )
    nom = models.CharField(max_length=160, verbose_name='Nom')
    email = models.EmailField(blank=True, default='', verbose_name='E-mail')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    cv_fichier = models.FileField(
        upload_to='rh/candidatures/cv/', null=True, blank=True,
        verbose_name='CV')
    source = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Source')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    etape = models.CharField(
        max_length=20, choices=Etape.choices,
        default=Etape.RECU, verbose_name='Étape')
    employe_cree = models.ForeignKey(
        'rh.DossierEmploye',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='candidatures_origine',
        verbose_name='Employé créé',
    )
    date_candidature = models.DateField(
        null=True, blank=True, verbose_name='Date de candidature')
    # XRH19 — opt-out des emails automatiques par étape (par défaut envoyés).
    emails_auto = models.BooleanField(
        default=True, verbose_name='Emails automatiques')
    # XRH21 — vivier de candidats (talent pool) : candidats non retenus
    # conservés pour un rattachement futur, taggés en recherche libre.
    vivier = models.BooleanField(default=False, verbose_name='Au vivier')
    tags_vivier = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Tags vivier (séparés par virgule)')
    # XRH21 — origine du rattachement (candidature du vivier dont celle-ci a
    # été clonée) — SET_NULL pour ne jamais perdre le lien si l'originale
    # est supprimée.
    vivier_origine = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rattachements',
        verbose_name='Origine (vivier)',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Candidature'
        verbose_name_plural = 'Candidatures'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'etape'],
                name='rh_cand_comp_etap_idx'),
            models.Index(
                fields=['company', 'ouverture'],
                name='rh_cand_comp_ouv_idx'),
        ]

    def __str__(self):
        return f'{self.nom} — {self.ouverture}'


class ModeleEvaluation(models.Model):
    """Gabarit de questions d'évaluation réutilisable (ZRH7, « Appraisal
    templates » Odoo).

    ``questions`` (JSON) : liste typée ``[{libelle, type, cible}]`` où
    ``type`` ∈ {texte, note1-5} et ``cible`` ∈ {employe, manager} (qui
    répond à la question). Ciblable optionnellement par ``departement`` ou
    ``poste_ref`` (le modèle le plus spécifique applicable est choisi à la
    création d'une ``EvaluationEmploye`` — défaut le modèle SANS département
    ni poste de la société, s'il existe). Multi-société : ``company`` posée
    CÔTÉ SERVEUR. Additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_modeles_evaluation',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=160, verbose_name='Nom')
    departement = models.ForeignKey(
        'rh.Departement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='modeles_evaluation',
        verbose_name='Département (cible)',
    )
    poste_ref = models.ForeignKey(
        'rh.Poste',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='modeles_evaluation',
        verbose_name='Poste (cible)',
    )
    # Liste de dicts {libelle, type (texte|note1-5), cible (employe|manager)}.
    questions = models.JSONField(
        default=list, blank=True, verbose_name='Questions')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Modèle d'évaluation"
        verbose_name_plural = "Modèles d'évaluation"
        ordering = ['nom']
        indexes = [
            models.Index(
                fields=['company', 'departement'],
                name='rh_modeval_comp_dep_idx'),
        ]

    def __str__(self):
        return self.nom


class CampagneEvaluation(models.Model):
    """Campagne d'appréciation annuelle (FG190) — entretiens & évaluations RH.

    Matérialise une CAMPAGNE D'APPRÉCIATION lancée par la société : le cycle
    d'entretiens annuels d'évaluation de la performance des collaborateurs.
    Chaque campagne porte un ``intitule`` (ex. « Entretiens annuels 2026 »),
    une ``annee`` et une ``periode`` libre (ex. « S2 », « Q4 »), des dates
    (``date_debut`` / ``date_fin``) qui bornent le cycle, une ``description``
    et un ``statut`` (ouverte → clôturée). Les entretiens individuels vivent
    dans le modèle enfant ``EvaluationEmploye`` (un par collaborateur évalué).

    C'est une appréciation RH de la performance — DISTINCTE des OBJECTIFS
    COMMERCIAUX de vente (FG39) : ici on évalue le collaborateur sur l'année,
    on ne pilote pas un quota de chiffre d'affaires.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête). Entièrement additif.

    RUNTIME-SAFETY (leçon FG136) : le code borné ``statut`` ≤ 20 ; ``intitule``
    / ``periode`` plafonnés ; la ``description``, potentiellement longue, est un
    ``TextField`` ; index nommés explicitement (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_campagnes_evaluation',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    annee = models.PositiveIntegerField(verbose_name='Année')
    periode = models.CharField(
        max_length=60, blank=True, default='', verbose_name='Période')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.OUVERTE, verbose_name='Statut')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # ZRH7 — modèle de questions structuré appliqué aux évaluations créées
    # dans cette campagne (NULL = comportement historique inchangé, aucune
    # question structurée).
    modele = models.ForeignKey(
        'rh.ModeleEvaluation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campagnes',
        verbose_name="Modèle d'évaluation",
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Campagne d'appréciation"
        verbose_name_plural = "Campagnes d'appréciation"
        ordering = ['-annee', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'annee'],
                name='rh_camp_comp_annee_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_camp_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.intitule} ({self.annee})'


class EvaluationEmploye(models.Model):
    """Entretien annuel d'évaluation d'un collaborateur (FG190).

    Une ligne par COLLABORATEUR ÉVALUÉ dans une campagne (``campagne`` →
    parent) : l'``employe`` apprécié (FK ``rh.DossierEmploye``, même société),
    l'``evaluateur`` qui mène l'entretien (FK ``rh.DossierEmploye`` optionnel,
    même société — typiquement le manager), la ``date_entretien``, une
    ``note_globale`` de synthèse (échelle 1–5, ``Decimal`` pour autoriser les
    demi-notes), une ``synthese`` libre (le commentaire de l'entretien) et un
    ``statut`` (planifié → réalisé → validé). Le couple (campagne, employe) est
    unique : un collaborateur n'est évalué qu'une fois par campagne (on met à
    jour l'entretien plutôt que d'en empiler). Les objectifs individuels fixés
    lors de l'entretien vivent dans le modèle enfant ``ObjectifIndividuel``.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps),
    celle de la campagne parente ; ``employe`` et ``evaluateur`` doivent
    appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : le code borné ``statut`` ≤ 20 ; la
    ``synthese``, potentiellement longue, est un ``TextField`` ;
    ``note_globale`` est un ``DecimalField`` borné (max_digits=3,
    decimal_places=1) ; index + contrainte d'unicité nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        REALISE = 'realise', 'Réalisé'
        VALIDE = 'valide', 'Validé'

    class Issue(models.TextChoices):
        # XRH26 — suite formalisée posée à la validation de l'entretien.
        AUGMENTATION_PROPOSEE = (
            'augmentation_proposee', "Augmentation proposée")
        PROMOTION = 'promotion', 'Promotion'
        FORMATION = 'formation', 'Formation'
        PIP = 'pip', 'Plan de performance (PIP)'
        AUCUNE = 'aucune', 'Aucune'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_evaluations_employe',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        CampagneEvaluation,
        on_delete=models.CASCADE,
        related_name='evaluations',
        verbose_name='Campagne',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='evaluations_recues',
        verbose_name='Employé',
    )
    evaluateur = models.ForeignKey(
        DossierEmploye,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='evaluations_menees',
        verbose_name='Évaluateur',
    )
    date_entretien = models.DateField(
        null=True, blank=True, verbose_name="Date de l'entretien")
    note_globale = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True, verbose_name='Note globale')
    synthese = models.TextField(
        blank=True, default='', verbose_name='Synthèse')
    # XRH26 — auto-évaluation : saisissable UNIQUEMENT par l'employé concerné
    # (via le portail self-service), à côté de l'évaluation manager.
    auto_evaluation = models.TextField(
        blank=True, default='', verbose_name='Auto-évaluation')
    note_auto = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True, verbose_name='Note (auto-évaluation)')
    # XRH26 — issue posée À LA VALIDATION (manager/RH) : suite formalisée.
    issue = models.CharField(
        max_length=25, choices=Issue.choices,
        blank=True, default='', verbose_name='Issue')
    issue_details = models.TextField(
        blank=True, default='', verbose_name="Détails de l'issue")
    # ZRH7 — réponses structurées instanciées depuis le modèle de la campagne
    # (``CampagneEvaluation.modele``) à la création : liste de dicts
    # ``{libelle, type, cible, reponse}`` (``reponse`` vide au départ, saisie
    # ensuite manager/employé). VIDE si la campagne n'a pas de modèle
    # (comportement historique inchangé).
    reponses = models.JSONField(
        default=list, blank=True, verbose_name='Réponses (modèle)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.PLANIFIE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Entretien d'évaluation"
        verbose_name_plural = "Entretiens d'évaluation"
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['campagne', 'employe'],
                name='rh_eval_camp_emp_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'campagne'],
                name='rh_eval_comp_camp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_eval_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.employe} — {self.campagne}'


class ObjectifIndividuel(models.Model):
    """Objectif individuel fixé lors d'un entretien d'évaluation (FG190).

    Une ligne par OBJECTIF fixé au collaborateur dans son entretien
    (``evaluation`` → parent) : un ``libelle`` (l'intitulé de l'objectif), une
    ``ponderation`` optionnelle (le poids relatif de l'objectif, en %), une
    ``cible`` visée (texte libre — la valeur attendue), une ``atteinte``
    constatée (le résultat observé) et une ``note`` optionnelle d'évaluation de
    cet objectif (échelle 1–5, ``Decimal``).

    C'est l'objectif RH de développement / performance du collaborateur —
    DISTINCT de l'objectif COMMERCIAL de vente (FG39).

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps),
    celle de l'évaluation parente. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` / ``cible`` / ``atteinte``
    plafonnés ; ``ponderation`` et ``note`` sont des ``DecimalField`` bornés ;
    index nommé (≤ 30 chars).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_objectifs_individuels',
        verbose_name='Société',
    )
    evaluation = models.ForeignKey(
        EvaluationEmploye,
        on_delete=models.CASCADE,
        related_name='objectifs',
        verbose_name='Évaluation',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    ponderation = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True, verbose_name='Pondération (%)')
    cible = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Cible')
    atteinte = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Atteinte')
    note = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True, verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Objectif individuel'
        verbose_name_plural = 'Objectifs individuels'
        ordering = ['id']
        indexes = [
            models.Index(
                fields=['company', 'evaluation'],
                name='rh_obj_comp_eval_idx'),
        ]

    def __str__(self):
        return self.libelle


class Sanction(models.Model):
    """Sanction disciplinaire d'un collaborateur (FG191).

    Registre des mesures disciplinaires conforme au code du travail marocain
    (loi 65-99) : observation, avertissement, blâme, mise à pied (avec durée
    en jours), mutation, rétrogradation, licenciement. Une ligne par mesure
    notifiée à un ``employe`` (FK ``rh.DossierEmploye``, même société) avec la
    ``date_faits`` (date des faits reprochés), la ``date_notification`` (date de
    remise de la sanction), le ``type_sanction``, une ``duree_jours`` (utile
    pour les mises à pied), le ``motif`` (les faits reprochés) et un ``statut``
    de procédure (notifiée → contestée → annulée). L'``auteur`` (le responsable
    qui prononce la mesure, FK ``rh.DossierEmploye`` optionnel) est tracé.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` et ``auteur`` doivent appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : codes ``type_sanction`` / ``statut`` ≤ 20 ;
    ``motif`` (potentiellement long) en ``TextField`` ; ``duree_jours`` borné
    (``PositiveIntegerField``) ; index nommés (≤ 30 chars).
    """

    class TypeSanction(models.TextChoices):
        OBSERVATION = 'observation', 'Observation'
        AVERTISSEMENT = 'avertissement', 'Avertissement'
        BLAME = 'blame', 'Blâme'
        MISE_A_PIED = 'mise_a_pied', 'Mise à pied'
        MUTATION = 'mutation', 'Mutation disciplinaire'
        RETROGRADATION = 'retrogradation', 'Rétrogradation'
        LICENCIEMENT = 'licenciement', 'Licenciement'

    class Statut(models.TextChoices):
        NOTIFIEE = 'notifiee', 'Notifiée'
        CONTESTEE = 'contestee', 'Contestée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_sanctions',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='sanctions',
        verbose_name='Employé',
    )
    auteur = models.ForeignKey(
        DossierEmploye,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sanctions_prononcees',
        verbose_name='Auteur',
    )
    type_sanction = models.CharField(
        max_length=20, choices=TypeSanction.choices,
        default=TypeSanction.AVERTISSEMENT, verbose_name='Type de sanction')
    date_faits = models.DateField(
        null=True, blank=True, verbose_name='Date des faits')
    date_notification = models.DateField(
        null=True, blank=True, verbose_name='Date de notification')
    duree_jours = models.PositiveIntegerField(
        default=0, verbose_name='Durée (jours)')
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.NOTIFIEE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Sanction disciplinaire'
        verbose_name_plural = 'Sanctions disciplinaires'
        ordering = ['-date_notification', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_sanc_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_sanc_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.get_type_sanction_display()} — {self.employe}'


class ElementsVariablesPaie(models.Model):
    """Éléments variables de paie mensuels par employé (FG192).

    Agrégat MENSUEL par collaborateur destiné au PRESTATAIRE DE PAIE — ce
    n'est PAS un moteur de paie : aucun calcul de net/brut légal n'est fait
    ici. Une ligne par (``employe``, ``annee``, ``mois``) récapitulant les
    éléments variables du mois : ``heures_normales``, ``heures_supp``,
    ``jours_absence``, ``jours_conges``, ``primes`` (total des primes/indemnités
    du mois), ``retenues`` (total des retenues : avances, sanctions…) et un
    ``commentaire`` libre. Un ``statut`` matérialise le cycle d'export
    (brouillon → validé → exporté) avec la ``date_export`` posée côté serveur
    au moment de l'export.

    DISTINCT de ``apps.paie.ElementVariable`` (PAIE11) : ce modèle est le
    BORDEREAU récapitulatif RH côté employeur, alimenté manuellement ou par
    agrégation des heures/absences.

    DÉCISION (YHIRE1) : ce bordereau reste un export EXTERNE UNIQUEMENT — à
    l'usage d'un prestataire de paie tiers qui ne consomme pas l'ERP. Le
    moteur de paie interne (``apps.paie.services.importer_elements_rh``) ne
    le lit JAMAIS : il importe directement les heures sup validées
    (``rh.selectors.heures_supp_pour_paie``), les absences non rémunérées
    validées (``rh.selectors.absences_non_remunerees_pour_paie``) et les
    primes validées du mois (``rh.selectors.primes_validees_pour_paie``) — ce
    sont les sources de vérité, jamais ce bordereau agrégé. Ne JAMAIS ajouter
    une 3ᵉ surface d'import paie : toute nouvelle donnée RH consommée par la
    paie interne passe par un sélecteur fin dédié, pas par ce modèle.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Le couple
    (``employe``, ``annee``, ``mois``) est unique (un bordereau par mois). Additif.

    RUNTIME-SAFETY (leçon FG136) : ``statut`` ≤ 20 ; montants/quantités en
    ``DecimalField`` borné ; ``commentaire`` en ``TextField`` ; index +
    contrainte d'unicité nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        EXPORTE = 'exporte', 'Exporté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_elements_variables_paie',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='elements_variables_paie',
        verbose_name='Employé',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois')
    heures_normales = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0'),
        verbose_name='Heures normales')
    heures_supp = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0'),
        verbose_name='Heures supplémentaires')
    jours_absence = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name="Jours d'absence")
    jours_conges = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Jours de congés')
    primes = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Primes/indemnités (total)')
    retenues = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Retenues (total)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    date_export = models.DateTimeField(
        null=True, blank=True, verbose_name='Exporté le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Éléments variables de paie'
        verbose_name_plural = 'Éléments variables de paie'
        ordering = ['-annee', '-mois', 'employe']
        constraints = [
            models.UniqueConstraint(
                fields=['employe', 'annee', 'mois'],
                name='rh_evp_emp_an_mois_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'annee', 'mois'],
                name='rh_evp_comp_an_mois_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_evp_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.employe} — {self.mois:02d}/{self.annee}'


class TypePrime(models.Model):
    """Référentiel des primes & indemnités (FG193).

    Catalogue normalisé des primes/indemnités d'une société : prime de
    rendement, indemnité de chantier, panier, transport, etc. Chaque type a un
    ``code`` interne, un ``libelle`` affiché, une ``nature`` (prime de
    performance / indemnité forfaitaire), un ``montant_defaut`` proposé à
    l'attribution, un drapeau ``imposable`` (entre ou non dans l'assiette
    fiscale, INDICATIF — le calcul légal reste au prestataire de paie) et un
    drapeau ``actif``.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps).
    Le couple (``company``, ``code``) est unique. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``code`` ≤ 30 / ``nature`` ≤ 20 bornés ;
    montant en ``DecimalField`` ; contrainte d'unicité nommée (≤ 30 chars).
    """

    class Nature(models.TextChoices):
        PRIME = 'prime', 'Prime'
        INDEMNITE = 'indemnite', 'Indemnité'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_types_prime',
        verbose_name='Société',
    )
    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    nature = models.CharField(
        max_length=20, choices=Nature.choices,
        default=Nature.PRIME, verbose_name='Nature')
    montant_defaut = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant par défaut')
    imposable = models.BooleanField(
        default=True, verbose_name='Imposable (indicatif)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Type de prime/indemnité'
        verbose_name_plural = 'Types de primes/indemnités'
        ordering = ['libelle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='rh_typeprime_comp_code_uniq'),
        ]

    def __str__(self):
        return self.libelle


class PrimeAttribuee(models.Model):
    """Prime/indemnité attribuée à un employé pour une période (FG193).

    Une ligne par ATTRIBUTION : un ``type_prime`` (FK ``rh.TypePrime``, même
    société) accordé à un ``employe`` (FK ``rh.DossierEmploye``, même société)
    pour une période ``annee``/``mois``, avec un ``montant`` (initialisé au
    montant par défaut du type mais modifiable) et un ``motif`` libre. Un
    ``statut`` matérialise le cycle (proposée → validée → payée) ; les primes
    validées alimentent le bordereau d'éléments variables de paie (FG192) côté
    employeur.

    Multi-société : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``type_prime`` et ``employe`` doivent appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``statut`` ≤ 20 borné ; ``montant`` en
    ``DecimalField`` ; ``motif`` plafonné ; index nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        PROPOSEE = 'proposee', 'Proposée'
        VALIDEE = 'validee', 'Validée'
        PAYEE = 'payee', 'Payée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_primes_attribuees',
        verbose_name='Société',
    )
    type_prime = models.ForeignKey(
        TypePrime,
        on_delete=models.PROTECT,
        related_name='attributions',
        verbose_name='Type de prime',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='primes_attribuees',
        verbose_name='Employé',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.PROPOSEE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Prime/indemnité attribuée'
        verbose_name_plural = 'Primes/indemnités attribuées'
        ordering = ['-annee', '-mois', 'employe']
        indexes = [
            models.Index(
                fields=['company', 'annee', 'mois'],
                name='rh_prime_comp_an_mois_idx'),
            models.Index(
                fields=['company', 'employe'],
                name='rh_prime_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_prime_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.type_prime} — {self.employe} ({self.mois:02d}/{self.annee})'


class OrdreMission(models.Model):
    """Ordre de mission / déplacement chantier (FG194).

    Document daté autorisant le déplacement d'un collaborateur : la ``reference``
    interne (posée côté serveur, unique par société), l'``employe`` missionné
    (FK ``rh.DossierEmploye``, même société), la ``destination`` (le lieu /
    chantier), le ``motif`` du déplacement, les dates ``date_depart`` →
    ``date_retour``, le ``moyen_transport``, une éventuelle camionnette du parc
    (``vehicule_id`` — STRING-FK vers ``flotte.Vehicule`` : on ne référence
    jamais ``flotte.models`` directement, comme ``AffectationRoster``), le
    ``per_diem`` (indemnité journalière de déplacement) et un ``statut``
    (brouillon → émis → clôturé). Restituable en PDF via l'action dédiée.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. ``reference`` est unique par
    société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``reference`` ≤ 40 / ``moyen_transport`` ≤ 60
    / ``statut`` ≤ 20 bornés ; ``motif`` en ``TextField`` ; ``per_diem`` en
    ``DecimalField`` ; contrainte d'unicité + index nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMIS = 'emis', 'Émis'
        CLOTURE = 'cloture', 'Clôturé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_ordres_mission',
        verbose_name='Société',
    )
    reference = models.CharField(max_length=40, verbose_name='Référence')
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='ordres_mission',
        verbose_name='Employé',
    )
    destination = models.CharField(max_length=255, verbose_name='Destination')
    motif = models.TextField(blank=True, default='', verbose_name='Motif')
    date_depart = models.DateField(
        null=True, blank=True, verbose_name='Date de départ')
    date_retour = models.DateField(
        null=True, blank=True, verbose_name='Date de retour')
    moyen_transport = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Moyen de transport')
    # String FK cross-app vers flotte.Vehicule — jamais importer flotte.models.
    vehicule_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Véhicule (ID, optionnel)')
    per_diem = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Per-diem (par jour)')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Ordre de mission'
        verbose_name_plural = 'Ordres de mission'
        ordering = ['-date_depart', '-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='rh_ordmiss_comp_ref_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_ordmiss_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_ordmiss_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.reference} — {self.destination}'


class AvanceSalaire(models.Model):
    """Avance sur salaire (FG195) — demande, validation, déduction.

    Une ligne par demande d'avance d'un ``employe`` (FK ``rh.DossierEmploye``,
    même société) : le ``montant`` demandé, la ``date_demande``, le ``motif``,
    le mois/année de déduction prévu (``annee_deduction`` / ``mois_deduction``,
    par défaut le mois suivant — l'avance est récupérée sur la paie suivante) et
    un ``statut`` (demandée → approuvée → déduite, ou refusée). Le ``valideur``
    (FK ``rh.DossierEmploye`` optionnel) trace qui approuve.

    INTÉGRATION EXPORT PAIE (FG192) : une avance APPROUVÉE constitue une retenue
    sur le bordereau mensuel d'éléments variables ; le sélecteur
    ``avances_a_deduire`` expose les avances à récupérer pour un mois donné.
    DISTINCT du modèle ``apps.paie`` (PAIE28) qui consomme ces données via les
    sélecteurs RH (jamais d'import croisé de models).

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` / ``valideur`` doivent appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``statut`` ≤ 20 borné ; ``montant`` en
    ``DecimalField`` ; ``motif`` en ``TextField`` ; index nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        DEMANDEE = 'demandee', 'Demandée'
        APPROUVEE = 'approuvee', 'Approuvée'
        DEDUITE = 'deduite', 'Déduite'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_avances_salaire',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='avances_salaire',
        verbose_name='Employé',
    )
    valideur = models.ForeignKey(
        DossierEmploye,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='avances_validees',
        verbose_name='Valideur',
    )
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    date_demande = models.DateField(
        null=True, blank=True, verbose_name='Date de demande')
    motif = models.TextField(blank=True, default='', verbose_name='Motif')
    annee_deduction = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Année de déduction')
    mois_deduction = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Mois de déduction')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.DEMANDEE, verbose_name='Statut')
    # YHIRE5 — lien vers l'avance MATÉRIALISÉE côté paie
    # (``paie.AvanceSalarie``, le seul moteur câblé au bulletin). Posé par
    # ``apps.paie.services.creer_avance_depuis_rh`` à l'approbation ;
    # string-ref (jamais d'import de ``paie.models`` depuis rh) — garantit
    # qu'une même demande ne matérialise JAMAIS deux retenues.
    paie_avance_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Avance paie liée (retenue)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Avance sur salaire'
        verbose_name_plural = 'Avances sur salaire'
        ordering = ['-date_demande', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_avance_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_avance_comp_stat_idx'),
            models.Index(
                fields=['company', 'annee_deduction', 'mois_deduction'],
                name='rh_avance_comp_ded_idx'),
        ]

    def __str__(self):
        return f'Avance {self.montant} — {self.employe}'


class BulletinPaie(models.Model):
    """Bulletin de paie déposé en LECTURE SEULE (FG196).

    Dépôt mensuel du bulletin de paie (le PDF produit par le prestataire de
    paie) rattaché à un ``employe`` (FK ``rh.DossierEmploye``, même société)
    pour une période ``annee``/``mois``. AUCUN calcul légal n'est fait ici : ce
    modèle ne fait que STOCKER et exposer en consultation le document fourni —
    décision assumée (FG196). Le fichier RÉUTILISE le stockage objet existant de
    ``records.Attachment`` (MinIO) : aucun nouveau stockage n'est construit. Le
    couple (``employe``, ``annee``, ``mois``) est unique (un bulletin par mois).

    Le collaborateur consulte SON bulletin via le portail self-service (FG199) ;
    le dépôt et l'administration restent Administrateur/Responsable.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``note`` plafonnée ; contrainte d'unicité +
    index nommés (≤ 30 chars).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_bulletins_paie',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='bulletins_paie',
        verbose_name='Employé',
    )
    # Réutilise le stockage MinIO existant : aucun nouveau stockage de fichier.
    attachment = models.OneToOneField(
        'records.Attachment',
        on_delete=models.CASCADE,
        related_name='bulletin_paie',
        verbose_name='Pièce jointe',
    )
    annee = models.PositiveIntegerField(verbose_name='Année')
    mois = models.PositiveSmallIntegerField(verbose_name='Mois')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Bulletin de paie'
        verbose_name_plural = 'Bulletins de paie'
        ordering = ['-annee', '-mois', 'employe']
        constraints = [
            models.UniqueConstraint(
                fields=['employe', 'annee', 'mois'],
                name='rh_bulletin_emp_an_mois_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'annee', 'mois'],
                name='rh_bulletin_comp_anmois_idx'),
            models.Index(
                fields=['company', 'employe'],
                name='rh_bulletin_comp_emp_idx'),
        ]

    def __str__(self):
        return f'Bulletin {self.mois:02d}/{self.annee} — {self.employe}'


class PermisConduire(models.Model):
    """Permis de conduire & habilitation à conduire d'un collaborateur (FG197).

    Suit le droit de conduire d'un ``employe`` (FK ``rh.DossierEmploye``, même
    société) : la ``categorie`` (catégorie de permis marocaine — B, C, D, EC…),
    le ``numero`` du permis, la ``date_delivrance`` et la ``date_expiration``
    (validité administrative ; un permis expiré n'autorise plus la conduite),
    et un drapeau ``habilitation_conduite`` (habilitation interne à conduire un
    véhicule de service, distincte du permis légal). C'est la SOURCE DE VÉRITÉ
    du droit de conduire côté RH : la garde d'affectation conducteur↔véhicule
    (FG198) la consulte via ``selectors.peut_conduire``.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Un permis par (société,
    employé, catégorie) — un collaborateur peut détenir plusieurs catégories.
    Additif.

    RUNTIME-SAFETY (leçon FG136) : ``categorie`` ≤ 10 / ``numero`` ≤ 40
    bornés ; contrainte d'unicité + index nommés (≤ 30 chars).
    """

    class Categorie(models.TextChoices):
        A = 'A', 'A — Motos'
        B = 'B', 'B — Véhicules légers'
        C = 'C', 'C — Poids lourds'
        D = 'D', 'D — Transport de personnes'
        EB = 'EB', 'EB — Léger + remorque'
        EC = 'EC', 'EC — Poids lourd + remorque'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_permis_conduire',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='permis_conduire',
        verbose_name='Employé',
    )
    categorie = models.CharField(
        max_length=10, choices=Categorie.choices,
        default=Categorie.B, verbose_name='Catégorie')
    numero = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Numéro de permis')
    date_delivrance = models.DateField(
        null=True, blank=True, verbose_name='Date de délivrance')
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    habilitation_conduite = models.BooleanField(
        default=False, verbose_name='Habilitation à conduire (interne)')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Permis de conduire'
        verbose_name_plural = 'Permis de conduire'
        ordering = ['employe', 'categorie']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'employe', 'categorie'],
                name='rh_permis_comp_emp_cat_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_permis_comp_emp_idx'),
            models.Index(
                fields=['company', 'date_expiration'],
                name='rh_permis_comp_exp_idx'),
        ]

    def __str__(self):
        return f'{self.employe} — permis {self.categorie}'


class AffectationVehicule(models.Model):
    """Affectation d'un conducteur à un véhicule (FG198).

    Lie un ``employe`` conducteur (FK ``rh.DossierEmploye``, même société) à un
    véhicule du parc (``vehicule_id`` — STRING-FK vers ``flotte.Vehicule`` : on
    ne référence jamais ``flotte.models`` directement, comme
    ``AffectationRoster`` / ``OrdreMission``) sur une période
    (``date_debut`` → ``date_fin`` optionnelle pour une affectation ouverte).

    GARDE PERMIS (décision FG198) : à la création/màj, le service
    ``services.controler_permis_affectation`` REFUSE l'affectation si le
    conducteur n'a pas de permis VALIDE (FG197 — via ``selectors.peut_conduire``).
    Le contrôle est posé CÔTÉ SERVEUR ; le flag ``permis_verifie`` matérialise
    qu'un permis valide existait à l'affectation.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``statut`` ≤ 20 borné ; ``note`` plafonnée ;
    index nommés (≤ 30 chars).
    """

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        TERMINEE = 'terminee', 'Terminée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_affectations_vehicule',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='affectations_vehicule',
        verbose_name='Conducteur',
    )
    # String FK cross-app vers flotte.Vehicule — jamais importer flotte.models.
    vehicule_id = models.PositiveIntegerField(verbose_name='Véhicule (ID)')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name="Début d'affectation")
    date_fin = models.DateField(
        null=True, blank=True, verbose_name="Fin d'affectation")
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.ACTIVE, verbose_name='Statut')
    # Posé côté serveur : vrai si un permis valide existait à l'affectation.
    permis_verifie = models.BooleanField(
        default=False, verbose_name='Permis vérifié')
    note = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Affectation véhicule'
        verbose_name_plural = 'Affectations véhicule'
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_affveh_comp_emp_idx'),
            models.Index(
                fields=['company', 'vehicule_id'],
                name='rh_affveh_comp_veh_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_affveh_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.employe} → véhicule {self.vehicule_id}'


class NoteDeFrais(models.Model):
    """Note de frais déclarée par un collaborateur (FG199).

    Déclaration de frais professionnels par un ``employe`` (FK
    ``rh.DossierEmploye``, même société) : la ``categorie`` (transport, repas,
    hébergement, fournitures, autre), le ``montant``, la ``date_frais`` (date de
    la dépense), un ``libelle`` descriptif et un ``statut`` de remboursement
    (soumise → approuvée → remboursée, ou refusée). Saisie depuis le portail
    self-service (FG199) par le collaborateur lui-même ; l'approbation reste
    Administrateur/Responsable. Les notes approuvées peuvent alimenter les
    retenues/primes du bordereau de paie (FG192) côté employeur.

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ;
    ``employe`` doit appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``categorie`` / ``statut`` ≤ 20 bornés ;
    ``montant`` en ``DecimalField`` ; ``libelle`` plafonné ; index nommés
    (≤ 30 chars).
    """

    class Categorie(models.TextChoices):
        TRANSPORT = 'transport', 'Transport'
        REPAS = 'repas', 'Repas'
        HEBERGEMENT = 'hebergement', 'Hébergement'
        FOURNITURES = 'fournitures', 'Fournitures'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        APPROUVEE = 'approuvee', 'Approuvée'
        REMBOURSEE = 'remboursee', 'Remboursée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_notes_frais',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='notes_frais',
        verbose_name='Employé',
    )
    categorie = models.CharField(
        max_length=20, choices=Categorie.choices,
        default=Categorie.AUTRE, verbose_name='Catégorie')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    date_frais = models.DateField(
        null=True, blank=True, verbose_name='Date de la dépense')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.SOUMISE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Note de frais'
        verbose_name_plural = 'Notes de frais'
        ordering = ['-date_frais', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_frais_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_frais_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} — {self.montant} ({self.employe})'


class DemandeRH(models.Model):
    """Guichet de demandes RH self-service (XRH9) — attestations à la demande.

    Les PDF d'attestations (travail / salaire / domiciliation) sont DÉJÀ
    générés par ``apps.paie.builders.render_attestation_pdf`` (PAIE34). Ce qui
    manquait était le GUICHET : un employé ne pouvait rien demander ni
    télécharger lui-même. ``DemandeRH`` matérialise cette demande : le
    ``type`` d'attestation souhaité, un ``statut`` (soumise → traitée /
    refusée), et — au traitement — le PDF généré est stocké via
    ``apps.records.storage`` (même mécanisme d'attachement que le reste de
    l'ERP) et lié par ``attachment``.

    Le PDF est PRODUIT en RÉUTILISANT le renderer paie existant via un thin
    wrapper cross-app (``apps.paie.services.generer_attestation_pdf_pour_dossier``)
    — AUCUN nouveau code PDF n'est dupliqué dans ``rh``.

    Téléchargeable UNIQUEMENT par l'employé concerné (``employe.user`` ==
    l'appelant) ou un porteur ``salaires_voir``/``IsResponsableOrAdmin`` côté
    traitement. L'attestation de salaire est refusée au traitement si le
    traitant ne porte pas ``salaires_voir``.

    Multi-société : ``company`` posée côté serveur (jamais lue du corps).
    ``employe`` et ``traite_par`` appartiennent à la même société.
    """

    class TypeAttestation(models.TextChoices):
        ATTESTATION_TRAVAIL = 'attestation_travail', 'Attestation de travail'
        ATTESTATION_SALAIRE = 'attestation_salaire', 'Attestation de salaire'
        ATTESTATION_DOMICILIATION = (
            'attestation_domiciliation', 'Attestation de domiciliation')
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        TRAITEE = 'traitee', 'Traitée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_demandes',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='demandes_rh',
        verbose_name='Employé',
    )
    type = models.CharField(
        max_length=30, choices=TypeAttestation.choices,
        default=TypeAttestation.ATTESTATION_TRAVAIL, verbose_name='Type')
    message = models.TextField(
        blank=True, default='', verbose_name='Message (précision « autre »)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.SOUMISE, verbose_name='Statut')
    motif_refus = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de refus')
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_demandes',
        verbose_name='Pièce jointe (PDF)',
    )
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_demandes_traitees',
        verbose_name='Traité par',
    )
    traite_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Traité le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Demande RH'
        verbose_name_plural = 'Demandes RH'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_demande_comp_emp_idx'),
            models.Index(
                fields=['company', 'statut'],
                name='rh_demande_comp_stat_idx'),
        ]

    def __str__(self):
        return f'{self.get_type_display()} — {self.employe} ({self.statut})'


# XRH10 — kiosque de pointage partagé (PIN/QR, tablette dépôt). Réutilise le
# schéma « hash déterministe HMAC-SHA256 » de ``publicapi.ApiKey`` : le secret
# en clair n'est montré qu'à la création/régénération, seul le hash est
# stocké/comparé (résolution O(1) par empreinte, table exploitable hors-ligne
# uniquement avec la SECRET_KEY serveur).

KIOSQUE_TOKEN_PREFIX = 'kio_'


def hash_device_token(raw_token):
    """Empreinte déterministe (HMAC-SHA256) d'un token de device kiosque."""
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        raw_token.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def generate_device_token():
    """Génère un nouveau token de device en clair (préfixe + secret)."""
    return KIOSQUE_TOKEN_PREFIX + secrets.token_urlsafe(32)


class DeviceKiosque(models.Model):
    """Token de device kiosque de pointage (XRH10) — une tablette dépôt.

    Authentifie l'endpoint kiosque ``pointages/kiosque/`` SANS session
    utilisateur : la tablette partagée présente ce token (jamais un compte
    ERP). Seul le HASH (``token_hash``) est stocké — le secret en clair n'est
    renvoyé qu'à la création/régénération (``services.emettre_device_kiosque``).
    Révocable (``actif=False``) à tout moment depuis Paramètres.

    Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_devices_kiosque',
        verbose_name='Société',
    )
    label = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    token_hash = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name='Empreinte')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    derniere_utilisation = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière utilisation')

    class Meta:
        verbose_name = 'Device kiosque'
        verbose_name_plural = 'Devices kiosque'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='rh_kiosque_comp_actif_idx'),
        ]

    def __str__(self):
        return self.label or f'Kiosque #{self.pk}'


class CorrectionPointage(models.Model):
    """Audit IMMUABLE des corrections de pointage (XRH11).

    Un ``Pointage`` modifié (heures/type/GPS) sans trace est indéfendable en
    litige prud'homal / inspection du travail. Chaque correction écrit UNE
    ligne : le ``champ`` touché, l'ancien et le nouvel état (``ancienne_valeur``
    / ``nouvelle_valeur``), un ``motif`` OBLIGATOIRE, et l'``auteur``/
    ``date_creation`` posés côté serveur. JAMAIS modifiable ni supprimable :
    aucune route update/delete n'est exposée (pattern write-once, comme
    ``contrats.ContratActivity``).

    Écrite AUTOMATIQUEMENT par la vue à toute modification d'un ``Pointage``
    existant (jamais par le navigateur). Multi-société : ``company`` posée
    côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_corrections_pointage',
        verbose_name='Société',
    )
    pointage = models.ForeignKey(
        Pointage,
        on_delete=models.CASCADE,
        related_name='corrections',
        verbose_name='Pointage',
    )
    champ = models.CharField(max_length=60, verbose_name='Champ modifié')
    ancienne_valeur = models.TextField(
        blank=True, default='', verbose_name='Ancienne valeur')
    nouvelle_valeur = models.TextField(
        blank=True, default='', verbose_name='Nouvelle valeur')
    motif = models.CharField(max_length=255, verbose_name='Motif')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_corrections_pointage',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Correction de pointage'
        verbose_name_plural = 'Corrections de pointage'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['pointage', '-date_creation'],
                name='rh_correction_pt_date_idx'),
        ]

    def __str__(self):
        return f'{self.pointage_id} — {self.champ}'


class ReglageRH(models.Model):
    """Réglages RH par société (Paramètres RH) — ``OneToOne`` company.

    Regroupe les réglages fins du module RH qui n'ont pas leur propre écran
    Paramètres dédié : ``geofence_metres`` (XRH12 — rayon de contrôle du
    pointage chantier, désactivé par défaut/``None``). Additif, une seule
    ligne par société (créée à la demande — ``get_or_create``).
    """
    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_reglage',
        verbose_name='Société',
    )
    # XRH12 — rayon de géofence (mètres) du pointage chantier. ``None`` =
    # contrôle désactivé (comportement par défaut, jamais bloquant).
    geofence_metres = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Géofence (mètres)')
    # XRH24 — rétention des candidatures rejetées (loi 09-08), en MOIS avant
    # anonymisation par ``manage.py purger_candidatures``. Défaut 24 mois.
    retention_candidatures_mois = models.PositiveIntegerField(
        default=24, verbose_name='Rétention candidatures (mois)')
    # ZRH5 — seuil (heures) après lequel un pointage ARRIVÉE sans DÉPART est
    # clôturé automatiquement par ``manage.py clore_pointages_ouverts``.
    # ``None`` = désactivé (comportement par défaut, aucune clôture auto).
    pointage_auto_depart_apres_h = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Clôture auto pointage après (heures)')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Réglage RH'
        verbose_name_plural = 'Réglages RH'

    def __str__(self):
        return f'Réglages RH — {self.company_id}'


class EmployeDeviceMap(models.Model):
    """Mappage pointeuse externe → employé (XRH13) — import CSV pivot.

    Aucun connecteur propriétaire ni dépendance : le CSV est le format pivot
    pour toute pointeuse badge/empreinte biométrique. ``device_user_id`` est
    l'identifiant de l'employé TEL QUE connu par la pointeuse externe (unique
    par société) ; il se mappe à un seul ``employe`` de l'ERP.

    Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_device_maps',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='device_maps',
        verbose_name='Employé',
    )
    device_user_id = models.CharField(
        max_length=60, verbose_name='ID employé (pointeuse)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Mappage pointeuse'
        verbose_name_plural = 'Mappages pointeuse'
        unique_together = [('company', 'device_user_id')]
        ordering = ['device_user_id']

    def __str__(self):
        return f'{self.device_user_id} → {self.employe.matricule}'


class PeriodeFermeture(models.Model):
    """Fermeture collective / congé imposé (XRH14) — pont, fermeture annuelle.

    À la VALIDATION (action ``appliquer``), génère une ``DemandeConge``
    VALIDÉE par employé concerné (décompte via les règles existantes de
    ``services.calculer_jours_demande`` + ``services.valider_demande``),
    IDEMPOTENT (ré-appliquer ne duplique pas). ``departements`` (M2M
    optionnel) restreint la fermeture : vide = TOUTE la société.

    Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_periodes_fermeture',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Du')
    date_fin = models.DateField(verbose_name='Au')
    type_absence = models.ForeignKey(
        TypeAbsence,
        on_delete=models.PROTECT,
        related_name='periodes_fermeture',
        verbose_name="Type d'absence",
    )
    # Vide = toute la société (comportement par défaut).
    departements = models.ManyToManyField(
        Departement, blank=True, related_name='periodes_fermeture',
        verbose_name='Départements')
    appliquee = models.BooleanField(default=False, verbose_name='Appliquée')
    appliquee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Appliquée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Fermeture collective'
        verbose_name_plural = 'Fermetures collectives'
        ordering = ['-date_debut']
        indexes = [
            models.Index(
                fields=['company', 'date_debut', 'date_fin'],
                name='rh_fermeture_comp_dates_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.date_debut}→{self.date_fin})'


class CompetenceRequise(models.Model):
    """Profil de compétences requises par poste (XRH15) — pour l'analyse
    d'écart. Un ``niveau_requis`` (0–4, même échelle que
    ``CompetenceEmploye.Niveau``) par (poste, compétence), unique.

    Multi-société : ``company`` posée côté serveur ; ``poste`` et
    ``competence`` doivent appartenir à la même société.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_competences_requises',
        verbose_name='Société',
    )
    poste = models.ForeignKey(
        Poste,
        on_delete=models.CASCADE,
        related_name='competences_requises',
        verbose_name='Poste',
    )
    competence = models.ForeignKey(
        Competence,
        on_delete=models.CASCADE,
        related_name='requise_pour_postes',
        verbose_name='Compétence',
    )
    niveau_requis = models.PositiveSmallIntegerField(
        choices=CompetenceEmploye.Niveau.choices,
        default=CompetenceEmploye.Niveau.INTERMEDIAIRE,
        verbose_name='Niveau requis')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compétence requise'
        verbose_name_plural = 'Compétences requises'
        constraints = [
            models.UniqueConstraint(
                fields=['poste', 'competence'],
                name='rh_competence_requise_uniq'),
        ]
        ordering = ['poste', 'competence']

    def __str__(self):
        return f'{self.poste} — {self.competence} (≥{self.niveau_requis})'


class GrilleSalariale(models.Model):
    """Grille salariale par poste (XRH16) — bandes min/max, compa-ratio.

    Une bande (``salaire_min``/``salaire_max``, MAD) par (poste, échelon
    optionnel), datée par ``date_effet``. Gatée LECTURE+ÉCRITURE par
    ``salaires_voir`` (donnée paie sensible, jamais dans un PDF ni une sortie
    client). ``selectors.compa_ratio`` compare le salaire actuel d'un employé
    au milieu de la bande de son poste.

    Multi-société : ``company`` posée côté serveur ; ``poste`` doit appartenir
    à la société.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_grilles_salariales',
        verbose_name='Société',
    )
    poste = models.ForeignKey(
        Poste,
        on_delete=models.CASCADE,
        related_name='grilles_salariales',
        verbose_name='Poste',
    )
    echelon = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Échelon')
    salaire_min = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Salaire minimum (MAD)')
    salaire_max = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Salaire maximum (MAD)')
    date_effet = models.DateField(verbose_name="Date d'effet")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Grille salariale'
        verbose_name_plural = 'Grilles salariales'
        ordering = ['poste', 'echelon', '-date_effet']
        indexes = [
            models.Index(
                fields=['company', 'poste'],
                name='rh_grille_comp_poste_idx'),
        ]

    def __str__(self):
        echelon = f' [{self.echelon}]' if self.echelon else ''
        return (f'{self.poste}{echelon} — {self.salaire_min}–'
                f'{self.salaire_max} MAD')


class EntretienRecrutement(models.Model):
    """Entretien de recrutement (XRH17) — planification pour une candidature.

    Le pipeline (FG189) a une étape « entretien » mais aucun objet dédié :
    pas de date, pas d'évaluateur, pas de notation structurée. Un entretien
    porte une ``date_heure``, un ``type`` (téléphonique/technique/RH/final),
    des ``evaluateurs`` (M2M users) et un ``statut``. Les notes vivent dans
    ``NoteEntretien`` (une par évaluateur).

    Multi-société : ``company`` posée côté serveur ; ``candidature`` doit
    appartenir à la société.
    """
    class TypeEntretien(models.TextChoices):
        TELEPHONIQUE = 'telephonique', 'Téléphonique'
        TECHNIQUE = 'technique', 'Technique'
        RH = 'rh', 'RH'
        FINAL = 'final', 'Final'

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        REALISE = 'realise', 'Réalisé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_entretiens_recrutement',
        verbose_name='Société',
    )
    candidature = models.ForeignKey(
        Candidature,
        on_delete=models.CASCADE,
        related_name='entretiens',
        verbose_name='Candidature',
    )
    date_heure = models.DateTimeField(
        null=True, blank=True, verbose_name='Date et heure')
    type = models.CharField(
        max_length=15, choices=TypeEntretien.choices,
        default=TypeEntretien.RH, verbose_name='Type')
    evaluateurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='rh_entretiens_a_evaluer', verbose_name='Évaluateurs')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.PLANIFIE, verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Entretien de recrutement'
        verbose_name_plural = 'Entretiens de recrutement'
        ordering = ['-date_heure', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'candidature'],
                name='rh_entretien_comp_cand_idx'),
        ]

    def __str__(self):
        return f'Entretien {self.get_type_display()} — {self.candidature}'


class NoteEntretien(models.Model):
    """Grille d'évaluation d'un entretien (XRH17) — une note par évaluateur.

    ``notes_criteres`` (JSON, {critère: note 1–5}) porte la notation par
    critère ; ``avis`` synthétise (favorable/réservé/défavorable).
    ``evaluateur`` est posé CÔTÉ SERVEUR (jamais lu du corps). Un même
    évaluateur ne note qu'une fois un même entretien.

    Multi-société : ``company`` posée côté serveur.
    """
    class Avis(models.TextChoices):
        FAVORABLE = 'favorable', 'Favorable'
        RESERVE = 'reserve', 'Réservé'
        DEFAVORABLE = 'defavorable', 'Défavorable'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_notes_entretien',
        verbose_name='Société',
    )
    entretien = models.ForeignKey(
        EntretienRecrutement,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name='Entretien',
    )
    evaluateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rh_notes_entretien',
        verbose_name='Évaluateur',
    )
    notes_criteres = models.JSONField(
        default=dict, blank=True, verbose_name='Notes par critère')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    avis = models.CharField(
        max_length=15, choices=Avis.choices,
        default=Avis.RESERVE, verbose_name='Avis')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Note d'entretien"
        verbose_name_plural = "Notes d'entretien"
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['entretien', 'evaluateur'],
                name='rh_note_entretien_uniq'),
        ]

    @property
    def moyenne_criteres(self):
        """Moyenne des notes par critère (None si aucun critère noté)."""
        valeurs = [
            v for v in (self.notes_criteres or {}).values()
            if isinstance(v, (int, float))]
        if not valeurs:
            return None
        return sum(valeurs) / len(valeurs)

    def __str__(self):
        return f'{self.entretien_id} — {self.evaluateur_id} ({self.avis})'


class CandidatureActivity(models.Model):
    """Chatter / journal d'une candidature (XRH18) — audit + collaboration.

    Pattern aligné sur ``DossierActivity`` (XRH6) / ``crm.LeadActivity`` :
    deux familles d'entrées — automatiques (``type=log``, transitions
    d'étape old→new) écrites CÔTÉ SERVEUR à chaque changement, et manuelles
    (``type=note``) via ``candidatures/{id}/noter``.

    Multi-société : ``company`` posée côté serveur ; ``auteur`` nullable
    (une transition automatisée sans utilisateur reste journalisable).
    """
    class Kind(models.TextChoices):
        LOG = 'log', 'Transition'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_candidature_activites',
        verbose_name='Société',
    )
    candidature = models.ForeignKey(
        Candidature,
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Candidature',
    )
    type = models.CharField(
        max_length=10, choices=Kind.choices, verbose_name='Type')
    field = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Champ')
    old_value = models.TextField(
        blank=True, default='', verbose_name='Ancienne valeur')
    new_value = models.TextField(
        blank=True, default='', verbose_name='Nouvelle valeur')
    message = models.TextField(
        blank=True, default='', verbose_name='Message')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_candidature_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité candidature'
        verbose_name_plural = 'Activités candidature'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['candidature', '-date_creation'],
                name='rh_cand_act_cand_date_idx'),
        ]

    def __str__(self):
        return f'{self.candidature_id} {self.type}'.strip()


class GabaritEmailRecrutement(models.Model):
    """Gabarit d'email automatique par étape du pipeline (XRH19).

    À la transition d'une ``Candidature`` vers ``etape`` (un gabarit ACTIF
    existe pour cette étape), un email est envoyé via l'infra existante
    (``SENDGRID_API_KEY`` key-gated, backend console sinon — no-op propre
    sans clé) avec ``objet``/``corps`` substitués par des placeholders sûrs
    ``{nom}``/``{poste}``/``{date_entretien}``. Journalisé dans le chatter
    (``CandidatureActivity``). Opt-out par candidature
    (``Candidature.emails_auto``).

    Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_gabarits_email_recrutement',
        verbose_name='Société',
    )
    etape = models.CharField(
        max_length=20, choices=Candidature.Etape.choices,
        verbose_name='Étape')
    objet = models.CharField(max_length=255, verbose_name='Objet')
    corps = models.TextField(verbose_name='Corps')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Gabarit email recrutement'
        verbose_name_plural = 'Gabarits email recrutement'
        ordering = ['etape']
        indexes = [
            models.Index(
                fields=['company', 'etape', 'actif'],
                name='rh_gabarit_email_etape_idx'),
        ]

    def __str__(self):
        return f'{self.get_etape_display()} — {self.objet}'


def _default_promesse_token():
    return secrets.token_urlsafe(32)


def _default_promesse_expiry():
    from datetime import timedelta

    from django.utils import timezone as dj_timezone
    return dj_timezone.now() + timedelta(days=30)


class PromesseEmbauche(models.Model):
    """Promesse d'embauche / lettre d'offre PDF + e-sign interne (XRH20).

    L'étape « offre » du pipeline (FG189) n'émettait rien. Génère une
    promesse d'embauche WeasyPrint depuis la ``Candidature`` (poste, type de
    contrat, date de début proposée, ``salaire_propose`` — nullable, gaté
    ``salaires_voir`` — jamais dans le PDF sauf pour le candidat via son lien
    tokenisé). Le candidat SIGNE via un lien tokenisé (pattern liens publics
    WhatsApp FG79 — jeton long, imprévisible, expirant 30 j) : acceptation
    e-sign loi 53-05 par NOM TAPÉ (pattern CONTRAT16, AUCUN prestataire
    externe) avec évidence serveur ``ip_adresse``/``user_agent``/
    ``date_signature``. Signature figée, horodatée, immuable (pas de route
    update/delete sur la signature).

    Multi-société : ``company`` posée côté serveur ; ``candidature`` doit
    appartenir à la société.
    """
    class Statut(models.TextChoices):
        ENVOYEE = 'envoyee', 'Envoyée'
        SIGNEE = 'signee', 'Signée'
        EXPIREE = 'expiree', 'Expirée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_promesses_embauche',
        verbose_name='Société',
    )
    candidature = models.OneToOneField(
        Candidature,
        on_delete=models.CASCADE,
        related_name='promesse_embauche',
        verbose_name='Candidature',
    )
    poste_propose = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Poste proposé')
    type_contrat = models.CharField(
        max_length=10, choices=DossierEmploye.TypeContrat.choices,
        default=DossierEmploye.TypeContrat.CDI, verbose_name='Type de contrat')
    date_debut_proposee = models.DateField(
        null=True, blank=True, verbose_name='Date de début proposée')
    # Donnée SENSIBLE (salaire) — gatée salaires_voir à l'écriture/lecture
    # interne ; visible pour le candidat via son lien tokenisé (c'est SON
    # offre). Nullable.
    salaire_propose = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Salaire proposé (MAD)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.ENVOYEE, verbose_name='Statut')
    token = models.CharField(
        max_length=64, unique=True, default=_default_promesse_token,
        editable=False, verbose_name='Jeton')
    expires_at = models.DateTimeField(
        default=_default_promesse_expiry, verbose_name='Expire le')
    # Signature e-sign (loi 53-05) — figée dès posée, jamais éditable.
    signataire_nom = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Nom du signataire')
    date_signature = models.DateTimeField(
        null=True, blank=True, verbose_name='Signé le')
    ip_adresse = models.CharField(
        max_length=45, blank=True, default='', verbose_name='Adresse IP')
    user_agent = models.TextField(
        blank=True, default='', verbose_name='User agent')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Promesse d'embauche"
        verbose_name_plural = "Promesses d'embauche"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['token'], name='rh_promesse_token_idx'),
        ]

    @property
    def is_valid(self):
        from django.utils import timezone as dj_timezone
        return self.expires_at > dj_timezone.now()

    def __str__(self):
        return f'Promesse — {self.candidature} ({self.statut})'


class EntretienSortie(models.Model):
    """Entretien de sortie / exit interview (XRH25) — turnover structuré.

    L'offboarding (FG161) ne stocke qu'un ``DossierEmploye.motif_sortie``
    (coarse, obligatoire à la sortie). ``EntretienSortie`` ajoute un
    entretien STRUCTURÉ, optionnel, mené après la sortie : un
    ``motif_principal`` plus fin (RH), un questionnaire libre en JSON
    (``{question: réponse}``), un ``recommanderait`` (l'employé
    recommanderait-il l'entreprise, nullable — pas toujours demandé/répondu)
    et un commentaire libre.

    Un seul entretien par employé sorti (``OneToOneField`` — un second essai
    d'ajout échoue naturellement à la contrainte unique plutôt que dupliquer).
    Multi-société : ``company`` posée CÔTÉ SERVEUR ; ``employe`` doit
    appartenir à la société. Entièrement additif.
    """

    class MotifPrincipal(models.TextChoices):
        SALAIRE = 'salaire', 'Salaire'
        MANAGEMENT = 'management', 'Management'
        CONDITIONS = 'conditions', 'Conditions de travail'
        DISTANCE = 'distance', 'Distance / trajet'
        OPPORTUNITE = 'opportunite', "Opportunité ailleurs"
        SANTE = 'sante', 'Santé'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_entretiens_sortie',
        verbose_name='Société',
    )
    employe = models.OneToOneField(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='entretien_sortie',
        verbose_name='Employé',
    )
    date = models.DateField(
        null=True, blank=True, verbose_name="Date de l'entretien")
    motif_principal = models.CharField(
        max_length=20, choices=MotifPrincipal.choices,
        blank=True, default='', verbose_name='Motif principal')
    questionnaire = models.JSONField(
        default=dict, blank=True, verbose_name='Questionnaire (réponses)')
    recommanderait = models.BooleanField(
        null=True, blank=True, verbose_name='Recommanderait l’entreprise')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Entretien de sortie'
        verbose_name_plural = 'Entretiens de sortie'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'motif_principal'],
                name='rh_ent_sortie_comp_motif_idx'),
        ]

    def __str__(self):
        return f'Entretien de sortie — {self.employe}'


class AyantDroit(models.Model):
    """XRH29 — ayant droit (personne à charge) nominatif d'un employé.

    ``DossierEmploye.nombre_enfants`` n'est qu'un COMPTEUR pour l'IR ; l'AMO/
    mutuelle exige les ayants droit NOMINATIFS (conjoint, enfants…) avec leur
    couverture. Multi-société : ``company`` posée CÔTÉ SERVEUR ; ``employe``
    doit appartenir à la société. Entièrement additif.
    """

    class Lien(models.TextChoices):
        CONJOINT = 'conjoint', 'Conjoint(e)'
        ENFANT = 'enfant', 'Enfant'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_ayants_droit',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='ayants_droit',
        verbose_name='Employé',
    )
    lien = models.CharField(
        max_length=20, choices=Lien.choices, verbose_name='Lien')
    nom = models.CharField(max_length=160, verbose_name='Nom')
    date_naissance = models.DateField(
        null=True, blank=True, verbose_name='Date de naissance')
    couvert_amo = models.BooleanField(
        default=False, verbose_name='Couvert AMO')
    couvert_mutuelle = models.BooleanField(
        default=False, verbose_name='Couvert mutuelle')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Ayant droit'
        verbose_name_plural = 'Ayants droit'
        ordering = ['employe', 'nom']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_ayant_droit_comp_emp_idx'),
        ]

    def __str__(self):
        return f'{self.nom} ({self.get_lien_display()}) — {self.employe}'


class AvantageSocial(models.Model):
    """XRH29 — avantage social léger d'un employé (mutuelle, CIMR…).

    Registre léger (organisme + dates d'adhésion/fin), DISTINCT des montants
    de paie (``BulletinPaie``/``ElementsVariablesPaie``). Multi-société :
    ``company`` posée CÔTÉ SERVEUR ; ``employe`` doit appartenir à la société.
    Entièrement additif.
    """

    class Type(models.TextChoices):
        MUTUELLE = 'mutuelle', 'Mutuelle'
        ASSURANCE_GROUPE = 'assurance_groupe', 'Assurance groupe'
        CIMR = 'cimr', 'CIMR'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_avantages_sociaux',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='avantages_sociaux',
        verbose_name='Employé',
    )
    type = models.CharField(
        max_length=20, choices=Type.choices, verbose_name='Type')
    organisme = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Organisme')
    date_adhesion = models.DateField(
        null=True, blank=True, verbose_name="Date d'adhésion")
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Avantage social'
        verbose_name_plural = 'Avantages sociaux'
        ordering = ['employe', 'type']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_avantage_comp_emp_idx'),
        ]

    def __str__(self):
        return f'{self.get_type_display()} — {self.employe}'


def hash_participation_token(user_id, campagne_id):
    """XRH32 — empreinte déterministe (HMAC-SHA256) « qui a déjà voté ».

    Même construction que ``hash_device_token`` (kiosque XRH10) : dérivée de
    ``SECRET_KEY`` + ``(user_id, campagne_id)``. Stockée à part
    (``ParticipationPulse``), JAMAIS jointe à ``ReponsePulse`` — empêche le
    double vote SANS relier la réponse au votant.
    """
    raw = f'{user_id}:{campagne_id}'
    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        raw.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


class CampagnePulse(models.Model):
    """XRH32 — campagne de baromètre interne eNPS anonyme (pulse survey).

    Une question eNPS (0–10, « recommanderiez-vous... ») + une question
    libre, sur une fenêtre ``date_debut``/``date_fin``. Multi-société :
    ``company`` posée CÔTÉ SERVEUR. Entièrement additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_campagnes_pulse',
        verbose_name='Société',
    )
    question_enps = models.CharField(
        max_length=255,
        default=(
            'Sur une échelle de 0 à 10, recommanderiez-vous notre '
            'entreprise comme employeur à un proche ?'),
        verbose_name='Question eNPS')
    question_libre = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Question libre')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Campagne pulse'
        verbose_name_plural = 'Campagnes pulse'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Pulse — {self.date_debut or self.date_creation.date()}'


class ReponsePulse(models.Model):
    """XRH32 — réponse ANONYME à une campagne pulse.

    STRUCTURELLEMENT non reliable au votant : AUCUNE FK vers un utilisateur
    ou un employé sur ce modèle — c'est le garde-fou d'anonymat (testable par
    inspection du schéma : ``[f.name for f in ReponsePulse._meta.fields]``
    ne contient ni ``user`` ni ``employe``). Le double vote est empêché à
    PART, par ``ParticipationPulse`` (jeton haché, jamais joint ici).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_reponses_pulse',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        CampagnePulse,
        on_delete=models.CASCADE,
        related_name='reponses',
        verbose_name='Campagne',
    )
    score = models.PositiveSmallIntegerField(verbose_name='Note (0–10)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire libre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Réponse pulse'
        verbose_name_plural = 'Réponses pulse'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'campagne'],
                name='rh_reppulse_comp_camp_idx'),
        ]

    def __str__(self):
        return f'Réponse pulse — campagne {self.campagne_id}'

    @property
    def categorie(self):
        """Catégorie eNPS de la réponse (promoteur/passif/détracteur) —
        mêmes seuils que le NPS client (FG238)."""
        if self.score >= 9:
            return 'promoteur'
        if self.score >= 7:
            return 'passif'
        return 'detracteur'


class ParticipationPulse(models.Model):
    """XRH32 — jeton de participation (empêche le double vote SANS lien
    votant→réponse).

    Une ligne par (``user``, ``campagne``) — la contrainte d'unicité EST le
    mécanisme anti-double-vote. ``token_hash`` (HMAC déterministe, voir
    :func:`hash_participation_token`) est stocké pour vérification, mais ce
    modèle N'A AUCUN LIEN vers ``ReponsePulse`` : on sait QUI a voté, jamais
    CE QU'IL A RÉPONDU.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_participations_pulse',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        CampagnePulse,
        on_delete=models.CASCADE,
        related_name='participations',
        verbose_name='Campagne',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='participations_pulse',
        verbose_name='Utilisateur',
    )
    token_hash = models.CharField(max_length=64, verbose_name='Jeton (empreinte)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Participation pulse'
        verbose_name_plural = 'Participations pulse'
        constraints = [
            models.UniqueConstraint(
                fields=['campagne', 'user'],
                name='rh_partpulse_camp_user_uniq'),
        ]

    def __str__(self):
        return f'Participation — campagne {self.campagne_id}'


class QuizFormation(models.Model):
    """XRH34 — quiz d'évaluation de formation (eLearning léger).

    FG187/188 gèrent l'ADMIN de la formation (sessions + besoins) et
    FG172/173 la matrice de compétences + les habilitations à échéance —
    mais rien n'ÉVALUE : ``QuizFormation`` porte le CONTENU d'un quiz
    (questions à choix unique/multiple, bonne(s) réponse(s), seuil de
    réussite) qu'un employé passe via ``TentativeQuiz``.

    ``questions`` (JSON) — liste de dicts :
    ``{'question': str, 'type': 'unique'|'multiple',
    'choix': [str, ...], 'bonnes_reponses': [int, ...]}`` (index dans
    ``choix``). Les BONNES RÉPONSES ne sont JAMAIS exposées côté employé —
    seul le serializer RH (gestion) les inclut.

    ``validite_mois`` (optionnel) — si le quiz est lié à une
    ``habilitation``, une réussite prolonge sa ``date_validite`` de ce
    nombre de mois. ``competence`` / ``habilitation`` sont OPTIONNELS et
    doivent appartenir à la MÊME société que le quiz (validés côté serveur).

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps).
    Additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_quiz_formation',
        verbose_name='Société',
    )
    intitule = models.CharField(max_length=200, verbose_name='Intitulé')
    questions = models.JSONField(
        default=list, blank=True, verbose_name='Questions')
    score_reussite = models.PositiveSmallIntegerField(
        default=80, verbose_name='Score de réussite (%)')
    validite_mois = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Validité de la certification (mois)')
    # Liens optionnels — même app (rh), validation same-company côté serveur.
    competence = models.ForeignKey(
        'rh.Competence',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quiz',
        verbose_name='Compétence liée',
    )
    habilitation_type = models.CharField(
        max_length=10, blank=True, default='',
        choices=Habilitation.TypeHabilitation.choices,
        verbose_name="Type d'habilitation liée")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Quiz de formation'
        verbose_name_plural = 'Quiz de formation'
        ordering = ['intitule']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='rh_quiz_comp_actif_idx'),
        ]

    def __str__(self):
        return self.intitule


class TentativeQuiz(models.Model):
    """XRH34 — tentative d'un employé sur un ``QuizFormation``.

    ``reponses`` (JSON) — liste d'index (ou de listes d'index pour une
    question à choix multiple) parallèle à ``quiz.questions``. Le ``score``
    (%) est TOUJOURS calculé CÔTÉ SERVEUR (jamais accepté du corps de
    requête) — les bonnes réponses ne sortent JAMAIS dans le payload
    employé. ``reussi`` est dérivé de ``score >= quiz.score_reussite``.

    Multi-société : ``company`` posée CÔTÉ SERVEUR ; ``quiz`` et ``employe``
    doivent appartenir à la même société. Additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_tentatives_quiz',
        verbose_name='Société',
    )
    quiz = models.ForeignKey(
        QuizFormation,
        on_delete=models.CASCADE,
        related_name='tentatives',
        verbose_name='Quiz',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='tentatives_quiz',
        verbose_name='Employé',
    )
    # Session de formation optionnelle liée : quand renseignée, la réussite
    # met à jour ``InscriptionFormation.resultat`` de cette session.
    session = models.ForeignKey(
        'rh.SessionFormation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tentatives_quiz',
        verbose_name='Session liée',
    )
    reponses = models.JSONField(
        default=list, blank=True, verbose_name='Réponses')
    score = models.PositiveSmallIntegerField(
        default=0, verbose_name='Score (%)')
    reussi = models.BooleanField(default=False, verbose_name='Réussi')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Tentative de quiz'
        verbose_name_plural = 'Tentatives de quiz'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_tquiz_comp_emp_idx'),
            models.Index(
                fields=['company', 'quiz'],
                name='rh_tquiz_comp_quiz_idx'),
        ]

    def __str__(self):
        return f'{self.employe.matricule} — {self.quiz.intitule} ({self.score}%)'


class JourBloqueConge(models.Model):
    """Jour de blocage congés (« Mandatory / Stress Days » Odoo) — ZRH4.

    Interdit la SOUMISSION d'une ``DemandeConge`` chevauchant une période
    bloquée (haute saison de pose, inventaire…). ``departements`` (M2M
    optionnel) restreint le blocage à des départements précis ; VIDE = toute
    la société. Distinct de XRH14 (fermetures IMPOSÉES qui CRÉENT des congés) :
    ici on REFUSE la demande, on n'en crée aucune. Le RH
    (``IsResponsableOrAdmin``) peut forcer via ``?forcer=1`` à la soumission
    (journalisé — pas de champ dédié, le refus reste la garde par défaut).

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps).
    Additif.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_jours_bloques_conge',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=160, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Du')
    date_fin = models.DateField(verbose_name='Au')
    # VIDE = bloque TOUTE la société ; sinon restreint aux départements liés.
    departements = models.ManyToManyField(
        Departement, blank=True, related_name='jours_bloques_conge',
        verbose_name='Départements concernés (vide = toute la société)')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Jour bloqué (congés)'
        verbose_name_plural = 'Jours bloqués (congés)'
        ordering = ['-date_debut']
        indexes = [
            models.Index(
                fields=['company', 'date_debut', 'date_fin'],
                name='rh_jbc_comp_debut_fin_idx'),
        ]

    def __str__(self):
        return f'{self.libelle} ({self.date_debut} → {self.date_fin})'


class BadgeReconnaissance(models.Model):
    """Badge de reconnaissance interne (ZRH14, « Employee badges » Odoo).

    Catalogue par société des badges attribuables entre collègues
    (gamification pair-à-pair/manager) — ex. « Esprit d'équipe », « Sécurité
    exemplaire ». Purement additif, non lié à la paie. Multi-société :
    ``company`` posée côté serveur (jamais lue du corps).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_badges_reconnaissance',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=80, verbose_name='Nom')
    description = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Description')
    icone = models.CharField(
        max_length=8, blank=True, default='🏅', verbose_name='Icône/emoji')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Badge de reconnaissance'
        verbose_name_plural = 'Badges de reconnaissance'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class AttributionBadge(models.Model):
    """Attribution d'un badge de reconnaissance à un collègue (ZRH14).

    Tout utilisateur authentifié de la société peut attribuer un badge à un
    collègue (jamais à lui-même — refusé côté service/vue, 400). Multi-
    société : ``company`` posée côté serveur ; ``badge`` et ``beneficiaire``
    doivent appartenir à la même société. ``attribue_par`` référence
    ``AUTH_USER_MODEL`` (app foundation), posé CÔTÉ SERVEUR depuis la
    requête (jamais lu du corps).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_attributions_badge',
        verbose_name='Société',
    )
    badge = models.ForeignKey(
        BadgeReconnaissance,
        on_delete=models.CASCADE,
        related_name='attributions',
        verbose_name='Badge',
    )
    beneficiaire = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='badges_recus',
        verbose_name='Bénéficiaire',
    )
    attribue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_badges_attribues',
        verbose_name='Attribué par',
    )
    message = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Message')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Attribution de badge'
        verbose_name_plural = 'Attributions de badge'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'beneficiaire'],
                name='rh_attrib_badge_benef_idx'),
        ]

    def __str__(self):
        return f'{self.badge.nom} → {self.beneficiaire.matricule}'


class DemandeAllocation(models.Model):
    """Demande d'allocation de congés self-service (ZRH13, « My Allocations
    / request allocation » Odoo).

    Distincte de ``DemandeConge`` (FG163, une ABSENCE prise sur le solde
    existant) : ici l'employé demande une allocation EXCEPTIONNELLE de jours
    (RTT, congé d'ancienneté, don de jours…) qui, une fois VALIDÉE,
    AUGMENTE le ``SoldeConge.acquis`` de l'année via un service dédié
    (jamais écrit directement du corps). Multi-société : ``company`` posée
    côté serveur ; ``employe`` et ``type_absence`` doivent appartenir à la
    même société.
    """
    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        VALIDEE = 'validee', 'Validée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_demandes_allocation',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='demandes_allocation',
        verbose_name='Employé',
    )
    type_absence = models.ForeignKey(
        TypeAbsence,
        on_delete=models.PROTECT,
        related_name='demandes_allocation',
        verbose_name="Type d'absence",
    )
    jours = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name='Jours demandés')
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.SOUMISE,
        verbose_name='Statut')
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rh_allocations_decidees',
        verbose_name='Décidé par',
    )
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de décision')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Demande d'allocation de congés"
        verbose_name_plural = "Demandes d'allocation de congés"
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe', 'statut'],
                name='rh_demande_alloc_emp_st_idx'),
        ]

    def __str__(self):
        return f'{self.employe.matricule} — {self.jours} j ({self.statut})'


class TypeLigneParcours(models.Model):
    """Type de ligne de parcours (ZRH15, « Resume Line Types » Odoo) —
    catalogue configurable par société (ex. Expérience, Formation,
    Certification interne). Distinct de ``Certification`` (FG174,
    validité/organisme d'une certification EXTERNE) et de l'historique de
    poste interne (XRH6, chatter) — simple timeline de parcours librement
    saisie. Multi-société : ``company`` posée côté serveur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_types_ligne_parcours',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=80, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Type de ligne de parcours'
        verbose_name_plural = 'Types de ligne de parcours'
        ordering = ['ordre', 'libelle']

    def __str__(self):
        return self.libelle


class LigneParcours(models.Model):
    """Ligne de parcours (ZRH15) — timeline chronologique d'un employé
    (expériences antérieures, diplômes, certifications internes…).
    Affichée en lecture seule (champs non sensibles) dans l'annuaire
    self-service (XRH28) et éditable sur la fiche employé. Multi-société :
    ``company`` posée côté serveur ; ``employe`` et ``type`` doivent
    appartenir à la même société.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_lignes_parcours',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='lignes_parcours',
        verbose_name='Employé',
    )
    type = models.ForeignKey(
        TypeLigneParcours,
        on_delete=models.PROTECT,
        related_name='lignes',
        verbose_name='Type',
    )
    intitule = models.CharField(max_length=160, verbose_name='Intitulé')
    organisme = models.CharField(
        max_length=160, blank=True, default='',
        verbose_name='Organisme/employeur')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    description = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Description')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Ligne de parcours'
        verbose_name_plural = 'Lignes de parcours'
        ordering = ['-date_debut', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe'],
                name='rh_ligne_parcours_emp_idx'),
        ]

    def __str__(self):
        return f'{self.employe.matricule} — {self.intitule}'


class HistoriqueCompetence(models.Model):
    """Historique des changements de niveau de compétence (ZRH10, « Skills
    Evolution » Odoo).

    Écrit AUTOMATIQUEMENT (jamais manuellement) à chaque changement de
    ``CompetenceEmploye.niveau`` — via
    ``services.enregistrer_niveau_competence``, appelé par TOUS les chemins
    d'écriture du niveau : matrice manuelle (``CompetenceEmployeViewSet``),
    session de formation réalisée (FG187,
    ``SessionFormationViewSet.marquer_realisee``) et réussite de quiz
    (XRH34, ``services.passer_tentative_quiz``). ``source`` distingue
    l'origine. Multi-société : ``company`` posée côté serveur.
    """
    class Source(models.TextChoices):
        MANUELLE = 'manuelle', 'Manuelle'
        QUIZ = 'quiz', 'Quiz de formation'
        FORMATION = 'formation', 'Session de formation'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_historiques_competence',
        verbose_name='Société',
    )
    employe = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='historique_competences',
        verbose_name='Employé',
    )
    competence = models.ForeignKey(
        Competence,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name='Compétence',
    )
    ancien_niveau = models.PositiveSmallIntegerField(
        verbose_name='Ancien niveau')
    nouveau_niveau = models.PositiveSmallIntegerField(
        verbose_name='Nouveau niveau')
    source = models.CharField(
        max_length=12, choices=Source.choices, default=Source.MANUELLE,
        verbose_name='Source')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Historique de compétence'
        verbose_name_plural = 'Historiques de compétence'
        ordering = ['-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'employe', 'competence'],
                name='rh_hist_comp_emp_comp_idx'),
        ]

    def __str__(self):
        return (f'{self.employe.matricule} — {self.competence.code} : '
                f'{self.ancien_niveau} → {self.nouveau_niveau}')


class RetourFeedback360(models.Model):
    """Feedback 360° — avis multi-sources sur un entretien (ZRH9).

    ``EvaluationEmploye`` (FG190) ne porte que la note manager (+ l'auto-
    éval XRH26). Ici, le RH/manager INVITE N répondants (pairs,
    subordonnés, managers transversaux) sur une évaluation ; chaque
    répondant ne voit et ne remplit QUE SON PROPRE retour — un autre
    répondant reçoit 403/404 (contrôlé dans la vue). Le couple
    (evaluation, repondant) est unique : une invitation crée une ligne NON
    SOUMISE (``soumis=False``), le répondant la complète puis la soumet. Une
    synthèse agrégée (côté selector) masque les retours individuels sous un
    seuil de répondants pour préserver l'anonymat. Multi-société :
    ``company`` posée côté serveur ; ``evaluation`` et ``repondant``
    doivent appartenir à la même société.
    """
    class Relation(models.TextChoices):
        PAIR = 'pair', 'Pair'
        SUBORDONNE = 'subordonne', 'Subordonné'
        MANAGER_TRANSVERSAL = 'manager_transversal', 'Manager transversal'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_retours_feedback360',
        verbose_name='Société',
    )
    evaluation = models.ForeignKey(
        EvaluationEmploye,
        on_delete=models.CASCADE,
        related_name='retours_360',
        verbose_name='Évaluation',
    )
    repondant = models.ForeignKey(
        DossierEmploye,
        on_delete=models.CASCADE,
        related_name='retours_feedback360',
        verbose_name='Répondant',
    )
    relation = models.CharField(
        max_length=20, choices=Relation.choices,
        default=Relation.PAIR, verbose_name='Relation')
    reponses = models.JSONField(
        blank=True, default=dict, verbose_name='Réponses')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    soumis = models.BooleanField(default=False, verbose_name='Soumis')
    date_invitation = models.DateTimeField(
        auto_now_add=True, verbose_name="Date d'invitation")
    date_soumission = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de soumission')

    class Meta:
        verbose_name = 'Retour feedback 360°'
        verbose_name_plural = 'Retours feedback 360°'
        ordering = ['-date_invitation']
        constraints = [
            models.UniqueConstraint(
                fields=['evaluation', 'repondant'],
                name='rh_feedback360_eval_repondant_uniq'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'evaluation'],
                name='rh_feedback360_comp_eval_idx'),
        ]

    def __str__(self):
        return f'{self.evaluation_id} — {self.repondant.matricule}'


# ── ZRH8 — Plans d'appréciation automatiques (jalons d'ancienneté) ─────────

class PlanAppreciation(models.Model):
    """Plan d'appréciation automatique par jalon d'ancienneté (ZRH8).

    Définit, pour une société, les JALONS d'ancienneté (``mois_apres_
    embauche``, ex. ``[3, 12, 24]``) auxquels un ``EvaluationEmploye``
    « planifiée » doit être créée automatiquement pour chaque
    ``DossierEmploye`` actif qui franchit le jalon — voir
    ``manage.py planifier_appreciations``. ``campagne_cible`` (optionnelle)
    pointe une ``CampagneEvaluation`` précise ; si absente, la commande crée/
    réutilise une campagne annuelle par défaut pour l'année en cours (voir
    ``services.campagne_annuelle_par_defaut``).

    Multi-société : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps de
    requête) ; ``campagne_cible`` doit appartenir à la même société. Additif.

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` plafonné ; ``mois_apres_
    embauche`` est un ``JSONField`` (liste d'entiers) — validé en Python
    (``clean``), jamais une contrainte DB.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rh_plans_appreciation',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=150, verbose_name='Libellé')
    # Liste JSON d'entiers positifs (mois après l'embauche), ex. [3, 12, 24].
    mois_apres_embauche = models.JSONField(
        default=list, blank=True, verbose_name="Jalons (mois après embauche)",
        help_text='Liste de nombres de mois, ex. [3, 12, 24].')
    campagne_cible = models.ForeignKey(
        'CampagneEvaluation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='plans_appreciation',
        verbose_name='Campagne cible',
        help_text='Vide = une campagne annuelle par défaut est '
        "créée/réutilisée à l'exécution.")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = "Plan d'appréciation"
        verbose_name_plural = "Plans d'appréciation"
        ordering = ['libelle']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='rh_planappr_comp_actif_idx'),
        ]

    def clean(self):
        """ZRH8 — ``mois_apres_embauche`` doit être une liste d'entiers > 0 ;
        ``campagne_cible`` (si fournie) doit appartenir à la même société."""
        from django.core.exceptions import ValidationError

        if not isinstance(self.mois_apres_embauche, list):
            raise ValidationError(
                "Les jalons doivent être une liste de nombres de mois.")
        for jalon in self.mois_apres_embauche:
            if not isinstance(jalon, int) or isinstance(jalon, bool) \
                    or jalon <= 0:
                raise ValidationError(
                    "Chaque jalon doit être un nombre entier de mois "
                    "strictement positif.")
        if self.campagne_cible_id is not None \
                and self.campagne_cible.company_id != self.company_id:
            raise ValidationError(
                "La campagne cible n'appartient pas à la même société.")

    def __str__(self):
        return self.libelle
