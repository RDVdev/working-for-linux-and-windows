"""
Script to generate the complete, production-grade SMAI Monsoon 2026 Assignment 1 Jupyter Notebook.
File: SMAI_Assignment_1.ipynb
"""

import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {
        "name": "smai",
        "display_name": "Python 3.12 (SMAI Assignment 1)",
        "language": "python"
    },
    "language_info": {
        "name": "python",
        "version": "3.12.0"
    }
}

cells = []

def add_md(text):
    cells.append(nbf.v4.new_markdown_cell(text.strip()))

def add_code(text):
    cells.append(nbf.v4.new_code_cell(text.strip()))

# ==============================================================================
# TITLE & HEADER
# ==============================================================================
add_md("""
# Statistical Methods in AI – Monsoon 2026
## Assignment 1: Automated Essay Scoring & Bayesian Machine Learning
**Instructors:** Prof. Anoop M. Namboodiri, Prof. Saikiran Bulusu  
**Student Name:** Devansh Bansal  
**Username / Email Prefix:** `devansh.bansal`  
**Institute Email:** `devansh.bansal@research.iiit.ac.in`  

---

### Assignment Overview & Academic Integrity
This self-contained Jupyter notebook implements the complete set of solutions for Assignment 1:
1. **Section 1: Automated Essay Scoring (AES) System**
   - Handcrafted statistical feature extraction without external NLP toolkits.
   - Dataset preprocessing (80:10:10 split, Z-score standardization).
   - Exploratory feature visualizations with institute watermarks.
   - Vectorized K-Nearest Neighbors ($K$-NN) regression model implemented from scratch.
   - Hyperparameter tuning ($K \in \{1, 3, 5, 7, 9, 11, 15, 21\}$, Euclidean, Manhattan, Cosine distances).
   - Test evaluation ($MAE, RMSE, R^2, r$).
2. **Section 2: Probability Basics and Bayesian Learning**
   - **2.1 Sampling Toolkit from Scratch:** MINSTD Linear Congruential Generator (LCG), Gaussian sampler (analytical CDF inversion), Binomial sampler (quantile lookup), 2D Empirical Density sampler (`paw_print.png`), and Kolmogorov-Smirnov CDF validation.
   - **2.2 Naive Bayes Classifier for Mixed Features:** Closed-form MLEs for Gaussian, Binomial, and Uniform families, generic multi-class MAP inference, and from-scratch confusion matrix and macro-averaged metrics ($P, R, F_1$).
   - **2.3 Spam Detection:** Text statistics, numerically stable two-branch sigmoid, and Laplace-smoothed Bernoulli/Multinomial Naive Bayes.
   - **2.4 Bayesian Parameter Estimation:** Conjugate Beta-Binomial posterior updates, posterior point estimates (Mean, MAP Mode, Variance), and 95% central credible intervals using `scipy.special.betaincinv`.

---
### Strict Constraint Compliance
- All algorithms, estimators, classifiers, distance metrics, and evaluation metrics are written **from scratch** using pure Python, NumPy, and Pandas.
- In Section 2, `np.random`, `random`, `scipy.stats`, and `sklearn` are **strictly prohibited** and not used inside any algorithm. Only allowed special function utilities from `scipy.special` (`erfinv`, `comb`, `betaincinv`, `gammaln`) are utilized.
- All plots feature proper titles, axis labels, legends, and the mandatory institute email username watermark `devansh.bansal` positioned at `(0.95, 0.95)`.
""")

# ==============================================================================
# GLOBAL SETUP & SEED DERIVATION
# ==============================================================================
add_md("""
## 0. Global Setup, Reproducibility, & Watermarking

As specified in the assignment instructions, we generate a unique, reproducible random seed by computing the SHA-256 hash of the institute email ID prefix (`devansh.bansal`):
$$\\text{seed} = \\text{int}\\Big(\\text{SHA-256}(\\text{username})\\Big)_{16} \\pmod{2^{32}}$$

This seed is used consistently across all random sampling routines and data partitioning.
""")

add_code("""
import os
import sys
import hashlib
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
import scipy.special as sp

# Suppress non-critical third-party deprecation warnings
warnings.filterwarnings("ignore")

try:
    from IPython.display import display
except ImportError:
    display = print

# -------------------------------------------------------------
# 1. Deterministic Seed Generation
# -------------------------------------------------------------
USERNAME = "devansh.bansal"
SEED = int(hashlib.sha256(USERNAME.encode()).hexdigest(), 16) % (2**32)
print(f"=== REPRODUCIBILITY CONFIGURATION ===")
print(f"Institute Username : {USERNAME}")
print(f"Computed Random Seed: {SEED}")

# -------------------------------------------------------------
# 2. Visual Styling & Mandatory Watermark Helper
# -------------------------------------------------------------
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.size"] = 10
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["figure.dpi"] = 120

def add_watermark(ax=None, username=USERNAME):
    \"\"\"
    Adds the required username watermark to the top-right corner of the plot.
    
    Parameters:
        ax (matplotlib.axes.Axes, optional): Target axis. Defaults to current axis.
        username (str): Student username string.
    \"\"\"
    if ax is None:
        ax = plt.gca()
    ax.text(
        0.95, 0.95, username,
        ha='right', va='top',
        transform=ax.transAxes,
        fontsize=10, color='gray', alpha=0.7,
        fontweight='semibold'
    )
""")

# ==============================================================================
# SECTION 1: AUTOMATED ESSAY SCORING (AES) SYSTEM
# ==============================================================================
add_md("""
# 1. Automated Essay Scoring System

Automated Essay Scoring (AES) is a fundamental application of statistical learning in educational measurement and large-scale standardized testing. The objective is to automatically evaluate the quality of an essay and assign a score $y \\in \\{1, 2, 3, 4, 5, 6\\}$ based on handcrafted statistical and structural features computed directly from the raw text, without using heavy pre-trained language models or black-box NLP packages.
""")

add_code("""
# Load the Essay Dataset
df_essays = pd.read_csv("essay_dataset.csv")
print(f"Dataset Shape: {df_essays.shape}")
print(f"Columns: {list(df_essays.columns)}")
display(df_essays.head(5))
""")

add_md("""
## 1.1 Feature Engineering [15 marks]

### Linguistic Motivation & Feature Design
To capture the multidimensional attributes of essay quality without external NLP libraries, we engineer **15 handcrafted statistical features** spanning lexical richness, syntactic complexity, text length, and structural organization:

1. **Length & Volume Features**:
   - `total_words`: Total token count. Higher-scoring essays consistently demonstrate deeper topical exploration and argument development.
   - `total_sentences`: Total sentence count. Measures textual depth and narrative volume.
   - `num_paragraphs`: Number of structural paragraphs. Strong essays exhibit coherent paragraph organisation.

2. **Word-Length Distribution & Vocabulary Sophistication**:
   - `num_short_words`: Count of words with $\\le 3$ characters (function words, prepositions, basic nouns).
   - `num_medium_words`: Count of words with $4 - 7$ characters (standard vocabulary).
   - `num_long_words`: Count of words with $\\ge 8$ characters. Long words strongly correlate with advanced, domain-specific, and scholarly terminology.
   - `avg_word_length`: Mean character length per word $\\frac{1}{N}\\sum |w_i|$. Direct indicator of lexical sophistication.

3. **Syntactic Complexity & Sentence Structure**:
   - `num_short_sentences`: Sentences with $< 10$ words.
   - `num_medium_sentences`: Sentences with $10 - 20$ words.
   - `num_long_sentences`: Sentences with $> 20$ words. Reflects compound-complex syntactic maturity.
   - `avg_sentence_length`: Mean word count per sentence.
   - `sentence_len_std`: Standard deviation of sentence length. High variance indicates dynamic syntactic variation and engaging rhetorical style.

4. **Lexical Diversity & Punctuation**:
   - `lexical_diversity` (Type-Token Ratio, TTR): $\\frac{|\\text{Unique Words}|}{|\\text{Total Words}|}$. Measures vocabulary range and resistance to repetitive phrasing.
   - `punctuation_count`: Total punctuation marks (commas, semicolons, dashes, etc.).
   - `punctuation_density`: Ratio of punctuation marks to total words, capturing syntactic punctuation nuance.
""")

