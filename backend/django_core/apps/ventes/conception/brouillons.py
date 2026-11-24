"""ADEV147 / ADEV148 (D-ACAL-97, réponse Q2 du fondateur, 23/11/2026) — les
BROUILLONS d'un lead nés d'une version de conception plus ancienne.

* Un brouillon que personne n'a retouché SUIT la nouvelle conception
  (:func:`suivre_la_conception`) : réaligné par « Reprendre les valeurs du
  lead » (``pipeline.reappliquer_lead`` : études depuis le lead courant, compte
  de panneaux réconcilié par le mode RÉCONCILIER), son pointeur porté à la
  nouvelle version, une ligne d'historique qui nomme ce qui a changé.
* Un brouillon RETOUCHÉ à la main (:func:`est_retouche`) garde ses valeurs ; il
  est listé (``brouillons_a_mettre_a_jour``) et se réaligne SUR DEMANDE
  (:func:`appliquer_a_la_demande`, route ``mettre-a-jour-conception``).

Jamais un devis envoyé, accepté, refusé ou expiré : statut ``brouillon`` et
actif seulement ; aucun statut n'est écrit (règle #4). Seuls les devis nés
d'une conception (``Devis.conception_source``, ADEV143) sont concernés.
"""
import logging

logger = logging.getLogger(__name__)

MOTIF_RETOUCHE = 'retouché à la main'


def _brouillons_nes_avant(company_id, lead_id, version):
    """Les brouillons actifs du lead nés d'une version < ``version``, annotés
    ``_lignes_manuelles`` (une ligne à quantité ou prix tapés)."""
    from django.db.models import Exists, OuterRef, Q

    from apps.ventes.models import Devis, LigneDevis

    manuelles = LigneDevis.objects.filter(devis=OuterRef('pk')).filter(
        Q(quantite_manuelle=True) | Q(prix_manuel=True))
    return (Devis.objects.filter(company_id=company_id, lead_id=lead_id, statut=Devis.Statut.BROUILLON,
                                 is_active=True, conception_source__version__lt=version)
            .annotate(_lignes_manuelles=Exists(manuelles)).order_by('pk'))


def est_retouche(devis):
    """« Retouché à la main » (règle (4) de la consolidation C4) : une
    surcharge déclarée (``Devis.overrides`` non vide) ou une ligne à quantité
    ou prix saisis (``quantite_manuelle`` / ``prix_manuel``). Seule définition."""
    if devis.overrides:
        return True
    manuelles = getattr(devis, '_lignes_manuelles', None)
    if manuelles is None:
        manuelles = devis.lignes.filter(quantite_manuelle=True).exists() or devis.lignes.filter(
            prix_manuel=True).exists()
    return bool(manuelles)


def brouillons_a_mettre_a_jour(company_id, lead_id, version):
    """ADEV148 — ``[{devis, reference, motif}]`` du contrat : les brouillons
    RETOUCHÉS nés d'une version plus ancienne que ``version`` (numéro)."""
    return [{'devis': devis.pk, 'reference': devis.reference, 'motif': MOTIF_RETOUCHE}
            for devis in _brouillons_nes_avant(company_id, lead_id, version) if est_retouche(devis)]


def _panneaux(devis):
    """Les panneaux du devis, PAR OPTION quand il en porte deux
    (« sans 11 / avec 16 ») — classement des lignes du moteur PDF."""
    from apps.ventes.domain.catalogue import classer_produit

    par_option = {}
    for ligne in devis.lignes.filter(type_ligne='produit', optionnelle=False).select_related('produit'):
        if classer_produit(getattr(ligne.produit, 'nom', '') or ligne.designation) == 'panneau':
            option = ligne.variante or ''
            par_option[option] = par_option.get(option, 0) + int(ligne.quantite)
    if set(par_option) <= {''}:
        return str(par_option.get('', 0))
    return ' / '.join('%s %d' % (option or 'commun', nombre) for option, nombre in sorted(par_option.items()))


def _ce_qui_a_change(version):
    """Les entrées nommées par leur libellé (jamais leurs valeurs : une ligne
    du devis survit à l'effacement du lead), sinon le motif de l'origine."""
    from apps.ventes.conception.service import MOTIFS_ORIGINE, libelle_champ

    champs = [c.get('champ') for c in (version.declencheur or {}).get('champs') or []]
    if champs:
        return ', '.join(libelle_champ(version.lead, c) for c in champs) + ' modifié(s)'
    return MOTIFS_ORIGINE.get((version.declencheur or {}).get('origine'), 'conception recalculée')


def _realigner(devis, version, user=None):
    """Réaligne UN brouillon sur ``version`` : ``reappliquer_lead`` (mode
    RÉCONCILIER), pointeur posé, ligne d'historique. Rend les avertissements
    du pipeline (ce qui n'a PAS été appliqué)."""
    from apps.ventes import activity
    from apps.ventes.domain.pipeline import pointeur_de_conception, reappliquer_lead
    from apps.ventes.models import Devis

    avant = _panneaux(devis)
    if (devis.mode_installation or 'residentiel') == 'residentiel' and not est_retouche(devis):
        resultat = {'avertissements': _recomposer_residentiel(devis, version, user)}
    else:  # retouché (quantités tapées gardées) ou C&I / agricole : réconcilier
        resultat = reappliquer_lead(devis, user=user, company=devis.company)
    Devis.objects.filter(pk=devis.pk, statut=Devis.Statut.BROUILLON).update(
        conception_source=pointeur_de_conception(version))
    devis.refresh_from_db()
    apres = _panneaux(devis)
    activity.log_devis_note(devis, user, 'Mis à jour : panneaux %s → %s (%s)' % (
        avant, apres, _ce_qui_a_change(version)))
    return list(resultat.get('avertissements') or [])


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
            _realigner(devis, version)
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
    né de la version courante n'est pas réécrit (``appliquees`` vide)."""
    from apps.ventes.models import ConceptionLead, Devis

    if devis.statut != Devis.Statut.BROUILLON or not devis.is_active:
        raise MiseAJourRefusee('Ce devis est parti : réviser le devis pour suivre la conception.')
    version = ConceptionLead.objects.filter(company_id=devis.company_id, lead_id=devis.lead_id,
                                            courante=True, etat=ConceptionLead.Etat.COMPLET).first()
    if version is None or (devis.conception_source or {}).get('version') == version.version:
        return {'devis_id': devis.pk, 'appliquees': [], 'non_appliquees': []}
    avertissements = _realigner(devis, version, user=user)
    verrouillees = [{'champ': 'quantite', 'raison': ligne.designation + ' : quantité saisie à la main, gardée'}
                    for ligne in devis.lignes.filter(quantite_manuelle=True).order_by('ordre', 'pk')]
    return {'devis_id': devis.pk, 'appliquees': ['conception_v%d' % version.version],
            'non_appliquees': verrouillees + [{'champ': 'composition', 'raison': str(a)} for a in avertissements]}
