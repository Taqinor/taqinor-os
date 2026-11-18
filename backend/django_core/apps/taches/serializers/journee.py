"""Formes de la journée et de l'agenda (reference/api.md §2, §3.1 ; textes.md §2.2).

Tout est servi depuis les objets DÉJÀ chargés (`selectors.journee.lire_journee` avec
`formes.charger_items`) : aucune requête par ligne. Chaque ITEM reçoit ce que la forme ne calcule pas
seule par `calculs` (rang du jour, motif d'À revoir, raison de Proposé, explication, essentielle,
prévue au plan, peut_cloturer) ; les mots sont ceux de `textes.md` §2.2, les noms passent par
`nom_pour(…, usage)` (une requête « assistant » ne lit jamais le nom d'un projet confidentiel).
"""
from datetime import timedelta

from apps.taches.choix import RaisonPropose, SectionJournee
from apps.taches.confidentialite import ASSISTANT, ECRAN, est_confidentielle, nom_pour
from apps.taches.models.taches import Tache
from apps.taches.moteur import classement
from apps.taches.moteur.gabarits import CONSTANTES, format_jour
from apps.taches.serializers.formes import (
    ItemSerializer, PropositionSerializer, RendezVousSerializer, contexte, projet_court)

TACHE = classement.TACHE
ACTIVITE = classement.ACTIVITE
SEPARATEUR_FAITS = ' · '
SANS_PROJET = 'sans projet'
#: Ordre vertical des listes plafonnées à 200 lignes (api.md §2).
PLAFOND_LIGNES = 200


# --- Les mots d'une ligne (textes.md §2.2) -------------------------------------------------------

def _jj_mm(d):
    return f'{d.day:02d}/{d.month:02d}'


def _jj_mm_aaaa(d):
    return f'{d.day:02d}/{d.month:02d}/{d.year}'


def _accord(n, singulier, pluriel):
    return singulier if n < 2 else pluriel


def nom_du_projet(objet, usage, reglages):
    """Nom montré du projet d'une tâche (None sans projet)."""
    if getattr(objet, 'projet_id', None) is None:
        return None
    return nom_pour(objet.projet, usage, reglages)


def texte_raison(code, item, nom_projet, J):
    """Raison d'une ligne de Proposé (`RaisonPropose`, textes.md §2.2)."""
    if code == RaisonPropose.RETARD:
        hier = J - timedelta(days=1)
        return 'prévue hier' if item.jour_prevu == hier else f'prévue {format_jour(item.jour_prevu, J)}'
    if code == RaisonPropose.ECHEANCE_PASSEE:
        return f'échéance dépassée le {_jj_mm(item.echeance)}'
    if code == RaisonPropose.ECHEANCE_PROCHE:
        return f'échéance {format_jour(item.echeance, J)}'
    if nom_projet is None:
        return SANS_PROJET
    if code == RaisonPropose.PROCHAINE_ACTION:
        return f'prochaine action de {nom_projet}'
    return f'suite de {nom_projet}'


def _fait_date(code, valeur, J):
    if code == 'echeance_aujourdhui':
        return "échéance aujourd'hui"
    if code == 'echeance_depassee':
        return f'échéance dépassée le {_jj_mm(valeur)}'
    if code == 'activite_du_jour':
        return 'activité ERP du jour'
    if code == 'echeance_proche':
        echeance, n = valeur
        return (f'échéance {format_jour(echeance, J)} '
                f'({n} {_accord(n, "jour travaillé", "jours travaillés")})')
    if code == 'echeance_lointaine':
        return f'échéance {_jj_mm_aaaa(valeur)}'
    if code == 'prevue_aujourdhui':
        return "prévue aujourd'hui"
    if code == 'prevue_ce_soir':
        return 'prévue ce soir'
    if code == 'prevue_passee':
        return f'prévue {format_jour(valeur, J)}'
    return None


