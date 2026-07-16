"""
FG305 — Ordres de travaux émis à un sous-traitant chantier.

``OrdreSousTraitance`` matérialise la commande de PRESTATION passée à un
sous-traitant de l'annuaire (``SousTraitant``, FG304) : pour TEL chantier
(``Installation``, même app), TELLE prestation (terrassement, génie civil,
pose…), pour TEL montant, à émettre/réceptionner/clôturer. C'est le pendant
« main-d'œuvre sous-traitée » du bon de commande matériel — mais distinct : on
ne commande pas du panneau ici, on commande une intervention de pose/travaux.

Couche de statut PROPRE — distincte des trois couches de l'OS (entonnoir
``STAGES.py``, statut document devis/facture, statut chantier). Le ``Statut``
ci-dessous (brouillon → émis → en cours → réceptionné → clos) est le cycle de
vie de l'ORDRE lui-même, jamais l'un des autres. « annulé » n'en fait pas
partie ; un ordre se clôt, il ne s'annule pas (la liste reste fermée et courte).

Numérotation : la référence ``OST-YYYYMM-NNNN`` est posée CÔTÉ SERVEUR via le
numéroteur anti-collision partagé (``apps.ventes.utils.references`` ; jamais
``count()+1``), tenant-scopée par l'unicité ``(company, reference)``.

Additif & multi-tenant : on AJOUTE une table avec une FK ``company`` posée côté
serveur, jamais lue du corps de la requête. ``sous_traitant`` et ``chantier``
sont validés tenant (même société) côté vue.

SCA34 — pilote 1 du kit ``core.documents`` (Groupe SCA). ``OrdreSousTraitance``
hérite désormais de ``core.documents.DocumentMetier`` (ARC1 ``TenantModel`` +
contrat statut/transitions du kit) au lieu de ``models.Model`` nu. Conversion
MIXTE, justifiée champ par champ :

  * ``company`` — REDÉCLARÉE à l'identique (``null=True, blank=True``,
    ``related_name`` historique inchangé) : la colonne DB existe déjà avec CETTE
    forme, donc AUCUN changement de schéma pour ce champ (state résolu
    identique à avant — cf. note ``core.models.TenantModel`` sur la
    redéclaration ``company``) ;
  * ``created_at``/``updated_at`` — NOUVEAUX champs hérités de
    ``TenantModel``/``TimestampedModel`` : ``date_creation``/``date_modification``
    (auto_now_add/auto_now historiques) sont CONSERVÉS tels quels (aucune
    suppression, aucun renommage — rétrofit de colonne interdit) ; les deux
    nouvelles colonnes sont ADDITIVES (``AddField``, nullable via
    ``auto_now_add``/``auto_now`` — pas de valeur par défaut à fournir sur la
    table existante grâce au comportement ``auto_now*`` de Django au
    ``makemigrations``) ;
  * ``statut`` — le champ abstrait du kit est ``max_length=32`` (vs 20
    existant) ; ``__init_subclass__`` adosse ``choices``/``default`` à
    ``Statut`` mais PAS ``max_length`` → ``AlterField`` élargit 20→32
    (élargissement pur, aucune troncature possible, migration additive/sûre) ;
    les ``choices`` (mêmes 5 valeurs, même libellés) et le ``default``
    (BROUILLON) restent bit-identiques.
  * ``TRANSITIONS`` déclare le MÊME graphe que les gardes de vue historiques
    (``emettre``/``receptionner``/``cloturer``) — la migration vers
    ``changer_statut()`` viendra dans une passe ultérieure (hors périmètre
    SCA34, qui porte sur le SOCLE + chatter + PDF ; les 3 actions de cycle de
    vie existantes restent le point d'écriture aujourd'hui, inchangées).

Référence ``OST-YYYYMM-NNNN`` INCHANGÉE — même numéroteur anti-collision
(``core.numbering``, shim ``apps.ventes.utils.references``), même préfixe,
même padding (4) et période (mensuelle) : test de non-régression de format
dans ``tests_fg305_ordre_sous_traitance.py``.
"""
from django.conf import settings
from django.db import models

from core.documents import DocumentMetier


