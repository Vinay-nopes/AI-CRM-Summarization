import streamlit as st
import torch
import re

from transformers import (
pipeline,
T5Tokenizer,
T5ForConditionalGeneration,
BartTokenizer,
BartForConditionalGeneration
)

st.set_page_config(page_title="AI CRM Intelligence", layout="centered")

st.title("🧠 AI CRM Intelligence System")
st.write("Summarization + Sentiment + Category + Priority")

# ---------------------------------------------------
# Load Models
# ---------------------------------------------------

@st.cache_resource
def load_models():

    MODEL_PATH = "samsum_finetuned_model"

    tokenizer = T5Tokenizer.from_pretrained(MODEL_PATH)
    model = T5ForConditionalGeneration.from_pretrained(MODEL_PATH)

    bart_tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
    bart_model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")

    sentiment = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english"
    )

    zero_shot = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )

    return tokenizer, model, bart_tokenizer, bart_model, sentiment, zero_shot


tokenizer, model, bart_tokenizer, bart_model, sentiment_pipeline, zero_shot = load_models()

# ---------------------------------------------------
# Categories
# ---------------------------------------------------

candidate_labels = [
"customer complaint about service",
"customer asking for information",
"service booking or appointment request",
"urgent problem needing immediate help",
"casual conversation or feedback"
]

# ---------------------------------------------------
# Dialogue Cleaner
# ---------------------------------------------------

def clean_dialogue(text):

    text = re.sub(r"\b[A-Za-z]+:\s*", "", text)
    return text


# ---------------------------------------------------
# Smart Summarization Router
# ---------------------------------------------------

def generate_summary(dialogue):

    dialogue = clean_dialogue(dialogue)

    words = dialogue.split()

    # SHORT TEXT
    if len(words) < 20:
        return dialogue.strip()

    # MEDIUM TEXT → SAMSUM MODEL
    elif len(words) < 150:

        input_text = "summarize: " + dialogue

        inputs = tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        )

        with torch.no_grad():
         outputs = model.generate(
         **inputs,
         max_length=60,
         min_length=20,
         num_beams=6,
         length_penalty=2.0,
         no_repeat_ngram_size=3,
         early_stopping=True
       )

        summary = tokenizer.decode(outputs[0], skip_special_tokens=True)

        return summary

    # LONG TEXT → BART MODEL
    else:

        inputs = bart_tokenizer(
            dialogue,
            return_tensors="pt",
            truncation=True,
            max_length=1024
        )

        with torch.no_grad():
           outputs = bart_model.generate(
         **inputs,
          max_length=80,
          min_length=25,
          num_beams=6,
          length_penalty=2.0,
          no_repeat_ngram_size=3,
           early_stopping=True
        )

        summary = bart_tokenizer.decode(outputs[0], skip_special_tokens=True)

        return summary


# ---------------------------------------------------
# Priority Logic
# ---------------------------------------------------

def assign_priority(summary, sentiment):

    urgent_words = ["urgent", "immediately", "asap", "refund", "cancelled"]

    if any(word in summary.lower() for word in urgent_words):
        return "High"

    if sentiment == "NEGATIVE":
        return "Medium"

    return "Low"


# ---------------------------------------------------
# CRM Pipeline
# ---------------------------------------------------

def generate_crm_output(dialogue):

    summary = generate_summary(dialogue)

    # Sentiment + Confidence
    sentiment_result = sentiment_pipeline(summary)[0]
    sentiment = sentiment_result["label"]
    sentiment_conf = round(sentiment_result["score"] * 100, 2)

    # ---------------------------------------------------
    # Improved Category Detection
    # ---------------------------------------------------

    casual_words = ["lol","haha","bye","cu","fun talking","wtf"]

    # Only treat as casual if short + contains casual words
    if len(dialogue.split()) < 80 and any(word in dialogue.lower() for word in casual_words):

        category = "casual conversation or feedback"
        category_conf = 95.0

    else:

        category_result = zero_shot(dialogue, candidate_labels)
        category = category_result["labels"][0]
        category_conf = round(category_result["scores"][0] * 100, 2)

    # Priority
    priority = assign_priority(summary, sentiment)

    return summary, category, sentiment, priority, sentiment_conf, category_conf


# ---------------------------------------------------
# UI
# ---------------------------------------------------

dialogue = st.text_area("Enter customer dialogue:", height=200)

if st.button("Analyze Dialogue"):

    if dialogue.strip() == "":
        st.warning("Please enter a dialogue.")

    else:

        summary, category, sentiment, priority, sentiment_conf, category_conf = generate_crm_output(dialogue)

        st.subheader("📄 Summary")
        st.write(summary)

        st.subheader("📂 Category")
        st.write(f"{category} ({category_conf}%)")

        st.subheader("😊 Sentiment")
        st.write(f"{sentiment} ({sentiment_conf}%)")

        st.subheader("🚦 Priority")

        if priority == "High":
            st.error("HIGH 🔴")

        elif priority == "Medium":
            st.warning("MEDIUM 🟡")

        else:
            st.success("LOW 🟢")

        st.success("Analysis Complete ✅")