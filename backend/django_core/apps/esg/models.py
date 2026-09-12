"""Modèles du reporting ESG/durabilité consolidé (Groupe NTESG).

Cette app est une COUCHE DE CONSOLIDATION : elle ne resaisit rien de ce que
``qhse`` capture déjà (bilan carbone QHSE39, indicateurs ESG bruts QHSE40,
déchets, conformité environnementale…). Elle ajoute :

* ``PeriodeReportingESG`` — une période de reporting (mois/trimestre/année)
  que l'on peut FIGER : une fois figée, son ``SnapshotESG`` associé porte les
  chiffres AU MOMENT DE LA CLÔTURE, gelés, jamais recalculés en direct
  ensuite (même logique que ``compta.PeriodeComptable``) ;
* ``SnapshotESG`` — le JSON figé produit par
  ``apps.esg.services.figer_periode`` (agrégation cross-app via
  ``apps.esg.selectors.agreger_indicateurs_periode``) ;
* ``CatalogueIndicateurESG`` — référentiel GRI-lite seedable (~25-30
  indicateurs standards), sert de check-list de couverture ;
* ``ObjectifESGTrajectoire`` — objectif de réduction/progression avec
  trajectoire linéaire référence→cible, comparée aux valeurs réelles.

Tout hérite de ``core.models.TenantModel`` (FK ``company`` + timestamps —
convention SCA4 pour tout NOUVEAU modèle multi-société). Lecture des données
sources d'autres apps EXCLUSIVEMENT via leurs ``selectors.py`` (import
fonction-local, jamais leurs ``models``) — voir ``apps/esg/selectors.py``.
Entièrement additif.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TenantModel


class PeriodeReportingESG(TenantModel):
    """Période de reporting ESG d'une société (NTESG1).

    ``statut`` suit un cycle à sens unique : ``brouillon`` → ``figee`` →
    ``publiee``. Une fois ``figee`` (ou ``publiee``), la période devient
    IMMUABLE — son ``SnapshotESG`` (JSON gelé) est la seule source de vérité
    pour tout rendu (PDF/xlsx/API publique) ultérieur, quelles que soient les
    évolutions des données sources QHSE après coup.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        FIGEE = 'figee', 'Figée'
        PUBLIEE = 'publiee', 'Publiée'

    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    date_debut = models.DateField(verbose_name='Début')
    date_fin = models.DateField(verbose_name='Fin')
    statut = models.CharField(
        max_length=10, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    figee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Figée le')
    figee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='periodes_esg_figees',
        verbose_name='Figée par',
    )

    class Meta:
        verbose_name = 'Période de reporting ESG'
        verbose_name_plural = 'Périodes de reporting ESG'
        ordering = ['-date_debut', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'libelle'],
                name='esg_periode_co_libelle_uniq',
            ),
        ]

    def clean(self):
        super().clean()
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                'La date de fin ne peut pas précéder la date de début.')

    @property
    def est_figee(self):
        """Vrai si la période est ``figee`` ou ``publiee`` (immuable)."""
        return self.statut in (self.Statut.FIGEE, self.Statut.PUBLIEE)

    def __str__(self):
        return f'{self.libelle} ({self.get_statut_display()})'


class SnapshotESG(TenantModel):
    """Instantané JSON figé des chiffres ESG d'une période (NTESG1).

    Produit une seule fois par ``services.figer_periode`` (jamais recalculé
    après coup) : ``donnees`` porte la structure renvoyée par
    ``selectors.agreger_indicateurs_periode`` au moment du figeage, avec les
    dates sérialisées en ISO 8601 (JSON-safe).
    """

    periode = models.OneToOneField(
        PeriodeReportingESG,
        on_delete=models.CASCADE,  # on_delete: cascade parent→enfant (composant du parent)
        related_name='snapshot',
        verbose_name='Période',
    )
    donnees = models.JSONField(default=dict, blank=True, verbose_name='Données')
    figee_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Figé le')

    class Meta:
        verbose_name = 'Instantané ESG'
        verbose_name_plural = 'Instantanés ESG'
        ordering = ['-figee_le', '-id']

    def __str__(self):
        return f'Snapshot {self.periode_id} ({self.figee_le:%Y-%m-%d})'


