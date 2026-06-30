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
    # Gabarit dont ce contrat est issu (CONTRAT10) — référence interne à l'app
    # `contrats` (foundation), donc FK dur autorisé. NULLABLE + SET_NULL :
    # supprimer le gabarit n'efface jamais le contrat, il perd seulement le
    # lien (le rendu par fusion retombe alors sur un gabarit par défaut).
    modele = models.ForeignKey(
        'ModeleContrat',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_instancies',
        verbose_name='Modèle source',
    )
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    # CONTRAT20 — dates clés & tacite reconduction.
    # Délai de préavis (en JOURS) à respecter AVANT ``date_fin`` pour notifier
    # une non-reconduction / résiliation. NULL = aucun préavis exigé. La date
    # limite de préavis se calcule ``date_fin − preavis_jours`` (voir
    # ``echeance_preavis``). Un mois conventionnel se saisit en jours (ex. 30,
    # 60, 90) — on garde une seule unité (jours) pour un calcul sans ambiguïté.
    preavis_jours = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Préavis (jours avant la fin)')
    # Le contrat se renouvelle-t-il par TACITE RECONDUCTION à ``date_fin`` si
    # aucune partie ne dénonce dans le préavis ? Par défaut NON (sécurité : un
    # contrat ne se prolonge pas tout seul tant qu'on ne l'a pas déclaré).
    tacite_reconduction = models.BooleanField(
        default=False, verbose_name='Tacite reconduction')
    # Durée d'une période de reconduction, en MOIS (ex. 12 = reconduction
    # annuelle). NULL = non précisée. Pertinent seulement si
    # ``tacite_reconduction`` est vrai (purement déclaratif sinon).
    duree_reconduction_mois = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Durée de reconduction (mois)')
    # Drapeau métier : on a DÉJÀ AGI sur l'échéance de préavis de ce contrat
    # (dénoncé / reconduit explicitement / traité). Tant qu'il est faux, le
    # contrat remonte dans la liste « préavis à venir » (selectors.
    # contrats_a_preavis). Posé côté serveur ; jamais une transition de statut.
    preavis_traite = models.BooleanField(
        default=False, verbose_name='Préavis traité')
    # CONTRAT23 — renouvellement (manuel + tacite reconduction).
    # Date du DERNIER renouvellement effectif (manuel ou tacite). NULL = jamais
    # renouvelé. Posée côté serveur par ``services.renouveler_contrat`` — sert
    # à tracer qui/quand a été agi et de GARDE D'IDEMPOTENCE pour la tacite
    # reconduction (on ne re-reconduit pas une même période deux fois le même
    # jour). Jamais une transition de statut (préservation des statuts CONTRAT12).
    date_dernier_renouvellement = models.DateField(
        null=True, blank=True,
        verbose_name='Date du dernier renouvellement')
    # Nombre de renouvellements effectifs subis par le contrat (manuels +
    # tacites). Incrémenté de 1 à chaque renouvellement. Purement informatif /
    # audit ; n'entre dans aucune machine d'états.
    nb_renouvellements = models.PositiveIntegerField(
        default=0, verbose_name='Nombre de renouvellements')
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

    def echeance_preavis(self):
        """Date limite de préavis (``date_fin − preavis_jours``) ou ``None``.

        CONTRAT20. Renvoie la date au plus tard à laquelle il faut dénoncer le
        contrat pour éviter sa reconduction. ``None`` si ``date_fin`` ou
        ``preavis_jours`` n'est pas renseigné (rien à calculer).
        """
        from datetime import timedelta
        if self.date_fin is None or self.preavis_jours is None:
            return None
        return self.date_fin - timedelta(days=self.preavis_jours)

    def jours_avant_preavis(self, today=None):
        """Nombre de jours restants avant l'échéance de préavis (ou ``None``).

        CONTRAT20. Positif = l'échéance est à venir ; 0 = aujourd'hui ; négatif =
        l'échéance est dépassée. ``None`` si l'échéance n'est pas calculable
        (voir ``echeance_preavis``). ``today`` est injectable pour les tests.
        """
        echeance = self.echeance_preavis()
        if echeance is None:
            return None
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        return (echeance - today).days

    def jours_avant_echeance(self, today=None):
        """Nombre de jours restants avant la FIN du contrat (``date_fin``).

        CONTRAT21. Distinct de ``jours_avant_preavis`` (CONTRAT20) qui compte
        jusqu'à la date limite de préavis ; ici on compte jusqu'à l'échéance
        du contrat lui-même (``date_fin``). Positif = à venir ; 0 = aujourd'hui ;
        négatif = échéance dépassée. ``None`` si ``date_fin`` n'est pas
        renseigné. ``today`` est injectable pour les tests.
        """
        if self.date_fin is None:
            return None
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        return (self.date_fin - today).days

    @staticmethod
    def ajouter_mois(base, mois):
        """Renvoie ``base`` décalée de ``mois`` mois (sans dépendance externe).

        CONTRAT23. Décale une date d'un nombre entier de mois en gérant le
        débordement d'année et en bornant le jour au dernier jour du mois cible
        (ex. 31 janvier + 1 mois → 28/29 février). N'utilise que la bibliothèque
        standard (``calendar``) — pas de ``dateutil``.
        """
        import calendar

        total = (base.month - 1) + int(mois)
        annee = base.year + total // 12
        mois_cible = total % 12 + 1
        dernier_jour = calendar.monthrange(annee, mois_cible)[1]
        jour = min(base.day, dernier_jour)
        return base.replace(year=annee, month=mois_cible, day=jour)

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


