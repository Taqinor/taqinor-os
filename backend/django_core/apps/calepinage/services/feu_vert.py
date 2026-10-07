"""CAL206 — feu vert bureau d'études, réutilisant VT3 (VTA5).

AUCUN SECOND MÉCANISME DE VALIDATION
---------------------------------------
Le feu vert existe déjà comme geste de visite technique : quand
``apps.visites.services.valider_visite`` l'accorde, ``core.events.
visite_validee`` (VTA5) est émis et ``apps.crm.receivers`` pose
``Lead.visite_effectuee`` sur la fiche du lead (+ le récap et une note de
chatter). Ce module ne recrée RIEN de tout ça : il se contente de LIRE
``Lead.visite_effectuee`` (via ``apps.crm.selectors.get_company_lead``, jamais
``apps.crm.models``) au moment où une variante serait retenue.

QUEL LEAD DÉBLOQUE
--------------------
Celui DU CALEPINAGE (``Calepinage.lead_id``) ; à défaut, celui de son devis
lié (``Calepinage.devis.lead_id``). Sans lead NI devis, la règle NE
S'APPLIQUE PAS — un calepinage entièrement autonome ne peut pas être bloqué
par une visite qui ne concerne personne de connu.

OÙ VIT L'INTERRUPTEUR
------------------------
La section ``presets`` de ``ParametresCalepinage`` (CAL45/CAL197) porte la
clé ``feu_vert_bureau_etudes`` (booléen) — off par défaut : une société qui
n'a jamais réglé cette option retrouve le comportement d'aujourd'hui,
strictement inchangé (aucune variante n'est jamais bloquée).

LE REFUS EST UNE ``rest_framework.exceptions.ValidationError``
-------------------------------------------------------------------
``services.variantes.retenir_variante`` est le SEUL chemin d'écriture de
« retenue » (CAL9) — c'est donc LÀ, et nulle part ailleurs, que ce refus doit
vivre pour qu'aucun appelant ne puisse le contourner. L'action HTTP
``retenir`` (``views/calepinages.py``) n'attrape aujourd'hui que
``VarianteRefusee`` ; une ``ValidationError`` DRF, elle, est convertie en 400
par l'enveloppe d'erreur GLOBALE (``core.exceptions.taqinor_exception_
handler``) sans qu'aucune vue n'ait besoin d'un ``except`` dédié — donc sans
toucher à ``views/calepinages.py``.
"""
from __future__ import annotations

#: Clé, DANS la section ``presets`` (CAL197), qui active l'exigence.
CLE_ACTIF = 'feu_vert_bureau_etudes'

#: ACAL116 (D-ACAL-24) — les trois gestes que la porte unique tient.
GESTE_RETENUE, GESTE_DEVIS, GESTE_EXECUTION = 'retenue', 'devis', 'execution'

#: ACAL116 — les PIÈCES D'EXÉCUTION refusées tant que l'approbation exigée
#: n'est pas à jour (les livrables d'ÉTUDE, eux, sont produits avec la
#: mention « Conception non approuvée »). Un code par porte HTTP gardée.
PIECES_EXECUTION = (
    'plan_pose',            # plan-pose.pdf
    'plan_cablage',         # plan-cablage.pdf
    'plan_cablage_dxf',     # plan-cablage.dxf
    'export_dxf',           # export.dxf
    'export_xlsx',          # classeur / nomenclature
    'export_csv',
    'pack_technique',       # dossier technique (GED)
    'dossier_fin_chantier',  # dossier de fin de chantier (GED)
)

