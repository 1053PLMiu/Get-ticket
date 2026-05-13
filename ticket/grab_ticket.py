"""

12306 抢票小工具Edge版（仅供学习使用） 
功能：首次扫码登录 → 保存Cookie → 下次免登录 → 自动查票 → 有余票自动预订
      → 按指定顺序操作（提交→学生票提示→选座→确认） → 等待手动支付
"""

import time
import json
import os
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException


# ==================== 配置区域1（自己更改） ====================
CONFIG = {
    "from_station": "玉林北",            # 如广州南....不需要“站”字
    "to_station": "南宁东",             # 如广州南....不需要“站”字
    "train_date": "2026-05-16",         # 如2026-05-16
    "train_numbers": ["D8250","G1234", "D5678"],     # 监控特定车次，如 ["G1234", "D5678"]
    "seat_types": ["二等座", "一等座"],      # 优先级顺序，程序会按列表顺序尝试预订
    "passenger_names": ["张三"],       # 填写需要购买票人的名字
    "query_interval": 3,          # 查票间隔（秒），建议 >=3
    "headless": False,
}
# ==================== 配置区域2（自己更改） ====================
STATION_CODE = {
    "广州南": "IZQ",             # ！！！如果里面没有你的车站，请自己添加，格式 "车站名称": "车站代码"
    "贵港": "GGZ",               # 1.车站代码可以在文件夹使用“站点获取运行.bat”获得（运行前记得修改“ZD.py”里你想要的站点名称）
    "北京南": "VNP",             # 2.车站代码也可以在浏览器开发者工具的网络请求中找到，具体查看说明文档
    "上海虹桥": "AOH",
    "深圳北": "IOQ",
    "长沙南": "CWQ",
    "武汉": "WHN",
    "南宁东": "NFZ",
    "玉林": "YLZ",
    "玉林北": "ABZ",
    "兴业": "SNZ",
    "博白": "BBZ",
    "陆川": "LKZ",
}

COOKIE_FILE = "12306_cookies.json"
LOGIN_URL = "https://kyfw.12306.cn/otn/resources/login.html"
QUERY_URL = "https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc"
INDEX_URL = "https://kyfw.12306.cn/otn/view/index.html"


