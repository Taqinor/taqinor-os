"""CALX296 — les documents techniques du module, en français ET en anglais.

Le constat
==========
La mécanique de langue de SORTIE existe et elle est partagée
(``apps.parametres.i18n_resolver.resolve_langue_sortie`` : langue explicite,
puis préférence du client, puis repli de la société, puis français), mais
AUCUN rendu du module ne l'appelait : la note de calcul code ses libellés en
français dans son HTML.

Ce que ce module fait
=====================
* ``LIBELLES`` — une table ``{code: {'fr': …, 'en': …}}`` des TITRES de section
  et des EN-TÊTES de colonne des documents du module, plus les quelques
  phrases fixes d'impression ; ``libelle(code, langue)`` la lit ;
* ``langue_du_document(calepinage, langue_explicite=None)`` DÉLÈGUE à
  ``resolve_langue_sortie`` — une seconde règle de langue serait une seconde
  vérité ;
* ``resolution_langue(...)`` dit, en plus de la langue SERVIE, celle qui a été
  DEMANDÉE et la mention de repli à poser dans le pied du document.

Ce qui n'est PAS traduit
========================
* l'ARABE n'est pas servi par ce lot (aucun gabarit droite-à-gauche ici) : une
  demande ``ar`` retombe sur le français EN LE DISANT dans le pied du document
  (décision fondateur 9 du 21/09/2026 : « l'arabe plus tard ») ;
* les MOTIFS et avertissements rédigés par le moteur et par le contrat des
  sections restent dans leur langue d'origine (le français) : seuls les
  titres, les en-têtes et les phrases fixes du gabarit sont traduits ;
* l'ATELIER reste en français (D10) — ce module ne concerne que les pièces.
"""
from __future__ import annotations

__all__ = [
    'LANGUES_SERVIES', 'LANGUE_DE_REPLI', 'LIBELLES', 'LibelleInconnu',
    'libelle', 'langue_servie', 'resolution_langue', 'langue_du_document',
    'mention_de_repli', 'libelles_de_garde',
]

#: Les langues RÉELLEMENT servies par les documents du module.
LANGUES_SERVIES = ('fr', 'en')

#: La langue servie quand la langue demandée ne l'est pas.
LANGUE_DE_REPLI = 'fr'

#: Le nom, en français, des langues qu'on peut DEMANDER sans qu'elles soient
#: servies — pour que la mention de repli nomme ce qui a été demandé.
_NOM_LANGUE_DEMANDEE = {'ar': 'arabe'}

#: ``code -> {'fr': …, 'en': …}``. Chaque code du contrat
#: ``contract_samples/rapport_etude.json`` y figure (garde par un test).
LIBELLES = {
    # ── Pièces ────────────────────────────────────────────────────────────
    'rapport_etude': {'fr': "Rapport d'étude", 'en': 'Design report'},
    'note_calcul': {'fr': 'Note de calcul', 'en': 'Calculation note'},
    # CALX317 — le rapport d'ombrage autonome (pièce séparée du rapport
    # d'étude, MÊME titre que le libellé du document CALX291/CALX321).
    'rapport_ombrage': {'fr': "Rapport d'ombrage", 'en': 'Shading report'},

    # ── Sections du rapport d'étude (codes de rapport_etude.json) ─────────
    'garde': {'fr': 'Page de garde', 'en': 'Cover page'},
    'site_meteo': {'fr': 'Site et source météo',
                   'en': 'Site and weather source'},
    'systeme': {'fr': 'Système', 'en': 'System'},
    'pertes': {'fr': 'Chaîne de pertes', 'en': 'Loss chain'},
    'production': {'fr': 'Production', 'en': 'Energy yield'},
    'ombrage': {'fr': 'Ombrage', 'en': 'Shading'},
    'electrique': {'fr': 'Électrique', 'en': 'Electrical'},
    'nomenclature': {'fr': 'Nomenclature', 'en': 'Bill of materials'},
    'preuve': {'fr': 'Régime de preuve et empreinte',
               'en': 'Proof regime and fingerprint'},
    'hypotheses': {'fr': 'Hypothèses, sources et omissions',
                   'en': 'Assumptions, sources and omissions'},

    # ── Page de garde ─────────────────────────────────────────────────────
    'garde_titre_defaut': {'fr': 'Document technique du calepinage',
                           'en': 'Layout technical document'},
    'garde_societe': {'fr': 'Société', 'en': 'Company'},
    'garde_projet': {'fr': 'Projet', 'en': 'Project'},
    'garde_client': {'fr': 'Client', 'en': 'Customer'},
    'garde_adresse': {'fr': 'Adresse du site', 'en': 'Site address'},
    'garde_ville': {'fr': 'Ville', 'en': 'City'},
    'garde_produit_le': {'fr': 'Date de production',
                         'en': 'Date of issue'},
    'garde_empreinte': {'fr': "Empreinte d'entrée",
                        'en': 'Input fingerprint'},
    'garde_version_moteur': {'fr': 'Version du moteur',
                             'en': 'Engine version'},
    'non_renseigne': {'fr': 'non renseigné', 'en': 'not provided'},

    # ── Phrases fixes du rapport ──────────────────────────────────────────
    'donnee_manquante': {'fr': 'Donnée manquante', 'en': 'Missing data'},
    'source_non_renseignee': {'fr': 'source non renseignée',
                              'en': 'source not provided'},

    # ── Chaîne de pertes (en-têtes de colonne) ────────────────────────────
    'col_etape': {'fr': 'Étape', 'en': 'Step'},
    'col_poste': {'fr': 'Poste', 'en': 'Loss item'},
    'col_part': {'fr': 'Part (%)', 'en': 'Share (%)'},
    'col_kwh_avant': {'fr': 'Énergie avant (kWh)',
                      'en': 'Energy in (kWh)'},
    'col_kwh_apres': {'fr': 'Énergie après (kWh)',
                      'en': 'Energy out (kWh)'},
    'col_source': {'fr': 'Source', 'en': 'Source'},
    'total_chaine': {'fr': 'Total de la chaîne', 'en': 'Chain total'},
    'irradiance_incidente': {'fr': 'Irradiance incidente',
                             'en': 'Incident irradiance'},
    'energie_livree': {'fr': 'Énergie livrée', 'en': 'Delivered energy'},
    'poste_omis': {'fr': 'omis', 'en': 'omitted'},
    'gain': {'fr': 'gain', 'en': 'gain'},
}


