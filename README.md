## Steps to follow

Make sure to download the fine tuned intent model from google drive.

Make sure to update the path of the model in main.py.

Run docker on terminal

Run - docker pull qdrant/qdrant

Run - docker run -p 6334:6333 qdrant/qdrant

create virtual environment 

Run python -m venv env

Run env\Scripts\activate

Run pip install -r requirements.txt

Run uvicorn main:app --reload
