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

# SSL warnings ko ignore karne ke liye (Sarkari sites ke liye zaruri hai)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Env variables load karein
GROQ_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Groq aur Supabase clients initialize karein
groq_client = Groq(api_key=GROQ_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Anti-bot firewalls ko bypass karne ke liye mobile user-agent headers
STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

def is_relevant_notice(title, text=""):
    """Faltu notices ko filter karne ke liye key-word matcher"""
    keywords = ["recruitment", "vacancy", "apply", "online", "bharti", "exam", "post", "notification", "crp", "agniveer", "vayu", "navy", "army", "hiring", "officer", "jobs", "airforce"]
    combined_content = (title + " " + text).lower()
    return any(kw in combined_content for kw in keywords)

def get_existing_database_records():
    """AI Merge validation ke liye existing records fetch karna"""
    try:
        res = supabase.table("exams").select("id, notice_subject, department, last_date").execute()
        return res.data
    except Exception as e:
        print(f"⚠️ DB Fetch Error: {e}")
        return []

# ---- BROWSER ENGINE CONFIGURATION ----
if os.getenv("GITHUB_ACTIONS") == "true":
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    
    # Fast rendering ke liye images bypass
    options.add_argument("--blink-settings=imagesEnabled=false")
    
    # Automation footprint chhupane ke liye flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    
    # HTML load hote hi script execution trigger ho jaye
    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(options=options)
else:
    # Local development browser setup
    driver = webdriver.Safari()

# Quick cutoff time limits block hone se bachne ke liye
driver.set_page_load_timeout(20)

try:
    with open("sites.json", "r") as f:
        sites = json.load(f)
    all_sites_list = sites["central_jobs"] + sites["state_jobs"]

    for site in all_sites_list:
        print(f"\n🌍 Checking {site['name']}...")
        html_content = None
        
        # 🚀 ENGINE 1: Selenium Navigation
        try:
            driver.get(site['url'])
            time.sleep(4) 
            html_content = driver.page_source
        except Exception as se:
            # 🔄 ENGINE 2: Stealth HTTP Fallback (UPSC, Defense sites bypass)
            print(f"⚠️ Selenium timeout for {site['name']}. Triggering Stealth HTTP Fallback...")
            try:
                res = requests.get(site['url'], headers=STEALTH_HEADERS, verify=False, timeout=15)
                if res.status_code == 200:
                    html_content = res.text
                    print(f"✅ Stealth Fallback Successful for {site['name']}!")
            except Exception as re:
                print(f"❌ Both Selenium and HTTP Fallback failed for {site['name']}: {re}")
        
        if not html_content:
            print(f"⏭️ Skipping {site['name']} due to connection failure.")
            continue

        soup = BeautifulSoup(html_content, "html.parser")
        extracted_texts_to_analyze = []

        # ---- CASE 1: SARKARI RESULT AGGREGATOR (DEEP TRACKING) ----
        if "sarkariresult.com" in site['url'].lower():
            print("🎯 Sarkari Result sub-directories scan ho rahe hain...")
            job_links = []
            for link in soup.find_all("a", href=True):
                href = link['href'].lower()
                text = link.text.strip()
                
                # Sabhi dynamic sub-paths ko capture karein (Agniveer, Navy, Banks, etc.)
                if any(x in href for x in ["/latestjob/", "/force/", "/ssc/", "/upsc/", "/bank/", "/airforce/", "/navy/", "/army/"]) or "recruitment" in href or "agniveer" in href:
                    if is_relevant_notice(text):
                        full_job_url = urljoin(site['url'], link['href'])
                        if full_job_url not in [j[1] for j in job_links]:
                            job_links.append((text, full_job_url))
            
            # 🔥 TOP 15 LATEST NOTIFICATIONS DEEP CHECK (FIXED SYNTAX)
            for title, j_url in job_links[:15]:
                print(f"🔗 Crawling Deep Job Page: {title}")
                try:
                    res = requests.get(j_url, headers=STEALTH_HEADERS, verify=False, timeout=10)
                    j_soup = BeautifulSoup(res.text, "html.parser")
                    page_text = j_soup.get_text(separator=' ', strip=True)
                    extracted_texts_to_analyze.append({"source": title, "text": page_text[:3500]})
                except Exception as je:
                    print(f"⚠️ Skipping slow aggregator page: {title}")

        # ---- CASE 2: OFFICIAL DIRECT PORTALS (PDF BASED) ----
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
                print(f"📄 Downloading PDF Notice: {title}")
                try:
                    res = requests.get(pdf_link, headers=STEALTH_HEADERS, verify=False, timeout=12)
                    if 'application/pdf' in res.headers.get('Content-Type', ''):
                        with open("temp.pdf", "wb") as f:
                            f.write(res.content)
                        with pdfplumber.open("temp.pdf") as pdf:
                            pdf_text = pdf.pages