class LibelleInconnu(KeyError):
    """Un code sans libellé : un défaut de CODE, jamais un blanc imprimé."""


def langue_servie(langue):
    """``langue`` si elle est servie par le module, sinon la langue de repli."""
    return langue if langue in LANGUES_SERVIES else LANGUE_DE_REPLI


def libelle(code, langue='fr'):
    """Le libellé de ``code`` dans la langue SERVIE (``ar`` → français)."""
    try:
        entree = LIBELLES[code]
    except KeyError:
        raise LibelleInconnu(
            "Libellé de document inconnu : « %s » — ajoutez-le à "
            "services/documents/libelles_document.py (fr ET en)." % code
        ) from None
    return entree[langue_servie(langue)]


def mention_de_repli(resolution):
    """La phrase du pied quand la langue demandée n'est pas servie, ou ``''``.

    Elle est écrite dans la langue SERVIE (le français) : c'est celle que le
    lecteur a sous les yeux.
    """
    if not resolution or not resolution.get('repli'):
        return ''
    demandee = resolution.get('demandee') or ''
    nom = _NOM_LANGUE_DEMANDEE.get(demandee, demandee)
    return ('Document demandé en %s : servi en français — la version en %s '
            "n'est pas encore produite par ce module." % (nom, nom))


def _client_du_calepinage(calepinage):
    """Le client du calepinage, LU par le sélecteur du CRM (borné société)."""
    client_id = getattr(calepinage, 'client_id', None)
    company = getattr(calepinage, 'company', None)
    if not client_id or company is None:
        return None
    from apps.crm.selectors import get_company_client

    return get_company_client(company, client_id)


def resolution_langue(calepinage=None, langue_explicite=None):
    """``{langue, demandee, repli, mention}`` — la langue d'une pièce, DITE.

    ``demandee`` est celle que rend ``resolve_langue_sortie`` (langue
    explicite, préférence du client, repli société, français) ; ``langue`` est
    celle que le module SERT ; ``repli`` est vrai quand elles diffèrent, et
    ``mention`` porte alors la phrase du pied.
    """
    from apps.parametres.i18n_resolver import resolve_langue_sortie

    explicite = str(langue_explicite or '').strip().lower() or None
    demandee = resolve_langue_sortie(
        langue_explicite=explicite,
        client=_client_du_calepinage(calepinage),
        company=getattr(calepinage, 'company', None))
    langue = langue_servie(demandee)
    resolution = {'langue': langue, 'demandee': demandee,
                  'repli': langue != demandee}
    resolution['mention'] = mention_de_repli(resolution)
    return resolution


def langue_du_document(calepinage, langue_explicite=None):
    """La langue SERVIE d'un document du calepinage (``fr`` ou ``en``)."""
    return resolution_langue(calepinage, langue_explicite)['langue']


def libelles_de_garde(langue):
    """La table de libellés de la page de garde (``page_de_garde_html``)."""
    return {
        'titre_defaut': libelle('garde_titre_defaut', langue),
        'societe': libelle('garde_societe', langue),
        'projet': libelle('garde_projet', langue),
        'client': libelle('garde_client', langue),
        'adresse': libelle('garde_adresse', langue),
        'ville': libelle('garde_ville', langue),
        'produit_le': libelle('garde_produit_le', langue),
        'empreinte': libelle('garde_empreinte', langue),
        'version_moteur': libelle('garde_version_moteur', langue),
        'non_renseigne': libelle('non_renseigne', langue),
    }
