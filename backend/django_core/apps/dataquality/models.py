"""NTDATA14 — QUALITÉ DE DONNÉES : les règles métier, déclarées et évaluées.

LE PROBLÈME. Rien, dans le dépôt, ne disait « un client entreprise DOIT avoir
un ICE au bon format » ou « une facture ne peut pas avoir un montant négatif ».
Ces attentes vivaient dans la tête des gens, et les écarts ne se voyaient qu'au
moment où un document partait faux chez un client.

CE QUE CETTE APP EST. Un référentiel de RÈGLES company-scopées, posées sur les
datasets que les apps métier déclarent déjà (``core.data_explorer``), et le
moteur qui les évalue. Elle ne bloque RIEN par elle-même : elle MESURE et
RAPPORTE. La sévérité ``bloquant`` qualifie la gravité d'un écart, elle
n'empêche aucune écriture (ce serait une décision fondateur, pas une lane).

CE QUE CETTE APP N'EST PAS. Elle n'importe AUCUN modèle d'app métier :
``entite`` est le NOM d'un dataset enregistré, et c'est l'app propriétaire qui
garantit le scoping société de son queryset.

RÉUTILISATION DE ``core.rules``. Les types ``non_vide`` et ``plage`` se
traduisent EXACTEMENT en un arbre de conditions ``core.rules`` (opérateurs
``exists`` / ``gte`` / ``lte``) et sont évalués par lui — jamais une seconde
implémentation. ``format`` (expression régulière), ``unicite`` et
``reference_valide`` n'y sont PAS exprimables : ``core.rules`` n'a pas
d'opérateur regex, et les deux derniers raisonnent sur la POPULATION entière,
pas sur une ligne. Ils sont donc évalués ici, au-dessus, et c'est dit.
"""
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


class RegleQualite(TenantModel):
    """Une attente métier VÉRIFIABLE sur un champ d'un dataset.

    ``entite`` — nom d'un dataset enregistré (``crm_clients``,
    ``ventes_factures``…). ``champ`` — un champ de sa liste blanche.
    ``parametres`` — le paramétrage du type de règle :

    * ``non_vide``          — aucun paramètre ;
    * ``format``            — ``{"motif": "^[0-9]{15}$"}`` (regex Python) ;
    * ``plage``             — ``{"min": 0, "max": 100}`` (l'un OU l'autre) ;
    * ``unicite``           — aucun paramètre (la valeur du champ doit être
      unique dans la population, valeurs vides ignorées) ;
    * ``reference_valide``  — ``{"valeurs": [...]}`` : la valeur doit
      appartenir à cette liste de référence.
    """

    class TypeRegle(models.TextChoices):
        NON_VIDE = 'non_vide', 'Champ renseigné'
        FORMAT = 'format', 'Format (expression régulière)'
        PLAGE = 'plage', 'Plage de valeurs'
        UNICITE = 'unicite', 'Valeur unique'
        REFERENCE_VALIDE = 'reference_valide', 'Valeur d\'un référentiel'

    class Severite(models.TextChoices):
        INFO = 'info', 'Information'
        AVERTISSEMENT = 'avertissement', 'Avertissement'
        BLOQUANT = 'bloquant', 'Bloquant'

    libelle = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Libellé',
        help_text='Phrase lisible (ex. « ICE client au bon format »). Vide : '
                  'un libellé est dérivé du type et du champ.')
    entite = models.CharField(
        max_length=80, verbose_name='Entité (dataset)',
        help_text="Nom d'un dataset enregistré (ex. « crm_clients »).")
    champ = models.CharField(max_length=120, verbose_name='Champ')
    type_regle = models.CharField(
        max_length=20, choices=TypeRegle.choices, verbose_name='Type de règle')
    parametres = models.JSONField(
        default=dict, blank=True, verbose_name='Paramètres')
    severite = models.CharField(
        max_length=15, choices=Severite.choices, default=Severite.AVERTISSEMENT,
        verbose_name='Sévérité')
    actif = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Règle de qualité'
        verbose_name_plural = 'Règles de qualité'
        ordering = ['entite', 'champ', 'id']

    def __str__(self):
        return self.libelle or '%s.%s (%s)' % (
            self.entite, self.champ, self.get_type_regle_display())

    # ── Validation ──────────────────────────────────────────────────────────
    def clean(self):
        """Refuse un paramétrage incohérent, EN NOMMANT le champ fautif."""
        import re

        erreurs = {}
        if not (self.entite or '').strip():
            erreurs['entite'] = "L'entité (dataset) est obligatoire."
        if not (self.champ or '').strip():
            erreurs['champ'] = 'Le champ à contrôler est obligatoire.'
        parametres = (self.parametres
                      if isinstance(self.parametres, dict) else {})
        if self.type_regle == self.TypeRegle.FORMAT:
            motif = parametres.get('motif')
            if not motif:
                erreurs['parametres'] = (
                    'Une règle de FORMAT exige « motif » (expression '
                    'régulière).')
            else:
                try:
                    re.compile(motif)
                except re.error as exc:
                    erreurs['parametres'] = (
                        'Expression régulière invalide : %s.' % exc)
        elif self.type_regle == self.TypeRegle.PLAGE:
            if parametres.get('min') is None \
                    and parametres.get('max') is None:
                erreurs['parametres'] = (
                    'Une règle de PLAGE exige au moins « min » ou « max ».')
        elif self.type_regle == self.TypeRegle.REFERENCE_VALIDE:
            valeurs = parametres.get('valeurs')
            if not isinstance(valeurs, list) or not valeurs:
                erreurs['parametres'] = (
                    'Une règle de RÉFÉRENTIEL exige « valeurs » : la liste '
                    'des valeurs acceptées.')
        if erreurs:
            raise ValidationError(erreurs)

    # ── Traduction vers core.rules ──────────────────────────────────────────
    @property
    def condition_core_rules(self):
        """L'arbre ``core.rules`` équivalent, ou ``None`` si inexprimable.

        ``non_vide`` → ``exists`` ; ``plage`` → ``gte``/``lte`` dans un groupe
        ``and``. Les autres types n'ont pas d'équivalent (pas d'opérateur
        regex ; ``unicite``/``reference_valide`` raisonnent sur la population)
        et sont évalués par ``dataquality.services``.
        """
        if self.type_regle == self.TypeRegle.NON_VIDE:
            return {'field': self.champ, 'operator': 'exists', 'value': True}
        if self.type_regle == self.TypeRegle.PLAGE:
            parametres = (self.parametres
                          if isinstance(self.parametres, dict) else {})
            bornes = []
            if parametres.get('min') is not None:
                bornes.append({'field': self.champ, 'operator': 'gte',
                               'value': parametres['min']})
            if parametres.get('max') is not None:
                bornes.append({'field': self.champ, 'operator': 'lte',
                               'value': parametres['max']})
            return {'op': 'and', 'conditions': bornes}
        return None

    @property
    def est_population(self):
        """True si la règle ne peut PAS se juger ligne par ligne (unicité)."""
        return self.type_regle == self.TypeRegle.UNICITE


