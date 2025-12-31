from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
import json
import time
import os
import logging
import hashlib
from pathlib import Path
import subprocess
import socket
from django.http import HttpResponse
from EB.views import run_email_script

import time
import os

# from transformers import (AutoTokenizer,AutoModelForSeq2SeqLM,)
# chatbot now runs in socket so no longer needs to import from transformer

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE = 'I am sorry, I do not understand. Please contact mrcadillac@newcadillacdatabase.org for further assistance.'

CHATBOT_QUESTIONS_URL_ROOT = settings.CHATBOT_QUESTIONS_URL_ROOT
questions_without_answer_path = os.path.join(CHATBOT_QUESTIONS_URL_ROOT, "questions_without_answer.json")
questions_with_answers_path = os.path.join(CHATBOT_QUESTIONS_URL_ROOT, "questions_with_answers.json")

# Added a try except block to avoid django app crash on startup. Now it defaults to an empty list.
try:
    with open(questions_with_answers_path, "r", encoding="utf-8") as saved_questions_file:
        shortcut_qa = json.load(saved_questions_file)
except Exception as e:
    logger.error(f"Failed to load shortcut QA file: {e}")
    shortcut_qa = []

def chat_page(request):
    """ Chatbot demo page """
    return render(request, 'demo.html')

def send_alert_email(alert_subject,alert_body):
    try:
        logger.info("Email subject: " + alert_subject)
        logger.info("Email message: " + alert_body)

        script_args = []
        script_args.append(False)
        script_args.append(alert_subject)
        script_args.append(settings.EMAIL_ADMIN)
        script_args.append(alert_body)
        script_output = run_email_script(script_args)
        # script_output = local_run_email_script(script_args)
        if script_output.stderr == '':
            print('The email was sent successfully.')
            logger.info('The email was sent successfully.')
        else:
            logger.info(f"The SendMail emailer script encountered an error: {script_output.stderr}")
    except Exception as e:
        logger.error(f'An error occurred running the SendMail emailer script: {e}')

def add_unanswered_question(question):
    """Add unanswered question to a file"""
    with open(questions_without_answer_path, 'r', encoding='utf-8') as json_file:
        questions_without_answer = json.load(json_file)
    question_dict = questions_without_answer["questions"]
    question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()
    new_unaswered_question = {
        "content": question
    }
    question_dict[question_hash] = new_unaswered_question
    questions_without_answer["questions"] = question_dict
    print(f"len of question_dict is {len(question_dict)}")
    if len(question_dict) > 50: 
        print("preparing to send email to admin")
        alert_subject = "Alert: There are more than 50 questions in NCDB waiting for you to answer"
        alert_body = "Message: Please answer new questions in https://www.newcadillacdatabase.org."
        send_alert_email(alert_subject,alert_body)
    with open(questions_without_answer_path, 'w', encoding='utf-8') as json_file:
        json.dump(questions_without_answer, json_file)

def generate_answer_from_llm(query):
     # Now it sends the query to a get_llm_answer.py via Sockets.
    HOST = '0.0.0.0'
    PORT = 12345
    
    # this get response through socket from get_llm_answer.py in NCDBContent/Chatbot
    # Here is using socket because embedding models, embedding database and LLM
    # should only load once after getting new knowledge, instead of loading
    # each time if each user ask a question
    # Running get_llm_answer.py without using socket will add a lot of time & resources
    # for loading embedding models, embedding database and LLM each time

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Added a 20 second timeout to prevent the website from freezing 
            s.settimeout(20) 
            s.connect((HOST, PORT))
            s.sendall(query.encode('utf-8'))
            # Increased buffer size to 4096
            response = s.recv(4096).decode('utf-8')
            return response
    except Exception as e:
        # Added error logging
        logger.error(f"Chatbot Service Error: {e}")
        return "I do not know."

def chat(request):
    query = request.GET.get("query")
    # Added validation to handle empty requests gracefully.
    if not query:
        return JsonResponse({"status": False, "data": "No query provided."})

    response_str = None

    # look for an answer first
    for item in shortcut_qa:
        if item['question'].lower() == query.lower():
            response_str = item['answer']
            break
    
    # if no answer then use LLM socket service
    if response_str is None:
        answer_generated_from_llm = generate_answer_from_llm(query)
        
         # If AI fails or doesn't know log the question for the admin.
        if answer_generated_from_llm == "I do not know." or not answer_generated_from_llm:
            response_str = DEFAULT_RESPONSE
            add_unanswered_question(query)
        else:
            response_str = answer_generated_from_llm                

    resp_data = {
        "status": True,
        "data": response_str
    }
    # ensure the browser interprets the response as JSON.
    return HttpResponse(json.dumps(resp_data), content_type="application/json")


@staff_member_required
def admin(request):
    """Chatbot admin page"""
    ctx = {}

    return render(request, 'Chatbot/admin.html', ctx)


@staff_member_required
def get_new_question(request):
    """handle get request for new questions"""
    if is_ajax(request) and request.method == "GET":
        empty_question = {"hash": "N/A", "content": "N/A"}
        with open(questions_without_answer_path, 'r', encoding='utf-8') as file:
            unaswered_questions = json.load(file)["questions"]
            if not bool(unaswered_questions):
                question_hash = "N/A"
            else:
                question_hash = next(iter(unaswered_questions))
        if question_hash == "N/A":
            question = empty_question
        else:
            question = {"hash": question_hash,
                        "content": unaswered_questions[question_hash]["content"]}
        logger.info("The new question sent has content: %s, and hash: %s",
                    question["content"], question["hash"])
        return JsonResponse({"question": question}, status=200)
    else:
        return JsonResponse({"error": "Wrong request"}, status=400)


def is_ajax(request):
    """helper function to check whether a request is a ajax request"""
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

@csrf_exempt
@staff_member_required
def answer(request):
    """handle request to post an answer to a question"""
    if is_ajax(request) and request.method == "POST":
        question_with_answer = json.loads(
            request.body).get("question_with_answer")
        logger.info(question_with_answer)
        question_answer = question_with_answer.get("answer")
        question_hash = question_with_answer.get("hash")
        question_content = question_with_answer.get("question")
        msg = "We get the answer: "+question_answer+"for question: " + \
            question_content+" with hash: "+question_hash
        logger.info(msg)

        # delete this question in questions_without_answer_path
        with open(questions_without_answer_path, "r", encoding="utf-8") as file:
            questions_without_answer = json.load(file)
            del questions_without_answer["questions"][question_hash]

        # Load existing data from the JSON file
        with open(questions_with_answers_path, 'r') as json_file:
            existing_data = json.load(json_file)

        # New question and answer to add
        new_entry = {
            "question": question_content,
            "answer": question_answer
        }

        # Add the new entry at the beginning of the existing data
        existing_data.insert(0, new_entry)

        # Write the updated data back to the JSON file
        with open(questions_with_answers_path, 'w') as json_file:
            json.dump(existing_data, json_file, indent=4)

        print("New entry added to the beginning of the JSON file.")
        return JsonResponse({"msg": msg}, status=200)
    else:
        return JsonResponse({"error": "Wrong request"}, status=400)