class TicketGrabber:
    def __init__(self, config):
        self.config = config
        self.driver = None

    # ---------- 浏览器驱动（速度优化） ----------
    def init_driver(self):
        options = webdriver.EdgeOptions()
        if self.config["headless"]:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")               # 跳过首次运行引导
        options.add_argument("--disable-gpu")                # 禁用 GPU 加速，减少渲染耗费
        options.add_argument("--disable-dev-shm-usage")      # 防止内存不足闪退
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # ==================== 配置区域3（按需修改） ====================
        # ===== 修改为你的 msedgedriver.exe 真实路径 =====
        driver_path = r"C:\Users\25762\Desktop\ticket\msedgedriver.exe"
        service = Service(executable_path=driver_path)
        self.driver = webdriver.Edge(service=service, options=options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 8)           # 默认超时调低至 8s

    # ---------- Cookie 管理 ----------
    def save_cookies(self):
        try:
            cookies = self.driver.get_cookies()
            with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False)
            print("🍪 Cookie 已保存")
        except Exception as e:
            print(f"保存 Cookie 失败：{e}")

    def load_cookies(self):
        if not os.path.exists(COOKIE_FILE):
            return False
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            self.driver.get(INDEX_URL)
            time.sleep(0.5)   # 短暂等待页面初始化
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    continue
            print("🍪 已加载 Cookie，验证登录状态...")
            self.driver.get(INDEX_URL)
            # 等待页面跳转到 index，最多 10s
            WebDriverWait(self.driver, 10).until(EC.url_contains("index.html"))
            if "login" not in self.driver.current_url:
                print("✅ 自动登录成功！")
                return True
            else:
                print("⚠️ Cookie 已失效，需要重新登录")
                os.remove(COOKIE_FILE)
                return False
        except TimeoutException:
            print("⚠️ Cookie 验证超时，重新登录")
            return False
        except Exception as e:
            print(f"加载 Cookie 失败：{e}")
            return False

    def login(self):
        if self.load_cookies():
            return True
        print("📱 正在打开登录页，请使用12306 APP扫码...")
        self.driver.get(LOGIN_URL)
        try:
            WebDriverWait(self.driver, 120).until(EC.url_contains("index.html"))
            print("✅ 登录成功！")
            self.save_cookies()
            return True
        except TimeoutException:
            print("❌ 登录超时，请重新运行")
            return False

    # ---------- 站点与日期设置 ----------
    def input_station(self, from_span, to_span):
        from_code = STATION_CODE.get(from_span)
        to_code = STATION_CODE.get(to_span)
        if not from_code or not to_code:
            print(f"错误：未找到车站代码 {from_span} 或 {to_span}")
            return False
        self.driver.execute_script("""
            document.querySelector('#fromStationText').readOnly = false;
            document.querySelector('#toStationText').readOnly = false;
            document.querySelector('#fromStationText').value = arguments[0];
            document.querySelector('#toStationText').value = arguments[1];
            document.querySelector('#fromStation').value = arguments[2];
            document.querySelector('#toStation').value = arguments[3];
        """, from_span, to_span, from_code, to_code)
        print(f"站点已设置：{from_span}({from_code}) -> {to_span}({to_code})")
        return True

    def set_date(self, date_str):
        self.driver.execute_script("document.querySelector('#train_date').readOnly = false;")
        date_input = self.driver.find_element(By.ID, "train_date")
        date_input.clear()
        date_input.send_keys(date_str)

    # ---------- 车票查询 ----------
    def query_tickets(self):
        query_btn = self.driver.find_element(By.ID, "query_ticket")
        self.driver.execute_script("arguments[0].click();", query_btn)
        print("🔘 查询中...")
        try:
            # 等待表格出现，最多 5 秒
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "queryLeftTable"))
            )
            time.sleep(0.5)   # 给 JS 渲染留一丁点时间
        except TimeoutException:
            print("⏰ 查询超时，表格未加载。")
            return []

        trains = self.driver.find_elements(By.XPATH,
            "//table[@id='queryLeftTable']//tr[contains(@id,'ticket_')]")
        if not trains:
            trains = self.driver.find_elements(By.CSS_SELECTOR, "#queryLeftTable tr[id^='ticket_']")
        if not trains:
            trains = self.driver.find_elements(By.CSS_SELECTOR, "#queryLeftTable tbody tr")
        if not trains:
            trains = self.driver.find_elements(By.XPATH, "//table[@id='queryLeftTable']//tr[@class]")

        print(f"🔎 找到 {len(trains)} 个车次行")
        if trains:
            print(f"   首行预览: {trains[0].text[:80]}")

        ticket_list = []
        for train in trains:
            try:
                tds = train.find_elements(By.XPATH, "./td")
                if len(tds) < 10:
                    continue
                train_number = tds[0].find_element(By.XPATH, ".//a").text.strip()
                col_map = {"商务座": 1, "一等座": 3, "二等座": 4, "无座": 10}
                seats = {}
                for seat, idx in col_map.items():
                    if idx < len(tds):
                        seats[seat] = tds[idx].text.strip()
                    else:
                        seats[seat] = "无"
                ticket_list.append((train_number, train, seats))
            except Exception as e:
                print(f"⚠️ 解析某行出错：{e}")
                continue
        print(f"📋 成功解析车票数: {len(ticket_list)}")
        return ticket_list

    # ---------- 自动选座 ----------
    def select_seat_preference(self, seat_type):
        if seat_type == "二等座":
            seat_priority = ['F', 'D', 'C', 'A', 'B']
        elif seat_type == "一等座":
            seat_priority = ['F', 'D', 'C', 'A']
        else:
            print(f"   ⚠️ 未知席位类型 {seat_type}，跳过选座")
            return False

        print(f"   🪑 自动选座（优先级: {' > '.join(seat_priority)}）")

        try:
            # 点击选座按钮（可能已经在页面中）
            seat_btn = None
            for txt in ["选座服务", "选择座位"]:
                try:
                    seat_btn = self.driver.find_element(By.XPATH,
                        f"//a[contains(text(),'{txt}')] | //span[contains(text(),'{txt}')]")
                    if seat_btn.is_displayed():
                        break
                except:
                    continue
            if seat_btn:
                self.driver.execute_script("arguments[0].click();", seat_btn)
                print("   ✅ 已点击选座按钮")
                time.sleep(0.5)

            # 等待座位面板出现（最多 3s）
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".seat-layer, .seat-list"))
            )
            print("   ✅ 选座界面已出现")

            # 按优先级点击可选座位
            selected = False
            for s in seat_priority:
                seats = self.driver.find_elements(By.XPATH,
                    f"//li[contains(text(),'{s}') and not(contains(@class,'no')) and not(@disabled)] | "
                    f"//div[contains(text(),'{s}') and not(contains(@class,'no')) and not(@disabled)]"
                )
                for seat in seats:
                    if seat.is_displayed() and seat.is_enabled():
                        self.driver.execute_script("arguments[0].click();", seat)
                        print(f"   ✔️ 已选择座位: {s}")
                        selected = True
                        break
                if selected:
                    break

            if not selected:
                print("   ⚠️ 没有符合优先级的可选座位，将随机分配")
            # 选座面板可能需要手动关闭，尝试点击“确认”或“关闭”
            try:
                close_btn = self.driver.find_element(By.XPATH,
                    "//div[contains(@class,'seat-layer')]//a[contains(text(),'确定') or contains(text(),'关闭')]")
                if close_btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", close_btn)
                    print("   ✅ 已关闭选座面板")
            except:
                pass
            return True
        except TimeoutException:
            print("   ⚠️ 选座界面未出现，跳过")
            return False
        except Exception as e:
            print(f"   ⚠️ 选座流程异常: {e}")
            return False

    # ---------- 极速确认对话框处理----------
    def _handle_confirm_dialog(self):
        """快速处理订单确认弹窗，优先使用已知 ID，降低延迟"""
        # 先快速检测对话框是否出现（超时 1.5 秒）
        try:
            WebDriverWait(self.driver, 1.5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@id,'order') and contains(@class,'dialog')] | "
                               "//div[@id='order_confirm'] | //div[contains(@class,'pop') and contains(@class,'confirm')] "
                               "| //div[contains(@id,'popup') and contains(@class,'show')]")
                )
            )
            print("   ✅ 确认对话框已出现")
        except TimeoutException:
            pass  # 可能没有弹窗，直接继续尝试点击按钮

        # 极速定位器列表，按命中率高、速度快排序，每个只等 0.8 秒
        fast_locators = [
            # 1. 已知的实际 ID（优先）
            (By.ID, "qr_submit_id"),
            # 2. 其他常见 ID
            (By.ID, "order_confirm_popup_submit"),
            (By.ID, "pop_confirm_submit"),
            # 3. 精确文本按钮
            (By.XPATH, "//a[text()='确认'] | //button[text()='确认']"),
            # 4. 带有“确”字的按钮
            (By.XPATH, "//a[contains(text(),'确')] | //button[contains(text(),'确')]"),
        ]

        for by, value in fast_locators:
            try:
                btn = WebDriverWait(self.driver, 0.8).until(
                    EC.element_to_be_clickable((by, value))
                )
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    print(f"   ✅ 已点击确认按钮 [{value}]")
                    time.sleep(0.3)
                    return True
            except TimeoutException:
                continue

        # 如果还没点到，再用更宽泛的 onclick 匹配，但只试一次
        try:
            btn = WebDriverWait(self.driver, 1).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(@onclick,'confirm')] | //button[contains(@onclick,'confirm')]")
                )
            )
            if btn.is_displayed():
                self.driver.execute_script("arguments[0].click();", btn)
                print("   ✅ 备选 clicked 确认按钮")
                time.sleep(0.3)
                return True
        except:
            pass

        return False

    # ---------- 预订车票（使用极速确认） ----------
    def book_ticket(self, train_element, seat_type, passenger_name):
        try:
            # 1. 点击预订，跳转订单页
            print("   1️⃣ 点击预订按钮...")
            book_btn = train_element.find_element(By.XPATH, ".//a[contains(text(),'预订')]")
            self.driver.execute_script("arguments[0].scrollIntoView();", book_btn)
            time.sleep(0.3)
            self.driver.execute_script("arguments[0].click();", book_btn)
            print("   ✅ 预订按钮已点击，等待跳转...")

            time.sleep(2)   # 留出跳转时间，通常很快
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.driver.switch_to.window(handles[-1])
            cur_url = self.driver.current_url
            print(f"   📄 当前URL: {cur_url}")
            if "leftTicket" in cur_url or "login" in cur_url:
                print("   ⚠️ 页面未跳转到订单页（可能被拦截）")
                return False

            # 2. 等待乘客选择区（超时 8s 即可）
            print("   2️⃣ 等待乘客选择区...")
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.ID, "normal_passenger_id"))
                )
                print("   ✅ 乘客选择区已出现")
            except TimeoutException:
                print("   ❌ 乘客选择区加载超时")
                return False

            # 3. 勾选乘车人
            print(f"   3️⃣ 选择乘车人: {passenger_name}")
            passenger_found = False
            checkboxes = self.driver.find_elements(
                By.XPATH,
                f"//label[contains(., '{passenger_name}')]/input[@type='checkbox']"
            )
            if not checkboxes:
                checkboxes = self.driver.find_elements(
                    By.XPATH,
                    f"//input[@type='checkbox'][contains(@id,'normalPassenger')]"
                    f"[following-sibling::label[contains(text(), '{passenger_name}')] "
                    f"or preceding-sibling::label[contains(text(), '{passenger_name}')]]"
                )
            for cb in checkboxes:
                if not cb.is_selected():
                    self.driver.execute_script("arguments[0].click();", cb)
                    print(f"   ✔️ 已勾选: {passenger_name}")
                else:
                    print(f"   ⚡ {passenger_name} 之前已选中")
                passenger_found = True
                break
            if not passenger_found:
                print("   ❌ 未找到该乘车人复选框")
                return False

            # 4. 点击提交订单按钮
            print("   4️⃣ 点击提交订单按钮...")
            try:
                submit_btn = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((By.ID, "submitOrder_id"))
                )
                self.driver.execute_script("arguments[0].click();", submit_btn)
                print("   ✅ 提交按钮已点击")
            except TimeoutException:
                print("   ❌ 提交按钮不可点击或未出现")
                return False

            # 5. 处理学生票提示（若弹出）
            print("   5️⃣ 检查学生票提示...")
            try:
                student_popup = WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'学生票')]"))
                )
                confirm_btns = self.driver.find_elements(By.XPATH,
                    "//a[contains(text(),'确定')] | //a[contains(text(),'确认')] | //button[contains(text(),'确定')]")
                for btn in confirm_btns:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        print("   ✅ 已点击学生票提示的确定按钮")
                        time.sleep(0.3)
                        break
            except TimeoutException:
                print("   ℹ️ 未出现学生票提示")

            # 6. 自动选座
            print("   6️⃣ 执行自动选座...")
            self.select_seat_preference(seat_type)

            # 7. 极速确认对话框检测
            print("   7️⃣ 检测确认订单对话框...")
            confirm_handled = self._handle_confirm_dialog()
            if not confirm_handled:
                print("   ⚠️ 未检测到确认按钮，可能已直接提交，继续等待支付")

            # 8. 等待支付页面出现
            print("   8️⃣ 等待支付页面...")
            try:
                WebDriverWait(self.driver, 20).until(EC.url_contains("payOrder"))
                print("🎉 订单提交成功！请尽快手动支付。")
                return True
            except TimeoutException:
                print("   ⚠️ 未跳转到支付页（可能需滑块验证或排队），返回重试")
                return False

        except Exception as e:
            print(f"💥 预订流程异常: {e}")
            traceback.print_exc()
            return False

    # ---------- 主循环 ----------
    def run(self):
        self.init_driver()
        try:
            if not self.login():
                return

            print("🚀 进入查票页面...")
            self.driver.get(QUERY_URL)
            WebDriverWait(self.driver, 8).until(EC.presence_of_element_located((By.ID, "fromStationText")))

            if not self.input_station(self.config["from_station"], self.config["to_station"]):
                return
            self.set_date(self.config["train_date"])

            print(f"🎯 开始监控 {self.config['train_date']} {self.config['from_station']}→{self.config['to_station']}")
            while True:
                tickets = self.query_tickets()
                booked = False
                for t_number, t_elem, seats in tickets:
                    if t_number not in self.config["train_numbers"]:
                        continue
                    print(f"🚆 车次 {t_number} 余票：{seats}")
                    for seat in self.config["seat_types"]:
                        count = seats.get(seat, "无")
                        if count.isdigit() and int(count) > 0 or "有" in count:
                            print(f"   🎫 {seat}有票({count})，尝试预订！")
                            if self.book_ticket(t_elem, seat, self.config["passenger_names"][0]):
                                print("\n✅ 抢票流程成功，请勿关闭浏览器，手动完成支付。")
                                print("💡 按下 Ctrl+C 可退出本程序（浏览器不会关闭）")
                                while True:
                                    time.sleep(1)
                            else:
                                print("   预订失败，继续监控...")
                                booked = True
                                break
                        else:
                            print(f"   {seat}：{count}")
                    if booked:
                        break
                time.sleep(self.config["query_interval"])
                if "leftTicket" not in self.driver.current_url:
                    print("🔄 页面异常，重新进入查询页...")
                    self.driver.get(QUERY_URL)
                    WebDriverWait(self.driver, 8).until(EC.presence_of_element_located((By.ID, "fromStationText")))
                    self.input_station(self.config["from_station"], self.config["to_station"])
                    self.set_date(self.config["train_date"])
        except KeyboardInterrupt:
            print("\n⏹️ 用户手动中断，程序结束。")
        finally:
            print("浏览器保持打开，可手动关闭。")


if __name__ == "__main__":
    grabber = TicketGrabber(CONFIG)
    grabber.run()