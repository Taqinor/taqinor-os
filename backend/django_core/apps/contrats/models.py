"""Modèles de la Gestion des contrats (module `apps.contrats`).

Socle du cycle de vie contractuel (CLM) : le modèle ``Contrat`` recense les
contrats de la société (vente, O&M, monitoring, garantie, PPA, fournisseur,
sous-traitance, location, emploi, NDA, maintenance…) avec leur statut, leurs
dates et leur montant.

``ModeleContrat`` (CONTRAT7) — bibliothèque de modèles/gabarits réutilisables :
permet de pré-remplir un contrat à partir d'un gabarit enregistré (type,
clauses, corps, champs par défaut).  Tout est multi-société : chaque modèle
porte un FK ``company`` posé côté serveur (jamais lu du corps de requête).
Référence au client en lien lâche (``client_id``) — jamais un import cross-app
du modèle ``crm.Client``. Ce module est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Contrat(models.Model):
    """Un contrat de la société (cycle de vie contractuel).

    Le ``type_contrat`` qualifie la nature du contrat et le ``statut`` son
    avancement (brouillon → en approbation → signé → actif → suspendu/résilié/
    expiré). Le client est référencé en lien lâche par ``client_id`` ; un
    éventuel contrat de maintenance SAV l'est par ``sav_contrat_maintenance_id``
    (id seul, sans FK dur ni import de ``apps.sav``).
    """
    class TypeContrat(models.TextChoices):
        VENTE = 'vente', 'Vente'
        OM = 'om', 'O&M'
        MONITORING = 'monitoring', 'Monitoring'
        GARANTIE = 'garantie', 'Garantie'
        PPA = 'ppa', 'PPA'
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        SOUS_TRAITANCE = 'sous_traitance', 'Sous-traitance'
        LOCATION = 'location', 'Location'
        EMPLOI = 'emploi', 'Emploi'
        NDA = 'nda', 'NDA'
        MAINTENANCE = 'maintenance', 'Maintenance'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_APPROBATION = 'en_approbation', 'En approbation'
        SIGNE = 'signe', 'Signé'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        RESILIE = 'resilie', 'Résilié'
        EXPIRE = 'expire', 'Expiré'

    class NiveauConfidentialite(models.TextChoices):
        """Niveau de confidentialité d'un contrat.

        - ``PUBLIC`` : visible par tout utilisateur authentifié de la société.
        - ``INTERNE`` : visible uniquement par les Responsables et Administrateurs.
        - ``CONFIDENTIEL`` : visible uniquement par les Administrateurs.
        """
        PUBLIC = 'public', 'Public'
        INTERNE = 'interne', 'Interne'
        CONFIDENTIEL = 'confidentiel', 'Confidentiel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    type_contrat = models.CharField(
        max_length=20, choices=TypeContrat.choices,
        default=TypeContrat.VENTE, verbose_name='Type de contrat')
    objet = models.CharField(max_length=255, verbose_name='Objet')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Référence au client (crm.Client) en lien lâche — jamais un import du
    # modèle d'une autre app. NULL = pas de client rattaché.
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    # Lien LÂCHE vers un contrat de maintenance SAV (``sav.ContratMaintenance``)
    # par son ID seul — jamais un FK dur ni un import de ``sav.models``. NULL =
    # aucun contrat de maintenance rattaché. L'app `sav` n'expose PAS de
    # ``selectors.py`` aujourd'hui : on STOCKE l'id sans le valider ; un futur
    # sélecteur SAV permettra d'enrichir/valider (voir docstring du sérialiseur).
    sav_contrat_maintenance_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID du contrat de maintenance SAV')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    # Niveau de confidentialité : contrôle la visibilité du contrat au sein de
    # la société. PUBLIC = tous les utilisateurs authentifiés de la société ;
    # INTERNE = uniquement Responsables et Administrateurs ; CONFIDENTIEL =
    # uniquement Administrateurs. La valeur par défaut est INTERNE pour protéger
    # les données contractuelles sans sur-exposer.
    confidentialite = models.CharField(
        max_length=20,
        choices=NiveauConfidentialite.choices,
        default=NiveauConfidentialite.INTERNE,
        verbose_name='Confidentialité',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-id']

    def __str__(self):
        return f'{self.objet} ({self.get_type_contrat_display()})'

    def valider_parties(self):
        """Vérifie qu'un contrat finalisable a au moins deux parties.

        Renvoie ``True`` si la condition est remplie, sinon lève
        ``ValidationError`` — utilisé au moment de la finalisation/signature, et
        jamais en bloquant la création unitaire d'une partie.
        """
        if self.parties.count() < 2:
            raise ValidationError(
                'Un contrat doit comporter au moins deux parties.')
        return True


class PartieContrat(models.Model):
    """Une partie / un signataire d'un contrat (au moins deux par contrat).

    Chaque contrat met en présence plusieurs parties : le client, le
    prestataire, et éventuellement un témoin ou un garant. Le rôle est qualifié
    par ``type_partie`` et l'ordre d'affichage/signature par ``ordre``.

    La règle « au moins deux parties » n'est PAS imposée à la création unitaire
    (on ajoute les parties une à une) : elle est vérifiée au moment de la
    finalisation d'un contrat via ``Contrat.valider_parties`` (service léger),
    jamais en bloquant un simple POST.
    """
    class TypePartie(models.TextChoices):
        CLIENT = 'client', 'Client'
        PRESTATAIRE = 'prestataire', 'Prestataire'
        TEMOIN = 'temoin', 'Témoin'
        GARANT = 'garant', 'Garant'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='parties_contrat',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='parties',
        verbose_name='Contrat',
    )
    type_partie = models.CharField(
        max_length=20, choices=TypePartie.choices,
        default=TypePartie.CLIENT, verbose_name='Rôle de la partie')
    nom = models.CharField(max_length=255, verbose_name='Nom')
    fonction = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Fonction')
    email = models.EmailField(
        blank=True, default='', verbose_name='Email')
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Partie au contrat'
        verbose_name_plural = 'Parties au contrat'
        ordering = ['contrat_id', 'ordre', 'id']

    def __str__(self):
        return f'{self.nom} ({self.get_type_partie_display()})'


class ContratLien(models.Model):
    """Lien LÂCHE d'un contrat vers un document métier d'une AUTRE app.

    Permet de rattacher un contrat à un devis (``ventes``), un lead (``crm``),
    un chantier/installation (``installations``) ou une maintenance/ticket SAV
    (``sav``) SANS aucun FK dur : la cible est désignée par un couple typé
    ``(type_cible, cible_id)`` — jamais un import du modèle d'une autre app. Le
    ``libelle`` met en cache un libellé d'affichage ; les sélecteurs
    (``selectors.py``) l'enrichissent au vol quand l'app cible expose un
    sélecteur de lecture, et dégradent proprement (libellé stocké seul) sinon.
    """
    class TypeCible(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        LEAD = 'lead', 'Lead'
        INSTALLATION = 'installation', 'Installation'
        MAINTENANCE = 'maintenance', 'Maintenance'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrat_liens',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='liens',
        verbose_name='Contrat',
    )
    type_cible = models.CharField(
        max_length=20, choices=TypeCible.choices, verbose_name='Type de cible')
    # PK de l'objet cible dans son app (référence lâche, aucun FK dur).
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    # Libellé d'affichage mis en cache (fallback quand l'app cible n'a pas de
    # sélecteur d'enrichissement).
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Lien du contrat'
        verbose_name_plural = 'Liens du contrat'
        ordering = ['id']
        unique_together = [('contrat', 'type_cible', 'cible_id')]

    def __str__(self):
        return f'{self.contrat_id} → {self.type_cible} #{self.cible_id}'


class Clause(models.Model):
    """Clause réutilisable de la bibliothèque de clauses (CONTRAT8).

    Une ``Clause`` est un fragment textuel normatif (article, disposition,
    condition générale, obligation…) identifié par un ``titre``, rangé dans une
    ``categorie`` libre et qualifié par un ``type_clause``.  Elle est réutilisable
    sur n'importe quel ``ModeleContrat`` via la table de liaison ordonnée
    ``ModeleContratClause``.

    Multi-tenant : chaque clause porte un FK ``company`` posé côté serveur.
    ``actif=False`` masque la clause des listes de sélection sans la supprimer.
    ``ordre`` permet un tri par défaut au sein d'une catégorie.
    """

    class TypeClause(models.TextChoices):
        GENERALE = "generale", "Générale"
        TECHNIQUE = "technique", "Technique"
        FINANCIERE = "financiere", "Financière"
        JURIDIQUE = "juridique", "Juridique"
        RESILIATION = "resiliation", "Résiliation"
        GARANTIE = "garantie", "Garantie"
        CONFIDENTIALITE = "confidentialite", "Confidentialité"
        AUTRE = "autre", "Autre"

    company = models.ForeignKey(
        "authentication.Company",
        on_delete=models.CASCADE,
        related_name="contrats_clauses",
        verbose_name="Société",
    )
    titre = models.CharField(max_length=200, verbose_name="Titre")
    categorie = models.CharField(
        max_length=100, blank=True, default="", verbose_name="Catégorie"
    )
    type_clause = models.CharField(
        max_length=20,
        choices=TypeClause.choices,
        default=TypeClause.GENERALE,
        verbose_name="Type de clause",
    )
    corps = models.TextField(verbose_name="Corps de la clause")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name="Créé le"
    )

    class Meta:
        verbose_name = "Clause"
        verbose_name_plural = "Clauses"
        ordering = ["ordre", "titre"]
        indexes = [
            models.Index(
                fields=["company", "actif"],
                name="contrats_clause_co_actif",
            ),
            models.Index(
                fields=["company", "type_clause"],
                name="contrats_clause_co_type",
            ),
        ]

    def __str__(self):
        return f"{self.titre} ({self.get_type_clause_display()})"


class ModeleContrat(models.Model):
    """Gabarit/modèle de contrat réutilisable (bibliothèque de modèles — CONTRAT7).

    Permet de définir des canevas contractuels pré-remplis (clauses types,
    corps du contrat, valeurs par défaut) qu'un utilisateur peut instancier en
    un nouveau ``Contrat`` via l'action ``/instancier/``.

    Champs pré-remplis applicables à un ``Contrat`` :
    - ``type_contrat_defaut``  → ``Contrat.type_contrat``
    - ``devise_defaut``        → ``Contrat.devise``
    - ``confidentialite_defaut`` → ``Contrat.confidentialite``
    - ``corps``                → corps narratif du contrat (texte libre, non
                                 stocké directement sur ``Contrat`` — le gabarit
                                 peut servir de point de départ éditorial)
    - ``clauses``              → texte des clauses contractuelles types

    ``actif`` et ``ordre`` permettent de gérer la visibilité et l'ordre
    d'affichage dans les listes de sélection de gabarits.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_modeles',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du modèle')
    # Catégorie libre (ex. "O&M Standard", "PPA Résidentiel") — pas de choix
    # figés pour laisser la liberté à chaque société.
    categorie = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Catégorie')
    # Type de contrat par défaut (reprend les mêmes choix que Contrat).
    type_contrat_defaut = models.CharField(
        max_length=20,
        choices=Contrat.TypeContrat.choices,
        default=Contrat.TypeContrat.VENTE,
        verbose_name='Type de contrat par défaut',
    )
    # Corps narratif du contrat (texte libre, peut contenir des variables).
    corps = models.TextField(blank=True, default='', verbose_name='Corps du contrat')
    # Clauses contractuelles types (texte libre).
    clauses = models.TextField(
        blank=True, default='', verbose_name='Clauses types')
    # Valeurs par défaut propagées à un Contrat instancié depuis ce gabarit.
    devise_defaut = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise par défaut')
    confidentialite_defaut = models.CharField(
        max_length=20,
        choices=Contrat.NiveauConfidentialite.choices,
        default=Contrat.NiveauConfidentialite.INTERNE,
        verbose_name='Confidentialité par défaut',
    )
    actif = models.BooleanField(default=True, verbose_name='Actif')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Modèle de contrat'
        verbose_name_plural = 'Modèles de contrats'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.get_type_contrat_defaut_display()})'

    # M2M vers Clause via table de liaison ordonnée (CONTRAT8).
    # On ne peut pas déclarer le ManyToManyField ici avec through=ModeleContratClause
    # car la classe n'est pas encore définie — on l'ajoute juste après.


