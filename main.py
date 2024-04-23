from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.llms import Ollama


import re
import json
from urllib.parse import urlparse
import csv

from utils import get_html_body_from_document, response_from_llm, handle_unncessary_http

casual_delimiter = "\n ========= \n"
chunk_size = 10000
step_size = chunk_size - 500

input_url = input("Enter URL with list of faculties: ")
if input_url.endswith('/'):
    input_url =  input_url[:-1]
    

loader = AsyncHtmlLoader(input_url)
docs = loader.load() # array of Documents

# removing header, footer, style, script 
html_body_str  = get_html_body_from_document(docs[0])


llm = Ollama(model="llama3")


# From input_url content, get list of prof name and URL
extract_name_url_instruct = """"
    From the above HTML content, extract name of professor and URL to their webpage and write in below format:

    (Professor Name): (URL to their webpage)

    If the name or URL to their webpage is not available then write '---'
    
"""

name_url_output = ''
for i in range(0, len(html_body_str), step_size):
    html_chunk = html_body_str[i:i + chunk_size]
    extract_name_url_prompt = casual_delimiter + html_chunk + casual_delimiter + extract_name_url_instruct
    name_url_output += response_from_llm(llm, extract_name_url_prompt)
    print('\n --- XXX --- \n')


# From list of prof name and URL, make a JSON
text_to_json_instruct = """
    From the above text, make a JSON with keyname 'data' and value is an array of objects for names where URL is available. 
    Each object has professor name and their href. 
    Ignore the ones where the name of professor is '---' or missing. Ignore the ones where the URL is '---' or missing.
    Example: {'data': [ {'name': 'John', 'url': '/research/faculty/45'}  ]  }. 
    Don't write code. Don't write anything else. Give me JSON only
"""
text_to_json_prompt = casual_delimiter + name_url_output + casual_delimiter + text_to_json_instruct
json_output = response_from_llm(llm, text_to_json_prompt)


match = re.search(r'\{.*\}', json_output, re.DOTALL)
if match:
    json_str = match.group(0)
    # Parse the JSON string
    data_dict = json.loads(json_str)
    print(data_dict)  # or process the data as needed
else:
    print("No JSON found in the text")


data_arr = data_dict['data']

# Add hostname in the URLs
parsed_url = urlparse(input_url)
hostname = f"{parsed_url.scheme}://{parsed_url.netloc}"

indiv_prof_web_pages = []
for idx, name_url_dict in enumerate(data_arr):
    prof_name = name_url_dict['name']
    prof_url = name_url_dict['url']
    
    if not prof_url.startswith('http'):
        prof_web_page = hostname + prof_url
    else:
        if '.' not in prof_url:
            prof_url = handle_unncessary_http(prof_url)
            prof_web_page = hostname + prof_url
        else:
            prof_web_page = prof_url
    
    # change to complete URL
    data_arr[idx]['url'] = prof_web_page
    indiv_prof_web_pages.append(prof_web_page)


# Load HTML pages of indiv prof web pages
next_loader = AsyncHtmlLoader(indiv_prof_web_pages)
prof_website_docs = next_loader.load()

# Include HTML content of indiv prof in data_arr
for idx, prof_doc in enumerate(prof_website_docs):
    data_arr[idx]['html_body'] = get_html_body_from_document(prof_doc)

# Extract email, work summary, indiv lab page
# TODO: it doesn't write in this format always. Need to feed into LLM again
extract_prof_details_instruct = """
    From the above HTML content, extract the following:
    1) Lab webpage or professor's personal website
    2) Summary of professor's research under 100 words
    3) Email address of professor

    The extract content should be output in the following format only as in the below example.
    
    LABPAGE: https://example_webpage_of_prof.com 
     
    SUMMARY:  The example prof works on example topic in less than 100 words 
    EMAIL:  example_prof@gmail.com 

    If any piece of information is missing, put "---" instead.
"""

for idx, prof_info in enumerate(data_arr):
    prof_html_body = prof_info.get('html_body')
    if prof_html_body == None:
        continue
    str_html_body = str(prof_html_body)
    trimmed_str = str_html_body[0:min(len(str_html_body), 5000)]
    extract_prof_details_prompt = casual_delimiter + trimmed_str + casual_delimiter + extract_prof_details_instruct
    
    respone_single_prof = response_from_llm(llm, extract_prof_details_prompt)
    
    lab_page_pattern = r"LABPAGE: (\S+)"
    summary_pattern = r"SUMMARY: (.+)"
    email_pattern = r"EMAIL: (\S+)"

    personal_url = re.search(lab_page_pattern, respone_single_prof).group(1)
    summary = re.search(summary_pattern, respone_single_prof).group(1)
    email = re.search(email_pattern, respone_single_prof).group(1)

    data_arr[idx]['personal_url'] = personal_url
    data_arr[idx]['work_summary'] = summary
    data_arr[idx]['email'] = email
    data_arr[idx]['webpage_info_by_LLM'] = respone_single_prof 


    print('\n  ====== \n')


headers = ["Name", "Instiute Webpage URL", "Personal webpage", "email", "Work Summary"]
keys = ["name", "url", "personal_url", "email", "work_summary"]

with open('data.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=headers)
    writer.writeheader()

    for item in data_arr:
        row = {header: item.get(key) for header, key in zip(headers, keys)}
        writer.writerow(row)