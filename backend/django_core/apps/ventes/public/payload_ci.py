"""Proposition publique : la charge utile dans les mots et les chiffres du PDF.

CPRS, 27/10/2026.

Dernière passe sur ``payload`` avant l'envoi, appelée en UNE ligne par
``public_views.proposal_data`` :

- CPRS1 — C&I : la page titrait la puissance, le nombre de panneaux et la
  production de l'option AVEC batterie (``quote.puissance_kwc`` = option
  avec quand elle porte plus de panneaux) et une courbe mensuelle « ville »
  (``prod_kwh`` × poids GHI) à côté du prix de l'offre SANS ; le PDF imprime
  ceux de l'option servie (``synthese_ci.systeme``) et le bilan horaire du
  moteur (``synthese_ci.energie.par_mois``). Les scalaires et séries publics
  sont alignés sur ces deux sources — aucun chiffre calculé ici.
- CPRS2 — ``quote.libelles_document`` (dictionnaire de libellés du PDF) et
  ``quote.etude.etude_ci`` (étude C&I brute : composition, motifs, sources)
  ne partent plus : la page n'en lit rien.
- CPRS3 — textes servis par le moteur C&I (sources, motifs, mentions) :
  traduits ou retirés par LES fonctions du PDF (``ci/couverture.texte_client``,
  ``sans_reserve``, ``ci/mentions.ligne_tarif_client``) ; la liste interne
  « à confirmer » ne garde que les postes à chiffrer après la visite (le PDF
  ne l'imprime plus, décision fondateur 26/10/2026).

Les valeurs numériques ne sont jamais modifiées par CPRS3 ; l'empreinte de
signature est calculée AVANT cette passe sur la synthèse brute.
"""
import copy
import html
import re

#: Champs texte libres servis par le moteur C&I qui peuvent porter un code
#: ou une réserve interne.
_CHAMPS_TEXTE = frozenset({'source', 'motif', 'motif_base', 'van_motif'})

#: Résidus internes que ``texte_client`` ne traduit pas : la valeur est
#: retirée plutôt que montrée (jamais réécrite en un texte inventé).
_RESIDU_INTERNE = re.compile(
    r"moteur|\bGroupe [A-Z]{2,}|\bCIQ\d|\bD-[A-Z]{2,}-?\d|Paramètres|repli"
    r"|Wayback|fondateur|\binterne\b|\bReda\b|aucun défaut"
    r"|\b[a-z]+(?:_[a-z]+)+\b|\b[a-z]+_[a-z_]*\.[A-Za-z_]+", re.IGNORECASE)

#: Préfixe « décision fondateur D-XXX-n du jj/mm/aaaa — » d'une source
#: dont la suite est une phrase client : seul le préfixe part.
_PREFIXE_DECISION = re.compile(
    r"^\s*décision fondateur D-[A-Z]+-\d+(?: du [\d/]+)?\s*(?:—\s*)?",
    re.IGNORECASE)

#: Seuls blocs d'omission que la page rend au client (motifs propres).
_PREFIXE_OMISSION_CLIENT = 'argent'


def _texte_client(libelles, texte):
    from ..quote_engine.ci import couverture
    propre = couverture.sans_reserve(couverture.texte_client(
        libelles, _PREFIXE_DECISION.sub('', str(texte or ''))))
    return '' if _RESIDU_INTERNE.search(propre) else propre


def _assainir_textes(noeud, libelles):
    if isinstance(noeud, dict):
        for cle, val in list(noeud.items()):
            if cle in _CHAMPS_TEXTE and isinstance(val, str):
                noeud[cle] = _texte_client(libelles, val) or None
            else:
                _assainir_textes(val, libelles)
    elif isinstance(noeud, list):
        for val in noeud:
            _assainir_textes(val, libelles)


def _assainir_synthese_ci(synthese, libelles, langue):
    from ..quote_engine.ci import mentions
    synthese['a_confirmer'] = [
        a for a in synthese.get('a_confirmer') or []
        if isinstance(a, dict) and a.get('cle') == 'a_chiffrer_visite']
    synthese['omissions'] = [
        o for o in synthese.get('omissions') or []
        if isinstance(o, dict)
        and str(o.get('bloc') or '').startswith(_PREFIXE_OMISSION_CLIENT)]
    argent = synthese.get('argent')
    if isinstance(argent, dict) and isinstance(argent.get('tarif'), dict):
        mention = mentions.ligne_tarif_client(argent['tarif'], langue)
        argent['tarif']['mention'] = mention
        # AMOT88 — la valeur interne « grille ONEE …, repli » de
        # l'hypothèse tarif devient la même phrase que le PDF.
        for hyp in argent.get('hypotheses') or []:
            if isinstance(hyp, dict) and isinstance(hyp.get('valeur'), str) \
                    and _RESIDU_INTERNE.search(hyp['valeur']):
                hyp['valeur'] = mention
    # CPRS11 — le libellé O&M est échappé pour le HTML du PDF
    # (« O&amp;M ») ; la page l'affiche en texte : même mot, déséchappé.
    om = (synthese.get('services') or {}).get('om_option') \
        if isinstance(synthese.get('services'), dict) else None
    if isinstance(om, dict):
        for noeud in [om] + [li for li in om.get('lignes') or []
                             if isinstance(li, dict)]:
            for cle in ('libelle', 'designation'):
                if isinstance(noeud.get(cle), str):
                    noeud[cle] = html.unescape(noeud[cle])
    _assainir_textes(synthese, libelles)