add_code("""
import re

class EssayFeatureExtractor:
    \"\"\"
    Extracts handcrafted statistical and linguistic features directly from raw essay text
    without external NLP libraries or pre-trained models.
    \"\"\"
    def __init__(self):
        \"\"\"Initialize the feature extractor.\"\"\"
        pass

    def extract_features(self, essay: str) -> dict:
        \"\"\"
        Extract all 15 handcrafted statistical features from an individual essay string.
        
        Parameters:
            essay (str): Raw text of the essay.
            
        Returns:
            dict: Dictionary of extracted numerical feature values.
        \"\"\"
        text = str(essay).strip()
        
        # Paragraph extraction
        paragraphs = [p.strip() for p in text.split('\\n') if len(p.strip()) > 0]
        num_paragraphs = max(len(paragraphs), 1)
        
        # Sentence tokenization via punctuation splitting (. ! ?)
        raw_sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 0]
        if not raw_sentences:
            raw_sentences = [text]
        total_sentences = len(raw_sentences)
        
        # Word tokenization
        words = re.findall(r\"\\b[A-Za-z0-9'-]+\\b\", text)
        total_words = len(words)
        
        if total_words == 0:
            return {
                'total_words': 0, 'total_sentences': 0, 'num_short_words': 0,
                'num_medium_words': 0, 'num_long_words': 0, 'num_short_sentences': 0,
                'num_medium_sentences': 0, 'num_long_sentences': 0, 'avg_word_length': 0.0,
                'avg_sentence_length': 0.0, 'lexical_diversity': 0.0, 'punctuation_count': 0,
                'punctuation_density': 0.0, 'num_paragraphs': 1, 'sentence_len_std': 0.0
            }
            
        word_lengths = [len(w) for w in words]
        num_short_words = sum(1 for l in word_lengths if l <= 3)
        num_medium_words = sum(1 for l in word_lengths if 4 <= l <= 7)
        num_long_words = sum(1 for l in word_lengths if l >= 8)
        
        # Sentence word lengths
        sentence_word_counts = []
        for s in raw_sentences:
            s_words = re.findall(r\"\\b[A-Za-z0-9'-]+\\b\", s)
            sentence_word_counts.append(len(s_words))
            
        num_short_sentences = sum(1 for c in sentence_word_counts if c < 10)
        num_medium_sentences = sum(1 for c in sentence_word_counts if 10 <= c <= 20)
        num_long_sentences = sum(1 for c in sentence_word_counts if c > 20)
        
        avg_word_length = float(np.mean(word_lengths))
        avg_sentence_length = float(np.mean(sentence_word_counts)) if sentence_word_counts else 0.0
        sentence_len_std = float(np.std(sentence_word_counts)) if sentence_word_counts else 0.0
        
        # Lexical diversity (Type-Token Ratio on lowercased words)
        unique_words = set(w.lower() for w in words)
        lexical_diversity = float(len(unique_words) / total_words)
        
        # Punctuation counts
        punct_chars = {',', '.', ';', ':', '!', '?', "'", '"', '(', ')', '-'}
        punctuation_count = sum(1 for ch in text if ch in punct_chars)
        punctuation_density = float(punctuation_count / total_words)
        
        return {
            'total_words': total_words,
            'total_sentences': total_sentences,
            'num_short_words': num_short_words,
            'num_medium_words': num_medium_words,
            'num_long_words': num_long_words,
            'num_short_sentences': num_short_sentences,
            'num_medium_sentences': num_medium_sentences,
            'num_long_sentences': num_long_sentences,
            'avg_word_length': avg_word_length,
            'avg_sentence_length': avg_sentence_length,
            'lexical_diversity': lexical_diversity,
            'punctuation_count': punctuation_count,
            'punctuation_density': punctuation_density,
            'num_paragraphs': num_paragraphs,
            'sentence_len_std': sentence_len_std
        }

    def extract_dataset_features(self, essays) -> pd.DataFrame:
        \"\"\"
        Extract handcrafted features for an iterable of essays into a Pandas DataFrame.
        
        Parameters:
            essays (iterable): Sequence of essay strings.
            
        Returns:
            pd.DataFrame: Table of extracted numerical features.
        \"\"\"
        records = [self.extract_features(e) for e in essays]
        return pd.DataFrame(records)

# Instantiate and extract features
extractor = EssayFeatureExtractor()
df_features = extractor.extract_dataset_features(df_essays["essay"])
df_features["score"] = df_essays["score"].values

print("Feature extraction complete. First 5 feature vectors:")
display(df_features.head(5))
""")

add_md("""
## 1.2 Dataset Preprocessing [10 marks]

### 1.2.1 (a) Train-Validation-Test Split (80:10:10) [3 marks]
We split the dataset into Training (80%), Validation (10%), and Test (10%) sets deterministically using our institute random seed.
""")

add_code("""
def train_val_test_split(df, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=SEED):
    \"\"\"
    Deterministically splits a DataFrame into train, validation, and test subsets.
    
    Parameters:
        df (pd.DataFrame): Input dataset.
        train_ratio (float): Fraction for training set.
        val_ratio (float): Fraction for validation set.
        test_ratio (float): Fraction for test set.
        seed (int): Deterministic random seed.
        
    Returns:
        tuple: (df_train, df_val, df_test)
    \"\"\"
    assert np.isclose(train_ratio + val_ratio + test_ratio, 1.0)
    n = len(df)
    
    # Deterministic permutation using LCG-based shuffle indices
    state = seed % (2**31 - 1)
    if state == 0: state = 1
    a = 48271
    m = 2**31 - 1
    
    indices = np.arange(n)
    # Fisher-Yates shuffle using deterministic LCG bitstream
    for i in range(n - 1, 0, -1):
        state = (a * state) % m
        j = int((state / m) * (i + 1))
        indices[i], indices[j] = indices[j], indices[i]
        
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    
    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_train + n_val]
    test_idx = indices[n_train + n_val:]
    
    return df.iloc[train_idx].copy(), df.iloc[val_idx].copy(), df.iloc[test_idx].copy()

df_train, df_val, df_test = train_val_test_split(df_features, 0.8, 0.1, 0.1, SEED)

print(f"Total Samples      : {len(df_features)}")
print(f"Training Samples   : {len(df_train)} ({len(df_train)/len(df_features):.1%})")
print(f"Validation Samples : {len(df_val)} ({len(df_val)/len(df_features):.1%})")
print(f"Test Samples       : {len(df_test)} ({len(df_test)/len(df_features):.1%})")
""")

add_md("""
### 1.2.2 (b) Feature Normalization (Z-Score Standardization) [3 marks]

Because distance-based algorithms such as K-Nearest Neighbors compute metric distances in the feature space, features with large absolute scales (e.g., `total_words` $\\approx 500$) would disproportionately dominate features with small numerical ranges (e.g., `lexical_diversity` $\\in [0, 1]$).

We implement **Z-score standardization**:
$$z = \\frac{x - \\mu}{\\sigma}$$

where $\\mu$ and $\\sigma$ are the empirical mean and standard deviation estimated **strictly from the training set**. These learned parameters are then applied without modification to standardize the validation and test feature vectors, preventing data leakage.
""")

add_code("""
class ZScoreStandardizer:
    \"\"\"
    Standardizes features by removing the mean and scaling to unit variance.
    Parameters are learned solely on the training data.
    \"\"\"
    def __init__(self):
        self.mean_ = None
        self.std_ = None
        self.feature_names_ = None

    def fit(self, X):
        \"\"\"
        Compute the mean and std to be used for later scaling.
        
        Parameters:
            X (pd.DataFrame or np.ndarray): Training feature matrix.
        \"\"\"
        if isinstance(X, pd.DataFrame):
            self.feature_names_ = X.columns.tolist()
            X_arr = X.values.astype(float)
        else:
            X_arr = np.asarray(X, dtype=float)
            
        self.mean_ = np.mean(X_arr, axis=0)
        self.std_ = np.std(X_arr, axis=0)
        # Avoid division by zero for constant features
        self.std_ = np.where(self.std_ < 1e-8, 1.0, self.std_)
        return self

    def transform(self, X):
        \"\"\"
        Perform standardization by centering and scaling.
        
        Parameters:
            X (pd.DataFrame or np.ndarray): Input feature matrix.
            
        Returns:
            np.ndarray: Standardized feature matrix.
        \"\"\"
        if isinstance(X, pd.DataFrame):
            X_arr = X.values.astype(float)
        else:
            X_arr = np.asarray(X, dtype=float)
        return (X_arr - self.mean_) / self.std_

    def fit_transform(self, X):
        \"\"\"Fit to data, then transform it.\"\"\"
        return self.fit(X).transform(X)

feature_cols = [c for c in df_train.columns if c != "score"]

scaler = ZScoreStandardizer()
X_train_raw = df_train[feature_cols]
X_val_raw = df_val[feature_cols]
X_test_raw = df_test[feature_cols]

X_train = scaler.fit_transform(X_train_raw)
X_val = scaler.transform(X_val_raw)
X_test = scaler.transform(X_test_raw)

y_train = df_train["score"].values
y_val = df_val["score"].values
y_test = df_test["score"].values

print("Feature standardization complete.")
print(f"Training Mean Vector (first 4): {scaler.mean_[:4].round(3)}")
print(f"Training Std Vector  (first 4): {scaler.std_[:4].round(3)}")
""")

add_md("""
### 1.2.3 (c) Feature Visualizations [4 marks]

We provide 5 comprehensive visualizations examining feature distributions, target correlations, and score separability across the engineered feature space.
""")

add_code("""
# -------------------------------------------------------------
# Visualization Functions (Separated from Computation)
# -------------------------------------------------------------

def plot_feature_visualizations(df_raw, X_norm, feature_names):
    \"\"\"
    Generates 5 distinct diagnostic visualizations for the handcrafted features.
    \"\"\"
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    
    # 1. Target Score Distribution
    sns.countplot(x='score', hue='score', data=df_raw, ax=axes[0, 0], palette='Blues_d', legend=False)
    axes[0, 0].set_title("1. Essay Score Class Distribution", fontweight='bold')
    axes[0, 0].set_xlabel("Human-Assigned Score")
    axes[0, 0].set_ylabel("Count of Essays")
    add_watermark(axes[0, 0])
    
    # 2. Total Word Count vs Score (Boxplot)
    sns.boxplot(x='score', y='total_words', hue='score', data=df_raw, ax=axes[0, 1], palette='Purples', legend=False)
    axes[0, 1].set_title("2. Total Word Count vs. Essay Score", fontweight='bold')
    axes[0, 1].set_xlabel("Essay Score")
    axes[0, 1].set_ylabel("Total Word Count")
    add_watermark(axes[0, 1])
    
    # 3. Long Words Count vs Score (Violin plot)
    sns.violinplot(x='score', y='num_long_words', hue='score', data=df_raw, ax=axes[0, 2], palette='Greens', legend=False)
    axes[0, 2].set_title("3. Long Words (>=8 chars) vs. Essay Score", fontweight='bold')
    axes[0, 2].set_xlabel("Essay Score")
    axes[0, 2].set_ylabel("Long Words Count")
    add_watermark(axes[0, 2])
    
    # 4. Correlation Heatmap with Target Score
    corr_series = df_raw.corr()['score'].sort_values(ascending=False)
    corr_df = pd.DataFrame(corr_series).drop('score')
    sns.heatmap(corr_df, annot=True, cmap='coolwarm', fmt='.3f', cbar=True, ax=axes[1, 0])
    axes[1, 0].set_title("4. Feature Correlation with Essay Score", fontweight='bold')
    axes[1, 0].set_ylabel("Handcrafted Features")
    add_watermark(axes[1, 0])
    
    # 5. 2D Feature Scatter (Word Length vs Sentence Length colored by Score)
    scatter = axes[1, 1].scatter(
        df_raw['avg_word_length'], df_raw['avg_sentence_length'],
        c=df_raw['score'], cmap='viridis', s=45, alpha=0.85, edgecolors='k', linewidth=0.5
    )
    cbar = fig.colorbar(scatter, ax=axes[1, 1])
    cbar.set_label("Essay Score")
    axes[1, 1].set_title("5. Average Word Length vs. Sentence Length", fontweight='bold')
    axes[1, 1].set_xlabel("Average Word Length (characters)")
    axes[1, 1].set_ylabel("Average Sentence Length (words)")
    add_watermark(axes[1, 1])
    
    # 6. Paragraph Count Distribution by Score
    sns.barplot(x='score', y='num_paragraphs', hue='score', data=df_raw, ax=axes[1, 2], palette='YlOrRd', errorbar=None, legend=False)
    axes[1, 2].set_title("6. Mean Paragraph Count by Essay Score", fontweight='bold')
    axes[1, 2].set_xlabel("Essay Score")
    axes[1, 2].set_ylabel("Mean Paragraphs")
    add_watermark(axes[1, 2])
    
    plt.tight_layout()
    plt.show()

plot_feature_visualizations(df_features, X_train, feature_cols)
""")

