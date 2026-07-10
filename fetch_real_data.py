"""
fetch_real_data.py
从世界银行 API 获取 GDP、人口数据
从本地 OWID CSV 文件获取 CO₂ 排放数据
并保存为 historical_data_real.csv
"""
import pandas as pd
import requests
import sys
import os

print("🚀 开始获取真实历史数据...")

# ==================== 通用函数 ====================
def fetch_worldbank(indicator, name):
    """从世界银行 API 获取指定指标数据，返回 DataFrame"""
    url = f"https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=30000"
    print(f"   正在获取 {name} 数据...")
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            print(f"   ❌ 请求失败，状态码: {resp.status_code}")
            return None
        data = resp.json()
        if not data or len(data) < 2:
            print(f"   ❌ 返回数据为空")
            return None
        records = []
        for item in data[1]:
            if item.get('value') is not None:
                country = item['country']['value']
                year = int(item['date'])
                records.append({'country': country, 'year': year, name: item['value']})
        df = pd.DataFrame(records)
        print(f"   ✅ {name} 数据获取成功，共 {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"   ❌ 获取 {name} 时出错: {e}")
        return None

# ==================== 1. 获取 GDP 和人口 ====================
gdp_df = fetch_worldbank('NY.GDP.MKTP.CD', 'gdp')
pop_df = fetch_worldbank('SP.POP.TOTL', 'population')

# ==================== 2. 从本地文件获取碳排放数据 ====================
co2_df = None
local_co2_file = 'owid-co2-data.csv'

if os.path.exists(local_co2_file):
    print(f"   正在从本地文件 {local_co2_file} 读取碳排放数据...")
    try:
        raw = pd.read_csv(local_co2_file)
        # OWID 文件的常见列名：Entity, Code, Year, Annual CO2 emissions
        # 我们将其映射为标准列名
        column_mapping = {
            'Entity': 'country',
            'entity': 'country',
            'Year': 'year',
            'year': 'year',
            'Annual CO2 emissions': 'co2',
            'annual co2 emissions': 'co2',
            'Annual CO₂ emissions': 'co2',
            'co2': 'co2',
            'CO2': 'co2'
        }
        # 重命名存在的列
        rename_dict = {}
        for old, new in column_mapping.items():
            if old in raw.columns:
                rename_dict[old] = new
        if rename_dict:
            raw = raw.rename(columns=rename_dict)
        # 只保留需要的列
        if 'country' in raw.columns and 'year' in raw.columns and 'co2' in raw.columns:
            co2_df = raw[['country', 'year', 'co2']].copy()
            # 去除可能的汇总行（如 'World', 'Asia' 等非国家实体）
            co2_df = co2_df[~co2_df['country'].isin(['World', 'Asia', 'Europe', 'North America', 'South America', 'Africa', 'Oceania', 'International transport'])]
            co2_df['year'] = co2_df['year'].astype(int)
            # 单位已经是百万吨，无需转换
            print(f"   ✅ 碳排放数据读取成功，共 {len(co2_df)} 条记录")
        else:
            missing_cols = [c for c in ['country', 'year', 'co2'] if c not in raw.columns]
            print(f"   ⚠️ 本地文件缺少列: {missing_cols}，请检查文件格式。")
    except Exception as e:
        print(f"   ❌ 读取本地文件失败: {e}")
else:
    print(f"   ❌ 本地文件 {local_co2_file} 不存在，请将下载的 OWID 数据文件放在项目目录。")

# ==================== 3. 合并数据 ====================
print("🔄 正在合并数据...")
df_list = [df for df in [gdp_df, pop_df, co2_df] if df is not None]
if not df_list:
    print("❌ 没有获取到任何数据，请检查网络连接。")
    sys.exit(1)

merged = df_list[0]
for df in df_list[1:]:
    merged = merged.merge(df, on=['country', 'year'], how='outer')

print(f"   合并后总记录数: {len(merged)}")

# ==================== 4. 国家名称映射（英文 → 中文） ====================
name_map = {
    'China': '华夏',
    'United States': '美利坚',
    'Russian Federation': '俄罗斯',
    'Russia': '俄罗斯',
    'United Kingdom': '不列颠',
    'France': '法兰西',
    'Germany': '德意志',
    'Japan': '日本',
    'Italy': '意大利',
    'India': '印度',
    'Brazil': '巴西',
    'Canada': '加拿大',
    'Australia': '澳大利亚',
    'Argentina': '阿根廷',
    'Austria': '奥地利',
    'Hungary': '匈牙利',
    'Czechia': '捷克斯洛伐克',
    'Czech Republic': '捷克斯洛伐克',
    'Slovakia': '捷克斯洛伐克',
    'Turkey': '土耳其',
    'Spain': '西班牙',
    'Portugal': '葡萄牙',
    'Netherlands': '荷兰',
    'Belgium': '比利时',
    'Sweden': '瑞典',
    'Norway': '挪威',
    'Denmark': '丹麦',
    'Finland': '芬兰',
    'Poland': '波兰',
    'Ukraine': '乌克兰',
    'Belarus': '白俄罗斯',
    'Kazakhstan': '哈萨克斯坦',
    'Pakistan': '巴基斯坦',
    'Israel': '以色列',
    'South Africa': '南非',
    'Indonesia': '印尼',
    'Malaysia': '马来西亚',
    'Philippines': '菲律宾',
    'Thailand': '泰国',
    'Viet Nam': '越南',
    'Myanmar': '缅甸',
    'Laos': '老挝',
    'Cambodia': '柬埔寨',
    'Brunei': '文莱',
    'Singapore': '新加坡',
}
merged['country'] = merged['country'].map(name_map).fillna(merged['country'])

# ==================== 5. 单位转换 ====================
if 'gdp' in merged.columns:
    merged['gdp'] = merged['gdp'] / 1e9  # 美元 → 十亿
if 'population' in merged.columns:
    merged['population'] = merged['population'] / 1e6  # 人 → 百万
# OWID 数据中 co2 单位已经是百万吨，无需转换

# 按国家、年份排序，确保填充顺序正确
merged = merged.sort_values(['country', 'year'])

# 按国家分组，用前一年的值填充缺失的GDP和人口
merged['gdp'] = merged.groupby('country')['gdp'].ffill()
merged['population'] = merged.groupby('country')['population'].ffill()

# 填充后仍可能有最开头几年的 NaN（没有任何历史数据），可以删掉或填0
merged = merged.dropna(subset=['gdp', 'population'])

# 然后过滤所需国家和年份
target_countries = list(name_map.values())
merged = merged[(merged['country'].isin(target_countries)) &
                (merged['year'] >= 1900) &
                (merged['year'] <= 2025)]

# ==================== 7. 保存 ====================
if len(merged) > 0:
    merged = merged.ffill()
    merged.to_csv('historical_data_real.csv', index=False)
    print(f"✅ 数据已保存至 historical_data_real.csv，共 {len(merged)} 行")
    print("示例数据（前5行）：")
    print(merged.head())
else:
    print("❌ 过滤后无数据，请检查国家名称映射是否正确。")