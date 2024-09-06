import time
import asyncio
import threading
from utils import classify_intent, find_best_match
import random
import re


class AIReceptionist:
    def __init__(self):
        self.conversation_state = {} 

    @staticmethod
    def is_valid_input(user_input):
        # Check if the input contains only numbers or non-alphabetic characters
        if re.match(r'^[\d\W_]+$', user_input):
            return False  # Invalid input (only numbers or non-alphabetic characters)
        
        # If input passes all checks, return True
        return True


    async def handle_message(self, user_input, session_id, websocket):

        if not self.is_valid_input(user_input):
            await websocket.send_text("I could not understand what you typed. Could you please repeat?")
            return

        if session_id not in self.conversation_state:
            self.conversation_state[session_id] = {
                'step': 1, 
                'waiting': False, 
                'best_match': None, 
                'last_question': '', 
                'delayed_response': None, 
                'location': None
            }

        state = self.conversation_state[session_id]

        def repeat_last_question():
            return f"I don’t understand that. {state['last_question']}"

        if state['step'] == 1:
            state['last_question'] = "Are you having an emergency, or would you like to leave a message?"
            state['step'] = 2
            await websocket.send_text(state['last_question'])

        elif state['step'] == 2:
            intent = classify_intent(user_input)

            if intent == 0:  # Emergency
                state['last_question'] = "Please describe the emergency."
                state['step'] = 3
                await websocket.send_text("It appears that you are in distress. " + state['last_question'])

            elif intent == 1:  # Message
                state['last_question'] = "Please leave a message. I will make sure he receives it."
                state['step'] = 5
                await websocket.send_text("It appears that you wish to talk to the doctor. " + state['last_question'])

            else:
                state['step'] = 1
                await websocket.send_text(repeat_last_question())

        elif state['step'] == 3:
            # Store the user's emergency description before processing the match
            state['emergency_description'] = user_input  # Store the emergency description
            
            # Find best match and get the augmented response (which is now a string)
            augmented_response, similarity_score = find_best_match(state['emergency_description'])
            
            if similarity_score < 0.5:
                state['last_question'] = "Could you please describe the situation in more detail?"
                await websocket.send_text("I'm not sure I understand. " + state['last_question'])
            else:
                # In this case, we no longer store best_match as a dict; we store the augmented response
                state['best_match'] = augmented_response  # Store the full augmented response (now a string)
                state['last_question'] = "Can you tell me which area you are located right now?"
                state['step'] = 4  # Move to next step to collect location
                await websocket.send_text(f"I am checking what you should do immediately. {state['last_question']}")
                
                # Start the delayed response thread
                self.start_delayed_response_thread(session_id, websocket)


        elif state['step'] == 4:
            # This is where the location should be captured from user input
            state['location'] = user_input
            eta = random.randint(5, 15)
            
            await websocket.send_text(f"Dr. Adrin will arrive at your location in approximately {eta} minutes. Please hold just a sec for further instructions.")
            state['step'] = 6

        elif state['step'] == 5:
            del self.conversation_state[session_id]  # Reset conversation state for the session
            await websocket.send_text("Thanks for the message, I will forward it to Dr. Adrin.")

        elif state['step'] == 6:
            # Send delayed response if available and reset the state after sending
            if state['delayed_response']:
                await websocket.send_text(state['delayed_response'])
                state['delayed_response'] = None  # Clear the delayed response
                state['step'] = 1  # Reset state to start again for the next user input
            else:
                state['step'] = 1  # Reset state to handle new input
                await websocket.send_text("Don't worry, Dr. Adrin will be with you shortly. Please follow the steps I provide.")

    def start_delayed_response_thread(self, session_id, websocket):
        """Start a thread to handle the delayed emergency response."""
        threading.Thread(target=self.delayed_emergency_response, args=(session_id, websocket)).start()

    def delayed_emergency_response(self, session_id, websocket):
        """Function to simulate delayed database search in a separate thread."""
        time.sleep(15)  # Simulate the delay
        state = self.conversation_state[session_id]
        
        # Call the find_best_match function (returns augmented response string and similarity)
        augmented_response, similarity_score = find_best_match(state['emergency_description'])

        if similarity_score >= 0.5:
            # No need to handle this as a dictionary; just send the augmented response string
            state['delayed_response'] = augmented_response
        else:
            state['delayed_response'] = "I'm not sure I understand. Could you please describe the situation in more detail?"

        # After generating the response, send it to the user via WebSocket
        asyncio.run(self.send_delayed_response(session_id, websocket))


    async def send_delayed_response(self, session_id, websocket):
        """Send the delayed response through WebSocket after the delay."""
        state = self.conversation_state.get(session_id)
        if state and state['delayed_response']:
            await websocket.send_text(state['delayed_response'])
            state['delayed_response'] = None  # Clear it after sending
