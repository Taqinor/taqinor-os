"""Catalogue « Réalisations » de la société — ordre fondateur du 08/09/2026.

POURQUOI. La touche J4 du suivi après devis (`j4_preuve`) promettait une
PREUVE : « une installation comparable à la vôtre, posée en [mois] à
[ville] ». Les deux crochets se remplissaient à la main, aucun lien n'était
joint — la touche n'apportait donc rien de vérifiable. Ce référentiel est le
catalogue des installations RÉELLES de la société : le rendu du message y
choisit tout seul celle de la MÊME ville que le lead (à défaut la plus
proche), et envoie le lien de sa page publique.

RÈGLES FONDATRICES, non négociables :

  * **une réalisation = UNE installation réelle.** Jamais un montage de
    plusieurs chantiers : la ville, le mois et la puissance décrivent un seul
    ouvrage, celui que le client peut aller voir ;
  * **zéro chiffre inventé.** `puissance_kwc` et `mise_en_service` sont
    NULLABLES : un champ qu'on ne connaît pas reste VIDE, et la phrase qui le
    porterait est OMISE au rendu (mécanisme MRY13
    `crm.services._omettre_phrases_incompletes`) — jamais un défaut forfaitaire.

La `ville` est canonisée à l'ENREGISTREMENT par le gazetier
(`villes_resolution.corriger_ville`, VREF 07/09/2026) : « belksiri » saisi à la
main devient « Mechraa Bel Ksiri », donc la comparaison avec la ville du lead
(canonisée par le même gazetier) se fait sur le même nom. Un texte que le
gazetier ne reconnaît pas est CONSERVÉ tel quel — on ne devine pas une ville.

`mise_en_service` est ramenée au PREMIER JOUR DU MOIS : le message ne dit
jamais mieux que le mois (« posée en juillet 2026 »), et stocker un jour
précis laisserait croire à une exactitude qu'on n'affiche pas.

Socle ARC1 : `TenantModel` (FK `company` + `created_at`/`updated_at`). La
date de création exposée par l'API sous le nom `date_creation` est
`created_at` du socle — aucune colonne d'horodatage dupliquée.
"""
from django.db import models

from core.models import TenantModel

from .villes_resolution import corriger_ville


class Realisation(TenantModel):
    """UNE installation réelle de la société, avec sa page publique."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='realisations',
        verbose_name='Société')
    titre = models.CharField(
        'Titre', max_length=120,
        help_text="Nom de l'installation, ex. « Villa à Bouskoura ».")
    # Nom CANONIQUE du gazetier quand il reconnaît le texte saisi (voir
    # ``save``) ; sinon le texte tel quel — jamais une ville devinée.
    ville = models.CharField(
        'Ville', max_length=80,
        help_text='Ville de la réalisation. Corrigée automatiquement quand '
                  'elle est reconnue (« belksiri » → « Mechraa Bel Ksiri »).')
    # Puissance crête RÉELLE de l'ouvrage. Vide tant qu'elle n'est pas connue
    # (règle « zéro chiffre inventé ») — elle sert à départager deux
    # réalisations d'une même ville, jamais à remplir un message.
    puissance_kwc = models.DecimalField(
        'Puissance (kWc)', max_digits=6, decimal_places=2,
        null=True, blank=True)
    # Précision MOIS : la valeur est ramenée au premier jour du mois.
    mise_en_service = models.DateField(
        'Mise en service', null=True, blank=True,
        help_text='Mois de la mise en service (le jour est ramené au 1er).')
    # Domaine volontairement ABSENT de l'exemple : le site est celui de la
    # société (white-label, `CompanyProfile.site_web`), jamais une marque
    # codée en dur (garde SCA29).
    url_page = models.URLField(
        'Page publique', max_length=300,
        help_text='Page de la réalisation sur le site de la société, '
                  'ex. .../realisations/villa-bouskoura/')
    lien_suivi = models.URLField(
        'Lien de suivi de production', max_length=300,
        blank=True, default='',
        help_text='Suivi de production en temps réel, quand il est public.')
    actif = models.BooleanField(
        'Actif', default=True,
        help_text='Une réalisation inactive ne sert plus aucune preuve.')

    class Meta:
        verbose_name = 'Réalisation'
        verbose_name_plural = 'Réalisations'
        ordering = ['-mise_en_service', '-id']
        constraints = [
            # Une page publique ne décrit qu'UNE installation : deux lignes
            # pointant la même URL seraient le « mélange » que la règle
            # fondatrice interdit. Scopée SOCIÉTÉ (multi-tenant).
            models.UniqueConstraint(
                fields=['company', 'url_page'],
                name='param_realisation_co_url'),
        ]
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='param_realisation_idx'),
        ]

    def __str__(self):
        return f'{self.titre} ({self.ville})'

    # ── Normalisations d'écriture ──────────────────────────────────────────

    def _normaliser(self):
        """Ville canonisée + mise en service ramenée au 1er du mois.

        Posé sur ``save()`` (et pas seulement sur ``clean()``) : un
        ``objects.create(...)`` en ORM brut n'appelle jamais ``full_clean()``
        et stockerait sinon « belksiri », que la comparaison de villes du
        sélecteur ne retrouverait pas."""
        self.ville = corriger_ville((self.ville or '').strip())
        # ``getattr`` plutôt qu'un accès direct : une date affectée sous forme
        # de CHAÎNE (``objects.create(mise_en_service='2026-07-18')``, que
        # Django convertit seulement à l'écriture SQL) n'a pas de ``.day`` —
        # on la laisse alors passer telle quelle au lieu de planter.
        jour = getattr(self.mise_en_service, 'day', None)
        if jour is not None and jour != 1:
            self.mise_en_service = self.mise_en_service.replace(day=1)

    def clean(self):
        super().clean()
        self._normaliser()

    def save(self, *args, **kwargs):
        self._normaliser()
        return super().save(*args, **kwargs)
