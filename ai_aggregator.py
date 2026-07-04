import os
import time
import json
import requests
import pdfplumber
import urllib3
from bs4 import BeautifulSoup
from selenium import webdriver
from urllib.parse import urljoin
from google import genai
from google.genai import types
from dotenv import load_dotenv
from supabase import create_client, Client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = genai.Client(api_key=API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Supabase se saara purana data le aao AI ko dikhane ke liye
def get_existing_database_records():
    try:
        res = supabase.table("exams").select("id, notice_subject, department, last_date").execute()
        return res.data
    except Exception as e:
        print(f"⚠️ DB Fetch Error: {e}")
        return []

if os.getenv("GITHUB_ACTIONS") == "true":
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
else:
    driver = webdriver.Safari()

driver.set_page_load_timeout(45)

try:
    with open("sites.json", "r") as f:
        sites = json.load(f)
    all_sites_list = sites["central_jobs"] + sites["state_jobs"]

    for site in all_sites_list:
        print(f"\n🌍 Checking {site['name']}...")
        try:
            driver.get(site['url'])
            time.sleep(7) # Dhang se load hone ka time dein
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            extracted_texts_to_analyze = []

            # ---- CASE 1: SARKARI RESULT AGGREGATOR SCRAPING ----
            if "sarkariresult.com" in site['url'].lower():
                print("🎯 Sarkari Result ka Latest Jobs section scan ho raha hai...")
                # Latest Job column ke andar ke links dhoondna
                job_links = []
                for link in soup.find_all("a", href=True):
                    if "/latestjob/" in link['href'].lower():
                        full_job_url = urljoin(site['url'], link['href'])
                        job_links.append((link.text.strip(), full_job_url))
                
                # Top 7 latest jobs ko deeply check karein
                for title, j_url in job_links[:7]:
                    print(f"🔗 Visiting Job Page: {title}")
                    try:
                        driver.get(j_url)
                        time.sleep(3)
                        j_soup = BeautifulSoup(driver.page_source, "html.parser")
                        # Poore page ka text nikal lo jahan dates hoti hain
                        page_text = j_soup.get_text(separator=' ', strip=True)
                        extracted_texts_to_analyze.append({"source": title, "text": page_text[:4000]}) # Limit token usage
                    except Exception as je:
                        print(f"⚠️ Job page error: {je}")

            # ---- CASE 2: OFFICIAL SITES (PDF BASE) ----
            else:
                all_links = soup.find_all("a")
                valid_pdf_links = []
                for link in all_links:
                    href = link.get("href")
                    if href and ".pdf" in href.lower():
                        valid_pdf_links.append((link.text.strip() or "Notice", urljoin(site['url'], href)))
                        if len(valid_pdf_links) >= 5: # Top 5 notices checked
                            break
                
                for title, pdf_link in valid_pdf_links:
                    print(f"📄 Downloading PDF: {title}")
                    try:
                        res = requests.get(pdf_link, headers={"User-Agent": "Mozilla"}, verify=False, timeout=15)
                        if 'application/pdf' in res.headers.get('Content-Type', ''):
                            with open("temp.pdf", "wb") as f:
                                f.write(res.content)
                            with pdfplumber.open("temp.pdf") as pdf:
                                pdf_text = pdf.pages[0].extract_text() or ""
                            os.remove("temp.pdf")
                            if pdf_text.strip():
                                extracted_texts_to_analyze.append({"source": title, "text": pdf_text})
                    except Exception as pe:
                        print(f"⚠️ PDF Error: {pe}")

            # ---- AI PROCESSING & SMART MERGE ----
            existing_db_data = get_existing_database_records()

            for item in extracted_texts_to_analyze:
                print(f"🧠 AI Analyzing notice from: {item['source']}")
                
                prompt = f"""
                You are a Data Management AI for a Job Portal.
                Analyze this recruitment raw content: {item['text']}
                
                Here is the list of existing exams currently in our Database:
                {json.dumps(existing_db_data)}
                
                Your Task:
                1. Identify if this text is an official government exam application form notice.
                2. Check if this exam already exists in the Database list (Match intelligently, e.g., 'Agniveer 01/2026' matches 'Airforce Agniveer Vayu Recruitment').
                3. If it is a DUPLICATE or an UPDATE to an existing exam, set "is_duplicate_or_update" to true and provide the "existing_id".
                4. If it is completely NEW and not in the database list, set "is_duplicate_or_update" to false and "existing_id" to null.
                
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
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                
                ai_data = json.loads(response.text)
                
                if ai_data.get("is_valid_exam") == True:
                    # Clear out fields not needed in SQL Columns
                    is_dup = ai_data.pop("is_duplicate_or_update", False)
                    existing_id = ai_data.pop("existing_id", None)
                    ai_data.pop("is_valid_exam", None)

                    if is_dup and existing_id:
                        # Database mein naye data ke sath update (Merge) karein
                        supabase.table("exams").update(ai_data).eq("id", existing_id).execute()
                        print(f"🔄 AI MERGE SUCCESS: Updated existing record ID {existing_id} for {ai_data['notice_subject']}")
                    else:
                        # Naya record fresh insert karein
                        supabase.table("exams").insert(ai_data).execute()
                        print(f"💾 NEW INSERT SUCCESS: Saved {ai_data['notice_subject']}")
                else:
                    print("⏭️ Filtered out: Not a valid exam form notice.")

        except Exception as se:
            print(f"❌ Error scraping site {site['name']}: {se}")

finally:
    driver.quit()
    print("\n✅ System closed.")
