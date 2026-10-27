"""CEC — compléments PURS du moteur ``economie_ci`` (module neuf :
``economie_ci.py`` dépasse 2 000 lignes et ne grossit plus).

* :func:`investissement_hors_om` (CEC1) : une ligne O&M SOUSCRITE est une
  charge ANNUELLE (déduite des années 1 à 25 par ``economie_ci._om``) ; elle ne
  compte donc jamais aussi dans l'investissement de l'année 0 — sinon la
  première année d'O&M est payée deux fois et le retour comme le TRI baissent
  à tort.
* :func:`flux_option_avec` (CEC3) : le flux 25 ans de l'option « avec
  batterie » par le MÊME moteur que l'option « sans »
  (``economie_ci.flux_ci`` : dégradation, remplacement des onduleurs —
  hybrides compris — au montant de leurs lignes, entretien), PLUS le
  remplacement de la batterie au montant de SA ligne
  (:func:`annee_remplacement_batterie`). Jamais « total ÷ économie an 1 » :
  deux retours imprimés côte à côte se calculent pareil.
* :func:`retour_au_dixieme` (CEC3) : le retour lu sur le flux, au dixième
  d'année (interpolé dans l'année du passage à zéro), pour comparer deux
  options à la même précision.

Aucun accès base, aucun import de modèle ; ne change aucun statut (règle #4).
"""
from __future__ import annotations

ROLE_OM = 'om_ci'


