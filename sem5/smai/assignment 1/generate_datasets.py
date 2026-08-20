"""
Data generation script for SMAI Monsoon 2026 - Assignment 1.
Generates:
1. essay_dataset.csv (Section 1: Automated Essay Scoring)
2. dog_breeds_dataset.csv (Section 2.2 & 2.4: Naive Bayes and Bayesian Estimation)
3. spam_dataset.csv (Section 2.3: Spam Email Detection)
4. paw_print.png (Section 2.1.4: 2D Empirical Density Sampling)

Seed calculation strictly follows institute instructions:
username = "devansh.bansal"
seed = int(hashlib.sha256(username.encode()).hexdigest(), 16) % (2**32)
"""

import os
import hashlib
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

USERNAME = "devansh.bansal"
SEED = int(hashlib.sha256(USERNAME.encode()).hexdigest(), 16) % (2**32)
print(f"Generating datasets with Username: {USERNAME}, Seed: {SEED}")

rng = np.random.default_rng(SEED)

# -------------------------------------------------------------
# 1. Generate 100x100 grayscale paw_print.png
# -------------------------------------------------------------
def create_paw_print_image(filepath="paw_print.png"):
    img = Image.new('L', (100, 100), color=0)
    draw = ImageDraw.Draw(img)

    # Main pad (metacarpal / metatarsal pad)
    draw.ellipse([30, 45, 70, 80], fill=255)
    draw.ellipse([25, 55, 50, 85], fill=255)
    draw.ellipse([50, 55, 75, 85], fill=255)
    draw.ellipse([35, 40, 65, 65], fill=255)

    # 4 Toe pads in an arc
    draw.ellipse([18, 30, 32, 48], fill=255)
    draw.ellipse([34, 15, 48, 35], fill=255)
    draw.ellipse([52, 15, 66, 35], fill=255)
    draw.ellipse([68, 30, 82, 48], fill=255)

    img.save(filepath)
    print(f"Created {filepath} (100x100 grayscale).")

create_paw_print_image("paw_print.png")

