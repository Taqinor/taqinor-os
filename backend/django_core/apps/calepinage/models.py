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
``apps.ventes.selectors`` : ce fichier n'importe aucun modèle étranger.
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

    #: CAL139 — LES POSTES DE PERTES du calepinage, EXPLICITES et SOURCÉS.
    #:
    #: Trois jeux de constantes se contredisaient dans le dépôt
    #: (``DEFAULT_LOSS_FACTORS`` côté ventes, la perte système et la perte
    #: « intégrée » du site public, les constantes de l'écran devis). Ici la
    #: perte n'est plus une constante : c'est une LISTE de postes, chacun avec
    #: sa valeur et sa SOURCE, éditable calepinage par calepinage. La SOMME de
    #: ces postes est exactement la valeur ``loss`` passée à PVGIS (CAL238) —
    #: un double comptage devient impossible par construction, parce qu'il n'y
    #: a qu'UNE addition et qu'elle est publiée.
    #:
    #: Forme : ``[{poste, libelle, pct, source, reference, mensuel}]``.
    #: ``mensuel`` (12 valeurs) n'existe que pour les postes saisonniers (la
    #: salissure) et la ``pct`` d'un poste mensuel est la MOYENNE de ses douze
    #: mois — le calcul vit dans ``services/pertes.py``, jamais ici.
    #:
    #: Liste VIDE = aucune perte renseignée, donc AUCUNE simulation possible
    #: (``politique_de_pertes`` refuse) : c'est voulu — un « 14 % au cas où »
    #: serait exactement le chiffre inventé que la règle fondateur interdit.
    #: Champ AJOUTÉ EN FIN DE CLASSE (migration ``0005``) : aucune société
    #: existante ne change de comportement en le recevant.
    pertes = models.JSONField('Postes de pertes', default=list, blank=True)

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
        if self.pertes is not None and not isinstance(self.pertes, list):
            # CAL139 — les postes se donnent en LISTE ORDONNÉE : un objet
            # indexé par nom de poste perdrait l'ordre d'affichage et
            # laisserait croire qu'un poste peut être écrit deux fois.
            erreurs['pertes'] = (
                "Les postes de pertes se donnent en liste ordonnée "
                f"(reçu : {type(self.pertes).__name__})."
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

    def save(self, *args, **kwargs):
        """CAL9 — ``retenue`` ne s'écrit QUE par le service de variantes.

        La contrainte de base interdit DEUX retenues ; elle n'interdit pas
        d'en laisser ZÉRO. C'est l'autre moitié du bug : un calepinage sans
        option choisie. Le chemin d'écriture unique
        (``services/variantes.py``) garantit les deux à la fois, et ce garde
        empêche de le contourner par distraction. Aucune migration : c'est du
        comportement, pas du schéma.
        """
        # Import du VERROU seul (``garde_retenue``, stdlib pure) et jamais du
        # service : ``models -> services.variantes -> apps.ventes.services ->
        # … -> les modèles d'une autre app`` ferait rougir CAL5 (mesuré).
        from .garde_retenue import (
            bascule_en_cours,
            refuser_ecriture_directe,
        )

        # Le garde vise l'ÉCRITURE de ``retenue``, pas la simple existence
        # d'une variante retenue : un ``save(update_fields=[…])`` qui ne nomme
        # PAS ``retenue`` (renommer une variante déjà retenue, l'horodater)
        # n'écrit pas ce champ et n'a donc rien à contourner. Sans cette
        # lecture d'``update_fields``, le garde refusait toute retouche
        # partielle d'une variante retenue — un refus qu'aucune règle ne
        # demande et que le service lui-même ne pouvait pas lever.
        champs = kwargs.get('update_fields')
        ecrit_retenue = champs is None or 'retenue' in champs
        if ecrit_retenue and self.retenue and not bascule_en_cours():
            raise ValidationError({'retenue': refuser_ecriture_directe()})
        return super().save(*args, **kwargs)


class PhotoSite(TenantModel):
    """CAL52 — une photo drone / oblique / sol du SITE, rattachée au pivot.

    LE CONSTAT
    ----------
    La seule photo réelle acceptée jusqu'ici était celle de la visite terrain
    (``VisiteTerrain.photo_toit_key``, bascule ``rp9-photo-toit-toggle``) :
    rien ne permettait d'importer une photo drone dans un calepinage SANS
    devis. Parité marché : la mesure de toiture depuis imagerie oblique/drone.

    LES TROIS DÉCISIONS GRAVÉES ICI
    -------------------------------
    * **AUCUN ``FileField``.** Le fichier vit dans ``records.Attachment``
      (primitive plateforme, ARC26 — ``check_platform`` refuse tout nouveau
      champ fichier), stocké dans le MÊME magasin MinIO que ``roof-image``
      (CAL19) par les fonctions minces d'``apps.ventes.services``. Ce modèle
      ne porte que ce que la pièce jointe générique ne sait pas dire d'une
      photo de site.
    * **``prise_le`` est SAISIE, jamais devinée.** La date de dépôt d'un
      fichier n'est pas la date de prise de vue : une photo versée six mois
      après le vol daterait le toit du mauvais jour. Le champ est donc
      OBLIGATOIRE, et une date future est refusée en la nommant.
    * **``calage`` attend CAL53.** Le calage (géoréférencement de la photo)
      arrive dans une tâche suivante ; la colonne est posée ICI, vide, pour
      que CAL53 n'ait pas à rouvrir une migration sur ce modèle. Vide veut
      dire « photo non calée », jamais « calage nul ».

    AUCUNE PHOTOGRAMMÉTRIE SERVEUR : ce module range une photo, il ne la
    mesure pas.
    """

    class Genre(models.TextChoices):
        DRONE = 'drone', 'Drone'
        OBLIQUE = 'oblique', 'Oblique (aérienne)'
        SOL = 'sol', 'Depuis le sol'

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: une photo de site n'existe pas hors de son calepinage
        related_name='photos_site',
        verbose_name='Calepinage',
    )
    #: La pièce jointe GÉNÉRIQUE (``records``, app de fondation) qui porte le
    #: fichier : clé MinIO, nom, taille, mime. Jamais un second magasin.
    attachment = models.ForeignKey(
        'records.Attachment',
        on_delete=models.CASCADE,  # on_delete: sans son fichier, la fiche photo ne décrit plus rien
        related_name='photos_site_calepinage',
        verbose_name='Pièce jointe',
    )
    genre = models.CharField('Genre', max_length=10, choices=Genre.choices,
                             default=Genre.DRONE)
    #: SAISIE — jamais la date de dépôt (voir la docstring).
    prise_le = models.DateField('Prise de vue le')
    legende = models.CharField('Légende', max_length=200, blank=True,
                               default='')
    #: CAL53 — calage/géoréférencement, posé plus tard. Vide = non calée.
    calage = models.JSONField('Calage', null=True, blank=True)
    #: CAL64 — le relevé terrain auquel cette photo appartient, s'il y en a
    #: un. Nullable et additif : une photo déposée seule (CAL52) reste une
    #: photo de première classe. La chaîne est déclarée en TEXTE pour que
    #: ``PhotoSite`` n'ait pas à être défini après ``ReleveTerrain``.
    releve = models.ForeignKey(
        'calepinage.ReleveTerrain',
        on_delete=models.SET_NULL,  # on_delete: une photo survit à la suppression de son relevé
        null=True, blank=True,
        related_name='photos',
        verbose_name='Relevé terrain',
    )
    ajoutee_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: la photo survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_photos_site',
        verbose_name='Ajoutée par',
    )

    class Meta:
        verbose_name = 'Photo de site'
        verbose_name_plural = 'Photos de site'
        ordering = ['-prise_le', '-id']
        indexes = [
            models.Index(fields=['calepinage', '-prise_le'],
                         name='cal_pho_cal_prise_idx'),
            models.Index(fields=['company', '-created_at'],
                         name='cal_pho_co_cree_idx'),
        ]

    def __str__(self):
        return self.legende or f'Photo de site #{self.pk}'

    def clean(self):
        """Refuse, en français et en NOMMANT le champ, une photo indatable."""
        from django.utils import timezone

        erreurs = {}
        if self.prise_le is None:
            erreurs['prise_le'] = (
                "La date de prise de vue est obligatoire : elle est SAISIE, "
                "jamais déduite de la date d'import."
            )
        elif self.prise_le > timezone.localdate():
            erreurs['prise_le'] = (
                "La date de prise de vue ne peut pas être dans le futur "
                f"(reçu : {self.prise_le:%d/%m/%Y})."
            )
        if erreurs:
            raise ValidationError(erreurs)


