"""ACAL800 — la forme du groupe électrogène d'appoint d'un site hors réseau.

``hors_reseau.groupe = {actif, puissance_kw, soc_demarrage_pct, soc_arret_pct,
heures_max_par_jour}`` : le groupe démarre quand l'état de charge tombe au
démarrage et s'arrête à l'arrêt (onduleur pour les pointes, groupe pour la
queue — PV*SOL, Victron). Ce module ne JUGE que la forme, au moment de
l'enregistrement ; la simulation (ACAL801) le lira. Aucun carburant, aucun
prix, aucune valeur par défaut : une grandeur manquante est refusée sous
``hors_reseau.groupe.<champ>``.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre

__all__ = ['CLES_GROUPE', 'Groupe', 'recharge_du_groupe', 'valider_groupe']

#: Les clés d'un groupe d'appoint, et AUCUNE autre.
CLES_GROUPE = ('actif', 'puissance_kw', 'soc_demarrage_pct', 'soc_arret_pct',
               'heures_max_par_jour')

#: Les bornes du calendrier et du pourcentage (définitions, pas des réglages).
HEURES_PAR_JOUR_MAX = 24
POURCENT_MAX = 100


def _lire(groupe, cle, refuser, plage):
    """La valeur NUMÉRIQUE de ``cle`` (jamais un booléen), ou un refus nommé."""
    brut = groupe.get(cle)
    valeur = None if isinstance(brut, bool) else _nombre(brut)
    if valeur is None:
        refuser("« %s » : saisissez un nombre (%s) ; aucune valeur n'est "
                "supposée (reçu : « %s »)." % (cle, plage, brut),
                'hors_reseau.groupe.%s' % cle)
    return valeur


def valider_groupe(groupe, refuser):
    """``refuser(motif, champ)`` est appelée sur la première faute ; ``None``
    et ``{actif: false}`` sont acceptés (le groupe n'est alors pas utilisé)."""
    if groupe is None:
        return
    if not isinstance(groupe, dict):
        refuser("« groupe » doit être un objet {actif, puissance_kw, "
                "soc_demarrage_pct, soc_arret_pct, heures_max_par_jour} "
                "ou null.", 'hors_reseau.groupe')
    inconnues = sorted(set(groupe) - set(CLES_GROUPE))
    if inconnues:
        refuser("Champ du groupe inconnu : « %s ». Champs admis : %s."
                % (inconnues[0], ', '.join(CLES_GROUPE)),
                'hors_reseau.groupe.%s' % inconnues[0])
    if not isinstance(groupe.get('actif'), bool):
        refuser("« actif » vaut vrai (groupe utilisé) ou faux.",
                'hors_reseau.groupe.actif')
    if not groupe['actif']:
        return
    puissance = _lire(groupe, 'puissance_kw', refuser, 'kW, au-dessus de 0')
    if puissance <= 0:
        refuser("« puissance_kw » : strictement positive (reçu : « %s »)."
                % puissance, 'hors_reseau.groupe.puissance_kw')
    demarrage = _lire(groupe, 'soc_demarrage_pct', refuser, '0 à 100 %')
    arret = _lire(groupe, 'soc_arret_pct', refuser, '0 à 100 %')
    for cle, valeur in (('soc_demarrage_pct', demarrage),
                        ('soc_arret_pct', arret)):
        if not 0 <= valeur <= POURCENT_MAX:
            refuser("« %s » : un pourcentage de 0 à 100 (reçu : « %s »)."
                    % (cle, valeur), 'hors_reseau.groupe.%s' % cle)
    if demarrage >= arret:
        refuser("« soc_demarrage_pct » (%s %%) doit être strictement sous "
                "« soc_arret_pct » (%s %%) : le groupe démarre batterie "
                "basse et s'arrête batterie rechargée." % (demarrage, arret),
                'hors_reseau.groupe.soc_demarrage_pct')
    heures = _lire(groupe, 'heures_max_par_jour', refuser, 'au-dessus de 0 '
                   "et jusqu'à 24 h")
    if not 0 < heures <= HEURES_PAR_JOUR_MAX:
        refuser("« heures_max_par_jour » : au-dessus de 0 et jusqu'à 24 "
                "(reçu : « %s »)." % heures,
                'hors_reseau.groupe.heures_max_par_jour')


MENTION_GROUPE = (
    "Groupe d'appoint de %g kW : il démarre quand l'état de charge au début "
    "du pas est au plus %g %% et s'arrête à %g %% au moins, dans la limite de "
    "%g h de marche par jour ; en marche il sert d'abord le besoin que le "
    "soleil ne couvre pas, puis recharge la batterie. Le courant de démarrage "
    "des moteurs n'est pas modélisé. Aucun carburant, aucun prix.")


#: ACAL1932 — pourquoi un groupe actif n'a jamais tourné (seuils SAISIS, jamais devinés).
CAUSE_SOUS_LA_VEILLE = (
    "le groupe ne démarre jamais : seuil de démarrage sous la veille "
    "(démarrage à %g %%, veille à %g %%) — la batterie cesse de se décharger "
    "à la veille, son état de charge n'atteint donc jamais le démarrage")


class Groupe:
    """La machine d'états du groupe (``services/hors_reseau.py`` la fait
    avancer pas à pas) : arrêt ⇄ marche, un budget d'heures par jour.

    ``reglage`` est la déclaration validée par :func:`valider_groupe` ;
    ``capacite_kwh`` la capacité utile de la banque ; ``pas_heures`` la durée
    d'un pas. Le démarrage et l'arrêt se lisent sur l'état de charge au DÉBUT
    du pas.
    """

    def __init__(self, reglage, capacite_kwh, pas_heures, veille_pct=None):
        self.puissance_kw = _nombre(reglage['puissance_kw'])
        self.soc_demarrage_pct = _nombre(reglage['soc_demarrage_pct'])
        self.soc_arret_pct = _nombre(reglage['soc_arret_pct'])
        self.heures_max_par_jour = _nombre(reglage['heures_max_par_jour'])
        self.veille_pct = _nombre(veille_pct)
        self._demarrage_kwh = capacite_kwh * self.soc_demarrage_pct / 100.0
        self._arret_kwh = capacite_kwh * self.soc_arret_pct / 100.0
        self._pas = pas_heures
        self._pas_par_jour = max(1, int(round(HEURES_PAR_JOUR_MAX / pas_heures)))
        self._en_marche = False
        self._heures_du_jour = 0.0
        self._par_mois = {}
        self.heures_de_marche = 0.0
        self.energie_fournie_kwh = 0.0

    def marcher(self, rang, etat_kwh, mois=None):
        """L'énergie (kWh) que le groupe peut donner à ce pas (0 à l'arrêt)."""
        if rang % self._pas_par_jour == 0:
            self._heures_du_jour = 0.0
        budget = (self._heures_du_jour + self._pas
                  <= self.heures_max_par_jour + 1e-9)
        if self._en_marche and etat_kwh >= self._arret_kwh:
            self._en_marche = False
        elif not self._en_marche and etat_kwh <= self._demarrage_kwh:
            self._en_marche = budget
        if self._en_marche and not budget:
            self._en_marche = False
        if not self._en_marche:
            return 0.0
        self._heures_du_jour += self._pas
        self.heures_de_marche += self._pas
        if mois is not None:
            self._ligne(mois)['heures_de_marche'] += self._pas
        return self.puissance_kw * self._pas

    def fournir(self, energie_kwh, mois=None):
        """Comptabilise l'énergie réellement donnée (charge servie + recharge)."""
        self.energie_fournie_kwh += energie_kwh
        if mois is not None:
            self._ligne(mois)['energie_fournie_kwh'] += energie_kwh

    def _ligne(self, mois):
        return self._par_mois.setdefault(mois, {
            'mois': mois, 'heures_de_marche': 0.0, 'energie_fournie_kwh': 0.0})

    def cause_inactif(self):
        """Le texte qui dit pourquoi le groupe n'a jamais tourné, ou ``None`` :
        seulement s'il n'a pas marché ET que son démarrage est sous la veille."""
        if (self.heures_de_marche > 0 or self.veille_pct is None
                or self.soc_demarrage_pct >= self.veille_pct):
            return None
        return CAUSE_SOUS_LA_VEILLE % (self.soc_demarrage_pct, self.veille_pct)

    def publier(self):
        """Le bloc ``hors_reseau.groupe`` sur la fenêtre simulée (l'étape le
        ramène à l'année moyenne)."""
        return {
            'puissance_kw': self.puissance_kw,
            'soc_demarrage_pct': self.soc_demarrage_pct,
            'soc_arret_pct': self.soc_arret_pct,
            'heures_max_par_jour': self.heures_max_par_jour,
            'heures_de_marche': round(self.heures_de_marche, 3),
            'energie_fournie_kwh': round(self.energie_fournie_kwh, 3),
            'cause_inactif': self.cause_inactif(),
            'par_mois': [
                {'mois': ligne['mois'],
                 'heures_de_marche': round(ligne['heures_de_marche'], 3),
                 'energie_fournie_kwh': round(ligne['energie_fournie_kwh'], 3)}
                for _, ligne in sorted(self._par_mois.items())],
            'mention': MENTION_GROUPE % (
                self.puissance_kw, self.soc_demarrage_pct,
                self.soc_arret_pct, self.heures_max_par_jour),
        }


def recharge_du_groupe(reste_kwh, place_kwh, eta, budget_kwh, coupee):
    """L'énergie (kWh, côté groupe) qui recharge la banque ce pas : ce qui
    reste après la charge servie, bornée par la place libre (au rendement
    ``eta`` d'un sens) et le budget de puissance de charge (``None`` = aucune
    borne publiée) ; nulle si la banque est coupée par l'arrêt (CALX272)."""
    if coupee or reste_kwh <= 0 or place_kwh <= 0:
        return 0.0
    recharge = min(reste_kwh, place_kwh / eta if eta > 0 else 0.0)
    if budget_kwh is not None:
        recharge = min(recharge, max(0.0, budget_kwh))
    return recharge