class CatalogueIndicateurESG(TenantModel):
    """Référentiel GRI-lite d'indicateurs ESG standards (NTESG3).

    Seedé de façon idempotente par société via
    ``python manage.py seed_catalogue_esg`` (voir
    ``management/commands/seed_catalogue_esg.py``) — sert de check-list au
    responsable QHSE/RSE pour savoir quels ``qhse.IndicateurESG`` créer.
    ``reference_gri`` est affichée en info-bulle « inspiré de » — jamais
    présentée comme une certification GRI.
    """

    class Pilier(models.TextChoices):
        ENVIRONNEMENT = 'environnement', 'Environnement'
        SOCIAL = 'social', 'Social'
        GOUVERNANCE = 'gouvernance', 'Gouvernance'

    code = models.CharField(max_length=30, verbose_name='Code')
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    pilier = models.CharField(
        max_length=15, choices=Pilier.choices, verbose_name='Pilier ESG')
    unite_attendue = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Unité attendue')
    reference_gri = models.CharField(
        max_length=60, blank=True, default='',
        verbose_name='Référence GRI (inspiré de)')

    class Meta:
        verbose_name = 'Indicateur du catalogue GRI-lite'
        verbose_name_plural = 'Catalogue GRI-lite'
        ordering = ['pilier', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='esg_catalogue_co_code_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.code} — {self.libelle}'


class ObjectifESGTrajectoire(TenantModel):
    """Objectif de réduction/progression ESG avec trajectoire linéaire (NTESG7).

    ``indicateur_code`` référence en LECTURE le ``code`` d'un
    ``qhse.IndicateurESG`` (jamais une FK cross-app — string souple, résolue
    au moment du calcul via ``qhse.selectors.export_esg``). La trajectoire
    théorique interpole linéairement entre
    (``annee_reference``, ``valeur_reference``) et
    (``annee_cible``, ``valeur_cible``) ; des jalons intermédiaires optionnels
    peuvent affiner l'affichage (``jalons`` = ``{"2027": 120.5, ...}``).
    """

    indicateur_code = models.CharField(
        max_length=30, verbose_name='Code indicateur (qhse.IndicateurESG)')
    libelle = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Libellé')
    valeur_reference = models.DecimalField(
        max_digits=18, decimal_places=4, verbose_name='Valeur de référence')
    annee_reference = models.PositiveIntegerField(
        verbose_name='Année de référence')
    valeur_cible = models.DecimalField(
        max_digits=18, decimal_places=4, verbose_name='Valeur cible')
    annee_cible = models.PositiveIntegerField(verbose_name='Année cible')
    jalons = models.JSONField(
        default=dict, blank=True,
        verbose_name='Jalons intermédiaires ({année: valeur})')
    actif = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Objectif de trajectoire ESG'
        verbose_name_plural = 'Objectifs de trajectoire ESG'
        ordering = ['indicateur_code', 'annee_cible']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'indicateur_code', 'annee_cible'],
                name='esg_objectif_co_code_anneecible_uniq',
            ),
        ]

    def clean(self):
        super().clean()
        if self.annee_cible and self.annee_reference \
                and self.annee_cible <= self.annee_reference:
            raise ValidationError(
                "L'année cible doit être postérieure à l'année de référence.")

    def __str__(self):
        return (f'{self.indicateur_code} → {self.valeur_cible} '
                f'({self.annee_cible})')


class PartiePrenanteESG(TenantModel):
    """Registre des parties prenantes ESG — matérialité simplifiée (NTESG12).

    DISTINCT du ``PartieInteressee`` QHSE (SMQ/ISO, portée qualité) : ce
    registre est spécifiquement la matérialité RSE/extra-financière exigée
    par les cadres CSRD-like et les appels d'offres (matrice 2x2
    influence × intérêt, chacun noté 1-5 par l'utilisateur).
    """

    class Categorie(models.TextChoices):
        CLIENT = 'client', 'Client'
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        COLLABORATEUR = 'collaborateur', 'Collaborateur'
        COLLECTIVITE = 'collectivite', 'Collectivité'
        ACTIONNAIRE = 'actionnaire', 'Actionnaire'

    nom = models.CharField(max_length=255, verbose_name='Nom')
    categorie = models.CharField(
        max_length=15, choices=Categorie.choices, verbose_name='Catégorie')
    enjeux = models.TextField(
        blank=True, default='', verbose_name='Enjeux prioritaires')
    influence = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Influence (1-5)')
    interet = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Intérêt (1-5)')

    class Meta:
        verbose_name = 'Partie prenante ESG'
        verbose_name_plural = 'Parties prenantes ESG'
        ordering = ['-influence', '-interet', 'nom']

    def __str__(self):
        return f'{self.nom} ({self.get_categorie_display()})'