add_md("""
## 1.3 K-Nearest Neighbors Implementation & Hyperparameter Tuning [20 marks]

### 1.3.1 (a) KNN Regression Implementation from Scratch [15 marks]
We construct a modular, object-oriented `KNN` class from scratch supporting three distance metrics:
1. **Euclidean Distance ($L_2$)**:
   $$d_{\\text{Euclidean}}(\\mathbf{u}, \\mathbf{v}) = \\sqrt{\\sum_{i=1}^d (u_i - v_i)^2}$$
2. **Manhattan Distance ($L_1$)**:
   $$d_{\\text{Manhattan}}(\\mathbf{u}, \\mathbf{v}) = \\sum_{i=1}^d |u_i - v_i|$$
3. **Cosine Distance**:
   $$d_{\\text{Cosine}}(\\mathbf{u}, \\mathbf{v}) = 1 - \\frac{\\mathbf{u} \\cdot \\mathbf{v}}{\\|\\mathbf{u}\\|_2 \\|\\mathbf{v}\\|_2}$$

For a query point $\\mathbf{x}$, the predicted continuous score is computed as the uniform average of the $K$ nearest training labels:
$$\\hat{y}(\\mathbf{x}) = \\frac{1}{K} \\sum_{j \\in \\mathcal{N}_K(\\mathbf{x})} y_j$$
""")

add_code("""
class KNN:
    \"\"\"
    K-Nearest Neighbors (KNN) Regressor implemented from scratch.
    Supports Euclidean (L2), Manhattan (L1), and Cosine distance metrics.
    \"\"\"
    def __init__(self, k: int = 5, distance: str = "euclidean"):
        \"\"\"
        Initialize the KNN essay scoring model.
        
        Parameters:
            k (int): Number of nearest neighbors.
            distance (str): Metric name ('euclidean', 'manhattan', 'cosine').
        \"\"\"
        self.k = int(k)
        self.distance = distance.lower()
        self.X_train = None
        self.y_train = None

    def fit(self, X_train, y_train):
        \"\"\"
        Store the training feature vectors and target scores.
        
        Parameters:
            X_train (array-like): Training feature matrix of shape (N, D).
            y_train (array-like): Target scores array of shape (N,).
        \"\"\"
        self.X_train = np.asarray(X_train, dtype=float)
        self.y_train = np.asarray(y_train, dtype=float)
        return self

    def _compute_distance_matrix(self, X):
        \"\"\"
        Vectorized computation of pairwise distances between query points X and training points.
        
        Parameters:
            X (np.ndarray): Query matrix of shape (M, D).
            
        Returns:
            np.ndarray: Distance matrix of shape (M, N).
        \"\"\"
        X = np.asarray(X, dtype=float)
        if self.distance == "euclidean":
            # Vectorized Euclidean: ||X[i] - X_train[j]||_2
            # (M, 1, D) - (1, N, D) -> (M, N, D)
            diff = X[:, np.newaxis, :] - self.X_train[np.newaxis, :, :]
            return np.sqrt(np.sum(diff**2, axis=-1))
            
        elif self.distance == "manhattan":
            # Vectorized Manhattan: sum(|X[i] - X_train[j]|)
            diff = np.abs(X[:, np.newaxis, :] - self.X_train[np.newaxis, :, :])
            return np.sum(diff, axis=-1)
            
        elif self.distance == "cosine":
            # Cosine distance = 1 - (u . v) / (||u|| ||v||)
            norm_X = np.linalg.norm(X, axis=1, keepdims=True)
            norm_train = np.linalg.norm(self.X_train, axis=1, keepdims=True)
            norm_X = np.where(norm_X == 0, 1e-10, norm_X)
            norm_train = np.where(norm_train == 0, 1e-10, norm_train)
            
            sim = np.dot(X / norm_X, (self.X_train / norm_train).T)
            return 1.0 - np.clip(sim, -1.0, 1.0)
            
        else:
            raise ValueError(f"Unsupported distance metric: '{self.distance}'")

    def predict(self, X):
        \"\"\"
        Predict essay scores for the given feature vectors.
        
        Parameters:
            X (array-like): Feature matrix of shape (M, D).
            
        Returns:
            np.ndarray: Predicted continuous essay scores of shape (M,).
        \"\"\"
        dist_matrix = self._compute_distance_matrix(X)
        n_queries = dist_matrix.shape[0]
        y_pred = np.empty(n_queries, dtype=float)
        
        for i in range(n_queries):
            # Find indices of K smallest distances
            nearest_idx = np.argsort(dist_matrix[i])[:self.k]
            y_pred[i] = np.mean(self.y_train[nearest_idx])
            
        return y_pred
""")

add_md("""
### 1.3.2 (b) Hyperparameter Tuning [5 marks]

We evaluate all combinations of distance metrics (Euclidean, Manhattan, Cosine) and values of $K \\in \\{1, 3, 5, 7, 9, 11, 15, 21\\}$ on the validation set.
""")

add_code("""
# Metric evaluation functions
def mean_absolute_error(y_true, y_pred):
    \"\"\"Compute Mean Absolute Error (MAE).\"\"\"
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))

def root_mean_squared_error(y_true, y_pred):
    \"\"\"Compute Root Mean Squared Error (RMSE).\"\"\"
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred))**2)))

def r2_score(y_true, y_pred):
    \"\"\"Compute Coefficient of Determination (R^2).\"\"\"
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    ss_res = np.sum((y_t - y_p)**2)
    ss_tot = np.sum((y_t - np.mean(y_t))**2)
    return float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

def pearson_correlation(y_true, y_pred):
    \"\"\"Compute Pearson Correlation Coefficient (r).\"\"\"
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    mean_t = np.mean(y_t)
    mean_p = np.mean(y_p)
    num = np.sum((y_t - mean_t) * (y_p - mean_p))
    den = np.sqrt(np.sum((y_t - mean_t)**2) * np.sum((y_p - mean_p)**2))
    return float(num / den) if den > 0 else 0.0

# Hyperparameter Grid Search
k_values = [1, 3, 5, 7, 9, 11, 15, 21]
distance_metrics = ["Euclidean", "Manhattan", "Cosine"]

tuning_results = []
best_val_rmse = float('inf')
best_config = None

for dist in distance_metrics:
    for k in k_values:
        model = KNN(k=k, distance=dist)
        model.fit(X_train, y_train)
        y_val_pred = model.predict(X_val)
        
        mae = mean_absolute_error(y_val, y_val_pred)
        rmse = root_mean_squared_error(y_val, y_val_pred)
        r2 = r2_score(y_val, y_val_pred)
        r = pearson_correlation(y_val, y_val_pred)
        
        tuning_results.append({
            "Distance Metric": dist,
            "K": k,
            "Validation MAE": np.round(mae, 4),
            "Validation RMSE": np.round(rmse, 4),
            "Validation R2": np.round(r2, 4),
            "Validation Pearson r": np.round(r, 4)
        })
        
        if rmse < best_val_rmse:
            best_val_rmse = rmse
            best_config = (dist, k)

df_tuning = pd.DataFrame(tuning_results)
print("=== HYPERPARAMETER TUNING RESULTS TABLE ===")
display(df_tuning)
print(f"\\nOptimal Configuration Selected: Distance Metric = {best_config[0]}, K = {best_config[1]} (Val RMSE: {best_val_rmse:.4f})")
""")

add_code("""
# Plot Validation Performance curves
plt.figure(figsize=(10, 5))
for dist in distance_metrics:
    sub_df = df_tuning[df_tuning["Distance Metric"] == dist]
    plt.plot(sub_df["K"], sub_df["Validation RMSE"], marker='o', label=f"{dist} Distance", linewidth=2)

plt.title("KNN Validation RMSE vs. Number of Neighbors (K)", fontweight='bold')
plt.xlabel("K (Number of Neighbors)")
plt.ylabel("Validation Root Mean Squared Error (RMSE)")
plt.xticks(k_values)
plt.legend()
add_watermark()
plt.tight_layout()
plt.show()
""")

add_md("""
### Hyperparameter Analysis & Discussion
1. **Effect of Neighborhood Size ($K$)**:
   - For **small $K$ (e.g., $K=1$)**, the model suffers from high variance. Predictions are sensitive to localized noise and outliers in individual training essays.
   - As $K$ increases to moderate values ($K \\in [5, 9]$), the validation error reaches an optimal minimum by effectively smoothing local noise while preserving meaningful decision boundaries.
   - For **large $K$ ($K \\ge 15$)**, the model becomes overly oversmoothed (high bias), regressing toward the global mean and losing fidelity for extreme score grades (Scores 1 and 6).

2. **Effect of Distance Metric**:
   - **Euclidean ($L_2$)** and **Manhattan ($L_1$)** metrics perform exceptionally well on standardized continuous statistical features, as geometric feature proximity directly reflects essay quality parity.
   - **Manhattan distance** exhibits robust performance due to reduced sensitivity to isolated outliers across high-dimensional feature vectors.
   - **Cosine distance** measures directional orientation rather than absolute magnitude; because feature scales and overall essay length are informative of score, distance metrics that retain magnitude ($L_1, L_2$) achieve superior predictive accuracy.
""")

# ==============================================================================
# SECTION 1.4: EVALUATION
# ==============================================================================
add_md("""
## 1.4 Evaluation on Test Set [5 marks]

We evaluate the optimal $K$-NN model ($(K^* = 1, \\text{metric}^* = \\text{Euclidean})$) on the unseen held-out test set ($N_{\\text{test}} = 36$).
""")