class RegleApprobation(models.Model):
    """Règle d'approbation d'un contrat, par seuil de montant et/ou type (CONTRAT13).

    Détermine le ou les approbateur(s) requis avant de finaliser/signer un
    contrat, de façon DATA-DRIVEN : chaque règle déclare un intervalle de
    montant ``[montant_min, montant_max]`` (bornes optionnelles) et,
    optionnellement, un ``type_contrat`` ciblé. Le résolveur
    (``selectors.resoudre_regle_approbation``) choisit, parmi les règles
    actives de la société, la plus SPÉCIFIQUE qui couvre un couple
    (montant, type) donné — sans aucun seuil codé en dur.

    Spécificité (la plus spécifique gagne, à intervalle couvrant égal) :
    1. une règle ciblant le ``type_contrat`` exact prime sur une règle « tous
       types » (``type_contrat`` vide) ;
    2. à ce niveau égal, la règle dont l'intervalle de montant est le plus
       étroit prime ;
    3. à intervalle égal, ``priorite`` (plus grand d'abord) départage, puis
       l'``id`` le plus récent.

    Le résultat décrit l'exigence d'approbation : le ``niveau_approbation``
    requis (palier rôle) et un ``nombre_approbateurs`` minimal. La règle est
    purement déclarative — elle ne change AUCUN statut (préservation des
    statuts) ; un service appelant peut la consulter pour décider.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps).
    Lien de domaine LÂCHE uniquement (``type_contrat`` reprend les choix de
    ``Contrat`` mais reste une simple valeur — aucun import cross-app).
    """

    class NiveauApprobation(models.TextChoices):
        RESPONSABLE = 'responsable', 'Responsable'
        ADMINISTRATEUR = 'administrateur', 'Administrateur'
        DIRECTION = 'direction', 'Direction'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_regles_approbation',
        verbose_name='Société',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    # Type de contrat ciblé (reprend les choix de Contrat). Vide = tous types.
    type_contrat = models.CharField(
        max_length=20,
        choices=Contrat.TypeContrat.choices,
        blank=True,
        default='',
        verbose_name='Type de contrat ciblé',
    )
    # Bornes de montant (incluses). NULL = borne non fixée (ouverte de ce côté).
    montant_min = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant minimum')
    montant_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant maximum')
    # Exigence d'approbation portée par la règle.
    niveau_approbation = models.CharField(
        max_length=20,
        choices=NiveauApprobation.choices,
        default=NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis",
    )
    nombre_approbateurs = models.PositiveIntegerField(
        default=1, verbose_name="Nombre d'approbateurs requis")
    # Départage à intervalle/spécificité égaux (plus grand d'abord).
    priorite = models.PositiveIntegerField(default=0, verbose_name='Priorité')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Règle d'approbation"
        verbose_name_plural = "Règles d'approbation"
        ordering = ['-priorite', 'id']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='contrats_regleapp_co_act',
            ),
            models.Index(
                fields=['company', 'type_contrat'],
                name='contrats_regleapp_co_typ',
            ),
        ]

    def __str__(self):
        cible = self.get_type_contrat_display() if self.type_contrat else 'Tous types'
        return f'{self.libelle} ({cible})'

    def clean(self):
        """Valide la cohérence des bornes de montant.

        ``montant_min`` ne peut pas dépasser ``montant_max`` quand les deux sont
        fixés. Validation appliquée au niveau modèle (et relayée par le
        sérialiseur), sans jamais bloquer une borne ouverte (NULL).
        """
        if (
            self.montant_min is not None
            and self.montant_max is not None
            and self.montant_min > self.montant_max
        ):
            raise ValidationError(
                'Le montant minimum ne peut pas dépasser le montant maximum.')

    def couvre(self, montant, type_contrat=None):
        """Indique si la règle couvre un couple (montant, type_contrat).

        - Le ``type_contrat`` est couvert si la règle vise « tous types »
          (``type_contrat`` vide) OU correspond exactement au type demandé.
        - Le ``montant`` est couvert s'il tombe dans ``[montant_min,
          montant_max]`` (bornes incluses ; une borne NULL est ouverte).
        """
        if self.type_contrat and type_contrat and self.type_contrat != type_contrat:
            return False
        if self.type_contrat and not type_contrat:
            # Règle ciblée mais aucun type demandé : ne s'applique pas.
            return False
        if montant is None:
            return self.montant_min is None and self.montant_max is None
        montant = Decimal(str(montant))
        if self.montant_min is not None and montant < self.montant_min:
            return False
        if self.montant_max is not None and montant > self.montant_max:
            return False
        return True

    def largeur_intervalle(self):
        """Largeur de l'intervalle de montant (pour départager la spécificité).

        Une borne ouverte (NULL) compte comme « infinie » : une règle bornée des
        deux côtés est plus spécifique qu'une règle à borne ouverte.
        """
        if self.montant_min is None or self.montant_max is None:
            return None  # intervalle ouvert → moins spécifique
        return self.montant_max - self.montant_min


