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

import math

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


# ── CEC14 — saisies de l'économie : nombres finis, champs du contrat, et une
#    saisie FACULTATIVE invalide qui ne fait plus disparaître l'économie. ────
def fini(valeur):
    """``float`` fini, ou None (texte illisible, NaN, ±infini — le JSON
    ``1e400`` se lit ``inf``)."""
    try:
        x = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


#: Au-delà, une saisie d'offre est refusée : aucun prêt, taux ni tarif réel
#: n'en approche, et un exposant énorme déborde le calcul sur 25 ans.
PLAFOND_SAISIE = 1e12


#: Les grandeurs de ``economie.py`` → le nom du champ de l'écran (contrat
#: ``economie_ci.json``), pour qu'un refus s'affiche sous le bon champ.
CHAMPS_CONTRAT = {'principal_mad': 'montant_finance_mad',
                  'amortissement_duree_ans': 'duree_ans',
                  'taux_imposition_pct': 'taux_is_pct'}


def champ_contrat(champ):
    return CHAMPS_CONTRAT.get(champ, champ)


#: Saisies facultatives : invalides, elles sont ÉCARTÉES de la lecture d'un
#: devis (alerte interne) au lieu d'effacer toute l'économie du document.
SAISIES_FACULTATIVES = ('offre_financement', 'offre_cse_concurrente',
                        'fiscalite_client', 'taux_actualisation_client')


def sans_saisie_invalide(assembleur, apercu, *, saisies=None, **kw):
    """La lecture d'un DEVIS : ``assembleur(apercu, saisies=…, **kw)`` ; une
    saisie facultative refusée est retirée puis dite au vendeur
    (``alertes_internes``, jamais servie au client). Les autres refus
    remontent tels quels (l'aperçu de l'écran garde son 400 nommé)."""
    from apps.ventes.economie_ci import SaisieEconomieCiInvalide
    if (kw.get('reglages') or {}).get('regles_origine'):
        # Devis envoyé sous le niveau 3 : le comportement d'hier (refus ; une
        # durée d'amortissement non entière était tronquée, pas refusée).
        return assembleur(apercu, saisies=_duree_tronquee(saisies), **kw)
    saisies = dict(saisies) if isinstance(saisies, dict) else {}
    ecartees = []
    while True:
        try:
            bloc = assembleur(apercu, saisies=saisies, **kw)
            break
        except SaisieEconomieCiInvalide as refus:
            cle = str(refus.champ or '').split('.')[0]
            if cle not in SAISIES_FACULTATIVES or cle not in saisies:
                raise
            saisies.pop(cle)
            ecartees.append(f"{refus} — saisie « {cle} » écartée du calcul, "
                            f"à corriger dans le générateur.")
    for message in ecartees:
        bloc.setdefault('alertes_internes', []).append(
            {'code': 'saisie_ecartee', 'message': message, 'interne': True})
    return bloc


#: Le motif d'un client bi-horaire sur un devis envoyé avant le 27/10/2026
#: (règles d'origine) : texte d'avant CEC5, inchangé.
MOTIF_BI_HORAIRE_ORIGINE = (
    "option bi-horaire : plages heures pleines / normales non saisies — "
    "économies non chiffrées (aucune plage devinée)")


def _duree_tronquee(saisies):
    """CEC17 — règles d'origine : ``fiscalite_client.duree_ans`` 7,5 lu 7
    (``int()`` d'avant CEC14), jamais refusé."""
    fiscal = (saisies or {}).get('fiscalite_client') if isinstance(
        saisies, dict) else None
    duree = fini(str(fiscal.get('duree_ans')).replace(',', '.')) if isinstance(
        fiscal, dict) else None  # « 7,5 » se lit comme ``_nombre_fiscal``
    if duree is None or duree == int(duree):
        return saisies
    return dict(saisies, fiscalite_client=dict(fiscal, duree_ans=int(duree)))


def motif_tarif_omis(tarif, defaut):
    """CEC18 — le motif d'une économie omise faute de tarif : un contrat
    DOMESTIQUE déclaré sans tranches dit sa vraie raison (aucune grille
    professionnelle), jamais « contrat non déclaré »."""
    if isinstance(tarif, dict) and tarif.get('contrat') == 'bt_domestique':
        from apps.ventes.tarif_ci import MENTION_DOMESTIQUE
        return MENTION_DOMESTIQUE
    return defaut


# ═════════════════════════════════════════════════════════════════════════════
# CEC19 — bande de vraisemblance d'un prix déclaré (décision fondateur
# 28/10/2026 : k = 3).
# ═════════════════════════════════════════════════════════════════════════════
#: Un prix déclaré hors de [grille officielle ÷ k ; grille officielle × k] est
#: signalé au vendeur (alerte INTERNE, jamais côté client) : faute de virgule
#: ×10, prix en centimes. Le prix n'est PAS corrigé, seulement signalé.
K_BANDE_PRIX = 3.0
CODE_PRIX_HORS_BANDE = 'prix_declare_hors_bande'


