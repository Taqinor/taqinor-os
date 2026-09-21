"""Modèles du module « Veille appels d'offres » (``apps.veille_ao``).

Tout modèle ici hérite de ``core.models.TenantModel`` (FK ``company`` +
``created_at``/``updated_at``, ARC1) — jamais une FK ``company`` recodée.

Le couplage vers ``apps.ao`` se fait par **entier opaque**, jamais par FK :
c'est ce qui garde les deux apps découplées (contrat import-linter) et laisse
la chaîne de migrations d'``apps.ao`` mono-écrivain pour le groupe AOF.
"""
from django.db import models
from django.utils import timezone

from core.models import TenantModel


class TypeSource(models.TextChoices):
    """Les 6 couches de la carte des sources (VAO7).

    Elles ne sont PAS interchangeables : le portail officiel est collecté
    automatiquement (sous conditions strictes, règle #5), les portails
    sectoriels et agrégateurs sont des extensions de phase 2, et le tuyau
    partenaire est la SEULE porte qui aurait capté l'avis FRDISI — lequel n'a
    jamais été publié nulle part.
    """

    PORTAIL_OFFICIEL = 'portail_officiel', 'Portail officiel (PMMP)'
    SAISIE_MANUELLE = 'saisie_manuelle', 'Saisie manuelle'
    IMPORT_CSV = 'import_csv', 'Import de fichier'
    PORTAIL_SECTORIEL = 'portail_sectoriel', 'Portail sectoriel (EEP)'
    AGREGATEUR = 'agregateur', 'Agrégateur commercial'
    TUYAU_PARTENAIRE = 'tuyau_partenaire', 'Tuyau partenaire'


#: Les seuls types de source qu'un collecteur automatique peut interroger.
#: Les trois autres (saisie manuelle, import de fichier, tuyau partenaire)
#: sont des portes HUMAINES : elles n'ont aucune URL à lire.
TYPES_COLLECTABLES = frozenset({
    TypeSource.PORTAIL_OFFICIEL,
    TypeSource.PORTAIL_SECTORIEL,
    TypeSource.AGREGATEUR,
})


class SourceVeilleQuerySet(models.QuerySet):
    """Le filtre de collecte vit ICI, pas dans le collecteur.

    Une source désactivée ne doit jamais être interrogée — et la seule façon
    de le garantir est que personne n'ait à s'en souvenir : tout appelant
    passe par ``collectables()``.
    """

    def collectables(self):
        return self.filter(
            actif=True,
            type_source__in=sorted(TYPES_COLLECTABLES),
        ).exclude(url_base='')


class SourceVeille(TenantModel):
    """Le catalogue des sources — **aucune source en dur dans le code**.

    Constat de conception (VAO7) : la carte des sources compte 5 couches et va
    grandir (bons de commande, MASEN, CDG, ADM, Marsa Maroc tournent le MÊME
    logiciel Atexo que le portail officiel). Coder « le portail » en dur
    condamnerait chaque extension à toucher le collecteur ; l'URL de base, la
    cadence et l'interrupteur ``actif`` vivent donc en base.

    ``actif=False`` est un interrupteur d'arrêt réel : une source désactivée
    n'est JAMAIS interrogée (voir ``SourceVeilleQuerySet.collectables``).
    """

    code = models.SlugField(
        'Code', max_length=40,
        help_text="Identifiant stable de la source (ex. « pmmp »).")
    libelle = models.CharField('Libellé', max_length=160)
    type_source = models.CharField(
        'Type de source', max_length=32, choices=TypeSource.choices,
        default=TypeSource.SAISIE_MANUELLE)
    url_base = models.URLField(
        'URL de base', max_length=300, blank=True, default='',
        help_text=(
            "Racine de la source, quand elle en a une. C'est le SEUL endroit "
            "où une URL de portail est écrite — jamais dans le collecteur."))
    actif = models.BooleanField(
        'Active', default=False,
        help_text=(
            "Interrupteur d'arrêt : une source inactive n'est jamais "
            "interrogée ni collectée."))
    cadence_heures = models.PositiveIntegerField(
        'Cadence (heures)', default=24,
        help_text="Délai minimal entre deux collectes de cette source.")
    derniere_collecte_reussie = models.DateTimeField(
        'Dernière collecte réussie', null=True, blank=True)
    notes = models.TextField('Notes', blank=True, default='')

    objects = SourceVeilleQuerySet.as_manager()

    class Meta:
        verbose_name = 'Source de veille'
        verbose_name_plural = 'Sources de veille'
        ordering = ['libelle', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='veille_ao_source_co_code_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='veille_ao_src_co_actif_idx'),
        ]

    def __str__(self):
        return self.libelle

    @property
    def est_collectable_automatiquement(self):
        """Vrai seulement pour les sources qu'un collecteur peut interroger.

        Une saisie manuelle, un import de fichier ou un tuyau partenaire
        n'ont rien à interroger : ce sont des portes d'entrée HUMAINES.
        """
        return (
            self.actif
            and self.type_source in TYPES_COLLECTABLES
            and bool(self.url_base)
        )


