"""Copilote vague 2 (lane CALA) — ce que l'assistant LIT d'un calepinage.

Le résumé COMPACT (contrat ``calepinage_assistant_resume.json``, < 1 500
caractères) et LA règle du « premier blocage » (``a_faire``), écrite UNE
fois ici et partagée par le résumé, ``du-lead`` et ``a-traiter``.

Tout est LU, rien n'est recalculé ni écrit : la production vient du résultat
servi (``selectors.resultat_servi``), le verdict électrique de
``services.electrique.verdict_de_conception``, l'approbation de
``services.approbation``, la reprise de visite de
``services.reprise_visite.etat_reprise`` et la fraîcheur du devis de
``serializers.peremption_du_calepinage``.

D-ACAL-6 : la production montrée au client est celle du DEVIS ; le P50 de ce
résumé est une étude technique interne (``portee: etude_technique_interne``).
D-ACAL-7 : quand la production est une « borne haute » (pertes non
renseignées), ``p90_kwh`` vaut ``None`` — jamais réaffiché.

Délibérément ABSENTS : prix, prix d'achat, marge, ``roof_layout``, clé de
carte, série horaire, cascade complète, nom ou téléphone du client.
"""
from __future__ import annotations

#: L'ensemble FERMÉ des gestes suivants (contrat du résumé).
A_FAIRE = ('creer', 'reprendre_visite', 'dessiner', 'simuler',
           'corriger_electrique', 'retenir', 'faire_approuver', 'publier',
           'rien')

#: L'ensemble FERMÉ des signaux (contrat ``calepinage_assistant_a_traiter``).
SIGNAUX = ('visite_non_reprise', 'visite_changee', 'sans_pose',
           'simulation_jamais', 'simulation_perimee', 'bloquant_electrique',
           'devis_absent', 'devis_desynchronise', 'approbation_attendue',
           'approbation_perimee', 'approbation_refusee')

#: LA règle du premier blocage : le premier groupe de signaux présent donne
#: le geste. ``retenir`` n'a pas de signal (une variante existe sans retenue).
_PREMIER_BLOCAGE = (
    (('visite_non_reprise', 'visite_changee'), 'reprendre_visite'),
    (('sans_pose',), 'dessiner'),
    (('simulation_jamais', 'simulation_perimee'), 'simuler'),
    (('bloquant_electrique',), 'corriger_electrique'),
    (('approbation_attendue', 'approbation_perimee', 'approbation_refusee'),
     'faire_approuver'),
    (('devis_absent', 'devis_desynchronise'), 'publier'),
)

#: L'onglet de l'atelier qui porte chaque geste (liste fermée des onglets
#: ouvrables, ``apps/agent/contract_samples/assistant_ecrans.json``).
_ONGLET_DU_GESTE = {
    'reprendre_visite': 'reprise-visite',
    'corriger_electrique': 'verdict-electrique',
    'faire_approuver': 'approbation',
    'simuler': 'production',
}

#: Plafonds du résumé compact (contrat : au plus 3 pans, 3 pertes, 3
#: bloquants, 2 avertissements de 140 caractères).
MAX_PANS = 3
MAX_PERTES = 3
MAX_BLOQUANTS = 3
MAX_AVERTISSEMENTS = 2
MAX_TEXTE = 140

PORTEE_PRODUCTION = 'etude_technique_interne'


def _premier_blocage(signaux, *, archive=False, a_retenir=False):
    """LE geste suivant (clé de :data:`A_FAIRE`) depuis des signaux.

    ``a_retenir`` : une variante existe et aucune n'est retenue — placé après
    le verdict électrique (on ne retient pas une variante bloquante) et avant
    l'approbation. Un calepinage archivé n'appelle aucun geste."""
    if archive:
        return 'rien'
    presents = set(signaux or ())
    for groupe, geste in _PREMIER_BLOCAGE:
        if geste == 'faire_approuver' and a_retenir:
            return 'retenir'
        if presents.intersection(groupe):
            return geste
    return 'retenir' if a_retenir else 'rien'


def _lien_du_geste(calepinage_id, a_faire):
    """``/calepinage/<id>`` + l'onglet du geste (table des écrans)."""
    from apps.agent.ecrans import chemin

    return chemin('calepinage', int(calepinage_id),
                  _ONGLET_DU_GESTE.get(a_faire))


def _texte(valeur):
    return str(valeur or '')[:MAX_TEXTE]


