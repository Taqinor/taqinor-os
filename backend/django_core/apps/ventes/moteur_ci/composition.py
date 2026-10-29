"""CIQ115 — composition C&I SERVEUR (BOQ) : fin du kit résidentiel mis à
l'échelle.

``composer_ci(kwc, catalogue, *, onduleurs, entrees, forfaits)`` rend la forme
``composition`` de ``contract_samples/etude_ci_preview.json`` :
``{lignes, onduleurs, prix_a_renseigner, incomplet, options, alertes,
hypotheses}`` — chaque ligne ``{role, produit, designation, quantite, unite,
prix_connu, motif, a_confirmer_visite}``.

* Panneaux : module retenu (fiche complète), nombre = plafond(kWc ÷ Wc).
* Onduleurs : la combinaison de CIQ111 (``onduleurs`` = son résultat).
* Câble DC : Σ chaînes × longueur DÉCLARÉE ; protections et câble AC par
  onduleur par ``core.electrique`` (``courant_emploi_ac``,
  ``calibre_disjoncteur``, ``proposer_section`` sur le barème étendu
  CIQ139). Hors barème ⇒ « section/calibre à dimensionner par le bureau
  d'études » (``a_confirmer_visite``), JAMAIS une section extrapolée ;
  longueur non déclarée ⇒ ligne ``a_confirmer_visite`` sans quantité.
* Chaque organe est apparié au catalogue par son rôle C&I ET sa grandeur de
  fiche (calibre / pôles / section / type de pose — posés par CIQ103), sinon
  ligne « prix à renseigner » nommée (patron PV47).
* Structure : rôle ``structure_ci`` du ``type_pose`` du toit, jamais le
  bouton acier/alu résidentiel.
* Protections DC et parafoudres DC : une par CHAÎNE (R3, 28/10/2026) ;
  disjoncteur et parafoudre AC 4P derrière un triphasé, 2P sinon ; mise à la
  terre seulement quand la visite la dit nécessaire.
* Comptage / limitation d'injection : sans revente (BT toujours, MT sans
  revente choisie), un dispositif par POINT DE RACCORDEMENT déclaré, choisi
  PAR CALIBRE (courant AC au point d'injection, R3.5), autant de
  compteurs/contrôleurs que l'impose ``lim_onduleurs_max`` dès 2 onduleurs ;
  fiche muette ⇒ « à confirmer fournisseur ». Une clé wifi PAR ONDULEUR
  (``log_type == 'dongle'``, R3.6) ; sans clé de la marque, logger central
  dès 2 onduleurs, borné par ``log_onduleurs_max`` quand publié.
* Cellule MT seulement si ``besoin_cellule_mt`` est déclaré ; site MT sans ce
  fait ⇒ alerte « poste de livraison à confirmer à la visite », aucune ligne.
* Prestations : une ligne par prestation des forfaits C&I de la société
  (CIQ105 : fixe + par kWc + par panneau) ; non réglée ⇒ « prix à
  renseigner » ; AUCUN barème résidentiel (L-FORFAIT intouché).
* Option O&M NOMMÉE toujours proposée ; option batterie seulement si un
  ``batterie_ci`` est au catalogue ET un besoin déclaré — « valeur non
  chiffrée ». Aucun onduleur hybride ni batterie COMPOSÉS.
* ``incomplet = vrai`` dès qu'une ligne n'a pas de prix. Jamais ``prix_achat``
  ni marge.

PUR : aucun Django, aucune base, aucun ``apps.*`` (garde AST du test).
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation

from core.electrique.cables import (
    AMPACITE_U1000R2V_MONO, AMPACITE_U1000R2V_TRI, CHUTE_CIBLE_AC_PCT,
    bareme_pour, proposer_section,
)
from core.electrique.protections import calibre_disjoncteur, courant_emploi_ac
from core.pricing_paliers import MODE_VOLUME, calculer_prix_paliers

#: Prestations C&I réglées par société (``CompanyProfile.forfaits_ci``).
PRESTATIONS_CI = (
    ('etudes_ingenierie', 'Études et ingénierie C&I'),
    ('pose_structure', 'Pose de la structure C&I'),
    ('pose_modules', 'Pose des modules C&I'),
    ('raccordement_ac', 'Raccordement AC C&I'),
    ('mise_en_service', 'Mise en service C&I'),
    ('dossier_raccordement', 'Dossier de raccordement C&I'),
    ('levage_acces', 'Levage et accès C&I'),
    ('transport_ci', 'Transport C&I'),
)

#: R2 (fondateur, 28/10/2026) — les organes du « Tableau de protection AC/DC »
#: du document CLIENT C&I : coffrets DC/AC, disjoncteur AC et parafoudre AC
#: (``protection_ac``), protection DC et parafoudre DC par chaîne
#: (``protection_dc``), mise à la terre.
#: Reconnus par le RÔLE de ligne, jamais par la désignation ; UNE source pour
#: le rendu (``quote_engine/ci/tableau``) et le sérialiseur des lignes.
#: EXCLUS par décision (R2, à revoir par le fondateur) : ``cable_ac`` (câble,
#: pas un organe du tableau) et ``cellule_mt`` (poste de livraison) restent
#: des lignes à part. R3 (fondateur, 28/10/2026) : le Smart Meter SORT du
#: tableau — comptage et supervision forment leur propre groupe
#: (``ROLES_SUPERVISION_CI``).
ROLES_TABLEAU_CI = frozenset((
    'coffret_dc', 'coffret_ac', 'protection_ac', 'protection_dc',
    'mise_a_la_terre',
))

#: R3.4 (fondateur, 28/10/2026) — la ligne CLIENT « Supervision & comptage » :
#: compteur / contrôleur d'injection (Smart Meter) et supervision (clé wifi
#: par onduleur, ou logger central).
ROLES_SUPERVISION_CI = frozenset((
    'compteur_injection', 'controleur_injection', 'logger_supervision',
))

#: Groupe CLIENT d'un rôle C&I (clé ``groupe_client`` des lignes de devis) :
#: ``tableau_ci`` | ``supervision_ci`` | ``installation_ci`` | ``None``.
GROUPES_CLIENT = (
    ('tableau_ci', ROLES_TABLEAU_CI),
    ('supervision_ci', ROLES_SUPERVISION_CI),
    ('installation_ci', frozenset(cle for cle, _libelle in PRESTATIONS_CI)),
)


def groupe_client_du_role(role_ci):
    """Le groupe client d'une ligne d'après son ``role_ci``, ou ``None``."""
    for groupe, roles in GROUPES_CLIENT:
        if role_ci in roles:
            return groupe
    return None


MOTIF_PRIX = 'article C&I « prix à renseigner »'
MOTIF_FOURNISSEUR = 'à confirmer fournisseur (fiche muette)'
MOTIF_BUREAU = ("section/calibre à dimensionner par le bureau d'études "
                "(hors barème relevé)")
MOTIF_LONGUEUR = 'longueur non déclarée : à relever à la visite'
#: Fondateur 26/10/2026 — un devis C&I ne laisse JAMAIS un prix vide : avant
#: la visite, câbles et structure sont chiffrés sur ces hypothèses (devis
#: préliminaire, prix ajustés après la visite).
LONGUEUR_AC_DEFAUT_M = 30.0         # par onduleur, onduleur → TGBT
DISTANCE_DC_DEFAUT_M = 30.0         # champ → onduleur ; câble = 2 × chaînes × distance
PANNEAUX_PAR_CHAINE_DEFAUT = 12     # chaînes non calculées (fiches muettes)
TYPE_POSE_DEFAUT = 'toit_plat_leste'
MOTIF_PRELIMINAIRE = 'estimation préliminaire (%s) : ajustée après la visite'


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        x = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None
    return x if x.is_finite() else None


def _f(valeur):
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def nom_client(nom):
    """Le nom d'un article tel que le CLIENT le lit : sans le marqueur interne
    « C&I » du catalogue (fondateur 26/10/2026) — « Coffret DC C&I » →
    « Coffret DC », « Disjoncteur AC 25 A tétrapolaire (C&I) » → « … tétrapolaire »."""
    if not nom:
        return nom
    return re.sub(r'\s*\(C&I\)|\s+C&I\b', '', nom).strip()


def _alerte(code, message, niveau='alerte', champ='composition'):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': True}


def _du_role(catalogue, role, filtre=None):
    """Le premier article ÉLIGIBLE du rôle (C&I ou de devis) qui passe le
    filtre de fiche — ordre déterministe (id). ADEV82 : un article TARIFÉ
    passe devant un article sans prix du même rôle."""
    premier = None
    for p in sorted(catalogue, key=lambda x: (x.get('id') or 0)):
        if p.get('eligible_ci') is False:
            continue
        if role not in (p.get('role_ci'), p.get('role_devis')):
            continue
        if filtre is not None and not filtre(p.get('fiche') or {}, p):
            continue
        if p.get('prix_connu'):
            return p
        premier = premier or p
    return premier


def _ligne(role, article, designation, quantite, unite, *, motif=None,
           a_confirmer=False, visite=False, designation_moteur=False):
    """Une ligne de composition. La désignation est le NOM de l'article quand
    il existe (le catalogue nomme le produit vendu), ``designation`` sinon.

    R3 (fondateur, 28/10/2026) — ``designation_moteur=True`` : la désignation
    CALCULÉE par le moteur gagne sur le nom de l'article (``produit`` reste
    l'article, prix et stock inchangés). Réservé aux protections dont la
    QUANTITÉ ou les PÔLES sont une règle du moteur que le nom générique du
    catalogue ne dit pas : « Protection DC par chaîne », « Parafoudre DC par
    chaîne », « Disjoncteur AC 63 A 4P — sortie … », « Parafoudre AC 4P ».
    Cette désignation est celle qu'écrit le devis automatique
    (``etude_ci.lignes_du_devis_ci`` → ``LigneDevis.designation``)."""
    prix_connu = bool(article and article.get('prix_connu'))
    if article is None and motif is None:
        motif = MOTIF_PRIX
    elif article is not None and not prix_connu and motif is None:
        motif = MOTIF_PRIX
    nom_article = None if designation_moteur or not article else article.get('nom')
    ligne = {
        'role': role,
        'produit': article.get('id') if article else None,
        'designation': nom_article or designation,
        'quantite': quantite,
        'unite': unite,
        'prix_connu': prix_connu,
        'motif': motif,
        'a_confirmer_visite': bool(a_confirmer),
    }
    if visite:
        # ADEV79 (D-ACI-2=a) — poste qui dépend de la VISITE (type de pose,
        # longueurs, chaînes, section du bureau d'études) : « à chiffrer après
        # visite », hors total du devis, jamais un « prix à renseigner ».
        ligne['a_chiffrer_visite'] = True
    if article is not None and article.get('prix_vente_ht') is not None:
        ligne['prix_unitaire_ht'] = str(article['prix_vente_ht'])
    _appliquer_palier(ligne, article)
    return ligne


def _appliquer_palier(ligne, article):
    """CIQ123 — prix de VENTE TTC du palier atteint par la quantité (moteur
    générique ``core.pricing_paliers``, mode volume), dit dans la ligne.
    Paliers vides ⇒ ligne inchangée (prix catalogue). ``delai_appro_jours``
    (article « sur commande ») est servi à côté."""
    if not article:
        return
    if article.get('delai_appro_jours') is not None:
        ligne['delai_appro_jours'] = article['delai_appro_jours']
    paliers = article.get('paliers_prix_vente') or []
    quantite = _d(ligne.get('quantite'))
    if not paliers or quantite is None or quantite <= 0:
        return
    total = calculer_prix_paliers(
        quantite, [{'seuil_min': p.get('seuil_min'),
                    'seuil_max': p.get('seuil_max'),
                    'prix_unitaire': p.get('prix_vente_ttc')}
                   for p in paliers], MODE_VOLUME)
    if total is None:
        return
    atteint = None
    for p in sorted(paliers, key=lambda x: _d(x.get('seuil_min')) or 0):
        if quantite >= (_d(p.get('seuil_min')) or 0):
            atteint = p
    ligne['prix_unitaire_ttc'] = str(
        (total / quantite).quantize(Decimal('0.01')))
    # ADEV79 — la TVA de l'ARTICLE ramène ce TTC au HT (jamais un 20 % codé).
    if article.get('tva_pct') is not None:
        ligne['tva_pct'] = str(article['tva_pct'])
    ligne['palier'] = {'seuil_min': atteint.get('seuil_min'),
                       'seuil_max': atteint.get('seuil_max'),
                       'mention': 'prix palier dès %s unités' % (
                           atteint.get('seuil_min'),)} if atteint else None
    # ADEV82 — la ligne porte le HT du PALIER (celui de la taille), plus le
    # prix catalogue : taille et devis au même prix.
    palier_ht = prix_palier_ht(ligne)
    if palier_ht is not None:
        ligne['prix_unitaire_ht'] = str(palier_ht)
    ligne['prix_connu'] = True
    if ligne.get('motif') == MOTIF_PRIX:
        ligne['motif'] = None


def prix_palier_ht(ligne, taux_tva_pct=None):
    """ADEV82 — LA règle du prix unitaire HT (au centime) d'une ligne au prix
    de PALIER (TTC, CIQ123) : la TVA de son article (``tva_pct``), à défaut
    ``taux_tva_pct`` ; ``None`` hors palier ou sans taux. La taille
    (``taille.cout_vente_ht``) et la ligne écrite au devis portent CE prix."""
    if not ligne.get('palier') or not ligne.get('prix_unitaire_ttc'):
        return None
    tva = _d(ligne.get('tva_pct'))
    if tva is None:
        tva = _d(taux_tva_pct)
    ttc = _d(ligne['prix_unitaire_ttc'])
    if tva is None or ttc is None:
        return None
    return (ttc / (1 + tva / 100)).quantize(Decimal('0.01'))


def ligne_batterie(article, quantite):
    """Option « avec batterie » (fondateur 26/10/2026) : la banque HOMOGÈNE de
    modules, au prix de VENTE du catalogue (palier compris) ; sans prix ⇒
    « prix à renseigner » nommé, jamais un 0."""
    return _ligne('batterie_ci', article, 'Batterie', quantite, 'u')


def postes_non_chiffres(lignes):
    """ADEV79 — ``(prix à renseigner, à chiffrer après visite)`` : les
    désignations des lignes sans prix (hors visite) et celles qui attendent
    la visite (hors total, chiffrées ou non)."""
    a_renseigner, visite = [], []
    for ligne in lignes or []:
        # C-L3-MOT-02 — une désignation n'est listée qu'une fois (ordre gardé).
        if ligne.get('a_chiffrer_visite'):
            if ligne['designation'] not in visite:
                visite.append(ligne['designation'])
        elif not ligne.get('prix_connu'):
            if ligne['designation'] not in a_renseigner:
                a_renseigner.append(ligne['designation'])
    return a_renseigner, visite


def _par_id(catalogue):
    return {p.get('id'): p for p in catalogue}


def _onduleurs_unitaires(onduleurs):
    """``[(produit, kw_ac, triphase?)]`` — un élément PAR appareil."""
    sortie = []
    for item in (onduleurs or {}).get('combinaison') or []:
        for _ in range(int(item.get('quantite') or 0)):
            sortie.append(item)
    return sortie


#: ADEV86 (D-ACI-3=b) — rôle C&I d'onduleur string → triphasé ?
_ROLE_TRIPHASE = {'onduleur_string_tri': True, 'onduleur_string_mono': False}


def _onduleur_triphase(catalogue, ondu, entrees):
    """ADEV86 — la phase de la SORTIE de l'onduleur : sa fiche (``ond_phases``),
    sinon son rôle C&I, sinon la phase déclarée du site (règle d'hier)."""
    article = _par_id(catalogue).get(ondu.get('produit')) or {}
    phases = (article.get('fiche') or {}).get('ond_phases')
    if phases in (1, 3):
        return phases == 3
    role = _ROLE_TRIPHASE.get(article.get('role_ci'))
    if role is not None:
        return role
    return entrees.get('phase') != 'mono'


def _protection_et_cable_ac(catalogue, ondu, entrees, lignes, alertes,
                            hypotheses):
    kw = _f(ondu.get('kw_ac')) or 0.0
    # ADEV86 — un onduleur monophasé prend le disjoncteur BIPOLAIRE (2P) du
    # calibre, un triphasé le tétrapolaire (4P).
    triphase = _onduleur_triphase(catalogue, ondu, entrees)
    phases = 3 if triphase else 1
    ib = courant_emploi_ac(kw, phases)
    calibre = calibre_disjoncteur(ib)
    poles = 4 if triphase else 2
    disj = _du_role(catalogue, 'protection_ac', lambda f, _p: (
        f.get('prot_type') == 'disjoncteur'
        and _f(f.get('prot_calibre_a')) == calibre
        and f.get('prot_poles') in (None, poles)))
    nom = ondu.get('nom') or 'onduleur'
    if ib > calibre + 1e-9:
        lignes.append(_ligne('protection_ac', None,
                             'Protection AC sortie %s' % nom, 1, 'u',
                             motif=MOTIF_BUREAU, a_confirmer=True, visite=True))
    else:
        # R3.3 (fondateur, 28/10/2026) — le disjoncteur DIT ses pôles : 4P
        # derrière un onduleur triphasé, 2P derrière un monophasé.
        lignes.append(_ligne(
            'protection_ac', disj,
            'Disjoncteur AC %g A %dP — sortie %s' % (calibre, poles, nom), 1, 'u',
            designation_moteur=True))
    longueur = _f(entrees.get('longueur_ac_m'))
    defaut = longueur is None or longueur <= 0
    if defaut:
        longueur = LONGUEUR_AC_DEFAUT_M
    base = AMPACITE_U1000R2V_TRI if triphase else AMPACITE_U1000R2V_MONO
    bareme = bareme_pour(base, ib, calibre)
    proposee = proposer_section(
        ib, longueur, 400.0 if triphase else 230.0, CHUTE_CIBLE_AC_PCT,
        bareme=bareme, coefficient=math.sqrt(3.0) if triphase else 2.0,
        calibre_in_a=calibre)
    if proposee.thermique_hors_bareme or proposee.hors_bareme:
        lignes.append(_ligne('cable_ac', None,
                             'Câble AC %s → TGBT' % nom, longueur, 'm',
                             motif=MOTIF_BUREAU, a_confirmer=True, visite=True))
        return
    section = float(proposee.section_mm2)
    cable = _du_role(catalogue, 'cable_ac', lambda f, _p: (
        f.get('cable_cote') in ('ac', None, '')
        and _f(f.get('cable_section_mm2')) == section))
    lignes.append(_ligne(
        'cable_ac', cable, 'Câble AC %g mm² %s → TGBT' % (section, nom),
        longueur, 'm', a_confirmer=defaut))
    if defaut:
        lignes[-1]['motif'] = lignes[-1]['motif'] or MOTIF_PRELIMINAIRE % (
            '%g m par onduleur' % LONGUEUR_AC_DEFAUT_M)
    hypotheses.append({
        'cle': 'section_ac_%s' % (ondu.get('produit') or nom),
        'valeur': section, 'statut': 'source',
        'source': '%s (Ib %.1f A, In %g A, chute %.2f %%)' % (
            proposee.critere, ib, calibre, proposee.chute_pct)})


MOTIF_CHAINES_BLOQUANTES = 'chaînes non faisables : quantité non calculée'


def _est_parafoudre(fiche, article):
    return (fiche.get('prot_type') == 'parafoudre'
            or 'parafoudre' in (article.get('nom') or '').lower())


def _nombre_de_chaines(chaines, nb_panneaux, nb_ond):
    """R3.1 (fondateur, 28/10/2026) — ``(n, statut)`` : le nombre de CHAÎNES
    (strings) de l'installation, même source que le câble DC.

    * ``statut = 'bloquant'`` — chaînes infaisables (ADEV87) : ``n = None`` ;
    * ``'concu'`` — Σ ``nb_chaines`` de la conception (``onduleurs['chaines']``) ;
    * ``'estime'`` — chaînes non conçues : plafond(panneaux ÷
      ``PANNEAUX_PAR_CHAINE_DEFAUT``), au moins une par onduleur quand aucun
      panneau n'est compté."""
    if any(c.get('bloquants') for c in chaines or ()):
        return None, 'bloquant'
    if chaines:
        n = sum(int(c.get('nb_chaines') or 0) for c in chaines)
        if n > 0:
            return n, 'concu'
    n = int(math.ceil(nb_panneaux / float(PANNEAUX_PAR_CHAINE_DEFAUT)))
    return (n or nb_ond), 'estime'


def _parafoudre_ac(catalogue, poles):
    """R3.3 — le parafoudre AC du nombre de pôles de l'installation
    (``prot_poles``) ; repli sur un parafoudre AC sans pôles publiés. À
    égalité de rang, un article tarifé passe devant (ADEV82)."""
    exact = _du_role(catalogue, 'protection_ac', lambda f, p: (
        _est_parafoudre(f, p) and _f(f.get('prot_poles')) == poles))
    if exact is not None and exact.get('prix_connu'):
        return exact
    repli = _du_role(catalogue, 'protection_ac', lambda f, p: (
        _est_parafoudre(f, p) and f.get('prot_poles') in (None, '')))
    if repli is not None and repli.get('prix_connu'):
        return repli
    return exact or repli


def _poste_absent(alertes, cle, libelle):
    alertes.append(_alerte(
        'POSTE_ABSENT_CATALOGUE',
        '%s : aucun article de ce rôle au catalogue (poste non composé, '
        'à créer en Stock).' % libelle, champ='composition.%s' % cle))


def _protections_dc_et_terre(catalogue, unitaires, lignes, alertes, *,
                             chaines, nb_panneaux, entrees):
    """ADEV83 / R3 (fondateur, 28/10/2026) — dès qu'un article porte le rôle,
    au prix du catalogue :

    * protection DC (fusibles / sectionneur) et parafoudre DC : UNE PAR
      CHAÎNE (string), jamais par MPPT — Σ ``nb_chaines`` de la conception ;
      chaînes non conçues ⇒ estimation préliminaire (``a_confirmer``) ;
      chaînes infaisables ⇒ « à chiffrer après visite », sans quantité ;
    * parafoudre AC par installation, 4P dès qu'un onduleur est triphasé
      (2P sinon) ;
    * mise à la terre : JAMAIS automatique — ajoutée seulement quand la
      visite (ou la saisie) dit ``mise_a_la_terre_necessaire is True`` ;
      inconnue ⇒ alerte interne ``CI_MISE_A_LA_TERRE_VISITE`` ; ``False`` ⇒
      rien.

    Aucun article du rôle ⇒ alerte INTERNE ``POSTE_ABSENT_CATALOGUE`` nommant
    le poste : ni ligne « prix à renseigner », ni refus (on ne bloque pas sur
    un article que la société n'a pas créé)."""
    nb_ond = len(unitaires)
    n, statut = _nombre_de_chaines(chaines, nb_panneaux, nb_ond)
    for cle, filtre, libelle in (
            ('protection_dc', lambda f, p: not _est_parafoudre(f, p),
             'Protection DC par chaîne'),
            ('parafoudre_dc', _est_parafoudre, 'Parafoudre DC par chaîne')):
        article = _du_role(catalogue, 'protection_dc', filtre)
        if article is None:
            _poste_absent(alertes, cle, libelle)
            continue
        if statut == 'bloquant':
            lignes.append(_ligne('protection_dc', article, libelle, None, 'u',
                                 motif=MOTIF_CHAINES_BLOQUANTES, a_confirmer=True,
                                 visite=True, designation_moteur=True))
            continue
        lignes.append(_ligne('protection_dc', article, libelle, n, 'u',
                             a_confirmer=statut == 'estime',
                             designation_moteur=True))
        if statut == 'estime':
            lignes[-1]['motif'] = lignes[-1]['motif'] or MOTIF_PRELIMINAIRE % (
                'chaînes non conçues : %d chaînes estimées' % n)

    poles = 4 if any(_onduleur_triphase(catalogue, ondu, entrees)
                     for ondu in unitaires) else 2
    libelle = 'Parafoudre AC %dP' % poles
    article = _parafoudre_ac(catalogue, poles)
    if article is None:
        _poste_absent(alertes, 'parafoudre_ac', libelle)
    else:
        lignes.append(_ligne('protection_ac', article, libelle, 1, 'u',
                             designation_moteur=True))

    besoin_terre = entrees.get('mise_a_la_terre_necessaire')
    if besoin_terre is True:
        article = _du_role(catalogue, 'mise_a_la_terre')
        if article is None:
            _poste_absent(alertes, 'mise_a_la_terre', 'Mise à la terre du champ PV')
        else:
            lignes.append(_ligne('mise_a_la_terre', article,
                                 'Mise à la terre du champ PV', 1, 'u'))
    elif besoin_terre is None:
        alertes.append(_alerte(
            'CI_MISE_A_LA_TERRE_VISITE',
            'mise à la terre : à vérifier à la visite technique, ajoutée au '
            'devis si nécessaire', champ='composition.mise_a_la_terre'))


def _du_role_tous(catalogue, role):
    """Tous les articles ÉLIGIBLES du rôle, ordre déterministe (id)."""
    return [p for p in sorted(catalogue, key=lambda x: (x.get('id') or 0))
            if p.get('eligible_ci') is not False
            and role in (p.get('role_ci'), p.get('role_devis'))]


def _marques_onduleurs(catalogue, onduleurs):
    """CMP10 — les marques (minuscules) des onduleurs de la combinaison."""
    par_id = _par_id(catalogue)
    marques = set()
    for item in (onduleurs or {}).get('combinaison') or []:
        marque = str((par_id.get(item.get('produit')) or {}).get('marque') or '').strip().lower()
        if marque:
            marques.add(marque)
    return marques


def _marque_de(article):
    return str((article or {}).get('marque') or '').strip().lower()


def _compteurs_compatibles(catalogue, onduleurs):
    """Les modèles de compteur que la fiche des onduleurs retenus dit
    compatibles (``ond_compteurs_compatibles``, minuscules)."""
    par_id = _par_id(catalogue)
    compatibles = set()
    for item in (onduleurs or {}).get('combinaison') or []:
        fiche = (par_id.get(item.get('produit')) or {}).get('fiche') or {}
        compatibles.update(str(t).strip().lower()
                           for t in fiche.get('ond_compteurs_compatibles') or []
                           if str(t).strip())
    return compatibles


def _cite_par_fiche(p, compatibles):
    texte = ('%s %s' % (p.get('nom') or '', p.get('marque') or '')).lower()
    return any(t in texte for t in compatibles)


#: R3.5 — calibre « sans borne » d'un compteur à TC externes.
CALIBRE_ILLIMITE = float('inf')


def _calibre_comptage(p):
    """R3.5 — le calibre (A) d'un dispositif de comptage : ``lim_calibre_a``
    publié, ``CALIBRE_ILLIMITE`` pour un compteur à TC externes sans calibre
    (``lim_mode == 'compteur_tc_externe'``), ``None`` sinon (article
    « legacy » sans calibre publié)."""
    fiche = p.get('fiche') or {}
    calibre = _f(fiche.get('lim_calibre_a'))
    if calibre is not None and calibre > 0:
        return calibre
    if fiche.get('lim_mode') == 'compteur_tc_externe':
        return CALIBRE_ILLIMITE
    return None


def courant_point_injection(catalogue, unitaires, entrees):
    """R3.5 — I (A) au point d'injection : Σ courant d'emploi AC
    (``core.electrique.courant_emploi_ac``) des onduleurs retenus, à la phase
    de LEUR sortie (même règle que leur disjoncteur)."""
    return sum(courant_emploi_ac(_f(ondu.get('kw_ac')) or 0.0,
                                 3 if _onduleur_triphase(catalogue, ondu, entrees) else 1)
               for ondu in unitaires)


def _comptage_par_calibre(catalogue, onduleurs, courant_a, alertes):
    """R3.5 (fondateur, 28/10/2026) — le dispositif de comptage choisi PAR
    CALIBRE : éligibles = calibre publié ≥ I (le plus petit gagne), sinon —
    quand I dépasse tous les calibres finis — le compteur à TC externes. La
    préférence CMP10 (fiche de l'onduleur, puis marque) s'applique DANS
    l'ensemble éligible tarifé. ``(article, True)`` quand un article éligible
    est retenu ; ``(article_sans_prix_ou_None, False)`` quand aucun éligible
    n'a de prix connu (l'appelant replie alors sur l'article legacy)."""
    candidats = [p for p in (_du_role_tous(catalogue, 'compteur_injection')
                             + _du_role_tous(catalogue, 'controleur_injection'))
                 if _calibre_comptage(p) is not None]
    finis = [p for p in candidats
             if _calibre_comptage(p) != CALIBRE_ILLIMITE
             and _calibre_comptage(p) + 1e-9 >= courant_a]
    eligibles = finis or [p for p in candidats
                          if _calibre_comptage(p) == CALIBRE_ILLIMITE]
    tarifes = [p for p in eligibles if p.get('prix_connu')]
    if not tarifes:
        return (min(eligibles, key=_calibre_comptage) if eligibles else None), False
    marques = _marques_onduleurs(catalogue, onduleurs)
    compatibles = _compteurs_compatibles(catalogue, onduleurs)
    preferes = [p for p in tarifes if compatibles and _cite_par_fiche(p, compatibles)]
    if not preferes and marques:
        preferes = [p for p in tarifes if _marque_de(p) in marques]
    if not preferes and marques and any(_marque_de(p) not in ('', *marques)
                                        for p in tarifes):
        alertes.append(_alerte('COMPTAGE_MARQUE_A_CONFIRMER', (
            "Comptage / limitation d'injection : aucun article tarifé compatible avec "
            "la marque des onduleurs (%s) au catalogue — article actuel gardé, "
            "compatibilité à confirmer." % ', '.join(sorted(marques)))))
    # ``min`` garde le premier à calibre égal : ordre déterministe (id).
    return min(preferes or tarifes, key=_calibre_comptage), True


def _article_de_comptage(catalogue, onduleurs, alertes=None, *, courant_a=None):
    """R3.5 — le compteur de CALIBRE suffisant d'abord
    (:func:`_comptage_par_calibre`). Un article SANS calibre publié (legacy,
    ex. le Smart Meter SMART-MET) n'est qu'un REPLI quand aucun article
    éligible n'a de prix connu : alerte interne ``COMPTAGE_CALIBRE_A_CONFIRMER``.

    Repli legacy — ADEV82 : un article TARIFÉ passe devant un article sans
    prix ; à prix égal, le contrôleur d'injection, puis le compteur que la
    fiche des onduleurs retenus dit compatible (``ond_compteurs_compatibles``).
    CMP10 (D-CMP-6) — catalogue multi-marques : l'article compatible (fiche, à
    défaut même ``marque`` que les onduleurs) d'abord ; aucun article tarifé
    compatible ⇒ choix actuel gardé + alerte interne ``COMPTAGE_MARQUE_A_CONFIRMER``."""
    alertes = alertes if alertes is not None else []
    eligible = None
    if courant_a is not None:
        eligible, retenu = _comptage_par_calibre(catalogue, onduleurs, courant_a, alertes)
        if retenu:
            return eligible
    compatibles = _compteurs_compatibles(catalogue, onduleurs)

    def compatible(p):
        return not compatibles or _cite_par_fiche(p, compatibles)

    controleurs = [p for p in _du_role_tous(catalogue, 'controleur_injection')
                   if _calibre_comptage(p) is None]
    compteurs = [p for p in _du_role_tous(catalogue, 'compteur_injection')
                 if _calibre_comptage(p) is None]
    legacy = _article_de_comptage_legacy(catalogue, onduleurs, alertes,
                                         controleurs, compteurs, compatible,
                                         compatibles)
    if courant_a is None:
        return legacy
    if legacy is not None and (legacy.get('prix_connu') or eligible is None):
        alertes.append(_alerte('COMPTAGE_CALIBRE_A_CONFIRMER', (
            "Comptage / limitation d'injection : courant au point d'injection "
            "%.1f A — aucun compteur tarifé de calibre suffisant au catalogue ; "
            "article sans calibre publié retenu (%s), calibre à confirmer."
            % (courant_a, legacy.get('nom') or '?'))))
        return legacy
    return eligible


def _article_de_comptage_legacy(catalogue, onduleurs, alertes, controleurs,
                                compteurs, compatible, compatibles):
    """Le choix d'avant R3.5 (ADEV82 + CMP10) parmi les articles SANS calibre
    publié."""
    ordre = ([c for c in controleurs if c.get('prix_connu')]
             + [c for c in compteurs if c.get('prix_connu') and compatible(c)]
             + [c for c in compteurs if c.get('prix_connu')]
             + controleurs + compteurs)
    marques = _marques_onduleurs(catalogue, onduleurs)
    tarifes = [c for c in controleurs + compteurs if c.get('prix_connu')]
    if marques and any(_marque_de(c) not in ('', *marques) for c in tarifes):
        # La fiche d'abord, puis la même marque (ordre ADEV82 gardé dans chaque rang).
        preferes = [c for c in tarifes if _cite_par_fiche(c, compatibles)]
        preferes += [c for c in tarifes if _marque_de(c) in marques and c not in preferes]
        if preferes:
            return preferes[0]
        if alertes is not None:
            alertes.append(_alerte('COMPTAGE_MARQUE_A_CONFIRMER', (
                "Comptage / limitation d'injection : aucun article tarifé compatible avec "
                "la marque des onduleurs (%s) au catalogue — article actuel gardé, "
                "compatibilité à confirmer." % ', '.join(sorted(marques)))))
    return ordre[0] if ordre else None


def _comptage(catalogue, nb_ond, entrees, lignes, alertes, onduleurs=None,
              unitaires=None, hypotheses=None):
    tension = (entrees.get('tension') or '').upper()
    revente = bool(entrees.get('revente_choisie'))
    if tension == 'MT' and revente:
        return
    points = entrees.get('nb_points_raccordement')
    try:
        points = int(points) if points not in (None, '') else None
    except (TypeError, ValueError):
        points = None
    a_confirmer = points is None
    points = points or 1
    # R3.5 — le compteur suit le courant AC au point d'injection.
    courant = None
    if unitaires is not None:
        courant = courant_point_injection(catalogue, unitaires, entrees)
        if hypotheses is not None:
            hypotheses.append({
                'cle': 'comptage_courant_a', 'valeur': round(courant, 1),
                'statut': 'calculee',
                'source': "Σ courant d'emploi AC des onduleurs"})
    article = _article_de_comptage(catalogue, onduleurs, alertes, courant_a=courant)
    role = article.get('role_ci') if article else 'compteur_injection'
    fiche = (article or {}).get('fiche') or {}
    max_pilotes = fiche.get('lim_onduleurs_max')
    if nb_ond <= 1:
        # R3.5 — un seul onduleur : un dispositif par point, rien à demander
        # au fournisseur (``lim_onduleurs_max`` ne joue qu'à partir de deux).
        quantite = points
        motif = None
    elif max_pilotes:
        quantite = points * int(math.ceil(nb_ond / float(max_pilotes)))
        motif = None
    else:
        quantite = points
        motif = MOTIF_FOURNISSEUR
        a_confirmer = True
    lignes.append(_ligne(
        role, article, "Comptage / limitation d'injection", quantite, 'u',
        motif=motif,
        a_confirmer=a_confirmer))
    if a_confirmer and entrees.get('nb_points_raccordement') in (None, ''):
        alertes.append(_alerte(
            'CI_POINTS_RACCORDEMENT',
            'nombre de points de raccordement non déclaré : un dispositif '
            'de comptage compté, à confirmer à la visite'))


def _est_dongle(p):
    return ((p.get('fiche') or {}).get('log_type') or '') == 'dongle'


def _dongle_de_la_marque(catalogue, marques):
    """R3.6 — la clé wifi (``log_type == 'dongle'``) des onduleurs : marque
    des onduleurs d'abord (CMP10), puis sans marque ; tarifée d'abord dans
    chaque rang. ``None`` quand aucune clé n'est disponible pour la marque."""
    dongles = [p for p in _du_role_tous(catalogue, 'logger_supervision') if _est_dongle(p)]
    meme = [p for p in dongles if marques and _marque_de(p) in marques]
    neutres = [p for p in dongles if not _marque_de(p) or not marques]
    rangs = [p for rang in (meme, neutres) for p in rang if p.get('prix_connu')]
    rangs += [p for rang in (meme, neutres) for p in rang if not p.get('prix_connu')]
    return rangs[0] if rangs else None


def _logger(catalogue, nb_ond, lignes, onduleurs=None, alertes=None):
    marques = _marques_onduleurs(catalogue, onduleurs)
    dongle = _dongle_de_la_marque(catalogue, marques) if nb_ond else None
    if dongle is not None:
        # R3.6 (fondateur, 28/10/2026) — UNE clé wifi PAR ONDULEUR, sur la
        # ligne « Supervision & comptage » ; aucun logger central composé.
        lignes.append(_ligne('logger_supervision', dongle,
                             'Clé wifi de supervision', nb_ond, 'u'))
        if nb_ond >= 2 and alertes is not None:
            alertes.append(_alerte('SUPERVISION_LOGGER_A_CONFIRMER', (
                'Supervision : une clé wifi par onduleur (%d) ; logger central à '
                'confirmer selon la marque.' % nb_ond)))
        return
    if nb_ond < 2:
        return
    centraux = [p for p in _du_role_tous(catalogue, 'logger_supervision')
                if not _est_dongle(p)]
    article = next((p for p in centraux if p.get('prix_connu')),
                   centraux[0] if centraux else None)
    loggers = [p for p in centraux if p.get('prix_connu')]
    if marques and any(_marque_de(p) not in ('', *marques) for p in loggers):
        # CMP10 (D-CMP-6) — le logger de la marque des onduleurs d'abord.
        meme = _du_role(catalogue, 'logger_supervision',
                        lambda _f, p: _marque_de(p) in marques and not _est_dongle(p))
        if meme is not None and meme.get('prix_connu'):
            article = meme
        elif alertes is not None:
            alertes.append(_alerte('LOGGER_MARQUE_A_CONFIRMER', (
                'Logger de supervision : aucun article tarifé de la marque des onduleurs '
                '(%s) au catalogue — article actuel gardé, compatibilité à confirmer.'
                % ', '.join(sorted(marques)))))
    max_sup = ((article or {}).get('fiche') or {}).get('log_onduleurs_max')
    quantite = int(math.ceil(nb_ond / float(max_sup))) if max_sup else 1
    # ADEV82 — « à confirmer fournisseur » seulement quand la fiche se tait
    # sur le nombre d'onduleurs supervisés.
    lignes.append(_ligne('logger_supervision', article,
                         'Logger de supervision', quantite, 'u',
                         motif=None if max_sup else MOTIF_FOURNISSEUR,
                         a_confirmer=not max_sup))


def _appliquer_bareme_coffret(ligne, article, nb_ond, nb_panneaux):
    """Coffret C&I au barème (fondateur, 26/10/2026), comme le tableau
    résidentiel : total HT = par onduleur × onduleurs + par panneau ×
    panneaux, réparti sur la quantité de la ligne (centime). Sans barème :
    ligne inchangée (prix catalogue)."""
    bareme = (article or {}).get('bareme_coffret')
    if not bareme:
        return
    par_ond = _d(bareme.get('par_onduleur_ht')) or Decimal('0')
    par_pan = _d(bareme.get('par_panneau_ht')) or Decimal('0')
    quantite = Decimal(str(ligne.get('quantite') or 1))
    total = par_ond * Decimal(int(nb_ond or 0)) + par_pan * Decimal(int(nb_panneaux or 0))
    ligne['prix_unitaire_ht'] = str((total / quantite).quantize(Decimal('0.01')))
    ligne['prix_connu'] = True
    ligne['motif'] = None
    for cle in ('palier', 'prix_unitaire_ttc'):
        ligne.pop(cle, None)


def _prestation(cle, libelle, forfait, article, kwc, nb_panneaux):
    montants = [_d((forfait or {}).get(k))
                for k in ('fixe_ht', 'par_kwc_ht', 'par_panneau_ht')]
    source = ((forfait or {}).get('source') or '').strip()
    if not source or all(m is None for m in montants):
        return _ligne(cle, None, libelle, 1, 'forfait',
                      motif='prestation non réglée : prix à renseigner')
    fixe, par_kwc, par_panneau = (m or Decimal('0') for m in montants)
    total = (fixe + par_kwc * Decimal(str(kwc))
             + par_panneau * Decimal(nb_panneaux)).quantize(Decimal('0.01'))
    ligne = _ligne(cle, article, libelle, 1, 'forfait')
    ligne['prix_connu'] = True
    ligne['motif'] = 'forfait société (source : %s)' % source
    ligne['prix_unitaire_ht'] = str(total)
    return ligne


def composer_ci(kwc, catalogue, *, onduleurs, entrees, forfaits):
    """La composition C&I serveur (forme ``composition`` du contrat).

    ``catalogue`` : éléments ``stock.selectors.produits_ci`` (+ facultatif
    ``prix_vente_ht``). ``onduleurs`` : résultat de
    ``moteur_ci.onduleurs.combiner_onduleurs``. ``entrees`` : ``{module
    {produit, designation, pmax_wc, prix_connu}, phase, tension BT|MT,
    type_pose, longueur_dc_m, longueur_ac_m, nb_points_raccordement,
    revente_choisie, besoin_cellule_mt, batterie_souhaitee}``. ``forfaits`` :
    ``CompanyProfile.forfaits_ci``.
    """
    catalogue = list(catalogue or [])
    entrees = dict(entrees or {})
    lignes, alertes, hypotheses = [], [], []
    kwc = _f(kwc) or 0.0

    # ── Panneaux
    module = entrees.get('module') or {}
    pmax = _f(module.get('pmax_wc'))
    nb_panneaux = int(math.ceil(kwc * 1000.0 / pmax - 1e-9)) if pmax else 0
    if pmax:
        lignes.append({
            'role': 'panneau', 'produit': module.get('produit'),
            'designation': module.get('designation') or 'Module PV',
            'quantite': nb_panneaux, 'unite': 'u',
            'prix_connu': bool(module.get('prix_connu')),
            'motif': None if module.get('prix_connu') else MOTIF_PRIX,
            'a_confirmer_visite': False})
        _appliquer_palier(lignes[-1], module)
    else:
        alertes.append(_alerte('CI_MODULE_FICHE',
                               'module sans puissance publiée : nombre de '
                               'panneaux non calculé', niveau='bloquant'))

    # ── Onduleurs (combinaison CIQ111). ADEV86 — la ligne garde le rôle de
    # LIGNE « onduleur string » (``onduleur_string_tri``) que lisent
    # ``taille.cout_vente_ht`` et ``etude_ci._completer_prix`` : l'article
    # monophasé y est désigné par son nom, jamais par un texte « triphasé ».
    par_id = _par_id(catalogue)
    for item in (onduleurs or {}).get('combinaison') or []:
        lignes.append(_ligne(
            'onduleur_string_tri', par_id.get(item.get('produit')) or {
                'id': item.get('produit'), 'nom': item.get('nom'),
                'prix_connu': True},
            item.get('nom') or 'Onduleur', item.get('quantite'), 'u'))
    unitaires = _onduleurs_unitaires(onduleurs)
    nb_ond = len(unitaires)

    # ── Câble DC : Σ chaînes × longueur déclarée
    chaines = (onduleurs or {}).get('chaines')
    longueur_dc = _f(entrees.get('longueur_dc_m'))
    cable_dc = _du_role(catalogue, 'cable_dc')
    if any(c.get('bloquants') for c in chaines or ()):
        # ADEV87 — chaînes infaisables (alerte bloquante de la combinaison) :
        # aucune quantité tirée d'une conception impossible.
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC', None,
                             'm', motif='chaînes non faisables : quantité non '
                             'calculée', a_confirmer=True, visite=True))
    elif not chaines or longueur_dc is None or longueur_dc <= 0:
        nb_chaines = (sum(int(c.get('nb_chaines') or 0) for c in chaines) if chaines
                      else int(math.ceil(nb_panneaux / PANNEAUX_PAR_CHAINE_DEFAUT)))
        metres = 2 * nb_chaines * DISTANCE_DC_DEFAUT_M
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC', metres, 'm',
                             a_confirmer=True))
        lignes[-1]['motif'] = lignes[-1]['motif'] or MOTIF_PRELIMINAIRE % (
            '2 × %d chaînes × %g m' % (nb_chaines, DISTANCE_DC_DEFAUT_M))
    else:
        # D-CMP-2 (à revoir) — la distance déclarée est l'aller simple champ →
        # onduleur : 2 conducteurs (+ / −) par chaîne, comme le défaut fondateur.
        nb_chaines = sum(int(c.get('nb_chaines') or 0) for c in chaines)
        metres = round(2 * nb_chaines * longueur_dc, 2)
        lignes.append(_ligne('cable_dc', cable_dc, 'Câble solaire DC', metres, 'm'))
        hypotheses.append({
            'cle': 'cable_dc_m', 'valeur': metres, 'statut': 'declare',
            'source': '2 × %d chaînes × %g m (distance déclarée champ → onduleur)' % (
                nb_chaines, longueur_dc)})

    # ── Coffrets DC (un par onduleur), protections et câble AC par onduleur
    if nb_ond:
        lignes.append(_ligne('coffret_dc', _du_role(catalogue, 'coffret_dc'),
                             'Coffret DC C&I', nb_ond, 'u'))
        _appliquer_bareme_coffret(lignes[-1], _du_role(catalogue, 'coffret_dc'),
                                  nb_ond, nb_panneaux)
    for ondu in unitaires:
        _protection_et_cable_ac(catalogue, ondu, entrees, lignes, alertes,
                                hypotheses)
    # ── ADEV83 / R3 — protections DC (par chaîne), parafoudres DC / AC,
    # mise à la terre (seulement si la visite la dit nécessaire)
    if nb_ond:
        _protections_dc_et_terre(catalogue, unitaires, lignes, alertes,
                                 chaines=chaines, nb_panneaux=nb_panneaux,
                                 entrees=entrees)

    # ── Structure par type de pose du toit
    declare = (entrees.get('type_pose') or '').strip()
    type_pose = declare or TYPE_POSE_DEFAUT
    structure = _du_role(catalogue, 'structure_ci', lambda f, p: (
        (p.get('type_pose') or f.get('struct_type_pose')) == type_pose))
    if structure is None and not declare:
        structure = _du_role(catalogue, 'structure_ci')
    lignes.append(_ligne('structure_ci', structure,
                         'Structure C&I (%s)' % type_pose, nb_panneaux,
                         'module', a_confirmer=not declare))
    if not declare:
        lignes[-1]['motif'] = lignes[-1]['motif'] or MOTIF_PRELIMINAIRE % (
            'type de pose non déclaré : %s' % TYPE_POSE_DEFAUT)

    # ── Comptage / limitation, logger, coffret AC
    _comptage(catalogue, nb_ond, entrees, lignes, alertes, onduleurs,
              unitaires=unitaires, hypotheses=hypotheses)
    _logger(catalogue, nb_ond, lignes, onduleurs, alertes)
    lignes.append(_ligne('coffret_ac', _du_role(catalogue, 'coffret_ac'),
                         'Coffret AC C&I', 1, 'u'))
    _appliquer_bareme_coffret(lignes[-1], _du_role(catalogue, 'coffret_ac'),
                              nb_ond, nb_panneaux)

    # ── Cellule MT
    tension = (entrees.get('tension') or '').upper()
    if entrees.get('besoin_cellule_mt') is True:
        lignes.append(_ligne('cellule_mt', _du_role(catalogue, 'cellule_mt'),
                             'Cellule MT', 1, 'u'))
    elif tension == 'MT' and entrees.get('besoin_cellule_mt') is None:
        alertes.append(_alerte(
            'CI_POSTE_LIVRAISON',
            'poste de livraison à confirmer à la visite', champ='tension'))

    # ── Prestations réglées par la société
    for cle, libelle in PRESTATIONS_CI:
        lignes.append(_prestation(cle, libelle, (forfaits or {}).get(cle),
                                  _du_role(catalogue, cle), kwc, nb_panneaux))

    # ── Options : O&M nommée toujours ; batterie seulement si catalogue+besoin
    om = _du_role(catalogue, 'om_ci')
    options = [{'cle': 'om',
                'libelle': nom_client((om or {}).get('nom'))
                or 'Exploitation et maintenance (O&M)',
                'prix_connu': bool(om and om.get('prix_connu')),
                'valeur': 'valeur non chiffrée'}]
    batterie = _du_role(catalogue, 'batterie_ci')
    if batterie is not None and entrees.get('batterie_souhaitee'):
        options.append({'cle': 'batterie', 'libelle': batterie.get('nom'),
                        'prix_connu': bool(batterie.get('prix_connu')),
                        'valeur': 'valeur non chiffrée'})

    prix_a_renseigner, a_chiffrer_visite = postes_non_chiffres(lignes)
    return {
        'lignes': lignes,
        'onduleurs': {
            'combinaison': (onduleurs or {}).get('combinaison'),
            'ratio_dc_ac': (onduleurs or {}).get('ratio_dc_ac'),
            'chaines': chaines,
        },
        'prix_a_renseigner': prix_a_renseigner,
        'a_chiffrer_visite': a_chiffrer_visite,
        'incomplet': bool(prix_a_renseigner or a_chiffrer_visite),
        'options': options,
        'alertes': alertes,
        'hypotheses': hypotheses,
    }
