from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics import (
	accuracy_score,
	classification_report,
	confusion_matrix,
	f1_score,
	precision_score,
	recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.metrics.pairwise import cosine_similarity


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR / "data" / "ecommerce_support_tickets_dataset.csv"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_PATH = ARTIFACTS_DIR / "ticket_classifier.npz"
MODEL_NAME = "all-MiniLM-L6-v2"


def build_texts(dataframe: pd.DataFrame) -> pd.Series:
	return (
		dataframe["subject"].fillna("").astype(str)
		+ " "
		+ dataframe["message"].fillna("").astype(str)
	)


def train_classifier() -> None:
	dataframe = pd.read_csv(DATASET_PATH)
	required_columns = {"subject", "message", "category"}
	missing_columns = required_columns - set(dataframe.columns)
	if missing_columns:
		raise ValueError(f"Dataset is missing columns: {sorted(missing_columns)}")

	dataframe = dataframe.dropna(subset=["category"]).copy()
	texts = build_texts(dataframe).to_numpy()
	labels = dataframe["category"].astype(str).to_numpy()

	train_texts, test_texts, train_labels, test_labels = train_test_split(
		texts,
		labels,
		test_size=0.2,
		random_state=42,
		stratify=labels,
	)

	model = SentenceTransformer(MODEL_NAME)
	train_embeddings = model.encode(train_texts, show_progress_bar=True)
	test_embeddings = model.encode(test_texts, show_progress_bar=True)

	category_names = np.array(sorted(set(train_labels)))
	category_embeddings = np.vstack(
		[
			train_embeddings[train_labels == category].mean(axis=0)
			for category in category_names
		]
	)

	predictions = category_names[
		cosine_similarity(test_embeddings, category_embeddings).argmax(axis=1)
	]

	confidence_scores = cosine_similarity(test_embeddings, category_embeddings).max(axis=1)
	print(f"Accuracy: {accuracy_score(test_labels, predictions):.4f}")
	print(
		f"Weighted Precision: "
		f"{precision_score(test_labels, predictions, average='weighted', zero_division=0):.4f}"
	)
	print(
		f"Weighted Recall: "
		f"{recall_score(test_labels, predictions, average='weighted', zero_division=0):.4f}"
	)
	print(
		f"Weighted F1: "
		f"{f1_score(test_labels, predictions, average='weighted', zero_division=0):.4f}"
	)
	print("Classification report:")
	print(
		classification_report(
			test_labels,
			predictions,
			labels=category_names,
			target_names=category_names,
			zero_division=0,
		)
	)
	print(f"Confusion matrix category names: {list(category_names)}")
	print(confusion_matrix(test_labels, predictions, labels=category_names))
	print(f"Mean confidence: {confidence_scores.mean():.4f}")
	print(f"Minimum confidence: {confidence_scores.min():.4f}")
	print(f"Maximum confidence: {confidence_scores.max():.4f}")

	prediction_records = [
		{
			"predicted_category": predicted,
			"actual_category": actual,
			"cosine_similarity": confidence,
			"correct": predicted == actual,
		}
		for predicted, actual, confidence in zip(
			predictions,
			test_labels,
			confidence_scores,
		)
	]

	confidence_ranges = {
		"confidence >= 0.85": confidence_scores >= 0.85,
		"0.70 <= confidence < 0.85": (confidence_scores >= 0.70)
		& (confidence_scores < 0.85),
		"confidence < 0.70": confidence_scores < 0.70,
	}
	print("Confidence threshold analysis:")
	for range_name, range_mask in confidence_ranges.items():
		range_records = [
			record for record, included in zip(prediction_records, range_mask) if included
		]
		total_predictions = len(range_records)
		correct_predictions = sum(record["correct"] for record in range_records)
		incorrect_predictions = total_predictions - correct_predictions
		accuracy = correct_predictions / total_predictions if total_predictions else 0.0
		print(
			f"{range_name}: total={total_predictions}, "
			f"correct={correct_predictions}, "
			f"incorrect={incorrect_predictions}, "
			f"accuracy={accuracy:.4f}"
		)

	high_confidence_errors = sum(
		not record["correct"]
		for record in prediction_records
		if record["cosine_similarity"] >= 0.85
	)
	print(f"Incorrect predictions with confidence >= 0.85: {high_confidence_errors}")

	ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
	np.savez(
		ARTIFACT_PATH,
		category_embeddings=category_embeddings,
		category_names=category_names,
	)
	print(f"Saved classifier artifacts to {ARTIFACT_PATH}")


if __name__ == "__main__":
	train_classifier()