def _bloc_visite(calepinage):
    """``({validee_le, reprise, a_jour}, signaux)`` — jamais les mesures."""
    from .reprise_visite import etat_reprise

    etat = etat_reprise(calepinage)
    validee = etat.get('visite_id') is not None
    reprise = bool(etat.get('deja_repris'))
    signaux = []
    if validee and not reprise:
        signaux.append('visite_non_reprise')
    elif validee and not etat.get('a_jour'):
        signaux.append('visite_changee')
    return ({'validee_le': etat.get('validee_le'), 'reprise': reprise,
             'a_jour': bool(etat.get('a_jour'))}, signaux)


def _bloc_devis(calepinage, ecart):
    """``({id, reference, statut, a_jour, ecart_pct} | None, signaux)``."""
    from ..serializers import peremption_du_calepinage
    from .devis import _devis_lie_actif

    devis = _devis_lie_actif(calepinage)
    if devis is None:
        return None, ['devis_absent']
    perime = peremption_du_calepinage(devis, calepinage).get('layout_stale')
    a_jour = None if perime is None else not perime
    return ({'id': devis.pk, 'reference': devis.reference,
             'statut': devis.statut, 'a_jour': a_jour,
             'ecart_pct': (ecart or {}).get('ecart_pct')},
            ['devis_desynchronise'] if perime else [])


def _bloc_approbation(calepinage):
    """``({exigee, etat}, signaux)`` — l'état dérivé, jamais stocké."""
    from .approbation import (
        STATUT_BROUILLON, STATUT_PERIME, STATUT_REFUSE, approbation_exigee,
        statut_derive,
    )

    exigee = approbation_exigee(getattr(calepinage, 'company', None))
    etat = statut_derive(calepinage)
    signaux = []
    if etat == STATUT_REFUSE:
        signaux.append('approbation_refusee')
    elif exigee and etat == STATUT_PERIME:
        signaux.append('approbation_perimee')
    elif exigee and etat == STATUT_BROUILLON:
        signaux.append('approbation_attendue')
    return {'exigee': exigee, 'etat': etat if exigee else ''}, signaux


def _bloc_electrique(calepinage, variante=None):
    """``({verdict, bloquants[libellé]}, signaux)`` — coûteux (recalcul)."""
    from .electrique import verdict_de_conception

    verdict = verdict_de_conception(
        calepinage, layout=getattr(variante, 'roof_layout', None))
    bloquants = [_texte(b.get('libelle'))
                 for b in (verdict.get('bloquants') or ())][:MAX_BLOQUANTS]
    signaux = ['bloquant_electrique'] if verdict.get('verdict') == 'bloquant' else []
    # ACAL934 — l'état à trois valeurs et son nombre de points, tels que servis.
    return {'verdict': verdict.get('verdict'), 'bloquants': bloquants,
            'etat': verdict.get('etat'), 'points': verdict.get('points')}, signaux


def _pans(resultat):
    """Les 3 premiers pans posés, l'ombrage joint sur ``pan``."""
    ombrage = {}
    for ligne in ((resultat.get('ombrage') or {}).get('par_pan') or ()):
        if isinstance(ligne, dict) and not ligne.get('motif_omission'):
            ombrage[ligne.get('pan')] = ligne.get('perte_ombrage_pct')
    pans = [p for p in ((resultat.get('pose') or {}).get('pans') or ())
            if isinstance(p, dict)]
    lignes = [{'pan': p.get('pan'), 'modules': p.get('modules'),
               'kwc': p.get('kwc'), 'azimut_deg': p.get('azimut_deg'),
               'inclinaison_deg': p.get('inclinaison_deg'),
               'ombrage_pct': ombrage.get(p.get('pan'))}
              for p in pans[:MAX_PANS]]
    return lignes, max(len(pans) - MAX_PANS, 0)


def _bloc_conception(calepinage, resultat, variante=None):
    """``({modules, kwc, variantes, retenue, pans, pans_autres}, signaux, a_retenir)``."""
    from .. import selectors
    from .mesures import mesures_du_document

    pose = resultat.get('pose') or {}
    document = getattr(variante or calepinage, 'roof_layout', None)
    mesures = mesures_du_document(document) if isinstance(document, dict) and document else {}
    modules = pose.get('total_modules', mesures.get('modules'))
    lignes = list(selectors.variantes(calepinage).values_list('pk', 'retenue'))
    retenue = next((pk for pk, est in lignes if est), None)
    pans, autres = _pans(resultat)
    return ({'modules': modules, 'kwc': pose.get('kwc', mesures.get('kwc')),
             'variantes': len(lignes), 'retenue': retenue, 'pans': pans,
             'pans_autres': autres},
            [] if modules else ['sans_pose'],
            bool(lignes) and retenue is None)


