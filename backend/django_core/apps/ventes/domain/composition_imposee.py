"""COP2-V3 — la COMPOSITION IMPOSÉE du devis automatique résidentiel.

« Prépare-lui un devis : 10 panneaux, onduleur triphasé de 10 kW, batterie de
5 kWh » : le commercial (ou l'assistant pour lui) IMPOSE le kit. Ce module est
la couture MINCE entre la demande et le constructeur existant :

1. :func:`imposition_du_corps` lit les champs imposés du corps VALIDÉ ;
2. :func:`build_devis_auto_impose` applique les règles (résidentiel seulement,
   ``nb_panneaux`` obligatoire, ``target_kwc`` et ``les_deux`` refusés, forme
   id XOR forme taille), résout chaque élément par LE résolveur
   (``domain/resolution_catalogue``) — zéro ou plusieurs candidats ⇒ 409
   ``choix``, le serveur ne choisit jamais en silence —, contrôle la
   composition à blanc (couple panneau/onduleur, fenêtre de tension de la
   batterie, phase du lead), puis appelle LE constructeur résidentiel
   (``creation_auto_residentiel._build_devis_auto_residentiel``) avec
   l'imposition. ``build_devis_auto`` (golden AST) n'est pas touché ;
3. le MARQUEUR ``etude_params['composition_imposee']`` (propriétaire
   ``etude_schema.COMPOSITION_IMPOSEE``) dit aux chemins qui recomposent qu'ils
   ne doivent pas défaire l'imposition ; :func:`effacer_marqueur` est appelé
   par les gestes commerciaux explicites (appliquer / régénérer une taille) ;
   la taille changée EN PLACE par l'assistant le met à jour
   (:func:`marqueur_retaille`, ``domain/taille_assistant``).

Les alertes (règle du 17/11 : toute entrée SUPPOSÉE est annoncée avec le champ
du lead) partent dans ``journal_auto['alertes']``. Aucun statut touché
(règle #4), aucun prix d'achat nulle part.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from apps.ventes.domain.taille import AutoDevisError

CLE_MARQUEUR = 'composition_imposee'

#: Les champs de ``DevisAutoRequest`` qui déclenchent le mode imposé.
CHAMPS_IMPOSES = ('nb_panneaux', 'panneau_produit_id', 'onduleur_produit_id',
                  'onduleur_kw', 'onduleur_phase', 'batterie_produit_id',
                  'batterie_kwh')

#: Seuil « recommander ET signaler » (décision du 23/10, > 120 panneaux).
PANNEAUX_A_SIGNALER = 120
#: La borne publiée de ``DevisAutoRequest.nb_panneaux``.
NB_PANNEAUX_MAX = 200
RATIO_DC_AC = (0.8, 1.4)


class ChoixRequis(AutoDevisError):
    """409 ``{detail, field, choix}`` : zéro ou plusieurs produits pour un
    élément imposé. ``choix`` nomme les candidats (≤ 10)."""

    def __init__(self, message, *, field=None, choix=None):
        super().__init__(message, field=field)
        self.choix = list(choix or [])


@dataclass(frozen=True)
class Imposition:
    """Ce que le constructeur résidentiel reçoit, tout résolu."""

    nb_panneaux: int
    panel_watt: float
    panneau_id: int
    scenario: str
    onduleur_impose: object = None
    batterie_imposee: object = None
    marqueur: dict = field(default_factory=dict)


def imposition_du_corps(corps, *, nb_panneaux_seul_impose=True):
    """Les champs imposés PRÉSENTS (non nuls) du corps validé, ou ``{}``.

    ``nb_panneaux_seul_impose=False`` — le dry-run ``POST devis/composition/``,
    où ``nb_panneaux`` est l'entrée HISTORIQUE non imposée (``{kwc |
    nb_panneaux}``) : le mode imposé n'y commence qu'avec un des six AUTRES
    champs ; ``nb_panneaux`` seul ⇒ ``{}`` (route strictement inchangée)."""
    presents = {cle: corps.get(cle) for cle in CHAMPS_IMPOSES
                if (corps or {}).get(cle) not in (None, '')}
    if not nb_panneaux_seul_impose and set(presents) <= {'nb_panneaux'}:
        return {}
    return presents


def marqueur(devis):
    """Le marqueur d'imposition du devis, ou ``None``."""
    valeur = (getattr(devis, 'etude_params', None) or {}).get(CLE_MARQUEUR)
    return valeur if isinstance(valeur, dict) else None


