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

if not API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Environment variables missing! Check .env file.")
    exit()

# Setup Clients
client = genai.Client(api_key=API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🤖 Browser aur AI Engine start ho rahe hain...\n")

# CLOUD ENVIRONMENT CHECK
if os.getenv("GITHUB_ACTIONS") == "true":
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
else:
    driver = webdriver.Safari()

driver.set_page_load_timeout(30)

try:
    with open("sites.json", "r") as f:
        sites = json.load(f)

    all_sites_list = sites["central_jobs"] + sites["state_jobs"]

    for site in all_sites_list:
        print(f"\n🌍 Checking {site['name']} at {site['url']}...")
        
        try:
            driver.get(site['url'])
            time.sleep(5) 
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            all_links = soup.find_all("a")
            
            valid_pdf_links = []
            for link in all_links:
                href = link.get("href")
                if href and ".pdf" in href.lower():
                    notice_text = link.text.strip() or "Untitled Notice"
                    full_link = urljoin(site['url'], href)
                    valid_pdf_links.append((notice_text, full_link))
                    if len(valid_pdf_links) >= 3:
                        break

            if not valid_pdf_links:
                print(f"❌ {site['name']} par koi PDF link nahi mila.")
                continue

            for notice_text, pdf_link in valid_pdf_links:
                print(f"🎯 Notice mila: {notice_text}")
                
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                pdf_response = requests.get(pdf_link, headers=headers, verify=False, timeout=15)
                
                content_type = pdf_response.headers.get('Content-Type', '')
                if 'application/pdf' not in content_type:
                    print(f"⚠️ SKIPPED: Asli PDF nahi hai (Type: {content_type})")
                    continue
                
                file_name = "temp_notice.pdf"
                with open(file_name, "wb") as f:
                    f.write(pdf_response.content)
                    
                with pdfplumber.open(file_name) as pdf:
                    extracted_text = pdf.pages[0].extract_text() or ""
                
                os.remove(file_name)
                
                if not extracted_text.strip():
                    print("⚠️ SKIPPED: PDF khali hai.")
                    continue

                print("🧠 AI analysis chal raha hai...")
                prompt = f"""
                You are an expert Data Extractor for a Government Job Portal.
                Analyze this official notice text: {extracted_text}
                Respond STRICTLY in JSON format with these exact keys:
                {{"is_new_exam": boolean, "department": string, "notice_subject": string, "form_status": string, "start_date": string, "last_date": string, "exam_date": string}}
                """
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                
                ai_data = json.loads(response.text)
                
                if ai_data.get("is_new_exam") == True:
                    # CLOUD DATABASE CHECK (Duplicate check using Supabase)
                    check_dup = supabase.table("exams").select("*").eq("notice_subject", ai_data.get("notice_subject")).execute()
                    
                    if len(check_dup.data) == 0:
                        ai_data.pop("is_new_exam", None)
                        supabase.table("exams").insert(ai_data).execute()
                        print(f"💾 Cloud DB SUCCESS: [{ai_data.get('notice_subject')}] save ho gaya!")
                        break
                    else:
                        print("⏭️ SKIPPED: Yeh notice pehle se Cloud Database mein hai.")
                else:
                    print("⚠️ FILTERED: Yeh exam form ka notice nahi tha.")
                
        except Exception as e:
            print(f"❌ Error processing {site['name']}: {e}")

finally:
    driver.quit()
    print("\n✅ System successfully close ho gaya.")