"""TCH128 — balayage « même propriétaire » sur toutes les routes construites (reference/donnees.md
invariant 9 ; conception/socle.md §2.1).

Pour CHAQUE route construite et CHAQUE identifiant qu'elle reçoit (chemin, corps, paramètres, listes
d'ids de lot, de plan, de triage, de réordonnancement), trois essais : l'id d'un AUTRE compte de la
même société, l'id d'un compte d'une AUTRE société, un id que personne n'a. Les trois rendent la même
réponse (statut et corps, `request_id` mis à part) et n'écrivent rien : l'empreinte de toutes les
lignes de l'app et des activités ERP est identique avant et après. Un TÉMOIN rejoue la même requête
avec l'id du compte lui-même, dans un point de sauvegarde annulé : il réussit (2xx) et répond autrement
que l'id inconnu — sans lui, un refus dû à un corps mal formé passerait pour une preuve.

Genres écrits dans la table :
- REFUS : la règle générale (404, ou « Projet inexistant. » au champ, ou refus `introuvable` d'un lot
  ou d'une conversion, 200 partiel) ;
- LECTURE : `inclure`/`exclure` de `journee/proposition/` (exception de l'invariant 9 : ignorés) et les
  filtres de `taches/` répondent 200, comme pour un id inconnu ;
- IGNORE : `triage` de `journee/planifier/` (accepté, jamais lu : mode `express` seul, A17-T2) et la
  CLÉ de `valeurs.par_tache` d'un lot (une tâche hors de `ids`) : la requête réussit ; seules les
  lignes des autres comptes sont comparées.
Le lien ERP (`lien`) suit la visibilité de l'app cible (invariant 23), pas le propriétaire :
`test_liens.py` et `test_erp.py` le prouvent. `proprietaire_attendu` (le compte de la file hors ligne,
invariant 31) est essayé avec l'id d'un autre compte : 409 `autre_compte`, comme un id inconnu.

Liste FERMÉE : `ListeFermeeTests` (sans base) compare la table aux routes que `test_routes.est_construite`
voit construites — une route construite absente de la table fait échouer le test, comme une route
encore bouchon qui y serait ; chaque route à id de chemin a son essai `chemin`.

Horloge : les vues lisent le jour de la société ; le monde est daté de ce jour-là (`timezone.localdate()`
dans `setUpTestData`), comme dans `test_api_journee.py`. Aucun accès réseau : la lecture des agendas
externes et la vérification d'adresse sont remplacées.
"""
import datetime
from dataclasses import dataclass
from types import SimpleNamespace
from unittest import mock

from django.apps import apps as django_apps
from django.db import transaction
from django.db.models import Q
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.records.models import Activity
from apps.taches import agenda_externe as lecteur
from apps.taches.choix import CanalIncitation, ClePreference, Frequence, TypeIncitationEcran
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.rythme import IncitationCoach, Preference
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel, RegleRecurrence
from apps.taches.services.donnees import MODELES, _lignes_du_compte
from apps.taches.tests import fabriques
from apps.taches.tests.test_routes import PREFIXE, ROUTES, est_construite

#: Un id que personne n'a (borne des `IntegerField` de DRF et des clés `BigAutoField` respectée).
INCONNU = 2_000_000_000
REFUS, LECTURE, IGNORE = 'refus', 'lecture', 'ignore'
#: Clés sous lesquelles une réponse RÉPÈTE l'id refusé (`lot.json`, `convertir_activite.json`).
CLES_ECHO = ('id', 'activite_id')
UN_JOUR = datetime.timedelta(days=1)


class _Inconnu:
    """Un « monde » dont chaque objet porte un id que personne n'a (`x.T.pk`, `x.compte.pk`…)."""

    pk = INCONNU

    def __getattr__(self, nom):
        return self


MONDE_INCONNU = _Inconnu()


@dataclass(frozen=True)
class Cas:
    """Un identifiant reçu par une route. `requete(m, x)` → `(url sous PREFIXE, corps ou None)` : `m` est
    le monde du compte qui appelle, `x` celui dont vient l'id essayé (`cles` = ses objets essayés)."""

    methode: str
    chemin: str
    porte: str
    cles: tuple
    requete: object
    genre: str = REFUS
    echo: bool = False
    differe: bool = True


def _iso(jour):
    return jour.isoformat()


def _v(objet):
    """Le `lock_version` en base de `objet` (relu : les témoins sont annulés, la mémoire ne suit pas)."""
    return type(objet)._base_manager.filter(pk=objet.pk).values_list('lock_version', flat=True).get()


def _plan(m, lignes, **plus):
    return {'jour': _iso(m.jour), 'mode': 'express', 'lignes': lignes, **plus}


def _revue(m, **plus):
    return {'semaine': _iso(m.jour), 'decision': 'garder', **plus}


def _ligne(**champs):
    return {'lignes': [{'titre': 'Ligne', **champs}]}