def _bloc_production(resultat):
    """``(simulation, production, pertes, signaux)`` — lus, jamais recalculés."""
    simule = bool(resultat.get('simule'))
    perimee = bool(resultat.get('simulation_perimee'))
    etat = 'perimee' if perimee else ('a_jour' if simule else 'jamais')
    total = ((resultat.get('production') or {}).get('total') or {}) if etat == 'a_jour' else {}
    complete = bool(total.get('complete'))
    mention = _texte(total.get('mention'))
    borne_haute = (not complete) or 'borne haute' in mention
    pertes = sorted((p for p in (resultat.get('pertes') or ()) if isinstance(p, dict)
                     and isinstance(p.get('pct'), (int, float))),
                    key=lambda p: -p['pct'])[:MAX_PERTES]
    signaux = {'jamais': ['simulation_jamais'], 'perimee': ['simulation_perimee']}.get(etat, [])
    return (
        {'etat': etat, 'calcule_le': resultat.get('calcule_le'),
         'motif': _texte(resultat.get('motif'))},
        {'p50_kwh': total.get('p50_kwh'),
         'p90_kwh': None if borne_haute else total.get('p90_kwh'),
         'rendement_kwh_kwc': total.get('specific_yield_kwh_kwc'),
         'complete': complete, 'mention': mention,
         'portee': PORTEE_PRODUCTION},
        [{'poste': p.get('poste'), 'pct': p.get('pct'), 'source': p.get('source')}
         for p in pertes],
        signaux)


def _avertissements(resultat):
    """Les avertissements REGROUPÉS comme « ce qui manque » du parcours guidé
    (ACAL392, ``parcours_guide.regrouper_manque``) : la même phrase répétée
    par trois postes (« aucune norme électrique… ») n'occupe plus les deux
    places du résumé — une ligne, suivie de « (× n) »."""
    from .parcours_guide import regrouper_manque

    lignes = []
    for manque in regrouper_manque(resultat.get('avertissements')):
        suffixe = ' (× %d)' % manque['nombre'] if manque['nombre'] > 1 else ''
        lignes.append(_texte(manque['message'])[:MAX_TEXTE - len(suffixe)]
                      + suffixe)
    return lignes[:MAX_AVERTISSEMENTS]


def resume_compact(calepinage, *, variante=None):
    """CALA2 — le résumé COMPACT d'un calepinage (ou d'une de ses variantes).

    Forme EXACTE du contrat ``calepinage_assistant_resume.json``. Lecture
    pure : aucune version, aucun journal, aucun job.
    """
    from .. import selectors
    from .archivage import est_archive

    resultat = selectors.resultat_servi(calepinage, variante=variante) or {}
    conception, s_pose, a_retenir = _bloc_conception(calepinage, resultat, variante)
    simulation, production, pertes, s_simulation = _bloc_production(resultat)
    electrique, s_electrique = _bloc_electrique(calepinage, variante)
    devis, s_devis = _bloc_devis(calepinage, resultat.get('ecart_devis'))
    approbation, s_approbation = _bloc_approbation(calepinage)
    visite, s_visite = _bloc_visite(calepinage)
    archive = est_archive(calepinage)
    a_faire = _premier_blocage(
        s_visite + s_pose + s_simulation + s_electrique + s_approbation + s_devis,
        archive=archive, a_retenir=a_retenir)
    from .presentation import reference_calepinage

    return {
        'calepinage': calepinage.pk,
        'reference': reference_calepinage(calepinage),
        'lead': calepinage.lead_id,
        'statut': calepinage.statut,
        'archive': archive,
        'variante': ({'id': variante.pk, 'nom': variante.nom}
                     if variante is not None else None),
        'conception': conception,
        'simulation': simulation,
        'production': production,
        'pertes': pertes,
        'electrique': electrique,
        'devis': devis,
        'approbation': approbation,
        'visite': visite,
        'avertissements': _avertissements(resultat),
        'a_faire': a_faire,
        'lien': _lien_du_geste(calepinage.pk, a_faire),
    }


class LeadIntrouvable(LookupError):
    """Le lead n'est pas dans la portée CRM de l'appelant (404, sans oracle)."""


def lead_de_l_appelant(user, lead_id):
    """Le lead ``lead_id`` DANS la portée CRM de ``user``, sinon
    :class:`LeadIntrouvable` (même réponse qu'un identifiant absent)."""
    from .creation import lead_en_portee

    company = getattr(user, 'company', None)
    lead = lead_en_portee(company, lead_id, user) if company is not None else None
    if lead is None:
        raise LeadIntrouvable(lead_id)
    return lead