# -------------------------------------------------------------
# 2. Generate Essay Dataset for Section 1 (AES)
# -------------------------------------------------------------
# Essays with realistic progression across scores 1 to 6
def generate_essay_corpus(num_samples=360):
    topics = [
        ("the impact of renewable energy on global climate change",
         ["solar power", "wind turbines", "grid resilience", "carbon emissions", "environmental degradation", "policy incentives"]),
        ("the role of artificial intelligence in modern healthcare",
         ["diagnostic algorithms", "medical imaging", "patient care", "clinical ethics", "algorithmic precision", "healthcare infrastructure"]),
        ("the importance of space exploration for human civilization",
         ["interplanetary missions", "technological innovation", "scientific discoveries", "resource utilization", "astrobiology", "global cooperation"]),
        ("the effects of social media on teenage mental health and social development",
         ["digital connectivity", "psychological well-being", "screen time", "peer validation", "cyberbullying", "algorithmic curation"]),
        ("the necessity of preserving global biodiversity in marine ecosystems",
         ["coral reefs", "ocean acidification", "marine conservation", "ecosystem equilibrium", "overfishing", "environmental stewardship"]),
        ("the future of autonomous transportation and urban mobility",
         ["autonomous vehicles", "urban infrastructure", "traffic congestion", "safety regulations", "smart cities", "electric mobility"])
    ]

    essay_rows = []
    
    # Vocabulary banks by sophistication
    vocab_simple = ["good", "bad", "big", "small", "thing", "nice", "very", "see", "make", "think", "people", "hard", "easy", "use", "work", "world", "day", "way", "life"]
    vocab_intermediate = ["effective", "substantial", "significant", "development", "perspective", "influence", "community", "essential", "advantage", "challenge", "potential", "progress", "strategy", "technology"]
    vocab_advanced = ["unprecedented", "paradigm", "comprehensive", "infrastructure", "mitigation", "consequential", "equilibrium", "manifestation", "predominantly", "interconnected", "transformation", "sustainable", "deleterious", "exponential", "imperative"]

    for idx in range(num_samples):
        score = (idx % 6) + 1  # Balances scores 1 through 6
        topic_title, subtopics = topics[idx % len(topics)]
        
        # Essay characteristics scale with score:
        # Score 1: Very short (1-2 sentences), repetitive, simple words, frequent spelling/grammar issues
        # Score 2: Short (3-5 sentences), simple structure, limited vocabulary
        # Score 3: Moderate (6-10 sentences), basic cohesive paragraphs, intermediate vocabulary
        # Score 4: Solid (12-18 sentences), structured paragraphs, clear transitions, mixed sentence length
        # Score 5: Advanced (20-28 sentences), rich vocabulary, diverse syntax, strong argumentation
        # Score 6: Comprehensive (30-40 sentences), scholarly diction, sophisticated compound-complex sentences
        
        paragraphs = []
        if score == 1:
            n_sentences = rng.integers(2, 4)
            paras = [" ".join([
                f"I think {topic_title} is very {rng.choice(vocab_simple)}.",
                f"Many people say it is {rng.choice(vocab_simple)} and {rng.choice(vocab_simple)}.",
                f"We must do something {rng.choice(vocab_simple)} about {rng.choice(subtopics)}."
            ][:n_sentences])]
        elif score == 2:
            n_sentences = rng.integers(4, 7)
            s_list = [
                f"The topic of {topic_title} is important today.",
                f"First, {rng.choice(subtopics)} helps many people in the world.",
                f"However, there are {rng.choice(vocab_simple)} problems that make it hard.",
                f"Also, {rng.choice(subtopics)} can be {rng.choice(vocab_intermediate)} if we work on it.",
                f"In conclusion, we need to care more about {topic_title} for a good future."
            ][:n_sentences]
            paras = [" ".join(s_list[:3]), " ".join(s_list[3:])]
        elif score == 3:
            p1 = f"In contemporary discussions, {topic_title} has emerged as an important issue. Understanding the nuances of {rng.choice(subtopics)} is essential for progress. Several factors influence how society approaches these challenges."
            p2 = f"On one hand, {rng.choice(subtopics)} provides {rng.choice(vocab_intermediate)} benefits to diverse communities. It fosters practical development and encourages innovative solutions. Nevertheless, implementing effective strategies requires substantial investment and dedicated effort."
            p3 = f"Furthermore, another aspect to consider is {rng.choice(subtopics)}. When organizations focus on this domain, positive outcomes are frequently observed. Therefore, continued attention to {topic_title} remains necessary."
            paras = [p1, p2, p3]
        elif score == 4:
            p1 = f"The profound significance of {topic_title} has sparked extensive academic and public debate. As global society navigates complex modern challenges, examining {rng.choice(subtopics)} and {rng.choice(subtopics)} becomes increasingly vital for fostering sustainable progress."
            p2 = f"To begin with, {rng.choice(subtopics)} plays a pivotal role in driving transformative change. Empirical observations demonstrate that proactive investments in this area yield substantial long-term dividends. For instance, when institutions implement structured frameworks, the resulting advancements benefit both individual stakeholders and broader societal ecosystems."
            p3 = f"Conversely, overlooking the complexities of {rng.choice(subtopics)} can lead to unintended consequences. Resource constraints and policy inertia often hinder effective execution. Overcoming these systemic obstacles necessitates cohesive collaboration between policymakers, researchers, and community leaders."
            p4 = f"In summary, addressing {topic_title} demands a balanced, multifaceted approach. By leveraging the opportunities presented by {rng.choice(subtopics)}, society can build resilient foundations for future generations."
            paras = [p1, p2, p3, p4]
        elif score == 5:
            p1 = f"In an increasingly interconnected global landscape, {topic_title} represents a critical frontier of intellectual inquiry and practical policy. The rapid evolution of {rng.choice(subtopics)} demands a rigorous, multidisciplinary evaluation of underlying mechanisms, strategic implications, and ethical imperatives."
            p2 = f"Foremost among these considerations is the transformative capacity of {rng.choice(subtopics)}. By establishing robust analytical paradigms, researchers and industry leaders can harness {rng.choice(vocab_advanced)} methodologies to optimize efficiency and sustainability. For example, recent developments underscore how targeted interventions in {rng.choice(subtopics)} generate substantial positive externalities across diverse socioeconomic sectors."
            p3 = f"Nevertheless, the systemic implementation of these solutions is not without considerable impediments. Structural disparities, regulatory ambiguities, and technological constraints frequently undermine operational scalability. Mitigating these deleterious factors requires strategic resource allocation, adaptive governance frameworks, and enduring institutional commitment."
            p4 = f"Additionally, the synthesis of {rng.choice(subtopics)} with established protocols offers an unprecedented opportunity to advance systemic resilience. Stakeholders who proactively integrate these advanced modalities are far better positioned to anticipate disruptive trends and capitalize on emerging synergies."
            p5 = f"Ultimately, navigating {topic_title} requires visionary leadership combined with meticulous empirical oversight. Cultivating sustainable equilibrium in this vital arena will undoubtedly shape the socioeconomic trajectories of modern civilization."
            paras = [p1, p2, p3, p4, p5]
        else: # score == 6
            p1 = f"The multifaceted discourse surrounding {topic_title} stands as a paramount testament to the intricate challenges and profound opportunities defining twenty-first-century civilization. As global paradigms undergo unprecedented metamorphosis, a thorough, multidimensional appraisal of {rng.choice(subtopics)}, {rng.choice(subtopics)}, and their systemic intersections becomes an undeniable societal imperative."
            p2 = f"Fundamentally, the theoretical underpinnings of {rng.choice(subtopics)} elucidate a powerful catalyst for systemic transformation. When examined through rigorous empirical lenses, the integration of advanced principles consistently demonstrates exponential enhancements in institutional capability and public welfare. Furthermore, proactive architectural designs in {rng.choice(subtopics)} foster a self-reinforcing equilibrium, mitigating volatility while accelerating comprehensive innovation across interconnected domains."
            p3 = f"Crucially, however, the realization of such ambitious trajectories is inextricably linked to overcoming entrenched structural headwinds. Disjointed regulatory mandates, asymmetrical resource distribution, and legacy infrastructures often present formidable barriers to universal adoption. Resolving these persistent challenges necessitates not merely incremental adjustments, but rather a holistic realignment of strategic priorities and rigorous governance protocols."
            p4 = f"Moreover, synthesizing {rng.choice(subtopics)} within a broader ethical and operational matrix generates synergistic outcomes that transcend conventional methodologies. By establishing verifiable benchmarks and cultivating cross-sectoral alliances, institutions can effectively insulate vital ecosystems against unforeseen disruptions while simultaneously advancing the frontier of equitable development."
            p5 = f"In conclusion, the trajectory of {topic_title} will inherently dictate the resilience and prosperity of future generations. Achieving enduring excellence demands an unwavering commitment to intellectual rigor, strategic foresight, and sustainable innovation, establishing an enduring paradigm of progress."
            paras = [p1, p2, p3, p4, p5]

        essay_text = "\n\n".join(paras)
        essay_rows.append({
            "essay_id": f"ESSAY_{idx+1:04d}",
            "essay": essay_text,
            "score": score
        })

    df_essays = pd.DataFrame(essay_rows)
    df_essays.to_csv("essay_dataset.csv", index=False)
    print(f"Generated essay_dataset.csv with {len(df_essays)} samples across scores 1-6.")