def _tache_patch(m, **champs):
    return f'taches/{m.T.pk}/', {**champs, 'lock_version': _v(m.T)}


def _lot(ids, action, valeurs):
    return 'taches/lot/', {'ids': ids, 'action': action, 'valeurs': valeurs}


CAS_JOURNEE = (
    Cas('GET', 'journee/proposition/', '?exclure', ('T',),
        lambda m, x: (f'journee/proposition/?exclure={x.T.pk}', None), LECTURE, differe=False),
    Cas('GET', 'journee/proposition/', '?inclure', ('T',),
        lambda m, x: (f'journee/proposition/?inclure={x.T.pk}', None), LECTURE, differe=False),
    Cas('POST', 'journee/planifier/', 'lignes (tâche)', ('T',),
        lambda m, x: ('journee/planifier/', _plan(m, [{'type': 'tache', 'id': x.T.pk}]))),
    Cas('POST', 'journee/planifier/', 'lignes (activité ERP)', ('A',),
        lambda m, x: ('journee/planifier/', _plan(m, [{'type': 'activite', 'id': x.A.pk}]))),
    Cas('POST', 'journee/planifier/', 'essentielles', ('T',),
        lambda m, x: ('journee/planifier/', _plan(m, [], essentielles=[x.T.pk]))),
    Cas('POST', 'journee/planifier/', 'triage', ('T',),
        lambda m, x: ('journee/planifier/', _plan(m, [{'type': 'tache', 'id': m.T.pk}], triage=[x.T.pk])),
        IGNORE),
    Cas('POST', 'journee/essentiel/', 'tache_id', ('T',),
        lambda m, x: ('journee/essentiel/', {'tache_id': x.T.pk, 'essentielle': True})),
    Cas('POST', 'journee/alleger/', 'garder', ('T',),
        lambda m, x: ('journee/alleger/', {'jour': _iso(m.jour), 'garder': [x.T.pk]})),
    Cas('POST', 'journee/cloturer/', 'choix', ('T',),
        lambda m, x: ('journee/cloturer/', {'jour': _iso(m.jour), 'choix': [{'id': x.T.pk, 'choix': 'abandonner'}]})),
    Cas('GET', 'agenda/', '?projet', ('P',), lambda m, x: (f'agenda/?projet={x.P.pk}', None)),
)

CAS_SAISIE = (
    Cas('POST', 'saisie-rapide/', 'ids', ('B',), lambda m, x: ('saisie-rapide/', {'ids': [x.B.pk]})),
    Cas('POST', 'saisie-rapide/', 'projet_id', ('P',),
        lambda m, x: ('saisie-rapide/', {'texte': 'Appeler le fournisseur', 'projet_id': x.P.pk})),
    Cas('POST', 'saisie-rapide/', 'parent_id', ('T',),
        lambda m, x: ('saisie-rapide/', {**_ligne(), 'parent_id': x.T.pk})),
    Cas('POST', 'saisie-rapide/', 'lignes.projet_id', ('P',),
        lambda m, x: ('saisie-rapide/', _ligne(projet_id=x.P.pk))),
    Cas('POST', 'saisie-rapide/', 'lignes.section_id', ('S1',),
        lambda m, x: ('saisie-rapide/', _ligne(projet_id=m.P.pk, section_id=x.S1.pk))),
    Cas('POST', 'saisie-rapide/', 'lignes.etiquettes', ('E',),
        lambda m, x: ('saisie-rapide/', _ligne(etiquettes=[x.E.pk]))),
    Cas('POST', 'saisie-rapide/', 'lignes.recurrence', ('R2',),
        lambda m, x: ('saisie-rapide/', _ligne(recurrence=x.R2.pk, jour_prevu=_iso(m.jour + 2 * UN_JOUR)))),
    Cas('POST', 'saisie-rapide/', 'proprietaire_attendu', ('compte',),
        lambda m, x: ('saisie-rapide/', {'texte': 'Appeler le fournisseur', 'proprietaire_attendu': x.compte.pk})),
)