class ReleveTerrain(TenantModel):
    """CAL64 — un relevé terrain MOBILE : photos, cotes saisies, boussole.

    LE CONSTAT
    ----------
    Le relevé terrain existait côté visite technique mais n'alimentait que la
    TEXTURE du toit (VT13) ; l'AO a bien un modèle de relevé et de chaînes de
    cotes (``apps/ao/models.py``) que le calepinage ne peut pas lire (les deux
    apps sont mutuellement découplées, contrat import-linter). Le module avait
    donc besoin de SON entrée de relevé — sans dupliquer le SOLVEUR, qui vit
    dans le noyau pur (``core/calepinage/solveur_cotes.py``).

    LES TROIS DÉCISIONS
    -------------------
    * **AUCUNE COTE INVENTÉE EN SILENCE.** Les chaînes saisies sont résolues
      par ``core.calepinage.solveur_cotes.resoudre`` : une cote manquante est
      DÉDUITE par fermeture et marquée ``A_CONFIRMER`` — le résultat le dit,
      l'écran l'affiche, et personne ne croit avoir mesuré ce qu'il a déduit.
    * **UN AZIMUT SANS PRÉCISION DÉCLARÉE N'EST PAS UN AZIMUT.** Une boussole
      de téléphone se trompe de plusieurs degrés ; publier sa valeur nue la
      ferait lire comme une mesure exacte. ``precision_azimut_deg`` est donc
      OBLIGATOIRE dès qu'un azimut est saisi (refus nommant le champ).
    * **LES PHOTOS SONT CELLES DE CAL52.** Un relevé pointe des ``PhotoSite``
      existantes (``PhotoSite.releve``) : un seul magasin, une seule fiche
      photo, jamais un second stockage « pour le mobile ».

    ``geometrie`` est le RÉSULTAT résolu, recalculé à chaque enregistrement ;
    ``chaines`` reste la SAISIE brute, jamais réécrite par le solveur.
    """

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: un relevé n'existe pas hors de son calepinage
        related_name='releves_terrain',
        verbose_name='Calepinage',
    )
    #: La SAISIE brute : ``[{nom, tolerance_m, total_mesure, cotes:[…]}]``.
    chaines = models.JSONField('Chaînes de cotes (saisie)', default=list,
                               blank=True)
    #: Le RÉSULTAT du solveur du noyau — jamais recodé ici.
    geometrie = models.JSONField('Géométrie résolue', null=True, blank=True)
    azimut_boussole_deg = models.FloatField('Azimut boussole (°)', null=True,
                                            blank=True)
    #: SA précision DÉCLARÉE — obligatoire dès qu'un azimut est saisi.
    precision_azimut_deg = models.FloatField('Précision de l’azimut (°)',
                                             null=True, blank=True)
    #: SAISIE, jamais la date d'envoi (le terrain et le réseau ne coïncident
    #: pas : un relevé synchronisé le lendemain daterait du mauvais jour).
    releve_le = models.DateField('Relevé le')
    notes = models.TextField('Notes de terrain', blank=True, default='')
    releve_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: le relevé survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_releves_terrain',
        verbose_name='Relevé par',
    )

    class Meta:
        verbose_name = 'Relevé terrain'
        verbose_name_plural = 'Relevés terrain'
        ordering = ['-releve_le', '-id']
        indexes = [
            models.Index(fields=['calepinage', '-releve_le'],
                         name='cal_rel_cal_date_idx'),
            models.Index(fields=['company', '-created_at'],
                         name='cal_rel_co_cree_idx'),
        ]

    def __str__(self):
        return f'Relevé du {self.releve_le:%d/%m/%Y}' if self.releve_le \
            else f'Relevé #{self.pk}'

    def clean(self):
        """Refuse, en français et en NOMMANT le champ, un relevé indéfendable."""
        from django.utils import timezone

        erreurs = {}
        if self.releve_le is None:
            erreurs['releve_le'] = (
                "La date du relevé est obligatoire : elle est SAISIE, jamais "
                "déduite de la date d'envoi."
            )
        elif self.releve_le > timezone.localdate():
            erreurs['releve_le'] = (
                "La date du relevé ne peut pas être dans le futur "
                f"(reçu : {self.releve_le:%d/%m/%Y})."
            )
        if self.azimut_boussole_deg is not None:
            if not 0.0 <= float(self.azimut_boussole_deg) < 360.0:
                erreurs['azimut_boussole_deg'] = (
                    "L'azimut boussole se compte de 0 à 360° depuis le nord "
                    f"(reçu : {self.azimut_boussole_deg})."
                )
            if self.precision_azimut_deg is None:
                erreurs['precision_azimut_deg'] = (
                    "Un azimut relevé à la boussole doit porter sa précision "
                    "déclarée (± degrés) : sans elle, il se lirait comme une "
                    "mesure exacte."
                )
            elif float(self.precision_azimut_deg) < 0:
                erreurs['precision_azimut_deg'] = (
                    "La précision de l'azimut s'exprime en degrés positifs "
                    f"(reçu : {self.precision_azimut_deg})."
                )
        if erreurs:
            raise ValidationError(erreurs)