class OrdreSousTraitance(DocumentMetier):
    """FG305 — un ordre de travaux émis à un sous-traitant chantier.

    Relie un ``SousTraitant`` (FG304, prestataire de main-d'œuvre) à un
    ``chantier`` (``Installation``, même app, optionnel) pour une ``prestation``
    décrite, un ``montant`` engagé et une ``date_echeance``. ``montant_realise``
    (optionnel) capture le réalisé à la réception. Le ``statut`` suit le cycle de
    vie de l'ordre, distinct de toute autre couche de statut de l'OS.

    SCA34 — socle ``core.documents.DocumentMetier`` (ARC1 ``TenantModel`` +
    contrat statut/transitions du kit). Multi-tenant : la société est posée
    côté serveur. La référence ``OST-YYYYMM-NNNN`` est anti-collision (jamais
    count()+1)."""

    class Statut(models.TextChoices):
        # Machine à états PROPRE à l'ordre — distincte de toute autre couche.
        BROUILLON = 'brouillon', 'Brouillon'
        EMIS = 'emis', 'Émis'
        EN_COURS = 'en_cours', 'En cours'
        RECEPTIONNE = 'receptionne', 'Réceptionné'
        CLOS = 'clos', 'Clos'

    # SCA34 — table déclarative du graphe d'états (kit ``DocumentMetier``),
    # miroir des gardes historiques des actions de vue
    # (emettre/receptionner/cloturer) HORS ré-application idempotente du même
    # statut (permise par les vues, non déclarée ici — un document ne
    # « transite » pas vers lui-même, cf. ``changer_statut``). Documentaire
    # pour l'instant : les actions de vue restent le point d'écriture (pas de
    # bascule vers ``changer_statut()`` — périmètre SCA34 = socle+chatter+PDF).
    TRANSITIONS = {
        Statut.BROUILLON: {Statut.EMIS},
        Statut.EMIS: {Statut.EN_COURS, Statut.RECEPTIONNE},
        Statut.EN_COURS: {Statut.RECEPTIONNE},
        Statut.RECEPTIONNE: {Statut.CLOS},
        Statut.CLOS: set(),
    }

    # Redéclarée à l'identique (SCA34) : conserve le related_name + la
    # nullabilité historiques — colonne DB inchangée (state-only pour ce champ).
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance')
    reference = models.CharField(max_length=50)
    # DC34 — le sous-traitant est un stock.Fournisseur de type « service »
    # (référentiel UNIFIÉ, plus de table parallèle). FK CHAÎNE : on ne référence
    # jamais apps.stock.models par import (contrat de découplage M1). PROTECT :
    # on ne supprime pas un sous-traitant qui porte des ordres.
    sous_traitant = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.PROTECT,
        related_name='installations_ordres_sous_traitance')
    # Chantier concerné (même app). Optionnel : un ordre cadre peut précéder
    # l'affectation à un chantier précis. SET_NULL : la suppression d'un chantier
    # ne détruit pas l'historique de l'ordre.
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance')
    prestation = models.TextField()
    # Montant engagé (HT, MAD). DecimalField : jamais de flottant sur de l'argent.
    montant = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    # Réalisé à la réception (optionnel) — peut différer du montant engagé.
    montant_realise = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    date_emission = models.DateField(null=True, blank=True)
    date_echeance = models.DateField(null=True, blank=True)
    # SCA34 — ``statut`` n'est PLUS redéclaré ici : hérité du kit
    # (``DocumentMetier.statut``, ``max_length=32``) et adossé aux ``choices``/
    # ``default`` de CETTE sous-classe par ``__init_subclass__`` (mêmes 5
    # valeurs, même défaut BROUILLON — seul ``max_length`` change, 20→32,
    # élargissement pur). Cf. docstring de tête pour la justification complète.
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_ordres_sous_traitance_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ordre de sous-traitance'
        verbose_name_plural = 'Ordres de sous-traitance'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            # Noms d'index ≤ 30 caractères (contrainte Django/Postgres).
            models.Index(fields=['company', 'statut'],
                         name='idx_ost_co_statut'),
            models.Index(fields=['company', 'sous_traitant'],
                         name='idx_ost_co_soustrait'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.sous_traitant_id}'
