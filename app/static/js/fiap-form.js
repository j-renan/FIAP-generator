document.addEventListener("DOMContentLoaded", () => {
  const studentSelector = document.querySelector(".fiap-student-selector");
  const classSelect = document.getElementById("class_id");
  const studentSelect = document.getElementById("student_id");
  const status = document.getElementById("student-loading-status");

  if (studentSelector && classSelect && studentSelect && status) {
    const placeholder = new Option("Selecione um aluno", "0");

    async function loadStudents(classId) {
      studentSelect.replaceChildren(placeholder.cloneNode(true));
      studentSelect.disabled = true;
      status.textContent = "";

      if (!classId || classId === "0") {
        status.textContent = "Selecione uma turma para carregar os alunos.";
        return;
      }

      status.textContent = "Carregando alunos...";
      const url = new URL(studentSelector.dataset.studentsUrl, window.location.origin);
      url.searchParams.set("class_id", classId);

      try {
        const response = await fetch(url, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          status.textContent = "Não foi possível carregar os alunos desta turma.";
          return;
        }

        const students = await response.json();
        for (const student of students) {
          studentSelect.add(new Option(student.name, String(student.id)));
        }
        studentSelect.disabled = students.length === 0;
        status.textContent = students.length
          ? `${students.length} aluno(s) carregado(s).`
          : "Esta turma ainda não possui alunos cadastrados.";
      } catch (error) {
        status.textContent = "Erro de conexão ao carregar os alunos. Tente novamente.";
      }
    }

    classSelect.addEventListener("change", () => {
      loadStudents(classSelect.value);
    });
  }

  const unitSelector = document.querySelector(".fiap-unit-selector");
  const unitSelect = document.getElementById("curricular_unit_id");
  const absenceLimit = document.getElementById("absence_limit_hours");

  if (unitSelector && unitSelect && absenceLimit) {
    const absenceLimits = JSON.parse(unitSelector.dataset.absenceLimits);
    const updateAbsenceLimit = () => {
      absenceLimit.value = absenceLimits[unitSelect.value] || "";
    };

    unitSelect.addEventListener("change", updateAbsenceLimit);
    updateAbsenceLimit();
  }
});