def effacer_marqueur(devis):
    """Retire le marqueur (geste commercial explicite). Sans effet sinon."""
    if marqueur(devis) is None:
        return False
    from apps.ventes.domain.etude_schema import COMPOSITION_IMPOSEE, ecrire
    ecrire(devis, proprietaire=COMPOSITION_IMPOSEE, **{CLE_MARQUEUR: None})
    return True


def batterie_imposee_du_devis(devis):
    """``(produit, nombre)`` de la batterie IMPOSÉE, pour la resynchronisation.

    ``(None, 0)`` : aucune batterie imposée (le choix catalogue s'applique) ;
    ``(False, 0)`` : imposée mais plus tarifée au catalogue de la société
    (rien n'est posé, jamais un remplaçant)."""
    produits = (marqueur(devis) or {}).get('produits') or {}
    produit_id = produits.get('batterie')
    if not produit_id:
        return None, 0
    from apps.ventes.domain.etape_composer import _fiche_tarifee
    produit = _fiche_tarifee(devis.company, produit_id)
    if produit is None:
        return False, 0
    return produit, max(1, int(produits.get('batterie_nombre') or 1))


def batterie_de_resynchro(devis, batterie, avertissements):
    """La resynchronisation reprend la batterie IMPOSÉE (jamais le choix
    catalogue ``batterie``) : rend ``(batterie, nombre, manquante)``.
    ``manquante`` — imposée mais plus tarifée : rien n'est posé, et c'est
    DIT ici (une seule phrase, pas celle du catalogue)."""
    imposee, nombre = batterie_imposee_du_devis(devis)
    if imposee is False:
        avertissements.append(
            'La batterie imposée à la création du devis n\'est plus '
            'tarifée au catalogue : la ligne batterie n\'a pas été '
            'ajoutée.')
        return None, 0, True
    return (batterie if imposee is None else imposee), nombre, False


def abstention_onduleur(devis, ligne, avertissements):
    """Un onduleur IMPOSÉ n'est jamais permuté : rend ``True`` (abstention
    DITE) quand le marqueur porte un ONDULEUR imposé, ``False`` sinon — un
    marqueur sans onduleur (panneaux seuls imposés) laisse la permutation
    du catalogue jouer, sans quoi la batterie ajoutée resterait derrière un
    onduleur réseau (batterie fantôme)."""
    if not ((marqueur(devis) or {}).get('produits') or {}).get('onduleur'):
        return False
    avertissements.append(
        'L\'onduleur « %s » a été imposé à la création du devis : '
        'il n\'a pas été permuté. Changez-le à la main si le '
        'scénario batterie a changé.'
        % (ligne.designation or 'ligne sans désignation'))
    return True


def cles_tailles_servies(devis):
    """Les tailles que ``offres_tailles.deriver`` compose, dans l'ordre de
    déduplication : « Recommandé » seul sur un devis à composition imposée
    (Éco / Max composeraient un autre kit que celui imposé)."""
    if marqueur(devis) is not None:
        return ('recommande',)
    return ('recommande', 'eco', 'max')


def poser_marqueur(devis, contenu):
    from apps.ventes.domain.etude_schema import COMPOSITION_IMPOSEE, ecrire
    ecrire(devis, proprietaire=COMPOSITION_IMPOSEE, **{CLE_MARQUEUR: contenu})


# ── La taille d'un devis composé sur demande, changée en place ──────────────
def imposes_de_retaille(devis, nb_panneaux):
    """La demande qui recompose ce devis marqué à ``nb_panneaux`` : les
    produits du MARQUEUR désignés par leur id (forme id du mode imposé),
    jamais re-résolus par taille — l'onduleur et la batterie vendus restent
    ceux-là. ``None`` quand le marqueur ne nomme pas son panneau (marqueur
    incomplet : la recomposition en place est impossible)."""
    produits = (marqueur(devis) or {}).get('produits') or {}
    if not produits.get('panneau'):
        return None
    imposes = {'nb_panneaux': int(nb_panneaux),
               'panneau_produit_id': produits['panneau']}
    for cle, champ in (('onduleur', 'onduleur_produit_id'),
                       ('batterie', 'batterie_produit_id')):
        if produits.get(cle):
            imposes[champ] = produits[cle]
    return imposes


