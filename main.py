import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from azure.storage.blob import BlobServiceClient

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(title="API Fichiers Azure")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

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
# Debug (à supprimer après vérification)
# ---------------------------------------------------------------------------

@app.get("/debug-env")
def debug_env():
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    return {"set": bool(conn), "preview": conn[:40] + "..." if conn else "VIDE"}


# ---------------------------------------------------------------------------
# Interface HTML
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def upload_page(request: Request, status: str = "", filename: str = "") -> HTMLResponse:
    try:
        blobs = [b.name for b in get_container_client().list_blobs()]
    except Exception:
        blobs = []

    file_count = len(blobs)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "status": status,
            "filename": filename,
            "blobs": blobs,
            "file_count": file_count,
            "container_name": CONTAINER_NAME,
        },
    )


@app.post("/")
def upload_from_root(file: UploadFile = File(...)):
    try:
        result = upload_to_blob(file)
        return RedirectResponse(
            url=f"/?status=uploaded&filename={result['filename']}", status_code=303
        )
    except Exception as exc:
        logger.error("Upload échoué pour '%s': %s", file.filename, exc)
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
    except Exception as exc:
        logger.error("Suppression échouée pour '%s': %s", filename, exc)
        return RedirectResponse(url=f"/?status=error&filename={filename}", status_code=303)


@app.delete("/remove", summary="Supprimer un fichier (API REST)")
def remove_file(filename: str) -> dict:
    """Supprime le blob dont le nom est passé en query param (?filename=...)."""
    return delete_blob(filename)


@app.get("/file/{filename}", summary="Prévisualiser / télécharger un fichier")
def preview_file(filename: str):
    """Retourne le contenu brut du blob avec le bon Content-Type."""
    container_client = get_container_client()
    blob_client = container_client.get_blob_client(filename)
    if not blob_client.exists():
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' introuvable.")
    download = blob_client.download_blob()
    props = blob_client.get_blob_properties()
    content_type = props.content_settings.content_type or "application/octet-stream"
    return StreamingResponse(download.chunks(), media_type=content_type)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