def calepinage_ouvert_visible(user, lead_id):
    """``(calepinage | None, hors_vue)`` — L'ouvert du lead (D-ACAL-12), et
    s'il existe mais reste HORS de la vue de ``user`` (jamais servi alors)."""
    from .. import selectors

    ouvert = selectors.calepinage_ouvert_du_lead(getattr(user, 'company', None),
                                                 lead_id)
    if ouvert is None:
        return None, False
    if not selectors.calepinages_visibles(user, inclure_archives=True).filter(
            pk=ouvert.pk).exists():
        return None, True
    return ouvert, False


def etat_du_lead(user, lead_id):
    """CALA3 — « où en est le calepinage de ce lead ? » (contrat
    ``calepinage_assistant_du_lead.json``).

    ``calepinage`` = le résumé EXACT de l'ouvert, ou ``None`` ; sans
    calepinage, ``a_faire`` vaut ``creer`` (suite : ``calepinage.preparer``) —
    sauf s'il en existe un hors de la vue de l'appelant : ``rien`` (il n'est
    pas à lui de le créer, et l'existant n'est jamais nommé).

    Raises:
        LeadIntrouvable: lead hors de la portée CRM de ``user``.
    """
    from apps.agent.ecrans import chemin
    from apps.crm.selectors import contour_lnglat
    from apps.visites.selectors import releve_pour_calepinage

    lead = lead_de_l_appelant(user, lead_id)
    ouvert, hors_vue = calepinage_ouvert_visible(user, lead.pk)
    resume = resume_compact(ouvert) if ouvert is not None else None
    releve = releve_pour_calepinage(lead) or {}
    if resume is not None:
        a_faire, lien = resume['a_faire'], resume['lien']
    else:
        a_faire, lien = ('rien' if hors_vue else 'creer'), chemin('lead', lead.pk)
    return {
        'lead': lead.pk,
        'calepinage': resume,
        'visite': {'visite_id': releve.get('visite_id'),
                   'validee_le': releve.get('validee_le'),
                   'motif_absence': releve.get('motif_absence')},
        'trace_disponible': len(contour_lnglat(lead)) >= 3,
        'a_faire': a_faire,
        'lien': lien,
    }


class RefusAssistant(ValueError):
    """Refus NOMMÉ d'une route de l'assistant : ``{detail, field, code}`` et
    le statut HTTP que la vue rend tel quel."""

    def __init__(self, detail, champ, code, statut=409):
        super().__init__(detail)
        self.champ, self.code, self.statut = champ, code, statut

    def corps(self):
        return {'detail': str(self), 'field': self.champ, 'code': self.code}


#: CALA6 — le 409 quand l'ouvert du lead est HORS de la vue de l'appelant
#: (ACAL295) : ni identifiant, ni référence, ni nom.
MESSAGE_PREPARER_HORS_VUE = (
    "Ce lead a déjà un calepinage ouvert que vous ne voyez pas : demandez au "
    "responsable du calepinage de vous l'ouvrir.")


def _reprendre_la_visite(calepinage, user):
    """``reprise`` | ``deja_reprise`` | ``aucune_visite_validee`` — le service
    ``releve-visite`` avec ``remplacer`` TOUJOURS faux (rien n'est converti,
    la conception ne change pas, un relevé déjà repris n'est jamais touché)."""
    from .reprise_visite import RepriseRefusee, etat_reprise, reprendre_visite

    if etat_reprise(calepinage).get('visite_id') is None:
        return 'aucune_visite_validee'
    try:
        _reponse, cree = reprendre_visite(calepinage, user=user, remplacer=False)
    except RepriseRefusee as refus:
        raise RefusAssistant(str(refus), refus.champ or 'visite_id',
                             'reprise_refusee') from None
    return 'reprise' if cree else 'deja_reprise'


