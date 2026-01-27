# LLMRI Scoring Prompt - v3

**Objective:** Evaluate the provided neuroimaging research paper against the COBIDAS rubric.

**Your Role:** You are an expert neuroimaging methodologist. Score the paper *strictly* based on the rubric, but with intelligent interpretation of modern reporting practices.

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

## STANDARDIZED PIPELINE RECOGNITION (IMPORTANT!)

Modern neuroimaging papers often use **standardized, well-documented preprocessing pipelines**. When a paper cites one of these pipelines with a version number, you should give credit for all steps that pipeline performs BY DEFAULT.

### fMRIPrep

If the paper states preprocessing was performed using **fMRIPrep** (with version number and/or citation to Esteban et al.), give **FULL CREDIT** for the following items, as fMRIPrep performs these steps automatically and documents them in its methods boilerplate:

| Question | fMRIPrep Default Behavior |
|----------|---------------------------|
| Q18 | ✅ Coregistration method (EPI to T1w via boundary-based registration) |
| Q19 | ✅ Coregistration cost function (BBR - boundary-based registration) |
| Q20 | ✅ Coregistration interpolation method (documented in fMRIPrep) |
| Q21 | ✅ Skull stripping method (via ANTs or FreeSurfer antsBrainExtraction/mri_synthstrip) |
| Q22 | ✅ Tissue segmentation (via FreeSurfer or fast/ANTs) |
| Q23 | ✅ Brain extraction/skull stripping (via ANTs or FreeSurfer) |
| Q24-25 | ✅ Motion correction (via FSL MCFLIRT or FreeSurfer) |
| Q26 | ✅ Motion correction reference frame (documented - middle volume or first) |
| Q27 | ✅ Motion correction interpolation (documented in fMRIPrep) |
| Q28-29 | ✅ Susceptibility distortion correction (if fieldmaps provided, via TOPUP/FUGUE/SyN) |
| Q30-32 | ✅ Spatial normalization to MNI space (via ANTs SyN registration) |
| Q33 | ✅ Normalization template specified (MNI152NLin2009cAsym or MNI152NLin6Asym) |
| Q40+ | ✅ Confound variables computed (motion params, CompCor, FD, DVARS, etc.) |

**Evidence format:** When giving credit based on fMRIPrep usage, cite the fMRIPrep mention. Example:
- `"Preprocessing was performed using fMRIPrep version 23.1.0 (Esteban et al., 2019)"` → This covers tissue segmentation, brain extraction, motion correction, normalization.

**Note:** Slice timing correction and smoothing are NOT defaults in fMRIPrep - only give credit if explicitly mentioned.

### Other Standard Pipelines

Apply similar logic to other well-documented pipelines:

- **FreeSurfer:** Credit for cortical reconstruction, parcellation, tissue segmentation, surface-based analysis
- **FSL (FEAT/MELODIC):** Credit for standard preprocessing steps if using default pipeline
- **SPM:** Credit for standard preprocessing if using batch scripts
- **CONN Toolbox:** Credit for connectivity-specific preprocessing and denoising
- **C-PAC:** Credit for documented default preprocessing steps
- **HCP Pipelines:** Credit for HCP-standard processing steps
- **QSIPrep:** Credit for diffusion preprocessing steps (for dMRI studies)
- **MRIQC:** Credit for quality control procedures

**The Rationale:** Citing a versioned, peer-reviewed pipeline with published documentation IS good methodology reporting. It's actually MORE reproducible than a custom description because:
1. The exact code is available
2. The version specifies exact behavior
3. The pipeline generates detailed methods text

---

## IMPLICIT DATA AVAILABILITY

When scoring questions about data sharing/availability, use intelligent interpretation:

### ROI Data (Q37: "Are extracted ROI data values reported or made available?")

