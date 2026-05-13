import requests
import re

def fetch_station_codes():
    url = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js?station_version=1.9352"
    resp = requests.get(url)
    data = resp.text
    # 提取核心字符串
    raw = re.search(r"var station_names\s*=\s*'(.*)'", data).group(1)
    # 分割
    stations = raw.split('@')
    code_dict = {}
    for s in stations:
        if not s:
            continue
        parts = s.split('|')
        if len(parts) >= 3:
            name = parts[1]
            code = parts[2]
            code_dict[name] = code
    return code_dict

all_codes = fetch_station_codes()
# 在下面按照相同的格式填入你想要的站点
wanted = ['北京南', '上海虹桥', '深圳北', '长沙南', '武汉', '南宁东', '玉林', '玉林北', '兴业', '博白', '陆川']
for w in wanted:
    print(f'    "{w}": "{all_codes.get(w, "未找到")}",')
# 打印总数
print(f"\n共获取 {len(all_codes)} 个车站代码。")