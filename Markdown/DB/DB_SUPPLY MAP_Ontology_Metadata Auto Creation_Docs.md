# 온톨로지 메타데이터 자동 생성 가이드

## 1. 개요

### 1.1 목적

공급망 DB (`supply_chain.db`)의 구조를 분석하여 온톨로지 레이어의 메타데이터를 자동으로 생성합니다.

### 1.2 자동 생성 범위

| 메타데이터 | 자동 생성 | 수동 보정 필요 | 비고 |
|-----------|----------|--------------|------|
| 테이블 기본 정보 | ✅ | ❌ | table_name, table_type |
| 컬럼 기본 정보 | ✅ | ❌ | column_name, data_type, is_nullable |
| FK 관계 | ✅ | ❌ | 자동 추출 |
| semantic_type | ✅ | ⚠️ | 추론 규칙 기반, 확인 권장 |
| 테이블 설명 | ⚠️ | ✅ | 템플릿 기반, 수동 보정 필수 |
| 컬럼 설명 | ⚠️ | ✅ | 템플릿 기반, 수동 보정 필수 |
| search_operator | ✅ | ⚠️ | semantic_type 기반 추론 |
| sample_values | ✅ | ❌ | 실제 데이터에서 샘플 추출 |

---

## 2. 자동 생성 대상

### 2.1 DB_TABLE_METADATA

**자동 생성 가능 컬럼**:
- `table_id`: `TBL_{table_name}` 형식
- `table_name`: `PRAGMA table_list` 에서 추출
- `table_type`: 테이블명 패턴으로 추론
  - `_MAP` 또는 `_MAPPING`으로 끝나면 → `"MAPPING"`
  - 나머지 → `"MASTER"`
- `primary_entity_type`: 테이블명으로 추론
  - `SUPPLIER` 포함 → `"SUPPLIER"`
  - `SITE` 포함 → `"SITE"`
  - `MATERIAL` 포함 → `"MATERIAL"`
  - `RAW_MATERIAL` 또는 `SUBSTANCE` 포함 → `"RAW_MATERIAL"`
  - 매핑 테이블 → `null`
- `estimated_row_count`: `SELECT COUNT(*) FROM {table}` 실행
- `has_soft_delete`: `is_active` 컬럼 존재 여부

**템플릿 기반 생성 (수동 보정 권장)**:
- `llm_description`: 테이블명 기반 템플릿
- `typical_join_path`: FK 관계 분석으로 자동 생성

**수동 입력 필요**:
- `search_priority`: 도메인 지식 필요 (기본값 3)

---

### 2.2 DB_COLUMN_METADATA

**자동 생성 가능 컬럼**:
- `column_id`: `COL_{table_name}_{column_name}` 형식
- `column_name`: `PRAGMA table_info()` 에서 추출
- `data_type`: `PRAGMA table_info()` 에서 추출
- `is_nullable`: `PRAGMA table_info()` 의 notnull 필드 반전
- `is_primary_key`: `PRAGMA table_info()` 의 pk 필드
- `is_foreign_key`: `PRAGMA foreign_key_list()` 에서 확인
- `references_table`, `references_column`: FK인 경우 자동 추출
- `semantic_type`: 컬럼명 패턴으로 추론 (아래 규칙 참조)
- `search_operator`: semantic_type 기반 추론
- `sample_values`: 실제 데이터에서 `SELECT DISTINCT {column} LIMIT 5` 추출
- `value_count_estimate`: `SELECT COUNT(DISTINCT {column})` 실행

**템플릿 기반 생성 (수동 보정 권장)**:
- `llm_description`: 컬럼명 + semantic_type 기반 템플릿
- `search_hint`: semantic_type 기반 템플릿

**수동 입력 필요**:
- `is_searchable`, `is_filterable`: 기본값 활용 가능

---

### 2.3 DB_TABLE_RELATIONSHIP

**자동 생성 가능**:
- `relationship_id`: `REL_{from_table}_{to_table}` 형식
- `from_table`, `to_table`: FK 관계에서 추출
- `join_condition`: FK 정보로 자동 생성
  - 예: `SITE_MASTER.supplier_code = SUPPLIER_MASTER.supplier_code`
- `relationship_type`: 카디널리티 추론
  - `1:N`: FK가 있는 쪽이 N
  - `N:M`: 매핑 테이블 패턴 감지
- `is_indexed`: FK 컬럼에 인덱스 존재 여부 확인
- `avg_cardinality`: 실제 데이터로 계산
  - 예: `COUNT(child) / COUNT(DISTINCT parent)` → "1:2.3" 형식

**템플릿 기반 생성 (수동 보정 권장)**:
- `llm_join_hint`: 테이블명 기반 템플릿
- `typical_use_case`: 관계 패턴 기반 템플릿

