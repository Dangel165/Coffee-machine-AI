import openai
import speech_recognition as sr
import RPi.GPIO as GPIO
import sqlite3
from datetime import datetime
import re
import time

# OpenAI API 키 설정
openai.api_key = "sk-여기에_당신의_API키_입력"

# GPIO 설정
HEATER_PIN = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(HEATER_PIN, GPIO.OUT)
GPIO.output(HEATER_PIN, GPIO.LOW)

recognizer = sr.Recognizer()

# DB 초기화
def init_db():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user_input TEXT,
        ai_response TEXT
    )''')
    conn.commit()
    conn.close()

# DB 저장
def save_to_db(user_input, ai_response):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("INSERT INTO chat (timestamp, user_input, ai_response) VALUES (?, ?, ?)",
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_input, ai_response))
    conn.commit()
    conn.close()

# 전체 대화 출력
def show_all_logs():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, user_input, ai_response FROM chat ORDER BY id")
    for row in c.fetchall():
        print(f"[{row[0]}]\n사용자: {row[1]}\nAI: {row[2]}\n{'-'*40}")
    conn.close()

# 키워드 검색
def search_by_keyword(keyword):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, user_input, ai_response FROM chat WHERE user_input LIKE ? OR ai_response LIKE ?", (f"%{keyword}%", f"%{keyword}%"))
    results = c.fetchall()
    if results:
        for row in results:
            print(f"[{row[0]}]\n사용자: {row[1]}\nAI: {row[2]}\n{'-'*40}")
    else:
        print(f"'{keyword}'에 대한 검색 결과가 없습니다.")
    conn.close()

# 날짜 범위 검색
def search_by_date_range(start, end):
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT timestamp, user_input, ai_response FROM chat WHERE timestamp BETWEEN ? AND ?", (start, end))
    results = c.fetchall()
    if results:
        for row in results:
            print(f"[{row[0]}]\n사용자: {row[1]}\nAI: {row[2]}\n{'-'*40}")
    else:
        print("해당 기간에 기록이 없습니다.")
    conn.close()

# 대화 요약
def summarize_chat():
    conn = sqlite3.connect("chat_history.db")
    c = conn.cursor()
    c.execute("SELECT user_input, ai_response FROM chat ORDER BY id")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("요약할 대화 기록이 없습니다.")
        return

    conversation = "\n".join([f"사용자: {u}\nAI: {a}" for u, a in rows])
    prompt = f"다음은 커피머신과의 대화입니다. 핵심 내용을 요약해 주세요:\n{conversation}"

    try:
        result = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = result.choices[0].message.content.strip()
        print("\n📋 대화 요약:\n" + summary)
    except Exception as e:
        print(f"[GPT 오류] {e}")

# 히터 제어
def heater_on():
    GPIO.output(HEATER_PIN, GPIO.HIGH)
    print("[기계] 히터 ON")

def heater_off():
    GPIO.output(HEATER_PIN, GPIO.LOW)
    print("[기계] 히터 OFF")

def control_temperature(command):
    match = re.search(r"(\d{2,3})\s*도", command)
    if match:
        temp = int(match.group(1))
        print(f"[명령] 온도를 {temp}도로 설정합니다.")
        if temp >= 70:
            heater_on()
        else:
            heater_off()
        return f"온도를 {temp}도로 설정했습니다."
    else:
        return "온도 정보를 찾을 수 없어요. 다시 말씀해 주세요."

# GPT 응답
def chat_with_gpt(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[GPT 오류] {e}"

# 음성 인식
def listen():
    try:
        with sr.Microphone() as source:
            print("🎤 말씀하세요...")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)
        text = recognizer.recognize_google(audio, language="ko-KR")
        print(f"사용자: {text}")
        return text
    except:
        return ""

# 대화 루프 (공통)
def chat_loop(use_voice=True):
    print("AI 커피머신에 오신 걸 환영합니다.")
    while True:
        user_input = listen() if use_voice else input("입력 > ")
        if not user_input:
            continue
        if "종료" in user_input or "그만" in user_input:
            print("종료합니다.")
            heater_off()
            GPIO.cleanup()
            break

        if "도" in user_input:
            response = control_temperature(user_input)
        else:
            response = chat_with_gpt(user_input)

        print(f"AI: {response}")
        save_to_db(user_input, response)

# 메뉴
def menu():
    init_db()
    while True:
        print("\n===== AI 음성 대화 시스템 =====", flush=True)
        print("1. 음성 대화 시작", flush=True)
        print("2. 전체 대화 기록 보기", flush=True)
        print("3. 키워드로 검색", flush=True)
        print("4. 날짜 범위로 검색", flush=True)
        print("5. 종료", flush=True)
        print("6. 대화 전체 요약 (GPT)", flush=True)
        print("7. 키보드 대화 시작", flush=True)

        choice = input("원하는 기능 선택 (1~7): ").strip()
        if choice == "1":
            chat_loop(use_voice=True)
        elif choice == "2":
            show_all_logs()
        elif choice == "3":
            keyword = input("검색할 키워드 입력: ")
            search_by_keyword(keyword)
        elif choice == "4":
            start = input("시작 (YYYY-MM-DD HH:MM:SS): ")
            end = input("종료 (YYYY-MM-DD HH:MM:SS): ")
            search_by_date_range(start, end)
        elif choice == "5":
            print("종료합니다.")
            GPIO.cleanup()
            break
        elif choice == "6":
            summarize_chat()
        elif choice == "7":
            chat_loop(use_voice=False)
        else:
            print("잘못된 입력입니다.")

# 실행
if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("프로그램 종료. GPIO 정리 중...")
        GPIO.cleanup()

