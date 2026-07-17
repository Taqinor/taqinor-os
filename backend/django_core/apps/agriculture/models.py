"""Modèles du vertical Agriculture (exploitations, parcelles, campagnes,
intrants, main d'œuvre saisonnière).

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté
serveur (jamais lu du corps de requête). Les liens vers d'autres apps
(``stock.Produit``, ``rh.DossierEmploye``, utilisateurs) sont des string-FK
(``IntegerField``) résolus via les ``selectors.py``/``services.py`` de l'app
cible — jamais un import de modèle étranger (CLAUDE.md, frontière cross-app).
Les liens INTERNES à cette app (Parcelle→Exploitation, CampagneCulturale→
Parcelle, EtapeCampagne→CampagneCulturale/IntrantAgricole, PointageAgricole→
EquipeSaisonniere/CampagneCulturale/Parcelle) sont de vrais FK Django.
"""
import datetime

from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel


# ── NTAGR1 — Exploitation + Parcelle ────────────────────────────────────────

class Exploitation(TenantModel):
    """Une exploitation agricole (ou membre d'une coopérative) d'une société."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='exploitations_agricoles')
    nom = models.CharField(max_length=255)
    adresse = models.CharField(max_length=500, blank=True, default='')
    superficie_totale_ha = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # String-ref vers l'utilisateur responsable (authentication.User) — jamais
    # un FK direct pour rester cohérent avec le patron string-ref de l'app.
    responsable_id = models.IntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Parcelle(TenantModel):
    """Une parcelle cultivable d'une exploitation, avec son polygone GPS."""

    class Statut(models.TextChoices):
        EN_CULTURE = 'en_culture', 'En culture'
        JACHERE = 'jachere', 'Jachère'
        PREPARATION = 'preparation', 'Préparation'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='parcelles_agricoles')
    exploitation = models.ForeignKey(
        Exploitation, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='parcelles')
    nom = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, default='')
    superficie_ha = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Liste de points {lat, lng} du polygone GPS (JSON, aucun schéma strict).
    geometrie_gps = models.JSONField(null=True, blank=True)
    culture_principale = models.CharField(max_length=100, blank=True, default='')
    type_sol = models.CharField(max_length=100, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PREPARATION)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return f'{self.nom} ({self.exploitation.nom})'


# ── NTAGR2 — CampagneCulturale ──────────────────────────────────────────────

class CampagneCulturale(TenantModel):
    """Cycle semis→récolte d'une culture sur une parcelle.

    Une parcelle ne peut avoir qu'une seule campagne ``en_cours`` à la fois
    (garde applicative — voir ``clean()`` et ``serializers.py``)."""

    class Statut(models.TextChoices):
        PLANIFIEE = 'planifiee', 'Planifiée'
        EN_COURS = 'en_cours', 'En cours'
        RECOLTEE = 'recoltee', 'Récoltée'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='campagnes_agricoles')
    parcelle = models.ForeignKey(
        Parcelle, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='campagnes')
    culture = models.CharField(max_length=100)
    variete = models.CharField(max_length=100, blank=True, default='')
    date_semis = models.DateField(null=True, blank=True)
    date_recolte_prevue = models.DateField(null=True, blank=True)
    date_recolte_reelle = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.PLANIFIEE)
    rendement_prevu_qtl_ha = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.culture} — {self.parcelle.nom}'

    def clean(self):
        super().clean()
        if self.statut == self.Statut.EN_COURS and self.parcelle_id:
            qs = CampagneCulturale.objects.filter(
                parcelle_id=self.parcelle_id, statut=self.Statut.EN_COURS)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "Cette parcelle a déjà une campagne 'en_cours' — "
                    'clôturez-la ou récoltez-la avant d’en démarrer une '
                    'nouvelle.')


# ── NTAGR3 / NTAGR6 — EtapeCampagne + garde DAR ─────────────────────────────

