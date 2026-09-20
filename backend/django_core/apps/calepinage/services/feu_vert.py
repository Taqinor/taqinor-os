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

__all__ = ['CLE_ACTIF', 'option_active', 'lead_id_de_reference',
           'verifier_avant_retenue']


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


def verifier_avant_retenue(calepinage):
    """Refuse de retenir une variante si l'option est active ET qu'aucun feu
    vert n'a été accordé au lead de référence.

    No-op quand l'option est désactivée, ou quand le calepinage n'a ni lead
    ni devis (la règle ne s'applique alors pas — et rien ne le cache).

    Raises:
        rest_framework.exceptions.ValidationError: refus, champ
            ``feu_vert`` nommé — converti en 400 par l'enveloppe d'erreur
            globale.
    """
    from rest_framework.exceptions import ValidationError

    from apps.crm.selectors import get_company_lead

    company = getattr(calepinage, 'company', None) if calepinage else None
    if not option_active(company):
        return
    lead_id = lead_id_de_reference(calepinage)
    if not lead_id:
        return
    lead = get_company_lead(company, lead_id)
    if lead is None or not getattr(lead, 'visite_effectuee', False):
        raise ValidationError({
            'feu_vert': [
                "Cette variante ne peut pas être retenue : la visite "
                "technique du lead n'a pas encore reçu le feu vert du "
                "bureau d'études.",
            ],
        })
