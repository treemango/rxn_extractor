import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_ui(domain: Dict[str, Any], output_path: str) -> None:
    """Generates the HITL UI index.html file."""
    logger.info(f"Generating UI at {output_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Basic HTML structure
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{domain.get('domain_name', 'RXN Extractor')} HITL</title>
    <style>
        :root {{ --bg: #f9fafb; --sidebar: #1f2937; --sidebar-text: #f3f4f6; --text: #111827; --primary: #3b82f6; }}
        body {{ font-family: system-ui, sans-serif; margin: 0; display: flex; height: 100vh; background: var(--bg); color: var(--text); }}
        .sidebar {{ width: 250px; background: var(--sidebar); color: var(--sidebar-text); padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }}
        .sidebar a {{ color: var(--sidebar-text); text-decoration: none; padding: 0.5rem; border-radius: 4px; }}
        .sidebar a:hover {{ background: rgba(255,255,255,0.1); }}
        .main {{ flex: 1; overflow-y: auto; padding: 2rem; }}
        .page {{ display: none; }}
        .page.active {{ display: block; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f3f4f6; }}
        .btn {{ padding: 0.5rem 1rem; border: none; border-radius: 4px; background: var(--primary); color: white; cursor: pointer; }}
        .btn:hover {{ opacity: 0.9; }}
        .card {{ background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        [contenteditable] {{ border-bottom: 1px dashed #ccc; padding: 2px; }}
        [contenteditable]:focus {{ outline: none; border-bottom-color: var(--primary); background: #eff6ff; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>{domain.get('domain_name', 'HITL')}</h2>
        <a href="#" onclick="showPage('dashboard')">Dashboard</a>
        <a href="#" onclick="showPage('queue')">Validation Queue</a>
        <a href="#" onclick="showPage('papers')">Papers</a>
        <a href="#" onclick="showPage('export')">Export</a>
    </div>
    
    <div class="main">
        <div id="dashboard" class="page active">
            <h1>Dashboard</h1>
            <div class="grid">
                <div class="card"><h3>Total Papers</h3><p id="total-papers">0</p></div>
                <div class="card"><h3>Total Experiments</h3><p id="total-experiments">0</p></div>
                <div class="card"><h3>Pending Validation</h3><p id="pending-validation">0</p></div>
            </div>
        </div>
        
        <div id="queue" class="page">
            <h1>Validation Queue</h1>
            <table id="queue-table">
                <thead>
                    <tr>
                        <th>Experiment ID</th>
                        <th>Confidence</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div id="experiment" class="page">
            <h1>Experiment Details <button class="btn" onclick="showPage('queue')">Back</button></h1>
            <div id="experiment-details"></div>
        </div>
        
        <div id="papers" class="page">
            <h1>Papers</h1>
            <table id="papers-table">
                <thead><tr><th>Paper ID</th><th>Status</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div id="export" class="page">
            <h1>Export Data</h1>
            <button class="btn" onclick="exportData('csv')">Export CSV</button>
            <button class="btn" onclick="exportData('json')">Export JSON</button>
        </div>
    </div>

    <script>
        const API_BASE = window.location.origin + '/api';
        
        async function api(endpoint, options = {{}}) {{
            try {{
                const res = await fetch(API_BASE + endpoint, options);
                return await res.json();
            }} catch (e) {{
                console.error(e);
                toast('API Error');
            }}
        }}

        function toast(msg) {{
            console.log("Toast: ", msg);
        }}

        function showPage(id) {{
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            if (id === 'dashboard') loadDashboard();
            if (id === 'queue') loadQueue();
        }}

        async function loadDashboard() {{
            // Mock data fetch
            document.getElementById('total-papers').innerText = '10';
        }}

        async function loadQueue() {{
            // Mock data fetch
            const tbody = document.querySelector('#queue-table tbody');
            tbody.innerHTML = `<tr>
                <td>EXP-001</td>
                <td>3</td>
                <td>Pending</td>
                <td><button class="btn" onclick="openExperiment('EXP-001')">Review</button></td>
            </tr>`;
        }}

        async function openExperiment(id) {{
            showPage('experiment');
            // Mock load and render panels
            document.getElementById('experiment-details').innerHTML = `<p>Loading ${{id}}...</p>`;
        }}

        function renderPropertyPanel(data) {{
            // Dynamic render based on subdomains
        }}

        function startEdit(el) {{
            // setup edit logic
        }}

        async function validateExperiment(id, status) {{
            // validate api call
            toast('Experiment ' + status);
        }}

        async function exportData(format) {{
            toast('Exporting ' + format);
            window.open(API_BASE + '/export?format=' + format);
        }}

        setInterval(() => {{
            fetch(API_BASE + '/health').catch(() => console.log('Health check failed'));
        }}, 30000);

        // Init
        loadDashboard();
    </script>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
        
    logger.info("UI generated successfully")
