"""TCH32 — décalage d'un projet et modèles de projet (spec-4 §B et §G ; donnees.md §2.17), module PUR.

Aucun import Django, aucune base, aucune horloge : le jour J et la rectification « jour non travaillé →
prochain jour travaillé » (`prochain_ouvre(d) -> date`, rend `d` si `d` est travaillé) sont des paramètres.
Les dates rendues sont des chaînes ISO, comme dans `decalage.json` / `modele_instancier.json`.
Les objets lus (projet, sections, tâches) sont reconnus par leurs noms de champs (donnees.md §2).
"""
from dataclasses import dataclass
from datetime import timedelta

OUVERTES = ('a_faire', 'en_attente')
ANNULE = 'annule'
VERSION_MODELE = 1


@dataclass(frozen=True)
class Decalage:
    """`changements` : [{objet, id, champ, avant, apres}] ; `refus` : message de `delta_jours` ou None."""
    changements: tuple
    refus: str = None
    nb_avant: int = 0


def _iso(d):
    return d.isoformat() if d is not None else None


def _decale(d, delta, prochain_ouvre):
    return prochain_ouvre(d + timedelta(days=delta))


def _changement(objet, ident, champ, avant, apres):
    return {'objet': objet, 'id': ident, 'champ': champ, 'avant': _iso(avant), 'apres': _iso(apres)}


def _changements_champs(objet, o, champs, delta, prochain_ouvre):
    rendu = []
    for champ in champs:
        avant = getattr(o, champ)
        if avant is not None:
            apres = _decale(avant, delta, prochain_ouvre)
            if apres != avant:
                rendu.append(_changement(objet, o.id, champ, avant, apres))
    return rendu


def _phrase_refus(n):
    verbe = 'passerait' if n == 1 else 'passeraient'
    return f'{n} {"tâche" if n == 1 else "tâches"} {verbe} avant aujourd\'hui.'


def _passe_avant_aujourdhui(t, delta, J, prochain_ouvre):
    """Vrai si le jour prévu de `t` était ≥ J et tomberait avant J."""
    if t.jour_prevu is None or t.jour_prevu < J:
        return False
    return _decale(t.jour_prevu, delta, prochain_ouvre) < J


def decaler(delta, J, projet, sections, taches, prochain_ouvre):
    """Décale de `delta` jours calendaires les dates du projet, de ses étapes et de ses tâches ouvertes.

    Refus (aucun changement) si une tâche ouverte dont le jour prévu était ≥ J tomberait avant J.
    Les tâches faites ou abandonnées restent intactes.
    """
    ouvertes = [t for t in taches if t.statut in OUVERTES]
    nb = sum(1 for t in ouvertes if _passe_avant_aujourdhui(t, delta, J, prochain_ouvre))
    if nb:
        return Decalage(changements=(), refus=_phrase_refus(nb), nb_avant=nb)
    changements = _changements_champs('projet', projet, ('date_debut', 'echeance'), delta, prochain_ouvre)
    for s in sections:
        changements += _changements_champs('section', s, ('date_debut', 'date_fin'), delta, prochain_ouvre)
    for t in ouvertes:
        changements += _changements_champs('tache', t, ('jour_prevu', 'echeance'), delta, prochain_ouvre)
    return Decalage(changements=tuple(changements))


def _taches_figees(taches):
    """Tâches comptées (non abandonnées) et leurs sous-tâches, dans l'ordre reçu."""
    hautes = {t.id for t in taches if t.parent_id is None and t.statut != ANNULE}
    return [t for t in taches if t.statut != ANNULE and (t.parent_id is None or t.parent_id in hautes)]


def _origine(projet, sections, figees):
    """`date_debut` du projet, sinon la plus petite date du projet ; None si aucune."""
    if projet.date_debut is not None:
        return projet.date_debut
    dates = [projet.echeance]
    for s in sections:
        dates += [s.date_debut, s.date_fin]
    for t in figees:
        dates += [t.jour_prevu, t.echeance]
    dates = [d for d in dates if d is not None]
    return min(dates) if dates else None


def _ecart(d, origine):
    return (d - origine).days if d is not None and origine is not None else None


def _tache_figee(t, origine, index, sections_ids, inclure_notes):
    rendu = {
        'titre': t.titre,
        'section_index': sections_ids.get(t.section_id),
        'priorite': t.priorite,
        'jalon': bool(t.jalon),
        'decalage_jour': _ecart(t.jour_prevu, origine),
        'decalage_echeance': _ecart(t.echeance, origine),
        'parent_index': index.get(t.parent_id),
        'bloquee_par_index': index.get(t.bloquee_par),
        'checklist': list(t.checklist),
    }
    if inclure_notes:
        rendu['notes'] = t.notes
    return rendu


def figer_modele(projet, sections, taches, inclure_notes=False):
    """Contenu v1 d'un `ModeleProjet` : décalages à partir de l'origine, tâches comptées remises à faire."""
    figees = _taches_figees(taches)
    origine = _origine(projet, sections, figees)
    index = {t.id: i for i, t in enumerate(figees)}
    sections_ids = {s.id: i for i, s in enumerate(sections)}
    return {
        'v': VERSION_MODELE,
        'objectif': projet.objectif,
        'priorite': projet.priorite,
        'sections': [{'nom': s.nom, 'decalage_debut': _ecart(s.date_debut, origine),
                      'decalage_fin': _ecart(s.date_fin, origine)} for s in sections],
        'taches': [_tache_figee(t, origine, index, sections_ids, inclure_notes) for t in figees],
    }


def _date_modele(date_lancement, decalage, prochain_ouvre):
    if decalage is None:
        return None
    return _iso(_decale(date_lancement, decalage, prochain_ouvre))


def instancier(contenu, nom, date_lancement, prochain_ouvre):
    """Projet à créer depuis un modèle : chaque date = `date_lancement` + décalage, rectifiée (jour travaillé)."""
    if contenu.get('v') != VERSION_MODELE:
        raise ValueError(f'Version de modèle inconnue : {contenu.get("v")!r}.')

    def date_de(decalage):
        return _date_modele(date_lancement, decalage, prochain_ouvre)

    sections = [{'nom': s['nom'], 'date_debut': date_de(s.get('decalage_debut')),
                 'date_fin': date_de(s.get('decalage_fin'))} for s in contenu.get('sections', [])]
    taches = []
    for t in contenu.get('taches', []):
        tache = {k: t.get(k) for k in ('titre', 'section_index', 'priorite', 'jalon', 'parent_index',
                                       'bloquee_par_index')}
        tache.update(checklist=list(t.get('checklist', [])), jour_prevu=date_de(t.get('decalage_jour')),
                     echeance=date_de(t.get('decalage_echeance')))
        if 'notes' in t:
            tache['notes'] = t['notes']
        taches.append(tache)
    projet = {'nom': nom, 'objectif': contenu.get('objectif', ''), 'priorite': contenu.get('priorite', 0)}
    return {'projet': projet, 'sections': sections, 'taches': taches}