generate_essay_corpus()

# -------------------------------------------------------------
# 3. Generate Synthetic Dog Breeds Dataset for Section 2.2 & 2.4
# -------------------------------------------------------------
def generate_dog_breeds_dataset(samples_per_breed=125):
    # Four breeds: Golden Retriever, Beagle, German Shepherd, Chihuahua
    # Distributions specified in prompt:
    # height ~ Gaussian(mu, sigma)
    # weight ~ Gaussian(mu, sigma)
    # bark_days ~ Binomial(n=30, p)
    # ear_head_ratio ~ Uniform(a, b)
    
    breed_configs = {
        "Golden Retriever": {
            "height": (58.0, 3.5),       # Gaussian (mu, sigma)
            "weight": (30.0, 4.0),       # Gaussian (mu, sigma)
            "bark_days": 0.25,           # Binomial p (n=30)
            "ear_head_ratio": (0.35, 0.50) # Uniform [a, b]
        },
        "Beagle": {
            "height": (36.0, 2.5),
            "weight": (12.0, 2.0),
            "bark_days": 0.70,
            "ear_head_ratio": (0.50, 0.70)
        },
        "German Shepherd": {
            "height": (62.0, 4.0),
            "weight": (35.0, 4.5),
            "bark_days": 0.45,
            "ear_head_ratio": (0.30, 0.45)
        },
        "Chihuahua": {
            "height": (18.0, 2.0),
            "weight": (2.5, 0.8),
            "bark_days": 0.80,
            "ear_head_ratio": (0.40, 0.60)
        }
    }

    rows = []
    dog_id = 1
    for breed, cfg in breed_configs.items():
        h_mu, h_sigma = cfg["height"]
        w_mu, w_sigma = cfg["weight"]
        p_bark = cfg["bark_days"]
        e_a, e_b = cfg["ear_head_ratio"]

        heights = rng.normal(h_mu, h_sigma, samples_per_breed)
        weights = rng.normal(w_mu, w_sigma, samples_per_breed)
        bark_days = rng.binomial(30, p_bark, samples_per_breed)
        ear_ratios = rng.uniform(e_a, e_b, samples_per_breed)

        for i in range(samples_per_breed):
            rows.append({
                "dog_id": f"DOG_{dog_id:04d}",
                "breed": breed,
                "height": float(np.round(heights[i], 2)),
                "weight": float(np.round(weights[i], 2)),
                "bark_days": int(bark_days[i]),
                "ear_head_ratio": float(np.round(ear_ratios[i], 4))
            })
            dog_id += 1

    df_dogs = pd.DataFrame(rows)
    # Shuffle deterministically
    df_dogs = df_dogs.sample(frac=1.0, random_state=SEED % (2**32 - 1)).reset_index(drop=True)
    df_dogs.to_csv("dog_breeds_dataset.csv", index=False)
    print(f"Generated dog_breeds_dataset.csv with {len(df_dogs)} samples across 4 breeds.")

