export const getJdEvaluationSummary = (jdEvaluation) =>
  jdEvaluation?.summary || jdEvaluation?.core_requirements || '';

export const getJdEvaluationAdvice = (jdEvaluation) => {
  if (!jdEvaluation) return '';

  const details = [];
  if (jdEvaluation.strategic_advice) {
    details.push(jdEvaluation.strategic_advice);
  } else if (jdEvaluation.years_of_experience) {
    details.push(`Kinh nghiệm yêu cầu: ${jdEvaluation.years_of_experience}`);
  }

  if (Array.isArray(jdEvaluation.missing_info) && jdEvaluation.missing_info.length > 0) {
    details.push(`Thông tin còn thiếu: ${jdEvaluation.missing_info.join(', ')}`);
  }

  return details.join(' | ');
};

export const getSalaryRange = (salaryNegotiation) =>
  salaryNegotiation?.expected_salary_range || salaryNegotiation?.estimated_range || '';

export const getSalaryAdvice = (salaryNegotiation) => {
  if (!salaryNegotiation) return '';

  const details = [];
  if (salaryNegotiation.negotiation_strategy) {
    details.push(salaryNegotiation.negotiation_strategy);
  } else if (salaryNegotiation.market_context) {
    details.push(salaryNegotiation.market_context);
  }

  if (Array.isArray(salaryNegotiation.cv_strengths) && salaryNegotiation.cv_strengths.length > 0) {
    details.push(`Điểm mạnh để deal: ${salaryNegotiation.cv_strengths.join(', ')}`);
  }

  return details.join(' | ');
};

export const getInterviewQuestionNote = (question) =>
  question?.purpose || question?.reason || question?.suggested_answer_strategy || '';