def _grille_ttc_du_poste(poste, contrat):
    """Prix TTC publié de la grille officielle pour ce poste, ou None.

    Aucun repère trouvé (contrat inconnu, tranche au-delà de la grille) ⇒
    None : le poste n'est PAS contrôlé (aucun chiffre inventé, aucune alerte).
    """
    from apps.parametres import tarifs_officiels as officiels
    try:
        if contrat == 'mt_general':
            ligne = officiels.MT_GENERAL.get(poste)
            return _montant(ligne['valeur']) if ligne else None
        if contrat in ('bt_patente', 'bt_force_motrice') and str(
                poste).startswith('tranche_'):
            lignes = officiels.grille_bt(contrat)
            rang = int(str(poste).split('_', 1)[1]) - 1
            return _montant(lignes[rang]['valeur']) if 0 <= rang < len(
                lignes) else None
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    return None


def alertes_prix_hors_bande(tarif, k=K_BANDE_PRIX):
    """Alertes INTERNES (forme de ``economie_ci._alertes_internes``) pour
    chaque prix DÉCLARÉ hors de [grille ÷ k ; grille × k], nommant le poste
    et le prix. Seuls les prix déclarés sont contrôlés (origine facture)."""
    if not isinstance(tarif, dict) or tarif.get('origine') != 'declare_facture':
        return []
    alertes = []
    for entree in tarif.get('tarifs_par_poste') or []:
        poste = entree.get('poste')
        declare = _montant(entree.get('tarif_kwh_ttc'))
        grille = _grille_ttc_du_poste(poste, tarif.get('contrat'))
        if declare is None or not grille or grille <= 0:
            continue  # pas de repère officiel : poste non contrôlé
        if declare < grille / k or declare > grille * k:
            alertes.append({
                'code': CODE_PRIX_HORS_BANDE,
                'message': (
                    f"Prix déclaré du poste « {poste} » : {declare:g} MAD/kWh "
                    f"TTC, hors de la bande de vraisemblance (grille "
                    f"officielle {grille:g} ÷ {k:g} à × {k:g}) — faute de "
                    f"virgule ou prix en centimes ? À vérifier sur la "
                    f"facture."),
                'interne': True})
    return alertes


