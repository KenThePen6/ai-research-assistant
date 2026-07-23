from flask import Flask, render_template, request
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
import traceback
from citation import Citation
import openai
from dotenv import load_dotenv
import json
import os
import requests
from flask import make_response

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)


def save_citation(citation_data, filename="citations.json"):
    try:
        # If file exists, load current data
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    data = json.load(f)  # load existing JSON array
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        # Append new citation
        data.append(citation_data)

        # Save back as proper JSON array
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        print(f"Error saving citation: {e}")


def ai_summarize(text):
    if not text:
        return "No abstract available."
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": "You are an AI that summarizes research abstracts."},
                {"role": "user", "content": f"Summarize this abstract in 2-3 sentences:\n{text}"}
            ],
            temperature=0.7
        )
        return response.choices[0].message["content"].strip()
    except Exception:
        return None


def ai_expand_question(query):
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an academic research assistant."},
                {"role": "user", "content": f"Expand and improve this research question: {query}"}
            ],
            temperature=0.8
        )
        return response.choices[0].message["content"].strip()
    except Exception:
        return None


def ai_polish_citation(metadata):
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": "You are an AI that formats academic citations."},
                {"role": "user", "content": f"Fix and format this citation metadata nicely:\n{metadata}"}
            ],
            temperature=0.5
        )
        return response.choices[0].message["content"].strip()
    except Exception:
        return None

# Home page


@app.route('/')
def home():
    return render_template('home.html')

# Upload page


@app.route('/upload')
def upload():
    return render_template('upload.html')

# Process Download page


@app.route('/download', methods=['POST'])
def download():
    try:
        apa = request.form.get('apa')
        mla = request.form.get('mla')
        chicago = request.form.get('chicago')

        content = f"APA:\n{apa}\n\nMLA:\n{mla}\n\nChicago:\n{chicago}"

        response = make_response(content)
        response.headers["Content-Disposition"] = "attachment; filename=citations.txt"
        response.headers["Content-Type"] = "text/plain"
        return response
    except Exception as e:
        return f"Error generating download:<br>{str(e)}"

# Process PDF upload


@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    try:
        pdf_file = request.files.get('pdf_file')
        if not pdf_file:
            return "No PDF uploaded."

        # Save PDF temporarily
        filepath = f"temp_{pdf_file.filename}"
        pdf_file.save(filepath)

        # Extract metadata
        reader = PdfReader(filepath)
        metadata = reader.metadata

        title = metadata.title or "Unknown Title"
        author = metadata.author or "Unknown Author"
        creator = metadata.creator or "Unknown Creator"
        # Create citation object
        citation = Citation(title, author, "Unknown Date", source_type="pdf")

        # Format citations
        apa_cite = citation.apa()
        mla_cite = citation.mla()
        chicago_cite = citation.chicago()

        # Save to citations.json
        save_citation({
            "title": title,
            "author": author,
            "date": "Unknown Date",
            "format": "PDF"
        })

        return render_template(
            "results.html",
            title=title,
            author=author,
            date="Unknown Date",
            apa=apa_cite,
            mla=mla_cite,
            chicago=chicago_cite
        )

    except Exception as e:
        return f"Error reading PDF:<br>{str(e)}<br><pre>{traceback.format_exc()}</pre>"

# Process URL input


@app.route('/process_url', methods=['POST'])
def process_url():
    try:
        url = request.form.get('url')
        if not url:
            return "No URL provided."

        response = requests.get(url, timeout=8)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title = soup.title.string if soup.title else "Unknown Title"

        # Extract author
        author_tag = (
            soup.find("meta", attrs={"name": "author"}) or
            soup.find("meta", attrs={"property": "article:author"}) or
            soup.find("meta", attrs={"name": "dc.creator"})
        )
        author = author_tag["content"] if author_tag and "content" in author_tag.attrs else "Unknown Author"

        # Extract date
        date_tag = (
            soup.find("meta", attrs={"property": "article:published_time"}) or
            soup.find("meta", attrs={"name": "date"}) or
            soup.find("meta", attrs={"property": "og:updated_time"})
        )
        date = date_tag["content"] if date_tag and "content" in date_tag.attrs else "Unknown Date"

        # Create citation for URL
        citation = Citation(title, author, date, source_type="website")

        apa_cite = citation.apa()
        mla_cite = citation.mla()
        chicago_cite = citation.chicago()

        # Save to citations.json
        save_citation({
            "title": title,
            "author": author,
            "date": "Unknown Date",
            "format": "PDF"
        })

        return render_template(
            "results.html",
            title=title,
            author=author,
            date=date,
            apa=apa_cite,
            mla=mla_cite,
            chicago=chicago_cite
        )

    except Exception as e:
        return f"Error processing URL:<br>{str(e)}<br><pre>{traceback.format_exc()}</pre>"


@app.route('/ask')
def ask():
    return render_template("ask.html")


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == "POST":
        query = request.form.get("query")
        page = 1
        expanded_info = ai_expand_question(query)  # AI expansion
    else:
        query = request.args.get("query")
        page = int(request.args.get("page", 1))
        expanded_info = None

    # Fetch papers
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": 5,
        "offset": (page-1)*5,
        "fields": "title,abstract,year,authors,url"
    }

    response = requests.get(url, params=params)
    data = response.json().get("data", [])

    papers = []
    for result in data:
        title = result.get("title", "No title")
        abstract = result.get("abstract", "")
        year = result.get("year", "Unknown year")
        authors_list = result.get("authors", [])
        authors = ", ".join([a.get("name", "Unknown") for a in authors_list])
        paper_url = result.get("url", "#")

        # Try AI summary, fallback to plain abstract
        summary = ai_summarize(abstract) or abstract or "No summary available."

        papers.append({
            "title": title,
            "authors": authors,
            "year": year,
            "url": paper_url,
            "summary": summary
        })

    return render_template("search_results.html",
                           query=query,
                           papers=papers,
                           expanded_info=expanded_info,
                           next_page=page + 1)


if __name__ == '__main__':
    app.run(debug=True)
