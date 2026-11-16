document.addEventListener("DOMContentLoaded", () => {
  const workload = document.getElementById("workload_hours");
  const absenceLimit = document.getElementById("max_absence_hours");

  if (!workload || !absenceLimit) {
    return;
  }

  const updateAbsenceLimit = () => {
    const hours = Number.parseInt(workload.value, 10);
    absenceLimit.value = Number.isFinite(hours) && hours > 0
      ? (hours * 0.25).toFixed(2)
      : "";
  };

  workload.addEventListener("input", updateAbsenceLimit);
  updateAbsenceLimit();
});
