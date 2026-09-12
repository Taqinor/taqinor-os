"""NTDATA7 — COUCHE SÉMANTIQUE : une métrique se définit UNE fois.

LE PROBLÈME. « Marge brute », « DSO », « MRR » se recalculaient partout où on
en avait besoin — un widget de tableau de bord ici, un rapport là, une alerte
KPI ailleurs — chacun avec sa propre spec inline. Deux écrans pouvaient
afficher deux « marges brutes » différentes sans que personne ne puisse dire
laquelle avait raison, et corriger la définition supposait de la retrouver dans
N specs dispersées.

CE QUE CETTE APP EST. Un REGISTRE de définitions de métriques, company-scopé :
une clé stable (``mrr``, ``dso``, ``marge_brute``) → une définition unique,
éditable au même endroit par tout le monde. Le RÉSOLVEUR (NTDATA8,
``services.resolve_metric``) traduit ensuite cette définition en une requête
``core.data_explorer.run_query`` — la métrique n'a donc jamais de chemin de
données à elle : elle réutilise les datasets que les apps métier déclarent.

CE QUE CETTE APP N'EST PAS. Elle n'importe AUCUN modèle d'app métier : le
``dataset`` est désigné par son NOM (chaîne) dans le registre
``core.data_explorer``, et c'est l'app propriétaire qui garantit le scoping
société de son queryset. Aucune écriture métier, aucun statut changé.

MULTI-TENANT : ``MetricDefinition`` hérite de ``core.models.TenantModel``
(FK ``company`` + horodatage) ; ``cle`` est unique PAR SOCIÉTÉ — deux sociétés
peuvent avoir chacune leur ``marge_brute``, jamais la même ligne.
"""
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel

#: Agrégations autorisées pour une mesure simple — MÊME liste blanche que le
#: moteur (``core.data_explorer``), jamais une seconde qui dériverait.
AGREGATIONS = ('count', 'sum', 'avg', 'min', 'max')


