# Allergy Detective & Remedy Tracker

A lightweight Python web app that:
- accepts allergy issues in natural language (Hindi/English/mixed),
- sends issue text to OpenAI to infer likely allergy details,
- returns remedies, precautions, and most likely cause,
- stores each analysis in a local SQLite log,
- shows history and a frequency report (allergy type, trigger factors, daily count).

## Setup

```bash
export OPENAI_API_KEY="your_key_here"
# optional (defaults to gpt-4o-mini)
export OPENAI_MODEL="gpt-4o-mini"
python app.py
```

Open: `http://localhost:5000`

## API Endpoints

- `POST /api/analyze` `{ "issue": "doodh piya and pet dard ho gya" }`
- `GET /api/history`
- `GET /api/report`

## Notes

This app provides general guidance only and is **not** a replacement for professional medical diagnosis.
