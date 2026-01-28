from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import pdfplumber
import os
import tempfile
from dotenv import load_dotenv
import requests
import json
import csv
from contextlib import asynccontextmanager
from datetime import datetime
from weasyprint import HTML

# Load environment variables from .env file
load_dotenv()

# OpenAI API configuration
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Global variable to store ISO controls
iso_controls = []

def load_iso_controls():
    """
    Load ISO controls from CSV file and store them in a list of dictionaries.
    """
    global iso_controls
    csv_path = os.path.join("data", "iso_controls_master.csv")
    
    iso_controls = []
    with open(csv_path, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            iso_controls.append({
                "old_control_id": row["old_control_id"],
                "old_title": row["old_title"],
                "new_control_id": row["new_control_id"],
                "new_title": row["new_title"],
                "domain": row["domain"],
                "description": row["description"]
            })
    
    print(f"Loaded {len(iso_controls)} ISO controls from CSV")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load ISO controls from CSV
    load_iso_controls()
    yield
    # Shutdown: (nothing to clean up)

# Create a FastAPI instance with lifespan event
app = FastAPI(lifespan=lifespan)

# Define a GET route at the root path "/"
@app.get("/")
def read_root():
    return {"status": "Backend is running"}

# Define a GET route to view loaded ISO controls
@app.get("/controls")
def get_controls():
    """
    Returns the list of ISO controls loaded from the CSV file.
    """
    return {
        "total_controls": len(iso_controls),
        "controls": iso_controls
    }

# Define a GET route to download the HTML report
@app.get("/download-report")
def download_report():
    """
    Downloads the HTML compliance report as iso_27001_report.html
    """
    report_path = os.path.join("reports", "report.html")
    
    # Check if the file exists
    if not os.path.exists(report_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Report not found. Please run /analyze first to generate the report.")
    
    # Return the file with download headers
    return FileResponse(
        path=report_path,
        filename="iso_27001_report.html",
        media_type="text/html"
    )

# Define a GET route to download the PDF report
@app.get("/download-report-pdf")
def download_report_pdf():
    """
    Downloads the PDF compliance report as iso_27001_report.pdf
    """
    report_path = os.path.join("reports", "report.pdf")
    
    # Check if the file exists
    if not os.path.exists(report_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="PDF report not found. Please run /analyze first to generate the report.")
    
    # Return the file with download headers
    return FileResponse(
        path=report_path,
        filename="iso_27001_report.pdf",
        media_type="application/pdf"
    )

def analyze_control(control, extracted_text):
    """
    Analyzes a single ISO control against the extracted PDF text using OpenAI API.
    Returns the analysis result as a dictionary.
    """
    # System prompt for the AI
    system_prompt = """You are an ISO 27001 information security compliance assessor.
Your task is to perform a pre-audit readiness and gap assessment.
You are strict, factual, and conservative in your evaluation.
If evidence is unclear, incomplete, or missing, you must mark the control as NOT MET or PARTIALLY MET.
You do not assume compliance.
You do not give benefit of the doubt.
You base decisions only on the provided document text.
Your output must be structured, concise, and suitable for a professional compliance report.
You must always respond only in valid JSON as instructed."""

    # User prompt template with the control details
    user_prompt = f"""Assess the following ISO 27001 control against the provided policy text.

CONTROL ID: {control["new_control_id"]}
CONTROL TITLE: {control["new_title"]}
CONTROL DESCRIPTION: {control["description"]}

POLICY TEXT:
{extracted_text}

Instructions:
1. Determine whether this control is MET, PARTIALLY MET, or NOT MET.
2. Base your decision strictly on evidence found in the policy text.
3. If no clear evidence exists, mark as NOT MET.
4. Provide a short justification referencing the policy text or stating that evidence is missing.
5. Assign a risk level (LOW, MEDIUM, HIGH).
6. Provide a clear, actionable recommendation to address gaps.

Respond in the following JSON format ONLY:

{{
  "status": "MET | PARTIALLY MET | NOT MET",
  "justification": "...",
  "risk_level": "LOW | MEDIUM | HIGH",
  "recommendation": "..."
}}"""

    # Call OpenAI API using HTTP request
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    
    # Make HTTP request to OpenAI API
    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    # Parse the response JSON
    response_data = response.json()
    
    # Extract the AI's response content
    ai_response_text = response_data["choices"][0]["message"]["content"]
    
    # Parse the JSON response from the AI
    ai_response_json = json.loads(ai_response_text)
    
    return ai_response_json

def generate_html_report(summary, results):
    """
    Generates an HTML compliance report and saves it to reports/report.html
    """
    # Create reports directory if it doesn't exist
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # Generate timestamp for the report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISO 27001 Readiness Assessment Report</title>
    <style>
        @page {{
            size: A4 landscape;
            margin: 12mm;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: Arial, sans-serif;
            font-size: 9px;
            margin: 0;
            padding: 0;
            line-height: 1.4;
            color: #333;
            background-color: white;
        }}
        
        .container {{
            max-width: 100%;
            margin: 0;
            background-color: white;
            padding: 10px;
        }}
        
        h1 {{
            color: #2c3e50;
            margin-bottom: 8px;
            font-size: 20px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
        }}
        
        .timestamp {{
            color: #7f8c8d;
            margin-bottom: 15px;
            font-size: 9px;
        }}
        
        .summary-section {{
            background-color: #ecf0f1;
            padding: 12px;
            border-radius: 3px;
            margin-bottom: 15px;
        }}
        
        .summary-section h2 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 14px;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
        }}
        
        .summary-item {{
            background-color: white;
            padding: 8px;
            border-radius: 3px;
            text-align: center;
        }}
        
        .summary-item .label {{
            font-size: 8px;
            color: #7f8c8d;
            margin-bottom: 4px;
        }}
        
        .summary-item .value {{
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .summary-item .percentage {{
            color: #27ae60;
        }}
        
        .results-section h2 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 14px;
        }}
        
        table {{
            width: 100%;
            table-layout: fixed;
            border-collapse: collapse;
            word-wrap: break-word;
            margin-top: 10px;
            background-color: white;
            font-size: 9px;
        }}
        
        thead {{
            display: table-header-group;
            background-color: #34495e;
            color: white;
        }}
        
        th {{
            border: 1px solid #ddd;
            padding: 6px;
            text-align: left;
            font-weight: 600;
            font-size: 9px;
            vertical-align: top;
            word-break: break-word;
        }}
        
        td {{
            border: 1px solid #ddd;
            padding: 6px;
            vertical-align: top;
            word-break: break-word;
            font-size: 9px;
        }}
        
        tbody tr {{
            page-break-inside: avoid;
        }}
        
        tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        
        .status-met {{
            background-color: #d4edda;
            color: #155724;
            padding: 3px 6px;
            border-radius: 3px;
            font-weight: 600;
            display: inline-block;
            font-size: 8px;
        }}
        
        .status-partially-met {{
            background-color: #fff3cd;
            color: #856404;
            padding: 3px 6px;
            border-radius: 3px;
            font-weight: 600;
            display: inline-block;
            font-size: 8px;
        }}
        
        .status-not-met {{
            background-color: #f8d7da;
            color: #721c24;
            padding: 3px 6px;
            border-radius: 3px;
            font-weight: 600;
            display: inline-block;
            font-size: 8px;
        }}
        
        .risk-low {{
            color: #27ae60;
            font-weight: 600;
        }}
        
        .risk-medium {{
            color: #f39c12;
            font-weight: 600;
        }}
        
        .risk-high {{
            color: #e74c3c;
            font-weight: 600;
        }}
        
        .justification, .recommendation {{
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ISO 27001 Readiness Assessment Report</h1>
        <p class="timestamp">Generated on: {timestamp}</p>
        
        <div class="summary-section">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="label">Total Controls</div>
                    <div class="value">{summary['total_controls']}</div>
                </div>
                <div class="summary-item">
                    <div class="label">Met</div>
                    <div class="value" style="color: #27ae60;">{summary['met_count']}</div>
                </div>
                <div class="summary-item">
                    <div class="label">Partially Met</div>
                    <div class="value" style="color: #f39c12;">{summary['partially_met_count']}</div>
                </div>
                <div class="summary-item">
                    <div class="label">Not Met</div>
                    <div class="value" style="color: #e74c3c;">{summary['not_met_count']}</div>
                </div>
                <div class="summary-item">
                    <div class="label">Compliance Percentage</div>
                    <div class="value percentage">{summary['compliance_percentage']}%</div>
                </div>
            </div>
        </div>
        
        <div class="results-section">
            <h2>Detailed Results</h2>
            <table>
                <colgroup>
                    <col style="width: 6%">
                    <col style="width: 12%">
                    <col style="width: 8%">
                    <col style="width: 8%">
                    <col style="width: 6%">
                    <col style="width: 30%">
                    <col style="width: 30%">
                </colgroup>
                <thead>
                    <tr>
                        <th>Control ID</th>
                        <th>Control Title</th>
                        <th>Domain</th>
                        <th>Status</th>
                        <th>Risk Level</th>
                        <th>Justification</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add table rows for each result
    for result in results:
        # Determine status class
        status_class = ""
        if result["status"] == "MET":
            status_class = "status-met"
        elif result["status"] == "PARTIALLY MET":
            status_class = "status-partially-met"
        else:
            status_class = "status-not-met"
        
        # Determine risk level class
        risk_class = f"risk-{result['risk_level'].lower()}"
        
        # Escape HTML special characters in text fields
        def escape_html(text):
            return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        html_content += f"""                    <tr>
                        <td>{escape_html(result['control_id'])}</td>
                        <td>{escape_html(result['control_title'])}</td>
                        <td>{escape_html(result['domain'])}</td>
                        <td><span class="{status_class}">{escape_html(result['status'])}</span></td>
                        <td><span class="{risk_class}">{escape_html(result['risk_level'])}</span></td>
                        <td class="justification">{escape_html(result['justification'])}</td>
                        <td class="recommendation">{escape_html(result['recommendation'])}</td>
                    </tr>
"""
    
    html_content += """                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
    
    # Save HTML file
    report_path = os.path.join(reports_dir, "report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return report_path

def generate_pdf_report(html_path):
    """
    Converts the HTML report to PDF and saves it to reports/report.pdf
    Preserves colors, styling, and layout using WeasyPrint.
    """
    reports_dir = "reports"
    pdf_path = os.path.join(reports_dir, "report.pdf")
    
    # Convert HTML to PDF using WeasyPrint
    HTML(filename=html_path).write_pdf(pdf_path)
    
    return pdf_path

# Define a POST route at "/analyze" that accepts PDF file uploads
@app.post("/analyze")
async def analyze_pdf(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload, extracts text, analyzes all ISO 27001 controls from the CSV,
    and returns a list of analysis results for each control.
    """
    # Create a temporary file to save the uploaded PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_path = temp_file.name
        
        # Save the uploaded file to the temporary location
        content = await file.read()
        temp_file.write(content)
    
    try:
        # Extract text from the PDF using pdfplumber
        extracted_text = ""
        with pdfplumber.open(temp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text + "\n"
        
        # Analyze each control from the CSV
        results = []
        for control in iso_controls:
            # Analyze this control using the AI
            analysis = analyze_control(control, extracted_text)
            
            # Build the result dictionary
            result = {
                "control_id": control["new_control_id"],
                "control_title": control["new_title"],
                "domain": control["domain"],
                "status": analysis["status"],
                "risk_level": analysis["risk_level"],
                "justification": analysis["justification"],
                "recommendation": analysis["recommendation"]
            }
            
            results.append(result)
        
        # Calculate summary statistics
        total_controls = len(results)
        met_count = sum(1 for r in results if r["status"] == "MET")
        partially_met_count = sum(1 for r in results if r["status"] == "PARTIALLY MET")
        not_met_count = sum(1 for r in results if r["status"] == "NOT MET")
        compliance_percentage = (met_count / total_controls * 100) if total_controls > 0 else 0
        
        # Build summary object
        summary = {
            "total_controls": total_controls,
            "met_count": met_count,
            "partially_met_count": partially_met_count,
            "not_met_count": not_met_count,
            "compliance_percentage": round(compliance_percentage, 2)
        }
        
        # Generate and save HTML report
        html_path = generate_html_report(summary, results)
        print(f"HTML report generated at: {html_path}")
        
        # Generate and save PDF report
        pdf_path = generate_pdf_report(html_path)
        print(f"PDF report generated at: {pdf_path}")
        
        # Return the response with summary and results
        return {
            "summary": summary,
            "results": results
        }
    
    finally:
        # Always delete the temporary file, even if there's an error
        if os.path.exists(temp_path):
            os.remove(temp_path)
