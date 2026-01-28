🛡️ ISO 27001 AI Readiness Assessment Tool (MVP)

An AI-powered backend service that analyzes organizational security policies against selected ISO/IEC 27001:2022 Annex A controls and generates structured compliance readiness reports with risk levels and actionable recommendations.

This tool is designed as a pre-audit readiness checker, not a certification authority.

--------------------------------------------------------------------------------------

🚀 Features

Upload policy documents (PDF)

Extracts and analyzes policy text

Uses OpenAI API for control-by-control assessment

Evaluates against selected ISO 27001 Annex A controls

Generates structured JSON results

Auto-generates HTML compliance report

Exports full report as PDF

--------------------------------------------------------------------------------------

⚙️ Tech Stack

Backend: FastAPI (Python)

AI: OpenAI API

PDF Processing: PyPDF

Report Generation: HTML + WeasyPrint (PDF)

Data: ISO Controls stored in CSV
