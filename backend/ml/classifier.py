from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "ticket_classifier.npz"
MODEL_NAME = "all-MiniLM-L6-v2"


def predict_category(subject: str, message: str) -> tuple[str, float]:
	if not ARTIFACT_PATH.exists():
		raise FileNotFoundError(
			f"Classifier artifacts not found at {ARTIFACT_PATH}. "
			"Run train_classifier.py first."
		)

	artifacts = np.load(ARTIFACT_PATH)
	category_embeddings = artifacts["category_embeddings"]
	category_names = artifacts["category_names"]

	model = SentenceTransformer(MODEL_NAME)
	text = f"{subject} {message}"
	embedding = model.encode([text])
	similarities = cosine_similarity(embedding, category_embeddings)[0]
	best_index = int(similarities.argmax())

	return str(category_names[best_index]), float(similarities[best_index])
