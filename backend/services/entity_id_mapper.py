"""
Entity ID Mapper
PoC ID ↔ DB supplier_code 양방향 변환 및 엔티티 이름 정규화
"""
from typing import Optional
import re

# PoC ID → DB supplier_code 매핑
# frontend/lib/entities.ts의 12개 거점과 DB supplier_code 매핑
POC_TO_DB = {
    'tsmc': 'TW0001',              # TSMC (대만)
    'asml': 'SUP_ASML',            # ASML (네덜란드)
    'shinetsu': 'JP0201',          # Shin-Etsu Chemical (일본)
    'sumco': 'JP0202',             # SUMCO (일본)
    'jsr': 'JP0003',               # JSR Corporation (일본)
    'tel': 'JP0203',               # Tokyo Electron (일본)
    'amat': 'SUP_AMAT',            # Applied Materials (미국)
    'entegris': 'US0003',          # Entegris (미국)
    'merck': 'DE0001',             # Merck Electronics (독일)
    'neon-ua': 'UA0001',           # 우크라이나 네온가스
    'hoya': 'JP0204',              # HOYA (일본)
    'samsung-giheung': 'KR0101',   # 삼성 기흥 (한국)
}

# DB supplier_code → PoC ID 역방향 매핑
DB_TO_POC = {v: k for k, v in POC_TO_DB.items()}

# 엔티티 이름 정규화 매핑 (NEWS_ENTITY_EXTRACTION.matched_kg_entity → PoC ID)
# 대소문자, 공백, 한글명 변형 등을 모두 포함
ENTITY_NAME_TO_POC = {
    # TSMC 변형
    'tsmc': 'tsmc',
    'TSMC': 'tsmc',
    '대만 tsmc': 'tsmc',
    '대만tsmc': 'tsmc',
    'taiwan tsmc': 'tsmc',

    # ASML 변형
    'asml': 'asml',
    'ASML': 'asml',
    '네덜란드 asml': 'asml',
    'netherlands asml': 'asml',

    # Shin-Etsu 변형
    'shinetsu': 'shinetsu',
    'shin-etsu': 'shinetsu',
    'shin etsu': 'shinetsu',
    '신에츠': 'shinetsu',
    '신에츠화학': 'shinetsu',
    '신에쓰화학': 'shinetsu',
    '신에쓰화학코리아': 'shinetsu',

    # SUMCO
    'sumco': 'sumco',
    'SUMCO': 'sumco',
    '섬코': 'sumco',

    # JSR
    'jsr': 'jsr',
    'JSR': 'jsr',
    'jsr corporation': 'jsr',
    'jsr코퍼레이션': 'jsr',

    # Tokyo Electron
    'tel': 'tel',
    'TEL': 'tel',
    'tokyo electron': 'tel',
    '도쿄일렉트론': 'tel',

    # Applied Materials
    'amat': 'amat',
    'AMAT': 'amat',
    'applied materials': 'amat',
    '어플라이드': 'amat',
    '어플라이드 머티어리얼즈': 'amat',

    # Entegris
    'entegris': 'entegris',
    'ENTEGRIS': 'entegris',
    '엔테그리스': 'entegris',
    '엔테그리스(entegris)': 'entegris',

    # Merck
    'merck': 'merck',
    'MERCK': 'merck',
    'merck electronics': 'merck',
    '머크': 'merck',
    '머크kgaa': 'merck',
    '머크kgaa (반도체소재)': 'merck',

    # 네온가스 (우크라이나)
    'neon': 'neon-ua',
    'neon-ua': 'neon-ua',
    '네온': 'neon-ua',
    '네온가스': 'neon-ua',
    'iceblick': 'neon-ua',
    'cryoin': 'neon-ua',
    '우크라이나': 'neon-ua',

    # HOYA
    'hoya': 'hoya',
    'HOYA': 'hoya',
    '호야': 'hoya',

    # 삼성 기흥
    'samsung': 'samsung-giheung',
    '삼성': 'samsung-giheung',
    '삼성전자': 'samsung-giheung',
    'samsung electronics': 'samsung-giheung',
    'samsung giheung': 'samsung-giheung',
    'samsung-giheung': 'samsung-giheung',
    '기흥': 'samsung-giheung',
    'giheung': 'samsung-giheung',

    # SK하이닉스 (매핑되는 PoC 엔티티 없음 - 추가 협의 필요, 일단 TSMC로 임시 매핑)
    'sk하이닉스': None,
    'sk hynix': None,
    'hynix': None,
}


def normalize_entity_name(raw_name: str) -> Optional[str]:
    """
    NEWS_ENTITY_EXTRACTION.matched_kg_entity를 PoC ID로 정규화

    Args:
        raw_name: 뉴스에서 추출된 원본 엔티티 이름

    Returns:
        정규화된 PoC ID (매핑 없으면 None)
    """
    if not raw_name:
        return None

    # 1. 직접 매핑 시도 (대소문자 무시)
    normalized_input = raw_name.strip().lower()
    if normalized_input in ENTITY_NAME_TO_POC:
        return ENTITY_NAME_TO_POC[normalized_input]

    # 2. 공백/특수문자 제거 후 재시도
    clean_name = re.sub(r'[^\w가-힣]', '', normalized_input)
    if clean_name in ENTITY_NAME_TO_POC:
        return ENTITY_NAME_TO_POC[clean_name]

    # 3. 부분 문자열 매칭 (키워드 포함 여부)
    for key, poc_id in ENTITY_NAME_TO_POC.items():
        if key in normalized_input or normalized_input in key:
            return poc_id

    # 매핑 실패
    return None


def poc_to_db_id(poc_id: str) -> Optional[str]:
    """
    PoC ID → DB supplier_code 변환

    Args:
        poc_id: Frontend에서 사용하는 짧은 ID ('tsmc', 'asml' 등)

    Returns:
        DB의 supplier_code ('TW0001' 등) 또는 None
    """
    return POC_TO_DB.get(poc_id)


def db_to_poc_id(db_id: str) -> Optional[str]:
    """
    DB supplier_code → PoC ID 변환

    Args:
        db_id: DB의 supplier_code ('KR0001', 'TW0001' 등)

    Returns:
        PoC ID ('tsmc', 'asml' 등) 또는 None
    """
    return DB_TO_POC.get(db_id)


# 테스트용 함수
if __name__ == '__main__':
    # 정규화 테스트
    test_cases = [
        'TSMC',
        'asml',
        '대만 TSMC',
        '네덜란드 ASML',
        'tokyo electron',
        '삼성',
        '네온가스',
        'Applied Materials',
    ]

    print("=== Entity Name Normalization Test ===")
    for test in test_cases:
        result = normalize_entity_name(test)
        print(f"{test:30s} → {result}")

    print("\n=== PoC ↔ DB Mapping Test ===")
    print(f"{'tsmc':20s} → DB: {poc_to_db_id('tsmc')}")
    print(f"{'TW0001':20s} → PoC: {db_to_poc_id('TW0001')}")
    print(f"{'samsung-giheung':20s} → DB: {poc_to_db_id('samsung-giheung')}")
    print(f"{'KR0001':20s} → PoC: {db_to_poc_id('KR0001')}")
