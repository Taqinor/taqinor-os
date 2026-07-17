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
from django.utils import timezone

# NTSUB1-4 — nouveaux modèles « revenus récurrents » héritent du socle
# multi-tenant (core.models.TenantModel, ARC1/SCA4) plutôt que de re-hand-roller
# la FK ``company`` à la main (les modèles PRÉ-EXISTANTS de ce fichier restent
# tels quels — baseline gelée, cf. apps/records/platform_baselines).
from core.models import TenantModel


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
    # ZCTR1 — plan de facturation récurrente réutilisable rattaché (nullable).
    # NULL = comportement actuel inchangé (périodicité lue sur l'échéancier
    # local, ``EcheancierContrat.periodicite``). Référence interne à l'app
    # `contrats` (foundation), FK dur autorisé ; SET_NULL pour ne jamais
    # perdre le contrat si le plan est supprimé.
    plan_recurrent = models.ForeignKey(
        'PlanRecurrent',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats',
        verbose_name='Plan de facturation récurrente',
    )
    # NTSUB1 — offre catalogue rattachée (nullable). NULL = comportement actuel
    # inchangé. Sert UNIQUEMENT à pré-remplir montant/plan_recurrent à la
    # CRÉATION (services.appliquer_plan_abonnement, snapshot — jamais un lien
    # vivant qui recalculerait le montant si l'offre change après coup). SET_NULL
    # : supprimer l'offre ne perd jamais le contrat, il perd seulement le lien.
    plan_abonnement = models.ForeignKey(
        'PlanAbonnement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats',
        verbose_name="Plan d'abonnement",
    )
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
    # XCTR10 — propriétaire (owner) du contrat, pour attribuer MRR/churn par
    # commercial (commissions, redevabilité). NULLABLE (aucun changement de
    # comportement tant qu'il n'est pas renseigné) ; validé MÊME SOCIÉTÉ au
    # sérialiseur (jamais un utilisateur d'une autre société).
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_responsable',
        verbose_name='Responsable',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    # ARC14 — champs personnalisés (additif, jamais destructif). Les
    # définitions viennent de apps.customfields (module='contrat', pilote
    # enregistré via customfields.registry par apps/contrats/apps.py.ready()).
    custom_data = models.JSONField(
        null=True, blank=True, verbose_name='Champs personnalisés')

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

    # ── SCA35 — adoption du kit ``core.documents`` (lecture du graphe) ──────
    #
    # ``Contrat`` N'HÉRITE PAS de ``core.documents.DocumentMetier`` : le socle
    # du kit adosse ``TenantModel`` (related_name générique + nouvelles colonnes
    # ``created_at``/``updated_at``), alors que ``Contrat`` porte déjà sa propre
    # FK ``company`` (related_name historique ``'contrats'``) et son propre
    # horodatage (``date_creation``) — remplacer l'un ou l'autre exigerait soit
    # une migration additive non nécessaire, soit casser l'accesseur inverse
    # historique, pour ZÉRO gain fonctionnel. Le contrat de transitions du kit
    # (``TRANSITIONS`` : ``{source: {cible, ...}}`` + ``transitions_permises``/
    # ``transition_permise``) est en revanche adopté À L'IDENTIQUE : cette
    # propriété EXPOSE, en lecture seule, le graphe de la machine d'états
    # EXISTANTE (``machine_etats._transitions()``, CONTRAT12) sous la forme que
    # le kit attend — elle ne le duplique pas, ne le recalcule pas, ne mute
    # jamais le statut. Le SEUL point d'écriture reste ``services.changer_statut``
    # (alias de ``machine_etats.changer_statut``), qui applique EN PLUS la garde
    # « au moins deux parties » (``valider_parties``) sur la finalisation/
    # signature — une règle métier que le socle générique du kit ne connaît pas
    # et qui doit rester dans la machine d'états, pas migrée vers une table
    # statique. Un test de non-régression (``test_sca35_kit_transitions.py``)
    # prouve que ``Contrat.TRANSITIONS`` == le graphe de ``machine_etats`` pour
    # CHAQUE statut, statut par statut.
    @property
    def TRANSITIONS(self):  # noqa: N802 — nom du contrat kit (majuscules voulues)
        """Graphe de transitions au format du kit (``core.documents``).

        Miroir en LECTURE SEULE de ``machine_etats._transitions()`` — la machine
        d'états CONTRAT12 reste l'unique source de vérité et l'unique éditeur du
        statut (via ``services.changer_statut``)."""
        from . import machine_etats

        return machine_etats._transitions()

    def transitions_permises(self) -> set:
        """Ensemble des statuts atteignables depuis le statut courant.

        Même contrat que ``core.documents.DocumentMetier.transitions_permises``
        — lit le graphe de ``machine_etats`` (jamais une transition hardcodée)."""
        return set(self.TRANSITIONS.get(self.statut, ()) or ())

    def transition_permise(self, cible) -> bool:
        """``True`` si ``statut courant → cible`` est autorisé par le graphe.

        Même contrat que ``core.documents.DocumentMetier.transition_permise``."""
        return cible in self.transitions_permises()


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


class MotifResiliation(models.Model):
    """Référentiel éditable des motifs de résiliation (close reasons) — ZCTR3.

    Odoo attache un « Close Reason » configurable à chaque churn pour
    l'analyse. Jusqu'ici ``Resiliation.motif`` est un texte libre (le champ
    RESTE, pour rétrocompat) qui rend les agrégats de churn (XCTR7) bruités.
    ``MotifResiliation`` est un référentiel COMPANY-SCOPÉ (code, libellé,
    ordre d'affichage, catégorie optionnelle) qu'une ``Resiliation`` peut
    rattacher via ``motif_ref`` (FK nullable, en PLUS du texte libre).

    Multi-tenant : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps de
    requête, ``TenantMixin.perform_create``).

    RUNTIME-SAFETY (leçon FG136) : ``code``/``libelle`` bornés ; l'index est
    NOMMÉ explicitement (≤30 chars).
    """

    class Categorie(models.TextChoices):
        PRIX = 'prix', 'Prix'
        CONCURRENT = 'concurrent', 'Concurrent'
        INSATISFACTION = 'insatisfaction', 'Insatisfaction'
        FIN_PROJET = 'fin_projet', 'Fin de projet'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='motifs_resiliation',
        verbose_name='Société',
    )
    code = models.CharField(max_length=50, verbose_name='Code')
    libelle = models.CharField(max_length=150, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    categorie = models.CharField(
        max_length=20, choices=Categorie.choices,
        blank=True, default='', verbose_name='Catégorie')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Motif de résiliation'
        verbose_name_plural = 'Motifs de résiliation'
        ordering = ['ordre', 'libelle', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='contrats_motifresil_co_code',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='contrats_motifresil_co_act',
            ),
        ]

    def __str__(self):
        return self.libelle


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
    # jamais lever (leçon FG136). RESTE pour rétrocompat (texte libre) — ZCTR3
    # ajoute ``motif_ref`` en PLUS, jamais en remplacement.
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif de la résiliation')
    # ZCTR3 — motif NORMALISÉ (référentiel éditable), en plus du texte libre
    # ``motif`` ci-dessus. NULL = motif texte libre uniquement (comportement
    # historique inchangé) ; SET_NULL pour ne jamais perdre la résiliation si
    # le motif référentiel est supprimé.
    motif_ref = models.ForeignKey(
        'MotifResiliation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resiliations',
        verbose_name='Motif (référentiel)',
    )
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


class Obligation(models.Model):
    """Obligation / livrable contractuel d'un contrat — CONTRAT26.

    Une ``Obligation`` recense un ENGAGEMENT concret porté par un ``Contrat`` :
    un livrable à fournir, une prestation à exécuter, une condition à remplir
    (ex. « Mise en service de la centrale », « Remise du dossier ONEE »,
    « Rapport de performance trimestriel »). Chaque obligation porte une partie
    REDEVABLE (``redevable`` : prestataire / client), une échéance
    (``date_echeance``) et un statut d'avancement LOCAL — propre au suivi des
    obligations, sans AUCUN lien avec le ``Contrat.statut`` (machine d'états
    CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Une obligation peut être rattachée à un ``JalonContrat`` (regroupement par
    jalon) — référence INTERNE à l'app `contrats` (FK dur autorisé), NULLABLE
    (``SET_NULL``) : supprimer le jalon n'efface jamais l'obligation.

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat) —
    jamais lue du corps de requête. ``contrat`` est une référence interne à
    l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``intitule`` est un ``CharField`` borné
    (≤255) et ``description`` un ``TextField`` (un descriptif de livrable peut
    être long — aucune longueur maximale à dépasser et lever). L'index est NOMMÉ
    explicitement (≤30 chars) pour éviter la divergence d'auto-nommage Django.
    """

    class Redevable(models.TextChoices):
        PRESTATAIRE = 'prestataire', 'Prestataire'
        CLIENT = 'client', 'Client'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        EN_COURS = 'en_cours', 'En cours'
        FAITE = 'faite', 'Réalisée'
        EN_RETARD = 'en_retard', 'En retard'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_obligations',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='obligations',
        verbose_name='Contrat',
    )
    # Jalon de rattachement (optionnel) — référence interne à l'app contrats.
    jalon = models.ForeignKey(
        'JalonContrat',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='obligations',
        verbose_name='Jalon',
    )
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    redevable = models.CharField(
        max_length=20, choices=Redevable.choices,
        default=Redevable.PRESTATAIRE, verbose_name='Partie redevable')
    date_echeance = models.DateField(
        null=True, blank=True, verbose_name="Date d'échéance")
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.A_FAIRE, verbose_name='Statut')
    # Date de réalisation effective (posée côté serveur quand l'obligation passe
    # à ``faite``). NULL tant que non réalisée.
    date_realisation = models.DateField(
        null=True, blank=True, verbose_name='Réalisée le')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Obligation contractuelle'
        verbose_name_plural = 'Obligations contractuelles'
        ordering = ['contrat_id', 'ordre', 'date_echeance', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_oblig_co_st',
            ),
            models.Index(
                fields=['contrat', 'date_echeance'],
                name='contrats_oblig_ct_dt',
            ),
        ]

    def __str__(self):
        return f'{self.intitule} (contrat {self.contrat_id})'


