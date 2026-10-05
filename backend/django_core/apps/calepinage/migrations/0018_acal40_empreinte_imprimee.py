"""ACAL40 — recalcul des empreintes « imprimées » stockées (D-ACAL-4 + D-ACAL-21).

``apps.ventes.domain.geometrie.layout_hash`` couvre désormais, en plus du
canonique historique, ``poseSurfaces``, ``exclusionZones``, ``modules``,
``shading12x24``, ``environment``, ``shadeObstructions`` et ``horizonProfile``
(présents et non vides seulement). Les empreintes déjà STOCKÉES le sont avec
l'ancienne formule : cette migration UNIQUE (jamais quatre) les recalcule sur
les quatre tables qui en portent une — ``Calepinage``, ``CalepinageVersion``,
``CalepinageVariante`` et ``ventes.Devis``.

RÈGLES
------
* Les DEUX formules sont FIGÉES dans ce fichier (``ancienne_empreinte`` /
  ``nouvelle_empreinte``) : une migration ne lit jamais le code vivant, qui
  peut changer après elle. ``reverse`` = la même passe, formules inversées.
* Une ligne n'est écrite QUE si son empreinte stockée est EXACTEMENT celle que
  la formule de départ donne pour son document (elle en dérive bien) et que
  la formule d'arrivée en donne une autre. Toute autre ligne (empreinte posée
  depuis une autre source, document absent) est laissée intacte.
* Un devis sans ``roof_layout`` qui porte l'empreinte de SON calepinage lié
  (``generer_devis`` la pose sans copier le document) suit le document de ce
  calepinage : le badge « à jour » ne bascule pas pour rien.
* ``QuerySet.update`` ciblé : aucun ``save()`` (les versions sont gelées par
  leur modèle), aucun signal, aucun statut touché (règle #4), aucune ligne de
  devis, aucun PDF.

DRY-RUN FONDATEUR OBLIGATOIRE AVANT MERGE (D-ACAL-4, mémoire
reconfirm-client-visible-repairs) : ``python manage.py acal_empreintes_dry_run``
liste, sans rien écrire, chaque ligne qui bougerait et l'effet sur le badge
« à jour », ``layout_stale``, la dédup, l'empreinte d'étude électrique et la
trace « corrigé après envoi ». Elle réutilise EXACTEMENT ``plan_de_recalcul``
ci-dessous.
"""
import hashlib
import json

from django.db import migrations

# ── Les deux formules, FIGÉES ────────────────────────────────────────────────

_AJOUTEES = ('poseSurfaces', 'exclusionZones', 'modules', 'shading12x24',
             'environment', 'shadeObstructions', 'horizonProfile')


def _canonique_historique(layout):
    return {
        'zones': (layout.get('zones') or layout.get('areas')
                  or layout.get('pans')),
        'result': layout.get('result'),
        'scenario': layout.get('scenario'),
        'panelWatt': layout.get('panelWatt') or layout.get('watt'),
        'battery': bool(layout.get('battery')),
    }