class EtapeApprobation(models.Model):
    """Une étape d'un workflow d'approbation interne d'un contrat (CONTRAT14).

    Le workflow d'approbation matérialise, pour un ``Contrat`` donné, la suite
    ordonnée des décisions internes requises AVANT signature. Il est instancié à
    partir de la ``RegleApprobation`` la plus spécifique (CONTRAT13) couvrant le
    contrat (montant + type) : la règle déclare combien d'approbations sont
    requises (``nombre_approbateurs``) et à quel ``niveau`` ; le service de
    lancement crée une ``EtapeApprobation`` par approbation requise, dans
    l'ordre.

    Chaque étape porte son propre ``statut`` LOCAL (``en_attente`` → ``approuve``
    / ``rejete``) — ces statuts sont PROPRES au workflow d'approbation et n'ont
    AUCUN lien avec le funnel de ``STAGES.py`` ni avec le ``Contrat.statut`` (qui
    reste piloté par sa machine d'états — voir ``machine_etats.py``). Le service
    ``approuver_etape`` / ``rejeter_etape`` fait avancer le workflow étape après
    étape sans jamais toucher au statut du contrat (préservation des statuts).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). ``contrat`` est une référence interne à l'app `contrats`
    (foundation), donc FK dur autorisé ; ``approbateur`` pointe vers
    ``AUTH_USER_MODEL`` (app foundation), FK autorisé et nullable tant que
    l'étape n'a pas été décidée.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_etapes_approbation',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        'Contrat',
        on_delete=models.CASCADE,
        related_name='etapes_approbation',
        verbose_name='Contrat',
    )
    # Règle source ayant généré cette étape (CONTRAT13) — référence interne à
    # l'app `contrats`. NULLABLE + SET_NULL : supprimer la règle n'efface pas
    # l'historique des décisions, l'étape perd seulement son lien d'origine.
    regle = models.ForeignKey(
        'RegleApprobation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='etapes_approbation',
        verbose_name="Règle d'approbation source",
    )
    # Ordre / rang de l'étape dans le workflow (1, 2, 3…). Détermine la séquence
    # d'avancement : on n'approuve l'étape n+1 qu'une fois l'étape n approuvée.
    niveau = models.PositiveIntegerField(
        default=1, verbose_name="Niveau / rang de l'étape")
    # Niveau de rôle requis pour cette étape (repris de la règle source). Valeur
    # déclarative — aucun contrôle de rôle codé en dur sur l'approbateur.
    niveau_approbation = models.CharField(
        max_length=20,
        choices=RegleApprobation.NiveauApprobation.choices,
        default=RegleApprobation.NiveauApprobation.RESPONSABLE,
        verbose_name="Niveau d'approbation requis",
    )
    # Utilisateur ayant décidé (NULL tant que l'étape est en attente).
    approbateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_etapes_approuvees',
        verbose_name='Approbateur',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        verbose_name='Statut',
    )
    decision_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidé le')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = "Étape d'approbation"
        verbose_name_plural = "Étapes d'approbation"
        ordering = ['contrat_id', 'niveau', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_etapeapp_co_sta',
            ),
            models.Index(
                fields=['contrat', 'niveau'],
                name='contrats_etapeapp_ct_niv',
            ),
        ]

    def __str__(self):
        return (
            f'Étape {self.niveau} — {self.get_statut_display()} '
            f'(contrat {self.contrat_id})'
        )


class ContratActivity(models.Model):
    """Chatter / journal d'un contrat (audit des transitions) — CONTRAT15.

    Historique « chatter » à la Odoo d'un ``Contrat``, modèle maison aligné sur
    ``litiges.ReclamationActivity`` / ``crm.LeadActivity``. Deux familles
    d'entrées :

      - automatiques (``type=log``) : audit des transitions du contrat —
        changement de ``statut`` (machine d'états CONTRAT12), changement de
        ``confidentialite`` (CONTRAT6), et chaque pas du workflow d'approbation
        interne (CONTRAT14 : lancement, approbation, rejet d'une étape). On
        consigne le champ touché (``field``) et son ancien → nouveau état
        (``old_value`` → ``new_value``) ;
      - manuelles (``type=note``) : notes libres (``message``).

    La société et l'auteur sont TOUJOURS posés côté serveur (jamais lus du corps
    de requête) — les vues écrivent ces entrées, jamais le navigateur.

    Multi-tenant : ``company`` est posée côté serveur. ``contrat`` est une
    référence interne à l'app `contrats` (foundation), FK dur autorisé ;
    ``auteur`` pointe vers ``AUTH_USER_MODEL`` (app foundation), FK autorisé et
    nullable (un changement automatisé sans utilisateur reste journalisable).

    RUNTIME-SAFETY (leçon FG136) : les instantanés ``old_value`` / ``new_value``
    peuvent être longs (un commentaire d'approbation, un libellé de niveau de
    confidentialité…) — ils sont en ``TextField`` pour ne JAMAIS dépasser une
    longueur maximale et lever en base.
    """

    class Kind(models.TextChoices):
        LOG = 'log', 'Transition'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_activites',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='activites',
        verbose_name='Contrat',
    )
    type = models.CharField(
        max_length=10, choices=Kind.choices, verbose_name='Type')
    # Champ concerné par une transition automatique (ex. ``statut``,
    # ``confidentialite``, ``approbation``). Vide pour une note manuelle.
    field = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Champ')
    # Instantanés AVANT/APRÈS d'une transition. TextField (et non CharField) :
    # ces valeurs peuvent être longues (commentaire d'approbation, etc.) — elles
    # ne doivent jamais dépasser une longueur maximale et lever (leçon FG136).
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
        related_name='contrats_activites',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Activité contrat'
        verbose_name_plural = 'Activités contrat'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['contrat', '-date_creation'],
                name='contrats_act_ct_date',
            ),
        ]

    def __str__(self):
        return f'{self.contrat_id} {self.type}'.strip()


class SignatureContrat(models.Model):
    """Signature électronique IN-APP d'un contrat (point e-sign) — CONTRAT16.

    Point de capture de signature électronique INTERNE à l'ERP : AUCUN
    prestataire d'e-sign externe, AUCUNE dépendance tierce. La validité juridique
    repose sur la **loi marocaine 53-05** (échange électronique de données
    juridiques) : un **nom dactylographié** (``signataire_nom``) consenti vaut
    signature électronique. On enregistre QUI a signé (le nom saisi + l'éventuel
    utilisateur agissant), à quel TITRE (``role_signataire`` : client /
    prestataire / témoin) et les ÉLÉMENTS DE PREUVE de l'acte (``ip_adresse``,
    ``user_agent``, ``date_signature``, ``methode``).

    Quand toutes les parties REQUISES (client ET prestataire) ont signé, le
    service ``signer_contrat`` fait basculer ``Contrat.statut`` vers ``signe``
    via la machine d'états gardée (``machine_etats.changer_statut``) — JAMAIS un
    funnel ``STAGES.py`` (rule #2) ni une écriture directe du statut. Les statuts
    documentaires du contrat (brouillon → en_approbation → signe → actif…) sont
    préservés 1:1 (CONTRAT12).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). ``contrat`` est une référence interne à l'app `contrats`
    (foundation), FK dur autorisé ; ``signataire`` (l'utilisateur agissant)
    pointe vers ``AUTH_USER_MODEL`` (app foundation), FK autorisé et NULLABLE :
    une partie externe (client) signe sans compte ERP — seul son nom saisi et
    les preuves font foi.

    RUNTIME-SAFETY (leçon FG136) : les valeurs ``CharField`` restent dans leur
    ``max_length`` — ``ip_adresse`` ≤ 45 (assez pour une IPv6 mappée), les codes
    bornés ``role_signataire`` / ``methode`` ≤ 20 — et ``user_agent``, qui peut
    être très long, est un ``TextField`` (aucune limite à dépasser et lever).
    """

    class RoleSignataire(models.TextChoices):
        CLIENT = 'client', 'Client'
        PRESTATAIRE = 'prestataire', 'Prestataire'
        TEMOIN = 'temoin', 'Témoin'

    class Methode(models.TextChoices):
        # Saisie du nom dactylographié (loi 53-05) — méthode par défaut.
        TYPED = 'typed', 'Nom dactylographié'
        # Tracé manuscrit capturé (paraphe dessiné), évidence stockée ailleurs.
        DRAW = 'draw', 'Signature dessinée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_signatures',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='signatures',
        verbose_name='Contrat',
    )
    # Nom dactylographié du signataire — fait foi (loi 53-05). Toujours saisi.
    signataire_nom = models.CharField(
        max_length=255, verbose_name='Nom du signataire')
    # Utilisateur ERP ayant agi (NULL pour un signataire externe sans compte).
    signataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_signatures',
        verbose_name='Utilisateur signataire',
    )
    role_signataire = models.CharField(
        max_length=20,
        choices=RoleSignataire.choices,
        default=RoleSignataire.CLIENT,
        verbose_name='Rôle du signataire',
    )
    date_signature = models.DateTimeField(
        auto_now_add=True, verbose_name='Signé le')
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

    class Meta:
        verbose_name = 'Signature de contrat'
        verbose_name_plural = 'Signatures de contrat'
        ordering = ['contrat_id', 'id']
        constraints = [
            # Une même partie (rôle) ne signe qu'une fois par contrat : empêche
            # les doublons de signature (client signe deux fois → un seul acte).
            models.UniqueConstraint(
                fields=['contrat', 'role_signataire'],
                name='contrats_signature_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['contrat', 'role_signataire'],
                name='contrats_sig_ct_role',
            ),
        ]

    def __str__(self):
        return (
            f'{self.signataire_nom} ({self.get_role_signataire_display()}) '
            f'— contrat {self.contrat_id}'
        )


class VersionContrat(models.Model):
    """Version IMMUABLE d'un rendu de contrat (versionnage des rendus) — CONTRAT18.

    Chaque ``VersionContrat`` fige un INSTANTANÉ du contenu d'un contrat à un
    instant donné (corps fusionné via CONTRAT10) et, éventuellement, la clé du
    rendu PDF stocké (MinIO). Le but est de PRÉSERVER les états antérieurs : une
    fois créée, une version n'est plus jamais modifiée ni supprimée via l'API
    (lecture seule), de sorte que l'historique des rendus reste fidèle même
    quand le contrat évolue.

    Numérotation par contrat : ``version`` démarre à 1 et s'incrémente de 1 à
    chaque nouvel instantané d'un MÊME contrat. Le numéro est posé CÔTÉ SERVEUR
    par ``services.creer_version`` qui calcule ``max(version)+1`` SOUS
    ``select_for_update`` (verrou de ligne sur le contrat) — JAMAIS un
    ``count()+1`` (qui entrait en collision en production, cf. la règle de
    numérotation du repo).

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). ``contrat`` est une référence interne à l'app `contrats`
    (foundation), FK dur autorisé ; ``cree_par`` pointe vers ``AUTH_USER_MODEL``
    (app foundation), FK autorisé et NULLABLE (un instantané déclenché
    automatiquement — p. ex. à la signature — reste journalisable sans
    utilisateur).

    RUNTIME-SAFETY (leçon FG136) : ``contenu`` est un ``TextField`` (un rendu de
    contrat peut être très long — aucune longueur maximale à dépasser et lever) ;
    ``motif`` est un ``CharField`` borné (≤255) et ``fichier_key`` un
    ``CharField`` borné (≤512, assez pour une clé d'objet MinIO). La contrainte
    d'unicité ``(contrat, version)`` et l'index sont nommés explicitement
    (≤30 chars) pour éviter la divergence d'auto-nommage Django.
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_versions',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='Contrat',
    )
    # Numéro de version (1, 2, 3…) par contrat, posé côté serveur (max+1 sous
    # verrou de ligne — jamais count()+1).
    version = models.PositiveIntegerField(verbose_name='Version')
    # Instantané IMMUABLE du corps fusionné du contrat. TextField : un rendu peut
    # être long (leçon FG136). Reste vide si seul un rendu PDF est figé.
    contenu = models.TextField(
        blank=True, default='', verbose_name='Contenu figé')
    # Clé du rendu PDF stocké (MinIO) — optionnelle. Borne large mais finie pour
    # une clé d'objet (leçon FG136).
    fichier_key = models.CharField(
        max_length=512, blank=True, default='',
        verbose_name='Clé du rendu PDF')
    # Motif/justification facultatif de la version (ex. « signature », « envoi
    # client », « révision juridique »). Borné (leçon FG136).
    motif = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_versions_creees',
        verbose_name='Créée par',
    )
    cree_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Version de contrat'
        verbose_name_plural = 'Versions de contrat'
        # Plus récent d'abord par contrat (la dernière version en tête).
        ordering = ['contrat_id', '-version', '-id']
        constraints = [
            # Un même numéro de version n'existe qu'une fois par contrat : filet
            # de sécurité DB derrière le calcul max+1 sous verrou (creer_version).
            models.UniqueConstraint(
                fields=['contrat', 'version'],
                name='contrats_version_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['contrat', '-version'],
                name='contrats_ver_ct_ver',
            ),
        ]

    def __str__(self):
        return f'Contrat {self.contrat_id} — version {self.version}'