def composition_conforme_au_marqueur(devis):
    """Les lignes du devis portent-elles ENCORE les produits du marqueur ?
    Panneaux d'un seul produit (celui du marqueur), onduleur et batterie
    imposés présents et seuls de leur classe. Faux dès qu'un humain a changé
    un de ces produits à l'écran : la machine ne devine pas."""
    from apps.ventes.domain.catalogue import (
        _is_battery, _is_hybrid_inverter, _is_offgrid_inverter, _is_panel,
        _is_reseau_inverter)
    from apps.ventes.domain.lignes import _classe_ligne, _lignes_produit

    produits = (marqueur(devis) or {}).get('produits') or {}
    lignes = _lignes_produit(devis)

    def _ids(*predicats):
        return {li.produit_id for li in lignes
                if any(_classe_ligne(li, p) for p in predicats)}

    attendus = [((_is_panel,), produits.get('panneau')),
                ((_is_battery,), produits.get('batterie')),
                ((_is_reseau_inverter, _is_hybrid_inverter,
                  _is_offgrid_inverter), produits.get('onduleur'))]
    return bool(produits.get('panneau')) and all(
        _ids(*predicats) == {produit_id}
        for predicats, produit_id in attendus if produit_id)


def marqueur_retaille(devis, imposition, *, modules=None):
    """Le marqueur APRÈS une taille changée en place : la demande porte le
    nouveau compte, les produits restent ceux du marqueur (``batterie_nombre``
    suit ``modules`` s'il est donné), ``par`` / ``le`` disent qui et quand."""
    ancien = marqueur(devis) or {}
    produits = dict(ancien.get('produits') or {})
    if modules and produits.get('batterie'):
        produits['batterie_nombre'] = int(modules)
    return {**ancien,
            'demande': {**(ancien.get('demande') or {}),
                        'nb_panneaux': int(imposition.nb_panneaux)},
            'produits': produits,
            'par': imposition.marqueur.get('par'),
            'le': imposition.marqueur.get('le')}


