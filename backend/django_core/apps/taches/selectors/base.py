"""Sélecteur UNIQUE de l'app `taches` (reference/donnees.md §5, conception/socle.md §2.1).

Toute lecture passe par `taches_de(user)` et ses jumeaux : société ET propriétaire, toujours. Un
compte sans société ne lit rien. `user.company` peut avoir été posée en mémoire par une route à jeton
(MAJ-4) : c'est elle qui fait foi, jamais un paramètre reçu.
"""
import datetime
import operator
from functools import reduce

from django.db.models import Exists, Func, OuterRef, Q, TextField, Value
from django.db.models.functions import Lower

from apps.notifications.calendar_utils import jours_ouvres_entre
from apps.taches.choix import ClePreference
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.projets import Projet, Section
from apps.taches.models.rythme import Preference
from apps.taches.models.taches import Etiquette, EtiquetteTache, Rappel, Tache

#: Fenêtre où `prochain_jour_travaille` cherche (au-delà : `None`).
HORIZON_PROCHAIN_JOUR = 366
#: Masque `jours_travailles` par défaut : tous les jours, le calendrier de la société décide seul.
TOUS_LES_JOURS = '1111111'

#: Même règle que `confidentialite.est_confidentielle` (héritage 4 voies), écrite pour la base ;
#: `tests/test_selecteurs.py` vérifie que les deux disent la même chose.
TACHE_CONFIDENTIELLE = (
    Q(confidentiel=True) | Q(projet__confidentiel=True)
    | Q(parent__confidentiel=True) | Q(parent__projet__confidentiel=True))

CHAMPS_RECHERCHE = ('titre', 'notes', 'projet__nom')
CHAMPS_RECHERCHE_ASSISTANT = ('titre', 'projet__nom')  # jamais les notes sous l'en-tête assistant


def _du_compte(gestionnaire, user, champ='proprietaire'):
    company_id = getattr(user, 'company_id', None)
    if company_id is None or getattr(user, 'pk', None) is None:
        return gestionnaire.none()
    return gestionnaire.filter(company_id=company_id, **{champ: user})


def taches_de(user):
    """Tâches VIVANTES de `user`, dans sa société."""
    return _du_compte(Tache.objects, user)


def projets_de(user):
    """Projets VIVANTS de `user`, dans sa société."""
    return _du_compte(Projet.objects, user)


def sections_de(user):
    """Étapes des projets vivants de `user` (une étape n'a pas de propriétaire propre)."""
    return _du_compte(Section.objects, user, champ='projet__proprietaire').filter(projet__is_deleted=False)


def etiquettes_de(user):
    return _du_compte(Etiquette.objects, user)


def rappels_de(user):
    return _du_compte(Rappel.objects, user)


def gestes_de(user):
    return _du_compte(GesteAnnulable.objects, user)


def _preferences(user, *cles):
    lignes = _du_compte(Preference.objects, user).filter(cle__in=cles)
    return {ligne.cle: ligne.valeur for ligne in lignes}


def _date(texte):
    try:
        return datetime.date.fromisoformat(texte)
    except (TypeError, ValueError):
        return None


def _en_conge(jour, conges):
    return any(du <= jour <= au for du, au in conges)


def _conges(valeur):
    periodes = []
    for periode in valeur if isinstance(valeur, list) else ():
        du, au = _date((periode or {}).get('du')), _date((periode or {}).get('au'))
        if du is not None and au is not None:
            periodes.append((du, au))
    return periodes


def jours_travailles_de(user, du, au):
    """Ensemble des jours travaillés de `user` dans `[du, au]` : jours ouvrés de la société
    (`notifications.calendar_utils.jours_ouvres_entre`, fériés compris) ∩ son masque
    `jours_travailles` (lun→dim) − ses `conges`. Trois requêtes, quel que soit l'écart."""
    if getattr(user, 'company_id', None) is None:
        return set()
    prefs = _preferences(user, ClePreference.JOURS_TRAVAILLES, ClePreference.CONGES)
    masque = prefs.get(ClePreference.JOURS_TRAVAILLES)
    if not (isinstance(masque, str) and len(masque) == 7):
        masque = TOUS_LES_JOURS
    conges = _conges(prefs.get(ClePreference.CONGES))
    return {
        jour for jour in jours_ouvres_entre(user.company, du, au)
        if masque[jour.weekday()] == '1' and not _en_conge(jour, conges)
    }


def prochain_jour_travaille(user, jour):
    """Premier jour travaillé de `user` STRICTEMENT après `jour` (`None` s'il n'y en a aucun dans
    l'année qui suit)."""
    debut = jour + datetime.timedelta(days=1)
    jours = jours_travailles_de(user, debut, jour + datetime.timedelta(days=HORIZON_PROCHAIN_JOUR))
    return min(jours) if jours else None


def _sans_accents(expression):
    """`public.f_unaccent(<expression>)` : patron de `stock` (enveloppe de la migration stock 0148)."""
    return Func(expression, function='public.f_unaccent', output_field=TextField())


def normalise_sql(expression, sans_accents):
    return _sans_accents(expression) if sans_accents else expression


def _condition_terme(terme, alias, sans_accents):
    cible = normalise_sql(Value(terme.lower()), sans_accents)
    par_champ = reduce(operator.or_, [Q(**{f'{nom}__contains': cible}) for nom in alias])
    etiquettes = (EtiquetteTache.objects
                  .filter(tache=OuterRef('pk'))
                  .alias(_nom_q=normalise_sql(Lower('etiquette__nom'), sans_accents))
                  .filter(_nom_q__contains=cible))
    return par_champ | Exists(etiquettes)


def filtrer_q(qs, q, *, assistant=False):
    """Recherche `q` sur des tâches : chaque mot doit se trouver (ET) dans le titre, les notes, le nom
    du projet ou une étiquette, sans tenir compte des accents si la base le permet (sinon de la casse
    seulement). `assistant=True` : ni les notes, ni AUCUNE tâche confidentielle (IR17)."""
    termes = [terme for terme in (q or '').split() if terme]
    if not termes:
        return qs
    from apps.stock.selectors import recherche_sans_accents_disponible
    sans_accents = recherche_sans_accents_disponible()
    champs = CHAMPS_RECHERCHE_ASSISTANT if assistant else CHAMPS_RECHERCHE
    alias = {f'_q_{rang}': normalise_sql(Lower(champ), sans_accents) for rang, champ in enumerate(champs)}
    qs = qs.alias(**alias).filter(*[_condition_terme(terme, alias, sans_accents) for terme in termes])
    return qs.exclude(TACHE_CONFIDENTIELLE) if assistant else qs