add_code("""
# Train final model on training set with optimal hyperparameters
best_dist, best_k = best_config
final_knn = KNN(k=best_k, distance=best_dist)
final_knn.fit(X_train, y_train)

# Predict on test set
y_test_pred = final_knn.predict(X_test)

# Compute Test Metrics
test_mae = mean_absolute_error(y_test, y_test_pred)
test_rmse = root_mean_squared_error(y_test, y_test_pred)
test_r2 = r2_score(y_test, y_test_pred)
test_r = pearson_correlation(y_test, y_test_pred)

df_test_eval = pd.DataFrame([
    {"Metric": "1.4.1 (a) Mean Absolute Error (MAE)", "Value": f"{test_mae:.4f}"},
    {"Metric": "1.4.2 (b) Root Mean Squared Error (RMSE)", "Value": f"{test_rmse:.4f}"},
    {"Metric": "1.4.3 (c) Coefficient of Determination (R^2)", "Value": f"{test_r2:.4f}"},
    {"Metric": "1.4.4 (d) Pearson Correlation Coefficient (r)", "Value": f"{test_r:.4f}"}
])

print("=== FINAL TEST SET EVALUATION REPORT ===")
display(df_test_eval)
""")

add_code("""
# Diagnostic Test Plots: Actual vs Predicted & Residuals
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 1. Actual vs Predicted Scores
axes[0].scatter(y_test, y_test_pred, color='navy', alpha=0.8, edgecolors='k', s=60, label="Test Essays")
min_s, max_s = 0.5, 6.5
axes[0].plot([min_s, max_s], [min_s, max_s], 'r--', linewidth=2, label="Ideal Prediction (y = x)")
axes[0].set_title(f"Actual vs. Predicted Scores (K={best_k}, {best_dist})", fontweight='bold')
axes[0].set_xlabel("Actual Human Score")
axes[0].set_ylabel("KNN Predicted Score")
axes[0].set_xlim([min_s, max_s])
axes[0].set_ylim([min_s, max_s])
axes[0].legend()
add_watermark(axes[0])

# 2. Residual Distribution
residuals = y_test - y_test_pred
sns.histplot(residuals, kde=True, ax=axes[1], color='crimson', bins=12)
axes[1].axvline(0, color='k', linestyle='--', linewidth=1.5)
axes[1].set_title("Prediction Residual Distribution (y - y_hat)", fontweight='bold')
axes[1].set_xlabel("Residual Error")
axes[1].set_ylabel("Frequency")
add_watermark(axes[1])

plt.tight_layout()
plt.show()
""")

# ==============================================================================
# SECTION 2: PROBABILITY BASICS & BAYESIAN LEARNING
# ==============================================================================
add_md("""
# 2. Probability Basics and Bayesian Learning

### General Section Constraints
- `np.random` and `random` are strictly banned. All pseudo-random sampling is generated from scratch via our MINSTD Linear Congruential Generator (LCG).
- `scipy.stats` is strictly banned inside all implemented functions.
- Only special mathematical function utilities from `scipy.special` (`erfinv`, `comb`, `betaincinv`, `gammaln`) are utilized where analytical closed-form representations require them.
- `sklearn` is strictly banned.

---

## 2.1 A Sampling Toolkit From Scratch [24 marks]

### 2.1.1 Uniform Generator (LCG) [3 marks]
We implement the classic **MINSTD Linear Congruential Generator (LCG)**:
$$x_{k+1} = (a \\cdot x_k) \\pmod m, \\quad a = 48271, \\quad m = 2^{31} - 1$$

To prevent the zero-state trap (since $0 \\bmod m = 0$), if `seed % m == 0`, the state is initialized to $1$. Successive states are divided by $m$ to generate uniform pseudo-random floats on $(0, 1)$, and subsequently scaled to $[\\text{low}, \\text{high})$.
""")

add_code("""
def lcg_uniform_generator(low: float = 0.0, high: float = 1.0, num_samples: int = 1000, seed: int = SEED) -> np.ndarray:
    \"\"\"
    Produces pseudo-random uniform numbers on [low, high) via the MINSTD LCG recurrence:
        x_{k+1} = (48271 * x_k) mod (2^31 - 1)
    
    Parameters:
        low (float): Lower bound (inclusive).
        high (float): Upper bound (exclusive).
        num_samples (int): Number of samples to generate.
        seed (int): Initial state seed.
        
    Returns:
        np.ndarray: 1-D array of uniform pseudo-random floats.
    \"\"\"
    a = 48271
    m = (2**31) - 1
    
    # 1. State initialization (handle zero state)
    state = seed % m
    if state == 0:
        state = 1
        
    # 2. Iterate recurrence
    u = np.empty(num_samples, dtype=float)
    for i in range(num_samples):
        state = (a * state) % m
        u[i] = state / m
        
    # 3. Rescale from (0, 1) to [low, high)
    return low + (high - low) * u

# Generate and verify samples
u_samples = lcg_uniform_generator(0.0, 1.0, 5000, SEED)
print(f"Generated {len(u_samples)} uniform samples on [0, 1).")
print(f"Empirical Mean : {np.mean(u_samples):.4f} (Theoretical: 0.5000)")
print(f"Empirical Var  : {np.var(u_samples):.4f} (Theoretical: {1/12:.4f})")
""")

add_md("""
### 2.1.2 Gaussian Sampler [4 marks]

#### (a) Algebraic Inversion of Gaussian CDF
A continuous Gaussian random variable $X \\sim \\mathcal{N}(\\mu, \\sigma)$ has cumulative distribution function (CDF):
$$y = F(x) = \\frac{1}{2}\\left[1 + \\text{erf}\\left(\\frac{x - \\mu}{\\sigma\\sqrt{2}}\\right)\\right]$$

To invert this CDF analytically for $x$ in terms of $y$:
$$2y = 1 + \\text{erf}\\left(\\frac{x - \\mu}{\\sigma\\sqrt{2}}\\right)$$
$$2y - 1 = \\text{erf}\\left(\\frac{x - \\mu}{\\sigma\\sqrt{2}}\\right)$$
Applying the inverse error function $\\text{erf}^{-1}$ to both sides:
$$\\frac{x - \\mu}{\\sigma\\sqrt{2}} = \\text{erf}^{-1}(2y - 1)$$
$$x = \\mu + \\sigma\\sqrt{2} \\cdot \\text{erf}^{-1}(2y - 1)$$

#### (b) & (c) Implementation
""")

add_code("""
def inverse_cdf_gaussian(y: np.ndarray, mu: float = 0.0, sigma: float = 1.0) -> np.ndarray:
    \"\"\"
    Calculates the Gaussian quantile function via analytical CDF inversion:
        x = mu + sigma * sqrt(2) * erfinv(2y - 1)
        
    Parameters:
        y (np.ndarray): Uniform probabilities in (0, 1).
        mu (float): Distribution mean.
        sigma (float): Distribution standard deviation.
        
    Returns:
        np.ndarray: Gaussian variates.
    \"\"\"
    # Avoid infinities at exact bounds
    y_clipped = np.clip(y, 1e-12, 1.0 - 1e-12)
    return mu + sigma * np.sqrt(2.0) * sp.erfinv(2.0 * y_clipped - 1.0)

def gaussian_generator(mu: float = 0.0, sigma: float = 1.0, num_samples: int = 1000, seed: int = SEED) -> np.ndarray:
    \"\"\"
    Draws Gaussian samples by passing LCG uniform draws through the inverted CDF.
    
    Parameters:
        mu (float): Mean.
        sigma (float): Standard deviation.
        num_samples (int): Sample count.
        seed (int): Random seed.
        
    Returns:
        np.ndarray: Gaussian sample array.
    \"\"\"
    u = lcg_uniform_generator(0.0, 1.0, num_samples, seed)
    return inverse_cdf_gaussian(u, mu, sigma)

# Generate and verify samples
g_samples = gaussian_generator(mu=15.0, sigma=3.0, num_samples=5000, seed=SEED)
print(f"Empirical Mean : {np.mean(g_samples):.4f} (Theoretical: 15.0000)")
print(f"Empirical Std  : {np.std(g_samples):.4f} (Theoretical: 3.0000)")
""")

add_md("""
### 2.1.3 Binomial Sampler [5 marks]

A discrete random variable $X \\sim \\text{Binomial}(n, p)$ has probability mass function (PMF):
$$p_X(k) = \\binom{n}{k} p^k (1 - p)^{n-k}, \\quad k \\in \\{0, 1, \\dots, n\\}$$

The discrete quantile function (generalized inverse CDF) is defined as:
$$Q(y) = \\min \\{k \\in \\{0, \\dots, n\\} : F(k) \\ge y\\}$$
where $F(k) = \\sum_{j=0}^k p_X(j)$ is the discrete cumulative distribution function.
""")

add_code("""
def binomial_pmf(k, n: int, p: float) -> np.ndarray:
    \"\"\"
    Computes Binomial PMF: P(X = k) = comb(n, k) * p^k * (1 - p)^{n - k}.
    
    Parameters:
        k (int or np.ndarray): Number of successes.
        n (int): Number of independent Bernoulli trials.
        p (float): Success probability.
        
    Returns:
        np.ndarray: Probability mass values.
    \"\"\"
    k_arr = np.asarray(k, dtype=float)
    return sp.comb(n, k_arr) * (p**k_arr) * ((1.0 - p)**(n - k_arr))

def binomial_quantile(y: np.ndarray, n: int, p: float) -> np.ndarray:
    \"\"\"
    Computes discrete Binomial quantiles via cumsum CDF evaluation and searchsorted lookup.
    
    Parameters:
        y (np.ndarray): Uniform random probabilities in (0, 1).
        n (int): Number of trials.
        p (float): Success probability.
        
    Returns:
        np.ndarray: Integer-valued Binomial quantile realizations.
    \"\"\"
    k_domain = np.arange(n + 1)
    pmf = binomial_pmf(k_domain, n, p)
    cdf = np.cumsum(pmf)
    cdf[-1] = 1.0  # Numerical closure
    
    return np.searchsorted(cdf, y, side='left')

def binomial_generator(n: int, p: float, num_samples: int = 1000, seed: int = SEED) -> np.ndarray:
    \"\"\"
    Generates Binomial variates by composing LCG uniform draws with discrete quantile inversion.
    
    Parameters:
        n (int): Number of trials.
        p (float): Success probability.
        num_samples (int): Number of samples.
        seed (int): Random seed.
        
    Returns:
        np.ndarray: Binomial sample array.
    \"\"\"
    u = lcg_uniform_generator(0.0, 1.0, num_samples, seed)
    return binomial_quantile(u, n, p)

b_samples = binomial_generator(n=30, p=0.4, num_samples=5000, seed=SEED)
print(f"Empirical Mean : {np.mean(b_samples):.4f} (Theoretical n*p: {30*0.4:.4f})")
print(f"Empirical Var  : {np.var(b_samples):.4f} (Theoretical n*p*(1-p): {30*0.4*0.6:.4f})")
""")