class DocumentPolitiqueESG(TenantModel):
    """Registre déclaratif des politiques RSE publiées (NTESG13).

    Le FICHIER lui-même est déposé via ``records.Attachment`` (générique,
    MinIO — JAMAIS un ``FileField`` propre à cette app, ARC26) : ce modèle
    porte uniquement les métadonnées de cycle de vie. Cible enregistrée dans
    ``apps/esg/platform.py`` (``record_targets``). Aucune allégation de
    conformité générée automatiquement — l'utilisateur dépose et date ses
    propres documents ; inspiré du cycle de vie ``ged.Document.statut``
    (brouillon/publiée/obsolète) SANS import cross-app.
    """

    class TypeDocument(models.TextChoices):
        CHARTE_ETHIQUE = 'charte_ethique', 'Charte éthique'
        POLITIQUE_ENVIRONNEMENTALE = (
            'politique_environnementale', 'Politique environnementale')
        POLITIQUE_DIVERSITE = 'politique_diversite', 'Politique diversité'
        CODE_FOURNISSEUR = 'code_fournisseur', 'Code fournisseur'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PUBLIEE = 'publiee', 'Publiée'
        OBSOLETE = 'obsolete', 'Obsolète'

    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    type_document = models.CharField(
        max_length=30, choices=TypeDocument.choices,
        verbose_name='Type de document')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_publication = models.DateField(
        null=True, blank=True, verbose_name='Date de publication')
    date_revue = models.DateField(
        null=True, blank=True, verbose_name='Date de dernière revue')

    class Meta:
        verbose_name = 'Document de politique ESG'
        verbose_name_plural = 'Documents de politique ESG'
        ordering = ['-date_publication', '-id']

    def __str__(self):
        return f'{self.libelle} ({self.get_statut_display()})'


class FacteurEmissionReference(TenantModel):
    """Bibliothèque de facteurs d'émission éditable et versionnée (NTESG16).

    Centralise/met à jour les facteurs d'émission (ex. nouvelle version
    ADEME Base Carbone) au lieu de les ressaisir à la main à chaque
    ``qhse.LigneBilanCarbone.facteur_emission`` — reste une SUGGESTION
    pré-remplie éditable côté qhse, jamais imposée (hors périmètre de cette
    app : la consommation par le formulaire de ligne de bilan carbone est un
    futur lane qhse-side, cette app ne fait qu'exposer le registre versionné
    en lecture/écriture).

    JAMAIS d'écrasement silencieux : chaque mise à jour crée une NOUVELLE
    ligne ``version`` (numérotée ``max(version)+1``, jamais ``count()+1`` —
    ARC6, voir ``services.creer_version_facteur``) et désactive
    l'ancienne (``actif=False``) — l'historique complet reste consultable.
    """

    categorie = models.CharField(max_length=120, verbose_name='Catégorie')
    unite = models.CharField(max_length=30, verbose_name='Unité')
    valeur = models.DecimalField(
        max_digits=18, decimal_places=6,
        verbose_name="Valeur (facteur d'émission)")
    source = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Source')
    date_maj = models.DateTimeField(verbose_name='Date de mise à jour')
    version = models.PositiveIntegerField(default=1, verbose_name='Version')
    actif = models.BooleanField(default=True, verbose_name='Version active')

    class Meta:
        verbose_name = "Facteur d'émission de référence"
        verbose_name_plural = "Facteurs d'émission de référence"
        ordering = ['categorie', 'unite', '-version']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'categorie', 'unite', 'version'],
                name='esg_facteur_co_cat_unite_version_uniq'),
        ]

    def __str__(self):
        return f'{self.categorie} ({self.unite}) v{self.version}'


class FacteurEmissionVersionCounter(TenantModel):
    """Compteur PERSISTANT de version pour ``FacteurEmissionReference``
    (NTESG16, ARC6).

    Une ligne ``FacteurEmissionReference`` peut être supprimée manuellement
    (pas de soft-delete ici) — sans ce compteur SÉPARÉ, un simple
    ``max(version)`` recalculé sur les lignes RESTANTES ferait régresser puis
    RÉUTILISER un numéro de version déjà attribué (violerait la traçabilité
    d'audit : « version 2 » doit toujours désigner la même valeur historique,
    même si cette ligne a depuis été supprimée). Incrémenté sous verrou
    (``select_for_update``) par ``services.creer_version_facteur`` UNIQUEMENT
    — jamais lu/affiché directement ailleurs."""

    categorie = models.CharField(max_length=120)
    unite = models.CharField(max_length=30)
    dernier_version = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Compteur de version de facteur d'émission"
        verbose_name_plural = "Compteurs de version de facteur d'émission"
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'categorie', 'unite'],
                name='esg_facteur_version_counter_co_cat_unite_uniq'),
        ]

    def __str__(self):
        return f'{self.categorie} ({self.unite}) — dernier v{self.dernier_version}'