---

## 3. 자동 생성 규칙

### 3.1 semantic_type 추론 규칙

```python
def infer_semantic_type(column_name: str, data_type: str) -> str:
    """
    컬럼명과 데이터 타입으로 semantic_type 추론
    """
    col_lower = column_name.lower()
    
    # 1. 엔티티 코드 (PK/FK)
    if 'code' in col_lower and data_type == 'TEXT':
        return 'ENTITY_CODE'
    
    # 2. 엔티티 명칭
    if 'name' in col_lower and data_type == 'TEXT':
        return 'ENTITY_NAME'
    
    # 3. 위치 정보
    if col_lower in ['country', 'region', 'address']:
        return 'LOCATION'
    
    # 4. 분류/유형
    if '_type' in col_lower or 'category' in col_lower:
        return 'TYPE_CATEGORY'
    
    # 5. 수량/비율
    if any(x in col_lower for x in ['ratio', 'count', 'quantity', 'amount']):
        return 'QUANTITY'
    
    # 6. 불린 플래그
    if col_lower.startswith('is_') or col_lower.startswith('has_'):
        return 'FLAG'
    
    # 7. 좌표
    if col_lower in ['latitude', 'longitude', 'lat', 'lon']:
        return 'COORDINATE'
    
    # 8. 타임스탬프
    if col_lower.endswith('_at') or col_lower in ['created', 'updated']:
        return 'TIMESTAMP'
    
    # 9. 기타
    return None
```

**적용 예시**:
| column_name | data_type | semantic_type |
|-------------|-----------|---------------|
| supplier_code | TEXT | ENTITY_CODE |
| name_kor | TEXT | ENTITY_NAME |
| country | TEXT | LOCATION |
| raw_material_type | TEXT | TYPE_CATEGORY |
| supply_ratio | REAL | QUANTITY |
| is_active | INTEGER | FLAG |
| latitude | REAL | COORDINATE |
| created_at | TEXT | TIMESTAMP |

---

### 3.2 search_operator 추론 규칙

```python
def infer_search_operator(semantic_type: str, data_type: str) -> str:
    """
    semantic_type과 data_type으로 search_operator 추론
    """
    if semantic_type == 'ENTITY_CODE':
        return '='  # 정확 매칭
    
    elif semantic_type == 'ENTITY_NAME':
        return 'LIKE'  # 부분 매칭
    
    elif semantic_type == 'LOCATION':
        return '='  # 정확 매칭 (국가/지역명)
    
    elif semantic_type == 'TYPE_CATEGORY':
        return '='  # 정확 매칭
    
    elif semantic_type == 'QUANTITY':
        return '>='  # 범위 검색
    
    elif semantic_type == 'FLAG':
        return '='  # 0 또는 1
    
    elif semantic_type == 'COORDINATE':
        return 'BETWEEN'  # 범위 검색
    
    elif semantic_type == 'TIMESTAMP':
        return '>='  # 날짜 범위 검색
    
    else:
        # 기본값: TEXT는 LIKE, 나머지는 =
        return 'LIKE' if data_type == 'TEXT' else '='
```

---

### 3.3 llm_description 템플릿

#### 테이블 설명 템플릿

```python
TABLE_DESCRIPTION_TEMPLATES = {
    'SUPPLIER_MASTER': (
        '{table}는 협력사(법인) 기본 정보를 관리하는 마스터 테이블입니다. '
        '협력사명, 국가, 지역, 좌표 등의 정보를 포함합니다. '
        '협력사의 생산 거점은 SITE_MASTER 테이블에서 관리됩니다.'
    ),
    
    'SITE_MASTER': (
        '{table}는 생산 거점(Site, Plant, 창고 등) 정보를 관리하는 마스터 테이블입니다. '
        '각 협력사는 1~3개의 생산지를 가질 수 있습니다. '
        '생산지에서 생산하는 자재는 SITE_MATERIAL_MAP을 통해 확인할 수 있습니다.'
    ),
    
    'MATERIAL_MASTER': (
        '{table}는 반도체 제조에 사용되는 자재 정보를 관리하는 마스터 테이블입니다. '
        '자재에 포함된 소재는 MATERIAL_RAW_MATERIAL_MAP을 통해 확인할 수 있습니다.'
    ),
    
    'RAW_MATERIAL_MASTER': (
        '{table}는 원소재(원소, 가스, 금속, 화합물 등) 정보를 관리하는 마스터 테이블입니다. '
        '이 소재를 포함하는 자재는 MATERIAL_RAW_MATERIAL_MAP을 통해 역추적할 수 있습니다.'
    ),
    
    'SITE_MATERIAL_MAP': (
        '{table}는 생산지(Site)와 자재(Material)의 N:M 관계를 관리하는 매핑 테이블입니다. '
        '어느 생산지에서 어떤 자재를 공급하는지, 공급 비중은 얼마인지 저장합니다. '
        '동일 자재를 여러 생산지에서 생산하는 케이스가 30% 이상 포함됩니다.'
    ),
    
    'MATERIAL_RAW_MATERIAL_MAP': (
        '{table}는 자재(Material)와 소재(Raw Material)의 N:M 관계를 관리하는 매핑 테이블입니다. '
        '어느 자재가 어떤 소재를 포함하는지, 포함 비중은 얼마인지 저장합니다.'
    ),
    
    'SUPPLIER_RAW_MATERIAL_MAP': (
        '{table}는 협력사(Supplier)와 소재(Raw Material)의 N:M 관계를 관리하는 매핑 테이블입니다. '
        '어느 협력사가 어떤 소재를 공급하는지 저장합니다.'
    ),
}
```

