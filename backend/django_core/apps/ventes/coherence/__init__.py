"""QA-COHERENCE — auditeur d'invariants métier, en lecture seule.

* ``registre``          — règles, tolérances, :class:`Violation` ;
* ``regles_documents``  — chaîne des totaux, liens, statuts, dates, lignes ;
* ``regles_etude``      — chiffres de l'étude (portage du prototype COUV-HOR) ;
* ``regles_crm``        — cohérence funnel ↔ devis (via ``crm.selectors``) ;
* ``regles_securite``   — comptes de démo à mot de passe publié actifs en prod ;
* ``moteur``            — ``run_audit`` (calcul annulé, persistance à part).

Point d'entrée : ``python manage.py audit_coherence`` et la tâche beat
``ventes.audit_coherence_nuit``.
"""


def run_audit(*args, **kwargs):
    """Raccourci paresseux vers :func:`moteur.run_audit` (import au premier
    appel : le paquet reste importable sans charger les modèles)."""
    from .moteur import run_audit as _run
    return _run(*args, **kwargs)
