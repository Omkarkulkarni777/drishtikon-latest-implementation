# reading/rag.py
import time
import os
import sys
import tempfile
import uuid
from google import genai 
from google.genai import types
from google.genai.errors import ClientError
from dotenv import load_dotenv
from core.constants import STORE_DISPLAY_NAME
from core.llm_runner import run_llm_task
from core.llm_task import LLMTask
from core.playback_controls import non_blocking_play, play
from core.stt import listen_continuous
from core.stt_commands import helper_for_exit
from core.text_utils import split_into_sentences_rag
from core.tts import speak
from core.utils import retry, timeit
from core.tts_player import tts_main
from core.prompts import *

# Load environment variables
load_dotenv() 

def _get_or_create_file_search_store(client: genai.Client) -> str:
    """
    Checks for an existing store by display name. If found, returns its resource name.
    If not found, creates a new one and returns its resource name.
    Raises ClientError on permission failure (403).
    """
    print(f"Checking for existing store with display name: '{STORE_DISPLAY_NAME}'...")

    # 1. SEARCH FOR EXISTING STORE BY DISPLAY NAME
    try:
        # Note: client.file_search_stores.list() returns an iterator
        for store in client.file_search_stores.list():
            if store.display_name == STORE_DISPLAY_NAME:
                print(f"✅ Found existing store: {store.name}")
                return store.name
    except ClientError as e:
        # This handles the 403 PERMISSION_DENIED error during the list attempt.
        print("\n❌ CRITICAL PERMISSION ERROR DURING STORE LISTING/ACCESS ❌")
        print("Your API key lacks permissions to list File Search Stores. Error details below.")
        raise e
    except Exception as e:
        print(f"An unexpected error occurred during store listing: {e}")
        raise e

    # 2. CREATE NEW STORE (if not found)
    print("Store not found. Attempting to create a new one...")
    try:
        # Use the successful documentation pattern: name is auto-generated
        file_search_store = client.file_search_stores.create(
            config={'display_name': STORE_DISPLAY_NAME}
        )
        print(f"✅ Created new store: {file_search_store.name}")
        return file_search_store.name
    except ClientError as e:
        # This catches errors like ALREADY_EXISTS (if two processes try to create simultaneously) 
        # or another 403 on the create step.
        if 'ALREADY_EXISTS' in str(e):
             # Recursively call to retrieve the store that was just created by another process
             return _get_or_create_file_search_store(client)
        
        print("\n❌ CRITICAL ERROR DURING STORE CREATION ❌")
        raise e


def upload_text_to_store(text: str) -> str | None:
    """
    Manages the RAG lifecycle: gets/creates store, uploads text, and indexes.
    Returns the full resource name of the store used.
    """
    client = genai.Client()
    store_name = None

    try:
        # 1. Get or Create the File Search Store
        store_name = _get_or_create_file_search_store(client)
        if not store_name:
            return None 

        # 2. Create temporary file
        # Use mode="w" (write) and encoding="utf-8" for proper text handling
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=".txt") as f:
            f.write(text)
            file_path = f.name
        print(f"Created temp file: {file_path}")

        # 3. Upload + index file
        # Use a unique display name for the file to prevent conflicts in the store
        file_display_name = f"reading-doc-{uuid.uuid4().hex[:8]}"

        print(f"Uploading and indexing file to store {store_name}...")
        operation = client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store_name,
            config={
                'display_name': file_display_name
            }
        )
        
        # Wait for the indexing operation to complete
        while not operation.done:
            time.sleep(1)
            operation = client.operations.get(operation) 
            print(".", end="", flush=True)

        print("\n✅ Upload and indexing complete.")
        os.remove(file_path)
        return store_name
    
    except Exception as e:
        print(f"\n--- FATAL UPLOAD ERROR ---")
        print(e)
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path) # Clean up temp file on failure
        return None

@timeit("[RAG QUERY RESOLUTION]")
@retry(2)
def rag_query(question: str, store_name: str) -> str:
    """
    Runs a RAG query against the specified File Search store.
    """
    client = genai.Client()
    tool_store_names = [store_name]

    print(f"Querying store {store_name} with question: '{question}'")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=tool_store_names
                    )
                )
            ]
        )
    )

    return f"{response.text.strip()}\n\n"


def rag_query_voice(question: str) -> str:
    """
    Handles RAG query specifically for voice control context.
    It ensures the store exists before querying.
    """
    client = genai.Client()
    
    # 1. Get or Create the File Search Store
    try:
        store_name = _get_or_create_file_search_store(client)
    except Exception as e:
        return f"System error: Cannot initialize RAG store. Please check permissions."

    if not store_name:
        return "System error: Failed to retrieve store name."
    
    # 2. Run the actual RAG query
    answer = rag_query(question, store_name)
    return answer

def main_rag():
    # Announce rag mode
	play(tts_main, ask_query_intro_p)
	# Listen for user's voice question
	question = listen_continuous()
	if question is None or not question.strip() or helper_for_exit(question) == "q":
		# No question → back to voice mode
		play(tts_main, exiting_search_module_p)
		return

	else:    
		# Generate RAG answer
		play(tts_main, generating_answer_p)
		# --- RAG CALL ---
		task = LLMTask(
			rag_query_voice,
			question
		)

		answer = run_llm_task(task)
		print("\n========RAG ANSWER=======\n")
		print(answer)
		sentences = split_into_sentences_rag(answer)
		
		if not answer or not answer.strip() or answer.startswith("RAG Query Error"):
			play(tts_main, exiting_search_module_p)
			return
		else:
			# Speak the answer
			for i in range(len(sentences)):
				answer_audio = speak(sentences[i])
				wants_to_break_loop = non_blocking_play(tts_main, answer_audio, "Press 's' to stop response", stopping_response_p, in_a_loop=True)
				if wants_to_break_loop:
					break
			# Finished answer → back to voice mode
			play(tts_main, vc_back_p)
		
	return answer

if __name__ == "__main__":
    main_rag()