#### 컬럼 설명 템플릿

```python
COLUMN_DESCRIPTION_TEMPLATES = {
    'ENTITY_CODE': (
        '{column}은(는) {entity}의 고유 식별 코드입니다. '
        '{pk_or_fk} WHERE 절에서 정확 매칭(=)으로 사용합니다.'
    ),
    
    'ENTITY_NAME': (
        '{column}은(는) {entity}의 명칭입니다. '
        '뉴스에서 추출된 키워드로 검색할 때 LIKE 연산자로 부분 매칭을 권장합니다.'
    ),
    
    'LOCATION': (
        '{column}은(는) {entity}의 위치 정보입니다. '
        '국가/지역명으로 필터링할 때 사용합니다. 정확 매칭(=) 또는 IN 연산자를 사용하세요.'
    ),
    
    'TYPE_CATEGORY': (
        '{column}은(는) {entity}의 분류/유형입니다. '
        '동일 유형의 엔티티를 그룹화할 때 사용합니다. WHERE 또는 GROUP BY 절에서 활용하세요.'
    ),
    
    'QUANTITY': (
        '{column}은(는) {meaning}입니다. '
        '수치 범위로 필터링하거나 정렬(ORDER BY)에 사용할 수 있습니다.'
    ),
    
    'FLAG': (
        '{column}은(는) {meaning} 여부를 나타내는 불린 플래그입니다. '
        '0(거짓) 또는 1(참) 값을 가지며, WHERE 절에서 = 연산자로 필터링합니다.'
    ),
}
```

---

## 4. 자동 생성 프로세스

### 4.1 전체 흐름

```
[Step 1] supply_chain.db 연결 및 분석
  ├─ 테이블 목록 추출
  ├─ 각 테이블의 컬럼 정보 추출
  └─ FK 관계 추출

[Step 2] ontology_layer.db 생성 및 연결
  ├─ ATTACH supply_chain.db
  └─ 온톨로지 테이블 생성 (create_ontology_layer.py)

[Step 3] DB_TABLE_METADATA 자동 생성
  ├─ 테이블별 메타데이터 생성
  ├─ 템플릿으로 llm_description 생성
  └─ INSERT INTO DB_TABLE_METADATA

[Step 4] DB_COLUMN_METADATA 자동 생성
  ├─ 컬럼별 메타데이터 생성
  ├─ semantic_type 추론
  ├─ search_operator 추론
  ├─ sample_values 추출
  └─ INSERT INTO DB_COLUMN_METADATA

[Step 5] DB_TABLE_RELATIONSHIP 자동 생성
  ├─ FK 관계 분석
  ├─ join_condition 생성
  ├─ avg_cardinality 계산
  └─ INSERT INTO DB_TABLE_RELATIONSHIP

[Step 6] V_ENTITY_HIERARCHY 뷰 생성
  └─ CREATE VIEW (supply_chain.db 참조)

[Step 7] 검증
  ├─ 레코드 수 확인
  ├─ FK 무결성 검증
  └─ llm_description 샘플 확인
```

### 4.2 스크립트 구조