def _attente(objet, usage):
    """« en attente de : {qui} » ; hors de l'écran, le « qui » d'une confidentielle n'est jamais servi : le
    fait est omis (reference/regles.md « La confidentialité »)."""
    if usage != ECRAN and isinstance(objet, Tache) and est_confidentielle(objet):
        return None
    return f"en attente de : {getattr(objet, 'en_attente_de', '')}"


def _fait(code, valeur, objet, nom_projet, J, usage):
    texte = _fait_date(code, valeur, J)
    if texte is not None:
        return texte
    if code == 'en_attente':
        return _attente(objet, usage)
    autres = {
        'reportee_3_fois': f"reportée {CONSTANTES['reports']} fois",
        'projet_de_la_semaine': f'projet de la semaine {nom_projet}',
        'projet_prioritaire': f'projet prioritaire {nom_projet}',
        'priorite_haute': 'priorité haute',
        'priorite_moyenne': 'priorité moyenne',
        'dans_projet': f'dans {nom_projet}',
        'sans_projet': SANS_PROJET,
    }
    return autres.get(code)


def texte_explication(item, objet, nom_projet, J, travailles, usage):
    """≤ 3 faits joints par « · » (`classement.explication`, textes.md §2.2) ; `usage` de la route (`nom_pour`)."""
    faits = (_fait(code, valeur, objet, nom_projet, J, usage)
             for code, valeur in classement.explication(item, J, travailles))
    return SEPARATEUR_FAITS.join(f for f in faits if f)


# --- Calculs d'une journée ------------------------------------------------------------------------

class Rendu:
    """Ce qui sert à rendre les ITEM d'une journée : usage (écran ou assistant), réglages, et les
    `calculs` accumulés par clé `(type, id)`."""

    def __init__(self, journee, *, assistant=False, peut_cloturer=False, agendas=None):
        self.journee = journee
        self.usage = ASSISTANT if assistant else ECRAN
        self.assistant = bool(assistant)
        self.peut_cloturer = bool(peut_cloturer)
        self.agendas = dict(agendas or {})
        self.calculs = {}

    def nom_projet(self, cle):
        objet = self.journee.objets.get(cle)
        return nom_du_projet(objet, self.usage, self.journee.reglages) if cle[0] == TACHE else None

    def calcul(self, cle, *, raison=None):
        """Calcul d'une ligne : rang du jour, motif, raison OU explication, plan du jour."""
        journee, item = self.journee, self.journee.items[cle]
        placement = journee.placements.get(cle)
        ligne = journee.ligne_de(cle)
        calcul = {'rang': item.rang_jour, 'essentielle': bool(ligne and ligne.essentielle),
                  'prevue_au_plan': bool(ligne and ligne.prevue_au_plan),
                  'peut_cloturer': True if cle[0] == TACHE else self.peut_cloturer}
        if placement is not None and placement.section == SectionJournee.A_DECIDER:
            calcul['motif'] = placement.code
        if raison is not None:
            calcul['raison'] = {'code': str(raison),
                                'texte': texte_raison(raison, item, self.nom_projet(cle), journee.jour)}
        else:
            calcul['explication'] = texte_explication(item, journee.objets.get(cle), self.nom_projet(cle),
                                                      journee.jour, journee.travailles, self.usage)
        self.calculs[cle] = calcul
        return calcul

    def contexte(self):
        return contexte(assistant=self.assistant, reglages=self.journee.reglages, calculs=self.calculs,
                        agendas=self.agendas)

    def items(self, cles, raisons=None):
        """ITEM de chaque clé, dans l'ordre donné ; `raisons` : {clé: RaisonPropose}."""
        raisons = raisons or {}
        for cle in cles:
            self.calcul(cle, raison=raisons.get(cle))
        objets = [self.journee.objets[cle] for cle in cles]
        return list(ItemSerializer(objets, many=True, context=self.contexte()).data)


def plafonner(listes, plafond=PLAFOND_LIGNES):
    """Coupe des listes de clés, dans l'ordre vertical, à `plafond` lignes en tout → (listes, tronqué)."""
    sortie, reste = [], plafond
    for liste in listes:
        gardees = list(liste)[:max(0, reste)]
        reste -= len(gardees)
        sortie.append(gardees)
    return sortie, sum(len(liste) for liste in listes) > plafond


