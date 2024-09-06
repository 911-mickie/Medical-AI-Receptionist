import openai
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from transformers import BertForSequenceClassification, BertTokenizer, pipeline
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, PointStruct
import json
import os
from dotenv import load_dotenv

# Load the language model and embedding model
embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Load the fine-tuned model and tokenizer for intent classification
intent_model = BertForSequenceClassification.from_pretrained(r'C:\Testing\AI-Receptionist\Fine-Tuned-Bert')
tokenizer = BertTokenizer.from_pretrained(r'C:\Testing\AI-Receptionist\Fine-Tuned-Bert')

# Intent classification pipeline
nlp_pipeline = pipeline("text-classification", model=intent_model, tokenizer=tokenizer)

# openai.api_key = os.getenv("OPENAI_API_KEY")
load_dotenv()

openai_client = OpenAI(
    api_key = os.environ.get("OPENAI_API_KEY")
)

# Connect to Qdrant
client = QdrantClient(host="localhost", port=6334)

# Initialize a collection in Qdrant
collection_name = "emergencies"
client.recreate_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=embedding_model.get_sentence_embedding_dimension(), distance="Cosine"),
)

# Load emergency data from JSON file with error handling
try:
    with open('emergency_data.json', 'r') as f:
        emergency_data = json.load(f).get('emergencies', [])
        # Insert emergency data into Qdrant
        for idx, emergency in enumerate(emergency_data):
            keywords_text = " ".join(emergency.get('keywords', []))
            embedding = embedding_model.encode(keywords_text)
            #print(f"DEBUG: Embedding for {emergency['name']} generated: {embedding[:5]}...")  # Debug: Print part of the embedding
            point = PointStruct(id=idx, vector=embedding, payload={"name": emergency['name'], "steps": emergency['steps']})
            client.upsert(collection_name=collection_name, points=[point])
except FileNotFoundError:
    print("Error: 'emergency_data.json' file not found.")
    emergency_data = []
except json.JSONDecodeError:
    print("Error: Failed to decode JSON from 'emergency_data.json'.")
    emergency_data = []

# Function to classify intent
def classify_intent(text):
    result = nlp_pipeline(text)[0]
    intent_label = result['label']
    #print(f"DEBUG: Intent classified as {intent_label}")  # Debug: Print classified intent
    intent = 0 if intent_label == 'LABEL_0' else 1
    return intent

# Function to find the best match and generate augmented response
def find_best_match(user_input):
    user_embedding = embedding_model.encode(user_input)
    #print(f"DEBUG: User embedding generated: {user_embedding[:5]}...")  # Debug: Print part of the user embedding
    
    # Perform the search on Qdrant
    search_result = client.search(
        collection_name=collection_name,
        query_vector=user_embedding,
        limit=1  # We only want the top match
    )
    
    # Debugging the search result
    if search_result:
        best_match = search_result[0].payload
        #print(f"DEBUG: Raw search result payload: {best_match}")  # Check the structure of 'best_match'
        
        similarity_score = search_result[0].score
        #print(f"DEBUG: Similarity Score: {similarity_score}")
        
        # Ensure best_match is a dictionary
        if isinstance(best_match, dict):
            # Now we proceed with RAG (Augmentation)
            augmented_response = generate_augmented_response(best_match, user_input)
            return augmented_response, similarity_score
        else:
            #print(f"DEBUG: Unexpected best_match type: {type(best_match)}")  # Check if best_match is not a dictionary
            return "Error: Unexpected response format from Qdrant.", 0
    else:
        #print("DEBUG: No match found in Qdrant.")
        return "Sorry, I couldn't find relevant information. Can you provide more details?", 0



def generate_augmented_response(retrieved_data, user_input):

    prompt = (
    f"The user reported: '{user_input}'.\n"
    f"Here are the steps retrieved from the emergency database: '{retrieved_data['steps']}'.\n"
    f"Please rephrase these steps to be clear and concise, no longer than 2-3 complete sentences."
    )
    
    # Make a call to the chat completion endpoint
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",  # Or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "You are an AI assistant that provides emergency instructions."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=50,
        temperature=0.9
    )
    
    return response.choices[0].message.content
