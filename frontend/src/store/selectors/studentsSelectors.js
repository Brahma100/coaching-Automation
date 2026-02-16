const pieColors = ['#2f7bf6', '#10b981'];

export const selectStudentsState = (state) => state.students || {};

export const selectStudentsPageState = (state) => {
  const page = selectStudentsState(state);
  const rows = Array.isArray(page.rows) ? page.rows : [];
  const batches = Array.isArray(page.batches) ? page.batches : [];
  const search = String(page.search || '').toLowerCase().trim();
  const batchFilter = String(page.batchFilter || 'all');

  const filteredRows = rows.filter((row) => {
    const text = `${row.name || ''} ${row.phone || ''} ${row.parent_phone || ''}`.toLowerCase();
    const searchMatch = text.includes(search);
    const batchMatch = batchFilter === 'all' ? true : String(row.batch_id) === batchFilter;
    return searchMatch && batchMatch;
  });

  const batchStatsMap = filteredRows.reduce((acc, row) => {
    const key = row.batch || `Batch ${row.batch_id}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const batchChartData = Object.entries(batchStatsMap).map(([name, count]) => ({ name, count }));

  const withParent = filteredRows.filter((row) => (row.parent_phone || '').trim()).length;
  const withoutParent = Math.max(filteredRows.length - withParent, 0);
  const parentPieData = [
    { name: 'Parent Linked', value: withParent },
    { name: 'Missing Parent', value: withoutParent },
  ];

  return {
    ...page,
    rows,
    batches,
    filteredRows,
    batchChartData,
    parentPieData,
    pieColors,
  };
};
