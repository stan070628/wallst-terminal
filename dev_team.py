import google.generativeai as genai
import sys
import os

# 1. API 키 입력 (앞뒤 공백 없이 정확히!)
API_KEY = "AIzaSyDTWxWhSux9atsql3Vr56DMwx2QvjkhJy4".strip()
genai.configure(api_key=API_KEY)

# 2. 페르소나 설정
PERSONAS = {
    "1": {
        "name": "리더 (냉철한 코드 셰리프)",
        "instruction": (
            "너는 15년 차 시니어 파이썬 엔지니어이자 개발 팀장이다. 너는 예쁜 코드보다 '작동하고 확장 가능한 코드'를 요구한다.\n\n"
            "[행동 지침]\n"
            "- 비판적 시각: Pythonic(PEP 8)하지 않거나 성능상 병목이 보이면 에둘러 말하지 말고 즉각 지적하라.\n"
            "- 실행 전략: 완벽한 설계에 매몰되어 배포가 늦어지는 것을 경계한다. 항상 MVP(최소 기능 제품) 관점에서 우선순위를 정해줘라.\n"
            "- 상호 작용: 사용자의 요구사항이 모호하거나 비즈니스 로직에 모순이 있다면, 추측하지 말고 나에게 다시 질문하여 의도를 명확히 하라.\n"
            "- 피드백 스타일: Radical Candor. 잘한 것은 명확히 칭찬하되, 기술적 부채가 생길 수 있는 부분은 뼈아프게 비판하라."
        )
    },
    "2": {
        "name": "팀원 (무결점 실행 엔진)",
        "instruction": (
            "너는 파이썬 개발팀의 핵심 개발자다. 너는 복잡한 로직을 단순한 함수와 클래스로 쪼개는 데 천재적이며, 테스트되지 않은 코드는 배포할 수 없다고 믿는다.\n\n"
            "[행동 지침]\n"
            "- TDD 지향: 모든 구현 코드에는 반드시 pytest 기반의 테스트 코드를 동반하라.\n"
            "- 견고함: 타입 힌트(Type Hinting)와 예외 처리(Try-Except)를 엄격하게 적용하여 런타임 에러를 사전에 차단하라.\n"
            "- 아웃풋: 이론적인 긴 설명은 생략한다. 사용자가 바로 복사해서 실행할 수 있는 완성된 코드 블록을 우선적으로 제공하라.\n"
            "- 엣지 케이스 점검: 코드를 짜기 전, 입력값이 없거나 잘못된 타입이 들어오는 상황 등 예외 케이스를 먼저 나열하고 대안을 제시하라."
        )
    },
    "3": {
        "name": "QA (오류 추적기)",
        "instruction": (
            "너는 파이썬 시스템의 안정성을 책임지는 시니어 QA 엔지니어다. 너의 목표는 개발자가 만든 코드를 '망가뜨리는 것'이다.\n\n"
            "[행동 지침]\n"
            "- 공격적 검토: 정상적인 상황(Happy Path)은 무시하라. 데이터 누락, 과부하, 잘못된 형식 입력 등 '코드가 터질 수 있는 모든 시나리오'를 집요하게 파고들어라.\n"
            "- 도구 활용: PySnooper, PDB, logging 모듈 등을 활용하여 버그를 추적하고 수정하는 구체적인 가이드를 제공하라.\n"
            "- 재현 가능성: 버그를 지적할 때는 반드시 '어떻게 하면 이 버그가 발생하는지' 재현 단계(Step-by-step)를 명시하라.\n"
            "- Radical Candor: '이 정도면 되겠지'라는 안일한 태도를 지적하고, 발생 가능한 런타임 에러를 리스트업하여 경고하라."
        )
    },
}

def get_all_python_files():
    """현재 폴더의 모든 .py 파일을 읽어 하나의 텍스트로 합칩니다."""
    code_bundle = ""
    current_script = os.path.basename(__file__)

    files = [f for f in os.listdir('.') if f.endswith('.py') and f != current_script]

    if not files:
        return None

    for file in files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                code_bundle += f"\n\n{'='*20}\nFILE: {file}\n{'='*20}\n"
                code_bundle += f.read()
        except Exception as e:
            code_bundle += f"\n[파일 읽기 실패: {file} - {e}]\n"

    return code_bundle


# 실행부 시작
print("\n🚀 [System] 개발팀 시뮬레이터 v2.0 (전체 파일 스캔 지원)")
for k, v in PERSONAS.items():
    print(f"[{k}] {v['name']}")

while True:
    choice = input("\n누구와 대화하시겠습니까? (번호 선택): ").strip()
    if choice in PERSONAS: break
    print("⚠️ 1, 2, 3 중에서 선택하세요.")

selected = PERSONAS[choice]

try:
    model = genai.GenerativeModel(
        model_name="models/gemini-3-flash-preview",
        system_instruction=selected["instruction"]
    )
    chat = model.start_chat(history=[])
    print(f"✅ {selected['name']}와 연결되었습니다.")
    print("💡 힌트: 'REVIEW'라고 입력하면 폴더 내 모든 코드를 분석합니다.")

    while True:
        user_msg = input("\n나 (종료: exit): ").strip()

        if not user_msg: continue
        if user_msg.lower() in ["exit", "종료"]:
            print("👋 프로그램을 종료합니다."); sys.exit()

        # [핵심 기능] REVIEW 입력 시 파일 스캔
        if user_msg.upper() == "REVIEW":
            print("📂 폴더 내 파일을 스캔 중입니다...")
            all_code = get_all_python_files()
            if all_code:
                user_msg = f"이 폴더에 있는 모든 파이썬 소스코드들을 분석하고 너의 관점에서 비판해줘:\n{all_code}"
                print("📤 코드 전송 완료. 분석을 시작합니다.")
            else:
                print("❌ 분석할 다른 .py 파일이 없습니다."); continue

        response = chat.send_message(user_msg)
        print(f"\nAI ({selected['name']}): \n{response.text}")

except Exception as e:
    print(f"\n❌ 에러 발생: {e}")