import React from 'react';

function serialize(value) {
  try {
    return JSON.stringify(value ?? {});
  } catch {
    return '';
  }
}

function useDirtyForm(initialState) {
  const [initial, setInitial] = React.useState(initialState);
  const [values, setValues] = React.useState(initialState);

  const isDirty = React.useMemo(() => serialize(values) !== serialize(initial), [values, initial]);

  const reset = React.useCallback((nextState) => {
    setInitial(nextState);
    setValues(nextState);
  }, []);

  return {
    initial,
    values,
    setValues,
    isDirty,
    reset
  };
}

export default useDirtyForm;