def check_dar_guard(*, type_etape, date, intrant, campagne):
    """Garde bloquante DAR (délai avant récolte) — NTAGR6.

    Lève ``ValidationError`` si un traitement phyto appliqué à ``date``
    dépasserait le délai avant récolte (DAR) de l'intrant compte tenu de la
    date de récolte (réelle si connue, sinon prévue) de la campagne. Ne
    bloque JAMAIS si le type d'étape n'est pas ``traitement``, si l'intrant
    n'est pas renseigné ou n'a pas de DAR défini, ou si la campagne n'a
    aucune date de récolte connue — conformité ONSSA, garde bloquante et non
    un simple avertissement.
    """
    if type_etape != EtapeCampagne.TypeEtape.TRAITEMENT:
        return
    if intrant is None or intrant.delai_avant_recolte_jours is None:
        return
    if date is None:
        return
    candidates = [
        d for d in (campagne.date_recolte_prevue, campagne.date_recolte_reelle)
        if d is not None
    ]
    if not candidates:
        return
    # La date de récolte la plus contraignante (la plus proche) — si la
    # récolte réelle est déjà connue et plus proche que la prévision, elle
    # prime (NTAGR6 : "bloquer aussi une saisie a posteriori").
    date_recolte_contraignante = min(candidates)
    date_limite_traitement = date + datetime.timedelta(
        days=intrant.delai_avant_recolte_jours)
    if date_limite_traitement > date_recolte_contraignante:
        produit_label = intrant.matiere_active or f'intrant #{intrant.pk}'
        raise ValidationError(
            f"Traitement refusé — le délai avant récolte (DAR) de "
            f"{intrant.delai_avant_recolte_jours} jour(s) pour "
            f"« {produit_label} » appliqué le {date.isoformat()} dépasse la "
            f"date de récolte du {date_recolte_contraignante.isoformat()}.")


class EtapeCampagne(TenantModel):
    """Étape horodatée d'une campagne (semis, traitement, irrigation…)."""

    class TypeEtape(models.TextChoices):
        SEMIS = 'semis', 'Semis'
        TRAITEMENT = 'traitement', 'Traitement'
        IRRIGATION = 'irrigation', 'Irrigation'
        DESHERBAGE = 'desherbage', 'Désherbage'
        FERTILISATION = 'fertilisation', 'Fertilisation'
        RECOLTE = 'recolte', 'Récolte'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='etapes_campagne_agricole')
    campagne = models.ForeignKey(
        CampagneCulturale, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='etapes')
    type_etape = models.CharField(max_length=20, choices=TypeEtape.choices)
    date = models.DateField()
    description = models.TextField(blank=True, default='')
    cout_mad = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Intrant consommé par l'étape (traitement/fertilisation…), optionnel.
    intrant = models.ForeignKey(
        'IntrantAgricole', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='etapes')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'id']

    def __str__(self):
        return f'{self.get_type_etape_display()} — {self.date}'

    def clean(self):
        super().clean()
        check_dar_guard(
            type_etape=self.type_etape, date=self.date, intrant=self.intrant,
            campagne=self.campagne)


# ── NTAGR5 — IntrantAgricole (catalogue agronomique, lié à stock.Produit) ───

class IntrantAgricole(TenantModel):
    """Attributs agronomiques d'un ``stock.Produit`` (semence/engrais/phyto).

    Le stock physique reste géré EXCLUSIVEMENT par ``apps.stock`` — ce modèle
    n'ajoute QUE les attributs agronomiques et référence le produit par
    string-ref (``produit_id``), lu via ``apps.stock.selectors`` (jamais un
    import de ``stock.models``). ``produit_id`` est unique PAR SOCIÉTÉ : une
    fiche agricole par produit stock (relation « OneToOne » côté données, sans
    FK Django cross-app). L'unicité est scopée société via un
    ``UniqueConstraint(company, produit_id)`` — ``produit_id`` étant la PK d'un
    ``stock.Produit`` déjà scopé société, une unicité GLOBALE empêcherait à tort
    deux sociétés de référencer chacune leur propre produit portant le même id."""

    class Categorie(models.TextChoices):
        SEMENCE = 'semence', 'Semence'
        ENGRAIS = 'engrais', 'Engrais'
        PHYTO = 'phyto', 'Phytosanitaire'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='intrants_agricoles')
    produit_id = models.IntegerField()
    categorie = models.CharField(max_length=20, choices=Categorie.choices)
    dose_reference_par_ha = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True)
    delai_avant_recolte_jours = models.IntegerField(null=True, blank=True)
    matiere_active = models.CharField(max_length=255, blank=True, default='')
    numero_amm = models.CharField(max_length=100, blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categorie', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'produit_id'],
                name='uniq_intrant_produit_par_societe'),
        ]

    def __str__(self):
        return f'Intrant #{self.produit_id} ({self.get_categorie_display()})'