class JalonContrat(models.Model):
    """Jalon / étape clé d'un contrat (regroupe des obligations) — CONTRAT26.

    Un ``JalonContrat`` matérialise une ÉTAPE CLÉ datée du déroulé contractuel
    (ex. « Signature », « Mise en service », « Réception définitive »,
    « Fin de garantie ») à laquelle on rattache des ``Obligation`` (livrables).
    Le jalon porte sa propre date cible (``date_cible``) et un statut LOCAL
    d'avancement — propre au suivi des jalons, sans AUCUN lien avec le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Numérotation par contrat : ``numero`` démarre à 1 et s'incrémente de 1 pour
    chaque nouveau jalon d'un MÊME contrat. Le numéro est posé CÔTÉ SERVEUR par
    ``services.creer_jalon`` qui calcule ``max(numero)+1`` SOUS
    ``select_for_update`` (verrou de ligne sur le contrat) — JAMAIS un
    ``count()+1`` (qui collisionne, cf. la règle de numérotation du repo).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``intitule`` est borné (≤255) et
    ``description`` un ``TextField``. La contrainte d'unicité ``(contrat,
    numero)`` et l'index sont NOMMÉS explicitement (≤30 chars).
    """

    class Statut(models.TextChoices):
        A_VENIR = 'a_venir', 'À venir'
        EN_COURS = 'en_cours', 'En cours'
        ATTEINT = 'atteint', 'Atteint'
        EN_RETARD = 'en_retard', 'En retard'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_jalons',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='jalons',
        verbose_name='Contrat',
    )
    # Numéro de jalon (1, 2, 3…) par contrat, posé côté serveur (max+1 sous
    # verrou de ligne — jamais count()+1).
    numero = models.PositiveIntegerField(verbose_name='Numéro de jalon')
    intitule = models.CharField(max_length=255, verbose_name='Intitulé')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    date_cible = models.DateField(
        null=True, blank=True, verbose_name='Date cible')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.A_VENIR, verbose_name='Statut')
    # Date d'atteinte effective du jalon (posée côté serveur). NULL tant que
    # non atteint.
    date_atteinte = models.DateField(
        null=True, blank=True, verbose_name='Atteint le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jalon de contrat'
        verbose_name_plural = 'Jalons de contrat'
        ordering = ['contrat_id', 'numero', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['contrat', 'numero'],
                name='contrats_jalon_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['contrat', 'date_cible'],
                name='contrats_jalon_ct_dt',
            ),
        ]

    def __str__(self):
        return f'Jalon n°{self.numero} — {self.intitule} (contrat {self.contrat_id})'


class EngagementSLA(models.Model):
    """Engagement de niveau de service (SLA) & pénalités d'un contrat — CONTRAT27.

    Un ``EngagementSLA`` déclare, pour un ``Contrat``, un ENGAGEMENT DE SERVICE
    chiffré (ex. « disponibilité ≥ 98 % », « délai d'intervention ≤ 24 h »,
    « PR ≥ 80 % ») et la PÉNALITÉ contractuelle encourue en cas de manquement.
    Le ``taux_cible`` exprime l'objectif en pourcentage (0–100) ; ``unite``
    qualifie la métrique (disponibilité, délai, performance…). La pénalité est
    soit un MONTANT FIXE (``mode_penalite=fixe`` → ``valeur_penalite`` est un
    montant en devise du contrat) soit un POURCENTAGE du montant du contrat
    (``mode_penalite=pourcentage`` → ``valeur_penalite`` est un pourcentage,
    plafonné par ``penalite_max`` optionnel).

    Le calcul d'une pénalité encourue (``services.calculer_penalite_sla``) est
    PUREMENT DÉCLARATIF : il ne crée aucune écriture, ne touche AUCUN
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et
    n'émet aucune facture — il renvoie un montant indicatif qu'un service
    appelant peut consulter.

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` est borné (≤200), ``unite`` borné
    (≤30) ; les pourcentages/montants sont des ``DecimalField`` bornés. L'index
    est NOMMÉ explicitement (≤30 chars).
    """

    class ModePenalite(models.TextChoices):
        FIXE = 'fixe', 'Montant fixe'
        POURCENTAGE = 'pourcentage', 'Pourcentage du montant du contrat'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_sla',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='engagements_sla',
        verbose_name='Contrat',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé du SLA')
    # Objectif chiffré en pourcentage (ex. 98.00 pour 98 %). Borné [0, 100] au
    # niveau du modèle (``clean``) / sérialiseur.
    taux_cible = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Taux cible (%)')
    # Unité/métrique de l'engagement (libre, ex. « disponibilité », « délai »).
    unite = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Unité / métrique')
    mode_penalite = models.CharField(
        max_length=20, choices=ModePenalite.choices,
        default=ModePenalite.FIXE, verbose_name='Mode de pénalité')
    # Valeur de la pénalité : montant (mode fixe) OU pourcentage (mode
    # pourcentage). Interprétée selon ``mode_penalite``.
    valeur_penalite = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Valeur de la pénalité')
    # Plafond optionnel de la pénalité (montant en devise du contrat). NULL =
    # aucun plafond.
    penalite_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Plafond de pénalité')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Engagement SLA'
        verbose_name_plural = 'Engagements SLA'
        ordering = ['contrat_id', 'id']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='contrats_sla_co_act',
            ),
        ]

    def __str__(self):
        return f'{self.libelle} (contrat {self.contrat_id})'

    def clean(self):
        """Valide la cohérence du taux cible et des valeurs de pénalité.

        ``taux_cible`` doit rester dans [0, 100] ; en mode pourcentage,
        ``valeur_penalite`` doit aussi rester dans [0, 100]. Les valeurs
        négatives sont refusées.
        """
        if self.taux_cible is not None and not (
                Decimal('0') <= self.taux_cible <= Decimal('100')):
            raise ValidationError(
                'Le taux cible doit être compris entre 0 et 100.')
        if self.valeur_penalite is not None and self.valeur_penalite < 0:
            raise ValidationError(
                'La valeur de la pénalité ne peut pas être négative.')
        if (self.mode_penalite == self.ModePenalite.POURCENTAGE
                and self.valeur_penalite is not None
                and self.valeur_penalite > Decimal('100')):
            raise ValidationError(
                'En mode pourcentage, la pénalité ne peut pas dépasser 100 %.')

    def calculer_penalite(self, *, montant_contrat=None):
        """Montant de pénalité encouru pour ce SLA (lecture seule, déclaratif).

        - Mode ``fixe`` : renvoie ``valeur_penalite`` telle quelle.
        - Mode ``pourcentage`` : renvoie ``valeur_penalite % × montant_contrat``
          (``montant_contrat`` par défaut = ``self.contrat.montant``).
        Le résultat est borné par ``penalite_max`` quand il est fixé. Ne crée
        AUCUNE écriture et ne change AUCUN statut.
        """
        if montant_contrat is None:
            montant_contrat = self.contrat.montant or Decimal('0')
        montant_contrat = Decimal(str(montant_contrat))
        if self.mode_penalite == self.ModePenalite.POURCENTAGE:
            penalite = (montant_contrat * (self.valeur_penalite or Decimal('0'))
                        / Decimal('100'))
        else:
            penalite = self.valeur_penalite or Decimal('0')
        if self.penalite_max is not None and penalite > self.penalite_max:
            penalite = self.penalite_max
        return penalite.quantize(Decimal('0.01'))