```python
# populate_metadata.py

import sqlite3
from pathlib import Path
from typing import List, Dict

class MetadataGenerator:
    def __init__(self, supply_chain_db_path: str, ontology_db_path: str):
        self.supply_chain_db = supply_chain_db_path
        self.ontology_db = ontology_db_path
        
    def run(self):
        """메타데이터 자동 생성 실행"""
        print('[Step 1] supply_chain.db 분석...')
        tables = self.extract_tables()
        columns = self.extract_columns(tables)
        fks = self.extract_foreign_keys(tables)
        
        print('[Step 2] ontology_layer.db 연결...')
        conn = self.connect_ontology_db()
        
        print('[Step 3] DB_TABLE_METADATA 생성...')
        self.populate_table_metadata(conn, tables)
        
        print('[Step 4] DB_COLUMN_METADATA 생성...')
        self.populate_column_metadata(conn, columns, fks)
        
        print('[Step 5] DB_TABLE_RELATIONSHIP 생성...')
        self.populate_relationships(conn, fks)
        
        print('[Step 6] V_ENTITY_HIERARCHY 뷰 생성...')
        self.create_hierarchy_view(conn)
        
        print('[Step 7] 검증...')
        self.validate(conn)
        
        conn.close()
        print('완료!')
    
    def extract_tables(self) -> List[str]:
        """테이블 목록 추출"""
        conn = sqlite3.connect(self.supply_chain_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return tables
    
    def extract_columns(self, tables: List[str]) -> Dict[str, List[Dict]]:
        """각 테이블의 컬럼 정보 추출"""
        conn = sqlite3.connect(self.supply_chain_db)
        cursor = conn.cursor()
        
        columns = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = cursor.fetchall()
            
            columns[table] = [
                {
                    'name': col[1],
                    'type': col[2],
                    'notnull': col[3],
                    'default_value': col[4],
                    'pk': col[5]
                }
                for col in cols
            ]
        
        conn.close()
        return columns
    
    def extract_foreign_keys(self, tables: List[str]) -> Dict[str, List[Dict]]:
        """FK 관계 추출"""
        conn = sqlite3.connect(self.supply_chain_db)
        cursor = conn.cursor()
        
        fks = {}
        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fk_list = cursor.fetchall()
            
            fks[table] = [
                {
                    'from_column': fk[3],
                    'to_table': fk[2],
                    'to_column': fk[4]
                }
                for fk in fk_list
            ]
        
        conn.close()
        return fks
    
    def populate_table_metadata(self, conn: sqlite3.Connection, tables: List[str]):
        """DB_TABLE_METADATA 생성"""
        cursor = conn.cursor()
        
        for table in tables:
            table_id = f'TBL_{table}'
            table_type = self.infer_table_type(table)
            primary_entity_type = self.infer_entity_type(table)
            llm_description = self.generate_table_description(table)
            
            # 레코드 수 계산
            sc_cursor = sqlite3.connect(self.supply_chain_db).cursor()
            count = sc_cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            
            # is_active 컬럼 존재 여부
            columns = sc_cursor.execute(f"PRAGMA table_info({table})").fetchall()
            has_soft_delete = any(col[1] == 'is_active' for col in columns)
            
            cursor.execute("""
                INSERT INTO DB_TABLE_METADATA (
                    table_id, table_name, table_type, llm_description,
                    primary_entity_type, estimated_row_count, has_soft_delete
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (table_id, table, table_type, llm_description, 
                  primary_entity_type, count, int(has_soft_delete)))
        
        conn.commit()
    
    def infer_table_type(self, table_name: str) -> str:
        """테이블 유형 추론"""
        if '_MAP' in table_name or '_MAPPING' in table_name:
            return 'MAPPING'
        return 'MASTER'
    
    def infer_entity_type(self, table_name: str) -> str:
        """엔티티 유형 추론"""
        if 'SUPPLIER' in table_name:
            return 'SUPPLIER'
        elif 'SITE' in table_name:
            return 'SITE'
        elif 'RAW_MATERIAL' in table_name or 'SUBSTANCE' in table_name:
            return 'RAW_MATERIAL'
        elif 'MATERIAL' in table_name:
            return 'MATERIAL'
        else:
            return None
    
    def generate_table_description(self, table_name: str) -> str:
        """테이블 설명 생성"""
        return TABLE_DESCRIPTION_TEMPLATES.get(
            table_name, 
            f'{table_name}는 공급망 데이터를 관리하는 테이블입니다.'
        )
    
    # ... 나머지 메서드들 ...
```

---

## 5. 샘플 값 추출 전략

### 5.1 추출 규칙

```python
def extract_sample_values(table: str, column: str, semantic_type: str, max_samples: int = 5):
    """
    실제 데이터에서 샘플 값 추출
    """
    conn = sqlite3.connect(supply_chain_db)
    cursor = conn.cursor()
    
    # semantic_type에 따라 다른 추출 전략
    if semantic_type == 'ENTITY_NAME':
        # 엔티티명: 다양한 샘플 추출
        query = f"""
            SELECT DISTINCT {column} 
            FROM {table} 
            WHERE {column} IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {max_samples}
        """
    
    elif semantic_type == 'TYPE_CATEGORY':
        # 카테고리: 모든 유형 추출
        query = f"""
            SELECT DISTINCT {column} 
            FROM {table} 
            WHERE {column} IS NOT NULL
            ORDER BY {column}
        """
    
    elif semantic_type == 'LOCATION':
        # 위치: 빈도 높은 순
        query = f"""
            SELECT {column}, COUNT(*) as cnt
            FROM {table} 
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY cnt DESC
            LIMIT {max_samples}
        """
    
    else:
        # 기본: 무작위 샘플
        query = f"""
            SELECT DISTINCT {column} 
            FROM {table} 
            WHERE {column} IS NOT NULL
            LIMIT {max_samples}
        """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # JSON 배열 형식으로 반환
    if semantic_type == 'LOCATION':
        samples = [row[0] for row in rows]  # cnt 제외
    else:
        samples = [row[0] for row in rows]
    
    conn.close()
    
    return json.dumps(samples, ensure_ascii=False)
```

