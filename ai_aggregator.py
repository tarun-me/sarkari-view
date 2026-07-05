import os
import time
import json
import requests
import pdfplumber
import urllib3
from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.parse import urljoin
from groq import Groq
from dotenv import load_dotenv
from supabase import create_client, Client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_relevant_notice(title, text=""):
    keywords = ["recruitment", "vacancy", "apply", "online", "bharti", "exam", "post", "notification", "crp", "agniveer", "vayu", "navy", "army", "hiring", "officer", "jobs"]
    combined_content = (title + " " + text).lower()
    return any(kw in combined_content for kw in keywords)

def get_existing_database_records():
    try:
        res = supabase.table("exams").select("id, notice_subject, department, last_date").execute()
        return res.data
    except Exception as e:
        print(f"⚠️ DB Fetch Error: {e}")
        return []

# ---- BROWSER CONFIGURATION JAHAN TIMEOUTS KHATAM HONGE ----
if os.getenv("GITHUB_ACTIONS") == "true":
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    
    # 🔥 FIX 1: Heavy images ko download hone se roko taaki Renderer crash na ho
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    # 🔥 FIX 2: Hide automation footprint (Sarkari firewalls ko bypass karne ke liye)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(options=options)
else:
    driver = webdriver.Safari()

# Safe buffer timeout
driver.set_page_load_timeout(35)

try:
    with open("sites.json", "r") as f:
        sites = json.load(f)
    all_sites_list = sites["central_jobs"] + sites["state_jobs"]

    for site in all_sites_list:
        print(f"\n🌍 Checking {site['name']}...")
        try:
            driver.get(site['url'])
            time.sleep(5) 
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            extracted_texts_to_analyze = []

            # ---- CASE 1: SARKARI RESULT (BROAD SEARCH) ----
            if "sarkariresult.com" in site['url'].lower():
                print("🎯 Sarkari Result sections scan ho rahe hain...")
                job_links = []
                for link in soup.find_all("a", href=True):
                    href = link['href'].lower()
                    text = link.text.strip()
                    
                    # 🔥 FIX 3: Broaden matching parameters for Sarkari Result sub-folders
                    if any(x in href for x in ["/latestjob/", "/state-job/", "/force/", "/ssc/", "/upsc/", "/bank/", "/railway/"]) or "recruitment" in href or "agniveer" in href:
                        if is_relevant_notice(text):
                            full_job_url = urljoin(site['url'], link['href'])
                            if full_job_url not in [j[1] for j in job_links]:
                                job_links.append((text, full_job_url))
                
                for title, j_url in job_links[:6]:
                    print(f"🔗 Visiting Job Page: {title}")
                    try:
                        driver.get(j_url)
                        time.sleep(3)
                        j_soup = BeautifulSoup(driver.page_source, "html.parser")
                        page_text = j_soup.get_text(separator=' ', strip=True)
                        extracted_texts_to_analyze.append({"source": title, "text": page_text[:3500]})
                    except Exception as je:
                        print(f"⚠️ Skipping slow job page: {title}")

            # ---- CASE 2: OFFICIAL SITES (PDF) ----
            else:
                all_links = soup.find_all("a")
                valid_pdf_links = []
                for link in all_links:
                    href = link.get("href")
                    if href and ".pdf" in href.lower():
                        title = link.text.strip() or "Notice"
                        if is_relevant_notice(title):
                            valid_pdf_links.append((title, urljoin(site['url'], href)))
                        if len(valid_pdf_links) >= 3:
                            break
                
                for title, pdf_link in valid_pdf_links:
                    print(f"📄 Downloading PDF: {title}")
                    try:
                        res = requests.get(pdf_link, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=12)
                        if 'application/pdf' in res.headers.get('Content-Type', ''):
                            with open("temp.pdf", "wb") as f:
                                f.write(res.content)
                            with pdfplumber.open("temp.pdf") as pdf:
                                pdf_text = pdf.pages[0].extract_text() or ""
                            os.remove("temp.pdf")
                            
                            if pdf_text.strip() and is_relevant_notice(title, pdf_text):
                                extracted_texts_to_analyze.append({"source": title, "text": pdf_text})
                    except Exception as pe:
                        print(f"⚠️ PDF Download Failed for {title}")

            # ---- AI PROCESSING VIA GROQ ----
            if not extracted_texts_to_analyze:
                print(f"⏭️ No relevant active forms found on {site['name']}.")
                continue

            existing_db_data = get_existing_database_records()

            for item in extracted_texts_to_analyze:
                print(f"🧠 AI Analyzing notice: {item['source']}")
                
                prompt = f"""
                You are a Data Management AI for a Job Portal.
                Analyze this recruitment raw content: {item['text']}
                
                Existing Exams in Database:
                {json.dumps(existing_db_data)}
                
                Task:
                1. Verify if this text is an official government recruitment application form.
                2. Check if it already exists in the Database list intelligently.
                3. If it's a DUPLICATE or an UPDATE, set "is_duplicate_or_update" to true and provide the "existing_id".
                
                Respond STRICTLY in this JSON format:
                {{
                  "is_valid_exam": boolean,
                  "is_duplicate_or_update": boolean,
                  "existing_id": integer or null,
                  "department": string,
                  "notice_subject": string,
                  "form_status": string,
                  "start_date": string,
                  "last_date": string,
                  "exam_date": string
                }}
                """
                try:
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "You are a database parser that outputs raw JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        model="llama-3.3-70b-versatile",
                        response_format={"type": "json_object"}
                    )
                    
                    ai_data = json.loads(chat_completion.choices[0].message.content)
                    
                    if ai_data.get("is_valid_exam") == True:
                        is_dup = ai_data.pop("is_duplicate_or_update", False)
                        existing_id = ai_data.pop("existing_id", None)
                        ai_data.pop("is_valid_exam", None)

                        if is_dup and existing_id:
                            supabase.table("exams").update(ai_data).eq("id", existing_id).execute()
                            print(f"🔄 AI MERGE SUCCESS: Updated ID {existing_id}")
                        else:
                            supabase.table("exams").insert(ai_data).execute()
                            print(f"💾 NEW INSERT SUCCESS: Saved {ai_data['notice_subject']}")
                    else:
                        print("⏭️ AI Filtered out: Not a valid active recruitment form.")
                except Exception as ai_err:
                    print(f"⚠️ Groq processing failed for this entry: {ai_err}")

        except Exception as se:
            print(f"❌ Handled site timeout or error for {site['name']}")

finally:
    driver.quit()
    print("\n✅ System closed cleanly.")