def preparer(user, lead_id):
    """CALA6 — « prépare le calepinage de ce lead » en UN geste confirmé
    (contrat ``calepinage_assistant_preparer.json``).

    Ouvre le calepinage du lead s'il n'existe pas (``ouvrir_ou_creer_pour_lead``,
    la porte UNIQUE et idempotente de ``depuis-lead`` : jamais un second ouvert,
    D-ACAL-12), puis reprend la visite VALIDÉE (``releve-visite``, ``remplacer``
    faux). Le dessin et le pavage restent humains : la réponse porte les quatre
    clés de la carte ``lien_ecran`` pour ouvrir l'atelier.

    Returns:
        ``(reponse, cree)``.

    Raises:
        LeadIntrouvable: lead hors de la portée CRM (404).
        RefusAssistant: ouvert hors de la vue (409), relevé refusé (409).
    """
    from apps.agent.ecrans import chemin, ecrans

    from ..selectors_libelles import libelle_calepinage
    from .creation import corps_conflit, ouvrir_ou_creer_pour_lead
    from .mesures import mesures_du_document
    from .presentation import reference_calepinage

    lead = lead_de_l_appelant(user, lead_id)
    calepinage, cree = ouvrir_ou_creer_pour_lead(lead.pk, user.company, user=user)
    if not cree and 'detail' in corps_conflit(calepinage, user):
        raise RefusAssistant(MESSAGE_PREPARER_HORS_VUE, 'lead', 'calepinage_hors_vue')
    reprise = _reprendre_la_visite(calepinage, user)
    document = calepinage.roof_layout if isinstance(calepinage.roof_layout, dict) else {}
    a_dessiner = not (document and mesures_du_document(document).get('modules'))
    return {
        'ecran': 'calepinage',
        'chemin': chemin('calepinage', calepinage.pk,
                         'reprise-visite' if reprise == 'reprise' else None),
        'libelle': libelle_calepinage(calepinage),
        'titre': ('Ouvrir le calepinage pour dessiner le toit' if a_dessiner
                  else ecrans()['calepinage']['titre']),
        'calepinage': calepinage.pk,
        'reference': reference_calepinage(calepinage),
        'lead': lead.pk,
        'cree': cree,
        'reprise_visite': reprise,
    }, cree


# ── CALA7 — publier la conception au devis (aperçu, puis publication) ──────
#
# Décision fondateur D-W2-Q1 (19/11/2026) : l'assistant PEUT corriger un devis
# déjà ENVOYÉ, seulement après une confirmation qui montre l'ANCIEN et le
# NOUVEAU total. D'où deux temps : l'APERÇU (GET, calculé par le MÊME service
# que la publication dans une transaction ANNULÉE) puis la PUBLICATION (POST
# qui porte les deux totaux vus ; 409 ``apercu_perime`` s'ils ne sont plus
# ceux que le serveur recalcule — et alors rien n'est écrit). Les statuts
# FIGÉS (accepté, refusé, expiré, remplacé) refusent. Aucun PDF (règle #4),
# aucun statut de devis écrit, jamais de TVA, de remise ni de dérogation.


class _Annuler(Exception):
    """Sentinelle : annule la transaction de l'aperçu (rien n'est écrit)."""


def _montant(valeur):
    """Un total en texte décimal à deux chiffres (``"84500.00"``), ou None."""
    from decimal import Decimal, InvalidOperation

    if valeur is None:
        return None
    try:
        return str(Decimal(str(valeur)).quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError):
        return None


def _total_ttc(devis):
    """Le total TTC RELU en base (jamais l'instance de l'appelant)."""
    from apps.ventes.selectors import get_devis_by_pk

    frais = get_devis_by_pk(devis.pk) if devis is not None else None
    return _montant(frais.total_ttc) if frais is not None else None


def _kwc_du_document(document):
    from .mesures import mesures_du_document

    if not isinstance(document, dict) or not document:
        return None
    return mesures_du_document(document).get('kwc')


def _refuser_avant_publication(calepinage):
    """Les refus qui sortent AVANT tout calcul : devis lié figé, verdict
    électrique bloquant (la dérogation est humaine, D-ACAL-9)."""
    from .archivage import MESSAGE_ARCHIVE, est_archive
    from .devis import _devis_lie_actif
    from .electrique import verdict_de_conception
    from .verrou import est_verrouille

    if est_archive(calepinage):
        raise RefusAssistant(MESSAGE_ARCHIVE, 'calepinage', 'calepinage_archive')
    lie = _devis_lie_actif(calepinage)
    if lie is not None and est_verrouille(calepinage, devis=lie):
        raise RefusAssistant(
            f'Devis {lie.reference} {lie.get_statut_display().lower()} : il ne '
            'se corrige plus. Révisez-le (V2 brouillon) puis publiez la '
            'conception sur la V2.', 'devis', 'devis_fige')
    verdict = verdict_de_conception(calepinage)
    if verdict.get('verdict') == 'bloquant':
        motifs = ' ; '.join(_texte(b.get('libelle'))
                            for b in (verdict.get('bloquants') or ())[:MAX_BLOQUANTS])
        raise RefusAssistant(
            f'Verdict électrique bloquant ({motifs}) : un approbateur doit '
            'corriger ou déroger à l\'écran, onglet « Verdict électrique » du '
            'calepinage.', 'electrique', 'verdict_bloquant')
    return lie


def _sans_affiche(calepinage):
    """Une COPIE relue du calepinage, affiche retirée EN MÉMOIRE : la copie des
    octets de l'affiche vers la clé du devis est un effet HORS base qu'aucune
    annulation ne défait (elle se fait après validation, :func:`publier`)."""
    from ..models import Calepinage

    copie = Calepinage.objects.select_related('company', 'devis').get(pk=calepinage.pk)
    copie.roof_image = ''
    return copie