# ── Les lignes TTC (carte ``devis_cree`` + ``lignes-assistant``) ─────────────
def _deux(valeur):
    return str(Decimal(valeur).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def lignes_ttc(devis, *, avec_ids=False):
    """Les lignes PRODUIT du devis, prix TTC seulement (jamais d'achat).

    Le TTC est DÉRIVÉ du HT stocké : taux de la ligne, sinon celui du devis.
    Copilote vague 2 (VAD7) — le total de ligne part du prix unitaire TTC
    ARRONDI au centime (celui qui est affiché), comme l'écran 100 % TTC du
    devis : total = quantité × P.U. TTC × (1 − remise de ligne). Avant, le
    HT au centime remultiplié rendait 8 × 1 400,00 = 11 200,03."""
    rendu = []
    taux_devis = getattr(devis, 'taux_tva', None) or Decimal('0')
    for ligne in devis.lignes.all().order_by('ordre', 'id'):
        if (getattr(ligne, 'type_ligne', None) or 'produit') != 'produit':
            continue
        taux = ligne.taux_tva if ligne.taux_tva is not None else taux_devis
        facteur = Decimal('1') + Decimal(str(taux)) / Decimal('100')
        prix = Decimal(str(ligne.prix_unitaire or 0))
        quantite = Decimal(str(ligne.quantite or 0))
        remise = Decimal(str(getattr(ligne, 'remise', 0) or 0))
        unitaire_ttc = Decimal(_deux(prix * facteur))
        total = quantite * unitaire_ttc * (Decimal('1') - remise / Decimal('100'))
        entree = {
            'designation': ligne.designation,
            'quantite': (int(quantite) if quantite == quantite.to_integral_value()
                         else float(quantite)),
            'prix_unitaire_ttc': _deux(unitaire_ttc),
            'total_ttc': _deux(total),
            'variante': getattr(ligne, 'variante', '') or '',
        }
        if avec_ids:
            entree = {'ligne_id': ligne.pk, 'produit_id': ligne.produit_id,
                      **entree}
        rendu.append(entree)
    return rendu


# ── La construction imposée ──────────────────────────────────────────────────
def _alerter(alertes, code, message, champ=None):
    entree = {'code': code, 'message': message}
    if champ:
        entree['champ'] = champ
    if all(a.get('message') != message for a in alertes):
        alertes.append(entree)


def _resolu_ou_409(resolution, *, champ_id, champ_taille, company):
    from apps.ventes.domain import resolution_catalogue as rc
    if resolution.statut == rc.STATUT_UNIQUE:
        return resolution
    if resolution.statut == rc.STATUT_AMBIGU:
        raise ChoixRequis(resolution.raison, field=champ_id,
                          choix=rc.choix_409(resolution.candidats, company))
    raise ChoixRequis(resolution.raison, field=champ_taille or champ_id,
                      choix=[])


def _fmt(valeur):
    from apps.ventes.domain.resolution_catalogue import _fmt as fmt
    return fmt(valeur)


def _refuser_modes(imposes, *, target_kwc, scenario, lead):
    """Les règles d'entrée du mode imposé — refus 409 nommant le champ."""
    marche = (getattr(lead, 'type_installation', '') or '').strip().lower()
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            'La composition imposée ne vaut que pour le résidentiel : ce lead '
            'est « %s ». Utilisez le devis automatique sans composition, ou '
            'le générateur.' % marche, field='type_installation')
    if not imposes.get('nb_panneaux'):
        raise AutoDevisError(
            'Composition imposée : indiquez le nombre de panneaux '
            '(nb_panneaux).', field='nb_panneaux')
    if not 1 <= int(imposes['nb_panneaux']) <= NB_PANNEAUX_MAX:
        # Borne de ``DevisAutoRequest`` ; le dry-run (``devis/composition/``)
        # publie une borne plus large et passe aussi par ici.
        raise AutoDevisError(
            'Composition imposée : %d panneaux au plus (nb_panneaux).'
            % NB_PANNEAUX_MAX, field='nb_panneaux')
    if target_kwc not in (None, ''):
        raise AutoDevisError(
            'Composition imposée : la puissance cible (target_kwc) ne se '
            'combine pas avec un nombre de panneaux imposé.', field='target_kwc')
    if scenario == 'les_deux':
        raise AutoDevisError(
            'Composition imposée : une seule option (avec ou sans batterie), '
            'jamais « les_deux ».', field='scenario')
    if scenario not in ('', 'avec', 'sans'):
        raise AutoDevisError('Scénario inconnu « %s » — attendu : sans, avec.'
                             % scenario, field='scenario')
    if imposes.get('onduleur_produit_id') and (
            imposes.get('onduleur_kw') or imposes.get('onduleur_phase')):
        raise AutoDevisError(
            "Onduleur : donnez soit son produit (onduleur_produit_id), soit sa "
            'puissance et sa phase (onduleur_kw, onduleur_phase), pas les deux.',
            field='onduleur_produit_id')
    if imposes.get('onduleur_phase') and not imposes.get('onduleur_kw'):
        raise AutoDevisError(
            "Onduleur : la phase (onduleur_phase) s'accompagne de sa puissance "
            '(onduleur_kw).', field='onduleur_kw')
    if imposes.get('batterie_produit_id') and imposes.get('batterie_kwh'):
        raise AutoDevisError(
            'Batterie : donnez soit son produit (batterie_produit_id), soit sa '
            'capacité (batterie_kwh), pas les deux.', field='batterie_produit_id')
    batterie = bool(imposes.get('batterie_produit_id') or imposes.get('batterie_kwh'))
    if batterie and scenario == 'sans':
        raise AutoDevisError(
            'Une batterie est demandée : le scénario « sans » batterie ne '
            "s'applique pas.", field='scenario')
    return marche


