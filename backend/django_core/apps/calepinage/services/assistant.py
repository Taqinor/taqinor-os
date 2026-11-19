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


def premier_blocage(signaux, *, archive=False, a_retenir=False):
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


def lien_du_geste(calepinage_id, a_faire):
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
    return {'verdict': verdict.get('verdict'), 'bloquants': bloquants}, signaux


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
    a_faire = premier_blocage(
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
        'avertissements': [_texte(a) for a in (resultat.get('avertissements') or ())
                           ][:MAX_AVERTISSEMENTS],
        'a_faire': a_faire,
        'lien': lien_du_geste(calepinage.pk, a_faire),
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
