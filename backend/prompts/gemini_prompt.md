**Objective:** Evaluate the provided neuroimaging research paper (PDF file) against the criteria in the provided COBIDAS rubric (CSV file) and output the results in CSV format. Note that the pdf may contain supplementary documentation that succeeds the initial article.

**Your Role:** You are an expert research assistant specialized in neuroimaging methodology and reporting standards. Your task is to meticulously analyze the content of the provided PDF paper and score it based on the criteria listed in the provided `cobidas_rubric.csv` file.

**Inputs:**

1.  **COBIDAS Rubric File:** `cobidas_rubric.csv` (This file, which I have uploaded, contains `Question_Number`, `Status`, `Section`, `Question_Text`, and `Maximum_Score`).
2.  **Research Paper File:** This pdf file, which I have uploaded, contains the research paper to be evaluated. You will need to process this PDF to access its text content.

**Scoring Instructions:**

For each item (`Question_Number`) in the rubric CSV file:

1.  **Relevance:** Determine if the question is relevant to the study described in the paper.
    *   For **Conditional** items: If the condition described in the question (e.g., "If used...", "For dMRI...") does not apply to the study described in the paper, assign the score `N/A`.
    *   For **Mandatory** items: These must always receive a numerical score (Full, Half, or Zero). Even if the technique seems inapplicable (e.g., asking about motion correction for a structural-only analysis paper), score based on whether the paper *addresses* it (e.g., by stating it wasn't needed/done or by simply omitting it).
2.  **Analysis:** Carefully read the `Question_Text` from the rubric file and search the text content of the **PDF Paper File** for information that addresses this specific point.
3.  **Scoring (Assign `ai_score`):**
    *   **Full Points (`Maximum_Score`):** Award the full `Maximum_Score` if the paper *fully and explicitly* addresses all aspects of the `Question_Text`.
    *   **Half Points (`Maximum_Score / 2`):** Award half of the `Maximum_Score` (use integer division, e.g., 1 point for a 2-point question; 0 points for a 1-point question unless *significant* partial info warrants 0.5, but aim for 0 or 1) if the paper *partially addresses* the `Question_Text` (e.g., some details provided but incomplete).
    *   **Zero Points (0):** Award 0 points if the paper *does not address* the `Question_Text` at all, or the information is grossly insufficient. This applies to Mandatory items where the required information is missing.
    *   **N/A:** Assign `N/A` only for **Conditional** items where the condition is not met by the study (e.g., asking about dMRI processing in an fMRI-only paper).
4.  **Evidence (Assign `evidence`):**
    *   If scoring Full or Half points, **quote the exact sentence(s) or specific phrase(s)** from the **PDF Paper File** that contain the relevant information. Use quotation marks ("...") around the cited text. Ensure the quote directly supports the score given.
    *   If scoring Zero points, state: "Information not found."
    *   If assigning `N/A` (for Conditional items only), state: "Not applicable: [Brief reason, e.g., dMRI not used, No clinical instruments reported]."

**Output Format:**

Produce a single CSV formatted string as your output. The CSV should include the original columns from the rubric file (`cobidas_rubric.csv`) plus the new `ai_score` and `evidence` columns. Ensure proper CSV formatting (use double quotes around fields containing commas, newlines, or double quotes; escape internal double quotes with `""`).

The header row **must** be exactly:
`Question_Number,Status,Section,Question_Text,Maximum_Score,ai_score,evidence`

**Example Rows (Illustrative):**

`2,Mandatory,"Experimental Design Reporting","Is the age (mean, standard deviation, and range) of subjects provided?",2,2,"""Participants included 30 healthy adults (mean age = 25.3 years, SD = 4.1, range = 19-35 years)."""`
`4,Mandatory,"Experimental Design Reporting","Are the education level and/or socioeconomic status (SES) of subjects described?",1,0,"Information not found."`
`54,Conditional,"Preprocessing Reporting","For dMRI, is the method used for eddy current correction described?",1,"N/A","Not applicable: dMRI not used."`
`62,Conditional,Preprocessing Reporting,Is the spatial smoothing kernel size (FWHM) and method reported?,2,2,"""Data were smoothed using a 6 mm FWHM Gaussian kernel."""`

**Process:**

1.  Read and understand the structure of the `cobidas_rubric.csv` file provided.
2.  Extract and thoroughly read the text content from the provided PDF paper file.
3.  Systematically evaluate the paper against each `Question_Number` in the rubric.
4.  Apply the scoring (Full/Half/Zero/N/A) and evidence-gathering instructions precisely. Base your answers *only* on information explicitly present in the PDF text. Do not infer information not stated.
5.  Format the final result as a single CSV string with the specified header and columns.
6.  Provide the output as a downloadable file named "paper_name_gemini.csv" where "paper_name" is the string preceding `.pdf` in the input PDF filename (e.g., if the input is `Bach_et_al_2019.pdf`, the output file should be `Bach_et_al_2019_gemini.csv`).

**Now, please process the uploaded `cobidas_rubric.csv` file and the PDF paper file, then generate the scoring results in the specified CSV format and provide it as the requested file.**