def _onduleur(imposes, entrees, *, company, famille, hors_reseau,
              phase_lead, raccordement_vide, alertes):
    """L'``Entree`` de l'onduleur imposé, ou ``None`` (non imposé)."""
    from apps.ventes.domain import resolution_catalogue as rc
    if imposes.get('onduleur_produit_id'):
        resolution = _resolu_ou_409(
            rc.resoudre_par_id(company, rc.GENRE_ONDULEUR,
                               imposes['onduleur_produit_id'], entrees=entrees),
            champ_id='onduleur_produit_id', champ_taille=None, company=company)
        entree = resolution.candidats[0]
        if hors_reseau and entree.famille != rc.FAMILLE_OFFGRID:
            raise AutoDevisError(
                'Le lead déclare un site sans réseau (raccordement « aucun ») : '
                "« %s » est un onduleur raccordé, il ne peut pas l'alimenter. "
                'Choisissez un onduleur hors réseau.' % entree.produit.nom,
                field='raccordement')
        if not hors_reseau and entree.famille == rc.FAMILLE_OFFGRID:
            raise AutoDevisError(
                '« %s » est un onduleur hors réseau : ce lead est raccordé.'
                % entree.produit.nom, field='onduleur_produit_id')
        if not hors_reseau and entree.famille != famille:
            raise AutoDevisError(
                ('« %s » est un onduleur hybride : indiquez la batterie '
                 '(batterie_kwh ou batterie_produit_id) ou le scénario « avec ».'
                 if entree.famille == rc.FAMILLE_HYBRIDE else
                 "« %s » est un onduleur réseau : il ne porte pas de batterie. "
                 'Choisissez un onduleur hybride.') % entree.produit.nom,
                field='onduleur_produit_id')
        for message in resolution.alertes:
            _alerter(alertes, 'produit_designe', message, 'onduleur_produit_id')
    elif imposes.get('onduleur_kw'):
        resolution = _resolu_ou_409(
            rc.resoudre_onduleur(
                company, entrees, kw=imposes['onduleur_kw'],
                phase=imposes.get('onduleur_phase') or None,
                famille=None if hors_reseau else famille,
                hors_reseau=hors_reseau),
            champ_id='onduleur_produit_id', champ_taille='onduleur_kw',
            company=company)
        entree = resolution.candidats[0]
        for message in resolution.alertes:
            _alerter(alertes, 'marque', message, 'onduleur_kw')
    else:
        return None
    if entree.phase == rc.PHASE_TRI and phase_lead == rc.PHASE_MONO:
        raise AutoDevisError(
            'Le lead déclare un raccordement MONOPHASÉ : « %s » est triphasé et '
            'ne peut pas y être raccordé. Corrigez le raccordement du lead ou '
            'choisissez un onduleur monophasé.' % entree.produit.nom,
            field='raccordement')
    if entree.phase == rc.PHASE_TRI and raccordement_vide:
        _alerter(alertes, 'raccordement_suppose', (
            'Raccordement non renseigné sur le lead : onduleur triphasé '
            "« %s » retenu — vérifiez que le client a bien le triphasé "
            '(champ raccordement).' % entree.produit.nom), 'raccordement')
    if entree.phase == rc.PHASE_MONO and phase_lead == rc.PHASE_TRI:
        _alerter(alertes, 'raccordement', (
            'Raccordement triphasé déclaré : onduleur monophasé « %s » imposé '
            '— à valider avec le client.' % entree.produit.nom), 'raccordement')
    return entree


def _batterie(imposes, entrees, *, company, onduleur, alertes):
    """``(Entree, nombre)`` de la batterie imposée, ou ``(None, 0)``."""
    from apps.ventes.domain import resolution_catalogue as rc
    from apps.ventes.domain.catalogue import (
        _batterie_compatible, _plage_batterie_de_l_onduleur)
    if imposes.get('batterie_produit_id'):
        resolution = _resolu_ou_409(
            rc.resoudre_par_id(company, rc.GENRE_BATTERIE,
                               imposes['batterie_produit_id'], entrees=entrees),
            champ_id='batterie_produit_id', champ_taille=None, company=company)
        entree = resolution.candidats[0]
        if onduleur is not None and not _batterie_compatible(
                entree.produit, _plage_batterie_de_l_onduleur(onduleur)):
            raise AutoDevisError(
                '« %s » est hors de la fenêtre de tension batterie de « %s » : '
                'choisissez une batterie compatible.'
                % (entree.produit.nom, onduleur.nom), field='batterie_produit_id')
        for message in resolution.alertes:
            _alerter(alertes, 'produit_designe', message, 'batterie_produit_id')
        return entree, 1
    if imposes.get('batterie_kwh'):
        resolution = _resolu_ou_409(
            rc.resoudre_batterie(company, entrees, kwh=imposes['batterie_kwh'],
                                 onduleur=onduleur),
            champ_id='batterie_produit_id', champ_taille='batterie_kwh',
            company=company)
        for message in resolution.alertes:
            _alerter(alertes, 'marque', message, 'batterie_kwh')
        return resolution.candidats[0], resolution.nombre
    return None, 0


