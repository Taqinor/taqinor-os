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
import re

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


#: T4-X6-012 — « enregistré depuis l'écran avec des lignes changées », rangé DANS le
#: pointeur ``Devis.conception_source`` (jamais servi) : un nombre de panneaux recomposé
#: à l'écran ne pose aucun verrou de ligne, et le suivi effaçait la retouche du vendeur.
CLE_RETOUCHE_ECRAN = 'retouche_ecran'


def empreinte_des_lignes(devis):
    """Ce que le vendeur voit d'une ligne (produit, désignation, quantité, prix, remise,
    option) : deux empreintes égales = aucune retouche des lignes."""
    return list(devis.lignes.order_by('ordre', 'pk').values_list(
        'type_ligne', 'produit_id', 'designation', 'quantite', 'prix_unitaire', 'remise', 'variante',
        'optionnelle'))


def marquer_retouche_ecran(devis, avant):
    """T4-X6-012 — un BROUILLON né d'une conception, enregistré depuis l'écran avec des
    lignes différentes de ``avant`` (:func:`empreinte_des_lignes`), devient « retouché » :
    il ne suit plus seul la conception du lead, « Mettre à jour » lui est proposé. Appelé
    sous la transaction de l'écriture, AVANT tout suivi. Rend vrai quand il marque.

    Le statut ET le pointeur sont RELUS sous le verrou de la ligne (``select_for_update``) :
    un devis parti entre la lecture de l'instance et ce geste n'est ni marqué ni dit marqué,
    et un pointeur changé entre-temps par un suivi est gardé (seule la clé est ajoutée)."""
    from django.db import transaction

    from apps.ventes.models import Devis

    if not devis.conception_source or empreinte_des_lignes(devis) == avant:
        return False
    with transaction.atomic():
        # Le pointeur AUSSI est relu sous le verrou : un suivi de la conception
        # committé entre la lecture de l'instance et ce geste n'est jamais écrasé
        # par l'ancien pointeur.
        ligne = (Devis.objects.select_for_update().filter(pk=devis.pk)
                 .values('statut', 'conception_source').first())
        if ligne is None or ligne['statut'] != Devis.Statut.BROUILLON:
            return False
        source = ligne['conception_source']
        if not source or source.get(CLE_RETOUCHE_ECRAN):
            return False
        marque = dict(source, **{CLE_RETOUCHE_ECRAN: True})
        Devis.objects.filter(pk=devis.pk).update(conception_source=marque)
    devis.conception_source = marque
    return True


def est_retouche(devis):
    """« Retouché à la main » (règle (4) de la consolidation C4) : une
    surcharge déclarée (``Devis.overrides`` non vide), un enregistrement de l'écran qui
    a changé les lignes (:func:`marquer_retouche_ecran`) ou une ligne retouchée
    (:func:`_lignes_retouchees`). Seule définition."""
    if devis.overrides or (devis.conception_source or {}).get(CLE_RETOUCHE_ECRAN):
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


#: AGEN12 (constat en direct) — « Mettre à jour » emprunte le chemin réconcilier
#: (``domain/resynchronisation.py``), qui parle du CALEPINAGE ; sur ce geste la cause
#: est la conception du LEAD : ses deux phrases sont redites ici (le chemin réconcilier,
#: quand un calepinage est la cause, garde les siennes).
_PANNEAUX_DU_CALEPINAGE = re.compile(r'^La conception 3D porte le devis de (\d+) à (\d+) panneaux\.$')
_ECART_DU_CALEPINAGE = 'Écart de calepinage non entièrement appliqué'


def _dit_pour_la_conception(avertissement, version):
    """La phrase que lit le vendeur sur « Mettre à jour » : elle nomme la conception
    du lead et ce qui a changé (:func:`_ce_qui_a_change`), jamais un calepinage."""
    texte = str(avertissement)
    panneaux = _PANNEAUX_DU_CALEPINAGE.match(texte)
    if panneaux:
        return 'La conception du lead porte le devis de %s à %s panneaux (%s).' % (
            panneaux.group(1), panneaux.group(2), _ce_qui_a_change(version))
    if texte.startswith(_ECART_DU_CALEPINAGE):
        return ("La conception du lead n'a pas pu être entièrement appliquée (%s) : corrigez la cause "
                'ci-dessus puis cliquez de nouveau « Mettre à jour ».' % _ce_qui_a_change(version))
    return texte


#: Relecture E6 M5 — les valeurs d'une option qui décident des LIGNES du devis.
VALEURS_COMPOSEES = ('nb_panneaux', 'puissance_kwc', 'module_produit', 'onduleurs', 'batterie_produit')