def _publier(calepinage, user, confirmer_taille=False, choix_devis=None):
    """``(geste, devis, details)`` — génère le brouillon (aucun devis lié) ou
    resynchronise le devis lié, par les services EXISTANTS du pont devis,
    sans TVA, remise ni dérogation. ``DevisRefuse`` remonte tel quel.
    ACAL922 — ``confirmer_taille`` : la confirmation de l'utilisateur, relayée.
    CFIN2 (R2-22) — ``choix_devis`` ``{rattacher_devis, creer_autre_devis}`` :
    la réponse de l'utilisateur à la question ``devis_existant``, relayée."""
    from apps.ventes.selectors import get_devis_by_pk

    from .devis import _devis_lie_actif, generer_devis, resynchroniser_devis

    choix = choix_devis or {}
    lie = _devis_lie_actif(calepinage)
    if lie is None:
        journal = {}
        devis, cree = generer_devis(calepinage, user=user, journal=journal,
                                    confirmer_taille=confirmer_taille,
                                    rattacher_devis=choix.get('rattacher_devis'),
                                    creer_autre_devis=bool(choix.get('creer_autre_devis')))
        return 'genere', devis, {
            'deduplique': not cree, 'inchange': False,
            'rattache': not cree and choix.get('rattacher_devis') == devis.pk,
            'avertissements': list(journal.get('avertissements') or ()),
            'marques_manquantes': list(journal.get('marques_manquantes') or ()),
            'electrique': journal.get('electrique') or {}}
    resultat = resynchroniser_devis(calepinage, user=user)
    return 'resynchronise', get_devis_by_pk(lie.pk), {
        'deduplique': False, 'inchange': bool(resultat.get('inchange')),
        'avertissements': list(resultat.get('avertissements') or ()),
        'marques_manquantes': list(resultat.get('marques_manquantes') or ()),
        'electrique': resultat.get('electrique') or {}}


def _lien_publication(calepinage, devis):
    from apps.agent.ecrans import chemin

    return (chemin('devis', devis.pk) if devis is not None
            else chemin('calepinage', calepinage.pk))


def apercu_publication(calepinage, *, user, choix_devis=None):
    """CALA7 — l'APERÇU de la publication, sans aucune écriture (contrat
    ``calepinage_assistant_publier_apercu.json``) : le MÊME service que la
    publication, dans une transaction ANNULÉE, affiche retirée.
    CFIN2 (R2-22) — sans ``choix_devis``, un brouillon libre antérieur du lead
    est ANNONCÉ (``devis_existant``, ``a_faire: choisir``) au lieu d'échouer."""
    from django.db import transaction

    from .devis import DevisRefuse
    from .presentation import reference_calepinage

    lie = _refuser_avant_publication(calepinage)
    calcul = {'existant': None}
    try:
        with transaction.atomic():
            geste, devis, details = _publier(_sans_affiche(calepinage), user,
                                             confirmer_taille=True, choix_devis=choix_devis)
            calcul.update(nouveau=_total_ttc(devis), inchange=details['inchange'],
                          question=_question_de_taille(calepinage, devis, geste, details))
            raise _Annuler
    except _Annuler:
        pass
    except DevisRefuse as refus_devis:
        calcul.update(nouveau=None, inchange=False, question=None,
                      existant=_devis_existant_annonce(refus_devis))
        if calcul['existant'] is None:
            raise
    ancien = _total_ttc(lie)
    inchange = lie is not None and calcul['inchange'] and calcul['nouveau'] == ancien
    return {
        'calepinage': calepinage.pk,
        'reference': reference_calepinage(calepinage),
        'geste': 'resynchroniser' if lie is not None else 'generer',
        'devis': ({'id': lie.pk, 'reference': lie.reference, 'statut': lie.statut}
                  if lie is not None else None),
        'corrige_apres_envoi': lie is not None and lie.statut == 'envoye',
        'kwc_avant': _kwc_du_document(getattr(lie, 'roof_layout', None)),
        'kwc_apres': _kwc_du_document(calepinage.roof_layout),
        'ancien_total_ttc': ancien,
        'nouveau_total_ttc': calcul['nouveau'],
        'a_faire': 'choisir' if calcul['existant'] else ('rien' if inchange else 'publier'),
        'confirmation_taille': calcul['question'],
        'devis_existant': calcul['existant'],
        'lien': _lien_publication(calepinage, lie),
    }


