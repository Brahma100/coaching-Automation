export const selectBatchesState = (state) => state.batches || {};

export const selectBatchesPageState = (state) => {
  const page = selectBatchesState(state);
  const batches = Array.isArray(page.batches) ? page.batches : [];
  const students = Array.isArray(page.students) ? page.students : [];
  const batchStudents = Array.isArray(page.batchStudents) ? page.batchStudents : [];
  const selectedBatchId = Number(page.selectedBatchId || 0) || null;
  const selectedBatch = batches.find((row) => Number(row.id) === selectedBatchId) || null;
  const schedules = Array.isArray(selectedBatch?.schedules) ? selectedBatch.schedules : [];
  const linkedStudentIds = new Set(batchStudents.map((row) => Number(row.student_id)));
  const availableStudents = students.filter((row) => !linkedStudentIds.has(Number(row.id)));
  const chartData = batches.map((row) => ({ name: row.name, students: Number(row.student_count || 0) }));
  const activeCount = batches.filter((row) => row.active).length;
  const inactiveCount = Math.max(batches.length - activeCount, 0);

  return {
    ...page,
    batches,
    students,
    batchStudents,
    selectedBatchId,
    selectedBatch,
    schedules,
    availableStudents,
    chartData,
    activeCount,
    inactiveCount,
  };
};
