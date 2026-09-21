"""Export DPEF-friendly (NTESG14) — gabarit texte structuré, PAS un PDF
officiel homologué.

À partir d'une période figée (ou en aperçu live, NTESG1/2), génère un
export Markdown structuré suivant les 4 rubriques classiques d'une
déclaration de performance extra-financière : modèle d'affaires, risques
ESG principaux, politiques et résultats, indicateurs clés. Pré-rempli avec
les données ERP disponibles ; les sections narratives qualitatives que
l'ERP ne peut pas générer seul restent explicitement marquées « à
compléter manuellement ». Bandeau permanent : brouillon de travail, ne
constitue pas une DPEF déposée.
"""

BANDEAU = (
    'Brouillon de travail — ne constitue pas une DPEF déposée. Généré '
    'automatiquement à partir des données ERP disponibles ; les sections '
    'narratives qualitatives restent à compléter manuellement.')

A_COMPLETER_MODELE_AFFAIRES = (
    "À compléter manuellement — l'ERP ne génère pas de narratif qualitatif "
    'sur le modèle d\'affaires.')
A_COMPLETER_RISQUES = (
    'À compléter manuellement — déclarer ici les risques ESG jugés '
    'principaux par la direction.')


def _documents_politique_publies(company):
    """Documents de politique RSE PUBLIÉS de la société (NTESG13), triés par
    date de publication décroissante — jamais un document brouillon/obsolète
    (seule une politique effectivement publiée constitue une preuve
    documentaire opposable dans une DPEF)."""
    from .models import DocumentPolitiqueESG

    if company is None:
        return []
    return list(
        DocumentPolitiqueESG.objects.filter(
            company=company, statut=DocumentPolitiqueESG.Statut.PUBLIEE)
        .order_by('-date_publication'))


def _section_modele_affaires():
    return ['## 1. Modèle d\'affaires', '', A_COMPLETER_MODELE_AFFAIRES, '']


def _section_risques():
    return ['## 2. Risques ESG principaux', '', A_COMPLETER_RISQUES, '']


def _section_politiques_resultats(company):
    lignes = ['## 3. Politiques et résultats', '']
    documents = _documents_politique_publies(company)
    if not documents:
        lignes.append(
            "_Aucun document de politique RSE publié à ce jour "
            '(voir le registre NTESG13)._')
    else:
        for doc in documents:
            revue = (
                f' (dernière revue le {doc.date_revue})'
                if doc.date_revue else '')
            lignes.append(
                f'- {doc.get_type_document_display()} — « {doc.libelle} » — '
                f'publiée le {doc.date_publication or "date non renseignée"}'
                f'{revue}')
    lignes.append('')
    return lignes


def _section_indicateurs_cles(sources):
    lignes = ['## 4. Indicateurs clés', '']
    indic = sources.get('indicateurs_esg') or {}
    if not indic.get('disponible'):
        lignes.append(
            '_Aucun indicateur ESG disponible pour cette période._')
        lignes.append('')
        return lignes
    for pilier, bloc in (indic.get('piliers') or {}).items():
        lignes_pilier = [
            ligne for ligne in (bloc.get('lignes') or [])
            if ligne.get('valeur') is not None
        ]
        if not lignes_pilier:
            continue
        lignes.append(f'### {pilier.capitalize()}')
        for ligne in lignes_pilier:
            unite = f" {ligne.get('unite')}" if ligne.get('unite') else ''
            lignes.append(
                f"- {ligne.get('libelle')} : {ligne.get('valeur')}{unite}")
        lignes.append('')
    return lignes


def generer_dpef_texte(periode_esg):
    """Génère le gabarit DPEF-friendly (Markdown) d'une période ESG (NTESG14).

    Réutilise ``selectors.donnees_effectives_periode`` (snapshot gelé si
    figée, aperçu live sinon) — jamais un recalcul d'une période déjà
    figée."""
    from .selectors import donnees_effectives_periode

    donnees = donnees_effectives_periode(periode_esg)
    sources = donnees.get('sources', {})
    company_nom = getattr(periode_esg.company, 'nom', '') or ''

    lignes = [
        '# Déclaration de performance extra-financière (brouillon de '
        'travail)', '',
        f'> **{BANDEAU}**', '',
        f'Société : {company_nom}',
        f'Période : {periode_esg.libelle} '
        f'({periode_esg.date_debut} — {periode_esg.date_fin})',
        '',
    ]
    lignes += _section_modele_affaires()
    lignes += _section_risques()
    lignes += _section_politiques_resultats(periode_esg.company)
    lignes += _section_indicateurs_cles(sources)

    return '\n'.join(lignes)