def _devis_existant_annonce(refus_devis):
    """CFIN2 (R2-22) — la question ``devis_existant`` de ``generer-devis``, MOT
    POUR MOT : ``{detail, devis, reference, total_ttc}``, ``None`` pour un autre
    refus. Les deux réponses (``rattacher_devis`` = ``devis``, ou
    ``creer_autre_devis``) restent un geste de l'utilisateur."""
    donnees = getattr(refus_devis, 'donnees', None) or {}
    if donnees.get('code') != 'devis_existant':
        return None
    return {cle: donnees.get(cle) for cle in ('detail', 'devis', 'reference', 'total_ttc')}


def _question_de_taille(calepinage, devis, geste, details):
    """ACAL922 (critique D6) — la question « confirmer la taille » que la
    publication posera, MOT POUR MOT celle de ``generer-devis`` : ``None`` ou
    ``{detail, refus}``. L'aperçu l'ANNONCE ; la publication exige
    ``confirmer_taille: true``, geste explicite de l'utilisateur relayé.
    CFIN2 — un brouillon RATTACHÉ passe la même garde de taille (R2-17)."""
    from .devis import DevisRefuse, _garde_taille

    if geste != 'genere' or (details['deduplique'] and not details.get('rattache')):
        return None
    try:
        _garde_taille(devis, calepinage, False)
    except DevisRefuse as question:
        return {'detail': question.donnees['detail'], 'refus': question.donnees['refus']}
    return None


def _apercu_perime(nouveau):
    texte = (nouveau or '').replace('.', ',')
    return RefusAssistant(
        f"Les totaux ont changé depuis l'aperçu (nouveau total {texte} MAD "
        'TTC) : relisez l\'aperçu et faites confirmer les nouveaux chiffres.',
        'nouveau_total_ttc', 'apercu_perime')


def _exiger_devis_nomme(lie, devis_vu):
    """Revue 2B — la confirmation NOMME le devis qu'elle corrige : ``devis_vu``
    (recopié de l'aperçu) doit être le devis lié ; il est obligatoire quand ce
    devis est déjà chez le client."""
    lie_id = lie.pk if lie is not None else None
    if devis_vu is not None and devis_vu != lie_id:
        raise RefusAssistant(
            "Ce n'est pas le devis lié à ce calepinage : relisez l'aperçu et "
            'recopiez son champ devis.', 'devis', 'devis_autre')
    if devis_vu is None and lie is not None and lie.statut == 'envoye':
        raise RefusAssistant(
            f'Le devis {lie.reference} est déjà chez le client : relisez '
            "l'aperçu et recopiez son champ devis, pour que la confirmation le "
            'nomme.', 'devis', 'devis_a_nommer')


def publier(calepinage, *, user, ancien_vu, nouveau_vu, devis_vu=None,
            confirmer_taille=False, choix_devis=None):
    """CALA7 — PUBLIE la conception au devis (contrat
    ``calepinage_assistant_publier_devis.json``) aux seuls chiffres VUS.
    ACAL922 — ``confirmer_taille`` : la réponse de l'utilisateur à la question
    annoncée par l'aperçu, relayée telle quelle à ``generer_devis`` ; CFIN2 —
    ``choix_devis`` de même pour la question ``devis_existant``.

    ``ancien_vu`` / ``nouveau_vu`` : les totaux TTC de l'aperçu confirmé
    (texte décimal ; ``ancien_vu`` None sans devis lié). Recalculés ici, dans
    la transaction de la publication : s'ils diffèrent, tout est annulé et
    :class:`RefusAssistant` ``apercu_perime`` (409) est levé. L'affiche n'est
    copiée qu'APRÈS validation.
    """
    from django.db import transaction

    from .devis import _poser_affiche

    lie = _refuser_avant_publication(calepinage)
    _exiger_devis_nomme(lie, devis_vu)
    with transaction.atomic():
        ancien = _total_ttc(lie)
        geste, devis, details = _publier(_sans_affiche(calepinage), user,
                                         confirmer_taille=confirmer_taille,
                                         choix_devis=choix_devis)
        nouveau = _total_ttc(devis)
        if (ancien, nouveau) != (_montant(ancien_vu), _montant(nouveau_vu)):
            raise _apercu_perime(nouveau)
    if geste == 'genere' or not details['inchange']:
        _poser_affiche(calepinage, devis)
    electrique = details['electrique']
    return {
        'geste': geste,
        'devis': devis.pk,
        'reference': devis.reference,
        'statut': devis.statut,
        'corrige_apres_envoi': devis.statut == 'envoye',
        'deduplique': details['deduplique'],
        'inchange': details['inchange'],
        'ancien_total_ttc': ancien,
        'nouveau_total_ttc': nouveau,
        'avertissements': [_texte(a) for a in details['avertissements']],
        'marques_manquantes': list(details['marques_manquantes']),
        'electrique': {'verdict': electrique.get('verdict'),
                       'manquantes': list(electrique.get('manquantes') or ())},
        'lien': _lien_publication(calepinage, devis),
    }


