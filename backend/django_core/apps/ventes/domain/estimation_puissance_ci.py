"""Consommation C&I ESTIMÉE à partir de la puissance maximale appelée.

Décision fondateur du 24/11/2026 (lead « Karim Hasnaoui », industriel en
moyenne tension, 1×8, ouvert du lundi au samedi de 8 h à 18 h) : le client ne
connaît que la puissance MAXIMALE de son site (380 kVA). Multiplier ce
maximum par les heures d'ouverture donne un PLAFOND (90 000 kWh/mois), pas
une estimation. La règle retenue, en DERNIER recours seulement :

    kWh du mois = kVA max × cos φ × (charge moyenne / 100) × heures d'ouverture du mois

* heures d'ouverture du mois : le calendrier du profil déclaré
  (``moteur_ci.charge.heures_ouverture_par_mois``), jamais un second ;
* cos φ : celui DÉCLARÉ au lead, sinon :data:`COS_PHI_SUPPOSE` (0,90) ;
* charge moyenne : celle du lead, sinon :data:`CHARGE_MOYENNE_SUPPOSEE_PCT` (50 %).

Pour Hasnaoui : 380 × 0,90 × 0,50 × ≈ 261 h ≈ 44 600 kWh/mois.

Toute consommation réelle gagne (kWh déclarés, relevé, factures, facture en
MAD, ``bill_kwh``, courbe mesurée, registres MT) : l'orchestrateur n'appelle
:func:`estimer_consommation` qu'après elles. L'estimation est DITE (règle du
17/11/2026, « tout ce qui est supposé est dit ») : hypothèse ``estimation``,
alerte interne qui donne la formule chiffrée et le champ de la fiche qui la
lève, niveau de données ``estimation`` et réserve de visite — jamais une
consommation présentée comme mesurée. Elle nourrit ensuite le chemin EXISTANT
comme 12 kWh mensuels déclarés (même rythme, même talon, même taille).

Module pur (aucune base lue) : la résolution ``res`` est celle de
``etude_ci._Resolution``.
"""

#: Supposition (fondateur informé le 24/11/2026) : facteur de puissance
#: usuel d'un site industriel ou tertiaire sans compensation connue. Le cos φ
#: DÉCLARÉ au lead (lu sur la facture) le remplace toujours.
COS_PHI_SUPPOSE = 0.9
#: Décision fondateur du 24/11/2026 : charge moyenne pendant les heures
#: d'ouverture quand la fiche ne la donne pas.
CHARGE_MOYENNE_SUPPOSEE_PCT = 50

#: Feuilles PRIVÉES de la résolution, posées par la couche lead
#: (``etude_ci.CHEMINS_LEAD``) — jamais dans les entrées résolues.
FEUILLE_PUISSANCE_MAX = '_puissance_max_kva'
FEUILLE_CHARGE_MOYENNE = '_charge_moyenne_pct'
#: Marqueur PRIVÉ posé quand la consommation retenue est cette estimation.
MARQUEUR = '_conso_estimee_puissance'
#: ``feuille_consommation_retenue`` de l'étude quand l'estimation chiffre.
FEUILLE_ESTIMEE = 'puissance_max_estimee'

CODE_ALERTE = 'consommation_estimee_puissance'
#: Puissance déclarée mais rythme incomplet : aucune estimation, et on le dit.
CODE_SANS_JOURS = 'estimation_puissance_sans_jours'
CODE_SANS_HEURES = 'estimation_puissance_sans_heures'
MOTIF_SOUS_RESERVE = ('consommation estimée à partir de la puissance maximale : '
                      'estimation sous réserve de visite')
SOURCE_DECISION = 'décision fondateur du 24/11/2026'

#: Clés du rythme lues (mêmes feuilles que celles qu'``etudier_ci`` passe au profil).
CLES_RYTHME = ('jours_ouverts', 'plages', 'equipes', 'debut_equipe_h', 'fermetures',
               'ramadan', 'categorie_commerciale', 'reponses_categorie')
#: Feuille du rythme manquante → code de l'alerte qui le dit.
_CODE_PAR_FEUILLE = {'rythme.jours_ouverts': CODE_SANS_JOURS, 'rythme.plages': CODE_SANS_HEURES}
_MESSAGES_SANS_RYTHME = {
    CODE_SANS_JOURS: ("Puissance maximale déclarée, mais jours d'ouverture inconnus : aucune "
                      "consommation n'est estimée. Demandez au client quels jours le site travaille."),
    CODE_SANS_HEURES: ("Puissance maximale déclarée, mais heures d'ouverture inconnues : aucune "
                       "consommation n'est estimée. Demandez au client ses heures d'ouverture "
                       "(ou son régime d'équipes)."),
}


#: Code d'alerte « rythme incomplet » → champ du lead que le refus nomme.
_CHAMP_LEAD_SANS_RYTHME = {CODE_SANS_JOURS: 'jours_ouverture', CODE_SANS_HEURES: 'heure_debut'}