class MetricDefinition(TenantModel):
    """Une métrique NOMMÉE : sa clé, son dataset, sa mesure, son unité.

    DEUX FORMES DE MESURE, et deux seulement (``mesure``, JSON) :

    * MESURE SIMPLE — ``{"field": "montant_ttc", "agg": "sum"}`` : un agrégat
      direct sur un champ de la liste blanche du dataset.
    * MESURE FORMULE — ``{"formula": "ca / nb", "aggregates": [{"alias":
      "ca", "fn": "sum", "field": "montant_ttc"}, {"alias": "nb", "fn":
      "count", "field": "id"}]}`` : plusieurs agrégats bruts nommés, puis une
      expression qui les combine. L'expression est évaluée par
      ``core.formula`` (AST, jamais ``eval``) ; une division par zéro rend une
      valeur VIDE, jamais une exception ni un zéro inventé.

    ``format`` = nombre de décimales d'AFFICHAGE. Il ne change JAMAIS la
    valeur calculée : arrondir est une décision de rendu, et la résolution
    (NTDATA8) renvoie la valeur brute.
    """

    class Unite(models.TextChoices):
        MAD = 'MAD', 'Dirham (MAD)'
        POURCENT = '%', 'Pourcentage'
        JOURS = 'jours', 'Jours'
        NOMBRE = 'nombre', 'Nombre'

    cle = models.CharField(
        max_length=80, verbose_name='Clé',
        help_text="Identifiant stable de la métrique (ex. « mrr », « dso ») — "
                  "c'est par cette clé qu'un widget, un rapport ou une alerte "
                  'la référence.')
    libelle = models.CharField(max_length=150, verbose_name='Libellé')
    description = models.TextField(
        blank=True, default='', verbose_name='Définition',
        help_text='Ce que la métrique mesure, en français lisible — la phrase '
                  'que lira un commercial dans le glossaire.')
    dataset = models.CharField(
        max_length=80, verbose_name='Dataset',
        help_text="Nom d'un dataset enregistré dans core.data_explorer "
                  "(ex. « ventes_factures »).")
    mesure = models.JSONField(
        default=dict, verbose_name='Mesure',
        help_text='{"field": …, "agg": …} ou {"formula": …, "aggregates": […]}.')
    unite = models.CharField(
        max_length=10, choices=Unite.choices, default=Unite.NOMBRE,
        verbose_name='Unité')
    format = models.PositiveSmallIntegerField(
        default=2, verbose_name='Décimales',
        help_text="Décimales d'AFFICHAGE — n'altère jamais la valeur calculée.")
    dimensions_par_defaut = models.JSONField(
        default=list, blank=True, verbose_name='Dimensions par défaut',
        help_text='Champs de regroupement proposés par défaut (ex. ["mois"]).')
    # NTDATA11 — une métrique porte SA population. « CA HT » exclut les
    # factures annulées, « MRR » ne compte que les contrats actifs : sans ce
    # champ, chaque appelant devrait re-poser le filtre et deux écrans
    # rendraient deux « CA HT » différents — précisément ce que la couche
    # sémantique existe pour empêcher. Les filtres de l'APPELANT s'ajoutent
    # par-dessus (et peuvent en écraser un, par clé).
    filtres = models.JSONField(
        default=dict, blank=True, verbose_name='Filtres de la définition',
        help_text='Filtres TOUJOURS appliqués (ex. {"actif": true}) — la '
                  'population que cette métrique mesure.')
    actif = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Définition de métrique'
        verbose_name_plural = 'Définitions de métriques'
        ordering = ['cle']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'cle'],
                name='uniq_metricdefinition_company_cle'),
        ]

    def __str__(self):
        return f'{self.cle} — {self.libelle}'

    # ── Validation ──────────────────────────────────────────────────────────
    def clean(self):
        """Refuse une mesure malformée, EN FRANÇAIS et en nommant le champ.

        La validation est volontairement STRUCTURELLE seulement : elle ne
        vérifie pas que le dataset existe ni que le champ est dans sa liste
        blanche, parce que le registre des datasets est peuplé au démarrage
        par les apps et qu'une métrique doit rester éditable même si son
        module est momentanément désactivé. Le RÉSOLVEUR (NTDATA8) refait ces
        deux contrôles au moment où il exécute.
        """
        erreurs = {}
        if not (self.cle or '').strip():
            erreurs['cle'] = 'La clé est obligatoire.'
        mesure = self.mesure if isinstance(self.mesure, dict) else None
        # NTDATA11 — une métrique d'ADAPTATEUR n'a pas de dataset : son calcul
        # vit dans l'app propriétaire (ex. le DSO du grand livre).
        est_adaptateur = bool(mesure and mesure.get('adapter'))
        if not est_adaptateur and not (self.dataset or '').strip():
            erreurs['dataset'] = 'Le dataset est obligatoire.'
        if mesure is None:
            erreurs['mesure'] = (
                'La mesure doit être un objet JSON : {"field": …, "agg": …}, '
                '{"formula": …, "aggregates": […]} ou {"adapter": …}.')
        elif est_adaptateur:
            pass  # la clé d'adaptateur est validée à la RÉSOLUTION.
        elif mesure.get('formula'):
            agregats = mesure.get('aggregates')
            if not isinstance(agregats, list) or not agregats:
                erreurs['mesure'] = (
                    'Une mesure FORMULE exige « aggregates » : la liste des '
                    'agrégats nommés que la formule combine.')
            else:
                for agg in agregats:
                    if not isinstance(agg, dict) or not agg.get('alias'):
                        erreurs['mesure'] = (
                            'Chaque agrégat de « aggregates » doit porter un '
                            '« alias ».')
                        break
                    if agg.get('fn') not in AGREGATIONS:
                        erreurs['mesure'] = (
                            "Agrégation inconnue pour « %s » : %r "
                            '(attendu : %s).'
                            % (agg.get('alias'), agg.get('fn'),
                               ', '.join(AGREGATIONS)))
                        break
        else:
            if mesure.get('agg') not in AGREGATIONS:
                erreurs['mesure'] = (
                    'Agrégation inconnue : %r (attendu : %s).'
                    % (mesure.get('agg'), ', '.join(AGREGATIONS)))
            elif mesure.get('agg') != 'count' and not mesure.get('field'):
                erreurs['mesure'] = (
                    'Le champ « field » est obligatoire pour une mesure '
                    '« %s ».' % mesure.get('agg'))
        if erreurs:
            raise ValidationError(erreurs)

    @property
    def est_formule(self):
        """True si la mesure est une FORMULE combinant plusieurs agrégats."""
        return bool(isinstance(self.mesure, dict)
                    and self.mesure.get('formula'))

    @property
    def est_adaptateur(self):
        """True si le calcul vit dans une app (NTDATA11, ex. le DSO du grand
        livre) plutôt que dans une requête sur un dataset."""
        return bool(isinstance(self.mesure, dict)
                    and self.mesure.get('adapter'))
