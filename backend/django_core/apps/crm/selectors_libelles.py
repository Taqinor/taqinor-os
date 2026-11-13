"""COP-G4 — libellés des objets CRM nommés dans l'aperçu d'une proposition
(lead, touche de suivi, client), pour ``GET /api/django/agent/libelles/``.

Lecture seule, bornée à la SOCIÉTÉ et à la PORTÉE de l'utilisateur (mêmes
sélecteurs que les écrans : ``leads_visibles``, ``scope_client_queryset``). Un
objet inconnu, d'une autre société ou hors portée est simplement ABSENT du
résultat — jamais une erreur, jamais un indice de son existence. Aucun
téléphone, aucune adresse e-mail : un nom, une ville, un libellé de touche.
"""
from core.formats_fr import formater_date


def _nom_complet(prenom, nom):
    return ' '.join(p for p in ((prenom or '').strip(), (nom or '').strip()) if p)


def _libelle_lead(lead):
    """« Aziz Benali — Casablanca » (la ville seulement si elle est connue)."""
    nom = _nom_complet(lead.prenom, lead.nom)
    ville = (lead.ville or '').strip()
    return f'{nom} — {ville}' if nom and ville else (nom or ville)


def _libelle_touche(etape):
    """« Aziz Benali — Relance J+1 (WhatsApp, prévue le 14/11/2026) »."""
    nom = _nom_complet(etape.lead.prenom, etape.lead.nom)
    titre = (etape.libelle or '').strip() or f'Touche n° {etape.ordre}'
    detail = f'{etape.get_canal_display()}, prévue le {formater_date(etape.due_date)}'
    return f'{nom} — {titre} ({detail})' if nom else f'{titre} ({detail})'


def _libelle_client(client):
    """« Benali Aziz » (nom puis prénom, comme la liste des clients)."""
    return _nom_complet(client.nom, client.prenom)


def libelles_crm(user, *, lead=None, touche=None, client=None):
    """``{'lead': …, 'touche': …, 'client': …}`` pour les identifiants donnés
    qui existent dans la société ET la portée de ``user`` (les autres clés
    manquent). Un utilisateur sans société ne voit rien."""
    from authentication.scoping import scope_client_queryset

    from .clients_selectors import client_base_qs
    from .models import RelanceEtape
    from .portee_selectors import leads_visibles

    societe = getattr(user, 'company', None)
    if societe is None:
        return {}
    visibles = leads_visibles(user, societe)
    out = {}
    if lead:
        trouve = visibles.filter(pk=lead).only(
            'id', 'prenom', 'nom', 'ville').first()
        if trouve is not None:
            out['lead'] = _libelle_lead(trouve)
    if touche:
        etape = (RelanceEtape.objects.filter(
            pk=touche, company=societe, lead_id__in=visibles.values('id'))
            .select_related('lead').first())
        if etape is not None:
            out['touche'] = _libelle_touche(etape)
    if client:
        trouve = scope_client_queryset(
            client_base_qs(societe), user).filter(pk=client).first()
        if trouve is not None:
            out['client'] = _libelle_client(trouve)
    return out
