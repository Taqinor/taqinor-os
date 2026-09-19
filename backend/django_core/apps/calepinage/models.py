"""Modèles du module Calepinage — CAL7 (+ CAL8, CAL9, CAL45).

LES QUATRE MODÈLES NAISSENT DANS **UNE SEULE** MIGRATION ``0001_initial``
------------------------------------------------------------------------
``Calepinage`` (le pivot), ``CalepinageVersion`` (l'historique, CAL8),
``CalepinageVariante`` (les options comparées, CAL9) et
``ParametresCalepinage`` (les réglages société, CAL45) arrivent ENSEMBLE :
une migration pour le jour 1, donc UN seul manque de cache CI au lieu de
quatre. Les tâches suivantes ajoutent du COMPORTEMENT, pas de la migration.

LES DÉCISIONS D'ARCHITECTURE GRAVÉES ICI
----------------------------------------
* **Multi-tenant par ``core.models.TenantModel``** (ARC1) — FK ``company``
  obligatoire + horodatage, jamais une FK société recodée à la main. La
  société est TOUJOURS posée côté serveur, jamais lue d'un corps de requête.
* **``lead_id`` et ``appel_offre_id`` sont OPAQUES** (``PositiveIntegerField``,
  patron ``AppelOffre.lead_id``) : jamais une FK dure vers ``crm`` ou ``ao``.
  C'est ce que le contrat import-linter ``calepinage-models-decoupled`` (CAL5)
  verrouille, et c'est ce qui garde les chaînes de migrations séparées.
* **``client`` et ``devis`` sont des FK-STRING** vers ``'crm.Client'``
  (``apps/crm/models.py`` — ``ventes.Client`` N'EXISTE PAS, et ``Devis.client``
  pointe lui-même ``'crm.Client'``) et ``'ventes.Devis'``. Les deux sont
  nullables : un calepinage SANS devis est un objet de première classe (porte
  autonome du module).
* **Au moins un rattachement** : la base REFUSE un calepinage qui n'a ni
  ``lead_id`` ni ``client`` (contrainte ``CheckConstraint``). Un calepinage
  orphelin serait un document que personne ne retrouve jamais.
* **Le document ``roof_layout``** suit le schéma v2 publié par CAL232 ; il est
  stocké tel quel (JSON), et son empreinte ``layout_hash`` est calculée par
  ``apps.ventes.services.layout_hash`` — JAMAIS recodée ici (CAL13).

Les lectures cross-app passent EXCLUSIVEMENT par ``apps.crm.selectors`` /
``apps.ventes.selectors`` / ``apps.ao.selectors`` : ce fichier n'importe aucun
modèle étranger.
"""
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class Calepinage(TenantModel):
    """Le PIVOT : une conception de toiture, rattachée à qui la demande.

    Un calepinage naît d'un lead, d'un client, d'un devis ou d'une affaire
    d'appel d'offres — et il SURVIT à l'absence de devis : on peut concevoir
    une toiture avant de chiffrer quoi que ce soit.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        VALIDE = 'valide', 'Validé'
        PERIME = 'perime', 'Périmé'

    #: Lead d'origine — identifiant OPAQUE (jamais une FK ``crm``). Le lead est
    #: résolu, borné société, via ``apps.crm.selectors.get_company_lead``.
    lead_id = models.PositiveIntegerField(
        'Lead (identifiant)', null=True, blank=True, db_index=True)
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,  # on_delete: un client rattaché ne disparaît jamais sous son calepinage
        null=True, blank=True,
        related_name='calepinages',
        verbose_name='Client',
    )
    devis = models.ForeignKey(
        'ventes.Devis',
        on_delete=models.SET_NULL,  # on_delete: un devis supprimé ne détruit pas la conception
        null=True, blank=True,
        related_name='calepinages',
        verbose_name='Devis',
    )
    #: Affaire d'appel d'offres — identifiant OPAQUE (jamais une FK ``ao``).
    appel_offre_id = models.PositiveIntegerField(
        "Appel d'offres (identifiant)", null=True, blank=True, db_index=True)

    titre = models.CharField('Titre', max_length=200, blank=True, default='')
    statut = models.CharField(
        'Statut', max_length=12, choices=Statut.choices,
        default=Statut.BROUILLON, db_index=True)

    #: Document de conception (schéma v2, CAL232) — stocké tel quel.
    roof_layout = models.JSONField('Conception (roof_layout)',
                                   null=True, blank=True)
    #: SHA-256 de la géométrie, calculé par ``apps.ventes.services.layout_hash``
    #: (jamais recodé ici). Vide tant qu'aucun layout n'a été enregistré.
    layout_hash = models.CharField('Empreinte du layout', max_length=64,
                                   blank=True, default='', db_index=True)
    #: Clé MinIO du rendu de la toiture (image). Vide = pas de rendu.
    roof_image = models.CharField("Rendu (clé de stockage)", max_length=500,
                                  blank=True, default='')
    #: Version du moteur qui a produit ``resultat`` — un résultat sans version
    #: n'est pas rejouable.
    version_moteur = models.CharField('Version du moteur', max_length=40,
                                      blank=True, default='')
    resultat = models.JSONField('Résultat du moteur', null=True, blank=True)

    cree_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: un compte supprimé n'efface pas la conception
        null=True, blank=True,
        related_name='calepinages_crees',
        verbose_name='Créé par',
    )

    class Meta:
        verbose_name = 'Calepinage'
        verbose_name_plural = 'Calepinages'
        ordering = ['-id']
        constraints = [
            # Un calepinage sans lead NI client est un document que personne ne
            # retrouve. La garantie est en BASE, pas dans une vue.
            models.CheckConstraint(
                condition=(models.Q(lead_id__isnull=False)
                           | models.Q(client__isnull=False)),
                name='calepinage_lead_ou_client'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='cal_cal_co_statut_idx'),
            models.Index(fields=['company', 'lead_id'],
                         name='cal_cal_co_lead_idx'),
            models.Index(fields=['company', 'appel_offre_id'],
                         name='cal_cal_co_ao_idx'),
            models.Index(fields=['company', '-created_at'],
                         name='cal_cal_co_cree_idx'),
        ]

    def __str__(self):
        return self.titre or f'Calepinage #{self.pk}'

    def clean(self):
        """Refuse, EN FRANÇAIS et en NOMMANT le champ, un pivot inexploitable."""
        erreurs = {}
        if self.lead_id is None and self.client_id is None:
            erreurs['client'] = (
                "Un calepinage doit être rattaché à un lead ou à un client : "
                "renseignez « Client » ou « Lead (identifiant) »."
            )
        if self.layout_hash and len(self.layout_hash) != 64:
            erreurs['layout_hash'] = (
                "L'empreinte du layout doit être un SHA-256 de 64 caractères "
                f"(reçu : {len(self.layout_hash)})."
            )
        if erreurs:
            raise ValidationError(erreurs)


class CalepinageVersion(TenantModel):
    """CAL8 — un instantané GELÉ de la conception, jamais réécrit.

    L'atelier ventes n'historise rien : ``Devis.roof_layout`` est écrasé à
    chaque enregistrement, donc personne ne peut revenir à l'état de la veille.
    Ici, chaque enregistrement SIGNIFICATIF (empreinte différente) dépose une
    version. Le COMPORTEMENT (quand écrire, comment purger) vit dans
    ``services/versions.py`` ; ce modèle n'est que le support.
    """

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: une version n'existe pas hors de son calepinage
        related_name='versions',
        verbose_name='Calepinage',
    )
    libelle = models.CharField('Libellé', max_length=200, blank=True,
                               default='')
    #: Copie GELÉE — jamais modifiée après création (garde dans le service).
    roof_layout = models.JSONField('Conception (gelée)', null=True, blank=True)
    layout_hash = models.CharField('Empreinte du layout', max_length=64,
                                   blank=True, default='')
    resultat = models.JSONField('Résultat (gelé)', null=True, blank=True)
    cree_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: l'historique survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_versions_creees',
        verbose_name='Créée par',
    )

    class Meta:
        verbose_name = 'Version de calepinage'
        verbose_name_plural = 'Versions de calepinage'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['calepinage', '-created_at'],
                         name='cal_ver_cal_cree_idx'),
        ]

    def __str__(self):
        return self.libelle or f'Version #{self.pk}'

    def save(self, *args, **kwargs):
        """CAL8 — un instantané n'est JAMAIS réécrit après sa création.

        C'est ce qui en fait une preuve : une version qu'on peut retoucher ne
        prouve rien. Le refus est ici, sur le modèle, et pas seulement dans le
        service — pour qu'aucun chemin d'écriture (admin, script, futur
        sérialiseur) ne puisse le contourner par distraction. Aucune migration
        n'est ajoutée : c'est du comportement, pas du schéma.
        """
        if self.pk is not None:
            raise ValidationError({
                'calepinage': (
                    "Une version de calepinage est un instantané gelé : elle "
                    "ne peut pas être modifiée après sa création. Enregistrez "
                    "une nouvelle version."
                ),
            })
        return super().save(*args, **kwargs)


class CalepinageVariante(TenantModel):
    """CAL9 — une option comparée ; UNE SEULE peut être retenue.

    La garantie « une seule retenue » est en BASE (``UniqueConstraint``
    conditionnelle, patron ``ao.VarianteCalepinage``). Le chemin d'écriture
    unique et atomique vit dans ``services/variantes.py`` : aucune vue, aucun
    sérialiseur n'écrit ``retenue`` directement.
    """

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: une variante n'existe pas hors de son calepinage
        related_name='variantes',
        verbose_name='Calepinage',
    )
    nom = models.CharField('Nom', max_length=160)
    roof_layout = models.JSONField('Conception', null=True, blank=True)
    layout_hash = models.CharField('Empreinte du layout', max_length=64,
                                   blank=True, default='')
    resultat = models.JSONField('Résultat du moteur', null=True, blank=True)
    retenue = models.BooleanField('Retenue', default=False)
    cree_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: la variante survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_variantes_creees',
        verbose_name='Créée par',
    )

    class Meta:
        verbose_name = 'Variante de calepinage'
        verbose_name_plural = 'Variantes de calepinage'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['calepinage'], condition=models.Q(retenue=True),
                name='uniq_variante_retenue_par_calepinage'),
        ]
        indexes = [
            models.Index(fields=['calepinage', 'retenue'],
                         name='cal_var_cal_ret_idx'),
        ]

    def __str__(self):
        return self.nom


class ParametresCalepinage(TenantModel):
    """CAL45 — LES réglages société du module : UNE base, sept extensions.

    Sept tâches du groupe voulaient chacune leur modèle de réglage (imagerie/
    pays, dégagements, zones-types, gabarits de disposition, presets, favoris
    matériel, gabarits de dossier) : sept modèles et sept migrations pour une
    même surface. Ici, UN enregistrement par société et une SECTION JSON par
    domaine. Chaque tâche suivante ÉTEND sa section — elle ne crée plus de
    modèle.

    ÉQUIVALENCE GARANTIE : une société sans réglage se comporte exactement
    comme aujourd'hui. Toutes les sections valent ``{}`` par défaut, et une
    section vide veut dire « comportement actuel », jamais « valeur nulle ».
    """

    #: Les sections ADMISES — source unique. Une clé inconnue est REFUSÉE en la
    #: nommant (on ne range pas un réglage dans un tiroir qui n'existe pas).
    SECTIONS = (
        'imagerie',            # CAL47 — fournisseur d'imagerie, pays
        'degagements',         # CAL71 — retraits de rive, allées
        'zones_types',         # CAL74 — zones réglementaires types
        'gabarits_disposition',  # CAL82 — gabarits de disposition
        'presets',             # CAL197 — presets de conception
        'favoris_materiel',    # CAL200 — matériel épinglé
        'gabarits_dossier',    # CAL190 — gabarits de dossier réglementaire
    )

    imagerie = models.JSONField('Imagerie et pays', default=dict, blank=True)
    degagements = models.JSONField('Dégagements', default=dict, blank=True)
    zones_types = models.JSONField('Zones types', default=dict, blank=True)
    gabarits_disposition = models.JSONField('Gabarits de disposition',
                                            default=dict, blank=True)
    presets = models.JSONField('Presets', default=dict, blank=True)
    favoris_materiel = models.JSONField('Favoris matériel', default=dict,
                                        blank=True)
    gabarits_dossier = models.JSONField('Gabarits de dossier', default=dict,
                                        blank=True)

    class Meta:
        verbose_name = 'Réglages de calepinage'
        verbose_name_plural = 'Réglages de calepinage'
        constraints = [
            # Un enregistrement par société : deux jeux de réglages pour une
            # même société, c'est un réglage qui s'applique « parfois ».
            models.UniqueConstraint(fields=['company'],
                                    name='uniq_parametres_calepinage_societe'),
        ]

    def __str__(self):
        return f'Réglages calepinage — {self.company_id}'

    @classmethod
    def sections_inconnues(cls, donnees):
        """Les clés de ``donnees`` qui ne sont pas des sections admises."""
        return sorted(set(donnees or {}) - set(cls.SECTIONS))

    def clean(self):
        """Chaque section est un OBJET — jamais une liste ni un scalaire."""
        erreurs = {}
        for section in self.SECTIONS:
            valeur = getattr(self, section, None)
            if valeur is None:
                continue
            if not isinstance(valeur, dict):
                erreurs[section] = (
                    f"La section « {section} » doit être un objet "
                    f"(reçu : {type(valeur).__name__})."
                )
        if erreurs:
            raise ValidationError(erreurs)