class ProfilTypeConsommation(TenantModel):
    """CAL149 — un profil de consommation TYPE, SAISI par la société.

    LE CONSTAT
    ----------
    Les profils de charge vivaient en CONSTANTES : ``DAY_USAGE_DEFAULTS`` et
    ``COMMERCIAL_DAY_SHARE`` côté écran devis, ``_scaled_typical_load(…,
    'residential')`` côté ``apps/ventes/solar_design.py``. Aucun n'est
    sourçable, aucun n'est modifiable par la société, et aucun ne dit d'où il
    sort — alors qu'un profil de charge décide du taux d'autoconsommation,
    donc de la taille du champ et de la batterie vendus au client.

    LES TROIS DÉCISIONS GRAVÉES ICI
    -------------------------------
    * **``provenance`` est OBLIGATOIRE.** Un profil sans provenance écrite est
      REFUSÉ, en nommant le champ. C'est la garantie centrale de la tâche :
      « aucun profil livré sans provenance écrite ». Les profils codés en dur
      du dépôt restent en repli, mais ils sont ÉTIQUETÉS « hypothèse interne »
      partout où ils servent (``services/profils_types.py``) — jamais
      présentés comme une mesure.
    * **La courbe est 24 h × SAISON.** ``courbe`` vaut ``{saison: [24
      valeurs]}`` : une maison marocaine ne consomme pas en août comme en
      janvier, et un profil unique annuel effacerait précisément l'écart qui
      décide de l'autoconsommation. Une seule saison (``annuel``) reste
      admise — c'est un choix DÉCLARÉ, pas un défaut caché.
    * **Les valeurs sont des POIDS relatifs**, normalisés à la lecture
      (``services/profils_types.py``) : la société saisit la forme de sa
      journée, le module la cale sur l'énergie réellement connue. Enregistrer
      des kWh absolus ferait d'un profil TYPE la consommation d'UN client.

    Modèle ADDITIF (migration ``0006``) : une société sans profil se comporte
    exactement comme avant — les profils de repli, étiquetés, restent servis.
    """

    #: Les saisons ADMISES d'une courbe. ``annuel`` = une seule courbe pour
    #: toute l'année, DÉCLARÉE comme telle.
    SAISONS = ('annuel', 'hiver', 'printemps', 'ete', 'automne')

    #: Les heures d'une journée — une courbe en a exactement 24.
    HEURES = 24

    class Famille(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        COMMERCIAL = 'commercial', 'Commercial / tertiaire'
        INDUSTRIEL = 'industriel', 'Industriel'
        AGRICOLE = 'agricole', 'Agricole'
        AUTRE = 'autre', 'Autre'

    #: La clé employée par les écrans et les calculs (stable, minuscule).
    cle = models.SlugField('Clé', max_length=60)
    libelle = models.CharField('Libellé', max_length=160)
    famille = models.CharField('Famille', max_length=16,
                               choices=Famille.choices,
                               default=Famille.RESIDENTIEL)
    #: ``{saison: [24 poids]}`` — voir la docstring.
    courbe = models.JSONField('Courbe 24 h par saison', default=dict)
    #: OBLIGATOIRE — d'où vient ce profil (relevé, facturier, comptage,
    #: mesure sur site, étude). Un profil sans provenance est refusé.
    provenance = models.TextField('Provenance')
    actif = models.BooleanField('Actif', default=True)
    saisi_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: le profil survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_profils_types',
        verbose_name='Saisi par',
    )

    class Meta:
        verbose_name = 'Profil type de consommation'
        verbose_name_plural = 'Profils types de consommation'
        ordering = ['famille', 'libelle', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'cle'],
                name='uniq_profil_type_conso_par_societe'),
        ]
        indexes = [
            models.Index(fields=['company', 'famille'],
                         name='cal_pro_co_fam_idx'),
        ]

    def __str__(self):
        return self.libelle or self.cle

    def clean(self):
        """Refuse, EN FRANÇAIS et en NOMMANT le champ, un profil indéfendable."""
        erreurs = {}
        if not (self.provenance or '').strip():
            erreurs['provenance'] = (
                "La provenance est obligatoire : un profil type sans "
                "provenance écrite ne peut être ni défendu devant un client "
                "ni distingué d'une hypothèse interne."
            )
        if not isinstance(self.courbe, dict) or not self.courbe:
            erreurs['courbe'] = (
                "La courbe attend au moins une saison "
                "(« {saison: [24 valeurs]} »)."
            )
        else:
            for saison, valeurs in self.courbe.items():
                if saison not in self.SAISONS:
                    erreurs['courbe'] = (
                        f"Saison inconnue : « {saison} ». Saisons admises : "
                        f"{', '.join(self.SAISONS)}."
                    )
                    break
                if not isinstance(valeurs, (list, tuple)) \
                        or len(valeurs) != self.HEURES:
                    erreurs['courbe'] = (
                        f"La courbe de la saison « {saison} » attend "
                        f"exactement {self.HEURES} valeurs, une par heure."
                    )
                    break
                try:
                    nombres = [float(valeur) for valeur in valeurs]
                except (TypeError, ValueError):
                    erreurs['courbe'] = (
                        f"La courbe de la saison « {saison} » contient une "
                        "valeur illisible."
                    )
                    break
                if any(nombre < 0 for nombre in nombres):
                    erreurs['courbe'] = (
                        f"La courbe de la saison « {saison} » ne peut pas "
                        "porter d'heure négative."
                    )
                    break
                if sum(nombres) <= 0:
                    erreurs['courbe'] = (
                        f"La courbe de la saison « {saison} » est entièrement "
                        "nulle : elle ne décrit aucune journée."
                    )
                    break
        if erreurs:
            raise ValidationError(erreurs)


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
        'norme_electrique',    # CAL130 — norme applicable + coefficients
        'lestage',             # CAL163 — paramètres de lestage SAISIS
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

    #: CAL130 — LA NORME ÉLECTRIQUE APPLICABLE et ses coefficients SAISIS.
    #:
    #: ``core/electrique`` cite des sources françaises en dur (ampacité
    #: « IEC 60364-5-52 tableau B.52.4, reprise NF C 15-100 », chute DC cible
    #: 1,5 % / max 3 % « UTE C 15-712-1 », parafoudre au-delà de 10 m, DDR
    #: 300 mA en régime TT) et le moteur rappelle lui-même qu'« aucun texte
    #: normatif marocain n'est présent dans ce dépôt ».
    #:
    #: RÈGLE D5 (fondateur) : pour ``pays=ma``, AUCUNE norme n'est supposée.
    #: Tant que la société n'en a pas choisi une, le calcul concerné est OMIS
    #: avec sa mention — jamais « NF C 15-100 » imprimée sur un chantier
    #: casablancais. Le jeu français ne s'applique que s'il est explicitement
    #: sélectionné (naturellement pour ``pays=fr``).
    #:
    #: Le champ est AJOUTÉ EN FIN DE CLASSE (migration ``0002``) : la section
    #: vide ``{}`` veut dire « aucune norme choisie », ce qui est exactement
    #: le comportement d'aujourd'hui — aucune société existante ne change de
    #: comportement en recevant ce champ.
    norme_electrique = models.JSONField('Norme électrique applicable',
                                        default=dict, blank=True)

    #: CAL163 — LES PARAMÈTRES DE LESTAGE, tous SAISIS avec leur source.
    #:
    #: Le moteur ne fait « aucune vérification de tenue mécanique » et « aucun
    #: texte normatif marocain n'est présent dans ce dépôt » : publier ici un
    #: coefficient de vent ou de neige « par défaut » serait exactement le
    #: chiffre inventé que la règle fondateur interdit. La société saisit donc
    #: vitesse de vent de référence, catégorie et coefficient de terrain,
    #: coefficients de pression, charge de neige, frottement — et jusqu'à la
    #: masse volumique de l'air et l'accélération de la pesanteur — CHACUN
    #: avec la référence du texte dont il sort (``{valeur, source}``).
    #:
    #: Section VIDE = aucun paramètre saisi, donc AUCUN résultat calculé : la
    #: feuille dit « paramètres à saisir » et ne publie rien. C'est le
    #: comportement d'aujourd'hui (aucun lestage n'existait), donc aucune
    #: société existante ne change de comportement en recevant ce champ
    #: (AJOUTÉ EN FIN DE CLASSE, migration ``0007``).
    lestage = models.JSONField('Paramètres de lestage', default=dict,
                               blank=True)

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