CAS_TACHES = (
    Cas('GET', 'taches/', '?projet', ('P',), lambda m, x: (f'taches/?projet={x.P.pk}', None), LECTURE),
    Cas('GET', 'taches/', '?section', ('S1',), lambda m, x: (f'taches/?section={x.S1.pk}', None), LECTURE),
    Cas('GET', 'taches/', '?etiquette', ('E',), lambda m, x: (f'taches/?etiquette={x.E.pk}', None), LECTURE),
    Cas('POST', 'taches/', 'projet_id', ('P2',), lambda m, x: ('taches/', {'titre': 'Neuve', 'projet_id': x.P2.pk})),
    Cas('POST', 'taches/', 'section_id', ('S1',),
        lambda m, x: ('taches/', {'titre': 'Neuve', 'projet_id': m.P.pk, 'section_id': x.S1.pk})),
    Cas('POST', 'taches/', 'parent_id', ('T',), lambda m, x: ('taches/', {'titre': 'Neuve', 'parent_id': x.T.pk})),
    Cas('POST', 'taches/', 'etiquettes', ('E',), lambda m, x: ('taches/', {'titre': 'Neuve', 'etiquettes': [x.E.pk]})),
    Cas('POST', 'taches/', 'recurrence', ('R2',),
        lambda m, x: ('taches/', {'titre': 'Neuve', 'recurrence': x.R2.pk, 'jour_prevu': _iso(m.jour + 2 * UN_JOUR)})),
    Cas('POST', 'taches/', 'proprietaire_attendu', ('compte',),
        lambda m, x: ('taches/', {'titre': 'Neuve', 'proprietaire_attendu': x.compte.pk})),
    Cas('GET', 'taches/{id}/', 'chemin', ('T',), lambda m, x: (f'taches/{x.T.pk}/', None)),
    Cas('PATCH', 'taches/{id}/', 'chemin', ('T',),
        lambda m, x: (f'taches/{x.T.pk}/', {'titre': 'Renommée', 'lock_version': _v(m.T)})),
    Cas('PATCH', 'taches/{id}/', 'projet_id', ('P2',), lambda m, x: _tache_patch(m, projet_id=x.P2.pk)),
    Cas('PATCH', 'taches/{id}/', 'section_id', ('S1',), lambda m, x: _tache_patch(m, section_id=x.S1.pk)),
    Cas('PATCH', 'taches/{id}/', 'bloquee_par_id', ('T2',), lambda m, x: _tache_patch(m, bloquee_par_id=x.T2.pk)),
    Cas('PATCH', 'taches/{id}/', 'etiquettes', ('E',), lambda m, x: _tache_patch(m, etiquettes=[x.E.pk])),
    Cas('DELETE', 'taches/{id}/', 'chemin', ('T',), lambda m, x: (f'taches/{x.T.pk}/', None)),
)

CAS_ACTIONS = (
    Cas('POST', 'taches/{id}/planifier/', 'chemin', ('T',), lambda m, x: (
        f'taches/{x.T.pk}/planifier/', {'jour_prevu': _iso(m.jour + 3 * UN_JOUR), 'lock_version': _v(m.T)})),
    Cas('POST', 'taches/{id}/planifier/', 'proprietaire_attendu', ('compte',), lambda m, x: (
        f'taches/{m.T.pk}/planifier/', {'jour_prevu': _iso(m.jour + 3 * UN_JOUR), 'lock_version': _v(m.T),
                                        'proprietaire_attendu': x.compte.pk})),
    Cas('POST', 'taches/{id}/terminer/', 'chemin', ('T',), lambda m, x: (f'taches/{x.T.pk}/terminer/', None)),
    Cas('POST', 'taches/{id}/terminer/', 'proprietaire_attendu', ('compte',),
        lambda m, x: (f'taches/{m.T.pk}/terminer/', {'proprietaire_attendu': x.compte.pk})),
    Cas('POST', 'taches/{id}/rouvrir/', 'chemin', ('T',), lambda m, x: (f'taches/{x.T.pk}/rouvrir/', None)),
    Cas('POST', 'taches/{id}/rouvrir/', 'proprietaire_attendu', ('compte',),
        lambda m, x: (f'taches/{m.T.pk}/rouvrir/', {'proprietaire_attendu': x.compte.pk})),
    Cas('POST', 'taches/{id}/trancher/', 'chemin', ('T',),
        lambda m, x: (f'taches/{x.T.pk}/trancher/', {'choix': 'aujourdhui'})),
    Cas('POST', 'taches/{id}/sauter/', 'chemin', ('TR',), lambda m, x: (f'taches/{x.TR.pk}/sauter/', None)),
    Cas('POST', 'taches/{id}/attendre/', 'chemin', ('T',),
        lambda m, x: (f'taches/{x.T.pk}/attendre/', {'en_attente_de': 'Lydec'})),
    Cas('POST', 'taches/{id}/recu/', 'chemin', ('T',), lambda m, x: (f'taches/{x.T.pk}/recu/', None)),
    Cas('POST', 'taches/{id}/reordonner/', 'chemin', ('T',),
        lambda m, x: (f'taches/{x.T.pk}/reordonner/', {'liste': 'projet', 'apres_id': m.T2.pk})),
    Cas('POST', 'taches/{id}/reordonner/', 'avant_id', ('T2',),
        lambda m, x: (f'taches/{m.T.pk}/reordonner/', {'liste': 'projet', 'avant_id': x.T2.pk})),
    Cas('POST', 'taches/{id}/reordonner/', 'apres_id', ('T2',),
        lambda m, x: (f'taches/{m.T.pk}/reordonner/', {'liste': 'projet', 'apres_id': x.T2.pk})),
    Cas('POST', 'taches/{id}/restaurer/', 'chemin', ('D',), lambda m, x: (f'taches/{x.D.pk}/restaurer/', None)),
    Cas('POST', 'taches/{id}/rappels/', 'chemin', ('T',), lambda m, x: (
        f'taches/{x.T.pk}/rappels/', {'jour': _iso(m.jour + UN_JOUR), 'heure': '10:00'})),
    Cas('POST', 'taches/{id}/changement/apercu/', 'chemin', ('T',), lambda m, x: (
        f'taches/{x.T.pk}/changement/apercu/', {'geste': 'renommer', 'titre': 'Nouveau titre'})),
)

