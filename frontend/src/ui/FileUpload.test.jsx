import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { FileUpload } from './FileUpload'

/* ERR-QAH-GED-UPLOAD-TXT-SILENT-REJECT — le glisser-déposer d'un type de
   fichier non accepté doit produire le MÊME retour (onReject → toast) que le
   sélecteur de fichier (`<input type="file">`) : la dropzone appelle `handle`
   pour les deux chemins, donc un fichier .txt déposé sur une zone
   « PDF · PNG · JPEG · WEBP » doit être rejeté avec un message explicite,
   jamais silencieusement (bouton grisé sans aucun retour). */

afterEach(() => cleanup())

const ACCEPT = 'application/pdf,image/png,image/jpeg,image/webp'

describe('FileUpload — retour identique glisser-déposer et sélecteur', () => {
  it('glisser-déposer un .txt refusé appelle onReject avec le même message que le sélecteur', () => {
    const onFiles = vi.fn()
    const onReject = vi.fn()
    render(<FileUpload accept={ACCEPT} onFiles={onFiles} onReject={onReject} />)

    const zone = screen.getByRole('button')
    const file = new File(['contenu'], 'notes.txt', { type: 'text/plain' })
    fireEvent.drop(zone, { dataTransfer: { files: [file] } })

    expect(onFiles).not.toHaveBeenCalled()
    expect(onReject).toHaveBeenCalledTimes(1)
    const [rejected] = onReject.mock.calls[0]
    expect(rejected).toHaveLength(1)
    expect(rejected[0].error).toBe('Type de fichier non autorisé (notes.txt).')
  })

  it('le sélecteur de fichier produit le même message de refus (référence)', () => {
    const onFiles = vi.fn()
    const onReject = vi.fn()
    render(<FileUpload accept={ACCEPT} onFiles={onFiles} onReject={onReject} />)

    const input = document.querySelector('input[type="file"]')
    const file = new File(['contenu'], 'notes.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })

    expect(onFiles).not.toHaveBeenCalled()
    expect(onReject).toHaveBeenCalledTimes(1)
    expect(onReject.mock.calls[0][0][0].error).toBe('Type de fichier non autorisé (notes.txt).')
  })

  it('glisser-déposer un fichier accepté appelle onFiles', () => {
    const onFiles = vi.fn()
    const onReject = vi.fn()
    render(<FileUpload accept={ACCEPT} onFiles={onFiles} onReject={onReject} />)

    const zone = screen.getByRole('button')
    const file = new File(['%PDF-1.4'], 'facture.pdf', { type: 'application/pdf' })
    fireEvent.drop(zone, { dataTransfer: { files: [file] } })

    expect(onReject).not.toHaveBeenCalled()
    expect(onFiles).toHaveBeenCalledTimes(1)
    expect(onFiles.mock.calls[0][0][0].name).toBe('facture.pdf')
  })
})