class StatutAvis(models.TextChoices):
    """Le cycle de vie d'un avis DANS LE SAS.

    Ces statuts ne sont pas ceux d'un appel d'offres : un avis est un signal
    à trier, pas une affaire. La conversion en ``AppelOffre`` est un acte
    HUMAIN (statut ``converti``), jamais un effet de bord de la collecte.
    """

    NOUVEAU = 'nouveau', 'Nouveau'
    RETENU = 'retenu', 'Retenu'
    IGNORE = 'ignore', 'Ignoré'
    CONVERTI = 'converti', 'Converti en appel d\'offres'
    EXPIRE = 'expire', 'Expiré'


#: Statuts encore « vivants » : seuls ceux-là peuvent expirer.
STATUTS_OUVERTS = (StatutAvis.NOUVEAU, StatutAvis.RETENU)


class CategorieAvis(models.TextChoices):
    TRAVAUX = 'travaux', 'Travaux'
    FOURNITURES = 'fournitures', 'Fournitures'
    SERVICES = 'services', 'Services'
    AUTRE = 'autre', 'Autre / non précisée'


class Informateur(models.TextChoices):
    """VAO27 — QUI a signalé cet avis. La question qui vaut le module.

    L'avis qui a réellement occupé le fondateur (FRDISI) n'est passé par aucun
    portail : il est arrivé par un partenaire. Sans ce champ, la mesure
    d'attribution (VAO31) ne pourrait pas répondre à « d'où vient réellement
    le chiffre d'affaires » — et on continuerait à croire que le portail
    couvre tout.
    """

    PARTENAIRE = 'partenaire', 'Partenaire'
    CLIENT = 'client', 'Client'
    EMPLOYE = 'employe', 'Employé'
    PRESSE = 'presse', 'Presse'
    AUTRE = 'autre', 'Autre'


class AvisMarcheQuerySet(models.QuerySet):
    def ouverts(self):
        return self.filter(statut__in=STATUTS_OUVERTS)

    def depasses(self, maintenant=None):
        """Les avis encore ouverts dont la date limite est passée.

        LECTURE SEULE — la bascule est faite par ``expirer_les_depasses``.
        """
        maintenant = maintenant or timezone.now()
        return self.ouverts().filter(
            date_limite_remise__isnull=False,
            date_limite_remise__lt=maintenant)

    def expirer_les_depasses(self, maintenant=None, user=None):
        """Bascule en ``expire`` tout avis ouvert dont la date limite est
        dépassée. Renvoie le nombre d'avis basculés.

        Un avis sans date limite n'expire jamais tout seul : on ne devine pas
        une échéance qu'on n'a pas lue.

        VAO14 — DÉLÈGUE au service : le statut ne se mute qu'à un seul
        endroit du dépôt (``services.changer_statut_avis``). Import
        fonction-local, pour ne pas créer de cycle models ↔ services.
        """
        from .services import expirer_avis_depasses
        return expirer_avis_depasses(self, maintenant=maintenant, user=user)