class RetenueGarantie(models.Model):
    """Retenue de garantie d'un contrat + suivi de libération — CONTRAT28.

    Une ``RetenueGarantie`` enregistre la RETENUE DE GARANTIE pratiquée sur un
    ``Contrat`` (somme conservée par le maître d'ouvrage jusqu'à la levée des
    réserves / fin de la période de garantie). Elle porte la base de calcul
    (``montant_base``), le taux retenu (``taux``, en %) et le ``montant_retenu``
    (calculé ``montant_base × taux %``, posé côté serveur). Le SUIVI DE
    LIBÉRATION se fait via le ``statut`` LOCAL (``retenue`` → ``liberee`` /
    ``annulee``) et les dates clés (``date_retenue``, ``date_liberation_prevue``,
    ``date_liberation_effective``).

    Le ``statut`` est PROPRE au suivi de la retenue : il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et la
    libération n'émet aucune facture/aucun mouvement comptable (déclaratif).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``note`` est un ``TextField`` ; les montants
    sont des ``DecimalField`` bornés. L'index est NOMMÉ explicitement (≤30 chars).
    """

    class Statut(models.TextChoices):
        RETENUE = 'retenue', 'Retenue'
        LIBEREE = 'liberee', 'Libérée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_retenues',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='retenues_garantie',
        verbose_name='Contrat',
    )
    # Base de calcul de la retenue (montant HT/TTC du marché ou d'une situation).
    montant_base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant de base')
    # Taux de retenue en pourcentage (ex. 5.00 pour 5 %).
    taux = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Taux de retenue (%)')
    # Montant effectivement retenu (calculé côté serveur = base × taux %).
    montant_retenu = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant retenu')
    date_retenue = models.DateField(
        null=True, blank=True, verbose_name='Date de retenue')
    date_liberation_prevue = models.DateField(
        null=True, blank=True, verbose_name='Libération prévue le')
    date_liberation_effective = models.DateField(
        null=True, blank=True, verbose_name='Libérée le')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.RETENUE, verbose_name='Statut')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Retenue de garantie'
        verbose_name_plural = 'Retenues de garantie'
        ordering = ['contrat_id', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_retg_co_st',
            ),
            models.Index(
                fields=['contrat', 'date_liberation_prevue'],
                name='contrats_retg_ct_dt',
            ),
        ]

    def __str__(self):
        return (
            f'Retenue {self.montant_retenu} ({self.get_statut_display()}) '
            f'— contrat {self.contrat_id}'
        )

    def calculer_montant_retenu(self):
        """Montant retenu = ``montant_base × taux %`` (arrondi 2 décimales)."""
        base = self.montant_base or Decimal('0')
        taux = self.taux or Decimal('0')
        return (base * taux / Decimal('100')).quantize(Decimal('0.01'))


class Caution(models.Model):
    """Caution / garantie bancaire liée à un contrat (registre) — CONTRAT29.

    Une ``Caution`` recense une GARANTIE FINANCIÈRE liée à un ``Contrat`` :
    caution de soumission, caution de bonne exécution/réalisation, caution de
    restitution d'acompte, garantie de retenue de garantie, garantie de la
    société mère, ou autre. Elle porte le ``type_caution``, l'organisme GARANT
    (``garant`` — banque/assureur), une éventuelle référence d'acte
    (``reference``), le ``montant`` garanti, les dates de validité
    (``date_emission`` → ``date_expiration``) et un ``statut`` LOCAL de cycle de
    vie (``active`` → ``mainlevee`` / ``appelee`` / ``expiree`` / ``annulee``).

    Le ``statut`` est PROPRE au registre des cautions : il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``garant`` / ``reference`` sont des
    ``CharField`` bornés et ``note`` un ``TextField``. Les index sont NOMMÉS
    explicitement (≤30 chars).
    """

    class TypeCaution(models.TextChoices):
        SOUMISSION = 'soumission', 'Caution de soumission'
        BONNE_EXECUTION = 'bonne_execution', 'Caution de bonne exécution'
        RESTITUTION_ACOMPTE = 'restitution_acompte', "Restitution d'acompte"
        RETENUE_GARANTIE = 'retenue_garantie', 'Garantie de retenue'
        SOCIETE_MERE = 'societe_mere', 'Garantie société mère'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        ACTIVE = 'active', 'Active'
        MAINLEVEE = 'mainlevee', 'Mainlevée'
        APPELEE = 'appelee', 'Appelée'
        EXPIREE = 'expiree', 'Expirée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_cautions',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='cautions',
        verbose_name='Contrat',
    )
    type_caution = models.CharField(
        max_length=30, choices=TypeCaution.choices,
        default=TypeCaution.BONNE_EXECUTION, verbose_name='Type de caution')
    # Organisme garant (banque, compagnie d'assurance, maison mère…).
    garant = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Garant')
    # Référence de l'acte de cautionnement (numéro bancaire…).
    reference = models.CharField(
        max_length=100, blank=True, default='', verbose_name='Référence')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant garanti')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    date_emission = models.DateField(
        null=True, blank=True, verbose_name="Date d'émission")
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.ACTIVE, verbose_name='Statut')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Caution / garantie'
        verbose_name_plural = 'Cautions / garanties'
        ordering = ['contrat_id', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_caut_co_st',
            ),
            models.Index(
                fields=['contrat', 'date_expiration'],
                name='contrats_caut_ct_exp',
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_type_caution_display()} {self.montant} '
            f'({self.get_statut_display()}) — contrat {self.contrat_id}'
        )


class EcheancierContrat(models.Model):
    """Échéancier de paiement d'un contrat (en-tête) — CONTRAT30.

    Un ``EcheancierContrat`` regroupe les ÉCHÉANCES de paiement d'un ``Contrat``
    (plan de règlement). Il porte un ``libelle``, une ``periodicite`` indicative
    (mensuelle, trimestrielle…) et un ``statut`` LOCAL (``brouillon`` →
    ``actif`` → ``solde`` / ``annule``). Les montants détaillés vivent sur les
    ``LigneEcheance`` rattachées ; ``montant_total`` met en cache la somme des
    lignes (posé côté serveur).

    Le ``statut`` est PROPRE à l'échéancier : il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et
    n'émet aucune facture (l'émission récurrente est CONTRAT31, séparée).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné (≤200) ; l'index est NOMMÉ
    explicitement (≤30 chars).
    """

    class Periodicite(models.TextChoices):
        UNIQUE = 'unique', 'Paiement unique'
        MENSUELLE = 'mensuelle', 'Mensuelle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        SEMESTRIELLE = 'semestrielle', 'Semestrielle'
        ANNUELLE = 'annuelle', 'Annuelle'
        PERSONNALISEE = 'personnalisee', 'Personnalisée'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        SOLDE = 'solde', 'Soldé'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_echeanciers',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='echeanciers',
        verbose_name='Contrat',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    periodicite = models.CharField(
        max_length=20, choices=Periodicite.choices,
        default=Periodicite.UNIQUE, verbose_name='Périodicité')
    # Somme des lignes (cache posé côté serveur). Recalculé à chaque
    # création/modification/suppression de ligne.
    montant_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant total')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # CONTRAT31 — quand vrai, les lignes de cet échéancier peuvent ALIMENTER la
    # facturation récurrente (émission d'une Facture via ``ventes`` à
    # l'échéance). Faux par défaut : on n'émet jamais de facture tant que ce
    # drapeau n'est pas posé. Aucune écriture automatique tant qu'on n'appelle
    # pas explicitement le service de facturation.
    facturation_active = models.BooleanField(
        default=False, verbose_name='Facturation récurrente active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Échéancier de contrat'
        verbose_name_plural = 'Échéanciers de contrat'
        ordering = ['contrat_id', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_ech_co_st',
            ),
        ]

    def __str__(self):
        return (
            f'Échéancier {self.libelle or self.id} '
            f'({self.get_statut_display()}) — contrat {self.contrat_id}'
        )


