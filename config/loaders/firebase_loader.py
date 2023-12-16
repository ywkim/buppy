from __future__ import annotations
from typing import Type
from pydantic import BaseModel
from google.cloud import firestore

def load_settings_from_firestore(model: Type[BaseModel], collection: str, document_id: str) -> BaseModel:
    """
    Load settings from a Firestore document and return an instance of the specified Pydantic model.

    Args:
        model (Type[BaseModel]): The Pydantic model class to instantiate.
        collection (str): The Firestore collection name.
        document_id (str): The document ID within the collection.

    Returns:
        BaseModel: An instance of the specified Pydantic model with loaded settings.

    Raises:
        FileNotFoundError: If the specified document does not exist in Firestore.
    """
    db = firestore.Client()
    doc_ref = db.collection(collection).document(document_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise FileNotFoundError(f"Document with ID {document_id} does not exist in Firestore.")

    return model(**doc.to_dict())