class ModeleContratClause(models.Model):
    """Liaison ordonnée entre un ``ModeleContrat`` et une ``Clause`` (CONTRAT8).

    Table de liaison M2M EXPLICITE pour conserver un ``ordre`` d'affichage
    spécifique au gabarit, indépendant de l'ordre général de la clause.
    Multi-tenant : ``company`` est redondant (les deux FK le portent déjà) mais
    facilite les filtrages et l'audit ; il est posé côté serveur.
    """

    company = models.ForeignKey(
        "authentication.Company",
        on_delete=models.CASCADE,
        related_name="contrats_modele_clauses",
        verbose_name="Société",
    )
    modele = models.ForeignKey(
        ModeleContrat,
        on_delete=models.CASCADE,
        related_name="modele_clauses",
        verbose_name="Modèle de contrat",
    )
    clause = models.ForeignKey(
        Clause,
        on_delete=models.CASCADE,
        related_name="modele_clauses",
        verbose_name="Clause",
    )
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        verbose_name = "Clause du modèle"
        verbose_name_plural = "Clauses du modèle"
        ordering = ["modele_id", "ordre", "id"]
        unique_together = [("modele", "clause")]
        indexes = [
            models.Index(
                fields=["modele", "ordre"],
                name="contrats_mc_clause_modele",
            ),
        ]

    def __str__(self):
        return f"{self.modele_id} → clause#{self.clause_id} (ordre {self.ordre})"