generate_dog_breeds_dataset()

# -------------------------------------------------------------
# 4. Generate Spam / Ham Email Dataset for Section 2.3
# -------------------------------------------------------------
def generate_spam_dataset(num_samples=400):
    spam_templates = [
        "Urgent! You have won a cash prize of $10,000. Claim your reward immediately by clicking the link.",
        "Congratulations winner! Your account has been selected for a free gift card. Call now to claim.",
        "Exclusive deal: get 90% discount on luxury watches and designer goods. Limited time offer only!",
        "Earn $5,000 weekly working from home with no experience needed. Sign up today for free access.",
        "Security alert: Your bank account access is suspended. Verify your credentials instantly to restore.",
        "Claim your complimentary crypto bonus today! Instant withdrawal available for registered members.",
        "You are pre-approved for a zero-interest personal loan. Apply online now with zero paperwork.",
        "Refill your pharmacy prescription online with huge discounts and fast discreet shipping guaranteed.",
        "Act fast! Final notice regarding your unclaimed lottery jackpot payout. Submit verification details.",
        "Free trial membership access unlocked! Enjoy premium benefits with no subscription fees."
    ]

    ham_templates = [
        "Hi team, please find attached the meeting minutes and project action items from our discussion today.",
        "Dear professor, I had a question regarding problem 3 on the statistical methods assignment.",
        "Could you please review the latest pull request on GitHub when you have a moment? Thanks!",
        "Reminder: The department research seminar is scheduled for tomorrow at 3:00 PM in the auditorium.",
        "Hey, are we still meeting in the library this evening to study for the upcoming mid-term exam?",
        "Please submit your course project proposal by Friday evening through the university portal.",
        "Attached is the updated dataset and Python script for the experiment analysis pipeline.",
        "Thank you for attending the workshop. The slides and recording are now available on the portal.",
        "Let us schedule a sync call on Monday morning to discuss the milestones for the next sprint.",
        "Hi, just following up on our previous email regarding the lab equipment maintenance schedule."
    ]

    rows = []
    for i in range(num_samples):
        is_spam = (i % 2 == 0)
        label = "spam" if is_spam else "ham"
        template = spam_templates[i % len(spam_templates)] if is_spam else ham_templates[i % len(ham_templates)]
        
        # Add slight lexical variations
        words = template.split()
        if rng.random() > 0.4:
            extra_token = rng.choice(["details", "important", "update", "notes", "request", "review", "confirmed"])
            words.append(extra_token)
        text = " ".join(words)
        
        rows.append({
            "email_id": f"EMAIL_{i+1:04d}",
            "text": text,
            "label": label
        })

    df_spam = pd.DataFrame(rows)
    df_spam = df_spam.sample(frac=1.0, random_state=SEED % (2**32 - 1)).reset_index(drop=True)
    df_spam.to_csv("spam_dataset.csv", index=False)
    print(f"Generated spam_dataset.csv with {len(df_spam)} samples (50% spam, 50% ham).")

generate_spam_dataset()
print("All datasets generated successfully!")