class AvisMarche(TenantModel):
    """Le SAS — la table où atterrissent TOUS les avis, quelle que soit la
    porte d'entrée (portail public, tuyau partenaire, import de fichier).

    **JAMAIS de création automatique d'``AppelOffre``.** Le portail contient
    beaucoup de bruit : un avis est un signal, un humain tranche. Le lien vers
    l'affaire créée est un **entier opaque** (``appel_offre_id``), jamais une
    FK vers ``apps.ao`` — c'est ce qui garde les deux apps découplées et le
    contrat import-linter vert.

    Aucun champ de coût ni de marge ne vit ici : le sas décrit un avis
    PUBLIC, pas une affaire chiffrée. ``montant_estime`` et
    ``caution_provisoire`` sont des montants publiés PAR L'ACHETEUR, lus sur
    l'avis — jamais un prix de revient Taqinor.
    """

    source = models.ForeignKey(
        'veille_ao.SourceVeille', on_delete=models.PROTECT,
        related_name='avis', verbose_name='Source')

    # ── Identité d'origine (le portail expose ces deux-là dans l'URL de
    # détail : refConsultation + orgAcronyme). Vides pour une saisie
    # manuelle ou un import — c'est normal, le filet de dédoublonnage de
    # niveau 2 prend alors le relais (VAO11).
    ref_consultation = models.CharField(
        'Référence de consultation', max_length=60, blank=True, default='')
    org_acronyme = models.CharField(
        "Acronyme de l'organisme", max_length=60, blank=True, default='')
    reference_avis = models.CharField(
        "Référence de l'avis", max_length=120, blank=True, default='')

    # ── Le fond de l'avis
    objet = models.TextField('Objet')
    acheteur = models.CharField('Acheteur public', max_length=255, blank=True,
                                default='')
    lieu = models.CharField("Lieu d'exécution", max_length=255, blank=True,
                            default='')
    region = models.CharField('Région', max_length=120, blank=True,
                              default='')
    procedure = models.CharField('Procédure', max_length=160, blank=True,
                                 default='')
    categorie = models.CharField(
        'Catégorie', max_length=20, choices=CategorieAvis.choices,
        default=CategorieAvis.AUTRE)
    lot = models.CharField('Lot', max_length=160, blank=True, default='')

    # ── Les dates. La date de PUBLICATION est lue sur la ligne de résultat
    # (« Publié le ») — le filtre de dates du formulaire du portail a été
    # mesuré peu fiable, on ne s'en sert pas.
    date_publication = models.DateField('Publié le', null=True, blank=True)
    date_limite_remise = models.DateTimeField(
        'Date limite de remise', null=True, blank=True)
    date_ouverture = models.DateTimeField(
        "Date d'ouverture des plis", null=True, blank=True)

    # ── Les montants PUBLIÉS PAR L'ACHETEUR (jamais un coût interne)
    montant_estime = models.DecimalField(
        'Montant estimé (MAD)', max_digits=14, decimal_places=2,
        null=True, blank=True)
    caution_provisoire = models.DecimalField(
        'Caution provisoire (MAD)', max_digits=14, decimal_places=2,
        null=True, blank=True)

    url_detail = models.URLField("URL de la page de détail", max_length=500,
                                 blank=True, default='')

    # VAO27 — QUI me l'a signalé. Vide pour un avis COLLECTÉ (personne ne l'a
    # signalé, une machine l'a lu) ; OBLIGATOIRE pour une saisie manuelle,
    # exigé par le service, pas par la colonne — une contrainte NOT NULL ici
    # bloquerait toute collecte automatique.
    informateur = models.CharField(
        'Informateur', max_length=20, choices=Informateur.choices,
        blank=True, default='',
        help_text="Qui a signalé cet avis. C'est la seule porte qui aurait "
                  "capté l'avis FRDISI — et la matière de la mesure "
                  "d'attribution (VAO31).")

    # ── Pourquoi cet avis est remonté (VAO9 remplit ces deux champs)
    mots_cles_declenches = models.JSONField(
        'Mots-clés déclenchés', default=list, blank=True,
        help_text="La liste des mots qui ont fait remonter l'avis : "
                  "l'utilisateur doit voir POURQUOI il le voit.")
    score = models.PositiveIntegerField('Score', default=0)

    statut = models.CharField(
        'Statut', max_length=20, choices=StatutAvis.choices,
        default=StatutAvis.NOUVEAU)

    appel_offre_id = models.PositiveIntegerField(
        "Appel d'offres créé", null=True, blank=True,
        help_text="Entier OPAQUE vers apps.ao — jamais une clé étrangère : "
                  "les deux apps restent découplées.")

    donnees_brutes = models.JSONField(
        'Données brutes', default=dict, blank=True,
        help_text="Ce qui a été lu tel quel, pour pouvoir rejouer une "
                  "analyse sans retourner sur la source.")

    # VAO11 — dédoublonnage de NIVEAU 2 (le filet). Voir ``hashing.py`` :
    # empreinte SHA-256 de (référence + acheteur + date limite), pour les
    # deux cas où l'identifiant de portail est aveugle — l'avis RECTIFIÉ qui
    # ressort avec un nouvel identifiant, et la saisie manuelle / l'import
    # qui n'en ont aucun. NON unique : une collision doit METTRE À JOUR, pas
    # rejeter.
    empreinte = models.CharField(
        'Empreinte', max_length=64, blank=True, default='', db_index=True)

    # VAO10 — quelle règle a filtré cet avis. Un filtrage MUET est interdit :
    # sans cette trace, l'utilisateur ne peut ni comprendre ni corriger.
    regle_exclusion = models.ForeignKey(
        'veille_ao.RegleExclusion', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='avis_ignores',
        verbose_name="Règle d'exclusion appliquée")

    objects = AvisMarcheQuerySet.as_manager()

    class Meta:
        verbose_name = 'Avis de marché'
        verbose_name_plural = 'Avis de marché'
        ordering = ['-date_publication', '-id']
        constraints = [
            # VAO11 — dédoublonnage de NIVEAU 1 : l'identité propre du
            # portail, lue directement dans l'URL de détail. La contrainte
            # est PARTIELLE à dessein : une saisie manuelle et un import de
            # fichier n'ont AUCUN identifiant de portail, et sans la
            # condition ils entreraient tous en collision sur la chaîne
            # vide — c'est le niveau 2 (empreinte) qui les couvre.
            models.UniqueConstraint(
                fields=['company', 'source', 'ref_consultation',
                        'org_acronyme'],
                condition=~models.Q(ref_consultation=''),
                name='veille_ao_avis_identite_portail_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='veille_ao_avis_co_statut_idx'),
            models.Index(fields=['company', 'date_limite_remise'],
                         name='veille_ao_avis_co_limite_idx'),
            models.Index(fields=['company', '-score'],
                         name='veille_ao_avis_co_score_idx'),
            models.Index(fields=['company', 'empreinte'],
                         name='veille_ao_avis_co_empr_idx'),
        ]

    def __str__(self):
        return (self.reference_avis or self.ref_consultation
                or self.objet[:60])

    @property
    def est_depasse(self):
        """La date limite est-elle passée ? (lecture pure, sans écriture)"""
        if not self.date_limite_remise:
            return False
        return self.date_limite_remise < timezone.now()


class VerdictExecution(models.TextChoices):
    """Les TROIS issues d'une collecte, jamais confondues (VAO20/VAO24).

    Confondre « réussie, 0 nouveauté » et « cassée, 0 résultat » est
    exactement le scénario qui fait rater un AO en se croyant couvert : le
    portail change, la collecte renvoie vide, l'écran reste calme, et
    personne ne s'en aperçoit pendant des semaines.
    """

    SUCCES = 'succes', 'Réussie'
    ANOMALIE = 'anomalie', 'Réussie avec anomalie'
    ECHEC = 'echec', 'Échouée'


class DeclencheurCollecte(models.TextChoices):
    """Qui a lancé cette collecte — le beat de nuit ou un humain."""

    PLANIFIE = 'planifie', 'Tâche planifiée (06:00)'
    MANUEL = 'manuel', 'Déclenchement manuel'


class ExecutionCollecteQuerySet(models.QuerySet):
    def reussies(self):
        return self.exclude(verdict=VerdictExecution.ECHEC)

    def recentes(self):
        """De la plus récente à la plus ancienne — l'ordre de lecture."""
        return self.order_by('-debut', '-id')


class ExecutionCollecte(TenantModel):
    """Le JOURNAL d'exécution de la veille — la table qui empêche le silence.

    Écrit à CHAQUE exécution, réussie ou non : c'est le seul garde-fou contre
    le scénario réel où la veille ne ramène plus rien et où l'écran, resté
    calme, laisse croire à une couverture qui n'existe plus.

    Aucun champ de coût ni de marge : une exécution décrit un travail de
    lecture, pas une affaire.
    """

    source = models.ForeignKey(
        'veille_ao.SourceVeille',
        on_delete=models.SET_NULL,  # on_delete: le JOURNAL survit à la source
        null=True, blank=True, related_name='executions',
        verbose_name='Source')

    debut = models.DateTimeField('Début', default=timezone.now)
    fin = models.DateTimeField('Fin', null=True, blank=True)

    mots_cles_interroges = models.JSONField(
        'Mots-clés interrogés', default=list, blank=True,
        help_text="Ce qui a réellement été demandé — sans quoi « 0 résultat » "
                  "est illisible.")

    examines = models.PositiveIntegerField('Avis examinés', default=0)
    nouveaux = models.PositiveIntegerField('Avis nouveaux', default=0)
    mis_a_jour = models.PositiveIntegerField('Avis mis à jour', default=0)
    auto_ignores = models.PositiveIntegerField('Avis auto-ignorés', default=0)

    erreurs = models.JSONField('Erreurs', default=list, blank=True)
    verdict = models.CharField(
        'Verdict', max_length=12, choices=VerdictExecution.choices,
        default=VerdictExecution.SUCCES)
    message = models.CharField('Message', max_length=500, blank=True,
                               default='')
    declencheur = models.CharField(
        'Déclencheur', max_length=12, choices=DeclencheurCollecte.choices,
        default=DeclencheurCollecte.PLANIFIE)

    #: VAO24 — l'alarme de silence a-t-elle DÉJÀ été signalée pour cet état ?
    #: Empêche de renotifier le directeur à chaque passage : une alarme qui
    #: crie tous les jours est une alarme qu'on apprend à ignorer.
    alarme_notifiee = models.BooleanField(
        "Alarme déjà notifiée", default=False)

    objects = ExecutionCollecteQuerySet.as_manager()

    class Meta:
        verbose_name = 'Exécution de collecte'
        verbose_name_plural = 'Exécutions de collecte'
        ordering = ['-debut', '-id']
        indexes = [
            models.Index(fields=['company', '-debut'],
                         name='veille_ao_exec_co_debut_idx'),
            models.Index(fields=['company', 'verdict'],
                         name='veille_ao_exec_co_verdict_idx'),
        ]

    def __str__(self):
        return f'{self.debut:%d/%m/%Y %H:%M} — {self.get_verdict_display()}'

    @property
    def reussie(self):
        return self.verdict != VerdictExecution.ECHEC

    @property
    def muette(self):
        """Réussie mais RIEN vu : ni nouveau, ni mis à jour, ni examiné.

        C'est le signal faible de l'alarme : deux jours de suite ainsi, la
        veille ne ramène plus rien et il faut aller vérifier.
        """
        return self.reussie and self.examines == 0


class NiveauMotCle(models.TextChoices):
    """Deux niveaux, mesurés sur le portail réel (VAO9).

    Le NOYAU est de haute précision : ce qu'il attrape est presque toujours
    pour nous. Le LARGE accepte du bruit en échange de la couverture — il
    pèse donc moins lourd, jamais autant qu'un mot du noyau.
    """

    NOYAU = 'noyau', 'Noyau (précision haute)'
    LARGE = 'large', 'Large (bruit accepté)'


#: Poids par défaut d'un mot-clé selon son niveau. C'est un DÉFAUT de
#: création, pas une règle figée : le poids vit sur la ligne, et l'écran peut
#: le changer sans redéploiement.
POIDS_PAR_DEFAUT = {
    NiveauMotCle.NOYAU: 10,
    NiveauMotCle.LARGE: 3,
}

#: Plafond du score. Un avis qui déclenche huit mots n'est pas huit fois plus
#: intéressant qu'un avis qui en déclenche deux — le score est un indice de
#: tri, pas une mesure.
SCORE_MAX = 100


class MotCleVeilleQuerySet(models.QuerySet):
    def actifs(self):
        return self.filter(actif=True)


class MotCleVeille(TenantModel):
    """Les mots-clés sont de la DONNÉE, jamais une constante du code.

    Ajouter « ombrière photovoltaïque » doit être un geste d'écran, pas un
    déploiement — sinon la veille se périme au rythme des livraisons.
    """

    libelle = models.CharField('Mot-clé', max_length=120)
    niveau = models.CharField(
        'Niveau', max_length=10, choices=NiveauMotCle.choices,
        default=NiveauMotCle.LARGE)
    poids = models.PositiveIntegerField(
        'Poids', default=POIDS_PAR_DEFAUT[NiveauMotCle.LARGE],
        help_text="Contribution du mot-clé au score de l'avis.")
    actif = models.BooleanField('Actif', default=True)

    objects = MotCleVeilleQuerySet.as_manager()

    class Meta:
        verbose_name = 'Mot-clé de veille'
        verbose_name_plural = 'Mots-clés de veille'
        ordering = ['niveau', 'libelle', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'libelle'],
                name='veille_ao_motcle_co_libelle_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='veille_ao_mc_co_actif_idx'),
        ]

    def __str__(self):
        return self.libelle