---

## 6. TAG_SEARCH_STRATEGY_MAP 자동 생성 (신규 추가)

### 6.1 목적

Agent_2 출력에 등장하는 모든 태그에 대해 **자동으로 전략 매핑을 생성**하여 Fallback 전략 사용을 최소화합니다.

### 6.2 자동 생성 규칙

#### 태그 타입 패턴 기반 매핑

```python
def auto_generate_tag_strategy_mappings(agent2_output_path: str, ontology_db_path: str):
    """
    Agent_2 출력에서 태그를 추출하여 자동으로 TAG_SEARCH_STRATEGY_MAP 생성
    """
    # 1. Agent_2 출력에서 고유 태그 추출
    with open(agent2_output_path, 'r', encoding='utf-8') as f:
        agent2_data = json.load(f)
    
    all_tags = []
    for article in agent2_data.get('results', []):
        all_tags.extend(article.get('mapped_tags', []))
    
    unique_tags = list({tag['tag_id']: tag for tag in all_tags}.values())
    
    # 2. 태그 타입별 전략 매핑 규칙
    TAG_TYPE_STRATEGY_MAP = {
        # 원자재 태그
        'RAW_*': [
            {
                'strategy_id': 'STRAT_RAW_MATERIAL_SITE_IMPACT',
                'priority': 1,
                'condition': '원자재 태그는 생산지 영향 분석 우선'
            },
            {
                'strategy_id': 'STRAT_RAW_MATERIAL_FULL_CHAIN',
                'priority': 2,
                'condition': '전체 공급망 추적 (2차 전략)'
            }
        ],
        
        # 자재 태그
        'MAT_*': [
            {
                'strategy_id': 'STRAT_MATERIAL_SITE_TRACE',
                'priority': 1,
                'condition': '자재 태그는 생산지 추적 우선'
            },
            {
                'strategy_id': 'STRAT_MATERIAL_COMPOSITION',
                'priority': 2,
                'condition': '자재 구성 분석 (2차 전략)'
            }
        ],
        
        # 협력사 태그
        'SUP_*': [
            {
                'strategy_id': 'STRAT_SUPPLIER_SITE_LIST',
                'priority': 1,
                'condition': '협력사 태그는 생산지 조회 우선'
            },
            {
                'strategy_id': 'STRAT_SUPPLIER_RAW_MATERIAL_LIST',
                'priority': 2,
                'condition': '협력사 원자재 공급 현황 (2차 전략)'
            }
        ],
        
        # 생산지/국가 태그
        'SITE_*': [
            {
                'strategy_id': 'STRAT_SITE_COUNTRY_LIST',
                'priority': 1,
                'condition': '생산지 태그는 국가별 조회 우선'
            }
        ],
        
        # 이벤트 태그 (신규)
        'EVT_*': [
            {
                'strategy_id': 'STRAT_SITE_REGION_RISK',
                'priority': 1,
                'condition': '이벤트 태그는 지역 위험 분석 우선'
            }
        ]
    }
    
    # 3. 태그별 매핑 생성
    conn = sqlite3.connect(ontology_db_path)
    cursor = conn.cursor()
    
    generated_count = 0
    skipped_count = 0
    
    for tag in unique_tags:
        tag_id = tag['tag_id']
        tag_type = tag.get('tag_type', 'UNKNOWN')
        target_region = tag.get('target_region', 'KR')
        
        # 패턴 매칭으로 전략 결정
        strategies = None
        for pattern, strats in TAG_TYPE_STRATEGY_MAP.items():
            if pattern.endswith('*'):
                prefix = pattern[:-1]
                if tag_id.startswith(prefix):
                    strategies = strats
                    break
            elif pattern == tag_id:
                strategies = strats
                break
        
        if not strategies:
            print(f'  [SKIP] {tag_id}: 매칭되는 패턴 없음')
            skipped_count += 1
            continue
        
        # 이미 매핑된 태그인지 확인
        cursor.execute("""
            SELECT COUNT(*) FROM TAG_SEARCH_STRATEGY_MAP 
            WHERE tag_id = ? AND target_region = ?
        """, (tag_id, target_region))
        
        if cursor.fetchone()[0] > 0:
            print(f'  [EXIST] {tag_id}: 이미 매핑됨')
            continue
        
        # 전략 매핑 INSERT
        for strategy in strategies:
            mapping_id = f"MAP_{tag_id}_{strategy['strategy_id']}_{target_region}"
            
            cursor.execute("""
                INSERT INTO TAG_SEARCH_STRATEGY_MAP (
                    mapping_id, tag_id, target_region, strategy_id,
                    condition_description, priority, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                mapping_id,
                tag_id,
                target_region,
                strategy['strategy_id'],
                strategy['condition'],
                strategy['priority']
            ))
            
            generated_count += 1
            print(f'  [NEW] {tag_id} → {strategy["strategy_id"]} (P{strategy["priority"]})')
    
    conn.commit()
    conn.close()
    
    print(f'\n생성 완료: {generated_count}개 매핑 추가, {skipped_count}개 스킵')
```