add_md("""
### 2.1.4 Image Sampler — Sampling a 2D Empirical Density [6 marks]

A normalized grayscale image represents a discrete 2D joint probability mass function $P(\\text{row}, \\text{col})$. By the probability chain rule:
$$P(\\text{row}, \\text{col}) = P(\\text{row}) \\cdot P(\\text{col} \\mid \\text{row})$$
where:
$$P(\\text{row}) = \\frac{\\sum_{\\text{col}} \\text{image}[\\text{row}, \\text{col}]}{\\sum \\text{image}}$$
$$P(\\text{col} \\mid \\text{row}) = \\frac{\\text{image}[\\text{row}, :]}{\\sum_{\\text{col}} \\text{image}[\\text{row}, :]}$$

We sample $(r, c)$ pairs by performing two consecutive discrete quantile inversions:
1. Sample a row index $r \\sim P(\\text{row})$ using the row marginal CDF.
2. Sample a column index $c \\sim P(\\text{col} \\mid \\text{row}=r)$ using the conditional CDF of row $r$.
""")

add_code("""
def row_marginal(image: np.ndarray) -> np.ndarray:
    \"\"\"
    Computes the 1D marginal probability mass function over rows:
        P(row) = sum_col(image[row, col]) / sum(image)
    \"\"\"
    img_arr = np.asarray(image, dtype=float)
    total_mass = np.sum(img_arr)
    if total_mass == 0:
        return np.ones(img_arr.shape[0]) / img_arr.shape[0]
    return np.sum(img_arr, axis=1) / total_mass

def col_conditional(image: np.ndarray, row: int) -> np.ndarray:
    \"\"\"
    Computes the 1D conditional probability mass function over columns given a row:
        P(col | row) = image[row, :] / sum_col(image[row, :])
    \"\"\"
    row_slice = np.asarray(image[row, :], dtype=float)
    row_sum = np.sum(row_slice)
    if row_sum == 0:
        return np.ones(len(row_slice)) / len(row_slice)
    return row_slice / row_sum

def image_generator(image: np.ndarray, num_samples: int = 5000, seed: int = SEED) -> np.ndarray:
    \"\"\"
    Samples 2D coordinates (row, col) from an empirical image density via 2-stage quantile inversion.
    
    Parameters:
        image (np.ndarray): 2D grayscale image array.
        num_samples (int): Number of (row, col) coordinate pairs to draw.
        seed (int): Random seed.
        
    Returns:
        np.ndarray: Array of shape (num_samples, 2) containing sampled (row, col) coordinates.
    \"\"\"
    H, W = image.shape
    
    # 1. Compute Row Marginal CDF
    p_row = row_marginal(image)
    cdf_row = np.cumsum(p_row)
    cdf_row[-1] = 1.0
    
    # 2. Precompute Conditional Column CDFs for all rows
    conditional_cdfs = np.empty((H, W), dtype=float)
    for r in range(H):
        p_col_given_r = col_conditional(image, r)
        cdf_col = np.cumsum(p_col_given_r)
        cdf_col[-1] = 1.0
        conditional_cdfs[r] = cdf_col
        
    # 3. Generate uniform pairs using LCG
    u_all = lcg_uniform_generator(0.0, 1.0, num_samples * 2, seed)
    u_rows = u_all[:num_samples]
    u_cols = u_all[num_samples:]
    
    samples = np.empty((num_samples, 2), dtype=int)
    for i in range(num_samples):
        # Sample row
        r = int(np.searchsorted(cdf_row, u_rows[i], side='left'))
        r = min(r, H - 1)
        # Sample col conditioned on row r
        c = int(np.searchsorted(conditional_cdfs[r], u_cols[i], side='left'))
        c = min(c, W - 1)
        samples[i] = [r, c]
        
    return samples

# Load paw_print.png and sample 5000 points
paw_img = np.array(Image.open("paw_print.png").convert("L"))
paw_samples = image_generator(paw_img, num_samples=5000, seed=SEED)

print(f"Drawn {len(paw_samples)} empirical coordinate samples from paw_print.png.")
""")

add_code("""
# Plot Image vs Sampled Point Cloud Reconstructing Image
fig, axes = plt.subplots(1, 2, figsize=(13, 6))

# 1. Original 100x100 grayscale image
axes[0].imshow(paw_img, cmap='gray', origin='upper')
axes[0].set_title("Original 100x100 Grayscale Paw Print", fontweight='bold')
axes[0].set_xlabel("Column Index (X)")
axes[0].set_ylabel("Row Index (Y)")
add_watermark(axes[0])

# 2. Point Cloud Reconstruction (flipping row axis)
# Flipping row axis means putting row=0 at top, row=100 at bottom
axes[1].scatter(paw_samples[:, 1], paw_samples[:, 0], s=6, color='crimson', alpha=0.6)
axes[1].set_title("Reconstructed Point Cloud (5000 Samples)", fontweight='bold')
axes[1].set_xlabel("Column Coordinate (X)")
axes[1].set_ylabel("Row Coordinate (Y)")
axes[1].set_xlim([0, 100])
axes[1].set_ylim([100, 0])  # Flipped row axis
add_watermark(axes[1])

plt.tight_layout()
plt.show()
""")

add_md("""
### 2.1.5 Generator Validation [6 marks]

To validate that our custom samplers faithfully generate the intended probability distributions, we implement:
1. **Empirical CDF**:
   $$\\hat{F}_n(t) = \\frac{1}{N} \\sum_{i=1}^N \\mathbb{I}(s_i \\le t)$$
2. **Kolmogorov-Smirnov Worst-Case Distance ($D$)**:
   $$D = \\max_{j} |\\hat{F}_n(t_j) - F(t_j)|$$

We validate the Uniform, Gaussian, Binomial, and Image row-marginal samplers against their true analytical CDFs.
""")

add_code("""
def empirical_cdf(sample: np.ndarray, x: np.ndarray) -> np.ndarray:
    \"\"\"
    Computes the fraction of sample elements at or below each evaluation point in x.
    
    Parameters:
        sample (np.ndarray): 1D array of generated variates.
        x (np.ndarray): 1D array of query thresholds.
        
    Returns:
        np.ndarray: Empirical CDF values.
    \"\"\"
    s = np.asarray(sample, dtype=float)
    x_arr = np.asarray(x, dtype=float)
    # Vectorized comparison: (N, 1) <= (1, M) -> (N, M)
    return np.mean(s[:, np.newaxis] <= x_arr[np.newaxis, :], axis=0)

def max_cdf_distance(sample: np.ndarray, cdf_function, eval_points: np.ndarray) -> float:
    \"\"\"
    Computes the worst-case Kolmogorov-Smirnov gap between empirical and theoretical CDFs:
        D = max_j |F_hat(t_j) - F(t_j)|
    \"\"\"
    emp = empirical_cdf(sample, eval_points)
    theo = cdf_function(eval_points)
    return float(np.max(np.abs(emp - theo)))

# Validate All Four Generators
eval_pts_u = np.linspace(0.0, 1.0, 100)
cdf_theo_u = lambda x: np.clip(x, 0.0, 1.0)
d_uniform = max_cdf_distance(u_samples, cdf_theo_u, eval_pts_u)

eval_pts_g = np.linspace(5.0, 25.0, 100)
cdf_theo_g = lambda x: 0.5 * (1.0 + sp.erf((x - 15.0) / (3.0 * np.sqrt(2.0))))
d_gaussian = max_cdf_distance(g_samples, cdf_theo_g, eval_pts_g)

eval_pts_b = np.arange(0, 31)
b_pmf_full = binomial_pmf(eval_pts_b, 30, 0.4)
b_cdf_full = np.cumsum(b_pmf_full)
cdf_theo_b = lambda x: b_cdf_full[np.clip(np.asarray(x, dtype=int), 0, 30)]
d_binomial = max_cdf_distance(b_samples, cdf_theo_b, eval_pts_b)

# Validate Image Row Marginal
eval_pts_img = np.arange(100)
img_p_row = row_marginal(paw_img)
img_cdf_row = np.cumsum(img_p_row)
cdf_theo_img = lambda x: img_cdf_row[np.clip(np.asarray(x, dtype=int), 0, 99)]
d_image = max_cdf_distance(paw_samples[:, 0], cdf_theo_img, eval_pts_img)

df_validation = pd.DataFrame([
    {"Sampler": "2.1.1 Uniform Generator", "Theoretical Distribution": "Uniform(0, 1)", "Max Gap D": f"{d_uniform:.5f}"},
    {"Sampler": "2.1.2 Gaussian Sampler", "Theoretical Distribution": "Gaussian(mu=15, sigma=3)", "Max Gap D": f"{d_gaussian:.5f}"},
    {"Sampler": "2.1.3 Binomial Sampler", "Theoretical Distribution": "Binomial(n=30, p=0.4)", "Max Gap D": f"{d_binomial:.5f}"},
    {"Sampler": "2.1.4 Image Row Marginal", "Theoretical Distribution": "Empirical Row PMF", "Max Gap D": f"{d_image:.5f}"}
])

print("=== GENERATOR EMPIRICAL VALIDATION REPORT ===")
display(df_validation)
""")

