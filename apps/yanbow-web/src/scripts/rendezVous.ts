/**
 * Comportement du formulaire « Prendre rendez-vous » (YBW55).
 *
 * - Les valeurs sont normalisées par le registre (`normaliserDemande`), jamais
 *   refusées pour leur mise en forme ; les mêmes règles tournent côté serveur.
 * - Chaque erreur s'affiche SOUS son champ (`aria-invalid` + message lié par
 *   `aria-describedby`) et est NOMMÉE dans un bandeau (lien vers le champ).
 * - Envoi JSON en POST vers `/api/rendez-vous` : aucune donnée dans l'URL,
 *   aucun stockage navigateur, aucun cookie. `idempotency_key` est tirée UNE
 *   fois par saisie : un double clic ou un nouvel essai ne crée pas deux leads.
 * - Les paramètres `utm_*` de l'adresse sont LUS (jamais écrits) et joints.
 */
import { CLES_CHAMPS, POT_DE_MIEL, messageErreur, normaliserDemande, type CleChamp } from '../lib/rdv/champs';

type Libelles = Partial<Record<CleChamp, string>>;

function cleAleatoire(): string {
  return crypto.randomUUID();
}

function initialiser(form: HTMLFormElement): void {
  const langue = form.dataset.langue === 'en' ? 'en' : 'fr';
  const libelles = JSON.parse(form.dataset.libelles || '{}') as Libelles;
  const bandeau = form.querySelector<HTMLElement>('[data-bandeau]');
  const liste = form.querySelector<HTMLElement>('[data-bandeau-liste]');
  const bouton = form.querySelector<HTMLButtonElement>('[data-envoyer]');
  const bloc = form.closest<HTMLElement>('[data-rendez-vous-bloc]');
  const succes = bloc?.querySelector<HTMLElement>('[data-succes]') ?? null;
  let cle = cleAleatoire();
  let enCours = false;

  const champ = (nom: string) => form.elements.namedItem(nom) as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | null;

  function effacer(): void {
    for (const p of form.querySelectorAll<HTMLElement>('[data-erreur-pour]')) {
      p.textContent = '';
      p.hidden = true;
    }
    for (const el of form.querySelectorAll('[aria-invalid]')) el.removeAttribute('aria-invalid');
    if (liste) liste.textContent = '';
    if (bandeau) bandeau.hidden = true;
  }

  /** Affiche des erreurs par champ (+ une erreur générale `envoi`) et le bandeau. */
  function afficher(erreurs: Record<string, string>): void {
    effacer();
    if (!bandeau || !liste) return;
    for (const [nom, message] of Object.entries(erreurs)) {
      const li = document.createElement('li');
      const p = form.querySelector<HTMLElement>(`[data-erreur-pour="${nom}"]`);
      const el = champ(nom);
      if (p && el) {
        p.textContent = message;
        p.hidden = false;
        el.setAttribute('aria-invalid', 'true');
        const a = document.createElement('a');
        a.href = `#${el.id}`;
        a.textContent = libelles[nom as CleChamp] ?? nom;
        a.addEventListener('click', (e) => {
          e.preventDefault();
          el.focus();
        });
        li.append(a);
      } else {
        li.textContent = message;
      }
      liste.append(li);
    }
    bandeau.hidden = false;
    bandeau.focus();
  }

  function occupe(oui: boolean): void {
    enCours = oui;
    if (!bouton) return;
    bouton.disabled = oui;
    bouton.textContent = (oui ? form.dataset.texteEnvoi : form.dataset.texteEnvoyer) ?? '';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (enCours) return;
    const valeur = (nom: string) => champ(nom)?.value ?? '';
    const consentement = (champ('consentement') as HTMLInputElement | null)?.checked === true;
    const params = new URLSearchParams(location.search);
    const brut: Record<string, unknown> = {
      idempotency_key: cle,
      nom: valeur('nom'),
      societe: valeur('societe'),
      email: valeur('email'),
      telephone: valeur('telephone'),
      produit: valeur('produit'),
      message: valeur('message'),
      langue,
      consentement,
      page: location.pathname,
      [POT_DE_MIEL]: valeur(POT_DE_MIEL),
    };
    for (const k of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']) {
      const v = params.get(k);
      if (v) brut[k] = v;
    }

    const { erreurs } = normaliserDemande(brut, new Date(), () => cle);
    const locales: Record<string, string> = {};
    for (const k of CLES_CHAMPS) {
      const code = erreurs[k];
      if (code) locales[k] = messageErreur(k, code, langue);
    }
    if (Object.keys(locales).length > 0) {
      afficher(locales);
      return;
    }

    occupe(true);
    try {
      const r = await fetch('/api/rendez-vous', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(brut),
        credentials: 'same-origin',
      });
      const corps = (await r.json().catch(() => ({}))) as { ok?: boolean; erreurs?: Record<string, string> };
      if (r.ok && corps.ok) {
        effacer();
        cle = cleAleatoire();
        form.reset();
        form.hidden = true;
        if (succes) {
          succes.hidden = false;
          succes.focus();
        }
        return;
      }
      if (r.status === 429) {
        afficher({ envoi: form.dataset.texteLimite ?? '' });
        return;
      }
      afficher(corps.erreurs && Object.keys(corps.erreurs).length > 0 ? corps.erreurs : { envoi: form.dataset.texteReseau ?? '' });
    } catch {
      afficher({ envoi: form.dataset.texteReseau ?? '' });
    } finally {
      occupe(false);
    }
  });
}

for (const form of document.querySelectorAll<HTMLFormElement>('form[data-rendez-vous]')) initialiser(form);
