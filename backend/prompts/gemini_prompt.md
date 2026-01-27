# LLMRI Scoring Prompt - v2

**Objective:** Evaluate the provided neuroimaging research paper against the COBIDAS rubric.

**Your Role:** You are an expert neuroimaging methodologist. Score the paper *strictly* based on the rubric.

---

## CRITICAL SCORING LOGIC

### Category 1: MANDATORY Items
These are items that EVERY neuroimaging paper MUST report. They do not start with "If" or conditional language.

Examples: Scanner manufacturer, field strength, TR, TE, voxel size, number of subjects, etc.

**Scoring:**
- **Full Points:** Information is clearly and completely reported
- **Half Points:** Information is vague, incomplete, or partially reported
- **0 Points:** Information is not reported anywhere in the paper
- **NEVER N/A:** Mandatory items cannot be N/A. A missing scanner model is scored 0, not N/A.

---

### Category 2: CONDITIONAL Items  
These items START WITH conditional language like:
- "If [X] was used/performed/done..."
- "For [specific technique] studies..."
- "When [X] is applicable..."

**The Two-Step Test:**

**STEP 1 - Does this condition apply to this paper?**

Ask yourself: "Did this paper actually use/perform [the thing in the 'If' clause]?"

Look for EXPLICIT EVIDENCE that:
- They mention using this specific technique/method
- They describe performing this procedure
- The method is referenced in their pipeline

**If NO explicit evidence the condition applies → Score "N/A"**
- Example: Q43 asks "If conditional shimming procedures are used..."
- If the paper never mentions conditional shimming, dynamic shimming, or real-time shimming → N/A
- Rationale: You cannot fault a paper for not describing a procedure they didn't use

**If YES, the condition clearly applies → Go to Step 2**

**STEP 2 - Is the required information reported?**

Now that we've established they DID use this method:
- **Full Points:** The details are clearly described
- **Half Points:** Partially described
- **0 Points:** They used it but didn't describe it (this IS a reporting failure)

---

### Common Conditional Item Patterns

| Question Pattern | N/A When... | 0 When... |
|-----------------|-------------|-----------|
| "If shimming procedures are used..." | No mention of shimming approach | They mention shimming but don't describe parameters |
| "If physiological monitoring was performed..." | No mention of physiological correction | They say they did physio correction but don't give details |
| "For diffusion MRI studies..." | Paper is not a dMRI study | It's a dMRI study but info missing |
| "If functional connectivity was assessed..." | No connectivity analysis | They did connectivity but method unclear |
| "If multiple comparisons correction was used..." | They explicitly state no correction | They corrected but don't specify method |
| "If ROI analysis was performed..." | No ROI analysis done | ROI analysis done but ROIs not defined |

---

### Key Principle: Absence vs. Omission

**Absence (→ N/A):** The technique/method was not part of this study
- "Not applicable: Paper does not use diffusion imaging"
- "Not applicable: No physiological monitoring mentioned"
- "Not applicable: Study did not perform connectivity analysis"

**Omission (→ 0):** The technique WAS used but details were not reported
- "Information not found." (implies: they should have reported this but didn't)

---

## EVIDENCE REQUIREMENTS

**For Scores > 0:** Extract a VERBATIM quote from the paper supporting your score. Use quotation marks.

**For Score 0:** Write exactly: `Information not found.`

**For Score N/A:** Write: `Not applicable: [specific reason]`
- Good: "Not applicable: Study used standard (not conditional) shimming"
- Good: "Not applicable: No diffusion imaging performed"  
- Bad: "Not applicable" (too vague)
- Bad: "N/A" (need explanation)

---

## OUTPUT FORMAT

Return valid JSON with `metadata` and `csv` keys.

The CSV must contain ONLY 3 columns: `Question_Number,ai_score,evidence`

Do NOT include Question_Text, Section, or Status columns.

```json
{
  "metadata": {
    "title": "Paper Title Here",
    "authors": "Smith et al.",
    "year": "2024"
  },
  "csv": "Question_Number,ai_score,evidence\n1,2,\"Scanning was performed on a 3T Siemens Prisma...\"\n2,0,\"Information not found.\"\n43,N/A,\"Not applicable: No conditional shimming procedures mentioned.\"\n54,N/A,\"Not applicable: Study did not include diffusion MRI.\""
}
```

---

## FINAL CHECKLIST BEFORE SCORING

For each conditional item ("If...", "For...", "When..."):
1. ☐ Did I find explicit evidence this technique was used?
2. ☐ If NO evidence → Score N/A with reason
3. ☐ If YES evidence → Did they describe it adequately?
4. ☐ If described → Score appropriately with quote
5. ☐ If not described → Score 0 with "Information not found."

---

**Now process the attached PDF and rubric. Generate the JSON output.**