def refus_sans_rythme(codes):
    """``(message, champ du lead)`` quand une puissance maximale déclarée n'a pas
    pu être estimée faute de jours ou d'heures d'ouverture, sinon ``None`` : le
    refus « sans consommation » nomme alors ce qui manque vraiment."""
    for code, champ in _CHAMP_LEAD_SANS_RYTHME.items():
        if code in codes:
            return codes[code]['message'], champ
    return None


def _positif(valeur, maximum=None):
    """Nombre > 0 (et ≤ ``maximum``), sinon ``None`` — jamais un 0 fabriqué."""
    if valeur is None or valeur == '' or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre <= 0 or (maximum is not None and nombre > maximum):
        return None
    return nombre


def _fr(nombre, decimales=0):
    """« 44 600 », « 0,90 » : l'écriture française d'un nombre."""
    texte = '{:,.{}f}'.format(nombre, decimales).replace(',', ' ')
    return texte.replace('.', ',')


def kwh_mensuels_estimes(kva, heures, *, cos_phi=None, charge_pct=None):
    """Les 12 kWh de la règle, mois par mois (``cos_phi`` / ``charge_pct`` vides =
    les valeurs supposées)."""
    cos = cos_phi or COS_PHI_SUPPOSE
    charge = charge_pct or CHARGE_MOYENNE_SUPPOSEE_PCT
    return [kva * cos * (charge / 100.0) * h for h in heures]


def _message(kva, cos, cos_dit, charge, charge_dite, heures, kwh):
    return ('Consommation estimée à partir de la puissance maximale : %s kVA × cos φ %s (%s) '
            '× charge moyenne %s %% (%s) × heures d’ouverture (%s h par mois en moyenne) — '
            'environ %s kWh/mois. Demandez la facture pour remplacer cette estimation.' % (
                _fr(kva, 0 if kva == int(kva) else 2), _fr(cos, 2), cos_dit, _fr(charge),
                charge_dite, _fr(sum(heures) / 12.0), _fr(round(sum(kwh) / 12.0, -2))))


def estimer_consommation(res, annee_reference, alertes, hypotheses):
    """``(kwh_mensuels [12], FEUILLE_ESTIMEE)`` ou ``(None, None)``.

    Appelée seulement quand aucune consommation réelle n'a été retenue. Sans
    puissance maximale : rien. Une facture en MAD présente mais non convertie
    (``conversion_mad_impossible``) est une donnée réelle : rien non plus (son
    refus nomme le contrat). Rythme sans heures : rien, et une alerte le dit."""
    from apps.ventes.moteur_ci.charge import heures_ouverture_par_mois

    kva = _positif(res.valeur(FEUILLE_PUISSANCE_MAX))
    if kva is None or any(a.get('code') == 'conversion_mad_impossible' for a in alertes):
        return None, None
    rythme = {k: res.valeur(k) for k in CLES_RYTHME if res.valeur(k) is not None}
    heures, manquants = heures_ouverture_par_mois(rythme, annee_reference=annee_reference)
    if heures is None or sum(heures) <= 0:
        code = _CODE_PAR_FEUILLE.get((manquants or ['rythme.plages'])[0], CODE_SANS_HEURES)
        alertes.append({'code': code, 'champ': 'consommation', 'message': _MESSAGES_SANS_RYTHME[code],
                        'niveau': 'alerte', 'interne': True})
        return None, None
    cos_declare = _positif(res.valeur('_cos_phi'), maximum=1)
    charge_declaree = _positif(res.valeur(FEUILLE_CHARGE_MOYENNE), maximum=100)
    kwh = kwh_mensuels_estimes(kva, heures, cos_phi=cos_declare, charge_pct=charge_declaree)
    cos = cos_declare or COS_PHI_SUPPOSE
    charge = charge_declaree or CHARGE_MOYENNE_SUPPOSEE_PCT
    cos_dit = 'déclaré' if cos_declare else 'supposé'
    charge_dite = 'déclarée' if charge_declaree else 'supposée'
    alertes.append({'code': CODE_ALERTE, 'champ': 'consommation',
                    'message': _message(kva, cos, cos_dit, charge, charge_dite, heures, kwh),
                    'niveau': 'alerte', 'interne': True})
    hypotheses.append({
        'cle': 'consommation', 'valeur': round(sum(kwh), 1), 'statut': 'estimation',
        'source': ('puissance maximale appelée %s kVA × cos φ %s (%s) × charge moyenne %s %% (%s) '
                   '× heures d’ouverture du mois (%s)' % (
                       _fr(kva, 0 if kva == int(kva) else 2), _fr(cos, 2), cos_dit, _fr(charge),
                       charge_dite, SOURCE_DECISION))})
    res.poser(MARQUEUR, True, {'origine': 'estimation', 'detail': FEUILLE_ESTIMEE, 'date': None})
    return kwh, FEUILLE_ESTIMEE