class TypeAcheteur(models.TextChoices):
    """VAO29 — les CATÉGORIES d'organismes à démarcher.

    Des catégories, jamais des noms : le seed d'amorçage ne doit inventer
    aucun organisme. Un nom faux dans un carnet de prospection est pire qu'un
    carnet vide — il se recopie, il se démarche, et il fait perdre du temps.
    """

    FONDATION = 'fondation', 'Fondation'
    UNIVERSITE_PRIVEE = 'universite_privee', 'Université privée'
    CLINIQUE = 'clinique', 'Clinique'
    GROUPE_HOTELIER = 'groupe_hotelier', 'Groupe hôtelier'
    INDUSTRIEL = 'industriel', 'Industriel'
    COOPERATIVE_AGRICOLE = 'cooperative_agricole', 'Coopérative agricole'
    PROMOTEUR = 'promoteur', 'Promoteur'
    COLLECTIVITE = 'collectivite', 'Collectivité'


class StatutRelation(models.TextChoices):
    """Où en est la relation — le seul indicateur qui compte ici.

    Être sur la liste d'invitation d'une consultation privée ne se surveille
    pas : ça se construit. Ce champ dit à quelle distance on est de cette
    liste.
    """

    A_CONTACTER = 'a_contacter', 'À contacter'
    CONTACTE = 'contacte', 'Contacté'
    EN_DISCUSSION = 'en_discussion', 'En discussion'
    REFERENCE = 'reference', 'Référencé (reçoit les consultations)'
    CLIENT = 'client', 'Client'
    SANS_SUITE = 'sans_suite', 'Sans suite'