def suite_par_projet(rendu, plan_propose, raisons):
    """`suite_par_projet` : [{projet (forme courte ou nul), items}] dans l'ordre du tour."""
    groupes = []
    for _projet_id, file in plan_propose.suite_par_projet:
        cles = [(TACHE, item.id) for item in file]
        premier = rendu.journee.objets.get(cles[0]) if cles else None
        projet = premier.projet if premier is not None and premier.projet_id else None
        groupes.append({'projet': projet_court(projet, assistant=rendu.assistant, reglages=rendu.journee.reglages),
                        'items': rendu.items(cles, raisons)})
    return groupes


TOUR = (RaisonPropose.PROCHAINE_ACTION, RaisonPropose.ACTION_SUIVANTE)


def raisons_du_tour(plan_propose):
    """{clé: raison} des lignes proposées et de la suite dépliée : la première tâche sans jour d'un
    projet dont le tour n'a rien pris est sa prochaine action, les autres sa suite ; une tâche
    prévue plus tard n'a pas de raison (elle dit son jour)."""
    raisons = {(TACHE, item.id): raison for item, raison in plan_propose.pour_objectif}
    servis = {item.projet_id for item, raison in plan_propose.pour_objectif if raison in TOUR}
    for projet_id, file in plan_propose.suite_par_projet:
        premiere = projet_id not in servis
        for item in file:
            if item.jour_prevu is not None:
                continue
            raisons.setdefault((TACHE, item.id), TOUR[0] if premiere else TOUR[1])
            premiere = False
    return raisons


def proposition_forme(incitation, texte, boutons):
    """Forme PROPOSITION d'une `IncitationCoach` (texte et boutons rendus par l'appelant)."""
    calculs = {('proposition', incitation.pk): {'texte': texte, 'boutons': boutons}}
    return dict(PropositionSerializer(incitation, context=contexte(calculs=calculs)).data)


# --- L'agenda (api.md §3.1, §4 `agenda/`, TCH59) --------------------------------------------------

def jour_d_agenda(rendu, jour, *, ouvre, ferie, cles_jour, toute_la_journee=(), externes=()):
    """Un jour de l'agenda : Toute la journée (ERP), sans heure, blocs (à leur heure), échéances,
    rendez-vous externes (lecture seule, horodatés)."""
    items = rendu.journee.items
    au_jour = [cle for cle in cles_jour if items[cle].jour_prevu == jour]
    blocs = sorted((cle for cle in au_jour if items[cle].heure_debut is not None),
                   key=lambda cle: (items[cle].heure_debut, cle[1]))
    sans_heure = [cle for cle in au_jour if items[cle].heure_debut is None]
    echeances = [cle for cle in cles_jour if items[cle].echeance == jour and items[cle].jour_prevu != jour]
    return {
        'jour': jour.isoformat(), 'ouvre': ouvre, 'ferie': ferie,
        'toute_la_journee': list(toute_la_journee),
        'sans_heure': rendu.items(sans_heure), 'blocs': rendu.items(blocs), 'echeances': rendu.items(echeances),
        'externes': list(RendezVousSerializer(list(externes), many=True, context=rendu.contexte()).data),
    }


def mes_projets(rendu, candidates):
    """« Mes projets » de Planifier ma semaine : le tour complet (sans N), groupé par projet, chaque
    tâche avec sa raison (prochaine action, puis suite)."""
    groupes = []
    for _projet_id, file in classement.files_par_projet(candidates):
        cles = [(TACHE, item.id) for item in file]
        raisons = {cle: TOUR[0] if rang == 0 else TOUR[1] for rang, cle in enumerate(cles)}
        premier = rendu.journee.objets.get(cles[0])
        projet = premier.projet if premier is not None and premier.projet_id else None
        groupes.append({'projet': projet_court(projet, assistant=rendu.assistant, reglages=rendu.journee.reglages),
                        'items': rendu.items(cles, raisons)})
    return groupes