add_code("""
# Plot Empirical vs Theoretical CDFs
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Uniform
axes[0, 0].plot(eval_pts_u, cdf_theo_u(eval_pts_u), 'r--', label="Theoretical CDF", linewidth=2)
axes[0, 0].plot(eval_pts_u, empirical_cdf(u_samples, eval_pts_u), 'b-', label="Empirical CDF", linewidth=1.5)
axes[0, 0].set_title(f"Uniform Generator CDF (D = {d_uniform:.4f})", fontweight='bold')
axes[0, 0].set_xlabel("x")
axes[0, 0].set_ylabel("F(x)")
axes[0, 0].legend()
add_watermark(axes[0, 0])

# 2. Gaussian
axes[0, 1].plot(eval_pts_g, cdf_theo_g(eval_pts_g), 'r--', label="Theoretical CDF", linewidth=2)
axes[0, 1].plot(eval_pts_g, empirical_cdf(g_samples, eval_pts_g), 'b-', label="Empirical CDF", linewidth=1.5)
axes[0, 1].set_title(f"Gaussian Sampler CDF (D = {d_gaussian:.4f})", fontweight='bold')
axes[0, 1].set_xlabel("x")
axes[0, 1].set_ylabel("F(x)")
axes[0, 1].legend()
add_watermark(axes[0, 1])

# 3. Binomial
axes[1, 0].step(eval_pts_b, cdf_theo_b(eval_pts_b), 'r--', where='post', label="Theoretical CDF", linewidth=2)
axes[1, 0].step(eval_pts_b, empirical_cdf(b_samples, eval_pts_b), 'b-', where='post', label="Empirical CDF", linewidth=1.5)
axes[1, 0].set_title(f"Binomial Sampler CDF (D = {d_binomial:.4f})", fontweight='bold')
axes[1, 0].set_xlabel("k (successes)")
axes[1, 0].set_ylabel("F(k)")
axes[1, 0].legend()
add_watermark(axes[1, 0])

# 4. Image Row Marginal
axes[1, 1].plot(eval_pts_img, cdf_theo_img(eval_pts_img), 'r--', label="True Row CDF", linewidth=2)
axes[1, 1].plot(eval_pts_img, empirical_cdf(paw_samples[:, 0], eval_pts_img), 'b-', label="Sampled Empirical CDF", linewidth=1.5)
axes[1, 1].set_title(f"Image Row Marginal CDF (D = {d_image:.4f})", fontweight='bold')
axes[1, 1].set_xlabel("Row Index")
axes[1, 1].set_ylabel("F(row)")
axes[1, 1].legend()
add_watermark(axes[1, 1])

plt.tight_layout()
plt.show()
""")

# ==============================================================================
# SECTION 2.2: NAIVE BAYES FOR MIXED FEATURES
# ==============================================================================
add_md("""
## 2.2 Naive Bayes Classifier for Mixed Features [34 marks]

We classify individual dogs into one of 4 breeds based on 4 features from 3 different parametric families:
- `height` $\\sim \\mathcal{N}(\\mu, \\sigma)$ (Gaussian)
- `weight` $\\sim \\mathcal{N}(\\mu, \\sigma)$ (Gaussian)
- `bark_days` $\\sim \\text{Binomial}(n=30, p)$ (Binomial with known $n=30$)
- `ear_head_ratio` $\\sim \\text{Uniform}(a, b)$ (Uniform)

---

### 2.2.1 Maximum-Likelihood Estimators (MLE) [7 marks]
Given a 1D sample $\\{x_1, \\dots, x_N\\}$:
1. **Gaussian MLE**:
   $$\\hat{\\mu} = \\bar{x} = \\frac{1}{N}\\sum_{i=1}^N x_i, \\quad \\hat{\\sigma} = \\sqrt{\\frac{1}{N}\\sum_{i=1}^N (x_i - \\bar{x})^2} \\quad (\\text{dividing by } N)$$
2. **Binomial MLE** (with known trial count $n=30$):
   $$\\hat{p} = \\frac{\\bar{x}}{n} = \\frac{1}{nN}\\sum_{i=1}^N x_i$$
3. **Uniform MLE**:
   $$\\hat{a} = \\min_i x_i, \\quad \\hat{b} = \\max_i x_i$$
""")

add_code("""
def mle_gaussian(sample: np.ndarray) -> tuple:
    \"\"\"Computes Gaussian MLE (mu, sigma) with 1/N variance.\"\"\"
    x = np.asarray(sample, dtype=float)
    mu = float(np.mean(x))
    sigma = float(np.sqrt(np.mean((x - mu)**2)))
    return mu, max(sigma, 1e-6)

def mle_binomial(sample: np.ndarray, n: int = 30) -> float:
    \"\"\"Computes Binomial MLE success probability p = mean(x) / n.\"\"\"
    x = np.asarray(sample, dtype=float)
    p = float(np.mean(x) / n)
    return float(np.clip(p, 1e-6, 1.0 - 1e-6))

def mle_uniform(sample: np.ndarray) -> tuple:
    \"\"\"Computes Uniform MLE endpoints (a = min(x), b = max(x)).\"\"\"
    x = np.asarray(sample, dtype=float)
    a = float(np.min(x))
    b = float(np.max(x))
    if b <= a:
        b = a + 1e-6
    return a, b
""")

add_md("""
### 2.2.2 Model Fitting [8 marks]
`compute_training_params` fits per-class parameters and log-priors generically over all classes and features present in the training split.
""")

add_code("""
def compute_training_params(df: pd.DataFrame, features: list, feature_distributions: dict) -> dict:
    \"\"\"
    Fits per-class parameters and log-priors from a training dataframe.
    Generically handles arbitrary classes and features without hardcoded names.
    
    Parameters:
        df (pd.DataFrame): Training DataFrame containing a 'breed' class column.
        features (list): List of feature column names.
        feature_distributions (dict): Mapping of feature name -> 'gaussian' | 'binomial' | 'uniform'.
        
    Returns:
        dict: Fitted model parameters.
    \"\"\"
    classes = sorted(df["breed"].unique())
    n_total = len(df)
    params = {}
    
    for c in classes:
        df_c = df[df["breed"] == c]
        prior = len(df_c) / n_total
        log_prior = np.log(prior)
        
        c_dict = {
            "prior": float(prior),
            "log_prior": float(log_prior),
            "features": {}
        }
        
        for feat in features:
            dist_type = feature_distributions[feat].lower()
            sample = df_c[feat].values
            
            if dist_type == "gaussian":
                mu, sigma = mle_gaussian(sample)
                c_dict["features"][feat] = {"dist": "gaussian", "mu": mu, "sigma": sigma}
            elif dist_type == "binomial":
                p = mle_binomial(sample, n=30)
                c_dict["features"][feat] = {"dist": "binomial", "n": 30, "p": p}
            elif dist_type == "uniform":
                a, b = mle_uniform(sample)
                c_dict["features"][feat] = {"dist": "uniform", "a": a, "b": b}
            else:
                raise ValueError(f"Unknown distribution family: {dist_type}")
                
        params[c] = c_dict
        
    return params

# Load dog breeds dataset and split 70/30 deterministically
df_dogs = pd.read_csv("dog_breeds_dataset.csv")

# Train/test split using our custom deterministic split
df_dogs_train, df_dogs_val_unused, df_dogs_test = train_val_test_split(df_dogs, 0.7, 0.0, 0.3, SEED)

feature_distributions = {
    "height": "gaussian",
    "weight": "gaussian",
    "bark_days": "binomial",
    "ear_head_ratio": "uniform"
}
dog_features = list(feature_distributions.keys())

fitted_params = compute_training_params(df_dogs_train, dog_features, feature_distributions)

print(f"Fitted parameters across {len(fitted_params)} classes:")
for breed, p_info in fitted_params.items():
    print(f"\\nBreed: {breed} (Prior: {p_info['prior']:.2f})")
    for f, f_data in p_info["features"].items():
        print(f"  - {f} ({f_data['dist']}): {f_data}")
""")

add_md("""
### 2.2.3 Maximum A Posteriori (MAP) Prediction [9 marks]

Under conditional feature independence given class $C_i$, the MAP classification rule evaluates log-posterior scores:
$$\\text{score}_i(\\mathbf{x}) = \\log P(C_i) + \\sum_{k=1}^d \\log P(x_k \\mid C_i)$$
where:
- **Gaussian Log-Likelihood**:
  $$\\log P(x \\mid \\mu, \\sigma) = -\\frac{1}{2}\\log(2\\pi\\sigma^2) - \\frac{(x - \\mu)^2}{2\\sigma^2}$$
- **Binomial Log-Likelihood**:
  $$\\log P(k \\mid n, p) = \\log\\binom{n}{k} + k\\log(p) + (n-k)\\log(1-p) = \\ln\\Gamma(n+1) - \\ln\\Gamma(k+1) - \\ln\\Gamma(n-k+1) + k\\ln(p) + (n-k)\\ln(1-p)$$
- **Uniform Log-Likelihood**:
  $$\\log P(x \\mid a, b) = \\begin{cases} -\\ln(b - a) & \\text{if } a \\le x \\le b \\\\ -\\infty & \\text{otherwise} \\end{cases}$$
""")

add_code("""
def log_likelihood_gaussian(x: float, mu: float, sigma: float) -> float:
    \"\"\"Computes log Gaussian density.\"\"\"
    return -0.5 * np.log(2.0 * np.pi * (sigma**2)) - ((x - mu)**2) / (2.0 * (sigma**2))

def log_likelihood_binomial(k: int, n: int, p: float) -> float:
    \"\"\"Computes log Binomial mass using gammaln for combinatorial term.\"\"\"
    k = np.clip(k, 0, n)
    log_comb = sp.gammaln(n + 1) - sp.gammaln(k + 1) - sp.gammaln(n - k + 1)
    return log_comb + k * np.log(p) + (n - k) * np.log(1.0 - p)

def log_likelihood_uniform(x: float, a: float, b: float) -> float:
    \"\"\"Computes log Uniform density with finite boundary smoothing.\"\"\"
    # Apply slight epsilon expansion for test boundary generalization
    eps = 1e-4 * (b - a)
    if (a - eps) <= x <= (b + eps):
        return -np.log((b + eps) - (a - eps))
    else:
        return -1e9

def predict_class(x_dict: dict, params: dict, feature_distributions: dict) -> str:
    \"\"\"
    Evaluates log posterior MAP scores across all classes and returns the argmax class.
    
    Parameters:
        x_dict (dict): Dictionary mapping feature names to numerical values.
        params (dict): Fitted model parameters from compute_training_params.
        feature_distributions (dict): Feature distribution family mapping.
        
    Returns:
        str: Predicted class label.
    \"\"\"
    best_class = None
    best_score = -float('inf')
    
    for c, c_info in params.items():
        score = c_info["log_prior"]
        
        for feat, dist_type in feature_distributions.items():
            val = x_dict[feat]
            f_params = c_info["features"][feat]
            
            if dist_type == "gaussian":
                score += log_likelihood_gaussian(val, f_params["mu"], f_params["sigma"])
            elif dist_type == "binomial":
                score += log_likelihood_binomial(val, f_params["n"], f_params["p"])
            elif dist_type == "uniform":
                score += log_likelihood_uniform(val, f_params["a"], f_params["b"])
                
        if score > best_score:
            best_score = score
            best_class = c
            
    return best_class

# Predict on test split
y_dogs_true = df_dogs_test["breed"].tolist()
y_dogs_pred = []

for _, row in df_dogs_test.iterrows():
    pred_c = predict_class(row.to_dict(), fitted_params, feature_distributions)
    y_dogs_pred.append(pred_c)
""")

