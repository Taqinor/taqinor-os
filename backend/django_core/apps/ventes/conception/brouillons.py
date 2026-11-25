"""ADEV147 / ADEV148 (D-ACAL-97, réponse Q2 du fondateur, 23/11/2026) — les
BROUILLONS d'un lead nés d'une version de conception plus ancienne.

* Un brouillon que personne n'a retouché SUIT la nouvelle conception
  (:func:`suivre_la_conception`, en tâche après chaque version rangée) :
  recomposé comme le devis automatique né d'elle — résidentiel par la décision
  qui lit la recommandation rangée, commercial / industriel / agricole par LA
  décision du devis automatique (``decider_ci`` / ``decider_agricole``, blocs
  de la version copiés) —, lignes, études et totaux ; son pointeur porté à la
  nouvelle version, une ligne d'historique qui nomme ce qui a changé.
* Un brouillon RETOUCHÉ à la main (:func:`est_retouche` : surcharge, quantité
  ou prix tapés, remise de ligne, ligne ajoutée, section ou note — tout ce
  qu'une recomposition effacerait) garde ses valeurs ; il est listé
  (``brouillons_a_mettre_a_jour``) et se réaligne SUR DEMANDE
  (:func:`appliquer_a_la_demande`, route ``mettre-a-jour-conception``) par
  « Reprendre les valeurs du lead » (mode RÉCONCILIER). Hors résidentiel ce
  mode ne redimensionne pas : le pointeur n'avance que si la taille du
  brouillon est celle de la conception (sinon la mise à jour reste PROPOSÉE).

Chaque brouillon est réaligné sous UNE transaction, devis VERROUILLÉ puis RELU :
devenu envoyé, inactif (ou retouché, pour le suivi) entre la sélection et
l'écriture ⇒ rien n'est écrit (tâche) / 409 (route). Jamais un devis envoyé,
accepté, refusé ou expiré ; aucun statut n'est écrit (règle #4). Seuls les devis
nés d'une conception (``Devis.conception_source``, ADEV143) sont concernés.
"""
import logging

logger = logging.getLogger(__name__)

MOTIF_RETOUCHE = 'retouché à la main'
MESSAGE_PARTI = 'Ce devis est parti : réviser le devis pour suivre la conception.'


def _lignes_retouchees():
    """Relecture E4 m2 — une ligne que la recomposition ne reproduirait pas :
    quantité ou prix tapés, remise de ligne, ligne ajoutée à la main
    (``ligne_composee=False``), section ou note."""
    from django.db.models import Q
    return (Q(quantite_manuelle=True) | Q(prix_manuel=True) | Q(ligne_composee=False)
            | Q(type_ligne__in=('section', 'note')) | Q(remise__gt=0) | Q(remise__lt=0))


def _brouillons_nes_avant(company_id, lead_id, version):
    """Les brouillons actifs du lead nés d'une version < ``version``, annotés
    ``_lignes_manuelles`` (une ligne retouchée, :func:`_lignes_retouchees`)."""
    from django.db.models import Exists, OuterRef

    from apps.ventes.models import Devis, LigneDevis

    manuelles = LigneDevis.objects.filter(devis=OuterRef('pk')).filter(_lignes_retouchees())
    return (Devis.objects.filter(company_id=company_id, lead_id=lead_id, statut=Devis.Statut.BROUILLON,
                                 is_active=True, conception_source__version__lt=version)
            .annotate(_lignes_manuelles=Exists(manuelles)).order_by('pk'))


def est_retouche(devis):
    """« Retouché à la main » (règle (4) de la consolidation C4) : une
    surcharge déclarée (``Devis.overrides`` non vide) ou une ligne retouchée
    (:func:`_lignes_retouchees`). Seule définition."""
    if devis.overrides:
        return True
    manuelles = getattr(devis, '_lignes_manuelles', None)
    if manuelles is None:
        manuelles = devis.lignes.filter(_lignes_retouchees()).exists()
    return bool(manuelles)


def brouillons_a_mettre_a_jour(company_id, lead_id, version):
    """ADEV148 — ``[{devis, reference, motif}]`` du contrat : les brouillons
    RETOUCHÉS nés d'une version plus ancienne que ``version`` (numéro)."""
    return [{'devis': devis.pk, 'reference': devis.reference, 'motif': MOTIF_RETOUCHE}
            for devis in _brouillons_nes_avant(company_id, lead_id, version) if est_retouche(devis)]