def _sha(canonique):
    blob = json.dumps(canonique, sort_keys=True, separators=(',', ':'),
                      default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def ancienne_empreinte(layout):
    """``layout_hash`` AVANT ACAL40 (QJ17), à l'octet."""
    if not isinstance(layout, dict):
        return ''
    return _sha(_canonique_historique(layout))


def nouvelle_empreinte(layout):
    """``layout_hash`` APRÈS ACAL40 — empreinte imprimée, à l'octet."""
    if not isinstance(layout, dict):
        return ''
    canonique = _canonique_historique(layout)
    for cle in _AJOUTEES:
        valeur = layout.get(cle)
        if valeur is not None and valeur not in ('', [], {}):
            canonique[cle] = valeur
    return _sha(canonique)


# ── Le plan (partagé avec la commande de dry-run) ────────────────────────────

def _cible(stocke, documents, depart, arrivee):
    """La nouvelle empreinte d'une ligne, ou ``None`` (ligne inchangée).

    ``documents`` : les documents candidats, dans l'ordre de préférence. Le
    premier dont l'empreinte de DÉPART égale l'empreinte stockée décide.
    """
    if not stocke:
        return None
    for document in documents:
        if not isinstance(document, dict):
            continue
        if depart(document) != stocke:
            continue
        cible = arrivee(document)
        return cible if cible and cible != stocke else None
    return None


def plan_de_recalcul(apps, *, sens='avant'):
    """Toutes les lignes à réécrire : ``[(modele, pk, ancienne, nouvelle, info)]``.

    ``sens='avant'`` = ancienne → nouvelle formule ; ``'arriere'`` = l'inverse.
    ``info`` porte ce dont le dry-run a besoin (société, calepinage, devis).
    """
    depart, arrivee = ((ancienne_empreinte, nouvelle_empreinte)
                       if sens == 'avant'
                       else (nouvelle_empreinte, ancienne_empreinte))
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    CalepinageVersion = apps.get_model('calepinage', 'CalepinageVersion')
    CalepinageVariante = apps.get_model('calepinage', 'CalepinageVariante')
    Devis = apps.get_model('ventes', 'Devis')

    plan = []
    doc_du_calepinage_du_devis = {}
    for ligne in (Calepinage._base_manager
                  .only('pk', 'company_id', 'devis_id', 'roof_layout',
                        'layout_hash').iterator()):
        if ligne.devis_id:
            doc_du_calepinage_du_devis[ligne.devis_id] = ligne.roof_layout
        cible = _cible(ligne.layout_hash, [ligne.roof_layout], depart, arrivee)
        if cible:
            plan.append(('Calepinage', ligne.pk, ligne.layout_hash, cible,
                         {'company_id': ligne.company_id,
                          'devis_id': ligne.devis_id}))
    for modele, nom in ((CalepinageVersion, 'CalepinageVersion'),
                        (CalepinageVariante, 'CalepinageVariante')):
        for ligne in (modele._base_manager
                      .only('pk', 'company_id', 'calepinage_id',
                            'roof_layout', 'layout_hash').iterator()):
            cible = _cible(ligne.layout_hash, [ligne.roof_layout], depart,
                           arrivee)
            if cible:
                plan.append((nom, ligne.pk, ligne.layout_hash, cible,
                             {'company_id': ligne.company_id,
                              'calepinage_id': ligne.calepinage_id}))
    for ligne in (Devis._base_manager
                  .exclude(layout_hash__isnull=True).exclude(layout_hash='')
                  .only('pk', 'company_id', 'roof_layout', 'layout_hash',
                        'reference', 'statut', 'is_active',
                        'electrical_design_hash').iterator()):
        documents = [ligne.roof_layout,
                     doc_du_calepinage_du_devis.get(ligne.pk)]
        cible = _cible(ligne.layout_hash, documents, depart, arrivee)
        if cible:
            plan.append(('Devis', ligne.pk, ligne.layout_hash, cible,
                         {'company_id': ligne.company_id,
                          'reference': ligne.reference or '',
                          'statut': ligne.statut,
                          'is_active': ligne.is_active,
                          'etude_electrique': bool(
                              ligne.electrical_design_hash)}))
    return plan


def _appliquer(apps, sens):
    modeles = {
        'Calepinage': apps.get_model('calepinage', 'Calepinage'),
        'CalepinageVersion': apps.get_model('calepinage',
                                            'CalepinageVersion'),
        'CalepinageVariante': apps.get_model('calepinage',
                                             'CalepinageVariante'),
        'Devis': apps.get_model('ventes', 'Devis'),
    }
    for nom, pk, _ancienne, nouvelle, _info in plan_de_recalcul(apps,
                                                                sens=sens):
        modeles[nom]._base_manager.filter(pk=pk).update(layout_hash=nouvelle)


def recalculer(apps, schema_editor):
    _appliquer(apps, 'avant')


def revenir(apps, schema_editor):
    _appliquer(apps, 'arriere')


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0017_acal33_un_calepinage_par_devis'),
        ('ventes', '0121_err_qjr570_ligne_composee'),
    ]

    operations = [
        migrations.RunPython(recalculer, revenir),
    ]
