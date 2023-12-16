from typing import Type
from pydantic import BaseModel
from google.cloud import firestore

def load_settings_from_firestore(settings_class: Type[BaseModel], document_path: str) -> BaseModel:
    db = firestore.Client()
    doc_ref = db.document(document_path)
    doc = doc_ref.get()
    if doc.exists:
        return settings_class.parse_obj(doc.to_dict())
    else:
        raise FileNotFoundError(f"Document at path {document_path} does not exist.")