### 6.3 태그 타입별 전략 매핑 규칙

| 태그 패턴 | 전략 1 (P1) | 전략 2 (P2) | 설명 |
|----------|------------|------------|------|
| **RAW_*** | RAW_MATERIAL_SITE_IMPACT | RAW_MATERIAL_FULL_CHAIN | 원자재는 생산지 영향 우선 → 전체 공급망 추적 |
| **MAT_*** | MATERIAL_SITE_TRACE | MATERIAL_COMPOSITION | 자재는 생산지 추적 우선 → 구성 분석 |
| **SUP_*** | SUPPLIER_SITE_LIST | SUPPLIER_RAW_MATERIAL_LIST | 협력사는 생산지 조회 우선 → 원자재 공급 현황 |
| **SITE_*** | SITE_COUNTRY_LIST | - | 생산지/국가는 국가별 조회만 |
| **EVT_*** | SITE_REGION_RISK | - | 이벤트는 지역 위험 분석 우선 |

### 6.4 누락 태그 처리 전략

**현재 누락된 13개 태그 처리:**

| 태그 ID | 패턴 | 자동 매핑 전략 | 우선순위 |
|---------|------|--------------|---------|
| RAW_ABRASIVE | RAW_* | STRAT_RAW_MATERIAL_SITE_IMPACT | P1 |
| MAT_트랙_에칭액 | MAT_* | STRAT_MATERIAL_SITE_TRACE | P1 |
| MAT_슬러리 | MAT_* | STRAT_MATERIAL_SITE_TRACE | P1 |
| SUP_메르크KGaA_(반도체재료) | SUP_* | STRAT_SUPPLIER_SITE_LIST | P1 |
| SUP_바스프(BASF)_코팅솔루션 | SUP_* | STRAT_SUPPLIER_SITE_LIST | P1 |
| SUP_DE118_메르크그룹 | SUP_* | STRAT_SUPPLIER_SITE_LIST | P1 |
| SUP_토카이카본전극 | SUP_* | STRAT_SUPPLIER_SITE_LIST | P1 |
| SUP_DE072_에보닉 | SUP_* | STRAT_SUPPLIER_SITE_LIST | P1 |
| EVT_공장_가동 | EVT_* | STRAT_SITE_REGION_RISK | P1 |
| EVT_산불재난 | EVT_* | STRAT_SITE_REGION_RISK | P1 |
| EVT_인수합병 | EVT_* | STRAT_SITE_REGION_RISK | P1 |
| EVT_질병확산 | EVT_* | STRAT_SITE_REGION_RISK | P1 |
| EVT_ENTITY_LIST | EVT_* | STRAT_SITE_REGION_RISK | P1 |

→ **자동 생성으로 13개 모두 해결 가능**

### 6.5 실행 흐름

```python
# populate_metadata.py에 추가

def run(self):
    """메타데이터 자동 생성 실행"""
    print('[Step 1] supply_chain.db 분석...')
    tables = self.extract_tables()
    columns = self.extract_columns(tables)
    fks = self.extract_foreign_keys(tables)
    
    print('[Step 2] ontology_layer.db 연결...')
    conn = self.connect_ontology_db()
    
    print('[Step 3] DB_TABLE_METADATA 생성...')
    self.populate_table_metadata(conn, tables)
    
    print('[Step 4] DB_COLUMN_METADATA 생성...')
    self.populate_column_metadata(conn, columns, fks)
    
    print('[Step 5] DB_TABLE_RELATIONSHIP 생성...')
    self.populate_relationships(conn, fks)
    
    print('[Step 6] TAG_SEARCH_STRATEGY_MAP 자동 생성...')  # 신규 추가
    self.auto_generate_tag_mappings(conn)
    
    print('[Step 7] V_ENTITY_HIERARCHY 뷰 생성...')
    self.create_hierarchy_view(conn)
    
    print('[Step 8] 검증...')
    self.validate(conn)
    
    conn.close()
    print('완료!')
```