def _panneau(imposes, entrees, *, company, alertes):
    from apps.ventes.domain import resolution_catalogue as rc
    if imposes.get('panneau_produit_id'):
        resolution = _resolu_ou_409(
            rc.resoudre_par_id(company, rc.GENRE_PANNEAU,
                               imposes['panneau_produit_id'], entrees=entrees),
            champ_id='panneau_produit_id', champ_taille=None, company=company)
    else:
        resolution = _resolu_ou_409(
            rc.resoudre_panneau(company, entrees),
            champ_id='panneau_produit_id', champ_taille='panneau_produit_id',
            company=company)
    for message in resolution.alertes:
        _alerter(alertes, 'panneau_suppose', message, 'panneau_produit_id')
    return resolution.candidats[0]


#: Les rôles dont la marque épinglée ne s'applique pas en composition imposée :
#: le panneau (fiche désignée), les onduleurs (imposé, ou contrôlé par
#: ``verifier`` sur la famille vendue — l'autre famille n'est pas vendue).
ROLES_HORS_EPINGLE = frozenset({'panneau', 'onduleur_reseau',
                                'onduleur_hybride', 'onduleur_offgrid'})


def _refuser_marques_manquantes(lignes, imposition):
    """Même refus que le devis automatique ordinaire (``marques``) pour une
    marque épinglée absente sur un rôle NON imposé (structure, câbles,
    forfaits…, batterie quand elle n'est pas imposée) : jamais un devis qui
    perd une ligne en silence."""
    from apps.ventes.domain.catalogue import _libelle_role
    hors = ROLES_HORS_EPINGLE | (
        {'batterie'} if imposition.batterie_imposee is not None else set())
    manquantes = [m for m in (getattr(lignes, 'marques_manquantes', ()) or ())
                  if m.get('role') not in hors]
    if manquantes:
        raise AutoDevisError(
            'Marque épinglée introuvable au stock : %s. Ajoutez le produit ou '
            'changez la marque dans Paramètres → Gammes.' % ', '.join(
                '%s (%s)' % (m.get('marque'), _libelle_role(m.get('role')))
                for m in manquantes), field='marques')


