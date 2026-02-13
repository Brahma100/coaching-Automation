import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { FiChevronDown } from 'react-icons/fi';

function Accordion({
  title,
  children,
  defaultOpen = false,
  className = '',
  contentClassName = '',
  flush = false,
  icon = null,
}) {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <div className={`overflow-hidden ${flush ? '' : 'rounded-lg border border-slate-200 bg-slate-50/70'} ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-slate-700 transition ${flush ? 'hover:bg-slate-100' : 'hover:bg-slate-100/70'}`}
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2">
          {icon ? <span className="text-slate-500">{icon}</span> : null}
          {title}
        </span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          className="text-slate-500"
        >
          <FiChevronDown />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className={`border-t border-slate-200 px-3 py-2 ${contentClassName}`}>{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export default Accordion;