def _comptes(devis):
    """``{option: panneaux}`` (« '' » = commune) — classement du moteur PDF."""
    from apps.ventes.domain.catalogue import classer_produit

    par_option = {}
    for ligne in devis.lignes.filter(type_ligne='produit', optionnelle=False).select_related('produit'):
        if classer_produit(getattr(ligne.produit, 'nom', '') or ligne.designation) == 'panneau':
            option = ligne.variante or ''
            par_option[option] = par_option.get(option, 0) + int(ligne.quantite)
    return par_option


def _panneaux(devis):
    """Les panneaux du devis, PAR OPTION quand il en porte deux (« sans 11 / avec 16 »)."""
    par_option = _comptes(devis)
    if set(par_option) <= {''}:
        return str(par_option.get('', 0))
    return ' / '.join('%s %d' % (option or 'commun', nombre) for option, nombre in sorted(par_option.items()))


def _taille_de_la_conception(devis, version):
    """Relecture E4 M3 — les panneaux du brouillon, option par option, sont-ils
    ceux de la conception ``version`` ?"""
    comptes = _comptes(devis)
    attendus = {option: (valeurs.get('nb_panneaux') or {}).get('valeur')
                for option, valeurs in (version.valeurs or {}).items()}
    return all(comptes.get(option, comptes.get('')) == nombre for option, nombre in attendus.items()
               if nombre is not None)


def _ce_qui_a_change(version):
    """Les entrées nommées par leur libellé (jamais leurs valeurs : une ligne
    du devis survit à l'effacement du lead), sinon le motif de l'origine. Relecture E5
    (c) — accord en français simple, sans « (s) » : « champ modifié : Facture hiver »,
    « champs modifiés : Facture hiver, Ville » (le genre des libellés n'est pas connu)."""
    from apps.ventes.conception.service import MOTIFS_ORIGINE, libelle_champ

    champs = [c.get('champ') for c in (version.declencheur or {}).get('champs') or []]
    if champs:
        libelles = ', '.join(libelle_champ(version.lead, c) for c in champs)
        return ('champ modifié : %s' if len(champs) == 1 else 'champs modifiés : %s') % libelles
    return MOTIFS_ORIGINE.get((version.declencheur or {}).get('origine'), 'conception recalculée')


def _verrouiller(devis, version, *, a_la_demande):
    """Relecture E4 M1 — le devis VERROUILLÉ et relu, ou ``None`` s'il ne peut
    plus suivre : parti ou inactif (route : ``MiseAJourRefusee``), déjà né de
    ``version`` ou plus récente, ou retouché depuis la sélection (suivi)."""
    from apps.ventes.models import Devis

    verrou = Devis.objects.select_for_update().filter(pk=devis.pk, company_id=devis.company_id).first()
    if verrou is None or verrou.statut != Devis.Statut.BROUILLON or not verrou.is_active:
        if a_la_demande:
            raise MiseAJourRefusee(MESSAGE_PARTI)
        return None
    if (verrou.conception_source or {}).get('version', 0) >= version.version:
        return None
    if not a_la_demande and est_retouche(verrou):
        return None
    return verrou


def _realigner(devis, version, user=None, *, a_la_demande=False):
    """Réaligne UN brouillon sur ``version`` sous une transaction (devis
    verrouillé, relu) : intact ⇒ recomposé comme le devis automatique ;
    retouché ⇒ ``reappliquer_lead`` (mode RÉCONCILIER). Rend ``None`` quand
    rien n'est écrit, sinon ``(suivi, avertissements)`` — ``suivi`` faux quand
    le pointeur reste (taille gardée hors résidentiel)."""
    from django.db import transaction

    from apps.ventes import activity
    from apps.ventes.domain.pipeline import pointeur_de_conception, reappliquer_lead
    from apps.ventes.models import Devis

    with transaction.atomic():
        verrou = _verrouiller(devis, version, a_la_demande=a_la_demande)
        if verrou is None:
            return None
        avant, residentiel = _panneaux(verrou), (verrou.mode_installation or 'residentiel') == 'residentiel'
        avertissements, suit = [], True
        if not est_retouche(verrou):
            recomposer = _recomposer_residentiel if residentiel else _recomposer_par_la_decision
            avertissements = recomposer(verrou, version, user)
        else:  # quantités tapées gardées (mode réconcilier)
            avertissements = list(reappliquer_lead(verrou, user=user, company=verrou.company)
                                  .get('avertissements') or [])
            suit = residentiel or _taille_de_la_conception(verrou, version)
        if suit:
            Devis.objects.filter(pk=verrou.pk, statut=Devis.Statut.BROUILLON).update(
                conception_source=pointeur_de_conception(version))
        verrou.refresh_from_db()
        activity.log_devis_note(verrou, user, 'Mis à jour : panneaux %s → %s (%s)' % (
            avant, _panneaux(verrou), _ce_qui_a_change(version)))
    devis.refresh_from_db()
    return suit, avertissements


