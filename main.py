import os
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from azure.storage.blob import BlobServiceClient
from fastapi.responses import HTMLResponse, RedirectResponse

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(title="API Fichiers Azure")

CONTAINER_NAME = "fichiers-api"

def get_container_client(create_if_missing: bool = False):
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise HTTPException(
            status_code=500,
            detail="AZURE_STORAGE_CONNECTION_STRING non définie dans .env",
        )
    service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = service_client.get_container_client(CONTAINER_NAME)
    if create_if_missing:
        try:
            container_client.create_container()
        except Exception:
            pass  # Le conteneur existe déjà
    return container_client


def upload_to_blob(file: UploadFile) -> dict:
    container_client = get_container_client(create_if_missing=True)
    blob_client = container_client.get_blob_client(file.filename)
    contents = file.file.read()
    blob_client.upload_blob(contents, overwrite=True)
    return {"message": f"Fichier '{file.filename}' uploadé avec succès.", "filename": file.filename}


def delete_blob(filename: str) -> dict:
    container_client = get_container_client()
    blob_client = container_client.get_blob_client(filename)
    if not blob_client.exists():
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable.")
    blob_client.delete_blob()
    return {"message": f"Fichier '{filename}' supprimé avec succès."}


# ---------------------------------------------------------------------------
# Interface HTML simple
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def upload_page(status: str = "", filename: str = "") -> str:
    alert_html = ""
    if status == "uploaded":
        alert_html = f'<div class="toast success"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>Fichier <strong>&nbsp;{escape(filename)}&nbsp;</strong> uploadé avec succès.</div>'
    elif status == "deleted":
        alert_html = f'<div class="toast success"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>Fichier <strong>&nbsp;{escape(filename)}&nbsp;</strong> supprimé.</div>'
    elif status == "error":
        alert_html = f'<div class="toast error"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Erreur lors de l\'opération sur <strong>&nbsp;{escape(filename)}&nbsp;</strong>.</div>'

    try:
        container_client = get_container_client()
        blobs = [b.name for b in container_client.list_blobs()]
    except Exception:
        blobs = []

    rows = "".join(
        f"""<tr>
              <td>
                <div class="file-icon">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                    <polyline points="13 2 13 9 20 9"/>
                  </svg>
                  {escape(name)}
                </div>
              </td>
              <td>
                <form method="post" action="/delete">
                  <input type="hidden" name="filename" value="{escape(name)}">
                  <button type="submit" class="btn btn-danger">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6l-1 14H6L5 6"/>
                    </svg>
                    Supprimer
                  </button>
                </form>
              </td>
            </tr>"""
        for name in blobs
    )

    file_count = len(blobs)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Azure File Manager</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --azure:      #0078d4;
      --azure-dark: #005a9e;
      --azure-bg:   #eff6fc;
      --danger:     #c42b1c;
      --danger-bg:  #fde7e9;
      --success:    #0e700e;
      --success-bg: #dff6dd;
      --surface:    #ffffff;
      --bg:         #f4f6f8;
      --border:     #e1e4e8;
      --text:       #1a1a2e;
      --muted:      #6b7280;
      --radius:     10px;
      --shadow:     0 2px 12px rgba(0,0,0,.08);
    }}

    body {{
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}

    /* ── Top bar ── */
    header {{
      background: linear-gradient(135deg, #0078d4 0%, #005a9e 100%);
      color: #fff;
      padding: 0 32px;
      height: 60px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 2px 8px rgba(0,120,212,.35);
    }}
    header svg {{ flex-shrink: 0; }}
    header .brand {{ font-size: 1.05rem; font-weight: 700; letter-spacing: .3px; }}
    header .badge {{
      margin-left: auto;
      background: rgba(255,255,255,.18);
      border: 1px solid rgba(255,255,255,.3);
      border-radius: 20px;
      padding: 3px 12px;
      font-size: .75rem;
      font-weight: 500;
    }}

    /* ── Layout ── */
    main {{
      max-width: 860px;
      margin: 36px auto;
      padding: 0 20px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    /* ── Toast / alert ── */
    .toast {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 18px;
      border-radius: var(--radius);
      font-size: .9rem;
      font-weight: 500;
      animation: slideIn .3s ease;
    }}
    .toast.success {{ background: var(--success-bg); color: var(--success); border-left: 4px solid var(--success); }}
    .toast.error   {{ background: var(--danger-bg);  color: var(--danger);  border-left: 4px solid var(--danger); }}
    @keyframes slideIn {{ from {{ opacity:0; transform:translateY(-8px); }} to {{ opacity:1; transform:translateY(0); }} }}

    /* ── Card ── */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card-header {{
      padding: 18px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .card-header h2 {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
    }}
    .card-body {{ padding: 24px; }}

    /* ── Upload zone ── */
    .upload-zone {{
      border: 2px dashed var(--border);
      border-radius: 8px;
      padding: 36px 24px;
      text-align: center;
      transition: border-color .2s, background .2s;
      cursor: pointer;
      background: var(--azure-bg);
    }}
    .upload-zone:hover {{ border-color: var(--azure); background: #e4f0fb; }}
    .upload-zone svg {{ margin-bottom: 10px; color: var(--azure); }}
    .upload-zone p {{ color: var(--muted); font-size: .875rem; margin-bottom: 16px; }}
    .upload-zone p strong {{ color: var(--text); }}

    input[type=file] {{ display: none; }}

    .file-label {{
      display: inline-block;
      cursor: pointer;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 16px;
      font-size: .875rem;
      font-weight: 500;
      color: var(--text);
      transition: border-color .2s, box-shadow .2s;
    }}
    .file-label:hover {{ border-color: var(--azure); box-shadow: 0 0 0 3px rgba(0,120,212,.12); }}

    .selected-name {{
      display: block;
      margin-top: 10px;
      font-size: .8rem;
      color: var(--muted);
      min-height: 18px;
    }}

    /* ── Buttons ── */
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 9px 20px;
      border: none;
      border-radius: 6px;
      font-family: inherit;
      font-size: .875rem;
      font-weight: 600;
      cursor: pointer;
      transition: filter .15s, transform .1s;
    }}
    .btn:active {{ transform: scale(.97); }}
    .btn-primary  {{ background: var(--azure);  color: #fff; }}
    .btn-primary:hover  {{ filter: brightness(1.1); }}
    .btn-danger   {{ background: var(--danger); color: #fff; padding: 6px 14px; font-size: .8rem; }}
    .btn-danger:hover   {{ filter: brightness(1.12); }}

    .upload-actions {{
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
    }}

    /* ── Stats bar ── */
    .stats {{
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: .8rem;
      color: var(--muted);
      margin-left: auto;
    }}
    .stats .dot {{
      width: 7px; height: 7px;
      border-radius: 50%;
      background: {'#0e700e' if file_count > 0 else '#6b7280'};
    }}

    /* ── Table ── */
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: .875rem;
    }}
    thead tr {{ background: var(--bg); }}
    th {{
      padding: 11px 16px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      font-size: .7rem;
      letter-spacing: .6px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    td {{
      padding: 13px 16px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
    }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr {{ transition: background .15s; }}
    tbody tr:hover {{ background: var(--azure-bg); }}

    .file-icon {{ display: flex; align-items: center; gap: 9px; }}
    .file-icon svg {{ flex-shrink: 0; color: var(--azure); }}

    .empty-state {{
      text-align: center;
      padding: 48px 24px;
      color: var(--muted);
    }}
    .empty-state svg {{ margin-bottom: 12px; opacity: .4; }}
    .empty-state p {{ font-size: .9rem; }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 28px 0;
      font-size: .78rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>

<header>
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 15a4 4 0 0 0 4 4h9a5 5 0 1 0-.1-9.999 5.002 5.002 0 0 0-9.78 2.096A4 4 0 0 0 3 15z"/>
  </svg>
  <span class="brand">Azure File Manager</span>
  <span class="badge">Container: {CONTAINER_NAME}</span>
</header>

<main>
  {alert_html}

  <!-- Upload Card -->
  <div class="card">
    <div class="card-header">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      <h2>Uploader un fichier</h2>
    </div>
    <div class="card-body">
      <form method="post" action="/" enctype="multipart/form-data" id="uploadForm">
        <div class="upload-zone" onclick="document.getElementById('fileInput').click()">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 15a4 4 0 0 0 4 4h9a5 5 0 1 0-.1-9.999 5.002 5.002 0 0 0-9.78 2.096A4 4 0 0 0 3 15z"/>
            <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
          </svg>
          <p><strong>Glissez-déposez</strong> votre fichier ici, ou</p>
          <label class="file-label" for="fileInput">Parcourir les fichiers</label>
          <input type="file" name="file" id="fileInput" required onchange="showName(this)">
          <span class="selected-name" id="selectedName">Aucun fichier sélectionné</span>
        </div>
        <div class="upload-actions">
          <button type="submit" class="btn btn-primary">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
              <path d="M5 19h14"/>
            </svg>
            Envoyer
          </button>
        </div>
      </form>
    </div>
  </div>

  <!-- Files Card -->
  <div class="card">
    <div class="card-header">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <h2>Fichiers stockés</h2>
      <div class="stats">
        <span class="dot"></span>
        {file_count} fichier{'s' if file_count != 1 else ''}
      </div>
    </div>
    <div class="table-wrap">
      {'<table><thead><tr><th>Nom du fichier</th><th style="width:120px">Action</th></tr></thead><tbody>' + rows + '</tbody></table>' if rows else '<div class="empty-state"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg><p>Aucun fichier dans ce conteneur.</p></div>'}
    </div>
  </div>
</main>

<footer>Azure Blob Storage &mdash; File Manager &copy; {2026}</footer>

<script>
  function showName(input) {{
    const label = document.getElementById('selectedName');
    label.textContent = input.files.length ? input.files[0].name : 'Aucun fichier sélectionné';
  }}
</script>

</body>
</html>"""


@app.post("/")
def upload_from_root(file: UploadFile = File(...)):
    try:
        result = upload_to_blob(file)
        return RedirectResponse(
            url=f"/?status=uploaded&filename={result['filename']}", status_code=303
        )
    except HTTPException:
        return RedirectResponse(url=f"/?status=error&filename={file.filename}", status_code=303)


# ---------------------------------------------------------------------------
# Routes REST principales
# ---------------------------------------------------------------------------

@app.get("/files", summary="Lister tous les fichiers du conteneur")
def list_files() -> dict:
    """Retourne la liste des noms de blobs présents dans le conteneur."""
    container_client = get_container_client()
    blobs = [blob.name for blob in container_client.list_blobs()]
    return {"container": CONTAINER_NAME, "files": blobs, "count": len(blobs)}


@app.post("/upload", summary="Uploader un fichier vers Azure Blob Storage")
def upload_file(file: UploadFile = File(...)) -> dict:
    """Reçoit un fichier multipart et l'envoie dans le conteneur Azure."""
    return upload_to_blob(file)


@app.post("/delete", summary="Supprimer un fichier (formulaire HTML)")
def delete_from_root(filename: str = Form(...)):
    """Supprime un blob (appelé depuis le formulaire HTML)."""
    try:
        delete_blob(filename)
        return RedirectResponse(url=f"/?status=deleted&filename={filename}", status_code=303)
    except HTTPException:
        return RedirectResponse(url=f"/?status=error&filename={filename}", status_code=303)


@app.delete("/remove", summary="Supprimer un fichier (API REST)")
def remove_file(filename: str) -> dict:
    """Supprime le blob dont le nom est passé en query param (?filename=...)."""
    return delete_blob(filename)