CAS_LOT_ERP = (
    Cas('POST', 'taches/lot/', 'ids', ('T',), lambda m, x: _lot([x.T.pk], 'prioriser', {'priorite': 3}),
        echo=True),
    Cas('POST', 'taches/lot/', 'valeurs.projet_id', ('P2',),
        lambda m, x: _lot([m.T.pk], 'deplacer', {'projet_id': x.P2.pk})),
    Cas('POST', 'taches/lot/', 'valeurs.section_id', ('S1',),
        lambda m, x: _lot([m.T.pk], 'deplacer', {'projet_id': m.P.pk, 'section_id': x.S1.pk})),
    Cas('POST', 'taches/lot/', 'valeurs.par_tache.projet_id', ('P2',),
        lambda m, x: _lot([m.T.pk], 'deplacer', {'par_tache': {str(m.T.pk): {'projet_id': x.P2.pk}}})),
    Cas('POST', 'taches/lot/', 'valeurs.par_tache (clé)', ('T',),
        lambda m, x: _lot([m.T.pk], 'deplacer',
                          {'projet_id': m.P2.pk, 'par_tache': {str(x.T.pk): {'projet_id': m.P.pk}}}),
        IGNORE),
    Cas('POST', 'taches/lot/', 'valeurs.ajouter', ('E',),
        lambda m, x: _lot([m.T2.pk], 'etiqueter', {'ajouter': [x.E.pk]})),
    Cas('POST', 'taches/lot/', 'valeurs.retirer', ('E',),
        lambda m, x: _lot([m.T.pk], 'etiqueter', {'retirer': [x.E.pk]})),
    Cas('POST', 'taches/lier-activite/', 'activite_id', ('A',),
        lambda m, x: ('taches/lier-activite/', {'activite_id': x.A.pk})),
    Cas('POST', 'convertir-activite/', 'activite_ids', ('A',),
        lambda m, x: ('convertir-activite/', {'activite_ids': [x.A.pk]}), echo=True),
)

CAS_DETAILS = (
    Cas('DELETE', 'rappels/{id}/', 'chemin', ('RP',), lambda m, x: (f'rappels/{x.RP.pk}/', None)),
    Cas('POST', 'rappels/{id}/repeter/', 'chemin', ('RP',),
        lambda m, x: (f'rappels/{x.RP.pk}/repeter/', {'dans_minutes': 10})),
    Cas('PATCH', 'recurrences/{id}/', 'chemin', ('R',), lambda m, x: (f'recurrences/{x.R.pk}/', {'intervalle': 2})),
    Cas('POST', 'checklist/', 'tache_id', ('T',),
        lambda m, x: ('checklist/', {'tache_id': x.T.pk, 'libelle': 'Prix TTC'})),
    Cas('PATCH', 'checklist/{id}/', 'chemin', ('C1',), lambda m, x: (f'checklist/{x.C1.pk}/', {'fait': True})),
    Cas('DELETE', 'checklist/{id}/', 'chemin', ('C1',), lambda m, x: (f'checklist/{x.C1.pk}/', None)),
    Cas('POST', 'checklist/{id}/reordonner/', 'chemin', ('C1',),
        lambda m, x: (f'checklist/{x.C1.pk}/reordonner/', {'apres_id': m.C2.pk})),
    Cas('POST', 'checklist/{id}/reordonner/', 'avant_id', ('C2',),
        lambda m, x: (f'checklist/{m.C1.pk}/reordonner/', {'avant_id': x.C2.pk})),
    Cas('POST', 'checklist/{id}/reordonner/', 'apres_id', ('C2',),
        lambda m, x: (f'checklist/{m.C1.pk}/reordonner/', {'apres_id': x.C2.pk})),
    Cas('POST', 'gestes/{id}/annuler/', 'chemin', ('G',), lambda m, x: (f'gestes/{x.G.pk}/annuler/', None)),
    Cas('POST', 'rythme/propositions/{id}/repondre/', 'chemin', ('CARTE',),
        lambda m, x: (f'rythme/propositions/{x.CARTE.pk}/repondre/', {'reponse': 'ok'})),
    Cas('PATCH', 'agendas-externes/{id}/', 'chemin', ('AG',),
        lambda m, x: (f'agendas-externes/{x.AG.pk}/', {'libelle': 'Bureau'})),
    Cas('DELETE', 'agendas-externes/{id}/', 'chemin', ('AG',), lambda m, x: (f'agendas-externes/{x.AG.pk}/', None)),
    Cas('POST', 'agendas-externes/{id}/rafraichir/', 'chemin', ('AG',),
        lambda m, x: (f'agendas-externes/{x.AG.pk}/rafraichir/', None)),
    Cas('POST', 'jetons/{id}/revoquer/', 'chemin', ('J',), lambda m, x: (f'jetons/{x.J.pk}/revoquer/', None)),
)