def _controle_a_blanc(company, *, lead, imposition, hors_reseau, phase_lead,
                      alertes):
    """La composition À BLANC (sans écriture) de l'imposition : le couple
    panneau/onduleur et la fenêtre de la batterie sont jugés sur les produits
    RÉELLEMENT composés — jamais un remplacement silencieux. ADEV156 : le
    couple est jugé au froid du site du lead (D-ACAL-80), comme le devis."""
    from apps.ventes.compatibilites import (
        STATUT_INCOMPATIBLE, avertissement_panneau_onduleur, froid_du_lead,
        verdict_panneau_onduleur)
    from apps.ventes.domain.catalogue import (
        _batterie_compatible, _plage_batterie_de_l_onduleur)
    from apps.ventes.domain.etape_composer import (
        COMPOSITION_AVEC, COMPOSITION_SANS, IntentionComposition, composer)
    nb = imposition.nb_panneaux
    froid = froid_du_lead(lead)
    lignes = composer(IntentionComposition(
        company=company, kwc=nb * imposition.panel_watt / 1000.0,
        nb_panneaux=nb, panel_watt=imposition.panel_watt,
        scenario=(COMPOSITION_AVEC if imposition.scenario == 'avec'
                  else COMPOSITION_SANS),
        phase=phase_lead, hors_reseau=hors_reseau, avertissements=[],
        modeles=[{'produit_id': imposition.panneau_id,
                  'watt': imposition.panel_watt, 'count': nb}],
        onduleur_impose=imposition.onduleur_impose,
        batterie_imposee=imposition.batterie_imposee, froid=froid))
    roles = list(getattr(lignes, 'roles', ()) or ())
    par_role = {}
    for index, ligne in enumerate(lignes):
        role = roles[index] if index < len(roles) else ''
        par_role.setdefault(role, ligne.produit)
    panneau = par_role.get('panneau')
    onduleur = next((par_role[r] for r in (
        'onduleur_offgrid', 'onduleur_hybride', 'onduleur_reseau')
        if r in par_role), None)
    batterie = par_role.get('batterie')
    if panneau is not None and onduleur is not None:
        verdict = verdict_panneau_onduleur(panneau, onduleur, froid=froid)
        if verdict['statut'] == STATUT_INCOMPATIBLE:
            raise AutoDevisError(
                avertissement_panneau_onduleur(panneau, onduleur, verdict)
                + ' Aucun panneau n\'est remplacé en composition imposée : '
                'choisissez un autre panneau ou un autre onduleur.',
                field='panneau_produit_id')
    if batterie is not None and onduleur is not None and not _batterie_compatible(
            batterie, _plage_batterie_de_l_onduleur(onduleur)):
        raise AutoDevisError(
            '« %s » est hors de la fenêtre de tension batterie de « %s » : '
            'choisissez une batterie compatible.' % (batterie.nom, onduleur.nom),
            field='batterie_kwh')
    _refuser_marques_manquantes(lignes, imposition)
    for message in getattr(lignes, 'avertissements_composition', ()) or ():
        _alerter(alertes, 'composition', str(message))
    if onduleur is not None:
        from apps.ventes.domain.catalogue import _parse_kw
        kw_ac = _parse_kw(getattr(onduleur, 'nom', ''))
        kwc = nb * imposition.panel_watt / 1000.0
        if kw_ac and not (RATIO_DC_AC[0] <= kwc / kw_ac <= RATIO_DC_AC[1]):
            _alerter(alertes, 'ratio_dc_ac', (
                'Rapport DC/AC de %s (%s kWc de panneaux pour un onduleur de %s '
                'kW), hors de la plage habituelle 0,8-1,4 : à vérifier.'
                % (_fmt(round(kwc / kw_ac, 2)), _fmt(round(kwc, 2)),
                   _fmt(kw_ac))))
    return lignes


