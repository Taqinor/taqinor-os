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

from django.db import models

from core.models import TenantModel

__all__ = [
    "DocumentMetier",
    "TransitionRefusee",
    "changer_statut",
]


# ─────────────────────────────────────────────────────────────────────────────
# SCA30 — ``DocumentMetier`` : le bundle abstrait statut + transitions.
# ─────────────────────────────────────────────────────────────────────────────


class TransitionRefusee(Exception):
    """Levée par ``changer_statut()`` quand une transition n'est PAS permise par
    la table ``TRANSITIONS`` du document. Message en français, listant les
    cibles autorisées depuis le statut courant (utile pour un 400 côté API)."""


class DocumentMetier(TenantModel):
    """Socle abstrait d'un document métier : socle multi-tenant + statut gardé.

    Compose ARC1 (``core.TenantModel`` : FK ``company`` + timestamps) et ajoute
    le CONTRAT de cycle de vie d'un document :

    * une sous-classe déclare son énumération de statuts en surchargeant
      ``Statut`` (un ``models.TextChoices``) — le champ ``statut`` s'y adosse
      automatiquement (``choices``/``default`` dérivés de la sous-classe) ;
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
    #: sous-classe (calculé dans ``__init_subclass__``). Surchargeable.
    STATUT_INITIAL: str = ""

    #: Table de transitions déclarative — la SEULE source de vérité du graphe.
    #: ``{source: {cible, …}}``. Vide par défaut (une sous-classe la déclare).
    TRANSITIONS: dict = {}

    statut = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        """Adosse le champ ``statut`` aux ``Statut`` de la sous-classe CONCRÈTE.

        Django construit le champ hérité une seule fois sur l'abstrait ; pour que
        chaque document concret porte SES ``choices``/``default``, on ajuste le
        champ ``statut`` de la sous-classe à partir de son ``Statut`` et de son
        ``STATUT_INITIAL`` au moment où la classe est définie. Sans effet sur une
        sous-classe intermédiaire encore abstraite (pas de champs concrets)."""
        super().__init_subclass__(**kwargs)
        statuts = list(cls.Statut.choices)
        if not statuts:
            return
        if not cls.STATUT_INITIAL:
            cls.STATUT_INITIAL = cls.Statut.values[0]
        try:
            field = cls._meta.get_field("statut")
        except Exception:  # pragma: no cover - champ toujours présent
            return
        field.choices = statuts
        field.default = cls.STATUT_INITIAL

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