class GabaritDossierReglementaire(TenantModel):
    """CAL190 — LE GABARIT d'un dossier réglementaire, FOURNI par la société.

    LE CONSTAT
    ----------
    La fabrique documentaire AO ne connaît que les pièces d'un appel d'offres
    (``apps/ao/fabrique/gabarits.py``) ; aucun rail réglementaire n'existe
    dans ce dépôt, alors que la mémoire fondateur du 20/08/2026 désigne les
    rails FR (DP mairie, Enedis, Consuel) comme un GAP produit prioritaire.

    LA RÈGLE QUI GOUVERNE CE MODÈLE — AUCUNE PIÈCE INVENTÉE
    -------------------------------------------------------
    L'ERP ne fabrique AUCUN formulaire officiel qu'il n'a pas reçu. Le
    gabarit, l'intitulé du dossier, la liste de ses pièces et la référence de
    chaque pièce (numéro de CERFA, notice Consuel, documentation Enedis,
    circulaire marocaine…) sont **SAISIS ou DÉPOSÉS par la société** ; rien
    n'est reproduit de mémoire, et une société sans gabarit déposé ne voit
    **aucun dossier proposé** — pas de gabarit fictif en base.

    * ``fichier`` est une ``records.Attachment`` (primitive plateforme, ARC26
      — ``check_platform`` refuse tout nouveau champ fichier) : le fichier de
      gabarit vit dans le magasin générique, jamais dans un second magasin.
      Vide = gabarit DÉCLARÉ mais NON DÉPOSÉ : le dossier reste VISIBLE, avec
      « gabarit manquant » en clair (le masquer ferait croire que le dossier
      n'existe pas, alors que c'est le fichier qui manque — contrat CAL247).
    * ``pieces_attendues`` et ``champs`` sont des LISTES ORDONNÉES de
      descripteurs saisis ; chaque pièce porte sa ``source_reference``, et
      une pièce sans référence est refusée en la nommant.
    * ``pays`` est le code ISO 3166-1 alpha-2 (``ma``, ``fr``) : un gabarit
      appartient à un pays, parce qu'un dossier de raccordement n'a de sens
      que dans le sien.
    """

    #: Les CLÉS du calepinage qu'un champ de gabarit peut demander au serveur
    #: de préremplir (CAL191). Une clé hors de cette liste est refusée : un
    #: champ qui demande une donnée que le serveur ne sait pas produire
    #: resterait « à compléter » sans que personne ne sache pourquoi.
    CLES_PREREMPLISSAGE = (
        'societe_nom', 'client_nom', 'adresse', 'puissance_kwc',
        'nombre_modules', 'orientation_deg', 'inclinaison_deg',
    )

    #: Les types de champ admis (ils décrivent la SAISIE, pas une valeur).
    TYPES_CHAMP = ('texte', 'nombre', 'date')

    pays = models.CharField('Pays', max_length=2, db_index=True)
    code = models.SlugField('Code', max_length=60)
    genre = models.SlugField('Genre', max_length=40, blank=True, default='')
    intitule = models.CharField('Intitulé', max_length=200)
    #: ``[{code, intitule, obligatoire, source_reference}]`` — SAISIE.
    pieces_attendues = models.JSONField('Pièces attendues', default=list,
                                        blank=True)
    #: ``[{code, libelle, type, obligatoire, cle_calepinage}]`` — SAISIE.
    champs = models.JSONField('Champs du gabarit', default=list, blank=True)
    #: Le FICHIER de gabarit déposé par la société (``records``, ARC26).
    fichier = models.ForeignKey(
        'records.Attachment',
        on_delete=models.SET_NULL,  # on_delete: le gabarit survit au retrait de son fichier (il devient « à redéposer »)
        null=True, blank=True,
        related_name='gabarits_dossier_calepinage',
        verbose_name='Fichier de gabarit',
    )
    version = models.CharField('Version', max_length=20, blank=True,
                               default='')
    actif = models.BooleanField('Actif', default=True)
    depose_le = models.DateTimeField('Déposé le', null=True, blank=True)
    depose_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: le gabarit survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_gabarits_dossier',
        verbose_name='Déposé par',
    )

    class Meta:
        verbose_name = 'Gabarit de dossier réglementaire'
        verbose_name_plural = 'Gabarits de dossier réglementaire'
        ordering = ['pays', 'intitule', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'pays', 'code'],
                name='uniq_gabarit_dossier_par_societe_pays'),
        ]
        indexes = [
            models.Index(fields=['company', 'pays', 'actif'],
                         name='cal_gab_co_pays_idx'),
        ]

    def __str__(self):
        return self.intitule or self.code

    @property
    def fichier_present(self):
        """Le fichier de gabarit a-t-il été déposé ? (jamais deviné)."""
        return self.fichier_id is not None

    def clean(self):
        """Refuse, EN FRANÇAIS et en NOMMANT le champ, un gabarit indéfendable."""
        erreurs = {}
        pays = (self.pays or '').strip().lower()
        if len(pays) != 2 or not pays.isalpha():
            erreurs['pays'] = (
                "Le pays est un code à deux lettres (ISO 3166-1 alpha-2), "
                f"par exemple « ma » ou « fr » (reçu : « {self.pays} »)."
            )
        else:
            self.pays = pays
        if not (self.intitule or '').strip():
            erreurs['intitule'] = (
                "L'intitulé du dossier est obligatoire : il est PORTÉ par le "
                "gabarit de la société, jamais inventé par l'ERP."
            )
        erreur_pieces = self._erreur_pieces()
        if erreur_pieces:
            erreurs['pieces_attendues'] = erreur_pieces
        erreur_champs = self._erreur_champs()
        if erreur_champs:
            erreurs['champs'] = erreur_champs
        if erreurs:
            raise ValidationError(erreurs)

    def _erreur_pieces(self):
        if not isinstance(self.pieces_attendues, list):
            return ("Les pièces attendues se donnent en liste ordonnée "
                    f"(reçu : {type(self.pieces_attendues).__name__}).")
        codes = set()
        for rang, piece in enumerate(self.pieces_attendues, start=1):
            if not isinstance(piece, dict):
                return (f"La pièce n°{rang} doit être un objet "
                        f"(reçu : {type(piece).__name__}).")
            code = str(piece.get('code') or '').strip()
            if not code:
                return f"La pièce n°{rang} doit porter un code."
            if code in codes:
                return f"Deux pièces portent le même code : « {code} »."
            codes.add(code)
            if not str(piece.get('intitule') or '').strip():
                return (f"La pièce « {code} » doit porter son intitulé, tel "
                        "que le gabarit déposé le nomme.")
            if not str(piece.get('source_reference') or '').strip():
                return (
                    f"La pièce « {code} » doit porter sa SOURCE (référence "
                    "CERFA, notice Consuel, documentation Enedis, texte "
                    "marocain…) : aucune liste de pièces n'est reproduite de "
                    "mémoire."
                )
        return ''

    def _erreur_champs(self):
        if not isinstance(self.champs, list):
            return ("Les champs du gabarit se donnent en liste ordonnée "
                    f"(reçu : {type(self.champs).__name__}).")
        codes = set()
        for rang, champ in enumerate(self.champs, start=1):
            if not isinstance(champ, dict):
                return (f"Le champ n°{rang} doit être un objet "
                        f"(reçu : {type(champ).__name__}).")
            code = str(champ.get('code') or '').strip()
            if not code:
                return f"Le champ n°{rang} doit porter un code."
            if code in codes:
                return f"Deux champs portent le même code : « {code} »."
            codes.add(code)
            if not str(champ.get('libelle') or '').strip():
                return f"Le champ « {code} » doit porter son libellé."
            type_champ = str(champ.get('type') or 'texte').strip()
            if type_champ not in self.TYPES_CHAMP:
                return (f"Type de champ inconnu pour « {code} » : "
                        f"« {type_champ} ». Types admis : "
                        f"{', '.join(self.TYPES_CHAMP)}.")
            cle = champ.get('cle_calepinage')
            if cle and cle not in self.CLES_PREREMPLISSAGE:
                return (
                    f"Le champ « {code} » demande un préremplissage inconnu : "
                    f"« {cle} ». Clés admises : "
                    f"{', '.join(self.CLES_PREREMPLISSAGE)}."
                )
        return ''