# ── CALA9 — la file « calepinages à traiter » (et le bloc du matin) ────────

#: Fenêtre de la file : calepinages OUVERTS modifiés depuis N jours.
FENETRE_JOURS = 30
#: Au plus N calepinages évalués (les plus récents) — borne le coût.
CANDIDATS_MAX = 30
#: Les signaux COÛTEUX (simulation, électrique) ne sont évalués que pour les
#: N premiers candidats (les plus récents) ; au-delà ``evalue: false`` et ils
#: sont ABSENTS (jamais devinés).
COUTEUX_MAX = 5
LIMITE_DEFAUT, LIMITE_MAX = 10, 20


def _signaux_economiques(calepinage):
    """``(signaux, a_retenir)`` — visite, pose, devis, approbation : chacun
    par SON lecteur unique (les mêmes blocs que le résumé)."""
    from .. import selectors
    from .mesures import mesures_du_document

    _visite, signaux = _bloc_visite(calepinage)
    document = calepinage.roof_layout if isinstance(calepinage.roof_layout, dict) else {}
    if not (document and mesures_du_document(document).get('modules')):
        signaux = signaux + ['sans_pose']
    _devis, s_devis = _bloc_devis(calepinage, None)
    _approbation, s_approbation = _bloc_approbation(calepinage)
    lignes = list(selectors.variantes(calepinage).values_list('retenue', flat=True))
    return signaux + s_devis + s_approbation, bool(lignes) and not any(lignes)


def _signaux_couteux(calepinage):
    """Simulation (résultat servi) et verdict électrique — recalculés."""
    from .. import selectors

    resultat = selectors.resultat_servi(calepinage) or {}
    _simulation, _production, _pertes, s_simulation = _bloc_production(resultat)
    _electrique, s_electrique = _bloc_electrique(calepinage)
    return s_simulation + s_electrique


def _ligne_a_traiter(calepinage, *, evaluer):
    """Une ligne de la file (forme d'une ligne de
    ``calepinage_assistant_a_traiter.json``), ou None s'il n'y a rien à faire."""
    from .presentation import reference_calepinage

    signaux, a_retenir = _signaux_economiques(calepinage)
    if evaluer:
        signaux = signaux + _signaux_couteux(calepinage)
    signaux = sorted(set(signaux), key=SIGNAUX.index)
    a_faire = _premier_blocage(signaux, a_retenir=a_retenir)
    if a_faire == 'rien':
        return None
    modifie = getattr(calepinage, 'updated_at', None)
    return {
        'calepinage': calepinage.pk,
        'reference': reference_calepinage(calepinage),
        'lead': calepinage.lead_id,
        'modifie_le': modifie.isoformat() if modifie is not None else None,
        'signaux': signaux,
        'a_faire': a_faire,
        'lien': _lien_du_geste(calepinage.pk, a_faire),
        'evalue': bool(evaluer),
    }


def file_a_traiter(user, *, limite=LIMITE_DEFAUT, maintenant=None):
    """CALA9 — les calepinages OUVERTS de la vue de ``user``, modifiés depuis
    :data:`FENETRE_JOURS` jours, plus récents d'abord, qui appellent un geste
    (contrat ``calepinage_assistant_a_traiter.json``). ``total`` compte les
    lignes à traiter parmi les :data:`CANDIDATS_MAX` plus récents ; les
    signaux coûteux ne sont évalués que pour les :data:`COUTEUX_MAX` premiers.
    Aucun score, aucun classement de personnes, aucun prix."""
    from datetime import timedelta

    from django.utils import timezone

    from .. import selectors

    limite = max(1, min(int(limite), LIMITE_MAX))
    depuis = (maintenant or timezone.now()) - timedelta(days=FENETRE_JOURS)
    candidats = (selectors.calepinages_visibles(user)
                 .filter(updated_at__gte=depuis)
                 .order_by('-updated_at', '-id')[:CANDIDATS_MAX])
    from .devis_retenu import lecture_de_liste

    lignes, evalues = [], 0
    with lecture_de_liste():  # coût des requêtes (lot 4) : rien du moteur pendant une liste
        for calepinage in candidats:
            evaluer = evalues < COUTEUX_MAX
            evalues += int(evaluer)
            ligne = _ligne_a_traiter(calepinage, evaluer=evaluer)
            if ligne is not None:
                lignes.append(ligne)
    return {'total': len(lignes), 'limite': limite, 'lignes': lignes[:limite]}