class ClauseContrat(models.Model):
    """Clause RÉSOLUE rattachée à un ``Contrat`` concret (CONTRAT9).

    Là où ``ModeleContratClause`` rattache une ``Clause`` à un *gabarit*
    (``ModeleContrat``), ``ClauseContrat`` rattache une clause à un *contrat*
    réel et instancié. C'est l'état « résolu » d'une clause : son ``titre`` et
    son ``corps`` sont matérialisés sur le contrat et peuvent être SURCHARGÉS
    (édités) indépendamment de la clause-source de la bibliothèque.

    - ``clause`` (FK ``Clause``, optionnel) — la clause-source de la
      bibliothèque dont ce texte est issu. NULL pour une clause ad hoc saisie
      directement sur le contrat (sans source en bibliothèque).
    - ``titre`` / ``corps`` — le texte résolu. À la création, on peut les copier
      depuis la clause-source via ``resoudre_depuis_clause`` ; toute édition
      ultérieure les surcharge (``surchargee=True``) sans toucher la source.
    - ``ordre`` — ordre d'affichage des clauses AU SEIN du contrat.
    - ``surchargee`` — drapeau indiquant que le texte a été édité par rapport à
      la clause-source (pour distinguer les clauses « telles quelles » de celles
      personnalisées).

    Multi-tenant : ``company`` est posée côté serveur. Une même clause-source
    n'est rattachée qu'une fois par contrat (``unique_together`` sur
    ``contrat`` + ``clause``), mais plusieurs clauses ad hoc (``clause=NULL``)
    sont permises sur un même contrat.
    """

    company = models.ForeignKey(
        "authentication.Company",
        on_delete=models.CASCADE,
        related_name="contrats_clauses_resolues",
        verbose_name="Société",
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name="clauses_resolues",
        verbose_name="Contrat",
    )
    # Clause-source de la bibliothèque (optionnelle) : NULL = clause ad hoc.
    clause = models.ForeignKey(
        Clause,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contrats_clauses_resolues",
        verbose_name="Clause source",
    )
    titre = models.CharField(max_length=200, verbose_name="Titre")
    corps = models.TextField(verbose_name="Corps résolu")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    surchargee = models.BooleanField(
        default=False, verbose_name="Texte surchargé"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name="Créé le"
    )

    class Meta:
        verbose_name = "Clause du contrat"
        verbose_name_plural = "Clauses du contrat"
        ordering = ["contrat_id", "ordre", "id"]
        constraints = [
            # Une clause-source donnée n'est rattachée qu'une fois par contrat.
            # Les clauses ad hoc (clause=NULL) ne sont PAS contraintes : un
            # contrat peut en porter plusieurs.
            models.UniqueConstraint(
                fields=["contrat", "clause"],
                condition=models.Q(clause__isnull=False),
                name="contrats_clausecontrat_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["contrat", "ordre"],
                name="contrats_clausec_co_ordre",
            ),
        ]

    def __str__(self):
        return f"{self.contrat_id} → {self.titre} (ordre {self.ordre})"

    def resoudre_depuis_clause(self):
        """Copie ``titre``/``corps`` depuis la clause-source si non déjà fixés.

        Appelée au moment de la résolution initiale : si une clause-source est
        liée et que ``titre``/``corps`` sont vides, on les matérialise depuis
        la source. Ne touche jamais la clause-source ; ne marque pas
        ``surchargee`` (la surcharge se constate à l'édition, pas à la copie).
        """
        if self.clause_id and self.clause is not None:
            if not self.titre:
                self.titre = self.clause.titre
            if not self.corps:
                self.corps = self.clause.corps
        return self