class DossierReglementaire(TenantModel):
    """CAL190 — UN dossier réglementaire d'UN calepinage, sur SON gabarit.

    L'état du dossier (champs saisis, pièces jointes, génération) vit ici ;
    la FORME du dossier vit sur le gabarit de la société. Un dossier par
    (calepinage, gabarit) : deux dossiers sur le même gabarit seraient deux
    vérités pour une même démarche.

    ``document_id`` est OPAQUE (``PositiveIntegerField``) — le document GED
    produit est atteint par les SERVICES de la GED
    (``apps.ged.services``), jamais par une FK vers ses modèles : c'est ce
    que le contrat import-linter du module verrouille.
    """

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: un dossier n'existe pas hors de son calepinage
        related_name='dossiers_reglementaires',
        verbose_name='Calepinage',
    )
    gabarit = models.ForeignKey(
        GabaritDossierReglementaire,
        on_delete=models.PROTECT,  # on_delete: un gabarit utilisé par un dossier ne disparaît jamais sous lui
        related_name='dossiers',
        verbose_name='Gabarit',
    )
    #: ``{code_champ: valeur}`` — la SAISIE de l'utilisateur, jamais un
    #: préremplissage : le prérempli est recalculé à la lecture (CAL191).
    champs_saisis = models.JSONField('Champs saisis', default=dict,
                                     blank=True)
    #: ``{code_piece: {attachment_id, depose_le}}`` — les pièces JOINTES.
    pieces_jointes = models.JSONField('Pièces jointes', default=dict,
                                      blank=True)
    genere_le = models.DateTimeField('Généré le', null=True, blank=True)
    #: Identifiant OPAQUE du document GED produit (jamais une FK ``ged``).
    document_id = models.PositiveIntegerField('Document (identifiant)',
                                              null=True, blank=True)

    class Meta:
        verbose_name = 'Dossier réglementaire'
        verbose_name_plural = 'Dossiers réglementaires'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['calepinage', 'gabarit'],
                name='uniq_dossier_reglementaire_par_gabarit'),
        ]
        indexes = [
            models.Index(fields=['company', 'calepinage'],
                         name='cal_dos_co_cal_idx'),
        ]

    def __str__(self):
        return f'{self.gabarit} — {self.calepinage}'

    def clean(self):
        """Refuse, en français, un dossier incohérent avec son gabarit."""
        erreurs = {}
        if not isinstance(self.champs_saisis, dict):
            erreurs['champs_saisis'] = (
                "Les champs saisis se donnent en objet "
                f"(reçu : {type(self.champs_saisis).__name__})."
            )
        if not isinstance(self.pieces_jointes, dict):
            erreurs['pieces_jointes'] = (
                "Les pièces jointes se donnent en objet "
                f"(reçu : {type(self.pieces_jointes).__name__})."
            )
        if erreurs:
            raise ValidationError(erreurs)