### 6.6 예상 출력

```
[Step 6] TAG_SEARCH_STRATEGY_MAP 자동 생성...
  Agent_2 출력 분석: 22개 고유 태그 발견
  
  [EXIST] RAW_SPECIAL_GAS: 이미 매핑됨
  [EXIST] RAW_SEMICONDUCTOR_METAL: 이미 매핑됨
  [EXIST] RAW_ETCHANT: 이미 매핑됨
  [NEW] RAW_ABRASIVE → STRAT_RAW_MATERIAL_SITE_IMPACT (P1)
  [NEW] RAW_ABRASIVE → STRAT_RAW_MATERIAL_FULL_CHAIN (P2)
  
  [NEW] MAT_트랙_에칭액 → STRAT_MATERIAL_SITE_TRACE (P1)
  [NEW] MAT_트랙_에칭액 → STRAT_MATERIAL_COMPOSITION (P2)
  [NEW] MAT_슬러리 → STRAT_MATERIAL_SITE_TRACE (P1)
  [NEW] MAT_슬러리 → STRAT_MATERIAL_COMPOSITION (P2)
  
  [NEW] SUP_메르크KGaA_(반도체재료) → STRAT_SUPPLIER_SITE_LIST (P1)
  [NEW] SUP_메르크KGaA_(반도체재료) → STRAT_SUPPLIER_RAW_MATERIAL_LIST (P2)
  [NEW] SUP_바스프(BASF)_코팅솔루션 → STRAT_SUPPLIER_SITE_LIST (P1)
  [NEW] SUP_바스프(BASF)_코팅솔루션 → STRAT_SUPPLIER_RAW_MATERIAL_LIST (P2)
  (협력사 태그 3개 더...)
  
  [NEW] EVT_공장_가동 → STRAT_SITE_REGION_RISK (P1)
  [NEW] EVT_산불재난 → STRAT_SITE_REGION_RISK (P1)
  [NEW] EVT_인수합병 → STRAT_SITE_REGION_RISK (P1)
  (이벤트 태그 3개 더...)
  
  [EXIST] SITE_CN: 이미 매핑됨
  [EXIST] SITE_US: 이미 매핑됨
  (SITE 태그들은 기존 매핑 유지)
  
생성 완료: 26개 매핑 추가, 0개 스킵

최종 통계:
  - 기존 매핑: 29개
  - 신규 추가: 26개
  - 총 매핑: 55개
  - Fallback 예상 감소: 59.1% → 0%
```

---

## 7. 검증 단계

### 6.1 검증 항목

```python
def validate(conn: sqlite3.Connection):
    """생성된 메타데이터 검증"""
    cursor = conn.cursor()
    
    print('\n=== 검증 결과 ===')
    
    # 1. 레코드 수 확인
    table_count = cursor.execute("SELECT COUNT(*) FROM DB_TABLE_METADATA").fetchone()[0]
    column_count = cursor.execute("SELECT COUNT(*) FROM DB_COLUMN_METADATA").fetchone()[0]
    rel_count = cursor.execute("SELECT COUNT(*) FROM DB_TABLE_RELATIONSHIP").fetchone()[0]
    
    print(f'✓ DB_TABLE_METADATA: {table_count}개 테이블')
    print(f'✓ DB_COLUMN_METADATA: {column_count}개 컬럼')
    print(f'✓ DB_TABLE_RELATIONSHIP: {rel_count}개 관계')
    
    # 2. semantic_type 분포
    cursor.execute("""
        SELECT semantic_type, COUNT(*) 
        FROM DB_COLUMN_METADATA 
        GROUP BY semantic_type
    """)
    
    print('\nsemantic_type 분포:')
    for row in cursor.fetchall():
        print(f'  - {row[0] or "NULL"}: {row[1]}개')
    
    # 3. FK 무결성 검증
    cursor.execute("""
        SELECT COUNT(*) 
        FROM DB_COLUMN_METADATA 
        WHERE is_foreign_key = 1 
          AND (references_table IS NULL OR references_column IS NULL)
    """)
    
    invalid_fk = cursor.fetchone()[0]
    if invalid_fk > 0:
        print(f'\n⚠ 경고: FK 정보 누락 {invalid_fk}개')
    else:
        print(f'\n✓ FK 무결성 검증 통과')
    
    # 4. llm_description 샘플 확인
    cursor.execute("""
        SELECT table_name, llm_description 
        FROM DB_TABLE_METADATA 
        LIMIT 2
    """)
    
    print('\nllm_description 샘플:')
    for row in cursor.fetchall():
        print(f'\n[{row[0]}]')
        print(f'{row[1][:100]}...')
```

---

## 7. 실행 방법

### 7.1 스크립트 실행

