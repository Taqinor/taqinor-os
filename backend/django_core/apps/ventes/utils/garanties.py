"""VNT37 — les garanties RÉELLES d'une vente, en DONNÉES neutres.

Nouveau fichier car : aucun module neutre ne lit les garanties hors moteur.
La facture (gabarit legacy ``templates/pdf/facture.html``) imprimera le
tableau « Garanties » (VNT38) depuis ce helper : les MÊMES durées que la bande
du PDF devis du même marché, jamais une constante.

Règle #4 : lecture seule des helpers du moteur (``residential.theme``,
``agricole.garanties``, ``agricole.pages``, ``i18n_labels``) — aucun rendu,
aucun statut écrit.

Les quatre règles :
  * agricole (pompage) → ``agricole.garanties.garanties_pompage`` (jamais les
    garanties résidentielles, AGR305) ; résidentiel / C&I →
    ``theme.warranties_for`` sur les items de l'option retenue
    (``options.option_lines`` → ``lignes_classement._line_to_item``) ;
  * ``[]`` SANS ligne (``warranties_for`` rendrait sinon ses quatre
    constantes) ET sur toute exception (import compris) — jamais un chiffre
    inventé ;
  * TEXTE SEUL : l'arabe vient de ``i18n_labels.libelle`` (jamais
    ``theme.libelle_doc``, qui enveloppe l'arabe dans un ``<span>``) ;
  * le détail n'est imprimé que pour « Performance » (comme la bande du
    devis) : le sous-libellé « main-d'œuvre <société> » de la constante
    Installation ne sort jamais (multi-société).

Chaque garantie : ``{'designation', 'duree', 'detail', 'texte'}`` — ``texte``
est la phrase exacte de la bande du PDF devis du même marché.
"""
import logging

logger = logging.getLogger(__name__)

MODE_AGRICOLE = 'agricole'


def _langue(langue):
    from apps.ventes.quote_engine import i18n_labels
    return i18n_labels.normaliser((langue or 'fr').lower())


def _garanties_pompage(items, langue):
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.agricole import pages
    from apps.ventes.quote_engine.agricole.garanties import garanties_pompage
    sortie = []
    for g in garanties_pompage(items):
        cle = f"agr_garantie_{g.get('composant')}"
        designation = (i18n_labels.libelle(cle, langue).format(duree='')
                       .rstrip(' :'))
        sortie.append({
            'designation': designation,
            'duree': pages._duree(langue, g['mois']),
            'detail': '',
            'texte': pages._libelle_garantie(langue, g),
        })
    return sortie


def _garanties_solaire(items, langue):
    import importlib

    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.residential import theme
    # Mêmes imports que ``warranties_for`` : son ``except`` interne rend les
    # CONSTANTES ; ici une erreur d'import lève, donc ``[]`` (appelant).
    importlib.import_module('apps.ventes.quote_engine.lignes_classement')
    importlib.import_module('apps.ventes.utils.options')
    sortie = []
    for n, unite, label, sub in theme.warranties_for({'items': items}):
        detail = sub if label == 'Performance' else ''
        if langue == 'fr':
            designation, duree = label, f'{n} {unite}'
        else:
            cle = theme._CLES_GARANTIE.get(label)
            designation = i18n_labels.libelle(cle, langue) if cle else label
            duree = (f"{n} {i18n_labels.libelle('ci_ans', langue)}"
                     if unite == 'ans' else f'{n} {unite}')
            if detail.endswith(' garanti'):
                detail = i18n_labels.libelle(
                    'res_gar_pct_garanti', langue).format(
                        pct=detail[:-len(' garanti')])
            elif detail == 'performance linéaire':
                detail = i18n_labels.libelle('res_gar_lineaire', langue)
        texte = f'{duree} — {designation}' + (f' ({detail})' if detail else '')
        sortie.append({'designation': designation, 'duree': duree,
                       'detail': detail, 'texte': texte})
    return sortie


def garanties_des_items(items, mode, langue='fr'):
    """Garanties d'une composition d'items (forme ``_line_to_item``).

    ``[]`` sans item et sur toute exception — jamais les constantes."""
    lignes = [it for it in (items or []) if isinstance(it, dict)]
    if not lignes:
        return []
    try:
        lg = _langue(langue)
        if (mode or '').strip().lower() == MODE_AGRICOLE:
            return _garanties_pompage(lignes, lg)
        return _garanties_solaire(lignes, lg)
    except Exception:  # noqa: BLE001 — jamais une garantie inventée (D-ENF22-BLE001)
        logger.warning('garanties_des_items : erreur ignorée (liste vide)',
                       exc_info=True)
        return []


def garanties_de_la_vente(devis, langue='fr'):
    """Garanties de la vente portée par ``devis`` : lignes de l'option
    retenue (acceptée, sinon celle du total affiché), ``[]`` sans devis,
    sans ligne ou sur erreur."""
    if devis is None:
        return []
    try:
        from apps.ventes.quote_engine.lignes_classement import _line_to_item
        from apps.ventes.utils.options import option_lines
        items = [_line_to_item(li, devis.taux_tva)
                 for li in option_lines(devis)]
    except Exception:  # noqa: BLE001 — jamais une garantie inventée (D-ENF22-BLE001)
        logger.warning('garanties_de_la_vente : erreur ignorée (liste vide)',
                       exc_info=True)
        return []
    return garanties_des_items(
        items, getattr(devis, 'mode_installation', ''), langue)