CAS_PROJETS = (
    Cas('GET', 'projets/{id}/', 'chemin', ('P',), lambda m, x: (f'projets/{x.P.pk}/', None)),
    Cas('PATCH', 'projets/{id}/', 'chemin', ('P',),
        lambda m, x: (f'projets/{x.P.pk}/', {'nom': 'Renommé', 'lock_version': _v(m.P)})),
    Cas('DELETE', 'projets/{id}/', 'chemin', ('P2',), lambda m, x: (f'projets/{x.P2.pk}/', None)),
    Cas('POST', 'projets/{id}/reordonner/', 'chemin', ('P',),
        lambda m, x: (f'projets/{x.P.pk}/reordonner/', {'apres_id': m.P2.pk})),
    Cas('POST', 'projets/{id}/reordonner/', 'avant_id', ('P2',),
        lambda m, x: (f'projets/{m.P.pk}/reordonner/', {'avant_id': x.P2.pk})),
    Cas('POST', 'projets/{id}/reordonner/', 'apres_id', ('P2',),
        lambda m, x: (f'projets/{m.P.pk}/reordonner/', {'apres_id': x.P2.pk})),
    Cas('GET', 'projets/{id}/vue/', 'chemin', ('P',), lambda m, x: (f'projets/{x.P.pk}/vue/', None)),
    Cas('POST', 'projets/{id}/planification/apercu/', 'chemin', ('P',),
        lambda m, x: (f'projets/{x.P.pk}/planification/apercu/', {'texte': 'Visite'})),
    Cas('POST', 'projets/{id}/planification/', 'chemin', ('P',), lambda m, x: (
        f'projets/{x.P.pk}/planification/',
        {'actions': [{'titre': 'Réserver le stand', 'quand': 'aujourdhui'}], 'lock_version': _v(m.P)})),
    Cas('POST', 'projets/{id}/decaler/', 'chemin', ('P',),
        lambda m, x: (f'projets/{x.P.pk}/decaler/', {'delta_jours': 7, 'apercu': True})),
    Cas('POST', 'projets/{id}/terminer/', 'chemin', ('P',),
        lambda m, x: (f'projets/{x.P.pk}/terminer/', {'issue': 'atteint', 'taches_ouvertes': 'boite'})),
    Cas('POST', 'projets/{id}/terminer/', 'projet_cible_id', ('P2',), lambda m, x: (
        f'projets/{m.P.pk}/terminer/',
        {'issue': 'atteint', 'taches_ouvertes': 'deplacer', 'projet_cible_id': x.P2.pk})),
    Cas('POST', 'projets/{id}/rouvrir/', 'chemin', ('P',), lambda m, x: (f'projets/{x.P.pk}/rouvrir/', None)),
    Cas('POST', 'projets/{id}/restaurer/', 'chemin', ('PD',), lambda m, x: (f'projets/{x.PD.pk}/restaurer/', None)),
    Cas('POST', 'sections/', 'projet_id', ('P',),
        lambda m, x: ('sections/', {'projet_id': x.P.pk, 'nom': 'Étape neuve'})),
    Cas('PATCH', 'sections/{id}/', 'chemin', ('S1',), lambda m, x: (f'sections/{x.S1.pk}/', {'nom': 'Renommée'})),
    Cas('DELETE', 'sections/{id}/', 'chemin', ('S1',), lambda m, x: (f'sections/{x.S1.pk}/', None)),
    Cas('POST', 'sections/{id}/reordonner/', 'chemin', ('S1',),
        lambda m, x: (f'sections/{x.S1.pk}/reordonner/', {'apres_id': m.S2.pk})),
    Cas('POST', 'sections/{id}/reordonner/', 'avant_id', ('S2',),
        lambda m, x: (f'sections/{m.S1.pk}/reordonner/', {'avant_id': x.S2.pk})),
    Cas('POST', 'sections/{id}/reordonner/', 'apres_id', ('S2',),
        lambda m, x: (f'sections/{m.S1.pk}/reordonner/', {'apres_id': x.S2.pk})),
    Cas('PUT', 'revue/projets/{projet_id}/', 'chemin', ('P',), lambda m, x: (f'revue/projets/{x.P.pk}/', _revue(m))),
    Cas('PUT', 'revue/projets/{projet_id}/', 'prochaine_action_id', ('T',),
        lambda m, x: (f'revue/projets/{m.P.pk}/', _revue(m, prochaine_action_id=x.T.pk))),
)