# ═════════════════════════════════════════════════════════════════════════════
# CEC15 — l'apport, les frais et la valeur résiduelle SAISIS d'une offre de
# financement entrent dans le flux de l'offre (décision fondateur 28/10/2026 :
# inclure).
# ═════════════════════════════════════════════════════════════════════════════
def flux_offre(offre, echeance, duree_mois, economie_annee1):
    """Flux annuel du client avec l'offre : année 0 = −(apport + frais) ;
    années 1.. = économie − échéances de l'année (dernière année au prorata
    des mois restants) ; la valeur résiduelle saisie est payée en fin de
    durée (levée d'option / dernier loyer — lecture prudente). Champs absents
    ⇒ 0. Retourne ``{flux: [{annee, flux_mad, cumul_mad}], retour_ans}``."""
    def _v(cle):
        v = _montant((offre or {}).get(cle))
        return v if v and v > 0 else 0.0
    apport, frais, residuelle = (
        _v('apport_mad'), _v('frais_mad'), _v('valeur_residuelle_mad'))
    cumul = -(apport + frais)
    flux = [{'annee': 0, 'flux_mad': round(cumul, 2),
             'cumul_mad': round(cumul, 2)}]
    annees = -(-int(duree_mois) // 12)
    for a in range(1, annees + 1):
        mois = min(12, int(duree_mois) - 12 * (a - 1))
        gain = (economie_annee1 or 0.0) * mois / 12 - echeance * mois
        if a == annees:
            gain -= residuelle
        cumul += gain
        flux.append({'annee': a, 'flux_mad': round(gain, 2),
                     'cumul_mad': round(cumul, 2)})
    return {'flux': flux, 'retour_ans': retour_au_dixieme({'flux': flux})}


def cles_flux_offre(offre, echeance, duree_mois, economie_annee1):
    """Clés ADDITIVES du bloc ``financement`` : ``apport_mad`` et
    ``frais_mad`` tels que SAISIS sur l'offre (0 si absents — affichés
    seulement > 0), puis ``flux_offre`` et ``retour_offre_ans`` — omis sans
    économie an 1 (flux non calculable)."""
    def _saisi(cle):
        v = _montant((offre or {}).get(cle))
        return round(v, 2) if v and v > 0 else 0.0
    cles = {'apport_mad': _saisi('apport_mad'), 'frais_mad': _saisi('frais_mad')}
    if economie_annee1 is None:
        return cles
    res = flux_offre(offre, echeance, duree_mois, economie_annee1)
    return {**cles, 'flux_offre': res['flux'],
            'retour_offre_ans': res['retour_ans']}


# ERR-CI-SENSIBILITE-P90-INVERSEE (CEC6 P1.4) — le scénario « production » se
# calcule comme le central. Avec la série 8 760 h (AMOT99), une cellule du bilan
# central vaut la MOYENNE, sur les jours réels du mois, de min(charge, production
# du jour) ; la recalculer min(charge, production moyenne × facteur) la gonfle
# (moyenne des min ≤ min de la moyenne) : P90 montrait plus d'économie que le
# central. Le scénario relance donc LE moteur du central
# (``moteur_ci.autoconso.bilan_horaire``) à la puissance retenue × facteur, après
# avoir vérifié que ce moteur reproduit le bilan central stocké.
MOTIF_SENSIBILITE_NON_REPRODUCTIBLE = (
    "production non recalculable par le calcul du scénario central (étude à "
    "rafraîchir) : scénario non chiffré")


def _proche(a, b):
    x, y = _montant(a) or 0.0, _montant(b) or 0.0
    return abs(x - y) <= 0.002 + 1e-6 * abs(y)


def _meme_horaire(horaire, reference):
    if len(horaire) != len(reference):
        return False
    for x, y in zip(horaire, reference):
        if not isinstance(y, dict) or (x.get('mois'), x.get('type_jour')) != (y.get('mois'), y.get('type_jour')):
            return False
        for cle in ('autoconso_kwh', 'surplus_kwh'):
            a, b = x.get(cle) or [], y.get(cle) or []
            if len(a) != len(b) or not all(_proche(u, v) for u, v in zip(a, b)):
                return False
    return True


def _central_par_cellule(apercu):
    """Vrai si chaque cellule centrale vaut min(autoconsommé + surplus, charge) :
    le recalcul cellule par cellule est alors LE calcul du central."""
    charges = {(j.get('mois'), j.get('type_jour')): j.get('charge_kwh') or []
               for j in (apercu.get('profil_charge') or {}).get('jours_types') or []
               if isinstance(j, dict)}
    bilan = apercu.get('bilan') if isinstance(apercu.get('bilan'), dict) else {}
    for bloc in bilan.get('horaire') or []:
        if not isinstance(bloc, dict):
            continue
        charge = charges.get((bloc.get('mois'), bloc.get('type_jour')))
        if charge is None:
            return True  # l'appelant nomme l'omission « charge absente »
        auto, surplus = bloc.get('autoconso_kwh') or [], bloc.get('surplus_kwh') or []
        for h, a in enumerate(auto):
            prod = (_montant(a) or 0.0) + ((_montant(surplus[h]) or 0.0) if h < len(surplus) else 0.0)
            c = (_montant(charge[h]) or 0.0) if h < len(charge) else 0.0
            if not _proche(a, min(prod, c)):
                return False
    return True


def _valeur(entrees, cle):
    v = (entrees or {}).get(cle)
    return v.get('valeur') if isinstance(v, dict) else v


def _bilan_du_moteur(apercu, facteur):
    """Le bilan du moteur central à la puissance retenue × ``facteur``, ou None
    quand ce moteur ne reproduit pas le bilan central stocké."""
    from apps.ventes.moteur_ci.autoconso import bilan_horaire
    from apps.ventes.moteur_ci.production import production_pour_bilan
    bilan, production = apercu.get('bilan'), apercu.get('production')
    bilan = bilan if isinstance(bilan, dict) else {}
    kwc = _montant((apercu.get('taille') or {}).get('retenue_kwc'))
    jours = (apercu.get('profil_charge') or {}).get('jours_types')
    if bilan.get('batterie') or not kwc or not jours or not isinstance(production, dict):
        return None
    er = apercu.get('entrees_resolues') or {}
    kw = {'tension': str(_valeur(er, 'tension') or 'bt').lower(),
          'revente_choisie': bool(_valeur(er, 'revente_choisie'))}
    for source in (production_pour_bilan(production), production.get('jours_types')):
        central = bilan_horaire(jours, source, kwc, **kw)[0] if source else {}
        if central and _meme_horaire(central.get('horaire') or [], bilan.get('horaire') or []):
            return bilan_horaire(jours, source, kwc * facteur, **kw)[0]
    return None


def apercu_production_comparable(apercu, facteur, par_cellule, *, origine, motif_sans_charge):
    """``(aperçu du scénario | None, motif | None)`` — production × ``facteur``
    par LE calcul du central. ``par_cellule`` : le recalcul cellule par cellule
    d'origine, gardé tel quel pour un devis rendu sous les règles d'origine
    (``origine`` — fondateur 08/10 : un devis envoyé garde ce que le client a
    reçu) et quand le central est lui-même cellule par cellule."""
    if origine or _central_par_cellule(apercu):
        modifie = par_cellule(apercu, facteur)
        return modifie, None if modifie is not None else motif_sans_charge
    bilan = _bilan_du_moteur(apercu, facteur)
    if bilan is None:
        return None, MOTIF_SENSIBILITE_NON_REPRODUCTIBLE
    return dict(apercu, bilan=dict(apercu.get('bilan') or {}, **bilan)), None