MESSAGES_APPROBATION = {
    GESTE_DEVIS: ('Approbation à jour exigée avant de générer ou '
                  'resynchroniser le devis'),
    GESTE_EXECUTION: ("Approbation à jour exigée avant de produire une "
                      "pièce d'exécution"),
}
MESSAGES_FEU_VERT = {
    GESTE_RETENUE: ("Cette variante ne peut pas être retenue : la visite "
                    "technique du lead n'a pas encore reçu le feu vert "
                    "du bureau d'études."),
    GESTE_DEVIS: ("Le devis ne peut pas être généré ni resynchronisé : la "
                  "visite technique du lead n'a pas encore reçu le feu vert "
                  "du bureau d'études."),
    GESTE_EXECUTION: ("Cette pièce d'exécution ne peut pas être produite : "
                      "la visite technique du lead n'a pas encore reçu le "
                      "feu vert du bureau d'études."),
}

__all__ = ['CLE_ACTIF', 'option_active', 'lead_id_de_reference',
           'verifier_avant_publication', 'PIECES_EXECUTION',
           'GESTE_RETENUE', 'GESTE_DEVIS', 'GESTE_EXECUTION']


def option_active(company):
    """``True`` si la société exige le feu vert avant de retenir une
    variante. Lecture pure ; off par défaut (équivalence garantie CAL45)."""
    from ..selectors import parametres_de_societe

    presets = parametres_de_societe(company).get('presets') or {}
    return bool(presets.get(CLE_ACTIF))


def lead_id_de_reference(calepinage):
    """Le lead qui débloque : celui du calepinage, à défaut celui de son
    devis lié. ``None`` si ni l'un ni l'autre — la règle ne s'applique alors
    pas."""
    lead_id = getattr(calepinage, 'lead_id', None)
    if lead_id:
        return lead_id
    devis = getattr(calepinage, 'devis', None)
    return getattr(devis, 'lead_id', None) if devis is not None else None


def verifier_avant_publication(calepinage, *, geste=GESTE_RETENUE,
                               variante=None):
    """ACAL116 — LA porte unique (renommage de ``verifier_avant_retenue``) :
    ``geste`` ∈ ``retenue`` (retenir une variante), ``devis`` (générer /
    resynchroniser le devis), ``execution`` (pièce d'exécution).

    Refuse si l'option feu vert est active ET qu'aucun feu
    vert n'a été accordé au lead de référence.

    No-op quand l'option est désactivée, ou quand le calepinage n'a ni lead
    ni devis (la règle ne s'applique alors pas — et rien ne le cache).

    CALX348 — puis, au MÊME point d'entrée, l'approbation exigée
    (``_verifier_approbation_avant_retenue``), no-op elle aussi tant que la
    société ne l'exige pas.

    Raises:
        rest_framework.exceptions.ValidationError: refus, champ
            ``feu_vert`` (ou ``approbation``, CALX348) nommé — converti en
            400 par l'enveloppe d'erreur globale.
    """
    from rest_framework.exceptions import ValidationError

    from apps.crm.selectors import get_company_lead

    company = getattr(calepinage, 'company', None) if calepinage else None
    if option_active(company):
        lead_id = lead_id_de_reference(calepinage)
        if lead_id:
            lead = get_company_lead(company, lead_id, avec_corbeille=True)
            if lead is None or not getattr(lead, 'visite_effectuee', False):
                raise ValidationError({
                    'feu_vert': [MESSAGES_FEU_VERT.get(
                        geste, MESSAGES_FEU_VERT[GESTE_RETENUE])],
                })
    # CALX348 — la SECONDE vérification, au MÊME point d'entrée.
    if geste == GESTE_RETENUE:
        _verifier_approbation_avant_retenue(calepinage, variante=variante)
        return
    # ACAL116 (D-ACAL-24) — devis / pièce d'exécution : une approbation À
    # JOUR (non refusée, non périmée) quand la société l'exige.
    from .approbation import approbation_exigee, est_approuve

    if approbation_exigee(company) and not est_approuve(calepinage):
        raise ValidationError({
            'approbation': [MESSAGES_APPROBATION.get(
                geste, MESSAGES_APPROBATION[GESTE_EXECUTION])],
        })