class PoseReelle(TenantModel):
    """CAL212 — LE POSÉ RÉEL d'un pan, SAISI sur le chantier.

    LE CONSTAT
    ----------
    La capture terrain existe (``apps/installations/field_capture.py``,
    ``models_field.py``) mais ne porte AUCUNE notion de modules posés vs
    prévus : personne ne pouvait dire, après la pose, si le chantier avait
    suivi la variante retenue.

    LES DEUX DÉCISIONS GRAVÉES ICI
    ------------------------------
    * **L'ÉCART EST UNE SOUSTRACTION DE DEUX SAISIES RÉELLES**, jamais une
      estimation : le PRÉVU vient de la variante RETENUE du calepinage
      (CAL9/CAL209) et le POSÉ de cette table. Un pan sans saisie n'affiche
      AUCUN écart — pas un zéro rassurant (``services/asbuilt.py``).
    * **``releve_le`` est SAISIE**, jamais la date de synchronisation : le
      terrain et le réseau ne coïncident pas (même règle que ``PhotoSite`` et
      ``ReleveTerrain``), et une pose synchronisée le lendemain daterait du
      mauvais jour.

    ``ecarts_position`` est un TEXTE LIBRE : personne ne mesure au chantier
    des décalages au millimètre, et un champ numérique inviterait à inventer
    une précision que la saisie n'a pas.
    """

    calepinage = models.ForeignKey(
        Calepinage,
        on_delete=models.CASCADE,  # on_delete: un relevé de pose n'existe pas hors de son calepinage
        related_name='poses_reelles',
        verbose_name='Calepinage',
    )
    #: Le LIBELLÉ du pan, tel que le document le nomme (``label`` ou ``id``) —
    #: jamais un index de tableau, qui changerait au premier pan redessiné.
    pan = models.CharField('Pan', max_length=120)
    modules_poses = models.PositiveIntegerField('Modules réellement posés')
    ecarts_position = models.TextField("Écarts de position (texte libre)",
                                       blank=True, default='')
    releve_le = models.DateField('Relevé le')
    releve_par = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.SET_NULL,  # on_delete: le relevé survit au départ de son auteur
        null=True, blank=True,
        related_name='calepinage_poses_reelles',
        verbose_name='Relevé par',
    )

    class Meta:
        verbose_name = 'Pose réelle (as-built)'
        verbose_name_plural = 'Poses réelles (as-built)'
        ordering = ['pan', 'id']
        constraints = [
            # Un seul relevé par pan : deux comptes posés pour un même pan,
            # c'est un écart qui dépend de la ligne qu'on regarde.
            models.UniqueConstraint(
                fields=['calepinage', 'pan'],
                name='uniq_pose_reelle_par_pan'),
        ]
        indexes = [
            models.Index(fields=['company', 'calepinage'],
                         name='cal_pos_co_cal_idx'),
        ]

    def __str__(self):
        return f'{self.pan} — {self.modules_poses} module(s)'

    def clean(self):
        """Refuse, EN FRANÇAIS et en NOMMANT le champ, une saisie indatable."""
        from django.utils import timezone

        erreurs = {}
        if not (self.pan or '').strip():
            erreurs['pan'] = (
                "Le pan est obligatoire : un compte posé qui ne dit pas SUR "
                "QUEL PAN il porte ne se compare à rien."
            )
        if self.releve_le is None:
            erreurs['releve_le'] = (
                "La date du relevé est obligatoire : elle est SAISIE, jamais "
                "déduite de la date de synchronisation."
            )
        elif self.releve_le > timezone.localdate():
            erreurs['releve_le'] = (
                "La date du relevé ne peut pas être dans le futur "
                f"(reçu : {self.releve_le:%d/%m/%Y})."
            )
        if erreurs:
            raise ValidationError(erreurs)