class LigneEcheance(models.Model):
    """Ligne (échéance) d'un échéancier de paiement — CONTRAT30.

    Une ``LigneEcheance`` est une ÉCHÉANCE datée d'un ``EcheancierContrat`` :
    un montant à régler à une ``date_echeance`` donnée, avec un ``statut`` LOCAL
    (``a_venir`` → ``payee`` / ``en_retard`` / ``annulee``). La date de
    règlement effectif (``date_paiement``) est posée côté serveur lors du
    pointage de paiement.

    Numérotation par échéancier : ``numero`` démarre à 1 et s'incrémente de 1
    pour chaque nouvelle ligne d'un MÊME échéancier. Le numéro est posé CÔTÉ
    SERVEUR par ``services.ajouter_ligne_echeance`` qui calcule ``max(numero)+1``
    SOUS ``select_for_update`` (verrou de ligne sur l'échéancier) — JAMAIS un
    ``count()+1`` (qui collisionne, cf. la règle de numérotation du repo).

    Le ``statut`` est PROPRE à la ligne : il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2), et le
    pointage de paiement n'émet aucune facture.

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite de l'échéancier).
    ``echeancier`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné (≤200) ; la contrainte
    d'unicité ``(echeancier, numero)`` et l'index sont NOMMÉS explicitement
    (≤30 chars).
    """

    class Statut(models.TextChoices):
        A_VENIR = 'a_venir', 'À venir'
        PAYEE = 'payee', 'Payée'
        EN_RETARD = 'en_retard', 'En retard'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_lignes_echeance',
        verbose_name='Société',
    )
    echeancier = models.ForeignKey(
        EcheancierContrat,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Échéancier',
    )
    # Numéro de ligne (1, 2, 3…) par échéancier, posé côté serveur (max+1 sous
    # verrou de ligne — jamais count()+1).
    numero = models.PositiveIntegerField(verbose_name="Numéro d'échéance")
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    date_echeance = models.DateField(verbose_name="Date d'échéance")
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.A_VENIR, verbose_name='Statut')
    # Date de règlement effectif (posée côté serveur au pointage). NULL tant que
    # non payée.
    date_paiement = models.DateField(
        null=True, blank=True, verbose_name='Payée le')
    # CONTRAT31 — lien LÂCHE vers la Facture (``ventes.Facture``) émise pour
    # cette échéance par la facturation récurrente : l'ID seul, jamais un FK dur
    # ni un import de ``ventes.models``. NULL = aucune facture émise. Sert aussi
    # de GARDE D'IDEMPOTENCE (on ne facture pas deux fois la même échéance).
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la facture émise')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Ligne d\'échéance'
        verbose_name_plural = 'Lignes d\'échéance'
        ordering = ['echeancier_id', 'numero', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['echeancier', 'numero'],
                name='contrats_ligneech_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'statut', 'date_echeance'],
                name='contrats_ligneech_co_st',
            ),
        ]

    def __str__(self):
        return (
            f'Échéance n°{self.numero} ({self.montant}, '
            f'{self.date_echeance}) — échéancier {self.echeancier_id}'
        )


class IndexationPrix(models.Model):
    """Indexation / révision de prix d'un contrat — CONTRAT32.

    Une ``IndexationPrix`` déclare une RÈGLE DE RÉVISION du prix d'un ``Contrat``
    par INDICE : un indice de référence nommé (``indice``, ex. « Index BTP »,
    « IPC »), sa valeur de BASE au moment de la signature (``valeur_base``) et,
    optionnellement, une part FIXE non révisable (``part_fixe``, en fraction
    [0–1] de la formule). La révision applique la formule type :

        prix_revisé = prix_base × (part_fixe + (1 − part_fixe) × valeur_actuelle
                                   / valeur_base)

    Quand ``part_fixe = 0`` cela revient à une simple proportion
    ``valeur_actuelle / valeur_base``.

    Le calcul (``services.calculer_prix_indexe``) est PUREMENT DÉCLARATIF : il
    renvoie un prix révisé indicatif et n'écrit RIEN. L'APPLICATION d'une révision
    (``services.appliquer_indexation``) passe par un AVENANT (CONTRAT24) qui ajuste
    le ``Contrat.montant`` via ``creer_avenant`` (delta = prix_revisé − montant
    actuel) — le ``Contrat.statut`` n'est JAMAIS modifié (CONTRAT12) et aucun
    funnel ``STAGES.py`` n'intervient (rule #2).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` / ``indice`` bornés ; les valeurs
    sont des ``DecimalField`` bornés. ``date_derniere_revision`` trace la dernière
    application. L'index est NOMMÉ explicitement (≤30 chars).
    """

    class Periodicite(models.TextChoices):
        ANNUELLE = 'annuelle', 'Annuelle'
        SEMESTRIELLE = 'semestrielle', 'Semestrielle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        A_LA_DEMANDE = 'a_la_demande', 'À la demande'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_indexations',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='indexations',
        verbose_name='Contrat',
    )
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    # Nom de l'indice de référence (libre, ex. « Index BTP-01 », « IPC »).
    indice = models.CharField(max_length=100, verbose_name='Indice de référence')
    # Valeur de l'indice à la base (signature). Doit être strictement > 0 pour
    # un calcul de proportion valide.
    valeur_base = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0'),
        verbose_name='Valeur de base')
    # Part FIXE non révisable de la formule (fraction [0,1]). 0 = entièrement
    # révisable.
    part_fixe = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0'),
        verbose_name='Part fixe (0–1)')
    periodicite = models.CharField(
        max_length=20, choices=Periodicite.choices,
        default=Periodicite.ANNUELLE, verbose_name='Périodicité de révision')
    # Trace de la dernière révision effectivement appliquée (posée côté serveur
    # par ``appliquer_indexation``). NULL = jamais appliquée.
    date_derniere_revision = models.DateField(
        null=True, blank=True, verbose_name='Dernière révision le')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Indexation de prix'
        verbose_name_plural = 'Indexations de prix'
        ordering = ['contrat_id', '-id']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='contrats_idx_co_act',
            ),
        ]

    def __str__(self):
        return f'Indexation {self.indice} — contrat {self.contrat_id}'

    def clean(self):
        """Valide la cohérence des paramètres de la formule.

        ``valeur_base`` doit être strictement positive (dénominateur) et
        ``part_fixe`` doit rester dans [0, 1].
        """
        if self.valeur_base is not None and self.valeur_base <= 0:
            raise ValidationError(
                'La valeur de base doit être strictement positive.')
        if self.part_fixe is not None and not (
                Decimal('0') <= self.part_fixe <= Decimal('1')):
            raise ValidationError(
                'La part fixe doit être comprise entre 0 et 1.')

    def calculer_prix_indexe(self, *, valeur_actuelle, prix_base=None):
        """Prix révisé pour une ``valeur_actuelle`` d'indice (lecture seule).

        ``prix_base`` par défaut = ``self.contrat.montant``. Applique la formule
        ``prix_base × (part_fixe + (1 − part_fixe) × valeur_actuelle /
        valeur_base)`` et arrondit à 2 décimales. Ne crée AUCUNE écriture.
        """
        if self.valeur_base is None or self.valeur_base <= 0:
            raise ValueError('Valeur de base invalide pour l\'indexation.')
        if prix_base is None:
            prix_base = self.contrat.montant or Decimal('0')
        prix_base = Decimal(str(prix_base))
        valeur_actuelle = Decimal(str(valeur_actuelle))
        part_fixe = self.part_fixe or Decimal('0')
        coef = (part_fixe
                + (Decimal('1') - part_fixe)
                * valeur_actuelle / self.valeur_base)
        return (prix_base * coef).quantize(Decimal('0.01'))


class PieceConformite(models.Model):
    """Pièce de conformité / attestation obligatoire d'un contrat — CONTRAT34.

    Une ``PieceConformite`` recense une PIÈCE JUSTIFICATIVE attendue sur un
    ``Contrat`` (attestation d'assurance RC/décennale, attestation fiscale, RIB,
    KYC, certificat de conformité ONEE, PV de réception…). Elle porte un
    ``type_piece``, un ``libelle``, un drapeau ``obligatoire`` et un ``statut``
    LOCAL de complétude (``manquante`` → ``fournie`` → ``validee`` /
    ``expiree`` / ``refusee``). La pièce déposée peut être reliée LÂCHEMENT à un
    document GED par son id (``ged_document_id`` — id seul, jamais un FK dur ni
    un import de ``ged.models``).

    Le ``statut`` est PROPRE au suivi de conformité : il ne touche JAMAIS le
    ``Contrat.statut`` (CONTRAT12) ni le funnel ``STAGES.py`` (rule #2).

    Multi-tenant : ``company`` est posée CÔTÉ SERVEUR (déduite du contrat).
    ``contrat`` est une référence interne à l'app `contrats` (FK dur autorisé).

    RUNTIME-SAFETY (leçon FG136) : ``libelle`` borné (≤200) et ``note`` un
    ``TextField`` ; les index sont NOMMÉS explicitement (≤30 chars).
    """

    class TypePiece(models.TextChoices):
        ASSURANCE = 'assurance', 'Attestation d\'assurance'
        FISCALE = 'fiscale', 'Attestation fiscale'
        RIB = 'rib', 'RIB'
        KYC = 'kyc', 'Pièce KYC / identité'
        CERTIFICAT = 'certificat', 'Certificat de conformité'
        PV_RECEPTION = 'pv_reception', 'PV de réception'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        MANQUANTE = 'manquante', 'Manquante'
        FOURNIE = 'fournie', 'Fournie'
        VALIDEE = 'validee', 'Validée'
        EXPIREE = 'expiree', 'Expirée'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_pieces_conformite',
        verbose_name='Société',
    )
    contrat = models.ForeignKey(
        Contrat,
        on_delete=models.CASCADE,
        related_name='pieces_conformite',
        verbose_name='Contrat',
    )
    type_piece = models.CharField(
        max_length=20, choices=TypePiece.choices,
        default=TypePiece.AUTRE, verbose_name='Type de pièce')
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    obligatoire = models.BooleanField(
        default=True, verbose_name='Obligatoire')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.MANQUANTE, verbose_name='Statut')
    # Lien LÂCHE vers un document GED (id seul) — jamais un FK dur ni un import
    # de ``ged.models``. NULL = aucune pièce déposée en GED.
    ged_document_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du document GED')
    # Date de fourniture effective (posée côté serveur). NULL tant que non fournie.
    date_fourniture = models.DateField(
        null=True, blank=True, verbose_name='Fournie le')
    # Date d'expiration de la pièce (ex. attestation annuelle). NULL = sans date.
    date_expiration = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Pièce de conformité'
        verbose_name_plural = 'Pièces de conformité'
        ordering = ['contrat_id', 'id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_piece_co_st',
            ),
            models.Index(
                fields=['contrat', 'obligatoire'],
                name='contrats_piece_ct_obl',
            ),
        ]

    def __str__(self):
        return (
            f'{self.libelle} ({self.get_statut_display()}) '
            f'— contrat {self.contrat_id}'
        )


