# LLMRI

AI-powered methodological assessment for fMRI research papers using COBIDAS guidelines.

## Overview

LLMRI allows researchers to upload their neuroimaging papers and receive an automated assessment based on the OHBM Committee on Best Practices in Data Analysis and Sharing (COBIDAS) reporting standards. The tool uses Google's Gemini 2.5 to evaluate 82 rubric items across 7 categories.

**Features:**
- 📄 PDF upload with drag-and-drop support
- 🧠 Powered by Gemini 2.5
- 📊 Visual score breakdown by COBIDAS section
- 📥 Downloadable CSV and HTML reports
- 🔒 Rate-limited (1 analysis/day per user)
- 🌓 Light/dark mode with system preference detection

## Based on Research

This tool implements the methodology from:

> Pluimer, B., Sridhar, A., Mawla, I., et al. (2026). A Proof-of-Concept Study on the Use of Large Language Models for Assessing Research Methodology in Neuroimaging. *Neuroscience Informatics*. https://doi.org/10.1016/j.neuri.2026.100262

## Tech Stack

- **Backend:** Python 3.11+, Flask
- **Frontend:** Vanilla HTML/CSS/JS
- **AI:** Google Gemini 2.5 Flash API
- **Hosting:** Render (recommended) or any Python-compatible host

## Project Structure

```
llmri/
├── backend/
│   ├── app.py                    # Flask app entry point
│   ├── requirements.txt          # Python dependencies
│   ├── scorer/
│   │   ├── __init__.py
│   │   ├── gemini_service.py     # Gemini API integration
│   │   ├── routes.py             # API endpoints + rate limiting
│   │   └── utils.py              # CSV parsing utilities
│   ├── prompts/
│   │   └── gemini_prompt.md      # Prompt template
│   └── rubrics/
│       └── cobidas_rubric.csv    # COBIDAS rubric (82 items)
├── frontend/
│   ├── index.html                # Main HTML
│   ├── css/
│   │   └── style.css             # Styles (light/dark mode)
│   └── js/
│       └── main.js               # Frontend logic
├── .env.example                  # Environment variable template
├── .gitignore
├── Procfile                      # Heroku/Render deployment
├── render.yaml                   # Render blueprint
└── README.md
```

## Local Development

### Prerequisites

- Python 3.11+
- A Google AI / Gemini API key ([get one here](https://aistudio.google.com/apikey))

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/llmri.git
   cd llmri
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY
   ```

5. **Run the development server**
   ```bash
   cd backend
   python app.py
   ```

6. **Open in browser**
   ```
   http://localhost:5001
   ```

## Deployment

### Option 1: Render (Recommended)

1. Push your code to GitHub

2. Go to [Render Dashboard](https://dashboard.render.com)

3. Click **New → Web Service**

4. Connect your GitHub repository

5. Configure:
   - **Name:** `llmri`
   - **Runtime:** Python
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && gunicorn app:create_app() --bind 0.0.0.0:$PORT`

6. Add environment variable:
   - `GEMINI_API_KEY` = your API key

7. Deploy!

Your app will be available at `https://llmri.onrender.com` (or your custom domain).

### Option 2: Using render.yaml (Blueprint)

If you have the `render.yaml` in your repo, Render can auto-configure everything:

1. Go to [Render Blueprints](https://dashboard.render.com/blueprints)
2. Click **New Blueprint Instance**
3. Connect your repo
4. Add your `GEMINI_API_KEY` when prompted

### Option 3: Railway

1. Go to [Railway](https://railway.app)
2. Create new project → Deploy from GitHub
3. Add environment variable `GEMINI_API_KEY`
4. Railway auto-detects Python and deploys

## Configuration

### Rate Limiting

Default: 1 analysis per IP per 24 hours.

To modify, edit `backend/scorer/routes.py`:
```python
RATE_LIMIT_WINDOW = 24 * 60 * 60  # 24 hours
MAX_REQUESTS_PER_WINDOW = 1
```

**Note:** The current rate limiting uses in-memory storage. For production with multiple workers, use Redis.

### API Costs

Gemini 2.5 Pro is very cost-effective:
- Input: ~$0.075 per 1M tokens
- Output: ~$0.30 per 1M tokens

A typical paper analysis (~50K input + ~5K output tokens) costs approximately **$0.005** (half a cent).

## API Endpoints

### `POST /api/score-paper`

Upload a PDF for COBIDAS scoring.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `paper` (PDF file)

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "Question_Number": "1",
      "Status": "Mandatory",
      "Section": "Experimental Design Reporting",
      "Question_Text": "Are the subjects who participated...",
      "Maximum_Score": "2",
      "ai_score": "2",
      "evidence": "\"Participants included 30 healthy adults...\""
    }
  ],
  "filename": "paper.pdf"
}
```

### `GET /api/health`

Health check endpoint for monitoring.

## Customization

### Changing the Accent Color

Edit `frontend/css/style.css`:
```css
:root {
    --color-accent: #4285F4;  /* Change this */
    --color-accent-hover: #3367d6;
}
```

## Support

If you find this tool useful, consider supporting its development:

☕ [Buy us a coffee on Ko-fi](https://ko-fi.com/YOUR_KOFI)

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

Built with ❤️ by Brock Pluimer & collaborators
