from bs4 import BeautifulSoup
import re

def get_html_body_from_document(doc):
    """
    input:
        doc: Document object with 'doc.page_content' having HTML
    
    output:
        html_body_trimmed(str type): HTML of the document with unncessary tags removed
    """

    soup = BeautifulSoup(doc.page_content, 'html.parser')
    body_content = soup.body

    for header in body_content.find_all('header'):
            header.decompose()

    for footer in body_content.find_all('footer'):
        footer.decompose()

    for script in body_content.find_all('script'):
        script.decompose()

    for style in body_content.find_all('style'):
        style.decompose()

    body_string = str(body_content)
    
    return body_string



def handle_unncessary_http(url):
    """
    inputs url: str
    remove http/https:// and add '/'
    """
    modified_url = re.sub(r'^https?://', '', url)
    return '/' + modified_url
    



def response_from_llm(llm, query):
    """
    inputs:
        llm: takes an llm
        query: a prompt
    
    output:
        prints response and returns it at once
    """
    response = ''
    for chunks in llm.stream(query):
        response += chunks
        print(chunks, end = '')
    
    return response