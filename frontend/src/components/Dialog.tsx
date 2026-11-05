// Fenêtre de dialogue modale, sur l'élément <dialog> natif (SC-17) :
// le focus reste dans la fenêtre et Échap la ferme, sans bibliothèque de plus.

import { useEffect, useId, useRef, type FormEvent, type ReactNode } from 'react'
import { CloseIcon } from './icons'

interface Props {
  open: boolean
  title: string
  description?: ReactNode
  onClose: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  footer: ReactNode
  children?: ReactNode
  size?: 'normal' | 'small'
}

export default function Dialog({ open, title, description, onClose, onSubmit, footer, children, size = 'normal' }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
      // Le premier champ marqué data-autofocus reçoit le focus, sinon le navigateur choisit
      dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className={size === 'small' ? 'dialog dialog-small' : 'dialog'}
      aria-labelledby={titleId}
      onCancel={(event) => {
        // Échap : on passe par onClose pour garder l'état React à jour
        event.preventDefault()
        onClose()
      }}
    >
      {open && (
        <form className="dialog-form" onSubmit={onSubmit} noValidate>
          <div className="dialog-head">
            <div>
              <h2 id={titleId}>{title}</h2>
              {description && <p>{description}</p>}
            </div>
            <button type="button" className="icon-button" onClick={onClose} aria-label="Fermer">
              <CloseIcon />
            </button>
          </div>
          {children && <div className="dialog-body">{children}</div>}
          <div className="dialog-foot">{footer}</div>
        </form>
      )}
    </dialog>
  )
}