class CycleFacturationLog(models.Model):
    """Journal d'un run de facturation récurrente + file d'exceptions — XCTR5.

    Chaque tentative de facturation d'une période récurrente (contrats
    ``EcheancierContrat``/``LigneEcheance`` — CONTRAT31 — OU ``sav.ContratMaintenance``
    — FG40) écrit UNE ligne ici : générée, échouée (avec motif) ou sautée (aucune
    lecture d'usage disponible, etc.). Le SOURCE contrat est référencé en lien
    LÂCHE par un couple typé ``(source_type, source_id)`` — jamais un FK dur ni un
    import du modèle de l'app source (``sav`` n'expose pas de modèle importable
    depuis ``contrats`` — frontière cross-app, CLAUDE.md).

    ``periode`` identifie la PÉRIODE facturée (ex. ``2026-07`` pour un cycle
    mensuel, ou une date ISO pour une échéance datée) — sert de GARDE ANTI
    DOUBLE-FACTURATION : ``services.enregistrer_cycle`` refuse une seconde entrée
    ``genere`` pour le même ``(source_type, source_id, periode)``.

    ``rejouer`` (service) ne re-tente qu'une entrée ``echec`` — EXACTEMENT une
    fois avec succès (elle passe alors à ``genere`` et ne peut plus être
    rejouée deux fois pour la même période, la garde anti-doublon l'en empêche).

    Multi-tenant : ``company`` posée CÔTÉ SERVEUR par le service appelant (jamais
    lue du corps de requête).

    RUNTIME-SAFETY (leçon FG136) : ``motif`` est un ``TextField`` (le message
    d'erreur d'une facturation ratée peut être long) ; ``periode``/``source_type``
    sont des ``CharField`` bornés. L'index est NOMMÉ explicitement (≤30 chars).
    """

    class SourceType(models.TextChoices):
        CONTRAT = 'contrat', 'Contrat (échéancier)'
        SAV_MAINTENANCE = 'sav_maintenance', 'Maintenance SAV'
        # XCTR20 — cycle de facturation récurrente d'un OrdreLocation longue
        # durée. Choix additif (CharField, aucune migration de schéma requise).
        ORDRE_LOCATION = 'ordre_location', 'Location longue durée'

    class Statut(models.TextChoices):
        GENERE = 'genere', 'Générée'
        ECHEC = 'echec', 'Échec'
        SAUTE = 'saute', 'Sautée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_cycles_facturation',
        verbose_name='Société',
    )
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices,
        verbose_name='Type de source')
    # ID de la source (contrat ou ContratMaintenance SAV) — lien LÂCHE, jamais
    # de FK dur ni d'import cross-app.
    source_id = models.PositiveIntegerField(verbose_name='ID de la source')
    # Période facturée (ex. « 2026-07 » mensuel, ou une date ISO). Sert de clé
    # de garde anti double-facturation avec (source_type, source_id).
    periode = models.CharField(max_length=20, verbose_name='Période')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, verbose_name='Statut')
    motif = models.TextField(
        blank=True, default='', verbose_name='Motif (échec/saut)')
    # Lien LÂCHE vers la facture émise (ventes.Facture) — id seul, NULL si non
    # générée.
    facture_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la facture émise')
    # Nombre de tentatives (1 à la création ; incrémenté par ``rejouer``).
    nb_tentatives = models.PositiveIntegerField(
        default=1, verbose_name='Nombre de tentatives')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Journal de cycle de facturation'
        verbose_name_plural = 'Journaux de cycles de facturation'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_cyclelog_co_st',
            ),
            models.Index(
                fields=['source_type', 'source_id', 'periode'],
                name='contrats_cyclelog_src_per',
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_source_type_display()} #{self.source_id} '
            f'— {self.periode} ({self.get_statut_display()})'
        )


# ---------------------------------------------------------------------------
# XCTR17 — Location de matériel SORTANTE (aux clients) — fondation
# ---------------------------------------------------------------------------