class ResultatQualite(TenantModel):
    """NTDATA15 — le résultat DATÉ d'une évaluation de règle.

    Un enregistrement PAR EXÉCUTION (jamais un écrasement) : l'historique est
    ce qui permet de dire « la conformité ICE est passée de 62 % à 91 % » —
    un simple champ « dernier taux » sur la règle effacerait cette trajectoire.

    ``taux_conformite`` est NULLABLE : une population VIDE ne vaut pas 100 %
    (« aucune donnée » n'est pas « tout est bon »). ``echantillon`` porte au
    plus :data:`TAILLE_ECHANTILLON` identifiants en violation — de quoi aller
    corriger, jamais un export déguisé de toute la base.
    """

    #: Nombre maximal d'identifiants conservés par résultat.
    TAILLE_ECHANTILLON = 50

    regle = models.ForeignKey(
        RegleQualite, on_delete=models.CASCADE,  # on_delete: composition
        related_name='resultats', verbose_name='Règle')
    entite = models.CharField(max_length=80, verbose_name='Entité (dataset)')
    nb_lignes = models.PositiveIntegerField(
        default=0, verbose_name='Lignes évaluées')
    nb_violations = models.PositiveIntegerField(
        default=0, verbose_name='Violations')
    taux_conformite = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Taux de conformité (%)',
        help_text='Vide quand la population est vide — « aucune donnée » '
                  "n'est pas « tout est bon ».")
    echantillon = models.JSONField(
        default=list, blank=True, verbose_name='Échantillon en violation')
    evalue_le = models.DateTimeField(auto_now_add=True,
                                     verbose_name='Évalué le')

    class Meta:
        verbose_name = 'Résultat de qualité'
        verbose_name_plural = 'Résultats de qualité'
        ordering = ['-evalue_le', '-id']

    def __str__(self):
        return '%s : %s/%s en violation' % (
            self.regle_id, self.nb_violations, self.nb_lignes)
