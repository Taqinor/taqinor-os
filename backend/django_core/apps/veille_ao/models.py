"""Modèles du module « Veille appels d'offres » (``apps.veille_ao``).

Tout modèle ici hérite de ``core.models.TenantModel`` (FK ``company`` +
``created_at``/``updated_at``, ARC1) — jamais une FK ``company`` recodée.

Le couplage vers ``apps.ao`` se fait par **entier opaque**, jamais par FK :
c'est ce qui garde les deux apps découplées (contrat import-linter) et laisse
la chaîne de migrations d'``apps.ao`` mono-écrivain pour le groupe AOF.
"""
from django.db import models

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