def _montant(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def investissement_hors_om(investissement, lignes, actif=True):
    """``{ht, ttc}`` de l'option retenue SANS ses lignes O&M souscrites
    (rôle ``om_ci``, non optionnelles — les optionnelles ne sont pas dans le
    total). ``actif`` faux (devis rendu aux règles d'origine) ⇒ inchangé."""
    if not actif or not isinstance(investissement, dict):
        return investissement
    om = [li for li in (lignes or []) if isinstance(li, dict)
          and li.get('role_ci') == ROLE_OM and not li.get('optionnelle')]
    if not om:
        return investissement
    sortie = dict(investissement)
    for cle in ('ht', 'ttc'):
        total = _montant(investissement.get(cle))
        if total is None:
            continue
        retire = sum(_montant(li.get(cle)) or 0.0 for li in om)
        sortie[cle] = round(total - retire, 2)
    return sortie


#: CEC3 — défaut fondateur (à revoir) quand la fiche batterie ne porte ni
#: garantie ni cycles : garantie usuelle d'une batterie lithium de 10 ans,
#: remplacement l'année suivante. Décision prise pour le fondateur
#: (27/10/2026) : prudent (l'option « avec » n'est jamais flattée).
DEFAUT_GARANTIE_BATTERIE_ANS = 10
SOURCE_DEFAUT_BATTERIE = (
    "défaut fondateur (à revoir) : garantie usuelle de 10 ans, aucune "
    "garantie ni nombre de cycles saisis sur la fiche batterie")
CYCLES_PAR_AN = 365  # une décharge par jour (pricing.BATTERY_CYCLES_PER_DAY)
MOTS_ACCESSOIRE = ('câble', 'cable', 'connecteur', 'fusible', 'support',
                   'rack', 'coffret')


def annee_remplacement_batterie(garantie_mois=None, cycles_publies=None):
    """``{annee, source}`` du remplacement de la batterie : l'année qui suit
    la fin de la garantie constructeur, ou l'épuisement des cycles publiés à
    une décharge par jour si c'est plus tôt (le plus prudent des deux) ; sans
    l'un ni l'autre, :data:`DEFAUT_GARANTIE_BATTERIE_ANS` étiqueté."""
    candidats = []
    mois = _montant(garantie_mois)
    if mois and mois > 0:
        ans = -(-int(mois) // 12)
        candidats.append((ans + 1, f'garantie constructeur de la fiche '
                                   f'({int(mois)} mois) : remplacement '
                                   "l'année suivant sa fin"))
    cycles = _montant(cycles_publies)
    if cycles and cycles > 0:
        ans = int(cycles // CYCLES_PAR_AN)
        candidats.append((ans + 1, f'{int(cycles)} cycles publiés par le '
                                   f'fabricant, une décharge par jour'))
    if not candidats:
        return {'annee': DEFAUT_GARANTIE_BATTERIE_ANS + 1,
                'source': SOURCE_DEFAUT_BATTERIE}
    annee, source = min(candidats)
    return {'annee': annee, 'source': source}


def _est_batterie(ligne):
    """La batterie elle-même : le mot du découpage des options du document
    (``solar_classification.is_battery``), jamais une ligne onduleur (un
    hybride « compatible batterie ») ni un câble ou un accessoire. Une ligne
    qui COMMENCE par « Batterie » (désignation de l'option avec,
    ``etude_ci_batterie.designation_option_avec``) l'est toujours, même si
    elle dit « rack » ou « support inclus » (CEC11)."""
    from apps.ventes.solar_classification import is_battery
    nom = str(ligne.get('designation') or '').strip().lower()
    if ligne.get('onduleur') or not is_battery(nom):
        return False
    return nom.startswith('batterie') or not any(
        m in nom for m in MOTS_ACCESSOIRE)


def retour_au_dixieme(bloc):
    """Le retour (années, au dixième) lu sur un flux ``flux_de_tresorerie``,
    interpolé dans l'année où le cumul passe à zéro ; None sans passage."""
    flux = (bloc or {}).get('flux') or []
    precedent = None
    for f in flux:
        cumul = _montant(f.get('cumul_mad'))
        if cumul is None:
            return None
        if cumul >= 0 and f.get('annee'):
            gain = _montant(f.get('flux_mad')) or 0.0
            if precedent is None or gain <= 0:
                return float(f['annee'])
            return round(f['annee'] - 1 + (-precedent) / gain, 1)
        precedent = cumul
    return None


def flux_option_avec(base_eco, *, lignes, batterie=None, **kw):
    """Le flux de l'option « avec batterie » : ``economie_ci.flux_ci`` (même
    forme, mêmes post-traitements : coût du kWh, sources codées, jalons HT et
    TTC) avec le remplacement de la batterie en plus, et
    ``indicateurs.retour_dixieme_ans``.

    ``base_eco`` : ``economie_ci.base_economique`` de l'option avec (son
    investissement CLIENT, son économie an 1). ``lignes`` : ses lignes à la
    forme ``economie_ci.onduleur_et_om``. ``batterie`` :
    :func:`annee_remplacement_batterie` (None ⇒ son défaut étiqueté) ; une
    année au-delà de l'horizon n'ajoute aucun remplacement. ``kw`` : les
    autres arguments de ``flux_ci``. Aucune écriture.
    """
    from apps.ventes import economie_ci as eco
    lignes = [li for li in (lignes or []) if isinstance(li, dict)]
    onduleur, om = eco.onduleur_et_om(lignes)
    comptees = [li for li in lignes
                if _est_batterie(li) and not li.get('optionnelle')]
    batterie = batterie or annee_remplacement_batterie()
    autres = []
    if comptees and batterie['annee'] <= eco.HORIZON_CI_ANS:
        autres = [{'equipement': 'batterie', 'annee': batterie['annee'],
                   'source': batterie['source'],
                   'ht': round(sum(_montant(li.get('ht')) or 0.0
                                   for li in comptees), 2),
                   'ttc': round(sum(_montant(li.get('ttc')) or 0.0
                                    for li in comptees), 2)}]
    sortie = eco.flux_ci(base_eco, onduleur=onduleur, om=om,
                         autres_remplacements=autres, **kw)
    sortie['remplacements'] = list(sortie['remplacements']) + [
        {'composant': 'batterie', 'annee': r['annee'],
         'montant_ht_mad': r['ht'], 'montant_ttc_mad': r['ttc'],
         'source': r['source']} for r in autres]
    principal = 'flux_ttc' if base_eco['base'] == eco.BASE_TTC else 'flux_ht'
    sortie['indicateurs']['retour_dixieme_ans'] = retour_au_dixieme(
        sortie[principal])
    return sortie


#: CEC9 — décision prise pour le fondateur (à revoir) : la charge annuelle
#: d'O&M reste le total de la ligne ; une quantité ≠ 1 (« 5 ans × 6 000 » ?)
#: est DITE au vendeur, jamais devinée.
ALERTE_OM_QUANTITE = (
    "Ligne O&M « {designation} » : quantité {quantite:g} — l'étude déduit "
    "chaque année le total de la ligne ; un contrat pluriannuel se saisit en "
    "quantité 1 au prix d'UNE année.")


def alertes_om(lignes):
    """Alertes INTERNES : lignes O&M souscrites de quantité ≠ 1."""
    return [{'code': 'om_quantite', 'interne': True,
             'message': ALERTE_OM_QUANTITE.format(
                 designation=li.get('designation') or '',
                 quantite=_montant(li.get('quantite')))}
            for li in (lignes or []) if isinstance(li, dict)
            and li.get('role_ci') == ROLE_OM and not li.get('optionnelle')
            and _montant(li.get('quantite')) not in (None, 1.0)]