CAS = CAS_JOURNEE + CAS_SAISIE + CAS_TACHES + CAS_ACTIONS + CAS_LOT_ERP + CAS_DETAILS + CAS_PROJETS

#: Routes construites qui ne reçoivent AUCUN id d'objet : la ligne lue ou écrite est toujours celle du
#: compte (`preferences/{cle}/` : une CLÉ, relue par `preference_de(user, cle)`). Balayées pour « rien
#: n'est écrit chez un autre compte » : `requete(m)` → `(url, corps)`.
SANS_ID = {
    ('GET', 'aujourdhui/'): lambda m: ('aujourdhui/', None),
    ('GET', 'aujourdhui/ailleurs/'): lambda m: ('aujourdhui/ailleurs/', None),
    ('GET', 'badge/'): lambda m: ('badge/', None),
    ('POST', 'vu/'): lambda m: ('vu/', {'ecran': 'aujourdhui'}),
    ('GET', 'journee/cloture/'): lambda m: ('journee/cloture/', None),
    ('GET', 'recherche/'): lambda m: ('recherche/?q=Projet', None),
    ('GET', 'supprimees/'): lambda m: ('supprimees/', None),
    ('GET', 'gestes/'): lambda m: ('gestes/', None),
    ('GET', 'projets/'): lambda m: ('projets/', None),
    ('POST', 'projets/'): lambda m: ('projets/', {'nom': 'Projet neuf'}),
    ('POST', 'projets/trier-par-priorite/'): lambda m: ('projets/trier-par-priorite/', None),
    ('GET', 'revue/projets/'): lambda m: ('revue/projets/', None),
    ('GET', 'rythme/'): lambda m: ('rythme/', None),
    ('POST', 'rythme/'): lambda m: ('rythme/', {'mode': 'pousser', 'objectif': 7}),
    ('POST', 'preferences/'): lambda m: ('preferences/', {'cle': 'heure_limite', 'valeur': '19:00'}),
    ('DELETE', 'preferences/{cle}/'): lambda m: ('preferences/heure_limite/', None),
    ('GET', 'reglages/'): lambda m: ('reglages/', None),
    ('PATCH', 'reglages/'): lambda m: ('reglages/', {'titres_tuile': True}),
    ('GET', 'coach/entete/'): lambda m: ('coach/entete/', None),
    ('GET', 'mes-donnees/'): lambda m: ('mes-donnees/', None),
    ('POST', 'tout-effacer/'): lambda m: ('tout-effacer/', {'confirmation': 'EFFACER'}),
    ('GET', 'agendas-externes/'): lambda m: ('agendas-externes/', None),
    ('POST', 'agendas-externes/'): lambda m: ('agendas-externes/', {'url': 'https://agenda.example/b.ics'}),
    ('GET', 'jetons/'): lambda m: ('jetons/', None),
    ('POST', 'jetons/'): lambda m: ('jetons/', {'usage': 'flux'}),
    # Le projet de la capture est lu par son NOM parmi les projets du compte (test_capture.py : celui
    # d'un collègue reste du texte) ; aucun id n'est reçu.
    ('POST', 'capture/'): lambda m: ('capture/', {'titre': 'Appeler le fournisseur demain'}),
    ('GET', 'tuile/'): lambda m: ('tuile/', None),  # compte forcé (`force_authenticate`) : celui du jeton
    ('GET', 'flux/{jeton}.ics'): lambda m: ('flux/tqf_force.ics', None),  # idem : le jeton de l'adresse n'est pas lu
}
#: Écritures sans id d'une route qui en reçoit aussi (même vérification que `SANS_ID`).
AUSSI_SANS_ID = (
    ('POST', 'convertir-activite/', lambda m: ('convertir-activite/', {'toutes': True})),
)


# --- Le monde d'un compte ------------------------------------------------------------------------

