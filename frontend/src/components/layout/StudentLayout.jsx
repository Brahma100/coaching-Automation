import React from 'react';
import { Outlet } from 'react-router-dom';

function StudentLayout() {
  return <Outlet />;
}

export default React.memo(StudentLayout);
