"""Copilote vague 2 (BRF) — blocs ajoutés au point du matin et au dossier d'un lead.

Chaque bloc vient d'UN sélecteur public de l'app propriétaire (visites,
calepinage, installations, ventes, sav) : ce module ne lit jamais leurs modèles.
Un sélecteur rend ``None`` quand le compte n'a pas la lecture du module : la clé
est alors ABSENTE de la réponse (jamais vide, jamais une erreur). L'interrupteur
du copilote reste décidé par l'appelant (``copilote_allume_pour``).

Formes servies : ``contract_samples/assistant_digest_matin.json`` (``vague2``)
et ``contract_samples/assistant_lead_resume.json`` (``vague2``).
"""
import datetime
import json

#: Taille maximale (caractères) du point du matin servi au copilote : le modèle
#: n'en voit pas davantage.
LIMITE_CARACTERES = 5000
#: « Visite validée sans calepinage » : fenêtre des visites regardées.
FENETRE_VALIDEES_JOURS = 30
LIGNES_SANS_CALEPINAGE = 5


def _sans_calepinage(user, aujourdhui):
    """``{total, lignes}`` des visites validées des 30 derniers jours dont le
    lead est dans la portée de ``user`` et n'a AUCUN calepinage (le calepinage
    est lu chez son propriétaire, la visite chez le sien)."""
    from apps.calepinage.selectors import liste_calepinages
    from apps.visites.selectors import visites_validees_sans_calepinage

    from .portee_selectors import leads_visibles

    company = user.company
    depuis = aujourdhui - datetime.timedelta(days=FENETRE_VALIDEES_JOURS)
    candidates = visites_validees_sans_calepinage(company, depuis)
    ids = [c['lead_id'] for c in candidates]
    visibles = set(leads_visibles(user, company).filter(
        pk__in=ids).values_list('pk', flat=True))
    avec = set(liste_calepinages(company).filter(
        lead_id__in=ids).values_list('lead_id', flat=True))
    lignes = [c for c in candidates
              if c['lead_id'] in visibles and c['lead_id'] not in avec]
    return {'total': len(lignes), 'lignes': lignes[:LIGNES_SANS_CALEPINAGE]}


def _bloc_calepinages(user, aujourdhui, voit_les_leads):
    from apps.calepinage.selectors import brief_calepinage

    bloc = brief_calepinage(user, aujourdhui)
    if bloc is not None and voit_les_leads:
        bloc = {**bloc, 'sans_calepinage': _sans_calepinage(user, aujourdhui)}
    return bloc


def blocs_du_matin(user, aujourdhui, voit_les_leads):
    """Les blocs de la vague 2 du point du matin de ``user`` :
    ``{clé: bloc}`` sans les clés dont le sélecteur rend ``None``.
    ``voit_les_leads`` : le compte lit le CRM (ligne « visite validée sans
    calepinage », qui parle de leads)."""
    from apps.installations.selectors_assistant import brief_chantiers
    from apps.sav.selectors_assistant import brief_sav
    from apps.ventes.selectors_assistant import brief_ventes
    from apps.visites.selectors import brief_visites

    blocs = {
        'visites_equipe': brief_visites(user, aujourdhui),
        'calepinages': _bloc_calepinages(user, aujourdhui, voit_les_leads),
        'chantiers': brief_chantiers(user, aujourdhui),
        'impayes': brief_ventes(user, aujourdhui),
        'tickets': brief_sav(user, aujourdhui),
    }
    return {cle: bloc for cle, bloc in blocs.items() if bloc is not None}


def _listes_lignes(noeud):
    """Toutes les listes servies sous une clé ``lignes`` dans ``noeud``."""
    trouvees = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if cle == 'lignes' and isinstance(valeur, list):
                trouvees.append(valeur)
            trouvees.extend(_listes_lignes(valeur))
    return trouvees


def _taille(reponse):
    return len(json.dumps(reponse, ensure_ascii=False, default=str))


def borner_taille(reponse, limite=LIMITE_CARACTERES):
    """Ramène ``reponse`` à ``limite`` caractères en retirant des LIGNES (la
    dernière de la liste la plus lourde, tant qu'il le faut) ; les compteurs
    (``total``, ``ouverts``, …) ne sont jamais touchés. Rend ``reponse``."""
    while _taille(reponse) > limite:
        listes = [liste for liste in _listes_lignes(reponse) if liste]
        if not listes:
            break
        max(listes, key=_taille).pop()
    return reponse