def _monde(compte, jour):
    """Les mêmes objets pour chaque compte : projets, étapes, tâches (dont une supprimée et une
    occurrence de série), étiquette, check-list, règles, rappel, geste, carte, préférence, activité ERP,
    agenda externe ÉTEINT (jamais lu par la journée)."""
    societe = compte.company
    m = SimpleNamespace(compte=compte, jour=jour)
    fabriques.reglages(compte)
    m.P, m.P2, m.PD = fabriques.projet(compte), fabriques.projet(compte), fabriques.projet(compte)
    m.PD.soft_delete(compte, record=False)
    m.S1, m.S2 = fabriques.section(m.P), fabriques.section(m.P)
    m.T = fabriques.tache(compte, projet=m.P, jour_prevu=jour)
    m.T2 = fabriques.tache(compte, projet=m.P, jour_prevu=jour)
    m.T3 = fabriques.tache(compte, projet=m.P, section=m.S1)
    m.B = fabriques.tache(compte)
    m.D = fabriques.tache(compte, projet=m.P)
    m.D.soft_delete(compte, record=False)
    m.E = Etiquette.objects.create(company=societe, proprietaire=compte, nom='magasin')
    EtiquetteTache.objects.create(company=societe, tache=m.T, etiquette=m.E)
    m.C1 = ElementChecklist.objects.create(company=societe, tache=m.T, libelle='Prix', rang=1024)
    m.C2 = ElementChecklist.objects.create(company=societe, tache=m.T, libelle='Quantités', rang=2048)
    m.R = RegleRecurrence.objects.create(company=societe, proprietaire=compte, frequence=Frequence.HEBDO,
                                         jours_semaine='1000000', date_debut=jour - 7 * UN_JOUR)
    m.TR = fabriques.tache(compte, titre='Rapport hebdo', recurrence=m.R, occurrence_du=jour + UN_JOUR,
                           jour_prevu=jour + UN_JOUR)
    m.R2 = RegleRecurrence.objects.create(company=societe, proprietaire=compte, frequence=Frequence.QUOTIDIEN,
                                          date_debut=jour)
    m.RP = Rappel.objects.create(company=societe, proprietaire=compte, tache=m.T, jour=jour + UN_JOUR,
                                 heure=datetime.time(9, 0))
    m.G = GesteAnnulable.objects.create(company=societe, proprietaire=compte, type='modification',
                                        message='Modifiée', operations=[])
    m.CARTE = IncitationCoach.objects.create(
        company=societe, proprietaire=compte, jour=jour, type=TypeIncitationEcran.REVELATION, cle='mon_iphone',
        canal=CanalIncitation.ECRAN)
    Preference.objects.create(company=societe, proprietaire=compte, cle=ClePreference.HEURE_LIMITE, valeur='19:00')
    m.A = fabriques.activite(compte)
    m.AG = fabriques.agenda_externe(compte, actif=False)
    m.J, _clair = fabriques.jeton(compte, 'flux')
    return m


# --- Empreintes, réponses ------------------------------------------------------------------------

def empreinte():
    """Toutes les lignes (supprimées comprises) des modèles de l'app et des activités ERP."""
    modeles = [*django_apps.get_app_config('taches').get_models(), Activity]
    return {modele._meta.label: list(modele._base_manager.order_by('pk').values_list()) for modele in modeles}


def empreinte_de(*comptes):
    """Les lignes de ces comptes seulement (les 21 modèles par `_lignes_du_compte`, leurs activités)."""
    lignes = {}
    for compte in comptes:
        for cle in MODELES:
            lignes[(cle, compte.pk)] = list(_lignes_du_compte(cle, compte).order_by('pk').values_list())
        activites = Activity._base_manager.filter(Q(assigned_to=compte) | Q(created_by=compte))
        lignes[('activite', compte.pk)] = list(activites.order_by('pk').values_list())
    return lignes


def _contenu(reponse):
    if not reponse.content:
        return None
    try:
        return reponse.json()
    except ValueError:
        return reponse.content


def _normalise(valeur, ids=()):
    """Le corps sans `request_id` ; l'id refusé répété (`ids`, sous `CLES_ECHO` ou en clé) devient « ID »."""
    textes = {str(i) for i in ids}
    if isinstance(valeur, dict):
        return {('ID' if cle in textes else cle): (
            'ID' if cle in CLES_ECHO and valeur_ in ids else _normalise(valeur_, ids))
            for cle, valeur_ in valeur.items() if cle != 'request_id'}
    if isinstance(valeur, list):
        return [_normalise(element, ids) for element in valeur]
    return valeur


def _ids(cas, monde):
    return [getattr(monde, cle).pk for cle in cas.cles]


# --- Les tests ---------------------------------------------------------------------------------

class ListeFermeeTests(SimpleTestCase):
    """Sans base : la table couvre EXACTEMENT les routes construites."""

    def _construites(self):
        return {(methode, chemin) for methode, chemin in ROUTES if est_construite(methode, chemin)}

    def test_la_table_couvre_exactement_les_routes_construites(self):
        balayees = {(cas.methode, cas.chemin) for cas in CAS} | set(SANS_ID)
        construites = self._construites()
        self.assertEqual(sorted(construites - balayees), [], 'route construite absente du balayage')
        self.assertEqual(sorted(balayees - construites), [], 'route balayée mais pas construite ou inconnue')

    def test_chaque_id_de_chemin_est_essaye(self):
        for methode, chemin in sorted(self._construites() - set(SANS_ID)):
            if '{' not in chemin:
                continue
            with self.subTest(methode=methode, chemin=chemin):
                portes = {cas.porte for cas in CAS if (cas.methode, cas.chemin) == (methode, chemin)}
                self.assertIn('chemin', portes)

    def test_sans_id_ni_doublon(self):
        for methode, chemin in SANS_ID:
            with self.subTest(methode=methode, chemin=chemin):
                self.assertNotIn('{id}', chemin)
                self.assertNotIn('{projet_id}', chemin)
        portes = [(cas.methode, cas.chemin, cas.porte) for cas in CAS]
        self.assertEqual(len(portes), len(set(portes)))
        self.assertTrue(all(cas.genre in (REFUS, LECTURE, IGNORE) and cas.cles for cas in CAS))


