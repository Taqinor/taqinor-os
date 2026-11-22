"""R2-15 / R2-01 — la toiture DÉCLARÉE sur le lead, servie à l'atelier.

Bloc ``toiture_lead`` du contexte de conception (contrat
``contract_samples/calepinage_design_context.json``) : ce que la fiche du lead
dit de son toit et de son site (section « Toiture & site »), TEL QUEL. Chaque
champ vaut ``None`` quand le lead ne le dit pas — jamais une valeur devinée
(D-ACAL-7). Décision Q1 de la recette du 22/11 : l'atelier AFFICHE ces valeurs
en lecture et n'en préremplit aucune (ni pente, ni orientation).

``mode_pose`` est le seul champ qui agit : c'est le mode que le SERVEUR a posé
dans le document à la création du calepinage (CIQ112, ``modePoseDeclare``) et
que le traducteur applique déjà aux pans ; il est relu du DOCUMENT (jamais
recalculé depuis le lead, qui a pu changer depuis). L'atelier le relit lui
aussi dans le document pour son pan vierge ; ce bloc le redit à l'écran.

Lead lu par ``apps.crm.selectors`` (jamais ses modèles). LECTURE PURE.
"""
from ..services.valeurs import nombre

#: Champs à choix : servis par leur LIBELLÉ de fiche (``get_<champ>_display``).
CHAMPS_LIBELLES = ('type_surface', 'type_toiture', 'orientation', 'ombrage', 'structure_pref')
#: Champs numériques : ``float`` fini ou ``None``.
CHAMPS_NOMBRES = ('surface_toiture_m2', 'inclinaison_deg', 'nb_etages', 'roof_age')


def toiture_du_lead(company, calepinage, *, lire_lead=None):
    """Le bloc ``toiture_lead`` : toutes ses clés, toujours présentes."""
    lead = _lead(company, getattr(calepinage, 'lead_id', None), lire_lead)
    bloc = {champ: _libelle(lead, champ) for champ in CHAMPS_LIBELLES}
    bloc.update({champ: nombre(getattr(lead, champ, None)) for champ in CHAMPS_NOMBRES})
    bloc['ombrage_notes'] = str(getattr(lead, 'ombrage_notes', None) or '').strip() or None
    mode = (getattr(calepinage, 'roof_layout', None) or {}).get('modePoseDeclare')
    bloc['mode_pose'] = mode if isinstance(mode, str) and mode else None
    return bloc


def _lead(company, lead_id, lire_lead):
    """Le lead de la société (sélecteur CRM), ou ``None``."""
    if company is None or not lead_id:
        return None
    if lire_lead is None:
        from apps.crm.selectors import get_company_lead as lire_lead
    return lire_lead(company, lead_id)


def _libelle(lead, champ):
    """Le libellé de fiche d'un champ à choix renseigné, sinon ``None``."""
    if lead is None or not getattr(lead, champ, None):
        return None
    return str(getattr(lead, f'get_{champ}_display')()) or None