class OrdreLocation(models.Model):
    """Ordre de location de matériel À UN CLIENT (XCTR17) — location SORTANTE.

    Distinct de FG342 (location ENTRANTE / allocation interne d'engins) : ici
    la société LOUE un ``stock.Produit`` marqué ``louable`` (groupe
    électrogène, pompe, nacelle…) à un client. Le client est référencé en lien
    LÂCHE par ``client_id`` (jamais un import de ``crm.Client``) et le produit
    par FK DUR (``stock`` est une app cœur métier lue via son sélecteur
    ``get_produit_louable`` à la création — jamais son modèle importé côté
    vue — mais le FK lui-même reste nécessaire pour les jointures/rapports
    internes à ``contrats``, comme le fait déjà tout le reste du module pour
    ses propres références).

    Machine d'états LOCALE (jamais confondue avec ``Contrat.statut`` ni le
    funnel ``STAGES.py`` — rule #2) : ``reservee`` → ``enlevee`` → ``retournee``
    → ``cloturee``, ou ``reservee``/``enlevee`` → ``annulee``. Les transitions
    sont gardées par ``machine_etats.py`` (même patron que ``Contrat``).

    DÉTECTION DE CONFLIT : deux ordres ACTIFS (non annulés/clôturés) sur le
    MÊME produit + même ``numero_serie`` dont les fenêtres
    ``[date_enlevement_prevue, date_retour_prevue]`` se chevauchent sont
    refusés (400) — voir ``services.creer_ordre_location``.
    """

    class Statut(models.TextChoices):
        RESERVEE = 'reservee', 'Réservée'
        ENLEVEE = 'enlevee', 'Enlevée'
        RETOURNEE = 'retournee', 'Retournée'
        CLOTUREE = 'cloturee', 'Clôturée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ordres_location',
        verbose_name='Société',
    )
    # Client locataire — lien LÂCHE (jamais un import de crm.Client).
    client_id = models.PositiveIntegerField(verbose_name='ID du client')
    # ZCTR6 — devis d'ORIGINE (``ventes.Devis``), lien LÂCHE (id seul, jamais
    # un import de ``ventes.models`` ni un FK dur). NULL = ordre créé
    # manuellement (comportement XCTR17 inchangé). ``ContratLien`` exige un
    # ``Contrat`` (FK dur) qui n'existe pas dans ce flux devis→location pur —
    # ce champ sert de GARDE ANTI-DOUBLON pour
    # ``services.creer_ordres_location_depuis_devis`` (un re-run sur le même
    # devis ne duplique jamais un ordre déjà créé pour la même ligne).
    devis_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du devis d\'origine')
    # ZCTR6 — ligne du devis d'origine (id seul, même lien lâche que
    # ``devis_id``) : distingue plusieurs lignes louables d'un même devis.
    devis_ligne_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID de la ligne devis d\'origine')
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name='ordres_location',
        verbose_name='Produit loué',
    )
    numero_serie = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='N° de série / unité')
    date_reservation = models.DateField(
        verbose_name='Date de réservation')
    date_enlevement_prevue = models.DateField(
        verbose_name="Date d'enlèvement prévue")
    date_retour_prevue = models.DateField(
        verbose_name='Date de retour prévue')
    date_enlevement_reelle = models.DateField(
        null=True, blank=True, verbose_name="Date d'enlèvement réelle")
    date_retour_reelle = models.DateField(
        null=True, blank=True, verbose_name='Date de retour réelle')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.RESERVEE, verbose_name='Statut')
    tarif_jour = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Tarif journalier appliqué')
    montant_estime = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant estimé')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ordres_location_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    # Statuts considérés ACTIFS pour la détection de chevauchement (une
    # réservation/enlèvement en cours bloque une fenêtre qui la chevauche ;
    # une location déjà clôturée/annulée ne bloque plus rien).
    STATUTS_ACTIFS = (Statut.RESERVEE, Statut.ENLEVEE)

    class CautionStatut(models.TextChoices):
        """XCTR18 — cycle de vie de la caution/dépôt de garantie de l'ordre.

        LOCAL à l'ordre de location : ne touche JAMAIS ``Contrat.statut`` ni
        le funnel ``STAGES.py`` (rule #2). ``AUCUNE`` = aucune caution
        demandée (comportement par défaut, inchangé)."""
        AUCUNE = 'aucune', 'Aucune'
        ENCAISSEE = 'encaissee', 'Encaissée'
        RESTITUEE = 'restituee', 'Restituée'
        RETENUE_PARTIELLE = 'retenue_partielle', 'Retenue partielle'

    # ── XCTR18 — Caution (dépôt de garantie) sur location ───────────────────
    caution_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant de la caution')
    caution_statut = models.CharField(
        max_length=20, choices=CautionStatut.choices,
        default=CautionStatut.AUCUNE, verbose_name='Statut de la caution')
    caution_retenue = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant retenu sur la caution')
    caution_motif_retenue = models.TextField(
        blank=True, default='', verbose_name='Motif de la retenue')

    # ── XCTR19 — Retour de location : retards, frais, inspection ────────────
    # Frais de retard par jour, configurable PAR ordre. NULL = aucun frais de
    # retard appliqué (comportement inchangé).
    frais_retard_jour = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Frais de retard / jour')
    # Montant de frais de retard EFFECTIVEMENT facturé à la clôture — posé
    # côté serveur, NULL tant qu'aucune clôture en retard n'a eu lieu.
    frais_retard_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Frais de retard facturés')
    frais_retard_facture_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID de la facture (frais de retard)')
    # Checklist d'inspection de retour (JSON libre : {"item": "ok"/"endommage",
    # ...}) + relevé compteur (heures moteur, km…). Vide/NULL tant que le
    # matériel n'est pas encore inspecté.
    inspection_checklist = models.JSONField(
        null=True, blank=True, verbose_name="Checklist d'inspection")
    inspection_releve_compteur = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Relevé compteur')
    inspection_dommages_montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant des dommages chiffrés')
    inspection_facture_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID de la facture (dommages)')
    inspection_ticket_sav_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID du ticket SAV de remise en état')
    inspection_date = models.DateTimeField(
        null=True, blank=True, verbose_name="Date de l'inspection")

    # ── XCTR20 — Location longue durée : facturation récurrente ─────────────
    class CyclePeriodicite(models.TextChoices):
        MENSUELLE = 'mensuelle', 'Mensuelle'

    class CycleMoment(models.TextChoices):
        AVANCE = 'avance', "D'avance"
        ECHU = 'echu', 'À terme échu'

    # False par défaut : un ordre reste facturé UNE fois (montant_estime, à la
    # clôture) tant que ce drapeau n'est pas explicitement activé —
    # comportement XCTR17/18/19 inchangé.
    facturation_recurrente_active = models.BooleanField(
        default=False, verbose_name='Facturation récurrente active')
    facturation_periodicite = models.CharField(
        max_length=20, choices=CyclePeriodicite.choices,
        default=CyclePeriodicite.MENSUELLE, verbose_name='Périodicité')
    facturation_moment = models.CharField(
        max_length=10, choices=CycleMoment.choices,
        default=CycleMoment.AVANCE, verbose_name='Facturé')
    derniere_facturation = models.DateField(
        null=True, blank=True, verbose_name='Dernière facturation')

    class Meta:
        verbose_name = 'Ordre de location'
        verbose_name_plural = 'Ordres de location'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut'],
                name='contrats_ordloc_co_st',
            ),
            models.Index(
                fields=['produit', 'numero_serie'],
                name='contrats_ordloc_prod_serie',
            ),
            # ZCTR6 — garde anti-doublon rapide (devis, ligne) → ordre créé.
            models.Index(
                fields=['devis_id', 'devis_ligne_id'],
                name='contrats_ordloc_devis_ligne',
            ),
        ]

    def __str__(self):
        return (
            f'Location {self.produit_id} ({self.numero_serie or "—"}) '
            f'— {self.get_statut_display()}'
        )

    def chevauche(self, autre_debut, autre_fin):
        """``True`` si la fenêtre ``[autre_debut, autre_fin]`` chevauche la
        fenêtre d'enlèvement/retour PRÉVUE de cet ordre (bornes incluses)."""
        return (
            self.date_enlevement_prevue <= autre_fin
            and autre_debut <= self.date_retour_prevue
        )

    def est_en_retard(self, today=None):
        """``True`` si l'ordre est ENLEVÉ et que le retour prévu est dépassé
        SANS retour effectif — XCTR19. ``today`` injectable pour les tests."""
        if self.statut != OrdreLocation.Statut.ENLEVEE:
            return False
        if today is None:
            today = timezone.localdate()
        return today > self.date_retour_prevue

    def jours_de_retard(self, today=None):
        """Nombre de jours de retard (0 si pas en retard) — XCTR19."""
        if not self.est_en_retard(today=today):
            return 0
        if today is None:
            today = timezone.localdate()
        return (today - self.date_retour_prevue).days

    def prochaine_facturation(self):
        """Date du prochain cycle de facturation récurrente — XCTR20.

        Basée sur ``derniere_facturation`` (si posée) ou
        ``date_enlevement_prevue``, avancée d'un mois (seule périodicité
        supportée aujourd'hui — ``CyclePeriodicite.MENSUELLE``)."""
        base = self.derniere_facturation or self.date_enlevement_prevue
        return Contrat.ajouter_mois(base, 1)

    def facturation_recurrente_due(self, today=None):
        """``True`` si la facturation récurrente est active et due — XCTR20."""
        if not self.facturation_recurrente_active:
            return False
        if today is None:
            today = timezone.localdate()
        return today >= self.prochaine_facturation()