class MemeProprietaireTests(TestCase):
    """Avec base (CI) : chaque id reçu d'un autre compte répond comme un id inconnu et n'écrit rien."""

    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        a, b = fabriques.societe('mp-a'), fabriques.societe('mp-b')
        cls.moi = _monde(fabriques.compte(a, nom='moi'), cls.jour)
        cls.autre = _monde(fabriques.compte(a, nom='autre'), cls.jour)
        cls.etranger = _monde(fabriques.compte(b, nom='etranger'), cls.jour)

    def setUp(self):
        for cible, valeur in (('lire_agenda_externe', ()), ('verifier_adresse', None)):
            remplacement = mock.patch.object(lecteur, cible, return_value=valeur)
            remplacement.start()
            self.addCleanup(remplacement.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.moi.compte)

    def _essais(self):
        return (('autre compte', self.autre), ('autre société', self.etranger), ('id inconnu', MONDE_INCONNU))

    def _envoyer(self, methode, url, corps):
        appel = getattr(self.api, methode.lower())
        if methode == 'GET':
            return appel(PREFIXE + url)
        return appel(PREFIXE + url, corps if corps is not None else {}, format='json')

    def _rendu(self, reponse, ids=()):
        return reponse.status_code, _normalise(_contenu(reponse), ids)

    def _temoin(self, cas):
        """La même requête avec l'id du compte lui-même, annulée : elle doit réussir."""
        url, corps = cas.requete(self.moi, self.moi)
        with transaction.atomic():
            reponse = self._envoyer(cas.methode, url, corps)
            transaction.set_rollback(True)
        self.assertTrue(200 <= reponse.status_code < 300, f'témoin refusé : {reponse.status_code} {_contenu(reponse)}')
        return self._rendu(reponse, _ids(cas, self.moi) if cas.echo else ())

    def _comparer(self, cas):
        """REFUS et LECTURE : trois réponses identiques, rien d'écrit, témoin réussi et différent."""
        avant = empreinte()
        rendus = {}
        for nom, monde in self._essais():
            url, corps = cas.requete(self.moi, monde)
            with transaction.atomic():
                reponse = self._envoyer(cas.methode, url, corps)
            rendus[nom] = self._rendu(reponse, _ids(cas, monde) if cas.echo else ())
            self.assertEqual(empreinte(), avant, f'{nom} : une écriture a eu lieu')
        self.assertEqual(rendus['autre compte'], rendus['id inconnu'])
        self.assertEqual(rendus['autre société'], rendus['id inconnu'])
        if cas.genre == LECTURE:
            self.assertEqual(rendus['id inconnu'][0], 200)
        temoin = self._temoin(cas)
        if cas.differe:
            self.assertNotEqual(temoin, rendus['id inconnu'], "l'id du compte ne change rien : essai vide")

    def _ignorer(self, cas):
        """IGNORE : la requête réussit pareil pour les trois ids ; les lignes des autres ne bougent pas."""
        autres = (self.autre.compte, self.etranger.compte)
        avant = empreinte_de(*autres)
        statuts = set()
        for nom, monde in self._essais():
            url, corps = cas.requete(self.moi, monde)
            with transaction.atomic():
                reponse = self._envoyer(cas.methode, url, corps)
                apres = empreinte_de(*autres)
                transaction.set_rollback(True)
            statuts.add(reponse.status_code)
            self.assertEqual(apres, avant, f'{nom} : une ligne d\'un autre compte a bougé')
        self.assertEqual(len(statuts), 1, statuts)
        self.assertTrue(200 <= statuts.pop() < 300)

    def test_un_id_d_un_autre_compte_repond_comme_un_id_inconnu(self):
        for cas in CAS:
            with self.subTest(methode=cas.methode, chemin=cas.chemin, porte=cas.porte):
                if cas.genre == IGNORE:
                    self._ignorer(cas)
                else:
                    self._comparer(cas)

    def test_sans_id_rien_n_est_ecrit_chez_un_autre_compte(self):
        autres = (self.autre.compte, self.etranger.compte)
        avant = empreinte_de(*autres)
        essais = [(methode, chemin, requete) for (methode, chemin), requete in SANS_ID.items()]
        for methode, chemin, requete in [*essais, *AUSSI_SANS_ID]:
            with self.subTest(methode=methode, chemin=chemin):
                url, corps = requete(self.moi)
                with transaction.atomic():
                    reponse = self._envoyer(methode, url, corps)
                    apres = empreinte_de(*autres)
                    transaction.set_rollback(True)
                self.assertTrue(200 <= reponse.status_code < 300, f'{reponse.status_code} {_contenu(reponse)}')
                self.assertEqual(apres, avant)