class AlerteContrat(models.Model):
    """Rappel/alerte planifié sur un contrat, dispatché via les notifications — CONTRAT22.

    Une ``AlerteContrat`` enregistre un RAPPEL daté pour un ``Contrat`` :
    approche d'une échéance de préavis (``preavis`` — CONTRAT20), approche de la
    fin/renouvellement du contrat (``echeance`` — CONTRAT21), ou une date
    personnalisée (``personnalise``). À la date de déclenchement, le service
    ``declencher_alertes_contrat`` diffuse chaque alerte DUE via le SEUL point
    d'entrée de notification existant (``apps.notifications.services.notify`` —
    frontière cross-app : jamais d'import des modèles/vues de l'app
    notifications) puis marque l'alerte ``envoyee`` (avec ``date_envoi``).

    IDEMPOTENCE : seul un statut ``planifiee`` est dispatché ; une fois passé à
    ``envoyee`` une alerte n'est plus jamais renvoyée. Un statut ``annulee``
    sort définitivement l'alerte du circuit de déclenchement.

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête). ``contrat`` est une référence interne à l'app `contrats`
    (foundation), FK dur autorisé ; ``cree_par`` pointe vers ``AUTH_USER_MODEL``
    (app foundation), FK autorisé et NULLABLE (une alerte semée
    automatiquement — p. ex. à partir des sélecteurs préavis/renouvellement —
    reste journalisable sans utilisateur).

    RUNTIME-SAFETY (leçon FG136) : ``message`` est un ``TextField`` (un libellé
    d'alerte peut être long — aucune longueur maximale à dépasser et lever).
    Ces alertes sont PROPRES au module contrats : elles ne touchent jamais le
    funnel ``STAGES.py`` (rule #2) ni le ``Contrat.statut`` (préservation des
    statuts — CONTRAT12).
    """

    class TypeAlerte(models.TextChoices):
        PREAVIS = 'preavis', 'Échéance de préavis'
        ECHEANCE = 'echeance', 'Échéance / renouvellement'
        PERSONNALISE = 'personnalise', 'Date personnalisée'

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        ENVOYEE = 'envoyee', 'Envoyée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_alertes',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='alertes',
        verbose_name='Contrat',
    )
    type_alerte = models.CharField(
        max_length=20,
        choices=TypeAlerte.choices,
        default=TypeAlerte.PERSONNALISE,
        verbose_name="Type d'alerte",
    )
    # Date à laquelle l'alerte doit se déclencher (jour). Une alerte est DUE dès
    # que ``date_declenchement`` ≤ aujourd'hui ET ``statut == planifiee``.
    date_declenchement = models.DateField(
        verbose_name='Date de déclenchement')
    # Libellé de l'alerte affiché dans la notification. TextField : peut être
    # long sans jamais lever (leçon FG136).
    message = models.TextField(
        blank=True, default='', verbose_name='Message')
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.PLANIFIEE,
        verbose_name='Statut',
    )
    # Horodatage de l'envoi effectif (posé côté serveur lors du dispatch). NULL
    # tant que l'alerte n'a pas été envoyée.
    date_envoi = models.DateTimeField(
        null=True, blank=True, verbose_name='Envoyée le')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_alertes_creees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Alerte de contrat'
        verbose_name_plural = 'Alertes de contrat'
        ordering = ['date_declenchement', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut', 'date_declenchement'],
                name='contrats_alerte_co_st_dt',
            ),
            models.Index(
                fields=['contrat', 'statut'],
                name='contrats_alerte_ct_st',
            ),
        ]

    def __str__(self):
        return (
            f'Alerte {self.get_type_alerte_display()} '
            f'(contrat {self.contrat_id}, {self.date_declenchement})'
        )