class CautionLocationLog(models.Model):
    """Journal (chatter) des transitions de caution d'un ``OrdreLocation`` —
    XCTR18.

    ``OrdreLocation`` n'est PAS un ``Contrat`` (pas de FK vers ``Contrat``,
    voir docstring de ``OrdreLocation``) — ce journal dédié rejoue le même
    patron que ``ContratActivity`` (CONTRAT15) sans dépendre de son FK requis.
    Une entrée par transition de ``caution_statut`` : ancien → nouveau statut,
    montant concerné et motif éventuel. Société posée CÔTÉ SERVEUR.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats_caution_location_logs',
        verbose_name='Société',
    )
    ordre_location = models.ForeignKey(
        OrdreLocation,
        on_delete=models.CASCADE,
        related_name='caution_logs',
        verbose_name='Ordre de location',
    )
    ancien_statut = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Ancien statut')
    nouveau_statut = models.CharField(
        max_length=20, verbose_name='Nouveau statut')
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Montant concerné')
    motif = models.TextField(blank=True, default='', verbose_name='Motif')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='caution_location_logs',
        verbose_name='Auteur',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Journal de caution (location)'
        verbose_name_plural = 'Journaux de caution (location)'
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return (
            f'Caution ordre #{self.ordre_location_id} : '
            f'{self.ancien_statut} → {self.nouveau_statut}'
        )


class PlanRecurrent(models.Model):
    """Plan de facturation récurrente réutilisable (nommé) — ZCTR1.

    Odoo Subscriptions définit des « Recurring Plans » nommés (période, délai
    de clôture auto, alignement début-de-période) réutilisables sur tout
    contrat ; ici la périodicité était jusqu'ici un enum figé recopié cas par
    cas (``ContratMaintenance.periodicite``, ``EcheancierContrat.periodicite``).
    Un ``PlanRecurrent`` centralise ces réglages et peut être RATTACHÉ (FK
    nullable) à un ``Contrat`` ou (via id + sélecteur, jamais un import
    cross-app) à un ``sav.ContratMaintenance`` : la lecture reste RÉTROCOMPATIBLE
    — un contrat SANS plan rattaché conserve exactement son comportement actuel
    (enum de périodicité local).

    Multi-tenant : ``company`` posée CÔTÉ SERVEUR, jamais lue du corps de
    requête (perform_create du ``TenantMixin``).

    RUNTIME-SAFETY (leçon FG136) : ``nom`` borné (≤120).
    """

    class Unite(models.TextChoices):
        MENSUEL = 'mensuel', 'Mensuel'
        TRIMESTRIEL = 'trimestriel', 'Trimestriel'
        SEMESTRIEL = 'semestriel', 'Semestriel'
        ANNUEL = 'annuel', 'Annuel'

    # Nombre de mois PAR PAS de l'unité (avant application de ``intervalle``).
    MOIS_PAR_UNITE = {
        Unite.MENSUEL: 1,
        Unite.TRIMESTRIEL: 3,
        Unite.SEMESTRIEL: 6,
        Unite.ANNUEL: 12,
    }

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='plans_recurrents',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=120, verbose_name='Nom')
    unite = models.CharField(
        max_length=15, choices=Unite.choices, default=Unite.MENSUEL,
        verbose_name='Unité')
    # Multiplicateur de l'unité (ex. unite=mensuel + intervalle=2 → tous les
    # 2 mois). Toujours ≥ 1.
    intervalle = models.PositiveIntegerField(
        default=1, verbose_name='Intervalle')
    # Délai (jours) après lequel un cycle impayé déclenche la clôture
    # automatique (ZCTR2). NULL = jamais de clôture auto.
    delai_cloture_auto_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Délai de clôture auto (jours)')
    # Aligne le premier cycle sur le DÉBUT de la période calendaire (ex. le
    # 1er du trimestre) plutôt que sur la date de signature/activation brute.
    aligner_debut_periode = models.BooleanField(
        default=False, verbose_name='Aligner sur le début de période')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Plan de facturation récurrente'
        verbose_name_plural = 'Plans de facturation récurrente'
        ordering = ['nom', 'id']
        indexes = [
            models.Index(
                fields=['company', 'actif'],
                name='contrats_planrec_co_act',
            ),
        ]

    def __str__(self):
        return f'{self.nom} ({self.get_unite_display()})'

    def mois_par_cycle(self):
        """Nombre de mois d'un cycle complet (``unite`` × ``intervalle``)."""
        return self.MOIS_PAR_UNITE.get(self.unite, 1) * max(1, self.intervalle)

    def debut_periode_alignee(self, date_reference):
        """Renvoie ``date_reference`` alignée sur le début de sa période.

        Sans alignement (``aligner_debut_periode=False``), renvoie
        ``date_reference`` inchangée. Avec alignement : ramène au 1er du mois
        pour une unité mensuelle, ou au 1er du bloc trimestriel/semestriel/
        annuel civil couvrant ``date_reference``.
        """
        if not self.aligner_debut_periode:
            return date_reference
        mois_par_unite = self.MOIS_PAR_UNITE.get(self.unite, 1)
        mois_index = date_reference.month - 1
        mois_bloc_debut = (mois_index // mois_par_unite) * mois_par_unite
        return date_reference.replace(month=mois_bloc_debut + 1, day=1)


class ParametresLocation(models.Model):
    """Réglages de location, singleton par société — ZCTR4.

    Odoo Rental Settings porte « minimal rental duration », « default
    padding time » (buffer d'indisponibilité entre deux locations d'une même
    unité pour l'entretien) et « default delay costs ». XCTR17 détecte le
    chevauchement STRICT (``OrdreLocation.chevauche``) mais ignore le
    padding et n'a aucun défaut de frais/durée.

    - ``duree_minimale_jours`` (NULL = aucun minimum) : la CRÉATION d'un
      ``OrdreLocation`` plus court que ce minimum est refusée (400 FR).
    - ``temps_securite_heures`` (défaut 0 = comportement XCTR17 inchangé) :
      élargit de part et d'autre la fenêtre occupée utilisée par la
      détection de conflit (``_verifier_disponibilite``) — deux locations
      trop rapprochées (temps d'entretien insuffisant) sont refusées.
    - ``frais_retard_jour_defaut`` (NULL = aucun défaut) : un ``OrdreLocation``
      dont ``frais_retard_jour`` n'est PAS saisi hérite de ce défaut à la
      création (XCTR19 s'applique ensuite sans changement).

    Toutes les valeurs NULL/0 laissent le comportement XCTR17/19 inchangé —
    ``ParametresLocation`` est entièrement OPTIONNEL (une société sans ligne
    créée se comporte exactement comme avant ZCTR4).

    Multi-tenant : ``company`` posée CÔTÉ SERVEUR (``OneToOneField``, une
    seule ligne par société — singleton).
    """

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='parametres_location',
        verbose_name='Société',
    )
    duree_minimale_jours = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Durée minimale (jours)')
    temps_securite_heures = models.PositiveIntegerField(
        default=0, verbose_name='Temps de sécurité / padding (heures)')
    frais_retard_jour_defaut = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Frais de retard / jour par défaut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Paramètres de location'
        verbose_name_plural = 'Paramètres de location'

    def __str__(self):
        return f'Paramètres de location — {self.company_id}'


# ---------------------------------------------------------------------------
# NTSUB1-4 — Revenus récurrents : catalogue d'offres, add-ons, paliers d'usage,
# compteurs génériques (fondation d'un moteur SaaS billing — bench Zuora/
# Chargebee « Product Catalog »).
#
# Ces quatre modèles héritent de ``core.models.TenantModel`` (FK ``company`` +
# horodatage, ARC1/SCA4) — contrairement aux modèles PRÉ-EXISTANTS de ce
# fichier (baseline gelée), tout NOUVEAU modèle de ce groupe suit le socle.
# ---------------------------------------------------------------------------


class PlanAbonnement(TenantModel):
    """Catalogue d'offres commerciales (« Product Catalog » Zuora/Chargebee) — NTSUB1.

    Distinct de ``PlanRecurrent`` (ZCTR1, réglages de CADENCE réutilisables —
    unité/intervalle/clôture auto — jamais un prix ni une offre vendable) et du
    ``Contrat.montant``/``ContratMaintenance.prix`` (saisis à la main à chaque
    contrat). Un ``PlanAbonnement`` est une OFFRE VENDABLE réutilisable : un
    ``code``/``nom``/``description`` commerciaux, un ``prix_base`` (MAD), un
    ``engagement_mois`` optionnel, et la CADENCE de facturation via ``plan_recurrent``
    (référence au socle ZCTR1 existant — jamais une nouvelle notion de
    périodicité).

    ``Contrat.plan_abonnement`` (FK nullable, NULL = comportement actuel
    inchangé) peut RÉFÉRENCER une offre : ``services.appliquer_plan_abonnement``
    PRÉ-REMPLIT alors ``montant``/``plan_recurrent`` du contrat en SNAPSHOT (copie
    ponctuelle à la création) — le contrat garde ensuite ses valeurs PROPRES,
    éditables librement, et modifier l'offre après coup ne touche JAMAIS un
    contrat déjà créé.

    **Note de nommage (ne pas confondre)** : ``contrats.PlanAbonnement`` désigne
    une offre commerciale VENDUE PAR LE TENANT à SES clients (maintenance,
    monitoring, location) — un concept TOTALEMENT DIFFÉRENT des plans de
    LICENCE de l'ERP lui-même (souscription au logiciel, tenant/modules/
    sièges) qui vivent dans ``adminops.PlanLicence`` (NTADM7, renommé
    précisément pour éviter cette collision). Aucune relation entre les deux
    modèles.

    Multi-tenant : ``company`` héritée de ``TenantModel``, posée CÔTÉ SERVEUR
    (``TenantMixin.perform_create`` — jamais lue du corps de requête).

    RUNTIME-SAFETY (leçon FG136) : ``code``/``nom`` bornés ; ``description`` en
    ``TextField`` (jamais de longueur maximale à dépasser) ; contrainte d'unicité
    et index NOMMÉS explicitement (≤30 chars).
    """

    code = models.CharField(max_length=50, verbose_name='Code')
    nom = models.CharField(max_length=120, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # Cadence de facturation réutilisée (ZCTR1) — jamais une nouvelle notion de
    # périodicité créée ici. PROTECT : un plan de facturation récurrente encore
    # référencé par au moins une offre du catalogue ne peut pas être supprimé
    # silencieusement (il faudrait d'abord réaffecter/désactiver l'offre).
    plan_recurrent = models.ForeignKey(
        'PlanRecurrent',
        on_delete=models.PROTECT,
        related_name='plans_abonnement',
        verbose_name='Plan de facturation récurrente',
    )
    prix_base = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Prix de base')
    engagement_mois = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Engagement (mois)')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='contrats_planabo_uniq_code'),
        ]
        indexes = [
            models.Index(
                fields=['company', 'actif'], name='contrats_planabo_co_act'),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'


class AddOnAbonnement(TenantModel):
    """Option payante (add-on) du catalogue, attachable à un abonnement — NTSUB2.

    Ex. « supervision avancée », « visite supplémentaire ». Rattachable
    optionnellement à un ``PlanAbonnement`` du catalogue (``plan_abonnement``
    nullable — un add-on peut aussi être générique, proposé sur plusieurs
    plans) ; ``facturation`` distingue un add-on RÉCURRENT (facturé à chaque
    cycle tant qu'actif) d'un add-on PONCTUEL (facturé une seule fois à
    l'activation — non branché ici, réservé à un futur point d'entrée manuel).

    Multi-tenant : ``company`` héritée de ``TenantModel``, posée CÔTÉ SERVEUR.
    """

    class Facturation(models.TextChoices):
        RECURRENTE = 'recurrente', 'Récurrente'
        PONCTUELLE = 'ponctuelle', 'Ponctuelle'

    plan_abonnement = models.ForeignKey(
        'PlanAbonnement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='addons',
        verbose_name="Plan d'abonnement",
    )
    code = models.CharField(max_length=50, verbose_name='Code')
    nom = models.CharField(max_length=120, verbose_name='Nom')
    prix_unitaire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Prix unitaire')
    facturation = models.CharField(
        max_length=15, choices=Facturation.choices,
        default=Facturation.RECURRENTE, verbose_name='Facturation')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = "Add-on d'abonnement"
        verbose_name_plural = "Add-ons d'abonnement"
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='contrats_addon_uniq_code'),
        ]

    def __str__(self):
        return f'{self.code} — {self.nom}'


