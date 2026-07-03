import { describe, expect, it } from 'vitest';
import {
  captureWhatsappText,
  caseStudyWhatsappText,
  leadWhatsappText,
  pageContextWhatsappText,
  pageLabelFr,
  regularizationWhatsappText,
  VOICE_NOTE_INVITE,
  whatsappLink,
} from '../src/lib/whatsapp';

describe('whatsappLink', () => {
  it('construit un lien wa.me avec texte encodé', () => {
    const url = whatsappLink('212612345678', 'Bonjour à tous');
    expect(url).toBe('https://wa.me/212612345678?text=Bonjour%20%C3%A0%20tous');
  });

  it('nettoie les caractères non numériques du numéro', () => {
    expect(whatsappLink('+212 6 12 34 56 78', 'x')).toContain('wa.me/212612345678');
  });
});

describe('messages pré-remplis', () => {
  it('le message lead contient nom, ville et bande ROI', () => {
    const text = leadWhatsappText({ fullName: 'Karim', city: 'Rabat', kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans' });
    expect(text).toContain('Karim');
    expect(text).toContain('Rabat');
    expect(text).toContain('5 à 9 kWc');
    expect(text).toContain('4 à 6 ans');
  });

  it('le message régularisation mentionne l’Article 33', () => {
    expect(regularizationWhatsappText()).toContain('Article 33');
  });

  it('ne contient JAMAIS de blancs « ___ » à éditer par le client', () => {
    expect(regularizationWhatsappText()).not.toContain('___');
    expect(regularizationWhatsappText({ kwc: '', ville: '' })).not.toContain('___');
  });

  it('intègre la puissance et la ville du mini-formulaire', () => {
    const msg = regularizationWhatsappText({ kwc: '5.5', ville: 'El Jadida' });
    expect(msg).toContain('Puissance approximative : 5.5 kWc');
    expect(msg).toContain('Ville : El Jadida.');
  });

  it('reste naturel quand la puissance est inconnue', () => {
    const msg = regularizationWhatsappText({ kwc: '', ville: 'Rabat' });
    expect(msg).toContain('Puissance : à déterminer ensemble.');
    expect(msg).toContain('Ville : Rabat.');
  });

  it('rogne les espaces et omet la ville vide, sans « undefined » ni blanc', () => {
    const msg = regularizationWhatsappText({ kwc: '  5  ', ville: '   ' });
    expect(msg).toContain('Puissance approximative : 5 kWc');
    expect(msg).not.toContain('Ville :');
    expect(msg).not.toContain('undefined');
    expect(msg).not.toContain('___');
  });
});

describe('WJ50 — invitation au vocal dans le parcours (captureWhatsappText)', () => {
  it('se termine par l’invitation au vocal, avec ou sans estimation', () => {
    const withEstimate = captureWhatsappText({ fullName: 'Karim', city: 'Rabat', kwcLabel: '5 kWc', savingsLabel: '1 200 MAD/mois' });
    expect(withEstimate).toContain(VOICE_NOTE_INVITE);
    const withoutEstimate = captureWhatsappText({ fullName: 'Sara', city: 'Fès' });
    expect(withoutEstimate).toContain(VOICE_NOTE_INVITE);
  });

  it('ne casse jamais le message : toujours complet, jamais de blanc ni de "undefined"', () => {
    const msg = captureWhatsappText({ fullName: '', city: '' });
    expect(msg).not.toContain('undefined');
    expect(msg).not.toContain('___');
    expect(msg).toContain(VOICE_NOTE_INVITE);
  });
});

describe('WJ50 — pageLabelFr (libellé FR par page, pour les CTA site-wide)', () => {
  it('reconnaît les pages statiques connues', () => {
    expect(pageLabelFr('/financement')).toBe('la page Financement & rentabilité');
    expect(pageLabelFr('/')).toBe("la page d'accueil");
    expect(pageLabelFr('/devis/mon-toit')).toBe('le parcours devis « Mon toit »');
  });

  it('reconnaît les familles de pages dynamiques par préfixe', () => {
    expect(pageLabelFr('/installation-solaire-casablanca')).toContain('Installation solaire par ville');
    expect(pageLabelFr('/realisations/villa-el-jadida-468')).toContain('étude de cas');
    expect(pageLabelFr('/guides/faut-il-des-batteries')).toContain('guide');
    expect(pageLabelFr('/blog/prix-installation-solaire-maroc-2026')).toContain('blog');
  });

  it('retombe sur un libellé neutre pour une page inconnue — jamais un chemin technique', () => {
    const label = pageLabelFr('/une-page-qui-n-existe-pas-encore');
    expect(label).toBe('le site taqinor.ma');
    expect(label).not.toContain('/');
  });

  it('normalise la barre finale et ignore query/hash', () => {
    expect(pageLabelFr('/financement/')).toBe(pageLabelFr('/financement'));
    expect(pageLabelFr('/financement?utm_source=x')).toBe(pageLabelFr('/financement'));
  });
});

describe('WJ50 — pageContextWhatsappText (CTA site-wide StickyCta/Footer)', () => {
  it('cite la page dans le message, sans blanc ni "undefined"', () => {
    const msg = pageContextWhatsappText('/financement');
    expect(msg).toContain('Financement & rentabilité');
    expect(msg).not.toContain('undefined');
    expect(msg).not.toContain('___');
  });

  it('deux pages différentes produisent des messages distinguables (CRM)', () => {
    const a = pageContextWhatsappText('/résidentiel');
    const b = pageContextWhatsappText('/professionnel');
    expect(a).not.toBe(b);
  });

  it('s’encode proprement dans un lien wa.me', () => {
    const url = whatsappLink('212661850410', pageContextWhatsappText('/faq'));
    expect(url).toMatch(/^https:\/\/wa\.me\/212661850410\?text=/);
    expect(decodeURIComponent(url)).toContain('page FAQ');
  });
});

describe('caseStudyWhatsappText (W350 — bouton WhatsApp propre à une étude de cas)', () => {
  it('cite la ville, la puissance et la référence EXACTES de l’étude', () => {
    const msg = caseStudyWhatsappText({ ville: 'El Jadida', kwc: '17,04 kWc', ref: '468' });
    expect(msg).toContain('El Jadida');
    expect(msg).toContain('17,04 kWc');
    expect(msg).toContain('réf. 468');
  });

  it('reste un message complet, jamais de blanc « ___ » à éditer', () => {
    const msg = caseStudyWhatsappText({ ville: 'Casablanca', kwc: '11,36 kWc', ref: '400' });
    expect(msg).not.toContain('___');
    expect(msg).not.toContain('undefined');
  });
});