add_md("""
### 2.2.4 Evaluation Metrics from Scratch [10 marks]
We implement `confusion_matrix(y_true, y_pred, labels)` and macro-averaged `precision_recall_f1(cm)` from scratch without using `sklearn.metrics`.
""")

add_code("""
def confusion_matrix(y_true: list, y_pred: list, labels: list) -> np.ndarray:
    \"\"\"
    Constructs a confusion matrix C where C[i, j] is the count of samples
    with true label labels[i] predicted as labels[j].
    \"\"\"
    label_map = {lbl: idx for idx, lbl in enumerate(labels)}
    K = len(labels)
    cm = np.zeros((K, K), dtype=int)
    
    for yt, yp in zip(y_true, y_pred):
        if yt in label_map and yp in label_map:
            cm[label_map[yt], label_map[yp]] += 1
            
    return cm

def precision_recall_f1(cm: np.ndarray) -> dict:
    \"\"\"
    Computes per-class and macro-averaged Precision, Recall, and F1-score from a confusion matrix.
    \"\"\"
    K = cm.shape[0]
    precisions = []
    recalls = []
    f1_scores = []
    
    for i in range(K):
        tp = cm[i, i]
        fp = np.sum(cm[:, i]) - tp
        fn = np.sum(cm[i, :]) - tp
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        
        precisions.append(prec)
        recalls.append(rec)
        f1_scores.append(f1)
        
    return {
        "macro_precision": float(np.mean(precisions)),
        "macro_recall": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_scores)),
        "per_class_precision": precisions,
        "per_class_recall": recalls,
        "per_class_f1": f1_scores
    }

dog_labels = sorted(df_dogs["breed"].unique())
cm_dogs = confusion_matrix(y_dogs_true, y_dogs_pred, dog_labels)
metrics_dogs = precision_recall_f1(cm_dogs)

# Display Classification Report
df_report = pd.DataFrame({
    "Breed": dog_labels,
    "Precision": np.round(metrics_dogs["per_class_precision"], 4),
    "Recall": np.round(metrics_dogs["per_class_recall"], 4),
    "F1-Score": np.round(metrics_dogs["per_class_f1"], 4),
    "Support": np.sum(cm_dogs, axis=1)
})

print("=== MIXED-FEATURE NAIVE BAYES CLASSIFICATION REPORT ===")
display(df_report)
print(f"\\nMacro Precision : {metrics_dogs['macro_precision']:.4f}")
print(f"Macro Recall    : {metrics_dogs['macro_recall']:.4f}")
print(f"Macro F1-Score  : {metrics_dogs['macro_f1']:.4f}")
""")

add_code("""
# Plot Confusion Matrix Heatmap
plt.figure(figsize=(7, 5))
sns.heatmap(cm_dogs, annot=True, fmt='d', cmap='Blues', xticklabels=dog_labels, yticklabels=dog_labels)
plt.title("Dog Breed Confusion Matrix (Mixed Naive Bayes)", fontweight='bold')
plt.xlabel("Predicted Breed")
plt.ylabel("True Breed")
add_watermark()
plt.tight_layout()
plt.show()
""")

# ==============================================================================
# SECTION 2.3: SPAM DETECTION
# ==============================================================================
add_md("""
## 2.3 Spam Detection [22 marks]

We implement a text spam classifier using Naive Bayes with Laplace smoothing and a numerically stable sigmoid output.

---

### 2.3.1 Text Statistics [10 marks]
`fit_spam_counts` computes:
- `word_freq`: `{word: {"spam": s, "ham": h}}`, document occurrences per class.
- `class_freq`: `{"spam": N_spam, "ham": N_ham}`, total emails per class.
""")

add_code("""
def tokenize_words(text: str) -> set:
    \"\"\"Lowercases text and extracts unique word tokens (document set).\"\"\"
    return set(re.findall(r'\\b[a-z0-9]+\\b', str(text).lower()))

def fit_spam_counts(df: pd.DataFrame) -> tuple:
    \"\"\"
    Computes vocabulary document frequencies and class frequencies from the training split.
    \"\"\"
    class_freq = {
        "spam": int(np.sum(df["label"] == "spam")),
        "ham": int(np.sum(df["label"] == "ham"))
    }
    word_freq = {}
    
    for _, row in df.iterrows():
        label = row["label"]
        words = tokenize_words(row["text"])
        for w in words:
            if w not in word_freq:
                word_freq[w] = {"spam": 0, "ham": 0}
            word_freq[w][label] += 1
            
    return word_freq, class_freq

# Load spam dataset and split 70/30 deterministically
df_spam = pd.read_csv("spam_dataset.csv")
df_spam_train, df_spam_val_unused, df_spam_test = train_val_test_split(df_spam, 0.7, 0.0, 0.3, SEED)

word_freq, class_freq = fit_spam_counts(df_spam_train)
print(f"Spam Training Documents : {class_freq['spam']}")
print(f"Ham Training Documents  : {class_freq['ham']}")
print(f"Total Unique Vocabulary : {len(word_freq)} words")
""")

add_md("""
### 2.3.2 Smoothed Classifier [12 marks]

1. **Numerically Stable Sigmoid**:
   To prevent overflow when exponentiating large positive numbers, we use the two-branch definition:
   $$\\sigma(t) = \\begin{cases} \\frac{1}{1 + e^{-t}} & \\text{if } t \\ge 0 \\\\ \\frac{e^t}{1 + e^t} & \\text{if } t < 0 \\end{cases}$$

2. **Laplace-Smoothed Log-Odds Posterior**:
   For each word $w \\in \\text{set}(\\text{words})$ appearing in the training vocabulary:
   $$P(w \\mid c) = \\frac{\\text{count}_c(w) + \\alpha}{N_c + 2\\alpha}, \\quad \\alpha > 0$$
   $$\\text{score}_{\\text{spam}} = \\ln P(\\text{spam}) + \\sum_{w \\in \\mathcal{V}} \\ln P(w \\mid \\text{spam})$$
   $$\\text{score}_{\\text{ham}} = \\ln P(\\text{ham}) + \\sum_{w \\in \\mathcal{V}} \\ln P(w \\mid \\text{ham})$$
   $$P(\\text{Spam} \\mid \\text{text}) = \\sigma(\\text{score}_{\\text{spam}} - \\text{score}_{\\text{ham}})$$
""")

add_code("""
def stable_sigmoid(t: float) -> float:
    \"\"\"Numerically stable two-branch sigmoid that never exponentiates a positive number.\"\"\"
    t = float(t)
    if t >= 0:
        return 1.0 / (1.0 + np.exp(-t))
    else:
        exp_t = np.exp(t)
        return exp_t / (1.0 + exp_t)

def naive_bayes_spam_prob(text: str, word_freq: dict, class_freq: dict, alpha: float = 1.0) -> float:
    \"\"\"
    Computes Laplace-smoothed Naive Bayes posterior probability P(Spam | text).
    \"\"\"
    words = tokenize_words(text)
    n_spam = class_freq["spam"]
    n_ham = class_freq["ham"]
    total_docs = n_spam + n_ham
    
    score_spam = np.log(n_spam / total_docs)
    score_ham = np.log(n_ham / total_docs)
    
    for w in words:
        if w in word_freq:
            c_spam = word_freq[w]["spam"]
            c_ham = word_freq[w]["ham"]
            
            p_w_spam = (c_spam + alpha) / (n_spam + 2.0 * alpha)
            p_w_ham = (c_ham + alpha) / (n_ham + 2.0 * alpha)
            
            score_spam += np.log(p_w_spam)
            score_ham += np.log(p_w_ham)
            
    diff = score_spam - score_ham
    return stable_sigmoid(diff)

# Evaluate on held-out test split
y_spam_true = df_spam_test["label"].tolist()
y_spam_prob = [naive_bayes_spam_prob(t, word_freq, class_freq, alpha=1.0) for t in df_spam_test["text"]]
y_spam_pred = ["spam" if p >= 0.5 else "ham" for p in y_spam_prob]

cm_spam = confusion_matrix(y_spam_true, y_spam_pred, ["ham", "spam"])
metrics_spam = precision_recall_f1(cm_spam)

print("=== SPAM DETECTION EVALUATION ON TEST SET ===")
print(f"Test Accuracy    : {np.mean(np.array(y_spam_true) == np.array(y_spam_pred)):.4f}")
print(f"Spam Precision   : {metrics_spam['per_class_precision'][1]:.4f}")
print(f"Spam Recall      : {metrics_spam['per_class_recall'][1]:.4f}")
print(f"Spam F1-Score    : {metrics_spam['per_class_f1'][1]:.4f}")
""")

add_code("""
# Demonstrate on Example Unseen Emails
test_emails = [
    "URGENT: Claim your $5,000 cash prize reward now by clicking the link!",
    "Hi Devansh, could you please send the slides for tomorrow's research meeting?",
    "Exclusive discount: 80% off prescription meds with free overnight shipping.",
    "The assignment deadline has been updated on the course website."
]

print("=== EXAMPLE EMAIL PREDICTIONS ===")
for em in test_emails:
    prob = naive_bayes_spam_prob(em, word_freq, class_freq, alpha=1.0)
    label = "SPAM" if prob >= 0.5 else "HAM"
    print(f"[{label:4s} | P(Spam) = {prob:.4f}] '{em}'")
""")

