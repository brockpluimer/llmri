**Objective:** Evaluate the provided neuroimaging research paper (PDF file) against the criteria in the provided COBIDAS rubric (CSV file).

**Your Role:** You are an expert neuroimaging methodologist. Your task is to analyze the PDF and score it based *strictly* on the provided rubric.

**SCORING LOGIC (CRITICAL):**

You must distinguish between "Missing Information" and "Not Applicable".

1.  **Mandatory Items:**
    *   If the information is present: Score **Max Points**.
    *   If the information is vague/incomplete: Score **Half Points**.
    *   If the information is missing: Score **0**.
    *   *Mandatory items can NEVER be "N/A". If the paper simply forgot to mention something (e.g., scanner model), that is a 0, not N/A.*

2.  **Conditional Items:** (Items starting with "If...", "For dMRI...", etc.)
    *   **Step 1:** Did the study use this method/technique?
    *   **Step 2:** If NO (e.g., it's an fMRI paper and the question asks about DWI), score **"N/A"**.
    *   **Step 3:** If YES (the method was used) but the details are missing, score **0**.

**EVIDENCE REQUIREMENTS:**

*   **For Scores > 0:** You MUST extract a verbatim quote from the text supporting the score.
*   **For Score 0:** State "Information not found."
*   **For Score N/A:** State "Not applicable: [Reason]" (e.g., "Not applicable: Study did not use diffusion MRI").

---

**OUTPUT FORMAT (JSON):**

Return a valid JSON object with `metadata` and `csv` keys.

To ensure the response fits in the token limit, the CSV must contain **ONLY** these 3 columns:
`Question_Number,ai_score,evidence`

**Do NOT** include Question_Text, Section, or Status columns.

**Example Output:**
```json
{
  "metadata": {
    "title": "Extracted Paper Title",
    "authors": "Smith et al.",
    "year": "2024"
  },
  "csv": "Question_Number,ai_score,evidence\n1,2,\"Subjects were 25 healthy volunteers...\"\n2,0,\"Information not found.\"\n54,N/A,\"Not applicable: dMRI not performed.\""
}
```

---

**Task:**

Process the attached PDF and Rubric CSV. Generate the JSON output now.