```bash
# 온톨로지 DB 생성
python scripts/create_ontology_layer.py

# 메타데이터 자동 생성
python scripts/populate_metadata.py
```

### 7.2 예상 출력

```
============================================================
온톨로지 메타데이터 자동 생성
============================================================

[Step 1] supply_chain.db 분석...
  ✓ 테이블 7개 추출
  ✓ 컬럼 68개 추출
  ✓ FK 관계 6개 추출

[Step 2] ontology_layer.db 연결...
  ✓ ATTACH 완료

[Step 3] DB_TABLE_METADATA 생성...
  - SUPPLIER_MASTER: 120개 레코드
  - SITE_MASTER: 250개 레코드
  - MATERIAL_MASTER: 400개 레코드
  - RAW_MATERIAL_MASTER: 114개 레코드
  - SITE_MATERIAL_MAP: 625개 레코드
  - MATERIAL_RAW_MATERIAL_MAP: 1400개 레코드
  - SUPPLIER_RAW_MATERIAL_MAP: 789개 레코드
  ✓ 7개 테이블 메타데이터 생성 완료

[Step 4] DB_COLUMN_METADATA 생성...
  - SUPPLIER_MASTER: 14개 컬럼
  - SITE_MASTER: 14개 컬럼
  - MATERIAL_MASTER: 8개 컬럼
  - RAW_MATERIAL_MASTER: 8개 컬럼
  - SITE_MATERIAL_MAP: 9개 컬럼
  - MATERIAL_RAW_MATERIAL_MAP: 8개 컬럼
  - SUPPLIER_RAW_MATERIAL_MAP: 7개 컬럼
  ✓ 68개 컬럼 메타데이터 생성 완료

[Step 5] DB_TABLE_RELATIONSHIP 생성...
  ✓ 6개 관계 생성 완료

[Step 6] V_ENTITY_HIERARCHY 뷰 생성...
  ✓ 뷰 생성 완료 (2,814개 계층 관계)

[Step 7] 검증...

=== 검증 결과 ===
✓ DB_TABLE_METADATA: 7개 테이블
✓ DB_COLUMN_METADATA: 68개 컬럼
✓ DB_TABLE_RELATIONSHIP: 6개 관계

semantic_type 분포:
  - ENTITY_CODE: 7개
  - ENTITY_NAME: 14개
  - LOCATION: 8개
  - TYPE_CATEGORY: 4개
  - QUANTITY: 6개
  - FLAG: 12개
  - TIMESTAMP: 14개
  - NULL: 3개

✓ FK 무결성 검증 통과

llm_description 샘플:

[SUPPLIER_MASTER]
SUPPLIER_MASTER는 협력사(법인) 기본 정보를 관리하는 마스터 테이블입니다. 협력사명, 국가, 지역, 좌표 등의 정보를 포함합니다...

[SITE_MASTER]
SITE_MASTER는 생산 거점(Site, Plant, 창고 등) 정보를 관리하는 마스터 테이블입니다. 각 협력사는 1~3개의 생산지를 가질 수 있습니다...

============================================================
완료!
============================================================
```

---

## 8. 수동 보정 권장 사항

자동 생성 후 다음 항목은 수동 검토 및 보정을 권장합니다:

### 8.1 우선순위 높음

1. **테이블 llm_description**
   - 템플릿 기반이므로 도메인 지식 추가 권장
   - 특히 테이블 간 관계 설명 보강

2. **컬럼 llm_description**
   - 중요 컬럼(name_kor, country 등)은 상세 설명 추가

3. **search_priority**
   - 기본값(3)에서 도메인 지식 기반으로 조정

### 8.2 우선순위 중간

4. **semantic_type**
   - NULL 값 확인 및 수동 분류

5. **search_hint**
   - 복잡한 검색 조건이 필요한 컬럼은 힌트 보강

### 8.3 우선순위 낮음

6. **typical_join_path**
   - 자동 생성 결과 확인 후 필요시 수정

7. **sample_values**
   - 민감한 데이터 포함 여부 확인

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-06-26 | 초기 작성<br>- 자동 생성 대상 및 규칙 정의<br>- 추론 규칙 및 템플릿 명세<br>- 검증 방법 정의 |
| 1.1 | 2026-07-14 | TAG_SEARCH_STRATEGY_MAP 자동 생성 추가<br>- 6절 신규 추가: 태그 패턴 기반 전략 자동 매핑<br>- 태그 타입별 매핑 규칙 정의 (RAW_*, MAT_*, SUP_*, SITE_*, EVT_*)<br>- 누락 태그 13개 자동 처리 방안<br>- Agent_2 출력 연동 로직 추가<br>- Fallback 전략 최소화 (59.1% → 0% 목표) |

---

**작성자**: Claude Code (Sonnet 4.5)  
**최종 수정**: 2026-06-26
