"""Copilote vague 2 (B0, 19/11/2026) — contrats de l'assistant du calepinage.

Moitié SERVEUR de la citation exigée par
``scripts/check_contrats_calepinage_deux_moities.py`` (CALX385) : chaque
échantillon neuf de ``contract_samples/`` est cité ici par son nom de fichier,
et côté client par ``frontend/src/features/ia/cartes/contrats.js``
(``CONTRATS_CALEPINAGE_ASSISTANT``, même liste, même ordre). Les tests de la
lane calepinage importent ce tuple pour comparer chaque vue neuve à son
échantillon (PACT10 : le contrat est posé seul, avant les vues).
"""

CONTRATS_ASSISTANT = (
    'calepinage_assistant_resume.json',
    'calepinage_assistant_du_lead.json',
    'calepinage_assistant_a_traiter.json',
    'calepinage_assistant_contenance.json',
    'calepinage_assistant_preparer.json',
    'calepinage_assistant_publier_apercu.json',
    'calepinage_assistant_publier_devis.json',
)
