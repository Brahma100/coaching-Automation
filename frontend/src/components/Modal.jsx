import React from 'react';

function Modal({
  open,
  title,
  children,
  onClose,
  footer,
  closeButtonText = 'Close',
  closeButtonAriaLabel = 'Close',
  overlayClassName = '',
  panelClassName = '',
  headerClassName = '',
  titleClassName = '',
  closeButtonClassName = '',
  bodyClassName = '',
  footerClassName = ''
}) {
  if (!open) {
    return null;
  }

  return (
    <div className={`fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 px-3 py-4 ${overlayClassName}`.trim()}>
      <div className="flex min-h-full items-center justify-center">
        <div className={`flex max-h-[92vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900 ${panelClassName}`.trim()}>
        <div className={`flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-700 ${headerClassName}`.trim()}>
          <h3 className={`text-lg font-bold text-slate-900 dark:text-slate-100 ${titleClassName}`.trim()}>{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeButtonAriaLabel}
            className={`rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 ${closeButtonClassName}`.trim()}
          >
            {closeButtonText}
          </button>
        </div>
        <div className={`overflow-y-auto px-5 py-4 text-slate-700 dark:text-slate-200 ${bodyClassName}`.trim()}>{children}</div>
        {footer ? <div className={`border-t border-slate-200 px-5 py-4 dark:border-slate-700 ${footerClassName}`.trim()}>{footer}</div> : null}
      </div>
      </div>
    </div>
  );
}

export default Modal;