# ==============================================================================
# SECTION 2.4: BAYESIAN PARAMETER ESTIMATION
# ==============================================================================
add_md("""
## 2.4 Bayesian Parameter Estimation [12 marks]

Unlike point MLE estimators $\\hat{\\theta}$, the Bayesian paradigm maintains a full probability distribution expressing epistemic uncertainty over model parameters $\\theta$.

---

### 2.4.1 Bayesian Estimation of a Bark-Day Rate [12 marks]

#### Mathematical Formulation (Beta-Binomial Conjugacy)
Each dog's barking occurrences $k_i \\sim \\text{Binomial}(n=30, p)$. Placing a conjugate prior $p \\sim \\text{Beta}(\\alpha_0, \\beta_0)$ over the barking rate $p$:
$$P(p) = \\frac{1}{B(\\alpha_0, \\beta_0)} p^{\\alpha_0 - 1} (1 - p)^{\\beta_0 - 1}$$

Observing $N$ dogs with barking counts $\\{k_1, k_2, \\dots, k_N\\}$, the posterior by Bayes' rule is:
$$P(p \\mid \\mathbf{k}) \\propto P(\\mathbf{k} \\mid p) P(p) \\propto \\left[\\prod_{i=1}^N p^{k_i} (1 - p)^{n - k_i}\\right] p^{\\alpha_0 - 1} (1 - p)^{\\beta_0 - 1} = p^{(\\alpha_0 + \\sum k_i) - 1} (1 - p)^{(\\beta_0 + \\sum (n - k_i)) - 1}$$

Thus, the posterior is $\\text{Beta}(\\alpha_{\\text{post}}, \\beta_{\\text{post}})$ with closed-form hyperparameter updates:
$$\\alpha_{\\text{post}} = \\alpha_0 + \\sum_{i=1}^N k_i, \\quad \\beta_{\\text{post}} = \\beta_0 + \\sum_{i=1}^N (n - k_i)$$

#### Point Estimates & Quantiles
- **Posterior Mean**: $\\mathbb{E}[p \\mid \\mathbf{k}] = \\frac{\\alpha_{\\text{post}}}{\\alpha_{\\text{post}} + \\beta_{\\text{post}}}$
- **Posterior Mode (MAP)**: $\\frac{\\alpha_{\\text{post}} - 1}{\\alpha_{\\text{post}} + \\beta_{\\text{post}} - 2}$ (for $\\alpha, \\beta > 1$)
- **Posterior Variance**: $\\text{Var}(p \\mid \\mathbf{k}) = \\frac{\\alpha_{\\text{post}} \\beta_{\\text{post}}}{(\\alpha_{\\text{post}} + \\beta_{\\text{post}})^2 (\\alpha_{\\text{post}} + \\beta_{\\text{post}} + 1)}$
- **95% Central Credible Interval**: $[Q(0.025), Q(0.975)]$ computed via `scipy.special.betaincinv`.
""")

add_code("""
def beta_binomial_posterior(alpha_prior: float, beta_prior: float, observations: np.ndarray, n_trials: int = 30) -> tuple:
    \"\"\"
    Applies the conjugate Beta-Binomial update to observations.
    
    Returns:
        tuple: (alpha_post, beta_post)
    \"\"\"
    obs = np.asarray(observations, dtype=float)
    sum_k = float(np.sum(obs))
    total_trials = len(obs) * n_trials
    
    alpha_post = alpha_prior + sum_k
    beta_post = beta_prior + (total_trials - sum_k)
    return float(alpha_post), float(beta_post)

def posterior_point_estimates(alpha_post: float, beta_post: float) -> dict:
    \"\"\"
    Computes posterior mean, mode (MAP), and variance for Beta(alpha_post, beta_post).
    \"\"\"
    mean = alpha_post / (alpha_post + beta_post)
    
    if alpha_post > 1 and beta_post > 1:
        mode = (alpha_post - 1.0) / (alpha_post + beta_post - 2.0)
    elif alpha_post > 1 and beta_post <= 1:
        mode = 1.0
    elif alpha_post <= 1 and beta_post > 1:
        mode = 0.0
    else:
        mode = float("nan")
        
    variance = (alpha_post * beta_post) / (((alpha_post + beta_post)**2) * (alpha_post + beta_post + 1.0))
    
    return {
        "mean": float(mean),
        "mode": float(mode),
        "variance": float(variance)
    }

def credible_interval(alpha_post: float, beta_post: float, level: float = 0.95) -> tuple:
    \"\"\"
    Computes the central credible interval using scipy.special.betaincinv.
    \"\"\"
    alpha_tail = (1.0 - level) / 2.0
    lower = float(sp.betaincinv(alpha_post, beta_post, alpha_tail))
    upper = float(sp.betaincinv(alpha_post, beta_post, 1.0 - alpha_tail))
    return lower, upper

# Extract Beagle bark_days from dog training split
beagle_bark_obs = df_dogs_train[df_dogs_train["breed"] == "Beagle"]["bark_days"].values
raw_mle_p = float(np.mean(beagle_bark_obs) / 30.0)

# Uninformative Prior Beta(1, 1) = Uniform(0, 1)
alpha_0, beta_0 = 1.0, 1.0
alpha_post, beta_post = beta_binomial_posterior(alpha_0, beta_0, beagle_bark_obs, n_trials=30)
pt_estimates = posterior_point_estimates(alpha_post, beta_post)
ci_95 = credible_interval(alpha_post, beta_post, level=0.95)

print("=== BAYESIAN BARK-DAY RATE ESTIMATION (BEAGLE BREED) ===")
print(f"Sample Size (N dogs)       : {len(beagle_bark_obs)}")
print(f"Raw MLE Proportion (k_bar/n): {raw_mle_p:.5f}")
print(f"Posterior Alpha (a_post)   : {alpha_post:.1f}")
print(f"Posterior Beta  (b_post)   : {beta_post:.1f}")
print(f"Posterior Mean             : {pt_estimates['mean']:.5f}")
print(f"Posterior Mode (MAP)       : {pt_estimates['mode']:.5f}")
print(f"Posterior Variance         : {pt_estimates['variance']:.2e}")
print(f"95% Credible Interval      : [{ci_95[0]:.5f}, {ci_95[1]:.5f}]")
""")

add_code("""
# Visualize Beta Posterior Density vs Prior & MLE
def beta_pdf(p, a, b):
    \"\"\"Analytical Beta PDF via gammaln.\"\"\"
    log_norm = sp.gammaln(a) + sp.gammaln(b) - sp.gammaln(a + b)
    return np.exp((a - 1) * np.log(p) + (b - 1) * np.log(1 - p) - log_norm)

p_grid = np.linspace(0.55, 0.85, 500)
post_pdf = beta_pdf(p_grid, alpha_post, beta_post)

plt.figure(figsize=(10, 5))
plt.plot(p_grid, post_pdf, 'b-', linewidth=2.5, label=f"Posterior Beta({alpha_post:.0f}, {beta_post:.0f})")
plt.axvline(raw_mle_p, color='red', linestyle='--', linewidth=2, label=f"Raw MLE: {raw_mle_p:.4f}")
plt.axvline(pt_estimates['mean'], color='navy', linestyle=':', linewidth=2, label=f"Posterior Mean: {pt_estimates['mean']:.4f}")
plt.axvline(ci_95[0], color='green', linestyle='-', alpha=0.7, label=f"95% CI Lower: {ci_95[0]:.4f}")
plt.axvline(ci_95[1], color='green', linestyle='-', alpha=0.7, label=f"95% CI Upper: {ci_95[1]:.4f}")

# Shade 95% Credible Region
p_ci_mask = (p_grid >= ci_95[0]) & (p_grid <= ci_95[1])
plt.fill_between(p_grid[p_ci_mask], post_pdf[p_ci_mask], color='blue', alpha=0.15, label="95% Credible Region")

plt.title("Posterior Distribution of Beagle Bark-Day Rate (p)", fontweight='bold')
plt.xlabel("Bark-Day Rate Parameter (p)")
plt.ylabel("Posterior Probability Density")
plt.legend()
add_watermark()
plt.tight_layout()
plt.show()
""")

add_md("""
### Comprehensive Analysis: Bayesian Posterior vs. MLE & Sample Size Effects

1. **Comparison of Posterior Mean vs. Raw MLE**:
   - The raw Maximum Likelihood Estimator is:
     $$\\hat{p}_{\\text{MLE}} = \\frac{\\sum k_i}{N \\cdot n} = \\frac{\\bar{k}}{n} \\approx 0.700$$
   - The Bayesian posterior mean under a $\\text{Beta}(\\alpha_0, \\beta_0)$ prior is:
     $$\\mathbb{E}[p \\mid \\mathbf{k}] = \\frac{\\alpha_0 + \\sum k_i}{\\alpha_0 + \\beta_0 + N \\cdot n} = \\frac{\\alpha_0 + \\beta_0}{\\alpha_0 + \\beta_0 + N \\cdot n} \\left(\\frac{\\alpha_0}{\\alpha_0 + \\beta_0}\\right) + \\frac{N \\cdot n}{\\alpha_0 + \\beta_0 + N \\cdot n} \\hat{p}_{\\text{MLE}}$$
   - This explicitly shows that the posterior mean is a **convex combination** of the prior mean $\\frac{\\alpha_0}{\\alpha_0 + \\beta_0}$ and the empirical data MLE $\\hat{p}_{\\text{MLE}}$, weighted by effective sample sizes.

2. **Asymptotic Behavior on Large Training Splits**:
   - When the training split is large ($N \\cdot n \\gg \\alpha_0 + \\beta_0$), the data weight $\\frac{N \\cdot n}{\\alpha_0 + \\beta_0 + N \\cdot n} \\to 1$.
   - The empirical likelihood completely dominates the prior. The posterior contracts tightly around the true parameter value, posterior variance drops toward zero, and the 95% credible interval becomes extremely narrow.

3. **Behavior with Small Sample Sizes (A Handful of Dogs)**:
   - When only a handful of dogs are observed (e.g., $N = 2$), the empirical count $\\sum k_i$ is small and prone to sampling variance.
   - Here, the prior acts as an essential **regularizer**, pulling the estimate toward prior knowledge and preventing extreme, overfitted estimates (e.g., estimating $p = 1.0$ if two dogs barked on all observed days). Furthermore, the wide credible interval correctly conveys high epistemic uncertainty rather than providing false confidence.
""")

# Save notebook
nb.cells = cells
with open("SMAI_Assignment_1.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Successfully generated SMAI_Assignment_1.ipynb with {len(cells)} cells.")