def _recomposer_residentiel(devis, version, user):
    """Un brouillon résidentiel INTACT recomposé comme le devis automatique né
    de ``version`` (ADEV142) : la décision lit la recommandation rangée
    (aucun moteur horaire rappelé), le pipeline réécrit ses lignes, ses études
    et ses totaux. Rend les avertissements de la composition."""
    from apps.ventes.conception.decisions import decider_taille_residentielle, verifier_composition_residentielle
    from apps.ventes.domain import creation_auto_residentiel as R
    from apps.ventes.domain.pipeline import appliquer

    lead, company = devis.lead, devis.company
    decision = decider_taille_residentielle(
        lead=lead, company=company, scenario=None, imposition=None, plafond_toit=None,
        dimensionner=R.dimensionneur_de_la_conception(version))
    structure_produit_id, structure_type = verifier_composition_residentielle(
        decision, lead=lead, company=company, taux_tva=devis.taux_tva, imposition=None)
    intention = R.intention_auto_residentielle(
        decision, lead=lead, company=company, user=user, taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale, structure_produit_id=structure_produit_id,
        structure_type=structure_type)
    return list(appliquer(devis, intention).get('avertissements') or [])


def _recomposer_par_la_decision(devis, version, user):
    """Relecture E4 M3 — un brouillon commercial / industriel / agricole INTACT
    recomposé comme le devis automatique né de ``version`` (ADEV142, forme
    faisable) : UNE décision (``decider_ci`` / ``decider_agricole``) compose
    les lignes au prix du jour, l'étude de création est posée sous les blocs
    rangés de la version, puis l'écrivain (``MODE_ECRIRE``) et les études
    (``MODE_RAFRAICHIR``) du pipeline, comme ``_ecrire_devis_auto_par_pipeline``."""
    import contextlib

    from apps.ventes.conception.decisions import decider_agricole, decider_ci, etude_params_creation_ci
    from apps.ventes.domain.creation_auto import (
        alertes_journal_ci, blocs_et_creation, marquer_rapide, specs_des_lignes_moteur)
    from apps.ventes.domain.creation_auto_agricole import alertes_journal_agricole, etude_params_creation_agricole
    from apps.ventes.domain.pipeline import MODE_ECRIRE, MODE_RAFRAICHIR, ORIGINE_AUTO, IntentionDevis, appliquer
    from apps.ventes.domain.pompage import etude_precalculee

    lead, company, marche = devis.lead, devis.company, devis.mode_installation
    journal = 'journal_auto' in (devis.etude_params or {})
    if marche == 'agricole':
        decision = decider_agricole(lead=lead, company=company)
        lignes, entrees = decision.lignes, etude_params_creation_agricole(decision, lead)
        contexte = etude_precalculee(lead, decision.sortie)
    else:
        etude, lignes, scenario = decider_ci(lead=lead, company=company)
        entrees, contexte = etude_params_creation_ci(etude, mode=marche, scenario=scenario), contextlib.nullcontext()
    _poser_l_etude_de_creation(devis, blocs_et_creation(version, entrees))
    commun = {'origine': ORIGINE_AUTO, 'company': company, 'user': user, 'lead': lead,
              'mode_installation': marche}
    with contexte:
        appliquer(devis, IntentionDevis(mode=MODE_ECRIRE, composition=specs_des_lignes_moteur(lignes), **commun))
        appliquer(devis, IntentionDevis(mode=MODE_RAFRAICHIR, **commun))
    devis.refresh_from_db()
    alertes = (alertes_journal_agricole(decision.sortie, decision.omises) if marche == 'agricole'
               else alertes_journal_ci(etude, devis))
    marquer_rapide(devis, {'alertes': alertes} if journal else None)
    return []