# ── Dossier d'un lead (``crm.lead.resume``) ──────────────────────────────────

def _bloc_visite(lead):
    from apps.agent.ecrans import chemin
    from apps.visites.selectors import visites_pour_lead

    visites = visites_pour_lead(lead)
    if not visites:
        return None
    visite = visites[0]
    return {'id': visite['id'], 'statut': visite['statut'],
            'date': visite['date_realisee'] or visite['date_prevue'],
            'lien': chemin('visite', visite['id'])}


def _bloc_calepinage(user, lead):
    from apps.calepinage.services.assistant import (
        calepinage_ouvert_visible, resume_compact)

    ouvert, _hors_vue = calepinage_ouvert_visible(user, lead.pk)
    if ouvert is None:
        return None
    resume = resume_compact(ouvert)
    return {'id': resume['calepinage'], 'reference': resume['reference'],
            'a_faire': resume['a_faire'], 'lien': resume['lien']}


def _tete_de_devis(devis):
    """Le devis le plus avancé de ``devis`` (lignes du résumé, le plus récent
    d'abord) : un accepté d'abord, sinon le plus récent ; ``None`` sans devis."""
    acceptes = [d for d in devis if d['statut'] == 'accepte']
    return (acceptes or devis or [None])[0]


def _bloc_devis(tete):
    from apps.agent.ecrans import chemin

    if tete is None:
        return None
    return {'id': tete['id'], 'reference': tete['reference'],
            'statut': tete['statut'], 'lien': chemin('devis', tete['id'])}


def _bloc_chantier(user, lead):
    from apps.installations.selectors import chantiers_visibles
    from apps.installations.selectors_assistant import liste_chantiers

    lu = liste_chantiers(chantiers_visibles(user), user.company,
                         lead=lead.pk, limite=1)
    if not lu['lignes']:
        return None
    ligne = lu['lignes'][0]
    return {'id': ligne['id'], 'reference': ligne['reference'],
            'statut': ligne['statut'], 'lien': ligne['lien']}


def _bloc_factures(user, tete):
    """Reste à facturer / à payer de la vente du devis accepté ``tete``."""
    from apps.ventes.selectors import get_devis_by_pk
    from apps.ventes.selectors_assistant import vente_etat_compacte

    if tete is None or tete['statut'] != 'accepte':
        return None
    devis = get_devis_by_pk(tete['id'])
    if devis is None or devis.company_id != user.company_id:
        return None
    vente = vente_etat_compacte(devis, user)
    return {'devis_id': devis.pk,
            'reste_a_facturer_ttc': vente['etat']['reste_a_facturer_ttc'],
            'reste_a_payer_ttc': vente['etat']['reste_a_payer_ttc'],
            'a_faire': vente['a_faire'], 'lien': vente['lien']}


def _bloc_tickets(user, lead):
    from apps.sav.selectors_assistant import tickets_compacts

    if not lead.client_id:
        return {'ouverts': 0, 'lien': None}
    total, lignes = tickets_compacts(user, client=lead.client_id, limite=1)
    return {'ouverts': total, 'lien': lignes[0]['lien'] if lignes else None}


def bloc_dossier(user, lead, devis):
    """Le bloc ``dossier`` du résumé du lead : où il en est dans chaque module,
    ids et états seulement. Une clé n'est présente que si ``user`` lit le
    module ; elle vaut ``None`` quand rien n'existe pour ce lead. ``devis`` :
    la liste ``devis`` déjà lue par le résumé (jamais relue)."""
    from authentication.permissions import peut_lire_module
    from core.permissions import _user_has_or_legacy

    from apps.ventes.selectors_assistant import lit_les_factures

    tete = _tete_de_devis(devis)
    dossier = {}
    if _user_has_or_legacy(user, 'visites_voir'):
        dossier['visite'] = _bloc_visite(lead)
    if _user_has_or_legacy(user, 'calepinage_voir'):
        dossier['calepinage'] = _bloc_calepinage(user, lead)
    if lit_les_factures(user):
        dossier['devis'] = _bloc_devis(tete)
    if peut_lire_module(user, 'installations'):
        dossier['chantier'] = _bloc_chantier(user, lead)
    if lit_les_factures(user):
        dossier['factures'] = _bloc_factures(user, tete)
    if _user_has_or_legacy(user, 'sav_voir'):
        dossier['tickets'] = _bloc_tickets(user, lead)
    return dossier
