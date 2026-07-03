"""QD2 — Un seul helper de nom de fichier pour les documents téléchargés.

Le nom public d'une facture était ``Facture_FAC-202607-0001.pdf`` (redondant,
sans contexte client) ; les autres chemins servaient ``{reference}.pdf`` — donc
incohérent. On centralise ici la construction d'un nom propre et cohérent :

    TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf
    (société _ type _ client _ référence, slugifié, .pdf)

Le nom ne contient JAMAIS de prix d'achat/marge (juste des libellés publics).
Les segments manquants (client/société inconnus) sont simplement omis — le nom
dégrade proprement vers ``Facture_FAC-202607-0001.pdf`` puis ``document.pdf``.
"""
import re
import unicodedata


def _slug(value, keep_case=True):
    """Slugifie un segment pour un nom de fichier sûr (ASCII, tirets).

    Les accents sont retirés, les espaces/séparateurs deviennent des tirets, et
    tout caractère non alphanumérique est écarté. Les tirets multiples sont
    compactés. Renvoie '' si rien d'exploitable."""
    if not value:
        return ''
    text = str(value).strip()
    # Décompose les accents puis retire les diacritiques (é → e).
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    if not keep_case:
        text = text.lower()
    # Remplace tout ce qui n'est pas alphanumérique par un tiret.
    text = re.sub(r'[^A-Za-z0-9]+', '-', text)
    text = re.sub(r'-{2,}', '-', text).strip('-')
    return text


def _company_slug(company):
    """Nom court de la société pour préfixer le fichier (profil > nom brut)."""
    if company is None:
        return ''
    nom = ''
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=company)
        nom = getattr(profile, 'nom', '') or ''
    except Exception:  # noqa: BLE001 — repli sur le nom brut de la société
        nom = ''
    if not nom:
        nom = getattr(company, 'nom', '') or ''
    return _slug(nom)


def _client_slug(client):
    """Nom du client pour le fichier (prénom + nom quand disponibles)."""
    if client is None:
        return ''
    prenom = (getattr(client, 'prenom', '') or '').strip()
    nom = (getattr(client, 'nom', '') or '').strip()
    full = f'{prenom} {nom}'.strip() if prenom else nom
    if not full:
        full = str(client)
    return _slug(full)


def document_filename(type_label, reference, *, client=None, company=None,
                      ext='pdf'):
    """Construit un nom de fichier cohérent pour un document téléchargé.

    Forme : ``<Société>_<Type>_<Client>_<Référence>.<ext>`` — chaque segment
    slugifié, les segments vides omis. Toujours au moins la référence (repli
    ``document`` si elle manque aussi)."""
    parts = [
        _company_slug(company),
        _slug(type_label),
        _client_slug(client),
        _slug(reference),
    ]
    stem = '_'.join(p for p in parts if p) or 'document'
    ext = (ext or 'pdf').lstrip('.')
    return f'{stem}.{ext}'