class AbonnementAddOnLigne(TenantModel):
    """Rattachement d'un add-on à un ``Contrat`` ou ``sav.ContratMaintenance`` — NTSUB2.

    Lien LÂCHE polymorphe par couple typé ``(type_cible, cible_id)`` — même
    patron que ``CycleFacturationLog.source_type/source_id`` (XCTR5) : jamais
    un FK dur ni un import du modèle d'une autre app (``sav`` n'expose pas de
    modèle importable depuis ``contrats`` — frontière cross-app, CLAUDE.md).

    ``actif_depuis``/``actif_jusqua`` bornent la période de facturation : un
    add-on actif à la date du cycle de facturation ajoute son montant à la
    facture générée (``services.montant_addons_periode``) ; désactivé
    (``actif_jusqua`` dépassée) il n'est plus facturé au cycle suivant.

    Multi-tenant : ``company`` héritée de ``TenantModel``, posée CÔTÉ SERVEUR.
    """

    class TypeCible(models.TextChoices):
        CONTRAT = 'contrat', 'Contrat'
        SAV_MAINTENANCE = 'sav_maintenance', 'Maintenance SAV'

    type_cible = models.CharField(
        max_length=20, choices=TypeCible.choices, verbose_name='Type de cible')
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    addon = models.ForeignKey(
        'AddOnAbonnement',
        on_delete=models.CASCADE,  # on_delete: une ligne rattachée à un add-on supprimé n'a plus de sens (pas de facturation orpheline)
        related_name='lignes',
        verbose_name='Add-on',
    )
    quantite = models.PositiveIntegerField(default=1, verbose_name='Quantité')
    actif_depuis = models.DateField(verbose_name='Actif depuis')
    actif_jusqua = models.DateField(
        null=True, blank=True, verbose_name="Actif jusqu'à")

    class Meta:
        verbose_name = "Ligne add-on d'abonnement"
        verbose_name_plural = "Lignes add-on d'abonnement"
        ordering = ['-id']
        indexes = [
            models.Index(
                fields=['company', 'type_cible', 'cible_id'],
                name='contrats_addonlig_cible'),
        ]

    def actif_le(self, date_reference):
        """``True`` si cette ligne est active à ``date_reference`` (bornes incluses)."""
        if self.actif_depuis and date_reference < self.actif_depuis:
            return False
        if self.actif_jusqua and date_reference > self.actif_jusqua:
            return False
        return True

    def montant_periode(self):
        """Montant facturable de cette ligne (``quantite`` × prix unitaire de l'add-on)."""
        return (self.quantite or 0) * (self.addon.prix_unitaire or Decimal('0'))

    def __str__(self):
        return f'{self.addon_id} x{self.quantite} — {self.type_cible} #{self.cible_id}'


class PalierUsage(TenantModel):
    """Palier de prix (tiered/volume pricing) pour la facturation à l'usage — NTSUB3.

    XCTR16 (``apps.sav``) facture l'usage monitoring à un TARIF UNIQUE
    (``tarif_usage`` × unités au-delà de la franchise) — aucun palier
    dégressif/progressif. Un ``PalierUsage`` déclare UNE tranche de tarif,
    rattachée à un ``AddOnAbonnement`` ou un ``PlanAbonnement`` (l'un OU
    l'autre, jamais les deux — un palier qualifie soit un add-on à l'usage
    soit l'offre elle-même) : ``seuil_min``/``seuil_max`` (NULL = infini) et
    ``prix_unitaire`` de la tranche. ``mode`` distingue :

      - ``volume``    : la totalité de l'usage est facturée au tarif du DERNIER
        palier atteint ;
      - ``graduated`` : chaque tranche d'usage est facturée à SON tarif propre
        (cumul des tranches).

    Le calcul PUR (aucune app métier, aucune base) vit dans
    ``core.pricing_paliers.calculer_prix_paliers`` — réutilisé par XCTR16 (sav)
    et NTSUB2/4 (contrats). RÉTROCOMPATIBLE : sans palier configuré, un appelant
    retombe sur son tarif unique existant (comportement XCTR16 inchangé).

    ``seuil_alerte_pct`` (NTSUB18, non branché ici) : seuil optionnel
    d'alerte de dépassement, laissé pour un futur branchement notifications —
    NULL = aucune alerte.

    Multi-tenant : ``company`` héritée de ``TenantModel``, posée CÔTÉ SERVEUR.
    """

    class Mode(models.TextChoices):
        VOLUME = 'volume', 'Volume (dernier palier atteint)'
        GRADUATED = 'graduated', 'Graduated (par tranche)'

    addon = models.ForeignKey(
        'AddOnAbonnement',
        on_delete=models.CASCADE,  # on_delete: un palier n'a pas de sens sans l'add-on/plan qu'il tarife
        null=True, blank=True,
        related_name='paliers',
        verbose_name='Add-on',
    )
    plan_abonnement = models.ForeignKey(
        'PlanAbonnement',
        on_delete=models.CASCADE,  # on_delete: idem — un palier n'a pas de sens sans l'offre qu'il tarife
        null=True, blank=True,
        related_name='paliers',
        verbose_name="Plan d'abonnement",
    )
    seuil_min = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Seuil minimum')
    seuil_max = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Seuil maximum (NULL = infini)')
    prix_unitaire = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Prix unitaire de la tranche')
    mode = models.CharField(
        max_length=15, choices=Mode.choices, default=Mode.VOLUME,
        verbose_name='Mode')
    seuil_alerte_pct = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Seuil d'alerte (%)")

    class Meta:
        verbose_name = "Palier d'usage"
        verbose_name_plural = "Paliers d'usage"
        ordering = ['seuil_min', 'id']
        indexes = [
            models.Index(
                fields=['company', 'addon'], name='contrats_palier_co_addon'),
            models.Index(
                fields=['company', 'plan_abonnement'],
                name='contrats_palier_co_plan'),
        ]

    def __str__(self):
        borne = self.seuil_max if self.seuil_max is not None else '∞'
        return f'{self.seuil_min}–{borne} @ {self.prix_unitaire}'


class CompteurUsage(TenantModel):
    """Compteur d'usage générique (metering) au-delà du monitoring solaire — NTSUB4.

    XCTR16 lit exclusivement ``monitoring.ProductionReading`` (kWh/m³) — aucun
    mécanisme générique pour d'autres compteurs (interventions SAV consommées
    au-delà du quota, utilisateurs actifs, appels API publicapi…). Lien LÂCHE
    polymorphe par couple typé ``(type_cible, cible_id)`` — même patron que
    ``AbonnementAddOnLigne``/``CycleFacturationLog`` (XCTR5) : jamais un FK dur
    ni un import cross-app.

    ``code_compteur`` est un identifiant LIBRE (texte, choisi par l'appelant —
    ex. ``'interventions'``, ``'appels_api'``) : la lecture/agrégation se fait
    par ``(company, type_cible, cible_id, code_compteur, periode_debut,
    periode_fin)``. Idempotence d'ingestion garantie par une contrainte
    d'unicité sur ce sextuplet — ingérer deux fois le même relevé pour la MÊME
    période ne duplique jamais la ligne (``services.ingerer_compteur_usage``
    fait un update_or_create).

    Multi-tenant : ``company`` héritée de ``TenantModel``, posée CÔTÉ SERVEUR.
    """

    class Source(models.TextChoices):
        MANUEL = 'manuel', 'Manuel'
        API = 'api', 'API'
        CALCULE = 'calcule', 'Calculé'

    type_cible = models.CharField(
        max_length=20,
        choices=AbonnementAddOnLigne.TypeCible.choices,
        verbose_name='Type de cible')
    cible_id = models.PositiveIntegerField(verbose_name='ID de la cible')
    code_compteur = models.CharField(
        max_length=100, verbose_name='Code du compteur')
    periode_debut = models.DateField(verbose_name='Début de période')
    periode_fin = models.DateField(verbose_name='Fin de période')
    quantite = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('0'),
        verbose_name='Quantité')
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANUEL,
        verbose_name='Source')

    class Meta:
        verbose_name = "Compteur d'usage"
        verbose_name_plural = "Compteurs d'usage"
        ordering = ['-periode_debut', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'company', 'type_cible', 'cible_id', 'code_compteur',
                    'periode_debut', 'periode_fin',
                ],
                name='contrats_compteur_uniq_periode',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'type_cible', 'cible_id', 'code_compteur'],
                name='contrats_compteur_co_cible'),
        ]

    def __str__(self):
        return (
            f'{self.code_compteur} {self.type_cible}#{self.cible_id} '
            f'[{self.periode_debut}..{self.periode_fin}] = {self.quantite}'
        )