Give **FULL CREDIT** if ANY of these are true:
- ROI values are explicitly in a table in the paper
- ROI values are in supplementary tables
- Paper states "source data for figures is available" AND figures contain ROI results
- Paper states data is available in a repository AND the repository would contain ROI extractions
- Paper provides code/scripts that would output ROI values when run on shared data

**Example:** If paper says "Source data underlying Figures 2-5 are provided in Supplementary Data 1" and Figures 2-5 show ROI analysis results → The ROI data IS available → Full credit.

### Statistical Maps (Q73-74: "Are unthresholded statistical maps available?")

Give credit if:
- Maps explicitly shared on NeuroVault, OSF, GitHub, etc.
- Paper states "all neuroimaging derivatives available upon request" (half credit)
- Paper states "data available at [repository]" where repository would include maps

### Raw Data (Q75-77)

Give credit if:
- Data shared on OpenNeuro, XNAT, institutional repository
- Data available upon request (half credit for conditional sharing)
- BIDS-formatted data mentioned as available

---

## COMMON CONDITIONAL ITEM PATTERNS

| Question Pattern | N/A When... | 0 When... |
|-----------------|-------------|-----------|
| "If shimming procedures are used..." | No mention of shimming approach | They mention shimming but don't describe parameters |
| "If physiological monitoring was performed..." | No mention of physiological correction | They say they did physio correction but don't give details |
| "For diffusion MRI studies..." | Paper is not a dMRI study | It's a dMRI study but info missing |
| "If functional connectivity was assessed..." | No connectivity analysis | They did connectivity but method unclear |
| "If multiple comparisons correction was used..." | They explicitly state no correction OR it's descriptive only | They corrected but don't specify method |
| "If ROI analysis was performed..." | No ROI analysis done | ROI analysis done but ROIs not defined |
| "If smoothing was performed..." | They explicitly state no smoothing was applied | They smoothed but don't give FWHM |

---

## KEY PRINCIPLE: Absence vs. Omission

**Absence (→ N/A):** The technique/method was not part of this study
- "Not applicable: Paper does not use diffusion imaging"
- "Not applicable: No physiological monitoring mentioned"
- "Not applicable: Study did not perform connectivity analysis"
- "Not applicable: No conditional shimming procedures used"

**Omission (→ 0):** The technique WAS used but details were not reported
- "Information not found." (implies: they should have reported this but didn't)

---

## EVIDENCE REQUIREMENTS

**For Scores > 0:** Extract a VERBATIM quote from the paper supporting your score. Use quotation marks.
- For pipeline-based credit: Quote the pipeline mention (e.g., "Preprocessing was performed using fMRIPrep 23.1.0")
- For implicit data availability: Quote the data statement that implies availability

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
  "csv": "Question_Number,ai_score,evidence\n1,2,\"Scanning was performed on a 3T Siemens Prisma...\"\n2,0,\"Information not found.\"\n22,1,\"Preprocessing was performed using fMRIPrep version 21.0.1 (Esteban et al., 2019)\" \n37,1,\"Source data underlying Figures 2-5 are provided in Supplementary Data 1\"\n43,N/A,\"Not applicable: No conditional shimming procedures mentioned.\"\n54,N/A,\"Not applicable: Study did not include diffusion MRI.\""
}
```

---

## FINAL CHECKLIST BEFORE SCORING

For each item, ask:

1. ☐ Is this a conditional item? (starts with "If", "For", "When")
   - If YES: Did I verify the condition applies before scoring 0?
   
2. ☐ Did the paper use a standardized pipeline (fMRIPrep, FreeSurfer, etc.)?
   - If YES: Did I give credit for steps that pipeline includes?

3. ☐ For data availability questions:
   - Did I check supplementary materials statements?
   - Did I check data availability statements?
   - Could the data be implicitly available through stated resources?

4. ☐ Is my evidence appropriate?
   - Score > 0: Do I have a quote?
   - Score 0: Did I write "Information not found."?
   - Score N/A: Did I explain WHY it's not applicable?

---

**Now process the attached PDF and rubric. Generate the JSON output.**
