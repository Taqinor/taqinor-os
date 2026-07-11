"""Kit « document métier » — composition des briques ARC en un tout (Groupe SCA).

Constat (scout document). L'anatomie « document métier » — header + statut +
lignes + totaux + référence + PDF + chatter — se répète sur 17+ modèles du
dépôt (Devis/Facture/BonCommande/Avoir dans ``ventes``, réceptions/BC dans
``stock``, tickets dans ``pos``, contrats, RFQ…), chacun re-composant à la main
les mêmes primitives, et AUCUNE tâche ARC ne proposait l'UNITÉ qui compose les
briques ARC1/ARC2/ARC6/ARC8/ARC11 en un seul kit réutilisable. Ce module fournit
cette unité : un NOUVEAU type de document se déclare en quelques lignes et hérite
gratuitement le socle multi-tenant, le statut+transitions gardé, la ligne+totaux,
le viewset scopé/numéroté/chatté et le hook PDF.

Ce que le kit fait — et NE fait PAS
-----------------------------------
* Il gère le cycle de vie PROPRE du document (brouillon → … → clôturé) via une
  table ``TRANSITIONS`` déclarative + ``changer_statut()`` gardé côté service,
  émettant un événement bus (``core.events.document_statut_change``).
* Le cycle d'APPROBATION reste ARC10 / ``core.WorkflowDefinition`` (nommé) — un
  workflow multi-étapes s'attache par contenttypes à N'IMPORTE quel document ;
  le kit ne le duplique pas. Statut de document ≠ étape d'approbation.

EXCLUSION PERMANENTE (règle #4, CLAUDE.md) — nommée et absolue
--------------------------------------------------------------
Devis / Facture / BonCommande / Avoir ne sont **JAMAIS** rétrofittés sur ce kit.
Leurs chaînes de statuts (``brouillon``/``envoye``/``accepte``/``refuse``/
``expire`` ; downstream BC/Facture) sont préservées 1:1, séparées à jamais de la
couche funnel ``STAGES.py`` (règle #2). Le PDF de devis client passe
EXCLUSIVEMENT par ``apps/ventes/quote_engine`` (``/proposal``) et la facture
garde son PDF legacy. Le kit est réservé aux NOUVEAUX types de documents.

``core`` reste FONDATION : ce module n'importe AUCUNE app domaine. Il ne compose
que ``core`` (models/mixins/permissions/viewsets/numbering/pdf/events) et
``rest_framework`` ; le chatter générique (ARC8) vit dans l'app de fondation
``records`` et n'est câblé qu'au niveau viewset (SCA32), jamais importé ici au
niveau modèle. Aucun modèle CONCRET n'est déclaré ici → aucune migration (comme
tout ``core``).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models.base import ModelBase

from core.models import TenantModel

__all__ = [
    "DocumentMetier",
    "TotauxDocumentMixin",
    "LigneDocumentMetier",
    "TransitionRefusee",
    "changer_statut",
    "document_viewset",
    "render_document_pdf",
]


# ─────────────────────────────────────────────────────────────────────────────
# SCA30 — ``DocumentMetier`` : le bundle abstrait statut + transitions.
# ─────────────────────────────────────────────────────────────────────────────


class TransitionRefusee(Exception):
    """Levée par ``changer_statut()`` quand une transition n'est PAS permise par
    la table ``TRANSITIONS`` du document. Message en français, listant les
    cibles autorisées depuis le statut courant (utile pour un 400 côté API)."""


class DocumentMetierMeta(ModelBase):
    """Métaclasse du kit : dote CHAQUE document de SON PROPRE champ ``statut``.

    POURQUOI une métaclasse (et non ``__init_subclass__``) — le défaut réparé.
    ``__init_subclass__`` s'exécute pendant ``ModelBase.__new__`` AVANT que la
    sous-classe ait son propre ``_meta`` (il n'est posé qu'ensuite) : à ce
    moment, ``get_field('statut')`` résout par MRO vers le champ de l'ABSTRAIT
    ``DocumentMetier`` (un SEUL objet-champ partagé par héritage). L'ancien code
    mutait CE champ partagé en place (``field.choices = …`` / ``field.default =
    …``) → chaque nouvelle sous-classe écrasait les ``choices``/``default`` vus
    par ses FRÈRES et par le PARENT, et la voie « sans effet » (sous-classe sans
    ``Statut`` propre) héritait alors les valeurs du dernier frère défini.

    La réparation. On intervient dans la métaclasse, AVANT que
    ``ModelBase.__new__`` ne recopie (``copy.deepcopy``) le champ abstrait dans
    la sous-classe : si le CORPS de la classe déclare son propre ``Statut``
    peuplé, on injecte dans ``attrs`` un champ ``statut`` NEUF, propre à cette
    classe, avec SES ``choices``/``default``. Django voit alors ``'statut'`` déjà
    présent localement et NE recopie PAS le champ abstrait (cf. le test
    ``field.name not in new_class.__dict__`` de ``ModelBase.__new__``). Le champ
    partagé de l'abstrait n'est donc JAMAIS muté ; frères et parents gardent
    chacun leur champ intact.

    Garde-fous :
      * on n'agit QUE si ``attrs`` porte un ``Statut`` PROPRE et PEUPLÉ — une
        sous-classe intermédiaire abstraite, ou une sous-classe SANS ``Statut``
        propre (la voie documentée « sans effet »), garde le champ hérité TEL
        QUEL (défaut vide), jamais une valeur d'un frère ;
      * ``STATUT_INITIAL`` est (re)calculé dès que la classe ne le fixe pas
        elle-même dans son corps → un enfant portant son PROPRE ``Statut``
        n'hérite jamais d'un défaut du parent HORS de son énumération.

    (Un document CONCRET qui redéclare son ``Statut`` via une sous-classe MTI à
    parent CONCRET est refusé par Django lui-même — ``FieldError`` : un champ
    concret ne se redéclare pas en MTI. Un statut propre passe par une base
    ABSTRAITE intermédiaire, cas couvert ci-dessus.)
    """

    def __new__(mcs, name, bases, attrs, **kwargs):
        statut_cls = attrs.get("Statut")
        if statut_cls is not None and "statut" not in attrs:
            choices = list(getattr(statut_cls, "choices", ()) or ())
            if choices:
                initial = attrs.get("STATUT_INITIAL") or statut_cls.values[0]
                attrs["STATUT_INITIAL"] = initial
                attrs["statut"] = models.CharField(
                    max_length=32,
                    blank=True,
                    choices=choices,
                    default=initial,
                )
        return super().__new__(mcs, name, bases, attrs, **kwargs)


class DocumentMetier(TenantModel, metaclass=DocumentMetierMeta):
    """Socle abstrait d'un document métier : socle multi-tenant + statut gardé.

    Compose ARC1 (``core.TenantModel`` : FK ``company`` + timestamps) et ajoute
    le CONTRAT de cycle de vie d'un document :

    * une sous-classe déclare son énumération de statuts en surchargeant
      ``Statut`` (un ``models.TextChoices``) — la métaclasse ``DocumentMetierMeta``
      lui injecte alors un champ ``statut`` NEUF, propre à la sous-classe
      (``choices``/``default`` dérivés de SON ``Statut``), sans jamais muter le
      champ partagé de l'abstrait ni celui d'un frère/parent ;
    * une sous-classe déclare sa table ``TRANSITIONS`` DÉCLARATIVE :
      ``{statut_source: {statut_cible, …}, …}`` — la seule source de vérité du
      graphe d'états ; une transition absente de la table est REFUSÉE ;
    * ``changer_statut()`` (fonction de service ci-dessous) est le SEUL point qui
      mute le statut : il vérifie la transition contre ``TRANSITIONS``, applique
      le nouveau statut et ÉMET ``core.events.document_statut_change`` — jamais
      une écriture ``instance.statut = …`` directe hors de ce garde.

    Le kit ne fournit AUCUN statut par défaut : chaque document décrit le sien
    (le kit ne présume pas d'un ``brouillon`` universel). ``STATUT_INITIAL``
    (par défaut le premier membre de ``Statut``) pilote la valeur ``default`` du
    champ ; une sous-classe peut le surcharger.

    GÉNÉRIQUE : aucune référence à une app domaine (règle import-linter
    ``core-foundation-is-a-base-layer``). Abstrait ⇒ aucune table, aucune
    migration.
    """

    class Statut(models.TextChoices):
        """Contrat vide — chaque document CONCRET le surcharge par ses statuts.

        Laissé vide (et non pré-rempli d'un ``brouillon``) pour que le kit
        n'impose aucun vocabulaire de statut : un document de pompage, un bon de
        sortie ou un ordre de mission n'ont pas les mêmes états qu'un devis.
        """

    #: Statut posé à la création. Défaut : premier membre de ``Statut`` de la
    #: sous-classe (injecté par ``DocumentMetierMeta`` si la classe ne le fixe
    #: pas elle-même). Surchargeable dans le corps de la sous-classe.
    STATUT_INITIAL: str = ""

    #: Table de transitions déclarative — la SEULE source de vérité du graphe.
    #: ``{source: {cible, …}}``. Vide par défaut (une sous-classe la déclare).
    TRANSITIONS: dict = {}

    #: Champ ``statut`` de l'ABSTRAIT — vide par défaut. Une sous-classe qui
    #: déclare son propre ``Statut`` peuplé reçoit à la place un champ ``statut``
    #: NEUF (mêmes attributs + ``choices``/``default`` propres) injecté par
    #: ``DocumentMetierMeta`` AVANT la recopie Django du champ abstrait ; ce
    #: champ-ci n'est jamais muté et reste blanc pour les sous-classes « sans
    #: effet » (aucun ``Statut`` propre). Voir ``DocumentMetierMeta``.
    statut = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        abstract = True

    # ── API de lecture du graphe (sans mutation) ─────────────────────────────

    def transitions_permises(self) -> set:
        """Ensemble des statuts atteignables depuis le statut COURANT.

        Lit ``TRANSITIONS[statut_courant]`` — jamais une transition hardcodée.
        Retourne un ``set`` (vide si le statut courant est terminal/inconnu)."""
        return set(self.TRANSITIONS.get(self.statut, ()) or ())

    def transition_permise(self, cible) -> bool:
        """True si passer du statut courant à ``cible`` est autorisé par la table."""
        return cible in self.transitions_permises()


def changer_statut(instance, nouveau_statut, *, user=None, save=True):
    """SCA30 — mute le statut d'un ``DocumentMetier`` de façon GARDÉE (service).

    Le SEUL point d'écriture du statut d'un document du kit :

      1. vérifie que ``instance.statut → nouveau_statut`` est dans la table
         ``TRANSITIONS`` du document — sinon lève ``TransitionRefusee`` (aucune
         écriture) ;
      2. applique le nouveau statut ;
      3. persiste (écriture ciblée ``update_fields=['statut', 'updated_at']`` par
         défaut ; ``save=False`` pour laisser l'appelant persister) ;
      4. ÉMET ``core.events.document_statut_change`` (bus M6) avec l'ancien et le
         nouveau statut, l'utilisateur (posé côté serveur, jamais lu d'un corps
         de requête) et la société du document.

    C'est un SERVICE (fonction), pas une méthode, pour rester alignée sur le
    patron ``core.workflow`` (services de mutation hors des modèles) et garder le
    modèle purement déclaratif. Retourne l'instance mutée.

    Un no-op (``nouveau_statut == statut`` courant) est REFUSÉ comme toute autre
    transition non déclarée : un document ne « transite » pas vers lui-même à
    moins que sa table ne l'autorise explicitement (auquel cas l'événement est
    émis avec ancien == nouveau, à la charge de l'auteur de la table)."""
    from core import events

    ancien = instance.statut
    if nouveau_statut not in instance.transitions_permises():
        permises = ", ".join(sorted(instance.transitions_permises())) or "aucune"
        raise TransitionRefusee(
            f"Transition « {ancien} → {nouveau_statut} » refusée pour "
            f"{type(instance).__name__}. Transitions permises depuis "
            f"« {ancien} » : {permises}."
        )
    instance.statut = nouveau_statut
    if save:
        update_fields = ["statut"]
        # ``updated_at`` existe via TimestampedModel — l'inclure pour horodater.
        if any(f.name == "updated_at" for f in instance._meta.get_fields()):
            update_fields.append("updated_at")
        instance.save(update_fields=update_fields)
    events.document_statut_change.send(
        sender=type(instance),
        instance=instance,
        ancien_statut=ancien,
        nouveau_statut=nouveau_statut,
        user=user,
        company=getattr(instance, "company", None),
    )
    return instance


# ─────────────────────────────────────────────────────────────────────────────
# SCA31 — ``LigneDocumentMetier`` + ``TotauxDocumentMixin`` (factorisation NEUVE).
# ─────────────────────────────────────────────────────────────────────────────
#
# Constat. La chaîne de totaux (``montant_ht``/``montant_tva``/``montant_ttc``
# gelés + propriétés ``total_*`` recomputées en repli) est copiée 3× verbatim
# dans ``ventes/models.py`` (Facture ~626-874, Avoir ~1327-1498, tranches
# ~1452-1498) + variantes ``stock/models.py`` (~1601-1733) et ``pos/models.py``
# (~114-164) ; la formule de ligne ``quantite × prix_unitaire × (1 − remise/100)``
# (motif ``LigneDevis.total_ht``, ventes/models.py:330-333) est répétée sur
# chaque ``Ligne*``. On factorise pour le code NOUVEAU UNIQUEMENT : les 5 copies
# existantes NE BOUGENT PAS (rétrofit du money-path interdit, règle #4 dans
# l'esprit). Sémantique Decimal MIROIR EXACTE de ``LigneDevis.total_ht`` :
# ``quantite * prix_unitaire * (1 - remise / 100)`` sans quantize (l'arrondi
# reste à la charge de l'agrégat/panier TVA, exactement comme l'existant).


class LigneDocumentMetier(models.Model):
    """Socle abstrait d'une LIGNE de document métier (SCA31 — code NOUVEAU).

    Champs standard d'une ligne : ``designation`` / ``quantite`` /
    ``prix_unitaire`` / ``remise`` (%) / ``taux_tva`` (nullable). La formule
    ``total_ht`` est le MIROIR EXACT du motif ``ventes.LigneDevis.total_ht`` :
    ``quantite * prix_unitaire * (1 - remise / 100)`` — mêmes types
    ``DecimalField`` (``max_digits``/``decimal_places``), AUCUN quantize (comme
    l'existant, l'arrondi au centime est fait par l'agrégat, pas par la ligne).

    ``taux_tva`` NULL ⇒ ``taux_tva_effectif`` retombe sur le taux du PARENT. Le
    kit ne connaît pas le nom de la FK parente (chaque document nomme la sienne),
    donc la sous-classe déclare :

      * la FK parente elle-même (ex. ``document = models.ForeignKey(MonDoc, …)``) ;
      * ``PARENT_FIELD`` = le nom de cet attribut (``'document'``) — utilisé par
        ``taux_tva_effectif`` pour lire ``parent.taux_tva`` en repli.

    Abstrait ⇒ aucune table, aucune migration. GÉNÉRIQUE : aucune app domaine.
    """

    #: Nom de l'attribut FK vers le document parent (déclaré par la sous-classe).
    #: Sert au repli ``taux_tva_effectif`` → ``parent.taux_tva``.
    PARENT_FIELD: str = ""

    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Taux TVA de la ligne (%). Vide = taux du document parent.",
    )

    class Meta:
        abstract = True

    @property
    def total_ht(self):
        """Miroir EXACT de ``ventes.LigneDevis.total_ht`` (sémantique Decimal).

        ``quantite * prix_unitaire * (1 - remise / 100)`` — pas de quantize :
        l'arrondi au centime reste à la charge de l'agrégat (panier TVA), comme
        dans tout le money-path existant."""
        return self.quantite * self.prix_unitaire * (1 - self.remise / 100)

    @property
    def taux_tva_effectif(self):
        """Taux réellement appliqué : celui de la ligne, sinon celui du parent.

        Repli sur ``getattr(parent, 'taux_tva', None)`` via ``PARENT_FIELD`` —
        MÊME contrat que ``ventes.LigneDevis.taux_tva_effectif`` (``self.taux_tva
        if not None else self.devis.taux_tva``)."""
        if self.taux_tva is not None:
            return self.taux_tva
        parent = getattr(self, self.PARENT_FIELD, None) if self.PARENT_FIELD else None
        return getattr(parent, "taux_tva", None)


class TotauxDocumentMixin(models.Model):
    """Mixin abstrait des TOTAUX gelés + propriétés de repli (SCA31 — NOUVEAU).

    Reproduit à l'identique le patron gelé de ``ventes.Facture`` (montants figés
    à la création OU recomputés depuis les lignes) :

    * ``montant_ht`` / ``montant_tva`` / ``montant_ttc`` — champs ``DecimalField``
      NULLABLES (``max_digits=12``, ``decimal_places=2`` — comme Facture/Avoir) :
      NULL = document calculé depuis ses lignes ; renseignés = totaux FIGÉS
      (acompte, tranche d'échéancier…), qui priment ;
    * ``total_ht`` / ``total_tva`` / ``total_ttc`` — propriétés de REPLI : si le
      montant figé correspondant est renseigné, on le renvoie ; sinon on
      recompute depuis les lignes.

    Le kit ne connaît pas le ``related_name`` des lignes (chaque document nomme
    le sien), donc la sous-classe déclare ``LIGNES_ATTR`` = le nom de
    l'accesseur inverse des lignes (ex. ``'lignes'``). Le repli TVA du kit est
    VOLONTAIREMENT SIMPLE (somme de ``ligne.total_ht × taux_effectif/100`` par
    ligne) : le kit est un socle NEUF pour de NOUVEAUX documents, il n'a pas à
    répliquer la réconciliation par panier ``tva_buckets`` de ventes (spécifique
    au money-path devis/facture, hors périmètre du kit). Un document qui a besoin
    de la ventilation multi-taux au centime surcharge simplement ``total_tva``.

    Abstrait ⇒ aucune table, aucune migration. GÉNÉRIQUE : aucune app domaine.
    """

    #: Nom de l'accesseur inverse des lignes du document (déclaré par la
    #: sous-classe, ex. ``'lignes'``). Sert au recompute de repli.
    LIGNES_ATTR: str = "lignes"

    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        abstract = True

    def _lignes(self):
        """QuerySet/itérable des lignes via ``LIGNES_ATTR`` (repli liste vide)."""
        manager = getattr(self, self.LIGNES_ATTR, None)
        if manager is None:
            return []
        return manager.all()

    @property
    def total_ht(self):
        """Montant HT figé s'il existe, sinon somme des ``ligne.total_ht``.

        Miroir du patron ``ventes.Facture.total_ht`` (montant figé → repli
        lignes)."""
        if self.montant_ht is not None:
            return self.montant_ht
        return sum((ligne.total_ht for ligne in self._lignes()), Decimal("0"))

    @property
    def total_tva(self):
        """TVA figée s'il existe, sinon somme ligne par ligne (taux effectif).

        Repli simple : ``Σ ligne.total_ht × taux_tva_effectif / 100`` — chaque
        ligne applique son taux effectif (ligne sinon parent, cf.
        ``LigneDocumentMetier.taux_tva_effectif``). Un document à réconciliation
        par panier au centime surcharge cette propriété."""
        if self.montant_tva is not None:
            return self.montant_tva
        total = Decimal("0")
        for ligne in self._lignes():
            taux = ligne.taux_tva_effectif
            if taux is None:
                continue
            total += ligne.total_ht * (Decimal(str(taux)) / Decimal("100"))
        return total

    @property
    def total_ttc(self):
        """TTC figé s'il existe, sinon ``total_ht + total_tva`` (patron Facture)."""
        if self.montant_ttc is not None:
            return self.montant_ttc
        return self.total_ht + self.total_tva


# ─────────────────────────────────────────────────────────────────────────────
# SCA32 — Factory de viewset du kit : scoping + numérotation + chatter en 1 ligne.
# ─────────────────────────────────────────────────────────────────────────────


def document_viewset(model, serializer, *, prefix, padding=4, period="monthly",
                     base=None, chatter_mixin=None, **attrs):
    """Compose un ViewSet complet pour un document du kit en UNE déclaration.

    Un NOUVEAU type de document ⇒ ~1 ligne : ``MonDocViewSet =
    document_viewset(MonDoc, MonDocSerializer, prefix='MDOC')``. Le viewset
    produit COMPOSE, sans rien re-coder :

    * ``CompanyScopedModelViewSet`` (ARC2) — ``get_queryset`` scopé
      ``request.user.company`` + ``company`` forcée côté serveur ;
    * ``ChatterViewSetMixin`` (ARC8) — actions ``chatter/historique`` (GET) et
      ``chatter/noter`` (POST) adossées au chatter générique ``records.Activity``
      (auteur + société toujours posés côté serveur) ;
    * ``core.numbering.create_with_reference`` (ARC6) appelé en
      ``perform_create`` avec le ``prefix`` déclaré — référence race-safe
      (plus-haut-utilisé+1, savepoint+retry), JAMAIS ``count()+1`` (règle repo).

    Args:
        model: le modèle document (sous-classe de ``DocumentMetier``) — doit
            porter un champ ``reference`` unique par ``(company, reference)``.
        serializer: le ``ModelSerializer`` du document.
        prefix: préfixe de référence (ex. ``'MDOC'`` → ``MDOC-202607-0001``).
        padding / period: transmis à ``next_reference`` (défauts = historique
            mensuel 4-pad).
        base: base viewset alternative (défaut ``CompanyScopedModelViewSet``) —
            pour composer un document qui a en plus son propre ``get_permissions``
            (le passer via ``attrs``) ou une base déjà spécialisée.
        **attrs: attributs de classe supplémentaires (``permission_classes``,
            ``get_permissions``, ``filterset_fields``…) fusionnés dans la classe
            générée.

    Points d'extension NOMMÉS (YAPIC1 pagination / YAPIC2 filtres) : hérités du
    socle ``CompanyScopedModelViewSet``, NON implémentés ici (byte-identiques au
    défaut projet). Le grain fin des rôles reste YRBAC3.

    Retourne une CLASSE viewset prête à router. Elle est produite par ``type()``
    (dynamique) : le garde SCA4 (V) scanne des en-têtes ``class`` textuels, donc
    un viewset généré par factory n'a pas à figurer dans une baseline — et il est
    de toute façon basé socle par construction.
    """
    from core.numbering import create_with_reference
    from core.viewsets import CompanyScopedModelViewSet

    # Chatter ARC8 INJECTÉ, jamais importé ici : ``core`` (fondation) ne dépend
    # d'AUCUNE app — même records.views, qui tire tout le graphe domaine
    # (gestion_projet/sav/crm) via ses activités (contrat import-linter
    # core-foundation-is-a-base-layer + M1). L'app appelante passe son propre
    # ``ChatterViewSetMixin`` (elle, elle a le droit d'importer records) ; sans
    # lui, le viewset kit est simplement sans chatter (dégradation gracieuse).
    base_cls = base or CompanyScopedModelViewSet

    def perform_create(self, serializer_inst):
        """Force la société côté serveur ET attribue une référence race-safe.

        Compose ``TenantMixin.perform_create`` (company forcée) + ARC6
        (numérotation anti-collision) : la référence est générée dans un
        savepoint avec retry, jamais ``count()+1``. La société est TOUJOURS
        celle de l'utilisateur (jamais lue du corps de requête)."""
        company = self.request.user.company

        def _save(reference):
            return serializer_inst.save(company=company, reference=reference)

        create_with_reference(
            model, prefix, company, _save, padding=padding, period=period)

    namespace = {
        "queryset": model._default_manager.all(),
        "serializer_class": serializer,
        "perform_create": perform_create,
        "__doc__": (
            f"Viewset du document « {model.__name__} » composé par le kit "
            f"(SCA32) : scoping société (ARC2) + numérotation race-safe préfixe "
            f"« {prefix} » (ARC6) + chatter générique (ARC8)."
        ),
    }
    namespace.update(attrs)

    bases = (chatter_mixin, base_cls) if chatter_mixin is not None else (base_cls,)
    return type(f"{model.__name__}KitViewSet", bases, namespace)


# ─────────────────────────────────────────────────────────────────────────────
# SCA33 — Hook PDF du kit via ``core.pdf`` (allowlist ARC11 héritée verbatim).
# ─────────────────────────────────────────────────────────────────────────────


def render_document_pdf(instance, template, *, context=None, header=True,
                        footer=True, upload_to=None, upload_bucket=None):
    """Rend le PDF d'un document du kit en DÉLÉGUANT à ``core.pdf.render_pdf``.

    Le kit n'importe JAMAIS WeasyPrint : il délègue au service partagé ARC11
    (``core.pdf.render_pdf``), qui centralise l'import paresseux de WeasyPrint,
    le branding OPT-IN depuis ``CompanyProfile`` et l'upload MinIO optionnel. Le
    kit HÉRITE donc l'allowlist d'exclusion ARC11/ARC52 TELLE QUELLE — le garde
    ``scripts/check_platform.py`` (ARC52) le prouve : ce module ne figure pas
    dans ``GRANDFATHERED_WEASYPRINT`` et n'importe pas ``weasyprint``, donc il
    RESTE vert. EXCLUSION PERMANENTE (règle #4) inchangée : Devis/Facture/BC/Avoir
    gardent leurs chemins PDF propres (quote_engine ``/proposal`` + facture
    legacy), jamais ce hook.

    Args:
        instance: le document (sous-classe de ``DocumentMetier``) — sa société
            (``instance.company``) pilote le branding OPT-IN.
        template: nom du gabarit Django à rendre.
        context: contexte de rendu (défaut ``{'document': instance}`` enrichi de
            l'``instance`` fournie par l'appelant).
        header / footer: branding OPT-IN (défaut ``True`` — un NOUVEAU document
            du kit veut l'en-tête/pied brandés ; les pilotes ARC11 existants les
            laissaient à ``False`` pour un rendu inchangé, mais le kit est neuf).
        upload_to / upload_bucket: transmis tels quels à ``render_pdf`` (upload
            MinIO best-effort → retour ``(bytes, key)`` si ``upload_to`` fourni).

    Retour : ``bytes`` (PDF) — ou ``(bytes, key)`` si ``upload_to`` est fourni
    (contrat de ``core.pdf.render_pdf`` inchangé)."""
    from core.pdf import render_pdf

    ctx = {"document": instance}
    if context:
        ctx.update(context)
    return render_pdf(
        template=template,
        context=ctx,
        company=getattr(instance, "company", None),
        header=header,
        footer=footer,
        upload_to=upload_to,
        upload_bucket=upload_bucket,
    )