def preparer_imposition(*, company, lead, imposes, scenario=None,
                        target_kwc=None, user=None, hors_reseau=False):
    """Résout et contrôle une composition imposée SANS rien écrire : rend
    ``(Imposition, alertes, phase du lead, hors réseau)``. Partagée par la
    création (:func:`build_devis_auto_impose`) et le dry-run
    ``POST devis/composition/`` (règle U3 : l'aperçu et la création composent
    le même kit). Sans lead (dry-run), ``hors_reseau`` vient de l'appelant et
    aucune phase n'est déclarée."""
    from django.utils import timezone

    from apps.ventes.domain import resolution_catalogue as rc
    from apps.ventes.domain.taille import phase_et_isolement_du_lead

    alertes = []
    demande = (scenario or '').strip().lower()
    marche = _refuser_modes(imposes, target_kwc=target_kwc, scenario=demande,
                            lead=lead)
    if lead is not None and not marche:
        _alerter(alertes, 'type_installation_suppose', (
            "Type d'installation non renseigné sur le lead : résidentiel "
            'supposé (champ type_installation).'), 'type_installation')
    if lead is not None:
        phase_lead, hors_reseau = phase_et_isolement_du_lead(lead)
    else:
        phase_lead, hors_reseau = None, bool(hors_reseau)
    raccordement = (getattr(lead, 'raccordement', '') or '').strip().lower()
    raccordement_vide = lead is not None and raccordement in ('', 'inconnu')
    batterie_demandee = bool(imposes.get('batterie_produit_id')
                             or imposes.get('batterie_kwh'))
    avec = batterie_demandee or demande == 'avec' or hors_reseau
    famille = (rc.FAMILLE_OFFGRID if hors_reseau
               else (rc.FAMILLE_HYBRIDE if avec else rc.FAMILLE_RESEAU))
    if hors_reseau and demande == 'sans':
        raise AutoDevisError(
            'Site sans réseau (raccordement « aucun ») : la batterie est '
            'obligatoire, le scénario « sans » ne s\'applique pas.',
            field='scenario')

    entrees = rc.vivier(company)
    onduleur = _onduleur(imposes, entrees, company=company, famille=famille,
                         hors_reseau=hors_reseau, phase_lead=phase_lead,
                         raccordement_vide=raccordement_vide, alertes=alertes)
    batterie, nombre = _batterie(
        imposes, entrees, company=company,
        onduleur=onduleur.produit if onduleur is not None else None,
        alertes=alertes)
    panneau = _panneau(imposes, entrees, company=company, alertes=alertes)
    nb = int(imposes['nb_panneaux'])
    watt = float(panneau.wc or 0) or 0.0
    if watt <= 0:
        raise AutoDevisError(
            'Puissance du panneau « %s » illisible (ni au nom, ni sur sa fiche) '
            ': choisissez un autre panneau.' % panneau.produit.nom,
            field='panneau_produit_id')
    if nb > PANNEAUX_A_SIGNALER:
        _alerter(alertes, 'panneaux_nombreux', (
            '%d panneaux imposés : au-delà de %d, vérifiez la surface de toit '
            'et recommandez une visite technique.' % (nb, PANNEAUX_A_SIGNALER)))

    resume = '%d panneaux' % nb
    if onduleur is not None:
        resume += ', onduleur %s%s%s' % (
            '%s ' % {'hybride': 'hybride', 'reseau': 'réseau',
                     'offgrid': 'hors réseau'}.get(onduleur.famille, ''),
            '%s kW' % _fmt(onduleur.kw) if onduleur.kw else onduleur.produit.nom,
            ' %s' % ('triphasé' if onduleur.phase == rc.PHASE_TRI
                     else 'monophasé'))
    if batterie is not None:
        resume += ', batterie %s kWh' % _fmt(float(batterie.kwh or 0) * nombre) \
            if batterie.kwh else ', batterie %s' % batterie.produit.nom
    _alerter(alertes, 'composition_imposee', (
        'Composition imposée : %s — la facture du lead n\'a pas servi au '
        'dimensionnement.' % resume))

    imposition = Imposition(
        nb_panneaux=nb, panel_watt=watt, panneau_id=panneau.produit.pk,
        scenario='avec' if avec else 'sans',
        onduleur_impose=onduleur.produit.pk if onduleur is not None else None,
        batterie_imposee=({'produit_id': batterie.produit.pk, 'nombre': nombre}
                          if batterie is not None else None),
        marqueur={
            'demande': {cle: imposes[cle] for cle in sorted(imposes)},
            'produits': {
                'panneau': panneau.produit.pk,
                'onduleur': onduleur.produit.pk if onduleur is not None else None,
                'batterie': batterie.produit.pk if batterie is not None else None,
                'batterie_nombre': nombre if batterie is not None else 0,
            },
            'par': getattr(user, 'pk', None),
            'le': timezone.now().isoformat(),
        })
    _controle_a_blanc(company, lead=lead, imposition=imposition,
                      hors_reseau=hors_reseau, phase_lead=phase_lead,
                      alertes=alertes)
    return imposition, alertes, phase_lead, hors_reseau


def build_devis_auto_impose(*, lead, user, company, imposes, taux_tva=None,
                            remise_globale=Decimal('0'), scenario=None,
                            target_kwc=None, etude_extra=None,
                            journal_auto=None):
    """Le devis automatique RÉSIDENTIEL à composition IMPOSÉE.

    ``imposes`` — :func:`imposition_du_corps` du corps validé. Lève
    ``AutoDevisError`` (409 nommant le champ) ou :class:`ChoixRequis` (409
    ``choix``). Rend le ``Devis`` brouillon créé, marqueur posé."""
    from apps.ventes.domain.creation_auto_residentiel import (
        _build_devis_auto_residentiel)

    imposition, alertes, _phase, _isole = preparer_imposition(
        company=company, lead=lead, imposes=imposes, scenario=scenario,
        target_kwc=target_kwc, user=user)
    if isinstance(journal_auto, dict):
        for alerte in alertes:
            _alerter(journal_auto.setdefault('alertes', []), alerte['code'],
                     alerte['message'], alerte.get('champ'))
    from apps.ventes.domain.creation_auto import marquer_rapide  # ACAL1004
    return marquer_rapide(_build_devis_auto_residentiel(
        lead=lead, user=user, company=company, taux_tva=taux_tva,
        remise_globale=remise_globale, scenario=imposition.scenario,
        etude_extra=etude_extra, journal_auto=journal_auto,
        imposition=imposition), journal_auto)