def _poser_l_etude_de_creation(devis, etude):
    """L'étude du brouillon devient ``etude`` (celle que la création poserait)
    par L'écrivain unique (``etude_schema.ecrire``), chaque clé réservée écrite
    par SON propriétaire déclaré ; les clés de l'ancienne version absentes de
    ``etude`` sont retirées (``None``, règle Z2) — jamais une affectation en bloc."""
    from apps.ventes.domain import etude_schema as es

    cles = dict({cle: None for cle in (devis.etude_params or {}) if cle not in etude}, **etude)
    par_proprietaire = {}
    for cle, valeur in cles.items():
        regle = es.SCHEMA.get(cle) or {}
        reservee = regle.get('nature') == es.DERIVEE or regle.get('exclusif')
        par_proprietaire.setdefault(regle.get('proprietaire') if reservee else None, {})[cle] = valeur
    for proprietaire, lot in par_proprietaire.items():
        es.ecrire(devis, proprietaire=proprietaire, **lot)


def suivre_la_conception(version):
    """ADEV147 — la conception ``version`` vient d'être rangée : chaque
    brouillon NON retouché né d'une version plus ancienne la suit. Rend les
    ids réalignés. Un brouillon en échec est journalisé, jamais propagé."""
    if version is None or not version.lead_id or version.etat != 'complet':
        return []
    suivis = []
    for devis in _brouillons_nes_avant(version.company_id, version.lead_id, version.version):
        if est_retouche(devis):
            continue
        try:
            if (_realigner(devis, version) or (False,))[0]:
                suivis.append(devis.pk)
        except Exception:  # noqa: BLE001 — un brouillon en échec n'arrête pas les autres (D-ENF22-BLE001)
            logger.warning('ADEV147 : brouillon %s non réaligné sur la conception #%s',
                           devis.reference, version.pk, exc_info=True)
    return suivis


class MiseAJourRefusee(ValueError):
    """ADEV148 — le devis n'est pas un brouillon actif (409 « Réviser le devis »)."""


def appliquer_a_la_demande(devis, user):
    """ADEV148 — « Mettre à jour » : le brouillon (même retouché) est
    réaligné sur la conception COURANTE complète de son lead. Les quantités
    tapées restent (``_quantite_verrouillee`` du mode réconcilier) et sont
    NOMMÉES. Rend ``{devis_id, appliquees, non_appliquees}`` ; un brouillon déjà
    né de la version courante n'est pas réécrit (``appliquees`` vide) ; hors
    résidentiel, une taille gardée est nommée et le pointeur ne bouge pas."""
    from apps.ventes.models import ConceptionLead, Devis

    if devis.statut != Devis.Statut.BROUILLON or not devis.is_active:
        raise MiseAJourRefusee(MESSAGE_PARTI)
    version = ConceptionLead.objects.filter(company_id=devis.company_id, lead_id=devis.lead_id,
                                            courante=True, etat=ConceptionLead.Etat.COMPLET).first()
    if version is None or (devis.conception_source or {}).get('version') == version.version:
        return {'devis_id': devis.pk, 'appliquees': [], 'non_appliquees': []}
    realigne = _realigner(devis, version, user=user, a_la_demande=True)
    if realigne is None:  # né de cette version entre-temps : rien de plus
        return {'devis_id': devis.pk, 'appliquees': [], 'non_appliquees': []}
    suit, avertissements = realigne
    verrouillees = [{'champ': 'quantite', 'raison': ligne.designation + ' : quantité saisie à la main, gardée'}
                    for ligne in devis.lignes.filter(quantite_manuelle=True).order_by('ordre', 'pk')]
    if not suit:
        verrouillees.append({'champ': 'taille', 'raison': (
            'Taille gardée : ce devis porte %s panneaux, la conception v%d en propose %s.' % (
                _panneaux(devis), version.version, ' / '.join(
                    str((v.get('nb_panneaux') or {}).get('valeur')) for v in (version.valeurs or {}).values())))})
    return {'devis_id': devis.pk, 'appliquees': ['conception_v%d' % version.version] if suit else [],
            'non_appliquees': verrouillees + [{'champ': 'composition', 'raison': str(a)} for a in avertissements]}