# ── CALX348 — l'approbation exigée avant de retenir une variante ────────────
#
# Même discipline que le feu vert ci-dessus, et même point d'entrée : le
# refus vit ICI, appelé par ``verifier_avant_retenue`` — donc par
# ``services.variantes.retenir_variante``, le SEUL chemin d'écriture de
# « retenue » (CAL9). L'interrupteur est la clé ``approbation_exigee`` de la
# section ``presets`` (validée booléenne par ``services/presets.py``), off par
# défaut : réglage absent ⇒ AUCUNE lecture de la décision, comportement
# d'aujourd'hui strictement inchangé (D12). Le refus est une
# ``ValidationError`` DRF, donc un 400 par l'enveloppe d'erreur GLOBALE, sans
# toucher à ``views/calepinages.py``.

def _roles_approbateurs(company):
    """Les NOMS des rôles de la société qui portent le droit d'approuver.

    Lus en base (``apps.roles``, fondation) — jamais un nom de rôle ni de
    personne écrit en dur : c'est la matrice des rôles de la société qui dit
    qui approuve.
    """
    if company is None:
        return []
    from apps.roles.models import Role

    from ..permissions import CAL_APPROUVER

    return sorted(
        role.nom for role in Role.objects.filter(company=company).only(
            'nom', 'permissions')
        if CAL_APPROUVER in (role.permissions or []))


def _message_approbation_manquante(calepinage, roles):
    """Le refus FRANÇAIS, qui NOMME qui doit approuver (pur, testable)."""
    from .approbation import REFUSE

    decision = getattr(calepinage, 'approbation', None)
    decision = decision if isinstance(decision, dict) else {}
    if decision.get('etat') == REFUSE:
        motif = str(decision.get('motif') or '').strip()
        cause = ("sa conception a été REFUSÉE à la relecture"
                 + (f" (motif : {motif})" if motif else '')
                 + " et doit être reprise puis approuvée")
    elif decision.get('etat') == 'approuve':
        # ACAL114 — un accord PÉRIMÉ (empreinte imprimée changée depuis, ou
        # portant sur une autre conception que la variante retenue).
        cause = ("son approbation ne couvre plus la conception à retenir "
                 "(conception modifiée depuis l'accord) : elle est à redécider")
    else:
        cause = "sa conception n'a pas encore été approuvée"
    if roles:
        qui = ("par un porteur du droit « Approuver un calepinage » — "
               "rôle(s) : " + ', '.join(roles))
    else:
        qui = ("par un porteur du droit « Approuver un calepinage », que "
               "AUCUN rôle de la société ne porte encore : attribuez-le "
               "dans la gestion des rôles")
    return (f"Cette variante ne peut pas être retenue : {cause}, {qui}. "
            "La société exige cette approbation avant de retenir une "
            "variante.")


def _verifier_approbation_avant_retenue(calepinage, *, variante=None):
    """Refuse de retenir une variante si la société EXIGE l'approbation et
    que le calepinage n'est pas APPROUVÉ.

    No-op quand l'option est éteinte (la décision n'est alors même pas lue).

    Raises:
        rest_framework.exceptions.ValidationError: refus, champ
            ``approbation`` nommé — converti en 400 par l'enveloppe globale.
    """
    from rest_framework.exceptions import ValidationError

    from .approbation import approbation_exigee, est_approuve

    company = getattr(calepinage, 'company', None) if calepinage else None
    if not approbation_exigee(company):
        return
    # ACAL114 (D-ACAL-2, D-ACAL-11) — l'approbation NON périmée doit porter
    # sur la conception qui VA devenir courante : l'empreinte imprimée de la
    # variante retenue.
    empreinte = None
    if variante is not None:
        from apps.ventes.services import layout_hash

        empreinte = layout_hash(getattr(variante, 'roof_layout', None)) or ''
    if est_approuve(calepinage, empreinte=empreinte):
        return
    raise ValidationError({
        'approbation': [_message_approbation_manquante(
            calepinage, _roles_approbateurs(company))],
    })