def _nombre(valeur):
    return valeur if isinstance(valeur, (int, float)) \
        and not isinstance(valeur, bool) else None


def _aligner_sur_option_servie(payload, synthese):
    quote = payload.get('quote')
    systeme = synthese.get('systeme') if isinstance(synthese, dict) else None
    if isinstance(quote, dict) and isinstance(systeme, dict):
        for cle_quote, cle_systeme in (('puissance_kwc', 'kwc'),
                                       ('nb_panneaux', 'nb_panneaux'),
                                       ('prod_kwh', 'production_kwh_an')):
            if cle_quote in quote and \
                    _nombre(systeme.get(cle_systeme)) is not None:
                quote[cle_quote] = systeme[cle_systeme]
    par_mois = (synthese.get('energie') or {}).get('par_mois') \
        if isinstance(synthese.get('energie'), dict) else None
    if not isinstance(par_mois, list) or len(par_mois) != 12:
        return
    mois = sorted((m for m in par_mois if isinstance(m, dict)),
                  key=lambda m: m.get('mois') or 0)
    for cle_payload, cle_mois in (('monthly_production', 'production_kwh'),
                                  ('monthly_consumption', 'consommation_kwh')):
        serie = [_nombre(m.get(cle_mois)) for m in mois]
        if cle_payload in payload and len(serie) == 12 \
                and all(v is not None for v in serie):
            payload[cle_payload] = [round(v) for v in serie]


def synthese_ci_client(synthese, data):
    """CPRS3 — copie de ``synthese`` (la synthèse du PDF) dans les mots du
    client : mêmes nombres, textes internes traduits ou retirés."""
    data = data or {}
    libelles = {'libelles_document': data.get('libelles_document') or {},
                'langue_sortie': data.get('langue_sortie')}
    langue = data.get('langue_sortie') or None
    synthese = copy.deepcopy(synthese)
    _assainir_synthese_ci(synthese, libelles, langue)
    return synthese


def synthese_agricole_client(synthese, libelles):
    """CPRS8 — la synthèse agricole du PDF, ses textes (sources, motifs)
    servis assainis, nombres inchangés ; en place, et rendue."""
    _assainir_textes(synthese, libelles)
    return synthese


def _retirer_partout(noeud, cle):
    if isinstance(noeud, dict):
        noeud.pop(cle, None)
        for valeur in noeud.values():
            _retirer_partout(valeur, cle)
    elif isinstance(noeud, list):
        for valeur in noeud:
            _retirer_partout(valeur, cle)


def charge_utile_client(payload):
    """AMOT67 + CPRS1-3 — en place sur ``payload`` ; chaque bloc est copié
    en profondeur d'abord (jamais ``devis.etude_params`` muté).

    AMOT67 (C-AMOT-050, déplacé de ``public_views``) : ``economie_ci`` est
    retiré à TOUTE profondeur — la page lit ``synthese_ci``."""
    for cle in list(payload):
        payload[cle] = copy.deepcopy(payload[cle])
    _retirer_partout(payload, 'economie_ci')
    quote = payload.get('quote')
    data = quote if isinstance(quote, dict) else {}
    libelles = {'libelles_document': data.get('libelles_document') or {},
                'langue_sortie': data.get('langue_sortie')}
    if isinstance(quote, dict):
        quote.pop('libelles_document', None)
        # Note interne de la grille MT (« la page indique TVA 18 % … ») :
        # la page lit la mention tarif de ``synthese_ci``, jamais celle-ci.
        quote.pop('tarif_mt_mention', None)
        etude = quote.get('etude')
        if isinstance(etude, dict):
            etude.pop('etude_ci', None)
    if isinstance(payload.get('synthese_agricole'), dict):
        synthese_agricole_client(payload['synthese_agricole'], libelles)
    synthese = payload.get('synthese_ci')
    if not isinstance(synthese, dict):
        return
    _aligner_sur_option_servie(payload, synthese)
    payload['synthese_ci'] = synthese_ci_client(synthese, libelles)
