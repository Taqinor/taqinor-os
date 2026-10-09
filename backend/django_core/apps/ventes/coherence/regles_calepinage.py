"""QA-COHERENCE — ACAL346 (C-ACAL-146, C-ACAL-035) : trois invariants de
PARITÉ calepinage ↔ devis, en lecture seule.

* ``CAL_MODULES_DEVIS_VS_CALEPINAGE`` — modules POSÉS du document de
  conception (``geometrie.pans_du_document``, la primitive de C-ACAL-035) ≠
  quantité de panneaux de l'option retenue du devis ;
* ``CAL_KWC_DEVIS_VS_CALEPINAGE`` — kWc dessiné ≠ ``puissance_kwc_du_devis``
  au-delà de ``TOLERANCES['kwc_calepinage_ratio']`` ;
* ``CAL_EMPREINTE_IMPRIMEE_PERIMEE`` — empreinte imprimée du calepinage
  (``geometrie.layout_hash``, D-ACAL-4) ≠ ``Devis.layout_hash`` : le document
  a bougé sans resynchronisation.

Frontière cross-app (M6) : le calepinage est lu par
``apps.calepinage.selectors.calepinage_du_devis`` (import fonction-local),
jamais par ses modèles. Aucune troisième formule : modules et kWc viennent des
mêmes fonctions que la composition et le moteur. Avertissements, jamais
critiques ; aucune écriture.
"""
from __future__ import annotations

from .registre import GRAVITE_AVERTISSEMENT, PORTEE_DEVIS, TOLERANCES, regle


def _calepinage_lie(devis):
    """Le calepinage OUVERT rattaché DIRECTEMENT à ce devis, ou ``None``
    (devis inactif, sans conception, ou conception re-liée à une révision)."""
    if not getattr(devis, 'is_active', True):
        return None
    from apps.calepinage.selectors import calepinage_du_devis
    calepinage = calepinage_du_devis(devis.pk, devis.company)
    if calepinage is None or str(calepinage.devis_id) != str(devis.pk):
        return None
    if not isinstance(calepinage.roof_layout, dict) or not calepinage.roof_layout:
        return None
    return calepinage


def _mesures_document(calepinage):
    from apps.ventes.domain.geometrie import pans_du_document
    pans = pans_du_document(calepinage.roof_layout)
    modules = sum(int(p.get('modules') or 0) for p in pans)
    kwc = sum(float(p.get('kwc') or 0) for p in pans)
    return modules, kwc


def _modules_option_retenue(devis):
    from apps.ventes.domain.composition import (
        VARIANTE_AVEC, VARIANTE_COMMUNE, VARIANTE_SANS)
    from apps.ventes.domain.lignes import comptes_panneaux_du_devis
    from apps.ventes.utils.options import (
        AVEC_BATTERIE, SANS_BATTERIE, option_effective)
    comptes = comptes_panneaux_du_devis(devis) or {}
    variante = {AVEC_BATTERIE: VARIANTE_AVEC,
                SANS_BATTERIE: VARIANTE_SANS}.get(option_effective(devis),
                                                  VARIANTE_COMMUNE)
    valeur = comptes.get(variante)
    if valeur is None:
        valeur = comptes.get(VARIANTE_AVEC)
    return valeur


@regle('CAL_MODULES_DEVIS_VS_CALEPINAGE',
       'Modules posés au calepinage ≠ panneaux du devis (option retenue)',
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def modules_devis_vs_calepinage(r, devis, ctx):
    calepinage = _calepinage_lie(devis)
    if calepinage is None:
        return []
    modules_doc, _kwc = _mesures_document(calepinage)
    modules_devis = _modules_option_retenue(devis)
    if not modules_doc or modules_devis is None or modules_doc == modules_devis:
        return []
    return [r.violation(
        devis, 'Le calepinage pose %d modules, le devis en chiffre %d.'
        % (modules_doc, modules_devis),
        valeurs={'modules_calepinage': modules_doc,
                 'modules_devis': modules_devis,
                 'calepinage_id': calepinage.pk},
        attendu=modules_doc)]


@regle('CAL_KWC_DEVIS_VS_CALEPINAGE',
       'kWc dessiné au calepinage ≠ kWc du devis',
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def kwc_devis_vs_calepinage(r, devis, ctx):
    calepinage = _calepinage_lie(devis)
    if calepinage is None:
        return []
    _modules, kwc_doc = _mesures_document(calepinage)
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    kwc_devis = puissance_kwc_du_devis(devis)
    if not kwc_doc or kwc_devis is None:
        return []
    ecart = abs(float(kwc_devis) - kwc_doc) / kwc_doc
    if ecart <= TOLERANCES['kwc_calepinage_ratio']:
        return []
    return [r.violation(
        devis, 'Le calepinage dessine %.2f kWc, le devis en porte %.2f.'
        % (kwc_doc, float(kwc_devis)),
        valeurs={'kwc_calepinage': round(kwc_doc, 3),
                 'kwc_devis': round(float(kwc_devis), 3),
                 'ecart_ratio': round(ecart, 4),
                 'calepinage_id': calepinage.pk},
        attendu=round(kwc_doc, 3))]


@regle('CAL_EMPREINTE_IMPRIMEE_PERIMEE',
       'Empreinte imprimée du calepinage ≠ empreinte du devis (non resynchronisé)',
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS)
def empreinte_imprimee_perimee(r, devis, ctx):
    calepinage = _calepinage_lie(devis)
    if calepinage is None or not getattr(devis, 'layout_hash', ''):
        return []
    from apps.ventes.domain.geometrie import layout_hash
    empreinte = layout_hash(calepinage.roof_layout)
    if not empreinte or empreinte == devis.layout_hash:
        return []
    return [r.violation(
        devis, 'La conception a changé depuis la dernière resynchronisation '
        'du devis (empreinte imprimée périmée).',
        valeurs={'empreinte_calepinage': empreinte[:12],
                 'empreinte_devis': (devis.layout_hash or '')[:12],
                 'calepinage_id': calepinage.pk},
        cle={'empreinte_calepinage': empreinte},
        attendu=empreinte[:12])]