class AcheteurCibleQuerySet(models.QuerySet):
    def relances_dues(self, a_la_date=None):
        """Les relances échues — l'ordre d'urgence, jamais l'ordre alphabétique."""
        return self.filter(
            prochaine_relance__isnull=False,
            prochaine_relance__lte=(a_la_date or timezone.localdate()),
        ).exclude(statut_relation=StatutRelation.SANS_SUITE).order_by(
            'prochaine_relance', 'id')


class AcheteurCible(TenantModel):
    """Le carnet des acheteurs à DÉMARCHER — la vraie contre-mesure FRDISI.

    Constat central du groupe : ce marché-là ne se surveille pas, il se
    démarche. La seule façon de recevoir la PROCHAINE consultation FRDISI est
    d'être sur la liste d'invitation — et aucun collecteur, aucun agrégateur,
    aucun flux RSS ne peut y mettre Taqinor. C'est un travail de relation, et
    ce carnet est l'outil de ce travail.

    Le lien vers le CRM est un **entier opaque** (``lead_id``), jamais une FK
    vers ``apps.crm`` : les apps restent découplées et le contrat
    import-linter reste vert.
    """

    nom = models.CharField('Nom de l\'organisme', max_length=255)
    type = models.CharField(
        'Type', max_length=32, choices=TypeAcheteur.choices,
        default=TypeAcheteur.FONDATION)
    contact = models.CharField(
        'Contact', max_length=255, blank=True, default='',
        help_text='Nom, téléphone ou e-mail de la personne à joindre.')
    dernier_contact = models.DateField('Dernier contact', null=True,
                                       blank=True)
    prochaine_relance = models.DateField('Prochaine relance', null=True,
                                         blank=True)
    statut_relation = models.CharField(
        'Statut de la relation', max_length=20,
        choices=StatutRelation.choices, default=StatutRelation.A_CONTACTER)
    lead_id = models.PositiveIntegerField(
        'Lead CRM', null=True, blank=True,
        help_text='Entier OPAQUE vers apps.crm — jamais une clé étrangère : '
                  'les deux apps restent découplées.')
    notes = models.TextField('Notes', blank=True, default='')

    objects = AcheteurCibleQuerySet.as_manager()

    class Meta:
        verbose_name = 'Acheteur cible'
        verbose_name_plural = 'Acheteurs cibles'
        ordering = ['nom', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'nom'],
                name='veille_ao_acheteur_co_nom_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'prochaine_relance'],
                         name='veille_ao_ach_co_relance_idx'),
            models.Index(fields=['company', 'statut_relation'],
                         name='veille_ao_ach_co_statut_idx'),
        ]

    def __str__(self):
        return self.nom

    @property
    def relance_due(self):
        if not self.prochaine_relance:
            return False
        return self.prochaine_relance <= timezone.localdate()