class ParametresESG(TenantModel):
    """Réglages ESG d'UNE société (NTESG20) — singleton par tenant.

    Même patron que les paramètres existants du dépôt
    (``notifications.WorkingHoursConfig``,
    ``btp_chantier.ParametresBtpChantier``) : ``OneToOneField`` sur
    ``company``, au plus une ligne par société, créée à la demande. Tant
    qu'aucune ligne n'existe, les DÉFAUTS du module s'appliquent — le
    comportement au déploiement est donc inchangé.

    Chaque réglage a UN consommateur nommé, jamais un champ décoratif :

    * ``seuil_alerte_derive_pct`` → ``services.alerter_derive_trajectoire``
      (NTESG10), qui exposait jusqu'ici un défaut fixe de 10 % faute de ce
      modèle ;
    * ``pilote_esg`` → destinataire par défaut des notifications ESG, en
      remplacement du repli « tous les administrateurs actifs » ;
    * ``frequence_reporting`` → informatif, affiché par l'assistant de
      clôture (NTESG18) ;
    * ``ponderation_badge_maturite`` → ``selectors.badge_maturite_esg``
      (NTESG15), dont les trois composantes étaient pondérées à 1/3 en dur.

    La pondération DOIT sommer à 100 — validé côté SERVEUR (``clean()``), pas
    seulement à l'écran : un badge pondéré à 90 ou 110 produirait un score
    faux sans que personne ne le voie.
    """

    class Frequence(models.TextChoices):
        MENSUELLE = 'mensuelle', 'Mensuelle'
        TRIMESTRIELLE = 'trimestrielle', 'Trimestrielle'
        ANNUELLE = 'annuelle', 'Annuelle'

    #: Clés de ``ponderation_badge_maturite`` — les trois composantes EXACTES
    #: de ``selectors.badge_maturite_esg``. Toute autre clé est refusée : une
    #: pondération qui nomme une composante inexistante est un réglage qui ne
    #: fera jamais rien.
    CLES_PONDERATION = ('couverture', 'cibles', 'trajectoire')

    #: Poids par défaut = le comportement historique (1/3 chacun, arrondi à
    #: 34/33/33 pour sommer exactement à 100).
    PONDERATION_DEFAUT = {'couverture': 34, 'cibles': 33, 'trajectoire': 33}

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='esg_parametres', verbose_name='Société')
    seuil_alerte_derive_pct = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Seuil d'alerte de dérive de trajectoire (%)")
    pilote_esg = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        # on_delete: SET_NULL — le départ du pilote ne supprime pas les
        # réglages de la société (repli sur les administrateurs actifs).
        null=True, blank=True, related_name='esg_pilotages',
        verbose_name='Pilote ESG (destinataire par défaut)')
    frequence_reporting = models.CharField(
        max_length=15, choices=Frequence.choices,
        default=Frequence.ANNUELLE,
        verbose_name='Fréquence de reporting')
    ponderation_badge_maturite = models.JSONField(
        default=dict, blank=True,
        verbose_name='Pondération du badge de maturité (somme = 100)')

    class Meta:
        verbose_name = 'Réglages ESG'
        verbose_name_plural = 'Réglages ESG'

    def clean(self):
        super().clean()
        poids = self.ponderation_badge_maturite or {}
        if not poids:
            return  # vide = défauts du module, toujours valide
        if not isinstance(poids, dict):
            raise ValidationError({
                'ponderation_badge_maturite':
                    'La pondération doit être un objet {composante: poids}.'})
        inconnues = sorted(set(poids) - set(self.CLES_PONDERATION))
        if inconnues:
            raise ValidationError({
                'ponderation_badge_maturite':
                    f'Composante(s) inconnue(s) : {", ".join(inconnues)}. '
                    f'Attendues : {", ".join(self.CLES_PONDERATION)}.'})
        manquantes = sorted(set(self.CLES_PONDERATION) - set(poids))
        if manquantes:
            raise ValidationError({
                'ponderation_badge_maturite':
                    f'Composante(s) manquante(s) : {", ".join(manquantes)}.'})
        total = 0
        for cle in self.CLES_PONDERATION:
            valeur = poids[cle]
            if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
                raise ValidationError({
                    'ponderation_badge_maturite':
                        f'Poids invalide pour « {cle} » : {valeur!r}.'})
            if valeur < 0:
                raise ValidationError({
                    'ponderation_badge_maturite':
                        f'Poids négatif pour « {cle} » : {valeur}.'})
            total += valeur
        if round(total, 6) != 100:
            raise ValidationError({
                'ponderation_badge_maturite':
                    'La pondération doit sommer à 100 (actuellement '
                    f'{total:g}).'})

    def save(self, *args, **kwargs):
        # Le réglage est ENGAGEANT (il change un score affiché) : la
        # pondération est validée AU SAVE, pas seulement au serializer — une
        # écriture en shell ou en commande ne doit pas pouvoir poser une
        # pondération fausse. Les autres champs sont exclus pour ne pas
        # imposer une validation complète là où le modèle n'en avait pas.
        self.full_clean(exclude=[
            f.name for f in self._meta.fields
            if f.name != 'ponderation_badge_maturite'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Réglages ESG — société {self.company_id}'