class Avenant(models.Model):
    """Avenant (amendement) à un contrat → fige une nouvelle version — CONTRAT24.

    Un ``Avenant`` enregistre une MODIFICATION contractuelle apportée à un
    ``Contrat`` existant (changement d'objet, de montant, de périmètre…). Chaque
    avenant produit en aval un INSTANTANÉ IMMUABLE (``VersionContrat`` — CONTRAT18)
    figeant l'état du contrat AU MOMENT de l'amendement, de sorte que l'historique
    contractuel reste fidèle (l'avenant pointe vers la version créée via
    ``version_creee``). La création passe EXCLUSIVEMENT par
    ``services.creer_avenant`` (qui réutilise ``creer_version``) — jamais par un
    POST direct sur la ressource.

    Numérotation par contrat : ``numero`` démarre à 1 et s'incrémente de 1 pour
    chaque nouvel avenant d'un MÊME contrat. Le numéro est posé CÔTÉ SERVEUR par
    ``services.creer_avenant`` qui calcule ``max(numero)+1`` SOUS
    ``select_for_update`` (verrou de ligne sur le contrat) — JAMAIS un
    ``count()+1`` (qui entrait en collision en production, cf. la règle de
    numérotation du repo).

    ``montant_delta`` (optionnel) porte la VARIATION du montant du contrat
    introduite par l'avenant : quand il est fourni, ``services.creer_avenant``
    l'ajoute à ``Contrat.montant`` (côté serveur). Un avenant purement
    rédactionnel (sans impact financier) laisse ce champ ``NULL`` et ne touche
    pas le montant.

    Multi-tenant : ``company`` est posée côté serveur (jamais lue du corps de
    requête). ``contrat`` et ``version_creee`` sont des références INTERNES à
    l'app `contrats` (FK durs autorisés) ; ``version_creee`` est NULLABLE
    (``SET_NULL``) pour ne jamais perdre l'avenant si la version est purgée.
    ``cree_par`` pointe vers ``AUTH_USER_MODEL`` (app foundation), FK autorisé et
    NULLABLE (un avenant créé par un automatisme reste traçable sans utilisateur).

    RUNTIME-SAFETY (leçon FG136) : ``objet`` est un ``CharField`` borné (≤255) et
    ``description`` un ``TextField`` (un descriptif d'amendement peut être long —
    aucune longueur maximale à dépasser et lever). La contrainte d'unicité
    ``(contrat, numero)`` et les index sont NOMMÉS explicitement (≤30 chars) pour
    éviter la divergence d'auto-nommage Django. Cet objet ne touche JAMAIS le
    funnel ``STAGES.py`` (rule #2) ni le ``Contrat.statut`` (préservation des
    statuts — CONTRAT12).
    """

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_avenants',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='avenants',
        verbose_name='Contrat',
    )
    # Numéro d'avenant (1, 2, 3…) par contrat, posé côté serveur (max+1 sous
    # verrou de ligne — jamais count()+1).
    numero = models.PositiveIntegerField(verbose_name="Numéro d'avenant")
    # Objet court de l'amendement (titre). Borné (leçon FG136).
    objet = models.CharField(max_length=255, verbose_name="Objet de l'avenant")
    # Description détaillée de la modification. TextField : peut être long sans
    # jamais lever (leçon FG136).
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Date de prise d'effet de l'avenant.
    date_effet = models.DateField(
        null=True, blank=True, verbose_name="Date d'effet")
    # Variation du montant du contrat introduite par l'avenant (optionnelle).
    # Appliquée à ``Contrat.montant`` côté serveur quand fournie. NULL = avenant
    # rédactionnel sans impact financier.
    montant_delta = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True, verbose_name='Variation de montant')
    # Instantané immuable (CONTRAT18) figé par cet avenant. SET_NULL : on ne perd
    # jamais l'avenant si la version est supprimée.
    version_creee = models.ForeignKey(
        'VersionContrat',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='avenant',
        verbose_name='Version figée',
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_avenants_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Avenant de contrat'
        verbose_name_plural = 'Avenants de contrat'
        # Plus récent d'abord par contrat (le dernier avenant en tête).
        ordering = ['contrat_id', '-numero', '-id']
        constraints = [
            # Un même numéro d'avenant n'existe qu'une fois par contrat : filet
            # de sécurité DB derrière le calcul max+1 sous verrou (creer_avenant).
            models.UniqueConstraint(
                fields=['contrat', 'numero'],
                name='contrats_avenant_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['contrat', '-numero'],
                name='contrats_aven_ct_num',
            ),
        ]

    def __str__(self):
        return f'Avenant n°{self.numero} — contrat {self.contrat_id}'


class Resiliation(models.Model):
    """Résiliation d'un contrat (motif / préavis / solde) — CONTRAT25.

    Une ``Resiliation`` enregistre la RÉSILIATION d'un ``Contrat`` : le motif
    (``motif``), le préavis observé (``preavis_jours``), la date de prise d'effet
    (``date_effet``) et un éventuel solde de tout compte (``solde`` — montant de
    règlement/indemnité). Sa création passe EXCLUSIVEMENT par
    ``services.resilier_contrat``, qui fait basculer le ``Contrat.statut`` vers
    ``resilie`` via la machine d'états GARDÉE (``machine_etats.changer_statut``)
    — JAMAIS une écriture directe du statut, JAMAIS un funnel ``STAGES.py``
    (rule #2). L'état ``resilie`` est TERMINAL dans la machine d'états (CONTRAT12)
    et la résiliation n'est atteignable que depuis un état résiliable (la machine
    d'états en est l'unique gardienne).

    Statut LOCAL de la résiliation (``statut``) :
    - ``demande`` : la résiliation est demandée (préavis en cours) ;
    - ``effective`` : la résiliation a pris effet ;
    - ``annulee`` : la résiliation a été annulée (sort du circuit).

    UNE SEULE résiliation ACTIVE par contrat : une contrainte d'unicité PARTIELLE
    (``statut != annulee``) empêche d'ouvrir deux résiliations actives sur un même
    contrat ; une résiliation ``annulee`` ne bloque pas une nouvelle demande.

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (celle du contrat) — jamais
    lue du corps de requête. ``contrat`` et ``version_creee`` sont des références
    INTERNES à l'app `contrats` (FK durs autorisés) ; ``version_creee`` est
    NULLABLE (``SET_NULL``) pour ne jamais perdre la résiliation si la version est
    purgée. ``cree_par`` pointe vers ``AUTH_USER_MODEL`` (app foundation), FK
    autorisé et NULLABLE (une résiliation déclenchée par un automatisme reste
    traçable sans utilisateur).

    RUNTIME-SAFETY (leçon FG136) : ``motif`` est un ``TextField`` (un motif de
    résiliation peut être long — aucune longueur maximale à dépasser et lever) ;
    ``solde`` est un ``DecimalField`` nullable. La contrainte d'unicité partielle
    et l'index sont NOMMÉS explicitement (≤30 chars) pour éviter la divergence
    d'auto-nommage Django.
    """

    class Statut(models.TextChoices):
        DEMANDE = 'demande', 'Demandée'
        EFFECTIVE = 'effective', 'Effective'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_resiliations',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='resiliations',
        verbose_name='Contrat',
    )
    # Motif/justification de la résiliation. TextField : peut être long sans
    # jamais lever (leçon FG136).
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif de la résiliation')
    # Date de DEMANDE de la résiliation (posée côté serveur, défaut aujourd'hui).
    date_demande = models.DateField(
        null=True, blank=True, verbose_name='Date de demande')
    # Date de PRISE D'EFFET de la résiliation (après le préavis observé).
    date_effet = models.DateField(
        null=True, blank=True, verbose_name="Date d'effet")
    # Préavis (en JOURS) observé pour cette résiliation. NULL = non précisé.
    preavis_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Préavis (jours)')
    # Solde de tout compte / indemnité (montant de règlement). NULL = aucun solde.
    solde = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True, verbose_name='Solde / règlement')
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.DEMANDE,
        verbose_name='Statut',
    )
    # Instantané immuable (CONTRAT18) figé au moment de la résiliation. SET_NULL :
    # on ne perd jamais la résiliation si la version est supprimée.
    version_creee = models.ForeignKey(
        'VersionContrat',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resiliation',
        verbose_name='Version figée',
    )
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_resiliations_creees',
        verbose_name='Créée par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Résiliation de contrat'
        verbose_name_plural = 'Résiliations de contrat'
        ordering = ['contrat_id', '-id']
        constraints = [
            # UNE SEULE résiliation ACTIVE (non annulée) par contrat : filet de
            # sécurité DB derrière la garde idempotente du service.
            models.UniqueConstraint(
                fields=['contrat'],
                condition=~models.Q(statut='annulee'),
                name='contrats_resil_active_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['contrat', 'statut'],
                name='contrats_resil_ct_st',
            ),
        ]

    def __str__(self):
        return (
            f'Résiliation ({self.get_statut_display()}) '
            f'— contrat {self.contrat_id}'
        )