def _contenu_compose(version):
    """Ce qu'un devis recevrait de ``version`` : par option, la taille et le matériel
    (:data:`VALEURS_COMPOSEES`, valeurs seules), et les blocs que le devis copie
    (``creation_auto.blocs_a_apporter`` : sans la provenance horodatée), le marqueur
    d'imposition réduit à son contenu (jamais son auteur ni son heure)."""
    from apps.ventes.domain.composition_imposee import CLE_MARQUEUR
    from apps.ventes.domain.creation_auto import blocs_a_apporter

    blocs = dict(blocs_a_apporter(version))
    if isinstance(blocs.get(CLE_MARQUEUR), dict):
        blocs[CLE_MARQUEUR] = {cle: blocs[CLE_MARQUEUR].get(cle) for cle in ('demande', 'produits')}
    from apps.ventes.conception.societe import MOTIFS

    tailles = {option: {cle: (valeurs.get(cle) or {}).get('valeur') for cle in VALEURS_COMPOSEES}
               for option, valeurs in (version.valeurs or {}).items()}
    # Les prix et la TVA que les lignes recevraient : le catalogue de vente et les taux rangés.
    prix = {cle: ((version.entrees_utilisees or {}).get(cle) or {}).get('valeur')
            for cle in MOTIFS}
    return {'valeurs': tailles, 'blocs': blocs, 'prix': prix}


def _meme_contenu(devis, version):
    """Relecture E6 M5 — la version dont le brouillon est né (``conception_source``)
    porte-t-elle le même :func:`_contenu_compose` que ``version`` ? Une source illisible
    ⇒ ``False`` (le brouillon est recomposé, comme avant)."""
    from apps.ventes.models import ConceptionLead

    nee_de = (devis.conception_source or {}).get('version')
    source = (ConceptionLead.objects.filter(company_id=devis.company_id, lead_id=devis.lead_id, version=nee_de)
              .only('valeurs', 'blocs', 'entrees_utilisees').first() if nee_de is not None else None)
    return source is not None and _contenu_compose(source) == _contenu_compose(version)


def _imposition_de_la_version(version, lead, company):
    """Relecture E6 M5 — l'imposition avec laquelle ``version`` a été calculée (matériel
    désigné, pose ajustée : le marqueur rangé dans ses blocs), refaite par la MÊME
    préparation que le moteur (``composition_imposee.preparer_imposition``) ; ``None``
    sans imposition. Une option unique rangée = le scénario imposé."""
    from apps.ventes.domain.composition_imposee import CLE_MARQUEUR, preparer_imposition

    demande = ((version.blocs or {}).get(CLE_MARQUEUR) or {}).get('demande')
    if not demande:
        return None
    options = list(version.valeurs or {})
    scenario = options[0] if len(options) == 1 else None
    return preparer_imposition(company=company, lead=lead, imposes=dict(demande), scenario=scenario)[0]


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
        if not est_retouche(verrou) and _meme_contenu(verrou, version):
            # Relecture E6 M5 — rien de ce que le devis recevrait n'a changé (saut de
            # VERSION_MOTEUR, filet de lecture…) : seul le pointeur avance, sans historique.
            Devis.objects.filter(pk=verrou.pk, statut=Devis.Statut.BROUILLON).update(
                conception_source=pointeur_de_conception(version))
            devis.refresh_from_db()
            return True, []
        if not est_retouche(verrou):
            recomposer = _recomposer_residentiel if residentiel else _recomposer_par_la_decision
            avertissements = recomposer(verrou, version, user)
        else:  # quantités tapées gardées (mode réconcilier)
            avertissements = [_dit_pour_la_conception(a, version) for a in (
                reappliquer_lead(verrou, user=user, company=verrou.company).get('avertissements') or [])]
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
    # Relecture E6 M5 — l'imposition de la version (matériel désigné) passe à la recomposition.
    imposition = _imposition_de_la_version(version, lead, company)
    decision = decider_taille_residentielle(
        lead=lead, company=company, scenario=getattr(imposition, 'scenario', None), imposition=imposition,
        plafond_toit=None, dimensionner=R.dimensionneur_de_la_conception(version))
    structure_produit_id, structure_type = verifier_composition_residentielle(
        decision, lead=lead, company=company, taux_tva=devis.taux_tva, imposition=imposition)
    intention = R.intention_auto_residentielle(
        decision, lead=lead, company=company, user=user, taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale, structure_produit_id=structure_produit_id,
        structure_type=structure_type, imposition=imposition)
    avertissements = list(appliquer(devis, intention).get('avertissements') or [])
    R._poser_marqueur_impose(devis, imposition)  # comme la création : les recompositions ne la défont pas
    return avertissements


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


def reviser_sur_la_conception(devis, user):
    """Lane E6e (T4-X5-011) — « Réviser le devis » de l'atelier : la V2 (``revision.
    reviser_devis``, le devis envoyé jamais touché) est composée sur la conception COURANTE
    du lead par LA recomposition des brouillons (:func:`appliquer_a_la_demande`), sous UNE
    transaction : une recomposition refusée n'a créé aucune V2 (l'exception remonte).

    R6-N1 (suite) — avec un calepinage lié à la V1, le clonage ne calcule plus d'études
    (la recomposition les refait, et le calcul forcé du commit, après la re-liaison, a le
    dernier mot) : UN calcul forcé, hors du verrou de la V1, sur la V2 recomposée et re-liée.
    Sans calepinage : comme hier."""
    from django.db import transaction

    from apps.ventes.domain.revision import ETUDES_APRES_RECOMPOSITION, reviser_devis

    with transaction.atomic():
        nouveau = reviser_devis(devis, user=user, etudes=ETUDES_APRES_RECOMPOSITION)
        appliquer_a_la_demande(nouveau, user)
    nouveau.refresh_from_db()
    return nouveau


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