# ── NTAGR9 — Main d'œuvre saisonnière ───────────────────────────────────────

class EquipeSaisonniere(TenantModel):
    """Équipe de travailleurs saisonniers d'une exploitation."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='equipes_saisonnieres')
    nom = models.CharField(max_length=255)
    # String-ref vers l'utilisateur chef d'équipe (authentication.User).
    chef_equipe_id = models.IntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class PointageAgricole(TenantModel):
    """Pointage journalier par équipe/travailleur/tâche/parcelle.

    Donnée agricole INFORMATIVE — ne crée aucun élément de paie (voir
    NTAGR10, DECISION founder non tranchée). Si le travailleur est un employé
    RH enregistré, ``employe_id`` (string-ref vers ``rh.DossierEmploye``) peut
    être renseigné en plus, sans effet côté paie."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='pointages_agricoles')
    equipe = models.ForeignKey(
        EquipeSaisonniere, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pointages')
    travailleur_nom = models.CharField(max_length=255, blank=True, default='')
    campagne = models.ForeignKey(
        CampagneCulturale, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pointages')
    parcelle = models.ForeignKey(
        Parcelle, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='pointages')
    date = models.DateField()
    tache = models.CharField(max_length=255)
    nombre_journees = models.DecimalField(max_digits=6, decimal_places=2)
    taux_journalier_mad = models.DecimalField(max_digits=10, decimal_places=2)
    # String-ref optionnel vers rh.DossierEmploye — jamais un import direct.
    employe_id = models.IntegerField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        who = self.equipe.nom if self.equipe_id else (self.travailleur_nom or '—')
        return f'{who} — {self.date}'

    def clean(self):
        super().clean()
        if not self.equipe_id and not self.travailleur_nom:
            raise ValidationError(
                "Renseignez une équipe ou un nom de travailleur libre.")


# ── NTAGR11 — Matériel agricole (pattern flotte.EnginRoulant, jamais dupliqué) ─

class MaterielAgricole(TenantModel):
    """Matériel agricole non immatriculé suivi au compteur d'heures moteur.

    Même PATTERN que ``flotte.EnginRoulant.compteur_heures`` (heures cumulées),
    mais reste dans ``apps.agriculture`` : le matériel agricole n'est pas un
    véhicule immatriculé soumis aux obligations réglementaires de
    ``apps.flotte`` (vignette/assurance véhicule) — donc pas de duplication de
    flotte, juste le même patron d'heures moteur."""

    class TypeMateriel(models.TextChoices):
        TRACTEUR = 'tracteur', 'Tracteur'
        MOISSONNEUSE = 'moissonneuse', 'Moissonneuse'
        PULVERISATEUR = 'pulverisateur', 'Pulvérisateur'
        OUTIL = 'outil', 'Outil'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='materiels_agricoles')
    nom = models.CharField(max_length=255)
    type_materiel = models.CharField(
        max_length=20, choices=TypeMateriel.choices,
        default=TypeMateriel.TRACTEUR)
    numero_serie = models.CharField(max_length=100, blank=True, default='')
    heures_moteur = models.DecimalField(
        max_digits=10, decimal_places=1, default=0)
    parcelle_affectee = models.ForeignKey(
        Parcelle, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='materiels_affectes')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom


class UtilisationMateriel(TenantModel):
    """Utilisation journalière d'un ``MaterielAgricole`` — chaque création
    incrémente ``MaterielAgricole.heures_moteur`` (voir ``serializers.py``,
    mise à jour atomique via ``F()``)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='utilisations_materiel_agricole')
    materiel = models.ForeignKey(
        MaterielAgricole, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='utilisations')
    campagne = models.ForeignKey(
        CampagneCulturale, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='utilisations_materiel')
    date = models.DateField()
    heures_utilisees = models.DecimalField(max_digits=8, decimal_places=1)
    cout_carburant_mad = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.materiel.nom} — {self.date}'
