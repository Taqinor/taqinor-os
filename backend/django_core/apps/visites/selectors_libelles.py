"""Copilote vague 2 — libellé des visites nommées dans l'aperçu d'une
proposition de l'assistant, pour ``GET /api/django/agent/libelles/`` et
``erp.ouvrir`` (résolveur ``libelles_visites`` de la table
``apps/agent/libelles.py`` : l'écran « visite » et « calage du toit » ne sont
offerts au modèle que parce que ce module existe).

Lecture seule, bornée à la SOCIÉTÉ et à la PORTÉE de l'écran
(``selectors.visites_visibles`` : « mes visites » pour un terrain, l'équipe
pour un valideur) et au droit de LIRE les visites. Une visite inconnue,
d'une autre société ou hors portée est ABSENTE du résultat — jamais une
erreur, jamais un indice de son existence. Un nom, une ville, une date, le nom
de la personne qui fait la visite et son statut : ni téléphone, ni adresse, ni
texte saisi sur le terrain (les mots du terrain sont du contenu tiers, jamais
mêlés à une ligne que le modèle lit comme un titre).
"""
from core.formats_fr import formater_date


def _nom_complet(prenom, nom):
    return ' '.join(p for p in ((prenom or '').strip(), (nom or '').strip()) if p)


def _libelle_visite(visite):
    """« Visite du 21/11/2026 — Aziz Benali (Bouskoura), Youssef Alami
    (brouillon) » : la date, le client, QUI fait la visite (« sans technicien »
    si personne) et son statut — ce qu'un valideur doit voir avant de
    confirmer, y compris quand il valide la visite dont il est l'assigné."""
    quand = ('Visite du ' + formater_date(visite.date_prevue)
             if visite.date_prevue else 'Visite sans date')
    lead = visite.lead
    client = _nom_complet(lead.prenom, lead.nom)
    ville = (lead.ville or '').strip()
    client = f'{client} ({ville})' if client and ville else (client or ville)
    commercial = visite.commercial
    qui = ((commercial.get_full_name() or commercial.username).strip()
           if commercial is not None else 'sans technicien')
    statut = visite.get_statut_display().lower()
    return f'{quand} — {client}, {qui} ({statut})' if client \
        else f'{quand}, {qui} ({statut})'


def libelles_visites(user, *, visite=None):
    """``{'visite': …}`` pour l'identifiant donné s'il existe dans la société
    ET la portée de ``user`` (la clé manque sinon). Un utilisateur sans
    société, ou sans le droit de LIRE les visites (``visites_voir``, la garde
    du viewset), ne voit rien."""
    from core.permissions import _user_has_or_legacy

    from .selectors import visites_visibles

    if (not visite or getattr(user, 'company_id', None) is None
            or not _user_has_or_legacy(user, 'visites_voir')):
        return {}
    trouvee = visites_visibles(user).filter(pk=visite).first()
    return {} if trouvee is None else {'visite': _libelle_visite(trouvee)}