class PorteeExclusion(models.TextChoices):
    """Sur QUOI une règle d'exclusion mord (VAO10)."""

    ACHETEUR = 'acheteur', 'Acheteur'
    LIBELLE = 'libelle', "Mot de l'objet"
    CATEGORIE = 'categorie', 'Catégorie'
    REGION = 'region', 'Région'


class RegleExclusionQuerySet(models.QuerySet):
    def actives(self):
        return self.filter(actif=True)


class RegleExclusion(TenantModel):
    """« Ignorer » doit APPRENDRE, sinon l'écran se remplit de bruit.

    Constat de conception (VAO10) : un avis ignoré qui remonte à chaque
    collecte tue l'usage de l'écran en deux semaines. Une règle mémorise
    l'arbitrage — et **le motif est obligatoire** : une exclusion sans raison
    écrite est indéfendable six mois plus tard.

    Une règle DÉSACTIVÉE cesse immédiatement de mordre : les avis suivants
    réapparaissent (la marche arrière doit être triviale).
    """

    portee = models.CharField(
        'Portée', max_length=20, choices=PorteeExclusion.choices)
    valeur = models.CharField(
        'Valeur', max_length=200,
        help_text="Ce qui est comparé : acheteur, mot de l'objet, catégorie "
                  "ou région.")
    motif = models.CharField(
        'Motif', max_length=255,
        help_text="Pourquoi cet arbitrage — en français, obligatoire.")
    actif = models.BooleanField('Active', default=True)
    compteur_application = models.PositiveIntegerField(
        "Nombre d'applications", default=0,
        help_text="Combien d'avis cette règle a filtrés — une règle qui ne "
                  "sert jamais est une règle à supprimer.")

    objects = RegleExclusionQuerySet.as_manager()

    class Meta:
        verbose_name = "Règle d'exclusion"
        verbose_name_plural = "Règles d'exclusion"
        ordering = ['portee', 'valeur', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'portee', 'valeur'],
                name='veille_ao_regle_co_portee_valeur_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='veille_ao_regle_co_actif_idx'),
        ]

    def __str__(self):
        return f'{self.get_portee_display()} : {self.valeur}'
